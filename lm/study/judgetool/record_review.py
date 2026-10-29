#!/usr/bin/env python3
"""Run actual requested calibration review sessions and preserve exact outputs."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
STUDY=ROOT.parent
PYTHON=DATA_ROOT / 'ast/run/runtime-5ee2f066/venv/bin/python'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();pairs=args.pairs.resolve();output=args.output.resolve()
    if not output.is_relative_to(DATA_ROOT / 'judgetool') or output==DATA_ROOT / 'judgetool/review':
        parser.error('choose a new review directory inside judgetool; frozen review is protected')
    output.mkdir(parents=True,exist_ok=False)
    cases=[
      ('01-init-projection','63c82d29',[
        ('run','unfiltered','(RULE &fix (&X (:a *A) (:b *B) (:W *W)))',None),
        ('check','recovery','(RULE &fix (&X (:a *A) (:b *B) (:W *W)) (input (:P B) (:Col *Col)) (NOT (&bg (:C Col))) (!= A B))',['A','B','W'])]),
      ('02-rule-refusal','68bedb70',[
        ('check','refused-color-zero','(RULE &fix (&X (:P *P) (:POuter *POuter) (:PInner *PInner) (:Col *Col)) (!= Col 0))',None),
        ('check','unfiltered','(RULE &fix (&X (:P *P) (:POuter *POuter) (:PInner *PInner) (:Col *Col)))',None),
        ('check','no-X-source','(RULE &fix (input (:P *P) (:Col *Col)))',None),
        ('check','recovery','(RULE &fix (&X (:P *P) (:POuter *POuter) (:PInner *PInner) (:Col *Col)) (NOT (&bg (:C Col))))',None),
        ('check','single-row-lib','(RULE &fix (&X (:P *P0) (:POuter *POuter) (:PInner *PInner) (:Col *Col)) (NOT (&bg (:C Col))) (compose (:A P0) (:B 0) (:C *P)))',['P','POuter','PInner','Col'])]),
      ('03-lib-query','9567384f',[
        ('run','query','(RULE &fix (&X (:P *P)) (dir_elem (:D *D)))',None),
        ('alternative','continuation','(RULE &fix (&X (:P *P)) (dir_elem (:D *D)))',None)]),
      ('04-ident-selection','0ad31171',[
        ('check','recovery','(RULE &fix (&X (:P *P) (:P2 *P2) (:Id *Id)) (&diag.component P Id) (&diag.component (:P P2) (:Id Id)))',None)])]
    for done,(name,prefix,steps) in enumerate(cases,1):
        pair=next(pairs.glob(prefix+'*'));folder=output/name;folder.mkdir()
        version=json.loads((pair/'manifest.json').read_text())['render_version']
        text=[f'# Recorded tool session: {pair.name}', '', 'Document version: '+version, '', 'Actual commands and outputs, in order. No judge call. Test rows withheld by the tool.', '']
        machine=[]
        for command,title,clause,columns in steps:
            path=folder/(title+'.sexp');path.write_text(clause+'\n')
            argv=[str(PYTHON),str(ROOT/'judge_tool.py'),'--pair',str(pair),'--limit','6','--record',str(folder/(title+'.record.json')),command,'--clause-file',str(path)]
            if columns is not None:argv+=['--columns',json.dumps(columns)]
            print(f'{done}/{len(cases)} start {name} {title}',flush=True)
            started=time.monotonic();process=subprocess.run(argv,text=True,capture_output=True)
            text+=['## '+title,'','```sh',shlex.join(argv),'```','','Clause:','```lisp',clause,'```','','Stdout (exact):','```json',process.stdout.rstrip('\n'),'```','','Stderr (exact):','```text',process.stderr.rstrip('\n'),'```','',f'Exit status: {process.returncode}.','']
            machine.append(dict(command=argv,clause=clause,stdout=process.stdout,stderr=process.stderr,returncode=process.returncode,seconds=time.monotonic()-started))
            print(f'{done}/{len(cases)} {name} {title} exit={process.returncode} elapsed={time.monotonic()-started:.2f}s',flush=True)
        if name=='02-rule-refusal':
            manifest=json.loads((pair/'manifest.json').read_text())
            references=manifest['adapter']['target_catalog']['targets']
            later=next(r for r in references if r['role']=='later' and r.get('status')=='stored')
            other=next(r for r in references if r['role']=='other_case' and r.get('status')=='stored')
            for title,ref,offset in [('view-later',later,0),('view-other-case',other,0),('view-other-case-next-page',other,6)]:
                argv=[str(PYTHON),str(ROOT/'judge_tool.py'),'--pair',str(pair),'--limit','6','--record',str(folder/(title+'.record.json')),
                      'view-target','--target-id',ref['target_id'],'--assignment','0','--example','train1','--offset',str(offset)]
                process=subprocess.run(argv,text=True,capture_output=True)
                text+=['## '+title,'','```sh',shlex.join(argv),'```','','Stdout (exact):','```json',process.stdout.rstrip('\n'),'```',
                       '','Stderr (exact):','```text',process.stderr.rstrip('\n'),'```','',f'Exit status: {process.returncode}.','']
                machine.append(dict(command=argv,stdout=process.stdout,stderr=process.stderr,returncode=process.returncode))
                print(f'{done}/{len(cases)} {name} {title} exit={process.returncode}',flush=True)
        if name=='03-lib-query':
            manifest=json.loads((pair/'manifest.json').read_text())
            answer=dict(schema='judge-tool-answer-v3',pair_id=pair.name,render_version=manifest['render_version'],
                        clauses=[dict(kind='alternative',clause=steps[-1][2],reasons=['X supplies P; dir_elem supplies the four D values shown by the exploratory run.'])])
            path=folder/'answer.json';path.write_text(json.dumps(answer,indent=2)+'\n')
            argv=[str(PYTHON),str(ROOT/'judge_tool.py'),'--pair',str(pair),'--limit','6','--record',str(folder/'final.record.json'),'final','--answer',str(path)]
            process=subprocess.run(argv,text=True,capture_output=True)
            text+=['## Final check (submitted alternative kind retained)','','```sh',shlex.join(argv),'```','','Stdout (exact):','```json',process.stdout.rstrip('\n'),'```','','Stderr (exact):','```text',process.stderr.rstrip('\n'),'```','',f'Exit status: {process.returncode}.','']
            machine.append(dict(command=argv,answer=answer,stdout=process.stdout,stderr=process.stderr,returncode=process.returncode))
        (folder/'session.md').write_text('\n'.join(text)+'\n')
        (folder/'session.json').write_text(json.dumps(machine,indent=2)+'\n')
    (output/'index.md').write_text('# Recorded judge-tool review\n\n'+''.join(f'- [{p.name}/session.md]({p.name}/session.md) — exact commands and output.\n' for p in sorted(output.glob('0*')))+'\nComparison-only target viewing and pagination are recorded in 02. Full evidence stays in *.record.json; stdout withholds test rows.\n')
    print('Recorded all four actual sessions.',flush=True)

if __name__=='__main__':main()
