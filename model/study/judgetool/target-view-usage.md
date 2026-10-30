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
