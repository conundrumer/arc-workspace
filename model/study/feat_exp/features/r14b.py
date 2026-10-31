"""Round 14, explorer b: the box algebra (box.dl). Tests of how a library relation of that area is used, read from the
columns of X that the relation's atom binds or reads, against the train grids.

Each feature covers the positive atoms of the candidate's body that read one relation or a cluster of relations used
together, and is None for a candidate whose body has no such atom (or where the atom's columns are not columns of X).
A value averages over the atoms and over the train examples in which X has rows (the rows of the first model).

B1 neighbor and jump: the cell the step reaches.
B2 relative: the cell lies in the base box.
B3 inside and interior: the boxes that hold the cells overlap.
B5 split: the bands (row or column) that the split gives.
B6 dist_pair and diag_dist: the two distances are ordered.
B7 step_offset, jump_offset, apply_dir, apply_dir8, apply_diag_dir, diag_dist, corner_dist: X holds cells.
B8 compose: the box C lies in its frame.
B9 apply: the transform is not free.

`option_features` is not a feature: it scores the options of a relation-choice row (see explorer-b.md).
"""
import collections as C

from featlib import feature

MAX_ROWS = 6000   # rows of one example read; a larger example is cut to its first rows
DOMAIN = {'Dir': 4, 'DiagDir': 4, 'Dir8': 8, 'Axis': 2, 'D4': 8}


# ------------------------------------------------------------------------------------------------ helpers

def _atoms(p, rels):
    """The positive atoms of the candidate's body that read one of the relations."""
    body = p.clause.body if p.clause is not None else None
    if body is None:
        return []
    return [a for a in body.atoms if a.relation in rels and not a.negated and a.interface is not None]


def _col(atom, name):
    """The X column that the atom's site `name` holds (a label of the candidate that is a column of X), or None."""
    for g in atom.arguments:
        if g.name == name and g.label is not None and g.variable is not None:
            c = g.variable.column
            if c is not None and c.index is not None:
                return c
    return None


def _rows(p):
    """{example: rows of the first model}, rows as tuples of decoded values; an example without rows is left out."""
    x = p.x
    cache = x.__dict__.setdefault('_r14b_rows', {})
    if 'rows' not in cache:
        out = {}
        for (_, e), models in x.examples().items():
            if models and models[0]:
                out.setdefault(e, []).extend(models[0][:MAX_ROWS])
        cache['rows'] = out
    return cache['rows']


def _background(grid):
    return min(grid.most_common())


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _merge(parts):
    """The mean of each key over a list of {key: value} dicts; None if there is no key."""
    acc = C.defaultdict(list)
    for d in parts:
        for k, v in d.items():
            if v is not None:
                acc[k].append(v)
    out = {k: sum(v) / len(v) for k, v in acc.items()}
    return out or None


def _safe(fn):
    """A feature function that returns None where its body raises."""
    import functools

    @functools.wraps(fn)
    def run(p):
        try:
            return fn(p)
        except Exception:
            return None
    return run


def _is_margin(v):
    return hasattr(v, 'margins')


# ------------------------------------------------------------------------------------------------ B1

MOVE_SITES = {'neighbor': ('P', 'Q'), 'jump': ('P', 'Q'), 'compose': ('A', 'C'), 'apply': ('P', 'P_out')}


def _step(p, atom):
    src_name, dst_name = MOVE_SITES[atom.relation]
    q, src = _col(atom, dst_name), _col(atom, src_name)
    if q is None or q.type not in ('Position', 'Box'):
        return {}
    rows = _rows(p)
    examples = p.examples()
    tot = inn = 0
    fans, chg, cells = [], 0, 0
    tag = q.frame_kind if q.frame_kind in ('input', 'output') else None
    for e, rs in rows.items():
        for r in rs:
            m = r[q.index]
            if _is_margin(m) and m.size is not None:
                tot += 1
                inn += bool(m.in_frame())
        if src is not None:
            pairs = {(r[src.index], r[q.index]) for r in rs}
            starts = {r[src.index] for r in rs}
            if starts:
                fans.append(len(pairs) / len(starts))
        if tag and e < len(examples) and examples[e].same_size:
            ch = examples[e].changed()
            qs = {r[q.index].cell for r in rs if _is_margin(r[q.index]) and r[q.index].in_frame()}
            if ch is not None and qs:
                cells += len(qs)
                chg += len(qs & ch)
    out = {'q_in': inn / tot if tot else None, 'fan': _mean(fans), 'q_chg': chg / cells if cells else None}
    if atom.relation == 'compose':
        out.pop('fan')
    if atom.relation == 'apply':
        out.pop('q_in'), out.pop('q_chg')
    return out


@feature
@_safe
def b1_neighbor(p):
    """B1 neighbor and jump: the cell Q the step reaches. `q_in`: the share of Q cells (resolved extent) that lie in their
    frame; `fan`: the mean number of distinct Q cells per distinct start cell P (8 where the direction is free); `q_chg`:
    the share of the distinct Q cells (frame tag input or output, examples of one size) that the task changes."""
    atoms = _atoms(p, {'neighbor', 'jump'})
    if not atoms:
        return None
    return _merge(_step(p, a) for a in atoms)


@feature
@_safe
def b8_compose(p):
    """B8 compose: the box C = A + B placed in the outer frame, a column of X. `q_in`: the share of C values (resolved
    extent) that lie in their frame; `fan`: the mean number of distinct C per distinct A; `q_chg`: the share of the
    distinct C cells (frame tag input or output, examples of one size) that the task changes."""
    atoms = _atoms(p, {'compose'})
    if not atoms:
        return None
    return _merge(_step(p, a) for a in atoms)


@feature
@_safe
def b9_apply(p):
    """B9 apply, the D4 image P_out of a box P: `q_in` the share of images that lie in their frame; `fan` the mean number
    of distinct images per distinct P (8 where the transform is free); `dirs` the distinct transforms D of X per example
    over 8, None where D is not a column of X."""
    atoms = _atoms(p, {'apply'})
    if not atoms:
        return None
    out = [_step(p, a) for a in atoms]
    for a, d in zip(atoms, out):
        dc = _col(a, 'D')
        if dc is not None:
            rows = _rows(p)
            d['dirs'] = _mean(len({r[dc.index] for r in rs}) / DOMAIN['D4'] for rs in rows.values())
    return _merge(out)


ENUM = {'step_offset', 'jump_offset', 'apply_dir', 'apply_dir8', 'apply_diag_dir', 'diag_dist', 'corner_dist'}


@feature
@_safe
def b7_enum(p):
    """B7 step_offset, jump_offset, apply_dir, apply_dir8, apply_diag_dir, diag_dist and corner_dist, which give a number
    or a direction for each value of an enumerated type. `cells`: 1 where X has a column of type Position or Box (not
    Offset), 0 where X holds only enumerated values and numbers."""
    atoms = _atoms(p, ENUM)
    if not atoms:
        return None
    return {'cells': 1.0 if any(c.type in ('Position', 'Box') for c in p.x.columns()) else 0.0}


# ------------------------------------------------------------------------------------------------ B2

def _relative(p, atom):
    rel, base, cell = _col(atom, 'X_rel'), _col(atom, 'Base'), _col(atom, 'X')
    if rel is None or base is None or cell is None or base.type != 'Box' or cell.type != 'Position':
        return {}   # only a cell read in a box: the offset between two cells has negative margins by construction
    rows = _rows(p)
    neg = tot = 0
    any_neg = []
    for e, rs in rows.items():
        n = 0
        for r in rs:
            m = r[rel.index]
            if _is_margin(m):
                tot += 1
                if min(m.margins) < 0:
                    neg += 1
                    n += 1
        any_neg.append(1.0 if n else 0.0)
    return {'neg': neg / tot if tot else None, 'any_neg': _mean(any_neg) if tot else None}


@feature
@_safe
def b2_relative(p):
    """B2 relative, a cell X read in a base box (Base of type Box, X of type Position, both columns of X). `neg`: the share of
    X_rel values with a negative margin, which is a cell outside its base; `any_neg`: the share of examples with such a
    value."""
    atoms = _atoms(p, {'relative'})
    if not atoms:
        return None
    return _merge(_relative(p, a) for a in atoms)


# ------------------------------------------------------------------------------------------------ B3

def _contain(p, atom):
    a, b = _col(atom, 'A'), _col(atom, 'B')
    if a is None or b is None:
        return {}
    multi, dens, nboxes = [], [], []
    for e, rs in _rows(p).items():
        pairs = {(r[a.index], r[b.index]) for r in rs}
        cells = {u for u, _ in pairs}
        boxes = {v for _, v in pairs}
        if not cells or not boxes:
            continue
        per = C.Counter(u for u, _ in pairs)
        multi.append(sum(1 for v in per.values() if v > 1) / len(per))
        dens.append(len(pairs) / (len(cells) * len(boxes)))
        nboxes.append(len(boxes))
    return {'multi': _mean(multi), 'density': _mean(dens), 'boxes': _mean(nboxes)}


@feature
@_safe
def b3_contain(p):
    """B3 inside and interior: the cells A held by the boxes B, both columns of X. `multi`: the share of cells in two or
    more boxes; `density`: the distinct (cell, box) pairs over cells times boxes; `boxes`: the distinct boxes."""
    atoms = _atoms(p, {'inside', 'interior'})
    if not atoms:
        return None
    return _merge(_contain(p, a) for a in atoms)


# ------------------------------------------------------------------------------------------------ B5

def _bands(p, atom):
    out = []
    examples = p.examples()
    for name in ('Along', 'Across'):
        c = _col(atom, name)
        if c is None or c.type != 'Box' or c.frame_kind not in ('input', 'output'):
            continue
        tot = uni = touch = tot_ch = 0
        for e, rs in _rows(p).items():
            if e >= len(examples):
                continue
            ex = examples[e]
            grid = ex.input if c.frame_kind == 'input' else ex.output
            ch = ex.changed() if ex.same_size else None
            h, w = grid.size
            for m in {r[c.index] for r in rs if _is_margin(r[c.index])}:
                cells = [(x, y) for x, y in (m.cells() or []) if 0 <= x < h and 0 <= y < w]
                if not cells:
                    continue
                tot += 1
                uni += len({grid[x, y] for x, y in cells}) == 1
                if ch is not None:
                    tot_ch += 1
                    touch += any(cell in ch for cell in cells)
        out.append({'uniform': uni / tot if tot else None, 'touch': touch / tot_ch if tot_ch else None})
    return _merge(out) or {}


@feature
@_safe
def b5_split(p):
    """B5 split: the row or column bands (Along and Across, Boxes with perpendicular zeroed) of the cells. `uniform`: the
    share of distinct bands that hold one color in their grid (frame tag input or output); `touch`: the share of bands
    that hold a cell the task changes (examples of one size)."""
    atoms = _atoms(p, {'split'})
    if not atoms:
        return None
    return _merge(_bands(p, a) for a in atoms)


# ------------------------------------------------------------------------------------------------ B6

DIST_SITES = {'dist_pair': ('K', 'K2'), 'diag_dist': ('K1', 'K2')}


def _dist(p, atom):
    n1, n2 = DIST_SITES[atom.relation]
    c1, c2 = _col(atom, n1), _col(atom, n2)
    if c1 is None or c2 is None:
        return {}
    one, tie = [], []
    for e, rs in _rows(p).items():
        lt = sum(1 for r in rs if isinstance(r[c1.index], int) and isinstance(r[c2.index], int) and r[c1.index] < r[c2.index])
        gt = sum(1 for r in rs if isinstance(r[c1.index], int) and isinstance(r[c2.index], int) and r[c1.index] > r[c2.index])
        n = len(rs)
        if n:
            one.append(max(lt, gt) / n)
            tie.append((n - lt - gt) / n)
    return {'one_sided': _mean(one), 'tie': _mean(tie)}


@feature
@_safe
def b6_dist(p):
    """B6 dist_pair and diag_dist: the two distances K and K2 (or K1 and K2), both columns of X. `one_sided`: the larger
    of the shares of rows with K < K2 and K > K2; `tie`: the share of rows with K = K2."""
    atoms = _atoms(p, set(DIST_SITES))
    if not atoms:
        return None
    return _merge(_dist(p, a) for a in atoms)


# ------------------------------------------------------------------------------------------------ relation choice

# The non-enumerable input slots of each relation of box.dl that the sampler's library has, by type: a slot a finite type
# fills by enumeration (Dir, Axis, D4, ...) is not listed. A Number slot is met by a Nat or Int label.
INPUT_SLOTS = {
    'compose': ('Box', 'Box'), 'relative': ('Box', 'Box'), 'inside': ('Box', 'Box'), 'interior': ('Box', 'Box'),
    'dist_pair': ('Box',), 'diag_dist': ('Box',), 'corner_dist': ('Box',), 'split': ('Box',), 'sub_extent': ('Position',),
    'box_extent': ('Box', 'Position'), 'edge_inset': ('Number',), 'axis_inset': ('Number', 'Number'),
    'uniform_inset': ('Number',), 'edge_outset': ('Number',), 'axis_outset': ('Number', 'Number'),
    'uniform_outset': ('Number',), 'jump_offset': ('Number',), 'step_offset': (), 'neighbor': ('Box',),
    'jump': ('Box', 'Number'), 'apply': ('Box',), 'apply_dir': (), 'apply_diag_dir': (), 'apply_dir8': (),
    'same_dist': ('Box', 'Box'), 'same_line': ('Position', 'Position'), 'nearer': ('Position', 'Position'),
    'centered': ('Box',),
}
_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4',
          'Nat': 'Number', 'Int': 'Number'}
# Relations whose atom reads the cell or box that the atom before it relates (a crop's relative position, the second
# distance or the second axis of a pair).
FOLLOWS_INSIDE = ('relative', 'same_dist', 'centered')
FOLLOWS_RELATIVE = ('compose', 'apply', 'centered')
REPEATS = ('neighbor', 'split', 'box_extent', 'nearer', 'same_dist', 'apply', 'dist_pair')


def _sub(a, b):
    while a:
        if a == b:
            return True
        a = _SUPER.get(a)
    return False


def option_features(row, option):
    """Features of one option of a relation-choice row (`relrows`: `scope`, `prefix`, `options`), for the relations that
    INPUT_SLOTS lists; None for any other option. `ready`: every input slot has a label of a fitting type in scope;
    `boxpos`: ready, with a label of type Box and one of type Position in scope; `follows_crop`: the last atom of the prefix
    is `inside` and the option is `relative`, `same_dist` or `centered`; `follows_relative`: the last atom is `relative` and
    the option is `compose`, `apply` or `centered`; `repeat`: the option is the relation of the last atom (a relation of
    REPEATS); `fits_enum`: the last atom enumerates a finite-domain label (an `_elem` relation, `axis_of`, `opposite`,
    `perp`, `diag_dirs`) and a column of the option takes its type."""
    name = option.get('tok')
    if name not in INPUT_SLOTS:
        return None
    scope = row.get('scope') or []
    ready = all(any(_sub(t, slot) for t in scope) for slot in INPUT_SLOTS[name])
    prefix = row.get('prefix') or []
    last = prefix[-1][1:].split(' ')[0].rstrip(')') if prefix and prefix[-1].startswith('(') else None
    out = {'ready': float(ready),
           'boxpos': float(ready and 'Box' in scope and 'Position' in scope),
           'follows_crop': float(last == 'inside' and name in FOLLOWS_INSIDE),
           'follows_relative': float(last == 'relative' and name in FOLLOWS_RELATIVE),
           'repeat': float(last == name and name in REPEATS), 'fits_enum': 0.0}
    if last and (last.endswith('_elem') or last in ('axis_of', 'opposite', 'perp', 'diag_dirs')):
        made = set()
        for o in row.get('options') or []:
            if o.get('tok') == last and o.get('columns'):
                import re
                made = {dict(zip(o['columns'], o['types'])).get(col) for col, _ in re.findall(r'\(:(\w+) \*(\w+)\)', prefix[-1])}
        out['fits_enum'] = float(any(_sub(m, t) for m in made if m for t in option.get('types') or []))
    return out
