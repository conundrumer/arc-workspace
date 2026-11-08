"""Dev labeling layer: what a grown feature library adds to the library of a reference run, over tasks.

    CONTRACTS_OUT=<out dir> python3 growth.py [--jobs N] REF_OUT_DIR TASK [TASK ...]

Each task's line prints as soon as that task is measured; the totals print at the end. With --jobs, N tasks are measured at once.

A feature is new where the reference run's base record lacks its key. The reference library is the copy of features.py that the reference run
keeps as features.snapshot.py; it gives the input grid's reference features. For each family of new features:
- tables: the tables that have a feature of the family;
- postconditions: its features with a hull over the base examples;
- falsified: those that a counted variant falsifies;
- novel: those whose set of falsifying variants, among the variants that count the table, equals neither the set of variants that change a
  reference feature nor the set that falsify a reference postcondition.
- fails alone: those that a counted variant falsifies while every reference postcondition of the same table holds.
Per task: the (variant, table) pairs whose rows change, and those among them where no feature of the table changes, with the reference
features alone and with every feature.
"""
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'features'))
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402
import paths  # noqa: E402
import jsonl as J  # noqa: E402

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', HERE / 'out'))


def library(path):
    spec = importlib.util.spec_from_file_location('reference_features', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
COL = '(?:\\w+\\.)?⟨c:[^⟩]*⟩'  # a column's token in a feature key (features.py)
TAB = '⟨t:[^⟩]*⟩'  # another table's token in a feature key
FAMILIES = [
    ('descriptions', r' describe$'),
    ('dependence', r' (relation atoms|joins|alternatives|alternatives bind it from different sources|under a NOT|under an ALL|(computed|tested) by \w+|compared by \S+|made equal to (zero|another variable))$|^(relation atoms|lib atoms|comparisons|NOTs|ALLs|ORs|joined variables|reads one table twice|variables not at a column)$| (shares an atom with|interchangeable with) ' + COL + '$'),
    ('provenance', r' (origin kinds|copy steps|from the input|from the train outputs|from a task parameter|has joined sources|has alternative sources)$|^(columns of \w+ origin|every column is a copy|some column from the train outputs|some column from a task parameter)$'),
    ('structure against the relations it reads', r'^((duplicate of|projection of|functional extension of) a relation it reads|Cartesian product|degenerate|selectivity)$'),
    ('the output cells of its colors', r' vs the output cells of its colors$'),
    ('color counts vs the output', r' color counts agree with the output, proportion$'),
    ('groups vs the output components', r' vs the output foreground components$'),
    ('colors at the cells shared with another table', r' agrees with ' + TAB + r'.* at shared cells$'),
    ('numbers vs the groups of another table', r' max vs groups of ' + TAB),
    ('groups that rest toward one side', r' every group of .+ adjoins another group or the grid edge in one direction$'),
    ('a color in the holes of another', r' a color lies in the holes of another$'),
    ('touching color pairs', r' touching color pairs$'),
    ('two numbers that rise together', r' as ' + COL + r' rises$'),
    ('agreement with another table by object', r' agrees with ' + TAB + r'.* by '),
    ('the input foreground', r' vs the input foreground$'),
    ('the output foreground as a set', r' vs the output foreground$'),
    ('numbers vs the input color count', r' max vs the input color count$'),
    ('a frame that scales the input', r' frame (is a multiple of|divides) the input size$'),
    ('the holes of another table', r' vs the holes of ' + TAB),
    ('the filled box of another table', r' vs the box of ' + TAB),
    ('same shape and same colors', r' same (shape, same colors|colors, same shape), per '),
    ('the least frequent input color', r' includes the least frequent input color$'),
    ('row counts per value all distinct', r'rows per .+ all distinct$'),
    ('the most cells on one line', r' cells per line max$'),
    ('boxes that cover the grid', r' boxes cover the grid$'),
    ('offsets between two frames', r' offsets distinct, across frames$'),
    ('the train output foreground', r' (vs the output foreground cells|is the output foreground box)$'),
    ('boxes evenly spaced', r' evenly spaced along an axis$'),
    ('a unique largest or smallest group', r' (largest|smallest) group of .+ is unique$'),
    ('nearest other group', r' distance to the nearest other group of '),
    ('group count vs another table', r' group count vs ' + TAB),
    ('fewest edges a box touches', r' edges touched min$'),
    ('numbers vs the rows of another table', r' max vs rows of ' + TAB),
    ('orientations vs another table', r' orientations vs ' + TAB),
    ('two columns equal in a row', r' equals ' + COL + '$'),
    ('moves along rows or diagonals', r' to ' + COL + r' along (rows or columns|diagonals)$'),
    ('numbers is an arithmetic progression', r' is an arithmetic progression$'),
    ('boxes that overlap or nest', r' (some boxes overlap|nested boxes)$'),
    ('rows vs another table', r'^rows vs '),
    ("groups vs another table's groups", r' (groups|group shapes) vs ' + TAB),
    ('boxes vs another table', r' boxes vs ' + TAB),
    ('inside the boxes of another table', r' inside the boxes of ' + TAB),
    ('relative position to another table', r' (cells vs ' + TAB + r'.* cells|shares rows or columns with ' + TAB + r'|least distance to ' + TAB + ')'),
    ('colors or numbers vs another table', r' vs ' + TAB),
    ('same shape as another table', r' same shape (up to rotation and reflection )?as ' + TAB),
    ('position in the grid', r' (least margin|edges touched max|centered axes max)$'),
    ('box alignment and size', r' (aligned|boxes of one size)$'),
    ('straight-line components', r' every component is a straight line$'),
    ('colors vs the train output', r' (agrees with the output colors, proportion|vs the output colors)$'),
    ('numbers vs the input size', r' max vs the (longer|shorter) side of the input$'),
    ('colors per Ident group', r' (values per|value sets per) '),
    ('fills or outlines its box', r' (fills its bounding box|is the outline of its bounding box)'),
    ('colored symmetry', r',' + COL + r' symmetry count$'),
    ('least period', r' least period$'),
    ('rows per color all equal', r' rows per value all equal$'),
    ('unique columns', r' is unique$'),
    ('size of the train output', r' has the output size$'),
    ('symmetry', r' symmetry count'),
    ('enclosed regions', r' enclosed regions'),
    ('4-connected components', r' 4-connected components$'),
    ('shapes per group', r' distinct shapes per group'),
    ('input colors under the cells', r' (input colors distinct|is a union of input colors)$'),
    ('colors vs the input', r' (within the input colors|includes the most frequent input color|agrees with the input colors, proportion|vs the input colors)$'),
    ('frame of its own', r' frame (is the input size|is square|share of the input)$'),
    ('numbers form a run', r' is a range of consecutive integers$'),
    ('orientations', r' (covers its type|on one axis|includes an opposite pair|all turns|includes the identity)$'),
    ('offsets', r' (includes no move|along rows or columns|longest move|moves of one length)$'),
    ('rows per Ident', r'^rows per '),
    ('two numbers of a row', r' vs ' + COL + r' in every row$'),
    ('two cells of a row', r' to ' + COL + r' (moves distinct|distance max|distance min)$'),
    ('a cell in its row\'s box', r' inside ' + COL + r' in every row$'),
    ('graph of two columns', r' graph (components|greatest degree)$'),
    ('rows per number', r' rows per value (max|min)$'),
    ('full lines', r' full lines'),
    ('old features in a new frame', r''),
]


def family(feat):
    return next(f for f, pat in FAMILIES if re.search(pat, feat))


def reference_input_keys(REF, task, base):
    """The keys of the input grid's features that the reference library gives, at the task's own examples."""
    tj = json.load(open(paths.TASKS / ('%s.json' % task)))
    keys = set()
    for ex in base['examples']:
        p = tj[ex.split('/')[0]][int(ex.split('/')[1])]
        gi, go = p['input'], p.get('output') if ex.startswith('train') else None
        H, W = len(gi), len(gi[0])
        rows = [[[r, H - 1 - r, c, W - 1 - c], gi[r][c]] for r in range(H) for c in range(W)]
        tab = {'columns': [('P', 'Position', 'input'), ('Col', 'Color', '')], 'rows': {'x': rows}}
        sizes = {'input': (H, W)}
        if go is not None:
            sizes['output'] = (len(go), len(go[0]))
        keys |= {'input|' + k for k in REF.table_features('input', tab, 'x', sizes, {}, (gi, go))}
    return keys


def parsed(path):
    """The records of a JSON-lines file, without a last line that is still being written."""
    return list(J.records(path))


def load(out, task):
    lines = parsed(out / (task + '.variants.jsonl'))
    base = next(l for l in lines if l['kind'] == 'base')
    return base, [l for l in lines if l['kind'] != 'base' and 'features' in l]


def base_record(out, task):
    """The base record of a run's variants file, read without parsing the variants."""
    for l in J.lines(out / (task + '.variants.jsonl')):
        if '"kind": "base"' in l:
            return json.loads(l)
    raise ValueError('no base record for %s in %s' % (task, out))


REF = None


def measure(args):
    """(task, {family: Counter}, (rows change, no reference feature does, no feature does) or None) for one task, or the task and a reason."""
    global REF
    ref, task = args
    if REF is None:
        REF = library(ref / 'features.snapshot.py')
    fam = defaultdict(Counter)
    blind = []
    vp = OUTDIR / (task + '.verdicts.post.json')
    if not vp.exists():
        return task, 'no verdicts yet', None
    verdicts = json.load(open(vp))
    base, V = load(OUTDIR, task)
    rbase = base_record(ref, task)
    old = {k for f in rbase['examples'].values() for k in f} | reference_input_keys(REF, task, base)
    A.add_input(task, base, V)
    uses = {u['id']: u for u in parsed(OUTDIR / (task + '.uses.jsonl'))}
    idx = {v['id']: i for i, v in enumerate(V)}
    exs = base['examples']
    # bitsets over the variants: which change each reference feature, and which falsify each reference postcondition
    post = A.postconditions(base)
    ref_sets = []
    ref_fail = Counter()  # per table: the variants that falsify some reference postcondition of the table
    for k in old:
        ch = fl = 0
        for i, v in enumerate(V):
            x = v['features'].get(k, 'MISSING')
            if x != exs[v['source']].get(k, 'MISSING'):
                ch |= 1 << i
            if k in post and not A.holds(post[k], x):
                fl |= 1 << i
        ref_sets.append((ch, fl))
        ref_fail[k.split('|')[0]] |= fl
    masks = Counter()
    for vid, u in uses.items():
        if vid in idx:
            for t in u['counted']:
                masks[t] |= 1 << idx[vid]
    for t, r in verdicts.items():
        mask = masks[t]
        ref_here = {x & mask for pair in ref_sets for x in pair}
        seen = set()
        for k, d in r['postconditions'].items():
            if k in old:
                continue
            f = family(k.split('|', 1)[1])
            if f not in seen:
                fam[f]['tables'] += 1
                seen.add(f)
            fam[f]['postconditions'] += 1
            if d['verdict'] in ('new', 'redundant'):
                fam[f]['falsified'] += 1
                fails = 0
                for vid, u in uses.items():
                    if k in u['falsifies'] and vid in idx:
                        fails |= 1 << idx[vid]
                if fails & mask not in ref_here:
                    fam[f]['novel'] += 1
                if fails & mask & ~ref_fail[t]:
                    fam[f]['fails alone'] += 1
    # rows that change where no feature changes
    if 'digests' in base:
        n = b_old = b_new = 0
        for v in V:
            d0 = base['digests'].get(v['source'], {})
            for t, dg in v.get('digests', {}).items():
                if t not in d0 or dg == d0[t]:
                    continue
                n += 1
                same = [k for k in exs[v['source']] if k.split('|')[0] == t and v['features'].get(k, 'MISSING') == exs[v['source']][k]]
                keys = [k for k in exs[v['source']] if k.split('|')[0] == t]
                if len(same) == len(keys):
                    b_new += 1
                if all(v['features'].get(k, 'MISSING') == exs[v['source']][k] for k in keys if k in old):
                    b_old += 1
        blind.append((n, b_old, b_new))
    return task, {f: dict(c) for f, c in fam.items()}, (blind[0] if blind else None)


def main(ref, tasks, jobs=1):
    fam = defaultdict(Counter)
    blind = []
    work = [(ref, t) for t in tasks]
    if jobs > 1:
        import multiprocessing
        results = multiprocessing.Pool(jobs).imap_unordered(measure, work)
    else:
        results = map(measure, work)
    for task, got, bl in results:
        if isinstance(got, str):
            print('%s: %s' % (task, got), flush=True)
            continue
        for f, c in got.items():
            fam[f].update(c)
        if bl:
            blind.append((task,) + bl)
        print('%s: %d new postconditions, %d falsified, %d novel, %d fail alone' % (task, sum(c.get('postconditions', 0) for c in got.values()),
              sum(c.get('falsified', 0) for c in got.values()), sum(c.get('novel', 0) for c in got.values()), sum(c.get('fails alone', 0) for c in got.values())),
              flush=True)
    print()
    print('%-34s %7s %15s %10s %7s %12s' % ('family of new features', 'tables', 'postconditions', 'falsified', 'novel', 'fails alone'))
    for f, _ in FAMILIES:
        c = fam[f]
        if c:
            print('%-34s %7d %15d %10d %7d %12d' % (f, c['tables'], c['postconditions'], c['falsified'], c['novel'], c['fails alone']))
    if blind:
        print('\n%-10s %14s %26s %26s' % ('task', 'rows change', 'no reference feature does', 'no feature does'))
        for task, n, a, b in blind:
            print('%-10s %14d %18d (%3.0f%%) %18d (%3.0f%%)' % (task, n, a, 100 * a / max(n, 1), b, 100 * b / max(n, 1)))
        n, a, b = (sum(x[i] for x in blind) for i in (1, 2, 3))
        print('%-10s %14d %18d (%3.0f%%) %18d (%3.0f%%)' % ('all', n, a, 100 * a / max(n, 1), b, 100 * b / max(n, 1)))


if __name__ == '__main__':
    argv = sys.argv[1:]
    jobs = 1
    if argv[:1] == ['--jobs']:
        jobs, argv = int(argv[1]), argv[2:]
    main(Path(argv[0]), argv[1:], jobs)
