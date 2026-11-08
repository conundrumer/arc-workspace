"""Dev labeling layer: the tables of each variant at its example, kept in ../cache/<task>.tables.jsonl, so that a change to the feature
library needs no engine run. run.py, search.py and refeature.py read and write it through Cache.

    python3 tablecache.py migrate TASK [TASK ...]     gives each record that lacks a variant digest the digest of the corpus variant of its id
    <runtime python> -I -B tablecache.py check TASK N  reruns the engine on N records of the task's cache, and compares the tables

A record holds the variant's id, a digest of what the engine reads of the variant (`variant`), a digest of the solver's text (`solver`), the
example, the variant's stored status, and the tables at that example. A record serves a variant with the same id, variant digest and solver
digest. A record that lacks a variant digest serves the variant of its id. Two processes never append to one task's cache at once. A record
that an earlier engine wrote can hold a relation's columns in another order; the cache serves every table with its columns in the order of
the current engine's run of the task, since a feature names a column by its place in that order.
"""
import base64
import copy
import hashlib
import json
import os
import random
import sys
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'features'))
import jsonl as J  # noqa: E402
import paths  # noqa: E402

CACHE = Path(os.environ.get('CONTRACTS_CACHE', paths.DATA / 'cache'))
CORPUS = HERE.parent / 'corpus'
STORED = ('stored', 'stored_changed', 'stored_invalid')


def digest(text, size=8):
    return hashlib.blake2b(text.encode(), digest_size=size).hexdigest()


def variant_key(rec):
    """A digest of what the engine reads of a variant: an input variant's grid, or an output variant's train example and its edits (its
    whole output, where it has one)."""
    what = ['in', rec['grid']] if 'grid' in rec else ['out', rec['source'], rec['target']] if 'target' in rec else ['out', rec['source'], rec['ops']]
    return digest(json.dumps(what))


def edited_output(output, rec):
    """The train output that the output variant rec gives: its whole output (`target`) where it has one, else output with the cells of its
    `ops` changed."""
    if 'target' in rec:
        return [list(r) for r in rec['target']]
    o = [list(r) for r in output]
    for row, col, c in rec['ops']:
        o[row][col] = c
    return o


def task_with(bj, rec):
    """(the task file with the variant rec in it, the example at which the variant's tables are read). An input variant is an extra test
    input, and an output variant edits a train output."""
    tj = copy.deepcopy(bj)
    if 'grid' in rec:
        tj['test'] = tj['test'] + [{'input': rec['grid'], 'output': [list(r) for r in rec['grid']]}]  # the file needs an output; ex_output holds train outputs only
        return tj, 'test/%d' % (len(tj['test']) - 1)
    i = int(rec['source'].split('/')[1])
    tj['train'][i]['output'] = edited_output(tj['train'][i]['output'], rec)
    return tj, rec['source']


def at(T, ex):
    """The tables at example ex: what all_features and the row digests read at ex."""
    here = lambda held: {k: v for k, v in held.items() if k in (ex, 'task')}
    return {n: {'columns': [list(c) for c in t['columns']], 'rows': here(t['rows']),
                **({'counts': here(t['counts']), 'views': here(t['views'])} if 'counts' in t else {}),
                **({'ident_values': t['ident_values']} if 'ident_values' in t else {})}
            for n, t in T.items() if n not in ('ex_input', 'ex_output')}


def unpack(z):
    """The tables of a record written as zlib, then base64."""
    return json.loads(zlib.decompress(base64.b64decode(z)))


class Engine:
    """The task's solver, with the stored values that solve the task's own train pairs. Needs the engine runtime's python. others: whether to hold the
    tables at the task's other retained assignments, in `others`, for the features across assignments."""

    def __init__(self, task, others=False):
        import engine as E
        import observations
        import proposers as P
        import query as Q
        self.E, self.P = E, P
        self.s = observations.Solver(task)
        self.bj = json.load(open(E.ROOT / 'data/tasks' / (task + '.json')))
        self.T0 = self.s.tables(self.bj, keep_run=others)
        self.base_stored, self.base_types = self.s.stored, self.s.stored_types
        small = sum(len(r) for t in self.T0.values() for r in t['rows'].values()) <= 300000
        self.others = self.s.other_assignments(16) if others and small else []  # the tables at the task's other assignments
        self.s.last_run = None
        qf = Q.query_features(self.s.text)
        self.pins = {rel: rows for rel, rows in self.base_stored.items() if rel in E.proposer_relations(qf)}
        self.proposer_of = {n: q.get('proposer') for n, q in qf.items()}
        self.n_base = len(self.bj['train']) + len(self.bj['test'])

    def run(self, tj):
        """The tables of the task file tj, at the task's own proposer values, with their stored status."""
        T = self.s.tables(tj, pin=self.pins, no_assignment=lambda p: self.P.missing(p, self.proposer_of, tj))
        return T, self.E.settle_stored(self.s, T, self.T0, self.base_stored, self.base_types, self.n_base)


class Cache:
    """A task's cache under the engine's solver, as a context manager. ids, where given, are the variants it may serve; with hold False it
    holds no tables in memory, and serves them through hits. read_only serves hits without opening a cache writer."""

    def __init__(self, task, engine, ids=None, hold=True, read_only=False):
        self.path = CACHE / (task + '.tables.jsonl')
        self.engine = engine
        self.solver = digest(engine.s.text)
        self.ids = ids
        self.hold = hold
        self.read_only = read_only

    def __enter__(self):
        if not self.read_only:
            CACHE.mkdir(exist_ok=True)
            self.out = J.Appender(self.path).__enter__()
        self.held = {(c['id'], c.get('variant')): c for c in J.records(self.path)
                     if self.hold and c.get('solver') == self.solver and (self.ids is None or c['id'] in self.ids)} if self.hold else {}
        return self

    def __exit__(self, *exc):
        return False if self.read_only else self.out.__exit__(*exc)

    def hits(self, want):
        """(variant, tables, task file, example) for each variant of want ({id: variant record}) that the cache holds, in the cache's order,
        one record in memory at a time. Sets each one's stored status, and removes it from want."""
        for c in J.records(self.path):
            rec = want.get(c['id'])
            if rec is None or c.get('solver') != self.solver or c.get('variant', variant_key(rec)) != variant_key(rec):
                continue
            del want[c['id']]
            rec.update({k: c[k] for k in STORED})
            tj, ex = task_with(self.engine.bj, rec)
            yield rec, aligned(c['tables'] if 'tables' in c else unpack(c['z']), self.engine.T0), tj, ex

    def tables(self, rec):
        """(tables, task file, example) of the variant rec, its tables from the cache, or from the engine and then into the cache. Sets rec's
        stored status."""
        if self.read_only:
            raise ValueError('read-only caches serve hits only')
        tj, ex = task_with(self.engine.bj, rec)
        key = variant_key(rec)
        c = self.held.get((rec['id'], key)) or self.held.get((rec['id'], None))
        if c is not None:
            rec.update({k: c[k] for k in STORED})
            return aligned(c['tables'] if 'tables' in c else unpack(c['z']), self.engine.T0), tj, ex
        T, status = self.engine.run(tj)
        rec.update(zip(STORED, status))
        self.out.write(dict(id=rec['id'], variant=key, solver=self.solver, ex=ex, **{k: rec[k] for k in STORED}, tables=at(T, ex)))
        return T, tj, ex


def aligned(T, T0):
    """T with each table's columns in the order of T0, the current engine's run, where the two hold the same columns in another order."""
    out = {}
    for n, tab in T.items():
        ref = T0.get(n)
        names = [c[0] for c in tab['columns']]
        want = [c[0] for c in ref['columns']] if ref is not None else names
        if names == want or sorted(names) != sorted(want) or len(set(names)) != len(names):
            out[n] = tab
            continue
        perm = [names.index(c) for c in want]
        out[n] = dict(tab, columns=[list(c) for c in ref['columns']], rows={k: [[r[i] for i in perm] for r in rows] for k, rows in tab['rows'].items()})
        if 'views' in tab:
            out[n]['views'] = {k: [[[perm.index(c) for c in columns], rows] for columns, rows in views] for k, views in tab['views'].items()}
    return out


def migrate(task):
    """Gives each record of the task's cache that lacks a variant digest the digest of the corpus variant of its id. A record whose id the
    corpus lacks is dropped."""
    keys = {r['id']: variant_key(r) for r in J.records(CORPUS / (task + '.jsonl')) if 'grid' in r or 'ops' in r or 'target' in r}
    n = Counter()

    def recs():
        for c in J.records(CACHE / (task + '.tables.jsonl')):
            if 'z' in c and 'tables' not in c:
                c = dict(c)
                c['tables'] = unpack(c.pop('z'))
            if 'variant' in c:
                n['kept'] += 1
            elif c['id'] in keys:
                n['given a digest'] += 1
                c = dict(id=c['id'], variant=keys[c['id']], **{k: v for k, v in c.items() if k != 'id'})
            else:
                n['dropped'] += 1
                continue
            yield c
    J.write_all(CACHE / (task + '.tables.jsonl'), recs())
    print('%s: %s' % (task, ', '.join('%d %s' % (v, k) for k, v in n.items())), flush=True)


def check(task, n):
    """Reruns the engine on n records of the task's cache, chosen at random among those of its solver and in the corpus, and prints whether
    each one's tables have the same rows, up to the order of rows and the names of Idents."""
    import refeature as RF
    eng = Engine(task)
    corpus = {r['id']: {k: r[k] for k in ('id', 'grid', 'source', 'ops', 'target') if k in r} for r in J.records(CORPUS / (task + '.jsonl'))
              if 'grid' in r or 'ops' in r or 'target' in r}
    solver = digest(eng.s.text)
    want = set(random.Random(task).sample(sorted(corpus), min(3 * n, len(corpus))))
    held = [c for c in J.records(CACHE / (task + '.tables.jsonl')) if c['id'] in want and c.get('solver') == solver][:n]
    same = 0
    for c in held:
        r = corpus[c['id']]
        tj, ex = task_with(eng.bj, r)
        T, _ = eng.run(tj)
        T1 = c['tables'] if 'tables' in c else unpack(c['z'])
        a, b = RF.digests(T, ex), RF.digests(T1, ex)
        if a == b and ('variant' not in c or c['variant'] == variant_key(r)):
            same += 1
        else:
            print('%s %s: the tables differ at %s' % (task, c['id'], sorted(t for t in set(a) | set(b) if a.get(t) != b.get(t))), flush=True)
    print('%s: %d of %d records have the same rows' % (task, same, len(held)), flush=True)


if __name__ == '__main__':
    if sys.argv[1:2] == ['migrate']:
        for t in sys.argv[2:]:
            migrate(t)
    elif sys.argv[1:2] == ['check']:
        check(sys.argv[2], int(sys.argv[3]))
