"""G19 Frame and extent metadata.

Replaces `r1.e2_off_frame_rows`, `r1.e7_frame_metadata`, `r3f.f3_site_extent_agreement`, `r3f.f5_border_boxes` and
`r6r.r1_template_placement` (`bad`, `whole`). A frame is read from the frame tag of the column, never from a size:
`r7s.s2_frame_size` takes a frame from its size and is left out.
"""
import collections as C

from featlib import feature

CELL_TYPES = ('Position', 'Box')


@feature
def g19_frames(p):
    """G19 Frame and extent metadata, over the Position and Box columns of X. `fields_empty`, `fields_input`,
    `fields_output`, `fields_site`: the columns by frame tag kind. `unresolved` and `unresolved_<kind>`: the share of cells
    whose frame size is unknown. `off_rows` and `off_share`: the rows (and their share) with a cell outside its resolved
    frame (a Position not on a cell of it, a Box not inside it). `size_match`: for cells tagged input or output, the
    share whose resolved frame has the size of that example's grid. `site_agree`: over the columns tagged with a
    relation site (2 or more), the share of rows whose resolved cells all have one frame size, up to swapping height and
    width. `edge3` and `full`: the share of resolved Box cells that touch exactly three and all four sides of their
    frame. None without a Position or Box column. `size_match` is left out at a Det point: X there is the task-level
    body table without its Example column, and every train example's entry holds the rows of all examples, so a
    cell's frame size would be compared with another example's grid.

    Needs: partial. Monotone: no (a filter can drop the rows that are off their frame).
    """
    x = p.x
    cells = [c for c in x.columns() if c.type in CELL_TYPES and c.frame_kind is not None]
    if not cells:
        return None
    kind = {c.index: c.frame_kind or 'empty' for c in cells}
    kind = {i: ('site' if k == 'site' else k) for i, k in kind.items()}
    out = {'fields_' + k: sum(v == k for v in kind.values()) for k in ('empty', 'input', 'output', 'site')}
    sites = [i for i, k in kind.items() if k == 'site']
    exs = {e.index: e for e in p.examples()}
    total = unres = 0
    by_kind = C.defaultdict(lambda: [0, 0])
    rows = off = 0
    size_n = size_ok = 0
    site_rows = site_same = 0
    box_n = three = four = 0
    for (_, ex), models in x.examples().items():
        e = exs.get(ex)
        for model in models:
            for r in model:
                row_off = row_seen = False
                for i, k in kind.items():
                    m = r[i]
                    if not hasattr(m, 'margins'):
                        continue
                    total += 1
                    by_kind[k][0] += 1
                    if m.size is None:
                        unres += 1
                        by_kind[k][1] += 1
                        continue
                    row_seen = True
                    row_off = row_off or not m.in_frame()
                    if e is not None and k in ('input', 'output') and p.kind != 'Det':
                        size_n += 1
                        size_ok += m.size == (e.input if k == 'input' else e.output).size
                    if m.kind == 'Box':
                        z = sum(v == 0 for v in m.margins)
                        box_n += 1
                        three += z == 3
                        four += z == 4
                if row_seen:
                    rows += 1
                    off += row_off
                ext = {tuple(sorted(r[i].size)) for i in sites if hasattr(r[i], 'margins') and r[i].size is not None}
                n_site = sum(1 for i in sites if hasattr(r[i], 'margins') and r[i].size is not None)
                if len(sites) >= 2 and n_site >= 2:
                    site_rows += 1
                    site_same += len(ext) == 1
    if total:
        out['unresolved'] = unres / total
        for k, (n, u) in by_kind.items():
            out['unresolved_' + k] = u / n
    if rows:
        out['off_rows'] = off
        out['off_share'] = off / rows
    if size_n:
        out['size_match'] = size_ok / size_n
    if site_rows:
        out['site_agree'] = site_same / site_rows
    if box_n:
        out['edge3'] = three / box_n
        out['full'] = four / box_n
    return out
