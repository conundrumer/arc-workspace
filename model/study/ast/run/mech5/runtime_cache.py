"""Bounded task-local caches for immutable finalized native source evidence."""
from collections import OrderedDict
from pathlib import Path
import sys
from tables import TargetStore


def footprint(view):
    """Conservative shallow buffer/column estimate; aliases may overcount."""
    size=0
    for value in view.values():
        values=value.values() if isinstance(value,dict) else (value,)
        for column in values:
            if isinstance(column,memoryview):size+=column.nbytes
            elif isinstance(column,(bytes,bytearray)):size+=len(column)
            elif isinstance(column,(list,tuple)):
                size+=sys.getsizeof(column)+sum(sys.getsizeof(v) for v in column)
    # Native reader also owns entry/assignment index lists and cached schemas.
    return max(size*2,1)


class TaskNativeStore(TargetStore):
    def __init__(self,L,root,*,counters,max_bytes=128*1024*1024,max_views=16):
        super().__init__(L,root)
        self.cache=OrderedDict();self.sizes={};self.bytes=0
        self.counters=counters;self.max_bytes=max_bytes;self.max_views=max_views

    def clear(self):
        self.cache.clear();self.sizes.clear();self.bytes=0

    def snapshot(self,ref,base):
        base=Path(base).resolve()
        # Staging directories can be replaced during retries. Never retain a
        # staging view across calls; canonical load/authentication still runs.
        staging=any(p.startswith('.') and p.endswith('.tmp') for p in base.parts)
        key=(str(base),str(ref))
        if staging:
            self.clear()
        if key in self.cache:
            self.counters['native_views_reused']+=1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.counters['native_views_loaded']+=1
        view=super().snapshot(ref,base)
        amount=footprint(view);self.sizes[key]=amount;self.bytes+=amount
        while self.cache and (self.bytes>self.max_bytes or len(self.cache)>self.max_views or staging):
            old,_=self.cache.popitem(last=False);self.bytes-=self.sizes.pop(old)
        return view
