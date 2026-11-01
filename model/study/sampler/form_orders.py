"""A form as sets of atoms: its valid orders, and the sum of a chance over them. No engine: a caller gives the walk as a function.

A form's text is a tree of bodies. Each of these is a set, so the walk may take its items in any order:
- the atoms of a RULE or a DET, of a key group, of an instance clause, of a RIGID_DET's parts and of a port,
- the branches of an OR, and the atoms of each branch,
- the guard atoms of an ALL, and the atoms of its conclusion.
These keep their places: a form's ports and key group, a port's head, and an ALL's guard before its conclusion. An atom of no known compound
(an IF) is one item, and its inside keeps its text.

An order is one permutation of each set. A label's mark (`*` or `^`) goes on its first occurrence in the order, as in the decoder's tokens. An
order is valid here where a NOT or a comparison comes after the labels it reads, a `=` of two labels comes after one of them (it makes the other), and an
ALL comes after the labels it shares with the rest of the form. No label's mark is read from the text, so no written order is read. The rest of validity
is the caller's walk: the decoder's checks, and a chance above 0 at each choice. The two labels of a `=` or a `!=` stand in name order in the form, since no
result reads their written order.

Two orders of a form with like atoms can give one token stream, which is one path of the proposal. A path counts once: `Form.path` is its key and
`Form.multiplicity` is how many orders give it.
"""
import collections
import math
import random
import re
import time

TOKEN = re.compile(r'\(|\)|[^\s()]+')
LABEL = re.compile(r'^([*^]?)([A-Z][A-Za-z0-9_]*)$')
CMP = {'=', '!=', '<', '<=', '>', '>='}
KEYWORDS = {'NOT', 'OR', 'ALL', 'IF', 'ALSO', 'END'}
SYMMETRIC = ('=', '!=')  # the comparisons whose operands have no order of their own
MARK_ITEMS = ('ONE', 'SET')  # marks of a clause, which stand after its body
RULE_REASONS = ("no mode of the atom's relation", 'the `NOT` or the `ALL` stands')  # the refusals of the decoder that a rule of the form explains
EXPLORE = 0.1  # the share of a guided draw's choice that goes uniformly over the items
DEAD_BITS = 30.0  # the bits that a guided draw adds to a choice at which a walk ended
VALUE_STATES = 1 << 15  # the states of a form that the guided draw's value reads; past them it reads each item's mean bits
BATCH = 16  # draws between updates of the guided draw's table


def parse(text):
    """The s-expression of text as nested lists of strings."""
    stack = [[]]
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]


def unparse(x):
    return x if isinstance(x, str) else '(' + ' '.join(unparse(y) for y in x) + ')'


def tokens(x):
    if isinstance(x, str):
        yield x
    else:
        for y in x:
            yield from tokens(y)


def strip_marks(x):
    """The tree x with no label marks, which depend on the order."""
    if isinstance(x, list):
        return [strip_marks(y) for y in x]
    m = LABEL.match(x)
    return m[2] if m and m[1] else x


def lse2(bits):
    """-log2 of the sum of 2^-b over bits; inf for no bits."""
    bits = [b for b in bits if b != math.inf]
    if not bits:
        return math.inf
    m = min(bits)
    return m - math.log2(sum(2 ** (m - b) for b in bits))


class Node:
    """An item of a set or a place of a form. A Leaf has `tree`. Another node has `items`: with `free` the items are a set, and wrap makes the node's
    tree from its items' trees."""

    def __init__(self, items=(), free=False, wrap=None, tree=None, place='', all_form=False, or_form=False):
        self.items, self.free, self.wrap, self.tree, self.place, self.all_form, self.or_form = list(items), free, wrap, tree, place, all_form, or_form
        self.needs = self.any_of = frozenset()
        self.id = None
        self.leaves = []
        self.written = 0  # the place of the item in its set in the text
        self.sees = frozenset()
        self.key = self.make_key()

    def make_key(self):
        """A key of the node that depends on no order of any set: the items of a set are in sorted order."""
        if self.leaf:
            t = strip_marks(self.tree)
            return unparse([t[0], *sorted(t[1:])] if t[0] in SYMMETRIC else t)
        keys = [x.key for x in self.items]
        if self.free:
            keys.sort()
        return ('OR ' if self.or_form else '') + ' '.join(keys)

    @property
    def leaf(self):
        return self.tree is not None


def in_canonical_order(items):
    """The items by their keys, each with the place it has in the text."""
    for i, x in enumerate(items):
        x.written = i
    return sorted(items, key=lambda x: x.key)


def body(atoms, place):
    return Node(in_canonical_order([item(a, place) for a in atoms]), True, list, place=place)


def item(a, place):
    if isinstance(a, list) and len(a) == 3 and a[0] in SYMMETRIC and all(LABEL.match(x) for x in a[1:]):  # no written order of the operands is read
        a = [a[0], *sorted(a[1:], key=lambda x: LABEL.match(x)[2])]
    if isinstance(a, list) and a and a[0] == 'OR':
        return Node(in_canonical_order([body(b, place + ' branch') for b in a[1:]]), True, lambda xs: ['OR', *xs], place=place, or_form=True)
    if isinstance(a, list) and len(a) == 3 and a[0] == 'ALL':
        return Node([body(a[1], place + ' all'), body(a[2], place + ' all')], False, lambda xs: ['ALL', *xs], place=place, all_form=True)
    return Node(tree=a, place=place)


def port(p):
    """A port: its name, its head, and its body's atoms."""
    head = p[:2]
    return Node([body(p[2:], 'port ' + p[0])], False, lambda xs: [*head, *xs[0]], place='port')


def group(g, rigid=False):
    """A key group or an instance clause: its body, then its ports, or in a RIGID_DET an instance clause and the parts."""
    name, rest = g[0], g[2:]
    if rigid:
        parts = [x for x in rest if x[0] != 'instance']
        kids = [group(x, True) for x in rest if x[0] == 'instance'] + ([body(parts, 'parts')] if parts else [])
        wrap = lambda xs: [name, *xs[:-1], *xs[-1]] if parts else [name, *xs]  # noqa: E731
    else:
        kids, wrap = [port(p) for p in rest], lambda xs: [name, *xs]
    return Node([body(g[1], name), *kids], False, wrap, place=name)


def root(tree):
    kind = tree[0]
    if kind in ('RULE', 'DET'):
        head = tree[:2]
        if not all(isinstance(a, list) for a in tree[2:]):  # a clause of one proposer
            return Node(tree=tree, place='top')
        atoms = [a for a in tree[2:] if not (a and isinstance(a[0], str) and a[0] in MARK_ITEMS)]
        marks = [a for a in tree[2:] if a and isinstance(a[0], str) and a[0] in MARK_ITEMS]
        return Node([body(atoms, 'top'), *[Node(tree=m, place='mark') for m in marks]], False, lambda xs: [*head, *xs[0], *xs[1:]], place='top')
    if kind == 'INIT':
        head = tree[:3]
        return Node([group(c) if c[0] == 'key' else port(c) for c in tree[3:]], False, lambda xs: [*head, *xs], place='form')
    if kind == 'RIGID_DET':
        head = tree[:2]
        return Node([group(c, True) for c in tree[2:]], False, lambda xs: [*head, *xs], place='form')
    raise ValueError('a form of no known shape: %s' % kind)


class Form:
    """The tree of a form's text, and the decisions that make an order: an order is a tuple of an item's place in its set, one for each choice in
    walk order."""

    def __init__(self, text):
        self.text0 = text
        forms = parse(text)
        if len(forms) != 1 or unparse(forms[0]) != text:
            raise ValueError('the form does not read back as itself')
        self.kind = forms[0][0]
        self.root = root(forms[0])
        self.nodes, self.leaves = [], []
        self.number(self.root)
        self.marks = {}  # a label -> its mark
        for leaf in self.leaves:
            for t in tokens(leaf.tree):
                m = LABEL.match(t)
                if m and m[1] and m[2] not in KEYWORDS and m[2] not in self.marks:
                    self.marks[m[2]] = m[1]
        for leaf in self.leaves:
            leaf.names = self.labels(leaf)
            if leaf.tree[0] == '=':
                leaf.any_of = frozenset(leaf.names) if len(leaf.names) == 2 else frozenset()  # `=` makes a label of a fresh operand, so it reads one of its two labels
            elif leaf.tree[0] == 'NOT' or leaf.tree[0] in CMP:
                leaf.needs = frozenset(leaf.names)
        self.set_all(self.root)
        self.see(self.root, frozenset())
        self.refused = collections.defaultdict(set)  # a leaf's id -> the label sets that the decoder refused it with
        self.written = self.written_order()

    def number(self, node):
        node.id = len(self.nodes)
        self.nodes.append(node)
        if node.leaf:
            node.leaf_id = len(self.leaves)
            self.leaves.append(node)
            node.leaves = [node]
        else:
            for x in node.items:
                self.number(x)
                node.leaves += x.leaves

    def labels(self, leaf):
        out = set()
        for t in tokens(leaf.tree):
            m = LABEL.match(t)
            if m and m[2] in self.marks:
                out.add(m[2])
        return out

    def set_all(self, node):
        """An ALL's items read the labels that it shares with the form from before it, since an occurrence inside an ALL is local to the ALL."""
        for x in node.items:
            if x.all_form:
                inside = {n for leaf in x.leaves for n in leaf.names}
                outside = {n for leaf in self.leaves if leaf not in x.leaves for n in leaf.names}
                x.needs = frozenset(inside & outside)
            self.set_all(x)

    def see(self, node, outer):
        """leaf.sees: the ids of the leaves that may stand as conjuncts before the leaf."""
        if node.leaf:
            node.sees = outer - {node.leaf_id}
        elif node.free and not node.or_form:
            for x in node.items:
                self.see(x, outer | {y.leaf_id for z in node.items if z is not x for y in z.leaves})
        elif node.free:
            for x in node.items:
                self.see(x, outer)
        else:
            for i, x in enumerate(node.items):
                self.see(x, outer | {y.leaf_id for z in node.items[:i] for y in z.leaves})

    def visible(self, leaf, bound):
        """The leaf's labels that the conjuncts before it name."""
        return frozenset(n for l in leaf.sees if l in bound for n in self.leaves[l].names if n in leaf.names)

    def canonical_key(self):
        """A key of the form that no order of its sets changes."""
        return self.root.key

    def sets(self):
        return [n for n in self.nodes if not n.leaf and n.free]

    # ---------------------------------------------------------------- the decisions

    def start(self):
        return self.settle(((self.root.id, 0),), frozenset(), [])

    def settle(self, stack, bound, emitted):
        """(stack, bound) at the next choice, or at the end with an empty stack. A frame is (node id, mask of the items taken)."""
        while stack:
            nid, mask = stack[-1]
            node = self.nodes[nid]
            if node.leaf:
                stack = stack[:-1]
                bound = bound | node.names | {node.leaf_id}
                if node.tree[0] not in MARK_ITEMS:
                    emitted.append(node)
            elif node.free:
                if mask == (1 << len(node.items)) - 1:
                    stack = stack[:-1]
                else:
                    return stack, bound
            else:
                stack = stack[:-1] + tuple((x.id, 0) for x in reversed(node.items))
        return stack, bound

    def choices(self, stack, bound):
        """The places in the top set of the items that may come next."""
        nid, mask = stack[-1]
        items = self.nodes[nid].items
        return [i for i, x in enumerate(items) if not mask >> i & 1 and x.needs <= bound and (not x.any_of or x.any_of & bound)
                and not (x.leaf and x.leaf_id in self.refused and self.visible(x, bound) in self.refused[x.leaf_id])]

    def choose(self, stack, bound, i, emitted):
        nid, mask = stack[-1]
        return self.settle(stack[:-1] + ((nid, mask | 1 << i), (self.nodes[nid].items[i].id, 0)), bound, emitted)

    def orders(self):
        """Yields every order by the rule above, the written one where it comes."""
        trail = []  # (stack, bound, item) of each choice of the prefix

        def go(stack, bound, prefix):
            if not stack:
                yield tuple(prefix)
                return
            for i in self.choices(stack, bound):
                if self.refused and (i not in self.choices(stack, bound) or any(x not in self.choices(st, bo) for st, bo, x in trail)):  # a rule that the orders so far taught, here or at a choice before this one
                    continue
                s, b = self.choose(stack, bound, i, [])
                prefix.append(i)
                trail.append((stack, bound, i))
                yield from go(s, b, prefix)
                trail.pop()
                prefix.pop()
        stack, bound = self.start()
        yield from go(stack, bound, [])

    def count(self, limit):
        """The count of the orders, or limit + 1 where they are more."""
        n = 0
        for _ in self.orders():
            n += 1
            if n > limit:
                break
        return n

    def count_estimate(self, rng, draws=400):
        """An estimate of the count of the orders, from random walks down the choices (Knuth's estimate of a tree's size)."""
        total = 0.0
        for _ in range(draws):
            stack, bound = self.start()
            w = 1.0
            while stack:
                opts = self.choices(stack, bound)
                if not opts:
                    w = 0.0
                    break
                w *= len(opts)
                stack, bound = self.choose(stack, bound, rng.choice(opts), [])
            total += w
        return total / draws

    def written_order(self):
        """The order of the text, or None where the text breaks the rule of an order."""
        out = []
        stack, bound = self.start()
        while stack:
            nid, mask = stack[-1]
            items = self.nodes[nid].items
            i = min((k for k in range(len(items)) if not mask >> k & 1), key=lambda k: items[k].written)
            if i not in self.choices(stack, bound):
                return None
            out.append(i)
            stack, bound = self.choose(stack, bound, i, [])
        return tuple(out)

    # ---------------------------------------------------------------- rules learned from the decoder

    def locate(self, order, steps):
        """The leaf that the decoder's path steps name in the order, or None. steps leaves out the form's index. A path goes on past the atom to a site, and those steps aren't read."""
        perm = self.perms(order)

        def at(node, steps):  # node is a body
            item = node.items[perm[node.id][steps[0]]]
            if item.leaf:
                return item
            if item.or_form:
                return at(item.items[perm[item.id][steps[1]]], steps[2:])
            if item.all_form:
                return at(item.items[steps[1]], steps[2:])
            return None
        try:
            if self.kind in ('RULE', 'DET'):
                return at(self.root.items[0], steps[1:])
            if self.kind != 'INIT':
                return None
            child = self.root.items[steps[0]]
            if child.place != 'key':  # a port: steps[1] is the index of its body, past its head columns
                return at(child.items[0], steps[2:])
            if steps[1] == 0:
                return at(child.items[0], steps[2:])
            return at(child.items[steps[1]].items[0], steps[3:])
        except (IndexError, KeyError):
            return None

    def refuse(self, order, steps):
        """Learns the rule of a refusal of the order at the path steps, where the path names a leaf."""
        leaf = self.locate(order, steps)
        if leaf is None:
            return
        emitted = []
        stack, bound = self.start_emitted(emitted)
        before = bound
        for i in order:
            if leaf in emitted:
                break
            before = bound
            stack, bound = self.choose(stack, bound, i, emitted)
        self.refused[leaf.leaf_id].add(self.visible(leaf, before))

    # ---------------------------------------------------------------- the text of an order

    def perms(self, order):
        """{set's node id: its items' places in the order}."""
        perm = collections.defaultdict(list)
        stack, bound = self.start()
        for i in order:
            perm[stack[-1][0]].append(i)
            stack, bound = self.choose(stack, bound, i, [])
        return perm

    def tree(self, order):
        """The form's tree in the order, each label's mark on its first occurrence."""
        perm, seen = self.perms(order), set()

        def build(node):
            if node.leaf:
                return mark(self.operands(node, seen))
            items = [node.items[i] for i in perm[node.id]] if node.free else node.items
            return node.wrap([build(x) for x in items])

        def mark(x):
            if isinstance(x, list):
                return [mark(y) for y in x]
            m = LABEL.match(x)
            if not m or m[2] not in self.marks:
                return x
            if m[2] in seen:
                return m[2]
            seen.add(m[2])
            return self.marks[m[2]] + m[2]
        return build(self.root)

    def operands(self, leaf, seen):
        """The leaf's tree: a `=` of two labels has a label that seen lacks as its first operand, since the first operand is the site that makes a label."""
        t = leaf.tree
        if leaf.any_of and LABEL.match(t[2])[2] not in seen and LABEL.match(t[1])[2] in seen:
            return [t[0], t[2], t[1]]
        return t

    def text(self, order):
        return unparse(self.tree(order))

    def path(self, order):
        """A key of the order's token stream: its text with each label by the place of its first occurrence."""
        num = {}
        out = []
        for t in TOKEN.findall(self.text(order)):
            m = LABEL.match(t)
            if m and m[2] in self.marks:
                t = m[1] + 'L%d' % num.setdefault(m[2], len(num))
            out.append(t)
        return ' '.join(out)

    def multiplicity(self, order):
        """How many orders give the order's path."""
        want = self.path(order)
        wanted = self.leaf_keys(order)

        def go(stack, bound, prefix, num, j):
            if not stack:
                return int(self.path(tuple(prefix)) == want)
            total = 0
            for i in self.choices(stack, bound):
                emitted = []
                s, b = self.choose(stack, bound, i, emitted)
                n2, k = dict(num), j
                fits = True
                for leaf in emitted:
                    if self.leaf_key(leaf, n2) != wanted[k]:
                        fits = False
                        break
                    k += 1
                if fits:
                    prefix.append(i)
                    total += go(s, b, prefix, n2, k)
                    prefix.pop()
            return total
        stack, bound = self.start()
        return go(stack, bound, [], {}, 0)

    def leaf_key(self, leaf, num):
        out = []
        for t in tokens(leaf.tree):
            m = LABEL.match(t)
            if m and m[2] in self.marks:
                out.append('L%d' % num.setdefault(m[2], len(num)))
            else:
                out.append(t)
        return ' '.join(out)

    def leaf_keys(self, order):
        return [self.leaf_key(leaf, num) for num in [{}] for leaf in self.emission(order)]

    def emission(self, order):
        """The leaves in the order. A leaf that a settle takes with no choice is in its place."""
        out = []
        stack, bound = self.start_emitted(out)
        for i in order:
            stack, bound = self.choose(stack, bound, i, out)
        return out

    def start_emitted(self, out):
        return self.settle(((self.root.id, 0),), frozenset(), out)


# ---------------------------------------------------------------- the sum over orders

class DrawTable:
    """The table of the guided draw: for a state and an item, the mean bits that the walks gave that choice, and the choices at which a walk ended."""

    def __init__(self, form, rng):
        self.form, self.rng = form, rng
        self.cost, self.dead = {}, collections.Counter()
        self.mean = collections.defaultdict(lambda: [0.0, 0])  # a leaf's id -> its mean bits over the states seen
        self.value = {}

    def learn(self, order, marks):
        """Adds what a walk gave: marks has the walk's running bits after each atom that it took. A choice with no atom has no bits."""
        form = self.form
        emitted = []
        stack, bound = form.start_emitted(emitted)
        took, last = len(emitted), 0.0
        for i in order:
            s0 = stack
            stack, bound = form.choose(stack, bound, i, emitted)
            if len(emitted) == took:
                continue
            if len(emitted) > len(marks):
                self.dead[s0, i] += 1
                return
            bits = marks[len(emitted) - 1] - last
            last, took = marks[len(emitted) - 1], len(emitted)
            c = self.cost.setdefault((s0, i), [0.0, 0])
            c[0] += bits
            c[1] += 1
            m = self.mean[emitted[-1].leaf_id]
            m[0] += bits
            m[1] += 1

    def bits(self, stack, i):
        """The table's bits for item i of the top set at stack."""
        form = self.form
        c = self.cost.get((stack, i))
        node = form.nodes[stack[-1][0]].items[i]
        if c is not None:
            b = c[0] / c[1]
        elif node.leaf:
            b = self.leaf_bits(node.leaf_id)
        else:
            b = 0.0
        return b + (DEAD_BITS if (stack, i) in self.dead else 0.0)

    def leaf_bits(self, leaf):
        m = self.mean.get(leaf)
        if m:
            return m[0] / m[1]
        seen = [v[0] / v[1] for v in self.mean.values()]
        return sum(seen) / len(seen) if seen else 8.0

    def rest(self, stack):
        """The mean bits of the atoms that are left at stack."""
        form, total = self.form, 0.0
        for nid, mask in stack:
            node = form.nodes[nid]
            if node.leaf:
                total += self.leaf_bits(node.leaf_id)
            elif node.free:
                for i, x in enumerate(node.items):
                    if not mask >> i & 1:
                        total += sum(self.leaf_bits(y.leaf_id) for y in x.leaves)
            else:
                total += sum(self.leaf_bits(y.leaf_id) for y in node.leaves)
        return total

    def to_go(self, stack, bound):
        """-log2 of the table's chance of what is left at stack, over its orders. Past VALUE_STATES it is the mean bits of what is left."""
        if not stack:
            return 0.0
        v = self.value.get(stack)
        if v is None:
            if len(self.value) >= VALUE_STATES:
                return self.rest(stack)
            self.value[stack] = v = lse2([self.bits(stack, i) + self.to_go(*self.form.choose(stack, bound, i, [])) for i in self.form.choices(stack, bound)])
        return v

    def draw(self):
        """(order, log2 of its chance under the guided draw), or (None, None) at a dead end."""
        form, rng = self.form, self.rng
        stack, bound = form.start()
        order, logr = [], 0.0
        while stack:
            opts = form.choices(stack, bound)
            if not opts:
                return None, None
            nexts = [form.choose(stack, bound, i, []) for i in opts]
            xs = [self.bits(stack, i) + self.to_go(*n) for i, n in zip(opts, nexts)]
            low = min(xs)
            ws = [2 ** (low - x) if x != math.inf else 0.0 for x in xs]
            total = sum(ws)
            ps = [(1 - EXPLORE) * w / total + EXPLORE / len(opts) for w in ws] if total else [1.0 / len(opts)] * len(opts)
            j = rng.choices(range(len(opts)), ps)[0]
            logr += math.log2(ps[j])
            order.append(opts[j])
            stack, bound = nexts[j]
        return tuple(order), logr


def sum_orders(form, walk, check=None, cap=256, budget=256, seconds=None, seed=0, limit=20000):
    """The sum of the walk's chance over the form's paths.

    walk(text) gives a dict with `bits` (None where the walk can't take that order), `why` for such an order, and `marks`, the running bits after each
    atom that the walk took. check(text) gives None where the decoder takes the text, else (reason, steps); a refusal teaches the form a rule
    (Form.refuse). The written text is walked first, whatever check says of it. A form with at most cap orders that pass check has each path walked,
    and the sum is exact. Another form has orders from a draw that learns from each walk which item comes cheapest from each state, up to budget walks
    that passed check. The sum of such a form is an importance sampling estimate from the later half of the draws: the mean of
    chance / (multiplicity * chance under the draw), floored at the sum of the paths walked. The written walk is not in the draw's table, its samples
    or its sum of walked paths, unless the draw takes that order. Returns a dict: `walks` has one (order, the walk's dict) per path, in walk order;
    `written`, the written text's dict; `bits`; `tight`, the sum with the written walk added; `exact`; `refused`, reason -> count; `rules`; and for a
    report `orders`, `orders_exact`, `walked_bits`, `draws`, `se_bits`, `ess`, `stopped`.
    """
    t0, rng = time.monotonic(), random.Random(seed)
    memo, paths, walks = {}, {}, []
    written = walk(form.text0)
    if form.written is not None and form.text(form.written) == form.text0:
        memo[form.path(form.written)] = written

    def visit(order):
        key = form.path(order)
        if key not in paths:
            res = paths[key] = memo[key] if key in memo else walk(form.text(order))
            walks.append((order, res))
        return paths[key]

    def late():
        return seconds is not None and time.monotonic() - t0 > seconds

    refused, failed, passed = collections.Counter(), set(), {}

    def rules():
        return sum(len(v) for v in form.refused.values())

    def taken(order, key):
        """Whether the decoder takes the order; a refusal is counted and teaches its rule."""
        if key in failed:
            return False
        if key in passed:
            return True
        got = None if check is None else check(form.text(order))
        if got is None:
            passed[key] = order
            return True
        failed.add(key)
        refused[got[0][:40]] += 1
        if got[0].startswith(RULE_REASONS):
            form.refuse(order, got[1])
        return False

    n, over = 0, False
    for order in form.orders():
        n += 1
        if n > limit:
            over = True
            break
        taken(order, form.path(order))
        if len(passed) > cap:
            over = True
            break
    out = dict(exact=True, orders=len(passed), orders_exact=not over, stopped=False, draws=0, se_bits=0.0, ess=None)

    def finish(bits, walked, **more):
        wkey = None if form.written is None else form.path(form.written)
        extra = [written['bits']] if written['bits'] is not None and (wkey is None or wkey not in paths) else []
        tight = lse2([r['bits'] for _, r in walks if r['bits'] is not None] + extra)
        out.update(walks=walks, written=written, bits=bits, walked_bits=walked, tight=tight, refused=dict(refused), rules=rules(), **more)
        return out

    if not over:
        for order in list(passed.values()):
            if late():
                out.update(exact=False, stopped=True)
                break
            visit(order)
        good = lse2([r['bits'] for _, r in walks if r['bits'] is not None])
        return finish(good, good)
    out.update(exact=False, orders=form.count_estimate(rng), orders_exact=False)
    guide = DrawTable(form, rng)
    samples, idle, mult = [], 0, {}
    while len(walks) < budget and out['draws'] < 40 * budget and idle < 8 and not late():
        guide.value = {}
        before, learned = len(walks), rules()
        for _ in range(BATCH):
            out['draws'] += 1
            order, logr = guide.draw()
            if order is None:
                samples.append(math.inf)
                continue
            key = form.path(order)
            if not taken(order, key):
                samples.append(math.inf)
                continue
            res = visit(order)
            if res.get('marks') is not None:
                guide.learn(order, res['marks'])
            if res['bits'] is None:
                samples.append(math.inf)
                continue
            m = mult.get(key)
            if m is None:
                m = mult[key] = form.multiplicity(order)
            samples.append(res['bits'] + logr + math.log2(m))  # -log2 of the sample's weight
            if len(walks) >= budget:
                break
        idle = idle + 1 if len(walks) == before and rules() == learned else 0
    walked = lse2([r['bits'] for _, r in walks if r['bits'] is not None])
    later = samples[len(samples) // 2:]
    bits = walked
    if later:
        m = min(later)
        if m != math.inf:
            ws = [2 ** (m - x) if x != math.inf else 0.0 for x in later]
            mean = sum(ws) / len(ws)
            est = m - math.log2(mean)
            var = sum((w - mean) ** 2 for w in ws) / max(len(ws) - 1, 1) / len(ws)
            out.update(se_bits=math.sqrt(var) / mean / math.log(2), ess=sum(ws) ** 2 / sum(w * w for w in ws))
            bits = min(est, walked)
    return finish(bits, walked, stopped=late())
