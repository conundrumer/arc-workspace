# Handbook agents

The handbook is the solver docs and the lib, rendered by `scripts/context.py` into the system prompt of an agent. Two agents carry it, and they differ in how the lib is rendered.

## Renderings

- **Lib index.** One line per public unit of the lib, its name and the first sentence of its doc, grouped by module. A line under the index tells the session to read the module for a unit's signature and the rest of its doc. This is the rendering `patterns.md` gets.
- **Lib interface.** Every public unit with its signature, its `@input` defaults, and its full doc block.

The docs render the same way in both: `principles.md` with its formal statements, and every doc without its editing notes. The formal statement is the rule, so no rendering omits it.

## Agents

- `handbook` — the docs with the lib index. The default for any task under the solver docs.
- `handbook-lib` — the docs with the lib interface. For a task that writes or runs `.dl`: a solver, the lib, a proposal comp, a scratch reproduction.

The lib interface is opt-in. A task takes `handbook-lib` when its role writes `.dl`, and the default otherwise. A task that reads solvers and greps a module on demand takes the default.

## Where the choice lives

A role's file states which agent runs it, in one line at the top: `Agent: handbook-lib`. A role file with no such line runs as `handbook`. A spawner that runs a role reads that line: `retro.js`, the console's worker spawn, and a session that spawns a role by hand.

The session that `scripts/claude.py` starts, and the console's workers, are solver sessions, and take the `handbook-lib` rendering as their system prompt.

## Rendering switch

`render` takes one switch, `lib_index`, and `--write` writes both agent files from it. Nothing in either rendering is marked as omitted.
