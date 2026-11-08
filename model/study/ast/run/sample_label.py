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
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'mech'),str(HERE),str(HERE.parents[1])]
from study_paths import CODE_ROOT,DATA_ROOT,MAIN_ROOT,REPO_ROOT
# Study runtimes lack packages that stages import: zstandard in older runtimes, and pandas and pyarrow, which the
# normal-form pass needs. Append the study environment after the runtime's own packages, so the runtime's native
# wheel keeps precedence.
sys.path.append(str(MAIN_ROOT/'work/lm/.venv/lib/python3.12/site-packages'))
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
    {kind: body_replacement, text, source_revision[, stream]}. For native_edit_identity, `stream` is the whole
    program's stream. For body_replacement, `text` is the whole program with the body at point.body_path replaced,
    `source_revision` names the producer's revision, and `stream` holds the replacement clause's completion tokens
    in the decoder context of gold up to that point (RULE and DET only).
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
        if not candidate.get('source_revision'):raise ValueError('body_replacement candidate has no source_revision')
        # The pair ID needs the native identity, which Stages.construct gives.
        value.update(K=1,operation='replace_body',identity=None,
            construction=dict(kind='body_replacement',source_revision=candidate['source_revision'],body_stream=candidate.get('stream')))
        return None,value
    raise ValueError('unknown candidate kind '+str(candidate['kind']))


def admit(db,pair,value):
    from population_consume import member_inputs
    sha=member_inputs(value);old=db.execute('SELECT input_sha256 FROM members WHERE pair_id=?',(pair,)).fetchone()
    if old and old[0]!=sha:raise ValueError('conflicting candidate inputs for '+pair)
    with db:db.execute('INSERT OR IGNORE INTO members VALUES (?,?,?)',(pair,sha,canonical(value)))


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


def passes_dir(root):
    """Pass stores and replay artifacts of a sample root. Evaluator artifacts must lie under DATA_ROOT/population_passes."""
    return DATA_ROOT/'population_passes'/(root.name+'-'+hashlib.sha256(str(root).encode()).hexdigest()[:12])


def targets_path(root):
    """The all-target store of a sample root. The target pass writes only under DATA_ROOT/ast/run/mech5."""
    return DATA_ROOT/'ast/run/mech5/population'/passes_dir(root).name/'targets.sqlite3'


def pass_paths(root):
    passes=passes_dir(root)
    return dict(witness_tests=passes/'witness-tests.sqlite3',normal=passes/'normal.sqlite3',fit_split=passes/'fits.sqlite3',
                target_comparison=targets_path(root))


def reader(root):
    """The joined read of a sample root's members."""
    from population_read import PopulationReader
    return PopulationReader(paths=dict(population=str(Path(root).resolve()/'population.sqlite3'),population_passes=pass_paths(Path(root).resolve())))


def evaluator_config(a):
    """The corpus evaluator settings, with this root's task directory."""
    config=json.loads((DATA_ROOT/'ast/run/corpus-v12-body-full/run.json').read_text());config['tasks']=str(a.tasks)
    path=a.root/'evaluator.json'
    if not path.exists() or json.loads(path.read_text())!=config:
        tmp=path.with_suffix('.tmp');tmp.write_text(canonical(config));os.replace(tmp,path)
    return path


def reuse(db,old,sources,pair,value):
    """Bind a historical observation with an intact base label to the member, without evaluation."""
    from population_consume import accept,intact,observation
    if not value.get('identity') or observation(db,pair) is not None:return False
    row=old.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
    if not row or not intact(row,row[0]):return False
    result=json.loads(row[2]);src=result['source']
    return accept(db,pair,value,sources.record(result),dict(corpus=src['corpus'],file=src['file'],line=src['line'],stream=src.get('stream','kept')))


class Stages:
    """Per-sample labeling stages. Each stage resumes its own stored result; a stage failure is a fact of the sample."""
    def __init__(self,a,db,log):
        import population_consume as pc
        from source_read import SourceReader
        self.a,self.db,self.log,self.pc=a,db,log,pc
        self.sources=SourceReader(CODE_ROOT);self.old=pc.ro(a.base)
        self.materializer=pc.MaterializeSession(a,db);self.labeler=pc.LabelSession(a,db)
        self.passes=passes_dir(a.root);self.passes.mkdir(parents=True,exist_ok=True)
        self.labels=a.root/'labels.sqlite3';self.config=evaluator_config(a)
        self.witness=self.fits=None;self.contexts={}

    def close(self):
        for s in (self.witness,self.fits,self.materializer,self.labeler):
            if s is not None:s.close()
        self.sources.close();self.old.close()

    def construct(self,value):
        """The canonical member and pair ID of a body_replacement sample. A body stream that native rejects is
        reported and dropped, because the whole candidate text is checked without it."""
        import arclog
        from population_consume import construct_body
        note=None
        try:mutant=construct_body(value,self.a.tasks)
        except arclog.Refusal as error:
            if not (str(error).startswith('body_replacement:body_stream') and value['construction'].get('body_stream')):raise
            note=str(error);value=dict(value,construction=dict(value['construction'],body_stream=None))
            mutant=construct_body(value,self.a.tasks)
        identity=json.loads(mutant.identity_json)
        value=dict(value,identity=identity,K=mutant.k,construction=dict(value['construction'],identity=identity),program=put_object(self.a.root,mutant.sexp()))
        return digest(pair_key(value)),value,note

    def run(self,pair,value):
        out={}
        def stage(name,call):
            try:
                with contextlib.redirect_stdout(self.log):result=call()
                out[name]=result.get('status','done') if isinstance(result,dict) else 'done'
                return result
            except Exception as error:  # noqa: BLE001
                out[name]=dict(error=type(error).__name__,reason=str(error))
                return None
        if self.a.reuse_base:stage('reuse',lambda:dict(status='reused' if reuse(self.db,self.old,self.sources,pair,value) else 'none'))
        stage('materialize',lambda:self.pc.materialize_one(value,self.materializer,pair_id=pair))
        base=stage('label',lambda:self.pc.label_one(pair,self.labeler))
        if not base or base.get('status') not in ('label_members','resumed_own'):return out
        # Follow-up passes run on this root's own base results; reused pairs keep the historical passes' results.
        stage('normal',lambda:self.normal(pair))
        stage('witness_tests',lambda:self.witness_tests(pair))
        stage('fit_split',lambda:self.fit_split(pair))
        return out

    def normal(self,pair):
        if str(HERE/'mech2') not in sys.path:sys.path.append(str(HERE/'mech2'))  # classify_normal imports its siblings by bare name
        import classify_normal
        call=lambda retry:classify_normal.label_pair(pair,base=self.labels,output=self.passes/'normal.sqlite3',source_reader=self.sources,contexts=self.contexts,retry_unavailable=retry)
        result=call(False)
        # A sample reaches this stage only while it is pending, so its stored unavailable normal fact is tried again.
        if not result['written'] and result['mutant']['normal'] is None:result=call(True)
        return result

    def witness_tests(self,pair):
        if self.witness is None:
            from step2_check import WitnessTestSession
            self.witness=WitnessTestSession(base=self.labels,population_passes=self.passes,config=self.config,source_reader=self.sources,artifacts=self.passes/'witness-artifacts')
        return self.witness.check_pair(pair)

    def fit_split(self,pair):
        if self.fits is None:
            from mech3.pair_api import PairLabeler
            self.fits=PairLabeler(base=self.labels,population_passes=self.passes,config=self.config,source_reader=self.sources,artifacts=self.passes/'fit-artifacts')
        return self.fits.label_pair(pair)


def pending(a,done):
    seen=0
    for record in iter_json(a.samples):
        seen+=1
        if a.limit and seen>a.limit:break
        status=done.get(record.get('sample_id'))
        if status is not None and not (a.retry_unavailable and status=='unavailable'):continue
        yield record


def label(a):
    import arclog
    import population_consume as pc
    a.output=a.root/'population.sqlite3';a.retry_failures=a.retry_unavailable
    out=a.root/'labels.jsonl.zst'
    done={}
    if out.exists():
        for line in iter_json(out):done[line['sample_id']]=line.get('status')
    total=sum(1 for _ in iter_lines(a.samples))
    if a.limit:total=min(total,a.limit)
    db=pc.connect(a.output)
    with db:
        for k,v in dict(base=str(a.base.resolve()),labels=str(a.root/'labels.sqlite3'),tasks=str(a.tasks),passes=str(passes_dir(a.root))).items():
            old=db.execute('SELECT value FROM metadata WHERE key=?',(k,)).fetchone()
            if old and old[0]!=v:raise ValueError('population input location changed: '+k)
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',(k,v))
    golds=Golds(a.golds);joined_reader=None;counts=Counter();start=time.monotonic()
    resumed=min(sum(1 for s in done.values() if not (a.retry_unavailable and s=='unavailable')),total)
    finished=resumed;counts['resumed']=resumed
    log=open(a.root/'stages.log','a');stages=None
    try:
        stages=Stages(a,db,log)
        with JsonlWriter(out) as writer:
            for record in pending(a,done):
                line=None
                try:pair,value=member(a,record,golds.get(record.get('gold_ref')))
                except (ValueError,KeyError,TypeError) as error:
                    line=label_line(record,None,None)|dict(status='rejected',reason=str(error))
                if line is None:
                    note=None
                    try:
                        if pair is None:pair,value,note=stages.construct(value)
                        admit(db,pair,value)
                    except (arclog.Refusal,ValueError) as error:
                        line=label_line(record,pair,None)|dict(status='unavailable',reason=str(error))
                if line is None:
                    ran=stages.run(pair,value);log.flush()
                    if note:ran['body_stream']=dict(dropped=note)
                    if joined_reader is None:joined_reader=reader(a.root)
                    joined=joined_reader.read_pair(pair)
                    line=label_line(record,pair,joined)|dict(stages=ran)
                    if joined.get('reason')=='observation missing':line['status']='unavailable'
                writer.write(line);writer.flush()
                counts[line.get('status')]+=1;finished+=1
                elapsed=time.monotonic()-start;rate=(finished-resumed)/max(elapsed,.001)
                print(f'done={finished}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={(total-finished)/rate if rate else 0:.1f}s '+canonical(counts),flush=True)
        if finished==resumed:print(f'done={finished}/{total} nothing pending '+canonical(counts),flush=True)
    finally:
        if stages:stages.close()
        if joined_reader:joined_reader.close()
        log.close();db.close()


def targets(a):
    """All-target comparison of this root's own labeled pairs, then a new label line for each sample whose read changed."""
    out=a.root/'labels.jsonl.zst'
    last={}
    for line in iter_json(out):last[line['sample_id']]=line
    own={l['pair_id']:l['source_sha256'] for l in last.values()
         if (l.get('stages') or {}).get('label') in ('label_members','resumed_own') and l.get('source_sha256')}
    if not own:return print('no own labeled pairs',flush=True)
    selection=a.root/'targets-pairs.jsonl'
    with selection.open('w') as f:
        for pair,source in sorted(own.items()):f.write(canonical(dict(pair_id=pair,source_sha256=source))+'\n')
    # The target pass streams its own progress and resumes completed pairs.
    subprocess.run([sys.executable,'-B','-m','model.study.ast.run.mech5.targets','--base',str(a.root/'labels.sqlite3'),
        '--output',str(targets_path(a.root)),'--pairs-from',str(selection),'--pair-seconds',str(a.pair_seconds)]+(['--retry-unavailable'] if a.retry_unavailable else []),
        cwd=REPO_ROOT,check=True)
    keys=('status','grade','grade_reason','missing_steps')
    with reader(a.root) as r,JsonlWriter(out) as writer:
        changed=0
        for line in last.values():
            if line.get('pair_id') not in own:continue
            joined=r.read_pair(line['pair_id'])
            new=label_line(dict(sample_id=line['sample_id']),line['pair_id'],joined)|dict(stages=dict(line.get('stages') or {},target_comparison='run'))
            if any(new.get(k)!=line.get(k) for k in keys):
                writer.write(new);writer.flush();changed+=1
    print(f'pairs={len(own)} changed_lines={changed}',flush=True)


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
    l.add_argument('--no-reuse-base',dest='reuse_base',action='store_false',help='evaluate a mutant again even where the historical base has an intact label for it')
    l.add_argument('--limit',type=int,default=0,help='read at most this many sample lines')
    l.add_argument('--retry-unavailable',action='store_true',help='process again the samples whose last line is unavailable')
    t=sub.add_parser('targets',help='run the all-target comparison on the labeled pairs of a root, and add the changed label lines')
    t.add_argument('--root',type=Path,required=True);t.add_argument('--pair-seconds',type=float,default=120)
    t.add_argument('--retry-unavailable',action='store_true',help='retry pairs whose target facts are unavailable')
    e=sub.add_parser('from-population',help='write study-sample-v1 records for candidates of a substitute population')
    e.add_argument('--population',type=Path,required=True);e.add_argument('--tasks',type=Path,required=True)
    e.add_argument('--out',type=Path,required=True);e.add_argument('--limit',type=int,required=True)
    a=p.parse_args()
    if a.command=='from-population':return from_population(a)
    if a.command=='targets':
        a.root=a.root.resolve()
        with open(a.root/'sample_label.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return targets(a)
    if a.seconds<=0 or a.work_cap<=0 or a.session_mib<=0:p.error('limits must be positive')
    a.root=a.root.resolve();a.tasks=a.tasks.resolve();a.root.mkdir(parents=True,exist_ok=True)
    with open(a.root/'sample_label.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        label(a)


if __name__=='__main__':main()
