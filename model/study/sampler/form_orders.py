"""A form as sets of atoms: its valid orders, and the sum of a chance over them. No engine: a caller gives the walk as a function.

A form's text is a tree of bodies. Each of these is a set, so the walk may take its items in any order:
- the atoms of a RULE or a DET, of a key group, of an instance clause, of a RIGID_DET's parts and of a port,
- the branches of an OR, and the atoms of each branch,
- the guard atoms of an ALL, and the atoms of its conclusion.
These keep their places: a form's ports and key group, a port's head, and an ALL's guard before its conclusion. An atom of no known compound
(an IF) is one item, and its inside keeps its text.

An order is one permutation of each set. A label's mark (`*` or `^`) goes on its first occurrence in the order, as in the decoder's tokens. An
order is valid here where a NOT or a comparison comes after the labels it reads and doesn't mark, and an ALL comes after the labels it shares with
the rest of the form. The rest of validity is the caller's walk: the decoder's checks, and a chance above 0 at each choice.

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

    def __init__(self, items=(), free=False, wrap=None, tree=None, place='', all_form=False):
        self.items, self.free, self.wrap, self.tree, self.place, self.all_form = list(items), free, wrap, tree, place, all_form
        self.needs = frozenset()
        self.id = None
        self.leaves = []

    @property
    def leaf(self):
        return self.tree is not None


def body(atoms, place):
    return Node([item(a, place) for a in atoms], True, list, place=place)


def item(a, place):
    if isinstance(a, list) and a and a[0] == 'OR':
        return Node([body(b, place + ' branch') for b in a[1:]], True, lambda xs: ['OR', *xs], place=place)
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
        return Node([body(tree[2:], 'top')], False, lambda xs: [*head, *xs[0]], place='top')
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
            if leaf.tree[0] == 'NOT' or leaf.tree[0] in CMP:
                own = {LABEL.match(t)[2] for t in tokens(leaf.tree) if t[:1] in ('*', '^') and LABEL.match(t)}
                leaf.needs = frozenset(leaf.names - own)
        self.set_all(self.root)
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
                bound = bound | node.names
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
        return [i for i, x in enumerate(items) if not mask >> i & 1 and x.needs <= bound]

    def choose(self, stack, bound, i, emitted):
        nid, mask = stack[-1]
        return self.settle(stack[:-1] + ((nid, mask | 1 << i), (self.nodes[nid].items[i].id, 0)), bound, emitted)

    def orders(self):
        """Yields every order by the rule above, the written one where it comes."""
        def go(stack, bound, prefix):
            if not stack:
                yield tuple(prefix)
                return
            for i in self.choices(stack, bound):
                s, b = self.choose(stack, bound, i, [])
                prefix.append(i)
                yield from go(s, b, prefix)
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
            i = next(k for k in range(len(self.nodes[nid].items)) if not mask >> k & 1)
            if i not in self.choices(stack, bound):
                return None
            out.append(i)
            stack, bound = self.choose(stack, bound, i, [])
        return tuple(out)

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
                return mark(node.tree)
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


def sum_orders(form, walk, cap=256, budget=256, seconds=None, seed=0):
    """The sum of the walk's chance over the form's paths.

    walk(text) gives a dict with `bits` (None where the walk can't take that order), `why` for such an order, and `marks`, the running bits after each
    atom that the walk took. A form with at most cap orders has each path walked, and the sum is exact. Another form has the written order walked,
    then orders from a draw that learns from each walk which item comes cheapest from each state, up to budget walks. The sum of such a form is an
    importance sampling estimate from the later half of the draws: the mean of chance / (multiplicity * chance under the draw), floored at the sum
    of the paths walked. Returns a dict: `walks` has one (order, the walk's dict) per path, in walk order; `written`, the written order's dict or
    None; `bits`; `exact`; and for a report `orders`, `orders_exact`, `walked_bits`, `draws`, `se_bits`, `ess`, `stopped`.
    """
    t0, rng = time.monotonic(), random.Random(seed)
    paths, walks = {}, []

    def visit(order):
        key = form.path(order)
        if key not in paths:
            res = paths[key] = walk(form.text(order))
            walks.append((order, res))
        return paths[key]

    def late():
        return seconds is not None and time.monotonic() - t0 > seconds

    written = None if form.written is None else visit(form.written)
    n = form.count(cap)
    out = dict(exact=True, orders=n, orders_exact=n <= cap, stopped=False, draws=0, se_bits=0.0, ess=None)
    if n <= cap:
        for order in form.orders():
            if late():
                out.update(exact=False, stopped=True)
                break
            visit(order)
        good = [r['bits'] for _, r in walks if r['bits'] is not None]
        out.update(walks=walks, written=written, bits=lse2(good), walked_bits=lse2(good))
        return out
    out.update(exact=False, orders=form.count_estimate(rng))
    guide = DrawTable(form, rng)
    if written is not None and written.get('marks') is not None:
        guide.learn(form.written, written['marks'])
    samples, idle, mult = [], 0, {}
    while len(walks) < budget and out['draws'] < 8 * budget and idle < 8 and not late():
        guide.value = {}
        before = len(walks)
        for _ in range(BATCH):
            out['draws'] += 1
            order, logr = guide.draw()
            if order is None:
                samples.append(math.inf)
                continue
            res = visit(order)
            if res.get('marks') is not None:
                guide.learn(order, res['marks'])
            if res['bits'] is None:
                samples.append(math.inf)
                continue
            key = form.path(order)
            m = mult.get(key)
            if m is None:
                m = mult[key] = form.multiplicity(order)
            samples.append(res['bits'] + logr + math.log2(m))  # -log2 of the sample's weight
            if len(walks) >= budget:
                break
        idle = idle + 1 if len(walks) == before else 0
    good = [r['bits'] for _, r in walks if r['bits'] is not None]
    walked = lse2(good)
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
    out.update(walks=walks, written=written, bits=bits, walked_bits=walked, stopped=late())
    return out
