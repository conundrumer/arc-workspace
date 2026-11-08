"""Model input layer: the identity of each table and each column of a program, free of the names and the order that the program's author chose.

A table's identity is the engine's `ident`: the hash of its query's resolved content, for a port of an instance a hash of its `INIT` form's
ident and the port's lib name, and for a fact relation a hash of its name. A key holds its first DIGITS hex digits. A column's identity,
within its table, is the engine's `column_idents` entry: the lib's name for a column that the lib declares, `<lib column>.#<n>` for a record
field below a lib column, with n the canonical position of the field's label, and `#<n>`, the canonical position of its label, for any other
column. Only with `ARCLOG_DEMONSTRATED=1`, a demonstrated table hashes its resolved catalog, with inputs in the fixed
value-then-demonstration order, rule names and texts omitted, and rules sorted by content. Its columns use the fixed value roles `o`, `i`,
`v` and its `key`, with record fields identified by canonical outer labels. The flag defaults off and is read once per process; off,
demonstrated tables have no exported identity. A rigid part column that repeats a key label uses `part.#<n>` to distinguish that
occurrence from the key's `#<n>`; the other columns keep their identities, including the synthetic pose column's engine schema name.
A field's token keeps the lib column's name before it, as
`key.⟨c:#<n>⟩`. A feature key
names a table and a column by these identities (features.py), so a rename or a reorder of the program's text changes no key. Two tables of
equal query content have one identity, and give one key one value, since equal content gives equal rows; a task parameter is the exception,
since two parameters of equal content can take different values. So where tables of one identity include a task parameter, color refinement
over the program's reads, in both directions, splits them by how the program uses them, and a table that shares an identity only through
such parameters is split with them. Parameters that the same forms read start the refinement apart where their reads stand at different
places in those forms: color refinement within a form, over its lists and its labels, gives each read a color from what surrounds it. A
split table's identity is a hash of its refined color. Every other table keeps the engine's ident.

`CONTRACTS_PLACEHOLDER_IDS=1` stands in placeholders where the engine gives no identities: a hash of the table's name, and the column's
place in the table. They are unique in a program and serve a test of the code alone, since a rename or a reorder changes them.
"""
import hashlib
import os
import re
from collections import defaultdict

TABLE = '⟨t:%s⟩'
COLUMN = '⟨c:%s⟩'
DIGITS = 12  # hex digits of a table's identity in a key


class Identities:
    """table(name) and column(name, i) of the engine's Tables tb; `placeholder` where they are CONTRACTS_PLACEHOLDER_IDS's."""

    def __init__(self, tb, reads=None, params=(), text=None):
        """reads: {table: the tables its form reads} (form_reads); params: the tables that are task parameters; text: the program."""
        T = tb.T
        self.placeholder = False
        self.tables, self.columns = {}, {}
        given = engine_identities(tb)
        if given is None:
            if os.environ.get('CONTRACTS_PLACEHOLDER_IDS') != '1':
                raise RuntimeError('the engine gives no identities of tables and columns; set CONTRACTS_PLACEHOLDER_IDS=1 to test with placeholders')
            self.placeholder = True
            given = placeholder_identities(tb)
        table_ids, column_ids = given
        if reads is not None and not self.placeholder:
            named = {name: table_ids[t] for t, name in enumerate(tb.names) if name and table_ids[t]}
            split = refined(named, reads, set(params))
            left = unsplit(named, split, set(params))
            if left and text is not None:
                by_name = {name: dict(zip(T['column_names'][t], column_ids[t])) for t, name in enumerate(tb.names) if name}
                split = refined(named, reads, set(params), read_sites(text, left, named, by_name))
            table_ids = [split.get(name, i) for name, i in zip(tb.names, table_ids)]
        full = {}
        for t, name in enumerate(tb.names):
            if not name:
                continue
            if not table_ids[t]:
                raise ValueError('the engine gives table %s no identity' % name)
            short = table_ids[t][:DIGITS]
            if full.setdefault(short, table_ids[t]) != table_ids[t]:
                raise ValueError('two table identities share their first %d digits: %s' % (DIGITS, short))
            self.tables[name] = short
            self.columns[name] = list(column_ids[t])
            if any('~' in c for c in column_ids[t]):
                raise ValueError('a column identity of %s holds a name from the program text: %s' % (name, column_ids[t]))
            if len(set(column_ids[t])) != len(column_ids[t]):
                raise ValueError('two columns of %s share an identity: %s' % (name, column_ids[t]))

    def table(self, name):
        return self.tables[name]

    def column(self, name, i):
        return self.columns[name][i]

    def table_token(self, name):
        return TABLE % self.tables[name]

    def column_token(self, name, i):
        """The column's token; a field below a lib column keeps that column's name before the token, as `key.<token>`."""
        head, dot, field = self.columns[name][i].partition('.')
        return '%s.%s' % (head, COLUMN % field) if dot else COLUMN % head


def engine_identities(tb):
    """([table identity], [[column identity]]) by table number, from the fields of the engine's export, or None where it gives none."""
    T = tb.T
    if 'ident' not in T or 'column_idents' not in T:
        return None
    return list(T['ident']), [list(cs) for cs in T['column_idents']]


def placeholder_identities(tb):
    T = tb.T
    tables, columns = [], []
    for t, name in enumerate(tb.names):
        tables.append(hashlib.blake2b((name or '').encode(), digest_size=8).hexdigest()[:DIGITS])
        columns.append(['%s.#%d' % (col.partition('.')[0], i) if '.' in col else col if not lab else '#%d' % i
                        for i, (col, lab) in enumerate(zip(T['column_names'][t], T['column_labels'][t]))])
    return tables, columns


def form_reads(text, names):
    """{table: the tables of names that its form reads}: a port of an instance reads what its INIT form reads."""
    by_form = {}
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                m = re.match(r'\((RULE|DET|DET_OR_RULE|RULE_OR_DET|INIT|RIGID_DET|CHOOSE) (&[\w]+)', text[start:i + 1])
                if m:
                    by_form.setdefault(m[2], set()).update(re.findall(r'&[\w]+(?:\.[\w]+)?', text[start + m.end():i + 1]))
    out = {}
    for n in names:
        used = by_form.get(n.split('.')[0], set())
        out[n] = {u for u in names if u != n and (u in used or u.split('.')[0] in used and '.' not in u)}
    return out


def _h(*parts):
    return hashlib.blake2b(repr(parts).encode(), digest_size=16).hexdigest()


def unsplit(ids, split, params):
    """The parameters that split leaves sharing an identity with another table."""
    groups = defaultdict(list)
    for n, i in ids.items():
        groups[split.get(n, i)].append(n)
    return {n for ms in groups.values() if len(ms) > 1 for n in ms if n in params}


TOKEN = re.compile(r'"[^"]*"|;[^\n]*|[()]|[^\s()]+')
ROLES = {'IF', 'ALL'}
KEYWORDS = {'RULE', 'DET', 'INIT', 'DET_OR_RULE', 'RULE_OR_DET', 'RIGID_DET', 'CHOOSE', 'DEMO_RULE', 'DEMONSTRATED', 'NOT', 'OR', 'IF', 'ALL', 'ONE', 'SET', 'OUT'}


def forms_of(text):
    """The program's top-level forms as nested lists of tokens; comments and quoted text are left out."""
    stack = [[]]
    for token in TOKEN.findall(text):
        if token == '(':
            stack.append([])
        elif token == ')':
            done = stack.pop()
            stack[-1].append(done)
        elif token[0] not in ';"':
            stack[-1].append(token)
    return stack[0]


def read_sites(text, tables, ids, columns, rounds=12):
    """{table of tables: the sorted colors of its reads}; ids: {table: identity}; columns: {table: {column name: column identity}}. A read is
    a list that starts with the table's name. Color refinement runs within each form over its lists and its labels. A table's name counts as
    its identity, a site's head on a table as its column's identity, a label only by the places it stands in, and a list by its place only
    under IF and ALL, whose lists have fixed roles, so no name or order that the program's author chose enters a color."""
    sites = defaultdict(list)

    def is_label(token, at):
        if token[0] in '*^':
            return True
        if token[0] in '&:' or token == '0':
            return False
        return at > 0 or (token[0].isupper() and token not in KEYWORDS)

    for form in forms_of(text):
        lists = []

        def gather(x, up, role, on):
            on = x[0] if x and isinstance(x[0], str) and x[0][0] == '&' else on
            lists.append((x, up, role, on))
            roles = bool(x) and isinstance(x[0], str) and x[0] in ROLES
            for at, child in enumerate(c for c in x if isinstance(c, list)):
                gather(child, x, at if roles else None, on)
        gather(form, None, None, None)

        def given(token, on):
            if token[0] == '&':
                return ids.get(token, ids.get(token.split('.')[0], '&') + token.partition('.')[2])
            if token[0] == ':' and on is not None:
                return ':' + columns.get(on, {}).get(token[1:], '')
            return token
        constants = lambda x, on: sorted(given(c, on) for at, c in enumerate(x) if isinstance(c, str) and not is_label(c, at))
        names = lambda x: [c.lstrip('*^') for at, c in enumerate(x) if isinstance(c, str) and is_label(c, at)]
        color = {id(x): _h(role, constants(x, on)) for x, _, role, on in lists}
        labels = {name: '' for x, _, _, _ in lists for name in names(x)}
        for _ in range(rounds):
            new = {id(x): _h(color[id(x)], color[id(up)] if up is not None else '', sorted(color[id(c)] for c in x if isinstance(c, list)),
                             sorted(labels[name] for name in names(x))) for x, up, _, _ in lists}
            labels = {label: _h(c, sorted(new[id(x)] for x, _, _, _ in lists for name in names(x) if name == label)) for label, c in labels.items()}
            color = new
        for x, up, _, _ in lists:
            if up is not None and x and isinstance(x[0], str) and x[0] in tables:
                sites[x[0]].append(color[id(x)])
    return {table: sorted(sites[table]) for table in tables}


def refined(ids, reads, params, sites=None, rounds=12):
    """{table: split identity} of the tables that share an engine identity with another table and are split, as the module's docstring gives.
    sites: the colors of the reads of the tables that read_sites gives, which start those tables apart."""
    groups = defaultdict(list)
    for n, i in ids.items():
        groups[i].append(n)
    colliding = [g for g, ms in groups.items() if len(ms) > 1]
    if not colliding:
        return {}
    readers = defaultdict(set)
    for n in ids:
        for u in reads.get(n, ()):
            if u in ids:
                readers[u].add(n)
    color = {n: _h(i, sites[n]) if sites and n in sites else i for n, i in ids.items()}
    for _ in range(rounds):
        new = {n: _h(color[n], sorted(color[u] for u in reads.get(n, ()) if u in color), sorted(color[r] for r in readers[n])) for n in ids}
        stable = len(set(new.values())) == len(set(color.values()))
        color = new
        if stable:
            break
    split = {g for g in colliding if len({color[n] for n in groups[g]}) > 1}
    accepted = {g for g in split if any(n in params for n in groups[g])}
    while True:
        moved = {n for g in accepted for n in groups[g]}
        seen, todo = set(moved), list(moved)
        while todo:
            for r in readers[todo.pop()]:
                if r not in seen:
                    seen.add(r)
                    todo.append(r)
        more = {g for g in split - accepted if any(n in seen for n in groups[g])}
        if not more:
            break
        accepted |= more
    return {n: _h('split', color[n]) for g in accepted for n in groups[g]}
