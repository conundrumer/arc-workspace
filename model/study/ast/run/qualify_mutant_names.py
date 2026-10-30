#!/usr/bin/env python3
"""Regenerate only requested mutant text from certified native identities.

No task evaluation, source rewrite, label update or native-table serialization.
Qualifies preserved AST-path spellings and exact historical decode streams.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT
from mutant_names import tokens
sys.path.insert(0,str(Path(__file__).resolve().parent/'mech'))
from run import canonical,digest,pair_key


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ids',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--draw-fixtures',action='store_true',help='qualify native unique text and deterministic prefixes at the named duplicate point')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import arclog
    if arclog.StudyProgram.mutation_policy()!='complete-domain-unique-text-gold-names-v7':raise ValueError('requires the committed names/unique-text runtime')
    requests={}
    for line in a.ids.open():
        row=json.loads(line);loc=row['source'];path=(Path(loc['corpus'])/loc['file']).resolve()
        requests.setdefault(path,{})[loc['line']]=row
    total=sum(map(len,requests.values()));done=0;counts=collections.Counter();started=time.monotonic();draws=[]
    objects=a.output/'objects';objects.mkdir();fixture_dir=a.output/'qualification';fixture_dir.mkdir()
    fixtures=('03bf952c0a2a','3d88b0b3','00b987658378','de871c418ded')
    with (a.output/'receipts.jsonl').open('w') as out:
        for path,wanted in requests.items():
            sources={}
            with gzip.open(path,'rt') as source:
                for line,raw in enumerate(source,1):
                    if line not in wanted:continue
                    row=wanted[line];record=json.loads(raw);key=digest(pair_key(record))
                    if key!=row['pair_id']:raise ValueError('source locator now identifies another pair')
                    receipt=dict(schema='mutant-name-repair-v1',pair_id=key,source_sha256=digest(record),source=row['source'],identity_sha256=digest(record['identity']))
                    try:
                        text=record.get('gold_sexp') or record['programs']['gold'];gold_sha=hashlib.sha256(text.encode()).hexdigest()
                        if gold_sha not in sources:
                            gold=arclog.StudyProgram.from_sexp(text).decode_source()
                            if tokens(gold.sexp())!=tokens(text):raise ValueError('current native decode gold text differs from the recorded gold namespace')
                            export=json.loads(gold.render_json());sources[gold_sha]=(gold,export)
                        gold,gold_export=sources[gold_sha]
                        mutant=gold.construct_identity(canonical(record['identity']));audit=json.loads(mutant.audit_json())
                        if audit['changed_atoms']!=record['K'] or audit['outside_atoms_unchanged'] is not True:raise ValueError('native exact-edit audit differs')
                        new=mutant.sexp();stream=mutant.decode_stream();old=record['mutant_stream']
                        same_stream=(list(stream[0])==old['ids'] and list(map(int,stream[1]))==list(map(int,old['model'])) and stream[2]==old['paths'])
                        if not same_stream:raise ValueError('decode ids/model/paths changed; cannot reuse old table facts as a text-only repair')
                        echo=arclog.StudyProgram.from_sexp(new).decode_source().decode_stream()
                        if list(echo[0])!=list(stream[0]) or list(map(int,echo[1]))!=list(map(int,stream[1])):
                            raise ValueError('preserved-name text does not read back to the exact native mutant stream')
                        export=json.loads(mutant.render_json());before={tuple(n['path']):n for n in gold_export['nodes']};after={tuple(n['path']):n for n in export['nodes']}
                        unchanged=0;bad=[]
                        edits=[tuple(e['at']) for e in record['identity']['edits']]
                        for link in export['source_path_correspondence']:
                            at=tuple(link['before_path']);node=before.get(at)
                            if not node or link['status']!='preserved' or any(at[:len(e)]==e for e in edits):continue
                            atomic=node.get('data',{}).get('node') in ('atom','not_atom','comparison')
                            if not atomic and node['kind'] not in ('label','site'):continue
                            new_node=after.get(tuple(link['after_path']))
                            if not new_node or node['sexp']!=new_node['sexp']:bad.append(dict(path=list(at),gold=node['sexp'],mutant=new_node.get('sexp') if new_node else None))
                            unchanged+=1
                        if bad:raise ValueError('native preserved paths changed text: '+json.dumps(bad[:3]))
                        program_sha=hashlib.sha256(new.encode()).hexdigest();target=objects/(program_sha+'.arclog')
                        if not target.exists():target.write_text(new)
                        receipt.update(status='qualified',new_program_sha256=program_sha,new_program=str(target),decode_stream_unchanged=True,text_round_trip_unchanged=True,preserved_native_nodes=unchanged,
                            naming_scope='original native form/LabelId; native source_paths; packed physical wire labels unchanged',native_audit=audit)
                        for prefix in fixtures:
                            if key.startswith(prefix):
                                directory=fixture_dir/key;directory.mkdir()
                                (directory/'gold.arclog').write_text(gold.sexp());(directory/'mutant.arclog').write_text(new)
                                (directory/'native.json').write_text(json.dumps(export,indent=2)+'\n')
                                (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
                        if a.draw_fixtures and key.startswith('00b987658378'):
                            point=next(p for p in gold.points() if list(p.body_path)==record['point'])
                            kwargs=dict(source_revision=record['identity']['source']['revision'],task=record['task'],case=record['case'],operation='delete')
                            first,_=gold.draw_specs(point,record['K'],3,0,**kwargs)
                            specs,stats=gold.draw_specs(point,record['K'],100,0,**kwargs)
                            identities=[s.identity_json for s in specs];written=[gold.construct(s).sexp() for s in specs]
                            if len(written)!=len(set(written)):raise ValueError('native draw returned duplicate text')
                            if identities[:len(first)]!=[s.identity_json for s in first]:raise ValueError('unique text changed deterministic draw prefix')
                            draws.append(dict(task=record['task'],case=record['case'],point=record['point'],count=len(written),unique=True,prefix_stable=True,stats=json.loads(stats)))
                        counts['qualified']+=1
                    except Exception as error:
                        receipt.update(status='unavailable',reason=f'{type(error).__name__}: {error}');counts['unavailable']+=1
                    out.write(canonical(receipt)+'\n');out.flush();done+=1
                    elapsed=time.monotonic()-started;rate=done/elapsed
                    print(json.dumps(dict(done=done,total=total,elapsed=round(elapsed,1),rate=round(rate,2),eta=round((total-done)/rate,1),counts=dict(counts))),flush=True)
    report=dict(schema='mutant-names-qualification-v1',total=total,done=done,counts=dict(counts),draws=draws,elapsed_seconds=time.monotonic()-started,native_evaluations=0,source_writes=0,label_writes=0,
        native_module=str(arclog.__file__),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),ids=str(a.ids.resolve()))
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    if done!=total or counts['unavailable']:raise SystemExit('Qualification incomplete; inspect receipts; no automatic replay or relabeling.')

if __name__=='__main__':main()
