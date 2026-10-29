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
