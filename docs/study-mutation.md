# Study mutation certificates and reproducible checks

`StudyProgram.draw_specs` searches complete, unique K-edit assignments at an
AST clause. An assignment enters the selectable domain only after its exact
derived interfaces, declarations, named bindings, resolved whole-program types,
whole-program checks (including safety), and decode stream are certified.
`construct` consumes that immutable certificate; it performs no repair or retry.

Do not use gold's inferred label types as a mutation safety oracle. Deleting
or changing atoms can change an INIT parameter's inferred type and therefore
the usable binding modes in another body. The complete candidate must supply
the inference used by the safety walk. Pure deletion can prune an intermediate
assignment when a required derived interface is lost, without consulting types.

AST clause/key/candidate headers are materialized derived fields. A body edit
must retain their exact reader-derived exports, not merely their old values.
Otherwise the checker can treat a branch-local label as an externally given
head label while a sexp reader correctly derives fewer columns. Such an
assignment never enters the mutation domain; headers are never rewritten.

The sexp writer separates adjacent symbol tokens even if preserved source
positions would join them after an operator grows (for example `<` to `>=`).

`StudyProgram.from_stream` reads complete streams with the decoder's grammar,
binder and exact forced echoes, checks the complete AST and derived interfaces,
and requires exact stream reproduction. It does not search for a completion of
every already-complete prefix, or evaluate OUT. The online decoder is unchanged.

Build through `scripts/run_heavy.py` using `scripts/build_study_runtime.py
--revision COMMIT --output NEW_DIRECTORY`. The builder archives that commit,
builds into an exclusive target/wheel directory, installs into an exclusive
venv, copies the committed corpus checkers and writes `ready.json` only on
success. It refuses an existing destination. Later builds cannot reinstall a
running check's extension or replace its checker source. Every checker uses
one process per task, streams task results, reports progress and retains the
case and domain deadlines. Supply `--tasks` explicitly for archived checkers.

## Draw-prefix diversity (policy v5)

The old depth-first traversal could fill a short draw prefix with completions
of the same early edit. Reusing one seed for every point also correlated those
short prefixes. The production traversal now rotates among nonempty edit-kind
buckets (`argument_zero`, `argument_variable`, `relation`, `comparison`,
`delete`), then among their first-site alternatives. Each cursor resumes a
canonical suffix search; complete assignments remain unique and checked before
selection. Reserved zero gets one kind scheduling slot regardless of how many
columns admit it. An exhausted kind yields its slot to the others. This is a
stratified draw order, not uniform sampling of all complete K-edit assignments;
scarce domains can still contain predominantly zero substitutions. It preserves
the deterministic-prefix contract when a caller increases `count`.

Stats distinguish `domain_primitive_kind:*` (unique alternatives before whole
assignment constraints), `drawn_root_kind:*` (the interleaved root choices), and
`drawn_edit_kind:*` (every edited atom in selected complete assignments).
`audit_draw_order` returns these counts for both the legacy depth-first order
and production order over the same real ASTs and checks. It exposes no legacy
mutant handles. `scripts/study/check_mutation_diversity.py` runs the comparison
in parallel over tasks and streams each point/K report. Draw shares are measured
before evaluation, filters, quota and publication; a retained judge batch can
have a different distribution. A domain/deadline stop makes the audit incomplete
and is reported as a failure, never as a diversity improvement.

The batch renderer's reserved-zero meanings are documented in
[`study-reserved-zero.md`](study-reserved-zero.md).

## Stage-2 streaming audit and resume

The old rerun's recorded timings put 12,179 of 13,215 phase-seconds in
`mutant_stream_replay`; 1,038 of its 1,135 case deadlines occurred in that
phase. The complete-program reader above removes the online completion/OUT
work. Each immutable `StudyProgram` now retains one written stream for its
first registry/settings pair. Certification, printing and repeated round-trip
accessors share that stream. Returned arrays are independent copies.

`StudyProgram.from_sexp(text, settings, session=session)` and
`StudyProgram.from_stream(session, ids, model)` share exact native check results
within the case. Reading, header/interface validation, name resolution and
exact stream reproduction remain mandatory. `Session.reset_program_replay()`
releases the parser checkpoints and check cache between cases, including
faulted cases. `stream_reader_policy()` advertises the complete-program entry
point; the audit refuses an older online replay implementation.

The stage-2 checker still draws every point/K/operation and constructs every
selected certificate. A successful full AST/sexp/stream audit is reused only
for an identical serialized identity on the same immutable gold handle in
that case. The recorded old run contained 11,673 duplicate verified identities
among 39,846 mutant rows, all from `mixed` contexts. Duplicates retain their
own mutant records, with `verification_cached` and a case-local
`verification_ref`. Failures never enter the memo. Full-program samples are
limited to distinct verified identities. No certificates are reused across
cases or interpreter runs.

Parent supervisors drain bounded eight-record queues and flush each draw,
mutant, failure and case record directly to its JSONL. A separate heartbeat
prints case/task progress and active phases every second, including during
native calls. There is no task-long event list. The requested SIGALRM case
budget is retained; a parent guard allows at most one native-request deadline
of dispatch grace. A stuck case is recorded alone, and a fresh worker starts
at the next unattempted case. Startup failures are task events, not fabricated
failures for every unstarted case. An explicit `--task-seconds` remains a hard
whole-task override.

Use `--resume` with the same output prefix to append safely. A case row with
`complete=true` proves the requested audit matrix finished. Interrupted,
deadline and watchdog rows have `complete=false` and are retried. Add
`--retry-failed` to retry completed matrices with substantive audit failures as
well. Torn final JSONL rows are repaired; intact rows are retained. Runtime
binary hash, checker source, mutation policy, selections, seed and audit bounds
must match the output's `.config.json`. A new policy/build requires a new
output prefix, so an old mutation domain cannot masquerade as new coverage.

Build a committed runtime with `scripts/build_study_runtime.py` into a new
exclusive directory, then run its `checks/check_stage2.py` with that directory's
`venv/bin/python`. Supply `--tasks` explicitly, and use `--task-file` for the
recorded rerun's task list. The summary labels new invocation counts and
retained completed cases separately; rates count only new work.
