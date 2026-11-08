+ document-size-budget: 2100
+ lib: none

# arc-workspace
- ARC-AGI-2 work for the 2026 Kaggle competition.
- Python 3.12, `uv`.

## Commands
- Before you run the tests, the type check, a solver, or `scripts/materialize.py`, read [Project commands](prompts/agents/notes/project-commands.md#project-commands).
- Before you run a command that may use much memory or that starts several processes at once, read [Commands that use much memory](prompts/agents/notes/project-commands.md#commands-that-use-much-memory).

## Features
* comment: The user's words, session 12a37de8, 2026-11-06: "clean up the project documents so that it's clear what is the authoritative source or what's derived from what".
- Before you read or change anything about features over tables, read [Features map](docs/features-map.md).

## Handbook
- The handbook is what a solver session reads.

## Lib
* comment: The user's words, session dc433af1, 2026-10-04T21:27:39Z: "we need to have some pointer to souffle-undocumented.md so for agents looking to improve lib perf they can look here".
- When you work to speed up the lib, look in [Souffle: undocumented features](docs/souffle-undocumented.md) for Souffle features the official documentation leaves out.

## Conventions
- **Patches are the source of truth** for corrections.
    - `data/tasks/` regenerates from them via `scripts/materialize.py`.
    - Upstream is pinned via submodules, and corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **A grid is drawn as a grid**, wherever one is written: one row per line, cells separated by spaces, 0 as `0`.
* comment: The user's words, session 12a37de8, 2026-11-07: "Always use precise conventional literal terms, eg not row unless table row".
- **Reports and names use precise conventional terms.** "Row" is only a table row. Say training instance, feature vector, writing point, sampled query, experimental condition, engine build and patched code version, not row, point, draw, arm, site or overlay. A code name stands in text only where it names that code.

## Tests
- Before you write, ask for, change, delete or judge a test, read [Tests](prompts/agents/notes/tests.md#tests).
