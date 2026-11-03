"""The graph tables of one task's union, each a parameterized table, from the row store of the engine's export (work/lm/data-study/samples/SET/rows/<task>.jsonl.gz, model/study/samples/row_store.py).

- A parameterized table is (QueryHash, Name). It maps each Assignment over the DETs it depends on to a table, the TableRows at that assignment. Its map is {Assignment → TableHash}, an Assignment being the sorted (DET QueryHash, value hash) pairs.
- Two parameterized tables are one graph table when their maps are equal with each DET value written as the TableHash of the DET's table at that value, and each DET as the set of those TableHashes, so that DETs of different QueryHash pair by equal sets of value TableHashes (a value hash keeps the DET's column order, so it can differ where the table is equal), and with each DET of one value left out of the Assignments, since it gives every table that depends on it one choice. A graph table is named "t" and 16 hex digits of a hash of that map. This is a measurement, not an identity.
- A parameterized table whose output stopped at the cap of the engine's walk is `capped`; its map holds the assignments the walk reached.
- A union query is matched to its row store query by (union key, text), from the query's own line or one of its `alias` lines (a later union query of the same QueryHash). A union query with no match keeps its Python identity, and its parameterized tables are named "u<identity>.<Name>", each its own graph table.

  tables_of(s, u) -> Tables, or None where the task has no row store file of a version in VERSIONS
"""
import gzip, hashlib, json, os
from dataclasses import dataclass, field

ROWS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/%s/rows/%s.jsonl.gz'
VERSIONS = os.environ.get('ROWS_VERSION', 'engine@site-exp30').split(',')  # the row store hash_versions accepted, separated by commas


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class Tables:
    query: dict = field(default_factory=dict)  # Python identity -> QueryHash
    names: dict = field(default_factory=dict)  # QueryHash -> its Names, in the export's order
    graph: dict = field(default_factory=dict)  # (QueryHash, Name) -> graph table
    maps: dict = field(default_factory=dict)  # graph table -> [[Assignment as [[DET value set, value TableHash]], TableHash]], sorted
    capped: dict = field(default_factory=dict)  # graph table -> whether a table of it stopped at the cap
    shared_value_sets: int = 0  # assignments in which two DETs have one set of value hashes, so the map can't tell them apart
    unmatched: list = field(default_factory=list)  # Python identities of union queries with no row store query

    def table(self, ident, name):
        """The graph table of the union query `ident` at output `name`."""
        q = self.query.get(ident)
        if q is None:
            return 'u%s.%s' % (ident, name) if name else 'u' + ident
        if (q, name) in self.graph:
            return self.graph[q, name]
        if len(self.names.get(q, ())) == 1:  # a read the engine makes no table of, as a BoundingBox's `.cell`: its query's one table
            return self.graph[q, self.names[q][0]]
        return 'u%s.%s' % (q, name)

    def heads(self, ident):
        """The graph tables of every output of the union query `ident`, or None where it has no row store query."""
        q = self.query.get(ident)
        return [self.graph[q, n] for n in self.names[q]] if q in self.names else None


def tables_of(s, u):
    p = ROWS % (s, u['task'])
    if not os.path.exists(p):
        return None
    recs = [json.loads(x) for x in gzip.open(p, 'rt')]
    if not recs or recs[0].get('hash_version') not in VERSIONS:
        return None
    queries = [r for r in recs if r['t'] == 'function' and r.get('union_key') is not None]
    entries = [r for r in recs if r['t'] == 'entry']
    by_text = {(r['union_key'], r['text']): r['id'] for r in queries + [a for a in recs if a['t'] == 'alias' and a.get('union_key') is not None]}
    T = Tables()
    for t in u['tables']:
        for f in t['forms']:
            q = by_text.get((t['key'], f['text']))
            if q is None:
                T.unmatched.append(f['ident'])
            else:
                T.query[f['ident']] = q
    tables_at = {}  # (DET, value hash) -> the TableHashes of the DET's own entries at that value
    for e in entries:
        for d, v in e['assignment']:
            if d == e['function']:
                tables_at.setdefault((d, v), set()).add(e.get('hash') or 'none')
    table_of = {k: min(v) if len(v) == 1 else digest(sorted(v)) for k, v in tables_at.items()}  # (DET, value hash) -> the TableHash of the DET's table at that value
    values = {}
    for e in entries:
        for d, v in e['assignment']:
            values.setdefault(d, set()).add(table_of.get((d, v), v))
    value_set = {d: digest(sorted(v)) for d, v in values.items()}
    one_value = {d for d, v in values.items() if len(v) == 1}
    stopped = {(r['id'], o['name']) for r in queries for o in r['outputs'] if o.get('stopped')}
    raw = {}
    for e in entries:
        a = sorted([value_set[d], table_of.get((d, v), v)] for d, v in e['assignment'] if d not in one_value)
        T.shared_value_sets += len({x for x, _ in a}) < len(a)
        raw.setdefault((e['function'], e['name']), []).append([a, e.get('hash') or 'none'])
    for r in queries:
        T.names.setdefault(r['id'], [o['name'] for o in r['outputs']])
        for n in T.names[r['id']]:
            m = sorted(raw.get((r['id'], n), []))
            g = 't' + digest(m)
            T.graph[r['id'], n] = g
            T.maps[g] = m
            T.capped[g] = T.capped.get(g, False) or (r['id'], n) in stopped
    return T
