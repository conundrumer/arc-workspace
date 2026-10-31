"""Round 4, explorer J: what separates gold's table from the other valid and invalid tables at a Rule point.

A site term is `*V` (binds V), `^V` (binds V and exports it as a key column), a plain variable, or a literal.
A table-read atom is an atom whose interface is an input fact or a table (an earlier clause's, or an instance's port);
any other atom with sites is a library atom (relation or macro). A label is computed when a library atom makes it.
An atom makes the labels that it stars. Where one branch of an OR stars a label that every other branch names, the text
puts the star at one site, and every atom of the OR that names the label makes it.
The columns of X that hold the candidate's labels come from featlib's correspondence (`p.clause.x_columns`).
Rows of X are read per example, in the first model of each (assignment, example).
"""
import collections as C
import re

from featlib import BOX_TYPES, feature, parse

COMPARISON = {'=', '!=', '<', '>', '<=', '>=', }
TABLE_KINDS = ('fact', 'table', 'clause', 'port', 'output', 'x')
LIBRARY_KINDS = ('relation', 'macro')


def _walk(tree, neg=False):
    """Yield (atom, below NOT) for every relation atom of a parsed form."""
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] not in ('OR', 'NOT', 'IF') and not tree[0].startswith(':'):
            yield tree, neg
            return
        inner = neg or (bool(tree) and tree[0] == 'NOT')
        for t in tree:
            yield from _walk(t, inner)


def _made(scope):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in scope.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if any(True in flags for flags in branches.values()) and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _origin(p, v):
    """The Variable that stands for the label v where it is made. An INIT port reads the key's labels, and the key
    clause makes them."""
    key = p.clause.key
    if key is not None and v.scope is not key and v.label in key.key_order() and not v.binders:
        return key.variables.get(v.label, v)
    return v


def _makers(p, v):
    """The sites that make the label of the Variable v: its starred sites, and the sites of the OR atoms that name a
    label that the branches of an OR make."""
    v = _origin(p, v)
    made = _made(v.scope)
    return [a for a in v.occurrences if a.atom is not None and (
        a.binds or any((orp, v.label) in made for orp, _ in a.atom.branch))]


def _computed(p):
    """{X column name: Variable} for the X columns that hold a label which a library atom makes."""
    return {name: v for name, v in p.clause.x_columns.items()
            if any(a.atom.kind in LIBRARY_KINDS for a in _makers(p, v))}


def _cell_columns(p):
    """The computed X columns that hold cells in a grid frame (type Position or Box, and a frame tag that names no
    relation site): {X column name: Variable}."""
    return {name: v for name, v in _computed(p).items()
            if v.column.type in ('Position', 'Box') and v.column.frame_kind != 'site'}


def _example_rows(p):
    """The rows of the first model of each (assignment, example) context of X, as tuples of raw cell values. A context
    that X holds no row for is an empty list. A table with an Example column holds the rows of every example in each
    entry, and each row belongs to the example its Example cells name."""
    rows = p.x.examples(decoded=False)
    return [rows.get((e['assignment'], e['train']), [[]])[0]
            for e in {(e['assignment'], e['train']): e for e in p.x.entries}.values()]


@feature
def j1_ungrounded_cells(p):
    """J1: library-computed cell columns (Position or Box in a grid frame) that no table-read atom joins.

    cells: computed cell columns; ungrounded: those whose label occurs unstarred at no site of a table-read atom
    outside NOT (so nothing checks that the computed cell is a cell of a table or of the input); share: ungrounded over
    cells; bare: those that occur in no atom besides the one that makes them. None without a computed cell column.
    """
    cols = _cell_columns(p)
    if not cols:
        return None
    made = {}
    ung = bare = 0
    for v in cols.values():
        makers = {id(a) for a in _makers(p, _origin(p, v))}
        grounded = any(id(a) not in makers and a.atom.kind in TABLE_KINDS and not a.atom.negated
                       for a in v.joins + _origin(p, v).joins)
        ung += not grounded
        bare += len({id(a.atom) for a in v.occurrences + _origin(p, v).occurrences if a.atom is not None}) <= 1
    return {'cells': len(cols), 'ungrounded': ung, 'share': ung / len(cols), 'bare': bare}


def _collapses(p, v, constant):
    """Whether the constant computed column that holds the Variable v collapses varying inputs, and so loses
    information. It does where a library atom that makes it takes the literal 0, or a label that is not held by a
    constant X column (`constant` says whether an X column index is one). A column whose makers take only constant
    columns is constant by construction. An Offset made from two or more different varying labels, none repeated, is
    a law (the translation between two cells that move together), not a collapse."""
    held = {w.label: w.column.index for w in p.clause.x_columns.values()
            if w is not None and w.column is not None and w.column.index is not None}
    for site in _makers(p, v):
        atom = site.atom
        if atom.kind not in LIBRARY_KINDS or site.column_type not in BOX_TYPES:
            continue
        inputs = [b for b in atom.arguments if b is not site and not b.binds]
        if any(b.label is None for b in inputs):
            return True
        varying = {b.label for b in inputs if b.label not in held or not constant(held[b.label])}
        labels = [b.label for b in inputs]
        if varying and not (v.column.type == 'Offset' and len(varying) >= 2 and len(set(labels)) == len(labels)):
            return True
    return False


@feature
def j3_dead_derived(p):
    """J3: library-computed geometric columns (Position, Box or Offset) with one value in every example that has two
    or more rows, that collapse varying inputs.

    dead: such columns; share: dead over computed geometric columns; cols: computed geometric columns; multi: the share
    of examples with two or more rows. A computed column that does not vary while the table varies gives no row
    information, but one that is constant because every input of its makers is a constant column is not counted, and
    neither is an Offset between two different varying cells (see `_collapses`). A column is computed when the label it holds is made by a library atom at a site whose declared type
    is Box, Position or Offset; `p.clause.x_columns` says which label each column of X holds, in RULE, DET and INIT
    tables. A table with an Example column is read example by example. None without a computed geometric column or
    without an example of two or more rows.
    """
    cols = {v.column.index: v for v in _computed(p).values()
            if v.column.type in BOX_TYPES and any(a.atom.kind in LIBRARY_KINDS and a.column_type in BOX_TYPES
                                                  for a in _makers(p, v))}
    ctx = _example_rows(p)
    multi = [rows for rows in ctx if len(rows) >= 2]
    if not cols or not multi:
        return None

    def constant(k):
        return all(len({r[k] for r in rows}) == 1 for rows in multi)

    dead = sum(constant(k) and _collapses(p, v, constant) for k, v in cols.items())
    return {'dead': dead, 'share': dead / len(cols), 'cols': len(cols), 'multi': len(multi) / len(ctx)}


@feature
def j4_cell_collisions(p):
    """J4: rows that produce the same computed cell as another row of the same example.

    For each library-computed cell column (Position or Box in a grid frame), the share of rows whose value occurs in
    another row of the same example (the first model of each context); `max` and `mean` over those columns, `cols`
    their number. None without such a column or without rows.
    """
    cols = [v.column.index for v in _cell_columns(p).values()]
    ctx = _example_rows(p)
    if not cols or not any(ctx):
        return None
    shares = []
    for k in cols:
        tot = dup = 0
        for rows in ctx:
            c = C.Counter(r[k] for r in rows)
            tot += len(rows)
            dup += sum(n for n in c.values() if n > 1)
        if tot:
            shares.append(dup / tot)
    if not shares:
        return None
    return {'max': max(shares), 'mean': sum(shares) / len(shares), 'cols': len(shares)}


def _clause_names(prefix):
    """Name of the table each prefix clause defines -> index of the clause that defines it last."""
    idx = {}
    for j, line in enumerate(prefix):
        t = parse(line)
        t = t[0] if t and isinstance(t[0], list) else None
        if t and len(t) > 1 and isinstance(t[1], str) and t[1].startswith('&'):
            idx[t[1]] = j
    return idx


@feature
def j5_read_age(p):
    """J5: how long before the point the tables that the candidate reads were defined.

    For each read of an earlier clause's table (`&name` or `&name.port`) outside the clause itself, the age is the
    number of clauses between that clause and the point (1 for the clause just before). n: reads; mean, min and max age;
    prev: 1 when some read has age 1; deep: reads with age above 5. None without a read of an earlier clause.
    """
    idx = _clause_names(p.prefix)
    point = len(p.prefix)
    ages = []
    for a, _ in _walk(parse(p.form)):
        head = a[0]
        if head.startswith('&') and head.split('.')[0] in idx:
            ages.append(point - idx[head.split('.')[0]])
    if not ages:
        return None
    return {'n': len(ages), 'mean': sum(ages) / len(ages), 'min': min(ages), 'max': max(ages),
            'prev': float(min(ages) == 1), 'deep': sum(a > 5 for a in ages)}


_READ = re.compile(r'\((&[A-Za-z0-9_]+)')


def _pending(prefix):
    """Tables that prefix clauses define and no later prefix clause reads, as (clause index, name), oldest first. A DET
    clause is left out: the program declares its parameters ahead, and later clauses read them in any order."""
    defined, read = [], set()
    for j, line in enumerate(prefix):
        t = parse(line)
        t = t[0] if t and isinstance(t[0], list) else None
        if not t or len(t) < 2 or not isinstance(t[1], str) or not t[1].startswith('&'):
            continue
        body = line.split(t[1], 1)[1] if t[1] in line else ''
        read |= set(_READ.findall(body))
        if t[0] != 'DET':
            defined.append((j, t[1]))
    return [(j, n) for j, n in defined if n not in read]


@feature
def j6_pending_reads(p):
    """J6: how many tables that the earlier clauses define and nothing before the point reads this candidate reads.

    pending: such tables; read: the pending tables that the candidate reads; share: read over pending; newest: 1 when the
    candidate reads the most recently defined pending table. None without a pending table.
    """
    pend = _pending(p.prefix)
    if not pend:
        return None
    reads = {a[0].split('.')[0] for a, _ in _walk(parse(p.form)) if a[0].startswith('&')}
    hit = [(j, n) for j, n in pend if n in reads]
    return {'pending': len(pend), 'read': len(hit), 'share': len(hit) / len(pend),
            'newest': float(pend[-1][1] in reads)}


@feature
def j7_unbounded_numbers(p):
    """J7: computed Number columns of X that no comparison atom mentions.

    numbers: the Number columns of X that hold a label which a library atom makes; free: those whose label occurs in no
    comparison atom (`=`, `!=`, `<`, `>`, `<=`, `>=`); share: free over numbers. A computed count or distance that
    nothing bounds is not checked against anything. None without such a column.
    """
    nums = [v for v in _computed(p).values() if v.column.type == 'Number']
    if not nums:
        return None
    free = [v for v in nums if not any(a.atom is not None and a.atom.operator
                                       for a in v.occurrences + _origin(p, v).occurrences)]
    return {'numbers': len(nums), 'free': len(free), 'share': len(free) / len(nums)}
