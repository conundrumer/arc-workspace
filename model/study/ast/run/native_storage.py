"""Lossless, table-deduplicated native storage; no base64 on disk.

Each task has one append-only pack of independently zlib-compressed blocks.
References hash the exact compressed range. A native snapshot manifest maps
canonical table-local rows/runs back to original native indexes and offsets.
"""
from array import array
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

PARTS=('tables','entries','assigned','projections','projection_rows','flows','copies')
FORMATS={'uint8':'B','int32':'i','uint32':'I','uint64':'Q','int64':'q'}
MAGIC=b'ARCTBL5\0'


def raw_native(table):
    if isinstance(table, dict):
        return table
    return dict(dtypes=table.dtypes,values=table.values,**{p:getattr(table,p) for p in PARTS})


def binary_encode(value):
    data=bytearray()
    def visit(v):
        if isinstance(v,(bytes,bytearray,memoryview)):
            start=len(data);data.extend(v)
            return {'$buffer':[start,len(v)]}
        if isinstance(v,dict):return {k:visit(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):return [visit(x) for x in v]
        return v
    header=json.dumps(visit(value),sort_keys=True,separators=(',',':'),check_circular=False).encode()
    return MAGIC+struct.pack('<Q',len(header))+header+data


def binary_decode(data):
    if data[:8]!=MAGIC:raise ValueError('bad native pack block magic')
    size=struct.unpack_from('<Q',data,8)[0];header=json.loads(data[16:16+size]);buffers=data[16+size:]
    def visit(v):
        if isinstance(v,dict):
            if set(v)=={'$buffer'}:
                off,count=v['$buffer']
                if off<0 or count<0 or off+count>len(buffers):raise ValueError('native block buffer outside payload')
                return buffers[off:off+count]
            return {k:visit(x) for k,x in v.items()}
        if isinstance(v,list):return [visit(x) for x in v]
        return v
    return visit(header)


def view(raw,part,name):
    value=raw[part][name]
    return memoryview(value).cast(FORMATS[raw['dtypes'][part+'.'+name]]) if isinstance(value,bytes) else value


def pack_column(raw,part,name,values):
    return array(FORMATS[raw['dtypes'][part+'.'+name]],values).tobytes() if isinstance(raw[part][name],bytes) else list(values)


def row_runs(ids):
    """Keep storage row order while coalescing contiguous byte-copy ranges."""
    runs=[]
    for i in ids:
        if runs and runs[-1][1]==i:
            runs[-1][1]=i+1
        else:
            runs.append([i,i+1])
    return runs


def select_column(raw,columns,part,name,ids,runs):
    value=raw[part][name]
    if isinstance(value,bytes):
        size=columns[part][name].itemsize
        return b''.join(value[lo*size:hi*size] for lo,hi in runs)
    return [columns[part][name][i] for i in ids]


class NativeStore:
    def __init__(self,root,guard=None):
        self.root=Path(root);self.guard=guard
        (self.root/'native').mkdir(parents=True,exist_ok=True)
        self.pack=(self.root/'native/tables.pack').open('wb')
        self.index={};self.stats={'blocks':0,'table_blocks':0,'snapshot_blocks':0,'dedup_hits':0,'pack_bytes':0,'raw_block_bytes':0}
    def close(self):self.pack.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def block(self,value,kind):
        raw=binary_encode(value);digest=hashlib.sha256(raw).digest()
        if digest in self.index:
            self.stats['dedup_hits']+=1;return self.index[digest]
        compressed=zlib.compress(raw,6)
        ref=dict(format=kind,path='native/tables.pack',offset=self.pack.tell(),bytes=len(compressed),
                 sha256=hashlib.sha256(compressed).hexdigest())
        with self.guard.permit(len(compressed)) if self.guard else nullcontext():
            self.pack.write(compressed);self.pack.flush()
        self.index[digest]=ref
        self.stats['blocks']+=1;self.stats['pack_bytes']+=len(compressed);self.stats['raw_block_bytes']+=len(raw)
        self.stats['table_blocks' if kind=='arclog-table-v5' else 'snapshot_blocks']+=1
        return ref
    def put(self,table,cache=None):
        return self.put_raw(raw_native(table),cache)

    def put_raw(self,raw,cache=None):
        if cache is not None and cache.get('raw')==raw:
            self.stats['dedup_hits']+=1;return cache['ref']
        # Storage views only: logical decoding/status policy belongs to the
        # pinned canonical Native reader. Cast each buffer once per snapshot.
        columns={part:{name:view(raw,part,name) for name in raw[part]} for part in PARTS}
        nt=len(columns['tables']['width'])
        manifest=dict(format='arclog-native-v5',byteorder=sys.byteorder,dtypes=raw['dtypes'],
                      values_bytes=len(raw['values']),values_sha256=hashlib.sha256(raw['values']).hexdigest(),
                      counts={p:len(next(iter(raw[p].values())))//(array(FORMATS[raw['dtypes'][p+'.'+next(iter(raw[p]))]]).itemsize) if isinstance(next(iter(raw[p].values())),bytes) else len(next(iter(raw[p].values()))) for p in PARTS if p!='copies' and raw[p]},tables=[],copies=raw['copies'])
        manifest['columns']={p:{k:isinstance(v,bytes) for k,v in raw[p].items()} for p in PARTS if p!='copies'}
        # Per-part row membership, preserving original native row IDs.
        entries=list(columns['entries']['table']);entry_by_table=[[] for _ in range(nt)]
        for i,t in enumerate(entries):entry_by_table[t].append(i)
        projections=list(columns['projections']['table']);proj_by_table=[[] for _ in range(nt)]
        for i,t in enumerate(projections):proj_by_table[t].append(i)
        grouped={p:[[] for _ in range(nt)] for p in ('assigned','projection_rows','flows')}
        for i,e in enumerate(columns['assigned']['entry']):grouped['assigned'][entries[e]].append(i)
        for i,p in enumerate(columns['projection_rows']['projection']):grouped['projection_rows'][projections[p]].append(i)
        for i,t in enumerate(columns['flows']['table']):grouped['flows'][t].append(i)
        covered=[]
        for t in range(nt):
            rows=dict(tables=[t],entries=entry_by_table[t],projections=proj_by_table[t],
                      **{p:grouped[p][t] for p in grouped})
            runs_by_part={p:row_runs(ids) for p,ids in rows.items()}
            fragment={p:{k:select_column(raw,columns,p,k,ids,runs_by_part[p]) for k in raw[p]} for p,ids in rows.items()}
            emap={old:new for new,old in enumerate(rows['entries'])};pmap={old:new for new,old in enumerate(rows['projections'])}
            for part,col,mapping in (('entries','table',None),('projections','table',None),('flows','table',None),
                                     ('assigned','entry',emap),('projection_rows','entry',emap),('projection_rows','projection',pmap)):
                values=[mapping[columns[part][col][i]] if mapping is not None else 0 for i in rows[part]]
                fragment[part][col]=pack_column(raw,part,col,values)
            local=bytearray();runs=[];run_cache={};source_offsets={}
            def run(old,cells):
                if not cells:return 0
                if old<0 or (old+cells)*4>len(raw['values']):raise ValueError('native value run outside buffer')
                key=(old,cells)
                if key in run_cache:return run_cache[key]
                off=len(local)//4;local.extend(raw['values'][old*4:(old+cells)*4])
                runs.append([old,off,cells]);covered.append((old,old+cells));run_cache[key]=off
                return off
            widths=columns['tables']['width'];extent_columns=raw['tables']['extent_columns'][t]
            for part,col in (('entries','offset'),('entries','extent_offset'),('assigned','offset'),('projection_rows','offset'),('projection_rows','extent_offset')):
                original=[columns[part][col][i] for i in rows[part]];source_offsets[part+'.'+col]=original
                relocated=[]
                for i,old in zip(rows[part],original):
                    count=columns[part]['rows'][i]
                    if part=='entries':
                        cells=count*(2*len(extent_columns) if col=='extent_offset' else widths[t])
                        if columns['entries']['kind'][i]!=0:cells=0
                    elif part=='assigned':cells=count*raw['tables']['det_widths'][t][columns[part]['det'][i]]
                    else:
                        pi=columns[part]['projection'][i]
                        cols=raw['projections']['columns'][pi]
                        cells=count*(2*sum(c in extent_columns for c in cols) if col=='extent_offset' else columns['projections']['width'][pi])
                        if not columns['projection_rows']['defined'][i]:cells=0
                    relocated.append(old if old<0 else run(old,cells))
                fragment[part][col]=pack_column(raw,part,col,relocated)
            fragment['values']=bytes(local)
            ref=self.block(fragment,'arclog-table-v5')
            manifest['tables'].append(dict(ref=ref,rows=rows,source_offsets=source_offsets,runs=runs))
        # Preserve even unused native buffer ranges, so loading restores exact
        # original bytes rather than just equivalent rows.
        remaining=[];at=0
        for lo,hi in sorted(covered):
            if lo>at:remaining.append([at,raw['values'][at*4:lo*4]])
            at=max(at,hi)
        if at*4<len(raw['values']):remaining.append([at,raw['values'][at*4:]])
        if remaining:manifest['unclaimed']=self.block(remaining,'arclog-values-v5')
        ref=self.block(manifest,'arclog-native-v5')
        if cache is not None:cache.update(raw=raw,ref=ref)
        return ref


def read_block(ref,base):
    path=Path(base)/ref['path']
    with path.open('rb') as src:
        src.seek(ref['offset']);data=src.read(ref['bytes'])
    if len(data)!=ref['bytes'] or hashlib.sha256(data).hexdigest()!=ref['sha256']:
        raise ValueError('native pack digest mismatch: '+str(path))
    return binary_decode(zlib.decompress(data))


def load_native(ref,base):
    manifest=read_block(ref,base)
    if manifest['byteorder']!=sys.byteorder:raise ValueError('native byte order differs from host')
    dtypes=manifest['dtypes'];values=bytearray(manifest['values_bytes'])
    result=dict(dtypes=dtypes,values=None,copies=manifest['copies'],
                **{p:{k:bytearray(manifest['counts'].get(p,0)*array(FORMATS[dtypes[p+'.'+k]]).itemsize)
                       if binary else [None]*manifest['counts'].get(p,0) for k,binary in columns.items()}
                   for p,columns in manifest['columns'].items()})
    for table in manifest['tables']:
        fragment=read_block(table['ref'],base)
        for part,ids in table['rows'].items():
            for col,data in fragment[part].items():
                name=part+'.'+col
                if isinstance(data,bytes):
                    fmt=FORMATS[dtypes[name]];size=array(fmt).itemsize
                    if col=='table' and part in ('entries','projections','flows'):
                        data=array(fmt,[table['rows']['tables'][0]]*len(ids)).tobytes()
                    elif (part,col) in (('assigned','entry'),('projection_rows','entry'),('projection_rows','projection')):
                        family='projections' if col=='projection' else 'entries'
                        data=array(fmt,[table['rows'][family][v] for v in memoryview(data).cast(fmt)]).tobytes()
                    elif name in table['source_offsets']:data=array(fmt,table['source_offsets'][name]).tobytes()
                    target=result[part].setdefault(col,bytearray(manifest['counts'][part]*size))
                    for local,original in enumerate(ids):target[original*size:(original+1)*size]=data[local*size:(local+1)*size]
                else:
                    target=result[part].setdefault(col,[None]*manifest['counts'][part])
                    for local,original in enumerate(ids):target[original]=data[local]
        for original,local,cells in table['runs']:
            values[original*4:(original+cells)*4]=fragment['values'][local*4:(local+cells)*4]
    if 'unclaimed' in manifest:
        for offset,data in read_block(manifest['unclaimed'],base):values[offset*4:offset*4+len(data)]=data
    result['values']=bytes(values)
    if hashlib.sha256(values).hexdigest()!=manifest['values_sha256']:raise ValueError('native values reconstruction digest mismatch')
    for part in PARTS:
        result[part]={k:bytes(v) if isinstance(v,bytearray) else v for k,v in result[part].items()}
    return result


def materialize_pair(record,base):
    """Adapter for judge2.pair_loader.load_ast_pair; preserves byte payloads."""
    result=dict(record)
    result['native']={side:load_native(record['native'][side],base) for side in ('gold','mutant')}
    return result
