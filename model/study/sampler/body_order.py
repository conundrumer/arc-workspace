"""A random valid order of a body's tokens, for the walks of live_rows.py.

A body is a set of items. An item is an atom, an OR or an ALL. A branch of an OR, the guard of an ALL and the conclusion of an ALL are bodies. draw gives a body's items an order by the
law of S.BodyOrders: the next item is uniform over those that S.atom_binds lets stand there. An OR's branches take a random order, and the conclusion of an ALL stays after its guard. A
label's first occurrence takes the `*` (the `^` where the label is a key), and labels take new numbers in that order, in the body and in the tokens after it.

The walk is the last check: a walk that does not end cleanly refuses the order. An IF has no walk in live.py, so a body with an IF has no order here.
"""
import sample2_col as S
from live import ALSO_TOK, M


class NoOrder(Exception):
    """The tokens hold what this module does not order, or fit no body of the form's text."""


class Atom:
    text = None

    def __init__(self, start, end, neg):
        self.start, self.end, self.neg = start, end, neg

    def size(self):
        return 1

    def arranged(self, bound, outer, rng):
        return self


class Or:
    def __init__(self, branches, text=None):
        self.branches, self.text = branches, text

    def size(self):
        return len(self.branches)

    def arranged(self, bound, outer, rng):
        got = [arrange(b, bound, outer, rng) for b in self.branches]
        rng.shuffle(got)
        return Or(got, self.text)


class All:
    def __init__(self, guard, conclusion, text=None):
        self.guard, self.conclusion, self.text = guard, conclusion, text

    def size(self):
        return 1

    def arranged(self, bound, outer, rng):
        g, c = plain(self.text[1]), plain(self.text[2])
        guard = arrange(self.guard, bound, outer | S.atom_labels(c), rng)
        return All(guard, arrange(self.conclusion, S.atoms_bound(g, bound, outer), outer | S.atom_labels(g), rng), self.text)


def plain(atoms):
    """The atoms of a list, less the ONE and SET parts of a DET."""
    return [a for a in atoms if isinstance(a, list) and a[:1] not in (['ONE'], ['SET'])]


def bodies_of(target):
    """The bodies of a form's text, each a list of atoms: a RULE's or a DET's body, an INIT's key and ports. Other kinds give none."""
    f = S.M_sexprs(target)[0]
    if f[0] in ('RULE', 'DET'):
        return [plain(f[2:])]
    out = []
    for g in f[3:] if f[0] == 'INIT' else ():
        if isinstance(g, list) and g[:1] == ['key']:
            out.append(plain(g[1]))
            out += [plain(p[2:]) for p in g[2:] if isinstance(p, list)]
        elif isinstance(g, list) and g:
            out.append(plain(g[2:]))
    return out


def fits(items, atoms):
    """Whether items, parsed from tokens, have the shape of the atoms of a body's text, item by item. Where they do, each item takes its text."""
    if len(items) != len(atoms):
        return False
    for x, a in zip(items, atoms):
        if isinstance(x, Or):
            parts = [plain(p) for p in a[1:] if isinstance(p, list)]
            if a[0] != 'OR' or len(parts) != len(x.branches) or not all(fits(b, p) for b, p in zip(x.branches, parts)):
                return False
        elif isinstance(x, All):
            if a[0] != 'ALL' or not fits(x.guard, plain(a[1])) or not fits(x.conclusion, plain(a[2])):
                return False
        elif a[0] in ('OR', 'ALL', 'IF') or (a[0] == 'NOT') != x.neg:
            return False
        x.text = a
    return True


def parse(V, toks):
    """The items of a body's tokens."""
    n, all_tok = len(toks), V.id('ALL')
    if_tok = next((t for t in set(toks) if V.name(t) == 'IF'), None)

    def atom_end(i):
        j, rec, prev = i + (2 if toks[i] == M.NOT else 1), 0, None
        while j < n:
            t = toks[j]
            k = V.kind(t)
            if k == 'column' and prev is not None and V.kind(prev) == 'column':
                rec += 1
            if t == M.END:
                if not rec:
                    break
                rec -= 1
            elif not rec and (t in (ALSO_TOK, M.OR, all_tok, M.NOT, if_tok) or t in M.CMP or k in S.RELATION_KINDS):
                break
            prev = t
            j += 1
        return j

    def body(i):
        items = []
        while i < n and toks[i] not in (M.END, ALSO_TOK):
            t = toks[i]
            if t == if_tok:
                raise NoOrder('IF')
            if t == M.OR:
                branches, i = [], i + 1
                while True:
                    b, i = body(i)
                    branches.append(b)
                    if i >= n:
                        raise NoOrder('an OR with no END')
                    i += 1
                    if toks[i - 1] == M.END:
                        break
                items.append(Or(branches))
            elif t == all_tok:
                guard, i = body(i + 1)
                if i >= n or toks[i] != M.END:
                    raise NoOrder('an ALL with no conclusion')
                conclusion, i = body(i + 1)
                if i >= n or toks[i] != M.END:
                    raise NoOrder('an ALL with no END')
                i += 1
                items.append(All(guard, conclusion))
            elif t == M.NOT or t in M.CMP or V.kind(t) in S.RELATION_KINDS:
                j = atom_end(i)
                items.append(Atom(i, j, t == M.NOT))
                i = j
            else:
                raise NoOrder('token %s starts no item' % V.name(t))
        return items, i
    items, i = body(0)
    if i != n:
        raise NoOrder('tokens after the body')
    return items


def draw(atoms, bound, outer, rng):
    """[(position in atoms, the labels bound before it)] of a random valid order, by the step law of S.BodyOrders. bound: the labels bound before the atoms. outer: the labels that
    stand outside them. Where no atom may stand next, any atom may, as in S.BodyOrders.ready."""
    bound, left, out = set(bound), list(range(len(atoms))), []
    while left:
        got = {i: S.atom_binds(atoms[i], bound, outer | S.atom_labels(atoms[:i] + atoms[i + 1:])) for i in left}
        ready = {i: b for i, b in got.items() if b is not None} or {i: S.atom_labels(atoms[i]) for i in left}
        i = rng.choice(sorted(ready))
        out.append((i, frozenset(bound)))
        bound |= ready[i]
        left.remove(i)
    return out


def arrange(items, bound, outer, rng):
    """items in a random valid order, each arranged inside."""
    atoms = [x.text for x in items]
    return [items[i].arranged(before, outer | S.atom_labels(atoms[:i] + atoms[i + 1:]), rng) for i, before in draw(atoms, bound, outer, rng)]


def flat(items, toks, sites):
    """(token, label or None) of the arranged items, in order."""
    out = []
    for x in items:
        if isinstance(x, Atom):
            out += [(toks[i], sites.get(i)) for i in range(x.start, x.end)]
        elif isinstance(x, Or):
            out.append((M.OR, None))
            for j, b in enumerate(x.branches):
                out += flat(b, toks, sites)
                out.append((ALSO_TOK if j < len(x.branches) - 1 else M.END, None))
        else:
            out.append((ALL_TOK[0], None))
            out += flat(x.guard, toks, sites)
            out.append((M.END, None))
            out += flat(x.conclusion, toks, sites)
            out.append((M.END, None))
    return out


ALL_TOK = [None]  # the ALL token of the vocabulary in use


def choices(items):
    """Whether the items have more than one order."""
    return len(items) > 1 or any(x.size() > 1 or (isinstance(x, Or) and any(choices(b) for b in x.branches)) or (isinstance(x, All) and choices(x.guard)) for x in items)


def shuffle(V, span, rest, base, label_tok, rng, bodies):
    """(the body's tokens span in a random valid order, the tokens rest after it with the new label numbers, whether the body has other orders). base: the labels of the form before the
    body. bodies: the bodies of the form's text not yet taken; this call takes the first that fits. Raises NoOrder where the body has no order here."""
    ALL_TOK[0] = V.id('ALL')
    sites, carets, n = {}, set(), 0
    for i, t in enumerate(span):
        if t in (M.STAR, M.CARET):
            sites[i] = base + n
            if t == M.CARET:
                carets.add(base + n)
            n += 1
        elif V.kind(t) == 'label':
            sites[i] = int(V.name(t)[1:])
    items = parse(V, span)
    body = next((b for b in bodies if fits(items, b)), None)
    if body is None:
        raise NoOrder('no body of the text fits the tokens')
    bodies.remove(body)
    free = S.atom_labels(body) - S.atom_labels(body, True)
    num, out = {}, []
    for t, lab in flat(arrange(items, free, free, rng), span, sites):
        if lab is None:
            out.append(t)
        elif lab < base:
            out.append(label_tok[lab])
        elif lab in num:
            out.append(label_tok[num[lab]])
        else:
            num[lab] = base + len(num)
            out.append(M.CARET if lab in carets else M.STAR)
    if len(num) != n:
        raise NoOrder('a label has lost its first site')
    after = [label_tok[num[int(V.name(t)[1:])]] if V.kind(t) == 'label' and int(V.name(t)[1:]) in num else t for t in rest]
    return out, after, choices(items)
