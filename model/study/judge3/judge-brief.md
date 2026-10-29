# Write recovery and continuation clauses

Give clauses with one or two reasons each, naming the supporting relations, columns, rows or cells. If you find none, submit an empty clause list. Give no label or grade.

X is the changed table, exposed as `&X`. G is gold’s table there. Targets also include later tables of this case and every other case’s tables; other-case names do not affect equality. INIT pairs use the actual per-key input projection, including `^` key labels and declared port columns. Use the printed binding template.

A **recovery** is one RULE or DET producing `&fix`. Every target column comes from an X site or a lib relation over X’s columns giving exactly one row per X row. Other atoms only restrict X rows. Expanding relations such as axis_elem or dir_elem cannot supply recovery columns. INIT is not allowed. An X-reading union must contribute rows the target needs, and X must not be redundant. A matching clause taking target columns from another atom is a partial source; the tool distinguishes it.

An **alternative continuation** is one RULE or DET reading X. On every train input its result must be nonempty, different from X and different from every available table. A target match is checked as a recovery instead.

Read only X and the printed available relations: input, ex_input, train ex_output and gold tables independent of G. G and its dependents are comparison-only; viewing them never permits reading them. Invent no fields, rows, ports or frames.

G/X comparisons stay complete. Align only on stored candidate keys; without one, inspect G-only and X-only rows. Model ordinals are independent. Later same-case tables are complete when they fit; large tables may be sampled with full counts. Other-case target tables show samples. Use view-target for more rows and ungraded run queries to explore available relations. Samples and exploratory runs never decide verification.

The tool checks recoveries on complete train **and test** targets from full gold replay at compatible kept assignments. ex_output has no test rows. Columns match by name, else type; component IDs match up to renaming; Position and Box compare as four margins. No compatible entry gives unknown. Test rows are not shown.

`(:Field *V)` binds V; `(:Field V)` joins an existing V. NOT binds nothing. A label made in the first OR branch is bare in later branches; the tool normalizes later re-made `*` labels. Use printed nested/positional templates. Literal `0` is allowed only at Number/Box/Position/Offset sites, or as the second constraint label when the first is Number or Box. On Position it is the zero box, a cell only in a 1×1 frame. Never use `0` as Color; obtain colors from relations.

Each answer clause receives: recovery verified, partial source verified, continuation passed, refused by the engine, did not verify, or unknown. An unknown or unrun candidate is not evidence that no recovery exists.

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
