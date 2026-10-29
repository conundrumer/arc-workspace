## Tool

Use the supplied pair directory and these paths:

```sh
PYTHON=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python
TOOL=@STUDY_CODE_ROOT@/judgetool/judge_tool.py
```

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 run --clause-file query.sexp
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" check --clause-file recovery.sexp
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" alternative --clause-file continuation.sexp
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 view-target --target-id T7
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" --limit 30 view-target --target-id T7 --offset 30 --assignment 0 --example train1
```

`run` and `view-target` are ungraded exploration, not answers. Use the document’s target ID; G is supported too. The viewer shows only train rows, with complete counts and omissions. Offset skips rows across selected groups; assignment is zero-based in the target’s own case. Assignment and example selectors are optional. Increase the limit or page forward to see more. `--limit 0` shows schemas and counts only. Targets remain comparison-only.

Without `--columns`, checks compare the whole exported table. Optional `--columns '["P","Col"]'` selects those ordered `&fix` labels; use your actual output labels. Results show the outcome, reason, source columns, counts and per-target differences.

## Answer

Use the supplied pair_id and render_version. Write JSON:

```json
{"schema":"judge-tool-answer-v3","pair_id":"PAIR_ID","render_version":"RENDER_VERSION","clauses":[{"kind":"recovery","clause":"(RULE &fix (&X (:P *P) (:Col *Col)))","columns":["P","Col"],"reasons":["Name the actual supporting rows or cells."]}]}
```

Use your actual clause and binding sites. Each entry has kind `recovery` or `alternative`, clause, optional columns, and one or two reasons. `clauses: []` says none found.

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" final --answer answer.json
```
