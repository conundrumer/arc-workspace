"""Content-addressed witness receipt transport; read helpers never write."""
from run import canonical,digest

MARKER='$witness_object'


def unpack(db,value,cache=None):
    cache={} if cache is None else cache
    if isinstance(value,dict):
        if set(value)=={MARKER}:
            key=value[MARKER]
            if key not in cache:
                import json
                row=db.execute('SELECT payload FROM witness_objects WHERE sha256=?',(key,)).fetchone()
                if not row:raise ValueError('witness receipt object absent: '+key)
                raw=json.loads(row[0])
                if digest(raw)!=key:raise ValueError('witness receipt object digest differs')
                cache[key]=unpack(db,raw,cache)
                # Caller caches are deliberately bounded between pair reads.
            return cache[key]
        return {k:unpack(db,v,cache) for k,v in value.items()}
    if isinstance(value,list):return [unpack(db,v,cache) for v in value]
    return value


class FactObjects:
    def __init__(self,db):
        self.db=db;self.seen=set()
        db.execute('CREATE TABLE IF NOT EXISTS witness_objects(sha256 TEXT PRIMARY KEY,payload TEXT NOT NULL)')

    def pack(self,value,*,root=False):
        if isinstance(value,dict):out={str(k):self.pack(v) for k,v in value.items()}
        elif isinstance(value,(list,tuple)):
            # Rows, ASTs and model reports contain many tiny nested lists. They
            # are one receipt value: serializing every cell/container merely to
            # discover that it is too small to intern made packing expensive.
            # Normalize once, then hash/store the complete list once.
            def normalize(v):
                if isinstance(v,dict):return {str(k):normalize(x) for k,x in v.items()}
                if isinstance(v,(list,tuple)):return [normalize(x) for x in v]
                return v
            out=normalize(value)
        else:return value
        raw=canonical(out)
        if root or len(raw)<128:return out
        key=digest(out)
        if key not in self.seen:
            self.db.execute('INSERT OR IGNORE INTO witness_objects VALUES (?,?)',(key,raw));self.seen.add(key)
        return {MARKER:key}
