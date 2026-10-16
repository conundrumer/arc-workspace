+ budget: 4536

# arc-workspace
- ARC-AGI-2 work for the 2026 Kaggle competition.
- Python 3.12, `uv`.

## Commands
- `uv run pytest -q`
- `uv run pyright`
- `uv run python scripts/materialize.py`
- `uv run python scripts/run_dl.py`
    * comment: The user's words, session 6f8c73e4, 2026-10-02T22:45:12Z: "it needs to be known it is an expensive op".
    - Run every Souffle solver. It takes a long time, so run it only when the user asks to run every solver.
    - `--help` for per-solver tooling.
- `uv run python scripts/run_dl.py <stem>`
    - Run one.
- Souffle binary required for `.dl` solvers (`brew install souffle`).

## Handbook
- The handbook is what a solver session reads.

## Lib
* comment: The user's words, session dc433af1, 2026-10-04T21:27:39Z: "we need to have some pointer to souffle-undocumented.md so for agents looking to improve lib perf they can look here".
- When you work to speed up the lib, look in [Souffle: undocumented features](docs/souffle-undocumented.md) for Souffle features the official documentation leaves out.

## Solver console
- `tools/console/` is deprecated. It runs solver sessions as `claude -p` workers in staged chains.
- The module docstrings in [solver_console](tools/console/solver_console) index what each module holds: what a worker session reads and may do, how a stage hands off, and how the user reaches a session.
- Read them before answering a question about how console sessions run.
- A running server re-execs itself when `server.py` or a module under `solver_console/` changes, at its next quiet moment (`solver_console/reload.py`), so a code change needs no restart.
- The page and `ui/` are served from disk on each request.

## Tickets
- `tickets/` is the ticket tracker, which holds the tickets agents file, and [Ticket notes](prompts/agents/notes/tickets.md) states its conventions.

## Launching
- Before you launch an agent by a call that no command printed to you, read [Launching](prompts/agents/notes/launching.md#launching), where your context does not hold it.

## Conventions
- **Patches are the source of truth** for corrections.
    - `data/tasks/` regenerates from them via `scripts/materialize.py`.
    - Upstream is pinned via submodules, and corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **A grid is drawn as a grid**, wherever one is written: one row per line, cells separated by spaces, 0 as `0`.

## Tests
* comment: The user's words, session 7c26445d, 2026-09-15T21:30:26Z to 22:04:42Z: "we have a ton of useless tests ... requires maintanence like changing it when the impl changes. aggressively cut them", and "regression tests are theoretically useful, overwhemlingly useless".
* comment: The user's words, session 7fd429fb, 2026-10-16T16:18:26Z: "the rule should also be updating according to the evidence, like how to classify tests", and 16:29:03Z: "approve", which chose the coordinator's option "Yes" of 16:24:31Z, the cut and the rule wording of ticket 6-1450.
- A test costs an edit each time the code it pins changes, and a later session pays it.
- So the default is no test, and a test has to earn its place.
- A test stays only when its failure would be silent in use, and it is of one of these kinds:
    - An invariant over the real repo whose break makes another check skip something, like a lib component that no gate stem runs.
    - A stored result that must be computed again when a file it rests on changes.
    - A race or a half-written file: two writers, a lock, a rename.
    - A parser or a reader that must refuse wrong input.
    - A check, hook, or gate that must refuse or report: the test feeds it the bad case and asserts the refusal.
- When a run would show the failure (a wrong grid, a failed command, an error message, a changed line in a file, the page or the feed), the run is the check, and the test is not written.
- A test asserts what a caller sees: outputs, files, exit codes, refusals. It does not assert function signatures, module names, enum values, message wording, or cache internals.
- A test does not read `data/upstream/`, the live transcripts, or the session's environment variables. It builds what it reads in `tmp_path` and clears the environment it passes to a subprocess.
- A concurrency test does not depend on timing. It forces the interleaving with a barrier or a held lock.
- A test written to fail before the code exists is not by that fact a test that stays.
- Ask the same of a test your change broke. When it is not of a kind above, delete it; don't update it.
- Assertions you need while you work go under `tests/scratch/`.
- It is collected and not committed.
