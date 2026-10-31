"""Round 1, E8 for input-frame positions: X's paint against the train output, for X's computed Position columns with frame tag `input`.

A Position column counts as computed when no positive read of a table or fact in the candidate's form holds its label:
a library relation or macro makes its values.

This reads an input-frame position in the output grid, which assumes the two grids share coordinates;
equal sizes do not establish that. Only examples whose input and output grids have the same size count.
"""
from featlib import feature

READS = ('table', 'fact', 'port', 'output', 'clause')


def _computed(p):
    """Names of X's columns whose label no positive read of a table or fact holds."""
    out = set()
    for name, v in p.clause.x_columns.items():
        if not any(a.atom is not None and a.atom.operator is None and not a.atom.negated and a.atom.kind in READS
                   for a in v.occurrences):
            out.add(name)
    return out


@feature
def e8_paint_input_frame(p):
    """E8 (input-frame variant): precision of X rows against the train output, and coverage of the output grid's cells.

    A row whose position lies off the grid (a negative margin, or margins that do not add up to the grid's size) paints nothing and counts in the precision's denominator. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    computed = _computed(p)
    cols = x.columns()
    pos = [c.index for c in cols if c.type == 'Position' and c.frame == 'input' and c.name in computed]
    col = [c.index for c in cols if c.type == 'Color']
    if not pos or not col:
        return None
    examples = {e.index: e for e in p.examples()}
    rows_of = x.examples(decoded=False)
    best = None
    for pi in pos:
        for ci in col:
            rows = right = cells = painted = 0
            for (_, ex), models in rows_of.items():
                e = examples.get(ex)
                if e is None or not e.same_size:
                    continue
                grid = e.output.cells
                h, w = e.output.size
                cells += h * w
                hit = set()
                for model in models:
                    for row in model:
                        v = row[pi]
                        if len(v) != 4:
                            continue
                        rows += 1
                        t, b, l, r = v
                        if min(v) < 0 or t + b != h - 1 or l + r != w - 1:
                            continue
                        if grid[t][l] == row[ci][0]:
                            right += 1
                            hit.add((t, l))
                painted += len(hit)
            if cells:
                cand = (painted / cells, right / rows if rows else 0.0)
                if best is None or cand > best:
                    best = cand
    if best is None:
        return None
    return {'coverage': best[0], 'precision': best[1]}
