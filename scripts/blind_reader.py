#!/usr/bin/env python3
"""The blind reader: `scripts/arclog.py` for a task whose grids the caller may not see.

The blind reader tests whether an ARC task can be solved from features alone. An arclog agent, the tester, writes arclog
queries for a task and sees only the features of the tables those queries make. It never sees a grid, a table row, a row
value or the task's id. Each thing the tester must work around, such as a table that it writes by hand to get a number, points
at a feature that is missing.

Setting up: `scripts/blind_reader_setup.py` makes two folders for a list of tasks: one that the tester may see, and one
that it must not. The tester's folder holds a command, `arclog.py`, which runs this file, and an empty starting program
for each task alias (T1, T2, ...). The internal folder holds the alias map, the task files, the encoder and the files that a
run writes. This file finds the internal folder from the file `setting` in the tester's folder, which holds its path.
Give the tester the tester folder and nothing else. Nothing that this file prints holds a task id, a grid, a row value or
a path into the internal folder.

Running: the tester runs the commands below on `arclog.py` in the tester's folder, with a task alias as TASK. To test a
change to the features, run the same programs again after the encoder is rebuilt, with `--all` on the first `tables`.

The commands
  python3 arclog.py tables PROGRAM TASK [--case NAME] [--all] [--shapes] [--wide]
  python3 arclog.py rows PROGRAM TASK RELATION [--case NAME] [--assignment N] [--shapes] [--wide]

`tables` is scripts/arclog.py's: JSON with each table's columns and row counts at each example, at the table's assignment 1.
It then gives the solves lines, then the features of each table and query not yet shown for this task, or of all of them with
`--all`. `rows` takes RELATION as scripts/arclog.py does: a name, or arclog text placed before the OUT form, either atoms or
whole forms. It gives the relation's columns and its row counts at the assignment shown, with that assignment's number, in
place of its rows, then the solves lines, then its features, then the features of any query not yet shown.

A solves line is printed for each case, such as `solves: assignment 6: 4 of 4; others: 0 to 2 of 4`. For each assignment of the
case's parameters, it counts the train pairs that the case's OUT solves, as the engine's judge decides it (`gold_kept` of
the engine's `StudyTaskEvaluator`, the check that a `DET` that names a proposer applies). The numbers count the program's
assignments, in the order of a table that reads every parameter. The line then says whether the determination leaves exactly
one assignment, which, or how many. It holds counts and numbers alone.

Features are sparse: an entry at its default is left out.
- A table's section is `## TABLE`, with lines `VALUE<tab>SHAPE`. VALUE is the entry's value at each train example, as
  `a | b | c`, or one value where they agree. Where the shape's greatest and sum differ, it is `greatest,sum`. A fraction
  is `top/bottom`. `?` is no value: a bound on the walk stopped it, a value set does not have exactly one member, or a ratio has no rows below it. `test:` says whether each test input has a value.
  A shape's `T` is the table.
- `## TABLE task-wide` gives the shapes that read all examples at once, with one value each. Their names are long, and a table
  can have hundreds, so a run gives the count of them and the count of values, and `--wide` lists them, last.
- `## input`, `## ex_output` and `## pair` give the features of the input grids, the example outputs and the pairs.
- Entries with one value vector are one line, which names the first two shapes and the count of the others; `--shapes` lists
  them. Entries whose value is 0 or 1 at every example stay apart, since each states a claim of its own.
- A table with the features of a table already shown is one line that names that table.
- `## query HASH` gives the query's features, then its features against each table it uses.
- Features read the concept case, or the case of `--case`, at the assignment shown. That is `--assignment N`, counted from 1 in
  the table's own assignments; without it, the first assignment that solves every train pair, or assignment 1 where none does.
  A table that reads fewer parameters has fewer assignments, and shows the first of them that agrees with the solving
  assignment. A table with several assignments gives `N<tab>assignment shown`.
"""
import argparse, ast, hashlib, json, os, re, signal, subprocess, sys
from pathlib import Path

HEADS = ('(RULE', '(DET', '(INIT', '(RIGID_DET')
# The shape size. The learned model's shape columns use size 2, which can print megabytes a run; size 1 is the default.
SIZE = '1'
BASE = ('ex_input', 'ex_output', 'input', 'output')
TIMEOUT = float(os.environ.get('BLIND_READER_TIMEOUT', '170'))
INNER = 'BLIND_READER_INNER'
RUNTIME = 'work/lm/data-study/ast/run/runtime-272fa78fd'
CFG = {}
OUT = []


def configure(setting):
    internal = Path(Path(setting).read_text().strip()).resolve()
    cfg = json.loads((internal / 'config.json').read_text())
    CFG.update(internal=str(internal), here=str(Path(setting).resolve().parent), root=cfg['repo'], encoder=cfg['encoder'],
               runtime=cfg.get('runtime'), tasks=str(internal / 'tasks'), run=str(internal / 'run'),
               ids=list(json.loads((internal / 'map.json').read_text()).items()))


def clean(s):
    """Text without the internal folder's path, the tester's folder's path, the repo's path or a task id."""
    s = s.replace(CFG['internal'], '<internal>').replace(CFG['here'], '<here>').replace(CFG['root'], '<repo>')
    for alias, task in CFG['ids']:
        s = s.replace(task, alias)
    return s


def say(text=''):
    OUT.append(text)


def run(cmd, cwd):
    """The process's result, with every process of its group killed at the timeout."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, start_new_session=True)
    try:
        out, err = p.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        return subprocess.CompletedProcess(cmd, 124, out, err + 'timed out after %g s\n' % TIMEOUT)
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def tool(*a):
    runtime = ['--runtime', CFG['runtime']] if CFG['runtime'] else []
    return run([sys.executable, CFG['root'] + '/scripts/arclog.py', *a, '--tasks', CFG['tasks'], *runtime], CFG['root'])


def encoder(*a):
    return run([CFG['encoder'], *a], CFG['root'])


def fault(r):
    """The last two lines of a failed run's output."""
    return clean(' '.join((r.stderr + r.stdout).splitlines()[-2:]))[:400]


def shown(r):
    """A run's output, with a traceback cut to its last line."""
    err = r.stderr.rstrip('\n')
    if 'Traceback (most recent call last)' in err:
        err = err.splitlines()[-1]
    return (r.stdout + err).rstrip('\n')


def placed(program, task, relation=None):
    """The program in a file named for the encoder, with RELATION's text before OUT, and the relation's name."""
    text = open(program).read()
    name = relation
    if relation and relation.lstrip().startswith('('):
        q = relation.strip()
        if not q.startswith(HEADS):
            q = f'(RULE &query {q})'
        name = re.findall(r'\((?:RULE|DET|INIT|RIGID_DET)\s+(&\w+)', q)[-1]
        at = text.rfind('(OUT')
        text = text[:at] + q + '\n\n' + text[at:]
    d = f"{CFG['run']}/{task}"
    os.makedirs(d, exist_ok=True)
    open(f'{d}/{task}.arclog', 'w').write(text)
    data = Path(program).with_suffix('.arcdata')
    if data.exists():
        open(f'{d}/{task}.arcdata', 'w').write(data.read_text())
    return f'{d}/{task}.arclog', d, name


def number(n):
    return str(n) if isinstance(n, int) else f'{n[0]}/{n[1]}'


def one(x):
    """One slot: 0 at its default, null where a bound stopped it, else [greatest, sum]."""
    if x is None:
        return '?'
    if x == 0:
        return '0'
    return number(x[0]) if x[0] == x[1] else f'{number(x[0])},{number(x[1])}'


def value(at, train):
    vals = [one(x) for x in at[:train]]
    text = vals[0] if len(set(vals)) == 1 else ' | '.join(vals)
    if len(at) > train:
        text += '  test: ' + ','.join('?' if x is None else 'has' if x != 0 else 'none' for x in at[train:])
    return text


def matching(blocks, target):
    """The number of the first block whose assignment agrees with TARGET, a dict of relation to sorted rows, or None."""
    if target is None:
        return None
    for number, (label, _, _) in enumerate(blocks, 1):
        try:
            key = ast.literal_eval(label)
        except (ValueError, SyntaxError):
            return None
        if all(relation in target and target[relation] == sorted(rows) for relation, rows in key):
            return number
    return None


def read_vector(path, want, target=None):
    """(the lines of an assignment, its task-wide lines, the table's AssignmentVector, its number), or an error text.

    A table's file holds, for each assignment, a block of per-example entries and a block of task-wide entries, and then
    the AssignmentVector's line, which a block of pool entries can follow. The assignment is number WANT, or, where WANT is
    None, the first one that agrees with TARGET, and assignment 1 where none does.
    """
    blocks, wide, pool, now = [], {}, None, None
    for l in open(path):
        d = json.loads(l)
        if 'assignment_vector' in d:
            pool, now = d, None
        elif 'task_wide' in d:
            now = wide.setdefault(d['assignment'], [])
        elif 'table' in d:
            blocks.append((d['table']['assignment'], d['train'], []))
            now = blocks[-1][2]
        elif 'shape' in d and now is not None:
            if 'at' in d:
                now.append((d['size'], d['shape'], value(d['at'], blocks[-1][1])))
            else:
                now.append((len(d['shape']), d['shape'].removeprefix('task '), one(d['value'])))
    if want is None:
        want = matching(blocks, target) or 1
    if not 1 <= want <= len(blocks):
        return f'no assignment {want}; the table has {len(blocks)}', None, pool, None
    label, _, entries = blocks[want - 1]
    text = lambda es: [f'{v}\t{s}' for _, s, v in sorted(es)]
    return text(entries), text(wide.get(label, [])), pool, want


def table_section(task, corpus, name, assignment, target=None):
    """(lines, task-wide lines, pool, the number of the assignment shown, None where there is none) of a table."""
    out = f'{corpus}/v-{hashlib.sha1(name.encode()).hexdigest()[:10]}.jsonl'
    if os.path.exists(out):
        os.remove(out)
    r = encoder('vector', task, name, '--size', SIZE, '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
    if not os.path.exists(out):
        return [';; no vector: ' + fault(r)], [], None, None
    lines, wide, pool, number = read_vector(out, assignment, target)
    if isinstance(lines, str):
        return [';; ' + lines], [], pool, None
    head = []
    if pool and pool.get('count', 1) != 1:
        head = [f"{pool['count']}\tassignments", f"{number}\tassignment shown", f"{pool['distinct']:.3g}\tdistinct tables over assignments"] + (['true\tcapped'] if pool.get('capped') else [])
    return head + lines, wide, pool, number


def base_sections(task, corpus):
    out = corpus + '/b.jsonl'
    if os.path.exists(out):
        os.remove(out)
    r = encoder('base-vectors', task, '--size', SIZE, '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
    if not os.path.exists(out):
        return {'base': [';; no vector: ' + fault(r)]}
    res, name, train = {}, None, 0
    for l in open(out):
        d = json.loads(l)
        if 'shape' in d:
            res[name].append(f"{value(d['at'], train)}\t{d['shape']}")
        elif 'table' in d:
            name, train = d['table'].get('base', str(d['table'])), d['train']
            res[name] = []
    return res


def query_sections(task, corpus):
    out = corpus + '/q.jsonl'
    if os.path.exists(out):
        os.remove(out)
    r = encoder('query-vectors', task, '--size', SIZE, '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
    if not os.path.exists(out):
        return {}, ';; no query vectors: ' + fault(r)
    res = {}
    for l in open(out):
        d = json.loads(l)
        q = d['query'][:8]
        lines = [f'{v:g}\t{n}' for n, v in zip(d['names'], d['values']) if v]
        for use, vals in d['per_use']:
            used = use[:8] if re.fullmatch(r'[0-9a-f]{32}', use) else use
            lines += [f'{v:g}\tagainst {used}: {n}' for n, v in zip(d['use_names'], vals) if v]
        for name, cols in d['column_origin']:
            for ty, sources in cols:
                src = ', '.join(s[:8] if re.fullmatch(r'[0-9a-f]{32}', s) else s for s in sources) or 'new'
                lines.append(f'{ty}\tcolumn from {src}')
        res[q] = lines
    return res, ''


def inner(argv):
    """In the engine's python: for each case, the engine's judge result at each assignment, as JSON lines.

    This reuses `gold_kept` of the engine's `StudyTaskEvaluator`, which keeps the assignments at which the case's OUT solves
    every train pair, as docs/engine/cases.md#solves gives, and reports each assignment's result at each train pair.
    """
    import importlib.util
    sys.dont_write_bytecode = True
    program, task, tasks, case = argv
    spec = importlib.util.spec_from_file_location('arclog_script', os.environ['ARCLOG_PY_INNER'] + '/scripts/arclog.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    arclog, _, cases, tasks_dir, _ = script.load(argparse.Namespace(program=program, task=task, tasks=tasks))
    for c in script.pick_cases(cases, case):
        rec = {'case': c.case, 'concept': bool(getattr(c, 'concept', False))}
        try:
            if c.arclog is None:
                rec['error'] = 'no case program'
            else:
                settings = arclog.DecodeSettings()
                gold = arclog.StudyProgram.from_sexp(c.arclog, settings)
                evaluator = arclog.StudyTaskEvaluator(task, str(tasks_dir.resolve()), settings)
                report = json.loads(evaluator.gold_kept(gold))
                rec['complete'] = bool(report.get('observation_complete'))
                if report.get('status') == 'fault':
                    rec['error'] = 'the determination faulted'
                rec['assignments'] = [{'fits': [bool(p.get('fits')) for p in x.get('train', [])], 'key': x.get('assignment', [])}
                                      for x in report.get('gold_assignments', [])]
        except Exception as e:
            rec['error'] = f'{type(e).__name__}: {e}'
        print(json.dumps(rec))


def solve_records(file, task, case):
    """(each case's judge result at each assignment, or None, and the reason for None)."""
    runtime = Path(CFG['runtime'] or Path(CFG['root']) / RUNTIME)
    python = runtime / 'venv/bin/python'
    if not (runtime / 'ready.json').exists() or not python.exists():
        return None, 'no built runtime'
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    env.update({'ARCLOG_PY_INNER': CFG['root'], INNER: '1'})
    cmd = [str(python), '-I', '-B', os.path.abspath(__file__), file, task, CFG['tasks'], case or '']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=CFG['root'], env=env, start_new_session=True)
    try:
        out, err = p.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return None, 'timed out after %g s' % TIMEOUT
    records = []
    for line in out.splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            pass
    if p.returncode or not records:
        return None, fault(subprocess.CompletedProcess(cmd, p.returncode, out, err))
    return records, ''


def range_text(counts, pairs):
    return f'{counts[0]} of {pairs}' if min(counts) == max(counts) else f'{min(counts)} to {max(counts)} of {pairs}'


def solve_lines(records, why):
    """One line per case: how many train pairs the case's OUT solves at each assignment, and what the determination leaves.

    Each count is the engine's judge result. A line gives counts and assignment numbers, and no grid, row or value.
    """
    if records is None:
        return [f'solves: not available: {why}']
    lines = []
    for rec in records:
        label = 'solves' if len(records) == 1 else f"solves, case {rec['case']}"
        if rec.get('error'):
            lines.append(f"{label}: not available: {rec['error'][:200]}")
            continue
        found = [sum(x['fits']) for x in rec['assignments']]
        if not found:
            lines.append(f'{label}: no assignment was reached' + ('' if rec['complete'] else '; the walk stopped'))
            continue
        pairs = max(len(x['fits']) for x in rec['assignments'])
        at = lambda k: [i for i, n in enumerate(found, 1) if n == k]
        listed = lambda ns: ('assignments ' if len(ns) > 1 else 'assignment ') + ', '.join(map(str, ns))
        full = at(pairs)
        best = pairs if full else max(found)
        parts = [f'{listed(at(best))}: {best} of {pairs}' if full else f'no assignment solves all {pairs}; most: {listed(at(best))}: {best} of {pairs}']
        rest = [n for n in found if n < best]
        if rest:
            parts.append('others: ' + range_text(rest, pairs))
        if len(full) == 1:
            left = f'The determination leaves exactly one assignment: {full[0]}.'
        elif full:
            left = f'The determination leaves {len(full)} assignments: {", ".join(map(str, full))}.'
        else:
            left = 'The determination leaves no assignment.'
        stopped = '' if rec['complete'] else ' The walk stopped before its end, so more assignments may exist.'
        lines.append(f"{label}: {'; '.join(parts)}. {left}{stopped}")
    return lines


def default_target(records, case):
    """The first assignment that solves every train pair in the case that the features read, as relation to sorted rows."""
    for rec in records or []:
        if rec.get('concept') or case:
            for x in rec.get('assignments', []):
                if x['fits'] and all(x['fits']):
                    return {k['relation']: sorted(k['rows']) for k in x['key'] if k.get('rows') is not None}
            return None
    return None


def row_counts(file, a, name, number):
    """(the row counts at each example of the table's assignment NUMBER, in arclog.py's numbering), or (None, the reason)."""
    r = tool('rows', file, a.task, name, *(['--case', a.case] if a.case else []))
    if r.returncode:
        return None, fault(r)
    counts = {}
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if 'input' in d and d.get('assignment', {}).get('number', number) == number:
            counts.setdefault(d['input'], []).append(d.get('product_of_parts', len(d['rows'])))
    return counts, ''


class Seen:
    """The sections already shown for a task, by the hash of their lines."""

    def __init__(self, corpus, reset):
        self.path = corpus + '/seen.json'
        self.d = {} if reset or not os.path.exists(self.path) else json.load(open(self.path))

    @staticmethod
    def hashed(lines):
        return hashlib.sha1('\n'.join(lines).encode()).hexdigest()

    def new(self, key, lines):
        h = self.hashed(lines)
        if self.d.get(key) == h:
            return False
        self.d[key] = h
        return True

    def twin(self, key, lines, kinds=('table', 'base')):
        """Another section of one of the kinds, already shown with these lines."""
        h = self.hashed(lines)
        return next((k.split(' ', 1)[1] for k, v in self.d.items() if v == h and k != key and k.split(' ', 1)[0] in kinds), None)

    def save(self):
        json.dump(self.d, open(self.path, 'w'))


def is_flag(v):
    """A value of 0 or 1 at every example. Equal flags state different claims, so they stay apart."""
    return re.split(r'\s+test:', v)[0].strip() in ('0', '1', 'true', 'false')


def classed(lines, shapes):
    """Entries with one value vector, as one line that names the first two shapes and the count of the others."""
    if shapes:
        return lines
    groups, out = {}, []
    for l in lines:
        v, _, shape = l.partition('\t')
        if shape.startswith('(') and not is_flag(v):
            groups.setdefault(v, []).append(shape)
    done = set()
    for l in lines:
        v, _, shape = l.partition('\t')
        if v not in groups or not shape.startswith('('):
            out.append(l)
        elif v not in done:
            done.add(v)
            g = groups[v]
            out.append(f'{v}\t' + '  '.join(g[:2]) + (f'  +{len(g) - 2} more' if len(g) > 2 else ''))
    return out


def print_section(title, lines, shapes=False):
    say(f'## {title}')
    for l in classed(lines, shapes):
        say(l)


def print_wide(name, wide, seen, a, always=False):
    """A table's task-wide section, which comes last since it is the longest. Without --wide, one line that gives its size."""
    if not a.wide:
        if wide and (seen.new('wide-size ' + name, [str(len(wide))]) or always):
            say(f'## {name} task-wide: {len(wide)} entries, with {len({l.partition(chr(9))[0] for l in wide})} values; --wide lists them')
        return
    twin = seen.twin('wide ' + name, wide, ('wide',))
    if seen.new('wide ' + name, wide) or always:
        if not wide:
            return
        if twin:
            say(f'## {name} task-wide: the features of {twin} task-wide')
        else:
            print_section(name + ' task-wide', wide, a.shapes)


def print_new_queries(task, corpus, seen, shapes):
    queries, why = query_sections(task, corpus)
    if why:
        say(why)
    for q, lines in queries.items():
        if seen.new('query ' + q, lines):
            print_section('query ' + q, lines, shapes)


def tables(a):
    file, corpus, _ = placed(a.program, a.task)
    r = tool('tables', file, a.task, *(['--case', a.case] if a.case else []))
    say(shown(r))
    if r.returncode:
        return
    records, why = solve_records(file, a.task, a.case)
    for line in solve_lines(records, why):
        say(line)
    target = default_target(records, a.case)
    seen = Seen(corpus, a.all)
    for name, lines in base_sections(a.task, corpus).items():
        if seen.new('base ' + name, lines):
            print_section(name, lines, a.shapes)
    names = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('concept'):
            names = [t['relation'] for t in d.get('tables', []) if t['relation'] not in BASE]
    wides = []
    for name in names:
        lines, wide, _, _ = table_section(a.task, corpus, name, None, target)
        twin = seen.twin('table ' + name, lines)
        if seen.new('table ' + name, lines):
            if twin:
                say(f'## {name}: the features of {twin}')
            else:
                print_section(name, lines, a.shapes)
        wides.append((name, wide))
    print_new_queries(a.task, corpus, seen, a.shapes)
    for name, wide in wides:
        print_wide(name, wide, seen, a)
    seen.save()


def rows(a):
    file, corpus, name = placed(a.program, a.task, a.relation)
    r = tool('tables', file, a.task, *(['--case', a.case] if a.case else []))
    found = None
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        for t in d.get('tables', []):
            if t['relation'] == name and (d.get('concept') or a.case):
                found = t
        if d.get('refused') or d.get('error'):
            say(line)
    if found is None:
        say(shown(r) if r.returncode else f'{name}: no such table in this case')
        return
    records, why = solve_records(file, a.task, a.case)
    seen = Seen(corpus, False)
    lines, wide, _, number = table_section(a.task, corpus, name, a.assignment, default_target(records, a.case))
    header = {'relation': name, 'columns': found['columns']}
    counts = None
    if number == 1:
        counts = found['rows']
    elif number:
        counts, trouble = row_counts(file, a, name, number)
        if counts is None:
            say(';; no row counts: ' + trouble)
    if counts is not None:
        header['rows'] = counts
    header.update({'assignments': found.get('assignments'), 'assignment': number})
    say(json.dumps(header))
    for line in solve_lines(records, why):
        say(line)
    seen.new('table ' + name, lines)
    print_section(name, lines, a.shapes)
    print_new_queries(a.task, corpus, seen, a.shapes)
    print_wide(name, wide, seen, a, True)
    seen.save()


def main():
    if os.environ.get(INNER):
        return inner(sys.argv[1:])
    ap = argparse.ArgumentParser(prog='arclog.py', description=__doc__[__doc__.index('Running:'):], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--setting', required=True, help="the file that holds the internal folder's path")
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('tables'); p.add_argument('program'); p.add_argument('task'); p.add_argument('--size', choices=['1', '2'], default='1'); p.add_argument('--case'); p.add_argument('--all', action='store_true'); p.add_argument('--shapes', action='store_true'); p.add_argument('--wide', action='store_true')
    p = sub.add_parser('rows'); p.add_argument('program'); p.add_argument('task'); p.add_argument('relation'); p.add_argument('--size', choices=['1', '2'], default='1'); p.add_argument('--case'); p.add_argument('--assignment', type=int); p.add_argument('--shapes', action='store_true'); p.add_argument('--wide', action='store_true')
    a = ap.parse_args()
    global SIZE
    SIZE = a.size
    configure(a.setting)
    a.program = os.path.abspath(a.program)
    try:
        {'tables': tables, 'rows': rows}[a.command](a)
    except Exception as e:
        say(f'error: {type(e).__name__}: {e}')
    sys.stdout.write(clean('\n'.join(OUT).rstrip('\n')) + '\n')


main()
