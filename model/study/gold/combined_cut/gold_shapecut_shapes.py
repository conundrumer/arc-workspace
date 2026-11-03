# Written by gold_shapecut_make.py.
"""Shapes of cut that gold_shapecut_cuts.py adds to gold_orcut_cuts.py. Nothing here runs the engine.

Shapes:
  key-project     an INIT whose key body is one OR: a union RULE of that OR with only the key labels as columns, and the key reads it. Sites of a label that the OR reads once and that is no key go.
  split-groups    a body whose atoms fall in groups that share no label: each group of 2 or more atoms to a RULE, and the form reads them.
  flat-copy       an INIT with one read per port: for each derived relation it reads in more than one body, or with a record site, a RULE just before the INIT with flat columns, and each read goes to it.
  if-to-or        an IF to an OR of (condition, then) and (NOT condition, else).
  empty-port      a port with no body: its head reads a new label that a `=` of the key label binds.
"""
import re

from gold_chain import parse, show


def plain(x):
    return [plain(y) for y in x] if isinstance(x, list) else (x[1:] if isinstance(x, str) and x[0] in '*^' and len(x) > 1 and x[1].isupper() else x)


def labs(x):
    out = []

    def go(y, first):
        if isinstance(y, list):
            for k, e in enumerate(y):
                go(e, k == 0)
        elif isinstance(y, str) and not first and re.match(r'^[*^]?[A-Z]', y):
            out.append(y.lstrip('*^'))
    go(x, True)
    return out


def star_first(atoms, want):
    """atoms with marks gone and a star at the first positive site of each label of want."""
    atoms = plain(atoms)
    seen = set()

    def go(y):
        if isinstance(y, list):
            if y and y[0] in ('NOT',):
                return
            for k, z in enumerate(y):
                if isinstance(z, list):
                    go(z)
                elif k and z in want and z not in seen and y[0] not in ('=', '!=', '<', '<=', '>', '>='):
                    seen.add(z)
                    y[k] = '*' + z
    for a in atoms:
        go(a)
    return atoms


def key_project(text):
    p = parse(text)
    k = next((e for e in p[3:] if isinstance(e, list) and e and e[0] == 'key'), None)
    if k is None or len(k[1]) != 1 or k[1][0][0] != 'OR':
        return None
    o = k[1][0]
    keys = [t[1:] for t in re.findall(r'\^[A-Z]\w*', show(o))]
    if not keys:
        return None
    counts = {}
    for b in o[1:]:
        for l in labs(b):
            counts[(id(b), l)] = counts.get((id(b), l), 0) + 1

    def drop(a, b):
        """a without sites of a label that branch b reads once and that is no key."""
        if not isinstance(a, list):
            return a
        if a and isinstance(a[0], str) and a[0].startswith(':') and len(a) == 2 and isinstance(a[1], str):
            l = a[1].lstrip('*^')
            if l not in keys and counts.get((id(b), l)) == 1:
                return None
            return a
        out = [drop(y, b) for y in a]
        return [y for y in out if y is not None]
    bs = []
    for b in o[1:]:
        nb = [drop(a, b) for a in b]
        nb = [a for a in nb if len(a) >= 1 and not (isinstance(a, list) and len(a) >= 2 and isinstance(a[-1], list) and a[-1][0].startswith(':') and len(a[-1]) == 1)]
        if len(nb) != len(b) or not all(any(l in labs(a) for a in nb) for l in keys):
            return None
        bs.append(nb)
    helper = '(RULE &kp1 %s)' % show(['OR'] + bs).replace('^', '*')
    k[1] = [['&kp1'] + [[':' + l, '^' + l] for l in keys]]
    return [helper, show(p)]


def groups(atoms):
    gs = []
    for a in atoms:
        s = set(labs(a))
        hit = [g for g in gs if g[0] & s]
        members = [a]
        for g in hit:
            gs.remove(g)
            s |= g[0]
            members = g[1] + members
        gs.append((s, members))
    return gs


def split_groups(text, later_cols):
    p = parse(text)
    kind, head, atoms = p[0], p[1], p[2:]
    cmp_ = [a for a in atoms if a[0] in ('NOT', '=', '!=', '<', '<=', '>', '>=', 'ONE', 'SET', 'OR', 'ALL', 'IF')]
    pos = [a for a in atoms if a not in cmp_]
    gs = groups(pos)
    if len(gs) < 2 or not any(len(g[1]) >= 2 for g in gs):
        return None
    forms, reads = [], []
    outer = set(labs(cmp_)) | later_cols
    for n, (ls, members) in enumerate(gs):
        if len(members) < 2:
            reads += members
            continue
        name = '&sg%d' % n
        all_labs = list(dict.fromkeys(labs(members)))
        forms.append('(%s %s %s)' % ('DET' if kind == 'DET' else 'RULE', name, ' '.join(show(a) for a in members)))
        reads.append([name] + [[':' + l, '*' + l] for l in all_labs if l in outer])
    forms.append('(%s %s %s)' % (kind, head, ' '.join(show(a) for a in reads + cmp_)))
    return forms


def flat_copy(text):
    p = parse(text)
    atoms = []

    def go(y):
        if isinstance(y, list):
            if y and isinstance(y[0], str) and y[0].startswith('&'):
                atoms.append(y)
            for e in y:
                go(e)
    go(p[3:])
    rels = {}
    for a in atoms:
        rels.setdefault(a[0], []).append(a)
    forms, out = [], text
    n = 0
    for r, reads in rels.items():
        rec = any(isinstance(s, list) and len(s) > 1 and isinstance(s[1], list) for a in reads for s in a[1:])
        if len(reads) < 2 and not rec:
            continue
        cols = {}  # path -> flat label

        def leaf(sites, path):
            for s in sites:
                if len(s) == 2 and not isinstance(s[1], list):
                    yield path + (s[0],), s[1]
                elif all(isinstance(e, list) for e in s[1:]):
                    yield from leaf(s[1:], path + (s[0],))
                else:
                    raise ValueError
        try:
            leaves = [list(leaf(a[1:], ())) for a in reads]
        except ValueError:
            continue
        for ls in leaves:
            for path, _ in ls:
                cols.setdefault(path, 'C%d' % len(cols))
        name = '&fc%d' % n
        n += 1
        tree = {}
        for path, lab_ in cols.items():
            d = tree
            for c in path[:-1]:
                d = d.setdefault(c, {})
            d[path[-1]] = lab_

        def build(d):
            return [[c] + (build(v) if isinstance(v, dict) else ['*' + v]) for c, v in d.items()]
        forms.append('(RULE %s (%s %s))' % (name, r, ' '.join(show(s) for s in build(tree))))
        for a, ls in zip(reads, leaves):
            new = [name] + [[':' + cols[path], l] for path, l in ls]
            out = out.replace(show(a), show(new))
    if not forms:
        return None
    return forms + [out]


def if_to_or(text):
    p = parse(text)

    def go(y):
        if isinstance(y, list):
            for k, e in enumerate(y):
                if isinstance(e, list) and e and e[0] == 'IF' and len(e) == 4:
                    c, a, b = e[1:]
                    if len(c) != 1:
                        return False
                    y[k] = ['OR', c + a, [['NOT', c[0]]] + b]
                    return True
                if go(e):
                    return True
        return False
    return [show(p)] if go(p) else None


def empty_port(text):
    n = [0]

    def sub(m):
        n[0] += 1
        return '(%s ((%s E%d)) (= *E%d %s))' % (m[1], m[2], n[0], n[0], m[3])
    t = re.sub(r'\((\w+) \(\((:\w+) ([A-Z]\w*)\)\)\)', sub, text)
    return [t] if n[0] else None


def later_columns(ls, i, head):
    got = set()
    for x in ls[i + 1:]:
        for m in re.finditer(re.escape(head) + r'(?![\w.])((?: \(:\w+ [^()]*\))*)', x):
            got |= set(re.findall(r'\(:(\w+) ', m[1]))
    return got
