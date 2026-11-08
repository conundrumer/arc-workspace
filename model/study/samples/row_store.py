"""The dev row store: for one task, each table once by its TableHash with its Set of Rows, and each extension entry (function, Name, Assignment)
mapped to the TableHash of that entry. `rows_replay.py` writes it on the engine and sampler code of a writer kit release; the reach kit's map mode
(`build_map.py --rows`) writes it on the reach kit. The feature build reads either.

One file per task, `OUTD/SET/rows/<task>.jsonl.gz`, written to a temp file and renamed. It holds no feature, so a change of a feature re-runs
`build_tables.py` over the store and never the replay. Lines:

  header    task, src (the sha of the task's union record), versions (hash_version, query_hash_version, table_hash_version), n_train, n_test
  function  one per query: id (its QueryHash, `StudyProgram.query_hash`, equal to the export's `query`), union_key, kind, text, reads, depth, dets (the DETs in its use closure), refmap
            (label in text -> function id), outputs (one per Name: types, labels, assignments seen, kept, stopped)
  alias     one per further (union_key, text) of a function's QueryHash, from a later form: id, union_key, text. `read_store` gives each function
            `aliases`, every (union_key, text) it stands for, its own first
  table     one per distinct TableHash: hash, types, rows (one Rows each: ex, n, cells, boxes). Two entries with one hash share it
  entry     one per (table, assignment): function, name, o, assignment [[DET id, value hash]], hash, kind (content or counts_only), types,
            examples [[kind, index, distinct, rows, hash]] (the example keys), legacy (the reach kit's table_key, for the check of the hash; null
            where the writer has no reach kit)
  given     as entry, for input, ex_input and ex_output
  footer    counts

A Rows is the set of Row of one example under one constraint model. A Row has the Example column: its cells hold the example code
(kind * 10000 + index; -1 where the rows hold for every example). The cells are int32 as the engine writes them, base64, all rows. A counts-only
entry (today's Count entry) has no table record: the engine gives its row counts only.
"""
import base64
import gzip
import hashlib
import json
import os
import re
import tempfile
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

import definition_hash as DH
import table_export as TE
import table_hash as TH

VERSION = 'rows3'
MAX_ASSIGNMENTS = 256
EX_BASE = 10000
NO_EXAMPLE = -1
PROBE = ['(RULE &r0 (input (:P *P) (:Col *Col)))', '(DET &r1 (ex_input (:E *E) (:P *P) (:Col *Col)))', '(DET &r2 (ex_output (:E *E) (:P *P) (:Col *Col)))']
GIVEN = ['input', 'ex_input', 'ex_output']
LABEL = re.compile(r'&r(\d+)')
SLOT_NO = re.compile(r'(?:slot |&r)(\d+)')  # a DET of an assignment named by its slot, as the engine names it where it gives no QueryHash

type AssignKey = tuple[tuple[str, str], ...]


def example_code(kind: int, index: int) -> int:
    return NO_EXAMPLE if kind == TE.EXAMPLE_TASK else kind * EX_BASE + index


def _b64(a: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


@dataclass
class Rows:
    ex: int  # the example code; the Example column of every row holds it
    n: int
    cells: np.ndarray  # int32 (kept rows, cells), the Example column among them
    boxes: np.ndarray | None  # float32 (kept rows, Box columns, 2)


@dataclass
class StoredTable:
    function: str
    o: int
    name: str
    assignment: AssignKey
    hash: str
    counts_only: bool
    types: list[str]  # with Example
    rows: list[Rows]
    examples: list[tuple[int, int, int, int, int]]  # (kind, index, distinct, rows, hash)
    legacy: str | None
    engine_features: list[float] = field(default_factory=list)  # the engine's features at export (82 under site-exp11)


@dataclass
class Store:
    header: dict
    functions: dict[str, dict] = field(default_factory=dict)
    tables: list[StoredTable] = field(default_factory=list)
    given: list[StoredTable] = field(default_factory=list)


def _rows_of(types: list[str], raw: list[dict]) -> list[Rows]:
    width = sum(TH.WIDE.get(t, 1) for t in types)
    nbox = sum(t == 'Box' for t in types)
    out = []
    for x in raw:
        cells = np.frombuffer(base64.b64decode(x['cells']), dtype=np.int32).reshape(-1, width)
        boxes = np.frombuffer(base64.b64decode(x['boxes']), dtype=np.float32).reshape(-1, nbox, 2) if x['boxes'] else None
        out.append(Rows(x['ex'], x['n'], cells, boxes))
    return out


def read_store(path: str) -> Store:
    shared: dict[str, tuple[list[str], list[Rows]]] = {}  # TableHash -> (types, Set of Rows) as the first entry with that hash wrote them
    ents: list[dict] = []
    with gzip.open(path, 'rt') as f:
        store = Store(json.loads(f.readline()))
        for line in f:
            r = json.loads(line)
            if r['t'] == 'function':
                store.functions[r['id']] = r
                r['aliases'] = [[r['union_key'], r['text']]]
            elif r['t'] == 'alias' and r['id'] in store.functions:  # a function whose tables failed has an error line in place of its function line
                store.functions[r['id']]['aliases'].append([r['union_key'], r['text']])
            elif r['t'] == 'table':
                shared[r['hash']] = (r['types'], _rows_of(r['types'], r['rows']))
            elif r['t'] in ('entry', 'given'):
                ents.append(r)
    for r in ents:
        counts_only = r['kind'] == 'counts_only'
        types, rows = ([], []) if counts_only else shared[r['hash']]  # the columns of equal tables can come in different orders: the rows go with their types
        t = StoredTable(r['function'], r['o'], r['name'], tuple((a, b) for a, b in r['assignment']), r['hash'], counts_only,
                        r['types'] if counts_only else types, rows, [tuple(x) for x in r['examples']], r.get('legacy'),
                        r.get('engine_features', []))
        (store.tables if r['t'] == 'entry' else store.given).append(t)
    return store


def header_of(path: str) -> dict | None:
    try:
        with gzip.open(path, 'rt') as f:
            return json.loads(f.readline())
    except (OSError, EOFError, ValueError):
        return None


def code_sha() -> str:
    """The sha of the files that define the store: a change of any of them makes every finished file stale."""
    h = hashlib.sha256()
    for f in ('row_store.py', 'table_export.py', 'table_hash.py'):
        h.update(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f), 'rb').read())
    return h.hexdigest()[:16]


class GzWriter:
    """A gzip text writer on a path (`gzip.open` in write mode loses its file in the free-threaded build)."""

    def __init__(self, path: str):
        self.f = open(path, 'wb')
        self.z = zlib.compressobj(6, zlib.DEFLATED, 31)

    def write(self, s: str) -> None:
        self.f.write(self.z.compress(s.encode()))

    def close(self) -> None:
        self.f.write(self.z.flush())
        self.f.close()


# ---------------------------------------------------------------------- the engine's export by assignment, beside the kit's replay

SHADOW: dict[int, tuple[Any, Any]] = {}  # id of a replay result in the kit's layout -> (that result, the same step by assignment, with rows)
ACTIVE: list[bool] = [False]
FIRST: set[int] = set()  # ids of the results of a program's first step


def prune() -> None:
    """Drops the exports of a finished program, except those of first steps."""
    for k in [k for k in SHADOW if k not in FIRST]:
        del SHADOW[k]


def install(arclog: Any) -> None:
    """Wraps `arclog.step_tables`. The kit reads the layout of `stream_tables` (`by_assignment=False`), so it gets that. While ACTIVE, each step is
    also exported by assignment with its rows (`by_assignment=True, rows=True`) for the row store, and kept in SHADOW. The two calls see one decoder."""
    if getattr(arclog.step_tables, 'shadowed', False):
        return
    orig = arclog.step_tables

    def step_tables(dec: Any, task: Any, case: Any, bodies: bool = False, before: Any = None, **kw: Any) -> Any:
        legacy = orig(dec, task, case, bodies, before, **{**kw, 'by_assignment': False})
        if ACTIVE[0] or before is None:  # a program's first step is kept whenever it is made: the kit reuses it in later programs
            prev = SHADOW.get(id(before)) if before is not None else None
            try:
                if before is not None and (prev is None or isinstance(prev[1], Exception)):
                    raise ValueError('the previous step has no export by assignment' + (': %s' % prev[1] if prev else ''))
                SHADOW[id(legacy)] = (legacy, orig(dec, task, case, bodies, prev[1] if prev else None, **{**kw, 'by_assignment': True, 'rows': True}))
                if before is None:
                    FIRST.add(id(legacy))
            except Exception as e:  # noqa: BLE001  the kit's replay goes on; the sink records the table as not exported
                SHADOW[id(legacy)] = (legacy, e)
        return legacy
    step_tables.shadowed = True  # type: ignore[attr-defined]
    arclog.step_tables = step_tables


def describe(collect: list) -> None:
    import contextlib
    with open(os.environ['ARC_SHADOW_DEBUG'], 'a') as out, contextlib.redirect_stdout(out):
        _describe(collect)


def _describe(collect: list) -> None:
    import numpy as np
    for ct in collect[11:12]:
        got = SHADOW.get(id(ct))
        sh = got[1] if got else None
        if sh is None:
            print('no shadow', got)
            continue
        T, E, A, K = sh.tables, sh.entries, sh.assignments, sh.example_keys

        def col(part, name, dt):
            return np.frombuffer(memoryview(part[name]).cast('B'), dtype=dt)
        n = len(T['form'])
        print('rows of tables', n, 'table', col(T, 'table', np.int32), 'relation', col(T, 'relation', np.int32), 'token', col(T, 'token', np.int32))
        df = bytes(memoryview(T['query']).cast('B'))
        hs = bytes(memoryview(T['hash']).cast('B'))
        print('query', [df[i * 16:i * 16 + 16].hex()[:8] for i in range(n)], 'has', col(T, 'has_query', np.uint8), 'name', list(T['name']), 'hashed', col(T, 'hashed', np.uint8), 'capped', col(T, 'capped', np.uint8))
        print('hash', [hs[i * 16:i * 16 + 16].hex()[:8] for i in range(n)])
        print('features', col(T, 'features', np.float32).reshape(n, -1)[:2])
        print('det_relations', list(T['det_relations'])[:n], 'labels', list(T['column_labels']), 'types', list(T['column_types']))
        ne = len(E['example_kind'])
        print('entries', ne, 'table', col(E, 'table', np.int32), 'kind', col(E, 'kind', np.uint8), 'ex_kind', col(E, 'example_kind', np.uint8), 'ex_idx', col(E, 'example_index', np.int32), 'model', col(E, 'model', np.int32), 'rows', col(E, 'rows', np.int64), 'offset', col(E, 'offset', np.int64))
        print('assign table', col(A, 'table', np.int32), 'det', [repr(x)[:40] for x in list(A['det'])[:4]], 'value', bytes(memoryview(A['value']).cast('B')).hex()[:80])
        print('ekeys table', col(K, 'table', np.int32), 'kind', col(K, 'kind', np.uint8), 'idx', col(K, 'index', np.int32), 'distinct', col(K, 'distinct', np.int32), 'rows', col(K, 'rows', np.int32))
        print('values', type(sh.values), len(sh.values) if hasattr(sh.values, '__len__') else '')
        print('ekeys hash', col(K, 'hash', np.uint64), 'ehash', bytes(memoryview(E['hash']).cast('B')).hex()[:64])


def example_key_of(code: int) -> tuple[int, int]:
    return (TE.EXAMPLE_TASK, 0) if code == NO_EXAMPLE else divmod(code, EX_BASE)


class RowSink:
    """Takes the tables of the union replay, program by program, and writes the task's row store. `D` is the kit's `superdag` module."""

    def __init__(self, D: Any, task: str, rec: dict, task_path: str, out: str, src: str | None, split: str | None = None):
        TH.require_value_idents()
        arclog = DH.arclog
        self.D, self.M, self.task, self.out = D, D.M, task, out
        self.rows = {r['key']: r for r in rec['tables']}
        t = json.load(open(task_path))
        self.n_train, self.n_test = len(t['train']), len(t['test'])
        self.prog_fid: dict[int, list[str | None]] = {}  # id of a program -> the QueryHash (StudyProgram.query_hash) of each of its forms
        self.done: set[str] = set()  # the QueryHashes written
        self.fid_meta: dict[str, tuple[str, list[str]]] = {}  # QueryHash -> (kind, the QueryHashes it reads)
        self.aliases: dict[str, set[tuple[int, str]]] = {}  # QueryHash -> the (union key, text) pairs written for it
        self.stored: set[str] = set()
        self.errors = 0
        self.counts = dict(functions=0, tables=0, entries=0, counts_only=0)
        self.t0 = time.time()
        os.makedirs(os.path.dirname(out), exist_ok=True)
        fd, self.tmp = tempfile.mkstemp(dir=os.path.dirname(out), prefix=os.path.basename(out) + '.')
        os.close(fd)
        self.f = GzWriter(self.tmp)
        self.put(dict(t='header', task=task, split=split if split is not None else os.environ.get('ARC_UNION_ROWS_SPLIT'), src=src, version=VERSION, hash_source='engine', hash_version='engine@' + DH.VERSION.split('+')[0], code=code_sha(),
                      query_hash_version=DH.VERSION, engine_feature_names=list(arclog.table_feature_names()),
                      engine_features_version=arclog.table_features_version(), table_hash_version=arclog.table_hash_version(), n_train=self.n_train, n_test=self.n_test, max_assignments=MAX_ASSIGNMENTS,
                      ident_source=os.environ.get('ARCLOG_IDENT_SOURCE')))

    def put(self, r: dict) -> None:
        self.f.write(json.dumps(r) + '\n')

    # ------------------------------------------------------------------ one program

    def failed(self, prog: dict, err: str, start: int = 0) -> None:
        """A program that the replay refused at its form `start`: the functions of that form and the forms after it get no entry from it."""
        self.errors += 1
        self.counts['programs_failed'] = self.counts.get('programs_failed', 0) + 1
        self.put(dict(t='error', case=prog['cases'][0], union_keys=[k for k in prog['form_keys'][start:] if k is not None], error='program does not replay: ' + err))

    def hashes(self, prog: dict, forms: list[str]) -> list[str | None]:
        """The FunctionHash of each form of the program, over the lines before it. Two forms with one union key can have two (they differ in a column
        that the union key leaves out), so the store has a function for each FunctionHash."""
        if id(prog) not in self.prog_fid:
            out: list[str | None] = []
            for i, key in enumerate(prog['form_keys']):
                try:
                    out.append(DH.definition_hash(forms[:i], forms[i]) if key is not None else None)
                except ValueError as e:
                    self.errors += 1
                    self.put(dict(t='error', union_key=key, case=prog['cases'][0], error='query_hash: ' + str(e)[:300]))
                    out.append(None)
            self.prog_fid[id(prog)] = out
        return self.prog_fid[id(prog)]

    def pending(self, prog: dict, forms: list[str]) -> bool:
        return any(h is not None and h not in self.done for h in self.hashes(prog, forms))

    def program(self, prog: dict, forms: list[str], collect: list, names: dict[str, str]) -> None:
        """Writes the functions of the program that no earlier program gave. `collect`: the `step_tables` result of each form, in the kit's layout;
        SHADOW holds each one by assignment, with rows."""
        steps: list[tuple[Any, list[int], Any]] = []
        for ct in collect:
            got = SHADOW.get(id(ct))
            steps.append((got if got is None or isinstance(got[1], Exception) else got[1], [s for s, _ in self.D.relation_tables(ct)], ct))
        self.program_steps(prog, forms, steps)

    def program_steps(self, prog: dict, forms: list[str], steps: list[tuple[Any, list[int], Any]]) -> None:
        """Writes the functions of the program that no earlier program gave. `steps`: for each form, (its `step_tables` result by assignment, with
        rows, or the reason it has none; the relation slots it defines; its result in the kit's layout, for the `legacy` key, or None)."""
        keys, fids = prog['form_keys'], self.hashes(prog, forms)
        slot_fid: dict[int, str] = {}  # slot -> the QueryHash of the form that defines it, in this program
        for i, (_, slots, _) in enumerate(steps):
            for s in slots:
                if i < len(fids) and (f := fids[i]) is not None:
                    slot_fid[s] = f
        for i, (export, _, legacy) in enumerate(steps):
            fid = fids[i] if i < len(fids) else None
            if fid is None:
                continue
            if fid in self.done:
                self.alias(fid, keys[i], forms[i])
                continue
            self.aliases[fid] = {(keys[i], forms[i])}
            self.done.add(fid)
            try:
                if export is None or isinstance(export, tuple):
                    raise TE.ExportError('no export by assignment: %s' % (export[1] if export else 'not replayed'))
                self.function(prog, forms[i], keys[i], fid, legacy, export, slot_fid)
            except Exception as e:  # noqa: BLE001
                self.errors += 1
                self.put(dict(t='error', function=fid, error='%s: %s' % (type(e).__name__, str(e)[:300])))

    def aliases_of(self, prog: dict, forms: list[str]) -> None:
        """The alias lines of a program whose functions earlier programs gave all, with no replay."""
        for i, fid in enumerate(self.hashes(prog, forms)):
            if fid is not None and fid in self.done:
                self.alias(fid, prog['form_keys'][i], forms[i])

    def fid_dets(self, fid: str) -> set[str]:
        """The DETs in the use closure of a function, by QueryHash, its own included where it is one."""
        seen, todo = {fid}, [fid]
        while todo:
            for f in self.fid_meta.get(todo.pop(), ('', []))[1]:
                if f not in seen:
                    seen.add(f)
                    todo.append(f)
        return {f for f in seen if self.fid_meta.get(f, ('', []))[0] == 'DET'}

    def fid_depth(self, fid: str, open_: frozenset[str] = frozenset()) -> int:
        """0 for a function that uses no query, else 1 + the largest depth of the queries it uses."""
        reads = [f for f in self.fid_meta.get(fid, ('', []))[1] if f not in open_ and f != fid]
        return 1 + max(self.fid_depth(f, open_ | {fid}) for f in reads) if reads else 0

    def alias(self, fid: str, key: int, text: str) -> None:
        """A form of a later program whose QueryHash has a function already: one alias line for each new (union key, text)."""
        if (key, text) not in self.aliases.setdefault(fid, set()):
            self.aliases[fid].add((key, text))
            self.put(dict(t='alias', id=fid, union_key=key, text=text))

    def function(self, prog: dict, text: str, key: int, fid: str, legacy: Any, shadow: Any, slot_fid: dict[int, str]) -> None:
        refmap = {'&r' + m: slot_fid[int(m)] for m in sorted(set(LABEL.findall(text)), key=int) if int(m) in slot_fid}
        reads = sorted(set(refmap.values()) - {fid})  # the queries this text uses; the union key's reads also hold the uses of its other texts
        kind = self.rows[key]['kind']
        self.fid_meta[fid] = (kind, reads)
        dets = self.fid_dets(fid)
        slot_id = slot_fid
        outputs = []
        export = TE.read_export(self.M, shadow)
        if not export:
            raise TE.ExportError('the engine gives no table for this form')
        other = {a.query for t in export for a in t.at if a.query} - {fid}
        if other:  # the export computes a table of a query other than the one the program hashes to
            raise TE.ExportError('the export names the query %s, not %s' % (sorted(other)[0], fid))
        legacy_tables = self.D.relation_tables(legacy) if legacy is not None else []  # the kit's merge key, where the caller gives the kit's layout
        for o, t in enumerate(export):
            legacy_keys = None
            if o < len(legacy_tables) and legacy_tables[o][0] == t.slot:
                try:
                    legacy_keys = repr(self.D.table_key(self.D.S.parse_table(self.D.OneTable(legacy, legacy_tables[o][1])))[0])
                except self.M.Fail:
                    legacy_keys = None
            seen, kept, types_full, stopped = self.entries(fid, o, t, slot_id, legacy_keys, 'entry')
            outputs.append(dict(o=o, name=t.name, types=types_full, labels=t.labels, seen=seen, kept=kept, stopped=stopped))
            self.counts['tables'] += 1
        self.put(dict(t='function', id=fid, union_key=key, kind=kind, text=text, reads=reads, depth=self.fid_depth(fid), dets=sorted(dets),
                      refmap=refmap, case=prog['cases'][0], outputs=outputs))
        self.counts['functions'] += 1

    # ------------------------------------------------------------------ the tables of one function

    def code_of(self, v: int) -> int:
        return example_code(TE.EXAMPLE_TRAIN, v) if v < self.n_train else example_code(TE.EXAMPLE_TEST, v - self.n_train)

    def entries(self, fid: str, o: int, t: TE.ExportTable, slot_id: dict[int, str], legacy: str | None, kind: str) -> tuple[int, int, list[str], bool]:
        """Writes an entry for each of the table's first MAX_ASSIGNMENTS assignments. Returns (assignments, kept, types with Example, the engine's cap flag)."""
        native = 'Example' in t.types
        types_full = t.types if native else t.types + ['Example']
        for at in t.at[:MAX_ASSIGNMENTS]:
            self.entry(fid, o, t, at, slot_id, types_full, native, legacy, kind)
            self.counts['entries'] += 1
        return len(t.at), min(len(t.at), MAX_ASSIGNMENTS), types_full, any(a.capped for a in t.at)

    @staticmethod
    def det_id(name: str, query: str | None, slot_id: dict[int, str]) -> str:
        """The id of a DET of an assignment: the QueryHash that the export gives, else that of the form that defines its slot, else 'slot <n>' for
        a slot that no form of the program defines (a DET of the probe), else its name (a base DET)."""
        if query:
            return query
        m = SLOT_NO.fullmatch(name)
        return slot_id.get(int(m[1]), 'slot ' + m[1]) if m else name

    def entry(self, fid: str, o: int, t: TE.ExportTable, at: TE.At, slot_id: dict[int, str], types_full: list[str], native: bool, legacy: str | None, kind: str) -> None:
        queries = at.det_queries if kind != 'given' else []  # a given table's DETs are the probe's, named by slot
        pairs = sorted((self.det_id(d, queries[k] if k < len(queries) else None, slot_id), v) for k, (d, v) in enumerate(at.dets))  # the DET by QueryHash, its value by the engine's value hash
        r: dict[str, Any] = dict(t=kind, function=fid, o=o, name=t.name, assignment=[list(p) for p in pairs], types=types_full,
                                 legacy=legacy, engine_features=at.features)
        ex_at = sum(TH.WIDE.get(x, 1) for x in t.types[:t.types.index('Example')]) if native else -1
        es = at.entries
        if not es or not all(e.complete for e in es) or at.hash is None:
            counts = sorted((example_code(e.kind, e.index), e.n) for e in es)
            r.update(kind='counts_only', hash=at.hash or TH.counts_hash(types_full, counts), examples=[list(k) for k in at.keys])
            self.put(r)
            self.counts['counts_only'] += 1
            return
        units: dict[tuple[int, bytes], tuple[int, np.ndarray, np.ndarray | None]] = {}
        for e in es:
            assert e.rows is not None
            a = e.rows.astype(np.int64)
            if native:
                codes = np.array([self.code_of(int(v)) for v in a[:, ex_at]], np.int64)
                a[:, ex_at] = codes
            else:
                codes = np.full(len(a), example_code(e.kind, e.index), np.int64)
                a = np.concatenate([a, codes[:, None]], axis=1)
            parts = [(int(c), np.flatnonzero(codes == c)) for c in np.unique(codes)] if len(a) else [(example_code(e.kind, e.index), np.zeros(0, np.int64))]
            for c, idx in parts:
                sub = a[idx]
                order = np.lexsort(sub.T[::-1]) if len(sub) else idx
                sub = sub[order]
                box = e.boxes[idx][order] if e.boxes is not None and len(sub) else None
                units.setdefault((c, sub.tobytes()), (c, sub, box))
        r.update(kind='content', hash=at.hash, examples=[list(k) for k in at.keys])
        if at.hash not in self.stored:
            self.stored.add(at.hash)
            rows = [dict(ex=c, n=len(a), cells=_b64(a, '<i4'), boxes=_b64(box, '<f4') if box is not None else '')
                    for c, a, box in sorted(units.values(), key=lambda u: (u[0], u[1].tobytes()))]
            self.put(dict(t='table', hash=at.hash, types=types_full, rows=rows))
        self.put(r)

    # ------------------------------------------------------------------ the given tables

    def given_steps(self, cts: list) -> None:
        """Writes the entries of the given tables from the `step_tables` results by assignment, with rows, of the probe program PROBE."""
        for name, ct in zip(GIVEN, cts):
            for o, t in enumerate(TE.read_export(self.M, ct)):
                self.entries(name, o, t, {}, None, 'given')

    def given(self, run: Any) -> None:
        """Replays a probe program of three functions that copy the given tables, and writes their entries."""
        run.collect = []
        ACTIVE[0] = True
        try:
            run.scope(PROBE)
            cts = list(run.collect)
        finally:
            ACTIVE[0] = False
            run.collect, run.scoped = None, None
        for name, ct in zip(GIVEN, cts):
            got = SHADOW.get(id(ct))
            if got is None or isinstance(got[1], Exception):
                raise TE.ExportError('no export by assignment for the given table ' + name)
            for o, t in enumerate(TE.read_export(self.M, got[1])):
                self.entries(name, o, t, {}, None, 'given')
        prune()

    def close(self) -> None:
        self.put(dict(t='footer', **self.counts, errors=self.errors, seconds=round(time.time() - self.t0, 1)))
        self.f.close()
        os.replace(self.tmp, self.out)
