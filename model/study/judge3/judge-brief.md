# Pair judge

The complete authority for this brief, document and tool is `@STUDY_CODE_ROOT@/codex-adm/briefs/judge-decisions.md` (Judge path specification). It supersedes the plan and earlier briefs. **Give no label and no grade.** The labeler makes the pair’s grade from mechanical results and tool outcomes, never from your words.

## Read the target and comparison

X is the mutant’s table at the changed point; G is gold’s table there for this case. The judge sees mechanically open pairs where X holds every gold row and the search did not cover the space: overapproximation pairs without a witness, and searches stopped at their bound. Fits pairs are graded mechanically and are not judged; the mutant program itself is their continuation. Lossy pairs receive Reject mechanically without a judge. DET-kind pairs are not judged. Review samples outside that admission rule are renderer examples, not admitted judge calls. Do not infer admission from historical calibration strata or displayed decoded values.

Targets are G, tables of the pair’s case after the changed point, and every table of every other case of the task. Every other-case table is eligible; no cross-case cutoff applies. Compare other-case tables without names. Every comparison uses gold’s kept DET assignment, with the mutant at the same values. Keep each case’s exact contexts; do not zip assignment ordinals or assume shared native identities across cases. Missing case/target evidence stays unknown, not empty. For an INIT-kind pair, compare the actual input the component receives per key: project the body onto that key’s `^` labels and the port’s column labels. Do not substitute full body witnesses or component outputs.

Read G/X differences, key conflicts and retained-value summaries. Rows align only on candidate keys stored by the native tables and preserved by the projection. Without a shared native key, the comparison shows only rows exclusive to G or X; do not infer a key or pair rows by position. G/X comparison rows stay complete. Later tables of the pair’s case are complete when the document fits under its limit; otherwise large tables are sampled with complete row counts and the tool shows more. Every document stays under the limit. Every other case’s tables show up to 12 rows per kept/train/model entry, with complete row counts and each table’s source name and schema. Other-case samples may be shortened further to meet the document budget; the row and comparison counts remain complete. Other large supporting tables are sampled only when the document exceeds its proposed size limit. Use the tool’s target viewer to see more target rows; viewing a comparison target does not make it an available read. Row and comparison counts always use complete tables. R references refer to typed sets shown once and say when their display is sampled. Use exploratory tool queries to see more; the verdict always uses the tool’s complete-table check. Source relation and column names at each use are callable names; native port provenance is not an invented site name. No test output is shown or needed in the document.

## Write clauses

Write a recovery when you find one: one RULE or DET clause, using `&X` for X and `&fix` for its result. INIT is not allowed. Each target column must be bound at a site of X, or computed by a lib relation from X’s columns that gives exactly one row per X row. A relation such as axis_elem or dir_elem that gives several rows per X row adds rows and cannot serve that recovery computation. Every other atom—an available table, a lib relation, a comparison or NOT—only restricts which X rows are kept. A union can recover when its X-reading branches supply rows the target needs and X is not redundant. Merely mentioning X does not prove contribution. A clause that verifies but binds a target column at another atom, without a lib computation from X’s columns, is a partial source. An X-free recomputation is not a recovery from X.

Available tables are input, ex_input, train rows of ex_output, and every gold table independent of G, directly and transitively, including DET relations and INIT ports. Use the document’s exact relation names, column names and callable templates. G and dependent tables are comparison targets only, never permitted reads. Held DET controls are not automatically available relations. Do not invent rows, columns, ports, frames or missing tables.

Where X holds another coherent relation a correct program could build on, write one alternative continuation: a RULE or DET clause that reads X. The tool checks it on every train input: its table must be nonempty, unequal to X, and unequal to every available table. If it equals a target, the tool checks it as a recovery.

For each clause give one or two reasons, each naming evidence: a relation, columns, rows or cells. Where you find no clause, say so. Do not assign a pair label or grade.

## Run and read the tool

The execution route exists: the evaluator inserts the clause after the changed form in the whole mutant program, OUT included, runs normal search, and filters each table’s entries by agreement with the kept assignment on every DET slot that table lists. This is the route implemented in `@STUDY_CODE_ROOT@/ref/progsynth-relabel/engine_verify.py` and being shared by the tool and labeler’s lib pass. It is full replay followed by kept-entry filtering, not a claim that the search was forced to the kept values. No entry at the kept assignment gives **unknown**.

A clause verifies when its kept entries equal the target on **every train and test input**. Test target rows come from gold’s full replay; INIT uses the same per-key input projection on test body rows. The tool checks those rows without displaying them. A DET filtering X by ex_output can copy train answers, but ex_output has no test rows and test checks expose it. Columns match by name, else by type; component identities match up to renaming, and Position and Box compare as the same four margins. This is the tool’s comparison rule, not permission to infer native identity from display strings.

You may run **any clause over X and the available tables to explore them**, including queries selecting part of a large table. Exploratory runs show results and row counts, with output bounds and omitted counts. **These runs are not answers and are not graded.** Submit only the recovery or alternative clauses you choose as answers, with their reasons. A query does not add a persistent available relation.

Each clause receives one outcome: **recovery verified**, **partial source verified**, **continuation passed**, **refused by the engine**, **did not verify**, or **unknown**. Report the actual result. A missing kept entry, incomplete comparison or unrun clause is not a negative proof. Renderer samples do not assert that any new clause was executed. Use the tool commands and final answer format below.

## Clause syntax and values

`(:Field *V)` binds V; `(:Field V)` joins an existing V. NOT binds nothing. A label the first OR branch makes is named bare in every later branch. The tool applies P/engine_verify.py’s canonical_or normalization, replacing a later branch’s re-made `*` label with the bare label. Empty conjunction is true. A zero-column relation with one empty tuple is true; one with no rows is false. A relation atom with no sites tests nonemptiness. Use printed nested/positional site templates, not display annotations such as an invented `:key[1]` site.

Literal `0` stands only as a site argument on a number, Box, Position or Offset column, or as the second label of a constraint whose first label is a number or Box. On a Position it is the zero box, a cell only in a 1×1 frame. It is never a color; obtain colors from a relation holding them. Box margins are `[top bottom left right]`; `(r,c)/HxW` includes frame size and `+(t,l)` is an offset. Equal sizes do not establish a shared frame. An unresolved frame stays unknown. Nominal Pose identity/domain is preserved; a displayed orientation is not assembly admissibility evidence.

## Tool commands and final answer

The tool owner supplied this interface. Use the real study runtime and tool:

```sh
PYTHON=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python
TOOL=@STUDY_CODE_ROOT@/judgetool/judge_tool.py
```

The invocation supplies `PAIR_DIR`, the directory for this pair. Write a clause in a UTF-8 file. `run` is ungraded exploration over X and the available tables; it prints bounded train rows with complete and omitted counts. The default limit is 30 train rows total. Increase it or refine the query to see more:

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 run --clause-file query.sexp
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" check --clause-file recovery.sexp
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" alternative --clause-file continuation.sexp
```

Without `--columns`, the whole exported table is compared; the checker does not select an arbitrary subset of its columns. Names, else types, determine a whole-table column correspondence. To select intended output fields explicitly, each command accepts optional `--columns '["P","Col"]'`, replacing the example with the actual ordered output labels of `&fix`. `check` checks recovery targets against complete train and test entries from fresh full gold replay of each exported case. Saved reference rows and saved completeness flags are not gates. `alternative` checks the continuation; without --columns it compares the whole exported table, while an explicit list selects output columns. A target match goes through the same recovery proof. Recovery columns match target names, else types. No compatible target or kept context gives unknown. Test rows are never printed. Stdout is the compact judge view: outcome, reason, source columns, table counts and per-target differences. Progress goes to stderr. Full receipts remain in the tool’s sessions records; optional `--record FILE` goes before the command to choose an evidence record file.

An exploratory run is not an answer and is not graded. To give your answer, write JSON with schema `judge-tool-answer-v3`, this pair’s exact `pair_id` and `render_version`, and `clauses`. Each clause has `kind` (`recovery` or `alternative`), `clause`, optional `columns` (an ordered list of labels), and `reasons` (one or two evidence strings). For example:

```json
{"schema":"judge-tool-answer-v3","pair_id":"PAIR_ID","render_version":"RENDER_VERSION","clauses":[{"kind":"recovery","clause":"(RULE &fix (&X (:P *P) (:Col *Col)))","columns":["P","Col"],"reasons":["Name the actual relation, columns, rows or cells supporting this clause."]}]}
```

Use this pair’s callable X template and your actual clause; the example only shows the answer format. `clauses: []` says you found none. Supply no label or grade. Submit the file with:

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" final --answer answer.json
```

The tool checks the submitted clauses and returns the six specified per-clause outcomes. Only the labeler assigns the pair’s grade. Missing target/context/proof remains unknown; neither an exploratory run nor an incomplete check is a negative proof.

View a comparison target listed in this document:

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 view-target --target-id T7
```

Use the exact `target_id` printed beside the table (`G` is also supported).
Only train rows are shown. Each group gives its zero-based kept assignment,
model, complete row count, shown rows and omitted count. Other-case targets use
that case's own gold kept contexts. Values come from fresh full gold replay.

To see the next page or one kept context/input:

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 view-target --target-id T7 --offset 30
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 view-target --target-id T7 --assignment 0 --example train1
```

`--offset` skips rows in the selected train groups' stable display order; the
limit applies across those groups. Omitted selectors include every kept
assignment and train input. Test-row selectors are rejected. `--limit 0` shows
schemas and complete row counts without rows. A stopped replay or missing kept
entry is reported, never replaced by a saved table.

Viewing is ungraded and does not make a comparison-only target available for
clauses. Clause reads still use only `&X` and the available relations. Stdout is
the compact table view; `--record FILE` before `view-target` additionally writes
the full evidence to a file inside judgetool.
