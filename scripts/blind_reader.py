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

`tables` is scripts/arclog.py's: JSON with each table's columns and row counts at each example. It then gives the features of
each table and query not yet shown for this task, or of all of them with `--all`. `rows` takes RELATION as
scripts/arclog.py does: a name, or arclog text placed before the OUT form, either atoms or whole forms. It gives the
relation's columns and row counts in place of its rows, then its features, then the features of any query not yet shown.

Features are sparse: an entry at its default is left out.
- A table's section is `## TABLE`, with lines `VALUE<tab>SHAPE`. VALUE is the entry's value at each train example, as
  `a | b | c`, or one value where they agree. Where the shape's greatest and sum differ, it is `greatest,sum`. A fraction
  is `top/bottom`. `?` is no value, where a bound on the walk stopped it. `test:` says whether each test input has a value.
  A shape's `T` is the table.
- `## TABLE task-wide` gives the shapes that read all examples at once, with one value each. Their names are long, and a table
  can have hundreds, so a run gives the count of them and the count of values, and `--wide` lists them, last.
- `## input`, `## ex_output` and `## pair` give the features of the input grids, the example outputs and the pairs.
- Entries with one value vector are one line, which names the first two shapes and the count of the others; `--shapes` lists
  them. Entries whose value is 0 or 1 at every example stay apart, since each states a claim of its own.
- A table with the features of a table already shown is one line that names that table.
- `## query HASH` gives the query's features, then its features against each table it uses.
- Features read the concept case, at `--assignment N`, counted from 1.
"""
import argparse, hashlib, json, os, re, signal, subprocess, sys
from pathlib import Path

HEADS = ('(RULE', '(DET', '(INIT', '(RIGID_DET')
BASE = ('ex_input', 'ex_output', 'input', 'output')
TIMEOUT = float(os.environ.get('BLIND_READER_TIMEOUT', '170'))
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


def read_vector(path, want):
    """(the lines of assignment WANT, its task-wide lines, the table's AssignmentVector), or an error text.

    A table's file holds, for each assignment, a block of per-example entries and a block of task-wide entries, and then
    the AssignmentVector's line, which a block of pool entries can follow.
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
    if not 1 <= want <= len(blocks):
        return f'no assignment {want}; the table has {len(blocks)}', None, pool
    label, _, entries = blocks[want - 1]
    text = lambda es: [f'{v}\t{s}' for _, s, v in sorted(es)]
    return text(entries), text(wide.get(label, [])), pool


def table_section(task, corpus, name, assignment):
    """(lines, task-wide lines, pool) of a table."""
    out = f'{corpus}/v-{hashlib.sha1(name.encode()).hexdigest()[:10]}.jsonl'
    if os.path.exists(out):
        os.remove(out)
    r = encoder('vector', task, name, '--size', '1', '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
    if not os.path.exists(out):
        return [';; no vector: ' + fault(r)], [], None
    lines, wide, pool = read_vector(out, assignment)
    if isinstance(lines, str):
        return [';; ' + lines], [], pool
    head = []
    if pool and pool.get('count', 1) != 1:
        head = [f"{pool['count']}\tassignments", f"{pool['distinct']:.3g}\tdistinct tables over assignments"] + (['true\tcapped'] if pool.get('capped') else [])
    return head + lines, wide, pool


def base_sections(task, corpus):
    out = corpus + '/b.jsonl'
    if os.path.exists(out):
        os.remove(out)
    r = encoder('base-vectors', task, '--size', '1', '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
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
    r = encoder('query-vectors', task, '--size', '1', '--corpus', corpus, '--tasks', CFG['tasks'], '--out', out)
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
        lines, wide, _ = table_section(a.task, corpus, name, 1)
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
    say(json.dumps({'relation': name, 'columns': found['columns'], 'rows': found['rows'], 'assignments': found.get('assignments')}))
    seen = Seen(corpus, False)
    lines, wide, _ = table_section(a.task, corpus, name, a.assignment)
    seen.new('table ' + name, lines)
    print_section(name, lines, a.shapes)
    print_new_queries(a.task, corpus, seen, a.shapes)
    print_wide(name, wide, seen, a, True)
    seen.save()


def main():
    ap = argparse.ArgumentParser(prog='arclog.py', description=__doc__[__doc__.index('Running:'):], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--setting', required=True, help="the file that holds the internal folder's path")
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('tables'); p.add_argument('program'); p.add_argument('task'); p.add_argument('--case'); p.add_argument('--all', action='store_true'); p.add_argument('--shapes', action='store_true'); p.add_argument('--wide', action='store_true')
    p = sub.add_parser('rows'); p.add_argument('program'); p.add_argument('task'); p.add_argument('relation'); p.add_argument('--case'); p.add_argument('--assignment', type=int, default=1); p.add_argument('--shapes', action='store_true'); p.add_argument('--wide', action='store_true')
    a = ap.parse_args()
    configure(a.setting)
    a.program = os.path.abspath(a.program)
    try:
        {'tables': tables, 'rows': rows}[a.command](a)
    except Exception as e:
        say(f'error: {type(e).__name__}: {e}')
    sys.stdout.write(clean('\n'.join(OUT).rstrip('\n')) + '\n')


main()
