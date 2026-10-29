"""One-off authenticated reconstruction of runs 2/3, using stored rows only.

This audit compiles selected historical definitions from SHA-verified references,
never imports the retired writer into the current classifier, and makes no pair
engine evaluations. Run-3 code is read from its immutable repository commit.
Previous per-point states were not archived; results are marked reconstructed.
"""
import ast,builtins,collections,json,sqlite3,time,types,subprocess,hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import classify_normal as c
p=c.DATA_ROOT/'ast/run/mech2/normal.sqlite3'
db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
oldhash='234a89aeadb3057d24a59a7a5125fcf129a7c20b6e4462c6105baeed39bbce75'
manifest=json.loads(db.execute('select manifest_json from code_manifests where code_sha256=?',(oldhash,)).fetchone()[0])
assert c.digest(manifest)==oldhash
files={Path(p).name:(Path(p),h) for p,h in manifest['files'].items()}
for name in ['writer.py','classify_normal.py']:assert c.sha(files[name][0])==files[name][1]
oldwriter=ast.parse(files['writer.py'][0].read_text());oldscript=ast.parse(files['classify_normal.py'][0].read_text())
g=c.writer.__dict__.copy();node=next(n for n in oldwriter.body if isinstance(n,ast.FunctionDef) and n.name=='one_row_component')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(files['writer.py'][0]),'exec'),g)
oldnormal=types.FunctionType(c.writer.normal_form.__code__,g)
# The old writer's CaseRows imported detectors.spans, whose encoder was pinned.
# Clone that import resolution too; never alter current module globals.
encoder_file,encoder_sha=files['encoder.py'];assert c.sha(encoder_file)==encoder_sha
width_node=next(n for n in ast.parse(encoder_file.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='width')
wg={};exec(compile(ast.Module(body=[width_node],type_ignores=[]),str(encoder_file),'exec'),wg)
spans=types.FunctionType(c.detectors.spans.__code__,dict(c.detectors.spans.__globals__,E=types.SimpleNamespace(width=wg['width'])))
def historical_import(name,*args,**kwargs):
 return types.SimpleNamespace(spans=spans) if name=='detectors' else builtins.__import__(name,*args,**kwargs)
lg=dict(c.writer.CaseRows.layout.__globals__);lg['__builtins__']=dict(vars(builtins),__import__=historical_import)
layout=types.FunctionType(c.writer.CaseRows.layout.__code__,lg)
HistoricalCaseRows=type('HistoricalCaseRows',(c.writer.CaseRows,),dict(layout=layout))
proxy=types.SimpleNamespace(**c.writer.__dict__);proxy.passes=lambda shape,name:oldnormal(shape);proxy.CaseRows=HistoricalCaseRows
ns=c.__dict__.copy();ns['writer']=proxy
nodes=[n for n in oldscript.body if isinstance(n,ast.ClassDef) and n.name in ['StoredSource','StoredRows','Context']]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(files['classify_normal.py'][0]),'exec'),ns)
OldContext=ns['Context']
OriginalStoredRows=ns['StoredRows']
def traced_one_row(self,k,sites,head):
 if not hasattr(self,'calls'):self.calls=[]
 self.calls.append((int(k),c.canonical(sites),head))
 return OriginalStoredRows.one_row(self,k,sites,head)
ns['StoredRows']=type('TracedStoredRows',(OriginalStoredRows,),dict(one_row=traced_one_row))
# Freeze run 3's adapter as well; the current cache repair is intentionally
# excluded from this historical counterfactual.
run3='9cb15accb5b47ba69d2bd07c5d6d9ceb9038b7a545eb9f52e7abf13a5871658d'
if db.execute('SELECT count(*) FROM pairs WHERE code_sha256!=?',(run3,)).fetchone()[0]:raise ValueError('This one-off recipe requires the run-3 database snapshot')
run3manifest=json.loads(db.execute('SELECT manifest_json FROM code_manifests WHERE code_sha256=?',(run3,)).fetchone()[0])
for module in (c.writer,c.detectors,c.storage,c.native_reader,c.detectors.E):
 expected_module=next(h for path,h in run3manifest['files'].items() if Path(path).name==Path(module.__file__).name)
 if c.sha(module.__file__)!=expected_module:raise ValueError('Historical dependency changed: '+module.__file__)
expected=next(h for p,h in run3manifest['files'].items() if p.endswith('/mech2/classify_normal.py'))
source=subprocess.check_output(['git','show','dad2bc8f:model/study/ast/run/mech2/classify_normal.py'],cwd=c.REPO_ROOT,text=True)
if hashlib.sha256(source.encode()).hexdigest()!=expected:raise ValueError('Run 3 source receipt differs')
newns=c.__dict__.copy()
newnodes=[n for n in ast.parse(source).body if (isinstance(n,ast.ClassDef) and n.name in ('StoredSource','StoredRows','PrefixRows','Context')) or (isinstance(n,ast.FunctionDef) and n.name=='form_starts')]
exec(compile(ast.Module(body=newnodes,type_ignores=[]),'git:dad2bc8f/classify_normal.py','exec'),newns)
NewContext=newns['Context']
q='''SELECT g.point_id,g.record_json,p.record_json FROM gold_points g
JOIN (SELECT gold_point_id,MIN(rowid) AS rid FROM pairs GROUP BY gold_point_id) x ON x.gold_point_id=g.point_id
JOIN pairs p ON p.rowid=x.rid ORDER BY g.task,g.case_name,g.point'''
rows=db.execute(q).fetchall();before=collections.Counter();after=collections.Counter();deltas=[];oldctx=None;newctx=None;last=None;t0=time.monotonic()
for i,(pointid,gtext,ptext) in enumerate(rows,1):
 gp=json.loads(gtext);r=json.loads(ptext);corpus=Path(r['source']['corpus']);key=(str(corpus),r['task'])
 if key!=last:oldctx=OldContext(corpus,r['task']);newctx=NewContext(corpus,r['task']);last=key
 ids,flags=oldctx.streams[r['case']];starts=c.form_starts(ids,flags,oldctx.vocab.names);paths=[];form=-1;ss=set(starts)
 for pos in range(len(ids)):
  if pos in ss:form+=1
  paths.append([form])
 rec=dict(task=r['task'],case=r['case'],point=r['point'],mutant_stream=dict(ids=ids,model=flags,paths=paths),full_replay=dict(gold=r['inputs']['native_gold']),native=dict(gold=r['inputs'].get('native_prefix_gold')))
 
 for cached in oldctx.rows_cache.values():cached.calls=[]
 prev=oldctx.classify(rec,corpus/r['task'])['gold'];a=prev['normal'];b=gp['normal'];before[str(a)]+=1;after[str(b)]+=1
 if a!=b:
  shape,_=newctx.shape(ids,flags,r['point'][0]);pr=newctx.prefix_rows(rec,corpus/r['task'],(ids,flags));shape.rows=pr
  v=bool(oldnormal(shape));pr.optimistic=True;opt=bool(oldnormal(shape)) if not v else True;pr.optimistic=False
  adapter=True if v else None if opt else False
  evidence=[]
  for cached in oldctx.rows_cache.values():
   for k,sites_text,head in set(getattr(cached,'calls',[])):
    old_answer,old_reasons=cached.probes[(k,sites_text,head)]
    sites=json.loads(sites_text);pr.unavailable=[];now=pr.one_row(k,sites,head)
    old_lay=cached.lays.get(k)
    new_lays=[source.layout(k) for source in pr.sources]
    evidence.append(dict(relation=k,sites=sites,head=head,old_one_row=old_answer,
       old_reasons=old_reasons,new_one_row=None if not now and pr.unavailable else now,
       old_layout=None if old_lay is None else dict(head=old_lay['head'],spans=old_lay['spans']),
       new_source_answers=[dict(one_row=source.one_row(k,sites,head),reasons=source.probes[(k,c.canonical(sites),head)][1]) for source in pr.sources],new_layouts=[None if lay is None else dict(head=lay['head'],spans=lay['spans']) for lay in new_lays]))
  reasons=[]
  if adapter!=b:reasons.append('functional-lib rule removes the old lib obstruction' if b is True else 'functional-lib rule removes an obstruction but required stored row evidence remains unavailable')
  if a!=adapter:
   if any(e['old_layout'] is None and any(lay is not None for lay in e['new_layouts']) for e in evidence):reasons.append('stored point-prefix rows supply a table absent from full replay')
   if any(e['old_layout'] and any(lay and lay['head']!=e['old_layout']['head'] for lay in e['new_layouts']) for e in evidence):reasons.append('whole-form mapping repairs INIT-tail contamination of a declaration')
   if any(e['old_layout'] and any(lay and lay['spans']!=e['old_layout']['spans'] for lay in e['new_layouts']) for e in evidence):reasons.append('four-margin native spatial spans replace the old scalar spans')
   if any(e['old_one_row'] is True and e['new_one_row'] is False and len(e['new_source_answers'])>1 and e['new_source_answers'][0]['one_row'] is True and e['new_source_answers'][1]['one_row'] is False for e in evidence):reasons.append('additional stored point-prefix observation has more than one projected row')
   if not reasons:reasons.append('corrected stored-prefix/column evidence changes the old decision')
  deltas.append(dict(reasons=reasons,row_evidence_changes=evidence,point_id=pointid,task=r['task'],case=r['case'],point=r['point'],clause=r['clause'],before=a,after=b,adapter_only=adapter,old_unavailable=prev.get('unavailable',[]),new_unavailable=gp.get('unavailable',[])))
 if i%2000==0:print(i,len(rows),round(time.monotonic()-t0,1),flush=True)
result=dict(provenance_note='Reconstructed previous per-point states; previous rows were overwritten. Aggregate counts match the completed run. Cache history was not retained.',writer_definition_differences=['one_row_component'],encoder_widths={'Position':{'before':1,'after':4},'Offset':{'before':1,'after':4}},previous_code_sha256=oldhash,previous_counts=dict(before),current_counts=dict(after),transitions=[dict(before=a,after=b,count=n) for (a,b),n in collections.Counter((str(x['before']),str(x['after'])) for x in deltas).items()],changed_points=deltas)
assert dict(before)=={'True':14393,'False':100,'None':43},before
out=c.DATA_ROOT/'ast/run/mech2/gold-run-diff.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='changed_points'},indent=2),flush=True)
print('DIFF',str(out),len(deltas),'elapsed',time.monotonic()-t0,flush=True)
