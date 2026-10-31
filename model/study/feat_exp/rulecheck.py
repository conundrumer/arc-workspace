"""In-process hard-rule check of a candidate clause at one branch point.

    checker = RuleCheck(point_dir)               # once per point: reads the point's files, builds the shared state
    hit = checker.check(clause_text, x)          # per candidate: CheckResult(hard=[keys that fire], soft=[...])
    vals = checker.values(clause_text, x)        # per candidate: {key: value} of the functions the rule set needs

`point_dir` is a point of the feature-inputs export (`fstore/points/<dir>/`). It holds the train grids, the
libraries, the tables and `point.json`, which lists the tables and the point. The checker gives a feature the same
view as `featlib.Pair` gives a mutant: the train inputs and outputs, the available tables (not a target), the
clauses before the point, the library interfaces, the candidate's clause and its table X. It reads no target
table (G), and from the program it reads only the lines before the point, and stops at the point's line. The one other
fact about the program is `out_reads` (below), which the caller gives; `RuleCheck.gold_out_reads` reads it from gold's
`OUT` form for a replay of a stored point, and returns only whether `OUT` reads the candidate's relation.

Arguments of `check` and `values`:

- `clause_text`: the candidate's whole clause at the point, in program form, as one s-expression. At a Rule, Det or
  Choose point it is the clause (`(RULE &c (input (:P *P)) ... (ONE P))`). At an INIT point it is the INIT clause
  `(INIT &name Component (key ...) (port ...) ...)`; the groups before the point's group, the point's group and its
  head are the caller's, and whatever follows the port at the point is cut. Nothing of gold's clause is read: the
  clause text is the only source of the candidate's form, marks, names and heads.
- `x`: the candidate's table X as a dict with the schema of `tables/X.json`: `fields` (each with `name`, `type`,
  `frame`, `callable_row_path`) and `entries` (each with `assignment`, `train`, `model`, `rows`; a row is a list of
  cells `{'value': [...], 'extent': [...], 'extent_status': ...}`). `source_name` (default: the clause's name),
  `case` (default: the point's case) and `missing` (default: none) are optional. The dict is not changed.
- `out_reads`: whether `OUT` reads the candidate clause's relation (`Pair.out_reads`): True, False, or None where
  it is not known (the default). The output keys (`final_vs_output`, `q4c_declared.differs_no_box`, `q5a_output_tables`,
  `q5b_output_columns`, `q5c_output_cells`, `q5l_static_output`, `q6d_output_near`) apply only where it is True, and
  `q7a_equals_input` only where it is False; they give None where it is None. The sampler passes True when it writes
  `OUT` naming the candidate's relation, and False for a clause that `OUT` does not read. It is False at an INIT
  point whatever is passed: the X of an INIT port is not a table that `OUT` reads.
- `kind`: the point kind (`'Rule'`, `'Det'`, `'INIT key'`, `'INIT input'`, `'CHOOSE clause'`). Where None it is read
  from the clause keyword and the point (`kind_of`).

A key fires where its value is a number above 0. `check` runs only the feature functions that the rule set names
(`rules`: a file with one key per line, or a list of keys; default `DEFAULT_RULES`), so it returns the keys of the
rule set that fire (`hard`) and, at no extra cost, the other keys of those functions that fire (`soft`).

`check_draw(draw, names=None)` takes a row of the sampler's draws file (`clause`, `x`, `x_rows`) in place of
`clause_text` and `x`; `draw_table` converts the draw's X to the schema of `tables/X.json`, and
`rulecheck_draws.py` runs a whole draws file.

`prefix_check(clause_text, x=None)` checks a clause that is still being built: the clause text holds the atoms placed
so far, with every open form closed. It runs only the keys whose violation no later atom can repair: class SP (they read
the form), and class DA where `x` is given (they read the rows of X of the partial clause, and a later atom keeps the
violation). A key that fires there fires on every completion of the clause, so the draw can stop. The classes come from
`classes` (default `DEFAULT_CLASSES`, lines `key<TAB>class`); a rule key with no class is not run.

`self.errors` counts the functions that raised: a function that raises gives None for its keys.

`SoftScore(path)` is a trained soft score: `score(rc, clause_text, x, out_reads=None)` computes the feature functions it
reads (`functions`) through `rc.values` and gives the candidate's score; `keep(scores)` gives, of the scores of the
candidates at one point, the indexes to keep: those within `margin` of the best. The score was trained to rank gold
above the other candidates of its point, so the rule needs every candidate of the point scored first.
"""
import collections as C
import importlib.util
import json
import operator
import sys
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import featlib  # noqa: E402
from featlib import FEATURES, MARKS, Table, before, parse, unparse  # noqa: E402

MODULES = ('q1_column_laws', 'q2_table_tests', 'q3_form_filters', 'q4_unavailable_filters', 'q5_split_filters',
           'q6_residue_keys', 'q7_redundant_tables', 'syntax_g_unread', 'syntax_r3h')
DATA = featlib.DATA
DEFAULT_RULES = DATA / 'explore/rules/rules-v10.txt'
DEFAULT_CLASSES = DATA / 'explore/rules/rules-v10-classes.tsv'
PREFIX_CLASSES = ('SP',)
PREFIX_DATA_CLASSES = ('DA',)


class CheckResult(NamedTuple):
    hard: list
    soft: list


def load_feature_modules(names=MODULES):
    """Register the feature functions of the modules (as `features.load_modules` does, without its pandas and sklearn
    imports). A module that is already registered is not loaded again."""
    have = {fn.family for fn in FEATURES.values()}
    for name in names:
        if name in have:
            continue
        path = HERE / 'features' / (name + '.py')
        spec = importlib.util.spec_from_file_location(name, path)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


def read_rules(rules):
    """The keys of a rule file (one per line) or of an iterable of keys."""
    if isinstance(rules, (str, Path)):
        return [l.strip() for l in Path(rules).read_text().splitlines() if l.strip()]
    return list(rules)


def read_classes(path):
    """{key: class} of a class file (lines `key<TAB>class`); {} where the file is missing."""
    p = Path(path)
    if not p.exists():
        return {}
    return dict(l.split('\t')[:2] for l in p.read_text().splitlines() if '\t' in l)


def kind_of(clause, point):
    """The point kind of a parsed clause: Rule, Det, 'CHOOSE clause', or at an INIT 'INIT key' where the point is
    in the key group's body and 'INIT input' where it is in a port."""
    kw = clause[0] if clause else None
    if kw == 'INIT':
        found = featlib._locate_port(unparse(clause), point)
        if found is not None and found[1][0] == 'key' and found[2] in (None, 0):
            return 'INIT key'
        return 'INIT input'
    return {'RULE': 'Rule', 'DET': 'Det', 'CHOOSE': 'CHOOSE clause'}.get(kw, 'Rule')


def split_clause(clause_text, point, kind=None):
    """(kind, form, line, name) of a candidate clause: `form` is its body at the point as text (a list of items, as
    the export's `change.mutant`), `line` is the clause line a feature sees, cut after the candidate's port, and
    `name` is the clause's relation name."""
    tree = parse(clause_text)
    if len(tree) != 1 or not isinstance(tree[0], list) or not tree[0]:
        raise ValueError('clause_text must be one clause')
    t = tree[0]
    kind = kind or kind_of(t, point)
    if kind.startswith('INIT'):
        found = featlib._locate_port(unparse(t), point)
        if found is None:
            raise ValueError(f'no port at point {point} in the clause')
        _, group, item = found
        body = group[2:] if item is None else (group[1] if item == 0 else group[1 + item][2:])
    else:
        body = [q for q in t[2:] if not (isinstance(q, list) and q and q[0] in MARKS)]
    form = unparse(body)
    return kind, form, featlib._candidate_line(unparse(t), point, kind, form), (t[1] if len(t) > 1 else None)


class _Cand(featlib.Pair):
    """A mutant view of one candidate, served from the point's shared state and from memory. It has the attributes
    of `featlib.Pair`; `_state` holds what every candidate of the point shares."""

    def __init__(self, state, kind=None, line=None, form=None, x_data=None, out_reads=None):
        self._state = state
        self.out_reads = None if out_reads is None else bool(out_reads) and not (kind or '').startswith('INIT')
        self.pair_id, self.task, self.case = 'in-memory', state.task, state.case
        self.point, self.kind, self.layout = state.point, kind, 'features'
        self._candidate, self.form = 'mutant', form
        self.point_dir = state.point_dir
        self._native_point = state.native
        self._available = state.available_paths
        self._train, self._libraries = state.train_path, state.libraries_path
        self.prefix = state.prefix
        self._point_line_cache = line
        self._point_text = None
        self._x_data = x_data
        self._tables = {}
        self._examples_cache = state.examples()
        self._test_path, self._test_inputs_cache = state.test_path, state.test_inputs()
        self._meta = {'tables': [dict(x_data, id='X')] if x_data else []}
        self.dir = featlib._ViewDir(state.point_dir, self._view_program)

    @property
    def x(self):
        if 'X' not in self._tables:
            self._tables['X'] = Table(featlib._candidate_table(self._x_data, self.kind))
        return self._tables['X']

    def available(self):
        return self._state.available()

    def _schemas(self):
        if getattr(self, '_schemas_cache', None) is None:
            out = dict(self._state.schemas)
            if self._x_data is not None:
                x = {k: v for k, v in self._x_data.items() if k != 'entries'}
                out['X'] = dict(x, id='X', callable_atom=featlib._x_atom(x.get('fields') or [], self.kind))
            self._schemas_cache = out
        return self._schemas_cache

    def _typed(self):
        if getattr(self, '_typed_cache', None) is None:
            self._typed_cache = featlib._typed_sites(self, prefix=self._state.prefix_typed())
        return self._typed_cache


class _Point:
    """What every candidate at one point shares, read once."""

    def __init__(self, point_dir):
        d = self.point_dir = Path(point_dir).resolve()
        shared = featlib.load(d / 'point.json')
        self.task, self.case, self.point = shared['task'], shared['case'], shared['point']
        tables = [t for t in shared['tables'] if before(t)]  # a target (G) is dropped here and never read
        self.native = dict(shared, tables=tables)
        self.schemas = {t['id']: t for t in tables}
        self.available_paths = {t['id']: d / t['path'] for t in tables}
        self.train_path, self.libraries_path = d / shared['train'], d / shared['libraries']
        self.test_path = featlib.test_inputs_file(d, shared)  # None where the point has no test inputs
        self.prefix = self._read_prefix(d / shared['programs']['gold'])
        self._tables, self._examples, self._test, self._typed = {}, None, None, None

    def _read_prefix(self, path):
        """The non-blank lines of the program before the point's line; the file is read no further."""
        out = []
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                if len(out) == self.point[0]:
                    break
                out.append(line.rstrip('\n'))
        return out

    def warm(self):
        """Read the available tables, the train examples and the libraries, and type the clauses before the point."""
        with featlib.no_gc():  # one collection after the reads, not one after each file
            for _ in self.available():
                pass
            self.examples()
            self.test_inputs()
            featlib._lib(str(self.libraries_path))
            self.prefix_typed()

    def available(self):
        for tid, path in self.available_paths.items():
            if tid not in self._tables:
                self._tables[tid] = Table(featlib.load(path))
            yield self._tables[tid]

    def examples(self):
        if self._examples is None:
            tr = featlib._shared(str(self.train_path))
            tr = tr['train'] if isinstance(tr, dict) and 'train' in tr else tr
            self._examples = [featlib.Example(i, item) for i, item in enumerate(tr)]
        return self._examples

    def test_inputs(self):
        """The test input Grids by test index ([] where the point has none)."""
        if self._test is None:
            self._test = featlib.read_test_inputs(self.test_path)
        return self._test

    def prefix_typed(self):
        if self._typed is None:
            self._typed = featlib._typed_prefix(_Cand(self, kind='Rule'))
        return self._typed


def _fires(v):
    return v is True or (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)


# ------------------------------------------------------------------------------------------------ sampler draws

BOX_WIDTH_TYPES = frozenset({'Position', 'Box', 'Offset'})
# The draw's number types; the exported tables write them as `Number`.
NUMBER_TYPES = {'Int': 'Number', 'Nat': 'Number'}


def rename_relations(text, names):
    """The clause text with each relation name (`&r2`) written as its program name. names maps a sampler name to a
    program name, which for a port of an INIT is the name of one port (`&r5` -> `&tiling.cell`). A bare name takes
    names[name]; a name written with a port (`&r5.gap`) takes the INIT's name with that port (`&tiling.gap`); the head
    of an INIT form takes the INIT's name (`&tiling`)."""
    if not names:
        return text
    import re

    def sub(m):
        base, port = m.group(1), m.group(2)
        if base not in names:
            return m.group(0)
        return names[base].split('.')[0] + port if port else names[base]
    head = re.match(r'(\(INIT )(&[A-Za-z_0-9]+)', text)
    if head and head.group(2) in names:
        text = head.group(1) + names[head.group(2)].split('.')[0] + text[head.end():]
    return re.sub(r'(&[A-Za-z_0-9]+)(\.[A-Za-z_0-9]+)?', sub, text)


def names_from_gold(draw_clause, line):
    """{sampler name: program name} for the relation names that the gold clause uses, by aligning its tokens with
    the program's gold line. Only the names the gold clause uses are covered."""
    import re
    tok = re.compile(r'\(|\)|[^\s()]+')
    a, b = tok.findall(line), tok.findall(draw_clause)
    if len(a) != len(b):
        return {}
    out = {}
    for x, y in zip(a, b):
        if x.startswith('&') and y.startswith('&'):
            out[y.split('.')[0]] = x.split('.')[0]
    return out


def reader_fields(later_lines, relation):
    """The field names that the clauses after a DET point name on its relation: `(:Field ...)` in an atom
    `(relation ...)`. The exporter keeps a DET body's columns that readers name, so `x['read']` of a DET draw that
    matches stored data is the body labels in this set. This reads clauses after the point: use it to check gold
    against stored data, not for a search. `later_lines` are the program lines after the point."""
    out = set()

    def walk(t):
        if isinstance(t, list):
            if t and t[0] == relation:
                out.update(q[0][1:] for q in t[1:] if isinstance(q, list) and q and isinstance(q[0], str) and q[0].startswith(':'))
            for q in t:
                walk(q)
    for line in later_lines:
        walk(parse(line))
    return out


def _dets_key(dets):
    """The key that numbers a draw's DET slot assignments: equal exactly where `json.dumps(dets, sort_keys=True)` is.
    dets is {slot: [row, ...]}; rows of ints (the sampler's form) take a tuple key, a few times cheaper than the JSON
    text; anything else takes the JSON text, so that 1, 1.0 and True stay apart."""
    try:
        key = tuple(sorted((k, tuple(map(tuple, v))) for k, v in dets.items()))
    except TypeError:
        return json.dumps(dets, sort_keys=True)
    for _, rows in key:
        for row in rows:
            for c in row:
                if type(c) is not int:
                    return json.dumps(dets, sort_keys=True)
    return key


def draw_table(draw, train, frames=None, slots=None, head=None, port_types=None, entries_too=True, test_inputs=None):
    """A table in the schema of `tables/X.json` from a sampler draw: `x` {labels, types, frames, entries} and
    `x_rows` items [[kind, index], rows, n, {det slot: rows}, model, extents].

    A row holds the ints of its cells in label order: 4 for a Position, Box or Offset (top, bottom, left, right),
    else 1. The draw's `x['frames']` gives each column's frame tag (the engine's, as `X.json` writes it), else
    `frames` {label: tag}, else none. Number types `Int` and `Nat` become `Number`.

    Rule point (entries of kind 1, one per train example). The items of kind 2 (test) become test entries
    `{assignment, test, model, row_count, rows}` after the train entries (see below). An example can have
    several entries; the DET slot rows (fourth item) tell the assignment, and each distinct set of them is one
    assignment, numbered in order of first appearance. The model is the fifth item (0 where absent). Fields are named
    by their label with a `written` row path.

    Det point (entries of kind 0, task level). This is the exporter's table of a DET body (`acquire_train_table`):
    - the stored table keeps only the columns that later clauses read, so what it holds depends on the program after
      the point. Here the kept columns are the labels in `draw['x']['read']`, else every label that is not an
      Example column (all that is known without later clauses; the features then see more columns than the stored
      table gives them). They are ordered by `slots` and named `[slot+1]` with the row path `slot`, where
      `slots` {label: k} is the position of the label among the body's `clause_labels()` (`RuleCheck.draw_x` fills
      it). Without `slots` a field keeps its label as name.
    - a row whose Example column value is not a train index (0 up to the number of train examples) is dropped
      (`Document.visible`), the kept columns are projected, and the first of equal projected rows stays
      (`project_entries`).
    - the entry's rows go to every train example, as the evaluator broadcasts a task-level entry
      (assignment, train index, model). The model is the draw's, else a count per (assignment, train).

    INIT port point (`head` given by `RuleCheck.draw_x`: the port's head as [(column, [labels], record)], one item
    per head site `(:column L1 L2 ...)`; an argument may also be a field `(:Field L)`, and `record` is true where
    the site has two or more arguments or a field). The exporter's X and G for a port are the port body's table projected onto the head
    sites, one field per label (a site with two or more arguments or a field gives `column[1]`, `column[2]`, with the
    row path `written column` and `slot k`; a site with one label gives `column`), distinct rows per entry, one entry per train example
    and assignment. This does not depend on later clauses: the head fixes the columns. The draw's labels are the
    head labels (the body labels the head names); a draw whose labels are already the field names is also taken.
    A field's type is the component's declared type of that port column (`port_types` {column: type}, which
    `RuleCheck.draw_x` reads from the libraries; `Int`, `Nat` and `Number` stay as declared), else the draw's
    type of the label. Fields follow the head's order. A site with no label (an inserted Unit) and the group key columns `key[k]` of
    a port inside a `key` group are not built.

    Extents. A box cell has the extent of its frame's grid. The sixth item of an `x_rows` entry, where present,
    gives them: a dict {label: [h, w]} where a column has one extent in the entry, or a list with one item per
    row, each a list of [h, w] (or null for unresolved) per box column in label order of the draw. Without it, a
    column in frame `input` or `output` gets the size of the train grid (at a Det point, of the row's Example
    value, else of train 0) and any other box cell is unresolved.

    Test entries. Each item of kind 2 gives one test entry, `test` being its index, in the draw's order and after all
    the train entries. Its rows are the item's rows as they are: the Example filter, which keeps the train examples
    of a task-level table, does not apply to them. At a Det point, or an INIT port, the dedupe and the projection to the
    kept columns apply as for the train entries. Its assignment is that of the item's DET slot rows, the numbers
    of the train entries kept (a set of slot rows that only a test item has takes the next number). A box cell in
    frame `input` has the extent of the test input grid `test_inputs[index]` (the grids as lists of rows; where it
    is missing the extent is unresolved); a cell in frame `output` is unresolved, as a test output is not known.
    A test entry takes the model of the item (0 where absent; at a Det point a count per (assignment, test)).

    `entries_too=False` gives the fields only, with no entries."""
    labels = draw['x']['labels']
    types = [NUMBER_TYPES.get(t, t) for t in draw['x']['types']]
    port = None
    if head:
        port = []  # (field name, row path, index of the draw column)
        for column, labs, record in head:
            for k, lab in enumerate(labs):
                name = f'{column}[{k + 1}]' if record else column
                path = [{'kind': 'written', 'name': column}] + ([{'kind': 'slot', 'slot': k}] if record else [])
                at = labels.index(lab) if lab in labels else (labels.index(name) if name in labels else None)
                if at is None:
                    raise ValueError(f'port draw has no column for head label {lab}')
                port.append((name, path, at, None if record else (port_types or {}).get(column)))
    frames = dict(zip(labels, draw['x']['frames'])) if draw['x'].get('frames') is not None else (frames or {})
    widths = [4 if t in BOX_WIDTH_TYPES else 1 for t in types]
    task_level = any(item[0][0] == 0 for item in draw['x_rows'])
    keep = list(range(len(labels)))
    if port:
        keep = [p[2] for p in port]
    elif task_level:
        read = draw['x'].get('read')
        keep = [i for i, (l, t) in enumerate(zip(labels, types)) if (l in read if read is not None else t != 'Example')]
        if slots:
            keep.sort(key=lambda i: slots.get(labels[i], len(slots)))
    fields = []
    for out_index, i in enumerate(keep):
        if port:
            name, path = port[out_index][0], port[out_index][1]
            if port[out_index][3]:
                types = list(types)
                types[i] = port[out_index][3]
        elif task_level and slots and labels[i] in slots:
            name, path = f'[{slots[labels[i]] + 1}]', [{'kind': 'slot', 'slot': slots[labels[i]]}]
        else:
            name, path = labels[i], [{'kind': 'written', 'name': labels[i]}]
        fields.append({'index': out_index, 'name': name, 'type': types[i], 'frame': frames.get(labels[i], ''),
                       'callable_row_path': path})
    if not entries_too:
        return {'format': 'judge-dataset-v1', 'kind': 'table', 'id': 'X', 'roles': ['input'], 'fields': fields,
                'entries': [], 'missing': [], 'complete': True, 'side': 'mutant'}
    example_cols = [i for i, t in enumerate(types) if t == 'Example']
    ntrain = len(train)
    starts = [sum(widths[:i]) for i in range(len(widths))]
    example_at = [starts[i] for i in example_cols]
    # the kept columns: their spans in a row, and the box index (the count of box columns before it in label order)
    # of each box column, None for another column
    spans = [(starts[i], starts[i] + widths[i]) for i in keep]
    boxes = [i for i, w in enumerate(widths) if w == 4]
    box_at = [boxes.index(i) if widths[i] == 4 else None for i in keep]
    flat = [p for a, b in spans for p in range(a, b)]
    pick = operator.itemgetter(*flat) if flat else (lambda r: ())
    dedupe = bool(task_level or port)
    sizes = {}  # train index -> the extents of the kept columns (see `resolved`) by the train grids
    test_sizes = {}  # test index -> the same by the test input grid; a column in frame output is unresolved

    def resolved(ext):
        """A box cell's extent where it is resolved, else False."""
        return ext if ext and min(ext) >= 0 else False

    def grid_extents(ex):
        if ex not in sizes:
            item = train[ex]
            grids = {'input': item['input'], 'output': item['output']}
            fs = [grids.get(frames.get(labels[i], '')) if bi is not None else None for i, bi in zip(keep, box_at)]
            sizes[ex] = [None if bi is None else resolved([len(g), len(g[0])] if g else None) for g, bi in zip(fs, box_at)]
        return sizes[ex]

    def test_extents(ex):
        if ex not in test_sizes:
            grid = test_inputs[ex] if test_inputs and 0 <= ex < len(test_inputs) else None
            fs = [grid if frames.get(labels[i], '') == 'input' else None for i in keep]
            test_sizes[ex] = [None if bi is None else resolved([len(g), len(g[0])] if g else None)
                              for g, bi in zip(fs, box_at)]
        return test_sizes[ex]

    entries, assignments, models = [], {}, C.Counter()
    # the train items first, then the test items: a test item does not change the number of a train assignment
    items = [(False, it) for it in draw['x_rows'] if it[0][0] == (0 if task_level else 1)]
    items += [(True, it) for it in draw['x_rows'] if it[0][0] == 2]
    with featlib.no_gc():
        for is_test, ((kind, index), rows, n, dets, *rest) in items:
            assignment = assignments.setdefault(_dets_key(dets), len(assignments))
            given = rest[1] if len(rest) > 1 else None
            extents = test_extents if is_test else grid_extents
            # the extent of each kept column (None: not a box) where the whole entry has one
            exts = None
            if isinstance(given, dict):
                exts = [None if bi is None else resolved(given.get(labels[i])) for i, bi in zip(keep, box_at)]
            elif given is None and (is_test or not task_level) and rows:
                exts = extents(index)
            out, seen = [], set()
            for ri, r in enumerate(rows):
                if task_level and example_at and not is_test:
                    if len(example_at) == 1:
                        if not 0 <= r[example_at[0]] < ntrain:
                            continue
                    elif any(not 0 <= r[at] < ntrain for at in example_at):
                        continue
                if dedupe:
                    key = pick(r)
                    if key in seen:
                        continue
                    seen.add(key)
                row_exts = exts
                if row_exts is None:
                    if given is not None:
                        g = given[ri]
                        row_exts = [None if bi is None else resolved(g[bi]) for bi in box_at]
                    elif is_test:
                        row_exts = test_extents(index)
                    else:
                        row_exts = grid_extents(r[example_at[0]] if example_at else 0)
                out.append([{'value': r[a:b]} if e is None else
                            {'value': r[a:b], 'extent': list(e), 'extent_status': 'resolved'} if e else
                            {'value': r[a:b], 'extent': [-1, -1], 'extent_status': 'unresolved'}
                            for (a, b), e in zip(spans, row_exts)])
            model = rest[0] if rest else 0
            if is_test:
                if task_level and not rest:
                    model = models[assignment, 'test', index]
                    models[assignment, 'test', index] += 1
                entries.append({'assignment': assignment, 'test': index, 'model': model, 'row_count': len(out),
                                'rows': out})
                continue
            for example in (range(ntrain) if task_level else [index]):
                if task_level and not rest:
                    model = models[assignment, example]
                    models[assignment, example] += 1
                entries.append({'assignment': assignment, 'train': example, 'model': model, 'rows': out})
    return {'format': 'judge-dataset-v1', 'kind': 'table', 'id': 'X', 'roles': ['input'], 'fields': fields,
            'entries': entries, 'missing': [], 'complete': True, 'side': 'mutant'}


class RuleCheck:
    """The state of one point, and the check of many candidates at it. See the module docstring."""

    def __init__(self, point_dir, rules=DEFAULT_RULES, classes=DEFAULT_CLASSES, warm=True):
        load_feature_modules()
        self.state = _Point(point_dir)
        self.rules = read_rules(rules)
        self._rule_set = set(self.rules)
        self.classes = read_classes(classes)
        self.functions = sorted({k.split('.', 1)[0] for k in self.rules})
        missing = [f for f in self.functions if f not in FEATURES]
        if missing:
            raise KeyError(f'no feature function: {missing}')
        self.errors = C.Counter()
        if warm:
            self.state.warm()

    @property
    def point(self):
        return self.state.point

    def gold_out_reads(self, clause_text):
        """For a replay of a stored point: whether gold's `OUT` form reads the relation that `clause_text` declares
        (`Pair.out_reads`), from gold's program and nothing else of it."""
        reads = featlib._gold_out_relations(self.state.point_dir / 'gold.arclog')
        return featlib.out_fact(reads, featlib.clause_relation(clause_text), kind_of(parse(clause_text)[0], self.point))

    def candidate(self, clause_text, x, kind=None, out_reads=None):
        """The Pair-like view of a candidate, for a feature function."""
        kind, form, line, name = split_clause(clause_text, self.state.point, kind)
        x = dict(x)
        x.setdefault('source_name', name)
        x.setdefault('case', self.state.case)
        x.setdefault('missing', [])
        return _Cand(self.state, kind, line, form, x, out_reads)

    def values(self, clause_text, x, kind=None, functions=None, out_reads=None):
        """{key: value} of the feature functions that the rule set names (or of `functions`, a list of names)."""
        cand = self.candidate(clause_text, x, kind, out_reads)
        out = {}
        for name in functions or self.functions:
            try:
                v = FEATURES[name](cand)
            except Exception as e:
                self.errors[f'{name}: {type(e).__name__}'] += 1
                v = None
            if isinstance(v, dict):
                for k, val in v.items():
                    out[f'{name}.{k}'] = val
            else:
                out[name] = v
        return out

    def check(self, clause_text, x, kind=None, out_reads=None):
        """CheckResult(hard, soft): the keys of the rule set that fire on the candidate, and the other keys of
        the functions run that fire, each in sorted order."""
        vals = self.values(clause_text, x, kind, out_reads=out_reads)
        fires = sorted(k for k, v in vals.items() if _fires(v))
        return CheckResult([k for k in fires if k in self._rule_set], [k for k in fires if k not in self._rule_set])

    def draw_x(self, draw, clause_text):
        """X in the schema of `tables/X.json` from a sampler draw (see `draw_table`). At a Det point the slots of
        the columns come from the label order of the clause. Where the draw has no `x['frames']`, a column gets
        the frame `input` or `output` where featlib's typing of the clause puts it in exactly one of them, and no
        other frame tag. The slots and the frames come from the clause and X's fields, so the table they are read
        with has no entries."""
        train = featlib._shared(str(self.state.train_path))
        train = train['train'] if isinstance(train, dict) and 'train' in train else train
        slots = None
        tests = featlib.read_test_grids(self.state.test_path)
        head = self.port_head(clause_text)
        if head:
            t = parse(clause_text)[0]
            found = featlib._locate_port(unparse(t), self.state.point)
            comp = featlib._lib(str(self.state.libraries_path)).component(t[2])
            declared = ((comp or {}).get('inputs') or {}).get(found[1][0]) or []
            return draw_table(draw, train, head=head, port_types={n: ty for n, ty, _ in declared if ty}, test_inputs=tests)
        if any(item[0][0] == 0 for item in draw['x_rows']):
            body = self.candidate(clause_text, draw_table(draw, train, entries_too=False)).clause.body
            slots = {lab: k for k, lab in enumerate(body.clause_labels())} if body is not None else {}
        if draw['x'].get('frames') is not None:
            return draw_table(draw, train, slots=slots, test_inputs=tests)
        cand = self.candidate(clause_text, draw_table(draw, train, slots=slots, entries_too=False))
        frames = {}
        for name, v in cand.clause.x_columns.items():
            fs = {f for f in v.frames if f in ('input', 'output')}
            if len(fs) == 1:
                frames[name] = next(iter(fs))
        return draw_table(draw, train, frames, slots, test_inputs=tests)

    def port_head(self, clause_text):
        """At an INIT port (not a key group): the port's head as [(column, [labels], record)]; else None."""
        t = parse(clause_text)
        t = t[0] if t and isinstance(t[0], list) else None
        if not t or t[0] != 'INIT':
            return None
        found = featlib._locate_port(unparse(t), self.state.point)
        if found is None or found[2] is not None or len(found[1]) < 2:
            return None
        head = found[1][1]
        out = []
        for site in head:
            if isinstance(site, list) and site and isinstance(site[0], str) and site[0].startswith(':'):
                args = site[1:]
                labs = [a if isinstance(a, str) else a[-1] for a in args if isinstance(a, str) or (isinstance(a, list) and a)]
                out.append((site[0][1:], labs, len(args) > 1 or any(isinstance(a, list) for a in args)))
        return out

    def check_draw(self, draw, names=None, out_reads=None):
        """`check` of a sampler draw (a row of the draws file with `clause`, `x` and `x_rows`); `names` renames the
        sampler's relation names (`&r2`) to the program's, where they differ. `out_reads` defaults to the draw's own
        `out_reads` field."""
        clause = rename_relations(draw['clause'], names)
        if out_reads is None:
            out_reads = draw.get('out_reads')
        return self.check(clause, self.draw_x(draw, clause), out_reads=out_reads)

    def prefix_check(self, clause_text, x=None, kind=None, out_reads=None):
        """CheckResult(hard, soft) of a clause still being built (see the module docstring): `hard` the keys of class SP,
        and of class DA where `x` is given, that fire; `soft` is empty."""
        classes = PREFIX_CLASSES + (PREFIX_DATA_CLASSES if x is not None else ())
        keys = [k for k in self.rules if self.classes.get(k) in classes]
        functions = sorted({k.split('.', 1)[0] for k in keys})
        vals = self.values(clause_text, x if x is not None else {'fields': [], 'entries': []}, kind, functions, out_reads)
        return CheckResult(sorted(k for k in keys if _fires(vals.get(k))), [])


DEFAULT_SOFT = DATA / 'soft/deploy/soft_gold_v11.npz'


class SoftScore:
    """A linear soft score over feature columns: missing values take the training median (a `form.*` column takes 0
    where `form.atoms` has a value, as the feature tables write it), then each column is standardized, clipped and
    weighted. A draw is kept when its score is at least its point's best draw score minus the margin of the point's
    kind (`margin_for`); `margin` is the largest of them."""

    def __init__(self, path=DEFAULT_SOFT):
        import numpy as np
        m = np.load(path)
        self.cols = [str(c) for c in m['cols']]
        self.median, self.mean, self.scale, self.w = m['median'], m['mean'], m['scale'], m['w']
        self.clip, self.margin = float(m['clip']), float(m['margin'])
        self.margins = dict(zip((str(k) for k in m['kinds']), (float(v) for v in m['kind_margins']))) \
            if 'kinds' in m.files else {}
        self.functions = sorted({c.split('.', 1)[0] for c in self.cols})
        load_feature_modules((HERE / 'features/enabled.txt').read_text().split())

    def score_values(self, vals):
        import numpy as np
        form = vals.get('form.atoms') is not None
        v = np.array([vals.get(c) if vals.get(c) is not None else (0.0 if form and c.startswith('form.') else np.nan)
                      for c in self.cols], dtype=float)
        v = np.where(np.isnan(v), self.median, v)
        return float(np.clip((v - self.mean) / self.scale, -self.clip, self.clip) @ self.w)

    def score(self, rc, clause_text, x, kind=None, out_reads=None):
        return self.score_values(rc.values(clause_text, x, kind, self.functions, out_reads))

    def margin_for(self, kind):
        """The margin at a point of this kind (`Rule`, `Det`, `INIT input`, ...); the largest margin for a kind the
        model has none for."""
        return self.margins.get(kind, self.margin)

    @staticmethod
    def margin_of(path=DEFAULT_SOFT):
        """The margin of the model at path, or None where there is no model."""
        import numpy as np
        return float(np.load(path)['margin']) if Path(path).exists() else None

    def keep(self, scores):
        best = max(scores) if scores else 0.0
        return [i for i, s in enumerate(scores) if s >= best - self.margin]
