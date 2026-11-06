# Directive: the feature library

Build the encoder from tables to features that [the feature specification](feature-spec.md) defines. A feature is arclog, so the first version runs through the engine's evaluator as it is. Speed comes later.

## Read first

1. [Feature specification](feature-spec.md): what to build. Its grammar is the generating set.
2. [Arclog column types](arclog-types.md): what the engine knows about a column.
3. `docs/sample-build/contract.md`: the vectors. The specification's section "What in the sample contract changes" gives what differs.
4. `docs/engine/equivariance.md`: the obligations that each lib element meets.

## What to build, in order

Each step ends in something that runs. Write the code in the engine, in Rust, since the export will call it.

1. **Expander.** A function from a ground expression to arclog forms, by the rules of "How an expression expands". Run it on a table at one assignment and get the value. The operators need no change to the language, and neither do the leaves other than `output`. The worked expansions are its first cases, and each must give the value the specification states.
2. **Library file.** `engine/lib/features.arclog`, with its reader: `fragment`, `feature`, `QUERY`, `EXPORT`, the holes and the splices. `lib-join`, `component` and a proposer leaf read the registry for their names and columns.
3. **Additions.** The other items of "Additions to arclog": the leaf `output`, the program relations, the lib name type, and the check on `Pose`.
4. **Encoder.** Enumerate the ground expressions up to a size, for a table at an assignment, at every binding the checker accepts. Then the vector entries with their names, and the combination of per-input values over the examples. The size is a parameter, and small sizes come first.

5. **Evaluation.** Build and run [the evaluation protocol](evaluation-protocol.md), on the tasks of `work/feature-spec/eval-tasks.txt` in their order, the first 60 first. Write results under `../../work/feature-spec/results/`, per (task, d), as each ends. Start at size 1, report the first curves as soon as they exist, and add each larger size. Scene recognition on `input` and Rule recognition on the base tables come first, since they need no solver tables and no mutants. Then Separation, then Candidate recognition.

The export of the vectors is designed from the results.

## Checks

- Each worked expansion gives its stated value through the expander.
- The transformation law holds on a sample of tables: apply an element of D4 and a color permutation to a table's rows and to the grids, read the result as stored rows, and compare. A solver can't run on a transformed task as it stands, since its stored values hold orientations and colors. An invariant feature keeps its value, and an equivariant one moves by the group's action. A difference is a fault of the expander or of a lib element. Report it.

## Out of scope

- Speed, and the choice of a size to run.
- The model.
- `DEMONSTRATED`, and cases other than the concept case where a step needs a limit.
- The crate `engine/arclog-features`, which stays as it is until the library replaces it.

## Constraints

- Use the train-split tasks of `model/contracts/dev/out-expand/tasks.txt` alone. Do not run task 981571dc.
- No value depends on an authored label or an authored order.
- Use the specification's terms.
- `scripts/arclog.py rows` takes `--runtime`, and its default runtime is older than the engine. `work/lm/data-study/ast/run/runtime-814d592af` has Ident sources on by default.

## Questions

- A rule of the specification that can't be implemented as written is a design question. Send it to the session `arclog-analyst`, with the run that shows it, and go on with what doesn't depend on it.
- The specification changes only through that session.
