#!/usr/bin/env python
"""A task's super DAG: a pool of clauses, grown by drawing each clause over a scope that a policy picks.

A node is a relation of a kept clause. Two relations with the same column types and the same rows on every input, under every
DET assignment, are one node: the merge key is order-free in the columns, the assignments and the clauses that made the rows. A clause
is kept where one of its relations is a new node. A clause that gives only known nodes adds to their n_clauses and lowers their depth;
it adds no form, since its tables add nothing that a reader can use.

A scope is the forms of the nodes that the policy picks, with their ancestors by reads, in depth order. draws_per_scope draws share
one scope, which is replayed once.

A policy has add(node), called once per new node and again where its depth, readers or n_clauses change, and scope(k, rng), which
gives at most k node ids. It reads Node's fields, and no gold reaches it.

After each kept clause, Run.search tests the OUT candidates over its new relations. Each distinct attempt set that passes the filter is a
candidate program.

With a gold program, the cover check reads gold's tables in the same session, so that row hashes compare, and records when a node
equals each gold relation. This reads the task's solution, so it runs on dev tasks only, and its only effect is on the output's tags
and the cover events.

Output, under --out, per task:
- <task>.nodes.jsonl.zst: a record per new node, in the form of pool_rows.py's nodes files, with clause and n_clauses.
- <task>.events.jsonl: a line per candidate program, per gold relation covered, and a last line with the counts.
- With --seed-level, gold's shallow forms start the bank, and their nodes have tags.seeded true.
- <task>.done.json: the counts, once the task's budget ends. A task with this file is skipped on a restart.

  RAYON_NUM_THREADS=1 <runtime python> -u superdag.py TASK ... [--seconds 300] [--k 6] [--draws-per-scope 4] [--out DIR]
"""
import argparse
import collections
import dataclasses
import hashlib
import json
import os
import random
import re
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import sampler_paths as P  # noqa: E402
from live import M, S, arclog  # noqa: E402
from live_try import SETTINGS  # noqa: E402

SESSION_BYTES = 2 << 30
RELATIONS = 4096  # relation slots of a decode, and so the most that a scope declares
MAX_SCOPE_FORMS = 96
CLAUSE_SECONDS = 20.0
SPLIT_FORM = re.compile(r'&f(\d+)')
NAME = re.compile(r'&[A-Za-z_]\w*')


def rss_mib():
    """Peak RSS: ru_maxrss is in bytes on macOS and in KiB on Linux."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2 ** 20 if sys.platform == 'darwin' else 2 ** 10)


class OneTable:
    """Table j of a step_tables result, as parse_table reads a result that holds one table."""

    def __init__(self, ct, j):
        self.ct = ct
        self.base_tables = (ct.base_tables or 0) + j
        self.tables = {k: [v[j]] for k, v in ct.tables.items() if k != 'relation'}

    def __getattr__(self, name):
        return getattr(self.ct, name)


def relation_tables(ct):
    """[(relation slot, table index)] of a step_tables result, in its order."""
    rel = M.col(ct, 'tables', 'relation') if isinstance(ct.tables['relation'], (bytes, bytearray, memoryview)) else ct.tables['relation']
    return [(int(rel[j]), j) for j in range(len(ct.tables['form'])) if rel[j] >= 0]


def table_key(tb):
    """(merge key, [[example kind, index, rows, row hash]]) of a parsed table. Hashes compare within a session."""
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    entries = [(tuple(ex), rows) for ex, _, rows, _, _ in tb['entries']]
    cols = []
    for t, (a, b) in zip(tb['types'], spans):
        cols.append((str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries))), a, b))
    order = sorted(cols)
    per, counts = collections.defaultdict(set), collections.Counter()
    for ex, rows in entries:
        per[ex].add(hash(frozenset(tuple(v for _, _, a, b in order for v in r[a:b]) for r in rows)))
        counts[ex] = max(counts[ex], len(rows))
    body = tuple(sorted((ex, tuple(sorted(s))) for ex, s in per.items()))
    return (tuple(c[0] for c in order), hash(body)), [[ex[0], ex[1], counts[ex], '%016x' % (hash(tuple(sorted(per[ex]))) & (2 ** 64 - 1))] for ex in sorted(per)]


@dataclasses.dataclass
class Form:
    id: int
    text: str
    kind: str
    depth: int
    parents: list  # form ids
    reads: int  # relations the clause reads, atoms of a kind
    nodes: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Node:
    id: int
    form: int
    types: list
    arity: int
    depth: int
    parents: list  # node ids of the forms that the clause reads
    examples: list
    rows: list  # S.rows_with_models at X_ROWS_CAP
    table_types: list
    clause: str
    age: int  # the draw that made it; for an oldest-first share of picks, and for nothing else
    n_clauses: int = 1
    n_readers: int = 0
    frames: object = None


class UniformPolicy:
    """Picks nodes at random: the stand-in until the scored policy exists."""

    def __init__(self, task):
        self.ids = []

    def add(self, node):
        if node.n_clauses == 1 and node.n_readers == 0:
            self.ids.append(node.id)

    def scope(self, k, rng):
        return rng.sample(self.ids, min(k, len(self.ids)))


class Run(live.Run):
    """live.Run that keeps what each drawn clause reads, and can hold the tables of each form it replays."""

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
            self.collect.append(pg.before)


class Pool:
    def __init__(self, task_id, task, run, policy, gold, write, event, a):
        self.id, self.task, self.run, self.policy, self.gold, self.write, self.event, self.a = task_id, task, run, policy, gold, write, event, a
        self.forms, self.nodes, self.keys = {}, {}, {}
        self.candidates, self.covered, self.draws, self.rng = {}, {}, 0, random.Random('%s %d' % (task_id, a.seed))
        self.keep_rows, self.tick, self.stop = True, lambda: None, None  # stop gives a reason to end growth, or None
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
        names = [k for k in live.KIND_TOK if dec.admits([live.KIND_TOK[k]])[0]]
        return self.rng.choices(names, weights=[self.kinds[k] + 1 for k in names])[0]

    def draw(self, fids, deadline):
        """One clause over the scope fids. Keeps it where it gives a new node, and tests its OUT candidates."""
        run, forms = self.run, [self.forms[f].text for f in fids]
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
            run.c['drop:table: ' + re.sub(r'\d+', 'N', str(e))[:40]] += 1
        except Exception as e:  # noqa: BLE001
            run.failed(e)

    def take(self, f, pg, kind, nscope):
        """The new Form of the clause at decoder f, or None where it gives no new node."""
        run = self.run
        line = f.program_form().split('\n')[nscope]
        fid = len(self.forms)
        names = pg.written | {live.head_of(line): '&f%d' % fid}
        text = re.sub(r'&r\d+', lambda m: names.get(m[0], m[0]), line)
        parents = sorted({int(x) for x in SPLIT_FORM.findall(text)} - {fid})
        depth = 1 + max((self.forms[p].depth for p in parents), default=0)
        made = []
        for s, j in relation_tables(pg.before):
            tb = S.parse_table(OneTable(pg.before, j))
            made.append((s, tb, *table_key(tb)))
        if not made:
            run.c['node:no table'] += 1
            return None
        new = [m for m in made if m[2] not in self.keys]
        for _, _, key, _ in made:
            if key in self.keys:
                self.merge(self.nodes[self.keys[key]], text, depth, len(run.reads))
        if not new:
            run.c['node:equal'] += 1
            return None
        form = self.add_form(fid, text, kind, depth, parents, len(run.reads), new, pg)
        run.c['kept:' + kind] += 1
        return form

    def add_form(self, fid, text, kind, depth, parents, reads, new, pg, seeded=False):
        """The Form with the new nodes new, written and given to the policy. A form with no new node stays in the bank where seeded."""
        run = self.run
        form = Form(fid, text, kind, depth, parents, reads)
        self.forms[fid] = form
        pids = [n for p in parents for n in self.forms[p].nodes]
        for s, tb, key, ex in new:
            node = Node(len(self.nodes), fid, sorted(str(t) for t in pg.decl_types.get(s, ())), len(set(pg.decl_slots.get(s, ()))), depth, pids, ex,
                        S.rows_with_models(tb, S.X_ROWS_CAP), [str(t) for t in tb['types']], text, self.draws)
            self.nodes[node.id], self.keys[key] = node, node.id
            form.nodes.append(node.id)
            gold = self.gold.get(key)
            if gold is not None and key not in self.covered:
                self.covered[key] = node.id
                self.event(dict(event='cover', gold=gold, node=node.id, depth=depth, draw=self.draws, seconds=round(time.monotonic() - self.a.t0, 1)))
            self.write(dict(token='%d' % node.id, types=node.types, arity=node.arity, depth=depth, examples=ex, parents=['%d' % p for p in pids],
                            clause=text, n_clauses=1, x_rows=node.rows, table_types=node.table_types,
                            tags=dict(kind='gold' if gold is not None else 'junk', draw=self.draws, seeded=seeded)))
            self.policy.add(node)
            if not self.keep_rows:
                node.rows = None
        for p in parents:
            for n in self.forms[p].nodes:
                self.nodes[n].n_readers += 1
                self.policy.add(self.nodes[n])
        return form

    def seed(self, sexp, level, levels):
        """Puts gold's forms of DAG depth up to level / levels of gold's greatest depth in the bank. The cut reads read edges, so a form's
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
        tables, run.collect, run.scoped = run.collect, None, None
        for (h, x), text, ct in zip(keep, texts, tables):
            made = [(s, tb, *table_key(tb)) for s, j in relation_tables(ct) for tb in [S.parse_table(OneTable(ct, j))]]
            new = [m for m in made if m[2] not in self.keys]
            self.add_form(ids[h], text, x[1:x.index(' ')], depth[h], sorted(ids[r] for r in reads[h]), len(reads[h]), new, pg, seeded=True)
        return len(keep), len(lines), cut, max(depth.values())

    def merge(self, node, text, depth, reads):
        node.n_clauses += 1
        node.depth = min(node.depth, depth)
        self.policy.add(node)

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
        run.c['search_seconds'] += time.perf_counter() - t0

    def grow(self, deadline, every=50):
        last, t0 = 0, time.monotonic()
        while time.monotonic() < deadline:
            fids = self.scope()
            for _ in range(self.a.draws_per_scope):
                self.draw(fids, deadline)
            self.tick()
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
    """{merge key: gold form index} of gold's relations, in the session of run. Gives {} and counts a reason where gold does not replay."""
    forms = [str(f) for f in sexp.strip().split('\n') if not f.startswith('(OUT')]
    run.collect = []
    keys = {}
    try:
        run.scope(forms)
        for i, ct in enumerate(run.collect):
            for _, j in relation_tables(ct):
                try:
                    keys.setdefault(table_key(S.parse_table(OneTable(ct, j)))[0], i)
                except M.Fail:
                    run.c['gold:table not finished'] += 1
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
