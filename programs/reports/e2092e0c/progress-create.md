# e2092e0c progress

- interference: `uv run python scripts/run_dl.py deletions e2092e0c` in the worktree looked for the solver at the main worktree's `programs/solvers/e2092e0c.dl` and exited 2 with "no solver". Passing the worktree's absolute solver path as the stem worked. Cost: one extra run. Still wrong for a bare task id.
- delay: Develop, "The cases are the combinations of those branches that fit": nine binary points gave 512 combinations. Most witness reports were about combinations that failed Fit or were subsumed. Cost: about 5 min over the Develop and Witness budgets.
