"""Bounded inspection of real v5 packed choices, body subsets and conditional OUT.

No test runner, redraw, alternate FITS or installation. --continuation requires
new bindings and rejects any historical assignment mismatch before accepting OUT.
"""
import argparse
from collections import Counter, defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import hashlib
import subprocess
import time
import gzip
import json
from pathlib import Path
import signal
import struct
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def numeric(payload, part, key):
    value = payload[part][key]
    if not isinstance(value, bytes):
        return value
    formats = {'uint8': 'B', 'uint32': 'I', 'int32': 'i', 'uint64': 'Q', 'int64': 'q'}
    return [row[0] for row in struct.iter_unpack('<'+formats[payload['dtypes'][part+'.'+key]], value)]


def flatten(rows):
    result = []
    for row in rows:
        out = []
        for term in row:
            if term['kind'] == 'box':
                out.extend(term['margins'][k] for k in ('top', 'bottom', 'left', 'right'))
            elif term['kind'] == 'unit':
                out.append(0)
            elif term['kind'] in ('orientation', 'ident'):
                value = term['encoding_u32']
                out.append(value if value < 2**31 else value-2**32)
            else:
                out.append(term['value'])
        result.append(out)
    return sorted(result)


def inspect(record, base, args, context):
    import arclog
    from native_storage import load_native, materialize_pair
    r = materialize_pair(record, base)
    kept = r['evaluation']['kept_assignments']
    schemas = {}
    payloads = [*r['native'].values()]
    if r.get('full_replay', {}).get('gold'):
        payloads.append(load_native(r['full_replay']['gold'], base))
    for payload in payloads:
        ts = payload['tables']
        for names, types in zip(ts['det_relations'], ts['det_types'], strict=True):
            for name, ty in zip(names, types, strict=True):
                if name in schemas:
                    require(schemas[name] == ty, 'native DET schemas disagree: '+name)
                schemas[name] = ty
    decoded = []
    for assignment in kept:
        values = {}
        for det in assignment:
            name = det['relation']
            require(name in schemas, 'native evidence lacks full DET schema: '+name)
            terms = json.loads(arclog.StudyProgram.decode_rows_json(schemas[name], det['rows']))
            values[name] = dict(types=schemas[name], packed_rows=det['rows'], rows=terms)
        decoded.append(values)
    checked = 0
    subsets = {}
    for side, payload in r['native'].items():
        ts, es, assigned = payload['tables'], payload['entries'], payload['assigned']
        t = r['evaluation']['table_indices'][side+'_kept']
        names, types = ts['det_relations'][t], ts['det_types'][t]
        subsets[side] = names
        values = memoryview(payload['values']).cast('i')
        fields = {k: numeric(payload, 'entries', k) for k in ('table', 'model', 'example_kind', 'example_index')}
        af = {k: numeric(payload, 'assigned', k) for k in ('entry', 'det', 'rows', 'offset')}
        byentry = defaultdict(list)
        for i, entry in enumerate(af['entry']):
            byentry[entry].append(i)
        counters = defaultdict(lambda: -1)
        for entry, table in enumerate(fields['table']):
            if table != t:
                continue
            example = fields['example_kind'][entry], fields['example_index'][entry]
            if fields['model'][entry] == 0:
                counters[example] += 1
            choice = counters[example]
            require(0 <= choice < len(kept), 'native body entry lacks full choice index')
            require(len(byentry[entry]) == len(names), 'native body assignment omits DET')
            for i in byentry[entry]:
                d = af['det'][i]
                name = names[d]
                require(name in decoded[choice], 'body subset reads unknown held DET')
                require(types[d] == decoded[choice][name]['types'], 'body subset schema differs')
                width = ts['det_widths'][t][d]
                at, count = af['offset'][i], af['rows'][i]
                native = sorted(list(values[at+j*width:at+(j+1)*width]) for j in range(count))
                require(native == flatten(decoded[choice][name]['rows']), 'native body DET cells differ after Term::decode: '+name)
                checked += 1
    result = dict(task=r['task'], case=r['case'], body=r['identity']['body'], choices=len(kept),
                  full_dets=sum(map(len, decoded)), body_assignment_checks=checked, body_read_subsets=subsets,
                  term_decode='pass')
    if hasattr(arclog.StudyProgram, 'choice_evidence_json'):
        settings = arclog.DecodeSettings(deadline_seconds=args.native_seconds, rule_tests=False)
        key = r['programs']['gold']
        if key not in context['gold']:
            context['gold'][key] = arclog.StudyProgram.from_sexp(key, settings).decode_source()
            while len(context['gold']) > 4:
                context['gold'].popitem(last=False)
        gold = context['gold'][key]
        mutant = gold.construct_identity(json.dumps(r['identity']))
        for side, program in (('gold', gold), ('mutant', mutant.as_program())):
            evidence = json.loads(program.choice_evidence_json(json.dumps(kept)))
            require(evidence['complete'], 'native choices incomplete')
            body = next(b for b in evidence['bodies'] if b['body_path'] == r['identity']['body'])
            require(body['source_names'] == subsets[side], 'compiled body reads differ from recorded native metadata')
            for choice, expected in zip(evidence['choices'], decoded, strict=True):
                actual = {d['source_name']: d for d in choice['full_assignment']}
                require(set(actual) == set(expected), 'full choices omit DETs')
                for name in expected:
                    require(actual[name]['rows'] == expected[name]['rows'], 'native full choice decode differs')
            if hasattr(program, 'out_bindings_json'):
                binding = json.loads(program.out_bindings_json())
                require(binding['complete'] and len(binding['columns']) == 2, 'OUT projection incomplete')
                require(all(c['occurrences'] and c['body_column'] >= 0 for c in binding['columns']), 'OUT binding lacks original label path')
            else:
                result['out_binding'] = 'requires_new_wheel'
        result['native_choices'] = 'pass'
        if args.continuation or args.components:
            if context['evaluator'] is None:
                context['evaluator'] = arclog.StudyTaskEvaluator(r['task'], str(args.tasks), settings, compact=False)
            evaluator = context['evaluator']
            point = next(p for p in gold.points() if p.body_path == r['identity']['body'])
            evaluator.evaluate_pair(gold, point, mutant)
            if args.components:
                component, gt, mt = arclog.study_component_tables(evaluator, gold, mutant, json.dumps(kept))
                component = json.loads(component)
                for side, table in (('gold', gt), ('mutant', mt)):
                    require(component[side+'_status']['status'] == 'complete', side+' component tables stopped/faulted')
                    axes = {k: list(memoryview(table.entries[k]).cast('B' if k == 'example_kind' else 'I')) for k in ('table','example_kind','example_index','model')}
                    for mapping in component[side+'_assignment_map']:
                        entries = [i for i,t in enumerate(axes['table']) if t == mapping['table']]
                        require(len(entries) == len(mapping['entries']), 'component map omits entries')
                        for i,m in zip(entries,mapping['entries'],strict=True):
                            require(axes['example_kind'][i] == {'task':0,'train':1,'test':2}[m['example_kind']] and axes['example_index'][i] == m['example_index'] and axes['model'][i] == m['model'], 'component map axes differ')
                result['component_tables'] = 'pass'
            if not args.continuation:
                return result
            report, _, _ = arclog.study_continuation(evaluator, gold, mutant, json.dumps(kept))
            report = json.loads(report)
            require(report['gold_observation_stop'] is None, 'incomplete gold FITS observation')
            require(len(report['choices']) == len(kept), 'OUT choices missing')
            for choice, historic in zip(report['choices'], r['evaluation']['outputs'], strict=True):
                require(choice['assignment'] == historic['assignment'], 'OUT full choice index differs')
                out = choice['out']
                require(out['status'] == 'complete', 'conditional OUT stopped/faulted: '+str(out))
                require(historic['mutant']['status'] == 'complete', 'historical producer OUT incomplete')
                for example, old in zip(out['train'], historic['mutant']['train'], strict=True):
                    require(example['example'] == old['example'], 'OUT example differs')
                    for model, before in zip(example['models'], old['models'], strict=True):
                        require(model['equals'] == before['equals'] and model['differing_cells'] == before['differing_cells'], 'OUT comparison differs from historical producer')
                        if 'value_kind' not in model:
                            result['detailed_out'] = 'requires_new_wheel'
                        if model.get('value_kind') == 'rows':
                            require(len(model['rows']) == len(model['packed_rows']), 'OUT decoding loses rows')
                            require(model['grid_defined'] == (model['grid'] is not None), 'OUT grid status differs')
            result['conditional_out_comparison'] = 'pass'
            result['admissibility'] = [d for c in report['choices'] for d in c['admissibility']]
            require(all(d['status'] == 'complete' for d in result['admissibility']), 'DET admissibility incomplete')
    else:
        require(not args.continuation, 'new wheel required for OUT continuation')
        result['native_choices'] = 'requires_new_wheel'
    return result


def worker(args):
    import native_storage
    original = native_storage.load_native
    @lru_cache(maxsize=4)
    def cached(ref, base):
        return original(json.loads(ref), Path(base))
    native_storage.load_native = lambda ref, base: cached(json.dumps(ref, sort_keys=True), str(base))
    job = json.load(sys.stdin)
    context = dict(gold=OrderedDict(), evaluator=None)
    def alarm(*_):
        raise TimeoutError('per-record deadline')
    signal.signal(signal.SIGALRM, alarm)
    for item in job['items']:
        started = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, args.seconds)
        try:
            result = inspect(item['record'], Path(item['base']), args, context)
            result['status'] = 'pass'
        except Exception as error:
            result = dict(task=job['task'], source=item['source'], status='failure', reason=str(error))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        result['seconds'] = round(time.monotonic()-started, 6)
        print(json.dumps(result), flush=True)
    if context['evaluator'] is not None:
        context['evaluator'].finish_case()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--native-storage', type=Path, required=True)
    p.add_argument('--tasks', type=Path, required=True)
    p.add_argument('--only', nargs='*')
    p.add_argument('--limit', type=int, default=2, help='maximum records per task')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--seconds', type=float, default=10, help='per-record wall bound')
    p.add_argument('--native-seconds', type=float, default=1)
    p.add_argument('--continuation', action='store_true')
    p.add_argument('--components', action='store_true')
    p.add_argument('--output', type=Path)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    sys.path.insert(0, str(args.native_storage.resolve()))
    if args.worker:
        worker(args)
        return 0
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    jobs = []
    for path in sorted(args.corpus.glob('*/pairs.jsonl.gz')):
        if args.only and path.parent.name not in args.only:
            continue
        items = []
        with gzip.open(path, 'rt') as incoming:
            for index, line in enumerate(incoming):
                if index >= args.limit:
                    break
                items.append(dict(record=json.loads(line), base=str(path.parent.resolve()), source=str(path)))
        if items:
            jobs.append(dict(task=path.parent.name, items=items))
    counts = Counter()
    total = sum(len(j['items']) for j in jobs)
    started = time.monotonic()
    done = 0
    outgoing = (args.output/'cases.jsonl').open('w') if args.output else None
    import queue
    events = queue.Queue()
    def task(job):
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker',
                   '--corpus', str(args.corpus), '--native-storage', str(args.native_storage.resolve()),
                   '--tasks', str(args.tasks.resolve()), '--seconds', str(args.seconds),
                   '--native-seconds', str(args.native_seconds)]
        if args.continuation: command.append('--continuation')
        if args.components: command.append('--components')
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as process:
            process.stdin.write(json.dumps(job)); process.stdin.close()
            received = 0
            for line in process.stdout:
                events.put(json.loads(line)); received += 1
            code = process.wait()
            if code or received != len(job['items']):
                events.put(dict(status='worker_failure',task=job['task'],code=code,received=received,expected=len(job['items'])))
    def progress():
        elapsed = time.monotonic()-started
        rate = done/elapsed if elapsed else 0
        print(json.dumps(dict(event='progress',done=done,total=total,elapsed=round(elapsed,2),rate=round(rate,3),eta=round((total-done)/rate,1) if rate else None)),flush=True)
    progress()
    last_progress = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(task, job) for job in jobs]
        while any(not f.done() for f in futures) or not events.empty():
            try:
                result = events.get(timeout=.2)
            except queue.Empty:
                if time.monotonic()-last_progress >= 2:
                    progress(); last_progress = time.monotonic()
                continue
            counts[result['status']] += 1
            if result['status'] != 'worker_failure': done += 1
            line = json.dumps(result)
            print(line,flush=True)
            if outgoing: outgoing.write(line+'\n');outgoing.flush()
            progress()
        for future in futures: future.result()
    if outgoing: outgoing.close()
    runtime = Path(sys.executable).absolute().parent.parent.parent/'ready.json'
    import arclog
    summary = dict(engine_module=arclog.__file__,streams_digest=arclog.streams_digest(),done=done,total=total,seconds=round(time.monotonic()-started,3),counts=dict(counts),
                   python=sys.executable,check_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   runtime_manifest=json.loads(runtime.read_text()) if runtime.exists() else None)
    if args.output: (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(event='summary',**summary)),flush=True)
    return int(bool(counts['failure'] or counts['worker_failure']))


if __name__ == '__main__':
    raise SystemExit(main())
