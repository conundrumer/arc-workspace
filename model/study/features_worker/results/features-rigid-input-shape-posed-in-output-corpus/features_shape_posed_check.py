"""Checks of features_shape_posed.py on hand-made grids, each with a known reading."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
src = open(HERE + 'features_shape_posed.py').read().rsplit('\nmain()\n', 1)[0]
mod = {'__file__': HERE + 'features_shape_posed.py', '__name__': 'fp'}
exec(compile(src, 'features_shape_posed.py', 'exec'), mod)
FORMS, build, read, ev, whole = mod['FORMS'], mod['build_input'], mod['read_outputs'], mod['evaluate'], mod['whole_flag']
need = {(f['kind'], f['col']) for f in FORMS.values()}
emb = sorted({(f['kind'], f['col']) for f in FORMS.values() if f['match'] == 'embed'})


def run(train, tests=()):
    tabs, maps, _ = build(train, list(tests), need)
    recs, _ = read(train, [o for _, o in train], tabs, maps, emb)
    return {k: ev(v, tabs, recs, len(train)) for k, v in FORMS.items()}


def blank(h=8, w=8):
    return [[0] * w for _ in range(h)]


def draw(g, cells, col, at=(0, 0)):
    for r, c in cells:
        g[r + at[0]][c + at[1]] = col
    return g


L = [(0, 0), (1, 0), (2, 0), (2, 1)]
L_turned = [(0, 0), (0, 1), (0, 2), (1, 0)]
checks = []
# A turned copy at a pose the input lacks, on empty cells.
r = run([(draw(blank(), L, 3), draw(blank(), L_turned, 3, (5, 4)))])
checks += [('turned: base hit', r['base'][0] == 1), ('turned: same off', r['base'][1] == 0), ('turned: chg hit', r['chg'][0] == 1), ('turned: size 6 off', r['size6'][0] == 0)]
# A shape that stays put is the same-pose reading.
g = draw(blank(), L, 3)
r = run([(g, [x[:] for x in g])])
checks += [('stayed: base off', r['base'][0] == 0), ('stayed: same on', r['base'][1] == 1), ('stayed: chg same off', r['chg'][1] == 0)]
# A translated copy at the same pose: same on, also with chg.
r = run([(draw(blank(), L, 3), draw(blank(), L, 3, (4, 4)))])
checks += [('moved: same on', r['chg'][1] == 1), ('moved: base off', r['base'][0] == 0)]
# A recolored turned copy hits only with color free.
r = run([(draw(blank(), L, 3), draw(blank(), L_turned, 5, (5, 4)))])
checks += [('recolor: same off', r['base'][0] == 0), ('recolor: free on', r['free'][0] == 1)]
# Two poses in the input, both kept: other hits, new doesn't.
g = draw(draw(blank(), L, 3), L_turned, 3, (5, 4))
r = run([(g, [x[:] for x in g])])
checks += [('kept two: other on', r['other'][0] == 1), ('kept two: new off', r['base'][0] == 0), ('kept two: other-chg off', r['other-chg'][0] == 0)]
# A pose in a test input closes the task scope, and the pair scope still hits.
r = run([(draw(blank(), L, 3), draw(blank(), L_turned, 3, (5, 4)))], [draw(blank(), L_turned, 3)])
checks += [('test input: pair on', r['base'][0] == 1), ('test input: task off', r['task'][0] == 0)]
# Across: the source stands only in the other pair's input.
r = run([(draw(blank(), L, 3), blank()), (draw(blank(), [(0, 0)], 4), draw(blank(), L_turned, 3, (5, 4)))])
checks += [('across on', r['across'][0] == 1), ('across: pair off', r['base'][0] == 0)]
# Embed finds a copy that touches other cells of the same color.
o = draw(draw(blank(), L_turned, 3, (5, 4)), [(4, 4), (3, 4)], 3)
r = run([(draw(blank(), L, 3), o)])
checks += [('touching: comp off', r['base'][0] == 0), ('touching: embed on', r['embed'][0] == 1)]
# A window of two separate parts.
P = [(0, 0), (0, 1), (2, 0), (2, 2)]
Q = [(a, 2 - b) for a, b in P]
r = run([(draw(blank(), P, 3), draw(blank(), Q, 3, (4, 4)))])
checks += [('window on', r['win'][0] == 1)]
# Whole-grid images.
g = draw(blank(4, 4), L, 3)
gf = [row[::-1] for row in g]
checks += [('whole is', whole([(g, gf)])[0] == 1), ('whole holds', whole([(g, [a + b for a, b in zip(g, gf)])])[1] == 1), ('whole off', whole([(g, g)]) == (0, 0))]
bad = [n for n, ok in checks if not ok]
print(len(checks), 'checks,', len(bad), 'failed', bad)
sys.exit(bool(bad))
