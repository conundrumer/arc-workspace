#!/usr/bin/env python
"""The fixed order of the atoms of a body, and the canonical form of a query.

The order breaks the symmetry of atoms: the QueryHash of a query is the same for each order of its atoms, so a writer needs to write one order only.
An atom has a key, from its first model token: the plain atoms (a relation, and OR) first, ordered by the token id of the relation; then the atoms that need
their labels bound (NOT, a comparison, ALL), ordered by the token id of their first token. Atoms with the same key are tied: they may stand in any order.
The order holds in a body, in each branch of an OR and in each port body, each by itself. It does not reach into an ALL.

    order = AtomOrder(id_of)              # id_of(name) -> the token id of a token name ('NOT', '=', 'ALL', 'OR', a relation such as 'input' or '&r3')
    order.key(tok)                        # the key of an atom that starts with token id tok
    order.canonical(form)                 # the form (one S-expression line), with each body in the fixed order and the fresh labels (`*`, `^`) marked at their first use
    order.canonical_forms(forms)          # the same for a list of forms

`canonical` keeps a form as it is where each of its bodies stands in order. It has no other imports, so a data script can call it.
"""
import itertools
import re

CMP_NAMES = ('=', '!=', '<', '<=', '>', '>=')
LATE_NAMES = ('NOT', 'ALL') + CMP_NAMES  # the atoms that need their labels bound
_LABEL = re.compile(r'(?<![\w:*^])([*^]?)([A-Z][A-Za-z0-9]*)(?![\w])')


def parse(text):
    """The tree of an S-expression: a str for a symbol, a list for a list."""
    toks = re.findall(r'[()]|[^\s()]+', text)
    pos = 0

    def go():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t != '(':
            return t
        out = []
        while toks[pos] != ')':
            out.append(go())
        pos += 1
        return out
    return go()


def render(tree):
    return tree if isinstance(tree, str) else '(' + ' '.join(render(x) for x in tree) + ')'


def atom_heads(tree):
    """The relation names of the atoms of a form, in text order: the order of the relation tokens of its model tokens."""
    out = []

    def atom(a):
        if not (isinstance(a, list) and a and isinstance(a[0], str)):
            return
        h = a[0]
        if h == 'NOT':
            atom(a[1])
        elif h == 'OR':
            for b in a[1:]:
                for x in b:
                    atom(x)
        elif h == 'ALL':
            for g in a[1]:
                atom(g)
            atom(a[2])
        elif h not in CMP_NAMES:
            out.append(h)
    kind = tree[0]
    if kind in ('RULE', 'DET'):
        for a in tree[2:]:
            atom(a)
    elif kind in ('INIT', 'RIGID_DET'):
        for el in tree[3:]:
            if isinstance(el, list) and el and el[0] == 'key':
                for a in el[1]:
                    atom(a)
                ports = el[2:]
            else:
                ports = [el]
            for p in ports:
                for a in p[2:]:
                    atom(a)
    return out


class AtomOrder:
    def __init__(self, id_of, or_late=False, dep=False):
        """dep: an atom moves before an atom of a larger key only where it reads no label that atom made (DepOrder, below); else the order is the sort by key alone.
        or_late: OR counts with the atoms that need their labels bound (default: OR is a plain atom, keyed by its own token)."""
        self.base_id_of = id_of
        self.extra = {}
        self.id_of = lambda name: self.extra[name] if name in self.extra else self.base_id_of(name)
        self.or_late = or_late
        self.dep = dep
        self.late = {id_of(n) for n in LATE_NAMES} | ({id_of('OR')} if or_late else set())
        self.big = 1 << 20

    def learn(self, forms, rel_tokens):
        """Learns the token of each relation name that id_of does not give (a method of an INIT, `&r3.cell`), from the relation tokens (token ids of the relation kinds, in order)
        of the model tokens of each form: rel_tokens[i] for forms[i]."""
        for form, toks in zip(forms, rel_tokens):
            names = atom_heads(parse(form))
            if len(names) == len(toks):
                for n, t in zip(names, toks):
                    if self.base_id_of(n) is None:
                        self.extra[n] = int(t)

    def key(self, tok):
        """The key of an atom that starts with token id tok."""
        return (self.big if tok in self.late else 0) + tok

    def atom_key(self, atom):
        """The key of an atom of the tree."""
        return self.key(self.id_of(atom[0]))

    # ---- the order of a list of atoms

    def _list(self, atoms):
        """(atoms in order, whether they moved); the branches of an OR in them in order too."""
        moved = False
        out = []
        for a in atoms:
            if isinstance(a, list) and a and a[0] == 'OR':
                br = []
                for b in a[1:]:
                    nb, m = self._list(b) if isinstance(b, list) else (b, False)
                    br.append(nb)
                    moved |= m
                a = ['OR'] + br
            out.append(a)
        keys = [self.atom_key(a) if isinstance(a, list) and a else -1 for a in out]
        if any(k < 0 for k in keys):  # a bare symbol (a proposer): leave the list
            return out, moved
        order = self._sorted(out, keys)
        if order != list(range(len(out))):
            moved = True
            out = [out[i] for i in order]
        return out, moved

    def _sorted(self, atoms, keys):
        """The indices of atoms in the fixed order. Stable: tied atoms stay. With dep, the least order in which each atom stands after the atoms that made a label it reads."""
        if not self.dep:
            return sorted(range(len(atoms)), key=lambda i: keys[i])
        names = [set(n for _, n in _LABEL.findall(render(a))) - {'NOT', 'OR', 'ALL'} for a in atoms]
        first = {}
        for i, ns in enumerate(names):
            for n in ns:
                first.setdefault(n, i)
        need = [set(first[n] for n in names[i] if first[n] != i) for i in range(len(atoms))]
        left, order = set(range(len(atoms))), []
        while left:
            ready = [i for i in left if need[i] <= set(order)]
            if not ready:  # a cycle: keep the rest as written
                order += sorted(left)
                break
            i = min(ready, key=lambda j: (keys[j], j))
            order.append(i)
            left.discard(i)
        return order

    def _marks(self, bodies):
        """{label name: its mark} for the fresh labels (`*`, `^`) in the trees."""
        marks = {}
        for b in bodies:
            for m, name in _LABEL.findall(render(b)):
                if m and name not in marks:
                    marks[name] = m
        return marks

    def _remark(self, atoms, marks):
        """The atoms with each label of marks marked at its first use only."""
        seen = set()

        def sub(m):
            name = m.group(2)
            if name not in marks:
                return m.group(0)
            if name in seen:
                return name
            seen.add(name)
            return marks[name] + name
        return [parse(_LABEL.sub(sub, render(a))) for a in atoms]

    def _body(self, atoms):
        marks = self._marks(atoms)
        new, moved = self._list(atoms)
        if not moved:
            return atoms
        return self._remark(new, marks)

    def canonical_tree(self, tree):
        kind = tree[0]
        if kind in ('RULE', 'DET'):
            head, body = tree[:2], tree[2:]
            if any(isinstance(x, str) for x in body):  # a proposer
                return tree
            return head + self._body(body)
        if kind in ('INIT', 'RIGID_DET'):
            head, rest = tree[:3], tree[3:]
            out = []
            for el in rest:
                if isinstance(el, list) and el and el[0] == 'key':  # (key (key-body atoms) port ...)
                    key = el[1]
                    ports = [self._port(p) for p in el[2:]]
                    out.append(['key', self._body(key)] + ports)
                else:
                    out.append(self._port(el))
            return head + out
        return tree

    def _port(self, port):
        """(name head atom ...): the atoms in order."""
        if not (isinstance(port, list) and len(port) >= 2):
            return port
        return port[:2] + self._body(port[2:])

    def canonical(self, form):
        """The canonical form of one S-expression line (a str)."""
        tree = parse(form)
        new = self.canonical_tree(tree)
        return form if new == tree else render(new)

    def candidates(self, form, limit=24):
        """The forms that the order allows for the atoms of `form`: the canonical form, and for a RULE or DET each order of its tied top-level atoms (at most `limit`)."""
        tree = parse(form)
        if self.dep or tree[0] not in ('RULE', 'DET') or any(isinstance(x, str) for x in tree[2:]):
            return [self.canonical(form)]
        body = tree[2:]
        marks = self._marks(body)
        new, moved = self._list(body)
        if not moved and len(new) < 2:
            return [form]
        keys = [self.atom_key(a) for a in new]
        groups = []
        for a, k in zip(new, keys):
            if groups and groups[-1][0] == k:
                groups[-1][1].append(a)
            else:
                groups.append((k, [a]))
        out, orders = [], [[]]
        for _, g in groups:
            perms = list(itertools.permutations(g))[:limit]
            orders = [o + list(p) for o in orders for p in perms][:limit]
        for o in orders:
            atoms = self._remark(o, marks) if (moved or o != body) else o
            out.append(render(tree[:2] + atoms))
        return out

    def canonical_forms(self, forms):
        return [self.canonical(f) for f in forms]


def canonical(forms, id_of, or_late=False, dep=True):
    """The forms (S-expression lines), each with its bodies in the fixed order. id_of(name) is the token id of a token name. For a method of an INIT (`&r3.cell`), id_of must
    give its token, or use AtomOrder.learn. dep=True: the order the legal plan writes (an atom stands after the atoms that made the labels it reads, else by key);
    dep=False: the sort by key alone."""
    return AtomOrder(id_of, or_late, dep).canonical_forms(forms)
