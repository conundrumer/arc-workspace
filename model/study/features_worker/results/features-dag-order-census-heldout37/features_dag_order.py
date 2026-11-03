"""The atom DAG of an arclog form and the form DAG of a program. No engine import.

A form's body has no order of its own. An atom that binds a label comes before each atom that reads it, and that partial order is all that this module gives. An atom has an id made from its body and its text with no marks, so the id does not depend on written order.

The atom DAG
- A node is a leaf atom: a relation atom, a NOT or a comparison, in any body of the form. A body is the top of a RULE or DET, a key group, an INIT port, an OR branch, or an ALL's guard or conclusion. An OR and an ALL are items of their body, not nodes: `Body.items` holds them, and an order keeps each one whole.
- A binder of a label in a body:
    - In mode `binder` (the default): the atom that has the label's mark, `*X` or `^X`.
    - Where the body has no such atom, or in mode `join`: each relation atom that names the label, and each OR that binds it in its branches. A later OR branch is the usual case: it names `X`, and the mark is in the first branch. `=` binds the label only where no such atom exists.
- Each binder is a parent of each atom that reads the label. Binders of one label have no edge between them. A label bound by several atoms is the case of an OR whose branches each bind it: an atom after the OR has all of those binders as parents. It is also the case of several unmarked relation atoms in a later branch: a NOT or a comparison that reads the label comes after all of them. That is stricter than safety, which asks for one.
- A NOT and a comparison other than `=` bind nothing. Each label that they read has its binders as parents. A mark inside a NOT or an ALL is local to it.
- `=` with `*X` binds X and reads its other side.
- An atom that shares no label has no parent and no child. Its depth is 0, and it can stand anywhere in an order.
- An atom of an INIT port that reads a key label has the key group's binder as a parent. Key group and ports keep the component's order, so a body order never crosses them.
- OR branches have no edge between them. A rendered text keeps the written branch order, since the marks of the first branch depend on it.
- `(ONE)` and `(SET)` are marks of a clause, not atoms. They stay after the atoms.

Mode `join` ignores which relation atom has the mark, so all relation atoms that share a label are peers. A NOT or a comparison still comes after them. `render` then moves the marks to the first occurrence.

A prefix at a pick is a downset, an ancestor-closed set of atoms. `FormDag.frontier` gives the atoms of a set with no child in the set.
"""
import hashlib
import heapq
import random
import re
from typing import Any

CMP = ('=', '!=', '<', '<=', '>', '>=')
KEYWORDS = frozenset({'NOT', 'OR', 'ALL', 'IF', 'ALSO', 'END'})
LABEL = re.compile(r'^([*^]?)([A-Z][A-Za-z0-9_]*)$')
TOKEN = re.compile(r'\(|\)|[^\s()]+')
NAME = re.compile(r'&[A-Za-z_0-9]+')
CLAUSE_MARKS = (['ONE'], ['SET'])
EXTENSION_CAP = 200_000  # the downsets of one body that an exact count of its orders may hold

type Tree = list[Any]
type Order = dict[str, list[str]]  # a body's path -> its items' ids


def parse(text: str) -> Tree:
    """The s-expression as nested lists."""
    stack: list[Tree] = [[]]
    for token in TOKEN.findall(text):
        if token == '(':
            stack.append([])
        elif token == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(token)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError('not one s-expression: %s' % text[:80])
    return stack[0][0]


def unparse(tree: Any) -> str:
    return tree if isinstance(tree, str) else '(' + ' '.join(unparse(x) for x in tree) + ')'


def label_sites(tree: Tree):
    """(list, index, mark, name) of each label token of a tree, in text order. A list's head is never a label."""
    for i, x in enumerate(tree):
        if isinstance(x, list):
            yield from label_sites(x)
        elif i:
            m = LABEL.match(x)
            if m and m[2] not in KEYWORDS:
                yield tree, i, m[1], m[2]


def strip_marks(tree: Any) -> Any:
    if isinstance(tree, str):
        return tree
    return [tree[0] if isinstance(tree[0], str) else strip_marks(tree[0]), *(strip_marks(x) if isinstance(x, list) else LABEL.sub(r'\2', x) for x in tree[1:])] if tree else []


def short(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:n]


class Atom:
    """An item of a body. `kind` is rel, not, cmp, or or all. An or and an all have `bodies`; the others are leaf atoms, the nodes of the DAG."""

    def __init__(self, tree: Tree):
        self.tree, self.bodies = tree, []
        head = tree[0]
        self.kind = 'not' if head == 'NOT' else 'cmp' if head in CMP else 'or' if head == 'OR' else 'all' if head == 'ALL' else 'rel'
        if self.kind == 'or':
            self.bodies = [Body('branch', b, 0, len(b)) for b in tree[1:]]
        elif self.kind == 'all':
            self.bodies = [Body('guard', tree[1], 0, len(tree[1])), Body('conclusion', tree[2], 0, len(tree[2]))]
        self.marks: set[str] = set()  # the labels whose mark this item gives to the rest of the form
        self.names: set[str] = set()  # the labels it binds or reads from outside it
        sites = list(label_sites(tree))
        if self.kind in ('rel', 'cmp'):
            self.marks = {n for _, _, m, n in sites if m}
            self.names = {n for _, _, _, n in sites}
            if self.kind == 'cmp' and head != '=':
                self.marks = set()
        elif self.kind == 'or':
            self.marks = {n for b in self.bodies for a in b.items for n in a.marks}
            self.names = {n for b in self.bodies for a in b.items for n in a.names}
        else:  # a NOT and an ALL keep their marks local
            own = {n for _, _, m, n in sites if m}
            self.names = {n for _, _, _, n in sites} - own
        self.key = self.make_key()
        self.id = ''

    def make_key(self) -> str:
        if self.kind == 'or':
            return '(OR %s)' % ' '.join(sorted(b.key for b in self.bodies))
        if self.kind == 'all':
            return '(ALL %s %s)' % (self.bodies[0].key, self.bodies[1].key)
        return unparse(strip_marks(self.tree))

    def leaves(self):
        if self.bodies:
            for b in self.bodies:
                for a in b.items:
                    yield from a.leaves()
        else:
            yield self


class Body:
    """Items that have no written order. `holder[low:high]` is where they sit in the form's tree."""

    def __init__(self, role: str, holder: Tree, low: int, high: int):
        while high > low and holder[high - 1] in CLAUSE_MARKS:  # a mark of a clause stands after its atoms
            high -= 1
        self.role, self.holder, self.low, self.high = role, holder, low, high
        self.items = [Atom(x) for x in holder[low:high]]
        self.key = '(%s)' % ' '.join(sorted(a.key for a in self.items))
        self.path = role

    def identify(self, path: str):
        """Gives the body and its items ids from their content."""
        self.path, seen = path, {}
        for a in sorted(self.items, key=lambda x: (x.key, unparse(x.tree))):
            n = seen[a.key] = seen.get(a.key, 0) + 1
            a.id = '%s|%s%s' % (path, a.key, '#%d' % n if n > 1 else '')
            for b in a.bodies:
                b.identify('%s/%s%s/%s%s' % (path, a.kind, short(a.key), b.role, short(b.key)))

    def nested(self):
        yield self
        for a in self.items:
            for b in a.bodies:
                yield from b.nested()


def is_head(x: Any) -> bool:
    return isinstance(x, list) and (not x or isinstance(x[0], list))


def form_bodies(tree: Tree) -> list[Body]:
    """The bodies of a form, outside any OR, in the order of its text."""
    kind, out = tree[0], []

    def port(p):
        low = 2 if is_head(p[1]) else 1
        out.append(Body('port:' + p[0], p, low, len(p)))

    def group(c):
        if c[0] in ('key', 'instance', 'for'):
            out.append(Body(c[0], c[1], 0, len(c[1])))
            if c[0] == 'instance':
                out.append(Body('parts', c, 2, len(c)))
            else:
                for p in c[2:]:
                    group(p)
        elif len(c) > 1:
            port(c)
        else:
            out.append(Body('port:' + c[0], c, 1, 1))

    if kind in ('RULE', 'DET'):
        if len(tree) > 2 and not isinstance(tree[2], str):
            out.append(Body('top', tree, 2, len(tree)))
    elif kind == 'OUT':
        pass
    else:
        for c in tree[3 if kind == 'INIT' else 2:]:
            if isinstance(c, list):
                group(c)
    return out


class FormDag:
    """The atom DAG of a form's text. `mode` is binder or join (see the module's text)."""

    def __init__(self, text: str, mode: str = 'binder'):
        self.text, self.mode = text, mode
        tree = parse(text)
        self.kind, self.name = tree[0], tree[1] if len(tree) > 1 and isinstance(tree[1], str) else None
        self.proposer = tree[2] if self.kind in ('RULE', 'DET') and len(tree) > 2 and isinstance(tree[2], str) else None
        self.bodies = self.parsed(tree)
        self.all_bodies = [x for b in self.bodies for x in b.nested()]
        self.atoms = {a.id: a for b in self.bodies for i in b.items for a in i.leaves()}
        self.parent_ids: dict[str, set[str]] = {i: set() for i in self.atoms}
        visible: dict[str, set[str]] = {}
        for b in self.bodies:
            visible = self.visit(b, visible)
        self.child_ids: dict[str, set[str]] = {i: set() for i in self.atoms}
        for c, ps in self.parent_ids.items():
            for p in ps:
                self.child_ids[p].add(c)
        self.depths = self.layer(self.parent_ids, self.child_ids)
        self.item_preds = {b.path: self.item_edges(b) for b in self.all_bodies}

    @staticmethod
    def parsed(tree: Tree) -> list[Body]:
        bodies, roles = form_bodies(tree), {}
        for b in bodies:
            roles[b.role] = roles.get(b.role, 0) + 1
        for b in bodies:
            b.identify(b.role if roles[b.role] == 1 else '%s:%s' % (b.role, short(b.key)))
        return bodies

    # ---------------------------------------------------------------- binders and edges

    def binders(self, body: Body, label: str) -> set[Atom]:
        """The leaf atoms that bind the label in the body, where nothing outside it does."""
        if self.mode == 'binder':
            held = [a for a in body.items if label in a.marks]
            if held:
                return set().union(*[self.binds_item(a, label) for a in held])
        got: set[Atom] = set()
        for a in body.items:
            if a.kind == 'rel' and label in a.names:
                got.add(a)
            elif a.kind == 'or' and label in a.names:
                got |= self.binds_item(a, label)
        return got or {a for a in body.items if a.kind == 'cmp' and a.tree[0] == '=' and label in a.names}

    def binds_item(self, item: Atom, label: str) -> set[Atom]:
        if item.kind != 'or':
            return {item}
        each = [self.binders(b, label) for b in item.bodies]
        return set() if self.mode == 'join' and not all(each) else set().union(*each)

    def visit(self, body: Body, visible: dict[str, set[str]]) -> dict[str, set[str]]:
        """Adds the parents of the body's atoms. visible holds the labels bound outside the body, with their binders' ids. The result adds those that the body binds."""
        local = dict(visible)
        for label in {n for a in body.items for n in a.names} - visible.keys():
            got = self.binders(body, label)
            if got:
                local[label] = {a.id for a in got}
        for a in body.items:
            if not a.bodies:
                for label in a.names:
                    bound = local.get(label, set())
                    if a.id not in bound:
                        self.parent_ids[a.id] |= bound
                continue
            inside = {x.id for x in a.leaves()}
            outside = {k: v for k, v in local.items() if not v & inside}
            if a.kind == 'or':
                for b in a.bodies:
                    self.visit(b, outside)
            else:
                self.visit(a.bodies[1], self.visit(a.bodies[0], outside))
        return local

    def item_edges(self, body: Body) -> dict[str, set[str]]:
        """Item id -> the ids of the items of the body that must come before it."""
        under = {x.id: a.id for a in body.items for x in a.leaves()}
        preds: dict[str, set[str]] = {a.id: set() for a in body.items}
        for c, item in under.items():
            preds[item] |= {under[p] for p in self.parent_ids[c] if p in under and under[p] != item}
        return preds

    @staticmethod
    def layer(parents: dict[str, set[str]], children: dict[str, set[str]]) -> dict[str, int]:
        """The length of the longest path from a root to each node. Raises ValueError on a cycle."""
        left = {i: len(ps) for i, ps in parents.items()}
        todo = [i for i, n in left.items() if not n]
        depth = dict.fromkeys(todo, 0)
        while todo:
            i = todo.pop()
            for c in children[i]:
                depth[c] = max(depth.get(c, 0), depth[i] + 1)
                left[c] -= 1
                if not left[c]:
                    todo.append(c)
        if len(depth) != len(parents) or any(left.values()):
            raise ValueError('a cycle in the DAG')
        return depth

    # ---------------------------------------------------------------- an atom and a prefix

    def depth(self, atom_id: str) -> int:
        return self.depths[atom_id]

    def parents(self, atom_id: str) -> list[str]:
        return sorted(self.parent_ids[atom_id])

    def children(self, atom_id: str) -> list[str]:
        return sorted(self.child_ids[atom_id])

    def is_downset(self, ids) -> bool:
        ids = set(ids)
        return all(self.parent_ids[i] <= ids for i in ids)

    def frontier(self, ids) -> list[str]:
        """The atoms of the set with no child in the set."""
        ids = set(ids)
        return sorted(i for i in ids if not self.child_ids[i] & ids)

    # ---------------------------------------------------------------- orders

    def written_order(self) -> Order:
        return {b.path: [a.id for a in b.items] for b in self.all_bodies}

    def canonical_order(self) -> Order:
        """The topological order that takes the smallest id among the items that are ready. It depends on the DAG and the content alone."""
        out = {}
        for b in self.all_bodies:
            preds = self.item_preds[b.path]
            left = {i: len(ps) for i, ps in preds.items()}
            kids: dict[str, list[str]] = {i: [] for i in preds}
            for i, ps in preds.items():
                for p in ps:
                    kids[p].append(i)
            ready = [i for i, n in left.items() if not n]
            heapq.heapify(ready)
            order = []
            while ready:
                i = heapq.heappop(ready)
                order.append(i)
                for c in kids[i]:
                    left[c] -= 1
                    if not left[c]:
                        heapq.heappush(ready, c)
            out[b.path] = order
        return out

    def extension_table(self, body: Body) -> tuple[list[str], list[int], dict[int, int]] | None:
        """(item ids, predecessor masks, downset -> count of orders that finish it), or None past EXTENSION_CAP."""
        preds = self.item_preds[body.path]
        ids = sorted(preds)
        at = {i: k for k, i in enumerate(ids)}
        masks = [sum(1 << at[p] for p in preds[i]) for i in ids]
        full = (1 << len(ids)) - 1
        table = {full: 1}

        def count(mask: int) -> int:
            if mask not in table:
                if len(table) >= EXTENSION_CAP:
                    raise OverflowError
                table[mask] = sum(count(mask | 1 << k) for k, need in enumerate(masks) if not mask >> k & 1 and not need & ~mask)
            return table[mask]

        try:
            count(0)
        except OverflowError:
            return None
        return ids, masks, table

    def count_orders(self) -> int | None:
        """The count of topological orders of the form: the product over its bodies. None where a body passes the cap."""
        total = 1
        for b in self.all_bodies:
            got = self.extension_table(b)
            if got is None:
                return None
            total *= got[2][0]
        return total

    def random_order(self, seed: int) -> Order:
        """A topological order by the seed. Each body's order is uniform among the body's orders, or a uniform pick among the ready items at each step past the cap."""
        out = {}
        for b in self.all_bodies:
            rng = random.Random('%d|%s' % (seed, b.path))
            got = self.extension_table(b)
            if got is None:
                out[b.path] = self.ready_walk(self.item_preds[b.path], rng)
                continue
            ids, masks, table = got
            mask, order = 0, []
            while len(order) < len(ids):
                roll = rng.randrange(table[mask])
                for k, need in enumerate(masks):
                    if mask >> k & 1 or need & ~mask:
                        continue
                    roll -= table[mask | 1 << k]
                    if roll < 0:
                        mask |= 1 << k
                        order.append(ids[k])
                        break
            out[b.path] = order
        return out

    @staticmethod
    def ready_walk(preds: dict[str, set[str]], rng: random.Random) -> list[str]:
        done: set[str] = set()
        order = []
        while len(order) < len(preds):
            ready = sorted(i for i, ps in preds.items() if i not in done and ps <= done)
            pick = ready[rng.randrange(len(ready))]
            done.add(pick)
            order.append(pick)
        return order

    def is_topological(self, order: Order) -> bool:
        for path, ids in order.items():
            at = {i: k for k, i in enumerate(ids)}
            if any(at[p] > at[i] for i, ps in self.item_preds[path].items() for p in ps):
                return False
        return True

    def leaves(self, order: Order) -> list[str]:
        """The leaf atoms' ids in the order, as a walk meets them."""
        items = {a.id: a for b in self.all_bodies for a in b.items}

        def go(body):
            for i in order[body.path]:
                a = items[i]
                if a.bodies:
                    for b in a.bodies:
                        yield from go(b)
                else:
                    yield i
        return [i for b in self.bodies for i in go(b)]

    def render(self, order: Order) -> str:
        """The form's text in the order. Key group, ports and OR branches stay as written. In mode join, each label's mark goes to its first occurrence."""
        tree = parse(self.text)
        bodies = [x for b in self.parsed(tree) for x in b.nested()]
        for b in bodies:
            items = {a.id: a for a in b.items}
            b.items = [items[i] for i in order[b.path]]
            b.holder[b.low:b.high] = [a.tree for a in b.items]
        if self.mode == 'join':
            self.remark(self.parsed_top(tree, bodies))
        return unparse(tree)

    @staticmethod
    def parsed_top(tree: Tree, bodies: list[Body]) -> list[Atom]:
        """The leaf atoms of the reordered bodies in walk order."""
        inner = {id(b) for x in bodies for a in x.items for b in a.bodies}

        def go(body):
            for a in body.items:
                if a.bodies:
                    for b in a.bodies:
                        yield from go(b)
                else:
                    yield a
        return [a for b in bodies if id(b) not in inner for a in go(b)]

    @staticmethod
    def remark(leaves: list[Atom]):
        sites = [(a, s) for a in leaves for s in label_sites(a.tree)]
        mark = {s[3]: s[2] for _, s in sites if s[2]}
        placed: set[str] = set()
        local = {s[3] for a, s in sites if a.kind == 'not' and s[2]}
        for a, (holder, i, _, name) in sites:
            if name not in mark or name in local:
                continue
            first = name not in placed and a.kind != 'not' and (a.kind != 'cmp' or a.tree[0] == '=')
            holder[i] = (mark[name] if first else '') + name
            placed |= {name} if first else set()

    def summary(self, seeds=(0, 1, 2)) -> dict[str, Any]:
        """All the outputs of the DAG, keyed by id, which a test compares across written orders."""
        return dict(kind=self.kind, name=self.name, atoms={i: (self.depths[i], self.parents(i), self.children(i)) for i in sorted(self.atoms)},
                    canonical=self.canonical_order(), canonical_text=self.render(self.canonical_order()), count=self.count_orders(),
                    random={s: self.random_order(s) for s in seeds}, frontier=self.frontier(self.atoms))


class ProgramDag:
    """The DAG of a program's forms: a form that names `&rN` or `&rN.x` reads the form with head `&rN`. A form's key is its head, and `OUT` for the OUT form."""

    def __init__(self, lines: list[str]):
        self.lines = {}
        heads = {}
        for x in lines:
            tree = parse(x)
            key = 'OUT' if tree[0] == 'OUT' else tree[1]
            self.lines[key] = x
            heads[key] = tree[0]
        self.kinds = heads
        self.parent_ids: dict[str, set[str]] = {}
        for key, x in self.lines.items():
            self.parent_ids[key] = {n for n in NAME.findall(x) if n != key and n in self.lines}
        self.child_ids: dict[str, set[str]] = {k: set() for k in self.lines}
        for k, ps in self.parent_ids.items():
            for p in ps:
                self.child_ids[p].add(k)
        self.depths = FormDag.layer(self.parent_ids, self.child_ids)
        self.content = self.content_keys()

    def content_keys(self) -> dict[str, str]:
        """A hash of each form's text with each form name replaced by the hash of that form, so a tie does not read the numbers in `&rN`."""
        keys: dict[str, str] = {}
        for k in sorted(self.lines, key=lambda x: (self.depths[x], x)):
            keys[k] = short(NAME.sub(lambda m: 'SELF' if m[0] == k else keys.get(m[0], m[0]), self.lines[k]), 16)
        return keys

    def depth(self, key: str) -> int:
        return self.depths[key]

    def closure(self, key: str, step: dict[str, set[str]]) -> set[str]:
        got: set[str] = set()
        todo = [key]
        while todo:
            for k in step[todo.pop()]:
                if k not in got:
                    got.add(k)
                    todo.append(k)
        return got

    def ancestors(self, key: str) -> set[str]:
        return self.closure(key, self.parent_ids)

    def descendants(self, key: str) -> set[str]:
        return self.closure(key, self.child_ids)

    def non_descendants(self, key: str) -> set[str]:
        """The forms that this form could read: all but itself, its descendants and OUT."""
        return set(self.lines) - self.descendants(key) - {key, 'OUT'}

    def tie(self, key: str) -> tuple[str, str]:
        return self.content[key], key

    def canonical_order(self, keys=None) -> list[str]:
        """The topological order of the forms that takes the smallest content key among those that are ready."""
        keys = set(self.lines if keys is None else keys)
        left = {k: len(self.parent_ids[k] & keys) for k in keys}
        ready = [self.tie(k) for k, n in left.items() if not n]
        heapq.heapify(ready)
        order = []
        while ready:
            k = heapq.heappop(ready)[1]
            order.append(k)
            for c in self.child_ids[k] & keys:
                left[c] -= 1
                if not left[c]:
                    heapq.heappush(ready, self.tie(c))
        return order

    def random_order(self, seed: int, keys=None) -> list[str]:
        """A topological order by the seed: a uniform pick among the ready forms at each step."""
        keys = set(self.lines if keys is None else keys)
        rng = random.Random('%d|%s' % (seed, short(''.join(sorted(self.content[k] for k in keys)), 16)))
        done: set[str] = set()
        order = []
        while len(order) < len(keys):
            ready = sorted((k for k in keys if k not in done and self.parent_ids[k] & keys <= done), key=self.tie)
            pick = ready[rng.randrange(len(ready))]
            done.add(pick)
            order.append(pick)
        return order

    def texts(self, keys) -> list[str]:
        return [self.lines[k] for k in keys]

    def summary(self, seeds=(0, 1, 2)) -> dict[str, Any]:
        """All the outputs of the DAG, keyed by form, which a test compares across written orders."""
        return dict(forms={k: (self.kinds[k], self.depths[k], sorted(self.ancestors(k)), sorted(self.descendants(k)), sorted(self.non_descendants(k)),
                               self.canonical_order(self.non_descendants(k))) for k in sorted(self.lines)},
                    canonical=self.canonical_order(), random={s: self.random_order(s) for s in seeds})
