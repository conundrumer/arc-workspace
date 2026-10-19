"""The corpus survey, `docs/engine/corpus-survey.md`, as the output of its
sections (`study.corpus_survey.document`), which
`scripts/corpus_survey.py` runs.

The fast sections read `gen/` (`corpus`, its bodies `bodies` and their
trees `trees`), `data/tasks/`, `.cache/parity/` and
`.cache/determination-plan/`, a module per group of sections that share
inputs: `forms`, `alts`, `recursion`, `tasks`, `shapes` (with `symmetry`
and `joins`), `determination` and `open_values`. The slow sections run
Souffle: `open_values`, `prefix` and `join_orders` over the relation rows
of `solver_runs`, simulated in sqlite by `simulation` with `algebra`, and
`profiles`; each keeps what it computes per solver (`kept`)."""
