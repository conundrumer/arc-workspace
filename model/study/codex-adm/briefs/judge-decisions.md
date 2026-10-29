# Judge path specification

This file is the complete specification for the judge's document, its brief and its tool. Where another text differs from it, this file holds. S is /Users/davidlu/code/arc-workspace/work/lm/data-study. P is /Users/davidlu/code/arc-workspace/work/lm/data-study/ref/progsynth-relabel, a copy of another session's work.

## Terms

- X: the mutant's table at the changed point.
- G: gold's table at the same point, for the pair's case.
- Available tables: `input`, `ex_input`, the train rows of `ex_output`, and every gold table that does not depend on G, directly or through other tables, DET relations and INIT ports included. G and the tables that depend on it are never available.
- Targets: G, the tables of the pair's case after the changed point, and every table of every other case of the task. Tables of other cases are compared without names. A recovery to any target still needs X as the source of its rows, as the recovery rules below state.
- Kept assignment: gold's kept DET values. Every comparison is made at the kept assignment, with the mutant run at the same values.

## What the judge does

The judge gives no label and no grade. It writes clauses, and the tool runs and checks them:

- A recovery: one `RULE` or `DET` clause that gives a target from X. Each column of the target is bound at a site of X, or computed from X's columns by a lib relation that gives exactly one row per X row; every other atom (an available table, a lib relation, a comparison, a `NOT`) only restricts which rows of X are kept. A lib relation that gives several rows per X row, such as `axis_elem` or `dir_elem`, adds rows that do not come from X. A component instance (`INIT`) is not allowed.
- An alternative continuation, where X carries another relation a correct program could build on: one `RULE` or `DET` clause that reads X.
- Where it finds no clause, it says so.

The judge gives one or two reasons for each clause, each naming its evidence: a relation, columns, rows or cells.

## Which pairs the judge sees

A pair the mechanical labeler (S/ast/run/mech/) leaves without a recovery, where X holds every gold row, and where the search did not cover the space: `overapproximation` pairs without a witness, and pairs stopped at the bound. A `lossy` pair is not judged: no clause in the space can add rows X lacks, so its grade is Reject from the mechanical result alone. A `fits` pair is not judged: its grade is mechanical, and the mutant program is itself its continuation. A DET-kind pair is not judged. An INIT-kind pair is judged on the input the component receives per key: the projection of the body rows onto the key's `^` labels and the port's column labels.

## How the tool checks a clause

- The evaluator builds the whole mutant program with the clause inserted after the changed form, OUT included, runs the normal search, and keeps the table entries whose DET assignment agrees with the kept assignment on every slot the table lists. `P/engine_verify.py` does this. One evaluator serves the tool and the labeler's lib-relation pass.
- A clause verifies when its kept entries equal the target on every train input and on the test inputs. The target's test rows come from gold's full replay; for an INIT pair, from the same projection of gold's body rows on the test input. A `DET` that filters X by `ex_output` copies the train answers, and the test inputs, where `ex_output` has no rows, expose it.
- Equality: columns are matched by name, else by type; component ids match up to a renaming; Position and Box cells compare as the same four margins.
- The tool rewrites a label that a later OR branch re-makes with `*` to the bare label, as `P/engine_verify.py` (`canonical_or`) does.
- A union verifies as a recovery when its branches that read X supply rows the target needs and X is not `redundant`.
- A clause that verifies but binds a target column at an atom other than X, without a lib relation over X's columns, is a partial source.
- A continuation passes when its table, on every train input, is not empty, not equal to X, and not equal to any available table. A continuation whose table equals a target is a recovery, checked as one.
- A replay with no entry at the kept assignment gives unknown.
- The judge can also run any clause over X and the available tables to explore them, such as a query that selects part of a large candidate table, and see its result with the row count. These runs are not answers and are not graded. The tool bounds what it prints and says how many rows it left out.

Each clause gets one outcome: recovery verified, partial source verified, continuation passed, refused by the engine, did not verify, or unknown.

## How the pair's grade is made

The labeler makes the grade from the mechanical result and the tool's outcomes, never from the judge's words. Grades, from the strongest:

- `equivalent`: X equals a target.
- Recovery: a verified recovery to G or to a later table of some case.
- Partial source: a verified partial source.
- `fits`: the mutant program gives every train output and the test outputs, and a reader reads a column where X differs from gold. A difference no reader reads is `extension`. A DET-kind pair never grades `fits` or `extension`: the evaluation holds every DET at gold's kept values, so OUT never reads the mutant's DET, and its table is graded by the rows alone.
- Reject: the search covered the space and found no recovery, or the judge ran and no clause of it verified as a recovery or a partial source, and the mutant program does not fit. A passing continuation is recorded as an attribute of the Reject.
- Unknown: the search stopped at its bound, the comparison is incomplete, or the replay gave no kept entry.
- Refused: the engine refuses the mutant program.

Attributes: `redundant`, `sibling`, and the continuation's outcome.

## The judge's input

- The judge's input is the brief and the pair's data. The data is files in a standard format that Python reads directly: every table (X, G, the targets, the available tables), the comparisons of X with each target, the readers, the gold and mutant program text, and the task's train grids. Nothing in the brief inlines data.
- The judge reads the data with its own inline Python. The brief describes the file layout, the data conventions (how each type is stored, how rows split by example and DET assignment) and a few high-level recipes, such as loading a table, comparing X with a target, drawing positions as a grid, and finding a column of X that holds the same values as another column or an available table.
- Every relation and column carries its source name, the name a clause uses. A port's columns carry the port's declared column names, not the body labels.
- The brief states the clause rules: the OR rule (a label the first branch makes is named bare in every later branch), and the literal rules (`0` stands only as a site argument on a number, Box, Position or Offset column, or as the second label of a constraint whose first label is a number or a Box; on a Position, `0` is the zero box, a cell only in a 1×1 frame; `0` is never a color, and a color comes from a relation that holds it).
- Running a clause is the only command: run, check and alternative, each writing its result as data in the same format.
- No test output is in the data. The verdict on a clause always comes from the tool's check against the complete tables.

## Ownership

- n-judgedoc owns the document and the whole judge brief.
- n-judgetool owns the tool and the evaluator, and gives n-judgedoc the brief's text on using the tool.
- n-mech owns the labeler and the grade.
