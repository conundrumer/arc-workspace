"""Target queries written through stand-ins (docs/sample-build/contract.md, "Sample").

A state can hold a table that stands for a graph table (its map equals the graph table's map) while the union query that computes that graph table is not a member. A graph query
that reads that graph table is a target query all the same: it is written over the state's own members, each graph table it reads replaced by the member's table that stands for it.
The extractor has a query record for a graph query only over union queries, so the text of such a target is that of a query record of the graph query with each read of a union
query that is not the chosen member replaced by a read of the member.

  read_index(union)                     the tables that each query record's text reads, and the query records of each graph query
  choices(...)                          the targets that need a replacement: (graph query, query record, replaced reads)
  pair_columns(old, new)                the pairing of the columns of two tables of equal content
  column_map_of(...)                    the sites of a read moved from the columns of one table to those of another
  written_over(record, label, own, ...) the record's text over a scope's labels, the replaced reads written on the members

How the columns are named. The engine exports for each table its column types and column labels (`ExportTable.types`, `.labels`). A RULE or a DET names its columns `:<label>`, a bare proposer
by the proposer's columns; an INIT names the fields of its key record `key.<Label>` and its other columns by the fields of the output in engine/lib/registry.sexpr (canon_text.py,
column_map.py). A read writes a site `(:<column name> ...)` on each column it uses. The columns of two tables are paired by their content, not by their names: a column of one table is
paired with a column of the other that has its type and, at each TableHash that the two tables share, the same cells in each example; where the cells of several columns are equal the
pairings are tried in order until one gives equal rows, and the choice among them is then free (`Pairing.tied`).
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
import contextlib
import functools
import itertools
import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

import canon_text
import column_map
import column_names
import table_hash as TH

type Table = tuple[str, str]  # (QueryHash, Name)
READ = re.compile(r'^&r(\d+)(?:\.(\w+))?$')  # the head of an atom that reads a table: a local label, and the INIT output or port that it names
LABEL = re.compile(r'&r(\d+)')
INNER = re.compile(r'^r\d+$')  # the second part of a RIGID_DET's read: a local label, not an output Name
KINDS = ('INIT', 'RULE', 'DET')  # the kinds of query whose tables a read can be moved between
MAX_PAIRINGS = 720  # the most pairings tried among tied columns
MAX_CHOICES = 4096  # the most choices of members for one graph query


class NoStandIn(Exception):
    """A target that cannot be written through a stand-in; the message is the reason that is counted."""


# ---------------------------------------------------------------- the rule: which targets are written through stand-ins

@dataclass(frozen=True)
class Template:
    """A query record of a graph query: the tables its text reads, and the graph table of each."""
    hash: str
    table_of: tuple[tuple[Table, str], ...]  # (table read, its graph table), sorted


@dataclass
class Templates:
    reads: dict[str, frozenset[Table]]  # a query record -> the tables its text reads
    by_graph_query: dict[str, list[Template]]  # a graph query -> its query records whose reads are, as graph tables, the graph query's reads, sorted by QueryHash


@dataclass(frozen=True)
class StandIn:
    """A target query: the graph query written from the query record `template`, with each read in `swaps` replaced by the member's table."""
    graph_query: str
    template: str
    swaps: tuple[tuple[Table, Table], ...]  # (the table the record reads, the member's table that stands for its graph table), sorted


def direct_reads(record: dict) -> list[tuple[int, str]]:
    """(index into the record's closure, Name) of each atom of the record's own text that reads a table of a query of its use closure; the atoms in order of appearance."""
    closure = record['closure']
    out: list[tuple[int, str]] = []

    def go(x: canon_text.Tree) -> None:
        if not isinstance(x, list):
            return
        if x and isinstance(x[0], str):
            m = READ.match(x[0])
            if m and int(m[1]) < len(closure):
                out.append((int(m[1]), m[2] or ''))
            for y in x[1:]:
                go(y)
        else:
            for y in x:
                go(y)
    go(canon_text.parse(record['program'][-1])[0])
    return out


def read_index(union: Mapping[str, dict], graph_reads: Mapping[str, tuple[str, ...]]) -> Templates:
    """The reads of every query record of the union, and the records that can serve as a graph query's template: those whose reads are, as graph tables (`graph_tables` of the producing record), the
    graph tables that the graph query reads. A read of a port with no table of its own has no graph table, so a record with one is no template."""
    reads: dict[str, frozenset[Table]] = {}
    by_g: dict[str, list[Template]] = {}
    for h, r in sorted(union.items()):
        rs = sorted({(r['closure'][i], n) for i, n in direct_reads(r)})
        reads[h] = frozenset(rs)
        graph_of_read = [union[q]['graph_tables'].get(n) if q in union else None for q, n in rs]
        if None in graph_of_read:
            continue
        for g in r['graph_queries']:
            if g in graph_reads and set(graph_of_read) == set(graph_reads[g]):
                by_g.setdefault(g, []).append(Template(h, tuple(zip(rs, graph_of_read))))
    return Templates(reads, by_g)


def choices(candidates: list[str], graph_reads: Mapping[str, tuple[str, ...]], standing: Mapping[str, list[Table]], templates: Templates, covered: set[tuple[str, frozenset[Table]]]) -> tuple[list[StandIn], Counter[str]]:
    """The targets that need a replacement. `candidates` are the graph queries that apply and make progress at the state; `standing[t]` the state's tables that stand for the graph table t. A graph
    query gives one target for each choice of one standing table at each graph table it reads (the contract). A choice that a union query over those members already gives (`covered`: (graph query,
    the tables the union query reads)) is that union query's. Returns (the targets, a count of the choices that cannot be written, by reason)."""
    out: list[StandIn] = []
    lost: Counter[str] = Counter()
    for g in candidates:
        tabs = sorted(graph_reads[g])
        options = [standing[t] for t in tabs]
        size = math.prod(len(o) for o in options)
        if size > MAX_CHOICES:
            lost[f'more than {MAX_CHOICES} choices of members'] += 1
            continue
        temps = templates.by_graph_query.get(g, [])
        for pick in itertools.product(*options):
            if (g, frozenset(pick)) in covered:
                continue
            if not temps:
                lost['no query record of the graph query reads its graph tables'] += 1
                continue
            chosen = dict(zip(tabs, pick))
            best = min(temps, key=lambda t: (sum(chosen[gt] != rd for rd, gt in t.table_of), t.hash))
            swaps = tuple(sorted((rd, chosen[gt]) for rd, gt in best.table_of if chosen[gt] != rd))
            if swaps:  # no swap: the record is a query over these members, which the union rule decides
                out.append(StandIn(g, best.hash, swaps))
    return out, lost


# ---------------------------------------------------------------- the columns of two tables of equal content

@dataclass
class Pairing:
    to_new: list[int]  # to_new[i]: the column of the new table that the old table's column i is paired with
    tied: bool  # whether columns of equal content gave a choice


def _sorted_rows(m: np.ndarray) -> np.ndarray:
    return m if m.shape[0] < 2 or m.shape[1] == 0 else m[np.lexsort(m.T[::-1])]


def _by_hash(tab: Any) -> dict[str, list[tuple[int, int, np.ndarray]]]:
    """{TableHash: the entries of one table at an assignment with that TableHash as (example kind, example index, rows)}. Raises NoStandIn where a table has no TableHash at an assignment or an entry has no rows."""
    out: dict[str, list[tuple[int, int, np.ndarray]]] = {}
    for at in tab.at:
        if at.hash is None:
            raise NoStandIn('a table has no TableHash at an assignment')
        if at.hash in out:
            continue
        ents = []
        for e in at.entries:
            if not e.complete or e.rows is None:
                raise NoStandIn('the engine gives no rows for an entry of a table')
            ents.append((e.kind, e.index, e.rows))
        out[at.hash] = ents
    return out


def pair_columns(old: Any, new: Any) -> Pairing:
    """The pairing of the columns of two tables (`table_export.ExportTable`) that have equal content: at each TableHash that both have, the entries of the old table, with the columns
    put in the places of the new table's, are the entries of the new table. Raises NoStandIn where the tables' TableHashes differ, or no pairing gives equal rows."""
    types = list(old.types)
    if sorted(types) != sorted(new.types):
        raise NoStandIn('the two tables differ in column types')
    if not types:
        return Pairing([], False)
    a, b = _by_hash(old), _by_hash(new)
    if set(a) != set(b):
        raise NoStandIn('the engine gives the two tables different TableHashes')
    so, sn = TH.spans(types), TH.spans(list(new.types))
    hashes = sorted(a)

    def signature(by: dict, span: tuple[int, int]) -> tuple:
        return tuple((h, tuple(sorted((k, i, _sorted_rows(rows[:, span[0]:span[1]]).tobytes()) for k, i, rows in by[h]))) for h in hashes)
    sig_old = [(t, signature(a, s)) for t, s in zip(types, so)]
    sig_new = [(t, signature(b, s)) for t, s in zip(new.types, sn)]
    if Counter(sig_old) != Counter(sig_new):
        raise NoStandIn('a column of one table has no column of the other with its content')
    groups: dict[tuple, tuple[list[int], list[int]]] = {}
    for i, s in enumerate(sig_old):
        groups.setdefault(s, ([], []))[0].append(i)
    for j, s in enumerate(sig_new):
        groups[s][1].append(j)
    tied = [g for g in groups.values() if len(g[0]) > 1]
    if math.prod(math.factorial(len(g[0])) for g in tied) > MAX_PAIRINGS:
        raise NoStandIn(f'more than {MAX_PAIRINGS} pairings of columns of equal content')
    want = {h: sorted((k, i, _sorted_rows(rows).tobytes()) for k, i, rows in b[h]) for h in hashes}
    fixed = [g for g in groups.values() if len(g[0]) == 1]
    for perms in itertools.product(*(itertools.permutations(g[1]) for g in tied)):
        to_new = [-1] * len(types)
        for olds, news in fixed:
            to_new[olds[0]] = news[0]
        for (olds, _), news in zip(tied, perms):
            for i, j in zip(olds, news):
                to_new[i] = j
        inverse = [to_new.index(j) for j in range(len(types))]  # the old column that is in place j
        if all(sorted((k, i, _sorted_rows(np.concatenate([rows[:, so[c][0]:so[c][1]] for c in inverse], axis=1)).tobytes()) for k, i, rows in a[h]) == want[h] for h in hashes):
            return Pairing(to_new, bool(tied))
    raise NoStandIn('no pairing of the columns gives equal rows')


@dataclass(frozen=True)
class SiteMap:
    onto: tuple[tuple[str, str], ...]  # (the name of a column of the old table, the name of the paired column of the new table); `column_map.rewrite`'s `onto`
    records: frozenset[str]  # the heads of the old table's columns that are records of several columns
    tied: bool


_PORT_REGISTRY = canon_text.port_registry


@functools.cache
def _ports_without_frames() -> dict:
    return {k: (key, [f for f in fields if f != ':frames']) for k, (key, fields) in _PORT_REGISTRY().items()}


@contextlib.contextmanager
def registry_without_frames():
    """canon_text.port_registry() lists the `frames` clause of an output (engine/lib/registry.sexpr: which columns are frames) among its fields, but the engine exports no column for it, so the fields
    of a Frame, Tiling, Division or Occurrences output do not fit its columns. Within this block column_map reads the registry without that clause."""
    canon_text.port_registry = _ports_without_frames  # type: ignore[assignment]
    try:
        yield
    finally:
        canon_text.port_registry = _PORT_REGISTRY


def leaves_of(kind: str, text: str, name: str, tab: Any) -> tuple[list[column_map.Leaf | None], column_map.Leaf | None]:
    """(the leaf of each column of the table `tab`, in the engine's order; the leaf of the Example column that a read can name, or None) for the output `name` of the query of this kind
    and text. Raises NoStandIn where the labels and types do not give names to the columns."""
    if kind not in KINDS:
        raise NoStandIn(f'a table of a query of kind {kind} cannot be read through a stand-in')
    native = 'Example' in tab.types
    types_full = list(tab.types) if native else [*tab.types, 'Example']
    types, labels, example = column_names.without_example(types_full, list(tab.labels))
    tree = canon_text.parse(text)[0]
    assert isinstance(tree, list)
    if kind == 'DET' and len(tree) > 3 and isinstance(tree[2], str) and all(isinstance(x, list) and len(x) == 1 and isinstance(x[0], str) and x[0].isupper() for x in tree[3:]):
        tree = tree[:3]  # a proposer with modifiers, such as `(DET &r0 ScaleRatio (SET) (ONE))`, has the proposer's columns; column_map.leaves reads only the bare form
    with registry_without_frames():
        got = column_map.leaves(kind, tree, {}, name, types, labels, example)
    if got is None:
        what = f'INIT {tree[2]}.{name}' if kind == 'INIT' and len(tree) > 2 else f'{kind} with labels {"all named" if all(labels) else "some empty"}'
        raise NoStandIn(f'the columns of a table ({what}) have no names that a read can use')
    plain = got[:len(types)]
    ex = got[len(types)] if len(got) > len(types) else None
    out: list[column_map.Leaf | None] = []
    k = 0
    for t in tab.types:
        if t == 'Example':
            out.append(ex)
        else:
            out.append(plain[k])
            k += 1
    return out, (ex if not native else None)


def column_map_of(old: Any, old_kind: str, old_text: str, old_name: str, new: Any, new_kind: str, new_text: str, new_name: str) -> SiteMap:
    """The sites of a read of the old table written on the columns of the new table, which has the old one's content."""
    pairing = pair_columns(old, new)
    lo, ex_old = leaves_of(old_kind, old_text, old_name, old)
    ln, ex_new = leaves_of(new_kind, new_text, new_name, new)
    onto: dict[str, str] = {}
    for i, j in enumerate(pairing.to_new):
        if lo[i] is not None and ln[j] is not None:
            onto[lo[i].name] = ln[j].name  # type: ignore[union-attr]
    if ex_old is not None and ex_new is not None:
        onto[ex_old.name] = ex_new.name
    return SiteMap(tuple(sorted(onto.items())), frozenset(column_map.records_of([x for x in lo if x is not None])), pairing.tied)


# ---------------------------------------------------------------- the text

@dataclass(frozen=True)
class Swap:
    """A read to replace: the head that the new read has (a label of the scope, and `.<Name>` for an INIT's output), and how the sites move."""
    head: str
    sites: SiteMap


def written_over(record: dict, label: Mapping[str, str], own: str, swaps: Mapping[Table, Swap]) -> str:
    """The text of the query record over the scope's labels (`label`: QueryHash -> label; `own`: the label of the query itself), with each atom that reads a table in `swaps` written on the
    swap's head and sites. A read of a query that is neither in `label` nor in `swaps`, or a read that names a RIGID_DET's part, raises NoStandIn."""
    closure = record['closure']

    def put(m: re.Match[str]) -> str:
        i = int(m[1])
        if i < len(closure):
            if closure[i] not in label:
                raise NoStandIn('the query reads a query that is neither a member nor stood for')
            return label[closure[i]]
        if i == len(closure):
            return own
        return f'&r{len(label) + i - len(closure) - 1}'  # a relation that a DEMONSTRATED query declares: past every label of the scope

    def go(x: canon_text.Tree) -> canon_text.Tree:
        if isinstance(x, str):
            return LABEL.sub(put, x)
        if x and isinstance(x[0], str):
            m = READ.match(x[0])
            if m and int(m[1]) < len(closure):
                key = (closure[int(m[1])], m[2] or '')
                if m[2] and INNER.match(m[2]):
                    raise NoStandIn('the query reads a part of a RIGID_DET')
                if key in swaps:
                    done = column_map.rewrite(x, swaps[key].head, dict(swaps[key].sites.onto), set(swaps[key].sites.records))
                    if done is None:
                        raise NoStandIn('a site of the read is on a column that the member\'s table lacks')
                    return done
        return [go(y) for y in x]
    tree = go(canon_text.parse(record['program'][-1])[0])
    assert isinstance(tree, list)
    drop_repeats(tree)
    return canon_text.write(tree)


def drop_repeats(tree: list[canon_text.Tree]) -> None:
    """Drops each body atom that binds nothing and, but for its binders, is an earlier body atom: two reads of a graph query can be written on one member, and the engine refuses the repeated
    test ("the completed atom repeats an existing test")."""
    def bare(x: canon_text.Tree) -> canon_text.Tree:
        return [bare(y) for y in x] if isinstance(x, list) else x.lstrip('*') if isinstance(x, str) else x

    def binds(x: canon_text.Tree) -> bool:
        return any(binds(y) for y in x) if isinstance(x, list) else isinstance(x, str) and x.startswith('*')

    seen: list[canon_text.Tree] = []
    keep = tree[:2]
    for atom in tree[2:]:
        b = bare(atom)
        if isinstance(atom, list) and b in seen and not binds(atom):
            continue
        seen.append(b)
        keep.append(atom)
    tree[:] = keep
