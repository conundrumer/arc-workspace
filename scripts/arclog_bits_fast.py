"""The proxy of scripts/arclog_bits.py --fast: the bits of a form from its text, with no engine and no model files.

A form is read as s-expressions. Each atom gets features from its text (the class of its relation, its fields, the labels in them, its place) and a
linear model per column of the table (rel, col, val, stop, other) gives its bits; a form's own coins (stops, OR coins, a component, a port's head)
come from a linear model on its counts. The coefficients are in `arclog_bits_fast.json`, fitted on census rows by

  python scripts/arclog_bits_fast.py fit CENSUS.jsonl POINTS.json REL_ALL.jsonl OUT.json
  python scripts/arclog_bits_fast.py cv  CENSUS.jsonl POINTS.json REL_ALL.jsonl      (5 folds by task: median and worst gap per kind)

CENSUS.jsonl is a census of or_q (rows with `scope` before, `atoms`, `detail`, `parts`), POINTS.json its gold programs, and REL_ALL.jsonl a relation-pick
read whose `opts` give each relation's kind.
"""
import json
import math
import re
import sys
from typing import Any

CATS = ('rel', 'col', 'val', 'stop', 'other')
TOK = re.compile(r'\(|\)|[^\s()]+')
CLASSES = ('derived', 'lib relation', 'relation macro', 'fact relation', 'own', 'not', 'cmp')
SHRINK = 4.0
RIDGE = 1.0


def parse(text):
    stack, cur = [], []
    for t in TOK.findall(text):
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    return cur[0]


def unparse(node):
    return '(' + ' '.join(unparse(x) if isinstance(x, list) else x for x in node) + ')'


def label_counts(node, c):
    """Counts of the labels and constants in the field values of an atom."""
    for v in node:
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0].startswith(':'):
                c['nested'] += 1
                label_counts(v[1:], c)
            else:
                label_counts(v, c)
        elif v.startswith('*'):
            c['fresh'] += 1
        elif v.startswith('^'):
            c['keyed'] += 1
        elif v[0].isdigit() or v[0] == '-' or v[0] in '"#':
            c['const'] += 1
        else:
            c['reused'] += 1


def atoms_of(text):
    """(atoms, counts) of a form's text: the atoms in written order, each a dict of features, and the form's counts."""
    f = parse(text)
    kind = f[0]
    counts: dict[str, Any]
    atoms, counts = [], dict(component=f[2] if kind == 'INIT' else '', branches=0, ports=0, head_fields=0, keys=0, nots=0, else_nots=0)

    def add(item, place, branch):
        if not isinstance(item, list) or not item:
            return
        if isinstance(item[0], list):  # a branch: a list of atoms
            for x in item:
                add(x, place, branch)
        elif item[0] == 'NOT':
            counts['nots'] += 1
            atom(item[1], place, branch, True)
        elif item[0] == 'OR':
            for i, br in enumerate(item[1:]):
                counts['branches'] += 1
                for j, x in enumerate(br):
                    if i and j == 0 and x[0] == 'NOT' and x[1][0] == item[1][0][0]:  # the else branch: the walk draws its NOT as a coin, not as an atom
                        counts['else_nots'] += 1
                        continue
                    add(x, place, i + 1)
        else:
            atom(item, place, branch, False)

    def atom(item, place, branch, neg):
        if not isinstance(item, list) or not item or not isinstance(item[0], str):
            return
        c = dict.fromkeys(('fresh', 'keyed', 'const', 'reused', 'nested'), 0)
        fields = [x for x in item[1:] if isinstance(x, list) and x and isinstance(x[0], str) and x[0].startswith(':')]
        label_counts([v for x in item[1:] for v in (x[1:] if isinstance(x, list) and x and isinstance(x[0], str) and x[0].startswith(':') else [x])], c)
        atoms.append(dict(head=item[0], text=('(NOT %s)' if neg else '%s') % unparse(item), nfields=len(fields) or sum(1 for x in item[1:] if isinstance(x, str)), neg=neg, place=place, branch=branch, **c))

    if kind == 'INIT':
        ports = []
        for item in f[3:]:
            if item[0] == 'key':  # (key KEYBODY PORT ...)
                counts['keys'] += 1
                for x in item[1]:
                    add(x, 'key', 0)
                ports += item[2:]
            else:
                ports.append(item)
        for item in ports:
            counts['ports'] += 1
            counts['head_fields'] += len(item[1]) if len(item) > 1 and isinstance(item[1], list) else 0
            for x in item[2:]:
                add(x, 'port', 0)
    else:
        for item in f[2:]:
            add(item, 'top', 0)
    return kind, atoms, counts


def head_class(head, names, own):
    if head in own:
        return 'own'
    if head.startswith('&'):
        return 'derived'
    if not (head[0].isalpha() or head[0] == '_'):
        return 'cmp'
    return names.get(head, 'lib relation')


def atom_x(a, i, nscope, names, own, refs):
    """Features of atom i, for the models of each column: dict name -> feature list."""
    cls = head_class(a['head'], names, own)
    cl = [1.0 if cls == c else 0.0 for c in CLASSES]
    if a['neg']:
        cl[CLASSES.index('not')] = 1.0
    first = 1.0 if i == 0 else 0.0
    der = cl[0]
    m = re.match(r'&r\d+', a['head'])
    rk = refs.get(m[0]) if m else None
    rkind = [1.0 if rk == k else 0.0 for k in ('INIT', 'RULE', 'DET')]
    dotted = 1.0 if m and '.' in a['head'] else 0.0
    x = dict(
        rel=[1.0, first] + cl + [1.0 if a['branch'] else 0.0, der * math.log2(1 + nscope), 0.0 if i == 0 else math.log2(1 + i)] + rkind + [dotted],
        col=[1.0, first, a['nfields'], a['nfields'] * der, a['fresh'], a['reused'], a['const'], a['keyed'], cl[-1]] + rkind + [dotted],
        val=[1.0, first, a['reused'], a['fresh'], a['const'], a['nested'], cl[-1], cl[-2]],
        stop=[1.0, first, a['nfields'], cl[-1], 1.0 if a['branch'] else 0.0],
        other=[1.0, first, cl[4], 1.0 if a['reused'] else 0.0, 1.0 if a['place'] != 'top' else 0.0])
    return cls, x


def form_x(kind, atoms, counts):
    n = len(atoms)
    return [1.0, n, counts['branches'], counts['nots'], counts['ports'], counts['keys'], counts['head_fields'], math.log2(1 + n), counts['else_nots']]


def solve(xs, ys, ridge=RIDGE):
    """Ridge least squares by the normal equations."""
    d = len(xs[0])
    a = [[sum(r[i] * r[j] for r in xs) + (ridge if i == j and i > 0 else 0.0) for j in range(d)] + [sum(r[i] * y for r, y in zip(xs, ys))] for i in range(d)]
    for i in range(d):
        p = max(range(i, d), key=lambda k: abs(a[k][i]))
        a[i], a[p] = a[p], a[i]
        if abs(a[i][i]) < 1e-12:
            continue
        for k in range(d):
            if k != i:
                m = a[k][i] / a[i][i]
                a[k] = [u - m * v for u, v in zip(a[k], a[i])]
    return [a[i][d] / a[i][i] if abs(a[i][i]) > 1e-12 else 0.0 for i in range(d)]


def dot(w, x):
    return sum(u * v for u, v in zip(w, x))


def part_cat(key):
    sub = key.split('atom: ', 1)[1] if 'atom: ' in key else key
    if sub in ('relation', 'relation (op)'):
        return 'rel'
    if sub in ('column', 'fcol'):
        return 'col'
    if sub.startswith('value') or sub == 'op':
        return 'val'
    if sub == 'column stop' or 'stop' in sub or 'go on' in sub:
        return 'stop'
    return 'other'


def split(parts):
    out = dict.fromkeys(CATS, 0.0)
    for k, v in parts.items():
        out[part_cat(k)] += v
    return out


def names_of(rel_all):
    out = {}
    for line in open(rel_all):
        r = json.loads(line)
        for o in r.get('opts', ()):
            out.setdefault(o[0], o[1])
    return out


def rows_of(census, points, names):
    """Training rows: (task, kind, atoms with features and bits, counts, form residuals by column, total)."""
    tasks = {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(points))}
    rows = []
    for line in open(census):
        c = json.loads(line)
        if c['scope'] != 'before' or c['bad'] or c['dead'] or c['kind'] not in ('RULE', 'DET', 'INIT'):
            continue
        kind, atoms, counts = atoms_of(c['target'])
        refs = refs_of(tasks[c['task']])
        if len(atoms) != len(c['atoms']):
            continue
        own, feats = set(), []
        for i, (a, (place, text, bits), det) in enumerate(zip(atoms, c['atoms'], c['detail'])):
            cls, x = atom_x(a, i, c['nscope'], names, own, refs)
            own.add(a['head'])
            y = split(det['cur'])
            y['other'] += bits - sum(y.values())
            feats.append((a['head'], cls, x, y))
        tot = split(c['parts'])
        resid = {k: tot[k] - sum(f[3][k] for f in feats) for k in CATS}
        rows.append(dict(task=c['task'], kind=kind, component=counts['component'], atoms=feats, fx=form_x(kind, atoms, counts), resid=resid, total=c['total']))
    return rows


def fit(rows):
    model = dict(atom={}, form={}, names={}, name_resid={})
    for k in CATS:
        xs = [f[2][k] for r in rows for f in r['atoms']]
        ys = [f[3][k] for r in rows for f in r['atoms']]
        model['atom'][k] = solve(xs, ys)
    by_name = {}
    for r in rows:
        for head, cls, x, y in r['atoms']:
            if cls in ('lib relation', 'relation macro', 'fact relation'):
                by_name.setdefault(head, []).append(y['rel'] - dot(model['atom']['rel'], x['rel']))
    model['name_resid'] = {n: sum(v) / (len(v) + SHRINK) for n, v in by_name.items()}
    for kind in ('RULE', 'DET', 'INIT'):
        rs = [r for r in rows if r['kind'] == kind]
        model['form'][kind] = {k: solve([r['fx'] for r in rs], [r['resid'][k] for r in rs]) for k in CATS}
    by_comp = {}
    for r in rows:
        if r['kind'] == 'INIT':
            by_comp.setdefault(r['component'], []).append(sum(r['resid'][k] - dot(model['form']['INIT'][k], r['fx']) for k in CATS))
    model['comp_resid'] = {n: sum(v) / (len(v) + SHRINK) for n, v in by_comp.items()}
    return model


def refs_of(lines):
    """The kind of the form that each name `&rN` of the program stands for."""
    out = {}
    for l in lines:
        m = re.search(r'&r\d+', l)
        if m:
            out[m[0]] = l.split()[0].lstrip('(')
    return out


def predict(model, names, text, nscope, refs):
    """(form bits by column, [(atom head, bits by column)]) for the form text with nscope earlier forms."""
    kind, atoms, counts = atoms_of(text)
    own, out = set(), []
    for i, a in enumerate(atoms):
        cls, x = atom_x(a, i, nscope, names, own, refs)
        own.add(a['head'])
        y = {k: dot(model['atom'][k], x[k]) for k in CATS}
        y['rel'] += model['name_resid'].get(a['head'], 0.0)
        out.append((a['text'], a['place'], y))
    form = {k: sum(y[k] for _, _, y in out) for k in CATS}
    fm = model['form'].get(kind)
    if fm:
        fx = form_x(kind, atoms, counts)
        for k in CATS:
            form[k] += dot(fm[k], fx)
        form['other'] += model.get('comp_resid', {}).get(counts['component'], 0.0)
    return form, out


def cv(rows, k=5):
    tasks = sorted({r['task'] for r in rows})
    fold = {t: i % k for i, t in enumerate(tasks)}
    gaps = {}
    for f in range(k):
        m = fit([r for r in rows if fold[r['task']] != f])
        for r in rows:
            if fold[r['task']] != f:
                continue
            est = 0.0
            for (head, cls, x, y) in r['atoms']:
                v = sum(dot(m['atom'][c], x[c]) for c in CATS)
                if cls in ('lib relation', 'relation macro', 'fact relation'):
                    v += m['name_resid'].get(head, 0.0)
                est += v
            est += sum(dot(m['form'][r['kind']][c], r['fx']) for c in CATS)
            if r['kind'] == 'INIT':
                est += m['comp_resid'].get(r['component'], 0.0)
            gaps.setdefault(r['kind'], []).append((est - r['total'], r['total']))
    return gaps


def main():
    cmd = sys.argv[1]
    names = names_of(sys.argv[4])
    rows = rows_of(sys.argv[2], sys.argv[3], names)
    if cmd == 'fit':
        m = fit(rows)
        m['names'] = names
        json.dump(m, open(sys.argv[5], 'w'), separators=(',', ':'))
        print('fitted on', len(rows), 'forms')
    else:
        for kind, g in sorted(cv(rows).items()):
            a = sorted(abs(x) for x, _ in g)
            print(kind, len(g), 'median gap %.2f worst %.2f mean signed %.2f' % (a[len(a) // 2], a[-1], sum(x for x, _ in g) / len(g)))


if __name__ == '__main__':
    main()
