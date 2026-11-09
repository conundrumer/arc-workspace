#!/usr/bin/env python
"""One task's Candidate tables, for the generator's lists.

  <runtime python> -u -I -B tables_worker.py ROOT TASK

It draws each query's mutants as the first run did, and also draws argument edits whose query has
gold's structure, marked `extra`. It keeps the mutants and the tables' train rows under ROOT as zstd,
and prints to stdout the tables with their test rows too, as the framed stream of typed column arrays that tables_columns.py writes. Test rows go nowhere else, so a caller
reads them from the pipe and keeps none of them. A table has all its rows at each example, except where the engine stopped its evaluation: that entry has no rows. On a fault it prints only the fault's type.
"""
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path('/Users/davidlu/code/arc-workspace')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_structure import Reader, parse_forms, query_features, relation_of  # noqa: E402
sys.path.insert(0, str(REPO / 'src'))
from arclog_convert.readback import read_checked  # noqa: E402  the corpus is a gen/ directory

CORPUS = REPO / 'programs/arclog'
TASKS = REPO / 'data/tasks'
PER_QUERY = 5
PER_QUERY_EXTRA = 12
TRIES_EXTRA = 400
SEED = 'arc-feature-eval-1'
BUDGET = float(os.environ.get('CANDIDATE_ALL_BUDGET', '120'))
BUDGET_EXTRA = float(os.environ.get('CANDIDATE_EXTRA_BUDGET', '60'))
NAME = re.compile(r'&[A-Za-z0-9_]+')


def split_of(task):
    for line in (REPO / 'work/lm/data-study/samples/split.tsv').read_text().splitlines()[1:]:
        name, part, _ = line.split('\t')
        if name == task:
            return part
    raise ValueError('no split')


def keep(path, value):
    """Writes `value` as zstd JSON, with the rows of each Block as lists."""
    from tables_columns import json_default
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    subprocess.run(['zstd', '-q', '-f', '-o', str(temporary)], input=json.dumps(value, default=json_default).encode(), check=True, stderr=subprocess.DEVNULL)
    os.replace(temporary, path)


def entries_as_arrays(tb, t):
    """Each entry of table t as (example name, model, assignment key, rows, stop), with the rows as a numpy array of one line per row, as
    `tb.entries` gives them as lists. A Position, a Box and an Offset take four numbers."""
    import numpy as np
    types = tb.T['column_types'][t]
    stride = sum(tb.widths(types))
    kinds = {0: 'task', 1: 'train', 2: 'test'}
    out = []
    for e in tb.by_table.get(t, []):
        kind, idx = int(tb.E['example_kind'][e]), int(tb.E['example_index'][e])
        ex = 'task' if kind == 0 else '%s/%d' % (kinds[kind], idx)
        key = tb.entry_key(e, t)
        stop = None
        for field in ('fault', 'stop_bound', 'value_stop_bound'):
            v = tb.E[field][e] if field in tb.E else None
            if v is not None and not (isinstance(v, (int,)) and v < 0):
                stop = '%s %s' % (field, v)
                if field == 'value_stop_bound' and 'value_stop_assignment' in tb.E and tb.E['value_stop_assignment'][e]:
                    stop = 'assignment stop %s' % v  # rejects this assignment alone; the other entries are not stopped
        if not stop and ('kind' not in tb.E or int(tb.E['kind'][e]) == 0):
            rows, offset = int(tb.E['rows'][e]), int(tb.E['offset'][e])
            raw = tb.values[offset:offset + rows * stride].reshape(rows, stride)
        else:
            raw = np.empty((0, stride), np.int32)
        out.append((ex, int(tb.E['model'][e]), tuple(key), raw, stop))
    return out


def read_table(tb, name, prefer=None, sources=False):
    """A table at one assignment, the preferred one where the table has it and the least otherwise, or a reason it can't be read.

    An example keeps all its rows, and an entry that the engine stopped has none. A `rows` or `models` value holds each TableRows as a Block, of `tables_columns.py`.
    """
    from tables_columns import Block, Layout
    if name not in tb.names:
        return None, 'no table'
    t = tb.names.index(name)
    by_key = {}
    stopped = False
    for ex, model, key, raw, stop in entries_as_arrays(tb, t):
        if stop:
            stopped = True
            continue
        by_key.setdefault(repr(key), {}).setdefault(ex, {}).setdefault(model, raw)
    # The contract's `distinct`: how many assignments give different rows.
    contents = {hash(tuple(sorted((ex, tuple(sorted((model, (len(raw), hash(raw.tobytes()))) for model, raw in held.items()))) for ex, held in rows.items()))) for rows in by_key.values()} if len(by_key) > 1 else set(by_key)
    if not by_key:
        return None, 'stopped' if stopped else 'no rows at any assignment'
    chosen = prefer if prefer in by_key else min(by_key)
    by_example = by_key[chosen]
    types = list(tb.T['column_types'][t])
    layout = Layout(types, tb.orient)

    out, models = {}, {}
    # Each example's count of rows, the greatest over its constraint models.
    counts = {ex: max(len(raw) for raw in held.values()) for ex, held in by_example.items() if held}
    for ex, held in by_example.items():
        written = [Block(layout, raw.copy()) for raw in held.values()]
        if len(written) == 1:
            out[ex] = written[0]
        else:
            models[ex] = written
    names = list(tb.T['column_names'][t]) if 'column_names' in tb.T else [f'c{i}' for i in range(len(types))]
    if sources:
        held = tb.T['column_ident_sources'][t]
        types = [f'{ty}@{source}' if ty == 'Ident' and source else ty for ty, source in zip(types, held)]
    return dict(columns=names, types=types, assignments=len(by_key), distinct_assignments=len(contents), capped=stopped, assignment=chosen, task_level='task' in out or 'task' in models, row_counts=counts, rows=out, models=models), None


def worker(root, task):
    import numpy as np
    import arclog
    split = split_of(task)
    if split not in ('train', 'dev'):
        raise ValueError('not a train or dev task')
    spec = importlib.util.spec_from_file_location('arclog_script', REPO / 'scripts/arclog.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    data = CORPUS / (task + '.arcdata')
    cases = arclog.case_files(task, read_checked(CORPUS / (task + '.arclog')), read_checked(data) if data.exists() else '', str(CORPUS))
    c = [x for x in cases if x.concept][0]
    settings = arclog.DecodeSettings()
    gold = arclog.StudyProgram.from_sexp(c.arclog, settings)
    task_json = json.loads((TASKS / (task + '.json')).read_text())
    train = len(task_json['train'])
    test = len(task_json['test'])
    ev = arclog.StudyTaskEvaluator(task, str(TASKS), settings)
    rows_option = {'held_rows': True}
    status, gct = ev.gold_tables(gold, **rows_option)
    gtb = script.Tables(arclog, np, gold, gct, task_json)
    gold_forms = parse_forms(c.arclog)

    def rows(tb, names):
        out = {}
        for name in names:
            t = tb.names.index(name) if name in tb.names else None
            if t is None:
                continue
            for ex, model, key, raw, stop in tb.entries(t):
                out.setdefault((name, ex), set()).update(repr(r) for r in raw)
        return out

    read = read_table

    def train_rows(table):
        keep = lambda held: {k: v for k, v in held.items() if k == 'task' or k.startswith('train/')}
        return dict(rows=keep(table['rows']), models=keep(table['models']))

    nodes = {tuple(n['path']): n for n in json.loads(gold.render_json())['nodes']}

    def form_name(index):
        d = nodes.get((index,), {}).get('data', {})
        n = (d.get('defines') or {}).get('name') or d.get('name')
        return n.get('name') if isinstance(n, dict) else n

    by_form, points, extra_specs = {}, {}, {}
    for p in gold.points():
        form = p.clause_path[0]
        try:
            specs, _ = gold.draw_specs(p, 1, 5000, 0, operation='mixed', source_revision=SEED, task=task, case=c.case)
        except arclog.Refusal:
            continue
        by_form.setdefault(form, []).extend(specs)
        points.setdefault(form, set()).add(p.kind)
    rng = random.Random(f'{SEED}.{task}')
    state = {}
    gold_reads = {}
    for form in sorted(by_form):
        name = form_name(form)
        names = [n for n in gtb.names if n and name and (n == name or n.startswith(name + '.'))]
        specs = list(by_form[form])
        rng.shuffle(specs)
        state[form] = dict(name=name, names=names, gold_rows=rows(gtb, names), specs=specs, at=0, kept=[], reads=[], same=0, failed=0)
        for n in names:
            gold_reads.setdefault(n, read(gtb, n))

    def evaluate(q, m, extra):
        """Keeps a mutant whose tables differ from gold's at a train pair."""
        program = m.as_program()
        try:
            st, ct = ev.gold_tables(program, **rows_option)
            tb = script.Tables(arclog, np, program, ct, task_json)
            mrows = rows(tb, q['names'])
        except Exception:
            q['failed'] += 1
            return False
        differs = sorted({e for e in range(train) for n in q['names'] if mrows.get((n, f'train/{e}')) != q['gold_rows'].get((n, f'train/{e}'))})
        if not differs:
            q['same'] += 1
            return False
        edits = json.loads(m.identity_json).get('edits', [])
        q['kept'].append(dict(edit=edits[0].get('kind') if edits else None, differs_at_train=differs, status=json.loads(st).get('status'), text=m.sexp(), extra=extra))
        held = {}
        for n in q['names']:
            g = gold_reads[n][0]
            if g is not None:
                held[n] = read(tb, n, g['assignment'])
        q['reads'].append(held)
        return True

    start = time.time()
    cut = False
    live = list(state)
    while live and not cut:
        for form in list(live):
            q = state[form]
            while True:
                if time.time() - start > BUDGET:
                    cut = True
                    break
                if len(q['kept']) == PER_QUERY or q['at'] >= len(q['specs']):
                    live.remove(form)
                    break
                s = q['specs'][q['at']]
                q['at'] += 1
                if evaluate(q, gold.construct(s), False):
                    break
            if cut:
                break
    # The argument edits that leave the query's structure as gold's has it.
    started_extra = time.time()
    for form, q in state.items():
        wanted = query_features(gold_forms, form, gold_forms)
        found = tries = 0
        for s in q['specs'][q['at']:]:
            if found >= PER_QUERY_EXTRA or tries >= TRIES_EXTRA or time.time() - started_extra > BUDGET_EXTRA:
                break
            tries += 1
            m = gold.construct(s)
            edits = json.loads(m.identity_json).get('edits', [])
            if not edits or edits[0].get('kind') != 'argument':
                continue
            forms = parse_forms(m.sexp())
            if len(forms) != len(gold_forms) or query_features(forms, form, gold_forms) != wanted:
                continue
            if evaluate(q, m, True):
                found += 1
    queries = [dict(form=form, name=q['name'], tables=q['names'], kinds=sorted(points[form]), drawn=len(q['specs']), same_table=q['same'], failed=q['failed'], mutants=q['kept']) for form, q in state.items()]
    keep(Path(root) / split / 'mutants' / (task + '.json.zst'), dict(task=task, case=c.case, gold=c.arclog, gold_status=json.loads(status).get('status'), budget_cut=cut, queries=queries))
    def parents_of(forms, form, own):
        """The tables of the prefix that a query's form reads."""
        reader = Reader()
        reader.form(forms[form])
        return sorted({read for read in reader.reads if read in gtb.names and read not in own})

    prefix = {}

    def with_parents(names):
        for name in names:
            if name not in prefix:
                table, _ = read(gtb, name)
                prefix[name] = table
        return [name for name in names if prefix[name] is not None]

    items, kept_items, left_out = [], [], []
    for form, q in state.items():
        if not q['kept']:
            continue
        for name in q['names']:
            g, why = gold_reads[name]
            if g is None:
                left_out.append(dict(query=q['name'], table=name, why=why))
                continue
            mutants = []
            for at, (m, held) in enumerate(zip(q['kept'], q['reads'])):
                t, why = held[name]
                if t is None:
                    left_out.append(dict(query=q['name'], table=name, mutant=at, why='mutant: ' + why))
                elif train_rows(t) != train_rows(g):
                    parents = with_parents(parents_of(parse_forms(m['text']), form, q['names']))
                    mutants.append(dict(mutant=at, edit=m['edit'], extra=m['extra'], table=t, parents=parents))
            if mutants:
                items.append(dict(query=q['name'], form=form, table=name, gold=g, parents=with_parents(parents_of(gold_forms, form, q['names'])), mutants=mutants))
                strip = lambda t: {**t, **train_rows(t)}
                kept_items.append(dict(query=q['name'], form=form, table=name, gold=strip(g), mutants=[{**m, 'table': strip(m['table'])} for m in mutants]))
    last = [q['name'] for q in state.values()][-1] if state else None
    head = dict(task=task, case=c.case, train=train, last_query=last, budget_cut=cut, left_out=left_out)
    keep(Path(root) / split / 'candidate-tables' / (task + '.json.zst'), dict(head, items=kept_items))
    # Test rows leave by the pipe alone.
    from tables_columns import write_stream
    write_stream(dict(head, test=test, items=items, prefix={name: table for name, table in prefix.items() if table is not None}))


if __name__ == '__main__':
    try:
        worker(sys.argv[1], sys.argv[2])
    except Exception as error:
        sys.stderr.write(type(error).__name__ + '\n')
        sys.exit(1)
