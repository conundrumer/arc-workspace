"""Every table of a solver's concept case on a task JSON, in one engine call, at the assignment that solves the train pairs.

Runs under the engine runtime's python (-I). Reuses scripts/arclog.py's Tables and run_case.
"""
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

import paths  # noqa: E402

ROOT = paths.MAIN
GEN = paths.GEN
os.environ.setdefault('ARCLOG_PY_INNER', str(ROOT))
_spec = importlib.util.spec_from_file_location('arclog_cli', ROOT / 'scripts/arclog.py')
CLI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CLI)

import arclog  # noqa: E402
import numpy as np  # noqa: E402
import provenance as PV  # noqa: E402


class FlowTables(CLI.Tables):
    """The engine's Tables, with the flows of every column (`flows`: {field: list}, as provenance reads them)."""

    def __init__(self, arclog_, np_, program, ct, task_json):
        super().__init__(arclog_, np_, program, ct, task_json)
        dt = ct.dtypes
        self.flows = {k: (np_.frombuffer(v, dt['flows.' + k]).tolist() if isinstance(v, bytes) else list(v)) for k, v in ct.flows.items()}


CLI.Tables = FlowTables  # this module's own copy of scripts/arclog.py builds every Tables with the flows


def decode_once(tb):
    """Gives the engine's Tables tb a row decoder that converts each column with numpy, and decodes each table's entries once."""
    values = tb.values

    def raw_rows(offset, n, types):
        ws = [4 if ty in CLI.BOX_TYPES else 1 for ty in types]
        w = sum(ws)
        if n == 0 or w == 0:
            return [[] for _ in range(n)] if w == 0 else []
        a = values[int(offset):int(offset) + n * w].reshape(n, w)
        cols, s = [], 0
        for x in ws:
            cols.append(list(map(tuple, a[:, s:s + 4].tolist())) if x == 4 else a[:, s].tolist())
            s += x
        return [list(r) for r in zip(*cols)]

    held, entries = {}, tb.entries
    tb.raw_rows = raw_rows
    tb.entries = lambda t: held[t] if t in held else held.setdefault(t, entries(t))


class Solver:
    def __init__(self, task, text=None):
        """The task's solver, from its file in GEN, or from text in its place."""
        self.task = task
        text = (GEN / (task + '.arclog')).read_text() if text is None else text
        data = GEN / (task + '.arcdata')
        cases = arclog.case_files(task, text, data.read_text() if data.exists() else ';; %s\n' % task, str(GEN))
        self.case = ([c for c in cases if getattr(c, 'concept', False)] or cases)[0]
        self.text = self.case.arclog
        if self.text is None:
            raise ValueError('the program does not read')
        m = re.search(r'^\(OUT (.*)\)\s*$', self.text, re.M)
        self.out = []  # [(relation, column)] of the OUT form's sites, in written order
        for rel, body in re.findall(r'\((&[\w.]+)((?:[^()]|\([^()]*\))*)\)', m[1] if m else ''):
            self.out += [(rel, c) for c in re.findall(r'\^(\w+)', body)]
        self.tmp = Path(tempfile.mkdtemp(prefix='contracts-'))

    def run_engine(self, task_json):
        """The engine's Tables of the program on task_json, every assignment included. The first call sets self.provenance to
        provenance.provenance of the program's tables."""
        (self.tmp / (self.task + '.json')).write_text(json.dumps(task_json))
        tb, why = CLI.run_case(arclog, np, self.case, self.task, self.tmp, task_json)
        if tb is None:
            raise RuntimeError(why)
        decode_once(tb)
        if getattr(self, 'provenance', None) is None:  # the program's flows, the same on every task file
            self.provenance = PV.provenance(tb, self.text)
        return tb

    def read(self, tb, best):
        """{relation: {'columns': [(name, type, frame)], 'rows': {example: rows}}} at the assignment key best, or, where best is None, at
        each table's first assignment. Sets self.stored and self.stored_types to best's stored values."""
        self.stored = None if best is None else {rel: rows for rel, rows, _ in best}
        self.stored_types = None if best is None else {rel: types for rel, _, types in best}
        out = {}
        for t, name in enumerate(tb.names):
            if not name:
                continue
            types = tb.T['column_types'][t]
            cols = list(zip(tb.T['column_names'][t], types, tb.T['column_frames'][t]))
            ents = tb.entries(t)
            keys = tb.assignments(t)
            key = next((k for k in keys if consistent(k, best)), keys[0] if keys else ())
            rows = {}
            for ex, model, k, raw, stop in ents:
                if k == key and model == 0:
                    rows[ex] = [[tb.value(t, ty, v) for ty, v in zip(types, r)] for r in raw]
            out[name] = dict(columns=cols, rows=rows, assignments=len(keys))
        return out

    def tables(self, task_json, pin=None, no_assignment=None):
        """{relation: {'columns': [(name, type, frame)], 'rows': {example: rows}}} at the assignment that solves the train pairs, or, with pin
        ({stored relation: rows}), at the first assignment that gives those stored relations those rows. A pinned relation whose rows no
        assignment gives is missing (self.missing); the assignment is then the first that gives every other pinned relation its rows. Where the
        engine gives no assignment at all, no_assignment(pin) names the missing relations."""
        tb = self.run_engine(task_json)
        self.missing = []
        if pin is None:
            best = self.solving_key(tb, task_json)
        else:
            self.missing = self.missing_pins(tb, pin)
            if no_assignment is not None and set(self.missing) == set(pin) and not self.has_assignment(tb):
                self.missing = no_assignment(pin)
            best = self.pinned_key(tb, {r: v for r, v in pin.items() if r not in self.missing})
        return self.read(tb, best)

    def tables_each(self, task_json, pin, limit):
        """([(assignment key, tables)], count): the tables at each assignment of the OUT relation's table that gives each relation of pin that
        the key holds its rows, for the first `limit` such assignments, and how many such assignments there are."""
        tb = self.run_engine(task_json)
        self.missing = []
        t = tb.find(self.out[0][0]) if self.out else None
        keys = [k for k in (tb.assignments(t) if t is not None else [])
                if all(set(rows) == set(pin[rel]) for rel, rows, _ in k if rel in pin)]
        return [(k, self.read(tb, k)) for k in keys[:limit]], len(keys)

    def has_assignment(self, tb):
        t = tb.find(self.out[0][0]) if self.out else None
        return t is not None and any(len(k) for k in tb.assignments(t))

    def missing_pins(self, tb, pin):
        """The relations of pin whose rows no assignment key of the OUT relation's table gives."""
        t = tb.find(self.out[0][0]) if self.out else None
        keys = tb.assignments(t) if t is not None else []
        offered = {}
        for key in keys:
            for rel, rows, _ in key:
                offered.setdefault(rel, set()).add(frozenset(rows))
        return sorted(r for r, rows in pin.items() if frozenset(rows) not in offered.get(r, set()))

    def pinned_key(self, tb, pin):
        """The first assignment key of the OUT relation's table that gives each relation of pin its rows, or None."""
        t = tb.find(self.out[0][0]) if self.out else None
        if t is None:
            return None
        for key in tb.assignments(t) or [()]:
            have = {rel: rows for rel, rows, _ in key}
            if all(set(have.get(rel, ())) == set(rows) for rel, rows in pin.items()):
                return key
        return None

    def solving_key(self, tb, task_json):
        """The assignment key of the OUT relation's table under which the OUT rows equal every train output, or None."""
        if not self.out:
            return None
        rel = self.out[0][0]
        t = tb.find(rel)
        if t is None:
            return None
        for key in tb.assignments(t) or [()]:
            if all(self.out_grid(tb, task_json, ex, key) == task_json['train'][i]['output'] for i, ex in enumerate('train/%d' % i for i in range(len(task_json['train'])))):
                return key
        return None

    def out_grid(self, tb, task_json, ex, key):
        """The grid that the OUT form gives at ex, for the first OUT relation's assignment key; None where it gives none."""
        cells = {}
        if len(self.out) == 1 or (len(self.out) >= 2 and self.out[0][0] == self.out[1][0]):
            t = tb.find(self.out[0][0])
            names = tb.T['column_names'][t]
            pc, cc = names.index(self.out[0][1]), names.index(self.out[1][1] if len(self.out) > 1 else names[-1])
            for e, model, k, raw, stop in tb.entries(t):
                if e == ex and k == key and model == 0:
                    for r in raw:
                        cells.setdefault(r[pc], set()).add(r[cc])
        else:
            tp, tc = tb.find(self.out[0][0]), tb.find(self.out[1][0])
            pn, cn = tb.T['column_names'][tp], tb.T['column_names'][tc]
            ps = [r[pn.index(self.out[0][1])] for e, m, k, raw, s in tb.entries(tp) if e in (ex, 'task') and m == 0 for r in raw]
            cs = {r[next(i for i, n in enumerate(cn) if n.split('.')[-1] == self.out[1][1] or n == self.out[1][1])]
                  for e, m, k, raw, s in tb.entries(tc) if e in (ex, 'task') and m == 0 for r in raw}
            for p in ps:
                cells.setdefault(p, set()).update(cs)
        if not cells or any(len(v) != 1 for v in cells.values()):
            return None
        H = max(p[0] for p in cells) + 1
        W = max(p[2] for p in cells) + 1
        g = [[None] * W for _ in range(H)]
        for (t_, b, l, r), v in cells.items():
            if t_ + b + 1 != H or l + r + 1 != W:
                return None
            g[t_][l] = next(iter(v))
        return g if all(x is not None for row in g for x in row) else None


def stored_status(stored, base, types, n_examples, missing=()):
    """('same' | 'changed' | 'unsolved', the stored relations whose rows differ from the task's) of the stored values of the chosen assignment.
    `unsolved` where no assignment exists, or where a pinned relation is missing (no assignment offers its value). A stored relation with an
    Example column is compared at the task's own examples (indices below n_examples): an appended example adds rows of its own."""
    if stored is None:
        return 'unsolved', sorted(base)

    def own(rel, rows):
        e = [i for i, t in enumerate(types.get(rel, ())) if t == 'Example']
        return {r for r in rows if not e or r[e[0]] < n_examples}
    changed = sorted(set(missing) | {r for r in set(base) | set(stored) if own(r, stored.get(r, ())) != own(r, base.get(r, ()))})
    return ('unsolved' if missing else 'changed' if changed else 'same'), changed


def proposer_relations(query_features):
    """The stored relations whose value a proposer offers and the fit to the train pairs keeps: a DET, or a DET_OR_RULE line, that names a
    proposer and has no body."""
    return {n for n, q in query_features.items() if q.get('kind') in ('DET', 'DET_OR_RULE') and q.get('proposer') and not q.get('atoms')}


def settle_stored(solver, T, T0, base_stored, base_types, n_examples):
    """(status, changed, invalid) of the stored values of a variant's tables T, as stored_status gives them, with T fixed in place: a missing
    relation holds no row. Where the engine gave no assignment at all, nothing that reads a stored relation was derived, so every stored relation is
    invalid, and each one not missing keeps its rows from the task's tables T0; otherwise the invalid relations are the changed ones."""
    status, changed = stored_status(solver.stored, base_stored, base_types, n_examples, solver.missing)
    invalid = changed
    if solver.stored is None:
        changed, invalid = sorted(solver.missing), sorted(base_stored)
        for rel in base_stored:
            if rel in T and rel in T0 and rel not in solver.missing:
                T[rel] = T0[rel]
    blank_stored(T, solver.missing)
    return status, changed, invalid


def blank_stored(T, names):
    """Where no stored values solve the train pairs, a determination keeps no value, so each stored relation holds no row."""
    for n in names:
        if n in T:
            T[n] = dict(T[n], rows={'task': []})


def consistent(k, best):
    if best is None:
        return False
    have = {rel: rows for rel, rows, _ in best}
    return all(have.get(rel, rows) == rows for rel, rows, _ in k)


def reads(text):
    """{relation or instance: set of relations or instances it reads} of a case program; an instance's output is its instance."""
    forms, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                forms.append(text[start:i + 1])
    out = {}
    for f in forms:
        m = re.match(r'\((RULE|DET|DET_OR_RULE|RULE_OR_DET|INIT|RIGID_DET|CHOOSE) (&[\w]+)', f)
        if not m:
            continue
        name = m[2]
        used = {x.split('.')[0] for x in re.findall(r'&[\w]+(?:\.[\w]+)?', f[m.end():])} - {name}
        out.setdefault(name, set()).update(used)
    return out


def reads_ports(text):
    """{relation or instance: set of the names it reads, an instance's outputs with their port}."""
    out = {}
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                f = text[start:i + 1]
                m = re.match(r'\((RULE|DET|DET_OR_RULE|RULE_OR_DET|INIT|RIGID_DET|CHOOSE) (&[\w]+)', f)
                if m:
                    out.setdefault(m[2], set()).update(set(re.findall(r'&[\w]+(?:\.[\w]+)?', f[m.end():])) - {m[2]})
    return out


def table_reads(text):
    """{relation or instance: set of the names its form reads}: as reads_ports, with the facts (input, ex_input, ex_output) it reads."""
    out = reads_ports(text)
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                f = text[start:i + 1]
                m = re.match(r'\((RULE|DET|DET_OR_RULE|RULE_OR_DET|INIT|RIGID_DET|CHOOSE) (&[\w]+)', f)
                if m:
                    out.setdefault(m[2], set()).update(re.findall(r'\((input|ex_input|ex_output)\b', f[m.end():]))
    return out


def node(rel):
    return rel.split('.')[0] if rel.startswith('&') else rel


def upstream(graph, rel):
    seen, todo = set(), [node(rel)]
    while todo:
        x = todo.pop()
        for y in graph.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return seen
