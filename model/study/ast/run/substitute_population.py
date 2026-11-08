#!/usr/bin/env python3
"""New occurrence-proportional population. Native dry draws only; no task replay.

The journal is the generated population, not a grade/label store. Every source
occurrence gets the same requested count; argument-rich relations get no extra
tickets. Run again to resume input-valid completed occurrences.
"""
import argparse
import csv
import fcntl
import os
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT, MAIN_ROOT, REPO_ROOT
sys.path.insert(0, str(REPO_ROOT / 'scripts/study'))
from check_stage1_all import inventory

POLICY = 'substitute-source-occurrence-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def relation(source):
    if source['node'] == 'comparison':
        return 'cmp:' + {'Eq':'=', 'Ne':'!=', 'Lt':'<', 'Le':'<=', 'Gt':'>', 'Ge':'>='}.get(source['op'], source['op'])
    if source['node'] not in ('atom', 'not_atom'):
        return source['node']
    value = source['relation']
    if 'lib' in value:
        return value['lib']
    if 'declared' in value:
        return 'declared'
    if 'input_port' in value:
        return 'port:' + value['input_port']
    if 'path' in value:
        return next(('port:' + part['port'] for part in reversed(value['path']) if 'port' in part), 'port:unknown')
    return value.get('fact', 'unknown').lower()


def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS objects(sha256 TEXT PRIMARY KEY,kind TEXT,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS occurrences(key TEXT PRIMARY KEY,input_sha256 TEXT,result_sha256 TEXT,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS candidates(key TEXT PRIMARY KEY,occurrence_key TEXT,identity_ref TEXT,program_ref TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS failures(key TEXT PRIMARY KEY,input_sha256 TEXT,payload TEXT)')
    return db


def put(db, kind, payload):
    key = digest(payload)
    db.execute('INSERT OR IGNORE INTO objects VALUES (?,?,?)', (key, kind, canonical(payload)))
    return key


def report(db, destination):
    """Derived report, computed on request. It is not authoritative pass data."""
    counts = {}
    for payload, in db.execute('SELECT payload FROM occurrences'):
        value = json.loads(payload)
        row = counts.setdefault(relation(value['source']), dict(gold_uses=0, requested=0, certified_drawn=0, selected_unique=0,
            unsupported_occurrences=0, no_primitive_occurrences=0, exhausted_shortfalls=0, bounded_occurrences=0, unavailable=0, primitive_proposals=0, certification_attempts=0,
            check_rejected=0, interface_rejected=0, binding_rejected=0, held_det_rejected=0, stream_rejected=0,
            unvisited=0, duplicate_text_excluded=0, statically_pruned=0, pruning_unavailable=0))
        row['gold_uses'] += 1
        row['requested'] += value['requested']
        row['certified_drawn'] += value['drawn']
        row['selected_unique'] += len(value['candidates'])
        native = value.get('stats', {}).get('counts', {})
        row['unsupported_occurrences'] += bool(native.get('occurrence_unsupported_block'))
        row['no_primitive_occurrences'] += bool(native.get('occurrence_no_primitive_alternative'))
        row['exhausted_shortfalls'] += bool(native.get('domain_exhausted') and value['drawn'] < value['requested'])
        row['bounded_occurrences'] += any(k.startswith('domain_search_stopped:') and v for k, v in native.items())
        row['unavailable'] += value['status'] == 'unavailable'
        row['statically_pruned'] += native.get('domain_static_prune_candidates_excluded', 0)
        row['pruning_unavailable'] += sum(v for k,v in native.items() if k.startswith('domain_static_prune_unavailable:'))
        row['primitive_proposals'] += native.get('domain_primitive_values', 0)
        row['certification_attempts'] += native.get('domain_complete_assignments', 0)
        for field, prefix in [('check_rejected','domain_check_excluded'), ('interface_rejected','domain_interface_excluded'),
                ('binding_rejected','domain_binding_excluded'), ('held_det_rejected','domain_held_det_excluded'),
                ('stream_rejected','domain_stream_excluded')]:
            row[field] += sum(v for k, v in native.items() if k.startswith(prefix))
        row['unvisited'] += max(0, native.get('domain_primitive_values', 0) - native.get('domain_complete_assignments', 0))
        row['duplicate_text_excluded'] += value.get('duplicate_text_excluded', 0) + native.get('domain_text_duplicate_excluded', 0)
    fields = ['relation'] + list(next(iter(counts.values()), dict(gold_uses=0)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for name, row in sorted(counts.items()):
            writer.writerow(dict(relation=name, **row))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, default=MAIN_ROOT / 'work/lm/data-full-9fac8128')
    parser.add_argument('--tasks', type=Path, default=DATA_ROOT / 'ast/engine/data/tasks')
    parser.add_argument('--base', type=Path, default=DATA_ROOT/'ast/run/mech/labels.sqlite3',
        help='read-only task/case scope; no historical result is changed')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--counts', type=Path, help='write a derived CSV of actual dry-draw counts')
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--per-occurrence', type=int, default=1)
    parser.add_argument('--seed', type=int, default=4231)
    parser.add_argument('--deadline', type=float, default=1)
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    if args.per_occurrence <= 0:
        parser.error('--per-occurrence must be positive')
    lock = None
    if not args.report_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        lock = args.output.with_suffix('.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = sqlite3.connect(f'file:{args.output.resolve()}?mode=ro', uri=True) if args.report_only else database(args.output)
    if args.report_only:
        if not args.counts:
            parser.error('--report-only requires --counts')
        report(db, args.counts)
        print(canonical(dict(unavailable_cases=db.execute('SELECT COUNT(*) FROM failures').fetchone()[0])), flush=True)
        db.close()
        return
    for name in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS'):
        os.environ.setdefault(name, '1')
    import arclog
    base = sqlite3.connect(f'file:{args.base.resolve()}?mode=ro', uri=True)
    selected = {}
    for task, case in base.execute("SELECT DISTINCT json_extract(record_json,'$.task'),json_extract(record_json,'$.case') FROM pairs"):
        if not args.only or task in args.only:
            selected.setdefault(task, set()).add(case)
    base.close()
    settings = dict(policy=POLICY, per_occurrence=args.per_occurrence, seed=args.seed, deadline=args.deadline)
    started = time.monotonic()
    total = sum(map(len, selected.values()))
    done = occurrences = resumed = 0
    code = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with db:
        producer_ref = put(db, 'producer', dict(code_sha256=code, settings=settings, native_module=arclog.__file__,
            streams_digest=arclog.streams_digest(), historical_draw_policy=arclog.StudyProgram.mutation_policy()))
    for task in selected:
        names, offsets, ids, flags = inventory(args.export, task, True)
        native_settings = arclog.DecodeSettings(rule_tests=False)
        evaluator = arclog.StudyTaskEvaluator(task, str(args.tasks), native_settings, session_bytes=128<<20, compact=True)
        for index, case in enumerate(names):
            if case not in selected[task]:
                continue
            stream = dict(ids=ids[offsets[index]:offsets[index+1]], model=list(map(int, flags[offsets[index]:offsets[index+1]])))
            source_input = digest(stream)
            case_key = digest(dict(task=task, case=case, stream=source_input))
            try:
                gold = evaluator.from_stream(stream['ids'], stream['model'])
                with db:
                    gold_ref = put(db, 'gold_program', dict(task=task, case=case, stream=stream, text=gold.sexp()))
                for point in gold.points():
                    if point.kind.lower() != 'rule':
                        continue
                    for occurrence in json.loads(gold.substitution_occurrences_json(point))['occurrences']:
                        occurrences += 1
                        key = digest(dict(source=source_input, task=task, case=case, point=point.body_path, at=occurrence['at']))
                        inputs = digest(dict(source=source_input, occurrence=occurrence, settings=settings))
                        old = db.execute('SELECT input_sha256,result_sha256,payload FROM occurrences WHERE key=?', (key,)).fetchone()
                        if old and old[0] == inputs and digest(json.loads(old[2])) == old[1]:
                            resumed += 1
                            continue
                        value = dict(schema=POLICY, task=task, case=case, point=point.body_path, at=occurrence['at'],
                            source=occurrence['source'], gold_ref=gold_ref, producer_ref=producer_ref,
                            requested=args.per_occurrence, drawn=0, candidates=[], status='done')
                        try:
                            specs, stats = gold.draw_substitutes_at(point, occurrence['at'], args.per_occurrence, args.seed,
                                source_revision=POLICY, task=task, case=case)
                            value.update(stats=json.loads(stats), drawn=len(specs))
                            with db:
                                for spec in specs:
                                    mutant = gold.construct(spec)
                                    text = mutant.sexp()
                                    program_ref = put(db, 'mutant_program', text)
                                    candidate_key = digest(dict(source=source_input, task=task, case=case, point=point.body_path, text=program_ref))
                                    identity_ref = put(db, 'mutation_identity', json.loads(spec.identity_json))
                                    owner = db.execute('SELECT occurrence_key FROM candidates WHERE key=?', (candidate_key,)).fetchone()
                                    if owner and owner[0] != key:
                                        value['duplicate_text_excluded'] = value.get('duplicate_text_excluded', 0) + 1
                                        continue
                                    db.execute('INSERT OR IGNORE INTO candidates VALUES (?,?,?,?)', (candidate_key, key, identity_ref, program_ref))
                                    value['candidates'].append(candidate_key)
                        except Exception as error:
                            value.update(status='unavailable', reason=f'{type(error).__name__}: {error}')
                        with db:
                            db.execute('INSERT OR REPLACE INTO occurrences VALUES (?,?,?,?)', (key, inputs, digest(value), canonical(value)))
                        elapsed = time.monotonic() - started
                        print(canonical(dict(cases_done=done, cases_total=total, occurrences=occurrences, resumed=resumed,
                            elapsed=round(elapsed, 2), rate=round(occurrences/max(elapsed,.001),3),
                            eta=round((total-done)*elapsed/max(done,1),1), task=task, case=case, at=occurrence['at'])), flush=True)
            except Exception as error:
                with db:
                    db.execute('INSERT OR REPLACE INTO failures VALUES (?,?,?)', (case_key, source_input,
                        canonical(dict(task=task, case=case, reason=f'{type(error).__name__}: {error}'))))
            done += 1
        del evaluator
    if args.counts:
        report(db, args.counts)
    print(canonical(dict(cases_done=done, cases_total=total, occurrences=occurrences, resumed=resumed,
        elapsed=round(time.monotonic()-started,2), native_task_evaluations=0,
        unavailable_cases=db.execute('SELECT COUNT(*) FROM failures').fetchone()[0])), flush=True)
    db.close()
    if lock is not None:
        lock.close()


if __name__ == '__main__':
    main()
