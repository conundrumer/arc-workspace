# Empty-gold publication

`empty_gold_publication.py publish` calls the native
`arclog.empty_gold_json(corpus, tasks, task, deadline_seconds=None)` once per
missing or changed task. The native operation discovers emptiness, applies the
closure, checks output equality and returns `selection: filtered` or a whole-task
`selection: original` with its reason. Python does not reproduce these checks or
require additional native proof flags. Native skipped cases remain in the record.

Gold enters the pipeline at `model/export.py` / native `corpus_streams`, after
converted case expansion. This publication is a separate versioned gold input;
creating it does not change CURRENT, rewrite an old corpus/pair identity or alter
old normalized-gold/features publications. Consumers must explicitly select the
new version before generating their streams, points, prefixes, labels or features.

The output is framed zstd JSONL through `judge3.framed_jsonl.JsonlWriter`. Each
record contains the exact native result, original source-file inventory/hashes,
authenticated installed wheel/build, native deadline, policy and publisher source
identity. Native reports need no request/runtime binding; the outer record owns
those bindings. Every task is flushed before advancing. Valid committed results
resume without another native call. A changed input, build, policy or publisher
source changes the task resume key. Do not overwrite an earlier gold publication.

Native `singleton_double_read_lint` is report-only. Findings are separately
written to `singleton-double-read-findings.jsonl.zst`, with task, case, clause
index, relation and the two labels. Findings commit before the task record;
request-bound finding IDs and ordinals allow interrupted writes and journal
reconstruction without duplicate findings or reacquisition. Native complete zero
findings and unavailable lint coverage are distinct in the task record. Lint
findings do not change gold selection.

`--deadline-seconds` defaults to None (no deadline), as the native corpus replay
does. A positive deadline applies to each native evaluation request. Native stops
remain original-selection results, never emptiness proofs.

`--check-set` can repeat. It is an independent audit, never a discovery seed.
The audit records each input's raw SHA/line count and reports listed removals,
listed clauses kept (with fallback reasons), not-yet-processed tasks and removals
absent from the lists. Exact task/case/index/relation/clause source keys are used;
Python does not guess a source correspondence from renamed relations. The `audit`
subcommand can reread the final check files and saved publication without native
calls. Finished plain/gzip/framed inputs use the shared reader; no file conversion
is done here.
