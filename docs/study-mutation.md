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
