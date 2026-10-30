# Data-pair Workflows

`judge_workflows.py` and `make_batches.py` are the live adaptation of
`DATA_ROOT/judge2/judge_workflows.py` and `make_batches.py`. Historical runner
files and completed runs stay in the data root. The adaptation retains bounded
child `Promise.all`, a sequential parent, a strict 500,000-byte script ceiling,
frozen routing and input hashes, actual Workflow journal completion proofs,
and preflight of all replies before publication. It removes rendered prompt
reservations, label schemas and label-store writes.

A calls JSONL contains only `{"pair_dir":"/absolute/complete/pair/directory"}`
per line. Selection/admission belongs to the labeler; this runner does not
compute a grade or native evidence. Each pair starts one Sonnet session with
the brief and file directory, a sourced environment, and a short `judge`
wrapper. Full rows stay on disk. `create` only generates files; it launches
nothing. Pass a clean git worktree whose HEAD is the pinned commit, such as one
kept by `scripts/merge_change.py --keep` or made with
`git worktree add --detach`:

```sh
PYTHON model/study/judge3/judge_workflows.py create \
  --calls DATA_ROOT/judge3/pilot/calls.jsonl \
  --output-dir DATA_ROOT/judge3/pilot/run \
  --tool-snapshot WORKTREE \
  --python DATA_ROOT/ast/run/runtime-COMMIT/venv/bin/python \
  --sessions-per-child 3
```

`create` records `git rev-parse HEAD` of that worktree and refuses a worktree
that has uncommitted or untracked files. `ingest` and the labeler API refuse the
run if the worktree is not clean, its HEAD differs from the recorded commit, or
`judge_tool.py` differs from the recorded hash.

The final stdout object names `parent.js`, launchable through the coordinator's
Workflow tool as `scriptPath`. Children share the host's concurrency/token cap;
the generator additionally caps sessions per child. Parents invoke children
sequentially and stop scheduling later children after a null/error result.
In-flight agents finish normally. `make_batches.py --calls FILE --output DIR
--batch-size N` splits explicit calls into separate files when a parent would
be too large; it does not select or export corpus pairs.

Each session writes `answer.json` with `schema: judge-answer-v1`, `pair_id` and
`clauses`. A clause has `kind: recovery|alternative`, `clause_file`, `columns`
(list or null), `result_path`, and one or two `reasons`. Files must belong to
that session. The actual checked clause file, ordered output labels, operation,
pair and source are validated against `load_checked_result`. Outcome strings
are taken from the checked envelope; an answer supplies no label, grade,
outcome or completion assertion. Exploratory results are not selectable.
The typed Workflow reply contains only pair ID and the reserved answer path.

After a run, save the actual Workflow tool output under DATA_ROOT. Supply its
native `journal.jsonl` files, whose started/result entries identify each agent,
label and actual returned object:

```sh
PYTHON model/study/judge3/judge_workflows.py ingest \
  --run DATA_ROOT/judge3/pilot/run \
  --results DATA_ROOT/judge3/pilot/workflow-result.json \
  --journals /absolute/native/workflow/journal.jsonl
```

Ingestion verifies frozen inputs and script routing, exact scheduled
completed/skipped partition, source-bound checked result identities, and actual
host started/result matches. It publishes immutable `judge-submission-v1`
records in `run/submissions/` after validating all answers. Re-ingestion accepts
identical records; conflicts fail. Native journals are copied by content hash
into `run/host-receipts/`, retaining their original locator. The actual host
reply proves that the answer returned; a file merely appearing on disk does
not. Missing/unsupported journal events fail closed, without inferring a
completed negative. Null/interrupted/failed replies and unstarted pairs are
recorded separately in `dispositions.json`, never as completed empty answers.

The completed submission fields are pair/source/session identities,
`host_completion_status: completed`, `answer_artifact`, `selected_results`
(DATA-relative path/SHA, submitted kind and native outcome), `no_clause_found`,
`termination_receipt`, Workflow result references and checked-result identity
references. Empty clauses gives `no_clause_found: true` only after a real host
reply and a valid empty answer artifact. The labeler owns all grading and the
submission-index consumer. A completed answer containing unknown checks can
still yield Unknown; completion does not manufacture a verified clause or a
negative proof.

No prose specification hash is recorded or read. Code/runtime provenance stays
in stored results; completed facts are not rejected because current source
bytes differ. Public inputs and actual execution files remain hash-bound.

Per-session native transcripts and token reports belong beside the run data.
Record cumulative usage once per native message ID, the first request's full
prefix, and final context separately. An initial cache hit changes cache-write
cost without shrinking the harness. After actual pilot execution, write the
transcript analysis and token-efficiency notes for each session in the same
form as the single-pair trials; never invent those reports before it runs.

## Read-only labeler API

With `study_paths.CODE_ROOT` on the import path:

```python
from judge3.judge_workflows import load_submission
resolved = load_submission(path, expected_pair_id=pair_id,
                           expected_source_sha256=source_sha256)
```

The loader returns `status: available|unavailable`,
`host_completion_authenticated`, and a reason on unavailable. Available results
also contain the unmodified `submission`, `checked_results` (canonical
`load_checked_result` envelopes in the answer's selected order), and `identities`
for the submission, frozen run manifest, native journal, Workflow result files
and answer. It imports no native evaluator, writes nothing, and takes no lock.
There is one routing/host-result/journal/answer validator shared with ingest.

The producer retains the `judge-submission-v1` top-level fields. Its nested
`termination_receipt.run_manifest` is the canonical DATA-relative path/SHA256
of the immutable `run.json`, binding the script routing and frozen inputs.
Reading uses the hash-bound journal copy; cleanup of the original native host
journal does not invalidate completion. Current producer code and current brief
bytes are not compared with past producer hashes. Changes to a frozen artifact
itself do make that record unavailable. No historical completion is invented
for older artifacts without this proof closure.

The three-session pilot is the first end-to-end qualification of the new
structured-answer/ingestion contract. Script creation and read-only routing
validation do not mean an agent has run or an answer has been accepted.
