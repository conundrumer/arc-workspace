"""Candidate cuts of one form of a program, as text. Nothing here runs the engine: a candidate that the reader refuses, or that changes the program, drops at the bar in gold_orcut_one.py.

  candidates(lines, i) gives Cut(shape, forms) for the form at lines[i], where forms replace that one line.

Shapes:
  chain            a body cut at one atom, the later atoms reading the earlier ones through a helper. An OR, IF or ALL counts as one atom.
  chain-tail       a body cut at one atom, the later atoms to a helper that the earlier atoms read
  chain-tail+carry as chain-tail, where the later atoms cannot bind a label alone: the helper starts with the earlier atoms that bind it
  union-branches   each branch of a whole-body OR of 2 or more atoms to a RULE, and a union of reads
  union-branch     the largest branch alone to a RULE
  union-nested     as union-branches, with nested 2-way unions
  union-nest-only  nested 2-way unions, the branches left in place
  or-extract       an OR inside a join to a RULE of its own, read by the join
  or-distribute    the atoms before an OR to a helper, each branch reading it, and a union, read by the atoms after the OR
  init-bodies      every body of an INIT of 2 or more atoms, or with an OR, to a RULE; equal bodies share one RULE
  init-ports       the same, for the ports alone
  init-key         the key body alone, and the bodies equal to it
  init-body        one port body alone
  init-shared      the longest run of atoms that two bodies of an INIT begin with, to a RULE
A helper that is one read of a derived relation with every site fresh is a copy of that relation, and no cut writes one. A helper is a RULE, or a DET where the body reads ex_input or ex_output or the cut form is a DET.
"""
import re
from collections import namedtuple
from gold_chain import VAR, parse, reads, show

Cut = namedtuple('Cut', 'shape forms')
KEYWORDS = {'NOT', 'OR', 'ALL', 'IF', 'ONE', 'SET', 'RULE', 'INIT', 'DET', 'OUT', 'CHOOSE', 'RIGID_DET'}
OPS = {'=', '!=', '<', '<=', '>', '>='}
# The modes of the lib's relations and macros. Each mode is the columns, other than an orientation type's, that must be bound before the atom. A relation not here needs none.
MODES = {
    'apply': ['P'], 'axis_extents': ['P'], 'axis_inset': ['K1 K2'], 'axis_outset': ['K1 K2'], 'box_extent': ['B P'], 'centered': ['P'], 'compose': ['A B'], 'corner_dist': ['P'], 'corner_inset': ['K'], 'corner_outset': ['K'],
    'diag_dist': ['P'], 'dist_pair': ['P'], 'divide': ['T Side Gap'], 'edge_inset': ['K'], 'edge_outset': ['K'], 'frame_extent': ['P'], 'frame_offset': ['P'], 'gap': ['P Q'], 'inside': ['A B'], 'interior': ['A B'],
    'jump': ['P K'], 'jump_offset': ['K'], 'margin': ['B'], 'nearer': ['P Q'], 'neighbor': ['P'], 'relative': ['Base X'], 'same_corner': ['P1 P2'], 'same_dist': ['P1 P2'], 'same_line': ['P Q'], 'same_slab': ['P1 P2'],
    'split': ['P'], 'sub_extent': ['P'], 'tile_size': ['Ext N G', 'N G K'], 'uniform_inset': ['K'], 'uniform_outset': ['K'],
}


def base(t):
    m = VAR.match(t) if isinstance(t, str) else None
    return m[1] if m and m[1] not in KEYWORDS else None


def labels(x):
    """The labels of x, in order of first appearance."""
    out = {}

    def walk(y):
        if isinstance(y, list):
            for k, z in enumerate(y):
                if k or isinstance(z, list):
                    walk(z)
        elif base(y):
            out[base(y)] = 1
    walk(x)
    return list(out)


def made(x):
    """The labels that x makes with a star or a caret, at any depth."""
    out = {}

    def walk(y):
        if isinstance(y, list):
            for k, z in enumerate(y):
                if k or isinstance(z, list):
                    walk(z)
        elif isinstance(y, str) and y[0] in '*^' and base(y):
            out[base(y)] = 1
    walk(x)
    return list(out)


def unmark(x, keep_star=True):
    """A copy of x with each caret as a star."""
    if isinstance(x, list):
        return [unmark(y) for y in x]
    return '*' + x[1:] if isinstance(x, str) and x[0] == '^' and base(x) else x


def plain(x):
    """A copy of x with no marks."""
    if isinstance(x, list):
        return [plain(y) for y in x]
    return x[1:] if isinstance(x, str) and x[0] in '*^' and base(x) else x


def rename(x, m):
    if isinstance(x, list):
        return [x[0] if not isinstance(x[0], list) and k == 0 else rename(y, m) for k, y in enumerate(x)] if x else []
    b = base(x)
    if b in m:
        return (x[0] if x[0] in '*^' else '') + m[b]
    return x


def star_in(atom, label):
    """Stars the first site of label in a positive atom. Returns whether it did."""
    if not isinstance(atom, list) or not atom:
        return False
    h = atom[0]
    if h in ('NOT', 'ALL', 'IF', 'ONE', 'SET') or h in OPS:
        return False
    if h == 'OR':
        return any(star_in(a, label) for a in atom[1])

    def walk(y):
        for k, z in enumerate(y):
            if isinstance(z, list):
                if walk(z):
                    return True
            elif k and z == label:
                y[k] = '*' + label
                return True
        return False
    return walk(atom)


def closed(atoms):
    """atoms with carets as stars and each label that no site makes starred at a positive site, or None."""
    atoms = unmark(atoms)
    for l in labels(atoms):
        if l not in made(atoms) and not any(star_in(a, l) for a in atoms):
            return None
    return atoms


def canon(atoms):
    """The text of atoms with labels numbered in order and marks gone, and that order."""
    order = labels(atoms)
    return show(rename(plain(atoms), {l: 'L%d' % k for k, l in enumerate(order)})), order


def helper_kind(atoms, form_kind):
    text = show(atoms)
    return 'DET' if form_kind == 'DET' or 'ex_input' in text or 'ex_output' in text else 'RULE'


def rule(kind, name, atoms):
    return '(%s %s %s)' % (kind, name, ' '.join(show(a) for a in atoms))


def read(name, sites):
    """The atom that reads name at sites, each (column, label with its mark)."""
    return [name] + [[':' + c, l] for c, l in sites]


class Fresh:
    def __init__(self, ls):
        self.k, self.taken = 0, '\n'.join(ls)

    def __call__(self):
        while True:
            self.k += 1
            name = '&wc%d' % self.k
            if name not in self.taken:
                return name


def exports(or_atom):
    bs = or_atom[1:]
    return [l for l in made(bs[0]) if all(l in labels(b) for b in bs[1:])]


def split_branch(b, first, E, kind, fresh):
    """Branch b to a helper. Returns (helper forms, the branch that reads it), or None. An `=` on an exported label that no positive site binds stays in the branch, or becomes a renamed read."""
    rest, stay = [], []
    for a in b:
        if a[0] == '=' and base(a[1]) in E and base(a[1]) not in [base(t) for r in b if r[0] not in OPS and r[0] != 'NOT' for t in flatten(r)]:
            stay.append(a)
        else:
            rest.append(a)
    if not rest:
        return None
    alias, kept = {}, []
    for a in stay:
        y = a[2]
        if y != '0' and y in labels(rest) and y not in E:
            alias[y] = base(a[1])
        else:
            kept.append(a)
    body = closed(rest)
    if body is None:
        return None
    name = fresh()
    sites = []
    for l in labels(rest):
        if l in alias:
            sites.append((l, ('*' if first else '') + alias[l]))
        elif l in E:
            sites.append((l, ('*' if first else '') + l))
        elif any(l in labels(a) for a in kept):
            sites.append((l, '*' + l))
    return [rule(helper_kind(rest, kind), name, body)], [read(name, sites)] + kept


def flatten(x):
    return [z for y in x for z in flatten(y)] if isinstance(x, list) else [x]


def union_of(kind, head, branches, fresh, E, nested):
    """The forms of a union of branches, flat or as nested 2-way unions."""
    bs = list(branches)
    if not nested or len(bs) < 3:
        return [rule(kind, head, [['OR'] + bs])]
    forms = []
    while len(bs) > 2:
        name = fresh()
        forms.append(rule(kind, name, [['OR', bs[0], bs[1]]]))
        bs[:2] = [[read(name, [(l, '*' + l) for l in E])]]
    return forms + [rule(kind, head, [['OR'] + bs])]


def union_cuts(kind, head, or_atom, fresh, shape=''):
    bs, E = or_atom[1:], exports(or_atom)
    if not E:
        return []
    out = []

    def helpers(which):
        forms, new = [], []
        for k, b in enumerate(bs):
            got = split_branch(b, k == 0, E, kind, fresh) if k in which else None
            if got:
                forms += got[0]
                new.append(got[1])
            else:
                new.append(b)
        return forms, new

    big = [k for k, b in enumerate(bs) if len(b) >= 2 or (b[0][0] in ('OR', 'IF', 'ALL'))]
    if big:
        forms, new = helpers(set(big))
        if forms:
            out.append(Cut(shape + 'union-branches', forms + union_of(kind, head, new, fresh, E, False)))
            if len(bs) >= 3:
                forms2, new2 = helpers(set(big))
                out.append(Cut(shape + 'union-nested', forms2 + union_of(kind, head, new2, fresh, E, True)))
        if len(big) > 1:
            k = max(big, key=lambda k: len(show(bs[k])))
            forms, new = helpers({k})
            if forms:
                out.append(Cut(shape + 'union-branch', forms + union_of(kind, head, new, fresh, E, False)))
    if len(bs) >= 3:
        out.append(Cut(shape + 'union-nest-only', union_of(kind, head, bs, fresh, E, True)))
    return out


def alias(atoms):
    """Whether atoms are one read of a derived relation with each site a fresh label: a copy of that relation, which only moves it nearer in the program."""
    if len(atoms) != 1 or not str(atoms[0][0]).startswith('&'):
        return False
    return all(t[0] == '*' or t.startswith((':', '&')) for t in flatten(atoms[0]))


def site(atom, column):
    """The label at column of atom, or None."""
    return next((base(s[1]) for s in atom[1:] if isinstance(s, list) and s[0] == ':' + column), None)


def needs(atoms):
    """The labels that atoms, in their order, have to read from outside: the labels of a mode that no earlier atom binds, the outer labels of a NOT, ALL, OR or IF that no earlier atom binds, and the labels of a compare that no atom binds."""
    bound, need, compared = set(), set(), set()
    for a in atoms:
        if a[0] in OPS:
            compared |= set(labels(a)) - set(made(a))
            bound |= set(made(a))
        elif a[0] in ('NOT', 'ALL', 'OR', 'IF'):
            need |= set(labels(a)) - set(made(a)) - bound
            bound |= need | (set(made(a)) if a[0] in ('OR', 'IF') else set())
        else:
            if a[0] in MODES:
                need |= min(({site(a, c) for c in m.split()} - {None} - bound for m in MODES[a[0]]), key=len)
            bound |= need | set(labels(a))
    return need | (compared - bound)


def carried(a, b):
    """The indexes of the atoms of a that bind what atoms b need, with what those atoms need in turn, or None."""
    take = set()
    while True:
        need = needs([a[j] for j in sorted(take)] + b)
        if not need:
            return sorted(take)
        new = {next((j for j, x in enumerate(a) if l in made(x)), None) for l in need}
        if None in new or new <= take:
            return None
        take |= new


def project(atom, want):
    """atom with only the sites of labels in want, and the sites of no label. A lib relation keeps its sites."""
    if atom[0] != 'input' and not str(atom[0]).startswith('&'):
        return atom
    sites = [s for s in atom[1:] if not labels([s]) or set(labels([s])) & want]
    return [atom[0]] + sites if sites else atom


def chain_cut(kind, head, atoms, k, keep, fresh):
    """Atoms before k to a helper, and the form that reads it."""
    a, b = atoms[:k], atoms[k:]
    if set(labels(a)) - set(made(a)) or alias(a):
        return None
    later = set(labels(b)) | keep
    name = fresh()
    sites = [(l, '*' + l) for l in made(a) if l in later]
    if not sites:
        return None
    return Cut('chain', [rule(helper_kind(a, kind), name, a), rule(kind, head, [read(name, sites)] + b)])


def tail_cuts(kind, head, atoms, n, k, keep, fresh):
    """Atoms k to n to a helper that the atoms before k read. Atoms from n on are marks that stay with the form. A helper reads no bound label from the form, so where the atoms need one, it starts with what binds that label."""
    a, b, marks = atoms[:k], atoms[k:n], atoms[n:]
    if set(labels(a)) - set(made(a)):
        return []
    later = set(labels(a)) | set(labels(marks)) | keep
    need = needs(b)

    def cut(shape, front):
        body = closed(front + b)
        if body is None or alias(body):
            return []
        sites = [(l, l if l in made(a) else '*' + l) for l in labels(body) if l in later]
        if not sites:
            return []
        name = fresh()
        return [Cut(shape, [rule(helper_kind(body, kind), name, body), rule(kind, head, a + [read(name, sites)] + marks)])]

    if not need:
        return cut('chain-tail', [])
    out = []
    take = carried(a, b)
    if take is not None:
        counts = [l for j in take for l in labels(a[j])]
        want = set(labels(b)) | need | {l for l in counts if counts.count(l) > 1}
        front = [project(a[j], want) for j in take]
        if front != a[-len(front):] and needs(front + b) == set():  # that helper is the one of the cut at an earlier atom
            out += cut('chain-tail+carry', front)
    return out


def or_extract(kind, head, atoms, j, keep, fresh):
    """The OR at j to a union of its own, when each outer label stands in each branch."""
    o = atoms[j]
    others = atoms[:j] + atoms[j + 1:]
    bound = set(made(others))
    outer = [l for l in labels(o) if l not in made(o)]
    if any(l not in bound for l in outer) or not all(l in labels(b) for b in o[1:] for l in outer):
        return []
    o2 = unmark(o)
    if any(not star_in(a, l) for l in outer for a in [['OR', o2[1]]]):
        return []
    E = exports(o2)
    later = set(labels(others)) | keep
    sites = [(l, l if l in bound else '*' + l) for l in E if l in later]
    name = fresh()
    cuts = []
    me = read(name, sites)
    rest = atoms[:j] + [me] + atoms[j + 1:]
    tail = rule(kind, head, rest)
    if not any(needs(b) for b in o2[1:]):  # the star of an outer label stands in the first branch alone
        cuts.append(Cut('or-extract', [rule(helper_kind(o, kind), name, [o2]), tail]))
    for c in union_cuts(kind, name, o2, fresh, 'or-extract+'):
        cuts.append(Cut(c.shape, c.forms + [tail]))
    return cuts


def or_distribute(kind, head, atoms, j, keep, fresh, ones):
    """The atoms before the OR at j to a helper, each branch reading it, and a union that the atoms after the OR read."""
    pre, o, post = atoms[:j], atoms[j], atoms[j + 1:]
    if not pre or set(labels(pre)) - set(made(pre)):
        return []
    E0 = made(o[1:][0])
    later = set(labels(o)) | set(labels(post)) | keep
    need = [l for l in made(pre) if l in later]
    if not need:
        return []
    w = fresh()
    forms = [rule(helper_kind(pre, kind), w, pre)]
    first = [read(w, [(l, '*' + l) for l in need])]
    rest = [read(w, [(l, l) for l in need])]
    bs = [first + o[1]] + [rest + b for b in o[2:]]
    u = ['OR'] + bs
    E = exports(u)
    if post or ones:
        name = fresh()
        tail = [rule(kind, head, [read(name, [(l, '*' + l) for l in E if l in set(labels(post)) | keep or l in ones])] + post)]
    else:
        name, tail = head, []
    out = [Cut('or-distribute', forms + [rule(kind, name, [u])] + tail)]
    for c in union_cuts(kind, name, u, fresh, 'or-distribute+'):
        out.append(Cut(c.shape, forms + c.forms + tail))
    return out


def rule_cuts(ls, i, fresh):
    f = parse(ls[i])
    kind, head, atoms = f[0], f[1], f[2:]
    if not atoms or any(not isinstance(a, list) for a in atoms):
        return []
    keep = reads(ls[i + 1:], head)
    out = []
    if len(atoms) == 1 and atoms[0][0] == 'OR':
        return union_cuts(kind, head, atoms[0], fresh)
    n = next((k for k, a in enumerate(atoms) if a[0] in ('ONE', 'SET')), len(atoms))
    for k in range(1, n):
        c = chain_cut(kind, head, atoms, k, keep, fresh)
        if c:
            out.append(c)
        out += tail_cuts(kind, head, atoms, n, k, keep, fresh)
    ones = {l for a in atoms[n:] for l in labels(a)}
    for j, a in enumerate(atoms):
        if a[0] == 'OR':
            out += or_extract(kind, head, atoms, j, keep, fresh)
            out += or_distribute(kind, head, atoms, j, keep, fresh, ones)
    return out


class Init:
    def __init__(self, text):
        f = parse(text)
        self.f, self.name, self.comp = f, f[1], f[2]
        self.key = None
        self.bodies = []  # (where, atoms, head labels): where is 'key', or (key group?, index of the part or the port)
        for k, p in enumerate(f[3:]):
            if not isinstance(p, list):
                continue
            if p[0] == 'key':
                self.key = p
                self.bodies.append(('key', p[1], []))
                for m, q in enumerate(p[2:]):
                    if isinstance(q, list):
                        self.bodies.append(((k, m), q[2:], labels(q[1])))
            elif len(p) >= 2 and isinstance(p[1], list):
                self.bodies.append(((k, None), p[2:], labels(p[1])))
        self.key_labels = [] if self.key is None else [base(t) for t in flatten(self.key[1]) if isinstance(t, str) and t[0] == '^' and base(t)]

    def own(self, atoms):
        return any(isinstance(t, str) and t.startswith(self.name + '.') for t in flatten(atoms))

    def text(self, new):
        """The form with each body in new replaced: where -> atoms."""
        f = parse(show(self.f))
        for where, atoms in new.items():
            if where == 'key':
                p = next(p for p in f[3:] if isinstance(p, list) and p[0] == 'key')
                p[1] = atoms
            else:
                k, m = where
                p = f[3 + k]
                q = p if m is None else p[2:][m]
                q[2:] = atoms
        return show(f)


def body_sites(init, where, head, atoms, cols):
    """The sites that a body reads a helper with. cols maps a label of atoms to the helper's column."""
    out, keys = [], set(init.key_labels)
    for l in labels(atoms):
        if where == 'key':
            if l in keys:
                out.append((cols[l], '^' + l))
        elif l in keys:
            out.append((cols[l], l))
        elif l in head:
            out.append((cols[l], '*' + l))
    return out


def extract(init, where, atoms, head, kind, fresh, seen):
    """Body atoms to a helper. seen maps the text of a helper's body to its name and labels. Returns (new forms, new atoms), or None."""
    if init.own(atoms) or (len(atoms) < 2 and atoms and atoms[0][0] not in ('OR', 'IF', 'ALL')):
        return None
    rest = [a for a in atoms if not (a[0] == '=' and a[2] == '0')]
    stay = [a for a in atoms if a[0] == '=' and a[2] == '0']
    if not rest or (len(rest) < 2 and rest[0][0] not in ('OR', 'IF', 'ALL')):
        return None
    body = closed(rest)
    if body is None and init.key is not None and where != 'key':  # a key label that only a NOT or a compare reads: the helper reads the key's body too
        keys = set(init.key_labels)
        rest = rename(init.key[1], {l: l + 'K' for l in labels(init.key[1]) if l not in keys}) + rest
        body = closed(rest)
    if body is None:
        return None
    key, order = canon(rest)
    forms = []
    if key not in seen:
        name = fresh()
        seen[key] = (name, order)
        forms.append(rule(helper_kind(rest, kind), name, body))
    name, first = seen[key]
    cols = dict(zip(order, first))
    return forms, [read(name, body_sites(init, where, head, rest, cols))] + stay


def shared(init, kind, fresh):
    """The longest run of atoms that two bodies begin with, to a helper that each of those bodies reads."""
    bodies = [b for b in init.bodies if not init.own(b[1]) and len(b[1]) >= 2]
    best = None
    for x in range(len(bodies)):
        for y in range(x + 1, len(bodies)):
            a, b = bodies[x][1], bodies[y][1]
            for m in range(min(len(a), len(b)), 1, -1):
                if canon(a[:m])[0] == canon(b[:m])[0]:
                    if best is None or m > best[0]:
                        best = (m, x)
                    break
    if best is None:
        return []
    m, x = best
    want = canon(bodies[x][1][:m])[0]
    group = [b for b in bodies if len(b[1]) >= m and canon(b[1][:m])[0] == want]
    prefix = bodies[x][1][:m]
    body = closed(prefix)
    if body is None:
        return []
    name = fresh()
    order = canon(prefix)[1]
    new = {}
    keys = set(init.key_labels)
    for where, atoms, head in group:
        pre, tail = atoms[:m], atoms[m:]
        cols = dict(zip(canon(pre)[1], order))
        later = set(labels(tail)) | set(head)
        sites = []
        for l in labels(pre):
            if where == 'key':
                if l in keys:
                    sites.append((cols[l], '^' + l))
                elif l in later:
                    sites.append((cols[l], '*' + l))
            elif l in keys:
                sites.append((cols[l], l))
            elif l in later:
                sites.append((cols[l], '*' + l))
        new[where] = [read(name, sites)] + tail
    return [Cut('init-shared', [rule(helper_kind(prefix, kind), name, body), init.text(new)])]


def reuse_table(ls, i):
    """Bodies of earlier RULE forms, by text, for a cut body to read in place of a new helper."""
    seen = {}
    for x in ls[:i]:
        if not x.startswith('(RULE'):
            continue
        f = parse(x)
        atoms = f[2:]
        if atoms and all(isinstance(a, list) for a in atoms) and not any(a[0] in ('OR', 'ONE', 'SET') for a in atoms):
            key, order = canon(atoms)
            seen.setdefault(key, (f[1], order))
    return seen


def init_cuts(ls, i, fresh):
    init = Init(ls[i])
    kind = 'INIT'

    def cut(shape, wheres):
        seen = reuse_table(ls, i)
        forms, new = [], {}
        for where, atoms, head in init.bodies:
            if wheres is not None and where not in wheres:
                continue
            got = extract(init, where, atoms, head, kind, fresh, seen)
            if got:
                forms += got[0]
                new[where] = got[1]
        return Cut(shape, forms + [init.text(new)]) if new else None

    out = [cut('init-bodies', None)]
    ports = [b[0] for b in init.bodies if b[0] != 'key']
    if init.key is not None:
        out.append(cut('init-ports', set(ports)))
        same = {b[0] for b in init.bodies if b[1] and canon(b[1])[0] == canon(init.key[1])[0]}
        out.append(cut('init-key', {'key'} | same))
    if len(init.bodies) > 1:
        for where in sorted(ports, key=lambda w: -len(show(next(b[1] for b in init.bodies if b[0] == w))))[:6]:
            out.append(cut('init-body', {where}))
    out += shared(init, kind, fresh)
    return [c for c in out if c]


def candidates(ls, i):
    """The cuts of form i of ls, with no two of one text."""
    x, fresh = ls[i], Fresh(ls)
    try:
        cuts = init_cuts(ls, i, fresh) if x.startswith('(INIT') else rule_cuts(ls, i, fresh) if x.startswith(('(RULE', '(DET')) else []
    except (IndexError, ValueError, StopIteration, TypeError):
        return []
    seen, out = set(), []
    for c in cuts:
        t = re.sub(r'&wc\d+', '&w', '\n'.join(c.forms))
        if t not in seen:
            seen.add(t)
            out.append(c)
    return out
