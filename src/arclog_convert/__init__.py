"""The converter of the Souffle solvers to arclog and arcdata
(`arclog_convert.convert`), and the directories it reads and writes
outside the checkout it runs in.

The converter reads the solvers, the witnesses and the lib from the
checkout it runs in, and the lib signature from this package. It writes
under `work/arclog/` of the main worktree, or under the directory
`OUT_ENV` names. The lint (`arclog_convert.lint`) reads the files there.

The command, the name map and the plan files stand in `convert`. Its other
subjects stand in modules of their own: `lib` (the lib's declarations),
`forms` (the output forms and the text passes on them), `terms` (the helpers
on terms and clauses), `leaves` (`Converter`), `clauses` (`ClauseWriter`),
`solver` (`Solver`, composed of the mixins of `solver_params`,
`solver_instances`, `solver_render` and `solver_cases`) and `paths` (the
directories). No module but `convert` imports it, and a module reads a
directory of `paths` as an attribute, so that `--out` reaches every reader."""

from pathlib import Path

from engine import checkout

OUT_ENV = "ARCLOG_OUT"
"""The environment variable that names the directory the converter writes
under in place of `work/arclog/` of the main worktree. The pool's workers
read it."""


def out() -> Path:
    """The directory the converter writes `gen/`, `gen_macros/`, `plan/`,
    `names/` and `helper_rows/` under."""
    return checkout.from_env(OUT_ENV, lambda: checkout.work() / "arclog")


def signature() -> Path:
    """The signature of the lib the converter writes against, which
    `arclog_convert.gen_signature` writes."""
    return Path(__file__).resolve().parent / "lib-signature.dl"
