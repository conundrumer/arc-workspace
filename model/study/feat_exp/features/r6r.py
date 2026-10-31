"""Round 6, explorer R: what the search can see of a DET table, which fits the train outputs whatever its rows are.

R1: a Box column in a relation-site frame (a shape relative to a box) placed on the boxes of an earlier table, against the
    colors of the train input under it.
"""
import collections as C
import math

from featlib import BOX_TYPES, feature

MAX_WORK = 400000       # placements x cells that one column may cost
MAX_TABLE_ROWS = 20000  # an earlier table with more rows is not an anchor source


def _first_models(table):
    """{(assignment, example): rows of the table's first model}; rows are decoded tuples."""
    return {k: ms[0] for k, ms in table.examples().items() if ms}


def _anchor_columns(p, grids):
    """[(table name, column name, {(assignment, example): {(h, w): [(top, left)]}})] over the Box columns of the earlier tables whose
    frame is an input and whose cells all have the resolved extent of that example's input; (h, w) is the box's size."""
    out = []
    for t in p.available():
        if sum(len(e['rows']) for e in t.entries) > MAX_TABLE_ROWS:
            continue
        cols = [(i, c) for i, c in enumerate(t.columns()) if c.type == 'Box' and c.frame_kind == 'input']
        if not cols:
            continue
        rows = _first_models(t)
        for i, c in cols:
            per = {}
            ok = True
            for (a, e), rs in rows.items():
                g = grids.get(e)
                if g is None:
                    continue
                g = g.input
                sizes = C.defaultdict(set)
                for r in rs:
                    b = r[i]
                    if getattr(b, 'size', None) != g.size:
                        ok = False
                        break
                    sizes[(g.height - b.top - b.bottom, g.width - b.left - b.right)].add((b.top, b.left))
                if not ok:
                    break
                per[(a, e)] = {s: sorted(v) for s, v in sizes.items()}
            if ok and per:
                out.append((t.name, c.name, per))
    return out


def _x_site_columns(x):
    return [(i, c) for i, c in enumerate(x.columns()) if c.type in BOX_TYPES and c.frame_kind == 'site']


def _relative_columns(p):
    """The indices of the X columns whose label a `relative` atom makes at its X_rel site: the cell in the base's frame,
    which lies outside that frame wherever it is not in the base (the library gives it the size of the frame of X)."""
    return {v.column.index for v in p.clause.x_columns.values()
            if v is not None and v.column is not None and any(
                a.atom is not None and a.atom.relation == 'relative' and a.column == 'X_rel' for a in v.binders)}


def _entropy(counts):
    n = sum(counts)
    return -sum(c / n * math.log2(c / n) for c in counts if c) if n else 0.0


@feature
def r1_template_placement(p):
    """R1: for each Box or Position column of X in a relation-site frame whose cells have a resolved extent (h, w), and each Box
    column of an earlier table in an input frame, place X's cells on every box of size (h, w) that earlier column holds at each
    example (a box that reaches past the train input counts its cells on the input only). In the cells of those boxes, `mi` is the share of the entropy of the train input's color that the cell being placed
    explains (mutual information of placed and color over their entropy; 0 when all cells or no cell is placed, 1 when
    the placed cells hold colors that no other cell holds); `pure` is the share of placed cells, box by box, that hold the most common color among the placed cells of their box; `bad` the share of those columns' cells that lie outside their frame, leaving out the columns that a `relative` atom makes at X_rel (`bad_relative` is that share for those, which lie outside their frame by design; `bad` is absent where all the columns are such); `whole` the share of X's rows that are
    the whole frame (all margins 0). `mi` and `pure` are those of the earlier column with the largest `mi`. `anchored` is 1 when
    some column gives a placement and 0 when X has such a column and no earlier box has its size. None when X has no such column. At a Det point only `whole`, `bad` and `bad_relative` are given: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so the placement keys would compare a row with another example's grid."""
    x = p.x
    cols = _x_site_columns(x)
    if not cols:
        return None
    grids = {e.index: e for e in p.examples()}
    xrows = _first_models(x)
    total = bad = whole = rel_total = rel_bad = 0
    relative = _relative_columns(p)
    for i, _ in cols:
        for rs in xrows.values():
            for r in rs:
                v = r[i]
                if v.size is None:
                    continue
                h, w = v.size
                total += 1
                out_of_frame = min(v.margins) < 0 or v.top + v.bottom > h - 1 or v.left + v.right > w - 1
                if i in relative:
                    rel_total += 1
                    rel_bad += out_of_frame
                else:
                    bad += out_of_frame
                whole += v.margins == (0, 0, 0, 0)
    if not total:
        return None
    best = None
    for _, _, per in (_anchor_columns(p, grids) if p.kind != 'Det' else ()):
        for i, _ in cols:
            sum_h = sum_i = pure_n = pure_d = 0.0
            work = 0
            used = 0
            for (a, e), rs in xrows.items():
                g = grids.get(e)
                if g is None or (a, e) not in per:
                    continue
                grid = g.input
                by_size = C.defaultdict(set)
                for r in rs:
                    v = r[i]
                    if v.size is not None and min(v.margins) >= 0 and v.top + v.bottom <= v.size[0] - 1 \
                            and v.left + v.right <= v.size[1] - 1:
                        by_size[v.size].add(v.margins)
                for (h, w), ms in by_size.items():
                    boxes = per[(a, e)].get((h, w))
                    if not boxes:
                        continue
                    work += len(boxes) * h * w
                    if work > MAX_WORK:
                        break
                    inside = set()
                    for t, b, l, r in ms:
                        inside.update((i2, j2) for i2 in range(t, h - b) for j2 in range(l, w - r))
                    for bt, bl in boxes:
                        cnt = C.Counter()
                        for i2 in range(max(0, -bt), min(h, grid.height - bt)):
                            for j2 in range(max(0, -bl), min(w, grid.width - bl)):
                                cnt[(i2, j2) in inside, grid.cells[bt + i2][bl + j2]] += 1
                        if not cnt:
                            continue
                        used += 1
                        by_color = C.Counter()
                        by_placed = C.Counter()
                        for (pl, col), k in cnt.items():
                            by_color[col] += k
                            by_placed[pl] += k
                        n = sum(cnt.values())
                        hc = _entropy(list(by_color.values()))
                        sum_h += n * hc
                        sum_i += n * (hc + _entropy(list(by_placed.values())) - _entropy(list(cnt.values())))
                        placed = [k for (pl, _), k in cnt.items() if pl]
                        if placed:
                            pure_n += max(placed)
                            pure_d += sum(placed)
                if work > MAX_WORK:
                    break
            if work > MAX_WORK or not used or sum_h <= 0:
                continue
            mi = sum_i / sum_h
            if best is None or mi > best[0]:
                best = (mi, pure_n / pure_d if pure_d else 0.0)
    out = dict(whole=whole / total)
    if total > rel_total:
        out['bad'] = bad / (total - rel_total)
    if rel_total:
        out['bad_relative'] = rel_bad / rel_total
    if p.kind == 'Det':
        return out
    if best is None:
        out['anchored'] = 0.0
        return out
    out.update(anchored=1.0, mi=best[0], pure=best[1])
    return out


@feature
def r2_example_variation(p):
    """R2: for X with an Example column, the per-example slices of its rows (the columns other than Example, per assignment and
    example). `variation` is the number of distinct slices over the number of examples with a slice, `fill` the mean over
    examples of a slice's rows over the rows of all slices together (1 when every example holds every row), `same_all` is 1
    when every slice is the same set and there are at least 2 examples. None when X has no Example column or one example."""
    x = p.x
    cols = x.columns()
    ex = [i for i, c in enumerate(cols) if c.type == 'Example']
    if not ex or len(ex) == len(cols):
        return None
    rest = [i for i in range(len(cols)) if i not in ex]
    out = []
    for a in {k[0] for k in x.examples()}:
        slices = []
        for (a2, e), ms in x.examples().items():
            if a2 != a or not ms:
                continue
            slices.append(frozenset(tuple(r[i] for i in rest) for r in ms[0] if all(r[j] == e for j in ex)))
        if len(slices) < 2:
            continue
        union = frozenset().union(*slices)
        if not union:
            continue
        out.append((len(set(slices)) / len(slices), sum(len(s) for s in slices) / (len(slices) * len(union)),
                    float(len(set(slices)) == 1)))
    if not out:
        return None
    n = len(out)
    return dict(variation=sum(o[0] for o in out) / n, fill=sum(o[1] for o in out) / n, same_all=sum(o[2] for o in out) / n)
