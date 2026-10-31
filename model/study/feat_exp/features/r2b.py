"""Features of explorer B, round 2: degenerate computed columns, the domain of an INIT input, and overlap with
clauses before the point."""
import collections as C

from featlib import feature, parse


def _contexts(table, tests=False):
    """(assignment, train) -> rows of the first model; a row is a list of cell values (tuples). With `tests` the test
    entries are in it, under the key (assignment, ('test', test index))."""
    out = {}
    for e in (table.all_entries if tests else table.entries):
        out.setdefault((e['assignment'], e['train'] if 'train' in e else ('test', e['test'])), [[tuple(c['value']) for c in r] for r in e['rows']])
    return out


def _atoms(tree):
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] not in ('OR', 'NOT') and not tree[0].startswith(':'):
            yield tree
            return
        for t in tree:
            yield from _atoms(t)


def _sites(atom):
    for s in atom[1:]:
        if isinstance(s, list) and s and isinstance(s[0], str) and s[0].startswith(':'):
            yield s[0][1:], s[1:]


@feature
def b3_zero_relative(p):
    """B3: share of X cells, in columns that a `relative` atom outputs or that have type Offset, that are the zero vector; None without such a column or row."""
    names, types = p.x.names(), p.x.types()
    cols = {i for i, t in enumerate(types) if t == 'Offset'}
    for a in _atoms(parse(p.form)):
        if a[0] == 'relative':
            for f, terms in _sites(a):
                if f == 'X_rel':
                    cols |= {names.index(t[1:]) for t in terms if isinstance(t, str) and t.startswith('*') and t[1:] in names}
    if not cols:
        return None
    total = zero = 0
    for rows in _contexts(p.x, True).values():
        for r in rows:
            for i in cols:
                total += 1
                zero += all(v == 0 for v in r[i])
    return zero / total if total else None


def _init_line(p):
    """The parsed INIT clause at the point, cut to the ports before the point's port."""
    lines = [l for l in (p.dir / 'mutant.arclog').read_text().splitlines() if l.strip()]
    tree = parse(lines[p.point[0]])
    tree = tree[0] if tree else None
    if not tree or tree[0] != 'INIT':
        return None
    return tree[:3] + tree[3:3 + p.point[1]]


@feature
def b5_init_domain_share(p):
    """B5: for an INIT input point with earlier ports, the share of X's Position and Box cells (frame input) that lie in the same-named column of a table that an earlier port of that INIT reads; None otherwise."""
    if not p.kind.startswith('INIT') or len(p.point) < 2:
        return None
    init = _init_line(p)
    if not init or len(init) <= 3:
        return None
    tables = {t.name: t for t in p.available()}
    domain = C.defaultdict(set)
    for port in init[3:]:
        for a in _atoms(port[2:]):
            t = tables.get(a[0])
            if t is None:
                continue
            names = t.names()
            ctx = _contexts(t)
            for f, terms in _sites(a):
                if f in names:
                    for key, rows in ctx.items():
                        domain[key] |= {r[names.index(f)] for r in rows}
    if not domain:
        return None
    types, frames = p.x.types(), p.x.frames()
    cols = [i for i, (t, f) in enumerate(zip(types, frames)) if t in ('Position', 'Box') and f == 'input']
    total = inside = 0
    for key, rows in _contexts(p.x).items():
        for r in rows:
            for i in cols:
                total += 1
                inside += r[i] in domain.get(key, ())
    return inside / total if total else None


def _signatures(atoms):
    return C.Counter((a[0], tuple(f for f, _ in _sites(a))) for a in atoms if any(True for _ in _sites(a)))


def _bodies(line):
    """(role, atom signature counter) for the body of a RULE or DET, and for each port of an INIT.
    The role of an INIT port is (component, port name); the role of a RULE body is 'rule'."""
    tree = parse(line)
    if not tree or not isinstance(tree[0], list) or not tree[0]:
        return []
    t = tree[0]
    if t[0] in ('RULE', 'DET'):
        return [('rule', _signatures(_atoms(t[2:])))]
    if t[0] == 'INIT' and len(t) > 2:
        return [((t[2], port[0]), _signatures(_atoms(port[2:]))) for port in t[3:] if isinstance(port, list) and port]
    return []


def _point_role(p):
    """The role of the clause at the point: (component, port name) for an INIT port, else 'rule'."""
    if p.kind.startswith('INIT') and len(p.point) >= 2:
        lines = [l for l in (p.dir / 'mutant.arclog').read_text().splitlines() if l.strip()]
        t = parse(lines[p.point[0]])[0]
        if t[0] == 'INIT' and len(t) > 3 + p.point[1] and isinstance(t[3 + p.point[1]], list):
            return (t[2], t[3 + p.point[1]][0])
    return 'rule'


@feature
def b6_prior_clause_overlap(p):
    """B6: the largest multiset Jaccard overlap between the candidate's atoms (relation and site names only) and the atoms of one earlier clause body of the same role (an INIT port of the same component and port name, or a RULE body); 'exact' is 1 when the overlap is 1."""
    mine = _signatures(_atoms(parse(p.form)))
    if not mine:
        return None
    role = _point_role(p)
    best = 0.0
    for line in p.prefix:
        for r, body in _bodies(line):
            if r != role:
                continue
            union = sum((mine | body).values())
            if union:
                best = max(best, sum((mine & body).values()) / union)
    return {'jaccard': best, 'exact': float(best == 1.0)}
