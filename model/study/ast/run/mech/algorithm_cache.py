"""Candidate: bounded memoization of authenticated immutable native snapshots.

The labeling implementation is algorithm.py. Only its native acquisition calls
are bound to an owned cache; native codecs, search and policy are unchanged.
"""
from collections import OrderedDict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

import algorithm as original
from run import published_task


@dataclass
class Snapshot:
    view: dict
    charge: int


class NativeCache:
    def __init__(self, maximum_bytes=128 * 1024 * 1024, maximum_entries=24):
        self.maximum_bytes = maximum_bytes; self.maximum_entries = maximum_entries
        self.base = None; self.entries = OrderedDict(); self.bytes = 0
        self.hits = 0; self.misses = 0

    def read(self, reference, base):
        folder_path = Path(base).resolve()
        folder = os.fspath(folder_path)
        cacheable = published_task(folder_path)
        if folder != self.base:
            self.entries.clear(); self.bytes = 0; self.base = folder
        key = json.dumps(reference, sort_keys=True, separators=(',', ':'))
        if cacheable and key in self.entries:
            self.hits += 1
            self.entries.move_to_end(key)
            return self.entries[key]
        self.misses += 1
        # The canonical codec verifies every compressed-block digest on first
        # acquisition. Corpus packs are immutable/content-addressed, as required
        # by the existing resume contract; hits reuse that verified exact view.
        view = original.native(original.load_native(reference, base))
        values = view['values']
        raw_bytes = values.nbytes if isinstance(values, memoryview) else sys.getsizeof(values)
        # Conservative allowance for logical row tuples/cell caches. A strict
        # entry cap also prevents thousands of small snapshots accumulating.
        buffers = sum(column.nbytes if isinstance(column, memoryview) else sys.getsizeof(column)
                      for part in view.values() if isinstance(part, dict) for column in part.values())
        charge = raw_bytes * 24 + buffers * 8 + 4096
        entry = Snapshot(view, charge)
        if cacheable and charge <= self.maximum_bytes:
            while self.entries and (self.bytes + charge > self.maximum_bytes
                                    or len(self.entries) >= self.maximum_entries):
                _, evicted = self.entries.popitem(last=False); self.bytes -= evicted.charge
            self.entries[key] = entry; self.bytes += charge
        return entry


CACHE = NativeCache()


def native_view(snapshot):
    # Keep pair-local policy/cache annotations out of the cached snapshot. Native
    # value buffers are read-only; the canonical reader owns its schema memo.
    return dict(snapshot.view)


cached_inventory = original.bind_function(original.inventory, load_native=CACHE.read, native=native_view)
one_pair = original.bind_function(original.one_pair, load_native=CACHE.read, native=native_view,
                                  inventory=cached_inventory)
