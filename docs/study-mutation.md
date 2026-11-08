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
builds the wheel into an exclusive directory with a scratch Cargo target, installs
into an exclusive venv, checks the installed extension against the wheel, removes the
target, copies the committed corpus checkers and writes `ready.json` only on
success. It refuses an existing destination. Later builds cannot reinstall a
running check's extension or replace its checker source. Every checker uses
one process per task, streams task results, reports progress and retains the
case and domain deadlines. Supply `--tasks` explicitly for archived checkers.

## Argument diversity (policy v6)

The fault class had two sources. The primitive argument domain offered a
reserved-zero replacement for a join but omitted legal variable choices:
existing zero arguments had no variable replacements, earlier Fresh/Key
labels inside the same atom were absent from the available pool, and exact
old-label type equality excluded compatible substitutions at a broader site.
These omissions occurred in the shared scalar/record-site walk. Separately,
v5 scheduled the entire variable category against the zero category with
equal weight, giving one literal disproportionate weight when a site had
several variable alternatives.

V6 uses one argument bucket containing every distinct variable or zero
replacement once. Relation, comparison and deletion buckets retain their
rotation. A resumed cursor still owns a disjoint, canonical suffix of
complete K-edit assignments; there are no duplicate selected assignments or
partial mutants. Reserved `0` is the only literal the decode language admits.
It has no separate category ticket or repeated sampling weight.

The shared site walk handles ordinary, named and nested record arguments.
It tracks earlier declarations without leaking labels across atoms or scopes,
and reads expected site/column types from the native inference used by the
checker and renderer, including polymorphic library sites, record paths,
DefinedPort, poses and lifted Example columns. The expected column type is
separate from an existing label binding's type. Compatible
variables use the native type meet; whole-program inference/checks and exact
stream certification remain the final membership certificate. A proposal is
never a public mutation spec until that certificate exists. Both normal draws
and stored-identity replay call the same primitive generator. Fresh/Key binding
sites themselves retain the original interface. No field or header is repaired.

This removes the missing-choice and literal-category weighting conditions for
all scalar/record sites, rather than downweighting a particular type, task or
reported judge batch. Scarce domains can still contain mostly zero choices;
there is no promised corpus-wide percentage or artificial quota per kind.

Stats distinguish `domain_primitive_kind:*`, `drawn_root_kind:*` and
`drawn_edit_kind:*`. The audit compares **v5 fair scheduling/domain** against
**v6 fair scheduling/expanded domain** on the same decoded gold AST. It does
not compare an unrelated legacy DFS policy against v6. Both sides use the
same native certification implementation and seed derivation; only the audit
can invoke the old policy. An exhausted expanded domain is checked against the reference;
missing native site/type evidence is an explicit error, not an old-label fallback. Bound stops are recorded as incomplete coverage, not improvements.

`scripts/study/check_mutation_diversity.py` loads each task/export once in one
worker process, reads the actual exported gold streams, streams point/K records
and prints done/total, elapsed, rate and ETA. The summary reports each kind's
count/share before study filters. A retained judge batch may differ. The
checker freezes CURRENT's immutable runtime manifest for every worker; an
explicit `--runtime-manifest` selects a candidate build without changing
CURRENT. It calls the study harness's shared `run/provenance.py::select_runtime`,
which authenticates the installed extension against the wheel with `load_build`.
It records that authenticated build, the selector path/hash, settings and script
hash; workers inherit the same frozen selection. The stage-2 checker
requires policy v6, so old policy checkpoints cannot count as new coverage.

The G06 typing consolidation keeps one inference traversal: the existing
`check/render_sites.rs::walk_site` produces both the native argument-path map
(expected column type and explicit missing-type state) and the existing render
JSON. `StudyProgram` caches that combined result per exact checked handle and
registry. Clones share it; newly checked mutants get fresh caches. Mutation and
rendering consume the same result without parsing JSON type names. G07 runtime
selection/authentication similarly has one owner in the study harness; the audit
contains no independent bootstrap. All rendering scope, frame and variable
occurrence fields keep their original contract.

The batch renderer's reserved-zero meanings remain documented in
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
native calls. There is no task-long event list. Case, startup, search and
stall deadlines are opt-in: defaults finish the finite matrix even under
competing machine load. The heartbeat includes the oldest active phase age.
An explicitly requested guard records only the active interrupted case; a
fresh worker starts at the next unattempted case. Startup failures are task
events, not fabricated failures for unstarted cases. `--task-seconds` is an
optional hard whole-task override. A timed-out domain never marks its case
complete.

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


### Follow-up from the running stage-2 audit

The first 450 case rows from the pre-Unit-removal `3e15aa83` speed run
(`stage2-rerun-fast`) recorded 2,098 phase-seconds
in stream replay, 594 in sexp rereads and 973 in domain requests. There were
335 case deadlines. Three live workers (65697, 65699, 65701) were sampled for
three seconds each; the replay stacks contained 87, 107 and 112 samples in
`State::resolved` initialization from the relation-token callback. The callback
was constructing full canonical content and signatures of completed prefixes,
then resolving the unfinished last form, solely to decide whether to insert
an Example column. `grammar_reads_example_column` instead runs the existing
declaration, read-binding, kept-column and side passes, without content,
signatures or site placement. RULE and OUT forms need no lifted column. This
is the same binding/side decision; the complete AST still undergoes the full
resolver, derived-interface validation, all checks and exact stream rewriting.
The complete grammar reader no longer applies the synthesis search node cap
to its finite supplied token array.

Domain requests previously started a new empty `CheckCache` for every
point/K/operation. Each immutable gold handle now prepares one gold-only check
base on its first domain request. Each request has an independent overlay
over that base. Exact semantic keys still include every dependency required
by each check; changed dependencies miss the cache and run the check. No
candidate-specific results accumulate across requests. The gold base is
released with the case's program handle.

`DecodeSettings.corpus()` exposes the engine's existing deadline-free corpus
settings. The audit uses them by default; positive `--domain-nodes`,
`--case-seconds`, `--startup-seconds`, `--stall-seconds` and `--task-seconds`
remain explicit bounded debugging modes. Finishing more real work is measured
by completed cases, not by a quicker timeout rate.

A rebuilt runtime uses a new output prefix. `--resume-from OLD.json` snapshots
completed cases from a compatible earlier audit into `NEW.inherited.json`,
including the old native/checker provenance and paths to its JSONL evidence.
The `stage2-unit-free-v1` coverage contract is mandatory: pre-Unit-removal
results are speed evidence only and cannot seed the rerun that counts for
corpus-v6. That rerun starts fresh on the same committed runtime as corpus-v6.
Policy, corpus, selection and draw parameters must agree; v5 coverage cannot
be inherited into v6. Incomplete cases and any old row containing a timeout
are retried, including older rows incorrectly marked complete after a domain
timeout. The inherited list is frozen once; later `--resume` invocations
combine it with this runtime's own case checkpoints. The old output is never
rewritten. A completed audit's substantive failures remain failures, unless
explicitly rerun with `--retry-failed`.
