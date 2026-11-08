"""Tables of a concept case, retaining assignments whose entries are complete.

Each query uses the engine's evaluation caps. The task session has the same byte bound as verification. Each entry gives its rows as the
evaluation holds them: a product of parts over the projection cap gives its row count and its parts, so no product is built.
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

SESSION_BYTES = arclog.SESSION_BYTES


def product_of_parts(parts, columns):
    """The distinct rows of the given columns of a product of parts, [(columns of the part, its rows, each cell hashable)]."""
    held = [{}]
    for cols, rows in parts:
        here = [c for c in columns if c in cols]
        if here:
            at = [cols.index(c) for c in here]
            values = list(dict.fromkeys(tuple(r[a] for a in at) for r in rows))
            held = [dict(row, **{str(c): v for c, v in zip(here, value)}) for row in held for value in values]
    return [[row[str(c)] for c in columns] for row in held] if all(str(c) in held[0] for c in columns) else []


def decode_settings():
    """The engine's corpus settings, with no query deadline."""
    return arclog.DecodeSettings.corpus()


class AssignmentUnavailable(RuntimeError):
    """No required assignment has complete tables; selection records rejected bounds."""

    def __init__(self, selection):
        self.selection = selection
        super().__init__('no %s assignment has complete tables: %s' % (selection['selection'], json.dumps(selection)))


class FlowTables(CLI.Tables):
    """The engine's Tables, with the flows of every column (`flows`: {field: list}, as provenance reads them)."""

    def __init__(self, arclog_, np_, program, ct, task_json):
        self.held_entries, self.held_keys = {}, {}
        super().__init__(arclog_, np_, program, ct, task_json)
        dt = ct.dtypes
        self.flows = {k: (np_.frombuffer(v, dt['flows.' + k]).tolist() if isinstance(v, bytes) else list(v)) for k, v in ct.flows.items()}
        part = lambda name, cols: {k: (np_.frombuffer(v, dt['%s.%s' % (name, k)]) if isinstance(v, bytes) else v) for k, v in cols.items()}
        self.P = part('projections', ct.projections)
        self.PR = part('projection_rows', ct.projection_rows)
        self.projection_runs = {}
        for run, entry in enumerate(self.PR['entry'].tolist()):
            if self.PR['defined'][run]:
                self.projection_runs.setdefault(entry, []).append(run)
        self.held_views = {}

    def raw_rows(self, offset, n, types):
        """The rows at the offset, whose columns convert with numpy when they are read."""
        return RunRows(self.values, offset, n, types)

    def entries(self, t):
        if t not in self.held_entries:
            self.held_entries[t] = super().entries(t)
        return self.held_entries[t]

    def assignments(self, t):
        if t not in self.held_keys:
            self.held_keys[t] = super().assignments(t)
        return self.held_keys[t]

    def entry_views(self, entry, t):
        """[(columns of table t, raw rows)] of each part of the product at the entry."""
        if entry not in self.held_views:
            types = self.T['column_types'][t]
            views = []
            for run in self.projection_runs.get(entry, ()):
                columns = [int(c) for c in self.P['columns'][int(self.PR['projection'][run])]]
                views.append((columns, self.raw_rows(self.PR['offset'][run], int(self.PR['rows'][run]), [types[c] for c in columns])))
            self.held_views[entry] = views
        return self.held_views[entry]

    def read_columns(self, entry, t, columns, raw):
        """The distinct rows of the given columns of table t at the entry, from its rows, or as the product of what its parts give of them."""
        if not self.counted(entry):
            return [[r[c] for c in columns] for r in raw]
        return product_of_parts(self.entry_views(entry, t), columns)


CLI.Tables = FlowTables  # this module's own copy of scripts/arclog.py builds every Tables with the flows


class RunRows:
    """The rows of a run of cells, converted each time they are read, so an entry that nothing reads costs nothing."""

    __slots__ = ('values', 'offset', 'n', 'widths')

    def __init__(self, values, offset, n, types):
        self.values, self.offset, self.n = values, int(offset), n
        self.widths = [4 if ty in CLI.BOX_TYPES else 1 for ty in types]

    def __len__(self):
        return self.n

    def __iter__(self):
        w = sum(self.widths)
        if self.n == 0 or w == 0:
            return iter([[] for _ in range(self.n)] if w == 0 else [])
        a = self.values[self.offset:self.offset + self.n * w].reshape(self.n, w)
        cols, s = [], 0
        for x in self.widths:
            cols.append(list(map(tuple, a[:, s:s + 4].tolist())) if x == 4 else a[:, s].tolist())
            s += x
        return iter([list(r) for r in zip(*cols)])


def supported_case(case):
    """Whether the case has a program without a DEMONSTRATED form, ignoring strings and comments."""
    if case.arclog is None:
        return False
    forms = re.sub(r'"(?:[^"\\]|\\.)*"|;[^\n]*', ' ', case.arclog)
    return re.search(r'\(\s*DEMONSTRATED(?=[\s()])', forms) is None


class Solver:
    def __init__(self, task, text=None):
        """The task's solver, from its file in GEN, or from text in its place."""
        self.task = task
        text = paths.read_gen(GEN / (task + '.arclog')) if text is None else text
        data = GEN / (task + '.arcdata')
        cases = arclog.case_files(task, text, paths.read_gen(data) if data.exists() else ';; %s\n' % task, str(GEN))
        self.case = next((case for case in cases if case.concept), None)
        if self.case is None or not supported_case(self.case):
            raise ValueError(f'{task}: the concept case is not supported (it needs a program without DEMONSTRATED forms)')
        self.text = self.case.arclog
        m = re.search(r'^\(OUT (.*)\)\s*$', self.text, re.M)
        self.out = []  # [(relation, column)] of the OUT form's sites, in written order
        for rel, body in re.findall(r'\((&[\w.]+)((?:[^()]|\([^()]*\))*)\)', m[1] if m else ''):
            self.out += [(rel, c) for c in re.findall(r'\^(\w+)', body)]
        self.tmp = Path(tempfile.mkdtemp(prefix='contracts-'))

    def run_engine(self, task_json, pin=None, *, all_assignments=False):
        """Read all entries from one native export and record unavailable assignment keys."""
        (self.tmp / (self.task + '.json')).write_text(json.dumps(task_json))
        settings = decode_settings()
        try:
            program = arclog.StudyProgram.from_sexp(self.text, settings)
            evaluator = arclog.StudyTaskEvaluator(self.task, str(self.tmp), settings, session_bytes=SESSION_BYTES)
            status, ct = evaluator.gold_tables(program, held_rows=True)
            status = json.loads(status)
            tb = CLI.Tables(arclog, np, program, ct, task_json)
            dropped = []
            for t, name in enumerate(tb.names):
                for entry in tb.by_table.get(t, []):
                    stops = []
                    for field in ('fault', 'stop_bound', 'value_stop_bound'):
                        value = tb.E[field][entry] if field in tb.E else None
                        if value is not None and not (isinstance(value, int) and value < 0):
                            stops.append('%s %s' % (field, value))
                    if stops:
                        dropped.append(dict(key=tb.entry_key(entry, t), relation=name, entry=int(entry), stops=stops))
            if ct.materialization_stop:
                dropped.append(dict(key=(), stop=ct.materialization_stop))
            tb.selection = dict(status=status.get('status'), mode='ordinary', dropped_assignments=dropped,
                                report=status)
        except (arclog.Refusal, ValueError) as error:
            raise RuntimeError(str(error)) from error
        if not all_assignments:
            needed = self.solving_key(tb, task_json) if pin is None else self.pinned_key(tb, pin)
            if needed is None:
                report = dict(tb.selection, selection='pinned' if pin is not None else 'solving')
                raise AssignmentUnavailable(report)
        if getattr(self, 'provenance', None) is None:
            self.provenance = PV.provenance(tb, self.text)
        return tb

    @staticmethod
    def retained(tb, key):
        """Every table has compatible entries and none is stopped at this key."""
        if any(consistent(item['key'], key) for item in tb.selection['dropped_assignments']):
            return False
        return all(any(consistent(other, key) for other in tb.assignments(t))
                   for t, name in enumerate(tb.names) if name)

    def read(self, tb, best):
        """{relation: {'columns': [(name, type, frame)], 'rows': {example: rows}}} at the assignment key best, or the first retained joint
        OUT key where best is None. Sets self.stored and self.stored_types to best's stored values. assignments counts the retained
        assignment keys, including keys that do not fit the train outputs."""
        if best is None:
            best = next(iter(self.output_keys(tb)), None)
        if best is None or not self.retained(tb, best):
            raise AssignmentUnavailable(dict(tb.selection, selection='compatible'))
        self.stored = None if best is None else {rel: rows for rel, rows, _ in best}
        self.stored_types = None if best is None else {rel: types for rel, _, types in best}
        out = {}
        retained = self.output_keys(tb)
        for t, name in enumerate(tb.names):
            if not name:
                continue
            types = tb.T['column_types'][t]
            cols = list(zip(tb.T['column_names'][t], types, tb.T['column_frames'][t]))
            ents = tb.entries(t)
            keys = [key for key in tb.assignments(t) if any(consistent(key, full) for full in retained)]
            key = next((k for k in keys if consistent(k, best)), None) if best is not None else (keys[0] if keys else ())
            if key is None:
                raise AssignmentUnavailable(dict(tb.selection, selection='compatible', relation=name))
            rows, counts, views = {}, {}, {}
            for entry, (ex, model, k, raw, stop) in zip(tb.by_table.get(t, []), ents):
                if k == key and model == 0:
                    if tb.counted(entry):
                        counts[ex] = int(tb.E['rows'][entry])
                        views[ex] = [(held, [[tb.value(t, types[c], v) for c, v in zip(held, r)] for r in vrows]) for held, vrows in tb.entry_views(entry, t)]
                    else:
                        rows[ex] = [[tb.value(t, ty, v) for ty, v in zip(types, r)] for r in raw]
            out[name] = dict(columns=cols, rows=rows, assignments=len(keys), **(dict(counts=counts, views=views) if counts else {}))
        return out

    def tables(self, task_json, pin=None, no_assignment=None, keep_run=False):
        """{relation: {'columns': [(name, type, frame)], 'rows': {example: rows}}} at the assignment that solves the train pairs, or, with pin
        ({stored relation: rows}), at the first complete assignment that gives those stored relations those rows. Raises RuntimeError if
        no required assignment has complete tables. no_assignment remains an accepted argument for existing callers. keep_run keeps the engine
        result for other_assignments."""
        tb = self.run_engine(task_json, pin=pin)
        self.missing = []
        best = self.solving_key(tb, task_json) if pin is None else self.pinned_key(tb, pin)
        if best is None:
            raise RuntimeError('retained tables contain no required assignment')
        if keep_run:
            self.last_run = (tb, best)
        return self.read(tb, best)

    def other_assignments(self, limit):
        """The tables at each retained assignment other than the one the last call of tables with keep_run read, or none where more than limit
        assignments are retained. Lets go of that call's engine result, which the tables of one assignment do not hold."""
        tb, best = self.last_run
        del self.last_run
        keys = [key for key in self.output_keys(tb) if key != best]
        if not keys or len(keys) >= limit:
            return []
        stored, types = self.stored, self.stored_types
        others = [self.read(tb, key) for key in keys]
        self.stored, self.stored_types = stored, types
        return others

    def tables_each(self, task_json, pin, limit):
        """([(assignment key, tables)], count): tables at retained joint OUT keys matching pin, up to limit, and the number retained.
        Unavailable assignments are recorded in the acquisition report."""
        tb = self.run_engine(task_json, all_assignments=True)
        self.missing = []
        keys = [k for k in self.output_keys(tb)
                if all(set(rows) == set(pin[rel]) for rel, rows, _ in k if rel in pin)]
        return [(k, self.read(tb, k)) for k in keys[:limit]], len(keys)

    def has_assignment(self, tb):
        return any(len(key) for key in self.output_keys(tb))

    def missing_pins(self, tb, pin):
        """The relations of pin whose rows no assignment key of the OUT relation's table gives."""
        keys = self.output_keys(tb)
        offered = {}
        for key in keys:
            for rel, rows, _ in key:
                offered.setdefault(rel, set()).add(frozenset(rows))
        return sorted(r for r, rows in pin.items() if frozenset(rows) not in offered.get(r, set()))

    def output_keys(self, tb):
        """Joint keys of every relation read by OUT, in written relation and native assignment order."""
        keys = [()]
        for rel in dict.fromkeys(rel for rel, _ in self.out):
            t = tb.find(rel)
            if t is None:
                return []
            joined = []
            for key in keys:
                for other in tb.assignments(t):
                    if consistent(other, key):
                        names = {name for name, _, _ in key}
                        merged = key + tuple(part for part in other if part[0] not in names)
                        if merged not in joined:
                            joined.append(merged)
            keys = joined
        return [key for key in keys if self.retained(tb, key)] if self.out else []

    def pinned_key(self, tb, pin):
        """The first retained joint OUT key matching every pin."""
        for key in self.output_keys(tb):
            have = {rel: rows for rel, rows, _ in key}
            if all(rel in have and set(have[rel]) == set(rows) for rel, rows in pin.items()):
                return key
        return None

    def solving_key(self, tb, task_json):
        """The first retained joint OUT key whose first model gives each primary train output. If none does, accept an assignment whose
        model set equals each train pair's tiebreak candidate. Parameters from every OUT relation participate in the key."""
        keys = self.output_keys(tb)
        for key in keys:
            if all(self.out_grid(tb, task_json, 'train/%d' % i, key) == pair['output'] for i, pair in enumerate(task_json['train'])):
                return key
        # A tiebreak is a set of valid grids, not an ordering of native models.
        if len({rel for rel, _ in self.out}) == 1 and any(pair.get('alt', {}).get('kind') == 'tiebreak' for pair in task_json['train']):
            t = tb.find(self.out[0][0])
            freeze = lambda grid: tuple(map(tuple, grid)) if grid is not None else None
            for key in keys:
                fits = True
                for i, pair in enumerate(task_json['train']):
                    ex = 'train/%d' % i
                    accepted = {freeze(pair['output'])}
                    alt = pair.get('alt', {})
                    if alt.get('kind') == 'tiebreak':
                        accepted.add(freeze(alt['grid']))
                    models = {model for e, model, k, _, stop in tb.entries(t) if e == ex and consistent(k, key) and not stop}
                    actual = {freeze(self.out_grid(tb, task_json, ex, key, model=model)) for model in models}
                    if actual != accepted:
                        fits = False
                        break
                if fits:
                    return key
        return None

    def out_grid(self, tb, task_json, ex, key, model=0):
        """The grid that OUT gives at ex and the joint key in one native model; None where it gives none."""
        cells = {}
        if len(self.out) == 1 or (len(self.out) >= 2 and self.out[0][0] == self.out[1][0]):
            t = tb.find(self.out[0][0])
            names = tb.T['column_names'][t]
            pc, cc = names.index(self.out[0][1]), names.index(self.out[1][1] if len(self.out) > 1 else names[-1])
            for entry, (e, m, k, raw, stop) in zip(tb.by_table.get(t, []), tb.entries(t)):
                if e == ex and consistent(k, key) and m == model and not stop:
                    for p, c in tb.read_columns(entry, t, [pc, cc], raw):
                        cells.setdefault(p, set()).add(c)
        else:
            tp, tc = tb.find(self.out[0][0]), tb.find(self.out[1][0])
            pn, cn = tb.T['column_names'][tp], tb.T['column_names'][tc]
            at_p, at_c = pn.index(self.out[0][1]), next(i for i, n in enumerate(cn) if n.split('.')[-1] == self.out[1][1] or n == self.out[1][1])
            ps = [r[0] for entry, (e, m, k, raw, s) in zip(tb.by_table.get(tp, []), tb.entries(tp)) if e in (ex, 'task') and m == model and consistent(k, key) and not s
                  for r in tb.read_columns(entry, tp, [at_p], raw)]
            cs = {r[0] for entry, (e, m, k, raw, s) in zip(tb.by_table.get(tc, []), tb.entries(tc)) if e in (ex, 'task') and m == model and consistent(k, key) and not s
                  for r in tb.read_columns(entry, tc, [at_c], raw)}
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
