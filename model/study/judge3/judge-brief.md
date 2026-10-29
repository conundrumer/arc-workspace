# Pair judge

Find a recovery or an alternative continuation. Give no label or grade. Your
input is a directory of complete ordinary files; use inline Python to inspect
them. The invocation supplies `PAIR_DIR`, `PYTHON`, and `TOOL` (the path to
`judgetool/judge_tool.py`).

## Files and conventions

Start with `pair.json`. Its `change` describes the changed point and forms;
`programs` names the gold and mutant arclog files. `tables` indexes the table
files by ID, source name, case and roles. X is the mutant table at the changed
point; G is gold's table there. An INIT pair uses the actual key and input-port
columns, not all BODY witnesses or the component's output. `readers.json` gives
the source readers and columns they need. `train.json` gives train input/output
grids. `libraries.json` gives native library interfaces.

Each table has ordered physical `fields` and complete `entries`. A field gives
its source `name`, native `type`, and frame/callable path when present. Use
`callable_atom` to read X or an available table: printed nested field paths are
not interchangeable with flat site names. Targets without an available role
are comparison-only and cannot appear as reads in a clause.

An entry contains `assignment`, `train`, `model`, `row_count`, and all `rows`.
Assignment and train indices start at zero. Assignments belong to their case;
model numbers belong to their table and context. Never pair models or
other-case assignments by equal ordinal, or union their rows. Native TASK rows
have already been broadcast to the train inputs by the evaluator. An entry
with `rows: []` is empty. A context in `missing` is unavailable, not empty. A
zero-column true relation has `rows: [[]]`. Counts include every entry, so a
task relation broadcast to several inputs is counted at each input.

Cells are native objects: `value` is an array even for a scalar. Position and
Box values are `[top, bottom, left, right]` margins. An `extent` supplies frame
height and width when `extent_status` is `resolved`; unresolved evidence stays
unresolved. Equal frame sizes do not establish common frame identity. Ident
values are local component IDs; raw numbers across tables need not denote the
same component. Other nominal values, including colors and orientations, keep
their native types and domains.

`comparisons.json` gives X's canonical comparisons against each target. Targets
are G, the pair's case's tables after the changed point, and every table of
every other case. Other-case tables compare without names. The evaluator
matches columns by name, otherwise type, component IDs up to renaming, and
Position and Box by their four margins. Python set differences can help explore
values already in the same identity/frame namespace; they do not replace this
comparison. There are no test table rows or test output grids in these files.

## Inspect the pair

Load the index, schema, readers and change before inspecting rows:

```python
import json, os
from pathlib import Path
p = Path(os.environ['PAIR_DIR'])
load = lambda name: json.loads((p / name).read_text())
pair = load('pair.json')
tables = {t['id']: t for t in pair['tables']}
print(pair['change'])
print({k: [(f['name'], f['type']) for f in load(t['path'])['fields']]
       for k, t in tables.items()})
print(load(pair['readers']))
```

Read the changed forms and their surrounding program to understand what the
edit removed or weakened. Then inspect X/G and the comparison file: which
columns still match, which rows are extra, and whether a restriction can remove
them. For another promising target, inspect that target's own entries as well.
The comparison names the column mapping and differences; do not assume a key
that the tables do not supply.

Inspect one context without flattening models:

```python
x = load(tables['X']['path'])
for e in x['entries']:
    if e['assignment'] == 0 and e['train'] == 0:
        print('model', e['model'], 'rows', e['row_count'])
        print(e['rows'])
```

To find possible selector tables, list available tables with a field of the
needed type and inspect the values in each separate entry. Compare nominal
values only where identities are shared; Ident column overlap by numeric ID is
not evidence across fresh tables. Inspect their callable atoms and the reader
column requirements to choose a join. A target's columns may suggest a lib
computation; look up its native interface in `libraries.json` and check the
result with the command rather than implementing the library in Python.

```python
for t in pair['tables']:
    if 'available' in t['roles']:
        a = load(t['path'])
        print(t['id'], t['source_name'], a['callable_atom'])
        print([(f['name'], f['type']) for f in a['fields']])
```

To see spatial evidence, draw a Position/Box only when its native extent is
resolved. A box occupies rows `top:height-bottom` and columns
`left:width-right`. A Position cell covers one row and one column. Draw it on
the train input only when its frame is that input's frame; otherwise draw a
separate frame of its resolved extent. The train grids are ordinary nested
integer arrays; print them or build an SVG with one colored rectangle per cell.
Do not infer an unresolved frame from the apparent shape of its margins.

## Clauses and commands

Write one RULE or DET clause with head `&fix`. Read X as `&X` and other reads
through their supplied callable atoms. INIT is not allowed. `(:Field *V)`
binds V; `(:Field V)` joins V. NOT binds nothing. A label made by the first OR
branch is bare in later branches; the tool also normalizes later re-starred
labels. A zero-site atom tests nonemptiness.

NOT takes one atom or form. To negate a conjunction, put its atoms together
in one OR branch: `(NOT (OR ((atom1 ...) (atom2 ...))))`.

A recovery supplies every target column at an X site or through a lib relation
over X's columns giving exactly one row per X row; other atoms only restrict
which X rows remain. Multirow generators such as axis_elem or dir_elem cannot
supply recovery columns. X-reading union branches must supply needed rows and
X must not be redundant. A clause supplying target columns at another source
can be a partial source only where a successful path actually uses an X row;
a syntactic X read with no rows contributes nothing.

Literal `0` is allowed at a numeric, Box, Position or Offset site, or as the
second label of a constraint whose first label is a number or Box. Position
zero is the zero box, a cell only in a 1×1 frame. Zero is never a color; get a
color from a relation that holds it.

Write your clause in a UTF-8 file. Run it as exploration, check it as a
recovery, or check an alternative continuation. Each command writes a new
result directory; use a new path for each attempt:

```sh
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" run --clause-file query.sexp --output query-result
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" check --clause-file recovery.sexp --output check-result
"$PYTHON" "$TOOL" --pair "$PAIR_DIR" alternative --clause-file continuation.sexp --output alternative-result
```

The whole exported result table is the default. Add `--columns '["A","B"]'`
to select explicit output labels in order. Commands print the result filename;
read its `result.json` and the optional `table.json` using the same Python
recipe. Tables contain complete train rows, not previews. Result comparisons
say how the candidate differs from each target. Receipts stay outside the files
you read. `run` is exploration, not an answer, and has no graded outcome.

The check requires equality on every train and test input at gold's kept DET
values. Test target rows come from gold's full replay. A continuation must read
X and be nonempty on every train input, unequal to X and all available tables.
If it equals a target it is checked as a recovery instead. Outcomes are recovery
verified, partial source verified, continuation passed, refused by the engine,
did not verify, or unknown. A replay that has no compatible kept entry or stops
at its bound is unknown; it is not evidence that no clause exists.

Finish with the recovery/alternative clauses you choose, their command outcomes,
and one or two reasons per clause naming table, column, row or cell evidence.
If none is found, say no clause found. Give no grade or label.
