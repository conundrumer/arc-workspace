# Empty-gold publication

`empty_gold_publication.py publish` calls the native
`arclog.empty_gold_json(corpus, tasks, task, request_work_cap=None)` once per
missing or changed task. The native operation discovers emptiness, applies the
closure, checks output equality and returns `selection: filtered` or a whole-task
`selection: original` with its reason. Under `selection: filtered`, a case whose
edit fails keeps its original program, with its `reason`; a case with no program
text makes the whole task `selection: original`. Python does not reproduce these checks or
require additional native proof flags. Native skipped cases remain in the record.

Gold enters the pipeline at `model/export.py` / native `corpus_streams`, after
converted case expansion. This publication is a separate versioned gold input;
creating it does not change CURRENT, rewrite an old corpus/pair identity or alter
old normalized-gold/features publications. Consumers must explicitly select the
new version before generating their streams, points, prefixes, labels or features.

The output is framed zstd JSONL through `judge3.framed_jsonl.JsonlWriter`. Each
record contains the exact native result, original source-file inventory/hashes,
authenticated installed wheel/build, native request work cap, policy and publisher source
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

`--request-work-cap` defaults to None (the settings' default request work cap),
as the native corpus replay does. A given cap applies to each native evaluation
request, and no request reads a clock. The record keeps `deadline_seconds: null`
and, with a given cap, `request_work_cap`. Native stops remain original-selection
results, never emptiness proofs.

`--check-set` can repeat. It is an independent audit, never a discovery seed.
The audit records each input's raw SHA/line count and reports listed removals,
listed clauses kept (with fallback reasons), not-yet-processed tasks and removals
absent from the lists. Exact task/case/index/relation/clause source keys are used;
Python does not guess a source correspondence from renamed relations. The `audit`
subcommand can reread the final check files and saved publication without native
calls. Finished plain/gzip/framed inputs use the shared reader; no file conversion
is done here.


## Materialize a SAMPLER_GEN directory

The `materialize` subcommand writes a new output directory from committed
publication records (or the owner's saved raw native task results). `--corpus`
accepts either a converted `out/` directory or its `gen/`. For the v2 conversion,
use `work/arclog-v2-4b3e64f15/out`. Set `SAMPLER_GEN=<output>/gen`.

For filtered tasks the original top-level `.arclog`/`.arcdata` pair remains the
native case-discovery container (its ALTs enumerate the named cases). Every
published case, including the concept case where present, gets its
`filtered_program` at `gen/cases/<task>/<native-file>.arclog`, with each site that
the reader requires bare written bare (`*P` for `(:P *P)`), as native `case_files`
writes it. Native `case_files` supplies filenames and the matching `.arcdata`,
retaining only parameters read by the filtered case. Python does not reconstruct ALT blocks, rename cases or
trim parameter values. Native corpus readers use these case overrides for the
actual gold stream. Replacing the task container with one flat case would lose
its other cases.

Fallback tasks copy the input task files and original case overrides exactly.
Required representative solver files are copied as original source support;
only completed publication tasks appear in `<output>/.empty-gold/ready-tasks.txt`.
Use that list (or the explicit holdout/task subset) for sampling rather than
mistaking representative support files for additional published tasks. The
input's sibling columns/names/plan directories are not part of SAMPLER_GEN.

Each task is prepared privately, copied as whole files, and gets a completion
receipt last. Receipts bind the native result, input hashes, native build and
all generated file hashes. The process holds one materializer lock. A completed
task resumes by receipt without native calls or rewrites; an interrupted prepared
task resumes from its staged bytes. Case files are installed before the task
pair/ready receipt. Only completed tasks are ready for consumption. Changed
completed bytes/results/builds require a new output version, so an old valid
materialization is not silently replaced. The operator journal is framed zstd
JSONL. No native filtering, row/FITS/OUT evaluation or mask replay runs here.

`--task-ids` takes whitespace-separated IDs. Run it first with the 118 holdout IDs,
then without that option against the same publication/output to add the rest.
The reader snapshots complete publication records currently available. Requested
but unpublished tasks are reported separately; rerun as more records arrive.
There is no need to regenerate a native gold result or a completed materialized
task to extend the corpus.
