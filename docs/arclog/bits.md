* comment: when editing this doc
    - [Arclog documents](prompts/arclog.md) lists this document under Undisclosed.
    - The user's words, session e3928061-1720-4a0f-b4df-246232db80a7, 2026-11-01T15:18:00Z: "mostly dealing w lowering bits", with the command `uv run python scripts/arclog_bits.py PROGRAM.arclog TASK [--fast] [-v]`. The document states what the docstring and the code of that script and the census rows show, and leaves out what no document settles.

# Bits
- `scripts/arclog_bits.py` gives the bits of each form and each atom of an arclog program, in the census walk of the sampler. A form's bits are the sampler's cost of drawing it, and each form is measured over the forms before it.

## Running
- The command:
    ```
    uv run python scripts/arclog_bits.py PROGRAM.arclog TASK [--fast] [--parents] [--models DIR] [--steer-cover LIST] [--json OUT] [-v]
    ```
- `PROGRAM.arclog` has one form per line, as the gold text of the corpus has it: `(INIT ...)`, `(DET ...)`, `(RULE ...)`, `(RIGID_DET ...)`, then an optional `(OUT ...)`. A blank line and a line that starts with `;` are skipped. A line of another kind, such as `OUT`, shows its kind and `not a form` with no bits, and stays among the forms before the lines that follow it. `--fast` models only `RULE`, `DET` and `INIT` lines, and shows `not modeled` for another kind than `OUT`.
- `TASK` is a task id under `data/tasks/`.
- The options:
    - `--fast` gives the proxy, with no engine.
    - `--parents` adds, for each form, the bits when the scope is only the forms that it reads, directly or not.
    - `--models DIR` and `--steer-cover LIST` change the models and the `STEER_COVER` of the walk. The defaults are the models of the built bundle that `work/synth-kaggle/kernel-next-bundle-inputs.md` calls current, with `STEER_COVER` unset. A census with `init,branch` is `--steer-cover init,branch --models <its models dir>`.
    - `--json OUT` writes the records to `OUT`.
    - `-v` gives the whole reason of a `bad` or `dead` form.
- The exact mode runs a pinned engine, and the tool stops unless the installed engine has the hashes that the manifest `work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/manifest.json` gives for its wheel.
- `work/` is untracked and stands in the main tree, so a path under it is read from the main tree.

## Reading the table
- One row per form, and under it one row per atom. A row gives the bits and their split into the columns below. A form's row also gives its running total, and the `total` line gives the program total.
    - `rel`: the relation pick of an atom, with the operator relations.
    - `col`: the pick of a column, and of a function column.
    - `val`: a label or another value, and the comparison operator.
    - `stop`: the stop of an atom's column list, the stop of a body or of a branch, and whether a branch goes on.
    - `other`: the rest. In a form's row it is the component, the `OR` coins, the join mix, a port's coins and a head's. In an atom's row it is the atom's join mix.
- A form that the walk can't draw shows a reason and no number:
    - `bad`: a choice to which the walk gives gold chance 0.
    - `dead`: a gate or a refusal that ends gold's path.
- `fb` marks a form that the walk draws with something its priors lack, and a `fell_back:` line after the `total` line gives the keys.

## Exact and fast
- The exact mode is the default. It measures each form over every form before it, on a session of its own, and its figure equals the census row for the same text, code, models and `STEER_COVER`.
- `--fast` is a proxy: it reads a form as text and gives its bits from linear models, with no engine and no model files.

## The helper-form revision
- `work/lm/data-study/gold/gold-v3-helper-forms-a036da074/` holds a revision of the gold programs that cut 1,437 crossing clauses of 714 tasks into helper forms, as its `manifest.json` gives under `scope`. A crossing clause is one for which the census found a cheaper partition.
- The census rows before and after the revision are the rows of `census-base.jsonl` and `census-current.jsonl` under `work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/` whose `scope` is `before`, with no `bad` and no `dead`, of 37 tasks:
    | Revision | Forms with a figure | Median | Total bits | Forms at 18 bits or fewer |
    | --- | --- | --- | --- | --- |
    | Base | 813 | 24.1 | 27,846 | 297 |
    | Helper forms | 1,085 | 17.4 | 30,540 | 572 |
- Cutting adds forms, so the two rows have different form counts and are not paired.
- `gold_helper_one.py` in that folder cuts each crossing clause of one task at its census partition and checks the program under a bar. The bar of its docstring: every token passes at table work cap 2^20 in the Closed world, the program ends `Consistent`, its `OUT` rows equal gold's on each train and test input, its attempts equal gold's, its normal form is a fixed point of the round trip, and each new form walks in the census with nothing refused. A clause that breaks the bar stays as gold writes it.
