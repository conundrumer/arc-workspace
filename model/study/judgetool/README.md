# Judge clause tool

The public entry point is `judge_tool.py`. A judge receives the [whole brief](../judge3/judge-brief.md) and a plain pair-data directory produced by [the exporter](../judge3/export_dataset.py). The [data format](../judge3/dataset-format.md) is ordinary UTF-8 JSON with complete TRAIN typed cells and separate assignment/model axes. There is no viewing or pagination command.

```sh
python judge_tool.py --pair DATASET run --clause-file query.sexp --output NEW_RESULT_DIR
python judge_tool.py --pair DATASET check --clause-file recovery.sexp --output NEW_RESULT_DIR
python judge_tool.py --pair DATASET alternative --clause-file continuation.sexp --output NEW_RESULT_DIR
```

Each command writes `result.json` and the optional complete TRAIN `table.json`, then prints the result path and outcome. `run` has no graded outcome. `--columns` accepts an ordered JSON list of output labels; otherwise the whole exported table is used. Receipts and full checked records stay in private data-root directories. A startup failure is an error record, not a checked-clause verdict.

The CLI implementation is [clause_command.py](../judge3/clause_command.py); [dataset_format.py](../judge3/dataset_format.py) validates and writes the public data without implementing engine semantics. Existing imported `load_pair` and `check_answer` functions remain compatibility APIs for stored consumers. The retired final/view-target CLI is not dispatched.

Native execution, kept matching, equality, provenance, raw/body and case acquisition belong to the shared evaluator owner. The tool calls `evaluator_train.evaluate_train_clause`; the exporter calls its public TRAIN acquisition surfaces. No pass writes a grade, and prose specification hashes are neither read nor used for invalidation. Code/runtime/source-record receipts provide execution provenance; historical records remain readable.

`study_paths.CODE_ROOT` locates code in this checkout and `DATA_ROOT` locates all pair datasets, contexts, checked records, review transcripts and other generated files.
