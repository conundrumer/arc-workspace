"""The dev row store: for feature development only, on no search path. It is off unless the environment variable ROW_STORE_DIR names a folder.

It keeps each table once, by TableHash: its Type and its TableRows (the rows of each example under each constraint model, in the export's cell encoding, int32).
It also maps each table at an assignment, (QueryHash, Name, Assignment), to its TableHash. A table with no TableHash has no stored rows.

submit(ct, rows) hands a step_tables result and its AssignmentSummaries to a background thread and returns; the search does not wait on the write. A full queue drops the
result and counts it (stats()['dropped']). A restart reads the folder and writes only the tables it lacks.

Files in the folder:
  tables.bin      the int32 cells of each stored table, one after the other
  tables.jsonl    a line per stored table: hash (hex), types, width, cell offset, and per entry [example kind, example index, constraint model, rows, cell offset in the table]
  at.jsonl        a line per table at an assignment: table ([QueryHash hex, Name] or the base table's name), at ([[QueryHash hex, value hash hex]]), hash (hex)
"""
import atexit
import json
import os
import queue
import threading

import numpy as np
from sample import M

DIR = os.environ.get('ROW_STORE_DIR', '')  # empty: off
QUEUE = 4096  # the results that wait for the thread

_state = {}


def widths(types):
    return [4 if str(t) in M.WIDE else 1 for t in types]


class Store:
    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.folder = folder
        self.seen, self.ats = set(), set()
        for name, key in (('tables.jsonl', None), ('at.jsonl', None)):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                for line in open(path):
                    try:
                        x = json.loads(line)
                    except ValueError:  # a line cut off by a stop
                        continue
                    if name == 'tables.jsonl':
                        self.seen.add(x['hash'])
                    else:
                        self.ats.add(json.dumps([x['table'], x['at']]))
        path = os.path.join(folder, 'tables.bin')
        self.offset = os.path.getsize(path) // 4 if os.path.exists(path) else 0
        self.bin, self.tables, self.at = open(path, 'ab'), open(os.path.join(folder, 'tables.jsonl'), 'a'), open(os.path.join(folder, 'at.jsonl'), 'a')
        self.queue = queue.Queue(QUEUE)
        self.counts = dict(submitted=0, dropped=0, tables=0, at=0, errors=0)
        self.thread = threading.Thread(target=self.run, daemon=True, name='row-store')
        self.thread.start()

    def run(self):
        while True:
            ct, rows = self.queue.get()
            try:
                self.write(ct, rows)
            except Exception:  # noqa: BLE001  the store must not end a run
                self.counts['errors'] += 1
            finally:
                self.queue.task_done()

    def write(self, ct, rows):
        T, values = ct.tables, np.frombuffer(ct.values, np.int32)
        et, ex, ei, em = (M.col(ct, 'entries', k) for k in ('table', 'example_kind', 'example_index', 'model'))
        er, eo = M.col(ct, 'entries', 'rows'), M.col(ct, 'entries', 'offset')
        by = {}
        for e in range(len(et)):
            by.setdefault(int(et[e]), []).append(e)
        for j, row in enumerate(rows):
            if row.hash is None:
                continue
            h = '%032x' % row.hash
            if h not in self.seen:
                w = sum(widths(row.types))
                cells, entries = [], []
                size = 0
                for e in by.get(j, []):
                    part = values[eo[e]:eo[e] + er[e] * w]
                    entries.append([int(ex[e]), int(ei[e]), int(em[e]), int(er[e]), size])
                    cells.append(part)
                    size += len(part)
                data = np.concatenate(cells) if cells else np.zeros(0, np.int32)
                self.bin.write(data.tobytes())
                self.bin.flush()
                self.tables.write(json.dumps(dict(hash=h, types=list(row.types), width=w, offset=self.offset, cells=size, entries=entries)) + '\n')
                self.tables.flush()
                self.offset += size
                self.seen.add(h)
                self.counts['tables'] += 1
            if row.table is not None:
                table = list(('%032x' % row.table[0], row.table[1])) if isinstance(row.table, tuple) else row.table
                at = [['%032x' % d if d >= 0 else d, '%032x' % v] for d, v in row.at]
                key = json.dumps([table, at])
                if key not in self.ats:
                    self.ats.add(key)
                    self.at.write(json.dumps(dict(table=table, at=at, hash=h)) + '\n')
                    self.at.flush()
                    self.counts['at'] += 1


def store():
    """The Store of this process, made at the first use; None where the setting is off."""
    if not DIR:
        return None
    if 'store' not in _state:
        _state['store'] = Store(DIR)
        atexit.register(flush)
    return _state['store']


def submit(ct, rows):
    s = store()
    if s is None:
        return
    s.counts['submitted'] += 1
    try:
        s.queue.put_nowait((ct, rows))
    except queue.Full:
        s.counts['dropped'] += 1


def flush():
    """Waits until the thread has written what was submitted. For a caller that ends or reads the folder."""
    s = store()
    if s is not None:
        s.queue.join()


def stats():
    s = store()
    return dict(s.counts) if s is not None else None
