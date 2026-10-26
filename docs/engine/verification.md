# Verification

How each step of the [build order](overview.md#build-order) is checked against the Souffle solvers, and how an agent's loop of edit, build and check stays fast. This doc ends no step. The snapshot and the commands are in place before the first comparison of step 2, and every later step uses them.

## Snapshot of the Souffle outcomes

- A one-time snapshot stores the Souffle outcomes as files: each case's output on each pair, whether it solves each split task, the witness outcomes, and each solver's run time.
- Each engine check compares against the snapshot, and never starts Souffle.
- A solver's snapshot is made again only when its `.dl` file changes.

## Order of a check run

- After each change, the check runs on the solvers that use what the change touches, and on every solver only where what it touches reaches every solver. A map from each construct, lib relation and component to the files that use it gives those solvers. The map comes from the survey's pass over the files.
- `arclog-cli check-diff` compares the checker's diagnostics on those solvers with the base engine's, and runs no check whose result `.cache/check-diff/` holds for the same engine sources and solver files.

## Mismatch report

- A mismatch report gives the solver, the case and the pair. A command runs that Souffle call again with every relation written out, and gives the first relation whose rows differ, by arclog names.
- Where the Souffle outcome departs from Principles, the report gives the difference as a fault of the solver or of the Souffle lib, as the Principles requirement of [Requirements](overview.md#requirements) gives.

## Lib comparison

- Each lib relation and component is compared with its Souffle version on small generated inputs, outside any solver.
- After a change, the comparison runs on each lib element the change touches, and on every element only where what the change touches reaches every element.
- This comparison is a command, not a test of the test suite.
- Agreement with Souffle does not show that a lib element is equivariant, as [Equivalence and subsumption](../../docs/handbook/principles.md#equivalence-and-subsumption) gives for agreement on some inputs. How the lib keeps equivariance is in [equivariance.md](equivariance.md).

## Build speed

- The constructions are in a crate of their own, as [Crates](overview.md#crates) gives.
- Agent loops use `cargo check`, the engine's tests a debug build, and each corpus run a build under the incremental `tool` profile, as `cargo run --profile tool -p arclog-cli -- <subcommand>` in `engine/` gives. A corpus run runs on the threads `ARCLOG_THREADS` gives, and on as many as the machine has where it is unset. A debug build refuses a corpus run.
- Each agent that builds in parallel has its own Cargo target directory, since Cargo locks a target directory while it builds. Each such agent owns one construction or one step.
- The corpus run is the check. The engine's tests are the kinds that [Tests](../../prompts/agents/notes/tests.md#tests) keeps, such as a reader or a check that must refuse wrong input.

## How each decision can fail

| Decision | Failure | What catches or bounds it |
| --- | --- | --- |
| Rust in the agents' loop | compile time slows iteration | the crate split, `cargo check` in the loop, and the corpus run as the check |
