"""Stage 5 of the sample build: the training instances of the gradient-boosted trees, one writing point of a target query at a time, with the writer's own features.

  python3 points_write.py SET --plan ordered|unordered [--shard k/N] [--tasks T,T,...] [--samples-per-task K] [--seed S] [--seconds X] [--max-states N] [--vectors] [--draws GLOB|DIR] [--skeleton DIR] [--graphs DIR] [--out DIR]

SET is train, dev or held-out. The extractor (train_rows.points_of, with writer.Features) and the engine wheel come from sys.path: run it with the runtime python and with PYTHONPATH holding the
extractor's folder and the wheel's site folder. For each task of OUTD/SET/skeleton (or of --skeleton DIR) it writes OUTD/SET/points/<plan>/<task>.jsonl.gz (train and dev tasks) or OUTD/SET/points_held-out/<plan>/<task>.jsonl.gz
(held-out tasks), to a temp file and then renamed, and skips a task whose file holds the same skeleton sha, extractor shas, wheel, code sha and sample choice. It is not a fit: it writes every
task, held-out ones included, and calls no split guard. With --samples-per-task K a task keeps at most K samples, chosen by a hash of the seed and the sample id (0: all).

For each sample:
- Scope: the union of the members' programs, members in dependency order (fewest closure queries first, then QueryHash), each with one global label `&r<position>`, and each query's own text
  rewritten from its local labels to the global ones (local &r<i> is closure[i]; the last local label is the query's own).
- Targets: decided by target_rule (docs/sample-build/contract.md, "Sample") from the TableHashes of the scope's tables, for every state that is written, skeleton sample or added.
  The scope's tables come from the engine's step_tables results of the scope's queries (Run.keep_closed), and the graph tables' maps and each graph query's reads and heads from the union's graph files
  (--graphs DIR, default $ARC_SAMPLE_GRAPHS, else split.GRAPHS: `graph-prods-SET.jsonl` and `graph-tables-SET.jsonl`; their lines of the task must have the shas that the skeleton's header records, else the task is skipped
  and counted under failures). The skeleton's `target_queries` are not read.
  A target is a union query (its text is its query record's, over the scope's labels), or a graph query written through stand-ins (stand_in.py): the text of a query record of the graph query, with each read of a
  table that is not a member's replaced by a read of the member's table that stands for its graph table, and the sites of the read moved to that table's columns (paired by content). The engine computes the replaced
  query's table from its own program (a scope of its own) to pair the columns. A target that cannot be written is counted in the summary's `failures` under `target`, by reason (`stand-in: <reason>` for those).
- For each target query: its text over the scope's labels, its kind and its token stream as train_rows.py takes them; train_rows.points_of_targets gives the writing points of all targets of a kind with every feature name, a shared prefix once.
- Labels come from the extractor: `positive_ids` (a subset of `ids`), `live`, `order` and `order_why` of each record of `train_rows.points_of_targets(..., plan=PLAN)`. Under `ordered`
  each target is walked in its canonical order (or its given order where no rule gives its QueryHash), and the positives are the next tokens of the live targets. Under `unordered` the points are
  the states of a search over each target's item set, one record for each live target at a state, all with the state's positives. The records of one point must agree on `positive_ids` and
  `live`; the points where they do not are counted.
- A point is written once for each (sample, kind, token prefix); under `unordered` the token prefix is that of the first visit of a state, so it is the state's key too.

A file is gzip JSONL:
- `header`: task, set, plan, split, uses (every feature name, in the extractor's order), skeleton_sha, extractor_sha (train_rows.py), writer_sha (writer.py), wheel (the site folder's name), code (this file's sha), samples_per_task, seed, point_names,
  option_names (the option names without `table:`), table_names (the `table:` names, in order).
- `table`: {i, values}: one vector of the `table:` option columns, written once before its first use.
- `point`: sample, kind, length (the number of model tokens so far, the kind token included), ids, option (ids x option_names), table (the `table` index of each id), point (values of
  point_names), positive (indexes into ids), live (the count of live targets).
- `summary`: the counts of the file, last.
Rebuilding the extractor's option matrix from option and table must give it back bit for bit; each written point is checked on the text as written.

With --vectors a point row is the writer's full writing-point vector of each id (`writer.Features.vectors`; train_rows.points_of_targets(..., vectors=True)) in place of the 260 prefix features:
- `header` also has `vectors` (true), `vector_names` (the column names, in order), `vector_point_cols` (the indexes of the columns of the point-scope blocks, which every id of a point repeats)
  and `uses` = `vector_names`; `option_names`, `table_names` and `point_names` are empty.
- `point` has `vp` (the point-scope columns, one row) and `vo` (the other columns, one row for each id), each float32 little-endian in base64, and has neither `option`, `table` nor `point`.
- A point is written only if rebuilding the matrix from `vp` and `vo` gives the extractor's matrix back bit for bit (NaN equal to NaN) and every point-scope column is equal across the ids of the point.
  A point that fails is counted (`rebuild failures`, `point-scope columns that differ across ids`) and not written.
- A file with vectors and a file without are never current for each other.

With --draws, the sampled-query records of the search give each point's `drawn` counts and the states off the samples (docs/sample-build/training-instances.md, "Sampled queries of the search").
GLOB is a glob of record files (`draws.jsonl`, on disk plain or zstd; model/study/sampler/draw_record.py); DIR is a folder searched for `draws.jsonl` files. A record file of a task that is not
train by split.py is refused (exit 2) before any file is written.
- A record is one line of a file, or {"repeat": d, "draw": n}, which adds 1 to the count of the record of number d of that file. A record that solves every train example gives no `drawn` count.
- A record's last step is matched when its state (the set of its `state` QueryHashes) equals the state of a sample of the file (the samples that --samples-per-task keeps, and every skeleton
  sample whose state a record has); its other steps are used only to add a state. A record that matches several samples is walked, and counted, for each.
- A last step whose state equals no such sample's state adds the state as a sample (plan_added), once whatever the count of records that reach it. Its targets are the rule's, as for a skeleton sample. The state's queries that are no union queries are written from the steps of a
  record: each one's text with its pool names as local labels, and its use closure from the names that the text reads (off_path_queries). The scope holds them as it holds the union's queries, so
  the engine gives their tables with `run.scope`, as it gives the union's. The sample's id is the skeleton's rule over the state's sorted QueryHashes. A state that cannot be added is counted
  with its reason: a step has no QueryHash, a step does not give a query record, the rule gives no target query, or the sample fails (the engine refused
  the scope, or `error: <exception type>`; an exception of the engine that is no refusal is never counted as one).
- The drawn query's names are the sample's: the last step's own name (`&fN`, the first name of its text) is `&r<len(scope)>`, as a target's own label is, and each other `&fN` (or a RIGID_DET part's
  `.fN` step) is the global label of the QueryHash of the step whose own name it is. Its token stream is decoded over the sample's scope as a target's is.
- The path of the drawn query under the plan: `ordered` walks its canonical stream (order.canonical_stream, as the targets are walked); `unordered` walks its stream as written through the
  states of the search (train_rows.points_of_unordered's graph), from the first state, along the edge of each token.
- At the first point of the path whose positives do not hold the drawn query's next token, that token gets the record's count added to its `drawn` count, and the walk ends; where the token is not
  an id of the point it is counted (`not admitted`) and nothing is added. A path whose tokens are all positives gives nothing.
- `point` then also has `drawn`: [[index into ids, count], ...]. The header is written when the file is closed and also has `draws` (the task's record files, each [path, sha256 of the text]) and
  `draw_counts`, in last steps with their repeats unless stated: `matched` (last steps whose state is a skeleton sample's), `added` (last steps whose state was added and written), `added states`
  (the distinct states added and written), `not added: <reason>`, `solves` (of those, the records that solve every train example), and what became of the matched ones. The summary also has
  `samples_added`.
"""
import argparse
import base64
import glob
import io
import zstandard
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import zlib
from collections import ChainMap, Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_path = list(sys.path)
from split import GRAPHS, is_held_out, split_of  # noqa: E402
from union_forms import LineIndex  # noqa: E402
import study_zst as Z  # noqa: E402  (split.py puts model/study on sys.path for it)
import stand_in  # noqa: E402  (column_map.py puts model/study on sys.path too)
sys.path[:] = _path  # split.py puts model/study first on sys.path, where its writer.py would shadow the writer kit's
del _path

OUTD = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/samples')
REPO = Path(__file__).resolve().parents[3]
SCHEMA = 'points-1'
# the reasons that count a state as not added in the header's draw_counts (`not added: <reason>`); run/draw_targets.py reads them from here
NO_HASH = 'a step has no QueryHash'
NO_TARGET = 'the rule gives no target query'
NO_WRITTEN = 'no target query could be written'
# the counts of the summary's `target_rule`: the state's queries that have no table in the scope; the target queries that the rule gives through a stand-in (stand_in.py); the states with no target query
RULE_COUNTS = ('members with no table', 'target queries through a stand-in', 'samples with no target')
VECTOR_COUNTS = ('point-scope columns that differ across ids', 'vector shape or names differ from the header')
LABEL = re.compile(r'&r(\d+)')
DRAW_NAME = re.compile(r'(&f\d+)((?:\.\w+)*)')  # a pool name of a draw's text, with the steps of a RIGID_DET part or an INIT output
DRAW_HEAD = re.compile(r'^\(\s*\S+\s+(&f\d+)')  # the query's own name: the first name of its text
type Atom = tuple[int, ...]


class Reject(Exception):
    """A sample or a target query that cannot be written; the message is the reason that is counted."""


@dataclass
class Point:
    """A writing point of a sample, written once for its (kind, token prefix)."""
    kind: str
    tokens: tuple[int, ...]
    phase: str
    ids: list[int]
    ids_text: str
    option_text: str
    table: list[int]
    point_text: str
    positive_ids: np.ndarray
    live: int
    next_ids: set[int] = field(default_factory=set)
    drawn: Counter[int] = field(default_factory=Counter)  # with --draws: id -> the count of failed draws that took it here
    vp: str = ''  # with --vectors: the point-scope columns and the id-scope columns, as base64
    vo: str = ''


@dataclass
class Totals:
    counts: Counter[str] = field(default_factory=Counter)
    seconds: defaultdict[str, float] = field(default_factory=lambda: defaultdict(float))
    failures: dict[str, Counter[str]] = field(default_factory=dict)  # kind of failure -> reason -> count
    examples: dict[str, str] = field(default_factory=dict)  # reason -> one example
    search: Counter[str] = field(default_factory=Counter)  # the extractor's counts of the plan, and the order of each target
    largest: int = 0  # the most states of one search

    def fail(self, what: str, reason: str, example: str, n: int = 1) -> None:
        self.failures.setdefault(what, Counter())[reason] += n
        self.examples.setdefault(f'{what}: {reason}', example)

    def add(self, other: 'Totals') -> None:
        self.counts += other.counts
        for k, v in other.seconds.items():
            self.seconds[k] += v
        self.search += other.search
        self.largest = max(self.largest, other.largest)
        for what, c in other.failures.items():
            self.failures.setdefault(what, Counter()).update(c)
        for k, v in other.examples.items():
            self.examples.setdefault(k, v)



def prefix_hash(tokens):
    """16 hex digits that name a point's token prefix (the kind token on). The record also holds the prefix itself as `tokens`, so that a later filter replays the point's masks without walking its path again."""
    import hashlib
    return hashlib.blake2b(','.join(str(int(t)) for t in tokens).encode(), digest_size=8).hexdigest()

def why(e: BaseException) -> str:
    text = str(e).strip().splitlines()
    return f'{type(e).__name__}: {text[0][:90] if text else ""}'


def module_file(m: Any) -> Path:
    """The file of an imported module, resolved."""
    return Path(m.__file__).resolve()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- number text

def float_text(x: np.floating) -> str:
    if math.isnan(x):
        return 'NaN'
    if math.isinf(x):
        return 'Infinity' if x > 0 else '-Infinity'
    if x == 0:
        return '-0.0' if math.copysign(1.0, x) < 0 else '0'
    if x == int(x) and abs(x) < 1e7:
        return str(int(x))
    return str(np.float32(x))


def row_text(row: np.ndarray) -> str:
    """A float32 vector as JSON text, each number as the shortest text that gives its float32 back."""
    if np.isfinite(row).all() and not np.signbit(row[row == 0]).any() and (np.abs(row) < 1e7).all():
        as_int = row.astype(np.int64)
        if (as_int == row).all():
            return json.dumps(as_int.tolist(), separators=(',', ':'))
    return '[' + ','.join(float_text(x) for x in row) + ']'


def matrix_text(m: np.ndarray) -> str:
    return '[' + ','.join(row_text(r) for r in m) + ']'


def same_bits(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=True)) and bool(np.array_equal(np.signbit(a), np.signbit(b)))


def f32_text(a: np.ndarray) -> str:
    """A float32 array as little-endian bytes in base64."""
    return base64.b64encode(np.ascontiguousarray(a, dtype='<f4').tobytes()).decode('ascii')


def f32_back(text: str, shape: tuple[int, ...]) -> np.ndarray:
    return np.frombuffer(base64.b64decode(text), dtype='<f4').astype(np.float32).reshape(shape)


def vector_point_cols(wr: Any, names: tuple[str, ...]) -> list[int]:
    """The indexes of the columns of the point-scope blocks of writer.VECTOR_BLOCKS; each column name is `<block>:<feature>` and belongs to exactly one block."""
    cols = []
    for i, n in enumerate(names):
        owners = [b for b in wr.VECTOR_BLOCKS.values() if n.startswith(b.name + ':')]
        if len(owners) != 1:
            raise RuntimeError(f'the vector column {n!r} belongs to {len(owners)} blocks')
        if owners[0].scope == 'point':
            cols.append(i)
    return cols


# ---------------------------------------------------------------- the scope

def scope_of(members: list[str], queries: Mapping[str, dict]) -> tuple[list[str], dict[str, str]]:
    """(the members' texts in scope order, the global label of each member's QueryHash)."""
    for h in members:
        if h not in queries:
            raise Reject('a member has no query record')
    order = sorted(members, key=lambda h: (len(queries[h]['closure']), h))
    label = {h: f'&r{i}' for i, h in enumerate(order)}
    texts = []
    for h in order:
        q = queries[h]
        for c in q['closure']:
            if c not in label:
                raise Reject('a member\'s closure names a query that is not a member')
            if int(label[c][2:]) >= int(label[h][2:]):
                raise Reject('a member\'s closure is not before it in dependency order')
        texts.append(rewrite(q, label, label[h]))
    return texts, label


def rewrite(query: dict, label: dict[str, str], own: str) -> str:
    """The query's own text with its local labels written as the global ones; `own` is the label of the query itself. A label past the query's own
    is a relation that a DEMONSTRATED query declares in its rules, local to the query: it is written as a label past every label of the scope, so it
    names no member. A member's rules read only members before it, so a later query's label in that range does not reach them."""
    program, closure = query['program'], query['closure']
    if len(program) != len(closure) + 1:
        raise Reject('the program is not its closure and then the query\'s own text')

    def put(m: re.Match[str]) -> str:
        i = int(m.group(1))
        if i < len(closure):
            if closure[i] not in label:
                raise Reject('a closure query has no label in the scope')
            return label[closure[i]]
        if i == len(closure):
            return own
        return f'&r{len(label) + i - len(closure) - 1}'
    return LABEL.sub(put, program[-1])


# ---------------------------------------------------------------- the search draws

@dataclass
class Draw:
    """The last step of a sampled-query record, with the count of the records that it stands for."""
    text: str  # the drawn query as the pool wrote it, with &fN names
    state: frozenset[str | None]  # the QueryHashes of the steps before it
    names: dict[str, str]  # the own name of each step before it -> that step's QueryHash
    solves: bool
    earlier: tuple[tuple[str, str | None], ...]  # (text, QueryHash) of the steps before the last, in program order
    count: int = 1


def draw_files(spec: str) -> list[Path]:
    """The sampled-query record files of --draws, by their logical names (`draws.jsonl`, on disk plain or zstd): the files below a folder, or those that a glob matches."""
    if os.path.isdir(spec):
        found = {Z.logical(p) for p in Path(spec).rglob('draws.jsonl*') if p.name in ('draws.jsonl', 'draws.jsonl.zst')}
    else:
        pattern = Z.logical(spec)
        found = {Z.logical(p) for p in glob.glob(pattern, recursive=True) + glob.glob(pattern + '.zst', recursive=True) if os.path.isfile(p)}
    return sorted(Path(p) for p in found)


def draw_file_task(path: Path) -> str | None:
    """The task of a record file, from its first record (record 1 is never a repeat); None for an empty file."""
    with Z.open_text(path) as f:
        for text in f:
            rec = json.loads(text)
            if 'task' in rec:
                return rec['task']
    return None


def read_draws(paths: list[Path]) -> list[Draw]:
    """The last steps of the files' sampled-query records, one for each record, each with its repeats counted. A line that is neither a record nor a repeat is one of the
    worker's counts of an expansion that wrote no query (it has `ended`); any other line is an error."""
    draws: list[Draw] = []
    for path in paths:
        at: dict[int, Draw] = {}  # a record's number in this file -> its record
        with Z.open_text(path) as f:
            for text in f:
                rec = json.loads(text)
                if 'repeat' in rec:
                    first = at.get(int(rec['repeat']))
                    if first is not None:
                        first.count += 1
                    continue
                if 'steps' not in rec:
                    if 'ended' not in rec:
                        raise ValueError(f'{path}: a line that is no sampled-query record, repeat or count of an ended expansion: {text[:120]}')
                    continue
                steps = rec['steps']
                names = {}
                for s in steps[:-1]:
                    m = DRAW_HEAD.match(s['text'])
                    if m and s['query_hash'] is not None:
                        names[m[1]] = s['query_hash']
                d = Draw(steps[-1]['text'], frozenset(steps[-1]['state']), names, bool(rec['solves']), tuple((s['text'], s['query_hash']) for s in steps[:-1]))
                at[int(rec['draw'])] = d
                draws.append(d)
    return draws


def renamed(text: str, to: Mapping[str, str]) -> str:
    """The text with each pool name written as the label that `to` gives it. A RIGID_DET part's `.fN` step is written `.rK`, with &rK the label of &fN.
    Raises Reject where a name has no label."""
    def one(m: re.Match[str]) -> str:
        if m[1] not in to:
            raise Reject('a name of the query is no query of the sample\'s scope')
        steps = [to[m[1]]]
        for st in m[2].split('.')[1:] if m[2] else []:
            if re.fullmatch(r'f\d+', st):
                if '&' + st not in to:
                    raise Reject('a name of the query is no query of the sample\'s scope')
                steps.append(to['&' + st][1:])
            else:
                steps.append(st)
        return '.'.join(steps)
    return DRAW_NAME.sub(one, text)


def drawn_text(draw: Draw, label: dict[str, str], own: str) -> str:
    """The drawn query's text with the sample's names: its own name is `own`, and each other pool name is the global label of its step's QueryHash."""
    to = {n: label[h] for n, h in draw.names.items() if h in label}
    m = DRAW_HEAD.match(draw.text)
    if not m:
        raise Reject('the drawn query has no own name')
    to[m[1]] = own
    return renamed(draw.text, to)


# ---------------------------------------------------------------- the states off the samples

def pool_names(text: str) -> set[str]:
    """The pool names that a step's text mentions: each `&fN`, and each `.fN` step of a RIGID_DET part or an INIT output."""
    names = set()
    for m in DRAW_NAME.finditer(text):
        names.add(m[1])
        names.update('&' + st for st in m[2].split('.')[1:] if re.fullmatch(r'f\d+', st))
    return names


def off_path_queries(earlier: tuple[tuple[str, str | None], ...], union: Mapping[str, dict]) -> dict[str, dict]:
    """The query record of each step, among the steps of a sampled-query record that come before its last, that is no query of the union (`union`: the skeleton's query records by
    QueryHash). A record has the fields that `scope_of` and `rewrite` read: its use closure (the QueryHashes of the queries that it reads, and those they read, in step order) and its
    program (the closure's places empty, and its own text with `&r<i>` for the i-th query of the closure and `&r<len(closure)>` for itself). A union query has the closure that the
    skeleton gives it. Raises Reject where the steps do not give such a record."""
    steps: list[tuple[str, str, str]] = []  # (text, QueryHash, own pool name) of each step
    name_of: dict[str, str] = {}  # a pool name -> the QueryHash of the step that it names
    for text, h in earlier:
        m = DRAW_HEAD.match(text)
        if h is None:
            raise Reject(NO_HASH)
        if m is None:
            raise Reject('a step has no own name')
        if m[1] in name_of:
            raise Reject('two steps have one name')
        name_of[m[1]] = h
        steps.append((text, h, m[1]))
    if len(set(name_of.values())) != len(name_of):
        raise Reject('two steps have one QueryHash')
    below: dict[str, set[str]] = {}  # the QueryHash of a step -> the QueryHashes of its use closure
    out: dict[str, dict] = {}
    for text, h, own in steps:
        reads = pool_names(text) - {own}
        above: set[str] = set()
        for n in reads:
            r = name_of.get(n)
            if r is None:
                raise Reject('a step reads a name that no step has')
            if r not in below:
                raise Reject('a step reads a step that comes after it')
            above |= below[r] | {r}
        if h in union:
            below[h] = set(union[h]['closure'])
            continue
        closure = [x for _, x, _ in steps if x in above]
        if len(closure) != len(above):
            raise Reject('the closure of a step holds a query that is no step')
        local = {n: f'&r{closure.index(name_of[n])}' for n in reads}
        below[h] = above
        kind = re.match(r'\((\w+)', text)
        out[h] = dict(record='query', hash=h, kind=kind[1] if kind else None, closure=closure, program=[''] * len(closure) + [renamed(text, local | {own: f'&r{len(closure)}'})], off_path=True)
    return out


# ---------------------------------------------------------------- the targets of a state

# A table map is {(assignment, TableHash)} of one table: an assignment is written as the union graph writes it (gold_union_tables.py), the sorted pairs (the set of the TableHashes of a DET's values, the TableHash of
# the DET's table at the value) of the DETs that have more than one value, so that DETs of two programs compare by their values' TableHashes. A table that the engine gives no TableHash has UNHASHED at that assignment, and stands for nothing and gives no progress (`unhashed`).
type TableMap = frozenset[tuple[tuple[tuple[str, str], ...], str]]
UNHASHED = 'none'
# the parts of the rule that decide a union query that is no target (the reason of `Verdict.why`)
BY_MEMBER = 'a member of the state'
BY_INPUT = 'it reads a query that is no member of the state'
BY_APPLIES = 'a graph table it reads is stood for by no member\'s table'
BY_PROGRESS = 'no table it computes has a TableHash that no member\'s table has'
BY_GRAPH = 'its graph query is not in the graph files'


def digest(x: Any) -> str:
    """16 hex digits of a hash of x as JSON: the `digest` of model/study/gold/reads/union/gold_union_tables.py, which names the DET value sets in a graph table's map."""
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]


def table_maps(entries: list[tuple[str, str, tuple[tuple[Any, str], ...], str | None]]) -> dict[tuple[str, str], TableMap]:
    """The map of each table, from the engine's tables at assignments: entries are (QueryHash, Name, assignment as (DET QueryHash, value hash) pairs, TableHash or None). This is the rule of
    gold_union_tables.tables_of that makes a graph table's map, over these entries: a DET's value is the TableHash of the DET's own table at that value (else its value hash), a DET is its set of
    those, and a DET with one value is left out of the assignments."""
    tables_at: dict[tuple[Any, str], set[str]] = {}
    for fn, _, at, h in entries:
        for d, v in at:
            if d == fn:
                tables_at.setdefault((d, v), set()).add(h or UNHASHED)
    table_of = {k: min(v) if len(v) == 1 else digest(sorted(v)) for k, v in tables_at.items()}
    values: dict[Any, set[str]] = {}
    for _, _, at, _ in entries:
        for d, v in at:
            values.setdefault(d, set()).add(table_of.get((d, v), v))
    value_set = {d: digest(sorted(v)) for d, v in values.items()}
    one_value = {d for d, v in values.items() if len(v) == 1}
    out: dict[tuple[str, str], set] = {}
    for fn, name, at, h in entries:
        a = tuple(sorted((value_set[d], table_of.get((d, v), v)) for d, v in at if d not in one_value))
        out.setdefault((fn, name), set()).add((a, h or UNHASHED))
    return {k: frozenset(v) for k, v in out.items()}


def scope_maps(wr: Any, pg: Any) -> dict[tuple[str, str], TableMap]:
    """The map of each table of each query of the scope that `pg` (the Program that Run.scope gives) holds, keyed by (QueryHash, Name): the engine's TableHash of the table at each assignment.
    The Run must keep each closed query's step_tables result (writer.keep_state_tables)."""
    if len(pg.closed) != len(pg.kinds):
        raise RuntimeError('the scope did not keep its queries\' tables (writer.keep_state_tables)')
    entries: dict[tuple, tuple] = {}
    for ct in pg.closed:
        for r in wr.AS.assignment_summaries(ct, pg.queries):
            if isinstance(r.table, tuple):
                at = tuple(('%032x' % d if d >= 0 else d, '%032x' % v) for d, v in r.at)
                entries[('%032x' % r.table[0], r.table[1], at)] = ('%032x' % r.table[0], r.table[1], at, None if r.hash is None else '%032x' % r.hash)
    return table_maps(list(entries.values()))


@dataclass
class Graph:
    """The union graph of a task, from its graph files."""
    maps: dict[str, TableMap | None]  # a graph table -> its map; None where the graph table has none (the row store has no query for it) or an empty one
    reads: dict[str, tuple[str, ...]]  # a graph query (its identity) -> the graph tables it reads
    heads: dict[str, tuple[str, ...]]  # a graph query -> the graph tables it computes


def graph_of(prods: list[bytes], tables: list[bytes]) -> Graph:
    """The Graph of one task, from its lines of graph-prods-SET.jsonl and graph-tables-SET.jsonl."""
    maps: dict[str, TableMap | None] = {}
    for t in map(json.loads, tables):
        m = t['map']
        maps[t['table']] = frozenset((tuple((a, b) for a, b in e[0]), e[1]) for e in m) if t['exported'] and m else None
    p = [json.loads(x) for x in prods]
    return Graph(maps, {r['ident']: tuple(r['reads']) for r in p}, {r['ident']: tuple(r['heads']) for r in p})


def unhashed(m: TableMap) -> bool:
    """Whether a table's map has a pair with no TableHash, in the table's own place or in a DET's value in an assignment: such a table stands for no graph table and gives no progress."""
    return any(h == UNHASHED or any(v == UNHASHED for _, v in a) for a, h in m)


@dataclass
class Verdict:
    targets: list[str]  # the QueryHashes of the union queries that are target queries, sorted
    why: dict[str, str]  # a union query that is no target -> the part of the rule that decided it (BY_*)
    stand_ins: list[stand_in.StandIn]  # the target queries that are graph queries written through stand-ins: no union query is written over those members
    lost: Counter[str]  # the choices of members that give a target query but have no query record to be written from, by reason


def target_rule(state: frozenset[str], member_maps: Mapping[tuple[str, str], TableMap], graph: Graph, union: Mapping[str, dict], templates: stand_in.Templates, anywhere: bool = False) -> Verdict:
    """The target queries of a state, by the rule of docs/sample-build/contract.md ("Sample"). `member_maps` are the maps of the tables of the state's queries (scope_maps), `union` the skeleton's query records
    by QueryHash, `templates` their reads (stand_in.read_index). A graph query g is a target query when g applies at the state, g makes progress at it, and it is written over members that are not a member already.
    - g applies when each graph table that g reads is stood for by a member's table: its map equals that table's map. A table with no TableHash at some assignment (UNHASHED) stands for nothing.
    - g makes progress when a graph table that it computes has, at some assignment, a TableHash that no member's table has there (the contract's wording): the pair (assignment, TableHash) is in no member's
      map. A pair with no TableHash gives no progress. With `anywhere` the TableHash is compared with the TableHashes of all assignments of all member tables instead.
    - g is written over members in one way for each choice of one member's table at each graph table it reads. A union query h of g whose reads and use closure are members is such a target, and is `targets`.
      A choice that no such union query gives is `stand_ins`: a query record of g with its reads replaced by the choice."""
    by_map: dict[TableMap, list[tuple[str, str]]] = {}
    for k, m in sorted(member_maps.items()):
        if not unhashed(m):
            by_map.setdefault(m, []).append(k)
    maps = set(member_maps.values())
    hashes = {h for m in maps for _, h in m} - {UNHASHED}
    here = {e for m in maps for e in m}

    def stood(t: str) -> bool:
        m = graph.maps.get(t)
        return m is not None and m in by_map

    def applies(g: str) -> bool:
        return all(stood(t) for t in graph.reads[g])

    def progresses(g: str) -> bool:
        return any(e[1] != UNHASHED and all(v != UNHASHED for _, v in e[0]) and ((e[1] not in hashes) if anywhere else (e not in here)) for t in graph.heads[g] for e in graph.maps.get(t) or ())

    why: dict[str, str] = {}
    covered: set[tuple[str, frozenset[tuple[str, str]]]] = set()  # (graph query, the tables its union query over members reads)
    for h, r in union.items():
        reads = [(i['query'], i['name']) for i in r['inputs'] if 'query' in i]
        over_members = all(q in state for q, _ in reads) and set(r['closure']) <= state
        if h in state:
            why[h] = BY_MEMBER
            continue
        if not over_members:
            why[h] = BY_INPUT
            continue
        gs = [g for g in r['graph_queries'] if g in graph.reads]
        if not gs:
            why[h] = BY_GRAPH
            continue
        reason = BY_APPLIES  # the part that decides h is that of the graph query that gets furthest
        for g in gs:
            if not applies(g):
                continue
            if not progresses(g):
                reason = BY_PROGRESS if reason == BY_APPLIES else reason
                continue
            reason = ''
            covered.add((g, templates.reads[h]))
        if reason:
            why[h] = reason
    candidates = [g for g in sorted(graph.reads) if applies(g) and progresses(g)]
    standing = {t: by_map[graph.maps[t]] for g in candidates for t in graph.reads[g]}  # type: ignore[index]
    stand_ins, lost = stand_in.choices(candidates, graph.reads, standing, templates, covered)
    return Verdict(sorted(h for h in union if h not in why), why, stand_ins, lost)


def plan_added(task: str, draws: list[Draw], union: Mapping[str, dict], have: set[frozenset[str | None]]) -> tuple[list[dict], dict[str, dict[str, dict]], dict[frozenset[str | None], str]]:
    """The samples that the last steps' states off the samples add (docs/sample-build/training-instances.md, "States off the samples"): (the added samples, each state once, in the
    order of its first record; the query records of each added sample's queries that are no union query, by sample id; the reason for each state that cannot be added).
    `have` are the states of the samples that the extractor writes. An added sample has no target queries yet: `target_rule` gives them once the engine has computed the scope's tables.
    A state with a step that has no QueryHash, or whose records all fail `off_path_queries` (the first record that gives the queries is used), is not added, and has its reason in the third result."""
    by_state: dict[frozenset[str | None], list[Draw]] = {}
    for dr in draws:
        by_state.setdefault(dr.state, []).append(dr)
    added: list[dict] = []
    extra: dict[str, dict[str, dict]] = {}
    refused: dict[frozenset[str | None], str] = {}
    for st, group in by_state.items():
        if st in have:
            continue
        if None in st:
            refused[st] = NO_HASH
            continue
        got: dict[str, dict] | None = None
        for dr in group:
            try:
                got = off_path_queries(dr.earlier, union)
                break
            except Reject as e:
                refused.setdefault(st, str(e))
        if got is None:
            continue
        refused.pop(st, None)
        members = sorted(h for h in st if h is not None)
        sid = hashlib.sha256((task + '\n' + '\n'.join(members)).encode()).hexdigest()[:32]
        added.append(dict(record='sample', id=sid, task=task, state=dict(id=sid, queries=members), off_path=sum(h not in union for h in members)))
        extra[sid] = got
    return added, extra, refused


def reason_of(e: BaseException) -> str:
    """The reason that counts a failed sample in the header: a refusal by its first phrase, any other failure by its type."""
    return str(e).split(': ')[0] if isinstance(e, Reject) else 'error: ' + type(e).__name__


# ---------------------------------------------------------------- stepping a target's stream

# ---------------------------------------------------------------- one file

class Sink:
    """A task's file: the header, the table vectors once each before their first use, the points, the summary. The header is written at close, so that it can hold counts of the
    whole file: the file is one gzip member of the header and then the gzip member of the rest, which is written as it comes."""

    def __init__(self, path: Path, header: dict):
        fd, self.tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
        self.f = io.TextIOWrapper(zstandard.ZstdCompressor(level=3).stream_writer(os.fdopen(fd, 'wb')), encoding='utf-8')
        self.path = path
        self.header = header
        self.index: dict[bytes, int] = {}
        self.parsed: list[np.ndarray] = []
        self.pending: list[str] = []

    def table_index(self, row: np.ndarray) -> int:
        key = row.tobytes()
        i = self.index.get(key)
        if i is None:
            i = self.index[key] = len(self.parsed)
            text = row_text(row)
            self.parsed.append(np.array(json.loads(text), np.float32))
            self.pending.append(f'{{"record":"table","i":{i},"values":{text}}}\n')
        return i

    def flush_tables(self) -> None:
        self.f.writelines(self.pending)
        self.pending.clear()

    def close(self, summary: dict, header_counts: dict | None = None) -> None:
        """Ends the file: header_counts are added to the header."""
        self.f.write(json.dumps(dict(record='summary', **summary)) + '\n')
        self.f.close()
        fd, whole = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + '.')
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(zstandard.ZstdCompressor(level=3).compress((json.dumps(dict(self.header, **(header_counts or {}))) + '\n').encode()))
                with open(self.tmp, 'rb') as body:
                    shutil.copyfileobj(body, out)
            os.replace(whole, self.path)
        except BaseException:
            if os.path.exists(whole):
                os.unlink(whole)
            raise
        os.unlink(self.tmp)

    def abort(self) -> None:
        try:
            self.f.close()
        finally:
            if os.path.exists(self.tmp):
                os.unlink(self.tmp)


# ---------------------------------------------------------------- one sample

@dataclass
class Env:
    live: Any
    wr: Any
    tr: Any
    run: Any
    uses: tuple[str, ...]
    option_names: tuple[str, ...]
    point_names: tuple[str, ...]
    plain: list[int]  # the columns of the option names without `table:`
    table: list[int]  # the columns of the `table:` names
    sink: Sink
    totals: Totals
    plan: str
    seconds: float
    max_states: int
    vector_names: tuple[str, ...] | None = None  # with --vectors, the columns of the vector
    vector_point_cols: list[int] = field(default_factory=list)
    vector_id_cols: list[int] = field(default_factory=list)
    draws: dict[frozenset[str | None], list[Draw]] | None = None  # with --draws: the task's draws that do not solve, by state
    draw_counts: Counter[str] = field(default_factory=Counter)
    graph: Graph | None = None  # the task's union graph (the target rule's)
    union: Mapping[str, dict] = field(default_factory=dict)  # the skeleton's query records by QueryHash
    templates: stand_in.Templates | None = None  # the reads of the union's query records (the target rule's)
    union_tables: dict[tuple[str, str], Any] = field(default_factory=dict)  # (QueryHash, Name) of a union query -> its table as the engine computes it from the query's own program
    site_maps: dict[tuple[tuple[str, str], tuple[str, str]], stand_in.SiteMap | stand_in.NoStandIn] = field(default_factory=dict)  # (a union query's table, a table that stands for it) -> how a read moves between them


def point_of_vector(env: Env, kind: str, rec: dict) -> Point | None:
    """The point with its vector as vp and vo, or None (counted) where the vector does not rebuild or a point-scope column differs across the ids."""
    vec: np.ndarray = rec['vectors']
    n = len(rec['ids'])
    if env.vector_names is None or tuple(rec["names"]) != env.vector_names or vec.shape != (n, len(env.vector_names)) or vec.dtype != np.float32:
        env.totals.counts['vector shape or names differ from the header'] += 1
        return None
    pc, ic = env.vector_point_cols, env.vector_id_cols
    if n and not same_bits(vec[:, pc], np.broadcast_to(vec[:1, pc], (n, len(pc)))):
        env.totals.counts['point-scope columns that differ across ids'] += 1
        return None
    vp_text, vo_text = f32_text(vec[0, pc]), f32_text(vec[:, ic])
    full = np.empty(vec.shape, np.float32)
    full[:, pc] = f32_back(vp_text, (1, len(pc)))
    full[:, ic] = f32_back(vo_text, (n, len(ic)))
    ids_text = json.dumps(rec['ids'].tolist(), separators=(',', ':'))
    if not same_bits(full, vec) or json.loads(ids_text) != rec['ids'].tolist():
        env.totals.counts['rebuild failures'] += 1
        return None
    return Point(kind, tuple(int(t) for t in rec['tokens']), rec['phase'], rec['ids'].tolist(), ids_text, '', [], '', rec['positive_ids'], int(rec['live']), vp=vp_text, vo=vo_text)


def point_of_record(env: Env, kind: str, rec: dict) -> Point | None:
    if env.vector_names is not None:
        return point_of_vector(env, kind, rec)
    opt: np.ndarray = rec['option']
    n = len(rec['ids'])
    plain, table = opt[:, env.plain], np.ascontiguousarray(opt[:, env.table])
    option_text = matrix_text(plain)
    table_ix = [env.sink.table_index(table[i]) for i in range(n)]
    ids_text = json.dumps(rec['ids'].tolist(), separators=(',', ':'))
    point_text = row_text(rec['point'])
    # the rebuild check, on the text as written
    back_plain = np.array(json.loads(option_text), np.float32).reshape(n, len(env.plain))
    full = np.empty(opt.shape, np.float32)
    full[:, env.plain] = back_plain
    if env.table:
        full[:, env.table] = np.stack([env.sink.parsed[i] for i in table_ix])
    if not same_bits(full, opt) or not same_bits(np.array(json.loads(point_text), np.float32), rec['point']) or json.loads(ids_text) != rec['ids'].tolist():
        env.totals.counts['rebuild failures'] += 1
    return Point(kind, tuple(int(t) for t in rec['tokens']), rec['phase'], rec['ids'].tolist(), ids_text, option_text, table_ix, point_text, rec['positive_ids'], int(rec['live']))


def query_stream(env: Env, scope: tuple[str, ...], text: str) -> tuple[str, list[int]]:
    """(kind, the model tokens of the query's line, the kind token first) of a query text over the scope's labels."""
    live = env.live
    ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), env.run.session.settings).decode_stream()
    stream = [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
    kind = env.run.V.name(stream[0])
    if kind not in live.KIND_TOK:
        raise Reject(f'the kind {kind} is not written')
    return kind, stream


def drawn_streams(env: Env, sample: dict, scope: tuple[str, ...], label: dict[str, str], kinds: set[str]) -> dict[str, Counter[tuple[int, ...]]]:
    """The streams of the sample's matched draws, by kind, each with its count of draws. A draw that cannot be read, or whose kind has no target, is counted and left out."""
    got: dict[str, Counter[tuple[int, ...]]] = {}
    for d in (env.draws or {}).get(frozenset(sample['state']['queries']), ()):
        try:
            kind, stream = query_stream(env, scope, drawn_text(d, label, f'&r{len(scope)}'))
        except Reject as e:
            env.draw_counts['unread: ' + str(e)] += d.count
            continue
        except Exception as e:
            env.draw_counts['unread: decode: ' + type(e).__name__] += d.count
            env.totals.examples.setdefault('draw decode: ' + type(e).__name__, f'{d.text[:160]} {sample["id"]}: {why(e)}')
            continue
        if kind not in kinds:
            env.draw_counts['a kind with no target'] += d.count
            continue
        got.setdefault(kind, Counter())[tuple(stream)] += d.count
    return got


def positive_set(p: Point) -> set[int]:
    return {int(t) for t in p.positive_ids}


def first_drawn_ordered(points: dict[tuple[int, ...], Point], path: list[int]) -> tuple[Point | None, int, str]:
    """(the first point of the path whose positives lack the path's next token, that token, '') or (None, 0, why). A point's key is its token prefix, the kind token included."""
    rows = {p.tokens[1:]: p for p in points.values()}
    for k, t in enumerate(path):
        p = rows.get(tuple(path[:k]))
        if p is not None and t not in positive_set(p):
            return p, t, ''
    return None, 0, 'every token at a point is a positive'


def first_drawn_unordered(points: dict[tuple[int, ...], Point], graph: dict, state_point: dict[Any, tuple[int, ...]], path: list[int]) -> tuple[Point | None, int, str]:
    """As first_drawn_ordered, along the states of the unordered search from its first state, each token taking the edge of that token."""
    if not graph:
        return None, 0, 'the search has no state'
    key = next(iter(graph))
    for t in path:
        tk = state_point.get(key)
        p = points.get(tk) if tk is not None else None
        if p is not None and t not in positive_set(p):
            return p, t, ''
        edges = dict(graph[key]['edges']) if key in graph else {}
        if t not in edges:
            return None, 0, 'a positive of a state with no point' if p is None else 'the step of a positive failed'
        key = edges[t]
    return None, 0, 'every token at a point is a positive'


def add_drawn(env: Env, kind: str, scope: tuple[str, ...], points: dict[tuple[int, ...], Point], streams: Counter[tuple[int, ...]], graph: dict | None,
              state_point: dict[Any, tuple[int, ...]]) -> None:
    """Adds each drawn stream's count to the drawn count of its drawn id, at the first point of its path under the plan where the id is no positive."""
    for stream, count in streams.items():
        s = list(stream)
        if s and s[0] == env.live.KIND_TOK[kind]:
            s = s[1:]
        if env.plan == 'ordered':
            dec0, _ = env.run.scope(scope)
            s, order, _ = env.tr.order.canonical_stream(env.tr.order_env(env.run), dec0, kind, s, env.tr.ORDER_SECONDS)  # the targets' time (train_rows.points_of_targets)
            if order != 'canonical':
                env.draw_counts['walked as written: no canonical order'] += count
            p, t, no = first_drawn_ordered(points, s)
        else:
            p, t, no = first_drawn_unordered(points, graph or {}, state_point, s)
        if p is None:
            env.draw_counts['no drawn id: ' + no] += count
        elif t not in p.ids:
            env.draw_counts['not admitted'] += count
        else:
            p.drawn[t] += count
            env.draw_counts['drawn'] += count


def union_table(env: Env, queries: Mapping[str, dict], q: str, name: str) -> Any:
    """The table (QueryHash q, Name) as the engine computes it from the query's own program (a scope of its own), as a table_export.ExportTable."""
    key = (q, name)
    if key not in env.union_tables:
        try:
            _, pg = env.run.scope(tuple(queries[q]['program']))
        except (env.live.Drop, env.live.arclog.Refusal) as e:
            raise stand_in.NoStandIn('the engine refused the program of a replaced query') from e
        tabs = [t for t in env.wr.export_tables(pg.closed[-1]) if t.name == name]
        if len(tabs) != 1:
            raise stand_in.NoStandIn('the engine gives a replaced query not one table of that Name')
        env.union_tables[key] = tabs[0]
    return env.union_tables[key]


def site_map(env: Env, queries: Mapping[str, dict], old: tuple[str, str], new: tuple[str, str], scope_tabs: Mapping[tuple[str, str], Any]) -> stand_in.SiteMap:
    """How a read of the table `old` (a union query's) is written on the columns of the member's table `new`. Made once for each pair in a task: the tables' content does not depend on the scope."""
    got = env.site_maps.get((old, new))
    if got is None:
        try:
            if new not in scope_tabs:
                raise stand_in.NoStandIn('the engine gives a member no table')
            got = stand_in.column_map_of(union_table(env, queries, *old), queries[old[0]]['kind'], queries[old[0]]['program'][-1], old[1],
                                         scope_tabs[new], queries[new[0]]['kind'], queries[new[0]]['program'][-1], new[1])
        except stand_in.NoStandIn as e:
            got = e
        env.site_maps[(old, new)] = got
    if isinstance(got, stand_in.NoStandIn):
        raise stand_in.NoStandIn(str(got))
    return got


def stand_in_text(env: Env, queries: Mapping[str, dict], s: stand_in.StandIn, label: Mapping[str, str], own: str, scope_tabs: Mapping[tuple[str, str], Any]) -> str:
    """The text of the target query `s` over the scope's labels."""
    swaps = {}
    for old, new in s.swaps:
        head = label[new[0]] + ('.' + new[1] if queries[new[0]]['kind'] == 'INIT' and new[1] else '')
        swaps[old] = stand_in.Swap(head, site_map(env, queries, old, new, scope_tabs))
    return stand_in.written_over(queries[s.template], label, own, swaps)


def process_sample(env: Env, sample: dict, queries: Mapping[str, dict]) -> tuple[int, int]:
    """Writes the sample's points; returns (the count of its target queries by the rule, the count of those that are written)."""
    tot, wr, live = env.totals, env.wr, env.live
    texts, label = scope_of(sample['state']['queries'], queries)
    scope = tuple(texts)
    try:
        _, pg = env.run.scope(scope)
    except (live.Drop, live.arclog.Refusal) as e:  # a refusal of the engine; any other exception is a failure and ends the sample as an error
        raise Reject('the engine refused the scope: ' + why(e)) from e
    assert env.graph is not None and env.templates is not None
    state = frozenset(sample['state']['queries'])
    maps = scope_maps(wr, pg)
    tot.counts[RULE_COUNTS[0]] += sum(all(k[0] != h for k in maps) for h in state)
    verdict = target_rule(state, maps, env.graph, env.union, env.templates)
    tot.counts[RULE_COUNTS[1]] += len(verdict.stand_ins)
    for reason, n in verdict.lost.items():
        tot.fail('target', 'stand-in: ' + reason, sample['id'], n)
    # the state's tables as the engine exports them with their rows, for the columns of the members that stand in (made when the first stand-in needs them)
    scope_tabs: dict[tuple[str, str], Any] = {}
    if verdict.stand_ins:
        got = wr.state_tables(env.run, pg)
        if got is None:
            raise RuntimeError('the scope did not keep its queries\' tables (writer.keep_state_tables)')
        scope_tabs = {(next(a.query for a in t.at if a.query), t.name): t for t in got[0] if any(a.query for a in t.at)}
    # the targets: text over the scope's labels and the token stream
    targets: dict[str, list[tuple[str, list[int]]]] = {}
    written: set[str] = set()
    own = f'&r{len(scope)}'

    def take(example: str, make: Any) -> None:
        tot.counts['targets'] += 1
        try:
            text, want = make()
            kind, stream = query_stream(env, scope, text)
            if kind != want:
                raise Reject('the stream\'s kind differs from the query\'s kind')
        except Reject as e:
            tot.fail('target', str(e), example)
            return
        except stand_in.NoStandIn as e:
            tot.fail('target', 'stand-in: ' + str(e), example)
            return
        except Exception as e:
            tot.fail('target', 'decode: ' + why(e), example)
            return
        if text in written:
            tot.counts['targets equal to another target'] += 1
            return
        written.add(text)
        targets.setdefault(kind, []).append((text, stream))

    for h in verdict.targets:
        take(f'{h} {sample["id"]}', lambda h=h: (rewrite(queries[h], label, own), queries[h]['kind']))
    for s in verdict.stand_ins:
        take(f'{s.graph_query} {sample["id"]}', lambda s=s: (stand_in_text(env, queries, s, label, own, scope_tabs), queries[s.template]['kind']))
    drawn = drawn_streams(env, sample, scope, label, set(targets)) if env.draws is not None else {}
    for kind, group in targets.items():
        points: dict[tuple[int, ...], Point] = {}
        refused: set[tuple[int, ...]] = set()  # token prefixes whose point failed its checks
        failed: set[int] = set()
        stats: Counter[str] = Counter()
        graph: dict | None = {} if env.plan == 'unordered' and kind in drawn else None  # the unordered search's states, for the draws' paths
        state_point: dict[Any, tuple[int, ...]] = {}  # a state of the graph -> the key of its point
        t0 = time.perf_counter()
        if graph is not None:
            # points_of_targets under `unordered` is points_of_unordered; this call also fills the graph, whose last state is the state of the record just yielded
            it = env.tr.points_of_unordered(env.run, scope, kind, [stream for _, stream in group], env.uses, max_states=env.max_states, seconds=env.seconds, stats=stats, graph=graph,
                                            vectors=env.vector_names is not None)
        else:
            it = env.tr.points_of_targets(env.run, scope, kind, [stream for _, stream in group], env.uses, plan=env.plan, seconds=env.seconds, max_states=env.max_states, stats=stats,
                                          vectors=env.vector_names is not None)
        while True:
            try:
                got = next(it, None)
            except Exception as e:
                tot.seconds['extractor'] += time.perf_counter() - t0
                tot.fail('sample', 'points_of_targets: ' + why(e), f'{sample["id"]} {kind}')
                break
            tot.seconds['extractor'] += time.perf_counter() - t0
            if got is None:
                break
            ti, rec = got
            t1 = time.perf_counter()
            if 'error' in rec:
                if ti not in failed:
                    failed.add(ti)
                    tot.fail('target', 'points_of_targets: ' + why(rec['error']), f'{group[ti][0][:160]} {sample["id"]}')
            elif rec['left_mask']:
                tot.counts['left the mask'] += 1
            else:
                tot.counts['points before dedupe'] += 1
                key = tuple(int(t) for t in rec['tokens'])
                p = points.get(key)
                if key in refused:
                    continue
                if p is None:
                    p = point_of_record(env, kind, rec)
                    if p is None:
                        refused.add(key)
                        continue
                    points[key] = p
                elif not np.array_equal(p.positive_ids, rec['positive_ids']) or p.live != rec['live']:
                    tot.counts['points whose records disagree on the positives'] += 1
                if graph:
                    state_point.setdefault(next(reversed(graph)), key)
                if rec['next_id'] is not None:
                    p.next_ids.add(int(rec['next_id']))
                if rec['order'] == 'gold':
                    tot.examples.setdefault('order_why: ' + rec['order_why'].split(':')[0], f'{group[ti][0][:160]} {sample["id"]}: {rec["order_why"][:160]}')
            tot.seconds['assembly'] += time.perf_counter() - t1
            t0 = time.perf_counter()
        tot.search.update(stats)
        tot.largest = max(tot.largest, stats['unordered:states'])
        if stats['unordered:states'] == tot.largest and env.plan == 'unordered':
            tot.examples['largest search'] = f'{stats["unordered:states"]} states, {len(group)} targets of kind {kind}, sample {sample["id"]}'
        t1 = time.perf_counter()
        if kind in drawn:
            add_drawn(env, kind, scope, points, drawn[kind], graph, state_point)
        env.sink.flush_tables()
        for p in points.values():
            where = {t: i for i, t in enumerate(p.ids)}
            drawn_field = '' if env.draws is None else ',"drawn":' + json.dumps(sorted([where[t], c] for t, c in p.drawn.items()), separators=(',', ':'))
            pos = sorted(where[int(t)] for t in p.positive_ids if int(t) in where)
            if len(pos) != len(p.positive_ids):
                tot.counts['points with a positive that is not in ids'] += 1
            if any(nx not in set(int(t) for t in p.positive_ids) for nx in p.next_ids):
                tot.counts['points whose next token is no positive'] += 1
            tot.counts['points'] += 1
            tot.counts['ids'] += len(p.ids)
            tot.counts['positives'] += len(pos)
            tot.counts['live'] += p.live
            tot.counts['points with no positive'] += not pos
            tot.counts['points with one positive'] += len(pos) == 1
            if env.vector_names is not None:
                env.sink.f.write(f'{{"record":"point","sample":"{sample["id"]}","kind":"{kind}","length":{len(p.tokens)},"prefix":"{prefix_hash(p.tokens)}","tokens":{json.dumps([int(t) for t in p.tokens], separators=(",", ":"))},"ids":{p.ids_text},"vp":"{p.vp}","vo":"{p.vo}",'
                                 f'"positive":{json.dumps(pos, separators=(",", ":"))},"live":{p.live}{drawn_field}}}\n')
                continue
            env.sink.f.write(f'{{"record":"point","sample":"{sample["id"]}","kind":"{kind}","length":{len(p.tokens)},"prefix":"{prefix_hash(p.tokens)}","tokens":{json.dumps([int(t) for t in p.tokens], separators=(",", ":"))},"ids":{p.ids_text},"option":{p.option_text},'
                             f'"table":{json.dumps(p.table, separators=(",", ":"))},"point":{p.point_text},"positive":{json.dumps(pos, separators=(",", ":"))},"live":{p.live}{drawn_field}}}\n')
        tot.seconds['labels and writing'] += time.perf_counter() - t1
    return len(verdict.targets) + len(verdict.stand_ins), len(written)


# ---------------------------------------------------------------- one task

def chosen(samples: list[dict], k: int, seed: int) -> list[dict]:
    if k <= 0 or len(samples) <= k:
        return samples
    keep = sorted(samples, key=lambda s: hashlib.sha256(f'{seed}:{s["id"]}'.encode()).hexdigest())[:k]
    return sorted(keep, key=samples.index)


def header_of(path: Path) -> dict | None:
    try:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True), encoding='utf-8') as f:
            return json.loads(f.readline())
    except (OSError, EOFError, ValueError, zstandard.ZstdError):
        return None


def run_task(env_base: dict, set_name: str, task: str, args: argparse.Namespace, shas: dict[str, str], smp: Any, out: Path, draw_paths: list[Path] | None = None) -> Totals | None:
    """Writes the task's file, or returns None where the file is current. draw_paths: with --draws, the task's draw files."""
    live, wr, tr = env_base['live'], env_base['wr'], env_base['tr']
    skeleton = skeleton_folder(args) / f'{task}.jsonl'
    records = [json.loads(x) for x in skeleton.read_text().splitlines()]
    head = records[0]
    queries = {r['hash']: r for r in records if r['record'] == 'query'}
    skeleton_samples = [r for r in records if r['record'] == 'sample']
    draws = read_draws(draw_paths) if draw_paths else []
    drawn_states = {dr.state for dr in draws}
    kept = {s['id'] for s in chosen(skeleton_samples, args.samples_per_task, args.seed)}
    samples = [s for s in skeleton_samples if s['id'] in kept or frozenset(s['state']['queries']) in drawn_states]  # the K chosen, and each sample that a last step matches
    added, off_queries, refused = plan_added(task, draws, queries, {frozenset(s['state']['queries']) for s in samples}) if draw_paths is not None else ([], {}, {})
    samples += added
    added_ids = {s['id'] for s in added}
    split = head['split']
    folder = out / set_name / ('points_held-out' if is_held_out(split) else 'points') / args.plan
    path = folder / f'{task}.jsonl.zst'
    header = dict(record='header', schema=SCHEMA, task=task, set=set_name, plan=args.plan, split=split, skeleton_sha=file_sha(skeleton), extractor_sha=shas['extractor'], writer_sha=shas['writer'],
                  wheel=shas['wheel'], code=shas['code'], samples_per_task=args.samples_per_task, seed=args.seed, seconds=args.seconds, max_states=args.max_states,
                  uses=list(env_base['uses']), point_names=list(env_base['point_names']), option_names=[env_base['option_names'][i] for i in env_base['plain']],
                  table_names=[env_base['option_names'][i] for i in env_base['table']],
                  draws=None if draw_paths is None else [[str(q), Z.sha256(q)] for q in draw_paths])
    if args.vectors:
        # the vector's columns follow from the wheel and the writer, which the header names, so they are added after the skip check
        header = dict(header, vectors=True, point_names=[], option_names=[], table_names=[])
        header.pop('uses')
    old = header_of(path)
    if old and bool(old.get('vectors')) == args.vectors and {k: old.get(k) for k in header} == header:
        return None
    graph = task_graph(env_base['graph_idx'], task, head)
    folder.mkdir(parents=True, exist_ok=True)
    run = new_run(env_base, smp, task)
    vector_names: tuple[str, ...] | None = None
    point_cols: list[int] = []
    id_cols: list[int] = []
    if args.vectors:
        vector_names = tuple(wr.vector_names(run))
        point_cols = vector_point_cols(wr, vector_names)
        in_point = set(point_cols)
        id_cols = [i for i in range(len(vector_names)) if i not in in_point]
        header = dict(header, uses=list(vector_names), vector_names=list(vector_names), vector_point_cols=point_cols)
    sink = Sink(path, header)
    tot = Totals()
    uses = () if args.vectors else env_base['uses']  # the vector holds the features; the extractor need not make the prefix features too
    env = Env(live, wr, tr, run, uses, env_base['option_names'], env_base['point_names'], env_base['plain'], env_base['table'], sink, tot, args.plan, args.seconds, args.max_states,
              vector_names, point_cols, id_cols, graph=graph, union=queries, templates=stand_in.read_index(queries, graph.reads))
    steps_of: Counter[frozenset[str | None]] = Counter()  # an added state -> the last steps that reach it, repeats counted
    solving_of: Counter[frozenset[str | None]] = Counter()  # the same, of those that solve every train ARC example
    if draw_paths is not None:
        added_states = {frozenset(s['state']['queries']) for s in added}
        env.draws = {}
        for dr in draws:
            if dr.state in refused:
                env.draw_counts['not added: ' + refused[dr.state]] += dr.count
                continue
            if dr.state in added_states:
                steps_of[dr.state] += dr.count
                solving_of[dr.state] += dr.count if dr.solves else 0
            else:
                env.draw_counts['matched'] += dr.count
            if dr.solves:
                if dr.state not in added_states:
                    env.draw_counts['solves'] += dr.count
                continue
            env.draws.setdefault(dr.state, []).append(dr)
    try:
        for sample in samples:
            tot.counts['samples'] += 1
            before = tot.counts['points']
            state = frozenset(sample['state']['queries'])
            try:
                found, kept = process_sample(env, sample, ChainMap(off_queries[sample['id']], queries) if sample['id'] in added_ids else queries)
            except Exception as e:
                tot.fail('sample', str(e) if isinstance(e, Reject) else 'error: ' + why(e), f'{sample["id"]} {task}')
                if sample['id'] in added_ids:
                    env.draw_counts['not added: ' + reason_of(e)] += steps_of[state]
                elif env.draws:
                    env.draw_counts['the sample failed'] += sum(dr.count for dr in env.draws.get(state, ()))
                continue
            if not found:
                tot.counts['samples with no target'] += 1
                if sample['id'] in added_ids:
                    env.draw_counts['not added: ' + NO_TARGET] += steps_of[state]
                    continue
            elif not kept:
                tot.counts['samples whose target queries could not be written'] += 1
                if sample['id'] in added_ids:
                    env.draw_counts['not added: ' + NO_WRITTEN] += steps_of[state]
                    continue
            tot.counts['samples written'] += 1
            tot.counts['samples with a point'] += tot.counts['points'] > before
            if sample['id'] in added_ids:
                tot.counts['samples added'] += 1
                env.draw_counts['added states'] += 1
                env.draw_counts['added'] += steps_of[state]
                env.draw_counts['solves'] += solving_of[state]
        sink.close(dict(samples=tot.counts['samples'], samples_added=tot.counts['samples added'], points=tot.counts['points'],
                        checks=dict(points_with_no_positive=tot.counts['points with no positive'], left_the_mask=tot.counts['left the mask'],
                                    positive_not_in_ids=tot.counts['points with a positive that is not in ids'], next_token_no_positive=tot.counts['points whose next token is no positive']),
                        failures={k: dict(v) for k, v in tot.failures.items()}, rebuild_failures=tot.counts['rebuild failures'], **({'vector_failures': {k: tot.counts[k] for k in VECTOR_COUNTS}} if args.vectors else {}), search=dict(sorted(tot.search.items()))),
                   None if draw_paths is None else dict(draw_counts=dict(sorted(env.draw_counts.items()))))
        tot.counts.update({'draws ' + k: v for k, v in env.draw_counts.items()})
    except BaseException:
        sink.abort()
        raise
    return tot


def draw_files_by_task(paths: list[Path]) -> dict[str, list[Path]] | None:
    """The draw files of each task, or None (with the reason on stderr) where there is none or a file is of a task that is not train."""
    if not paths:
        print('error: --draws gives no draw file', file=sys.stderr)
        return None
    by_task: dict[str, list[Path]] = {}
    for path in paths:
        task = draw_file_task(path)
        if task is None:
            continue
        sp = split_of(task)
        if sp != 'train':
            print(f'error: {path} holds draws of task {task}, which is {sp}; only the draws of train tasks are read', file=sys.stderr)
            return None
        by_task.setdefault(task, []).append(path.resolve())
    return by_task


def skeleton_folder(args: argparse.Namespace) -> Path:
    return args.skeleton if args.skeleton is not None else OUTD / args.set / 'skeleton'


def load_engine(plan: str) -> tuple[dict, dict[str, str], Any]:
    """(the engine's modules and the writer's feature names, the shas of the extractor, writer, this file and the wheel, the Sampler) for the writer plan `plan`. The extractor and the wheel are found on sys.path."""
    os.environ.setdefault('WRITER_PLAN', plan)  # --plan is the writer plan of the process: a WRITER_PLAN or a WRITER_TREE of the other plan raises
    importlib.import_module('lookahead_legal').check_plan(plan)
    tr = importlib.import_module('train_rows')
    wr = importlib.import_module('writer')
    live = importlib.import_module('live')
    live_try = importlib.import_module('live_try')
    live_try.P.REPO = os.environ.get('ARC_ROOT', str(REPO))
    sampler_dir = module_file(tr).parent
    smp = live.Sampler(str(sampler_dir / '../../../models-current'), steers=())
    uses = tuple(wr.feature_names())
    option_names, point_names = tr.split_uses(uses)
    plain = [i for i, x in enumerate(option_names) if not x.startswith('table:')]
    table = [i for i, x in enumerate(option_names) if x.startswith('table:')]
    shas = dict(extractor=file_sha(module_file(tr)), writer=file_sha(module_file(wr)), code=file_sha(Path(__file__)), wheel=module_file(live.arclog).parent.parent.name)
    env_base = dict(live=live, live_try=live_try, wr=wr, tr=tr, uses=uses, option_names=option_names, point_names=point_names, plain=plain, table=table)
    return env_base, shas, smp


def new_run(env_base: dict, smp: Any, task: str) -> Any:
    """A Run of the task that keeps the tables of its scopes' queries (the target rule reads them)."""
    live, wr = env_base['live'], env_base['wr']
    sess, d, _ = env_base['live_try'].session_of(task)
    run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
    wr.keep_state_tables(run)
    return run


class GraphMismatch(Exception):
    """The task's lines of the graph files are not those that the skeleton was made from."""


def task_graph(idx: Mapping[str, Any], task: str, head: dict) -> Graph:
    """The Graph of the task, from its lines of the graph files (idx: LineIndex of `prods` and of `tables`), after the check that their shas are those that the skeleton's header records."""
    lines = {k: i.lines(task) for k, i in idx.items()}
    for k, key in (('prods', 'queries'), ('tables', 'tables')):
        h = hashlib.sha256()
        for line in lines[k]:
            h.update(line)
        if h.hexdigest() != head['inputs'][key]:
            raise GraphMismatch(f'{task}: its lines of the graph {k} file are not those that the skeleton was made from ({len(lines[k])} lines)')
    return graph_of(lines['prods'], lines['tables'])


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set', choices=('train', 'dev', 'held-out'))
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks with crc32(task) %% N == k')
    ap.add_argument('--tasks', help='comma-separated task ids')
    ap.add_argument('--samples-per-task', type=int, default=0, help='at most K samples of a task, chosen by a seeded hash of the sample id (0: all)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--seconds', type=float, default=10.0, help='the extractor\'s time for the order or the search of one target')
    ap.add_argument('--max-states', type=int, default=20000, help='the most states of one unordered search')
    ap.add_argument('--plan', choices=('ordered', 'unordered'), required=True, help='the writer plan: ordered (a fixed order of atoms) or unordered (set labels)')
    ap.add_argument('--vectors', action='store_true', help='write the writer\'s full writing-point vector of each id in place of the prefix features')
    ap.add_argument('--draws', help='a glob of draw record files, or a folder of draws.jsonl files: the drawn counts of train tasks')
    ap.add_argument('--skeleton', type=Path, help='the folder of the skeleton files (default OUTD/SET/skeleton)')
    ap.add_argument('--graphs', type=Path, help='the folder of the union graph files that the skeleton was made from (default $ARC_SAMPLE_GRAPHS, else split.GRAPHS)')
    ap.add_argument('--out', type=Path, default=OUTD)
    args = ap.parse_args()
    k, n = map(int, args.shard.split('/'))
    env_base, shas, smp = load_engine(args.plan)
    graph_dir = args.graphs or (Path(os.environ['ARC_SAMPLE_GRAPHS']) if os.environ.get('ARC_SAMPLE_GRAPHS') else GRAPHS)
    env_base['graph_idx'] = {'prods': LineIndex(graph_dir / f'graph-prods-{args.set}.jsonl'), 'tables': LineIndex(graph_dir / f'graph-tables-{args.set}.jsonl')}
    wanted = set(args.tasks.split(',')) if args.tasks else None
    tasks = sorted(p.stem for p in skeleton_folder(args).glob('*.jsonl') if zlib.crc32(p.stem.encode()) % n == k and (wanted is None or p.stem in wanted))
    draws_of: dict[str, list[Path]] | None = None
    if args.draws:
        draws_of = draw_files_by_task(draw_files(args.draws))
        if draws_of is None:
            return 2
    t0 = time.time()
    total, done, skipped = Totals(), 0, 0
    for i, task in enumerate(tasks, 1):
        t1 = time.time()
        try:
            got = run_task(env_base, args.set, task, args, shas, smp, args.out, None if draws_of is None else draws_of.get(task, []))
        except GraphMismatch as e:
            print(f'error: {e}', file=sys.stderr, flush=True)
            total.fail('task', 'its lines of the graph files are not those that the skeleton was made from', task)
            continue
        if got is None:
            skipped += 1
            continue
        done += 1
        total.add(got)
        el = time.time() - t0
        c = got.counts
        print(f'{args.set} {task} {i}/{len(tasks)} samples {c["samples written"]}/{c["samples"]} points {c["points"]} ids/point {c["ids"] / max(c["points"], 1):.1f} '
              f'{c["points"] / max(time.time() - t1, 1e-9):.1f} points/s ETA {el / done * (len(tasks) - i):.0f}s', flush=True)
    c = total.counts
    p = max(c['points'], 1)
    print(json.dumps(dict(
        set=args.set, shard=args.shard, written=done, current=skipped, seconds=round(time.time() - t0, 1), samples=c['samples'], samples_written=c['samples written'], samples_added=c['samples added'], targets=c['targets'],
        points_before_dedupe=c['points before dedupe'], points=c['points'], ids_per_point=round(c['ids'] / p, 2), positives_per_point=round(c['positives'] / p, 3),
        live_per_point=round(c['live'] / p, 3), points_with_one_positive=c['points with one positive'], points_with_no_positive=c['points with no positive'],
        records_disagree_on_positives=c['points whose records disagree on the positives'], positive_not_in_ids=c['points with a positive that is not in ids'],
        next_token_no_positive=c['points whose next token is no positive'], left_the_mask=c['left the mask'], rebuild_failures=c['rebuild failures'], **({'vector_failures': {k: c[k] for k in VECTOR_COUNTS}} if args.vectors else {}),
        ms_per_point=round(1000 * (time.time() - t0) / p, 3),
        extractor_ms_per_point=round(1000 * total.seconds['extractor'] / p, 3), assembly_ms_per_record=round(1000 * total.seconds['assembly'] / max(c['points before dedupe'], 1), 3),
        largest_search_states=total.largest, search=dict(sorted(total.search.items())),
        **({'draw_counts': {k2.removeprefix('draws '): v for k2, v in sorted(c.items()) if k2.startswith('draws ')}} if draws_of is not None else {}),
        target_rule={k2: c[k2] for k2 in RULE_COUNTS},
        failures={k2: dict(v) for k2, v in total.failures.items()}, examples=total.examples)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
