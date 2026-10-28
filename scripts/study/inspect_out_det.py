"""Bounded inspection of real v5 packed choices, body subsets and conditional OUT.

No test runner, redraw, alternate FITS or installation. --continuation requires
new bindings and rejects any historical assignment mismatch before accepting OUT.
"""
import argparse
from collections import Counter, defaultdict
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


def inspect(record, base, args):
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
        gold = arclog.StudyProgram.from_sexp(r['programs']['gold'], settings).decode_source()
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
            binding = json.loads(program.out_bindings_json())
            require(binding['complete'] and len(binding['columns']) == 2, 'OUT projection incomplete')
            require(all(c['occurrences'] and c['body_column'] >= 0 for c in binding['columns']), 'OUT binding lacks original label path')
        result['native_choices_and_out_binding'] = 'pass'
        if args.continuation:
            evaluator = arclog.StudyTaskEvaluator(r['task'], str(args.tasks), settings, compact=False)
            point = next(p for p in gold.points() if p.body_path == r['identity']['body'])
            evaluator.evaluate_pair(gold, point, mutant)
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
                        if model['value_kind'] == 'rows':
                            require(len(model['rows']) == len(model['packed_rows']), 'OUT decoding loses rows')
                            require(model['grid_defined'] == (model['grid'] is not None), 'OUT grid status differs')
            evaluator.finish_case()
            result['conditional_out'] = 'pass'
    else:
        require(not args.continuation, 'new wheel required for OUT continuation')
        result['native_choices_and_out_binding'] = 'requires_new_wheel'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--native-storage', type=Path, required=True)
    p.add_argument('--tasks', type=Path, required=True)
    p.add_argument('--only', nargs='*')
    p.add_argument('--limit', type=int, default=2)
    p.add_argument('--seconds', type=float, default=50)
    p.add_argument('--native-seconds', type=float, default=1)
    p.add_argument('--continuation', action='store_true')
    args = p.parse_args()
    sys.path.insert(0, str(args.native_storage))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('inspection deadline')))
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    counts = Counter()
    for path in sorted(args.corpus.glob('*/pairs.jsonl.gz')):
        if args.only and path.parent.name not in args.only:
            continue
        with gzip.open(path, 'rt') as incoming:
            for line in incoming:
                try:
                    result = inspect(json.loads(line), path.parent, args)
                    result['status'] = 'pass'
                except Exception as error:
                    result = dict(source=str(path), status='failure', reason=str(error))
                print(json.dumps(result), flush=True)
                counts[result['status']] += 1
                if sum(counts.values()) >= args.limit:
                    print(json.dumps(dict(event='summary', **counts)), flush=True)
                    return int(bool(counts['failure']))
    print(json.dumps(dict(event='summary', **counts)), flush=True)
    return int(bool(counts['failure']))


if __name__ == '__main__':
    raise SystemExit(main())
