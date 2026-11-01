#!/usr/bin/env python
"""Nodes one hop from deep gold points: at each point, gold's next table beside junk tables drawn on the same prefix, for feature work on
gold against noise at a depth that a pool does not reach.

- Point: a stored gold point in sample2_col.FSTORE of a dev task, target's depth DEPTH or more. The target is the point's clause, and
  points of one clause count as one. Folds: fB is the tasks of --fold-b, a JSON dict of task lists; fA is every other dev task. Each
  fold has --points / 2 points, at most PER_TASK of a task. RULE, DET and INIT take turns in the hash order of sample2_col.pick_groups
  until a kind has no points left. A point with a CHOOSE or a RIGID_DET form before the target is left out, since Sampler.clause
  refuses such a scope, and points.json counts those.
- Prefix: gold's forms before the target, in written order, which is a dependency order. It reads nothing but the program's text.
- Junk: --draws calls of live.Sampler.clause on the prefix, of the target's kind, seeded by the task, the point and the draw. Each clause
  reads only the prefix: no clause is added to the scope, so the tables of a draw are one hop from gold.
- A node is a relation's table. A clause's table that stops is no node, and the counts have it. A junk table that equals a node on column
  types and rows at every example is no node, and the counts say which kind of node it equals. Equal tables are compared as in pool_rows.
- Every kept point has one positive: the target's table, or the tables of its ports for an INIT, each tagged gold. A point whose target
  has no finished table is skipped and counted. A gold table that equals an earlier gold table is kept, with tags.repeat true.

Output, under --out:

- points.json: `points`, the fixed list of points, and `counts`, what picking left out. A run reads this file if it exists, so --points and
  --fold-b have an effect only on the run that makes it. A point has id (its directory in FSTORE), task, case, point, fold, kind, group,
  depth, gold_sexp and point_dir.
- nodes/<id>.nodes.jsonl.zst: a record per node, in pool_rows' nodes form: token, types (sorted), arity, depth, examples, parents (the
  tokens and lib names the clause reads), x_rows (entries [1, i] are train, [2, i] are test, and [0, 0] is one table for all examples,
  as a DET's or a relation's that reads no example has; a DET's Example column gives each row's example), table_types (the types in the
  order of x_rows' columns) and tags. Tags are for scoring and filtering, no feature: kind (gold, available or junk), draw (the draw index, None
  on gold's forms) and repeat. Tokens and row hashes compare within a point: each point has its own session.
- nodes/<id>.done.json: the point's counts, last written. status is done or skipped, with reason on a skipped point. A restart passes over
  a point that has this file and writes any other point again.

--shard K/N takes every Nth point of points.json from the Kth, before finished points are left out, so each shard's share stays the same
whichever shards have run. --seconds limits a point, gold's forms included. A draw that overruns its deadline does so by up to
OVERRUN seconds, so draws stop that long before the limit.

  RAYON_NUM_THREADS=1 <runtime python> -u hop1_rows.py [--out DIR] [--fold-b TASKS.json] [--shard K/N] [--seconds 60] [--draws 50] [--only ID ...] [--limit N]
"""
import argparse
import collections
import dataclasses
import gc
import gzip
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import pool_rows as R  # noqa: E402
import sampler_paths as P  # noqa: E402
from live import M, S, arclog  # noqa: E402
from live_try import SETTINGS  # noqa: E402

DEPTH = 4
PER_TASK = 2
KINDS = 'RULE', 'DET', 'INIT'  # the kinds that strata.point_fields has a point group for; a RIGID_DET target or an earlier RIGID_DET form leaves the point out
SESSION_BYTES = 1 << 30  # a session's cap: a process has the session, the priors and the models, and stays under 2 GiB
OVERRUN = 10.0  # seconds a draw can run past its deadline


def sha(x):
    return hashlib.sha256(x.encode()).hexdigest()


def store_points():
    """sample2_col.fstore_points' result. An index newer than the store is read alone, since listing the store takes minutes."""
    if not os.path.exists(S.FSTORE_INDEX) or os.path.getmtime(S.FSTORE_INDEX) < os.path.getmtime(S.FSTORE):
        return S.fstore_points()
    with gzip.open(S.FSTORE_INDEX, 'rt') as f:
        c = json.load(f)
    return {d: (e[0], e[1], c['golds'][e[2]]) for d, e in c['points'].items()}


def candidates(idx, dev, fold_b, counts):
    """{(fold, kind): [point]}, the points of a target in the hash order of pick_groups, a task's first point before any task's second."""
    parsed, seen, place = {}, set(), collections.Counter()
    out = collections.defaultdict(list)
    for d in sorted((d for d in idx if d.split('-')[0] in dev), key=lambda d: (sha(d.split('-')[0]), sha(d))):
        task = d.split('-')[0]
        case, point, gold = idx[d]
        forms = parsed.setdefault(gold, S.strata.sexprs(gold))
        i = point[0]
        if i >= len(forms) or not forms[i] or forms[i][0] not in KINDS or not any(isinstance(x, list) for x in forms[i][2:]):  # no body to draw
            continue
        pf = S.strata.point_fields(forms, i)
        target = (task, gold[:S.form_spans(gold)[i][1]])
        if pf['depth'] < DEPTH or target in seen:
            continue
        seen.add(target)
        counts['targets'] += 1
        other = sorted({str(f[0]) for f in forms[:i] if f and f[0] not in KINDS})
        if other:
            counts['left out: %s before the target' % ' and '.join(other)] += 1
            continue
        kind = forms[i][0]
        fold = 'fB' if task in fold_b else 'fA'
        out[fold, kind].append(dict(id=d, task=task, case=case, point=point, fold=fold, kind=kind, group=pf['point_group'], depth=pf['depth'],
                                    gold_sexp=gold, point_dir=S.FSTORE + d, order=(place[task, kind], sha(task))))
        place[task, kind] += 1
    return out


def deal(by_kind, n):
    """Up to n of one fold's points: the kinds take turns, a kind with no points left drops out, and a task gives at most PER_TASK."""
    queues = {k: iter(sorted(v, key=lambda s: s.pop('order'))) for k, v in by_kind.items()}
    per, got = collections.Counter(), []
    while queues and len(got) < n:
        for k in list(queues):
            s = next((s for s in queues[k] if per[s['task']] < PER_TASK), None)
            if s is None:
                del queues[k]
            elif len(got) < n:
                per[s['task']] += 1
                got.append(s)
    return got


def points(a):
    """The fixed list of points, from points.json. A run that finds no such file picks them; picking gives the same list each time."""
    p = a.out + '/points.json'
    if not os.path.exists(p):
        if not a.fold_b:
            sys.exit('%s does not exist, and picking needs --fold-b' % p)
        dev = {t for t, s in json.load(open(S.SPLITS)).items() if s == 'dev'}
        fold_b = set(sum(json.load(open(a.fold_b)).values(), []))
        counts = collections.Counter()
        cands = candidates(store_points(), dev, fold_b, counts)
        picked = []
        for fold in ('fA', 'fB'):
            picked += deal({k: v for (f, k), v in cands.items() if f == fold}, a.points // 2)
        os.makedirs(a.out, exist_ok=True)
        R.write_json(p, dict(points=sorted(picked, key=lambda s: sha(s['id'])), counts=counts))
    return json.load(open(p))['points']


def session_of(task):
    """An open-world session of the task with no test output, its settings, and the task."""
    d = json.load(open(S.TASKS + task + '.json'))
    for t in d['test']:
        t.pop('output', None)
    st = arclog.DecodeSettings(**SETTINGS)
    return arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), st, session_bytes=SESSION_BYTES), st, d


@dataclasses.dataclass
class Nodes:
    """A point's nodes so far. Junk clauses take the same slots as each other, so slot_node and slot_depth hold gold's slots alone."""

    run: object
    out: object
    tally: collections.Counter
    slot_node: dict = dataclasses.field(default_factory=dict)  # relation slot -> a node's token
    slot_depth: dict = dataclasses.field(default_factory=dict)
    seen: dict = dataclasses.field(default_factory=dict)  # (column types, examples) -> (a node's kind, its token)
    tokens: set = dataclasses.field(default_factory=set)

    def names(self, reads):
        """The parents of a clause that reads the relation tokens reads: nodes' tokens and lib or fact names, sorted. A slot whose table stopped has no name."""
        V = self.run.V
        got = (self.slot_node.get(M.slot_no(V.name(t))) if V.kind(t) == 'relation' else V.name(t) for t in reads)
        return sorted({n for n in got if n is not None})

    def depth(self, reads):
        V = self.run.V
        return 1 + max([self.slot_depth.get(M.slot_no(V.name(t)), 0) for t in reads if V.kind(t) == 'relation'], default=0)

    def add(self, ct, reads, kind, draw=None):
        """Writes the nodes of the step_tables result ct, a clause that reads reads, and gives how many it wrote."""
        names, depth, slots, fresh = self.names(reads), self.depth(reads), dict(self.slot_node), []
        for s, j in R.relation_tables(ct):
            if kind != 'junk':
                self.slot_depth[s] = depth
            try:
                tb = S.parse_table(R.OneTable(ct, j))
            except M.Fail:
                self.tally['table stopped: ' + kind] += 1
                continue
            ex, types = R.examples_of(tb), sorted(str(t) for t in ct.tables['column_types'][j])
            key = repr((types, ex))
            old = self.seen.get(key)
            if kind == 'junk' and old:
                self.tally['table equal: ' + old[0]] += 1
                slots[s] = old[1]
                continue
            tok = R.digest((types, ex))
            while tok in self.tokens:  # two gold tables equal on rows: one token each
                tok = R.digest((tok, types))
            self.tokens.add(tok)
            slots[s] = tok
            self.seen.setdefault(key, (kind, tok))
            arity = len({int(c) for c in ct.tables['column_slots'][j]})
            fresh.append((tb, tok, dict(token=tok, types=types, arity=arity, depth=depth, examples=ex, tags=dict(kind=kind, draw=draw, repeat=old is not None))))
        for tb, tok, node in fresh:
            xr = S.rows_with_models(tb, S.X_ROWS_CAP)
            for e in xr:
                e[3] = {slots.get(int(k), 'none'): v for k, v in e[3].items()}
            self.out.write(dict(node, parents=names, x_rows=xr, table_types=[str(t) for t in tb['types']]))
        if kind != 'junk':
            self.slot_node = slots
        self.tally['nodes: ' + kind] += len(fresh)
        return len(fresh)


def clause_reads(run, st, clause, at):
    """The relation tokens that form at of clause's program reads."""
    ids, model, paths = arclog.StudyProgram.from_sexp(clause.decoder.program_form() + '\n' + live.READER_OUT, st).decode_stream()
    return R.forms_of(run.V, ids, model, paths)[at][2]


def one_point(sampler, spec, a, nodes_p):
    """Writes the point's nodes to nodes_p and gives (the reason it was skipped or None, its counts, the run's counts)."""
    t0 = time.monotonic()
    end, tally = t0 + a.seconds, collections.Counter()
    gold, i = spec['gold_sexp'], spec['point'][0]
    texts = [gold[x:y] for x, y in S.form_spans(gold)]
    prefix, target = texts[:i], texts[i]
    sess, st, task = session_of(spec['task'])
    sampler.run = run = live.Run(sampler.pri, sess, 0, end, task, live.Limits())  # Sampler.clause keeps a Run of this session
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join([*prefix, target, live.READER_OUT]), st).decode_stream()
    forms = R.forms_of(run.V, ids, model, paths)
    pg, dec, tmap = live.Program(), run.root.fork(), {}
    with S.JsonlWriter(nodes_p) as out:
        nodes = Nodes(run, out, tally)
        for f in range(i + 1):
            if time.monotonic() >= end:
                return "gold's forms took the time limit", tally, run.c
            reads = R.step_form(run, pg, dec, (ids, model, forms), f, tmap)
            made = nodes.add(pg.before, reads, 'gold' if f == i else 'available')
        if not made:
            return "gold's next table stopped", tally, run.c
        tally['gold_seconds'] = round(time.monotonic() - t0, 3)
        stop = end - OVERRUN
        for k in range(a.draws):
            now = time.monotonic()
            if now >= stop:
                tally['draws cut by the time limit'] = a.draws - k
                break
            seed = int(R.digest((a.seed, spec['task'], spec['id'], k), 8), 16)
            got = sampler.clause(sess, seed, min(stop, now + a.draw_seconds), task, prefix, spec['kind'])
            tally['draws'] += 1
            if got is None:
                tally['draws with no clause'] += 1
            else:
                nodes.add(got.tables, clause_reads(run, st, got, i), 'junk', k)
    return None, tally, run.c


def finish_point(sampler, spec, a, nodes_p, done_p):
    """Runs a point from nothing, writes its done file, and gives that file's value."""
    for q in (nodes_p, nodes_p + '.idx.jsonl'):
        if os.path.exists(q):
            os.remove(q)
    t0 = time.monotonic()
    try:
        reason, tally, counts = one_point(sampler, spec, a, nodes_p)
    except Exception as e:  # noqa: BLE001  # a point that fails is counted: a restart would meet it again, and the shard's other points wait behind it
        reason, tally, counts = '%s: %s' % (type(e).__name__, str(e)[:100]), collections.Counter(), sampler.run.c
    if reason:
        for q in (nodes_p, nodes_p + '.idx.jsonl'):
            if os.path.exists(q):
                os.remove(q)
    done = dict(id=spec['id'], task=spec['task'], fold=spec['fold'], kind=spec['kind'], status='skipped' if reason else 'done', reason=reason,
                seconds=round(time.monotonic() - t0, 2), peak_rss_mib=round(R.rss_mib()), counts=dict(tally),
                draw_counts={k: v for k, v in sorted(counts.items()) if isinstance(k, str)})
    sampler.run = None  # the session goes before the next one comes
    gc.collect()
    R.write_json(done_p, done)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=P.SAMPLER_DATA + '/runs/hop1')
    ap.add_argument('--fold-b', default=None, help="a JSON dict of task lists, fold fB's tasks; only the run that makes points.json reads it")
    ap.add_argument('--points', type=int, default=500, help='the points of both folds; only the run that makes points.json reads it')
    ap.add_argument('--pick-only', action='store_true', help='makes points.json and ends')
    ap.add_argument('--draws', type=int, default=50, help='clause draws per point')
    ap.add_argument('--seconds', type=float, default=60, help="a point's time limit, gold's forms included")
    ap.add_argument('--draw-seconds', type=float, default=5, help="a draw's deadline")
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--shard', default='0/1', help='K/N: this run takes every Nth point of points.json from the Kth')
    ap.add_argument('--only', nargs='*', default=None, help="only these point ids of this shard's share")
    ap.add_argument('--limit', type=int, default=None, help='at most this many points of what is left')
    ap.add_argument('--models', default=P.SAMPLER_DATA + '/models')
    a = ap.parse_args()
    specs = points(a)
    print('%d points in %s/points.json: %s' % (len(specs), a.out, sorted(collections.Counter((s['fold'], s['kind']) for s in specs).items())), flush=True)
    if a.pick_only:
        return
    k, n = map(int, a.shard.split('/'))
    share = specs[k::n]
    if a.only:
        share = [s for s in share if s['id'] in a.only]
    os.makedirs(a.out + '/nodes', exist_ok=True)

    def path(s, x):
        return '%s/nodes/%s.%s' % (a.out, s['id'], x)

    todo = [s for s in share if not os.path.exists(path(s, 'done.json'))][:a.limit]
    print('shard %s: %d points of %d left' % (a.shard, len(todo), len(share)), flush=True)
    t0 = time.monotonic()
    sampler = live.Sampler(a.models)
    print('models loaded in %.1f s' % (time.monotonic() - t0), flush=True)
    t0 = time.monotonic()
    tally = collections.Counter()
    for done_n, s in enumerate(todo, 1):
        d = finish_point(sampler, s, a, path(s, 'nodes.jsonl.zst'), path(s, 'done.json'))
        c = d['counts']
        tally[d['status']] += 1
        tally['skipped: %s' % d['reason']] += bool(d['reason'])
        tally['points with no junk'] += d['status'] == 'done' and not c.get('nodes: junk')
        tally['junk'] += c.get('nodes: junk', 0)
        wall = time.monotonic() - t0
        rate = wall / done_n
        print('%d/%d %s %s %s %s%s: junk %d of %d draws, gold %d, available %d, stopped %d, %.1f s; %.1f s/point, ETA %.0f s, RSS peak %.0f MiB' % (
            done_n, len(todo), s['id'], s['fold'], s['kind'], d['status'], ' (%s)' % d['reason'] if d['reason'] else '', c.get('nodes: junk', 0), c.get('draws', 0),
            c.get('nodes: gold', 0), c.get('nodes: available', 0), sum(v for x, v in c.items() if x.startswith('table stopped')),
            d['seconds'], rate, rate * (len(todo) - done_n), R.rss_mib()), flush=True)
    print('finished: %s' % {k: v for k, v in tally.items() if v}, flush=True)


if __name__ == '__main__':
    main()
