# Data study: branch points of a rollout export

## Running

List the branch points of one task (or, with no task, of every held-out task), with prefix_tokens, gold length, sampled continuations and those with a table after the branch:

```
work/lm/.venv/bin/python lm/runs/data-study/render_branch.py list work/lm/rollouts-s2/export work/lm/data-full-09be8c8b [<task>]
```

Render one branch point to `lm/runs/data-study/<task>-<prefix_tokens>.md`:

```
work/lm/.venv/bin/python lm/runs/data-study/render_branch.py render work/lm/rollouts-s2/export work/lm/data-full-09be8c8b <task> <prefix_tokens> [--samples 6] [--tables 2] [--out FILE]
```

The second argument is the data export whose `vocab.json` maps token ids to names. A render keeps the "What I see" section of an existing file.

Render one corpus case whole to `lm/runs/data-study/case-<task>.md`, from a tables export and the streams export of the same master:

```
work/lm/.venv/bin/python lm/runs/data-study/render_case.py work/tables/full-9a98b493 work/lm/data-full-9a98b493 <task> '<case>' [--out FILE]
```

It reads only the rows of that case. A render keeps the "What I see" section of an existing file.

Compute the detectors of `marks.md` over the first table after the branch of every continuation, then measure how each ranks the gold continuation's table against the sampled ones:

```
work/lm/.venv/bin/python lm/runs/data-study/detectors.py compute work/lm/rollouts-s2/export [--seconds 840]
work/lm/.venv/bin/python lm/runs/data-study/detectors.py measure work/lm/data-full-09be8c8b
```

`compute` writes one parquet per task under `work/lm/data-study-detectors`, skips the tasks already written, and stops starting tasks after `--seconds`; run it again to go on. Once every task is written, it joins them into `detectors.parquet`. The second argument of `measure` is the data export whose held-out tasks give the split.

## Files

- `render_branch.py`: the script.
- `<task>-<prefix_tokens>.md`: one branch point each. Each holds the task's train pairs, the prefix program, then the gold continuation and up to `--samples` sampled continuations in the export's order. For each continuation, the file gives its labels, its text up to the clause of its last shown table, the first `--tables` tables after the branch with their rows for each train example, and a list of every table after the branch. It ends with a "What I see" section, written by hand.
- `render_case.py`: the script that renders one case.
- `case-<task>.md`: one concept case each. Each holds the task's train and test grids, then each clause of the case's token stream followed by the tables of the relations it declares: columns, depth, candidate keys, the DETs its entries are assigned, and the rows of each train example and of task-wide entries, those with an Example column grouped by it. A table with several DET assignments is given once per assignment, marked with the values of the DETs that differ between them. A drawing shows a Color, an Ident (as a letter) or a Number where each cell has one row, else the count. It ends with a "What I see" section, written by hand.
- `case-22425bda.md`: crossing lines stacked into a one-row list of colors; a DET with four assignments.
- `case-3979b1a8.md`: the input grown to twice its size, its diagonal continued with period 3; DETs that read the outputs.
- `case-2c608aff.md`: markers joined to a block along a row or column; no DET.
- `case-9565186b.md`: keep the majority color of a 3x3 grid and gray the rest; Mode as counts and an order, with the unread components of its sibling cases.
- `case-7c008303.md`: a divider cross, a key quadrant and a pattern quadrant; the pattern is recolored block by block from the key.
- `case-8e5a5113.md`: tiles filled with quarter turns of a pattern tile; five DETs of 16 assignments, most of them empty.
- `case-e633a9e5.md`: a scale-up of each cell to a tile, with seven DETs, three of which read the outputs for the cell correspondence.
- `case-b5bb5719.md`: a pyramid grown under seed pairs with a color swap, at 8 assignments of two lib DETs.
- `case-bda2d7a6.md`: a cycle of the colors of nested rings, beside the tables of three other cases' clauses.
- `case-44f52bb0.md`: the case `$Direct`, a 3x3 input classed by its mirror symmetry into the 1x1 output 1 or 7.
- `case-5ad8a7c0.md`: the case `$Shortest`, the pairs of marks at the least gap fill their spans, at two DET assignments of the axis.
- `case-6d1d5c90.md`: the case `$Marked`, a band is dropped and the rows rotate by the marker's row, at 16 DET assignments of two directions.
- `detectors.py`: the script that computes and measures the detectors. Its docstring defines each detector and the measurement.
- `detectors.parquet`: one row per Table at positions 0 to 3 after the branch, with its member, label and flags, the inputs of `value_eval.features`, and the detector values at position 0.
- `detectors.out`: the measurement: counts of lists, pairs and Tables, the Tables each filter fires on, and the ranking accuracy and AUC of each detector, of the trivial baseline and of a logistic regression on every detector, on the held-out branch points and in 5-fold cross-validation by task.
    - No held-out sampled continuation solves, so each pair is gold against sampled and the metric tells the gold writer's table from the LM's; gold tables have more columns, which part of each score reads (the file gives the score over pairs of one column count); and the trivial baseline's 0.651 is at positions 4, where the detectors are measured at positions 1.
- `observations.md`: what held across the `case-<task>.md` files about telling from a table that it adds information, and what took the clause text or the later program.

## Decoding

The script loads the cases of one branch point through `encoder.load_rollouts` (strict=False, allow_violations=True) on a copy of the export that holds only those cases and no `flows.parquet`. Each cell of a row is an int32, by the type of its column, as `engine/arclog/src/decode/columns.rs` writes it. A Box is four cells, its margins (top, bottom, left, right) in the example's grid. A cell at row r and column c of an h x w grid has the margins (r, h-1-r, c, w-1-c), and an offset of (dr, dc) has the margins (dr, -dr, dc, -dc), as `jump_offset` in `engine/arclog/src/algebra/boxes.rs` gives. So a Box is drawn as `(r,c)` where it is a cell of the example's input grid, as `(r,c)out` where it is a cell only of the output grid, as `+(dr,dc)` where top = -bottom and left = -right, as `rR0-R1 cC0-C1` where it is another box inside the input grid, and else as `[t b l r]`. Where the first Box column of every row of an example is a cell of one grid size, the rows are also drawn on a grid of that size: each cell shows the row's Color where the table has one Color column and the cell has one row, else the count of rows at the cell, and `.` where no row is. An orientation cell is its encoding, named by the export's `orientations.json` (for example 0 is DIR_T and 512 is AXIS_V). A Color is its digit, a Number is itself, an Example is `e<n>`, and an Ident is `id<n>`, which is equal only to an Ident of the same case.

## Viability of a step

`viability.py` classes each relation after the branch of every continuation of the export by the engine's output, a DET's assignments pooled, and `viability.out` holds its numbers:

```
work/lm/.venv/bin/python lm/runs/data-study/viability.py index|relation|restate|empty-dist work/lm/rollouts-s2/export
```

The classes: faulted; unseen (an entry stopped at the engine's work cap); empty in every train example; empty in some train examples; a restatement (its rows at every example equal an earlier table's of the same case, or a projection of one onto fewer columns; `restate` reads the rows of the first table after the branch); viable.

* comment: The user's words, session 64993706, 2026-10-25T18:14:04Z: "the thing we are looking for is 'does it add info that can help w solving'", and on the classes, "in the context of program synthesis": empty in every example, "filter out"; empty in some examples, "fine, but it's still a signal. questionable viability"; unseen, "probably invalid"; on a restatement, "in arclog, this doesn't add info".
- The question of a step is whether its table adds information that can help with solving. A table empty in every train example, a restatement or a projection of an earlier table, and a table over the work cap add none, in a gold program as in a sampled one: a gold program's guards read under `NOT`, its restatements of the input's cells or of a background color, and its tables over the cap are idiom, not steps. A table empty in some examples adds partial information and is a signal of questionable viability.
- On the 200-task rollout export: the first relation after the branch is viable for 91% of gold continuations and 46% of sampled ones, a cut with no table counted as not viable. Over all positions, sampled relations are empty in every example 32% of the time and faulted 14%; gold 6% and 0%. Restatement does not separate gold from sampled (14% and 16% at the first table). Relations empty in some examples are 3% of gold's and 2% of sampled ones' by continuation weight, and most are empty in one of two or one of three examples; sampled ones lie more often in the tails (under a third or over two thirds of the examples empty).
