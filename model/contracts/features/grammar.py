"""Model input layer: the grammar of the features.

A feature states something about a table's rows at an example. Its term says what: which items it ranges over (rows, cells, groups, boxes, values), what it
reads of each item, what it compares that with (a grid of the example, another table, the other examples), under which equivalence, and how it pools the items.
A term is built once, from a small set of operators, with variables in place of columns; a schema gives a term a name, and it gives a feature for each binding of its
variables to the columns of a table. So the factors of a feature are explicit: a term can be read as a tree, and the grids it reads follow from it.

    GRID_STAGE.define('{p},{x} determines the output color', determines(rows_if_several(), column(x), grid_color_of_row(p, OUTPUT)), p=cell_columns(OUTPUT), x=other_than(p))

An operator's value is ABSENT where it does not apply, and the schema then gives no feature.
"""
import os
import re

ABSENT = type('Absent', (), {'__repr__': lambda self: 'ABSENT'})()


class GridLabeling:
    """One grid of an example, as a labeling of its cells by an equivalence type. name: the grid as a feature says it; one, many: its labels as a feature says them."""

    def __init__(self, grid, label='color', say=None, plural=None):
        self.grid, self.label = grid, label
        self.name = grid if label == 'color' else '%s %s labeling' % (grid, label)
        self.kind = say or label
        self.kinds = plural or label + 's'
        self.one, self.many = '%s %s' % (grid, self.kind), '%s %s' % (grid, self.kinds)

    def __repr__(self):
        return self.name

    def other(self):
        return GridLabeling('output' if self.grid == 'input' else 'input', self.label, self.kind, self.kinds)


INPUT, OUTPUT = GridLabeling('input'), GridLabeling('output')
GRIDS = (INPUT, OUTPUT)
# the equivalence types of a second version of the library, beside the colors: (label, what a feature calls a label, and several)
LABEL_TYPES = (('shape', 'shape', 'shapes'), ('shape up to D4', 'shape up to rotation and reflection', 'shapes up to rotation and reflection'), ('component', 'component', 'components'), ('component size', 'component size', 'component sizes'))
VERSION = int(os.environ.get('CONTRACTS_LIBRARY', '1'))
LABELINGS = tuple(GridLabeling(g, *t) for t in LABEL_TYPES for g in ('input', 'output')) if VERSION > 1 else ()


_ids = {}


class Term:
    """A node of a term. Called with the context and the binding, or with those and an item, as its operator takes them. Equal nodes share one id, so
    the features of a table share what a memoized node gives."""
    __slots__ = ('head', 'fn', 'args', 'memo_vars', 'id', 'own_reads')

    def __init__(self, head, fn, args, memo, reads=()):
        self.head, self.fn, self.args = head, fn, args
        self.memo_vars = sorted(variables(args)) if memo else None
        self.id = _ids.setdefault((head, args), len(_ids))
        self.own_reads = frozenset(reads)

    def __call__(self, c, e, *item):
        if self.memo_vars is None:
            return self.fn(c, e, *item, *self.args)
        key = (self.id, tuple([e[v] for v in self.memo_vars]), item)
        held = c.memo.get(key, c)
        if held is c:
            held = c.memo[key] = self.fn(c, e, *item, *self.args)
        return held

    def tree(self):
        return (self.head,) + tuple(tree(a) for a in self.args)

    def reads(self):
        """The grids that the term reads: those its operators state, and those in their arguments."""
        return self.own_reads | grids_in(self.args)

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, Term) and self.id == other.id


def tree(x):
    if isinstance(x, Term):
        return x.tree()
    if isinstance(x, tuple):
        return tuple(tree(y) for y in x)
    if isinstance(x, GridLabeling):
        return x.name
    return x


def grids_in(args):
    out = frozenset()
    for u in args:
        if isinstance(u, GridLabeling):
            out |= {u.grid}
        elif isinstance(u, Term):
            out |= u.reads()
        elif isinstance(u, tuple):
            out |= grids_in(u)
    return out


class Var(str):
    """A variable of a term: a name that a schema binds to a column."""
    __slots__ = ()


def variables(args):
    out = set()
    for a in args:
        if isinstance(a, Var):
            out.add(str(a))
        elif isinstance(a, Term):
            out |= variables(a.args)
        elif isinstance(a, tuple):
            out |= variables(a)
    return out


def operator(fn=None, memo=False, name=None, reads=()):
    """Makes an operator of a function fn(c, e, [item,] *args). memo: whether a value is kept per binding of the variables it reads. reads: the grids it reads that its arguments do not name."""
    def wrap(f):
        head = name or f.__name__.rstrip('_')

        def make(*args):
            return Term(head, f, args, memo, reads)
        make.head = head
        return make
    return wrap(fn) if fn is not None else wrap


def function(fn):
    """Makes an operator of a pure function of its evaluated arguments. The term is absent where an argument is."""
    head = fn.__name__.rstrip('_')

    def run(c, e, *args):
        held = []
        for u in args:
            if isinstance(u, Term) or getattr(u, 'is_term', False):
                u = u(c, e)
                if u is ABSENT:
                    return ABSENT
            held.append(u)
        return fn(*held)

    def make(*args):
        return Term(head, run, args, False)
    make.head = head
    make.fn = fn
    return make


class Schema:
    """A named term with variables. binders: (variable, domain) in binding order, where a domain(c, e) gives the variable's values, as (column index, token)."""
    __slots__ = ('pattern', 'term', 'binders', 'fmt', 'order', 'also')

    def __init__(self, pattern, term, binders, also=None):
        self.pattern, self.term, self.binders, self.also = pattern, term, binders, also
        self.order = re.findall(r'\{(\w+)\}', pattern)
        self.fmt = re.sub(r'\{\w+\}', '%s', pattern.replace('%', '%%'))

    def reads(self):
        return self.term.reads()

    def semantic_term(self):
        """The term as a tree of operators, grids, equivalence relations and named measures, without its guards and limits. A column stands as ('column', k), the k-th column in the feature's name."""
        return prune(self.term, {v: k for k, v in enumerate(self.order)})

    def template(self):
        """The feature's name with a column as C and another table as T, as the feature's keys give it once their tokens are masked."""
        names = {'t': 'T', 'va': 'T.C via T.C', 'vb': 'T.C via T.C'}
        return re.sub(r'\{(\w+)\}', lambda m: names.get(m[1], 'C'), self.pattern)

    def run(self, c, out):
        walk(self, c, out, 0, {}, {})


def walk(r, c, out, at, e, names):
    if at == len(r.binders):
        v = r.term(c, e)
        if v is not ABSENT:
            key = r.fmt % tuple(names[n] for n in r.order)
            out[key] = v
            if r.also is not None:
                out[re.sub(r'\{\w+\}', '%s', r.also) % tuple(names[n] for n in re.findall(r'\{(\w+)\}', r.also))] = v
        return
    v, dom = r.binders[at]
    for i, tok in dom(c, e):
        e[v], names[v] = i, tok
        walk(r, c, out, at + 1, e, names)


GUARDS = ('nonempty', 'nonempty_set', 'several', 'guarded_rows', 'when_table_has_cells')  # an operator that gives its argument, where it applies
LIMITS = ('defined', 'varied', 'two')  # what a test needs of its items


def prune(x, places):
    if isinstance(x, Var):
        return ('column', places.get(str(x)))
    if isinstance(x, Term):
        if x.head == 'guarded':
            return prune(x.args[1], places)
        if x.head in GUARDS:
            return prune(x.args[0], places)
        if x.head in ('rows_if_several', 'rows_if_any'):
            return ('rows',)
        return (x.head,) + tuple(u for u in (prune(u, places) for u in x.args if u not in LIMITS) if u is not None)
    if isinstance(x, GridLabeling):
        return x.name
    if isinstance(x, tuple):
        return tuple(prune(u, places) for u in x)
    if isinstance(x, (bool, int, float)) or x is None:
        return None  # a limit
    if isinstance(x, str):
        return x
    if callable(x) and hasattr(x, '__name__'):
        return x.__name__.strip('_')
    return repr(x)


SCHEMAS = []


def tail(pattern):
    """The text of a feature's name after its last column: what a test by suffix reads."""
    return pattern[pattern.rindex('}') + 1:] if '}' in pattern else pattern


def tails(schemas, reads):
    """The tails of the schemas whose terms read what the test accepts. reads(set of grids)."""
    return tuple(dict.fromkeys(tail(r.pattern) for r in schemas if reads(r.reads())))


class Stage:
    """The schemas that one step of the library runs."""

    def __init__(self, name):
        self.name, self.rules = name, []

    def define(self, pattern, term, also=None, **binders):
        self.rules.append(Schema(pattern, term, [(k, v) for k, v in binders.items()], also))
        SCHEMAS.append(self.rules[-1])

    def run(self, c, out=None):
        out = {} if out is None else out
        for r in self.rules:
            r.run(c, out)
        return out
