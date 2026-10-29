#!/usr/bin/env python3
"""Run and check one judge clause through the shared existing-bindings evaluator."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
from evaluator import ReplayEvaluator,HERE,read_json,open_source,canonical,sha


def load_pair(directory):
    directory=Path(directory).resolve(); manifest=read_json(directory/'manifest.json');adapter=manifest['adapter']
    path=Path(adapter['source']['record_path']).resolve()
    raw=gzip.open(path,'rb').read() if path.suffix=='.gz' else path.read_bytes()
    # Renderer hashes the original decoded JSONL line (including its newline),
    # separately from the canonical source digest used by mechanical consumers.
    expected=adapter['source'].get('record_sha256')
    if expected and hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('render source raw JSON hash mismatch')
    record,source=open_source(path)
    taskpath=Path(adapter['source']['task_path']).resolve();task=read_json(taskpath)
    return manifest,record,dict(adapter=adapter,source=dict(source,source_sha256=source['sha256']),
        target_id='G',ntrain=len(task['train']),ntest=len(task['test']),
        catalog_complete=adapter.get('target_catalog',{}).get('complete') is True)


def check_answer(ev,manifest,record,target,answer,row_limit):
    if not isinstance(answer,dict) or set(answer)-{'schema','pair_id','render_version','clauses'}:
        raise ValueError('answer contains unsupported fields; do not supply a label or grade')
    if answer.get('schema')!='judge-tool-answer-v3' or answer.get('pair_id')!=manifest['pair_id'] or answer.get('render_version')!=manifest['render_version']:
        raise ValueError('answer schema/pair/version mismatch')
    if not isinstance(answer.get('clauses'),list):raise ValueError('clauses must be a list (empty if none found)')
    outcomes=[]
    for item in answer['clauses']:
        if set(item)-{'kind','clause','columns','reasons'} or item.get('kind') not in ('recovery','alternative'):
            raise ValueError('each answer clause requires kind recovery or alternative')
        reasons=item.get('reasons')
        if not isinstance(reasons,list) or not 1<=len(reasons)<=2 or any(not isinstance(r,str) or not r.strip() for r in reasons):
            raise ValueError('each clause requires one or two evidence reasons')
        try:
            outcome=ev.evaluate(record,item['clause'],dict(target,mode=item['kind']),item.get('columns'),row_limit=row_limit)
        except Exception as error:
            outcome=dict(outcome='unknown',verified=False,submitted_clause=item['clause'],
                         source_sha256=sha(record),reason=f'{type(error).__name__}: {error}')
        outcomes.append(dict(outcome,kind=item['kind'],reasons=reasons))
    admission=target['adapter'].get('admission',{})
    admitted=admission.get('eligible') is True and admission.get('receipt_authenticated') is True
    return dict(schema='judge-tool-final-v3',pair_id=manifest['pair_id'],render_version=manifest['render_version'],
                no_clause_found=not bool(outcomes),outcomes=outcomes,
                source_sha256=sha(record),adapter_sha256=sha(target['adapter']),
                judge_run=dict(completed=admitted and all(o.get('outcome')!='unknown' for o in outcomes),
                               clauses_checked=True,admission_authenticated=admitted,
                               no_kept_entry=any(o.get('missing_contexts') for o in outcomes)),
                instruction='labeler assigns the grade from checked evidence; no judge label or grade')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair',required=True,help='pair directory containing manifest.json')
    parser.add_argument('--record',help='write full checked result to this file inside judgetool')
    parser.add_argument('--deadline',type=float,default=30)
    parser.add_argument('--limit',type=int,default=30,help='maximum total printed train rows')
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('run','check','alternative'):
        p=commands.add_parser(name);p.add_argument('--clause-file',required=True);p.add_argument('--columns',type=json.loads)
    p=commands.add_parser('view-target');p.add_argument('--target-id',required=True)
    p.add_argument('--offset',type=int,default=0);p.add_argument('--assignment',type=int)
    p.add_argument('--example',help='train input name, e.g. train1; omitted means every train input')
    p=commands.add_parser('final');p.add_argument('--answer',required=True)
    args=parser.parse_args();start=time.monotonic();ev=None
    print(f'{args.command} 0/1 elapsed=0.0s',file=sys.stderr,flush=True)
    try:
        manifest,record,target=load_pair(args.pair)
        ev=ReplayEvaluator(deadline=args.deadline)
        if args.command=='view-target':
            from target_view import view_target
            result=view_target(ev,record,target,args.target_id,limit=max(0,args.limit),offset=args.offset,
                               assignment=args.assignment,example=args.example)
            result.update(pair_id=manifest['pair_id'],render_version=manifest['render_version'])
        elif args.command=='final':
            result=check_answer(ev,manifest,record,target,read_json(args.answer),max(0,args.limit))
        else:
            clause=Path(args.clause_file).read_text()
            result=ev.evaluate(record,clause,dict(target,mode='alternative' if args.command=='alternative' else 'recovery'),
                args.columns,explore=args.command=='run',row_limit=max(0,args.limit))
            result.update(pair_id=manifest['pair_id'],render_version=manifest['render_version'])
        result['specification_sha256']=hashlib.sha256((HERE.parent/'codex-adm/briefs/judge-decisions.md').read_bytes()).hexdigest()
    except Exception as error:
        result=dict(schema='judgetool-clause-v2',outcome='unknown',verified=False,
                    reason=f'{type(error).__name__}: {error}')
    finally:
        if ev is not None:ev.close()
    if args.command in ('run','view-target'):
        result.pop('outcome',None);result.pop('verified',None);result['graded']=False
    if args.record:
        path=Path(args.record).resolve()
        if not path.is_relative_to(DATA_ROOT / 'judgetool'):raise ValueError('--record must stay inside judgetool')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    from judge_view import render
    print(render(result),end='',flush=True)
    sessions=DATA_ROOT / 'judgetool/sessions';sessions.mkdir(exist_ok=True)
    with (sessions/(str(result.get('pair_id','input-error'))+'.jsonl')).open('a') as stream:
        stream.write(canonical(dict(argv=sys.argv,output=result))+'\n')
    elapsed=time.monotonic()-start
    print(f'{args.command} 1/1 elapsed={elapsed:.2f}s rate={1/max(elapsed,.001):.2f}/s',file=sys.stderr,flush=True)
    return 0 if (args.command=='final' and all(o.get('outcome')!='unknown' for o in result.get('outcomes',[{'outcome':'unknown'}]))) or result.get('verified') or result.get('continuation_passed') or args.command in ('run','view-target') and result.get('engine')=='ran' else 2


if __name__=='__main__':raise SystemExit(main())
