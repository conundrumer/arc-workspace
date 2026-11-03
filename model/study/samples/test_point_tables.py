"""Checks of `point_tables.py`, a feature that is in progress: each hand-made case has values worked out by hand (the comments hold the arithmetic),
and one case replays a small ramp program with the engine.

Run with the kit's python and the engine wheel:
  PYTHONPATH=<site folder>:model/study/samples ARCLOG_IDENT_SOURCE=value scripts/run_heavy.py .venv/bin/python -m pytest -q model/study/samples/test_point_tables.py

Task of the hand-made cases: two train examples (and one test example in `ex_output`, which no value may read), grids of 2 x 2.
  input     ex0 [[1 0] [0 0]]   ex1 [[0 0] [2 0]]
  output    ex0 [[1 3] [0 3]]   ex1 [[0 0] [2 5]]
  O(0) = {(0,0,1) (0,1,3) (1,0,0) (1,1,3)}, D(0) = {(0,1,3) (1,1,3)}        (a cell is (row, column, color))
  O(1) = {(0,0,0) (0,1,0) (1,0,2) (1,1,5)}, D(1) = {(1,1,5)}
"""
import math

import numpy as np
import pytest

pytest.importorskip('arclog')

import point_tables as PT  # noqa: E402
from table_export import At, Entry, ExportTable  # noqa: E402

NAN = float('nan')


def ap(x: float) -> object:
    return pytest.approx(x, abs=1e-6, nan_ok=True)


def pos(r: int, c: int) -> tuple[int, int, int, int]:
    return (r, 1, c, 1)  # a Position is four cells; cells 0 and 2 are the row and the column


def entry(kind: int, index: int, rows: list[tuple], width: int = 0) -> Entry:
    a = np.array(rows, np.int32).reshape(len(rows), -1) if rows else np.zeros((0, width), np.int32)
    return Entry(kind, index, 0, True, len(rows), a, None)


def at(entries: list[Entry], dets: list[tuple[str, str]] | None = None, hash: str | None = None, capped: bool = False, first: float = 0.0) -> At:
    return At(None, hash, capped, [first] + [0.0] * 81, dets or [], entries, [])


def table(labels: list[str], types: list[str], *ats: At) -> ExportTable:
    return ExportTable(0, '', labels, types, list(ats))


def pc(cells: list[tuple[int, int, int]]) -> list[tuple]:
    """The rows (Position, Color) of cells (row, column, color)."""
    return [(*pos(r, c), k) for r, c, k in cells]


GRID = (['P', 'Col'], ['Position', 'Color'])
BASE = {
    'input': table(*GRID, at([entry(1, 0, pc([(0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 1, 0)])), entry(1, 1, pc([(0, 0, 0), (0, 1, 0), (1, 0, 2), (1, 1, 0)])),
                              entry(2, 0, pc([(0, 0, 4)]))])),
    # a native Example column: its cells hold the example index, train first (2 is the test example)
    'ex_output': table(['E', 'P', 'Col'], ['Example', 'Position', 'Color'],
                       at([entry(0, 0, [(0, *pos(0, 0), 1), (0, *pos(0, 1), 3), (0, *pos(1, 0), 0), (0, *pos(1, 1), 3),
                                        (1, *pos(0, 0), 0), (1, *pos(0, 1), 0), (1, *pos(1, 0), 2), (1, *pos(1, 1), 5),
                                        (2, *pos(0, 0), 7)])])),
}

# C: a Position column
CUR = lambda dets=None: table(['P'], ['Position'], at([entry(1, 0, [pos(0, 0), pos(0, 1), pos(1, 0)]), entry(1, 1, [pos(0, 0), pos(1, 0), pos(1, 1)])], dets))  # noqa: E731
# S1: C and a Color column. Example 0 comes as two constraint models that share a row.
S1_E0 = [(0, 0, 1), (0, 0, 2), (0, 1, 3), (1, 1, 3)]
S1_E1 = [(0, 0, 0), (1, 0, 2), (1, 1, 5)]


def s1(dets=None, **kw) -> At:
    return at([entry(1, 0, pc(S1_E0[:2])), entry(1, 0, pc(S1_E0[1:])), entry(1, 1, pc(S1_E1))], dets, **kw)


# S2: S1 with a Nat column, and fewer rows
S2_E0 = [(0, 0, 1, 5), (0, 1, 3, 5)]
S2_E1 = [(0, 0, 0, 1), (1, 1, 5, 1), (0, 1, 9, 1)]


def s2() -> At:
    return at([entry(1, 0, [(*pos(r, c), k, n) for r, c, k, n in S2_E0]), entry(1, 1, [(*pos(r, c), k, n) for r, c, k, n in S2_E1])])


def named(v: np.ndarray) -> dict[str, float]:
    assert v.dtype == np.float32 and v.shape == (len(PT.delta_names()),)
    return dict(zip(PT.delta_names(), map(float, v)))


def same(d: dict[str, float], want: dict[str, float]) -> None:
    for k, x in want.items():
        for a in PT.AGGS:
            assert d[f'delta:{k}:{a}'] == ap(x), (k, a)


# Pair C -> S1.
# Example 0: C has 3 rows, S1 has 4; the rows at (0,0) and (0,1) extend, so kept 2/3 and fanout 4/2. cells(S1) = 4 cells, 3 of them in O(0): recall 3/4,
#   precision 3/4; D(0) is held whole, so changed_recall 1; S1 holds 3 of the 4 positions of O(0).
# Example 1: C has 3 rows, S1 has 3 that extend them all: kept 1, fanout 1; 3 cells, all in O(1): recall 3/4, precision 1; D(1) held; 3 of 4 positions.
# C has no Color column: recall(C) is 0, so the gain is the recall; the precision gain is NaN; C holds no cell, so lost_cells is 0.
def test_added_column_kept_fanout_and_cells():
    d = named(PT.body_delta(CUR(), table(*GRID, s1()), BASE))
    same(d, {
        'rows_cur': (math.log(4) + math.log(4)) / 2, 'rows_succ': (math.log(5) + math.log(4)) / 2,
        'kept': (2 / 3 + 1) / 2, 'lost': (1 / 3 + 0) / 2, 'fanout': (2 + 1) / 2, 'empty': 0,
        'cols_added': 1, 'cols_added:color': 1, 'cols_added:position': 0, 'cols_added:ident': 0, 'cols_added:int': 0, 'cols_added:other': 0,
        'out_recall': 3 / 4, 'out_precision': (3 / 4 + 1) / 2, 'out_recall_gain': 3 / 4, 'out_precision_gain': NAN,
        'changed_recall': 1, 'pos_recall': 3 / 4, 'lost_cells': 0})
    assert d['delta:pairs'] == 1


# Pair S1 -> S2 (S2 adds a Nat column and drops rows).
# Example 0: C = S1 has 4 rows, S2 has 2, both extend a row of C: kept 2/4, fanout 2/2. cells(S2) = {(0,0,1) (0,1,3)}, both in O(0): recall 2/4, precision 1;
#   cells(S1) has recall 3/4, precision 3/4. changed: (0,1,3) of D(0): 1/2. positions: 2 of 4. lost_cells: (1,1,3) is held by S1 and not by S2: 1/4.
# Example 1: S1 has 3 rows, S2 has 3, two of S1's extend: kept 2/3, fanout 3/2. cells(S2) = {(0,0,0) (1,1,5) (0,1,9)}: 2 in O(1): recall 2/4, precision 2/3;
#   cells(S1) has recall 3/4, precision 1. changed 1/1. positions: 3 of 4. lost_cells: (1,0,2) is held by S1 and not by S2: 1/4.
def test_dropped_rows_gains_and_lost_cells():
    d = named(PT.body_delta(table(*GRID, s1()), table(['P', 'Col', 'N'], ['Position', 'Color', 'Nat'], s2()), BASE))
    same(d, {
        'rows_cur': (math.log(5) + math.log(4)) / 2, 'rows_succ': (math.log(3) + math.log(4)) / 2,
        'kept': (2 / 4 + 2 / 3) / 2, 'lost': (2 / 4 + 1 / 3) / 2, 'fanout': (1 + 3 / 2) / 2,
        'cols_added': 1, 'cols_added:int': 1, 'cols_added:color': 0,
        'out_recall': 2 / 4, 'out_precision': (1 + 2 / 3) / 2, 'out_recall_gain': ((2 / 4 - 3 / 4) + (2 / 4 - 3 / 4)) / 2,
        'out_precision_gain': ((1 - 3 / 4) + (2 / 3 - 1)) / 2, 'changed_recall': (1 / 2 + 1) / 2, 'pos_recall': (2 / 4 + 3 / 4) / 2,
        'lost_cells': (1 / 4 + 1 / 4) / 2})


# A successor with more DETs than C: s_a and s_b restrict to C's assignment (slot 3 = v1), so there are two pairs; s_c restricts to v3, which C does not have,
# and makes no pair. s_b has no row: empty 1, kept 0 (no row of C is extended), fanout 0/1; cells(s_b) is empty: recall 0, precision NaN, changed 0, pos 0.
def test_successor_with_more_dets_makes_two_pairs():
    cur = CUR([('slot 3', 'v1')])
    s_a = s1([('slot 3', 'v1'), ('slot 9', 'x1')])
    s_b = at([entry(1, 0, [], 5), entry(1, 1, [], 5)], [('slot 3', 'v1'), ('slot 9', 'x2')])
    s_c = s1([('slot 3', 'v3'), ('slot 9', 'x1')])
    d = named(PT.body_delta(cur, table(*GRID, s_a, s_b, s_c), BASE))
    assert d['delta:pairs'] == 2
    assert d['delta:kept:min'] == ap(0) and d['delta:kept:max'] == ap(5 / 6) and d['delta:kept:mean'] == ap(5 / 12)
    assert d['delta:empty:min'] == ap(0) and d['delta:empty:max'] == ap(1) and d['delta:empty:mean'] == ap(.5)
    assert d['delta:fanout:min'] == ap(0) and d['delta:fanout:max'] == ap(1.5)
    assert d['delta:out_recall:min'] == ap(0) and d['delta:out_recall:max'] == ap(.75)
    assert d['delta:out_precision:min'] == ap(.875) and d['delta:out_precision:max'] == ap(.875)  # the NaN of s_b is left out
    assert d['delta:changed_recall:min'] == ap(0) and d['delta:pos_recall:min'] == ap(0) and d['delta:pos_recall:max'] == ap(.75)
    assert d['delta:rows_succ:min'] == ap(0)


# END: no current table, two output tables. C has no row and no column: kept and lost are NaN, rows_cur is 0, fanout is the row count, every column
# is added, and the gains over cells(C) read recall(C) = 0, which makes the recall gain the recall.
def test_end_with_two_output_tables():
    d = named(PT.body_delta(None, [table(*GRID, s1()), table(['P', 'Col', 'N'], ['Position', 'Color', 'Nat'], s2())], BASE))
    assert d['delta:pairs'] == 2
    for a in PT.AGGS:
        assert math.isnan(d[f'delta:kept:{a}']) and math.isnan(d[f'delta:lost:{a}']) and math.isnan(d[f'delta:out_precision_gain:{a}'])
        assert d[f'delta:rows_cur:{a}'] == 0 and d[f'delta:lost_cells:{a}'] == 0
    assert (d['delta:fanout:min'], d['delta:fanout:mean'], d['delta:fanout:max']) == (ap(2.5), ap(3), ap(3.5))  # S1: (4 + 3) / 2, S2: (2 + 3) / 2
    assert (d['delta:cols_added:min'], d['delta:cols_added:max']) == (ap(2), ap(3))
    assert d['delta:cols_added:int:max'] == ap(1) and d['delta:cols_added:int:min'] == ap(0)
    assert (d['delta:out_recall_gain:min'], d['delta:out_recall_gain:max']) == (ap(.5), ap(.75))
    assert d['delta:out_recall:mean'] == ap(.625)


# A successor with no Color column has no cells: its output columns are NaN, and the others are values.
def test_no_color_column_gives_nan_output_features():
    s3 = at([entry(1, 0, [(*pos(0, 0), 1), (*pos(0, 1), 1)]), entry(1, 1, [(*pos(0, 0), 1)])])
    d = named(PT.body_delta(CUR(), table(['P', 'N'], ['Position', 'Nat'], s3), BASE))
    for k in ('out_recall', 'out_precision', 'out_recall_gain', 'out_precision_gain', 'changed_recall', 'pos_recall', 'lost_cells'):
        for a in PT.AGGS:
            assert math.isnan(d[f'delta:{k}:{a}']), k
    same(d, {'rows_succ': (math.log(3) + math.log(2)) / 2, 'kept': (2 / 3 + 1 / 3) / 2, 'fanout': (1 + 1) / 2, 'cols_added': 1, 'cols_added:int': 1})


def test_state_vector_counts_means_and_best_assignment():
    one = table(['P1', 'P2', 'Col'], ['Position', 'Position', 'Color'],
                at([entry(1, 0, [(*pos(0, 0), *pos(0, 1), 3), (*pos(0, 0), *pos(1, 1), 3)]), entry(1, 1, [(*pos(0, 0), *pos(1, 1), 5)])], hash='h0', first=2.0))
    two = table(*GRID, s1(hash='h1', first=4.0), at([entry(1, 0, pc(S1_E0[1:3])), entry(1, 1, pc(S1_E1))], hash='h2', first=6.0, capped=True))
    v = PT.state_vector([one, two], BASE, ['RULE', 'DET'])
    names = PT.state_names()
    assert v.dtype == np.float32 and v.shape == (len(names),)
    d = dict(zip(names, map(float, v)))
    assert (d['state:tables'], d['state:dets'], d['state:capped'], d['state:differ']) == (2, 1, 1, .5)
    # the first feature is 2 for `one` and 4 and 6 for the assignments of `two`, whose AssignmentVector mean is 5
    first = PT.successor_names()[4].split(':')[1]
    assert d[f'state:{first}:mean:mean'] == ap(3.5) and d[f'state:{first}:mean:max'] == ap(5)
    # `one`: the pair (P1, Col) has recall 0; the pair (P2, Col) has recall (2/4 + 1/4) / 2 = 3/8, precision 1, changed_recall 1.
    # `two`: S1 has recall 3/4, precision 7/8, changed_recall 1; the other assignment has recall (1/4 + 3/4) / 2 = 1/2, so S1 is its best assignment.
    assert d['state:out_recall:max'] == ap(3 / 4) and d['state:out_precision:max'] == ap(7 / 8) and d['state:changed_recall:max'] == ap(1)
    only = PT.state_vector([one], BASE, ['RULE'])
    d1 = dict(zip(names, map(float, only)))
    assert d1['state:out_recall:max'] == ap(3 / 8) and d1['state:out_precision:max'] == ap(1) and d1['state:changed_recall:max'] == ap(1)


def test_successor_vector_is_the_writers_assignment_vector():
    t = table(*GRID, s1(hash='h1', first=4.0), at([entry(1, 0, pc(S1_E0[1:3])), entry(1, 1, pc(S1_E1))], hash='h2', first=6.0))
    v = PT.successor_vector(t, False)
    names = PT.successor_names()
    assert v.dtype == np.float32 and v.shape == (250,) and len(names) == 250 and names[0] == 'succ:count'
    d = dict(zip(names, map(float, v)))
    assert (d['succ:count'], d['succ:capped'], d['succ:distinct'], d['succ:differ']) == (2, 0, 1, 1)
    assert PT.successor_vector(t)[1] == 0 and PT.successor_vector(t, True)[1] == 1


# ---------------------------------------------------------------------- real tables

PROGRAM = ['(DET &r3 D4Domain)', '(RULE &r4 (input (:P *P) (:Col *Col)) (&r3 (:D *D)) (apply (:D D) (:P P) (:P_out *POut)))', '(OUT (&r4 ^P ^Col))']


def real_setup():
    """(the engine's arclog, the kit's M, a session on task 74dd1130, the tables of the program after each model token, the base tables of the probe program)."""
    import pathlib

    import row_store as RS
    from build_tables import sampler_writer
    from table_export import read_export

    w = sampler_writer()
    root = pathlib.Path(__file__).resolve().parents[3]
    arclog = w.arclog
    task = (root / 'data/tasks/74dd1130.json').read_text()
    sess = arclog.Session(arclog.Task.from_json(task, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
    ids, model, _ = arclog.StudyProgram.from_sexp('\n'.join([*RS.PROBE, *PROGRAM]), sess.settings).decode_stream()
    dec, ct, steps = sess.decoder(), None, []
    for t, m in zip(ids, model):
        if m:
            dec.step(int(t))
            ct = arclog.step_tables(dec, 'live', 'live', True, ct, by_assignment=True, rows=True)
            steps.append(read_export(w.M, ct))
    tabs = [x for s in steps for x in s]
    by_labels = lambda labels, slot: [t for t in tabs if t.labels == labels and t.slot == slot][-1]  # noqa: E731
    base = {'input': by_labels(['P', 'Col'], 0), 'ex_input': by_labels(['E', 'P', 'Col'], 1), 'ex_output': by_labels(['E', 'P', 'Col'], 2)}
    rule = [t for t in tabs if t.slot == 4]
    return arclog, w.M, sess, rule, base


def real_deltas(PT, rule, base):
    """The body_delta values of the real pairs: the empty body to the last, the last to itself, and END."""
    return [PT.body_delta(rule[0], rule[-1], base), PT.body_delta(rule[-1], rule[-1], base), PT.body_delta(None, [rule[-1]], base)]


# sha256 of the float32 bytes of real_deltas() under version point_tables.1
V1_DIGESTS = {
    0: 'bbc6e8c194cf01c884f105d432f9c4a9549af07e2b425da62cf665cd0b4e9ce4',
    1: '5a0a399499410cf9123beb21f541250de90362374de640f2ecf2617c733a0f6f',
    2: '848fec3a97981c449540605d69b645f3d1208760cae835fa01a8a5692b584a23',
}


def test_real_tables_of_a_ramp_program():
    """Task 74dd1130: the tables after the tokens of a RULE whose body reads `input` and a DET with eight assignments."""
    arclog, M, sess, rule, base = real_setup()
    cur, succ = rule[0], rule[-1]
    assert len(succ.at) == 8
    for c, s in ((cur, succ), (succ, succ)):
        v = PT.body_delta(c, s, base)
        d = named(v)
        assert d['delta:pairs'] == 8 and np.isfinite(v[-1])
        assert all(0 <= d[f'delta:{k}:{a}'] <= 1 for k in ('kept', 'lost', 'empty', 'out_recall', 'out_precision', 'changed_recall', 'pos_recall', 'lost_cells') for a in PT.AGGS
                   if not math.isnan(d[f'delta:{k}:{a}']))
        assert d['delta:rows_succ:mean'] > 0 and d['delta:out_recall:mean'] == d['delta:out_recall:mean']
    end = named(PT.body_delta(None, [succ], base))
    assert end['delta:pairs'] == 8 and math.isnan(end['delta:kept:mean']) and end['delta:fanout:min'] >= 1
    sv = PT.successor_vector(succ)
    assert sv.shape == (250,) and np.isfinite(sv).all()
    st = PT.state_vector([succ, base['ex_output']], base, ['RULE', 'DET'])
    assert st.shape == (len(PT.state_names()),) and st[0] == 2 and 0 <= st[-3] <= 1


def test_values_are_those_of_version_1_and_a_prebuilt_context_gives_the_same_bits():
    import hashlib

    arclog, M, sess, rule, base = real_setup()
    ctx = PT.base_context(base)
    raw, pre = real_deltas(PT, rule, base), real_deltas(PT, rule, ctx)
    for k, (a, b) in enumerate(zip(raw, pre)):
        assert a.tobytes() == b.tobytes()
        assert hashlib.sha256(a.tobytes()).hexdigest() == V1_DIGESTS[k]
    kinds = ['RULE', 'DET']
    assert PT.state_vector([rule[-1], base['ex_output']], base, kinds).tobytes() == PT.state_vector([rule[-1], base['ex_output']], ctx, kinds).tobytes()
    assert PT.VERSION == 'point_tables.2'


def test_base_from_the_engines_base_tables():
    """`arclog.base_tables` gives input, ex_input and ex_output (a real `input`, and ex_input and ex_output with one entry for each example); the values are those of the probe's."""
    arclog, M, sess, rule, base = real_setup()
    if not hasattr(arclog, 'base_tables'):
        pytest.skip('the engine wheel has no base_tables')
    from table_export import read_export

    class AllTables:
        """M with every table given a relation number of 0, since read_export leaves out the tables of a negative relation, which the base tables are."""

        def __init__(self, m):
            self.m = m

        def col(self, ct, part, key):
            v = self.m.col(ct, part, key)
            return np.zeros(len(v), np.int64) if (part, key) == ('tables', 'relation') else v

        def __getattr__(self, k):
            return getattr(self.m, k)

    given = {t.name: t for t in read_export(AllTables(M), arclog.base_tables(sess.decoder(), 'live', 'live', rows=True))}
    assert {'input', 'ex_input', 'ex_output'} <= set(given)
    want = real_deltas(PT, rule, base)
    for got in (real_deltas(PT, rule, given), real_deltas(PT, rule, PT.base_context(given))):
        for a, b in zip(want, got):
            assert a.tobytes() == b.tobytes()
