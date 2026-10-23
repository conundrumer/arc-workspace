+ document-size-budget: 2100
+ lib: none

# arc-workspace
- ARC-AGI-2 work for the 2026 Kaggle competition.
- Python 3.12, `uv`.

## Commands
- Before you run the tests, the type check, a solver, or `scripts/materialize.py`, read [Project commands](prompts/agents/notes/project-commands.md#project-commands).

## Handbook
- The handbook is what a solver session reads.

## Lib
* comment: The user's words, session dc433af1, 2026-10-04T21:27:39Z: "we need to have some pointer to souffle-undocumented.md so for agents looking to improve lib perf they can look here".
- When you work to speed up the lib, look in [Souffle: undocumented features](docs/souffle-undocumented.md) for Souffle features the official documentation leaves out.

## Tickets
- `tickets/` is the ticket tracker, and [Ticket notes](prompts/agents/notes/tickets.md) states its conventions.

## Launching
- Before you launch an agent by a call that no command printed to you, read [Launching](prompts/agents/notes/launching.md#launching), where your context does not hold it.

## Conventions
- **Patches are the source of truth** for corrections.
    - `data/tasks/` regenerates from them via `scripts/materialize.py`.
    - Upstream is pinned via submodules, and corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **A grid is drawn as a grid**, wherever one is written: one row per line, cells separated by spaces, 0 as `0`.
* comment: The user's words, session b7409037, 2026-10-23: at 14:22:45Z "also we cannot use \"lattice\" in both senses"; at 14:23:36Z "no more using \"lattice\" to mean lattice-as-grid"; at 14:24:52Z "tell session11 to remove all lattice-as-grid \"lattice\" usages".
- **"Lattice" names an order alone**. Name a periodic structure by its periods, and a grid of tiles a tiling.

## Tests
- Before you write, change, delete or judge a test, read [Tests](prompts/agents/notes/tests.md#tests).
