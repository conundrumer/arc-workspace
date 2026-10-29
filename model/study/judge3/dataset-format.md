# Judge data

All public files are UTF-8 JSON except the two plain arclog program files. The
format identifier is `judge-dataset-v1`. `dataset_format.py` is the writer and
validator. It imports no engine and implements no equality or assignment policy.

`pair.json` contains `pair_id`, `task`, `case`, `change`, a `tables` index and
relative paths for `comparisons`, `readers`, `train`, `programs` and `libraries`.
Each table index entry supplies its `id`, `source_name`, `case`, `roles`, and
`path`. Roles can overlap: a table may be both a target and an available read.
G and X have IDs `G` and `X`. Other IDs are opaque and local to this dataset.
The programs index names `gold` and `mutant`. Change metadata gives the changed
point and kind, plus the original and changed form text. No execution-context
path, test output, grade, source hash or renderer version is public.

A table file has `kind: table`, `id`, `source_name`, `case`, `roles`,
`callable_atom`, `fields`, `entries`, `required`, `missing`, `complete`, and
`row_count`. `fields` is an ordered physical schema: `index`, `name`, native
`type`, and native `frame` and `callable_row_path` when supplied. Display names
are not substituted for callable sites. The full binding atom is supplied for
available reads and X; comparison-only targets have no callable atom.

Every entry has `assignment` (zero-based kept assignment local to its case),
`train` (zero-based train input), `model` (local to this table/context),
`row_count`, and complete `rows`. Every row has one native cell object per
physical field. Cells preserve `value` and any native `extent`/`extent_status`
evidence. Values are arrays, including scalar values. A zero-column true table
has one row `[]`; a false table has no rows. No set of model rows is flattened
into another model or assignment. Model ordinals do not align across tables.
Each required context is `[assignment, 1, train_index]`; the middle 1 denotes
TRAIN. The evaluator expands native TASK entries onto the required train axis.
An empty relation is an entry with zero rows; a missing entry is listed in
`missing` and is not evidence of emptiness. Row counts count entry rows, so a
task-level relation broadcast to several train inputs is counted at each input.

`comparisons.json` records canonical X-versus-target comparisons, indexed by
target ID. Equality/containment is computed by the shared evaluator; the data
writer never compares raw component IDs. Other-case assignments have their own
axes and are compared as independent model families, not zipped by ordinal.
`readers.json` records source reader names, their bound columns and exact
source callable templates. `train.json` contains only train input/output grids.
The public exporter must construct this allowlisted file instead of copying
the task JSON. `libraries.json` contains the native relation interfaces used to
write library atoms, not a separate implementation of their semantics.

The three-command CLI is `clause_command.py`. Each invocation writes a fresh
directory containing `result.json` and, when the engine returned a table,
`table.json` with the same table format. A result gives command, pair ID,
engine, reason, table path and per-target comparisons; `check` and `alternative`
also give outcome. An exploratory `run` has no outcome/grade. Stdout gives only
the result path, optional table path and outcome. Full checked records and
execution receipts remain under the private data-root run directory.

Private `judgetool/dataset-contexts/<pair_id>.json` binds the public pair ID to
the original source pair and canonical source-record identity. The tool checks
that identity; it never hashes or reads the prose specification. Existing
records containing historical prose hashes remain unaffected.
