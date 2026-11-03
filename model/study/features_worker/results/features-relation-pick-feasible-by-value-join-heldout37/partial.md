# Feasible relation picks: partial

Rows: 1724 of 1761 gold-alive picks, 37 tasks, 428 forms. Prior bits on these picks 3.120. Largest gap to the census per pick 0.0. Numbers below change as rows land.

## The feasible set

A relation pick's feasible set is the set of options, among those alive by column type, that can give a row with the labels bound at the pick, on the task's own train examples. The test input is not read.

- **Bound labels.** The labels of the clause's prefix at the pick. Their values are the rows of the prefix's table, from `arclog.step_tables` at that clause.
- **Column map.** One column of the relation, or one field of a record column, set to one bound label. The decoder decides which label may stand at which column, by its own type rules. Other columns stay unnamed. A column that the atom must name, and that takes no fresh label, takes a label or `0`.
- **Join.** The relation is feasible on an example where some map gives a row of the prefix joined with the relation, by the engine's row count on that clause. A map of more labels gives a subset of the rows of a map of fewer, so one label per map is enough for this test.
- **Relation that shares no bound label.** At a later atom, a relation with no column that a bound label can stand at is out. The census calls it dead by join, so it is out of the alive set too.
- **First atom.** No label is bound, and the relation stands alone: it is feasible where its own atom gives a row.
- **OR branch.** The engine gives no table inside an OR, so the walk reads the flat clause that the branch stands for: the atoms before the OR and the branch's atoms so far, with labels renumbered. A label that an earlier branch made and this branch has not named is not bound. The first atom of a branch of an OR at the body's start stands alone.
- **NOT.** The NOT token is one option, in the set where the prefix has a row. At the relation pick after it, a map must remove a row and keep a row on one example. A map under NOT may hold up to 3 labels, since a map of more labels removes fewer rows. A column under NOT takes no fresh label. The `keep` set drops the need to remove a row.
- **Comparison.** An operand pair that the decoder admits must remove a row and keep a row on one example, or be `(= *X Y)`, which makes a label and keeps every row. The `keep` set drops the need to remove a row.
- **Across examples.** The `any` set needs a map that gives a row on at least one train example. The `all` set needs one map that gives a row on every train example where the prefix has a row. The per-example size counts the options that have some map on that example alone.
- **Undetermined.** An option with no row, and with a stop, a fault, or the cap of 120 tables on its maps, stays in each set and is counted.

## Part 1

| Picks | Count | Alive: Q1, median, Q3 | Feasible, any example | Feasible, all examples | Mean over examples, one example at a time |
|---|---|---|---|---|---|
| all picks | 1724 | 53.0, 70.0, 86.0 | 35.0, 55.0, 78.0 | 34.0, 53.0, 77.0 | 34.0, 53.3, 77.0 |
| first atom | 428 | 83.0, 90.0, 103.0 | 78.0, 86.0, 99.0 | 78.0, 86.0, 98.2 | 78.0, 86.0, 98.8 |
| second atom | 394 | 42.0, 51.0, 66.0 | 24.0, 33.5, 50.0 | 24.0, 32.0, 47.0 | 24.0, 32.7, 48.5 |
| third atom | 327 | 48.0, 59.0, 71.0 | 31.0, 42.0, 56.0 | 31.0, 41.0, 55.5 | 31.0, 42.0, 56.0 |
| later atoms | 575 | 57.0, 67.0, 80.5 | 39.0, 51.0, 65.0 | 37.5, 50.0, 64.0 | 38.0, 50.0, 64.2 |

| Set | Gold in set | Share | Prior, same picks | Uniform over alive, same picks | Uniform over set | Prior in set | Saved by the prior in set, 95% by task |
|---|---|---|---|---|---|---|---|
| any | 1668 | 0.968 | 3.107 | 5.938 | 5.515 | 2.888 | +0.218 (+0.193 to +0.247) |
| all | 1635 | 0.948 | 3.083 | 5.943 | 5.493 | 2.850 | +0.233 (+0.212 to +0.255) |
| keep | 1687 | 0.979 | 3.113 | 5.938 | 5.647 | 2.938 | +0.175 (+0.153 to +0.202) |

All picks, with an escape weight from 1254 test picks: {'any': 0.0534, 'all': 0.0686, 'keep': 0.0423}.

| Set | Prior | Uniform over set, escape | Prior in set, escape | Saved |
|---|---|---|---|---|
| any | 3.120 | 5.694 | 3.072 | +0.049 (+0.012 to +0.087) |
| all | 3.120 | 5.732 | 3.108 | +0.012 (-0.027 to +0.048) |
| keep | 3.120 | 5.774 | 3.064 | +0.056 (+0.025 to +0.091) |

Gold out of the `any` set:

- gold's atom reads no bound label: 32
- NOT: gold's atom removes all on some examples and none on the others: 7
- gold's atom reads no bound label, inside a branch: 5
- comparison: gold's atom removes no row on any train example: 5
- comparison: gold's atom removes and keeps a row, and no map shows it: 3
- comparison: gold's atom removes every row: 1
- NOT: gold's atom removes every row: 1
- NOT: gold's atom removes no row on any train example: 1
- NOT: gold's atom removes and keeps a row, and no map shows it: 1

Probe cost per relation: step_tables with before, on a fork at the atom; ms is the whole probe of one option: decoder admits, forks, steps and tables, one thread. Median 1.58 ms, largest 48926.1 ms, over 108685 option probes; 1 tables each at the median, 120 at most. Per pick: median 188.6 ms, mean 1060.3 ms, largest 102276.7 ms.

Calls on one atom, ms, 109 picks:

- step_tables with before, read, fork: median 0.903, mean 2.18, largest 78.113
- projections: median 0.523, mean 2.925, largest 7789.939
- Decoder.admits, per token: median 0.003, mean 0.004, largest 0.008
- Decoder.forced: median 0.022, mean 0.028, largest 0.117

## Part 2

Weight fit on test rows: theta -0.2752. 1761 held picks, 1671 on the pool's 35 tasks.

| Set | Picks | Gold in set | Relation options in set | Saved, 95% by task |
|---|---|---|---|---|
| kept | 1761 | 0.450 | 0.189 | +0.004 (-0.006 to +0.014) |
| kept on pool tasks | 1671 | 0.444 | 0.188 | +0.003 (-0.007 to +0.013) |
| control_search | 1671 | 0.291 | 0.346 | +0.009 (-0.002 to +0.019) |
| factored_search | 1671 | 0.288 | 0.344 | +0.009 (+0.001 to +0.018) |
| both_control_search | 1671 | 0.545 | 0.456 | +0.010 (-0.001 to +0.020) |
| both_factored_search | 1671 | 0.537 | 0.449 | +0.011 (+0.001 to +0.021) |

## Part 3

Every earlier steer conditioned on names, kinds, column types and form structure, general across tasks: the prior's log share, relation name and kind by atom index, option types against scope types, arity, repeats and name crosses with the prefix, the point group and head name (`relfit.py`, `relfeat.py`, `relcheap.py`, `relnet.py`), and in the rank read the reader count, depth, DAG path, rank among options and pick-level counts. Only the rank read's content features read values, and they gave no gain.

