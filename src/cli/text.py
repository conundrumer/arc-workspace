"""The line of each argument a command refuses, on stderr. Every other
line a command prints comes from `checker.render`."""

from controlled_markdown import mctx

# Files and grids

NO_SOLVER = mctx("no solver at {path}")
NO_GRID_FILE = mctx("no grid file at {path}")
BAD_GRID = mctx("bad grid: {error}")
BAD_ASSIGN_JSON = mctx("bad --assign JSON: {error}")
ASSIGN_NOT_OBJECT = mctx("--assign takes a JSON object")
NO_PAIRS_FILE = mctx("no pairs file at {path}")
NO_FILE = mctx("no witness file at {path}")
NO_TASK = mctx("{stem} has no task: no file at {path}")
GRID_ONE = mctx("`---` belongs to `record`; `{command}` takes one grid")

# `run`

PAIRS_ONE_STEM = mctx("--pairs needs one solver stem")
PAIRS_NO_JSON = mctx("`--pairs` takes no `--json`")
PAIRS_NOT_JSON = mctx("the file is not JSON: {error}")
PAIRS_BAD_KEY = mctx("`{key}` is no key of a pairs file; its pairs stand "
                     "under {sections}")
PAIRS_NO_FORM = mctx("the file holds neither a list of pairs nor an object "
                     "of {sections} pairs")
PAIRS_NO_LIST = mctx("`{section}` holds no list of pairs")
PAIRS_NONE = mctx("the file holds no pair")
OPEN_VALUE_UNRUN = mctx("pairs: not run, since an `OpenValue` field is off "
                        "its form; see the lint section")
PAIRS_LIST_OUTPUT = mctx("a pair of a bare list holds an output, and an "
                         "output is judged on a pair under {sections} alone")

# `grid`, `relation` and `record`

NO_CASE_NAMED = mctx("no case of {stem} is `{name}`")
NO_WITNESSED_TAKES = mctx("no witnessed case takes the branches of `{name}`")
NO_RELATION = mctx("no relation `{name}`")
NO_ENTRY = mctx("no witness `{id}` in {path}; a new witness takes "
                "`--separates`")
FORMAT_ALONE = mctx("`--format` rewrites the file and takes no id, grid, "
                    "`--separates`, `--assign` or `--all`")
ALL_ALONE = mctx("`--all` runs the file's witnesses again and takes no id, "
                 "grid, `--separates` or `--assign`")
RECORD_NEEDS = mctx("record takes a witness id, `--all` or `--format`")
NEW_NEEDS_SEPARATES = mctx("a new witness takes `--separates`; without it, "
                           "record runs the witness the file holds under "
                           "that id again and takes no grid file")
ONE_SEPARATOR = mctx("record takes one `---` separator at most")
REMOVE_ALONE = mctx("`--remove` takes a witness id alone, and no grid, "
                    "`--separates`, `--assign`, `--all` or `--format`")

# `witness`, `derive` and `store`

BOTH_FILES = mctx("witness: give `--file` or `--witness-file`, not both")
WITNESS_FILE_STEM = mctx("witness: `--witness-file` takes a stem")
WITNESS_NEEDS = mctx("witness: give a task id, `--file`, or both")
WITNESS_FILE_NEEDS_STEM = mctx("{command}: `--witness-file` takes a stem")
TRY_ALONE = mctx("witness: `--try` takes a task id and no `--file` or "
                 "`--every-case`")
TRY_ONE_GRID = mctx("witness: `--try` takes one grid")
DROPPED_FROM_EVERY = mctx("witness: `--dropped-from` takes `--every-case`")
DROPPED_FROM_TASK = mctx("witness: `--dropped-from` takes a solver file of "
                         "task {task}")

# `since`

GIT_FAILED = mctx("git failed: {error}")
