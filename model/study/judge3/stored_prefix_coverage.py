#!/usr/bin/env python3
"""Read-only inventory of stored raw prefix-reuse candidates; never evaluates.

A dependency-Search snapshot is not a common prefix-universe certificate.
All output is operator metadata, not feature input or a replacement corpus.
"""
import argparse
from collections import Counter
import hashlib
import json
import zlib
import concurrent.futures
import subprocess
from pathlib import Path
import sqlite3
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path[:0] = [str(CODE_ROOT / 'ast/run/mech'), str(CODE_ROOT / 'ast/run'),
                str(CODE_ROOT / 'judge3')]
from native_storage import read_block_metadata, view
from native_tables import Native
from source_read import SourceReader
from export_by_pair_id import PairSource
from dataset_format import write_json


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def record_text(value):
    if isinstance(value, bytes):
        if not value.startswith(b'ZJ1\0'):
            raise ValueError('unknown compressed inventory record')
        return zlib.decompress(value[4:]).decode('utf-8')
    return value


def db_json(db, table, key):
    for connection in (db, *getattr(db, 'parents', ())):
        row = connection.execute('SELECT result FROM ' + table + ' WHERE key=?', (key,)).fetchone()
        if row:return json.loads(record_text(row[0]))
    return None


def save(db, table, key, result):
    db.execute('INSERT OR REPLACE INTO ' + table + ' VALUES (?,?)',
               (key, b'ZJ1\0' + zlib.compress(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 3)))


class CacheDB:
    """One process-local writer plus read-only completed inventory caches."""
    def __init__(self, connection, parents=()):
        self.connection,self.parents=connection,parents
    def execute(self,*args):return self.connection.execute(*args)
    def commit(self):self.connection.commit()
    def close(self):
        self.connection.close()
        for parent in self.parents:parent.close()


def inventory_worker(command,log):
    with log.open('w') as stream:
        return subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT).returncode


class RawInventory:
    def __init__(self, db, max_block_bytes):
        self.db, self.max_block_bytes = db, max_block_bytes
        self.counters = Counter()

    def _key(self, base, ref, role):
        path = Path(base) / ref['path']
        stat = path.stat()
        return sha(dict(base=str(Path(base).resolve()), ref=ref, role=role,
            file_stat=[stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]))

    def snapshot(self, base, ref):
        if not isinstance(ref, dict) or ref.get('format') != 'arclog-native-v5':
            raise ValueError('unsupported/non-v5 stored reference; no snapshot acquisition fallback')
        key = self._key(base, ref, 'snapshot-metadata')
        old = db_json(self.db, 'snapshots', key)
        if old:
            self.counters['snapshot_cache_hits'] += 1
            return old
        value = read_block_metadata(ref, base, fields=[(k,) for k in
            ('format','byteorder','dtypes','values_bytes','values_sha256','counts')] +
            [('tables','*','ref'),('tables','*','rows','tables'),('tables','*','rows','entries')])['metadata']
        if value['byteorder'] != sys.byteorder:
            raise ValueError('stored native byte order differs from host')
        result = dict(key=key, base=str(base), ref=ref, dtypes=value['dtypes'],
            byteorder=value['byteorder'], values_bytes=value['values_bytes'],
            values_sha256=value['values_sha256'], counts=value['counts'],
            copies={}, copies_metadata_used=False, tables=[dict(index=t['rows']['tables'][0],
                ref=t['ref'], original_entry_ids=t['rows']['entries']) for t in value['tables']])
        save(self.db, 'snapshots', key, result)
        self.counters['snapshot_blocks_read'] += 1
        self.counters['compressed_bytes_read'] += ref['bytes']
        return result

    def table(self, snapshot, item):
        base = snapshot['base'];ref = item['ref']
        key = self._key(base, ref, 'table-metadata:' + sha(snapshot['dtypes']))
        old = db_json(self.db, 'table_blocks', key)
        if old:
            self.counters['table_cache_hits'] += 1
            return old
        if ref['bytes'] > self.max_block_bytes:
            # This is an inventory resource limit, NOT an evaluation deficit.
            result = dict(key=key, status='inventory_block_limit',
                compressed_bytes=ref['bytes'], reason='table block exceeds inventory byte allowance')
            save(self.db, 'table_blocks', key, result)
            return result
        names = ('table','kind','rows','example_kind','example_index','model',
            'fault','stop_bound','stop_form','value_stop_bound','value_stop_form',
            'extent_fault','extent_stop_bound','extent_stop_form')
        envelope = read_block_metadata(ref, base,
            fields=[('tables',),('values',)] + [('entries',name) for name in names],
            declared_only=[('values',)])
        fragment = envelope['metadata'];fragment['dtypes'] = snapshot['dtypes']
        ts = {name:view(fragment,'tables',name) for name in fragment['tables']}
        es = {name:view(fragment,'entries',name) for name in fragment['entries']}
        # Reuse the schema-only canonical helper. No Native construction,
        # assignment/value run, Unit-cell or extent-status validation occurs.
        schema = Native.schema(SimpleNamespace(tables=ts,schemas={}),0)
        selected = [e for e in range(len(es['table'])) if es['example_kind'][e] in (0,1)]
        kinds=Counter();examples=Counter();recorded_flags=Counter();extent_flags=Counter();deficits=[]
        valid=0
        for e in selected:
            kinds[str(es['kind'][e])] += 1
            examples[str((es['example_kind'][e],es['example_index'][e],es['model'][e]))] += 1
            diagnostic={name:es[name][e] for name in names if name!='table' and name in es}
            flags=[name for name in ('fault','stop_bound','value_stop_bound','extent_fault','extent_stop_bound')
                   if diagnostic.get(name)]
            for name in flags:recorded_flags[name]+=1
            for name in ('extent_fault','extent_stop_bound'):
                if diagnostic.get(name):extent_flags[name]+=1
            if es['kind'][e]==0 and not ts['fault'][0] and not any(diagnostic.get(k) for k in
                    ('fault','stop_bound','value_stop_bound')):valid+=1
            if flags or es['kind'][e]!=0:deficits.append(dict(local_entry=e,**diagnostic))
        status=('no_train_task_entries' if not selected else
                'potential_raw_metadata_unvalidated_values' if valid==len(selected) else
                'known_selected_source_value_deficit')
        result=dict(key=key,status=status,form=ts['form'][0],point=ts['point'][0],
            relation=ts['relation'][0],fact=ts['fact'][0],schema=schema,
            dependency_dets=ts['det_relations'][0],dependency_types=ts['det_types'][0],
            native_entry_count=len(es['table']),train_task_entry_count=len(selected),
            test_entry_metadata_count=sum(k==2 for k in es['example_kind']),
            complete_rows_metadata_entries=valid,stored_row_count=sum(es['rows'][e] for e in selected),
            entry_kinds=dict(kinds),value_errors={},extent_flags=dict(extent_flags),
            recorded_flags=dict(recorded_flags),entry_deficits=deficits,
            observed_example_model_counts=dict(examples),projections=ts['projections'][0],
            compressed_bytes=ref['bytes'],declared_value_bytes=envelope['declared_buffers']['values']['bytes'],
            table_fault=ts['fault'][0],exhaustive_prefix_certificate=False,
            validation_level='compressed-SHA+selected-metadata-only; values/assignments/layout/tail unvalidated',
            metadata_authentication=envelope['authentication'])
        save(self.db,'table_blocks',key,result)
        self.counters['table_metadata_blocks_read']+=1
        self.counters['compressed_bytes_read']+=ref['bytes']
        self.counters['value_payload_bytes_restored']+=0
        return result

    def observation(self, base, ref, table_index=None):
        snapshot = self.snapshot(base, ref)
        key = sha(dict(snapshot=snapshot['key'], table_index=table_index))
        old = db_json(self.db, 'observations', key)
        if old:
            self.counters['observation_cache_hits'] += 1
            return dict(key=key, snapshot_key=snapshot['key'], ref=ref, base=str(base), table_index=table_index)
        items = snapshot['tables'] if table_index is None else [t for t in snapshot['tables'] if t['index'] == table_index]
        if table_index is not None and len(items) != 1:
            raise ValueError('exact recorded table index is absent/ambiguous in its own snapshot')
        tables = []
        for item in items:
            try:
                summary = self.table(snapshot, item)
                tables.append(dict(index=item['index'], table_key=summary['key']))
            except Exception as error:
                tables.append(dict(index=item['index'], error=f'{type(error).__name__}: {error}'))
        save(self.db, 'observations', key, dict(snapshot_key=snapshot['key'], tables=tables,
            universe_status='unproven_no_native_common_prefix_certificate'))
        return dict(key=key, snapshot_key=snapshot['key'], ref=ref, base=str(base), table_index=table_index)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection', type=Path, default=DATA_ROOT / 'codex-adm/n-featapi/prefix-assignment-design/store-inventory.json')
    p.add_argument('--output', type=Path, default=DATA_ROOT / 'codex-adm/n-featapi/prefix-raw-coverage')
    p.add_argument('--labels', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    p.add_argument('--max-compressed-block-mib', type=int, default=128)
    p.add_argument('--workers',type=int,default=6)
    p.add_argument('--worker-shard',type=int)
    args = p.parse_args()
    if not 1<=args.workers<=16:raise ValueError('workers must be 1..16')
    start = time.monotonic()
    if args.worker_shard is None and args.output.exists():
        # Restore exact paused bytes before SQLite can create an empty cache.
        from paused_storage import restore_file, sidecar
        compressed = [p for p in args.output.rglob('*.gz') if sidecar(p).is_file()
            and ('.sqlite3' in p.name or p.name.endswith('.jsonl.gz'))]
        # WAL/SHM before main DB; no SQLite connection exists yet.
        for path in sorted(compressed,key=lambda p:p.name.endswith('.sqlite3.gz')):
            print(json.dumps(dict(stage='restore_paused',**restore_file(path))),flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    selection = json.loads(args.selection.read_text())
    selected = {pair: group['path'] for group in selection['groups'] for pair in group['pair_ids']}
    group_by_path = {group['path']:group for group in selection['groups']}
    if len(selected) != selection['pairs']:raise ValueError('selection pair identities differ')
    inputs = dict(selection_sha256=file_sha(args.selection), script_sha256=file_sha(__file__),
        helpers={str(p):file_sha(p) for p in (CODE_ROOT/'ast/run/native_storage.py', CODE_ROOT/'ast/run/native_tables.py',
            CODE_ROOT/'ast/run/mech/source_read.py', CODE_ROOT/'judge3/export_by_pair_id.py')},
        max_compressed_block_mib=args.max_compressed_block_mib)
    source_db = sqlite3.connect(args.labels.resolve().as_uri() + '?mode=ro', uri=True)
    source_db.execute('PRAGMA query_only=ON')
    source_db.execute('PRAGMA cache_size=-65536')
    seed_path=args.output/'inventory.sqlite3'
    shard_dir=args.output/'shards';shard_dir.mkdir(exist_ok=True)
    db_path=(shard_dir/(str(args.workers)+'-'+str(args.worker_shard)+'.sqlite3')
             if args.worker_shard is not None else seed_path)
    connection=sqlite3.connect(db_path)
    parents=[]
    if args.worker_shard is not None:
        for path in [seed_path,*sorted(shard_dir.glob('*.sqlite3'))]:
            if path==db_path:continue
            parent=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            parent.execute('PRAGMA query_only=ON');parents.append(parent)
    db=CacheDB(connection,parents)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA cache_size=-32768')
    for name in ('snapshots','table_blocks','observations','pairs'):
        db.execute('CREATE TABLE IF NOT EXISTS '+name+' (key TEXT PRIMARY KEY,result TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (pair_id TEXT PRIMARY KEY,point_path TEXT,source_file TEXT,line INTEGER,base TEXT)')
    if args.worker_shard is None:
        prior = json.loads((args.output/'inputs.json').read_text()) if (args.output/'inputs.json').exists() else None
        # Earlier completed stronger validations stay valid. Implementation
        # hashes are provenance, not a reason to throw away those results.
        if prior and any(prior.get(k)!=inputs[k] for k in ('selection_sha256','max_compressed_block_mib')):
            raise ValueError('inventory selection/limit differs; explicit affected invalidation required')
        if prior and prior!=inputs:
            write_json(args.output/('inputs-'+sha(prior)[:16]+'.json'),prior)
        write_json(args.output/'inputs.json', inputs)
    resolver = SimpleNamespace(labels=source_db)
    if args.worker_shard is None and db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] != len(selected):
        for i,(pair,point) in enumerate(selected.items(),1):
            if db.execute('SELECT 1 FROM jobs WHERE pair_id=?',(pair,)).fetchone():continue
            try:
                base = PairSource.base(resolver,pair)
                minimal = {k:base[k] for k in ('task','case','kind','source','source_sha256')}
                source_file = str(Path(base['source']['corpus'])/base['task']/base['source']['file'])
            except Exception as error:
                group = group_by_path[point]
                minimal = dict(task=group['task'],case=group['case'],kind=group['kind'],
                    source=dict(corpus='',file='',line=0),source_sha256=None,
                    source_index_error=f'{type(error).__name__}: {error}')
                source_file = ''
            minimal['pair_id'] = pair
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',(pair,point,source_file,minimal['source']['line'],json.dumps(minimal)))
            if i%1000==0:db.commit();print(json.dumps(dict(stage='source_index',done=i,total=len(selected))),flush=True)
        db.commit()
    if (args.worker_shard is None and (args.output/'summary.json').exists()
            and (args.output/'pairs.jsonl').exists() and (args.output/'points.jsonl').exists()
            and db.execute('SELECT COUNT(*) FROM jobs WHERE pair_id NOT IN (SELECT key FROM pairs)').fetchone()[0]==0):
        summary=json.loads((args.output/'summary.json').read_text())
        print(json.dumps(dict(stage='reused_complete_inventory',points=summary['points'],pairs=summary['pairs'],
            native_evaluations=0)),flush=True)
        db.close();source_db.close();return 0
    parallel_done=False
    if args.worker_shard is None and args.workers>1:
        # Keep every task's source streams/cache locality together. Partition
        # only unfinished jobs, balancing their counts without rescan work.
        tasks={}
        for source_file,count in db.execute('SELECT source_file,COUNT(*) FROM jobs WHERE pair_id NOT IN (SELECT key FROM pairs) GROUP BY source_file'):
            task=str(Path(source_file).parent);tasks.setdefault(task,[]).append((source_file,count))
        bins=[[] for _ in range(args.workers)];loads=[0]*args.workers
        for files in sorted(tasks.values(),key=lambda x:-sum(c for _,c in x)):
            i=min(range(args.workers),key=loads.__getitem__)
            bins[i].extend(f for f,c in files);loads[i]+=sum(c for f,c in files)
        write_json(shard_dir/'assignment.json',dict(files=bins,remaining_loads=loads))
        db.commit();db.close()
        # Publish all local-cache schemas before any peer opens them read-only.
        for i in range(args.workers):
            local=sqlite3.connect(shard_dir/(str(args.workers)+'-'+str(i)+'.sqlite3'))
            local.execute('PRAGMA journal_mode=WAL')
            for table in ('snapshots','table_blocks','observations','pairs'):
                local.execute('CREATE TABLE IF NOT EXISTS '+table+' (key TEXT PRIMARY KEY,result TEXT NOT NULL)')
            local.commit();local.close()
        common=[sys.executable,'-B',str(Path(__file__).resolve()),'--selection',str(args.selection),
                '--output',str(args.output),'--labels',str(args.labels),'--workers',str(args.workers),
                '--max-compressed-block-mib',str(args.max_compressed_block_mib)]
        returns=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(inventory_worker,common+['--worker-shard',str(i)],
                shard_dir/('worker-'+str(i)+'.log')):i for i in range(args.workers) if bins[i]}
            for future in concurrent.futures.as_completed(futures):
                code=future.result();returns.append(code)
                print(json.dumps(dict(stage='worker_finished',worker=futures[future],returncode=code)),flush=True)
        db=CacheDB(sqlite3.connect(seed_path));db.execute('PRAGMA journal_mode=WAL')
        # Merge metadata only, never overwrite a completed stronger record.
        for path in sorted(shard_dir.glob('*.sqlite3')):
            db.execute('ATTACH DATABASE ? AS shard',(str(path),))
            for table in ('snapshots','table_blocks','observations','pairs'):
                db.execute('INSERT OR IGNORE INTO '+table+' SELECT * FROM shard.'+table)
            # Every ephemeral shard key must exist in the durable main cache
            # before its duplicate working copy can be discarded.
            for table in ('snapshots','table_blocks','observations','pairs'):
                missing=db.execute('SELECT COUNT(*) FROM shard.'+table+' s LEFT JOIN main.'+table+' m ON s.key=m.key WHERE m.key IS NULL').fetchone()[0]
                if missing:raise ValueError('inventory shard merge is incomplete')
            db.commit();db.execute('DETACH DATABASE shard')
            path.unlink()
            for suffix in ('-wal','-shm'):path.with_name(path.name+suffix).unlink(missing_ok=True)
        if any(returns):
            db.close();source_db.close();return 1
        parallel_done=True
    allowed_files=None
    jobs_db=db
    if args.worker_shard is not None:
        allowed_files=set(json.loads((shard_dir/'assignment.json').read_text())['files'][args.worker_shard])
        jobs_db=next(parent for parent in db.parents if Path(parent.execute('PRAGMA database_list').fetchone()[2]).resolve()==seed_path.resolve())
    reader = SourceReader(CODE_ROOT);raw = RawInventory(db,args.max_compressed_block_mib*1024*1024)
    counts = Counter()
    try:
        jobs = [] if parallel_done else jobs_db.execute('SELECT pair_id,point_path,base,source_file FROM jobs ORDER BY source_file,line,pair_id')
        for number,(pair,point,encoded,source_file) in enumerate(jobs,1):
            if allowed_files is not None and source_file not in allowed_files:continue
            old = db_json(db,'pairs',pair)
            if old:
                counts['reused_pair_inventories'] += 1
                if number%1000==0:print(json.dumps(dict(stage='resume',done=number,total=len(selected))),flush=True)
                continue
            base = json.loads(encoded)
            result = dict(pair_id=pair,point_path=point,kind=base['kind'],task=base['task'],case=base['case'],
                source=base['source'],source_sha256=base['source_sha256'],universe_status='unproven',observations={})
            try:
                if base.get('source_index_error'):raise ValueError(base['source_index_error'])
                record = reader.record(base)
                native_base = Path(base['source']['corpus'])/base['task']
                result['gold_program_sha256'] = hashlib.sha256(record['programs']['gold'].encode()).hexdigest()
                result['producer'] = {k:record[k] for k in ('engine_commit','wheel_sha256','native_binary_sha256') if k in record}
                roles = record['evaluation']['table_indices']
                for side in ('gold','mutant'):
                    for suffix in ('all','kept'):
                        role=side+'_'+suffix
                        try:result['observations'][role] = raw.observation(native_base,record['native'][side],roles[role])
                        except Exception as error:result['observations'][role]=dict(error=f'{type(error).__name__}: {error}')
                full = record.get('full_replay',{}).get('gold')
                if full is not None:
                    try:result['observations']['whole_gold_relation_snapshot'] = raw.observation(native_base,full)
                    except Exception as error:result['observations']['whole_gold_relation_snapshot']=dict(error=f'{type(error).__name__}: {error}')
                result['status']='inventoried'
            except Exception as error:
                result.update(status='source_read_error',reason=f'{type(error).__name__}: {error}')
            save(db,'pairs',pair,result);counts[result['status']] += 1
            if number%100==0:
                db.commit();print(json.dumps(dict(stage='stored_raw',done=number,total=len(selected),
                    seconds=round(time.monotonic()-start,2),counts=dict(counts),raw=dict(raw.counters))),flush=True)
        db.commit()
        if args.worker_shard is not None:
            write_json(shard_dir/('worker-'+str(args.worker_shard)+'-summary.json'),
                dict(counts=dict(counts),raw=dict(raw.counters),seconds=time.monotonic()-start))
            return 0
        # Summaries contain references and counts, never decoded value rows.
        point_stats = {g['path']:dict(point_path=g['path'],kind=g['kind'],pairs=len(g['pair_ids']),
            universe_status='unproven_no_native_common_prefix_certificate',gold_potential=0,mutant_potential=0,
            gold_source_deficits=0,mutant_source_deficits=0,inventory_errors=0,
            available_mapping_status='whole_relation_snapshots_inventoried; public Tn mapping and prefix coverage not inferred') for g in selection['groups']}
        with (args.output/'pairs.jsonl').open('w') as pair_out:
            for (encoded,) in db.execute('SELECT result FROM pairs ORDER BY key'):
                encoded=record_text(encoded);row=json.loads(encoded);point=point_stats[row['point_path']]
                pair_out.write(encoded+'\n')
                if row['status']!='inventoried':point['inventory_errors']+=1;continue
                for side in ('gold','mutant'):
                    observed=row['observations'].get(side+'_all',{})
                    observation=db_json(db,'observations',observed['key']) if observed.get('key') else {}
                    tables=observation.get('tables',[])
                    statuses=[db_json(db,'table_blocks',t['table_key'])['status'] if t.get('table_key') else 'inventory_error' for t in tables]
                    if statuses in (['potential_raw_values_unproven_universe'],['potential_raw_metadata_unvalidated_values']):point[side+'_potential']+=1
                    elif statuses==['known_selected_source_value_deficit']:point[side+'_source_deficits']+=1
                    else:point['inventory_errors']+=1
        with (args.output/'points.jsonl').open('w') as points_out:
            for point in point_stats.values():points_out.write(json.dumps(point,separators=(',',':'))+'\n')
        summary = dict(schema='study-stored-prefix-coverage-inventory-v1',points=len(point_stats),pairs=len(selected),
            certified_common_prefix_universes=0,
            certificate_reason='Current source contracts expose dependency-Search or whole-FITS-held observations only; no recognized common full-prior-prefix receipt exists. This does not prove missing rows.',
            points_with_gold_all_potential= sum(p['gold_potential']>0 for p in point_stats.values()),
            points_without_any_readable_gold_all_in_observed_sources=sum(p['gold_potential']==0 for p in point_stats.values()),
            mutant_all_potential_pairs=sum(p['mutant_potential'] for p in point_stats.values()),
            source_value_deficit_pairs=sum(p['mutant_source_deficits'] for p in point_stats.values()),
            counts=dict(counts),raw=dict(raw.counters),seconds=time.monotonic()-start,workers=args.workers,
            worker_summaries=[json.loads(p.read_text()) for p in sorted(shard_dir.glob('worker-*-summary.json'))],
            limits='Source deficits apply to exact observed raw queries, not proof that no alternate cache or future prefix query can supply values. Inventory errors/resource caps are not semantic deficits.',
            native_evaluations=0,decoded_cell_rows=0,full_snapshot_reconstructions=0,original_store_writes=0,
            metadata_policy='v3 storage: same metadata-only semantics; lossless compressed cache records, no duplicate committed shards; original stronger records reused')
        public_index = DATA_ROOT/'feat-exp/det-full-body-v1/published-points'
        kept_publications = []
        for path in sorted(public_index.glob('*.json')):
            record = json.loads(path.read_text())
            kept_publications.append(dict(point_id=record['point_id'],path=str(path),sha256=file_sha(path),
                pairs=len(record.get('pairs',{})),contract=record.get('contract'),
                coverage='whole-gold-kept subset; not a native common-prefix U receipt'))
        summary['preserved_det_publications'] = dict(points=len(kept_publications),
            pair_references=sum(r['pairs'] for r in kept_publications),native_universe_certificates=0)
        write_json(args.output/'preserved-det-publications.json',kept_publications)
        cache=DATA_ROOT/'judgetool/det-full-body-train-cache'
        packets=[p for p in cache.rglob('*') if p.is_file()] if cache.exists() else []
        summary['kept_packet_cache_metadata'] = dict(path=str(cache),files=len(packets),
            bytes=sum(p.stat().st_size for p in packets),contents_read=False,
            coverage='recorded kept subset only; not certified prefix coverage')
        write_json(args.output/'summary.json',summary)
        print(json.dumps(summary),flush=True)
    finally:
        reader.close();source_db.close();db.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
