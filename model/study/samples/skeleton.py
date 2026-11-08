"""Stage 2 of the sample build: the state-sequence samples over the union graph, with the target queries keyed by QueryHash and no table values or vectors.

  python3 skeleton.py SET [--shard k/N] [--tasks T,T,...] [--out DIR]

SET is ramp, 37 or training. For each task of walk-states-SET.jsonl it writes OUTD/SET/skeleton/<task>.jsonl, to a temp file and then renamed, and skips a task whose file holds the same input shas and code sha. Its lines are JSON:
- one `header`: the versions, `inputs` (sha256 of the task's lines of each input file, `split`, and `row_store`: the sha of the stage 3 row store's header fields `version`, `code`, `src`, `hash_version` and `query_hash_version`, which name the code, the source and the hash versions that wrote it; 'none' where there is no readable store), `code`, and the counts, among them `samples_with_refused_targets` (samples that lost at least one target to the engine's refusal) and `samples_with_all_targets_refused` (samples that lost at least one and kept none);
- one `query` for each QueryHash that a state holds or a target query has: hash, kind, hash_exact, body (canonical text), body_decodes (null: the decoder check is not run), inputs (list of {query, name}, a base table with only its name), outputs (sorted Names), graph_tables (Name -> graph table), graph_queries (the union identities), program (the engine program text of the query: the lines of its use closure in dependency order under the labels &r0.., then its own line, as `Writer.program` gives them), closure (the QueryHashes of the closure lines, in the order of those lines);
- one `sample` for each distinct (task, set of QueryHash), in the order of walk-states-SET.jsonl: id, task, split, eval_only (true for a held-out task: its samples serve evaluation, and the skeleton is no fit, so it calls no guard), state {id, queries}, target_queries (hashes sorted; the fields are those of the `query` line), target_tables ([hash, name] sorted), refused_target_queries (the count of this sample's targets that the engine refused, so dropped), no_progress_queries, frontier_depth.
The fields of the contract's `Sample` that come from table values (`state.members`' hashes and vectors, `computes*`, `query_vector`, `capped_target_tables`) are absent: stage 3 adds them.

A query in a state is written over the state's own members: each graph table it uses is the table of a member that computes it (where several members do, the least (hash, Name)). A target query is a graph query that is applicable (every graph table it reads is built), not a member, and has a head not built; it is written once for each combination of members, one member at each table that several members compute, with no cap on the combinations. Its QueryHash is `query_hash` of its canonical text.

The Names of a query's outputs are those of its graph query's heads. The union graph names an INIT's table by the output that a consumer reads, so an INIT that no consumer reads has the bare table and Name ''; its Names are then those that the row store holds for the INIT (stage 3 names a table by (QueryHash, Name)).
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parent))
import argparse, gzip, hashlib, itertools, json, math, os, re, sys, tempfile, time, zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import canon_text
import column_map
import column_names
import query_hash
import union_forms
from split import GRAPHS, OUTD, is_held_out, split_of
from union_forms import Form, LineIndex, TaskGraph

SCHEMA = 'skeleton-3'
SOURCES = ('canon_text.py', 'column_map.py', 'column_names.py', 'query_hash.py', 'union_forms.py', 'skeleton.py')
ROW_STORE_FIELDS = ('version', 'code', 'src', 'hash_version', 'query_hash_version', 'table_hash_version')
type Table = tuple[str, str]  # (QueryHash, Name)


@dataclass
class Query:
    hash: str
    body: str
    exact: bool
    conflicts: int
    graph_query: Form
    uses: dict[str, Table]  # graph table (or, where a case program reads two queries of one graph table, the reference) -> the (QueryHash, Name) of the member whose table the query uses there
    outputs: dict[str, str]  # Name -> graph table
    program: list[str]  # the lines of the use closure, then the query's own line
    closure: list[str]  # the QueryHashes of the closure lines
    inputs: list[Table]  # the tables the query reads, a base table as ('', name); see Writer.holder


@dataclass
class Stats:
    counts: Counter[str] = field(default_factory=Counter)
    refused: dict[str, str] = field(default_factory=dict)
    sizes: Counter[int] = field(default_factory=Counter)  # product size of the choices -> graph queries enabled at a state with that size


class Writer:
    """The queries of one task, hashed once for each (graph query, tables it uses)."""

    def __init__(self, graph: TaskGraph, stats: Stats, store: column_names.Outputs | None = None):
        self.graph, self.stats, self.store = graph, stats, store or {}
        self.own: Writer | None = None  # the graph queries written over the queries they name in their case programs
        self.own_memo: dict[str, str | None] = {}
        self.own_open: set[str] = set()  # the graph queries whose own hash is being computed
        self.output_memo: dict[str, dict[str, str]] = {}
        self.leaves_memo: dict[tuple[str, str, str], list[column_map.Leaf] | None] = {}
        self.labels_memo: dict[tuple[str, tuple[str, ...], tuple[str, ...]], list[str]] = {}
        self.memo: dict[tuple[str, tuple[Table, ...]], Query | None] = {}
        self.queries: dict[str, Query] = {}
        self.graph_hashes: dict[str, set[str]] = {}  # QueryHash -> the graph queries written to it

    def read(self, graph_query: Form, token: str, uses: dict[str, Table]) -> Table:
        """The (QueryHash, Name) that the reference `token` of the graph query reads: the member's table, and, where that member is an INIT of the component that the case program's INIT has, the port the token names (one graph table can hold two ports of an INIT, such as BoundingBox's `box` and `cell`)."""
        h, name = self.bound(graph_query, token, uses)
        named = self.graph.form(graph_query.read_idents[token])
        producer = self.queries[h].graph_query
        if named is not None and named.kind == 'INIT' and producer.kind == 'INIT' and named.tree[2] == producer.tree[2]:
            return h, token.partition('.')[2].split('.')[0] or name
        return h, name

    @staticmethod
    def bound(graph_query: Form, token: str, uses: dict[str, Table]) -> Table:
        """The member that the reference `token` reads. `uses` binds a graph table to one member for all the references to it, or a reference (a key that is the token) to its own member: one graph table holds the tables of equal maps, so a case program can read two of its queries, such as `start` and `end_cand`, that the table binding would make one."""
        return uses[token] if token in uses else uses[graph_query.refs[token]]

    def holder(self, h: str, port: str) -> Table:
        """The table whose rows are those of the output `port` of the query `h`: that output's own table, or, where the engine exports none for an input port whose body is one positive atom and NOT atoms (`gives_no_table`), the table of the positive atom (a base table is ('', name)); the port itself where the atom is of no table."""
        query = self.queries[h]
        atom = column_map.held_atom(query.graph_query.tree, port) if query.graph_query.kind == 'INIT' else None
        if atom is None:
            return h, port
        if atom in canon_text.GIVEN:
            return '', atom
        if atom not in query.graph_query.refs:
            self.stats.counts['ports with no table whose positive atom is of no table'] += 1
            return h, port
        self.stats.counts['ports with no table followed to the table of their positive atom'] += 1
        return self.holder(*self.read(query.graph_query, atom, query.uses))

    def table_inputs(self, graph_query: Form, uses: dict[str, Table]) -> list[Table]:
        """The tables the query reads, one for each reference, a port with no table written as the table that holds its rows."""
        return sorted({self.holder(*self.read(graph_query, tok, uses)) for tok in graph_query.refs})

    def query_text(self, graph_query: Form, uses: dict[str, Table], label: dict[str, str], own: str) -> str:
        """The graph query's text with its own label `own` and each reference written as the label of the query that its table is taken from. Where that query is not the one named in the case program, the reference's sites are written on the columns of the table taken."""
        tree = canon_text.parse(graph_query.line)[0]
        assert isinstance(tree, list)
        tree[1] = own

        def go(x: canon_text.Tree) -> None:
            if not isinstance(x, list):
                return
            if x and isinstance(x[0], str) and x[0] in graph_query.refs:
                x_token = x[0]
                h, name = self.read(graph_query, x[0], uses)
                producer = self.queries[h].graph_query
                named = self.graph.form(graph_query.read_idents[x[0]])
                old = x[0].partition('.')[2].split('.')[0]
                if named is not None and producer.ident != named.ident:
                    done = self.rewrite(x, producer, name, named, old, h)
                    if done is not None:
                        x[1:] = done[1:]
                x[0] = label[h] + ('.' + name if producer.kind == 'INIT' and name else '')
                if producer.kind == 'RIGID_DET' and named is not None and '.' in x_token:
                    inner = self.rigid_port(producer, named, '&' + x_token.partition('.')[2], self.queries[h].uses)
                    if inner is not None:
                        x[0] += '.' + label[inner].lstrip('&')
            for y in x:
                go(y)
        go(tree)
        self.drop_repeats(tree)
        return canon_text.write(tree)

    def drop_repeats(self, tree: list[canon_text.Tree]) -> None:
        """Drops each body atom that binds nothing and, but for its binders, is an earlier body atom: two references of a case program can be written as one
        query, where their tables hold the same rows, and the engine refuses the repeated test ("the completed atom repeats an existing test")."""
        def bare(x: canon_text.Tree) -> canon_text.Tree:
            return [bare(y) for y in x] if isinstance(x, list) else x.lstrip('*') if isinstance(x, str) else x

        def binds(x: canon_text.Tree) -> bool:
            return any(binds(y) for y in x) if isinstance(x, list) else isinstance(x, str) and x.startswith('*')

        seen: list[canon_text.Tree] = []
        keep = tree[:2]
        for atom in tree[2:]:
            b = bare(atom)
            if isinstance(atom, list) and b in seen and not binds(atom):
                self.stats.counts['body atoms dropped: a repeat of an earlier atom'] += 1
                continue
            seen.append(b)
            keep.append(atom)
        tree[:] = keep

    def rigid_port(self, producer: Form, named: Form, token: str, uses: dict[str, Table]) -> str | None:
        """The QueryHash of the query that the port `token` of the RIGID_DET `named` (as its case program writes it, such as `&r18` in `&r20.r18`) reads, in the RIGID_DET `producer` with the members `uses`: the producer's reference that reads the same form. None where there is none."""
        if token not in named.refs:
            return None
        for tok in producer.refs:
            if producer.read_idents[tok] == named.read_idents[token]:
                return self.read(producer, tok, uses)[0]
        return None

    def rewrite(self, atom: list[canon_text.Tree], new: Form, new_out: str, old: Form, old_out: str, new_hash: str) -> list[canon_text.Tree] | None:
        """The atom that reads the output `old_out` of `old` written over the output `new_out` of `new`, which hold the same rows; None where the sites can't be moved."""
        a, b = self.leaves(old, old_out), self.leaves(new, new_out, new_hash)
        if a is not None and b is not None:
            paired = column_map.pair(a, b)
            same = self.own_hash(old.ident)
            if same is not None and same == self.own_hash(new.ident) and len(a) == len(b):
                paired = {x.name: y.name for x, y in zip(a, b)}, 0  # one function written twice: its columns are the same, in the same order
            if paired is None:
                self.stats.counts['references left as written: the two tables differ in column types'] += 1
                return None
            onto, ties = paired
        else:
            # a table whose columns the row store lacks has those of its text
            old_cols = {x.name: x.origin for x in a} if a is not None else old.cols if old.kind != 'INIT' else {}
            new_cols = {x.name: x.origin for x in b} if b is not None else new.cols if new.kind != 'INIT' else {}
            onto = column_map.pair_cols(old_cols, new_cols) if old_cols and new_cols else None
            if onto is None:  # the table of a text has an Example column only where its text names one
                example = {x.name for x in [*(a or []), *(b or [])] if x.type == 'Example'}
                old_cols, new_cols = ({n: o for n, o in c.items() if n not in example} for c in (old_cols, new_cols))
                onto = column_map.pair_cols(old_cols, new_cols) if old_cols and new_cols else None
            ties = 0
            if onto is None:
                self.stats.counts['references left as written: columns of a table not in the row store'] += 1
                return None
            self.stats.counts['references paired by the columns of their texts'] += 1
        done = column_map.rewrite(atom, str(atom[0]), onto, column_map.records_of(a or []))
        if done is None:
            self.stats.counts['references left as written: a site on a column the table lacks'] += 1
            return None
        self.stats.counts['references written on the columns of another table'] += 1
        self.stats.counts['of those, with types of several columns'] += ties > 0
        return done

    def leaves(self, form: Form, out: str, written: str = '') -> list[column_map.Leaf] | None:
        """The leaves of the graph query's output `out`; None where the row store lacks its columns. `written` is the QueryHash of a member that is this graph query written over a state's members, which the store can hold in place of the graph query's own."""
        key = (form.ident, out, written)
        if key not in self.leaves_memo:
            got = self.store.get(written, {}).get(out) or self.store.get(self.own_hash(form.ident) or '', {}).get(out)  # row store `function` record (future name: `query`)
            if got is None:
                got = self.sibling(form, out)
            if got is None:
                self.leaves_memo[key] = None
            else:
                types, labels, example = got
                self.leaves_memo[key] = column_map.leaves(form.kind, form.tree, form.cols, out, types, self.own_labels(form, labels, types), example)
        return self.leaves_memo[key]

    def sibling(self, form: Form, out: str) -> tuple[list[str], list[str], str] | None:
        """The row store's (types, labels, Example name) for the output `out` of a form that the store lacks, taken from the tables its graph table holds: those are tables of equal rows, and the store holds them. None where they differ in column types, or where the form's own column names can't be put against the types: an INIT takes the labels of the held table (they only name the fields of a type parameter's record), a bare proposer needs none, and a RULE or DET of one column names it."""
        held = {tuple(rec[0]): rec for t, n in form.heads if n == out for h, name in self.graph.entries.get(t, []) if (rec := self.store.get(h, {}).get(name))}
        if len(held) != 1:
            return None
        types, labels, example = next(iter(held.values()))
        if form.kind == 'INIT' or (len(form.tree) == 3 and isinstance(form.tree[2], str)):
            return types, labels, example
        if len(types) == 1 and len(form.cols) == 1:
            return types, [next(iter(form.cols)).lstrip(':')], example
        return None

    def own_labels(self, form: Form, labels: list[str], types: list[str]) -> list[str]:
        """The column labels of a RULE or DET as its own text names them. The row store holds one record for the graph queries of one QueryHash, with the labels of the first of them; for another, each label is the label of this form's column that has the same origin (the column it came from)."""
        names = [':' + x for x in labels]
        if form.kind == 'INIT' or not form.cols or set(names) == set(form.cols) or not all(names):
            return labels
        key = (form.ident, tuple(labels), tuple(types))
        if key not in self.labels_memo:
            self.labels_memo[key] = self.relabel(form, names, labels, types)
        return self.labels_memo[key]

    def relabel(self, form: Form, names: list[str], labels: list[str], types: list[str]) -> list[str]:
        """`labels` as `form` names them, where the store's record is that of another graph query with the same QueryHash. Where no graph query of the task is that one, `fit_labels`."""
        h = self.own_hash(form.ident)
        for other in self.graph.forms.values():
            if other.ident != form.ident and other.ident not in self.own_open and other.kind == form.kind and set(other.cols) == set(names) and self.own_hash(other.ident) == h:  # a graph query whose own hash is being computed reads this form, so its hash differs
                mine: dict[str, list[str]] = {}
                for n, o in form.cols.items():
                    mine.setdefault(o, []).append(n)
                used: Counter[str] = Counter()
                got = []
                for n in names:
                    o = other.cols[n]
                    used[o] += 1
                    if used[o] > len(mine.get(o, [])):
                        return self.fit_labels(form, labels, types)
                    got.append(mine[o][used[o] - 1].lstrip(':'))
                return got
        return self.fit_labels(form, labels, types)

    def fit_labels(self, form: Form, labels: list[str], types: list[str]) -> list[str]:
        """`labels` with the names of the form's columns, where the store's labels are those of a text that names its columns otherwise (such as a column of a record field, which the store names by the field). Where one label is no column of the form and one column of the form is no label (among several such columns, the one whose origin no named column has), that column replaces the label. Else, where the form's own record in the store has its columns, the form's column names take the places of the labels by column type, in the order of that record; else `labels`."""
        cols = {x.lstrip(':'): o for x, o in form.cols.items()}
        lost = [x for x in labels if x not in cols]
        taken = {cols[x] for x in labels if x in cols}
        spare = [n for n in cols if n not in labels]
        if len(spare) > 1:
            spare = [n for n in spare if cols[n] not in taken]
        if len(lost) == 1 and len(spare) == 1 and len(set(labels)) == len(labels):
            return [spare[0] if x == lost[0] else x for x in labels]
        own = self.store.get(self.own_hash(form.ident) or '', {})
        record = next(iter(own.values())) if len(own) == 1 else None
        if record is not None and set(record[1]) <= set(cols) and len(record[1]) == len(labels) and Counter(record[0]) == Counter(types):
            queue: dict[str, list[str]] = {}
            for t, n in zip(record[0], record[1]):
                queue.setdefault(t, []).append(n)
            return [queue[t].pop(0) for t in types]
        return labels

    def own_hash(self, graph_hash: str) -> str | None:
        """The QueryHash of the graph query written over the queries its case program names: the id by which the row store holds it."""
        if graph_hash in self.own_open:  # the case programs' reads, joined by identity, can form a cycle; a query on one has no own hash
            self.stats.counts['own hash on a cycle of reads'] += 1
            return None
        if graph_hash not in self.own_memo:
            if self.own is None:  # one own Writer, which is its own own Writer, and one memo and one open set for all, so that its own hashes do not start a Writer each
                self.own = Writer(self.graph, Stats(), self.store)
                self.own.own, self.own.own_memo, self.own.own_open = self.own, self.own_memo, self.own_open
            f = self.graph.form(graph_hash)
            assert f is not None
            uses: dict[str, Table] = {}
            self.own_open.add(graph_hash)  # open until its query is made: the made query's text can call for the own hash of this graph query (through `relabel`)
            try:
                for tok, t in f.refs.items():
                    r = self.graph.form(f.read_idents[tok])
                    h = self.own_hash(r.ident) if r is not None else None
                    if r is None or h is None:
                        self.own_memo[graph_hash] = None
                        return None
                    uses[tok] = (h, next((n for t2, n in r.heads if t2 == t), ''))
                query = self.own.make(f, uses)
            finally:
                self.own_open.discard(graph_hash)
            self.own_memo[graph_hash] = query.hash if query else None
        return self.own_memo[graph_hash]

    def output_names(self, graph_query: Form) -> dict[str, str]:
        """{Name: graph table} of the graph query's outputs: the Names of its heads. An INIT head with Name '' (no consumer in any case reads that INIT's table by Name) stands for each Name that the row store holds for the INIT, where it holds the INIT; otherwise it stays ''."""
        got = self.output_memo.get(graph_query.ident)
        if got is None:
            got = {n: t for t, n in graph_query.heads}
            if self.store and graph_query.kind == 'INIT' and '' in got:
                stored = self.store.get(self.own_hash(graph_query.ident) or '')  # row store `function` record (future name: `query`)
                if stored:
                    table = got.pop('')
                    for n in sorted(stored):
                        got.setdefault(n, table)
            self.output_memo[graph_query.ident] = got
        return got

    def closure(self, uses: dict[str, Table]) -> list[str]:
        """The QueryHashes of the queries in the use closure of `uses`, in dependency order."""
        order: list[str] = []

        def visit(h: str) -> None:
            if h not in order:
                for u in sorted(self.queries[h].uses.values()):
                    visit(u[0])
                order.append(h)
        for h, _ in sorted(uses.values()):
            visit(h)
        return order

    def program(self, graph_query: Form, uses: dict[str, Table]) -> tuple[list[str], str]:
        """(the texts of the queries that `graph_query` uses, its own text): the use closure in dependency order, under labels of this program."""
        order = self.closure(uses)
        label = {h: f'&r{i}' for i, h in enumerate(order)}
        scope = [self.query_text(self.queries[h].graph_query, self.queries[h].uses, label, label[h]) for h in order]
        return scope, self.query_text(graph_query, uses, label, f'&r{len(order)}')

    def make(self, graph_query: Form, uses: dict[str, Table]) -> Query | None:
        key = (graph_query.ident, tuple(self.bound(graph_query, tok, uses) for tok in sorted(graph_query.refs)))
        if key in self.memo:
            got = self.memo[key]
        else:
            scope, text = self.program(graph_query, uses)
            try:
                h = query_hash.query_hash(scope, text)
            except query_hash.arclog.Refusal as e:
                self.stats.counts['graph queries the engine refused over these members'] += 1
                self.stats.refused.setdefault(graph_query.ident, str(e).splitlines()[0][:200])
                self.memo[key] = got = None
            else:
                def refs(token: str) -> str:
                    if token in graph_query.refs:
                        d, n = self.read(graph_query, token, uses)
                        return '@' + d + ('.' + n if n else '')
                    return token
                c = canon_text.canonical(graph_query.tree, refs)
                self.memo[key] = got = Query(h, c.text, c.exact, c.field_conflicts, graph_query, dict(uses), self.output_names(graph_query), [*scope, text], self.closure(uses), self.table_inputs(graph_query, uses))
        if got is not None:
            self.queries.setdefault(got.hash, got)
            self.graph_hashes.setdefault(got.hash, set()).add(graph_query.ident)
        return got

    def fit(self, graph_query: Form, table: str, producers: list[Table]) -> list[Table]:
        """The members of `producers` whose table has the column types of the table that the graph query reads in its case program, where there are any; else all of them. The union graph holds as one table some tables of different column types."""
        want = []
        for tok, t in graph_query.refs.items():
            named = self.graph.form(graph_query.read_idents[tok])
            if t == table and named is not None:
                a = self.leaves(named, tok.partition('.')[2].split('.')[0])
                if a is not None:
                    want.append(Counter(x.type for x in a))
        if not want:
            return producers
        keep = []
        for h, n in producers:
            b = self.leaves(self.queries[h].graph_query, n, h)
            if b is None or all(w == Counter(x.type for x in b) for w in want):
                keep.append((h, n))
        return keep or producers

    def pick(self, graph_query: Form, table: str, producers: list[Table]) -> Table:
        """The member of `producers` that the graph query reads in its case program, else the least (hash, Name) of the members that fit."""
        producers = self.fit(graph_query, table, producers)
        own = {tok for tok, t in graph_query.refs.items() if t == table}
        named = {graph_query.read_idents[tok] for tok in own}
        for h, n in sorted(producers):
            if self.queries[h].graph_query.ident in named:
                return h, n
        return min(producers)

    def members(self, graph_hashes: list[str]) -> dict[str, Query]:
        """{graph query's identity: its query written over the state's members}, at a table with several members, the one the graph query names in its case program, else the least (hash, Name)."""
        made: dict[str, Query] = {}
        by_table: dict[str, list[Table]] = {}
        todo = [self.graph.forms[i] for i in graph_hashes if i in self.graph.forms]
        while todo:
            ready = [f for f in todo if all(t in by_table for t in f.refs.values())]
            if not ready:
                self.stats.counts['members with a table no member makes'] += len(todo)
                break
            for f in ready:
                uses = {t: self.pick(f, t, by_table[t]) for t in f.refs.values()}
                query = self.make(f, uses)
                if query is not None:
                    made[f.ident] = query
            todo = [f for f in todo if f.ident not in {r.ident for r in ready}]
            for f in ready:
                if f.ident in made:
                    for n, t in made[f.ident].outputs.items():
                        by_table.setdefault(t, []).append((made[f.ident].hash, n))
        return made


def state_sample(task: str, split: str, state: dict, w: Writer, st: Counter[str]) -> dict | None:
    graph = w.graph
    graph_hashes = list(state['forms'])  # the input file's field
    built = set(state['built'])
    made = w.members(graph_hashes)
    producers: dict[str, list[Table]] = {}
    for query in made.values():
        for n, t in query.outputs.items():
            producers.setdefault(t, []).append((query.hash, n))
    if set(producers) != built:
        st['states whose built tables are not the members\' heads'] += 1
    member_hashes = sorted({q.hash for q in made.values()})
    sid = hashlib.sha256('\n'.join(member_hashes).encode()).hexdigest()[:32]
    targets: dict[str, Query] = {}
    no_progress = enabled = refused = 0
    depths = []
    for graph_hash, graph_query in graph.forms.items():
        if graph_hash in made or not set(graph_query.reads) <= built:
            continue
        if {h for h, _ in graph_query.heads} <= built:
            no_progress += 1
            continue
        enabled += 1
        if graph_query.depth is not None:
            depths.append(graph_query.depth)
        tables = sorted(set(graph_query.refs.values()))
        choices = [w.fit(graph_query, t, sorted(set(producers.get(t, [])))) for t in tables]
        if any(not c for c in choices):
            st['enabled graph queries with a table no member makes'] += 1
            continue
        w.stats.sizes[_count(choices)] += 1
        st['target combinations'] += _count(choices)
        for pick in itertools.product(*choices):
            query = w.make(graph_query, dict(zip(tables, pick)))
            if query is None:
                refused += 1
                continue
            if query.hash in member_hashes:
                st['target queries equal to a member'] += 1
            else:
                targets[query.hash] = query
    st['states'] += 1
    st['enabled graph queries'] += enabled
    st['no progress'] += no_progress
    st['no progress differs from redundant_forms'] += no_progress != state['redundant_forms']
    st['frontier depth differs from depth'] += (min(depths) if depths else None) != state['depth']
    st['target queries'] += len(targets)
    return dict(record='sample', id=hashlib.sha256((task + '\n' + '\n'.join(member_hashes)).encode()).hexdigest()[:32], task=task, split=split, eval_only=is_held_out(split),
                state=dict(id=sid, queries=member_hashes), target_queries=sorted(targets),
                target_tables=sorted({(h, n) for h, q in targets.items() for n in q.outputs}),
                refused_target_queries=refused, no_progress_queries=no_progress, frontier_depth=min(depths) if depths else None)


def _count(choices: list[list[Table]]) -> int:
    n = 1
    for c in choices:
        n *= len(c)
    return n


def percentile(sizes: Counter[int], q: float) -> int:
    """The least size that at least the fraction q of the counted sizes do not pass."""
    need, run = math.ceil(q * sum(sizes.values())), 0
    for size in sorted(sizes):
        run += sizes[size]
        if run >= need:
            return size
    return 0


def query_record(query: Query, graph_hashes: set[str]) -> dict:
    inputs = [dict(query=h, name=n) for h, n in query.inputs if h] + [dict(name=g) for g in sorted({*query.graph_query.givens, *(n for h, n in query.inputs if not h)})]
    return dict(record='query', hash=query.hash, kind=query.graph_query.kind, hash_exact=True, body_exact=query.exact, body=query.body, body_decodes=None, inputs=inputs,
                outputs=sorted(query.outputs), graph_tables=dict(sorted(query.outputs.items())), graph_queries=sorted(graph_hashes), program=query.program, closure=query.closure)


def code_sha() -> str:
    h = hashlib.sha256()
    for name in SOURCES:
        h.update((Path(__file__).resolve().parent / name).read_bytes())
    return h.hexdigest()


def sha_lines(lines: list[bytes]) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update(line)
    return h.hexdigest()


def row_store_sha(path: Path) -> str:
    """The sha of the row store's header fields that name the code, the source and the hash versions that wrote it. The whole file's sha is no input: supplement.py appends to the store after its footer, and this stage reads only the lines before it. 'none' where there is no readable store."""
    try:
        with gzip.open(path, 'rt') as f:
            header = json.loads(f.readline())
    except (OSError, EOFError, ValueError):
        return 'none'
    return hashlib.sha256(json.dumps({k: header.get(k) for k in ROW_STORE_FIELDS}, sort_keys=True).encode()).hexdigest()


def read_header(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.loads(f.readline())
    except (FileNotFoundError, ValueError):
        return None


def run_task(sset: str, task: str, idx: dict[str, LineIndex], out: Path, code: str) -> tuple[Counter[str], Counter[int]] | None:
    """Writes the task's file; returns (its totals, its product sizes), or None where the file is current."""
    split = split_of(task)
    lines = {k: v.lines(task) for k, v in idx.items()}
    rows_path = OUTD / sset / 'rows' / f'{task}.jsonl.gz'
    inputs = {k: sha_lines(v) for k, v in lines.items()} | {'split': hashlib.sha256(f'{task} {split}'.encode()).hexdigest(), 'row_store': row_store_sha(rows_path)}
    path = out / f'{task}.jsonl'
    old = read_header(path)
    if old and old.get('inputs') == inputs and old.get('code') == code and old.get('schema') == SCHEMA and old.get('query_hash_version') == query_hash.VERSION:
        return None
    graph = union_forms.load(task, lines['queries'], lines['tables'], lines['keys'])
    stats = Stats()
    w = Writer(graph, stats, column_names.load(rows_path))
    samples, seen = [], set()
    for raw in lines['states']:
        s = json.loads(raw)
        sample = state_sample(task, split, s, w, stats.counts)
        if sample is None:
            continue
        if sample['id'] in seen:
            stats.counts['states merged by equal query sets'] += 1
            continue
        seen.add(sample['id'])
        samples.append(sample)
    targets = {h for s in samples for h in s['target_queries']}
    tables = {(h, n) for s in samples for h, n in s['target_tables']}
    with_refused = sum(s['refused_target_queries'] > 0 for s in samples)
    with_all_refused = sum(s['refused_target_queries'] > 0 and not s['target_queries'] for s in samples)
    header = dict(record='header', schema=SCHEMA, set=sset, task=task, split=split, query_hash_version=query_hash.VERSION,
                  canon_version=canon_text.VERSION, or_branches_sorted_in_body=True, inputs=inputs, code=code,
                  samples=len(samples), queries=len(w.queries), target_queries=len(targets), target_tables=len(tables),
                  samples_with_refused_targets=with_refused, samples_with_all_targets_refused=with_all_refused,
                  inexact_bodies=sum(not q.exact for q in w.queries.values()), field_conflicts=sum(q.conflicts > 0 for q in w.queries.values()),
                  unresolved_queries=graph.unresolved, refused=stats.refused, queries_without_consistent_case=sum(not f.consistent for f in graph.forms.values()), counts=dict(sorted(stats.counts.items())))
    out.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out, prefix=f'{task}.jsonl.')
    with os.fdopen(fd, 'w') as f:
        for rec in [header, *(query_record(q, w.graph_hashes[h]) for h, q in sorted(w.queries.items())), *samples]:
            f.write(json.dumps(rec) + '\n')
    os.replace(tmp, path)
    totals = Counter({'samples': len(samples), 'target queries': len(targets), 'target tables': len(tables), 'samples losing a target': with_refused,
                      'samples losing all targets': with_all_refused, 'refused targets': sum(s['refused_target_queries'] for s in samples),
                      'combinations': sum(size * n for size, n in stats.sizes.items())})
    return totals, stats.sizes


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set', choices=('train', 'dev', 'held-out'))
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks with crc32(task) %% N == k')
    ap.add_argument('--tasks', help='comma-separated task ids')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    k, n = map(int, a.shard.split('/'))
    # `queries` indexes graph-prods-SET.jsonl, whose lines are the union graph's productions (future name: queries)
    graphs = Path(os.environ['ARC_SAMPLE_GRAPHS']) if os.environ.get('ARC_SAMPLE_GRAPHS') else GRAPHS  # another graph folder, such as a pass of the graph
    idx = {'states': LineIndex(graphs / f'walk-states-{a.set}.jsonl'), 'queries': LineIndex(graphs / f'graph-prods-{a.set}.jsonl'),
           'tables': LineIndex(graphs / f'graph-tables-{a.set}.jsonl'), 'keys': LineIndex(graphs / f'union-keys-{a.set}.jsonl')}
    wanted = set(a.tasks.split(',')) if a.tasks else None
    tasks = [t for t in idx['states'].tasks() if zlib.crc32(t.encode()) % n == k and (wanted is None or t in wanted)]
    out = a.out or OUTD / a.set / 'skeleton'
    code = code_sha()
    t0, done, skipped = time.time(), 0, 0
    tot: Counter[str] = Counter()
    sizes: Counter[int] = Counter()
    for i, task in enumerate(tasks, 1):
        t1 = time.time()
        got = run_task(a.set, task, idx, out, code)
        if got is None:
            skipped += 1
            continue
        done += 1
        tot += got[0]
        sizes += got[1]
        el = time.time() - t0
        print(f'{a.set} {task} {i}/{len(tasks)} states {got[0]["samples"]} target queries {got[0]["target queries"]} target tables {got[0]["target tables"]} {time.time() - t1:.1f}s '
              f'{done / el * 60:.1f} tasks/min ETA {el / done * (len(tasks) - i):.0f}s', flush=True)
    print(f'{a.set} shard {a.shard}: {done} written, {skipped} current, states {tot["samples"]} target queries {tot["target queries"]} target tables {tot["target tables"]} '
          f'samples losing a target {tot["samples losing a target"]} samples losing all targets {tot["samples losing all targets"]} refused targets {tot["refused targets"]} '
          f'combinations {tot["combinations"]} product size max {max(sizes, default=0)} p99 {percentile(sizes, 0.99)} in {time.time() - t0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
