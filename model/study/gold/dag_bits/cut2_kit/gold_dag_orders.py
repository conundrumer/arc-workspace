"""The orders of a form, as text. Nothing here runs the engine.

A site is a list of items with no order of their own: the atoms of a RULE's or a DET's body, of an INIT's or a RIGID_DET's key group and of each port, of each branch of an OR and each part of an ALL or an IF, and the branches of an OR. A form's orders are the products of its sites' orders. The ports of an INIT keep the order that the decoder gives them.

The sites of a form go in the order of their sorted item keys, so an order tuple reads no written position of a site; an item inside a site is named by its written place in the site, and the sampler draws from the items sorted by text.

A site's order is valid by rule where each NOT and comparison comes after the labels that it reads and that the site binds. In text, a label's first occurrence takes its mark. The reader and the walk check the rest.

Sites sort their items by text with marks gone, so the set of orders, the sample and its seed read no written position.
"""
import collections, hashlib, itertools, json, math, random, re

from gold_chain import parse, show

CMP = ('=', '!=', '<', '<=', '>', '>=')
KEYWORDS = {'NOT', 'OR', 'ALL', 'IF', 'ALSO', 'END'}
LABEL = re.compile(r'^([*^]?)([A-Z][A-Za-z0-9_]*)$')
MAX_COUNT_ITEMS = 20  # a site with more items has no exact count


def plain(x):
    return [plain(y) for y in x] if isinstance(x, list) else (x[1:] if x[0] in '*^' and len(x) > 1 and x[1].isupper() else x)


def key_of(item):
    """The text of item with marks gone and the sites inside it in sorted order: a body (a list of atoms) and the branches of an OR sort by their keys, so the key reads no written place of an atom inside the item."""
    if isinstance(item, str):
        return plain(item)
    ch = [key_of(y) for y in item]
    if item and all(isinstance(y, list) for y in item):
        ch.sort()
    elif item and item[0] == 'OR':
        ch = ch[:1] + sorted(ch[1:])
    return '(' + ' '.join(ch) + ')'


def label_refs(x):
    """[(parent list, index, marker, name)] of the label tokens of x, in token order."""
    out = []

    def go(y):
        for i, z in enumerate(y):
            if isinstance(z, str):
                m = LABEL.match(z)
                if m and m[2] not in KEYWORDS:
                    out.append((y, i, m[1], m[2]))
            else:
                go(z)
    go(x)
    return out


def is_guard(a):
    return a[0] == 'NOT' or a[0] in CMP


def is_atoms(x):
    return isinstance(x, list) and all(isinstance(y, list) for y in x)


class Body:
    """The items of a site, as trees, with what an order needs."""

    def __init__(self, items):
        self.items = items
        self.n = len(items)
        self.refs = [label_refs(a) for a in items]
        self.mark, self.binder = {}, {}
        for i, rs in enumerate(self.refs):
            for _, _, m, n in rs:
                if m and n not in self.mark:
                    self.mark[n], self.binder[n] = m, i
        self.labs = [{n for _, _, _, n in rs if n in self.mark} for rs in self.refs]
        self.needs = [{n for n in self.labs[i] if self.binder[n] != i} if is_guard(a) else set() for i, a in enumerate(items)]

    def ok(self, order):
        bound = set()
        for i in order:
            if not self.needs[i] <= bound:
                return False
            bound |= self.labs[i]
        return True

    def count(self):
        """The orders that the guard rule takes, by subsets, or None past MAX_COUNT_ITEMS items."""
        if self.n > MAX_COUNT_ITEMS:
            return None
        if not any(self.needs):
            return math.factorial(self.n)
        ways = {0: 1}
        for _ in range(self.n):
            nxt = collections.Counter()
            for mask, w in ways.items():
                bound = set().union(*(self.labs[j] for j in range(self.n) if mask >> j & 1))
                for i in range(self.n):
                    if not mask >> i & 1 and self.needs[i] <= bound:
                        nxt[mask | 1 << i] += w
            ways = nxt
        return sum(ways.values())

    def all_orders(self):
        """Each order that the guard rule takes, by items sorted by text."""
        by = sorted(range(self.n), key=lambda i: key_of(self.items[i]))

        def go(mask, bound, prefix):
            if len(prefix) == self.n:
                yield tuple(prefix)
                return
            for i in by:
                if not mask >> i & 1 and self.needs[i] <= bound:
                    prefix.append(i)
                    yield from go(mask | 1 << i, bound | self.labs[i], prefix)
                    prefix.pop()
        yield from go(0, set(), [])

    def random_order(self, rng):
        """An order of the guard rule, uniform where a shuffle passes the rule within 300 tries."""
        by = sorted(range(self.n), key=lambda i: key_of(self.items[i]))
        idx = list(by)
        for _ in range(300):
            rng.shuffle(idx)
            if self.ok(idx):
                return tuple(idx)
        order, bound, left = [], set(), list(by)
        while left:
            i = rng.choice([j for j in left if self.needs[j] <= bound])
            left.remove(i)
            order.append(i)
            bound |= self.labs[i]
        return tuple(order)

    def reordered(self, order):
        """The items in order, as new trees, with each label that the site binds marked at its first occurrence."""
        items = json.loads(json.dumps(self.items))
        refs = [label_refs(a) for a in items]
        bound, first_at = set(), {}
        for i in order:
            for _, _, _, n in refs[i]:
                if n in self.mark and n not in bound:
                    bound.add(n)
                    first_at[n] = i
        for n, i in first_at.items():
            b = self.binder[n]
            if i == b:
                continue
            for x, k, m, name in refs[b]:
                if name == n and m:
                    x[k] = n
            for x, k, m, name in refs[i]:
                if name == n:
                    x[k] = self.mark[n] + n
                    break
        return [items[i] for i in order]


def sites_of(form):
    """[(container, lo, hi)] of a form, each outer site before the sites inside it."""
    out = []

    def body(c, lo, hi):
        if hi - lo < 1 or not all(isinstance(c[j], list) for j in range(lo, hi)):
            return
        if hi - lo > 1:
            out.append((c, lo, hi))
        for j in range(lo, hi):
            atom(c[j])

    def atom(a):
        if a[0] == 'OR':
            if len(a) > 2:
                out.append((a, 1, len(a)))
            for b in a[1:]:
                body(b, 0, len(b))
        elif a[0] in ('ALL', 'IF'):
            for b in a[1:]:
                if is_atoms(b):
                    body(b, 0, len(b))
        elif a[0] == 'NOT' and len(a) == 2 and isinstance(a[1], list):
            atom(a[1])
    if form[0] in ('RULE', 'DET'):
        body(form, 2, len(form))
    elif form[0] in ('INIT', 'RIGID_DET'):
        for child in form[3:]:
            if not isinstance(child, list):
                continue
            if child[0] == 'key':
                body(child[1], 0, len(child[1]))
                ports = child[2:]
            else:
                ports = [child]
            for p in ports:
                body(p, 2, len(p))
    return out


class Orders:
    """The orders of one form. An order is a tuple with one order per site."""

    def __init__(self, text):
        self.text = text
        self.form = parse(text)
        if show(self.form) != text:
            raise ValueError('the form does not read back as itself')
        raw = sites_of(self.form)
        # sites go by their sorted item keys, not by written position; perm[k] is the written index of site k
        keys = [sorted(key_of(x) for x in c[lo:hi]) for c, lo, hi in raw]
        self.perm = sorted(range(len(raw)), key=lambda s: (keys[s], s))
        self.sites = [raw[s] for s in self.perm]
        self.bodies = [Body(list(c[lo:hi])) for c, lo, hi in self.sites]
        self.counts = [b.count() for b in self.bodies]
        self.total = None if None in self.counts else math.prod(self.counts)
        self.written = tuple(tuple(range(b.n)) for b in self.bodies)

    def seed(self):
        return int.from_bytes(hashlib.sha256('\n'.join(sorted(key_of(x) for b in self.bodies for x in b.items) or [self.text]).encode()).digest()[:8], 'big')

    def every(self):
        return itertools.product(*(b.all_orders() for b in self.bodies))

    def sample(self, rng):
        return tuple(b.random_order(rng) for b in self.bodies)

    def neighbours(self, order):
        """The orders one swap of neighbours from order that pass the guard rule."""
        for s, o in enumerate(order):
            for j in range(len(o) - 1):
                x = list(o)
                x[j], x[j + 1] = x[j + 1], x[j]
                if self.bodies[s].ok(x):
                    yield order[:s] + (tuple(x),) + order[s + 1:]

    def render(self, order):
        """The form's text in the order. Inner sites go first, since an outer site's move keeps the items inside its own items."""
        form = parse(self.text)
        sites = sites_of(form)
        by_written = [None] * len(sites)
        for k, s in enumerate(self.perm):
            by_written[s] = order[k]
        for (c, lo, hi), o in reversed(list(zip(sites, by_written))):
            c[lo:hi] = Body(list(c[lo:hi])).reordered(o)
        return show(form)


def rng_of(orders):
    return random.Random(orders.seed())


def lse2(bits):
    """-log2 of the sum of 2^-b."""
    m = min(bits)
    return m - math.log2(sum(2 ** (m - b) for b in bits))
