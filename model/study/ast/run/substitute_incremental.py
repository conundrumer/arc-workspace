#!/usr/bin/env python3
"""Incremental added-only substitute draws. Never replays completed parent draws."""
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT
from substitute_population import canonical, digest, database, put, relation


class View:
    """Read-only chain of own facts; no copies of predecessor results."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True)
        has_meta = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone()
        parent = self.db.execute("SELECT value FROM metadata WHERE key='parent'").fetchone() if has_meta else None
        self.parent = View(parent[0]) if parent else None

    def object(self, key):
        row = self.db.execute('SELECT payload FROM objects WHERE sha256=?', (key,)).fetchone()
        if row:
            value = json.loads(row[0])
            if digest(value) != key:
                raise ValueError('object integrity mismatch')
            return value
        if self.parent:
            return self.parent.object(key)
        raise KeyError(key)

    def candidate_program(self, path, key):
        if str(self.path)==path:
            row=self.db.execute('SELECT program_ref FROM candidates WHERE key=?',(key,)).fetchone()
            if not row:
                raise ValueError('missing candidate reference')
            return row[0]
        if self.parent:
            return self.parent.candidate_program(path,key)
        raise ValueError('candidate database outside parent chain')

    def rows(self):
        if not self.parent:
            for key, inputs, sha, text in self.db.execute('SELECT key,input_sha256,result_sha256,payload FROM occurrences'):
                value = json.loads(text)
                if digest(value) != sha:
                    raise ValueError('occurrence integrity mismatch')
                yield key, dict(value, reference_sha=sha, reference_inputs=inputs,
                    candidate_refs=[(str(self.path), c) for c in value['candidates']])
            return
        own = {key:(inputs, sha, text) for key, inputs, sha, text in self.db.execute('SELECT key,input_sha256,result_sha256,payload FROM occurrences')}
        for key, value in self.parent.rows():
            delta = own.pop(key, None)
            if delta:
                inputs, sha, text = delta
                fact = json.loads(text)
                if digest(fact) != sha or fact['parent_result_sha256'] != value['reference_sha']:
                    raise ValueError('delta integrity/parent input mismatch')
                value = dict(value, reference_sha=sha, reference_inputs=inputs, delta=fact,
                    candidate_refs=value['candidate_refs']+[(str(self.path), c) for c in fact['candidates']])
            else:
                value = dict(value)
                value.pop('delta', None)
            yield key, value
        if own:
            raise ValueError('delta has no parent occurrence')

    def close(self):
        self.db.close()
        if self.parent:
            self.parent.close()


def counts(view, path):
    result = {}
    for key, value in view.rows():
        row = result.setdefault(relation(value['source']), dict(gold_uses=0, requested=0, selected_total=0,
            reused_selected=0, new_selected=0, unchanged_occurrences=0, added_draw_occurrences=0,
            added_proposals=0, added_attempts=0, added_statically_pruned=0, added_bound=0,
            added_unavailable=0, added_no_primitive=0))
        row['gold_uses'] += 1
        row['requested'] += value['requested']
        row['selected_total'] += len(value['candidate_refs'])
        delta = value.get('delta', {})
        new = len(delta.get('candidates', []))
        row['new_selected'] += new
        row['reused_selected'] += len(value['candidate_refs'])-new
        row['unchanged_occurrences'] += not bool(delta)
        row['added_draw_occurrences'] += bool(delta)
        native = delta.get('stats', {}).get('counts', {})
        row['added_proposals'] += native.get('domain_primitive_values', 0)
        row['added_attempts'] += native.get('domain_complete_assignments', 0)
        row['added_statically_pruned'] += native.get('domain_static_prune_candidates_excluded', 0)
        row['added_bound'] += any(v and (k.startswith('domain_search_stopped:') or k.startswith('domain_proposal_stopped:')) for k,v in native.items())
        row['added_unavailable'] += delta.get('status') == 'unavailable'
        row['added_no_primitive'] += bool(delta) and not native.get('domain_primitive_values', 0) and delta.get('status') != 'unavailable'
    with Path(path).open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=['relation']+list(next(iter(result.values()), {'gold_uses':0})))
        writer.writeheader()
        for name, row in sorted(result.items()):
            writer.writerow(dict(relation=name, **row))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--counts', type=Path)
    parser.add_argument('--profile', choices=['typed-v2', 'blocks-v3'], default='typed-v2')
    parser.add_argument('--tasks', type=Path, default=DATA_ROOT/'ast/engine/data/tasks')
    parser.add_argument('--deadline', type=float, default=1)
    parser.add_argument('--seed', type=int, default=4231)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    if args.report_only:
        if not args.counts:
            parser.error('--report-only needs --counts')
        view = View(args.output)
        counts(view, args.counts)
        view.close()
        return
    if not args.parent:
        parser.error('--parent required for added-only generation')
    parent = View(args.parent)
    # Cheap stored-fact routing precedes all native setup. Filled sites and
    # source kinds outside this addition's scope make no native call.
    groups = {}
    seen_programs = {}
    reused = 0
    total_occurrences = 0
    for key, value in parent.rows():
        total_occurrences += 1
        point_key=(value['task'],value['case'],tuple(value['point']))
        seen_programs.setdefault(point_key,set()).update(parent.candidate_program(path,candidate) for path,candidate in value['candidate_refs'])
        supported = value['source']['node'] in (('atom', 'not_atom') if args.profile=='typed-v2' else ('or','if','all','not_form'))
        if len(value['candidate_refs']) >= value['requested'] or not supported:
            reused += 1
            continue
        groups.setdefault((value['task'],value['case'],value['gold_ref']), []).append((key,value))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = args.output.with_suffix('.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = database(args.output)
    db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)')
    old_parent = db.execute("SELECT value FROM metadata WHERE key='parent'").fetchone()
    if old_parent and Path(old_parent[0]).resolve() != parent.path:
        raise ValueError('output already has another predecessor')
    with db:
        db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('parent', str(parent.path)))
    settings = dict(profile=args.profile, deadline=args.deadline, seed=args.seed)
    # Resume before parsing gold or creating any native evaluator.
    queued = {}
    resumed = 0
    for group, values in groups.items():
        for key, value in values:
            inputs = digest(dict(parent=value['reference_sha'], source_inputs=value['reference_inputs'], settings=settings))
            old = db.execute('SELECT input_sha256,result_sha256,payload FROM occurrences WHERE key=?', (key,)).fetchone()
            if old and old[0]==inputs and digest(json.loads(old[2]))==old[1]:
                resumed += 1
                continue
            queued.setdefault(group, []).append((key,value,inputs))
    for name in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS'):
        os.environ.setdefault(name, '1')
    import arclog
    with db:
        producer_ref=put(db,'producer',dict(profile=args.profile,settings=settings,
            code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_module=arclog.__file__,
            streams_digest=arclog.streams_digest()))
    started = time.monotonic()
    total = sum(map(len,queued.values()))
    done = 0
    print(canonical(dict(occurrences=total_occurrences, reused_unchanged=reused, resumed_delta=resumed,
        queued_added_draws=total, profile=args.profile)), flush=True)
    evaluator = None
    current_task = None
    for (task,case,gold_ref), values in sorted(queued.items()):
        source = parent.object(gold_ref)
        setup_problem = None
        try:
            if task != current_task:
                evaluator = None
                native_settings = arclog.DecodeSettings(rule_tests=False)
                evaluator = arclog.StudyTaskEvaluator(task,str(args.tasks),native_settings,session_bytes=128<<20,compact=True)
                current_task = task
            gold = evaluator.from_stream(source['stream']['ids'],source['stream']['model'])
            points = {tuple(point.body_path):point for point in gold.points()}
        except Exception as error:
            setup_problem = f'{type(error).__name__}: {error}'
        for key, previous, inputs in values:
            fact = dict(schema='substitute-added-facts-v1', profile=args.profile, parent_result_sha256=previous['reference_sha'],
                status='done', candidates=[], drawn=0, producer_ref=producer_ref)
            try:
                if setup_problem:
                    raise ValueError(setup_problem)
                point = points[tuple(previous['point'])]
                method = gold.draw_added_substitutes_at if args.profile=='typed-v2' else gold.draw_block_substitutes_at
                specs, stats = method(point,previous['at'],previous['requested']-len(previous['candidate_refs']),args.seed,
                    source_revision='substitute-'+args.profile,task=task,case=case)
                fact.update(stats=json.loads(stats), drawn=len(specs))
                with db:
                    for spec in specs:
                        text = gold.construct(spec).sexp()
                        program_ref = digest(text)
                        point_key=(task,case,tuple(previous['point']))
                        if program_ref in seen_programs[point_key]:
                            fact['duplicate_text_excluded']=fact.get('duplicate_text_excluded',0)+1
                            continue
                        put(db,'mutant_program',text)
                        candidate = digest(dict(gold=gold_ref,point=previous['point'],program=program_ref))
                        identity_ref = put(db,'mutation_identity',json.loads(spec.identity_json))
                        db.execute('INSERT OR IGNORE INTO candidates VALUES (?,?,?,?)', (candidate,key,identity_ref,program_ref))
                        owner = db.execute('SELECT occurrence_key FROM candidates WHERE key=?',(candidate,)).fetchone()[0]
                        if owner==key:
                            fact['candidates'].append(candidate)
                            seen_programs[point_key].add(program_ref)
                        else:
                            fact['duplicate_text_excluded'] = fact.get('duplicate_text_excluded',0)+1
            except Exception as error:
                fact.update(status='unavailable',reason=f'{type(error).__name__}: {error}')
            with db:
                db.execute('INSERT OR REPLACE INTO occurrences VALUES (?,?,?,?)',(key,inputs,digest(fact),canonical(fact)))
            done += 1
            elapsed = time.monotonic()-started
            rate = done/max(elapsed,.001)
            print(canonical(dict(done=done,total=total,reused_unchanged=reused,resumed_delta=resumed,elapsed=round(elapsed,2),
                rate=round(rate,3),eta=round((total-done)/rate,1),task=task,case=case,at=previous['at'])),flush=True)
    db.close()
    parent.close()
    lock.close()
    if args.counts:
        view = View(args.output)
        counts(view,args.counts)
        view.close()


if __name__ == '__main__':
    main()
