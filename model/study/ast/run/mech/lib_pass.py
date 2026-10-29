#!/usr/bin/env python3
"""Durable bounded library search through the ONE shared ReplayEvaluator.

Jobs JSONL supplies record_path, source_sha256, manifest_path, ntrain, ntest,
base_evidence and plan. Missing shared metadata is unknown, never a negative.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import sys
import time

from clause_evidence import clause_evidence
from grades import judge_eligible
from lib_plan import candidates
from outcomes import canonical
from review_metadata import load_review_metadata
from run import digest, pair_key

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[2]
STOP = False


def stop(signum, frame):
    global STOP
    STOP = True


def manifest():
    own = ['lib_pass.py','lib_plan.py','clause_evidence.py','grades.py',
           'review_metadata.py','outcomes.py','run.py','registry_plan.py']
    shared = ['evaluator.py','checks.py','tables.py','surface.py','registry.py','catalog.py']
    paths = [HERE/p for p in own] + [STUDY/'judgetool'/p for p in shared]
    paths.append(CODE_ROOT / 'study_paths.py')
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def valid(row, source, code, config, plan):
    if row is None or row[0]!=source or row[3]!=plan:
        return False
    return digest(json.loads(row[5])) == row[4]


def run_pair(ev, db, job, config, code, progress):
    from evaluator import open_source
    record, _ = open_source(job['record_path'], expected_sha256=job['source_sha256'])
    pair_id = digest(pair_key(record)); source = digest(record)
    plan_hash = digest(dict(plan=job['plan'],manifest=job['manifest_path'],
                            base_evidence=job['base_evidence'],ntrain=job['ntrain'],ntest=job['ntest'],
                            manifest_sha256=hashlib.sha256(Path(job['manifest_path']).read_bytes()).hexdigest()))
    config_hash = digest(config)
    row = db.execute('SELECT source,code,config,plan,result_hash,payload FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
    if valid(row,source,code,config_hash,plan_hash) and not json.loads(row[5]).get('interrupted'):
        saved=json.loads(row[5])
        if saved.get('schema')=='mech-lib-facts-v2':
            saved=dict(saved,search=dict(status='recovery_verified' if saved['stop']['reason']=='verified recovery' else 'bound_unknown'))
        return saved, True
    evidence = dict(job['base_evidence'])
    if (evidence.get('source_sha256') != source or evidence.get('pair_id') != pair_id
            or evidence.get('kind') != record['kind']):
        raise ValueError('base evidence source/pair/kind binding differs')
    metadata = load_review_metadata(job['manifest_path'],record)
    # This pass is for unresolved source-preserving rows. An authenticated base
    # admission is mandatory; old raw-label heuristics never admit a pair.
    eligible = judge_eligible(evidence)
    answers = list(evidence.get('mechanical_clauses', []))
    start = time.monotonic(); visited = 0; reused = 0; unknown = 0; found = False; seen = set()
    reason = 'not eligible for no-witness source-preserving pass'
    registry_receipt = None
    if eligible:
        registry_info = None
        if job['plan'].get('registry', True):
            registry_info = ev.registry_interfaces(record)
            if registry_info.get('source_sha256') != source:
                raise ValueError('native registry source binding differs')
            registry_receipt = {k:v for k,v in registry_info.items() if k not in ('registry','entries','typed_sites','readers')}
        import itertools
        from registry_plan import registry_candidates
        generated = candidates(metadata['adapter'],job['plan'])
        if registry_info is not None:
            generated = itertools.chain(generated,registry_candidates(ev.legacy,registry_info,metadata['adapter'],
                         max_atoms=job['plan'].get('max_registry_atoms',256),
                         per_relation=job['plan'].get('per_relation',32)))
        reason = 'finite plan visited; settled full space not certified'
        for candidate in generated:
            if STOP or time.monotonic()-start >= config['seconds'] or visited >= config['max_candidates']:
                reason = 'stopped at configured pair bound' if not STOP else 'interrupted after durable candidate'
                break
            identity = digest(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            receipt_key = digest(dict(pair_id=pair_id,source=source,plan=plan_hash,candidate=identity))
            old = db.execute('SELECT result_hash,payload FROM candidates WHERE key=?', (receipt_key,)).fetchone()
            if old and digest(json.loads(old[1])) == old[0]:
                raw = json.loads(old[1]); reused += 1
            else:
                target = dict(adapter=metadata['adapter'],ntrain=job['ntrain'],ntest=job['ntest'],
                              target_id='G',source=dict(source_sha256=source),
                              catalog_complete=metadata['adapter'].get('target_catalog',{}).get('complete') is True)
                # Target-specific execution bindings come only from the shared
                # catalog; arbitrary caller target fragments are not merged.
                if candidate.get('target') not in (None,'G'):
                    raw = dict(schema='judgetool-clause-v2',outcome='unknown',
                               reason='explicit target override unsupported; shared evaluate searches complete supplied catalog',graded=True,
                               source_sha256=source,route='replay_search_then_kept_filter')
                else:
                    raw = ev.evaluate(record,candidate['clause'],target,candidate.get('columns'),
                                      compatibility=False,explore=False,row_limit=0)
                if digest(manifest()) != code:
                    raise RuntimeError('labeling source changed during run; restart with new code hash')
                with db:
                    db.execute('INSERT OR REPLACE INTO candidates VALUES (?,?,?,?)',
                               (receipt_key,pair_id,digest(raw),canonical(raw)))
            ref = dict(database=str(config['output']),table='candidates',key=receipt_key,result_sha256=digest(raw))
            normalized = clause_evidence(raw,record,ref,role=candidate.get('role','recovery'),
                                         ntrain=job['ntrain'],ntest=job['ntest'])
            answers.append(normalized); visited += 1
            if normalized['outcome'] == 'unknown':
                unknown += 1
            found = normalized['outcome'] == 'recovery verified'
            progress(visited,reused,unknown,time.monotonic()-start)
            if found:
                reason = 'verified recovery';break
    evidence['mechanical_clauses'] = answers
    search = dict(status='recovery_verified' if found else 'bound_unknown' if eligible else 'unavailable',
                  complete=False,settled_space=False,unvisited=None,reason=reason,
                  receipt_ref=dict(database=str(config['output']),table='pairs',pair_id=pair_id))
    evidence['search'] = search
    result = dict(schema='mech-lib-facts-v2',pair_id=pair_id,source_sha256=source,
                  code_sha256=code,config_sha256=config_hash,plan_sha256=plan_hash,
                  candidate_refs=[a['receipt_ref'] for a in answers],
                  stop=dict(reason=reason,seconds=time.monotonic()-start),interrupted=STOP)
    if digest(manifest()) != code:
        raise RuntimeError('labeling source changed during run; restart with new code hash')
    with db:
        db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?,?,?)',
                   (pair_id,source,code,config_hash,plan_hash,digest(result),canonical(result)))
    return dict(result,search=search), False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('jobs',type=Path)
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/lib.sqlite3')
    ap.add_argument('--seconds',type=float,default=30)
    ap.add_argument('--max-candidates',type=int,default=128)
    ap.add_argument('--candidate-seconds',type=float,default=.5)
    ap.add_argument('--config',type=Path)
    ap.add_argument('--artifacts',type=Path,default=DATA_ROOT / 'judgetool/replays/mech-lib')
    a=ap.parse_args()
    if a.seconds<=0 or a.candidate_seconds<=0 or a.max_candidates<1:
        ap.error('positive limits required')
    if a.jobs.resolve()==a.output.resolve():
        ap.error('jobs and output must differ')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix(a.output.suffix+'.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sys.path.insert(0,str(STUDY/'judgetool'))
    from evaluator import ReplayEvaluator
    ev=ReplayEvaluator(config=a.config,deadline=a.candidate_seconds,artifacts=a.artifacts)
    config=dict(schema='mech-lib-config-v1',seconds=a.seconds,max_candidates=a.max_candidates,
                evaluator=ev.receipt,output=str(a.output.resolve()))
    code_files=manifest();code=digest(code_files)
    db=sqlite3.connect(a.output);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.executescript('CREATE TABLE IF NOT EXISTS pairs(pair_id TEXT PRIMARY KEY,source TEXT,code TEXT,config TEXT,plan TEXT,result_hash TEXT,payload TEXT);'
                     'CREATE TABLE IF NOT EXISTS candidates(key TEXT PRIMARY KEY,pair_id TEXT,result_hash TEXT,payload TEXT);')
    with a.jobs.open() as stream:total=sum(1 for line in stream if line.strip())
    started=time.monotonic();done=0;skip=0;gained=0;bounded=0
    def report(visited=0,reused=0,unknown=0,pair_seconds=0):
        elapsed=time.monotonic()-started;rate=done/max(elapsed,.001)
        print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s '
              f'ETA={(total-done)/rate:.1f}s' if rate else
              f'done={done}/{total} elapsed={elapsed:.1f}s rate=0/s ETA=unknown',
              f'skip={skip} gained={gained} bounded={bounded} candidate_done={visited} '
              f'candidate_reuse={reused} unknown={unknown} pair_elapsed={pair_seconds:.3f}s',
              file=sys.stderr,flush=True)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        with a.jobs.open() as stream:
            for line_no,line in enumerate(stream,1):
                if STOP:break
                if not line.strip():continue
                try:
                    result,was_skip=run_pair(ev,db,json.loads(line),config,code,report)
                except Exception as error:
                    raise RuntimeError(f'{a.jobs}:{line_no}: {error}') from error
                done+=1;skip+=was_skip
                gained+=result['search']['status']=='recovery_verified'
                bounded+=result['search']['status']=='bound_unknown'
                report()
                ev.finish_case()
    finally:
        ev.close();db.close();lock.close()
    report()


if __name__=='__main__':main()
