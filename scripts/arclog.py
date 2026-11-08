#!/usr/bin/env python
"""Run an arclog program on a task and show its tables.

  uv run python scripts/arclog.py tables PROGRAM TASK [--case NAME] [--tasks DIR] [--runtime DIR]
  uv run python scripts/arclog.py rows PROGRAM TASK RELATION [--case NAME] [--assignment N] [--render ['LAYOUT']]
                                  [--tasks DIR] [--runtime DIR]

`tables` prints, as JSON, each case's tables with their columns and row counts, or why the case is refused. `rows` prints
the rows of one relation as JSON lines, one per example, model and assignment; it takes the concept case unless `--case`
names one, such as `$Mask` (a file with no ALTS has one case, `concept`). TASK is a task id under data/tasks/ or `--tasks`.

A Position, Box or Offset is `[t, b, l, r]`, its margins from the top, bottom, left and right edges of its frame. An Ident
is a label such as `a0`, with a letter of its own for each table, so labels of different tables do not correspond.

RELATION is a name, such as `&fg`, `&blocks.component` or `ex_input`, or arclog text placed before the case's OUT form:
atoms, as the body of `(RULE &query ...)`, or whole forms, of which the last is shown. The labels the text makes are the
columns, so `'(&fg *P)'` gives P alone. The checker refuses a literal, so to keep some rows, write a rule over other
relations.

`--render` draws one assignment (`--assignment N`, default 1) as text. LAYOUT is one argument of words:

  E     a block for each example; without E, every example in one block
  ^P    a grid on the cell column P; a second ^Q draws a grid of Q in each cell of P
  Col   a column whose values stand side by side in the innermost cell

An empty grid cell is `.`, and a cell that shows no column is `#`. For the relation that the case's OUT form reads, the
default layout is E, a grid on OUT's position column, and OUT's color column. For another relation, it is E, a grid on the
first column that can hold one, then every other column. Past 6000 characters the last words of the layout are dropped, and the header
names them.

`--runtime DIR` names another engine runtime that scripts/build_study_runtime.py built.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INNER = 'ARCLOG_PY_INNER'
BOX_TYPES = ('Position', 'Box', 'Offset')
LETTERS = 'abcdefghijklmnopqrstuvwxyz'
BUDGET = 6000
FORM_HEADS = ('(RULE', '(DET', '(INIT', '(RIGID_DET')
KIND = {0: 'task', 1: 'train', 2: 'test'}


def main_worktree():
    out = subprocess.run(['git', '-C', str(ROOT), 'worktree', 'list', '--porcelain'], capture_output=True, text=True).stdout
    return Path(out.split('\n', 1)[0].removeprefix('worktree ').strip())


def outer(argv):
    """Run this file again under the runtime's python, which holds the engine."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--runtime', type=Path)
    a, _ = ap.parse_known_args(argv)
    runtime = a.runtime or main_worktree() / 'work/lm/data-study/ast/run/runtime-272fa78fd'
    python = runtime / 'venv/bin/python'
    if not (runtime / 'ready.json').exists() or not python.exists():
        sys.exit('no built runtime at %s' % runtime)
    env = dict(os.environ, **{INNER: str(ROOT)})
    env.pop('PYTHONPATH', None)
    # -I keeps this file's folder off sys.path, where this file would stand for the engine's `arclog`.
    sys.exit(subprocess.call([str(python), '-I', '-B', os.path.abspath(__file__), *argv], env=env))


# ---- the engine's tables

COUNT = 1  # the kind of an entry that gives its row count alone


class Tables:
    """The tables of one case, read from the engine's CaseTables."""

    def __init__(self, arclog, np, program, ct, task_json):
        self.np = np
        self.T = ct.tables
        dt = ct.dtypes
        part = lambda name, cols: {k: (np.frombuffer(v, dt[f'{name}.{k}']) if isinstance(v, bytes) else v) for k, v in cols.items()}
        self.E = part('entries', ct.entries)
        self.A = part('assigned', ct.assigned)
        self.values = np.frombuffer(ct.values, np.int32) if isinstance(ct.values, bytes) else np.asarray(ct.values, np.int32)
        self.orient = dict(arclog.orientation_names())
        native = json.loads(program.render_json())['definitions']['native_relations']
        slots = [n.get('display_name') for n in native]
        rel = self.T['relation']
        rel = np.frombuffer(rel, dt['tables.relation']).tolist() if isinstance(rel, bytes) else list(rel)
        self.names = [self.T['fact'][i] if rel[i] < 0 else slots[rel[i]] for i in range(len(rel))]
        self.task = task_json
        self.by_table = {}
        for e, t in enumerate(self.E['table'].tolist()):
            self.by_table.setdefault(t, []).append(e)
        self.assigned = {}
        for i, e in enumerate(self.A['entry'].tolist()):
            self.assigned.setdefault(e, []).append(i)
        self.letters = {}
        for t in range(len(self.names)):
            if 'Ident' in self.T['column_types'][t]:
                self.letters[t] = LETTERS[len(self.letters) % 26]
        self.labels = {}

    def find(self, name):
        want = name if name.startswith('&') or name in ('ex_input', 'ex_output') else '&' + name
        hits = [t for t, n in enumerate(self.names) if n == want]
        return hits[-1] if hits else None

    def widths(self, types):
        return [4 if ty in BOX_TYPES else 1 for ty in types]

    def raw_rows(self, offset, n, types):
        w = sum(self.widths(types))
        flat = self.values[int(offset):int(offset) + n * w]
        out, starts = [], [0]
        for x in self.widths(types):
            starts.append(starts[-1] + x)
        for j in range(n):
            r = flat[j * w:(j + 1) * w]
            out.append([tuple(int(v) for v in r[starts[c]:starts[c + 1]]) if types[c] in BOX_TYPES else int(r[starts[c]])
                        for c in range(len(types))])
        return out

    def ident_label(self, t, v):
        lab = self.labels.setdefault(t, {})
        if v not in lab:
            lab[v] = '%s%d' % (self.letters.get(t, 'a'), len(lab))
        return lab[v]

    def value(self, t, ty, v):
        if ty in BOX_TYPES:
            return list(v)
        if ty == 'Ident':
            return self.ident_label(t, v)
        if v in self.orient and ty not in ('Number', 'Nat', 'Int', 'Color', 'Example'):
            return self.orient[v]
        return v

    def number_idents(self, t):
        """Label the table's Idents in the order of their raw ids, so that a label does not depend on what is shown."""
        types = self.T['column_types'][t]
        ids = set()
        for e in self.by_table.get(t, []):
            for r in self.raw_rows(self.E['offset'][e], int(self.E['rows'][e]), types):
                ids.update(r[c] for c, ty in enumerate(types) if ty == 'Ident')
        for v in sorted(ids):
            self.ident_label(t, v)

    def entry_key(self, e, t):
        """The assignment key of an entry, without decoding its row payload."""
        key = []
        for i in sorted(self.assigned.get(e, []), key=lambda i: int(self.A['det'][i])):
            d = int(self.A['det'][i])
            dtypes = self.T['det_types'][t][d]
            rows = self.raw_rows(self.A['offset'][i], int(self.A['rows'][i]), dtypes)
            key.append((self.T['det_relations'][t][d], tuple(tuple(tuple(v) if isinstance(v, tuple) else v for v in r) for r in rows), tuple(dtypes)))
        return tuple(key)

    def entries(self, t):
        """Each entry of table t as (example name, model, assignment key, raw rows, stop)."""
        types = self.T['column_types'][t]
        out = []
        for e in self.by_table.get(t, []):
            kind, idx = int(self.E['example_kind'][e]), int(self.E['example_index'][e])
            ex = 'task' if kind == 0 else '%s/%d' % (KIND[kind], idx)
            key = self.entry_key(e, t)
            stop = None
            for field in ('fault', 'stop_bound', 'value_stop_bound'):
                v = self.E[field][e] if field in self.E else None
                if v is not None and not (isinstance(v, (int,)) and v < 0):
                    stop = '%s %s' % (field, v)
                    if field == 'value_stop_bound' and 'value_stop_assignment' in self.E and self.E['value_stop_assignment'][e]:
                        stop = 'assignment stop %s' % v  # rejects this assignment alone; the other entries are not stopped
            rows = self.raw_rows(self.E['offset'][e], int(self.E['rows'][e]), types) if not stop and ('kind' not in self.E or int(self.E['kind'][e]) == 0) else []
            out.append((ex, int(self.E['model'][e]), tuple(key), rows, stop))
        return out

    def counted(self, entry):
        """Whether the entry gives its row count alone: the engine holds its rows as a product of parts too large to build."""
        return 'kind' in self.E and int(self.E['kind'][entry]) == COUNT

    def assignments(self, t):
        keys = []
        for entry in self.by_table.get(t, []):
            key = self.entry_key(entry, t)
            if key not in keys:
                keys.append(key)
        return keys

    def assignment_json(self, t, key):
        return {rel: [[self.value(t, ty, v) for ty, v in zip(dtypes, r)] for r in rows] for rel, rows, dtypes in key}


def grid_size(task_json, ex, frame):
    kind, _, idx = ex.partition('/')
    if kind not in ('train', 'test') or frame not in ('input', 'output'):
        return None
    pair = task_json[kind][int(idx)]
    g = pair.get(frame)
    return (len(g), len(g[0])) if g else None


# ---- render

def cell_of(v, ty, size):
    """The (row, col, V, H) of a cell value, or None where the value is not one cell."""
    t, b, l, r = v
    if ty == 'Position':
        return (t, l, t + b + 1, l + r + 1)
    if ty == 'Box' and size and size[0] - t - b == 1 and size[1] - l - r == 1:
        return (t, l, size[0], size[1])
    return None


def text_of(v):
    return '[%s]' % ','.join(str(x) for x in v) if isinstance(v, list) else str(v)


def render(rows, words):
    """The lines of rows (dicts of column -> (shown value, cell or None)) under layout words."""
    grids = [w[1:] for w in words if w.startswith('^')]
    cols = [w for w in words if not w.startswith('^')]
    if not grids:
        seen = sorted({tuple(text_of(r[c][0]) for c in cols) for r in rows})
        return [' '.join(s) for s in seen] if cols else ['#']
    g, rest = grids[0], ['^' + x for x in grids[1:]] + cols
    by_size = {}
    for r in rows:
        cell = r[g][1]
        by_size.setdefault(cell[2:], {}).setdefault(cell[:2], []).append(r)
    out = []
    for (V, H), at in sorted(by_size.items()):
        if len(by_size) > 1:
            out.append('(cells of a %dx%d frame)' % (V, H))
        blocks = {p: render(rs, rest) for p, rs in at.items()}
        w = [max([len(s) for (y, x), b in blocks.items() if x == col for s in b] + [1]) for col in range(H)]
        if all(len(b) == 1 for b in blocks.values()):
            out += [' '.join(blocks.get((y, x), ['.'])[0].ljust(w[x]) for x in range(H)).rstrip() for y in range(V)]
        else:
            for y in range(V):
                cells = [blocks.get((y, x), ['.']) for x in range(H)]
                for i in range(max(len(c) for c in cells)):
                    out.append('│'.join((c[i] if i < len(c) else '').ljust(w[x]) for x, c in enumerate(cells)).rstrip())
                if y < V - 1:
                    out.append('┼'.join('─' * w[x] for x in range(H)))
    return out


def view(tb, t, words, assignment, case):
    names = tb.T['column_names'][t]
    types = tb.T['column_types'][t]
    frames = tb.T['column_frames'][t]
    for w in words:
        c = w.lstrip('^')
        if c != 'E' and c not in names:
            sys.exit('%s is not a column of %s: %s' % (c, tb.names[t], ', '.join(names)))
    keys = tb.assignments(t)
    if not 1 <= assignment <= max(len(keys), 1):
        sys.exit('%s has %d assignments' % (tb.names[t], len(keys)))
    key = keys[assignment - 1] if keys else ()
    blocks = {}
    for ex, model, k, raw, stop in tb.entries(t):
        if k != key:
            continue
        rows = []
        for r in raw:
            d = {}
            for c, (n, ty) in enumerate(zip(names, types)):
                size = grid_size(tb.task, ex, frames[c])
                d[n] = (tb.value(t, ty, r[c]), cell_of(r[c], ty, size) if ty in BOX_TYPES else None)
            rows.append(d)
        for w in words:
            if w.startswith('^') and any(r[w[1:]][1] is None for r in rows):
                sys.exit('^%s: column %s holds values that are not one cell of their frame' % (w[1:], w[1:]))
        label = ex + (' model %d' % model if any(m != 0 for _, m, kk, _, _ in tb.entries(t) if kk == key) else '')
        blocks[label if 'E' in words else 'every example'] = blocks.get(label if 'E' in words else 'every example', []) + rows + ([{'stop': stop}] if stop else [])
    body_words = [w for w in words if w != 'E']

    def lines(ws):
        out = []
        for label, rows in blocks.items():
            stops = [r['stop'] for r in rows if 'stop' in r]
            rows = [r for r in rows if 'stop' not in r]
            out.append('%s  (%d rows)%s' % (label, len(rows), ''.join('  stopped: ' + s for s in stops)))
            out += ['  ' + s for s in (render(rows, ws) if rows else [])]
        return out

    shown, dropped = list(body_words), []
    out = lines(shown)
    while len('\n'.join(out)) > BUDGET and len(shown) > 1:
        dropped.insert(0, shown.pop())
        out = lines(shown)
    col_text = ', '.join('%s:%s%s' % (n, ty, ' [t,b,l,r]' if ty in BOX_TYPES else ' %s#' % tb.letters.get(t, 'a') if ty == 'Ident' else '')
                         for n, ty in zip(names, types))
    head = ['%s  case %s  (%s)' % (tb.names[t], case, col_text)]
    if len(keys) > 1:
        head.append('assignment %d of %d: %s' % (assignment, len(keys), json.dumps(tb.assignment_json(t, key))))
    head.append('layout: ' + ' '.join((['E'] if 'E' in words else []) + shown)
                + ('  (dropped, past %d characters: %s)' % (BUDGET, ' '.join(dropped)) if dropped else ''))
    return '\n'.join(head + out)


def default_words(tb, t, out=None):
    """The default layout of table t. `out` is (position column, color column) of the OUT form where t is the relation it reads."""
    if out:
        return ['E', '^' + out[0], out[1]]
    names, types = tb.T['column_names'][t], tb.T['column_types'][t]
    frames = tb.T['column_frames'][t]
    for c, (n, ty) in enumerate(zip(names, types)):
        if ty == 'Position' or (ty == 'Box' and frames[c] in ('input', 'output')):
            ok = True
            for ex, _, _, raw, _ in tb.entries(t):
                size = grid_size(tb.task, ex, frames[c])
                if any(cell_of(r[c], ty, size) is None for r in raw):
                    ok = False
                    break
            if ok:
                return ['E', '^' + n] + [x for x in names if x != n]
    return ['E'] + list(names)


# ---- commands

def load(a):
    import arclog
    import numpy as np
    program = Path(a.program)
    text = program.read_text()
    data = program.with_suffix('.arcdata')
    tasks = Path(a.tasks) if a.tasks else Path(os.environ[INNER]) / 'data/tasks'
    if not (tasks / (a.task + '.json')).exists():
        sys.exit('no task %s in %s' % (a.task, tasks))
    task_json = json.load(open(tasks / (a.task + '.json')))
    arcdata = data.read_text() if data.exists() else ';; %s\n' % a.task
    # The checker takes `arclog` for this file, which the runtime's python never imports.
    cases = arclog.case_files(a.task, text, arcdata, str(program.parent))  # pyright: ignore[reportAttributeAccessIssue]
    return arclog, np, cases, tasks, task_json


def pick_cases(cases, name):
    if name:
        hit = [c for c in cases if c.case == name]
        if not hit:
            sys.exit('no case %s; the cases are %s' % (name, ', '.join(c.case for c in cases)))
        return hit
    return cases


def run_case(arclog, np, c, task, tasks, task_json, query=None, *, settings=None):
    """(Tables, None) for a case, or (None, the reason it gives no tables). Uses the engine's defaults unless settings is supplied."""
    if c.arclog is None:
        return None, 'no case program: %s' % c.fault
    text = c.arclog
    if query:
        at = text.rfind('(OUT')
        text = (text[:at] + query + '\n\n' + text[at:]) if at >= 0 else text + '\n\n' + query + '\n'
    if settings is None:
        settings = arclog.DecodeSettings()
    try:
        program = arclog.StudyProgram.from_sexp(text, settings)
    except ValueError as e:
        return None, 'refused: %s' % e
    evaluator = arclog.StudyTaskEvaluator(task, str(tasks.resolve()), settings)
    # The runtime can hold an engine older than this file. Both arguments give each entry's rows; the newer one gives a large product as its parts.
    rows = 'held_rows' if 'held_rows' in type(evaluator).gold_tables.__text_signature__ else 'full_rows'
    status, ct = evaluator.gold_tables(program, **{rows: True})
    st = json.loads(status)
    if st.get('status') not in (None, 'complete'):
        return None, 'replay: %s' % st.get('status')
    return Tables(arclog, np, program, ct, task_json), None


def cmd_tables(a):
    arclog, np, cases, tasks, task_json = load(a)
    concept = [c for c in cases if getattr(c, 'concept', False)]
    for c in pick_cases(cases, a.case):
        tb, why = run_case(arclog, np, c, a.task, tasks, task_json)
        rec = {'case': c.case, 'concept': bool(getattr(c, 'concept', False))}
        if tb is None:
            rec['refused'] = why
        else:
            rec['tables'] = []
            for t, name in enumerate(tb.names):
                counts, stops = {}, {}
                for entry, (ex, model, key, raw, stop) in zip(tb.by_table.get(t, []), tb.entries(t)):
                    if key == (tb.assignments(t) or [()])[0]:
                        counts.setdefault(ex, []).append(int(tb.E['rows'][entry]) if tb.counted(entry) else len(raw))
                        if stop:
                            stops[ex] = stop
                columns = []
                for n, ty, f in zip(tb.T['column_names'][t], tb.T['column_types'][t], tb.T['column_frames'][t]):
                    columns.append({'name': n, 'type': ty, **({'frame': f} if f in ('input', 'output') else {})})
                table = {'relation': name, 'columns': columns, 'rows': counts, 'assignments': len(tb.assignments(t))}
                if stops:
                    table['stopped'] = stops
                rec['tables'].append(table)
        print(json.dumps(rec))


def cmd_rows(a):
    arclog, np, cases, tasks, task_json = load(a)
    concept = [c for c in cases if getattr(c, 'concept', False)]
    c = pick_cases(cases, a.case)[0] if a.case else (concept or cases)[0]
    rel = a.relation.strip()
    query = None
    if rel.startswith('('):
        query = rel if rel.startswith(FORM_HEADS) else '(RULE &query %s)' % rel
        forms = re.findall(r'\((?:RULE|DET|INIT|RIGID_DET) (&[\w]+)', query)
        rel = forms[-1] if forms else '&query'
    tb, why = run_case(arclog, np, c, a.task, tasks, task_json, query)
    if tb is None:
        sys.exit('case %s: %s' % (c.case, why))
    t = tb.find(rel)
    if t is None:
        sys.exit('no table for %s in case %s; the tables are %s' % (rel, c.case, ', '.join(n for n in tb.names if n)))
    tb.number_idents(t)
    if a.render is not None:
        m = re.search(r'^\(OUT \((&[\w.]+) \^(\w+) \^(\w+)\)\)', c.arclog or '', re.M)
        words = a.render.split() if a.render else default_words(tb, t, (m[2], m[3]) if m and tb.find(m[1]) == t else None)
        print(view(tb, t, words, a.assignment, c.case))
        return
    names, types = tb.T['column_names'][t], tb.T['column_types'][t]
    keys = tb.assignments(t)
    for entry, (ex, model, key, raw, stop) in zip(tb.by_table.get(t, []), tb.entries(t)):
        rec = {'solver': a.task, 'case': c.case, 'input': ex, 'relation': tb.names[t], 'model': model,
               'columns': [{'name': n, 'type': ty} for n, ty in zip(names, types)],
               'rows': [[tb.value(t, ty, v) for ty, v in zip(types, r)] for r in raw]}
        if tb.counted(entry):
            rec['product_of_parts'] = int(tb.E['rows'][entry])
        if key:
            rec['assignment'] = {'number': keys.index(key) + 1, 'of': len(keys), 'values': tb.assignment_json(t, key)}
        if stop:
            rec['stopped'] = stop
        print(json.dumps(rec))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ('tables', 'rows'):
        p = sub.add_parser(name)
        p.add_argument('program')
        p.add_argument('task')
        if name == 'rows':
            p.add_argument('relation')
            p.add_argument('--assignment', type=int, default=1)
            p.add_argument('--render', nargs='?', const='', default=None, metavar='LAYOUT')
        p.add_argument('--case')
        p.add_argument('--tasks')
        p.add_argument('--runtime', type=Path)
    a = ap.parse_args()
    {'tables': cmd_tables, 'rows': cmd_rows}[a.command](a)


if __name__ == '__main__':
    if not os.environ.get(INNER):
        if any(x in ('-h', '--help') for x in sys.argv[1:]):
            print(__doc__)
            sys.exit(0)
        outer(sys.argv[1:])
    main()
