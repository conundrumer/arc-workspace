"""Model input layer: functional dependencies. One attribute of an item may determine another: a column another column, a cell's place, or a group's property, the output's color there or whether the
output changes it. Each feature asks whether such a function exists, so it keeps its value under the symmetries of the square and a permutation of the colors. A dependency over the examples uses only
what does not depend on which corner of a grid its places count from.
"""
from grammar import ABSENT, INPUT, OUTPUT, GRIDS, Var, operator
from vocabulary import *  # noqa: F401,F403
from vocabulary import ALL_EXAMPLES_STAGE, BASE_STAGE, GRID_STAGE, GROUPS, MAX_CELLS, MAX_GROUPS, MAX_ROWS, OWN_STAGE, POSITION, TABLE_STAGE, TRAIN_EXAMPLES_STAGE

# ---- groups

def group_properties(g_, H, W, F):
    return {'size': len(g_), 'holes': F.enclosed_regions(g_), 'symmetry': F.symmetry_count(g_), 'shape': F.normalized(g_), 'shape up to rotation and reflection': F.canon(g_),
            'touching the edge': any(u[0] in (0, H - 1) or u[1] in (0, W - 1) for u in g_), 'filling its box': F.fills_box(g_)}


@operator(memo=True)
def groups_in_grid(c, e, v, grid, at_least):
    """[(cells, properties)] of the groups of a Position column in the grid: the cells of each group by the table's Ident, Color and key columns."""
    import features as F
    if cells_in_grid(v, grid, at_least)(c, e) is ABSENT:
        return ABSENT
    H, W = c.size(grid)
    groups = c.grouped(e[v])
    if not groups or len(groups) > MAX_GROUPS or sum(len(u) for u in groups.values()) > MAX_CELLS:
        return ABSENT
    cells = [{u for u in g_ if 0 <= u[0] < H and 0 <= u[1] < W} for g_ in groups.values()]
    cells = [g_ for g_ in cells if g_]
    if len(cells) < at_least or not cells:
        return ABSENT
    return [(g_, group_properties(g_, H, W, F)) for g_ in cells]


@operator
def group_property(c, e, group, name):
    return group[1][name]


@operator
def unique_label(c, e, group, grid):
    g_ = c.array(grid)
    held = {g_[r][k] for r, k in group[0]}
    return next(iter(held)) if len(held) == 1 else ABSENT


@operator(reads=('input', 'output'))
def contains_changed_cell(c, e, group):
    if not c.same():
        return ABSENT
    return any(c.gi[r][k] != c.go[r][k] for r, k in group[0])


# ---- one attribute of an item determines another

CELL_PARTITIONS = {'its row or column': lambda s: (row_of(), column_of()), 'its diagonal': lambda s: (main_diagonal(), anti_diagonal()), 'its distance from the grid border': lambda s: (border_distance(s),),
          'its coordinate parity': lambda s: (coordinate_parity(),)}
INPUT_CELL_PARTITIONS = {'its neighbor colors': neighbor_color_multiset(INPUT), 'its color and its same-color neighbor count': same_color_neighbor_count(INPUT)}
GROUP_PROPERTIES = ('size', 'holes', 'symmetry', 'shape', 'shape up to rotation and reflection', 'touching the edge', 'filling its box')
GROUP_DETERMINES = '{p} groups of %s their %%s determines %%s' % GROUPS
MAX_ROWS_PER_EXAMPLE = 2000  # the rows at one example up to which a feature over a table's examples reads each row


def declare_dependencies():
    TABLE_STAGE.define('{a} determines {b}', determines(rows_if_any(), column_value(a), column_value(b)), a=columns(), b=other_than(a))
    for grid, stage in ((OUTPUT, GRID_STAGE), (INPUT, OWN_STAGE)):
        cells2 = cells_in_grid(p, grid, 2)
        for name, ways in CELL_PARTITIONS.items():
            stage.define('{p} %s determines the %s color' % (name, grid), disjunction(*[determines(cells2, way, grid_label_of_cell(grid)) for way in ways(grid)]), p=POSITION)
    for grid, stage in ((OUTPUT, GRID_STAGE), (INPUT, BASE_STAGE)):
        stage.define('{p},{x} determines the %s color' % grid, determines(rows_if_several(), column_value(x), grid_label_of_row(p, grid)), p=cell_columns(grid), x=other_than(p))
        stage.define('{p},{x} is determined by the %s color' % grid, determines(rows_if_several(), grid_label_of_row(p, grid), column_value(x)), p=cell_columns(grid), x=other_than(p))
    for name, way in INPUT_CELL_PARTITIONS.items():
        GRID_STAGE.define('{p} %s determines the output color' % name, guarded(grids_same_size(), determines(cells_in_grid(p, OUTPUT, 2), way, grid_label_of_cell(OUTPUT))), p=POSITION)
        TRAIN_EXAMPLES_STAGE.define('{p} %s determines the output color across the examples' % name, guarded(all_grids_same_size(MAX_ROWS, False), over_examples(determines(cells_in_grid(p, OUTPUT, 1), way, grid_label_of_cell(OUTPUT)), MAX_ROWS, False)), p=POSITION)
    TRAIN_EXAMPLES_STAGE.define('{p} its distance from the grid border determines the output color across the examples', over_examples(determines(cells_in_grid(p, OUTPUT, 1), border_distance(OUTPUT), grid_label_of_cell(OUTPUT)), MAX_ROWS, False), p=POSITION)
    for name in GROUP_PROPERTIES:
        GRID_STAGE.define(GROUP_DETERMINES % (name, 'their output color'), determines(groups_in_grid(p, OUTPUT, 2), group_property(name), unique_label(OUTPUT), 'defined'), p=POSITION)
        GRID_STAGE.define(GROUP_DETERMINES % (name, 'whether they change'), guarded(grids_same_size(), determines(groups_in_grid(p, OUTPUT, 2), group_property(name), contains_changed_cell(), 'varied')), p=POSITION)
        TRAIN_EXAMPLES_STAGE.define(GROUP_DETERMINES % (name, 'their output color across the examples'), over_examples(determines(groups_in_grid(p, OUTPUT, 1), group_property(name), unique_label(OUTPUT), 'defined', 'two'), MAX_ROWS, False), p=POSITION)
        TRAIN_EXAMPLES_STAGE.define(GROUP_DETERMINES % (name, 'whether they change across the examples'), over_examples(determines(groups_in_grid(p, OUTPUT, 1), group_property(name), contains_changed_cell(), 'defined', 'varied', 'two'), MAX_ROWS, False), p=POSITION)
    # a value at a row's cell, and what the output does there, in a grid of the output's size
    rows2 = rows_in_grid(p, INPUT, 2)
    GRID_STAGE.define('{p} its Moore neighborhood determines the output color', guarded(grids_same_size(), determines(rows2, neighborhood_of_row(p, INPUT), grid_label_of_row(p, OUTPUT))), p=POSITION)
    GRID_STAGE.define('{p},{x} determines which cells change', guarded(grids_same_size(), determines(rows2, column_value(x), is_changed(p))), p=POSITION, x=other_than(p))
    GRID_STAGE.define('{p},{x} with the input color determines the output color', guarded(grids_same_size(), determines(rows2, pair(column_value(x), grid_label_of_row(p, INPUT)), grid_label_of_row(p, OUTPUT))), p=POSITION, x=other_than(p))
    # over the examples
    ALL_EXAMPLES_STAGE.define('{a} determines {b} across the examples', over_examples(determines(rows(), column_value(a), column_value(b)), MAX_ROWS_PER_EXAMPLE, True, False), a=columns(VALUE), b=other_than(a, VALUE))
    rows1 = rows_in_grid(p, OUTPUT, 1)
    TRAIN_EXAMPLES_STAGE.define('{p} its Moore neighborhood determines the output color across the examples', guarded(all_grids_same_size(MAX_ROWS_PER_EXAMPLE, True), over_examples(determines(rows1, neighborhood_of_row(p, INPUT), grid_label_of_row(p, OUTPUT)), MAX_ROWS_PER_EXAMPLE, True)), p=POSITION)
    TRAIN_EXAMPLES_STAGE.define('{p},{x} determines the output color across the examples', over_examples(determines(rows1, column_value(x), grid_label_of_row(p, OUTPUT)), MAX_ROWS_PER_EXAMPLE, True), p=POSITION, x=other_than(p, VALUE))
    TRAIN_EXAMPLES_STAGE.define('{p},{x} is determined by the output color across the examples', over_examples(determines(rows1, grid_label_of_row(p, OUTPUT), column_value(x)), MAX_ROWS_PER_EXAMPLE, True), p=POSITION, x=other_than(p, VALUE))
    TRAIN_EXAMPLES_STAGE.define('{p},{x} with the input color determines the output color across the examples', guarded(all_grids_same_size(MAX_ROWS_PER_EXAMPLE, True), over_examples(determines(rows1, pair(column_value(x), grid_label_of_row(p, INPUT)), grid_label_of_row(p, OUTPUT)), MAX_ROWS_PER_EXAMPLE, True)), p=POSITION, x=other_than(p, VALUE))


declare_dependencies()
