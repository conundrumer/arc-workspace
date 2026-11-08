#!/usr/bin/env python
"""Ranker rows for relation picks among a large pool of nodes, one pool per task, as a search that grows one set of clauses has.

A pool is one live decode. Its session has DecodeSettings(relations=R), R = 2 * the largest size + 512, so one program declares
every node; the vocabulary has no slot past R. The bound that a pool reaches first is another: a DET's END walks the joint assignments of
every DET of the program (engine: held_dets), under the assignment cap of 256, which the binding does not set. Once a DET is refused
at that cap the decode can admit no DET, so the pool draws none after it; done.json's info.det_cap_at gives the nodes at that draw.
Nothing here depends on the order a gold program is written in, or on a relation slot:

- Point: one RULE depth 3+ point of each picked dev task (sample2_col.pick_groups), holdout untouched.
- Gold nodes: the relations of the point clause's ancestors by reads (role 'ancestor'), and of the gold clauses that neither read
  it nor are read by it (role 'unrelated'), whichever side of the point they are written on. The clause, the clauses that read it
  and OUT are left out. The kept clauses are stepped in a topological order, their relation tokens renumbered.
- Junk nodes: clauses from live.Run on that decode, which may read gold nodes and earlier junk. A clause that a table of it does
  not finish (a stop or a Count entry) is not kept, and neither is one whose relations each equal a node on column types and rows
  at every example. The relation of a kept clause that equals a node is that node.
- A node's token is its content's hash: a slot number shows the draw order and which nodes are gold. Content is the rows with
  the columns in a canonical order (by type, then by the column's values), since a table's order follows a clause's labels.
- depth: 1 + the largest depth among the relations the clause reads, 1 with none. readers: the kept clauses that read the relation.

Output, under --out:

- points.json: per task, the point, `train_path` (the point's train pairs) and `point_dir`.
- N<size>/<task>.rows.jsonl.zst: a row per read of the point clause, with order 'written': the atoms in the order gold writes them.
  Fields: task, case, point, pool_n (the nodes at that size), pool_target, pick ('derived', 'lib relation', 'relation macro' or
  'fact relation'), gold (the option's token), cols ({column: fresh, read, zero or rec} of the read in that order), order, tags
  (atom: the read's place in that order; occurrence: its count among reads of one relation; both for filtering, no feature),
  options, sorted by token.
- An option: token, types (sorted), arity, depth, readers, examples ([[example kind, index, rows, row hash]], over its assignments
  and models), tags. Its `tags` are for scoring and filtering, no feature: kind (gold or junk), role, draw (the draw index, None on
  gold). A lib or fact option has no examples.
- N<size>/<task>.nodes.jsonl.zst: a record per node that size added: the option's fields with no readers, `parents` (the tokens
  the clause reads), table_types (the types in the order of x_rows' columns) and x_rows, as sample2_col.rows_with_models gives them
  at X_ROWS_CAP, DET slots replaced by tokens. A node of a row at size n lies in the nodes file of n or of a smaller size. A kill
  can leave records of nodes that the pool does not hold, which no row names.
- N<size>/<task>.state.json holds the pool at the last checkpoint, which a restart and a larger size grow from, and
  N<size>/<task>.done.json its counts once the pool has the size (.done.json.last, the last run's, before that). A checkpoint comes each --checkpoint seconds and when --seconds
  ends a size on a task; the second also writes the rows of the pool as it stands, which a later run replaces. A task with a done
  file is skipped on a restart.

Row hashes compare within a task. An Ident cell is the same in every session where ARCLOG_IDENT_SOURCE is `value`, and a number that has no meaning in another session where it is not.

  RAYON_NUM_THREADS=1 <runtime python> -u pool_rows.py [--out DIR] [--tasks 40] [--large 10] [--sizes 300,3000] [--seconds 3600] [--shard K/N] [--only TASK ...]
"""
import argparse
import collections
import dataclasses
import hashlib
import json
import os
import random
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import sampler_paths as P  # noqa: E402
from live import M, S, arclog  # noqa: E402
from live_try import SETTINGS  # noqa: E402

GROUP = 'RULE depth 3+'
OPTIONS = 500  # the junk nodes of a row
SESSION_BYTES = 2 << 30
DET_CAP = 'form:DET refused: DetAdmission(Bound(Assignments { cap: N }))'  # live.Run's count of DETs refused at the cap
OUT_FORMS = '\n(RULE &pool_end (input (:P *P) (:Col *Col)))\n(OUT (&pool_end ^P ^Col))'  # a program's text needs them to parse; restore does not step them


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20


def digest(x, n=12):
    return hashlib.sha1(repr(x).encode()).hexdigest()[:n]


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


def examples_of(tb):
    """[[example kind, index, rows, row hash]] of a parsed table, each example's rows taken over its assignments and models, and
    hashed with the columns in a canonical order: by type, then by the column's values at every example."""
    per = collections.defaultdict(set)
    for ex, _, rows, _, _ in tb['entries']:
        per[ex].update(rows)
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    per = sorted(per.items())
    keys = [(str(t), digest([sorted(r[a:b] for r in rows) for _, rows in per])) for t, (a, b) in zip(tb['types'], spans)]
    order = [spans[c] for c in sorted(range(len(spans)), key=keys.__getitem__)]
    return [[k, i, len(rows), digest(sorted([r[a:b] for a, b in order] for r in rows), 16)] for (k, i), rows in per]


def forms_of(V, ids, model, paths):
    """{form index: (token indices, relations it declares, relations it reads)} of a stream. The engine emits a declaration."""
    out, cur = {}, None
    for i, p in enumerate(paths):
        cur = p[0] if p else cur
        idx, decl, reads = out.setdefault(cur, ([], [], []))
        idx.append(i)
        if V.kind(ids[i]) in S.RELATION_KINDS:
            (reads if model[i] else decl).append(ids[i])
    return out


def closure(start, edges):
    seen, todo = set(), list(start)
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo += edges.get(x, ())
    return seen


def gold_roles(ids, forms, clause):
    """{form: role} of the gold clauses that a pool holds, for the point's clause: 'ancestor' or 'unrelated'."""
    owner = {t: f for f, (_, decl, _) in forms.items() for t in decl}
    parents = {f: {owner[t] for t in reads if t in owner} - {f} for f, (_, _, reads) in forms.items()}
    children = collections.defaultdict(set)
    for f, ps in parents.items():
        for p in ps:
            children[p].add(f)
    ancestors = closure(parents[clause], parents)
    below = closure([clause], children)
    return {f: 'ancestor' if f in ancestors else 'unrelated' for f, (idx, decl, _) in forms.items()
            if f not in below and decl and ids[idx[0]] != live.OUT_TOK}


class PoolRun(live.Run):
    """live.Run that keeps the relations each drawn clause reads."""

    def __init__(self, *args):
        super().__init__(*args)
        self.reads = []
        self.table_seconds, self.parse_seconds = 0.0, 0.0

    def open_form(self, pg, dec, kind):
        self.reads = []
        return super().open_form(pg, dec, kind)

    def det(self, pg, f):
        if self.c[DET_CAP]:
            raise live.Drop('DET past the cap')
        return super().det(pg, f)

    def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        got = super().body(pg, dr, dec, kind, nlab, need, keys)
        self.reads += [t for t, _ in S.atom_uses(self.V, got[1])]
        return got

    def close(self, pg, f):
        t0 = time.perf_counter()
        super().close(pg, f)
        self.table_seconds += time.perf_counter() - t0


@dataclasses.dataclass
class Pool:
    """A task's pool: the nodes in draw order, and what the decode's slots stand for. It holds no rows, which go to the nodes file."""

    task: str
    nodes: list = dataclasses.field(default_factory=list)  # rows-free node records, gold first
    clauses: list = dataclasses.field(default_factory=list)  # per kept clause, the tokens and lib names it reads
    slot_node: dict = dataclasses.field(default_factory=dict)  # relation slot -> a node's token
    slot_depth: dict = dataclasses.field(default_factory=dict)
    seen: dict = dataclasses.field(default_factory=dict)  # (column types, examples) -> a node's token
    picks: list = dataclasses.field(default_factory=list)  # per read of the point clause: its gold token, kind, cols, and a lib or fact option's types and arity
    draws: int = 0
    det_cap_at: int = 0  # the nodes when the first DET was refused at the assignment cap; 0: none was

    def name_of(self, run, tok):
        """A read's name: a node's token, or a lib or fact relation's name; None for a slot with no node."""
        return self.slot_node.get(M.slot_no(run.V.name(tok))) if run.V.kind(tok) == 'relation' else run.V.name(tok)

    def take(self, run, pg, reads, role, draw, out):
        """Adds the nodes of the clause that ended at pg.before, written to out, and gives True; gives False where the clause is
        not kept. A gold relation is kept with examples None where its table did not finish."""
        depth = 1 + max([self.slot_depth.get(M.slot_no(run.V.name(t)), 0) for t in reads if run.V.kind(t) == 'relation'], default=0)
        names = sorted({n for n in (self.name_of(run, t) for t in reads) if n is not None})
        made, t0 = [], time.perf_counter()
        for s, j in relation_tables(pg.before):
            try:
                tb = S.parse_table(OneTable(pg.before, j))
            except M.Fail:
                if role == 'junk':
                    run.c['node:table not finished'] += 1
                    return False
                tb = None
            types = sorted(str(t) for t in pg.decl_types.get(s, ()))
            ex = examples_of(tb) if tb else None
            made.append((s, tb, types, ex, repr((types, ex)) if tb else None))
        run.parse_seconds += time.perf_counter() - t0
        new = {m[4] for m in made if m[4] not in self.seen}
        if role == 'junk' and not new:
            run.c['node:no table' if not made else 'node:equal'] += 1
            return False
        for s, tb, types, ex, key in made:
            self.slot_depth[s] = depth
            if role == 'junk' and key in self.seen:
                self.slot_node[s] = self.seen[key]
                continue
            tok = base = digest((types, ex) if tb else ('unfinished', self.task, s))
            while role != 'junk' and any(n['token'] == tok for n in self.nodes):  # two gold relations equal on rows: one token each
                tok = digest((tok, base))
            self.slot_node[s] = tok
            if tb:
                self.seen.setdefault(key, tok)
            node = dict(token=tok, types=types, arity=len(set(pg.decl_slots.get(s, ()))), depth=depth, examples=ex,
                        tags=dict(kind='junk' if role == 'junk' else 'gold', role=role, draw=draw))
            self.nodes.append(node)
            xr = S.rows_with_models(tb, S.X_ROWS_CAP) if tb else None
            for e in xr or ():
                e[3] = {self.slot_node.get(int(k), 'none'): v for k, v in e[3].items()}
            out.write(dict(node, parents=names, x_rows=xr, table_types=[str(t) for t in tb['types']] if tb else None))
        self.clauses.append(names)
        return True

    def rows(self, spec, target, seed):
        """A row per read of the point clause: gold's option, the other gold nodes, and OPTIONS junk nodes at random."""
        rs = collections.Counter(n for names in self.clauses for n in names)
        by = {n['token']: n for n in self.nodes}
        golds = [n for n in self.nodes if n['tags']['kind'] == 'gold']
        junk = [n for n in self.nodes if n['tags']['kind'] == 'junk']
        seen = collections.Counter()
        for k, (tok, pick, cols, types, arity) in enumerate(self.picks):
            occurrence = seen[tok]
            seen[tok] += 1
            rng = random.Random(digest((seed, spec['task'], target, tok, occurrence), 16))
            keep = {n['token']: n for n in golds + rng.sample(junk, min(OPTIONS, len(junk)))}
            keep.setdefault(tok, by.get(tok) or dict(token=tok, types=types, arity=arity, depth=0, examples=None, tags=dict(kind='gold', role='read', draw=None)))
            yield dict(task=spec['task'], case=spec['case'], point=spec['point'], pool_n=len(self.nodes), pool_target=target, pick=pick, gold=tok,
                       cols=cols, order='written', tags=dict(atom=k, occurrence=occurrence),
                       options=[{**keep[t], 'readers': rs[t]} for t in sorted(keep)])


def session_of(task, relations):
    """An open-world session of the task with no test output, and its settings."""
    d = json.load(open(S.TASKS + task + '.json'))
    for t in d['test']:
        t.pop('output', None)
    st = arclog.DecodeSettings(relations=relations, **SETTINGS)
    return arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), st, session_bytes=SESSION_BYTES), st


def step_form(run, pg, dec, stream, form, tmap):
    """Steps a form of stream (ids, model, forms) on dec, its relation tokens through tmap, and adds its new tokens to tmap."""
    ids, model, forms = stream
    idx, decl, reads = forms[form]
    new = []
    for i in idx:
        if model[i]:
            new += [t for t in dec.step(tmap.get(ids[i], ids[i]))[0] if run.V.kind(t) == 'relation']
            if pg.before is None:  # a program's first model step has step_tables' first result
                pg.before = arclog.step_tables(dec, *live.TABLES, True, None)
    run.declared(pg, new)
    slots = [M.slot_no(run.V.name(t)) for t in new]
    if ids[idx[0]] == live.INIT_TOK:
        pg.names.update({'&r%d' % s: '&r%d.%d' % (slots[0], i) for i, s in enumerate(slots)})
    run.close(pg, dec)
    tmap.update(zip(decl, new))
    return [tmap.get(t, t) for t in reads]


def gold_pool(run, spec, st, out):
    """The pool of the point's gold nodes, and (decoder, Program). Gold forms are stepped in written order, a topological order."""
    gp = arclog.StudyProgram.from_sexp(spec['gold_sexp'], st)
    ids, model, paths = gp.decode_stream()
    forms = forms_of(run.V, ids, model, paths)
    clause = spec['point'][0]
    roles = gold_roles(ids, forms, clause)
    pool, pg, dec, tmap = Pool(spec['task']), live.Program(), run.root.fork(), {}
    for f in sorted(roles):
        reads = step_form(run, pg, dec, (ids, model, forms), f, tmap)
        pool.take(run, pg, reads, roles[f], None, out)
    toks = [ids[i] for idx in M.atoms_of(paths, ids, model, spec['point']).values() for i in idx if model[i]]
    for t, cols in S.atom_uses(run.V, toks):
        t2 = tmap.get(t, t)
        name, kind = pool.name_of(run, t2), run.V.kind(t2)
        if name is not None:
            types = run.pri['regtypes'].get(name)
            pool.picks.append((name, 'derived' if kind == 'relation' else kind, cols, sorted(map(str, types)) if types else None, len(run.pri['regcols'].get(name, ()))))
    return pool, dec, pg, dict(ancestors=sum(r == 'ancestor' for r in roles.values()), unrelated=sum(r == 'unrelated' for r in roles.values()), clauses=len(forms))


def restore(run, st, state):
    """The pool, decoder and Program that a state file holds."""
    gp = arclog.StudyProgram.from_sexp(state['program'] + OUT_FORMS, st)
    ids, model, paths = gp.decode_stream()
    forms = forms_of(run.V, ids, model, paths)
    pg, dec = live.Program(), run.root.fork()
    for f in sorted(forms)[:-2]:
        step_form(run, pg, dec, (ids, model, forms), f, {})
    pool = Pool(state['task'], state['nodes'], state['clauses'], {int(k): v for k, v in state['slot_node'].items()}, {int(k): v for k, v in state['slot_depth'].items()},
                dict(state['seen']), [tuple(p) for p in state['picks']], state['draws'], state['det_cap_at'])
    run.c[DET_CAP] = int(pool.det_cap_at > 0)
    return pool, dec, pg


def grow(run, pool, dec, pg, target, deadline, show):
    """Draws clauses on dec until the pool holds target nodes or the deadline passes: the decoder after the last kept clause.
    show(n, dec) runs at each kept clause, with n nodes."""
    run.deadline = deadline
    prev = '^'
    while len(pool.nodes) < target and time.monotonic() < deadline:
        ndecl, before = pg.ndecl, pg.before
        kind = run.next_kind(dec, prev, len(pool.clauses))
        pool.draws += 1
        run.c['draws'] += 1
        kept = False
        try:
            f = run.form(pg, dec, kind)
            kept = pool.take(run, pg, run.reads, 'junk', pool.draws, run.out)
        except live.Deadline:
            run.c['drop:deadline'] += 1
        except live.Drop as e:
            run.c['drop:' + str(e)] += 1
        except arclog.Refusal:
            run.c['drop:refused'] += 1
        if run.c[DET_CAP] and not pool.det_cap_at:
            pool.det_cap_at = len(pool.nodes)
        if kept:
            dec, prev = f, kind
            run.c['kept:' + kind] += 1
            show(len(pool.nodes), dec)
            continue
        for s in range(ndecl, pg.ndecl):  # slots that the kept clause after this one takes again
            pg.decl_types.pop(s, None)
            pg.decl_slots.pop(s, None)
            pg.pending.pop(s, None)
            pg.names.pop('&r%d' % s, None)
        pg.ndecl, pg.before = ndecl, before
        for k, j in run.jc.items():
            run.jc[k] = {x: v for x, v in j.items() if v and max(t for t in x if isinstance(t, int)) < run.rel0}
    return dec


def paths_of(out, target, task):
    d = '%s/N%d' % (out, target)
    os.makedirs(d, exist_ok=True)
    return ['%s/%s.%s' % (d, task, x) for x in ('nodes.jsonl.zst', 'rows.jsonl.zst', 'state.json', 'done.json')]


def write_json(path, value):
    tmp = '%s.%d' % (path, os.getpid())
    with open(tmp, 'w') as f:
        json.dump(value, f)
    os.replace(tmp, path)


def state_of(pool, dec, info, spent, n0):
    """What restore reads, and the counts of the size so far."""
    return dict(task=pool.task, program=dec.program_form(), nodes=pool.nodes, clauses=pool.clauses, slot_node=pool.slot_node, slot_depth=pool.slot_depth,
                seen=list(pool.seen.items()), picks=pool.picks, draws=pool.draws, det_cap_at=pool.det_cap_at, info=info, grow_seconds=spent, size_start=n0)


def one_size(sampler, spec, target, before, a, relations, tell):
    """Grows spec's pool to target nodes, from this size's checkpoint, else the size before it, else gold, and writes the size's
    files: its done file once the pool has target nodes. Gives the size's counts and whether it finished."""
    task = spec['task']
    nodes_p, rows_p, state_p, done_p = paths_of(a.out, target, task)
    sess, st = session_of(task, relations)
    t0 = time.monotonic()
    run = PoolRun(sampler.pri, sess, int(digest((a.seed, task, target, time.time_ns()), 8), 16), t0 + a.seconds, live.Limits())
    if a.engine_stats:
        arclog.engine_stats(reset=True, collect=True)
    resume = os.path.exists(state_p)
    if not resume:
        for q in (nodes_p, nodes_p + '.idx.jsonl'):
            if os.path.exists(q):
                os.remove(q)
    with S.JsonlWriter(nodes_p) as out:
        run.out = out
        if resume:
            state = json.load(open(state_p))
            pool, dec, pg = restore(run, st, state)
            info, spent, n0 = state['info'], state['grow_seconds'], state['size_start']
        elif before:
            state = json.load(open(paths_of(a.out, before, task)[2]))
            pool, dec, pg = restore(run, st, state)
            info, spent, n0 = state['info'], 0.0, len(pool.nodes)
        else:
            pool, dec, pg, info = gold_pool(run, spec, st, out)
            info, spent, n0 = dict(info, gold_nodes=len(pool.nodes)), 0.0, len(pool.nodes)
        t1 = time.monotonic()
        tell(task, target, len(pool.nodes), 0, 0.0, 0.0)
        last = [t1, len(pool.nodes), t1]

        def show(n, d):
            now = time.monotonic()
            if n - last[1] >= a.every:
                tell(task, target, n, n - n0, spent + now - t1, (n - last[1]) / max(now - last[0], 1e-9))
                last[:2] = now, n
            if now - last[2] >= a.checkpoint:
                out.flush()
                write_json(state_p, state_of(pool, d, info, spent + now - t1, n0))
                last[2] = now

        dec = grow(run, pool, dec, pg, target, t0 + a.seconds, show)
    spent += time.monotonic() - t1
    for q in (rows_p, rows_p + '.idx.jsonl'):
        if os.path.exists(q):
            os.remove(q)
    with S.JsonlWriter(rows_p) as out:
        rows = 0
        for r in pool.rows(spec, target, a.seed):
            out.write(r)
            rows += 1
    write_json(state_p, state_of(pool, dec, info, spent, n0))
    added = len(pool.nodes) - n0
    done = dict(task=task, target=target, pool_n=len(pool.nodes), rows=rows, added=added, grow_seconds=round(spent, 2), seconds_per_node=round(spent / max(added, 1), 4),
                table_seconds=round(run.table_seconds, 2), parse_seconds=round(run.parse_seconds, 2), draws=pool.draws, relations=relations, declared=pg.ndecl,
                peak_rss_mib=round(rss_mib()), info=dict(info, det_cap_at=pool.det_cap_at), counts=dict(run.c), engine_ms={k: round(v['ns'] / 1e6) for k, v in arclog.engine_stats().items() if v['ns']} if a.engine_stats else None)
    finished = len(pool.nodes) >= target
    write_json(done_p if finished else done_p + '.last', done)
    return done, finished


def points(a):
    """The picked points, kept in points.json: picking reads the whole feature store."""
    p = a.out + '/points.json'
    if os.path.exists(p):
        return json.load(open(p))
    dev = [t for t, s in json.load(open(S.SPLITS)).items() if s == 'dev']
    specs = list(S.pick_groups(a.tasks, dev, {GROUP}, 1))
    for s in specs:
        s['train_path'] = s['point_dir'] + '/train.json'
    os.makedirs(a.out, exist_ok=True)
    write_json(p, specs)
    return specs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=P.SAMPLER_DATA + '/runs/pool1')
    ap.add_argument('--tasks', type=int, default=40)
    ap.add_argument('--large', type=int, default=10, help='tasks that go past the smallest size, in points.json order')
    ap.add_argument('--sizes', default='300,3000')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--seconds', type=float, default=3600, help="one run's budget for a size on a task; at its end the size has a checkpoint and the rows of the pool as it stands")
    ap.add_argument('--checkpoint', type=float, default=300, help='seconds between checkpoints')
    ap.add_argument('--every', type=int, default=25, help='nodes between progress lines')
    ap.add_argument('--only', nargs='*', default=None, help='only these tasks')
    ap.add_argument('--shard', default='0/1', help='K/N: this run takes every Nth size from the Kth, so N runs share the sizes')
    ap.add_argument('--models', default=P.SAMPLER_DATA + '/models')
    ap.add_argument('--engine-stats', action='store_true', help="each size's done file gives the engine's ms per phase (`engine_ms`); the engine's collection of them costs time")
    a = ap.parse_args()
    specs = points(a)
    if a.only:
        specs = [s for s in specs if s['task'] in a.only]
    sizes = sorted(int(x) for x in a.sizes.split(','))
    relations = 2 * sizes[-1] + 512
    jobs = [(s, n, sizes[i - 1] if i else None) for i, n in enumerate(sizes) for s in (specs if not i else specs[:a.large])]
    k, n = map(int, a.shard.split('/'))
    todo = [j for j in jobs if not os.path.exists(paths_of(a.out, j[1], j[0]['task'])[3])][k::n]
    print('%d sizes to do of %d, relations=%d' % (len(todo), len(jobs), relations), flush=True)
    sampler = live.Sampler(a.models)
    t0 = time.monotonic()
    left, done_nodes = sum(n - (b or 0) for _, n, b in todo), [0]

    def tell(task, target, n, added, seconds, window):
        wall = time.monotonic() - t0
        rate = (done_nodes[0] + added) / max(wall, 1e-9)
        eta = '%.0f s' % ((left - done_nodes[0] - added) / rate) if rate else '?'
        print('%s N=%d nodes %d, %.2f nodes/s in the last lot, %.2f on this size, %.2f overall, ETA %s, RSS peak %.0f MiB' % (
            task, target, n, window, added / max(seconds, 1e-9), rate, eta, rss_mib()), flush=True)

    open_sizes = []
    for k, (s, n, before) in enumerate(todo, 1):
        d, finished = one_size(sampler, s, n, before, a, relations, tell)
        done_nodes[0] += d['added']
        if not finished:
            open_sizes.append((s['task'], n))
        print('%d/%d %s N=%d%s: pool_n %d, rows %d, %.3f s/node, tables %.1f s and parsing %.1f s of %.1f s, draws %d' % (
            k, len(todo), s['task'], n, '' if finished else ' (budget ended)', d['pool_n'], d['rows'], d['seconds_per_node'], d['table_seconds'], d['parse_seconds'], d['grow_seconds'], d['draws']), flush=True)
    print('unfinished: %s' % (open_sizes or 'none'), flush=True)


if __name__ == '__main__':
    main()
