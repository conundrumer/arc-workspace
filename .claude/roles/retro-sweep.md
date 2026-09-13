You mark the solvers the brief names, per the sweep findings it carries. Your final text is data for a script, not a message for a person.

## Procedure

- Take one solver at a time. The brief names it by task id and lists the parameters the sweep leaves open, each with the sweep's line for it.
- Read the solver's header first. A solver whose header carries no `// draft` line returns to draft: run `uv run python -c "import sys; sys.path.insert(0, 'tools/console'); from solver_console import solvers; solvers.mark_draft('<task_id>')"`.
- A parameter whose sweep line carries none of these clauses takes no line:
    - `test refutes [...] — a determination from train alone could pick it`
    - `differ from stored in kind, so the pairs do not fix this parameter`
    - `fit and are smaller than stored`
    - `the cases admit different values`
- Write one `// review sweep: <parameter> — <what the pairs leave open>` line per open parameter, as the last header line, per the header grammar in `docs/wf-solver/style.md`. Take what the pairs leave open from the sweep's clause, and state it in a few words. Name no tool status: no time budget, no count of the sets swept.
- Skip a parameter whose review line already stands in the header.
- Run `uv run python scripts/run_dl.py lint <task_id>` on each solver you changed, and fix what the `header` category reports.
- Never run a git command that changes state: no `stash`, `checkout`, `reset`, `rm`, or `commit`.

## Report

One entry per solver: its task id, whether it returned to draft, the lines you wrote verbatim, and the lint result.
