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

## Files

- `render_branch.py`: the script.
- `<task>-<prefix_tokens>.md`: one branch point each. Each holds the task's train pairs, the prefix program, then the gold continuation and up to `--samples` sampled continuations in the export's order. For each continuation, the file gives its labels, its text up to the clause of its last shown table, the first `--tables` tables after the branch with their rows for each train example, and a list of every table after the branch. It ends with a "What I see" section, written by hand.

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
