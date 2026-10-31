"""What a feature may read about a candidate table at a branch point, and the feature registry.

A `Pair` exposes only what the search has at the point: the train grids, the available tables,
the candidate table X, the candidate's form, the clauses before the point, and the library
interfaces. `Pair.gold(...)` gives the same view with gold's table and form as the candidate,
for scoring gold; features cannot tell the two apart.

A feature is a function of a Pair, registered with `@feature`. It returns a number, a dict of
numbers (one feature per key, named `<function>.<key>`), or None where it does not apply. Its
family is its module's name. Feature modules go in `features/` next to this file.

Raw access: `form`, `kind`, `point`, `prefix`, `train`, `libraries`, `x` (a Table), `available()`,
`ports_before()`, `out_reads`, `parse` and `atoms`. Attributes whose name starts with `_` are private: they can
differ between the gold and the mutant view, and the screen flags a feature whose value depends on them.

Typed access, so that no feature guesses a type, a frame or an atom from a name:

- `p.clause`: the candidate's Clause. `p.clause.body` is the candidate's Scope, `p.clause.x_columns`
  maps each X column name to the Variable it holds. At an INIT point, `p.clause.key` is the INIT's key
  Scope, `p.clause.port` the port at the point and `p.clause.before` the INIT's scopes before it.
- `p.clauses_before()`: the Clauses before the point, in order. `clause.table_ids` and `clause.tables()`
  give the available tables it produced; `clause.relation`, `keyword`, `component`, `proposers`.
- A Scope has `atoms` (every Atom in text order, through NOT, OR, IF and ALL, comparisons included),
  `variables` ({label: Variable}), `head` (an INIT port's head Arguments), `literals`, `marks`,
  `creation_order()`, `clause_labels()` and `key_order()`.
- An Atom has `relation`, `kind` ('comparison', 'fact', 'relation', 'macro', 'table', 'port', 'output',
  'clause', 'x', 'unknown'), `interface`, `arguments`, `operator`, `first` and `second` (comparisons),
  `table` (the Table it reads), and its context: `negated`, `branch`, `quantifier`, `conditional`,
  `conjunction`, `path`. `atom.key()` compares atoms of one scope; `signature(atom)` atoms of two scopes.
- An Argument is one label or literal at a site: `column`, `field`, `name`, `term`, `label`, `literal`
  ('number zero', 'zero box' or None), `is_zero`, `binds`, `key`, `joins`, `head`, `column_type`,
  `resolved_type`, `frame` and `variable`.
- A Variable has `label`, `resolved_type`, `frame`, `occurrences`, `binders`, `joins`, `sites`, `clash`
  and, for the candidate, `column` (its X Column).
- `canonical(scope)`: the scope's canonical form and label order, the same for every respelling.
- Tables: `table.columns()` (Columns with `name`, `column`, `field`, `type`, `frame`, `frame_kind`,
  `index`), `table.column(name)`, `table.rows()` (decoded rows with their context) and `table.examples()`
  (the rows of each (assignment, example)). `decode(cell, column, table)` gives Margins for a Position,
  Box or Offset (margins, frame tag, frame size where known, `row`, `col`, `cells()`, `in_frame()`), an
  Ident local to its table, or an int. `p.table(id or source name)` gives X or an available table.
- `p.out_reads`: whether `OUT` reads the candidate clause's relation, so that the candidate is the clause that
  `OUT` paints from: True, False, or None where it is not known. It is the one fact that a feature gets from the
  program after the point, and it is only which relations `OUT` names (`out_relations`): not its labels, its columns
  or any other form. It is False at an INIT point, whose X is a port table and not a table that `OUT` reads.
- `p.examples()`: the train examples, each with `input` and `output` Grids (`cells`, `size`, `array`,
  `colors()`, `most_common()`), `same_size` and `changed()`.
- `p.lib`: the library interfaces: `interface(name)` (a relation, macro, fact or proposer's columns and
  types) and `component(name)` (ports and their column types).

Types follow the engine's spelling, with `number` as Number; `subtype(a, b)` says whether a value of
type a stands at a column of type b. Each value featlib derives (types and frames, the X correspondence,
the INIT port, the tables of a clause, Ident groups, the canonical form) comes from one function named
in the section "typed access" below, so that an engine export can replace it.
"""
import collections as C
import contextlib
import functools
import gc
import json
import operator
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # model/study, for study_paths
from study_paths import DATA_ROOT  # noqa: E402

# The fit's cache keys each module's values on this number and the module's file, not on this file: raise it
# with every change here that alters a feature value.
VERSION = 6

FX = DATA_ROOT / 'feat-exp'
DATA = FX / 'data'  # the rule files and score models the scorers load
FULL = FX / 'pairs'
STORE = FX / 'store'
FSTORE = FX / 'fstore'


_VIRTUAL = {}


# The export writes a number column as one of the subtypes Nat and Int; the features read both as Number.
NUMBER_SUBTYPES = ('Nat', 'Int')


@contextlib.contextmanager
def no_gc():
    """Pause the cyclic garbage collector while code builds many containers that stay alive (a parsed table, a
    candidate's X): the collections that such a build triggers find nothing to free."""
    was = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was:
            gc.enable()


def load(path):
    """A JSON file of the export, with a table's Nat and Int fields typed Number. The screen's invariance checks
    register changed copies in `_VIRTUAL`."""
    key = str(path)
    if key in _VIRTUAL:
        return _VIRTUAL[key]
    text = Path(path).read_text()
    with no_gc():
        data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get('fields'), list):
        for f in data['fields']:
            if isinstance(f, dict) and f.get('type') in NUMBER_SUBTYPES:
                f['type'] = 'Number'
    return data


@functools.lru_cache(maxsize=8)
def _shared(path):
    """A point's shared file (train grids, libraries), read once for all its pairs. Do not modify it."""
    return load(path)


TEST_INPUTS_FILE = 'test_inputs.json'


def test_inputs_file(point_dir, shared):
    """The path of a point's test-inputs file (the test input grids, no outputs), or None where the point has none.
    `point.json` says `"test_inputs": n` (a number, or the file's name); a point without test inputs has no such key."""
    n = shared.get('test_inputs')
    if not n:
        return None
    return Path(point_dir) / (n if isinstance(n, str) else TEST_INPUTS_FILE)


_RELATION = re.compile(r'&[A-Za-z_0-9]+')
_CLAUSE_HEAD = re.compile(r'\s*\(\s*[A-Z_]+\s+(&[A-Za-z_0-9]+)')


def out_relations(program_text):
    """The relations (`&name`, with the port dropped) that the last `OUT` form of a program reads, as a frozenset, or
    None where the program has no `OUT` form. Nothing else of the form is returned: not the labels that `OUT` paints
    from, not its columns."""
    for line in reversed(program_text.splitlines()):
        if line.lstrip().startswith('(OUT'):
            return frozenset(_RELATION.findall(line))
    return None


def clause_relation(line):
    """The relation a clause line declares (`&name`; at an INIT, the instance), or None."""
    m = _CLAUSE_HEAD.match(line or '')
    return m.group(1) if m else None


def out_fact(reads, relation, kind):
    """The value of `Pair.out_reads`: whether the relations `reads` that `OUT` names include the candidate's
    `relation`. None where either is unknown. False at an INIT point: X is then the table of an input port (or of
    the key), which `OUT` does not read, even when `OUT` reads an output port of the same instance."""
    if reads is None or relation is None or kind is None:
        return None
    if kind.startswith('INIT'):
        return False
    return relation.split('.')[0] in reads


_out_cache = {}


def _gold_out_relations(path):
    """`out_relations` of the program file at `path`, read once; None where the file is missing."""
    key = str(path)
    if key not in _out_cache:
        _out_cache[key] = out_relations(Path(path).read_text()) if Path(path).exists() else None
    return _out_cache[key]


def _is_test(entry):
    """True for a test entry: {assignment, test, model, row_count, rows}. A train entry has `train` instead."""
    return 'test' in entry and 'train' not in entry


def entry_example(entry):
    """The example an entry belongs to: its train index, or ('test', test index) for a test entry."""
    return ('test', entry['test']) if _is_test(entry) else entry['train']


class Table:
    def __init__(self, data):
        self.id, self.name, self.case = data['id'], data['source_name'], data['case']
        self.fields, self.missing = data['fields'], data['missing']
        # `entries` holds the train entries (key `train`), the ones every reader of a train example reads. The test
        # entries (key `test`, no `train`) are in `test_entries`; `all_entries` has both, in file order.
        self.all_entries = data['entries']
        self.test_entries = [e for e in self.all_entries if _is_test(e)]
        self.entries = [e for e in self.all_entries if not _is_test(e)] if self.test_entries else self.all_entries
        # False where the table was written without test rows ("test_rows": false)
        self.has_test = bool(self.test_entries)
        self.atom = data.get('callable_atom')
        # Where the table was written at every live assignment (build_points --all-assignments): the numbers of the
        # case's kept assignments, the DET slot rows of each number, and the marks that the table holds fewer
        # assignments than were live (`assignments_partial`, `assignments_fallback`). None where the table has none.
        self.kept_assignments = data.get('kept_assignments')
        self.assignments = data.get('assignments')
        self.assignments_partial = bool(data.get('assignments_partial'))
        self.assignments_fallback = data.get('assignments_fallback')

    def names(self):
        return [f['name'] for f in self.fields]

    def types(self):
        return [f['type'] for f in self.fields]

    def frames(self):
        return [f.get('frame', '') for f in self.fields]

    def contexts(self, tests=False):
        """(assignment, train) -> list of models; a model is a list of rows of cell values (tuples). With `tests` the
        test entries are in it too, under the key (assignment, ('test', test index))."""
        if tests and self.test_entries:
            out = dict(self.contexts())
            out.update({(a, ('test', u)): m for (a, u), m in self.test_contexts().items()})
            return out
        shape = (id(self.entries), tuple(len(e['rows']) for e in self.entries))
        cached = self.__dict__.get('_contexts_cache')
        if cached is None or cached[0] != shape:
            out = C.defaultdict(list)
            for e in self.entries:
                out[e['assignment'], e['train']].append([[tuple(c['value']) for c in r] for r in e['rows']])
            cached = self._contexts_cache = (shape, out)
        return cached[1]  # shared by the callers: do not modify it

    def test_contexts(self):
        """(assignment, test) -> list of models, as `contexts` for the test entries; empty where there are none."""
        shape = (id(self.test_entries), tuple(len(e['rows']) for e in self.test_entries))
        cached = self.__dict__.get('_test_contexts_cache')
        if cached is None or cached[0] != shape:
            out = C.defaultdict(list)
            for e in self.test_entries:
                out[e['assignment'], e['test']].append([[tuple(c['value']) for c in r] for r in e['rows']])
            cached = self._test_contexts_cache = (shape, out)
        return cached[1]  # shared by the callers: do not modify it

    def every_models(self):
        """The models of every example, train then test: a list of row lists (rows of cell value tuples)."""
        return [m for ms in self.contexts().values() for m in ms] + [m for ms in self.test_contexts().values() for m in ms]


_point_cache = {}


class Pair:
    """A mutant pair, from a full pair directory, the compact store or the feature-inputs export."""

    def __init__(self, pair_id, candidate='mutant'):
        for root, layout in ((FULL, 'full'), (STORE / 'pairs', 'store'), (FSTORE / 'pairs', 'features')):
            if (root / pair_id / 'pair.json').exists():
                self.dir, self.layout = root / pair_id, layout
                break
        else:
            raise FileNotFoundError(pair_id)
        meta = load(self.dir / 'pair.json')
        self.pair_id, self.task, self.case = meta['pair_id'], meta['task'], meta['case']
        change = meta['change']
        self.point, self.kind = change['point'], change['kind']
        self._candidate = candidate
        self.form = change['mutant'] if candidate == 'mutant' else change['gold']
        self._meta = meta
        self._tables = {}
        if self.layout == 'features':
            self.point_dir = (self.dir / meta['point']).resolve()
            if self.point_dir not in _point_cache:
                _point_cache.clear()
                _point_cache[self.point_dir] = load(self.point_dir / 'point.json')
            shared = _point_cache[self.point_dir]
            self._native_point = shared
            index = {t['id']: t for t in shared['tables']}
            self._available = {t['id']: self.point_dir / t['path'] for t in shared['tables'] if before(t)}
            self._x = (self.dir / {t['id']: t for t in meta['tables']}['X']['path'] if candidate == 'mutant'
                       else self.point_dir / index['G']['path'])
            self._train = self.point_dir / shared['train']
            self._libraries = self.point_dir / shared['libraries']
            self._test_path = test_inputs_file(self.point_dir, shared)
        elif self.layout == 'store':
            self.point_dir = STORE / 'points' / (self.dir / 'point').read_text().strip()
            if self.point_dir not in _point_cache:
                _point_cache.clear()
                _point_cache[self.point_dir] = load(self.point_dir / 'point.json')
            shared = _point_cache[self.point_dir]
            own = (self.dir / 'tables').exists()
            self._available = {t['id']: self.dir / 'tables' / (t['id'] + '.json') for t in meta['tables']
                               if before(t)} if own else {
                t['id']: self.point_dir / t['path'] for t in shared['tables'] if before(t)}
            self._x = self.dir / 'X.json' if candidate == 'mutant' else self.point_dir / 'tables/G.json'
            self._train = self.point_dir / 'train.json'
            self._libraries = (self.dir if own else self.point_dir) / 'libraries.json'
            self._test_path = test_inputs_file(self.point_dir, shared)
        else:
            index = {t['id']: t for t in meta['tables']}
            self._available = {t['id']: self.dir / t['path'] for t in meta['tables'] if before(t)}
            self._x = self.dir / index['X' if candidate == 'mutant' else 'G']['path']
            self._train = self.dir / meta['train']
            self._libraries = self.dir / meta['libraries']
            self._test_path = None
        lines = [l for l in (self.dir / 'mutant.arclog').read_text().splitlines() if l.strip()]
        self.prefix = lines[:self.point[0]]
        self._point_text = lines[self.point[0]] if self.point[0] < len(lines) else None
        gold_program = (self.point_dir / ((shared.get('programs') or {}).get('gold') or 'gold.arclog')
                        if self.layout != 'full' else None)
        reads = (_gold_out_relations(gold_program) if gold_program is not None
                 else out_relations('\n'.join(lines)))
        self.out_reads = out_fact(reads, clause_relation(self._point_text), self.kind)
        self.dir = _ViewDir(self.dir, self._view_program)

    def _view_program(self):
        """The text of `mutant.arclog` as a feature sees it: the clauses before the point, then the candidate's
        clause (gold's in the gold view) cut after the candidate's port. The two views differ only in that clause."""
        line = self._point_line()
        return '\n'.join(self.prefix + ([line] if line else [])) + '\n'

    def _point_line(self):
        """The clause at the point as one line, with the candidate's body in place and nothing after its port."""
        if not hasattr(self, '_point_line_cache'):
            self._point_line_cache = _candidate_line(self._point_text, self.point, self.kind, self.form)
        return self._point_line_cache

    def ports_before(self):
        """At an INIT point: (component, port name at the point, the parsed ports before it); else None.

        The INIT clause is read from the program at the point, cut to the ports before the point's port. Where the
        port stands inside the key clause, its name is that port's, and the ports before it are the INIT's earlier
        groups and the ports of the key clause before it; the key clause's own body is in `Pair.clause.key`.
        """
        if not self.kind.startswith('INIT') or len(self.point) < 2:
            return None
        found = _locate_port(self._point_line(), self.point)
        if found is None:
            return None
        t, group, item = found
        if item is None:
            port = group
            before_ = t[3:3 + self.point[1]]
        elif item == 0:
            port = group
            before_ = t[3:3 + self.point[1]]
        else:
            port = group[1 + item]
            before_ = t[3:3 + self.point[1]] + [q for q in group[2:1 + item] if isinstance(q, list)]
        name = port[0] if isinstance(port, list) and port else None
        return t[2], name, before_

    @classmethod
    def gold(cls, pair_id):
        return cls(pair_id, candidate='gold')

    @property
    def train(self):
        return _shared(str(self._train))

    @property
    def libraries(self):
        return _shared(str(self._libraries))

    @property
    def x(self):
        """The candidate table, presented alike in both views: id `X`, the callable atom a mutant's X has,
        entries in (assignment, train, model) order and rows in value order."""
        if 'X' not in self._tables:
            self._tables['X'] = Table(_candidate_table(load(self._x), self.kind))
        return self._tables['X']

    def available(self):
        for tid, path in self._available.items():
            if tid not in self._tables:
                self._tables[tid] = Table(load(path))
            yield self._tables[tid]


def _x_atom(fields, kind):
    """The callable atom of a candidate table, as the export writes it for a mutant's X: one site per written
    column, record slots inside it, bare slots for positional columns, and none at a Det point."""
    if kind == 'Det':
        return None
    groups = []
    for k, f in enumerate(fields):
        path = f.get('callable_row_path') or []
        head = path[0] if path and isinstance(path[0], dict) else {}
        if head.get('kind') == 'written':
            nested = len(path) > 1
            if nested and groups and groups[-1][0] == head.get('name') and groups[-1][2]:
                groups[-1][1].append(k)
            else:
                groups.append([head.get('name'), [k], nested])
        else:
            groups.append([None, [k], False])
    parts = []
    for name, ks, _ in groups:
        terms = ' '.join(f'*V{k}' for k in ks)
        parts.append(f'(:{name} {terms})' if name is not None else terms)
    return '(&X ' + ' '.join(parts) + ')'


def _row_key(row):
    return [c.get('value') for c in row], [c.get('extent') or [] for c in row], [c.get('extent_status') or '' for c in row]


def _sorted_rows(rows):
    """The rows in `_row_key` order. They are sorted by their values, and only rows with equal values are compared on
    extents and extent status, so most rows build one key list in place of three."""
    values = [[c.get('value') for c in r] for r in rows]
    order = sorted(range(len(rows)), key=values.__getitem__)
    ordered = [values[k] for k in order]
    if not any(map(operator.eq, ordered, ordered[1:])):
        return [rows[k] for k in order]
    out, i = [], 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        tie = [rows[k] for k in order[i:j]]
        out.extend(sorted(tie, key=_row_key) if len(tie) > 1 else tie)
        i = j
    return out


def _candidate_table(data, kind):
    """A copy of a candidate table's data in the presentation both views share. Entries that share one rows list (a
    task-level table gives the same rows to every train example) sort it once, and each gets its own copy."""
    out = dict(data)
    out['id'] = 'X'
    out['callable_atom'] = _x_atom(data.get('fields') or [], kind)
    done = {}  # id of a rows list -> (that list, its rows sorted)
    entries = []
    with no_gc():
        for e in data.get('entries') or []:
            rows = e.get('rows') or []
            if id(rows) not in done:
                done[id(rows)] = (rows, _sorted_rows(rows))
            entries.append(dict(e, rows=list(done[id(rows)][1])))
    entries.sort(key=lambda e: (e.get('assignment', 0), _is_test(e), e.get('test', 0) if _is_test(e) else e.get('train', 0),
                                e.get('model', 0)))
    out['entries'] = entries
    return out


def unparse(tree):
    """The text of a parsed form, as `parse` reads it."""
    if isinstance(tree, str):
        return tree
    return '(' + ' '.join(unparse(t) for t in tree) + ')'


def _locate_port(line, point):
    """At an INIT clause line: (clause tree, group at point[1], item) where item is None when the group is a port,
    and else the index in the key clause (0 for the key's body, k for its k-th port); None where it does not parse."""
    if not line or len(point) < 2:
        return None
    tree = parse(line)
    t = tree[0] if tree and isinstance(tree[0], list) else None
    if not t or t[0] != 'INIT' or len(t) <= 3 + point[1]:
        return None
    group = t[3 + point[1]]
    if not isinstance(group, list) or not group:
        return None
    if group[0] == 'key' and len(point) >= 3 and isinstance(point[2], int) and 1 + point[2] < len(group):
        return t, group, point[2]
    return t, group, None


def _candidate_line(line, point, kind, form):
    """The clause line at the point with its candidate body replaced by `form`'s, cut after the candidate's port."""
    if line is None:
        return None
    try:
        body = parse(form)
        body = body[0] if body and isinstance(body[0], list) else []
        if kind.startswith('INIT'):
            found = _locate_port(line, point)
            if found is None:
                return line
            t, group, item = found
            if item is None:
                group = group[:2] + body
            elif item == 0:
                group = group[:1] + [body]
            else:
                port = group[1 + item]
                group = group[:1 + item] + [port[:2] + body]
            return unparse(t[:3 + point[1]] + [group])
        tree = parse(line)
        t = tree[0] if tree and isinstance(tree[0], list) else None
        if not t or len(t) < 2:
            return line
        marks = [q for q in t[2:] if isinstance(q, list) and q and q[0] in ('ONE', 'SET')]
        return unparse(t[:2] + body + marks)
    except Exception:
        return line


class _ViewFile:
    """A file of a pair directory whose text the view gives; every other use goes to the file on disk."""

    def __init__(self, path, text):
        self._path, self._text = path, text

    def read_text(self, *args, **kwargs):
        return self._text()

    def exists(self):
        return True

    def open(self, mode='r', *args, **kwargs):
        import io
        return io.StringIO(self._text())

    def __fspath__(self):
        return str(self._path)

    def __str__(self):
        return str(self._path)

    def __repr__(self):
        return repr(self._path)

    def __getattr__(self, name):
        return getattr(self._path, name)


class _ViewDir:
    """A pair directory as a feature sees it: `mutant.arclog` is the view's program (`Pair._view_program`), and
    every other name is the file on disk."""

    def __init__(self, path, program):
        self._path, self._program = Path(path), program

    def __truediv__(self, name):
        if str(name) == 'mutant.arclog':
            return _ViewFile(self._path / name, self._program)
        return self._path / name

    def __fspath__(self):
        return str(self._path)

    def __str__(self):
        return str(self._path)

    def __repr__(self):
        return repr(self._path)

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self._path))

    def __getattr__(self, name):
        return getattr(self._path, name)


FEATURES = {}


def before(entry):
    """A table index entry of a table built before the point: an available read that is not also a target.
    A target depends on the changed clause, and its stored rows are gold's."""
    return 'available' in entry['roles'] and 'target' not in entry['roles']


def feature(fn):
    """Register a feature; its family is its module's last name."""
    fn.family = fn.__module__.rsplit('.', 1)[-1]
    FEATURES[fn.__name__] = fn
    return fn


TOKEN = re.compile(r'\(|\)|[^\s()]+')


def parse(text):
    """Parse an s-expression form into nested lists of strings."""
    stack = [[]]
    for tok in TOKEN.findall(text):
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return stack[0]


def atoms(tree):
    """Yield every atom (a list whose head is a relation name) in a parsed form."""
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] not in ('OR', 'NOT') and not tree[0].startswith(':'):
            yield tree
        for t in tree:
            yield from atoms(t)


# =============================================================================================== typed access
#
# A feature reads clauses, tables and grids through the objects below, never through names it guesses from.
# Each value featlib derives itself comes from one function, so that an engine export can replace that function's
# source and leave the API as it is:
#
#   _typed_sites(pair)      types and frames of every argument, comparison and variable (engine: typed_sites)
#   canonical(scope)        canonical form of a scope (engine: canonical_form)
#   _x_correspondence(...)  the map from X's columns to the candidate's labels (engine: correspondence export)
#   _port_at(...)           the INIT port at the point and its head (engine: correspondence export)
#   _clause_tables(...)     the available tables each clause before the point produced (engine: table clause index)
#   ident_group(table)      the tables that share Ident values with a table (engine: Ident groups)
#
# The objects follow the shape of the engine's typed_sites export: a Scope is one reading (a RULE or DET body, an
# INIT key clause or port, a CHOOSE part), an Argument is one label or literal at a site, a Comparison is one
# constraint, and a Variable is one label of one scope with its occurrences.

BOX_TYPES = frozenset({'Box', 'Position', 'Offset'})
ZERO_TYPES = BOX_TYPES | {'Number'}
# The orientation types: a column of one of them ranges over a small fixed set, the same in every table that lists it.
ORIENTATION_TYPES = frozenset({'Dir', 'DiagDir', 'Dir8', 'Axis', 'DiagAxis', 'Axis4', 'C4', 'D4', 'Sym', 'Sense'})
# The sites where the zero box is the grid frame, with the relation and the column it stands at: the box a cell lies
# inside (`inside`, `interior`), the second cell of a pair that agree on a corner or a distance, and the box that
# `split` takes along an axis. Gold writes the literal 0 there.
FRAME_ZERO_SITES = frozenset({('inside', 'B'), ('interior', 'B'), ('same_corner', 'P2'), ('same_dist', 'P2'),
                              ('split', 'Along')})


def frame_zero(argument):
    """Whether an Argument is the literal 0 at a site where the zero box is the grid frame (`FRAME_ZERO_SITES`)."""
    return argument.is_zero and (argument.atom.relation, argument.column) in FRAME_ZERO_SITES

COMPARISON = frozenset({'=', '!=', '<', '>', '<=', '>='})
FACTS = frozenset({'input', 'ex_input', 'ex_output'})
FORMS = frozenset({'OR', 'NOT', 'IF', 'ALL'})
MARKS = frozenset({'ONE', 'SET'})
_SUPER = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4',
          'DiagAxis': 'Axis4', 'C4': 'D4'}
# The constraint operators with a converse, and the symmetric constraints and lib relations, as the language docs
# and docs/lib-spec.md state them: `=` and `!=`; the involutions opposite, diag_opposite, dir8_opposite, perp and
# diag_perp ("the other element of a pair"); perp_dir; d4_inverse (a group inverse); compose (addition in the box
# algebra, an abelian group); and the `same_` relations, which say that two boxes agree on a margin.
CONVERSE = {'<': '>', '>': '<', '<=': '>=', '>=': '<='}
SYMMETRIC = {'=': None, '!=': None, 'opposite': ('D', 'Opp'), 'diag_opposite': ('D', 'Opp'),
             'dir8_opposite': ('D', 'D2'), 'perp': ('A', 'A2'), 'diag_perp': ('Da', 'Da2'), 'perp_dir': ('D', 'D2'),
             'd4_inverse': ('D', 'D_inv'), 'compose': ('A', 'B'), 'same_dist': ('P1', 'P2'),
             'same_corner': ('P1', 'P2'), 'same_slab': ('P1', 'P2'), 'same_line': ('P', 'Q')}


def type_name(t):
    """A type as the export or the library spells it, normalized: `number`, Nat and Int are Number, any Pose is Pose,
    `Fixed(X)` is X, and a type parameter is None."""
    if t is None:
        return None
    t = str(t)
    if t == 'number' or t in NUMBER_SUBTYPES:
        return 'Number'
    if t.startswith('Pose') or t == 'shared-pose':
        return 'Pose'
    m = re.fullmatch(r'Fixed\((\w+)\)', t)
    if m:
        return type_name(m.group(1))
    if t.startswith('Parameter('):
        return None
    return t


def _types(t):
    """The set of types a declared column type admits: `(pose-or D4)` admits Pose and D4."""
    if t is None:
        return frozenset()
    if isinstance(t, list):
        return frozenset(x for x in (type_name(s) for s in t if isinstance(s, str) and s != 'pose-or') if x)
    n = type_name(t)
    return frozenset({n}) if n else frozenset()


def subtype(a, b):
    """True when a value of type a stands at a column of type b (Position and Offset are Boxes, Dir and DiagDir
    are Dir8, Axis and DiagAxis are Axis4)."""
    while a:
        if a == b:
            return True
        a = _SUPER.get(a)
    return False


def _meet(a, b):
    out = {x for x in a if any(subtype(x, y) for y in b)} | {y for y in b if any(subtype(y, x) for x in a)}
    return frozenset(x for x in out if not any(y != x and subtype(y, x) for y in out))


def _join(a, b):
    """The most specific types that admit every value of a and every value of b: Dir and DiagDir join at Dir8. An
    empty set is an unknown type and adds nothing."""
    if not a or not b:
        return a or b

    def up(x):
        out = []
        while x:
            out.append(x)
            x = _SUPER.get(x)
        return out
    out = set()
    for x in a:
        for y in b:
            common = [t for t in up(x) if t in up(y)]
            if common:
                out.add(common[0])
    return frozenset(x for x in out if not any(y != x and subtype(x, y) for y in out))


def _resolve(sets):
    """(the most specific types every set admits, whether two sets admit no common type)."""
    cur, clash = None, False
    for s in sets:
        if not s:
            continue
        if cur is None:
            cur = s
            continue
        m = _meet(cur, s)
        if m:
            cur = m
        else:
            clash = True
    return (cur or frozenset()), clash


def _one(types):
    return next(iter(types)) if len(types) == 1 else None


def zero_meaning(t):
    """What the reserved label `0` means at a site of type t (docs/study-reserved-zero.md): 'number zero' at a
    Number, 'zero box' at a Box, Position or Offset, None where it is illegal or the type is unknown."""
    if t == 'Number':
        return 'number zero'
    if t in BOX_TYPES:
        return 'zero box'
    return None


# ------------------------------------------------------------------------------------------------- columns

class Column:
    """One column of a table or of a relation's interface.

    name: the field's name as the table writes it (`P`, `key.E`, `key[1]`, `[3]`); column: the top-level column
    (`key`, `P`, '' for `[3]`); field: the record field (`E`, `1`) or None; type: the type, or None where it is not
    one known type; types: every type it admits; frame: the frame tag ('' for none, None where unknown); index:
    its place in the table's fields, or None for a library column.
    """
    __slots__ = ('name', 'column', 'field', 'type', 'types', 'frame', 'index', 'path')

    def __init__(self, name, types, frame='', index=None, path=None):
        self.name = name
        m = re.fullmatch(r'(.*?)\[(\d+)\]', name)
        if m:
            self.column, self.field = m.group(1), m.group(2)
        elif '.' in name:
            self.column, self.field = name.split('.', 1)
        else:
            self.column, self.field = name, None
        self.types = frozenset(types)
        self.type = _one(self.types)
        self.frame, self.index, self.path = frame, index, path

    @property
    def frame_kind(self):
        """'input', 'output', 'site' (a frame a relation or instance makes) or '' (no frame tag); None if unknown."""
        f = self.frame
        if f is None:
            return None
        return f if f in ('', 'input', 'output') else 'site'

    def __repr__(self):
        return f'Column({self.name}: {self.type or "|".join(sorted(self.types)) or "?"}, frame={self.frame!r})'


def _table_columns(self):
    """The table's columns (Column objects), in field order."""
    if getattr(self, '_columns', None) is None:
        self._columns = [Column(f['name'], _types(f.get('type')), f.get('frame', '') or '', i,
                                f.get('callable_row_path')) for i, f in enumerate(self.fields)]
    return self._columns


def _table_column(self, name):
    """The column of that field name, or None."""
    for c in self.columns():
        if c.name == name:
            return c
    return None


class Margins:
    """A decoded Position, Box or Offset: its margins (top, bottom, left, right) in its frame, the frame's tag, and
    the frame's size (height, width) where the cell's extent is resolved, else None. Equality is by frame tag and
    margins, so two values of different frames are never equal."""
    __slots__ = ('kind', 'top', 'bottom', 'left', 'right', 'frame', 'size', 'margins')

    def __init__(self, kind, v, frame, size):
        self.kind, self.frame, self.size = kind, frame, size
        self.top, self.bottom, self.left, self.right = self.margins = tuple(v)

    @property
    def row(self):
        """The row of a Position: its top margin."""
        return self.top

    @property
    def col(self):
        """The column of a Position: its left margin."""
        return self.left

    @property
    def cell(self):
        return (self.top, self.left)

    def in_frame(self):
        """True when the value lies on its frame (a Position on one of its cells, a Box inside it); None when the
        frame's size is unknown."""
        if self.size is None:
            return None
        h, w = self.size
        ok = min(self.margins) >= 0 and self.top + self.bottom <= h - 1 and self.left + self.right <= w - 1
        if self.kind == 'Position':
            ok = ok and self.top + self.bottom == h - 1 and self.left + self.right == w - 1
        return ok

    def cells(self):
        """The (row, col) cells a Box covers in its frame; None when the frame's size is unknown."""
        if self.size is None:
            return None
        h, w = self.size
        return [(r, c) for r in range(self.top, h - self.bottom) for c in range(self.left, w - self.right)]

    def is_zero(self):
        return self.margins == (0, 0, 0, 0)

    def __eq__(self, other):
        return isinstance(other, Margins) and self.frame == other.frame and self.margins == other.margins

    def __hash__(self):
        return hash((self.frame, self.margins))

    def __repr__(self):
        return f'{self.kind}{list(self.margins)}@{self.frame!r}{"" if self.size is None else list(self.size)}'


class Ident(C.namedtuple('Ident', 'table value')):
    """An Ident value with the table it belongs to. Ident values are local to their table: Idents of two tables are
    never equal. `ident_group(table)` gives the tables that share Ident values (each table alone, for now)."""


def ident_group(table):
    """The key of the tables whose Ident values are shared with this one. The export does not say which tables
    share Idents yet, so each table is its own group."""
    return getattr(table, '_key', None) or table.id


def decode(cell, column, table=None):
    """A cell's value by its column's type: a Margins for a Position, Box or Offset; an Ident for an Ident; an int
    for any other type of one number; a tuple otherwise."""
    v = cell.get('value') or []
    t = column.type
    if t in BOX_TYPES and len(v) == 4:
        ext = cell.get('extent')
        size = tuple(ext) if cell.get('extent_status') == 'resolved' and ext and len(ext) == 2 else None
        return Margins(t, v, column.frame, size)
    if t == 'Ident':
        return Ident(ident_group(table) if table is not None else None, v[0] if len(v) == 1 else tuple(v))
    return v[0] if len(v) == 1 else tuple(v)


def _table_rows(self, assignment=None, train=None):
    """Every row of the train entries with its context: (assignment, train, model, decoded row), in entry order; the
    row is a tuple of decoded values, one per column. Restrict to one assignment or train input with the arguments.
    The rows of the test entries are `test_rows`."""
    cols = self.columns()
    for e in self.entries:
        if (assignment is not None and e['assignment'] != assignment) or (train is not None and e['train'] != train):
            continue
        for r in e['rows']:
            yield e['assignment'], e['train'], e['model'], tuple(decode(c, col, self) for c, col in zip(r, cols))


def _table_test_rows(self, assignment=None, test=None):
    """Every row of the test entries with its context: (assignment, test, model, decoded row), in entry order.
    Restrict to one assignment or test input with the arguments."""
    cols = self.columns()
    for e in self.test_entries:
        if (assignment is not None and e['assignment'] != assignment) or (test is not None and e['test'] != test):
            continue
        for r in e['rows']:
            yield e['assignment'], e['test'], e['model'], tuple(decode(c, col, self) for c, col in zip(r, cols))


def _table_test_examples(self, decoded=True):
    """The rows of each test input: {(assignment, test): [rows of model 0, rows of model 1, ...]}, from the test
    entries. An entry names its test input, so a row belongs to it whatever its Example column holds. Rows are decoded
    tuples, or raw value tuples with decoded=False; a repeated row is listed once."""
    shape = (decoded, id(self.test_entries), tuple(len(e['rows']) for e in self.test_entries))
    cache = self.__dict__.setdefault('_test_examples_cache', {})
    if shape not in cache:
        cache[shape] = _table_examples_uncached(self, decoded, self.test_entries)
        if decoded:
            cache[(False,) + shape[1:]] = cache[shape][1]
            cache[shape] = cache[shape][0]
    return {k: [list(m) for m in v] for k, v in cache[shape].items()}


def _table_examples(self, decoded=True, tests=False):
    """The rows of each example: {(assignment, example): [rows of model 0, rows of model 1, ...]}, from the train
    entries (the test inputs are `test_examples`). With `tests`, the test examples are in it too, under the key
    (assignment, ('test', test index)).

    A table with an Example column is task-level: each of its entries holds the rows of every example, and a row
    belongs to the example its Example value names (a row with two Example columns of two values belongs to both).
    A table without one is per input: an entry holds the rows of its train input. Rows are decoded tuples, or raw
    value tuples with decoded=False; a row repeated by the broadcast to several train inputs is listed once.
    """
    shape = (decoded, id(self.entries), tuple(len(e['rows']) for e in self.entries))
    cache = self.__dict__.setdefault('_examples_cache', {})
    if shape not in cache:
        cache[shape] = _table_examples_uncached(self, decoded)
        if decoded:  # the raw rows come out of the same pass
            cache[(False,) + shape[1:]] = cache[shape][1]
            cache[shape] = cache[shape][0]
    out = {k: [list(m) for m in v] for k, v in cache[shape].items()}
    if tests and self.test_entries:
        out.update({(a, ('test', u)): m for (a, u), m in _table_test_examples(self, decoded).items()})
    return out


def _table_examples_uncached(self, decoded, entries=None):
    """The rows of each example (see `_table_examples`); with decoded, the pair (decoded rows, raw rows). With
    `entries` the test entries: an entry's rows all belong to its test input."""
    cols = self.columns()
    test = entries is not None
    ex = [] if test else [i for i, c in enumerate(cols) if c.type == 'Example']
    # per column: 1 for a Box, Position or Offset, 2 for an Ident, else 0; as `decode` reads them
    plan = [(2 if c.type == 'Ident' else 1 if c.type in BOX_TYPES else 0, c.type, c.frame) for c in cols]
    group = ident_group(self)
    out, raws = {}, {}
    seen = set()
    for e in (entries if test else self.entries):
        assignment, model = e['assignment'], e['model']
        for r in e['rows']:
            raw = tuple([tuple(c.get('value') or ()) for c in r])
            for x in sorted({raw[i][0] for i in ex if raw[i]}) if ex else (e['test'] if test else e['train'],):
                key = (assignment, x, model, raw)
                if key in seen:
                    continue
                seen.add(key)
                models = out.setdefault((assignment, x), [])
                while len(models) <= model:
                    models.append([])
                if not decoded:
                    models[model].append(raw)
                    continue
                row = []
                for (kind, t, frame), c, v in zip(plan, r, raw):
                    if kind == 1 and len(v) == 4:
                        ext = c.get('extent')
                        row.append(Margins(t, v, frame, tuple(ext) if c.get('extent_status') == 'resolved' and ext
                                           and len(ext) == 2 else None))
                    elif kind == 2:
                        row.append(Ident(group, v[0] if len(v) == 1 else tuple(v)))
                    else:
                        row.append(v[0] if len(v) == 1 else tuple(v))
                models[model].append(tuple(row))
                rm = raws.setdefault((assignment, x), [])
                while len(rm) <= model:
                    rm.append([])
                rm[model].append(raw)
    return (out, raws) if decoded else out


Table.columns = _table_columns
Table.column = _table_column
Table.rows = _table_rows
Table.examples = _table_examples
Table.test_rows = _table_test_rows
Table.test_examples = _table_test_examples


# --------------------------------------------------------------------------------------------------- grids

class Grid:
    """A train grid: `cells` (a tuple of rows), `height`, `width`, `size` (height, width), `array` (a numpy array,
    in the study's venv) and `colors()` (a Counter of its colors)."""

    def __init__(self, rows):
        self.cells = tuple(tuple(r) for r in rows)
        self.height = len(self.cells)
        self.width = len(self.cells[0]) if self.cells else 0
        self.size = (self.height, self.width)
        self._colors = self._most_common = None

    def __getitem__(self, rc):
        return self.cells[rc[0]][rc[1]] if isinstance(rc, tuple) else self.cells[rc]

    def colors(self):
        if self._colors is None:
            self._colors = C.Counter(v for row in self.cells for v in row)
        return C.Counter(self._colors)

    def most_common(self):
        """The set of colors with the most cells."""
        if self._most_common is None:
            c = self.colors()
            top = max(c.values()) if c else 0
            self._most_common = frozenset(k for k, v in c.items() if v == top)
        return self._most_common

    @property
    def array(self):
        import numpy
        return numpy.array(self.cells, dtype=int).reshape(self.height, self.width)


class Example:
    """One train example: `index` (its train index, which entries' `train` and Example values use), `input` and
    `output` Grids. `same_size` says whether the two grids have one size; `changed()` gives the (row, col) cells
    where the output differs from the input, or None where the sizes differ."""

    def __init__(self, index, item):
        self.index = index
        self.input, self.output = Grid(item['input']), Grid(item['output'])
        self.same_size = self.input.size == self.output.size
        self._changed = None

    def changed(self):
        if not self.same_size:
            return None
        if self._changed is None:
            self._changed = frozenset((r, c) for r in range(self.input.height) for c in range(self.input.width)
                                      if self.input.cells[r][c] != self.output.cells[r][c])
        return self._changed


# ---------------------------------------------------------------------------------------------- the library

def _decl(entry):
    sexp = (entry.get('declaration') or {}).get('sexp')
    tree = parse(sexp) if sexp else []
    return tree[0] if tree and isinstance(tree[0], list) else None


class Interface:
    """The columns a read sees: `name`, `kind` and `columns` ({field name: Column}).

    kind is 'fact', 'relation' or 'macro' (libraries.json), 'table' (an available table), 'x' (the candidate's own
    table), 'port' or 'output' (an instance port with no exported table, from the INIT clause and the component),
    'clause' (a relation before the point with no exported table, from its clause), 'proposer' or 'unknown'.
    `table` is the Table id behind it, if any; `modes` the columns the relation needs bound.
    """

    def __init__(self, name, kind, columns, table=None, modes=(), entry=None):
        self.name, self.kind, self.columns, self.table, self.modes, self.entry = name, kind, columns, table, modes, entry

    def column(self, name):
        c = self.columns.get(name)
        if c is None and name and '.' in name:
            c = self.columns.get(name.split('.', 1)[0])
        return c

    def is_record(self, column):
        """True when the column is a record whose fields its sites read (`key.E`, `t.P`)."""
        return any(n.startswith(column + '.') or n.startswith(column + '[') for n in self.columns) or (
            self.columns.get(column) is not None and getattr(self.columns[column], 'path', None) == 'record')

    def __repr__(self):
        return f'Interface({self.name}, {self.kind}, {list(self.columns.values())})'


class Lib:
    """The library interfaces of libraries.json: `interface(name)` for a relation, macro, fact or proposer, and
    `component(name)` for a component's ports. A macro column without a declared type takes the types of the
    library columns its variable stands at in the macro's body."""

    def __init__(self, entries):
        self.entries = {e['name']: e for e in entries or [] if isinstance(e, dict) and e.get('name')}
        self._ifaces, self._comps = {}, {}

    def kind(self, name):
        e = self.entries.get(name)
        return e.get('kind') if e else None

    def interface(self, name, depth=0):
        if name not in self._ifaces:
            self._ifaces[name] = None
            try:
                self._ifaces[name] = self._build(name, depth)
            except Exception:
                self._ifaces[name] = None
        return self._ifaces[name]

    def _build(self, name, depth):
        e = self.entries.get(name)
        if not e or e.get('kind') == 'component':
            return None
        kind = e.get('kind')
        tree = _decl(e)
        if not tree:
            return None
        specs, modes, body = [], (), []
        for part in tree[2:]:
            if isinstance(part, list) and part and part[0] == 'columns':
                for c in part[1:]:
                    if isinstance(c, str):
                        specs.append((c, c, None))
                    elif kind == 'macro':
                        specs.append((c[0], c[1] if len(c) > 1 else c[0], c[2] if len(c) > 2 else None))
                    else:
                        specs.append((c[0], c[0], c[1] if len(c) > 1 else None))
            elif isinstance(part, list) and part and part[0] == 'modes':
                modes = tuple(m for m in part[1] if isinstance(m, str)) if len(part) > 1 and isinstance(part[1], list) else ()
            elif isinstance(part, list) and part and part[0] not in ('frames', 'types'):
                body.append(part)
        if kind == 'proposer' and not body:
            impl = (e.get('arclog_implementation') or {}).get('sexp')
            t = parse(impl)[0] if impl else []
            body = [q for q in t[2:] if isinstance(q, list)]
        inferred = self._infer(body, depth) if body and depth < 6 else {}
        frames = {('input', 'P'): 'input', ('ex_input', 'P'): 'input', ('ex_output', 'P'): 'output'}
        columns = {}
        for i, (col, var, t) in enumerate(specs):
            ts = _types(t) if t is not None else inferred.get(var, frozenset())
            columns[col] = Column(col, ts, frames.get((name, col), '' if kind == 'fact' else None), None)
        return Interface(name, kind, columns, modes=modes, entry=e)

    def _infer(self, body, depth):
        """{variable: types} of a macro body. The sites in one conjunction meet; the branches of an `OR`, and the
        then and the else of an `IF`, join, since a variable they export takes its values from any branch."""
        def scope(items):
            sets = C.defaultdict(list)
            for it in items:
                if not isinstance(it, list) or not it:
                    continue
                if not isinstance(it[0], str):
                    for v, t in scope(it).items():
                        sets[v].append(t)
                elif it[0] in ('OR', 'IF'):
                    parts = [p for p in it[1:] if isinstance(p, list)]
                    if it[0] == 'IF' and parts:
                        for v, t in scope(parts[0]).items():
                            sets[v].append(t)
                        parts = parts[1:]
                    joined = {}
                    for p in parts:
                        for v, t in scope(p).items():
                            joined[v] = _join(joined[v], t) if v in joined else t
                    for v, t in joined.items():
                        sets[v].append(t)
                elif it[0] in FORMS:
                    for v, t in scope(it[1:]).items():
                        sets[v].append(t)
                elif it[0] not in MARKS and not it[0].startswith(':') and it[0] not in COMPARISON:
                    iface = self.interface(it[0], depth + 1)
                    if iface is None:
                        continue
                    for col, args in _raw_sites(it):
                        c = iface.columns.get(col)
                        for arg in args:
                            if isinstance(arg, str) and c is not None:
                                sets[arg.lstrip('*^')].append(c.types)
            return {v: _resolve(ts)[0] for v, ts in sets.items()}
        return scope(body)

    def component(self, name):
        """{'inputs': {port: [(column, type or None, type parameter or None)]}, 'outputs': {...},
        'from_key': {port: bool}, 'key': the key column's name or None}; None for no such component."""
        if name in self._comps:
            return self._comps[name]
        e = self.entries.get(name)
        out = None
        if e and e.get('kind') == 'component' and isinstance(e.get('ports'), dict):
            out = {'inputs': {}, 'outputs': {}, 'from_key': {}, 'key': None}
            for side in ('inputs', 'outputs'):
                for port in e['ports'].get(side) or []:
                    cols = []
                    for c in port.get('columns') or []:
                        expr = c.get('type_expression', '')
                        m = re.search(r'name: "(\w+)"', expr)
                        param = m.group(1) if expr.startswith('Parameter') and m else None
                        cname = (c.get('name') or {}).get('name')
                        cols.append((cname, type_name(expr), param))
                        if param == 'Key' and out['key'] is None:
                            out['key'] = cname
                    out[side][port['name']] = cols
                    if side == 'inputs':
                        out['from_key'][port['name']] = bool(port.get('from_key'))
        self._comps[name] = out
        return out


@functools.lru_cache(maxsize=8)
def _lib(path):
    return Lib(_shared(path))


def _raw_sites(atom):
    """(column, arguments) for each site of an atom; an elided site `*P` is the column P with argument `*P`."""
    for el in atom[1:]:
        if isinstance(el, str):
            yield el.lstrip('*^'), [el]
        elif el and isinstance(el[0], str) and el[0].startswith(':'):
            yield el[0][1:], el[1:]


# ------------------------------------------------------------------------------------------- clause model

class Argument:
    """One label or literal at a site, or one operand of a comparison (the engine's `arguments`).

    atom: its Atom; scope: its Scope; path: the atom's path, then the site's and the argument's index.
    column, field, name: the column the site reads, the record field (or None) and `column.field`; for an operand
    of a comparison, column is '' and name is the operand's place, 'first' or 'second'.
    term: the text as written (`*P`, `P`, `^Id`, `0`); label: the label's spelling, None at a literal;
    literal: zero_meaning(...) of the literal `0` ('number zero', 'zero box', or None where it is illegal), and
    None where the argument is a label; is_zero: True for the literal `0`.
    binds: the site makes its label (`*L` or `^L`); key: the label is a key column (`^L`); joins: a label the site
    does not make. head: a head site of an INIT port (it projects the label onto the port's column).
    column_type: the column's type (None where it is not one known type); column_types: every type it admits;
    resolved_type: the label's type, or the column's type at a literal (for an operand, the other operand's).
    frame: the column's frame tag where the column belongs to a table, else the label's frame; None if unknown.
    variable: the label's Variable.
    """
    __slots__ = ('atom', 'scope', 'path', 'column', 'field', 'name', 'term', 'label', 'literal', 'is_zero', 'binds',
                 'key', 'head', 'column_type', 'column_types', 'resolved_type', 'frame', 'variable')

    def __init__(self, atom, scope, path, column, field, term, head=False):
        self.atom, self.scope, self.path, self.column, self.field, self.term = atom, scope, path, column, field, term
        self.name = column if not field else f'{column}.{field}'
        self.head = head
        self.is_zero = term == '0'
        self.binds = term[:1] in ('*', '^') and len(term) > 1
        self.key = term[:1] == '^' and len(term) > 1
        self.label = None if self.is_zero else term.lstrip('*^') or None
        self.literal = None
        self.column_type, self.column_types, self.resolved_type, self.frame, self.variable = None, frozenset(), None, None, None

    @property
    def joins(self):
        return self.label is not None and not self.binds

    def __repr__(self):
        return f'Argument({self.name}={self.term}: {self.resolved_type})'


class Atom:
    """One atom of a scope: a read of a relation, or a comparison.

    relation: its head (`inside`, `&box.box`, `input`, `<=`); kind: 'comparison', or its interface's kind ('fact',
    'relation', 'macro', 'table', 'x', 'port', 'output', 'clause', 'unknown'); interface: the Interface it reads
    (None for a comparison); arguments: its Arguments in text order (for a comparison, `first` and `second`);
    operator: the comparison's operator, or None.
    Context: negated (below a NOT), branch (the OR branches it stands in, outer first, as (OR path, branch index)),
    quantifier ('domain' or 'body' of the innermost ALL, or None), conditional ('test', 'then' or 'else' of the
    innermost IF, or None), conjunction (the id of the list of conjuncts it stands in, unique in its clause).
    path: its index path in the scope's body (relation-site frame tags use these indices after the point path).
    """
    __slots__ = ('relation', 'kind', 'interface', 'arguments', 'operator', 'scope', 'path', 'tree', 'negated',
                 'branch', 'quantifier', 'conditional', 'conjunction')

    def __init__(self, tree, scope, path, ctx):
        self.tree, self.scope, self.path = tree, scope, path
        self.relation = tree[0]
        self.negated, self.branch, self.quantifier, self.conditional, self.conjunction = ctx
        self.operator = tree[0] if tree[0] in COMPARISON else None
        self.kind, self.interface, self.arguments = 'comparison' if self.operator else 'unknown', None, []

    @property
    def positive(self):
        return not self.negated

    @property
    def first(self):
        return self.arguments[0] if self.operator and self.arguments else None

    @property
    def second(self):
        return self.arguments[1] if self.operator and len(self.arguments) > 1 else None

    @property
    def table(self):
        """The Table the atom reads (an available table or X), loaded; None for a library relation."""
        i = self.interface
        pair = self.scope.clause.pair if self.scope and self.scope.clause else None
        return pair.table(i.table) if pair is not None and i is not None and i.table else None

    @property
    def text(self):
        return unparse(self.tree)

    def key(self):
        """The atom up to binding marks, in a form that does not depend on its site order, the operand order of a
        symmetric relation or comparison, or the direction of a converse operator: (negated, relation, sorted
        (column, label or '0') pairs). Two atoms of one scope are the same atom when their keys are equal. Columns
        are full field paths, and a read of a table is named by the table, so `(:a (:P X))` and `(:b (:P X))`
        differ."""
        return _atom_key(self, lambda a: a.label if a.label is not None else '0')

    def __repr__(self):
        return f'Atom({self.text})'


class Variable:
    """One label of one scope (the engine's `variables`).

    label: its spelling; occurrences: its Arguments in text order (sites and comparison operands); binders: the
    sites that make it; joins: the other sites; resolved_type / types: its type and every type its sites admit
    together; clash: True when two of its sites admit no common type; frame: its frame tag where one is known
    (from X or from the tables it is read from), else None; frames: every such tag; column: the X Column it
    is, for the candidate's labels; key: made with `^`.
    """
    __slots__ = ('scope', 'label', 'occurrences', 'resolved_type', 'types', 'clash', 'frame', 'frames', 'column')

    def __init__(self, scope, label):
        self.scope, self.label, self.occurrences = scope, label, []
        self.resolved_type, self.types, self.clash, self.frame, self.frames, self.column = None, frozenset(), False, None, frozenset(), None

    @property
    def binders(self):
        return [a for a in self.occurrences if a.binds]

    @property
    def joins(self):
        return [a for a in self.occurrences if a.joins and not a.head and a.atom is not None and a.atom.operator is None]

    @property
    def sites(self):
        return [a for a in self.occurrences if a.atom is not None and a.atom.operator is None]

    @property
    def key(self):
        return any(a.key for a in self.occurrences)

    def __repr__(self):
        return f'Variable({self.label}: {self.resolved_type}, {len(self.occurrences)} occurrences)'


class Scope:
    """One reading (the engine's `scopes`): a RULE or DET body, an INIT key clause or port, or a part of a CHOOSE
    or RIGID_DET.

    clause: its Clause; name: 'body', 'key', the port's name, or the part's name; body: its parsed list of conjuncts;
    head: the head Arguments of an INIT port; atoms: every Atom in text order, through NOT, OR, IF and ALL
    (comparisons included); arguments, comparisons, literals (the Arguments that hold `0`); variables:
    {label: Variable}, its own labels and the key labels it reads; marks: its ONE and SET forms; keyed: True
    for a port inside an INIT key clause, which reads the key's labels.
    """

    def __init__(self, clause, name, body, path):
        self.clause, self.name, self.body, self.path = clause, name, body, path
        self.head, self.atoms, self.variables, self.marks, self.keyed = [], [], {}, [], False
        self._at, self._conj = {}, 0

    @property
    def arguments(self):
        return [a for at in self.atoms for a in at.arguments]

    @property
    def comparisons(self):
        return [a for a in self.atoms if a.operator]

    @property
    def literals(self):
        return [a for a in self.head + self.arguments if a.is_zero]

    def atom_at(self, path):
        return self._at.get(tuple(path))

    def creation_order(self):
        """The labels in the order they are made: the first `*` or `^` of each, in text order (the engine's label
        order, which numbers the `[k]` columns of a Det X)."""
        out = []
        for a in self.arguments:
            if a.binds and a.label not in out:
                out.append(a.label)
        return out

    def clause_labels(self):
        """The labels that are columns of the scope's relation, in the order they are made: those made outside every
        OR, NOT, ALL and IF test, and those an OR's first branch (or an IF's then) makes and every later branch
        names. A label local to a branch is left out (the engine numbers a Det X's `[k]` columns over these)."""
        named = C.defaultdict(set)
        for a in self.arguments:
            if a.label:
                for orp, b in a.atom.branch:
                    named[a.label].add((orp, b))
                if a.atom.conditional:
                    named[a.label].add(('if', a.atom.conditional))
        out = []
        for a in self.arguments:
            if not a.binds or a.label in out or a.atom.negated or a.atom.quantifier or a.atom.conditional == 'test':
                continue
            ok = True
            for orp, b in a.atom.branch:
                node = _at_path(self.body, orp)
                n = len(node) - 1 if isinstance(node, list) else 0
                if b != 1 or any((orp, k) not in named[a.label] for k in range(2, n + 1)):
                    ok = False
            if a.atom.conditional == 'then' and ('if', 'else') not in named[a.label]:
                ok = False
            if ok:
                out.append(a.label)
        return out

    def key_order(self):
        """The `^` labels in text order: the key's columns."""
        out = []
        for a in self.arguments:
            if a.key and a.label not in out:
                out.append(a.label)
        return out

    def __repr__(self):
        return f'Scope({self.name}, {len(self.atoms)} atoms)'


class Clause:
    """One clause: a clause before the point, or the candidate's (Pair.clause).

    index: its line in the program (the point's for the candidate); keyword: RULE, DET, INIT, CHOOSE, RIGID_DET or
    OUT; relation: the relation it declares (`&r`; at an INIT, the instance); component and proposers: an INIT's
    component, and the proposers a DET names; scopes: its Scopes, in text order; key: an INIT's key Scope or None;
    atoms and variables: over its scopes; table_ids and tables(): the available tables it produced; defines: the
    relation names it declares. On the candidate's clause: body is the candidate's Scope, port the INIT port at
    the point (None elsewhere), before the INIT's scopes before that port, and x_columns {X column name: Variable}.
    """

    def __init__(self, pair, index, tree):
        self.pair, self.index, self.tree = pair, index, tree
        self.keyword = tree[0] if tree and isinstance(tree[0], str) else None
        self.relation = tree[1] if len(tree) > 1 and isinstance(tree[1], str) else None
        self.component = tree[2] if self.keyword == 'INIT' and len(tree) > 2 and isinstance(tree[2], str) else None
        self.proposers = [s for s in tree[2:] if isinstance(s, str)] if self.keyword in ('DET', 'DET_OR_RULE', 'RULE_OR_DET') else []
        self.scopes, self.key, self.table_ids, self.body, self.port, self.before, self.x_columns = [], None, [], None, None, [], {}

    @property
    def text(self):
        return unparse(self.tree)

    @property
    def atoms(self):
        return [a for s in self.scopes for a in s.atoms]

    @property
    def variables(self):
        return [v for s in self.scopes for v in s.variables.values()]

    @property
    def defines(self):
        if self.keyword == 'INIT':
            return {t.name for t in self.tables()} | ({self.relation} if self.relation else set())
        return {self.relation} if self.relation else set()

    def tables(self):
        return [self.pair.table(t) for t in self.table_ids]

    def port_interface(self, port, lib):
        """The interface of the instance port `port` (an output or an input) where no table was exported: the
        component's columns, the key's fields from the key clause, and a written input's head columns."""
        comp = lib.component(self.component) if self.component else None
        if comp is None:
            return Interface(f'{self.relation}.{port}', 'unknown', {})
        key_labels = self.key.key_order() if self.key else []
        kv = self.key.variables if self.key else {}
        out, kind = {}, 'output' if port in comp['outputs'] else 'port'
        for cname, t, param in comp['outputs'].get(port) or comp['inputs'].get(port) or []:
            if param == 'Key':
                for lab in key_labels:
                    v = kv.get(lab)
                    out[f'{cname}.{lab}'] = Column(f'{cname}.{lab}', v.types if v else (), None)
            else:
                out[cname] = Column(cname, {t} if t else (), None)
        written = next((s for s in self.scopes if s.name == port and s.head), None)
        if written is not None:
            for a in written.head:
                if a.column in out and not a.field:
                    del out[a.column]
                out[a.name] = Column(a.name, a.variable.types if a.variable else (), None)
        return Interface(f'{self.relation}.{port}', kind, out)

    def __repr__(self):
        return f'Clause({self.keyword} {self.relation}, {len(self.scopes)} scopes)'


def _at_path(tree, path):
    node = tree
    for i in path:
        if not isinstance(node, list) or i >= len(node):
            return None
        node = node[i]
    return node


def _atom_key(atom, name):
    """(negated, relation, operator-and-arguments) with symmetric and converse forms in one order; name(argument)
    gives the label's name in the key."""
    rel = _relation_id(atom)
    if atom.operator:
        op, x, y = atom.operator, name(atom.first) if atom.first else None, name(atom.second) if atom.second else None
        if op in ('>', '>='):
            op, x, y = CONVERSE[op], y, x
        if op in ('=', '!=') and None not in (x, y):
            x, y = sorted((x, y), key=repr)
        return (atom.negated, rel, op, x, y)
    sites = [(_column_id(a), name(a)) for a in atom.arguments]
    sym = SYMMETRIC.get(atom.relation)
    if sym and atom.interface is not None and atom.interface.kind in ('relation', 'macro'):
        p, q = [s for s in sites if s[0] == sym[0]], [s for s in sites if s[0] == sym[1]]
        if len(p) == 1 and len(q) == 1 and repr(q[0][1]) < repr(p[0][1]):
            sites = [s for s in sites if s[0] not in sym] + [(sym[0], q[0][1]), (sym[1], p[0][1])]
    return (atom.negated, rel, tuple(sorted(sites, key=repr)))


def _relation_id(atom):
    i = atom.interface
    if atom.operator:
        return ('comparison',)
    if i is not None and i.table:
        return ('table', i.table)
    return (atom.kind, atom.relation)


def _column_id(arg):
    """A site's column, by name for a library relation or fact and by place for a table or a relation whose column
    names are labels, so that renaming those labels keeps the id."""
    i = arg.atom.interface if arg.atom is not None else None
    if i is None or i.kind in ('relation', 'macro', 'fact', 'proposer', 'unknown'):
        return arg.name
    names = list(i.columns)
    if arg.name in i.columns:
        return ('c', names.index(arg.name))
    if arg.column in i.columns:
        return ('c', names.index(arg.column), arg.field)
    return arg.name


# --------------------------------------------------------------------------------------- building clauses

def _walk_items(items, start, scope, ctx, base, resolver):
    """Make the Atoms of a list of conjuncts (items[start:]), with their context, into scope."""
    scope._conj += 1
    conj = (scope.name, scope._conj)
    neg, branch, quant, cond, _ = ctx
    for i in range(start, len(items)):
        it, p = items[i], base + (i,)
        if not isinstance(it, list) or not it:
            continue
        h = it[0]
        if not isinstance(h, str):
            _walk_items(it, 0, scope, ctx, p, resolver)
        elif h == 'NOT':
            _walk_items(it, 1, scope, (True, branch, quant, cond, None), p, resolver)
        elif h == 'OR':
            for b in range(1, len(it)):
                if isinstance(it[b], list):
                    _walk_items(it[b], 0, scope, (neg, branch + ((p, b),), quant, cond, None), p + (b,), resolver)
        elif h == 'IF':
            for b, part in zip((1, 2, 3), ('test', 'then', 'else')):
                if b < len(it) and isinstance(it[b], list):
                    _walk_items(it[b], 0, scope, (neg, branch, quant, part, None), p + (b,), resolver)
        elif h == 'ALL':
            for b, part in zip((1, 2), ('domain', 'body')):
                if b < len(it) and isinstance(it[b], list):
                    _walk_items(it[b], 0, scope, (neg, branch, part, cond, None), p + (b,), resolver)
        elif h in MARKS:
            scope.marks.append(it)
        elif h.startswith(':'):
            continue
        else:
            _make_atom(it, scope, p, (neg, branch, quant, cond, conj), resolver)


def _make_atom(tree, scope, path, ctx, resolver):
    atom = Atom(tree, scope, path, ctx)
    if atom.operator:
        for k, name in ((1, 'first'), (2, 'second')):
            if k < len(tree) and isinstance(tree[k], str):
                atom.arguments.append(Argument(atom, scope, path + (k,), '', None, tree[k]))
                atom.arguments[-1].name = name
    else:
        iface = resolver.interface(atom.relation, scope.clause)
        atom.interface = iface
        atom.kind = iface.kind if iface is not None else 'unknown'
        for k, (col, args) in enumerate(_raw_sites(tree)):
            for j, (column, field, term) in enumerate(_leaves(col, args, iface)):
                atom.arguments.append(Argument(atom, scope, path + (k + 1, j), column, field, term))
    scope.atoms.append(atom)
    scope._at[path] = atom
    return atom


def _leaves(col, args, iface):
    """(column, field, term) for each label or literal of one site."""
    if len(args) == 1 and isinstance(args[0], str):
        if iface is not None and iface.is_record(col):
            return [(col, args[0].lstrip('*^'), args[0])]
        return [(col, None, args[0])]
    out = []
    for a in args:
        if isinstance(a, str):
            out.append((col, a.lstrip('*^'), a))
        elif isinstance(a, list) and a and isinstance(a[0], str) and a[0].startswith(':'):
            for t in a[1:]:
                if isinstance(t, str):
                    out.append((col, a[0][1:], t))
                elif isinstance(t, list) and t and isinstance(t[0], str) and t[0].startswith(':'):
                    out += [(col, a[0][1:] + '.' + t[0][1:], u) for u in t[1:] if isinstance(u, str)]
    return out


def _head(scope, heads, resolver):
    """The head Arguments of an INIT port, read against the component's port."""
    comp = resolver.lib.component(scope.clause.component) if scope.clause.component else None
    cols = {c: (t, param) for c, t, param in (comp['inputs'].get(scope.name, []) if comp else [])}
    iface = Interface(scope.name, 'port', {c: Column(c, {t} if t else ()) for c, (t, _) in cols.items()})
    for k, (col, args) in enumerate(_raw_sites(['head'] + list(heads))):
        for j, (column, field, term) in enumerate(_leaves(col, args, None)):
            a = Argument(None, scope, scope.path + (1, k, j), column, field, term, head=True)
            c = iface.columns.get(column)
            a.column_types = c.types if c is not None and not field else frozenset()
            scope.head.append(a)


def _type_scope(scope, seeds=None):
    """Give each Argument and Variable of the scope its types and frames (featlib's own derivation)."""
    sets = C.defaultdict(list)
    frames = C.defaultdict(set)
    for a in scope.arguments:
        if a.atom.operator:
            continue
        c = a.atom.interface.column(a.name) if a.atom.interface is not None else None
        if c is not None:
            a.column_types, a.column_type = c.types, c.type
            a.frame = c.frame
            if a.label and c.frame:
                frames[a.label].add(c.frame)
        if a.label:
            sets[a.label].append(a.column_types)
    for a in scope.head:
        if a.label:
            sets[a.label].append(a.column_types)
    for lab, types in (seeds or {}).items():
        sets[lab].append(types)
    for _ in range(2):
        for cmp in scope.comparisons:
            x, y = cmp.first, cmp.second
            if x is not None and y is not None and x.label and y.label:
                t = _meet(_resolve(sets[x.label])[0], _resolve(sets[y.label])[0])
                if t:
                    sets[x.label].append(t)
                    sets[y.label].append(t)
    for a in scope.head + scope.arguments:
        if a.label is None:
            continue
        v = scope.variables.get(a.label)
        if v is None:
            v = scope.variables[a.label] = Variable(scope, a.label)
        v.occurrences.append(a)
        a.variable = v
    for lab, v in scope.variables.items():
        v.types, v.clash = _resolve(sets[lab])
        v.resolved_type = _one(v.types)
        v.frames = frozenset(frames[lab])
        v.frame = _one(v.frames) if v.frames else ('' if v.resolved_type and v.resolved_type not in BOX_TYPES else None)
    _settle(scope)


def _settle(scope):
    """Copy each Variable's type and frame to its Arguments, and type the literals."""
    for a in scope.head + scope.arguments:
        if a.variable is not None:
            a.resolved_type = a.variable.resolved_type
            if a.frame is None:
                a.frame = a.variable.frame
        elif a.is_zero:
            if a.atom is not None and a.atom.operator:
                other = a.atom.first if a is a.atom.second else a.atom.second
                a.resolved_type = other.variable.resolved_type if other is not None and other.variable else None
            else:
                a.resolved_type = _one(_resolve([a.column_types])[0])
            a.literal = zero_meaning(a.resolved_type)


class _Resolver:
    """Finds the interface each relation name reads: an available table, a library relation, or a clause before."""

    def __init__(self, lib, schemas):
        self.lib, self.tables, self.defined, self.instances = lib, {}, {}, {}
        for s in schemas:
            name = s.get('source_name')
            if name and name not in self.tables:
                cols = {f['name']: Column(f['name'], _types(f.get('type')), f.get('frame', '') or '', i,
                                          f.get('callable_row_path')) for i, f in enumerate(s.get('fields') or [])}
                self.tables[name] = Interface(name, 'fact' if name in FACTS else 'table', cols, table=s.get('id'))

    def interface(self, rel, clause=None):
        if rel in COMPARISON:
            return None
        if rel in self.tables:
            return self.tables[rel]
        if rel in self.defined:
            return self.defined[rel]
        if rel.startswith('&'):
            base, _, port = rel.partition('.')
            owner = self.instances.get(base) or (clause if clause is not None and clause.relation == base else None)
            if port and owner is not None and owner.keyword == 'INIT':
                return owner.port_interface(port, self.lib)
            return Interface(rel, 'unknown', {})
        return self.lib.interface(rel) or Interface(rel, 'unknown', {})

    def register(self, clause):
        if clause.keyword == 'INIT' and clause.relation:
            self.instances[clause.relation] = clause
        elif clause.relation and clause.relation not in self.tables:
            if clause.proposers:
                iface = self.lib.interface(clause.proposers[0])
                if iface is not None:
                    self.defined[clause.relation] = Interface(clause.relation, 'clause', dict(iface.columns))
                    return
            cols = {}
            for s in clause.scopes:
                for lab in s.creation_order():
                    v = s.variables.get(lab)
                    cols.setdefault(lab, Column(lab, v.types if v else (), None))
            self.defined[clause.relation] = Interface(clause.relation, 'clause', cols)


def _build_clause(pair, index, line, resolver, candidate=None):
    """A typed Clause from one line. candidate: (point, kind, x schema) for the candidate's clause."""
    tree = parse(line)
    tree = tree[0] if tree and isinstance(tree[0], list) else []
    clause = Clause(pair, index, tree)
    kw = clause.keyword
    ctx = (False, (), None, None, None)
    if kw == 'INIT':
        key_labels = {}
        for gi, g in enumerate(tree[3:]):
            if not isinstance(g, list) or not g or not isinstance(g[0], str):
                continue
            gp = (3 + gi,)
            if g[0] == 'key':
                ks = Scope(clause, 'key', g[1] if len(g) > 1 and isinstance(g[1], list) else [], gp + (1,))
                _walk_items(ks.body, 0, ks, ctx, (), resolver)
                _type_scope(ks)
                clause.key = ks
                clause.scopes.append(ks)
                key_labels = {lab: ks.variables[lab].types for lab in ks.key_order() if lab in ks.variables}
                ports = [(gp + (2 + k,), q) for k, q in enumerate(g[2:])]
                keyed = True
            else:
                ports, keyed = [(gp, g)], False
            for pp, q in ports:
                if not isinstance(q, list) or not q or not isinstance(q[0], str):
                    continue
                s = Scope(clause, q[0], q[2:], pp)
                s.keyed = keyed
                _head(s, q[1] if len(q) > 1 and isinstance(q[1], list) else [], resolver)
                _walk_items(s.body, 0, s, ctx, (), resolver)
                _type_scope(s, {k: v for k, v in key_labels.items()} if keyed else None)
                clause.scopes.append(s)
    elif kw in ('CHOOSE', 'RIGID_DET'):
        def parts(items, base):
            for k, part in enumerate(items):
                if not isinstance(part, list) or not part:
                    continue
                if isinstance(part[0], str) and part[0] in ('for', 'instance', 'key'):
                    s = Scope(clause, part[0], part[1] if len(part) > 1 and isinstance(part[1], list) else [], base + (k, 1))
                    _walk_items(s.body, 0, s, ctx, (), resolver)
                    _type_scope(s)
                    clause.scopes.append(s)
                    parts(part[2:], base + (k,))
                elif isinstance(part[0], str) and part[0] in ('from', 'never'):
                    s = Scope(clause, part[0], part[1:], base + (k,))
                    _walk_items(s.body, 0, s, ctx, (), resolver)
                    _type_scope(s)
                    clause.scopes.append(s)
                else:
                    s = Scope(clause, 'part', [part], base + (k,))
                    _walk_items(s.body, 0, s, ctx, (), resolver)
                    _type_scope(s)
                    clause.scopes.append(s)
        parts(tree[2:], ())
    elif kw is not None:
        body = [q for q in tree[2:] if isinstance(q, list)]
        s = Scope(clause, 'body', body, (2,))
        _walk_items(body, 0, s, ctx, (), resolver)
        _type_scope(s)
        clause.scopes.append(s)
    return clause


def _candidate_body_scope(clause, point, kind):
    """The candidate's Scope in its clause, and the INIT scopes before it."""
    if kind.startswith('INIT'):
        found = _locate_port(unparse(clause.tree), point) if clause.tree else None
        if found is None:
            return None, []
        _, group, item = found
        if item == 0:
            body = clause.key
        else:
            name = group[1 + item][0] if item else group[0]
            body = next((s for s in reversed(clause.scopes) if s.name == name), None)
        before = [s for s in clause.scopes if s is not body]
        return body, before
    return (clause.scopes[0] if clause.scopes else None), []


def _x_correspondence(clause, xschema, kind, lib):
    """{X column name: the Variable it holds} (featlib's reading; the engine's correspondence export will
    replace it). Rule: X names each column by its label. Det: column `[k]` holds the k-th label made in the form.
    INIT key: `[k]` is the k-th `^` label. A Det or INIT key column written with a name holds the label of that name.
    INIT input: `key[k]` is the k-th key label of the INIT's key clause, `key.L` is its key label L, and each other
    column is the label of the port's head site on that column (by slot in a record)."""
    out = {}
    body = clause.body
    if body is None or not xschema:
        return out
    made = body.clause_labels()
    keys = body.key_order()
    comp = lib.component(clause.component) if clause.component else None
    keycol = comp['key'] if comp else 'key'
    for f in xschema.get('fields') or []:
        path = [p for p in f.get('callable_row_path') or [] if isinstance(p, dict)]
        names = [p.get('name') for p in path if p.get('kind') == 'written']
        written = names[0] if names else None
        slot = next((p.get('slot') for p in path if p.get('kind') == 'slot'), None)
        lab = None
        if kind == 'Rule':
            lab = written
        elif kind == 'Det' and slot is not None and slot < len(made):
            lab = made[slot]
        elif kind == 'INIT key' and slot is not None and slot < len(keys):
            lab = keys[slot]
        elif kind in ('Det', 'INIT key') and slot is None:
            lab = written
        elif kind == 'INIT input':
            if written == keycol and clause.key is not None and (slot is not None or len(names) > 1):
                kl = clause.key.key_order()
                lab = (kl[slot] if slot < len(kl) else None) if slot is not None else names[1] if names[1] in kl else None
            else:
                heads = [a for a in body.head if a.column == written]
                if slot is not None and slot < len(heads):
                    lab = heads[slot].label
                elif slot is None and len(heads) == 1:
                    lab = heads[0].label
        if lab is not None and lab in body.variables:
            out[f['name']] = body.variables[lab]
        elif lab is not None and kind == 'INIT input' and clause.key is not None and lab in clause.key.variables:
            out[f['name']] = clause.key.variables[lab]
    return out


def _clause_tables(clause, schemas):
    """The ids of the available tables a clause before the point produced, by the names it declares (featlib's
    reading; the engine's table clause index will replace it)."""
    if not clause.relation:
        return []
    out = []
    for tid, s in schemas.items():
        name = s.get('source_name') or ''
        if name == clause.relation or (clause.keyword in ('INIT', 'RIGID_DET') and name.startswith(clause.relation + '.')):
            out.append(tid)
    return sorted(out)


def _typed_prefix(pair):
    """(the typed Clauses before the point, the Resolver that has registered them). They depend on the clauses before
    the point, the available tables and the libraries, and on no candidate, so that `_typed_sites` can take them
    from a caller that types many candidates at one point."""
    lib = _lib(str(pair._libraries))
    avail = {tid: s for tid, s in pair._schemas().items() if tid != 'X'}
    resolver = _Resolver(lib, avail.values())
    before_ = []
    for i, line in enumerate(pair.prefix):
        try:
            c = _build_clause(pair, i, line, resolver)
        except Exception:
            c = Clause(pair, i, [])
        c.table_ids = _clause_tables(c, avail)
        resolver.register(c)
        _native_types(pair, c, False)
        before_.append(c)
    return before_, resolver


def _typed_sites(pair, prefix=None):
    """The typed clauses of a pair: (clauses before the point, the candidate's clause). This is featlib's own
    derivation of types and frames; the engine's typed_sites export will replace it. `prefix` is the result of
    `_typed_prefix` for the same point, where the caller has it."""
    lib = _lib(str(pair._libraries))
    schemas = pair._schemas()
    before_, resolver = prefix if prefix is not None else _typed_prefix(pair)
    line = pair._point_line()
    xs = schemas.get('X')
    try:
        cand = _build_clause(pair, pair.point[0], line or '()', resolver)
    except Exception:
        cand = Clause(pair, pair.point[0], [])
    cand.body, cand.before = _candidate_body_scope(cand, pair.point, pair.kind) if cand.tree else (None, [])
    _native_types(pair, cand, True)
    if cand.body is not None and pair.kind.startswith('INIT') and cand.body.name != 'key':
        cand.port = cand.body.name
    if cand.body is not None and xs is not None:
        xcols = {f['name']: Column(f['name'], _types(f.get('type')), f.get('frame', '') or '', i, f.get('callable_row_path'))
                 for i, f in enumerate(xs.get('fields') or [])}
        for name, v in _x_correspondence(cand, xs, pair.kind, lib).items():
            col = xcols[name]
            v.column = col
            if col.types:
                v.types, v.resolved_type = col.types, col.type
            if col.frame:
                v.frames = v.frames | {col.frame}
            v.frame = col.frame
            cand.x_columns[name] = v
        for s in {id(v.scope): v.scope for v in cand.x_columns.values()}.values():
            _settle(s)
    return before_, cand


# ------------------------------------------------------------------------------------------- native keys

# The exporter's native key `types_frames_v1`, read for a clause before the point where the point's key has a complete
# entry for it that names the labels of the clause's one scope; else the Python derivation of this module stays. The
# clauses before the point are the same in both views, so both read them alike. The candidate's clause takes the
# Python derivation in both views: the exporter writes a key for the mutant's clause only (the point's keys cover the
# clauses before the point, and nothing covers gold's clause), so a native read of the candidate would differ
# between the views. `canonical_clauses_v1` and `x_nf4f_v1` are not read, for the same reason: `canonical` is the
# Python form for every scope, and `Pair.x_normal()` gives None.
USE_NATIVE = True
_NATIVE_LOG = None  # a list, in checks: the places where both a native entry and the Python derivation exist


def _native_raw(pair, key, index, candidate):
    """The entry of the native key for the clause (any status), or None."""
    if not USE_NATIVE:
        return None
    if candidate:
        return None  # the candidate is derived in Python in both views
    point = getattr(pair, '_native_point', None)
    top = point.get(key) if isinstance(point, dict) else None
    if not isinstance(top, dict):
        return None
    by_path = top.get('_by_index')
    if by_path is None:
        by_path = top['_by_index'] = {e['path'][0]: e for e in top.get('prefix') or [] if len(e.get('path', [])) == 1}
    return by_path.get(index)


def _native_entry(pair, key, clause, candidate):
    e = _native_raw(pair, key, clause.index, candidate)
    return e if e is not None and e.get('status') == 'complete' else None


def _native_types(pair, clause, candidate):
    """Give the Variables of the clause's one scope the types and frames of the native `types_frames_v1`."""
    entry = _native_entry(pair, 'types_frames_v1', clause, candidate)
    if entry is None or len(clause.scopes) != 1:
        return
    scope = clause.scopes[0]
    labels = entry.get('labels') or []
    if {l['label_spelling'] for l in labels} != set(scope.variables):
        return
    for l in labels:
        if l.get('status') != 'complete' or not l.get('resolved_type'):
            continue
        v = scope.variables[l['label_spelling']]
        tag = l['frame_id'] if l.get('frame_status', {}).get('status') == 'established' else None
        if _NATIVE_LOG is not None:
            _NATIVE_LOG.append(dict(key='types_frames_v1', pair=pair.pair_id, clause=clause.index, label=l['label_spelling'],
                                    python_type=v.resolved_type, native_type=type_name(l['resolved_type']),
                                    python_frame=v.frame, native_frame=tag,
                                    native_frame_status=l.get('frame_status', {}).get('status')))
        t = type_name(l['resolved_type'])
        v.resolved_type, v.types, v.clash = t, frozenset([t]) if t else frozenset(), False
        if tag is not None and v.frame is None:
            v.frame, v.frames = tag, v.frames | {tag}
    _settle(scope)


# ----------------------------------------------------------------------------------------- canonical form

def canonical(scope):
    """The canonical form of a scope, as (form, order): the form of `canonical_python`, in both views."""
    return canonical_python(scope)


def canonical_python(scope):
    """The canonical form of a scope, as (form, order): form is a nested tuple that is the same for two spellings
    of one body that differ in label names, atom order, OR branch order, site order, the operand order of a
    symmetric comparison or lib relation, or the direction of a converse operator; order is the scope's labels in
    canonical order. Relations read from a table are named by the table and their columns by field index, so a
    renamed relation or column gives the same form. Labels are told apart by the atoms they occur in (colour
    refinement), and the order among labels that nothing tells apart follows the text. featlib's own derivation;
    the engine's canonical_form will replace it."""
    labels = list(scope.variables)
    keys = {lab: i for i, lab in enumerate(scope.key_order())}
    heads = C.defaultdict(list)
    for a in scope.head:
        if a.label:
            heads[a.label].append(a.name)
    color = {lab: repr((keys.get(lab), sorted(heads[lab]))) for lab in labels}
    occ = C.defaultdict(list)
    for at in scope.atoms:
        for a in at.arguments:
            if a.label:
                occ[a.label].append(at)

    def ctx(at):
        return (at.negated, len(at.branch), at.quantifier, at.conditional)
    for _ in range(6):
        new = {}
        for lab in labels:
            sigs = sorted(repr((ctx(at), _atom_key(at, lambda a, lab=lab: 'SELF' if a.label == lab else
                                                    (color.get(a.label) if a.label is not None else '0'))))
                          for at in occ[lab])
            new[lab] = repr((color[lab], sigs))
        ranks = {c: i for i, c in enumerate(sorted(set(new.values())))}
        new = {lab: str(ranks[c]) for lab, c in new.items()}
        stable = len(set(new.values())) == len(set(color.values()))
        color = new
        if stable:
            break
    first = {lab: i for i, lab in enumerate(scope.creation_order())}
    order = sorted(labels, key=lambda lab: (int(color[lab]), first.get(lab, len(first))))
    rank = {lab: str(int(color[lab])) for lab in labels}

    def name(a):
        return rank.get(a.label) if a.label is not None else '0'

    head = tuple(sorted((a.name, name(a)) for a in scope.head))
    form = ('SCOPE', scope.name, head, _canon_body(scope, scope.body, (), name))
    scope._canonical = (form, order, rank)
    return form, order


def _canon_body(scope, items, base, name, start=0):
    out = []
    for i in range(start, len(items)):
        it, p = items[i], base + (i,)
        if not isinstance(it, list) or not it:
            continue
        h = it[0]
        if not isinstance(h, str):
            out.append(('AND', _canon_body(scope, it, p, name)))
        elif h == 'NOT':
            out.append(('NOT', _canon_body(scope, it, p, name, 1)))
        elif h == 'OR':
            out.append(('OR', tuple(sorted((_canon_body(scope, it[b], p + (b,), name) for b in range(1, len(it))
                                            if isinstance(it[b], list)), key=repr))))
        elif h in ('IF', 'ALL'):
            out.append((h,) + tuple(_canon_body(scope, it[b], p + (b,), name) for b in range(1, len(it))
                                    if isinstance(it[b], list)))
        elif h in MARKS:
            out.append(('MARK', h, tuple(sorted(name(_Named(x)) if not x[:1].isdigit() else x for x in it[1:] if isinstance(x, str)))))
        elif not h.startswith(':'):
            at = scope.atom_at(p)
            if at is not None:
                out.append(('ATOM',) + _atom_key(at, name)[1:])
    return tuple(sorted(out, key=repr))


class _Named:
    """A bare label (in a ONE mark) in the shape canonical()'s naming reads."""
    __slots__ = ('label',)

    def __init__(self, label):
        self.label = label


def signature(atom):
    """The atom's key with its labels named by their canonical class in the scope (labels that the atoms they occur
    in do not tell apart share a name), so that atoms of two scopes compare and the signature depends on no label name
    or atom order: two atoms with equal signatures read the same relation with labels in the same canonical places."""
    if getattr(atom.scope, '_canonical', None) is None:
        canonical(atom.scope)
    rank = atom.scope._canonical[2]
    return _atom_key(atom, lambda a: rank.get(a.label) if a.label is not None else '0')


# ------------------------------------------------------------------------------------------- Pair access

def _pair_schemas(self):
    """{table id: index entry (fields, source_name, callable_atom, roles)} for the available tables, and the
    candidate table under `X` in both views; read from the index files, without the rows."""
    if getattr(self, '_schemas_cache', None) is None:
        index = {}
        if self.layout in ('features', 'store'):
            try:
                for t in _shared(str(self.point_dir / 'point.json')).get('tables', []):
                    index.setdefault(t['id'], t)
            except Exception:
                pass
        for t in self._meta.get('tables', []):
            index[t['id']] = t
        out = {tid: index[tid] for tid in self._available if tid in index}
        x = index.get('X' if self._candidate == 'mutant' else 'G')
        if x is not None:
            out['X'] = dict(x, id='X', callable_atom=_x_atom(x.get('fields') or [], self.kind))
        self._schemas_cache = out
    return self._schemas_cache


def _pair_table(self, ref):
    """The Table with that id (`X` for the candidate) or source name, among X and the available tables; None if
    there is none. A table that is a target is never given."""
    if ref == 'X':
        return self.x
    if ref in self._available:
        for t in self.available():
            if t.id == ref:
                return t
    schemas = self._schemas()
    for tid, s in schemas.items():
        if tid != 'X' and s.get('source_name') == ref:
            return self.table(tid)
    if schemas.get('X', {}).get('source_name') == ref:
        return self.x
    return None


def _pair_typed(self):
    if getattr(self, '_typed_cache', None) is None:
        self._typed_cache = _typed_sites(self)
    return self._typed_cache


def _pair_clause(self):
    """The candidate's Clause, typed: `body` is the candidate's Scope; at an INIT point, `key`, `port` and
    `before` give the INIT's key clause, the port at the point and the scopes before it."""
    return self._typed()[1]


def _pair_clauses_before(self):
    """The Clauses before the point, typed, in program order; each has `table_ids` and `tables()`."""
    return self._typed()[0]


def _pair_examples(self):
    """The train examples as Example objects (input and output Grids), in train order."""
    if getattr(self, '_examples_cache', None) is None:
        tr = self.train
        tr = tr['train'] if isinstance(tr, dict) and 'train' in tr else tr
        self._examples_cache = [Example(i, item) for i, item in enumerate(tr)]
    return self._examples_cache


def read_test_grids(path):
    """The test input grids (lists of rows) of a test-inputs file (a list of grids, of {'input': grid}, or
    {'test': [...]}), in test order; [] where `path` is None or missing. Do not modify them."""
    if path is None or not Path(path).exists():
        return []
    data = _shared(str(path))
    if isinstance(data, dict):
        data = data.get('test', data.get('test_inputs', []))
    return [g['input'] if isinstance(g, dict) else g for g in data]


def read_test_inputs(path):
    """The test input Grids of a test-inputs file (see `read_test_grids`)."""
    return [Grid(g) for g in read_test_grids(path)]


def _pair_test_inputs(self):
    """The test input Grids (no outputs; a test input has no output here), by test index: [] where the point has none.
    The `test` key of a test entry indexes this list."""
    if getattr(self, '_test_inputs_cache', None) is None:
        self._test_inputs_cache = read_test_inputs(getattr(self, '_test_path', None))
    return self._test_inputs_cache


def _pair_lib(self):
    """The library interfaces (Lib) of the pair's libraries.json."""
    return _lib(str(self._libraries))


Pair._schemas = _pair_schemas
Pair.table = _pair_table
Pair._typed = _pair_typed
Pair.clause = property(_pair_clause)
Pair.clauses_before = _pair_clauses_before
Pair.examples = _pair_examples
Pair.test_inputs = property(_pair_test_inputs)
Pair.lib = property(_pair_lib)


def _pair_x_normal(self):
    """The normal form of X: None in both views. The exporter's `x_nf4f_v1` describes the mutant's X only and has no
    gold counterpart, so no feature reads it; a feature of X reads `Pair.x`."""
    return None


Pair.x_normal = _pair_x_normal
