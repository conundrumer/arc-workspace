#!/usr/bin/env python3
"""Audit stored mutant text outside certified edits and duplicate text per point.

Reads every published pairs.jsonl.gz once, including filtered records. The first
corpus wins for tasks present in several builds. No evaluation/replay or labels
are computed. Native gold metadata is checked once per distinct case program;
its canonical AST paths locate atom text, not a second Python AST policy.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT
sys.path.insert(0,str(Path(__file__).resolve().parent/'mech'))
from run import canonical,digest,pair_key,published_task

TOKENS=re.compile(r'\(|\)|[^\s()]+')
TESTS=('03bf952c0a2a','3d88b0b3','00b987658378','de871c418ded')


def tokens(text):return TOKENS.findall(text)



def source_header(raw):
    """Read only leading identity/program fields; skip large native/eval payloads.

    Corpus rows write these fields before mutant_stream/evaluation/native. This
    audit is about stored text, not an integrity validator of unused row data.
    A missing required header fails explicitly rather than guessing a program.
    """
    decoder=json.JSONDecoder();at=0;out={}
    required={'task','case','point','clause','K','operation','identity','gold_sexp','mutant_sexp','programs'}
    while at<len(raw) and raw[at].isspace():at+=1
    if at==len(raw) or raw[at]!='{':raise ValueError('corpus record is not a JSON object')
    at+=1
    while True:
        while at<len(raw) and raw[at] in ' \t\r\n,':at+=1
        if at==len(raw) or raw[at]=='}':raise ValueError('stored program header incomplete')
        key,at=decoder.raw_decode(raw,at)
        while raw[at].isspace():at+=1
        if raw[at]!=':':raise ValueError('invalid source header separator')
        at+=1
        while raw[at].isspace():at+=1
        value,at=decoder.raw_decode(raw,at);out[key]=value
        if required<=out.keys():return out


def find(sequence,part,start):
    for i in range(start,len(sequence)-len(part)+1):
        if sequence[i:i+len(part)]==part:return i
    raise ValueError('canonical native atom text not found in stored gold text')


def gold_view(arclog,text):
    checked=arclog.StudyProgram.from_sexp(text)
    export=json.loads(checked.render_json())
    source=tokens(text);spans={};cursor=0
    kinds={tuple(node['path']):node['kind'] for node in export['nodes']}
    # Source order is the engine's NodeRef children order. Only leaf conjuncts
    # are sought; body wrappers and labels are never treated as edit locations.
    for node in export['nodes']:
        if node.get('data',{}).get('node') not in ('atom','not_atom','comparison'):continue
        path=tuple(node['path'])
        # OUT uses elided ^sites in the whole file; it cannot be a mutation point.
        if kinds.get((path[0],))=='out':continue
        part=tokens(node['sexp']);at=find(source,part,cursor)
        spans[path]=(at,at+len(part));cursor=at+len(part)
    return source,spans,text.splitlines()


def differences(gold,spans,mutant,edits):
    regions=[]
    for edit in edits:
        start,end=spans[tuple(edit['at'])]
        regions.append((start,end,edit['replacement'] is not None))
    regions.sort()
    if any(a[1]>b[0] for a,b in zip(regions,regions[1:])):raise ValueError('overlapping edited atoms')
    actual=tokens(mutant);before=[];after=[];i=j=0
    for start,end,replaced in regions:
        width=start-i
        left=gold[i:start];right=actual[j:j+width]
        if left!=right:
            # An unchanged atom can gain/lose a named-field wrapper when its
            # variable is renamed. That is already an outside-edit defect;
            # never advance a fixed token width and mislocate a later edit.
            return dict(changed=True,structural=len(left)!=len(right),
                changes=[dict(index=i+n,gold=a,mutant=b) for n,(a,b) in enumerate(zip(left,right)) if a!=b][:32],
                proof='unchanged prefix before next certified edit differs')
        before.extend(left);after.extend(right);j+=width
        if replaced:
            if j>=len(actual) or actual[j]!='(':raise ValueError('replacement is not one balanced conjunct at its certified location')
            depth=0
            while j<len(actual):
                t=actual[j];depth+=(t=='(')-(t==')');j+=1
                if depth==0:break
            if depth:raise ValueError('unbalanced mutant replacement')
        i=end
    before.extend(gold[i:]);after.extend(actual[j:])
    if len(before)!=len(after):return dict(changed=True,structural=True,before_count=len(before),after_count=len(after),changes=[])
    changes=[dict(index=i,gold=a,mutant=b) for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    return dict(changed=bool(changes),structural=False,changes=changes)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpora',type=Path,nargs='+',default=[DATA_ROOT/'ast/run/corpus-v11',DATA_ROOT/'ast/run/corpus-v12-body-full'])
    p.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tasks',nargs='*',help='explicit bounded qualification scope; omitted means all published tasks')
    p.add_argument('--only-ids',type=Path,help='audit only source locators in an earlier affected/unavailable JSONL; no full corpus rerun')
    p.add_argument('--require-qualification',action='store_true',help='require the named feature examples to reproduce both reported defects')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import arclog
    base=sqlite3.connect(a.base.resolve().as_uri()+'?mode=ro',uri=True)
    labeled={r[0] for r in base.execute('SELECT pair_id FROM pairs')};base.close()
    requested=None
    if a.only_ids:
        requested={}
        for line in a.only_ids.open():
            item=json.loads(line);source=item['source'];path=(Path(source['corpus'])/source['file']).resolve()
            requested.setdefault(path,{})[source['line']]=item['pair_id']
    selected={}
    for root in a.corpora:
        for task in sorted(root.resolve().iterdir()):
            if published_task(task) and (not a.tasks or task.name in a.tasks):
                if (task/'pairs.jsonl.gz').is_file() and (requested is None or (task/'pairs.jsonl.gz').resolve() in requested):selected.setdefault(task.name,task)
    if a.tasks and set(a.tasks)!=set(selected):raise ValueError('requested task not published: '+str(set(a.tasks)-set(selected)))
    timings=collections.Counter();scanned=0;counts=collections.Counter();duplicate_counts=collections.Counter();by_scope=collections.defaultdict(collections.Counter)
    tests={};errors=[];start=time.monotonic();last=start;done=0
    outputs={name:(a.output/(name+'.jsonl')).open('w') for name in ('affected','duplicate-groups','unavailable')}
    def flush_groups(seen):
        for group,members in seen.items():
            if len(members)<2:continue
            counts['duplicate_groups']+=1;counts['duplicate_pairs']+=len(members);counts['duplicate_excess']+=len(members)-1
            selected_members=[r for r in members if r['labeled']]
            if len(selected_members)>1:
                duplicate_counts['labeled_groups']+=1;duplicate_counts['labeled_pairs']+=len(selected_members);duplicate_counts['labeled_excess']+=len(selected_members)-1
            value=dict(task=members[0]['task'],case=group[0],point=list(group[1]),gold_sha256=group[2],mutant_sha256=hashlib.sha256(group[3].encode()).hexdigest(),members=members)
            outputs['duplicate-groups'].write(canonical(value)+'\n')
            for prefix in TESTS:
                if any(m['pair_id'].startswith(prefix) for m in members):tests.setdefault(prefix,{})['duplicate_group']=value
    try:
        for task in selected.values():
            seen={};views={};current_point=None;finished_points=set()
            with gzip.open(task/'pairs.jsonl.gz','rt') as source:
                for line,raw in enumerate(source,1):
                    scanned+=1
                    if requested is not None and line not in requested[(task/'pairs.jsonl.gz').resolve()]:
                        now=time.monotonic()
                        if now-last>=5:
                            print(json.dumps(dict(tasks_done=done,tasks_total=len(selected),records=counts['records'],source_lines_scanned=scanned,elapsed=round(now-start,1),rate=round(scanned/(now-start),2))),flush=True);last=now
                        continue
                    tick=time.monotonic();record=source_header(raw);timings['header_seconds']+=time.monotonic()-tick;counts['records']+=1
                    key=digest(pair_key(record));gold=record.get('gold_sexp') or record.get('programs',{}).get('gold');mutant=record.get('mutant_sexp') or record.get('programs',{}).get('mutant')
                    if requested is not None and key!=requested[(task/'pairs.jsonl.gz').resolve()][line]:raise ValueError('requested source locator now identifies another pair')
                    meta=dict(pair_id=key,task=record['task'],case=record['case'],point=record['point'],clause=record['clause'],K=record['K'],operation=record['operation'],retained=record.get('retained'),labeled=key in labeled,source=dict(corpus=str(task.parent),file=task.name+'/pairs.jsonl.gz',line=line))
                    scope='labeled' if meta['labeled'] else 'not_labeled';by_scope[scope]['records']+=1
                    if not isinstance(gold,str) or not isinstance(mutant,str):
                        counts['no_constructed_text']+=1;continue
                    counts['constructed']+=1;by_scope[scope]['constructed']+=1
                    gh=hashlib.sha256(gold.encode()).hexdigest();mh=hashlib.sha256(mutant.encode()).hexdigest()
                    point_key=(record['case'],tuple(record['point']),gh)
                    if current_point is not None and point_key!=current_point:
                        flush_groups(seen);seen.clear();finished_points.add(current_point)
                        if point_key in finished_points:raise ValueError('published corpus revisits a completed point; cannot bound duplicate inventory by point')
                    current_point=point_key
                    # Exact text is the key, not hash equality or alpha equivalence.
                    groupkey=(record['case'],tuple(record['point']),gh,mutant)
                    seen.setdefault(groupkey,[]).append(dict(meta,mutant_sha256=mh))
                    if gh not in views:
                        tick=time.monotonic()
                        try:views[gh]=gold_view(arclog,gold)
                        except Exception as error:views[gh]=error
                        timings['native_metadata_seconds']+=time.monotonic()-tick
                    view=views[gh]
                    gold_lines=view[2] if not isinstance(view,Exception) else gold.splitlines()
                    mutant_lines=mutant.splitlines()
                    changed_forms=[i for i,(g,m) in enumerate(zip(gold_lines,mutant_lines)) if g!=m]
                    if len(gold_lines)!=len(mutant_lines):changed_forms=None
                    one_line=changed_forms is not None and len(changed_forms)==1
                    if one_line:
                        counts['one_line']+=1;by_scope[scope]['one_line']+=1
                        if len(mutant)<len(gold):counts['one_line_shorter']+=1;by_scope[scope]['one_line_shorter']+=1
                    try:
                        if isinstance(view,Exception):raise view
                        tick=time.monotonic()
                        if changed_forms is None or any(i!=record['point'][0] for i in changed_forms):
                            diff=dict(changed=True,structural=False,changes=[],proof='unchanged top-level form text differs')
                        else:diff=differences(view[0],view[1],mutant,record['identity']['edits'])
                        timings['text_comparison_seconds']+=time.monotonic()-tick
                        value=dict(meta,gold_sha256=gh,mutant_sha256=mh,changed_forms=changed_forms,**diff)
                        if diff['changed']:
                            counts['outside_edit_changed']+=1;by_scope[scope]['outside_edit_changed']+=1
                            outside=changed_forms is None or any(i!=record['point'][0] for i in changed_forms)
                            if outside:counts['outside_form_changed']+=1;by_scope[scope]['outside_form_changed']+=1
                            value['outside_form_changed']=outside
                            outputs['affected'].write(canonical(value)+'\n')
                        for prefix in TESTS:
                            if key.startswith(prefix):
                                tests[prefix]=dict(value,gold_program=gold,mutant_program=mutant)
                    except Exception as error:
                        counts['unavailable']+=1;by_scope[scope]['unavailable']+=1
                        value=dict(meta,reason=f'{type(error).__name__}: {error}');outputs['unavailable'].write(canonical(value)+'\n')
                        if len(errors)<12:errors.append(value)
                        for prefix in TESTS:
                            if key.startswith(prefix):tests[prefix]=dict(value,gold_program=gold,mutant_program=mutant)
                    now=time.monotonic()
                    if now-last>=5:
                        elapsed=now-start;rate=counts['records']/elapsed
                        print(json.dumps(dict(tasks_done=done,tasks_total=len(selected),records=counts['records'],elapsed=round(elapsed,1),records_per_second=round(rate,2),task_eta_seconds=round((len(selected)-done)*elapsed/done,1) if done else None,affected=counts['outside_edit_changed'],unavailable=counts['unavailable'])),flush=True)
                        for out in outputs.values():out.flush()
                        last=now
            flush_groups(seen)
            done+=1
        for prefix in TESTS:
            if prefix in tests:
                folder=a.output/'qualification';folder.mkdir(exist_ok=True);(folder/(prefix+'.json')).write_text(json.dumps(tests[prefix],indent=2)+'\n')
        report=dict(schema='mutant-names-audit-v1',counts=dict(counts),scope_counts={k:dict(v) for k,v in by_scope.items()},duplicate_counts=dict(duplicate_counts),tasks=len(selected),elapsed_seconds=time.monotonic()-start,timings=dict(timings),source_lines_scanned=scanned,requested_ids=str(a.only_ids) if a.only_ids else None,requested_population=sum(map(len,requested.values())) if requested is not None else None,corpora=[str(p.resolve()) for p in a.corpora],scope=('requested source locators only; duplicate counts cover this subset' if requested is not None else 'all published pair records, filtered included; v11 first, v12 completed supplements; recovered copies not read twice'),native_module=str(arclog.__file__),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),qualification={k:('available' if k in tests else 'absent_from_scope') for k in TESTS},error_examples=errors,method='Compare native-path-located gold atoms with exactly one replacement or deletion masked per edit; compare every remaining printed token. Duplicate by exact full mutant text per source gold/task/case/point. Native program parse/export only, no replay/evaluation.',ids_file=str(a.output/'affected.jsonl'),duplicate_ids_file=str(a.output/'duplicate-groups.jsonl'))
        (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        if requested is not None and counts['records']!=sum(map(len,requested.values())):raise ValueError('some requested source locators were not read')
        if a.require_qualification:
            for prefix in TESTS:
                if prefix not in tests or tests[prefix].get('reason'):raise ValueError('named qualification unavailable: '+prefix)
            if not all(tests[prefix].get('changed') is True for prefix in TESTS[:2]):raise ValueError('named outside-edit renames did not reproduce')
            if not all(tests[prefix].get('duplicate_group') for prefix in TESTS[2:]):raise ValueError('named duplicate group did not reproduce')
    finally:
        for out in outputs.values():out.close()

if __name__=='__main__':main()
