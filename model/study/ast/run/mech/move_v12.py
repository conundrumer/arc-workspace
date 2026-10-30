#!/usr/bin/env python3
"""Resumable v12 source move. No draws; paused lib/target/judge jobs stay paused."""
from copy import deepcopy
from collections import Counter,OrderedDict
from contextlib import ExitStack
import argparse
import builtins
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import zlib

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parents[2]),str(HERE.parents[2]/'judgetool')]
from study_paths import DATA_ROOT,CODE_ROOT
from run import canonical,digest,pair_key
import source_bindings as binding



def sync_directory(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def open_ro(path):return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=120)

def setup(path):
    path.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(path,timeout=120)
    db.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS objects(sha256 TEXT PRIMARY KEY,payload BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS requests(old_sha TEXT PRIMARY KEY,pair_id TEXT,locator TEXT,base_result TEXT);
    CREATE TABLE IF NOT EXISTS sources(old_sha TEXT PRIMARY KEY,pair_id TEXT,current_sha TEXT,current_locator TEXT,patch_ref TEXT,proof_ref TEXT);
    CREATE INDEX IF NOT EXISTS sources_pair ON sources(pair_id);
    CREATE INDEX IF NOT EXISTS sources_current ON sources(current_sha);
    CREATE TABLE IF NOT EXISTS blocks(sha256 TEXT PRIMARY KEY,bytes INTEGER,path TEXT,offset INTEGER,payload BLOB);
    CREATE TABLE IF NOT EXISTS files(original TEXT PRIMARY KEY,destination TEXT,sha256 TEXT);
    CREATE TABLE IF NOT EXISTS scans(path TEXT PRIMARY KEY,signature TEXT,line INTEGER,complete INTEGER);
    CREATE TABLE IF NOT EXISTS matches(pair_id TEXT PRIMARY KEY,locator TEXT);
    CREATE TABLE IF NOT EXISTS base_changes(pair_id TEXT PRIMARY KEY,old_result TEXT,current_result TEXT,patch_ref TEXT,applied INTEGER,proof_ref TEXT,forward_ref TEXT);
    CREATE TABLE IF NOT EXISTS witness_aliases(pair_id TEXT,assignment INTEGER,old_sha TEXT,new_sha TEXT,PRIMARY KEY(pair_id,assignment));
    CREATE TABLE IF NOT EXISTS extra_native(sha256 TEXT,base TEXT,reference TEXT,PRIMARY KEY(sha256,base));
    CREATE TABLE IF NOT EXISTS failures(key TEXT PRIMARY KEY,payload TEXT);
    ''');return db


def put(db,value):
    sha=digest(value)
    if db.execute('SELECT 1 FROM objects WHERE sha256=?',(sha,)).fetchone():return sha
    def pack(v,root=False):
        if isinstance(v,(dict,list)) and not root and len(canonical(v))>=1024:
            return {'$migration_object':put(db,v)}
        if isinstance(v,dict):return {k:pack(x) for k,x in v.items()}
        if isinstance(v,list):return [pack(x) for x in v]
        return v
    db.execute('INSERT OR IGNORE INTO objects VALUES (?,?)',(sha,zlib.compress(canonical(pack(value,True)).encode(),1)))
    return sha


def diff(old,new,path=()):
    if old==new:return []
    if isinstance(old,dict) and isinstance(new,dict):
        result=[]
        for k in sorted(old.keys()|new.keys()):
            if k not in old:result.append([list(path+(k,)),False,None])
            elif k not in new:result.append([list(path+(k,)),True,old[k]])
            else:result.extend(diff(old[k],new[k],path+(k,)))
        return result
    return [[list(path),True,old]]


def norm(v):
    if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [norm(x) for x in v]
    if isinstance(v,(set,frozenset)):return sorted((norm(x) for x in v),key=canonical)
    return v


def physical_manifest(v):
    if isinstance(v,dict):
        return {k:physical_manifest(x) for k,x in v.items() if not ({'path','offset','bytes','sha256','format'}<=v.keys() and k in ('path','offset'))}
    if isinstance(v,list):return [physical_manifest(x) for x in v]
    return v


def refs(v):
    if isinstance(v,dict):
        if {'path','offset','bytes','sha256','format'}<=v.keys():yield v
        else:
            for x in v.values():yield from refs(x)
    elif isinstance(v,list):
        for x in v:yield from refs(x)


class Transport:
    def __init__(self,db,root):self.db=db;self.root=root;self.manifests=OrderedDict();self.borrowed={};self.counts=Counter()
    def compressed(self,ref,base):
        path=Path(base)/ref['path']
        with path.open('rb') as f:f.seek(ref['offset']);data=f.read(ref['bytes'])
        if len(data)!=ref['bytes'] or hashlib.sha256(data).hexdigest()!=ref['sha256']:raise ValueError('source compressed block corrupt: '+str(path))
        return data
    def manifest(self,ref,base):
        key=str(Path(base).resolve()),ref['sha256']
        if key not in self.manifests:
            from native_storage import binary_decode
            self.manifests[key]=binary_decode(zlib.decompress(self.compressed(ref,base)))
            while len(self.manifests)>256:self.manifests.popitem(last=False)
        return self.manifests[key]
    def offer(self,ref,base):
        # Exact compressed content is sufficient even when global row positions
        # differ; the ORIGINAL parent manifest restores those positions.
        stack=[ref]
        while stack:
            item=stack.pop();key=item['sha256']
            if key not in self.borrowed:self.borrowed[key]=(item,Path(base))
            if item['format']=='arclog-native-v5':stack.extend(refs(self.manifest(item,base)))
        if len(self.borrowed)>20000:self.borrowed={}
    def preserve(self,ref,base):
        if self.db.execute('SELECT 1 FROM blocks WHERE sha256=?',(ref['sha256'],)).fetchone():return
        borrowed=self.borrowed.get(ref['sha256'])
        if borrowed:
            candidate=(borrowed[1]/borrowed[0]['path']).resolve()
            if candidate!=self.root and self.root not in candidate.parents:borrowed=None
        if borrowed:
            other,otherbase=borrowed
            if other['bytes']!=ref['bytes'] or other['format']!=ref['format']:raise ValueError('block identity collision')
            # Verify borrowed bytes once, rather than trusting an unvisited leaf.
            self.compressed(other,otherbase)
            self.db.execute('INSERT OR IGNORE INTO blocks VALUES (?,?,?,?,NULL)',(ref['sha256'],ref['bytes'],str((otherbase/other['path']).resolve()),other['offset']))
            self.counts['borrowed_blocks']+=1
        else:
            data=self.compressed(ref,base)
            self.db.execute('INSERT OR IGNORE INTO blocks VALUES (?,?,NULL,NULL,?)',(ref['sha256'],len(data),data));self.counts['preserved_bytes']+=len(data)
        if ref['format']=='arclog-native-v5':
            for child in refs(self.manifest(ref,base)):self.preserve(child,base)
    def same(self,a,abase,b,bbase):return physical_manifest(self.manifest(a,abase))==physical_manifest(self.manifest(b,bbase))


def source_roots(record):
    yield from refs(record.get('native',{}));yield from refs(record.get('full_replay',{}))


def current_locator(corpus,task,file,line):return dict(corpus=str(corpus.resolve()),task=task,file=file,line=line,stream='kept')

def read_locator(locator):
    if locator.get('json_path'):
        p=Path(locator['json_path']);raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
    return binding._read_locator(locator)


LAST_PROGRESS={}

def progress(start,done,total,**counts):
    now=time.monotonic()
    if done not in (1,total) and now-LAST_PROGRESS.get(start,0)<5:return
    LAST_PROGRESS[start]=now
    elapsed=time.monotonic()-start;rate=done/max(elapsed,.001)
    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={(total-done)/rate if rate else 0:.1f}s '+canonical(counts),flush=True)


def request(db,pair,sha,loc,result=None):
    db.execute('INSERT OR IGNORE INTO requests VALUES (?,?,?,?)',(sha,pair,canonical(loc),result))


def collect(a,db):
    base=open_ro(a.base);count=0
    for pair,source,result,text in base.execute('SELECT pair_id,source_sha256,result_sha256,record_json FROM pairs'):
        value=json.loads(text)
        if digest(value)!=result or value['source_sha256']!=source:raise ValueError('base result corrupt: '+pair)
        src=value['source'];loc=dict(src,task=value['task'],corpus=str(Path(src['corpus']).resolve()))
        if binding.legacy_path(Path(loc['corpus'])/loc['task']/loc['file']):request(db,pair,source,loc,result)
        count+=1
        if count%256==0:db.commit()
    base.close();db.commit()
    if a.population.exists():
        pop=open_ro(a.population)
        for pair,sha,text in pop.execute('SELECT pair_id,source_sha256,locator FROM observations'):
            loc=json.loads(text)
            if binding.legacy_path(Path(loc['corpus'])/loc['task']/loc['file']):request(db,pair,sha,loc)
        pop.close();db.commit()
    # Frozen judge source copies retain their exact hashes, but their native
    # references need the same content-addressed transport closure.
    manifests=set((DATA_ROOT/'judgetool/dataset-sources').glob('*/*/manifest.json'))
    for pattern in ('00[4-8]*','009*'):
        for trial in (DATA_ROOT/'judge3/trials').glob(pattern):manifests.update(trial.rglob('manifest.json'))
    for path in sorted(manifests):
        try:
            manifest=json.loads(path.read_text());source=manifest['adapter']['source'];native_base=Path(source['native_base'])
            if not binding.legacy_path(native_base):continue
            recpath=Path(source['record_path']);loc=dict(json_path=str(recpath.resolve()),native_base=str(native_base.resolve()))
            rec=read_locator(loc);request(db,digest(pair_key(rec)),digest(rec),loc)
            for ref in refs(manifest['adapter']):
                db.execute('INSERT OR IGNORE INTO extra_native VALUES (?,?,?)',(ref['sha256'],str(native_base.resolve()),canonical(ref)))
        except (KeyError,TypeError):continue
    db.commit()
    tasks={json.loads(r[0]).get('task') for r in db.execute('SELECT locator FROM requests')};tasks.discard(None)
    for loc, in db.execute('SELECT locator FROM requests'):
        if json.loads(loc).get('json_path'):tasks.add(read_locator(json.loads(loc))['task'])
    for task in sorted(tasks|{None} ,key=lambda x:x or ''):
        for name in (('run.json',) if task is None else (task+'/manifest.json',)):
            src=a.old/name
            if not src.exists():continue
            dest=a.output.parent/'metadata'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            raw=src.read_bytes()
            if not dest.exists():
                with dest.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            sync_directory(dest.parent)
            db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?)',(str(src.resolve()),str(dest),hashlib.sha256(raw).hexdigest()))
    for folder in (a.output.parent/'metadata',a.output.parent,a.output.parent.parent):
        if folder.exists():sync_directory(folder)
    db.commit()
    print('requests',db.execute('SELECT count(*) FROM requests').fetchone()[0],flush=True)


def scan(a,db):
    from mutant_names import source_header
    wanted={}
    for pair,loc in db.execute('SELECT pair_id,locator FROM requests'):
        v=json.loads(loc);task=v.get('task') or read_locator(v)['task']
        wanted.setdefault(task,set()).add(pair)
    tasks=sorted(wanted);start=time.monotonic();done=0
    for task in tasks:
        requests=wanted[task];request_signature=digest(sorted(requests))
        from judge3.framed_jsonl import JsonlReader
        with JsonlReader(a.new/task/'pairs.jsonl') as source:file=source.path
        if not file.exists():raise ValueError('published v12 task missing: '+task)
        stat=file.stat();signature=canonical([stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,request_signature])
        previous=db.execute('SELECT signature,line,complete FROM scans WHERE path=?',(str(file),)).fetchone()
        if previous and previous[0]==signature and previous[2]:done+=1;continue
        after=previous[1] if previous and previous[0]==signature else 0;n=after;last=time.monotonic()
        if previous and previous[0]!=signature:
            with db:db.execute("DELETE FROM matches WHERE json_extract(locator,'$.task')=?",(task,))
        with JsonlReader(file) as source:
            for n,raw in enumerate(source.iter_lines(start_line=after+1),after+1):
                try:header=source_header(raw.decode('utf-8'));pair=digest(pair_key(header))
                except (KeyError,ValueError,TypeError):continue
                if pair in requests:
                    loc=current_locator(a.new,task,file.name,n)
                    db.execute('INSERT OR IGNORE INTO matches VALUES (?,?)',(pair,canonical(loc)))
                if n%256==0:
                    db.execute('INSERT OR REPLACE INTO scans VALUES (?,?,?,0)',(str(file),signature,n));db.commit()
                    if time.monotonic()-last>=5:
                        progress(start,done,len(tasks),task=task,source_line=n);last=time.monotonic()
        db.execute('INSERT OR REPLACE INTO scans VALUES (?,?,?,1)',(str(file),signature,n));db.commit();done+=1;progress(start,done,len(tasks))


def prepare(record,base):
    import algorithm as A
    from native_storage import load_native
    from filters import native
    G=native(load_native(record['native']['gold'],base));X=native(load_native(record['native']['mutant'],base));e=record['evaluation'];n=len(e['kept_assignments']);trains=A.training_scope(record,G)
    available,issues=A.inventory(record,base,G,trains,n)
    gold=A.Observation.read(G,e['table_indices']['gold_kept'],e['gold_kept_assignment_map'],n,trains)
    mutant=A.Observation.read(X,e['table_indices']['mutant_kept'],e['mutant_kept_assignment_map'],n,trains)
    return gold,mutant,available,issues


def source_key(table):
    i=table['identity'];return canonical(dict(fact=i.get('fact'),form=i.get('form'),relation=i.get('relation'),proof=i.get('proof'),types=table['types']))


def id_structure(parts):
    """Encode typed model SETs into one relation for canonical _id_equal.

    Model nodes are existential IDs in their own column, not ordinal pairing.
    A unique sentinel anchor keeps padding distinct from actual native Ids.
    """
    maximum=max((sum(t=='Ident' for t in types) for _,types,_ in parts),default=0)
    rows=set();model=-2
    tags={}
    # Non-Ident content is itself the Number tag (integer IDs assigned jointly
    # by the caller); all identifier equality stays in canonical _id_equal.
    for scope,types,family in parts:
        for values in family:
            model_id=model;model-=1
            tag=canonical([scope,types,'model'])
            rows.add((tag,(model_id,))+((-1,),)*maximum)
            for value in values:
                ids=tuple(c for c,t in zip(value,types) if t=='Ident')
                if any(len(c)!=1 or c[0]<0 for c in ids):raise ValueError('unsupported native Ident representation')
                rest=[(i,c) for i,(c,t) in enumerate(zip(value,types)) if t!='Ident']
                tag=canonical([scope,types,rest])
                rows.add((tag,(model_id,))+ids+((-1,),)*(maximum-len(ids)))
    rows.add(('__sentinel__',(-1,))+((-1,),)*maximum)
    return rows,maximum


def equal_parts(left,right,seconds=5):
    if norm(left)==norm(right):return True
    labels=[canonical(a) for a,_,_ in left]
    if len(labels)!=len(set(labels)):return False
    if [(a,b) for a,b,_ in left]!=[(a,b) for a,b,_ in right]:return False
    from tables import _id_equal
    a,ma=id_structure(left);b,mb=id_structure(right)
    if ma!=mb:return False
    tags={x:i for i,x in enumerate(sorted({r[0] for r in a|b}))}
    encode=lambda rows:frozenset(((tags[r[0]],),)+r[1:] for r in rows)
    return _id_equal(encode(a),encode(b),['Number']+['Ident']*(ma+1),time.monotonic()+seconds)


def parts(prepared,assignment,*,tests=False):
    G,X,sources,_=prepared;result=[]
    for tag,obs in [('G',G),('X',X)]:
        if tests:
            axes,families=obs.test_family(assignment)
        else:axes=range(len(obs.families[assignment]));families=obs.families[assignment]
        for axis,family in zip(axes,families):result.append(((tag,axis),obs.types,family))
    if not tests:
        for table in sorted(sources[assignment],key=source_key):
            for train,rows in enumerate(table['rows']):result.append(((source_key(table),train),table['types'],frozenset((rows,))))
    return result



TASK_COUNTS={}

def replay_parts(record,base,prepared):
    """Shared kept reader, including TEST values of every used inventory table.

    Compare raw native fields (including Example) rather than rebuilding their
    projection policy. Equality of this stronger footprint preserves the
    canonical selector's projected inputs as well.
    """
    import algorithm as A
    from evaluator import legacy_helpers
    from tables import kept_groups
    if record['task'] not in TASK_COUNTS:
        cfg=json.loads((DATA_ROOT/'ast/run/corpus-v12-body-full/run.json').read_text())
        task=json.loads((Path(cfg['tasks'])/(record['task']+'.json')).read_text())
        TASK_COUNTS[record['task']]=(len(task['train']),len(task['test']))
    ntrain,ntest=TASK_COUNTS[record['task']];G,X,available,_=prepared
    full=A.native(A.load_native(record['full_replay']['gold'],base))
    L=legacy_helpers();cache={};result=[]
    for assignment,tables in enumerate(available):
        result.extend(((assignment,'train',scope),types,family) for scope,types,family in parts(prepared,assignment))
        result.extend(((assignment,'test',scope),types,family) for scope,types,family in parts(prepared,assignment,tests=True))
        for source in sorted(tables,key=source_key):
            identity=source['identity'];table=identity['table']
            snapshot=G.snapshot if identity.get('proof')=='det_independent_native_fact' else full
            key=id(snapshot),table
            if key not in cache:
                schema,_,_=A.rows_at(snapshot,table)
                grouped=kept_groups(L,snapshot,table,record,ntrain,ntest)
                if grouped['missing'] or set(grouped['groups'])!=set(grouped['required']) or not all(grouped['groups'].values()):
                    raise ValueError('available TRAIN/TEST contexts incomplete')
                cache[key]=(tuple(t for t,_ in schema),grouped['groups'])
            types,groups=cache[key]
            for (a,kind,index),family in sorted(groups.items()):
                if a==assignment:result.append((('available_raw',source_key(source),a,kind,index),types,frozenset(family)))
    return result

def assess(old,oldbase,new,newbase,transport,a):
    programs=all(old.get(k)==new.get(k) for k in ('programs','audit')) and pair_key(old)==pair_key(new)
    maps=all(old['evaluation'].get(k)==new['evaluation'].get(k) for k in ('kept_assignments','gold_kept_assignment_map','mutant_kept_assignment_map','table_indices'))
    def inventory_contract(record):
        replay=record.get('full_replay',{});e=replay.get('evaluation',{})
        return (replay.get('scope'),replay.get('ident_namespace'),e.get('kept_assignments'),e.get('gold_assignment_map'))
    maps=maps and inventory_contract(old)==inventory_contract(new)
    same={}
    for side in ('gold','mutant','full'):
        x=old.get('full_replay',{}).get('gold') if side=='full' else old.get('native',{}).get(side)
        y=new.get('full_replay',{}).get('gold') if side=='full' else new.get('native',{}).get(side)
        same[side]=bool(x and y and transport.same(x,oldbase,y,newbase))
    full=programs and maps and all(same.values())
    comparable=True;errors=[];per=[];tests=[];replay_equal=full;named_layouts_equal=full
    if full:
        per=[True]*len(old['evaluation']['kept_assignments']);tests=list(per)
    else:
        try:
            left=prepare(old,oldbase);right=prepare(new,newbase)
            named_layouts_equal=all(norm(a.snapshot['_native_reader'].schema(a.table))==norm(b.snapshot['_native_reader'].schema(b.table)) for a,b in zip(left[:2],right[:2]))
            n=len(old['evaluation']['kept_assignments'])
            kept=old['evaluation']['kept_assignments']==new['evaluation']['kept_assignments']
            for i in range(len(new['evaluation']['kept_assignments'])):
                per.append(bool(programs and kept and i<n and equal_parts(parts(left,i),parts(right,i),a.compare_seconds)))
                try:tests.append(bool(programs and kept and i<n and equal_parts(parts(left,i,tests=True),parts(right,i,tests=True),a.compare_seconds)))
                except (ValueError,IndexError,KeyError):tests.append(False)
            try:replay_equal=equal_parts(replay_parts(old,oldbase,left),replay_parts(new,newbase,right),a.compare_seconds)
            except (ValueError,KeyError,IndexError) as error:errors.append('replay footprint: '+str(error))
        except Exception as error:
            comparable=False;errors.append(type(error).__name__+': '+str(error))
    base_equal=full or bool(per) and all(per)
    # Whole-program/reader operations have explicit and separate input scopes.
    stable_program=programs and old['evaluation'].get('kept_assignments')==new['evaluation'].get('kept_assignments')
    flags=dict(base=base_equal,program=stable_program,normal=programs and same['gold'] and same['full'],normal_program=programs,
               fits=stable_program and base_equal and named_layouts_equal and bool(tests) and all(tests),
               lib=stable_program and replay_equal and named_layouts_equal,
               targets=stable_program and replay_equal and named_layouts_equal,
               judge=stable_program and replay_equal and named_layouts_equal,
               clauses=stable_program and replay_equal and named_layouts_equal,
               tests=stable_program and replay_equal,det_fit=stable_program and same['gold'])
    return dict(schema='v12-input-binding-v1',programs_equal=programs,manifest_equal=same,assignment_equal=per,
        test_assignment_equal=tests,named_layouts_equal=named_layouts_equal,replay_inputs_equal=replay_equal,compatible=flags,comparison_complete=comparable,issues=errors)


def bind(a,db):
    t=Transport(db,a.new);rows=list(db.execute('SELECT old_sha,pair_id,locator FROM requests ORDER BY json_extract(locator,\'$.task\'),json_extract(locator,\'$.file\'),json_extract(locator,\'$.line\')'))
    start=time.monotonic();counts=Counter()
    for done,(sha,pair,text) in enumerate(rows,1):
        if db.execute('SELECT 1 FROM sources WHERE old_sha=?',(sha,)).fetchone():
            counts['resumed']+=1;progress(start,done,len(rows),**counts);continue
        loc=json.loads(text);old=read_locator(loc)
        if digest(old)!=sha:raise ValueError('old source bytes differ: '+sha)
        oldbase=Path(loc['native_base']) if loc.get('json_path') else Path(loc['corpus'])/old['task']
        match=db.execute('SELECT locator FROM matches WHERE pair_id=?',(pair,)).fetchone()
        if match:
            current=json.loads(match[0]);new=read_locator(current);newbase=Path(current['corpus'])/old['task']
            if pair_key(old)!=pair_key(new) or old.get('programs')!=new.get('programs') or old.get('audit')!=new.get('audit'):
                raise ValueError('same pair_id has changed program/audit; needs explicit native correspondence: '+pair)
            for ref in source_roots(new):t.offer(ref,newbase)
            proof=assess(old,oldbase,new,newbase,t,a);counts['fast' if all(proof['manifest_equal'].values()) else 'semantic']+=1
        else:
            # Genuine v11-only members keep exact original source bytes, inside
            # the ONE v12 corpus root. No redraw and no silent loss of labels.
            root=a.output.parent/'legacy'/sha;dest=root/old['task'];dest.mkdir(parents=True,exist_ok=True)
            target=dest/'pairs.jsonl.zst'
            from judge3.framed_jsonl import JsonlWriter
            with JsonlWriter(target) as out:
                if out.committed_lines==0:out.write(old)
                elif out.committed_lines!=1:raise ValueError('legacy capsule has extra records')
            for original,filename in ((a.old/'run.json',root/'run.json'),(a.old/old['task']/'manifest.json',dest/'manifest.json')):
                if original.exists() and not filename.exists():
                    shutil.copyfile(original,filename)
                    with filename.open('rb') as f:os.fsync(f.fileno())
            for folder in (dest,root,root.parent,a.output.parent):sync_directory(folder)
            current=current_locator(root,old['task'],target.name,1);new=old;newbase=dest
            proof=dict(schema='v12-input-binding-v1',legacy_only=True,compatible={k:True for k in ('base','program','normal','normal_program','fits','lib','targets','judge','clauses','tests','det_fit')},assignment_equal=[True]*len(old['evaluation']['kept_assignments']))
            counts['legacy_only']+=1
        proof.update(pair_id=pair,old_source_sha256=sha,current_source_sha256=digest(new),
            current_locator_sha256=digest(current),old_native_roots_sha256=digest(list(source_roots(old))),
            current_native_roots_sha256=digest(list(source_roots(new))))
        try:
            for ref in source_roots(old):t.preserve(ref,oldbase)
            with db:
                patch=put(db,diff(old,new));proof_ref=put(db,proof)
                db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?)',(sha,pair,digest(new),canonical(current),patch,proof_ref))
                db.execute('DELETE FROM failures WHERE key=?',(sha,))
            counts['written']+=1
        except Exception as error:
            db.rollback()
            with db:db.execute('INSERT OR REPLACE INTO failures VALUES (?,?)',(sha,canonical(dict(reason=str(error),phase='bind'))))
            raise
        progress(start,done,len(rows),**counts,**t.counts)

    # Other-case tables in frozen/paused judge adapters may not belong to any
    # labeled pair. Preserve those exact native closures as well.
    for root,ref in db.execute('SELECT base,reference FROM extra_native'):
        with db:t.preserve(json.loads(ref),Path(root))


def remap_witness(witness,old_available,new_available):
    value=deepcopy(witness);new={source_key(t):i for i,t in enumerate(new_available)}
    def atom(v):
        if isinstance(v,dict):
            if v.get('kind') in ('semijoin','antijoin'):
                key=source_key(old_available[v['available']])
                if key not in new:raise ValueError('old witness source absent')
                if sum(source_key(t)==key for t in old_available)!=1 or sum(source_key(t)==key for t in new_available)!=1:
                    raise ValueError('witness source correspondence ambiguous')
                v['available']=new[key]
            for child in v.values():atom(child)
        elif isinstance(v,list):
            for child in v:atom(child)
    atom(value);return value


def refresh(oldbase,old,oldroot,new,newroot,proof,a):
    """Use canonical one_pair bytecode, with an input-bound solve cache.

    Old bounds remain unknown. Positives on changed contexts are directly
    reverified. Only cache misses run the existing solver/baseline implementation.
    """
    import algorithm as A
    try:oldprep=prepare(old,oldroot)
    except (ValueError,KeyError,IndexError):
        if oldbase.get('per_assignment'):raise
        # No stored search result exists to reuse: compute only this changed
        # pair through the canonical algorithm, owing full-Gold TEST below.
        def no_compact_test(*args):return None,'v12 inputs changed: full Gold witness TEST check owed'
        one=A.bind_function(A.one_pair,generalization=no_compact_test)
        config=oldbase.get('config',{})
        result=one(new,str(newroot),config.get('seconds',1),config.get('baseline_seconds',.5))
        return result,[],dict(new_pair_searches=1)
    newprep=prepare(new,newroot);OG,OX,OA,_=oldprep;NG,NX,NA,_=newprep
    prior={};reused=Counter();aliases=[]
    for i,item in enumerate(oldbase.get('per_assignment',[])):
        prior[(i,'main',None)]=(item['witness'],OG.types,OG.families[i],OX.types,OX.families[i],OA[i])
        for kind,obs in [('sibling',OG),('redundant',OX)]:
            for p in item.get(kind+'_searches',[]):
                idx=p['source_index'];source=OA[i][idx];family=tuple(frozenset((r,)) for r in source['rows']);companions=OA[i][:idx]+OA[i][idx+1:]
                prior[(i,kind,source_key(source))]=(p,obs.types,obs.families[i],source['types'],family,companions)
    calls=[]
    for i,available in enumerate(NA):
        calls.append((i,'main',None))
        for table in available:
            calls.extend([(i,'sibling',source_key(table)),(i,'redundant',source_key(table))])
    cursor=iter(calls)
    def cached_solve(types,target,source_types,source,available,seconds):
        key=next(cursor);entry=prior.get(key)
        if entry:
            oldproof,ot,og,ox,om,oa=entry
            try:
                mapped=remap_witness(oldproof,oa,available)
                lhs=[(('G',n),ot,f) for n,f in enumerate(og)]+[(('X',n),ox,f) for n,f in enumerate(om)]
                rhs=[(('G',n),types,f) for n,f in enumerate(target)]+[(('X',n),source_types,f) for n,f in enumerate(source)]
                for tables,parts_out in ((oa,lhs),(available,rhs)):
                    for table in sorted(tables,key=source_key):
                        for n,rows in enumerate(table['rows']):parts_out.append(((source_key(table),n),table['types'],frozenset((rows,))))
                same=equal_parts(lhs,rhs,a.compare_seconds)
                if same:
                    reused['reused_searches']+=1;return mapped
                if mapped.get('recoverable') is True:
                    deadline=time.monotonic()+a.compare_seconds
                    def budget():
                        if time.monotonic()>deadline:raise A.recovery.SearchBound('migration direct verification bound')
                    if A.recovery.verify(target,source,mapped,available,budget=budget,mutant_types=source_types):
                        reused['reverified_positives']+=1;return mapped
            except (ValueError,IndexError,KeyError,A.recovery.SearchBound):pass
        reused['new_searches']+=1
        return A.solve(types,target,source_types,source,available,seconds)
    def generalization(gold,mutant,assignment,witness):
        previous=next((x for x in oldbase.get('per_assignment',[]) if x['assignment']==assignment),None)
        same_application=False
        if previous and previous.get('witness',{}).get('recoverable') is True:
            try:
                mapped=remap_witness(previous['witness'],OA[assignment],NA[assignment])
                expression=lambda w:(w.get('projection'),w.get('selection_any',[w.get('selection',[])]))
                same_application=expression(mapped)==expression(witness)
            except (ValueError,IndexError,KeyError):pass
        compatible_test=binding.application_compatible(proof,assignment,witness)
        if same_application and compatible_test:
            aliases.append((assignment,digest(previous['witness']),digest(witness)))
            return previous.get('test_verified'),previous.get('test_reason')
        # Newly selected applications need the existing full-Gold TEST pass,
        # not a new private evaluator or a compact train-table substitution.
        return None,'v12 inputs changed: full Gold witness TEST check owed'
    baseline=A.bind_function(A.baseline_searches,solve=cached_solve)
    one=A.bind_function(A.one_pair,solve=cached_solve,baseline_searches=baseline,generalization=generalization)
    config=oldbase.get('config',{});result=one(new,str(newroot),config.get('seconds',1),config.get('baseline_seconds',.5))
    return result,aliases,dict(reused)


def apply(a,db):
    import algorithm as A
    if db.execute('SELECT count(*) FROM requests').fetchone()!=db.execute('SELECT count(*) FROM sources').fetchone():raise ValueError('source binding phase incomplete')
    if db.execute('SELECT count(*) FROM extra_native e LEFT JOIN blocks b ON e.sha256=b.sha256 WHERE b.sha256 IS NULL').fetchone()[0]:raise ValueError('frozen native closure phase incomplete')
    live=sqlite3.connect(a.base,timeout=120);live.execute('PRAGMA synchronous=FULL')
    start=time.monotonic();rows=list(live.execute('SELECT pair_id,source_sha256,result_sha256 FROM pairs'));counts=Counter()
    import run as runner
    manifest=runner.code_manifest(HERE.parent,HERE/'algorithm.py')
    manifest['files']['mech/move_v12.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest['files']['mech/source_bindings.py']=hashlib.sha256((HERE/'source_bindings.py').read_bytes()).hexdigest()
    manifest_sha=digest(manifest);runner_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    algorithm_sha=hashlib.sha256(Path(A.__file__).read_bytes()).hexdigest()
    for done,(pair,source,oldsha) in enumerate(rows,1):
        text=live.execute('SELECT record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()[0]
        previous=db.execute('SELECT current_result,applied FROM base_changes WHERE pair_id=?',(pair,)).fetchone()
        if previous and previous[0]==oldsha:
            if not previous[1]:
                with db:db.execute('UPDATE base_changes SET applied=1,forward_ref=NULL WHERE pair_id=?',(pair,))
            counts['resumed']+=1;progress(start,done,len(rows),**counts);continue
        pending=db.execute('SELECT old_result,current_result,forward_ref FROM base_changes WHERE pair_id=? AND applied=0',(pair,)).fetchone()
        if pending and pending[0]==oldsha:
            successor=binding.reverse_patch(json.loads(text),binding.object_value(db,pending[2]))
            if digest(successor)!=pending[1]:raise ValueError('pending successor corrupt')
            with live:live.execute('UPDATE pairs SET source_sha256=?,code_sha256=?,config_sha256=?,result_sha256=?,record_json=? WHERE pair_id=? AND result_sha256=?',(successor['source_sha256'],successor['code_sha256'],successor['config_sha256'],pending[1],canonical(successor),pair,oldsha))
            with db:db.execute('UPDATE base_changes SET applied=1,forward_ref=NULL WHERE pair_id=?',(pair,))
            counts['recovered_commit']+=1;continue
        entry=db.execute('SELECT current_sha,current_locator,proof_ref FROM sources WHERE old_sha=?',(source,)).fetchone()
        if not entry:
            # A committed base row may be between its commit and journal's
            # applied flag after a crash; validate and finish that transaction.
            pending=db.execute('SELECT current_result FROM base_changes WHERE pair_id=? AND applied=0',(pair,)).fetchone()
            if pending and pending[0]==oldsha:
                with db:db.execute('UPDATE base_changes SET applied=1,forward_ref=NULL WHERE pair_id=?',(pair,))
                counts['recovered_commit']+=1;continue
            raise ValueError('canonical base source was not bound: '+pair)
        value=json.loads(text)
        if digest(value)!=oldsha:raise ValueError('base corrupt before cutover')
        new=read_locator(json.loads(entry[1]));proof=binding.object_value(db,entry[2]);old=binding.record(source);oldroot=Path(value['source']['corpus'])/value['task'];newloc=json.loads(entry[1]);newroot=Path(newloc['corpus'])/value['task']
        migrated=deepcopy(value);aliases=[];counters={}
        if proof['compatible']['base'] and not value.get('error'):
            # Collection completeness may improve even with identical rows.
            # Reuse all search facts; only the canonical scalar reduction changes.
            def inventory_envelope(record):
                r=record.get('full_replay',{});e=r.get('evaluation',{})
                return (r.get('scope'),r.get('ident_namespace'),e.get('kept_assignments'),
                    e.get('gold_assignment_map'),e.get('gold_status',{}).get('status'),
                    e.get('gold_collection',{}).get('materialization_complete'),e.get('gold_observation_stop'))
            if inventory_envelope(old)==inventory_envelope(new):
                issues=value.get('available_incomplete',[])
            else:_,_,_,issues=prepare(new,newroot)
            assignments=deepcopy(value.get('per_assignment',[]))
            for item in assignments:
                if not binding.application_compatible(proof,item['assignment'],item.get('witness',{})):
                    item['test_verified']=None;item['test_reason']='v12 inputs changed: full Gold witness TEST check owed'
            migrated['per_assignment']=assignments
            refreshed=A.classify(new,assignments,not issues,value.get('error'))
            migrated['available_incomplete']=issues
            migrated.update(refreshed);counts['base_reused']+=1
        else:
            refreshed,aliases,counters=refresh(value,old,oldroot,new,newroot,proof,a);migrated.update(refreshed);counts.update(counters);counts['base_changed']+=1
        migrated.update(source_sha256=entry[0],source={k:newloc[k] for k in ('corpus','file','line','stream')},retained=new.get('retained'),reasons=new.get('rejection_reasons',[]),old=new.get('code_label'))
        # Original producer metadata describes retained facts. New search facts
        # carry their own producer/operation ledger in this binding proof.
        proof=dict(proof,refresh=dict(algorithm_sha256=algorithm_sha,counts=counters))
        migrated.update(code_manifest=manifest,code_sha256=manifest_sha,runner_sha256=runner_sha,
            source_binding=dict(database=str(a.output),old_source_sha256=source,current_source_sha256=entry[0],old_result_sha256=oldsha,input_proof_sha256=entry[2]))
        result=digest(migrated)
        with db:
            p=put(db,diff(value,migrated));ref=put(db,proof)
            forward=put(db,diff(migrated,value))
            db.execute('INSERT OR REPLACE INTO base_changes VALUES (?,?,?,?,0,?,?)',(pair,oldsha,result,p,ref,forward))
            for assignment,before,after in aliases:db.execute('INSERT OR REPLACE INTO witness_aliases VALUES (?,?,?,?)',(pair,assignment,before,after))
        with live:
            changed=live.execute('UPDATE pairs SET source_sha256=?,code_sha256=?,config_sha256=?,result_sha256=?,record_json=? WHERE pair_id=? AND result_sha256=?',(entry[0],migrated['code_sha256'],migrated['config_sha256'],result,canonical(migrated),pair,oldsha)).rowcount
            if changed!=1:raise ValueError('another writer changed base during cutover')
        with db:db.execute('UPDATE base_changes SET applied=1,forward_ref=NULL WHERE pair_id=?',(pair,))
        progress(start,done,len(rows),**counts)
    live.close()
    if a.population.exists():
        pop=sqlite3.connect(a.population,timeout=120);pop.execute('PRAGMA synchronous=FULL')
        for pair,sha,text in list(pop.execute('SELECT pair_id,source_sha256,locator FROM observations')):
            entry=db.execute('SELECT current_sha,current_locator FROM sources WHERE old_sha=?',(sha,)).fetchone()
            if entry:
                with pop:pop.execute('UPDATE observations SET source_sha256=?,locator=? WHERE pair_id=? AND source_sha256=?',(entry[0],entry[1],pair,sha))
        pop.close()
    with db:db.execute("INSERT OR REPLACE INTO metadata VALUES ('active','true')")


OLD_OPEN_ATTEMPTS=[]

def deny_old_reads():
    original=(builtins.open,io.open,os.open)
    def check(path):
        if isinstance(path,(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(path)).resolve()
            if p==binding.OLD.resolve() or binding.OLD.resolve() in p.parents:
                OLD_OPEN_ATTEMPTS.append(str(p))
                raise RuntimeError('AUDIT denied v11 open: '+str(p))
    def b(path,*args,**kwargs):check(path);return original[0](path,*args,**kwargs)
    def i(path,*args,**kwargs):check(path);return original[1](path,*args,**kwargs)
    def o(path,*args,**kwargs):check(path);return original[2](path,*args,**kwargs)
    builtins.open=b;io.open=i;os.open=o


def dependency_state(a,db):
    base=open_ro(a.base)
    try:base_digest=digest(list(base.execute('SELECT pair_id,source_sha256,result_sha256 FROM pairs ORDER BY pair_id')))
    finally:base.close()
    pop_digest=None
    if a.population.exists():
        pop=open_ro(a.population)
        try:pop_digest=digest(list(pop.execute('SELECT pair_id,source_sha256,locator FROM observations ORDER BY pair_id')))
        finally:pop.close()
    files=list(db.execute('SELECT original,destination,sha256 FROM files ORDER BY original'))
    for original,dest,sha in files:
        if hashlib.sha256(Path(dest).read_bytes()).hexdigest()!=sha:raise ValueError('preserved metadata changed: '+dest)
    return dict(base_digest=base_digest,population_digest=pop_digest,
        source_proofs_digest=digest(list(db.execute('SELECT old_sha,current_sha,current_locator,patch_ref,proof_ref FROM sources ORDER BY old_sha'))),
        blocks_digest=digest(list(db.execute('SELECT sha256,bytes,path,offset FROM blocks ORDER BY sha256'))),
        metadata_digest=digest(files))


def audit(a,db):
    if not binding.active():raise ValueError('cutover is not active')
    deny_old_reads();start=time.monotonic();counts=Counter();issues=[];verified=set()
    from source_read import SourceReader
    from read_grades import StudyReader
    sources=SourceReader(CODE_ROOT);base=open_ro(a.base);verified_sources=set()
    from native_storage import read_block
    def closure(ref,root):
        if ref['sha256'] in verified:return
        value=read_block(ref,root);verified.add(ref['sha256'])
        if ref['format']=='arclog-native-v5':
            for child in refs(value):closure(child,root)
    for sha,pair,locator,patch,proof in db.execute("SELECT old_sha,pair_id,current_locator,patch_ref,proof_ref FROM sources ORDER BY json_extract(current_locator,'$.task'),json_extract(current_locator,'$.line')"):
        current_loc=json.loads(locator)
        rec=sources.record(dict(task=current_loc['task'],source_sha256=sha,source=current_loc))
        verified_sources.add(binding.source_entry(sha)['current_sha'])
        if digest(rec)!=sha:raise ValueError('historical input binding failed')
        loc=json.loads(db.execute('SELECT locator FROM requests WHERE old_sha=?',(sha,)).fetchone()[0])
        root=Path(loc['native_base']) if loc.get('native_base') else Path(loc['corpus'])/rec['task']
        for ref in source_roots(rec):closure(ref,root)
        counts['source_closures']+=1
        if counts['source_closures']%256==0:progress(start,counts['source_closures'],db.execute('SELECT count(*) FROM sources').fetchone()[0],**counts)
    for root,ref in db.execute('SELECT base,reference FROM extra_native'):
        closure(json.loads(ref),Path(root));counts['extra_native_roots']+=1
    for pair,sha,text in base.execute("SELECT pair_id,source_sha256,record_json FROM pairs ORDER BY json_extract(record_json,'$.task'),json_extract(record_json,'$.source.line')"):
        value=json.loads(text);entry=binding.source_entry(sha)
        if sha not in verified_sources or entry is None:raise ValueError('live base source not v12-bound')
        actual=dict(value['source'],task=value['task']);expected=entry['locator']
        if any(actual[k]!=expected[k] for k in ('corpus','task','file','line')):raise ValueError('base source locator not current')
        corpus=Path(value['source']['corpus']).resolve()
        if corpus==binding.OLD.resolve() or binding.OLD.resolve() in corpus.parents:raise ValueError('base retains physical v11 locator')
        counts['base_sources']+=1
    base.close();sources.close()
    # All unique native blocks (including leaves omitted by a damaged manifest)
    # are verified once, never by replay or repeated reconstruction per pair.
    for sha,n,path,offset in db.execute('SELECT sha256,bytes,path,offset FROM blocks'):
        if sha not in verified:
            raw=binding.read_native_bytes(dict(sha256=sha,bytes=n,path='native/tables.pack'),a.old)
            if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('transport block changed: '+sha)
        counts['native_blocks']+=1
    with StudyReader(paths=dict(base=a.base)) as reader:
        for result in reader.read_pairs():
            counts['joined_pairs']+=1
            counts['grade:'+str(result.get('grade',result.get('status','unknown')))]+=1
    # Frozen checked submissions retain the REAL historical source identity.
    # Validate each via its owner; no judge invocation or outcome rewrite.
    from judge3.judge_workflows import load_submission
    seen=set()
    for trial in (DATA_ROOT/'judge3/trials').glob('00[4-8]*'):
        for path in trial.rglob('submissions/*.json'):
            if path in seen:continue
            seen.add(path)
            loaded=load_submission(path)
            if loaded.get('status')!='available':issues.append(dict(path=str(path),reason=loaded.get('reason')))
            counts['judge_submissions']+=1
    if a.population.exists():
        pop=open_ro(a.population)
        for pair,sha,text in pop.execute('SELECT pair_id,source_sha256,locator FROM observations'):
            loc=json.loads(text);corpus=Path(loc['corpus']).resolve()
            if binding.OLD.resolve() in corpus.parents or corpus==binding.OLD.resolve():raise ValueError('consumer still locates v11')
        pop.close()
    if OLD_OPEN_ATTEMPTS:raise ValueError('old physical reads attempted, including caught errors: '+canonical(OLD_OPEN_ATTEMPTS[:10]))
    if issues:raise ValueError('frozen judge receipts unavailable: '+canonical(issues[:3]))
    baseline_count=db.execute("SELECT value FROM metadata WHERE key='base_pair_count'").fetchone()[0]
    if counts['base_sources']!=int(baseline_count):raise ValueError('base population count changed')
    state=dict(schema='v12-no-old-reader-audit-v1',base_rows=counts['base_sources'],counts=dict(counts),old_open_attempts=0,
        registry_sources=db.execute('SELECT count(*) FROM sources').fetchone()[0],base_changes=db.execute('SELECT count(*) FROM base_changes WHERE applied=1').fetchone()[0],
        dependencies=dependency_state(a,db),completed_at=time.time())
    dest=a.output.parent/'no-v11-readers.json';temp=dest.with_suffix('.tmp')
    with temp.open('w') as stream:stream.write(canonical(state)+'\n');stream.flush();os.fsync(stream.fileno())
    temp.replace(dest);sync_directory(dest.parent);print(canonical(state),flush=True)


def deletion_check(a,db):
    state=json.loads((a.output.parent/'no-v11-readers.json').read_text())
    if state['old_open_attempts'] or not binding.active():raise ValueError('no completed v11-denial audit')
    if dependency_state(a,db)!=state['dependencies']:raise ValueError('reader inputs changed since audit; rerun audit')
    if db.execute('SELECT count(*) FROM failures').fetchone()[0]:raise ValueError('unresolved migration failure')
    print('v11 deletion dependency check passed',flush=True)


def delete(a,db):
    deletion_check(a,db)
    if a.old!=DATA_ROOT/'ast/run/corpus-v11' or a.old.is_symlink():raise ValueError('unexpected deletion root')
    shutil.rmtree(a.old)
    print('deleted '+str(a.old),flush=True)



def owed(a,db):
    """Derive the changed-footprint work list; no duplicate facts or job launches."""
    from judge3.framed_jsonl import JsonlWriter
    rows=list(db.execute('SELECT pair_id,old_sha,current_sha,proof_ref FROM sources ORDER BY old_sha'))
    path=a.output.parent/('changed-inputs-'+digest(rows)[:16]+'.jsonl.zst')
    with JsonlWriter(path) as out:
        for number,(pair,old,current,ref) in enumerate(rows):
            if number<out.committed_lines:continue
            flags=binding.object_value(db,ref)['compatible']
            out.write(dict(pair_id=pair,old_source_sha256=old,source_sha256=current,
                source_proof_sha256=ref,changed_scopes=[k for k,v in flags.items() if v is not True]))
    print('changed-input work list: '+str(path),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['collect','scan','bind','apply','audit','deletion-check','delete','owed']);p.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3');p.add_argument('--old',type=Path,default=binding.OLD);p.add_argument('--new',type=Path,default=DATA_ROOT/'ast/run/corpus-v12-body-full');p.add_argument('--output',type=Path,default=binding.DATABASE);p.add_argument('--population',type=Path,default=DATA_ROOT/'ast/run/substitute-population-v3/consumed/population.sqlite3');p.add_argument('--compare-seconds',type=float,default=5)
    a=p.parse_args();a.output=a.output.resolve();a.old=a.old.resolve();a.new=a.new.resolve();a.base=a.base.resolve()
    os.environ['STUDY_SOURCE_BINDINGS']=str(a.output);a.output.parent.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        locks=[str(a.output)+'.lock']
        if a.phase in ('apply','deletion-check','delete'):locks += [str(a.base)+'.lock',str(a.population)+'.lock']
        if a.phase in ('deletion-check','delete'):
            locks += [str(DATA_ROOT/'ast/run'/p) for p in (
                'mech/settled.postprocess.lock','mech2/normal.lock','mech3/step4.lock','mech4/lib.lock','mech5/targets.lock')]
        for lockpath in locks:
            Path(lockpath).parent.mkdir(parents=True,exist_ok=True);lock=stack.enter_context(open(lockpath,'a'));fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=setup(a.output)
        with db:
            for k,v in dict(base=str(a.base),old=str(a.old),new=str(a.new)).items():
                old=db.execute('SELECT value FROM metadata WHERE key=?',(k,)).fetchone()
                if old and old[0]!=v:raise ValueError('migration input location changed')
                db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',(k,v))
            if a.phase=='collect':
                x=open_ro(a.base);n=x.execute('SELECT count(*) FROM pairs').fetchone()[0];x.close();db.execute("INSERT OR IGNORE INTO metadata VALUES ('base_pair_count',?)",(str(n),))
        try:globals()[a.phase.replace('-','_')](a,db)
        finally:db.close()
if __name__=='__main__':main()
