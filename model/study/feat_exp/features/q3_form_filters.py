"""Q3 Form filters: tests on the candidate's form that no gold atom fires, found by the per-relation-group studies.

Each key is a count of the atoms, labels or atom pairs of the candidate's body where the test holds (0 where none does),
and None where the test needs a context the candidate is not in. A test reads the candidate's form, the clauses before
the point, the library interfaces and, for `orphan_label`, the schema of X. The type of a label is the type of the column
that first makes it (`_ltype`), and so does not depend on the sites that read it.

A literal 0 that is the frame (`featlib.frame_zero`) is legal and never counts.
"""
import collections as C

from featlib import BOX_TYPES, CONVERSE, feature, frame_zero, subtype

NEGATE = {'<': '>=', '>': '<=', '<=': '>', '>=': '<', '=': '!=', '!=': '='}
OUTCOMES = {'<': {'<'}, '<=': {'<', '='}, '>': {'>'}, '>=': {'>', '='}, '=': {'='}, '!=': {'<', '>'}}
ALL_OUTCOMES = {'<', '=', '>'}
GEO = frozenset('''split neighbor same_dist same_line same_corner same_slab nearer jump jump_offset dist_pair diag_dist
diag_dirs axis_of opposite perp_dir perp turn corner_dir diag_axis_of apply_dir apply_diag_dir step_offset
dir8_opposite'''.split())
OUTSET = frozenset({'axis_outset', 'uniform_outset', 'edge_outset', 'corner_outset'})
INSET = frozenset({'axis_inset', 'uniform_inset', 'edge_inset', 'corner_inset'})
# (relation, column) sites that read the box an outset atom makes, as an inset box is read in gold
BOX_READERS = frozenset({('inside', 'B'), ('interior', 'B'), ('relative', 'Base'), ('same_corner', 'P2'),
                         ('same_dist', 'P2')})
DIST_SOURCES = frozenset({'margin.K', 'corner_dist.K', 'port:distance.K', 'port:ray.K', 'diag_dist.K1', 'diag_dist.K2',
                          'divide.Remainder'})
SIZE_SOURCES = frozenset({'box_extent.N', 'port:size.N', 'frame_extent.N', 'declared.N', 'port:fundamental_period.K',
                          'port:minimal.t'})


# ------------------------------------------------------------------------------------------------ helpers

def _body(p):
    try:
        return p.clause.body
    except Exception:
        return None


def _library(atom):
    return atom.kind in ('relation', 'macro')


def _port(atom):
    """The port name of an atom that reads a port of an instance (`&inst.port`), else None."""
    r = atom.relation
    if atom.operator is None and r.startswith('&') and '.' in r:
        return r.rsplit('.', 1)[1]
    return None


def _declared(atom):
    return atom.operator is None and atom.relation.startswith('&') and '.' not in atom.relation


def _relkey(atom):
    if atom.operator:
        return 'cmp'
    port = _port(atom)
    if port is not None:
        return 'port:' + port
    if _declared(atom):
        return 'declared'
    return atom.relation


def _binder(arg):
    """The first Argument that makes the label of arg, or None."""
    v = arg.variable
    if v is None:
        return None
    bs = [b for b in v.binders if b.atom is not None]
    return bs[0] if bs else None


def _src(arg):
    """'relation.column' of the site that first makes the label, with a port as `port:<name>` and any declared table
    as `declared`; None where no site in the form makes it."""
    b = _binder(arg)
    if b is None or b.atom.operator:
        return None
    return f'{_relkey(b.atom)}.{b.name}'


def _meet(a, b):
    out = {x for x in a if any(subtype(x, y) for y in b)} | {y for y in b if any(subtype(y, x) for x in a)}
    return {x for x in out if not any(y != x and subtype(y, x) for y in out)}


def _vtype(v):
    """The most specific type that every site of the label admits, without X's schema."""
    cur = None
    for a in v.occurrences:
        s = set(a.column_types or ())
        if not s:
            continue
        if cur is None:
            cur = s
        else:
            m = _meet(cur, s)
            cur = m or cur
    return next(iter(cur)) if cur and len(cur) == 1 else None


def _ltype(arg):
    """The type of the label at arg: that of the column that first makes it, else the meet of its sites' columns."""
    if arg.label is None or arg.variable is None:
        return None
    b = _binder(arg)
    if b is not None and b.column_type is not None:
        return b.column_type
    return _vtype(arg.variable)


def _context(a):
    return a.branch, a.quantifier, a.conditional


def _encloses(c1, c2):
    return c1 != c2 and c2[0][:len(c1[0])] == c1[0] and c1[1] in (None, c2[1]) and c1[2] in (None, c2[2])


def _related(a, b):
    """Whether atoms a and b can hold in one conjunction: one context equals or encloses the other."""
    ca, cb = _context(a), _context(b)
    return ca == cb or _encloses(ca, cb) or _encloses(cb, ca)


def _op(atom):
    """The operator of a comparison that holds (a comparison below NOT says its converse)."""
    return NEGATE.get(atom.operator) if atom.negated else atom.operator


def _operand(arg):
    """'0' for the literal, the label for a label that is joined, None for anything else."""
    if arg is None:
        return None
    if arg.is_zero:
        return '0'
    return arg.label if arg.joins else None


def _sites(atom):
    return {a.name: a for a in atom.arguments}


# ------------------------------------------------------------------------------------------------ cell geometry

def _fn_dup(a, b):
    """Atoms of one relation that read one label at every column where neither makes a label, with at least one such
    column."""
    sa, sb = _sites(a), _sites(b)
    if set(sa) != set(sb):
        return False
    n = 0
    for name, x in sa.items():
        y = sb[name]
        if x.term[:1] == '*' or y.term[:1] == '*':
            continue
        if (x.label or '0') != (y.label or '0'):
            return False
        n += 1
    return n >= 1


@feature
def q3a_cell_geometry(p):
    """Q3a Cell geometry. `zero_geo`: atoms of the cell-geometry relations (split, neighbor, same_*, nearer, jump,
    dist_pair, diag_*, axis_of, opposite, perp, turn, ...) with a literal 0 at a Box, Position or Offset column that is
    not a frame site (`inside.B`, `interior.B`, `same_corner.P2`, `same_dist.P2`, `split.Along`). `fn_dup`: atoms of
    those relations for which another atom of the same relation, in the same or an enclosing branch, reads the same
    label at every column where neither atom makes a label, and at least one such column exists (the atoms differ only
    in the labels they make, or one reads what the other makes).

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    geo = [a for a in body.atoms if _library(a) and (a.relation in GEO or a.relation.endswith('_elem'))]
    zero = sum(1 for a in geo if any(x.is_zero and x.literal == 'zero box' and not frame_zero(x) for x in a.arguments))
    dup = 0
    for i, a in enumerate(geo):
        if any(b is not a and b.relation == a.relation and _related(a, b) and _fn_dup(a, b) for b in geo):
            dup += 1
    return {'zero_geo': zero, 'fn_dup': dup}


# ------------------------------------------------------------------------------------------------ comparisons

def _canon_cmp(atom):
    """(operand pair in sorted order, the outcomes of the first operand against the second), or None where an operand
    is not a joined label or the literal 0."""
    x, y = _operand(atom.first), _operand(atom.second)
    op = _op(atom)
    if x is None or y is None or x == y or op not in OUTCOMES:
        return None
    if x > y:
        x, y, op = y, x, CONVERSE.get(op, op)
    return (x, y), frozenset(OUTCOMES[op])


@feature
def q3b_comparisons(p):
    """Q3b Comparisons. `ne_numbers`: `!=` between two labels of type Number. `partial_overlap_pair`: comparisons for
    which another comparison of the clause has the same two operands and an outcome set that overlaps theirs, is not
    equal to it and does not cover with it all of <, = and >. `ge0_unsigned`: `>= 0` on a Number label that `margin.K`
    does not make (`margin.K` is signed). A comparison below NOT counts as its converse.

    Needs: form. Monotone: partly.
    """
    body = _body(p)
    if body is None:
        return None
    ne = ge0 = overlap = 0
    cmps = [a for a in body.comparisons if a.first is not None and a.second is not None]
    canon = [_canon_cmp(a) for a in cmps]
    for i, a in enumerate(cmps):
        op = _op(a)
        x, y = a.first, a.second
        if op == '!=' and x.joins and y.joins and _ltype(x) == 'Number' and _ltype(y) == 'Number':
            ne += 1
        if op in ('>=', '<=') and x.is_zero != y.is_zero:
            lab, zero_first = (y, True) if x.is_zero else (x, False)
            eff = CONVERSE.get(op, op) if zero_first else op
            if eff == '>=' and lab.joins and _ltype(lab) == 'Number' and _src(lab) != 'margin.K':
                ge0 += 1
        if canon[i] is not None:
            pair, s = canon[i]
            for j, c in enumerate(canon):
                if j == i or c is None or c[0] != pair:
                    continue
                t = c[1]
                if s != t and s & t and (s | t) != ALL_OUTCOMES:
                    overlap += 1
                    break
    return {'ne_numbers': ne, 'partial_overlap_pair': overlap, 'ge0_unsigned': ge0}


# ------------------------------------------------------------------------------------------------ containment

@feature
def q3c_containment(p):
    """Q3c Containment, inset and outset relations. `axis_k_zero`: a K site of an inset or outset relation holds the
    literal 0. `axis_d_from_opposite`: the D of axis_inset or axis_outset is a label that `opposite.Opp` makes.
    `centered_zero`: P of `centered` is the literal 0. `outset_box_read_by_containment`: an outset atom whose box is
    read at B of inside or interior, Base of relative, or the second Box site of same_corner or same_dist.
    `containment_same_atom`: inside or interior whose A and B are first made by one atom. `containment_B_from_offset_or_outset`:
    inside or interior whose B is first made by `relative.X_rel` or an outset relation. `containment_A_eq_B`: inside or
    interior with one label at A and B.

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    out = C.Counter({k: 0 for k in ('axis_k_zero', 'axis_d_from_opposite', 'centered_zero', 'outset_box_read_by_containment',
                                   'containment_same_atom', 'containment_B_from_offset_or_outset', 'containment_A_eq_B')})
    for a in body.atoms:
        if not _library(a):
            continue
        sites = _sites(a)
        r = a.relation
        if r in INSET or r in OUTSET:
            out['axis_k_zero'] += any(x.is_zero for n, x in sites.items() if n in ('K', 'K1', 'K2'))
        if r in ('axis_inset', 'axis_outset'):
            d = sites.get('D')
            out['axis_d_from_opposite'] += bool(d is not None and d.label is not None and d.variable is not None and any(
                b.atom.relation == 'opposite' and b.name == 'Opp' for b in d.variable.binders if b.atom is not None))
        if r == 'centered':
            out['centered_zero'] += bool(sites.get('P') is not None and sites['P'].is_zero)
        if r in OUTSET:
            box = sites.get('B')
            if box is not None and box.variable is not None and any(
                    o.atom is not a and o.atom.operator is None and (o.atom.relation, o.name) in BOX_READERS
                    for o in box.variable.occurrences if o.atom is not None):
                out['outset_box_read_by_containment'] += 1
        if r in ('inside', 'interior'):
            x, y = sites.get('A'), sites.get('B')
            if x is None or y is None:
                continue
            if x.label is not None and x.label == y.label:
                out['containment_A_eq_B'] += 1
            bx, by = _binder(x), _binder(y)
            if bx is not None and by is not None and bx.atom is by.atom:
                out['containment_same_atom'] += 1
            if by is not None and (by.atom.relation in OUTSET or (by.atom.relation == 'relative' and by.name == 'X_rel')):
                out['containment_B_from_offset_or_outset'] += 1
    return dict(out)


# ------------------------------------------------------------------------------------------------ box measures

def _graph_distance(atoms, a, b, skip):
    """Hops from label a to label b through the atoms that name labels, or 99 where the labels are not connected."""
    if a is None or b is None:
        return None
    if a == b:
        return 0
    edges = [{x.label for x in at.arguments if x.label} for at in atoms if at.operator is None and id(at) not in skip]
    seen, frontier, d = {a}, {a}, 0
    while frontier:
        d += 1
        nxt = set()
        for ls in edges:
            if ls & frontier:
                nxt |= ls - seen
        if b in nxt:
            return d
        seen |= nxt
        frontier = nxt
    return 99


def _before_scope(p):
    c = p.clause
    return c.body is not None and c.component == 'Order' and c.body.name == 'before'


def _margin_k_comparisons(body):
    """(comparison, effective operator, margin atom of the first operand, margin atom of the second) for the
    comparisons between two labels that `margin.K` makes."""
    for cmp in body.comparisons:
        x, y = cmp.first, cmp.second
        if x is None or y is None or not x.joins or not y.joins or _src(x) != 'margin.K' or _src(y) != 'margin.K':
            continue
        yield cmp, _op(cmp), _binder(x).atom, _binder(y).atom


@feature
def q3d_box_measures(p):
    """Q3d Box measures. `dup_margin_BD`: pairs of `margin` atoms of one sign in one conjunction with one label at B and
    one at D (their Ks measure one thing). `boxext_B_position`, `boxext_P_box`: box_extent atoms whose B label is first
    made at a Position column, or whose P label is first made at a Box column. `divide_T_zero`: divide with the literal 0
    at T. `divide_T_size`: divide whose T label is made by a size (box_extent.N, port:size.N, frame_extent.N,
    declared.N, a period). `divide_Gap_dist`: divide whose Gap label is made by a distance (margin.K, corner_dist.K,
    ray, distance, diag_dist, Remainder). `unread_box_B`, `unread_perp_A2`, `unread_cell_P_outer`: labels that a
    `port box` B column, a `perp` A2 column or a `port cell` P_outer column makes and no site reads (an A2 label that X holds is left out: a later clause can read
    it) (None in an INIT
    key clause, whose labels the ports read). `before_nonstrict`: in the `before` port of Order, comparisons between
    two `margin.K` labels with an operator other than `<`. `before_inverted`: there, `<` whose first margin is the one
    nearer the head `b` than `a`, or `>`, `>=` whose first margin is nearer `a` (nearness: hops through the atoms of
    the INIT that are not margins). The two `before` keys are None outside that port.

    Needs: form. Monotone: partly.
    """
    body = _body(p)
    if body is None:
        return None
    atoms = body.atoms
    out = {k: 0 for k in ('dup_margin_BD', 'boxext_B_position', 'boxext_P_box', 'divide_T_zero', 'divide_T_size',
                          'divide_Gap_dist', 'unread_box_B', 'unread_perp_A2', 'unread_cell_P_outer')}
    margins = [a for a in atoms if a.relation == 'margin' and _library(a)]
    for i, a in enumerate(margins):
        sa = _sites(a)
        for b in margins[i + 1:]:
            if b.negated != a.negated or not _related(a, b):
                continue
            sb = _sites(b)
            if all(sa.get(c) is not None and sb.get(c) is not None and sa[c].joins and sb[c].joins and
                   sa[c].label == sb[c].label for c in ('B', 'D')):
                out['dup_margin_BD'] += 1
    for a in atoms:
        if not _library(a):
            continue
        sites = _sites(a)
        if a.relation == 'box_extent':
            b, q = sites.get('B'), sites.get('P')
            out['boxext_B_position'] += bool(b is not None and b.joins and _ltype(b) == 'Position')
            qb = _binder(q) if q is not None and q.joins else None
            out['boxext_P_box'] += bool(qb is not None and _ltype(q) == 'Box' and not qb.column.startswith('P'))
        elif a.relation == 'divide':
            t, gap = sites.get('T'), sites.get('Gap')
            if t is not None:
                out['divide_T_zero'] += t.is_zero
                out['divide_T_size'] += bool(t.joins and _src(t) in SIZE_SOURCES)
            if gap is not None:
                out['divide_Gap_dist'] += bool(gap.joins and _src(gap) in DIST_SOURCES)
    if body.name == 'key':
        for k in ('unread_box_B', 'unread_perp_A2', 'unread_cell_P_outer'):
            out[k] = None
    else:
        held = {id(v) for v in p.clause.x_columns.values()}
        for v in body.variables.values():
            occ = v.occurrences
            if not occ or any(not (o.binds and not o.key and o.atom is not None) for o in occ):
                continue
            src = _src(occ[0])
            if src == 'perp.A2' and id(v) in held:
                continue  # X holds it, so a later clause can read it
            if src == 'port:box.B':
                out['unread_box_B'] += 1
            elif src == 'perp.A2':
                out['unread_perp_A2'] += 1
            elif src == 'port:cell.P_outer':
                out['unread_cell_P_outer'] += 1
    if not _before_scope(p):
        out['before_nonstrict'] = out['before_inverted'] = None
        return out
    nonstrict = inverted = 0
    heads = {h.column: h.label for h in body.head if h.field is None and h.label}
    c = p.clause
    graph = [a for s in ([c.key] if c.key is not None and c.key is not body else []) + [s for s in c.before
                                                                                       if s is not c.key] + [body]
             for a in s.atoms]
    skip = {id(a) for a in graph if a.relation == 'margin'}
    for cmp, op, m1, m2 in _margin_k_comparisons(body):
        nonstrict += op != '<'
        s1, s2 = _sites(m1), _sites(m2)
        b1, b2 = s1.get('B'), s2.get('B')
        if 'a' not in heads or 'b' not in heads or b1 is None or b2 is None or not b1.joins or not b2.joins:
            continue
        da1, db1 = (_graph_distance(graph, heads[k], b1.label, skip) for k in ('a', 'b'))
        da2, db2 = (_graph_distance(graph, heads[k], b2.label, skip) for k in ('a', 'b'))
        aligned = da1 <= db1 and db2 <= da2 and (da1 < db1 or db2 < da2)
        reversed_ = db1 <= da1 and da2 <= db2 and (db1 < da1 or da2 < db2)
        inverted += (op == '<' and reversed_) or (op in ('>', '>=') and aligned)
    out['before_nonstrict'], out['before_inverted'] = nonstrict, inverted
    return out


# ------------------------------------------------------------------------------------------------ box algebra

def _instances(p):
    """{instance relation: component} of the INIT clauses before the point and of the candidate's clause."""
    out = {c.relation: c.component for c in p.clauses_before() if c.keyword == 'INIT' and c.relation}
    c = p.clause
    if c.keyword == 'INIT' and c.relation:
        out[c.relation] = c.component
    return out


@feature
def q3e_box_algebra(p):
    """Q3e Box algebra. `reflection_A_not_diagonal`: `reflection` whose A label is of the cardinal type Axis (the
    library's `diag_axis_of` makes DiagAxis). `relative_base_position_x_not_position`: `relative` whose Base label is
    a Position and whose X label is not. `apply_P_from_bbox_box`: `apply` whose P label is made by the `box` port of a
    BoundingBox instance.

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    out = C.Counter({'reflection_A_not_diagonal': 0, 'relative_base_position_x_not_position': 0, 'apply_P_from_bbox_box': 0})
    inst = None
    for a in body.atoms:
        if not _library(a):
            continue
        sites = _sites(a)
        if a.relation == 'reflection':
            x = sites.get('A')
            out['reflection_A_not_diagonal'] += bool(x is not None and x.joins and _ltype(x) == 'Axis')
        elif a.relation == 'relative':
            base, x = sites.get('Base'), sites.get('X')
            if base is not None and x is not None and base.joins and x.joins:
                tb, tx = base.resolved_type, x.resolved_type
                out['relative_base_position_x_not_position'] += bool(tb == 'Position' and tx is not None and tx != 'Position')
        elif a.relation == 'apply':
            x = sites.get('P')
            b = _binder(x) if x is not None and x.joins else None
            if b is not None and _port(b.atom) == 'box':
                if inst is None:
                    inst = _instances(p)
                out['apply_P_from_bbox_box'] += inst.get(b.atom.relation.rsplit('.', 1)[0]) == 'BoundingBox'
    return dict(out)


# ------------------------------------------------------------------------------------------------ table reads

@feature
def q3f_table_reads(p):
    """Q3f Reads of declared tables and the input. `zero_nonnumber`: a declared-table or `input` atom with the literal 0
    at a column whose type is known and is not Number. `contra`: atoms that read a relation or table with the labels of
    another atom in the same or an enclosing branch, one of the two below NOT (the pair cannot both hold).

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    zero = 0
    for a in body.atoms:
        if a.operator is None and (_declared(a) or a.relation == 'input'):
            zero += any(x.is_zero and x.column_type not in (None, 'Number') for x in a.arguments)
    reads = [a for a in body.atoms if a.operator is None and a.kind in ('table', 'clause', 'fact', 'port', 'output')]
    contra = 0
    for a in reads:
        ka = a.key()[1:]
        if any(b.negated != a.negated and b.key()[1:] == ka and _related(a, b) for b in reads):
            contra += 1
    return {'zero_nonnumber': zero, 'contra': contra}


# ------------------------------------------------------------------------------------------------ components

@feature
def q3g_components(p):
    """Q3g Component ports. `port_walk_field_arg`: an atom that reads the `walk` port with a field argument at p or p0
    (a record in a site that takes a position). `order_before_op`: in the `before` port of Order, comparisons whose
    operator is neither `<` nor `!=` (None outside that port). `ray_end_misaligned_join`: an atom that reads the `ray`
    or `end` port with a label that the `ray` or `end` port makes at a column of another name.

    Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    walk = misaligned = 0
    for a in body.atoms:
        port = _port(a)
        if port == 'walk':
            walk += any(x.column in ('p', 'p0') and x.field is not None for x in a.arguments)
        elif port in ('ray', 'end'):
            for x in a.arguments:
                b = _binder(x) if x.joins and x.field is None else None
                if b is not None and b.field is None and _port(b.atom) in ('ray', 'end') and b.column != x.column:
                    misaligned += 1
                    break
    before = None
    if _before_scope(p):
        before = sum(1 for a in body.comparisons if _op(a) not in ('<', '!='))
    return {'port_walk_field_arg': walk, 'order_before_op': before, 'ray_end_misaligned_join': misaligned}


# ------------------------------------------------------------------------------------------------ deletes

@feature
def q3h_orphan(p):
    """Q3h Orphan labels. `orphan_label`: labels that the clause makes (`*L`) and that no site reads (no plain or `^`
    site, no head site), that are not made inside a record (a key field) and that X does not hold as a column. None
    except in a Rule clause.

    Needs: partial. Monotone: no.
    """
    body = _body(p)
    if body is None or p.kind != 'Rule':
        return None
    held = {id(v) for v in p.clause.x_columns.values()}
    n = 0
    for v in body.variables.values():
        occ = v.occurrences
        if occ and id(v) not in held and all(o.binds and not o.key and o.atom is not None and o.field is None
                                             for o in occ):
            n += 1
    return {'orphan_label': n}
