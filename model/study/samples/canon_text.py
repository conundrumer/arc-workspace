"""The canonical text of one form, the `body` of a target function, and the stand-in for the engine's canonical form.

The engine exposes no canonical text to Python, so this module writes one (spec Part 3, "The canonical text"; contract, `TargetFunction.body`). It is the `body` of a function, not its hash: `function_hash.py` gives the engine's FunctionHash.

- The form's own label is dropped.
- A reference is written by the caller's `refs`: the table it uses, `@<FunctionHash>.<Name>`.
- A derived relation's field is written as the field it came from (`with_fields`): the field of the first positive atom that binds `*V`, followed through derived relations.
- `*` is dropped and `^` is kept.
- The atoms of a body, the branches of an OR (sorted, as decided for the engine), the atoms of a branch, a NOT, an ALL's guard and conclusion, a key group's atoms and a port's atoms are sets: they are written in the order of their text, each NOT and ALL after the other items.
- A key group, a port and the head of a port keep their places. A form of kind CHOOSE or of one proposer keeps its written order.
- Variables are named by color refinement over their sites. Where classes tie when refinement ends, each numbering of the tied classes is tried, up to NUMBERINGS, and the least text is kept; past that the text is written with the first NUMBERINGS and `exact` is false.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
import functools, itertools, math, re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from study_paths import MAIN_ROOT

type Tree = str | list[Tree]

VERSION = 'canon-1'
NUMBERINGS = 720
TOKEN = re.compile(r'\(|\)|[^\s()]+')
MARKED = re.compile(r'^[*^]([A-Z][A-Za-z0-9_]*)$')
VARIABLE = re.compile(r'^([*^]?)([A-Z][A-Za-z0-9_]*)$')
GIVEN = ('input', 'ex_input', 'ex_output')
SYMMETRIC = ('=', '!=')
LATE = ('NOT', 'ALL')
OUT_FIELD = ':out#'  # the origin of a column that comes from the i-th field of a component's output: `:out#i`


def parse(text: str) -> list[Tree]:
    stack: list[list[Tree]] = [[]]
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]


def write(t: Tree) -> str:
    return t if isinstance(t, str) else '(' + ' '.join(write(x) for x in t) + ')'


def is_atom(t: Tree) -> bool:
    return isinstance(t, list) and len(t) > 1 and isinstance(t[0], str) and all(isinstance(x, list) and x and isinstance(x[0], str) and x[0].startswith(':') for x in t[1:])


def atoms(t: Tree, positive: bool = True) -> Iterator[tuple[list[Tree], bool]]:
    if isinstance(t, list):
        if is_atom(t):
            yield t, positive
        else:
            for x in t:
                yield from atoms(x, positive and t[0] != 'NOT')


def out_field(i: int) -> str:
    return OUT_FIELD + str(i)


def _ports(section: str) -> dict[tuple[str, str], tuple[bool, list[str]]]:
    text = re.sub(r';[^\n]*', '', (MAIN_ROOT / 'engine/lib/registry.sexpr').read_text())
    got: dict[tuple[str, str], tuple[bool, list[str]]] = {}
    for form in parse(text):
        if isinstance(form, list) and form[:1] == ['component']:
            for part in form:
                if isinstance(part, list) and part[:1] == [section]:
                    for o in part[1:]:
                        if isinstance(o, list):
                            fs = [f for f in o[1:] if isinstance(f, list)]
                            got[(str(form[1]), str(o[0]))] = (any(f[0] == 'key' for f in fs), [':' + str(f[0]) for f in fs if f[0] not in ('key', 'copies', 'default')])
    return got


@functools.cache
def registry() -> dict[tuple[str, str], list[str]]:
    """{(component, output): the output's fields other than its key, as `:name`} from engine/lib/registry.sexpr."""
    return {k: v[1] for k, v in _ports('outputs').items()}


@functools.cache
def port_registry() -> dict[tuple[str, str], tuple[bool, list[str]]]:
    """{(component, port): (whether the port has the component's key, its fields other than its key as `:name`)}, for the input ports and the outputs of each component. The engine exports a table for an input port that a consumer reads, such as `&r1.minus`: the key's columns where the port has the key, then the port's own."""
    return _ports('inputs') | _ports('outputs')


@functools.cache
def proposer_columns() -> dict[str, list[str]]:
    """{proposer: its columns as `:name`, in order} from engine/lib/registry.sexpr: the columns of a form that is a bare proposer, such as `(DET &r0 DominantColor)`."""
    text = re.sub(r';[^\n]*', '', (MAIN_ROOT / 'engine/lib/registry.sexpr').read_text())
    got: dict[str, list[str]] = {}
    for form in parse(text):
        if isinstance(form, list) and form[:1] == ['proposer']:
            for part in form:
                if isinstance(part, list) and part[:1] == ['columns']:
                    got[str(form[1])] = [':' + str(c[0] if isinstance(c, list) else c) for c in part[1:]]
    return got


def with_fields(lines: list[str]) -> tuple[list[list[Tree]], dict[str, dict[str, str]]]:
    """(the trees of a case's lines, each derived relation's field written as the field it came from; {label of a RULE or DET: {its column's field `:V`: the field it came from}})."""
    origin: dict[str, dict[str, str]] = {}
    component: dict[str, str] = {}
    out: list[list[Tree]] = []
    for line in lines:
        t = parse(line)[0]
        assert isinstance(t, list)
        own = t[1][1:] if len(t) > 1 and isinstance(t[1], str) else ''
        if t[0] == 'INIT' and len(t) > 2 and isinstance(t[2], str):
            component[own] = t[2]
        binds = t[0] in ('RULE', 'DET') and len(t) > 2 and isinstance(t[1], str)
        for a, pos in atoms(t[2:] if len(t) > 2 else []):
            head = a[0]
            fields: list[str] = []
            if isinstance(head, str) and head.startswith('&'):
                label, _, rest = head[1:].partition('.')
                if '.' not in head:
                    m = origin.get(label, {})
                    for x in a[1:]:
                        assert isinstance(x, list) and isinstance(x[0], str)
                        x[0] = m.get(x[0], x[0])
                elif label in component:
                    fields = registry().get((component[label], rest.split('.')[0]), [])
            if binds and pos:
                for x in a[1:]:
                    assert isinstance(x, list)
                    if len(x) == 2 and isinstance(x[1], str) and x[1].startswith('*') and isinstance(x[0], str):
                        src = out_field(fields.index(x[0])) if x[0] in fields else x[0]
                        origin.setdefault(own, {}).setdefault(':' + x[1][1:], src)
                    elif isinstance(x[0], str) and x[0].startswith(':'):
                        for k, f in enumerate(x[1:]):  # a site on a record (`:key`, `:a`) has a site on each field in it, and a starred one is a column too
                            if isinstance(f, list) and len(f) == 2 and isinstance(f[0], str) and isinstance(f[1], str) and f[1].startswith('*'):
                                origin.setdefault(own, {}).setdefault(':' + f[1][1:], x[0][1:] + '.' + f[0][1:])
                            elif isinstance(f, str) and f.startswith('*'):
                                origin.setdefault(own, {}).setdefault(':' + f[1:], f'{x[0][1:]}.{k}')
        out.append(t)
    return out, origin


@dataclass
class Node:
    """A part of a form. A leaf has `tree`. Another node writes `head`, then its `items` (sorted where `sort`), in parentheses where `paren`."""
    head: list[str] = field(default_factory=list)
    items: list['Node'] = field(default_factory=list)
    sort: bool = False
    paren: bool = True
    tree: Tree | None = None


@dataclass
class Canon:
    text: str
    exact: bool
    field_conflicts: int


def conjuncts(items: list[Tree]) -> list[Node]:
    out = []
    for a in items:
        if isinstance(a, list) and a and a[0] == 'OR':
            out.append(Node(['OR'], [Node([], conjuncts(b if isinstance(b, list) else [b]), True) for b in a[1:]], True))
        elif isinstance(a, list) and a and a[0] == 'NOT':
            out.append(Node(['NOT'], conjuncts(a[1:]), True))
        elif isinstance(a, list) and len(a) == 3 and a[0] == 'ALL' and isinstance(a[1], list) and isinstance(a[2], list):
            out.append(Node(['ALL'], [Node([], conjuncts(a[1]), True), Node([], conjuncts(a[2]), True)]))
        else:
            out.append(Node(tree=a))
    return out


def port(p: list[Tree]) -> Node:
    """A port: its name and its head keep their places, its atoms are a set."""
    name, rest = p[0], p[1:]
    assert isinstance(name, str)
    if not rest:
        return Node([name])
    return Node([name], [Node(tree=rest[0]), Node([], conjuncts(rest[1:]), True, False)])


def structure(t: list[Tree]) -> Node:
    """The form without its own label as parts. The caller has dropped t[1]."""
    kind = t[0]
    assert isinstance(kind, str)
    rest = t[1:]
    if kind in ('RULE', 'DET') and all(isinstance(a, list) for a in rest):
        return Node([kind], [Node([], conjuncts(rest), True, False)])
    if kind == 'INIT' and isinstance(rest[0], str):
        kids = []
        for c in rest[1:]:
            assert isinstance(c, list)
            if c[0] == 'key' and len(c) > 1 and isinstance(c[1], list):
                kids.append(Node(['key'], [Node([], conjuncts(c[1]), True)] + [port(q) for q in c[2:] if isinstance(q, list)]))
            else:
                kids.append(port(c))
        return Node([kind, rest[0]], kids)
    return Node([kind], [Node(tree=a) for a in rest], False, False)


def variables(t: list[Tree]) -> list[str]:
    """The labels that carry a mark somewhere in the form, in order of first appearance."""
    got: dict[str, None] = {}

    def go(x: Tree) -> None:
        if isinstance(x, str):
            m = MARKED.match(x)
            if m:
                got.setdefault(m[1])
        else:
            for y in x:
                go(y)
    go(t)
    return list(got)


def leaf_text(x: Tree, ren: Callable[[str], str], vs: frozenset[str], head: bool = False) -> str:
    if isinstance(x, str):
        m = VARIABLE.match(x)
        if m and m[2] in vs and not head:
            return m[1].replace('*', '') + ren(m[2])
        return x
    parts = [leaf_text(y, ren, vs, i == 0) for i, y in enumerate(x)]
    if x and x[0] in SYMMETRIC:
        parts = [parts[0], *sorted(parts[1:])]
    return '(' + ' '.join(parts) + ')'


def emit(n: Node, ren: Callable[[str], str], vs: frozenset[str]) -> str:
    if n.tree is not None:
        return leaf_text(n.tree, ren, vs)
    kids = [emit(k, ren, vs) for k in n.items]
    if n.sort:
        late = [k.tree is None and bool(k.head) and k.head[0] in LATE for k in n.items]
        order = sorted(range(len(kids)), key=lambda i: (late[i], kids[i]))
        kids = [kids[i] for i in order]
    body = ' '.join([*n.head, *kids])
    return f'({body})' if n.paren else body


def leaves(n: Node, ctx: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Tree]]:
    if n.tree is not None:
        yield ctx, n.tree
        return
    for k in n.items:
        yield from leaves(k, ctx + (' '.join(n.head),))


def mentions(x: Tree, v: str) -> bool:
    if isinstance(x, str):
        m = VARIABLE.match(x)
        return bool(m) and m[2] == v
    return any(mentions(y, v) for y in x)


def refine(root: Node, vs: list[str]) -> dict[str, int]:
    """The color of each variable: the rank of its class, by color refinement over the sites in the form's leaves."""
    names = frozenset(vs)
    sites = [(c, t) for c, t in leaves(root)]
    color = {v: 0 for v in vs}
    classes = 1
    while True:
        sig = {}
        for v in vs:
            ren = (lambda u, v=v: '@' if u == v else f'c{color[u]}')
            sig[v] = (color[v], tuple(sorted((c, leaf_text(t, ren, names)) for c, t in sites if mentions(t, v))))
        rank = {s: i for i, s in enumerate(sorted(set(sig.values())))}
        color = {v: rank[sig[v]] for v in vs}
        if len(rank) == classes:
            return color
        classes = len(rank)


def canonical(tree: list[Tree], refs: Callable[[str], str]) -> Canon:
    """The canonical text of a form (its tree with the own label at tree[1]), with each `&` reference written by `refs`."""
    own = tree[1] if len(tree) > 1 and isinstance(tree[1], str) and tree[1].startswith('&') else None

    def sub(x: Tree) -> Tree:
        if isinstance(x, str):
            return refs(x) if x.startswith('&') else x
        return [sub(y) for y in x]
    conflicts = 0
    for a, _ in atoms(tree[2:]):
        if isinstance(a[0], str) and a[0].startswith('&'):
            fs = [f[0] for f in a[1:] if isinstance(f, list) and isinstance(f[0], str)]
            conflicts += len(set(fs)) < len(fs)
    t = [sub(x) for i, x in enumerate(tree) if not (own and i == 1)]
    root = structure(t)
    vs = variables(t)
    names = frozenset(vs)
    color = refine(root, vs)
    by_class: dict[int, list[str]] = {}
    for v in vs:
        by_class.setdefault(color[v], []).append(v)
    total = math.prod(math.factorial(len(m)) for m in by_class.values())
    orders = itertools.product(*(itertools.permutations(by_class[c]) for c in sorted(by_class)))
    best = None
    for perm in itertools.islice(orders, NUMBERINGS):
        number = {v: i for i, v in enumerate(v for cls in perm for v in cls)}
        text = emit(root, lambda u: f'V{number[u]}', names)
        if best is None or text < best:
            best = text
    return Canon(best if best is not None else emit(root, lambda u: u, names), total <= NUMBERINGS, conflicts)


def given_tables(tree: Tree) -> list[str]:
    """The given tables that an atom of the form uses, sorted."""
    got: set[str] = set()

    def go(x: Tree) -> None:
        if isinstance(x, list):
            if x and isinstance(x[0], str) and x[0] in GIVEN:
                got.add(x[0])
            for y in x:
                go(y)
    go(tree)
    return sorted(got)
