#!/usr/bin/env python
"""A task's super DAG: a pool of queries, grown by writing each query over a scope that a policy picks.

A table at an assignment (TableAt) is one table of a query at one assignment, with its TableHash, its example keys and its TableVector from the engine. A
query whose QueryHash the pool has is a known state, not a new one. A query with a new QueryHash is kept, with one TableAt for each table of it at
each assignment. Each TableAt has two measurement flags: its TableHash equals that of a TableAt of another query in the scope (same_in_state), and its TableHash
was seen before in the pool (seen_before). A query with no table, or with a table that has no TableHash, is not kept.

A scope is the forms of the nodes that the policy picks, with their ancestors by reads, in depth order. draws_per_scope draws share
one scope, which is replayed once.

A policy has add(node), called once per new TableAt and again where its readers change, and scope(k, rng), which
gives at most k TableAt ids. It reads TableAt's fields, and no gold reaches it.

After each kept clause, Run.search tests the OUT candidates over its new relations. Each distinct attempt set that passes the filter is a
candidate program.

With a gold program, the cover check reads gold's tables in the same session, so that TableHashes compare, and records when a TableAt
has the TableHash of a gold table. This reads the task's solution, so it runs on dev tasks only, and its only effect is on the output's tags
and the cover events.

Output, under --out, per task:
- <task>.nodes.jsonl.zst: a record per new TableAt, in the form of pool_rows.py's nodes files, with clause and n_clauses, and its QueryHash, Name, assignment, TableHash, example keys and TableVector.
- <task>.events.jsonl: a line per candidate program, per gold relation covered, and a last line with the counts.
- With --seed-level, gold's shallow queries start the bank, and their TableAts have tags.seeded true.
- <task>.done.json: the counts, once the task's budget ends. A task with this file is skipped on a restart.

  RAYON_NUM_THREADS=1 <runtime python> -u superdag.py TASK ... [--seconds 300] [--k 6] [--draws-per-scope 4] [--out DIR]
"""
import argparse
import collections
import dataclasses
import hashlib
import itertools
import json
import math
import os
import random
import re
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import table_adapter as TA  # noqa: E402
import sampler_paths as P  # noqa: E402
from live import M, S, arclog  # noqa: E402
from live_try import SETTINGS  # noqa: E402

SESSION_BYTES = 2 << 30
RELATIONS = 4096  # relation slots of a decode, and so the most that a scope declares
MAX_SCOPE_FORMS = 96
CLAUSE_SECONDS = 20.0
SPLIT_FORM = re.compile(r'&f(\d+)')
NAME = re.compile(r'&[A-Za-z_]\w*')
ENTRY_STOP = re.compile(r'\bstop (.*?)(?:, fault | at )')  # the bounds in the text of an entry that a stop left incomplete; ` at ` ends a Count entry's projection stop
STOP_DETAIL = re.compile(r'\s*(?:\{[^{}]*\}|\([^()]*\))')  # what the engine's text of a bound adds to its name


def count_drop(c, e):
    """Adds to counter c the clause that M.Fail e dropped at its table: `drop:table: ` with the reason's first 40 characters and digits as N, and `drop:stop:<bound>` for each bound
    that stopped an entry, with the bound's whole name. The engine's bounds are a fixed list, so these keys are bounded."""
    text = str(e)
    c['drop:table: ' + re.sub(r'\d+', 'N', text)[:40]] += 1
    if text.startswith('entry '):
        for stops in ENTRY_STOP.findall(text):
            while STOP_DETAIL.search(stops):
                stops = STOP_DETAIL.sub('', stops)
            for bound in stops.split():
                if bound != 'None' and bound.isalpha():
                    c['drop:stop:' + bound] += 1


def written_names(line, names):
    """line with each engine name written as its stored name. A RIGID_DET's part is named by the table that the part reads, without its
    '&', step by step: the engine writes `&r4.r1` for the part that reads `&r1`, and `&r77.r4.r1` for a part of &r77 that reads the part
    `&r4.r1` of another RIGID_DET; this writes `&f4.f1` and `&f77.f4.f1`. A step that isn't an engine slot, such as an INIT output's name or
    `pose`, stays as it is."""
    def one(m):
        steps = [names.get(m[1], m[1])]
        for st in m[2].split('.')[1:] if m[2] else []:
            q = names.get('&' + st) if re.fullmatch(r'r\d+', st) else None
            steps.append(q[1:] if q else st)
        return '.'.join(steps)
    return re.sub(r'(&r\d+)((?:\.\w+)*)', one, line)


def rss_mib():
    """Peak RSS: ru_maxrss is in bytes on macOS and in KiB on Linux."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2 ** 20 if sys.platform == 'darwin' else 2 ** 10)


@dataclasses.dataclass
class Query:
    id: int
    text: str
    kind: str
    depth: int
    parents: list  # query ids
    reads: int  # tables the query reads, atoms of a kind
    nodes: list = dataclasses.field(default_factory=list)  # ids of its TableAts


@dataclasses.dataclass
class TableAt:
    """A table of a query at one assignment."""
    id: int
    form: int  # the id of its Query
    table: object  # (QueryHash, Name)
    at: tuple  # the assignment: ((DET QueryHash, value hash), ...)
    hash: int  # the TableHash
    types: list
    arity: int
    depth: int
    parents: list  # ids of the TableAts of the queries that the query reads
    examples: tuple  # (kind, index, distinct, rows, hash) per example
    features: object  # the TableVector
    rows: list | None  # TA.rows_of at X_ROWS_CAP, where the Run exports rows (Run.rows); else None
    table_types: list
    clause: str
    age: int  # the draw that made it; for an oldest-first share of picks, and for nothing else
    same_in_state: bool = False
    seen_before: bool = False
    n_clauses: int = 1
    n_readers: int = 0
    frames: object = None


class UniformPolicy:
    """Picks nodes at random: the stand-in until the scored policy exists."""
    needs_rows = False

    def __init__(self, task):
        self.ids = []

    def add(self, node):
        if node.n_clauses == 1 and node.n_readers == 0:
            self.ids.append(node.id)

    def scope(self, k, rng):
        return rng.sample(self.ids, min(k, len(self.ids)))


class Run(live.Run):
    """live.Run that keeps what each written query reads, and can hold the tables of each query it replays: (step_tables result, AssignmentSummaries by slot, their places).
    It exports no rows unless its Pool's policy reads them (Pool sets want_rows)."""
    want_rows = False

    def __init__(self, *args):
        super().__init__(*args)
        self.reads, self.collect, self.last_loo = [], None, []
        fit = self.gate.leave_one_out

        def leave_one_out(text):
            self.last_loo = fit(text)
            return self.last_loo
        self.gate.leave_one_out = leave_one_out

    def open_form(self, pg, dec, kind):
        self.reads = []
        return super().open_form(pg, dec, kind)

    def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        got = super().body(pg, dr, dec, kind, nlab, need, keys)
        self.reads += [t for t, _ in S.atom_uses(self.V, got[1])]
        return got

    def close(self, pg, f):
        super().close(pg, f)
        if self.collect is not None:
            self.collect.append((pg.before, pg.tables, pg.indexes))


class Pool:
    def __init__(self, task_id, task, run, policy, gold, write, event, a):
        self.id, self.task, self.run, self.policy, self.gold, self.write, self.event, self.a = task_id, task, run, policy, gold, write, event, a
        run.want_rows = bool(getattr(policy, 'needs_rows', True))  # the run exports rows only for a policy that reads them
        self.forms, self.nodes = {}, {}  # Query id -> Query; TableAt id -> TableAt
        self.defs, self.keys, self.table_sets, self.hash_count = {}, {}, {}, collections.Counter()  # QueryHash -> Query id; (QueryHash, Name, assignment) -> TableAt id; the TableHashes of a table's assignments -> TableAt id; TableHash -> TableAts that have it
        self.candidates, self.covered, self.draws, self.rng = {}, {}, 0, random.Random('%s %d' % (task_id, a.seed))
        self.keep_rows, self.tick, self.stop = True, lambda: None, None  # stop gives a reason to end growth, or None
        self.save, self.saved_before_end = None, False  # save writes the worker's bank; save_before_end calls it once
        self.mark = lambda phase: None  # kaggle_worker.Meter.mark: called at the end of each phase of a visit
        self.scoped = ()  # the forms of the scope of the current draw
        self.kinds = {k: sum(c.get(k, 0) for c in run.pri['kinds1'].values()) for k in live.KIND_TOK}
        self.c = run.c

    def scope(self):
        """The forms of a scope, in depth order: a policy's picks with their ancestors, up to MAX_SCOPE_FORMS."""
        seen = set()
        for n in self.policy.scope(self.a.k, self.rng):
            got, todo = set(), [self.nodes[n].form]
            while todo:
                f = todo.pop()
                if f not in got and f not in seen:
                    got.add(f)
                    todo += self.forms[f].parents
            if len(seen) + len(got) <= MAX_SCOPE_FORMS:
                seen |= got
            else:
                self.c['scope:pick past the form cap'] += 1
        return sorted(seen, key=lambda f: (self.forms[f].depth, f))

    def kind(self, dec):
        names = [k for k in live.KIND_TOK if self.run.makes(k) and dec.admits([live.KIND_TOK[k]])[0]]
        return self.rng.choices(names, weights=[self.kinds[k] + 1 for k in names])[0]

    def draw(self, fids, deadline):
        """One query written over the scope fids. Keeps it where its QueryHash is new, and tests its OUT candidates."""
        run, forms = self.run, [self.forms[f].text for f in fids]
        self.scoped = fids
        self.draws += 1
        run.rng.seed(int(hashlib.sha1(('%s %d %d' % (self.id, self.a.seed, self.draws)).encode()).hexdigest()[:12], 16))
        run.deadline = min(deadline, time.monotonic() + CLAUSE_SECONDS)
        run.c['draws'] += 1
        try:
            dec, pg = run.scope(forms)
            kind = self.kind(dec)
            f = run.form(pg, dec, kind)
            kept = self.take(f, pg, kind, len(forms))
            if kept:
                self.test(f, pg, kept)
        except M.Fail as e:
            count_drop(run.c, e)
        except Exception as e:  # noqa: BLE001
            run.failed(e)

    def take(self, f, pg, kind, nscope):
        """The new Query of the clause at decoder f, or None where its QueryHash is a known state's, it has no table, or a table at an assignment has no TableRows on any example. Raises M.Fail where a table at
        an assignment has no TableHash."""
        run = self.run
        line = f.program_form().split('\n')[nscope]
        fid = len(self.forms)
        names = pg.written | {live.head_of(line): '&f%d' % fid}
        text = written_names(line, names)
        parents = sorted({int(x) for x in SPLIT_FORM.findall(text)} - {fid})
        depth = 1 + max((self.forms[p].depth for p in parents), default=0)
        made = [(s, r, j) for s in pg.new for r, j in zip(pg.tables.get(s, ()), pg.indexes.get(s, ()))]
        self.mark('key')
        if not made:
            run.c['state:no table'] += 1
            return None
        for _, r, _ in made:
            if r.hash is None:
                raise M.Fail('table with no TableHash: %s' % (r.unhashed or 'no reason'))
            if not isinstance(r.table, tuple):
                raise M.Fail('table with no QueryHash')
        if any(r.examples and all(k[2] == 0 for k in r.examples) for _, r, _ in made):  # no TableRows on any example (distinct 0): the engine hashes an all-Undefined table as an empty Set
            run.c['state:no TableRows'] += 1
            return None
        if made[0][1].table[0] in self.defs:
            run.c['state:known'] += 1
            return None
        query = self.add_query(fid, text, kind, depth, parents, len(run.reads), made, pg.before, pg)
        run.c['kept:' + kind] += 1
        return query

    def add_query(self, fid, text, kind, depth, parents, reads, made, ct, pg, seeded=False):
        """The Query with a TableAt for each (slot, AssignmentSummary, place in ct) of made, written and given to the policy. A query with no TableAt
        stays in the bank where seeded. Where it raises, it has stored nothing: the TableAts are made before anything is stored."""
        run = self.run
        pids = [n for p in parents for n in self.forms[p].nodes]
        in_state = {self.nodes[n].hash for f in self.scoped for n in self.forms[f].nodes}
        made_hashes, tables = set(), []  # made_hashes: the TableHashes of the TableAts made so far in this call, which count as seen before
        for s, r, j in made:
            tables.append(TableAt(len(self.nodes) + len(tables), fid, r.table, r.at, r.hash, sorted(pg.decl_types.get(s, ())), len(set(pg.decl_slots.get(s, ()))), depth, pids, r.examples,
                                  r.features, S.rows_with_models(S.parse_table(ct, [j]), S.X_ROWS_CAP) if run.rows else None, list(r.types), text, self.draws, r.hash in in_state,
                                  r.hash in self.hash_count or r.hash in made_hashes))
            made_hashes.add(r.hash)
        query = Query(fid, text, kind, depth, parents, reads)
        self.forms[fid] = query
        if made:
            self.defs[made[0][1].table[0]] = fid
        for (s, r, j), table_at in zip(made, tables):
            self.nodes[table_at.id], self.keys[(*r.table, r.at)] = table_at, table_at.id
            self.hash_count[r.hash] += 1
            query.nodes.append(table_at.id)
            gold = self.gold.get(r.hash)
            if gold is not None and r.hash not in self.covered:
                self.covered[r.hash] = table_at.id
                self.event(dict(event='cover', gold=gold, node=table_at.id, depth=depth, draw=self.draws, seconds=round(time.monotonic() - self.a.t0, 1)))
            self.write(dict(token='%d' % table_at.id, types=table_at.types, arity=table_at.arity, depth=depth, examples=[[k, i, n, '%016x' % h] for k, i, _, n, h in r.examples],
                            example_keys=[list(x) for x in r.examples], query='%032x' % r.table[0], name=r.table[1], at=[['%032x' % d, '%032x' % v] for d, v in r.at],
                            hash='%032x' % r.hash, features=[float(x) for x in r.features], same_in_state=table_at.same_in_state, seen_before=table_at.seen_before,
                            parents=['%d' % p for p in pids], clause=text, n_clauses=1, x_rows=table_at.rows or [], table_types=table_at.table_types,
                            scope=['%d' % n for f in self.scoped for n in self.forms[f].nodes],
                            tags=dict(kind='gold' if gold is not None else 'junk', draw=self.draws, seeded=seeded)))
            self.policy.add(table_at)
            if not self.keep_rows:
                table_at.rows = None
        per_table = collections.defaultdict(list)
        for s, r, j in made:
            per_table[s].append(r)
        for rs in per_table.values():
            self.table_sets.setdefault(tuple(sorted(r.hash for r in rs)), self.keys[(*rs[0].table, rs[0].at)])
        for p in parents:
            for n in self.forms[p].nodes:
                self.nodes[n].n_readers += 1
                self.policy.add(self.nodes[n])
        return query

    def rebuild_maps(self):
        """defs, keys, hash_count, covered and table_sets from forms and nodes, as add_query makes them: a bank holds the queries and the TableAts, and a renewal reads them
        back. A query with no TableAt has no QueryHash here, as it has none in defs. covered reads self.gold, which the Pool has from its start. A slot's TableAts have the same
        (QueryHash, Name), in the order that add_query made them."""
        self.defs = {self.nodes[q.nodes[0]].table[0]: i for i, q in self.forms.items() if q.nodes}
        self.keys = {(*t.table, t.at): t.id for t in self.nodes.values()}
        self.hash_count = collections.Counter(t.hash for t in self.nodes.values())
        self.covered, self.table_sets = {}, {}
        for q in self.forms.values():
            per_table = collections.defaultdict(list)
            for n in q.nodes:
                t = self.nodes[n]
                per_table[t.table].append(t)
                if self.gold.get(t.hash) is not None and t.hash not in self.covered:
                    self.covered[t.hash] = t.id
            for ts in per_table.values():
                self.table_sets.setdefault(tuple(sorted(t.hash for t in ts)), self.keys[(*ts[0].table, ts[0].at)])

    def seed(self, sexp, level, levels):
        """Puts gold's queries of DAG depth up to level / levels of gold's greatest depth in the bank. The cut reads read edges, so a query's
        ancestors are always in it, and written order plays no part."""
        lines = [x for x in sexp.strip().split('\n') if not x.startswith('(OUT')]
        heads = [live.head_of(x) for x in lines]
        depth, reads = {}, {}
        for h, x in zip(heads, lines):
            reads[h] = {m for m in NAME.findall(x) if m in depth and m != h}
            depth[h] = 1 + max((depth[r] for r in reads[h]), default=0)
        cut = -(-max(depth.values()) * level // levels)
        keep = [(h, x) for h, x in zip(heads, lines) if depth[h] <= cut]
        ids = {h: i for i, (h, _) in enumerate(keep)}
        texts = [NAME.sub(lambda m: '&f%d' % ids[m[0]] if m[0] in ids else m[0], x) for h, x in keep]
        run = self.run
        run.collect = []
        _, pg = run.scope(texts)
        steps, run.collect, run.scoped = run.collect, None, None
        for (h, x), text, (ct, tables, indexes) in zip(keep, texts, steps):
            made = [(s, r, j) for s in tables for r, j in zip(tables[s], indexes[s]) if r.hash is not None and isinstance(r.table, tuple)]
            if made and made[0][1].table[0] in self.defs:
                made = []
            self.add_query(ids[h], text, x[1:x.index(' ')], depth[h], sorted(ids[r] for r in reads[h]), len(reads[h]), made, ct, pg, seeded=True)
        return len(keep), len(lines), cut, max(depth.values())

    def test(self, f, pg, form):
        run = self.run
        t0 = time.perf_counter()
        for dec in run.search(pg, f):
            att = dec.attempts()
            key = json.dumps(att)
            if key not in self.candidates:
                loo, text = run.last_loo, dec.program_form()
                self.candidates[key] = dict(attempts=att, program=text, form=form.id)
                self.event(dict(event='candidate', form=form.id, depth=form.depth, draw=self.draws, seconds=round(time.monotonic() - self.a.t0, 1), attempts=att, program=text,
                                score=sum(r == 'pass' for r in loo) / len(loo) if loo else 0, size=text.count('\n')))
        fills = getattr(run, 'fills', None)  # the forms leave-one-out refused, which may fill attempt slots that candidates leave open
        if fills:
            for text, att in fills:
                self.event(dict(event='fill', attempts=att, size=text.count('\n'), program=text))
            fills.clear()
        run.c['search_seconds'] += time.perf_counter() - t0

    def save_before_end(self, deadline):
        """Calls save one time, when no more than CLAUSE_SECONDS are left to deadline: a draw can run past the deadline, and the supervisor kills the worker there, so the bank
        is on disk before the last draw starts."""
        if not self.saved_before_end and deadline - time.monotonic() <= CLAUSE_SECONDS and self.save is not None:
            self.saved_before_end = True
            self.save()

    def grow(self, deadline, every=50):
        last, t0 = 0, time.monotonic()
        while time.monotonic() < deadline:
            fids = self.scope()
            for _ in range(self.a.draws_per_scope):
                self.draw(fids, deadline)
            self.tick()
            self.save_before_end(deadline)
            why = self.stop and self.stop()
            if why:
                return why
            if self.draws - last >= every:
                last = self.draws
                t = time.monotonic() - t0
                print('%s %d s, %.0f s left: %d draws, %.1f draws/s, %d forms, %d nodes, depth %d, candidates %d, gold covered %d of %d, RSS peak %.0f MiB' % (
                    self.id, t, deadline - time.monotonic(), self.draws, self.draws / max(t, 1e-9), len(self.forms), len(self.nodes),
                    max((f.depth for f in self.forms.values()), default=0), len(self.candidates), len(self.covered), len(self.gold), rss_mib()), flush=True)


def make_policy(folder, task):
    """The scored Policy of the policy.py in folder, or UniformPolicy with no folder."""
    if not folder:
        return UniformPolicy(task)
    sys.path.insert(0, folder)
    import policy
    return policy.Policy(task)


def session_of(task_id):
    """An open-world session of the task with no test output, the task, and the settings."""
    d = json.load(open(S.TASKS + task_id + '.json'))
    outs = [t.pop('output', None) for t in d['test']]
    st = arclog.DecodeSettings(relations=RELATIONS, **SETTINGS)
    return arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), st, session_bytes=SESSION_BYTES), d, outs


def gold_keys(run, sexp):
    """{TableHash: gold query index} of gold's tables at each assignment, in the session of run. Gives {} and counts a reason where gold does not replay."""
    forms = [str(f) for f in sexp.strip().split('\n') if not f.startswith('(OUT')]
    run.collect = []
    keys = {}
    try:
        run.scope(forms)
        for i, (_, tables, _) in enumerate(run.collect):
            for rs in tables.values():
                for r in rs:
                    if r.hash is None:
                        run.c['gold:table not finished'] += 1
                    else:
                        keys.setdefault(r.hash, i)
    except Exception as e:  # noqa: BLE001
        run.c['gold:no replay %s' % type(e).__name__] += 1
        print('gold does not replay: %s' % str(e)[:200], flush=True)
    run.collect = None
    run.scoped = None
    return keys


def one_task(sampler, task_id, gold_sexp, a):
    out = '%s/%s' % (a.out, task_id)
    sess, d, outs = session_of(task_id)
    a.t0 = time.monotonic()
    deadline = a.t0 + a.seconds
    run = Run(sampler.pri, sess, a.seed, deadline, d, live.Limits())
    gold = gold_keys(run, gold_sexp) if gold_sexp else {}
    print('%s: %d gold relations in the cover check, %d train pairs' % (task_id, len(gold), len(d['train'])), flush=True)
    with S.JsonlWriter(out + '.nodes.jsonl.zst') as nodes, open(out + '.events.jsonl', 'w') as ev:
        def event(x):
            ev.write(json.dumps(x) + '\n')
            ev.flush()
        pool = Pool(task_id, d, run, make_policy(a.policy, d), gold, nodes.write, event, a)
        if a.seed_level:
            print('seeded: %d of %d forms, depth cut %d of %d' % pool.seed(gold_sexp, a.seed_level, a.levels), flush=True)
        pool.grow(deadline)
        hits = sum(all(o in at for o, at in zip(outs, t['attempts'])) for t in pool.candidates.values())
        done = dict(task=task_id, seconds=round(time.monotonic() - a.t0, 1), draws=pool.draws, forms=len(pool.forms), nodes=len(pool.nodes), candidates=len(pool.candidates), right=hits,
                    gold=len(gold), covered=len(pool.covered), depth=collections.Counter(f.depth for f in pool.forms.values()), peak_rss_mib=round(rss_mib()),
                    counts={k: v for k, v in run.c.items() if isinstance(v, (int, float))})
        event(dict(event='done', **done))
    with open(out + '.done.json', 'w') as f:
        json.dump(done, f)
    print(json.dumps({k: v for k, v in done.items() if k != 'counts'}), flush=True)
    for k, v in sorted(run.c.items(), key=lambda x: -x[1])[:24]:
        print('  %8.1f %s' % (v, k), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='*')
    ap.add_argument('--seconds', type=float, default=300)
    ap.add_argument('--k', type=int, default=6, help='nodes a scope picks')
    ap.add_argument('--draws-per-scope', type=int, default=4)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--seed-level', type=int, default=0, help="seed gold's forms up to this share of its DAG depth")
    ap.add_argument('--levels', type=int, default=3)
    ap.add_argument('--policy', default='', help='a folder with policy.py; none: UniformPolicy')
    ap.add_argument('--out', default=P.SAMPLER_DATA + '/runs/superdag1')
    ap.add_argument('--points', default=P.SAMPLER_DATA + '/runs/pool1/points.json', help="gold programs for the cover check; a task with none runs with no cover check")
    ap.add_argument('--models', default=P.SAMPLER_DATA + '/models')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    golds = {s['task']: s['gold_sexp'] for s in json.load(open(a.points))} if os.path.exists(a.points) else {}
    tasks = a.tasks or sorted(golds)
    sampler = live.Sampler(a.models)
    for k, t in enumerate(tasks, 1):
        if os.path.exists('%s/%s.done.json' % (a.out, t)):
            continue
        print('%d/%d %s' % (k, len(tasks), t), flush=True)
        one_task(sampler, t, golds.get(t), a)


if __name__ == '__main__':
    main()
