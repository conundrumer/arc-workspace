#!/usr/bin/env python3
"""Label synthesized samples (a task, a gold point and a candidate program) as corpus pairs are labeled.

`label` reads study-sample-v1 records and writes one study-sample-label-v1 line per sample.
`from-population` writes study-sample-v1 records for candidates of a substitute population.
"""
import argparse
from collections import Counter
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'mech'),str(HERE),str(HERE.parents[1])]
from study_paths import DATA_ROOT,MAIN_ROOT
# Some study runtimes lack zstandard. Append it after the runtime's own packages,
# so the runtime's native wheel keeps precedence.
if importlib.util.find_spec('zstandard') is None:
    sys.path.append(str(MAIN_ROOT/'.venv/lib/python3.12/site-packages'))
from judge3.framed_jsonl import JsonlWriter,iter_json,iter_lines
from run import canonical,digest,pair_key

SAMPLE='study-sample-v1'
LABEL='study-sample-label-v1'
KINDS=('native_edit_identity','body_replacement')
# Fields of the joined read that go into a label line. `results` is reduced to the status of each pass.
KEEP=('status','valid','grade','grade_reason','filter_class','normal','judge_eligible','missing_steps','attributes','facts','reason','attempt',
      'filters','source_sha256','base_result_sha256','pruning_status')


def sample_id(record):
    return digest({k:record[k] for k in ('task','task_sha256','case','gold_ref','point','candidate')})


def sample_record(*,task,task_sha256,case,gold,point,candidate,proposal=None):
    """A study-sample-v1 record, and the gold_ref of `gold` ({task, case, text, stream: {ids, model}}).

    `point` is {body_path, clause_path, kind} of a point in gold.points(). `candidate` is one of
    {kind: native_edit_identity, identity, operation, text[, stream]} and
    {kind: body_replacement, text[, stream]}. For native_edit_identity, `stream` is the whole program's stream.
    For body_replacement, `text` is the whole program with the body at point.body_path replaced, and `stream`
    holds the replacement body's tokens in the decoder context of gold up to that point.
    `proposal` is the producer's own facts.
    """
    if candidate['kind'] not in KINDS:raise ValueError('unknown candidate kind '+str(candidate['kind']))
    record=dict(schema=SAMPLE,task=task,task_sha256=task_sha256,case=case,gold_ref=digest(gold),point=point,candidate=candidate,proposal=proposal or {})
    record['sample_id']=sample_id(record)
    return record,record['gold_ref']


class Golds:
    """Gold objects by gold_ref. Lines that the producer appends later are read when a sample needs them."""
    def __init__(self,path):
        self.path=path;self.line=0;self.values={}

    def get(self,ref):
        if ref not in self.values and self.path.exists():
            for value in iter_json(self.path,start_line=self.line+1):
                self.line+=1;self.values[digest(value)]=value
        return self.values.get(ref)


def put_object(root,value):
    sha=digest(value);path=root/'objects'/(sha+'.json')
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
        tmp.write_text(canonical(value));os.replace(tmp,path)
    return dict(path=str(path),sha256=sha)


def member(a,record,gold):
    """Population member for a sample. Raises ValueError for a sample that cannot be a member."""
    if record.get('schema')!=SAMPLE:raise ValueError('not a study-sample-v1 record')
    if sample_id(record)!=record['sample_id']:raise ValueError('sample_id differs from its fields')
    if gold is None:raise ValueError('gold object absent')
    if gold['task']!=record['task'] or gold['case']!=record['case']:raise ValueError('gold source binding differs')
    task_file=a.tasks/(record['task']+'.json')
    if not task_file.exists():raise ValueError('task file absent')
    if hashlib.sha256(task_file.read_bytes()).hexdigest()!=record['task_sha256']:raise ValueError('task input differs')
    point,candidate=record['point'],record['candidate']
    whole=candidate['kind']=='native_edit_identity' and candidate.get('stream')
    program=dict(text=candidate['text'],stream=candidate['stream']) if whole else candidate['text']
    value=dict(task=record['task'],case=record['case'],point=point['body_path'],clause=point['clause_path'],kind=point['kind'],
        task_sha256=record['task_sha256'],gold=put_object(a.root,gold),program=put_object(a.root,program),sample_id=record['sample_id'])
    if candidate['kind']=='native_edit_identity':
        identity=candidate['identity']
        if identity['body']!=value['point'] or identity['clause']!=value['clause']:raise ValueError('candidate point binding differs')
        for k in ('task','case'):
            if identity.get('source',{}).get(k,value[k])!=value[k]:raise ValueError('candidate source binding differs')
        value.update(K=len(identity['edits']),operation=candidate['operation'],identity=identity,construction=dict(kind='native_edit_identity',identity=identity))
        return digest(pair_key(value)),value
    if candidate['kind']=='body_replacement':
        value.update(K=1,operation='replace_body',identity=None,construction=dict(kind='body_replacement',stream=candidate.get('stream')))
        return digest(dict(schema='study-sample-body-v1',sample_id=record['sample_id'])),value
    raise ValueError('unknown candidate kind '+str(candidate['kind']))


def admit(db,pair,value):
    from population_consume import member_inputs
    sha=member_inputs(value);old=db.execute('SELECT input_sha256 FROM members WHERE pair_id=?',(pair,)).fetchone()
    if old and old[0]!=sha:raise ValueError('conflicting candidate inputs for '+pair)
    with db:db.execute('INSERT OR IGNORE INTO members VALUES (?,?,?)',(pair,sha,canonical(value)))


def only(db,pairs):
    """An in-memory observations table holding only `pairs`, so that the label phase reads no other member."""
    view=sqlite3.connect(':memory:')
    view.execute('CREATE TABLE observations(pair_id TEXT PRIMARY KEY,source_sha256 TEXT,locator TEXT)')
    for pair in pairs:
        row=db.execute('SELECT pair_id,source_sha256,locator FROM observations WHERE pair_id=?',(pair,)).fetchone()
        if row:view.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?)',row)
    return view


def label_line(record,pair,joined):
    line=dict(schema=LABEL,sample_id=record['sample_id'],pair_id=pair,labeled_at=time.time())
    if joined is None:return line
    line.update({k:joined[k] for k in KEEP if k in joined})
    if isinstance(joined.get('results'),dict):
        line['results']={k:(v.get('status','present') if isinstance(v,dict) else ('absent' if v is None else 'present')) for k,v in joined['results'].items()}
    base=(joined.get('results') or {}).get('base')
    if isinstance(base,dict) and 'label' in base:line['base_label']=base['label']
    if isinstance(joined.get('population'),dict):line['population']=joined['population']
    return line


def batches(a,done):
    """Consecutive pending samples of one (task, case, gold), at most a.batch per batch."""
    batch,key,seen=[],None,0
    for record in iter_json(a.samples):
        seen+=1
        if a.limit and seen>a.limit:break
        status=done.get(record.get('sample_id'))
        if status is not None and not (a.retry_unavailable and status=='unavailable'):continue
        k=(record.get('task'),record.get('case'),record.get('gold_ref'))
        if batch and (k!=key or len(batch)>=a.batch):
            yield batch;batch=[]
        batch.append(record);key=k
    if batch:yield batch


def label(a):
    import population_consume as pc
    from population_read import PopulationReader
    a.root.mkdir(parents=True,exist_ok=True)
    a.output=a.root/'population.sqlite3';a.retry_failures=a.retry_unavailable
    out=a.root/'labels.jsonl.zst'
    done={}
    if out.exists():
        for line in iter_json(out):done[line['sample_id']]=line.get('status')
    total=sum(1 for _ in iter_lines(a.samples))
    if a.limit:total=min(total,a.limit)
    db=pc.connect(a.output)
    with db:
        for k,v in dict(base=str(a.base.resolve()),labels=str(a.root/'labels.sqlite3'),tasks=str(a.tasks.resolve())).items():
            old=db.execute('SELECT value FROM metadata WHERE key=?',(k,)).fetchone()
            if old and old[0]!=v:raise ValueError('population input location changed: '+k)
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',(k,v))
    golds=Golds(a.golds);reader=None;counts=Counter();start=time.monotonic()
    resumed=sum(1 for s in done.values() if not (a.retry_unavailable and s=='unavailable'))
    finished=min(resumed,total);counts['resumed']=finished
    stages=open(a.root/'stages.log','a')
    try:
        with JsonlWriter(out) as writer:
            for batch in batches(a,done):
                admitted=[]
                for record in batch:
                    try:
                        pair,value=member(a,record,golds.get(record.get('gold_ref')))
                        admit(db,pair,value);admitted.append((record,pair))
                    except (ValueError,KeyError,TypeError) as error:
                        writer.write(label_line(record,None,None)|dict(status='rejected',reason=str(error)));writer.flush()
                        counts['rejected']+=1;finished+=1
                if admitted:
                    pairs=[pair for _,pair in admitted]
                    # The population phases print their own progress; it goes to stages.log.
                    with contextlib.redirect_stdout(stages):
                        pc.materialize(a,db)
                        pc.label(a,only(db,pairs))
                    stages.flush()
                    if reader is None:reader=PopulationReader(paths=dict(population=str(a.output)))
                    for record,pair in admitted:
                        joined=reader.read_pair(pair)
                        line=label_line(record,pair,joined)
                        if joined.get('reason')=='observation missing':line['status']='unavailable'
                        writer.write(line);writer.flush()
                        counts[line.get('status')]+=1;finished+=1
                elapsed=time.monotonic()-start;rate=(finished-resumed)/max(elapsed,.001)
                print(f'done={finished}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={(total-finished)/rate if rate else 0:.1f}s '+canonical(counts),flush=True)
    finally:
        stages.close()
        if reader:reader.close()
        db.close()


def from_population(a):
    from population_consume import candidates,object_value
    a.out.mkdir(parents=True,exist_ok=True)
    seen=set();n=0
    with JsonlWriter(a.out/'golds.jsonl.zst') as golds,JsonlWriter(a.out/'samples.jsonl.zst') as samples:
        if golds.committed_lines or samples.committed_lines:raise ValueError('output already has records; use a new --out')
        for m in candidates(a.population,None):
            if n>=a.limit:break
            gold=object_value(m['gold']);program=object_value(m['program'])
            text=program['text'] if isinstance(program,dict) else program
            candidate=dict(kind='native_edit_identity',identity=m['identity'],operation=m['operation'],text=text)
            if isinstance(program,dict) and program.get('stream'):candidate['stream']={k:program['stream'][k] for k in ('ids','model')}
            identity=m['identity']
            record,ref=sample_record(task=m['task'],task_sha256=hashlib.sha256((a.tasks/(m['task']+'.json')).read_bytes()).hexdigest(),case=m['case'],gold=gold,
                point=dict(body_path=identity['body'],clause_path=identity['clause'],kind=m['kind']),candidate=candidate,
                proposal=dict(population=str(a.population.resolve()),program_sha256=m['program']['sha256']))
            if ref not in seen:golds.write(gold);seen.add(ref)
            samples.write(record);n+=1
    print(f'samples={n} golds={len(seen)}',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    l=sub.add_parser('label',help='label study-sample-v1 records')
    l.add_argument('--samples',type=Path,required=True);l.add_argument('--golds',type=Path,required=True)
    l.add_argument('--root',type=Path,required=True,help='output directory; one per sample population')
    l.add_argument('--tasks',type=Path,required=True);l.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    l.add_argument('--seconds',type=float,default=1);l.add_argument('--work-cap',type=int,default=67108864);l.add_argument('--session-mib',type=int,default=2048)
    l.add_argument('--batch',type=int,default=8,help='most samples of one gold that share one evaluator session')
    l.add_argument('--limit',type=int,default=0,help='read at most this many sample lines')
    l.add_argument('--retry-unavailable',action='store_true',help='process again the samples whose last line is unavailable')
    e=sub.add_parser('from-population',help='write study-sample-v1 records for candidates of a substitute population')
    e.add_argument('--population',type=Path,required=True);e.add_argument('--tasks',type=Path,required=True)
    e.add_argument('--out',type=Path,required=True);e.add_argument('--limit',type=int,required=True)
    a=p.parse_args()
    if a.command=='from-population':return from_population(a)
    if a.seconds<=0 or a.work_cap<=0 or a.session_mib<=0 or a.batch<=0:p.error('limits must be positive')
    a.root=a.root.resolve();a.tasks=a.tasks.resolve();a.root.mkdir(parents=True,exist_ok=True)
    with open(a.root/'sample_label.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        label(a)


if __name__=='__main__':main()
