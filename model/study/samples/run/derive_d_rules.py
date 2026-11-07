#!/usr/bin/env python
"""derive_d_rules.py OUT_DIR SKELETON TASK... [--targets N] [--order-seconds S] [--shard I/N]

Measures, over the canonical gold paths of every target query of each TRAIN task's skeleton (each distinct target once, in the scope of the first sample that
has it), the statistics that the parameters of the writer's D parts (lookahead_legal.py: UnjoinedAtom, DerivedPort, UnreadPort, OrNesting, OrBranchClose,
AllGuardRead, RigidDetPlain, ZeroBinder and the sets of KindsProposer and KindsComponent) follow from. One JSON line per finished task is appended to
OUT_DIR/shard-<I>.jsonl.zst (one zstd frame per line, so a killed run keeps its finished tasks); a rerun skips each task that any OUT_DIR/*.jsonl.zst holds.
combine_d_rules.py then sums the lines and derives the parameter file that WRITER_TRAIN_STATS names.

A line is {task, targets, orders, sums: {counter: n}, maxes: {name: n}, sets: {name: [..]}, examples: {name: [..]}}. Counters are named in the code below.
"""
import argparse, collections, importlib, json, os, sys, time, types
from pathlib import Path
import numpy as np
import zstandard
import live, live_try, writer, train_rows, order, lookahead_legal as LL
from live import M, ALSO_TOK
from writer import Phase, core_of
from lookahead import body_level

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('skeleton'); ap.add_argument('tasks', nargs='+')
ap.add_argument('--targets', type=int, default=0, help='at most this many distinct targets per task (0: all)')
ap.add_argument('--order-seconds', type=float, default=20.0)
ap.add_argument('--shard', default='0/1')
a = ap.parse_args()
live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
pw = importlib.import_module('points_write')
smp = live.Sampler(str(Path(writer.__file__).resolve().parents[3] / 'models-current'), steers=())
shard, nshard = (int(x) for x in a.shard.split('/'))
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

NOT, CMP, OR = M.NOT, tuple(M.CMP), M.OR
EQ = M.CMP[0]
FACT_NAMES = ('input', 'ex_input', 'ex_output')
STARTS = (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER)


def done_tasks():
    got = set()
    for f in out.glob('*.jsonl.zst'):
        try:
            with open(f, 'rb') as fh:
                text = zstandard.ZstdDecompressor().stream_reader(fh, read_across_frames=True).read().decode()
        except Exception:
            continue
        for line in text.splitlines():
            try:
                got.add(json.loads(line)['task'])
            except Exception:
                pass
    return got


def path_has(path, kind):
    return any(g[1] == kind for g in path)


class Walk:
    """The statistics of one task: fed each (point, token, next point) of each gold path."""

    def __init__(self, run):
        self.run, self.core = run, core_of(run)
        self.sums = collections.Counter()
        self.maxes = collections.defaultdict(int)
        self.sets = collections.defaultdict(set)
        self.examples = collections.defaultdict(list)
        self.stop_parts = [LL.StopEmpty(), LL.StopOneAtom()]
        self.body = None

    def count(self, key, n=1):
        self.sums[key] += n

    def mx(self, key, v):
        if v > self.maxes[key]:
            self.maxes[key] = v

    def ex(self, key, **kw):
        if len(self.examples[key]) < 3:
            self.examples[key].append(kw)

    def name(self, t):
        return self.core.names[int(t)]

    def before(self, pt, n=12):
        return ' '.join(self.name(x) for x in pt.tokens[-n:])

    def atom_cat(self, atom):
        if not atom:
            return 'none'
        if atom[0] in CMP:
            return 'cmp'
        if atom[0] == NOT:
            return 'not'
        nm = self.name(atom[0])
        return 'derived' if nm.startswith('&') else 'fact' if nm in FACT_NAMES else 'lib'

    # ---- a target
    def start_target(self, kind):
        self.kind, self.comp, self.body = kind, None, None
        self.reset_body()

    def reset_body(self):
        self.made = collections.defaultdict(set)   # atom id -> labels it makes
        self.read = collections.defaultdict(set)   # atom id -> labels it reads
        self.atoms = []                            # atom records of the body

    def flush_body(self):
        for r in self.atoms:
            aid = r['aid']
            mine = self.made.get(aid, set())
            shared_prior = bool(self.read.get(aid, set()) - mine)
            later = any(x in self.read[o] for x in mine for o in list(self.read) if o != aid)
            connected = shared_prior or later
            self.count('unj|%s|req%d|js%d|ja%d|ld%d|%s' % (r['ctx'], r['req'], r['js'], r['ja'], int(later), r['cat']))
            if r['ctx'].startswith('top|') and r['n_top'] >= 2:
                self.count('iso|%s|%s|%d' % (r['ctx'].split('|')[1], r['cat'], int(connected)))
        self.reset_body()

    # ---- one step
    def step(self, pt, t, pt2):
        T, T2 = pt.track, pt2.track
        t = int(t)
        if T2.body != T.body or self.body is None:
            self.flush_body()
            self.body = T2.body
        self.kinds(pt, t)
        self.stops(pt, t)
        self.rigid(pt, t)
        self.zero_binder(pt, t)
        self.or_all(pt, t)
        self.port_end(pt, t, pt2)
        if T2.body == T.body and len(T2.texts) == len(T.texts) + 1 and T.atom:  # the token closes the open atom
            self.close_atom(pt, t)
        aid = len(T2.firsts) - 1  # the atom that holds the token makes and reads labels
        i1, i2 = pt.labels.items, pt2.labels.items
        if len(i2) > len(i1):
            for L in i2[len(i1):]:
                self.made[aid].add(L.tok)
        for x, y in zip(i1, i2):
            if len(y.reads) > len(x.reads):
                self.read[aid].add(y.tok)

    # ---- KindsProposer, KindsComponent: what gold uses
    def kinds(self, pt, t):
        T = pt.track
        k = self.core.kind[t]
        if k == 'proposer':
            self.sets['proposers'].add(self.name(t))
        if T.where == 'start' and k == 'component':
            self.comp = self.name(t)
            self.sets['comps'].add(self.comp)
        if self.comp and T.where == 'group' and pt.place.phase == Phase.PORT and not T.form and pt.kind == 'INIT':
            self.sets['comp_ports'].add(self.comp)

    # ---- StopEmpty and StopOneAtom, the parts as they stand
    def stops(self, pt, t):
        ids = pt.ids_
        if t != M.END or not (ids == M.END).any():
            return
        gi = int(np.flatnonzero(ids == t)[0])
        for part in self.stop_parts:
            f = np.asarray(part.factors(pt, ids), np.float64)
            if (f == -np.inf).any():
                self.count('stop|%s|refusing_points' % part.name)
            if f[gi] == -np.inf:
                self.count('stop|%s|gold_removed' % part.name)
                self.ex('stop|' + part.name, kind=pt.kind, tokens=len(pt.tokens), before=self.before(pt))
        if body_level(pt) and pt.kind in ('RULE', 'DET'):
            self.count('stop|ends|' + pt.kind)

    # ---- RIGID_DET parts
    def rigid(self, pt, t):
        T, core = pt.track, self.core
        if pt.kind != 'RIGID_DET' or T.inkey or T.where != 'body' or T.col is not None or T.need or T.rec or pt.place.phase not in STARTS:
            return
        if t == NOT:
            self.count('rd|not')
        elif t == EQ:
            self.count('rd|eq')
        elif t in CMP:
            self.count('rd|cmp_other')
        elif t == OR:
            self.count('rd|or')
        elif t == core.ALL:
            self.count('rd|all')
        elif core.is_rel[t]:
            nm = self.name(t)
            self.count('rd|atoms')
            if nm == 'input':
                self.count('rd|input')
            elif nm in FACT_NAMES:
                self.count('rd|fact_other')
            if not T.negated and any(f[0] == T.path and f[1] == t for f in T.firsts):
                self.count('rd|dup_rel')

    # ---- ZeroBinder: the kinds of value at a (relation, column)
    def zero_binder(self, pt, t):
        T, core = pt.track, self.core
        if pt.place.phase != Phase.VALUE or T.rtok is None or T.rec or not T.atom or not core.is_column[T.atom[-1]]:
            return
        rel = self.name(T.rtok)
        if rel.startswith('&') or rel in FACT_NAMES:
            return
        kind = 'fresh' if t == M.STAR else 'key' if t == M.CARET else 'join' if core.is_label[t] else 'zero' if t == M.ZERO else 'other'
        self.count('zb|%s|%s|%s' % (rel, self.name(T.atom[-1]), kind))

    # ---- OR and ALL
    def or_all(self, pt, t):
        T, core = pt.track, self.core
        path = T.path
        if T.where != 'body':
            return
        if t == OR and LL.flat(T) and pt.place.phase in STARTS:
            ors, in_all, in_branch = LL.or_open(pt)
            self.mx('or|depth', ors + 1)
            self.count('or|total')
            if in_all:
                self.count('or|in_all')
            if ors >= 1:
                self.count('or|nested')
                self.count('or|nested|%s' % ('second_in_branch' if in_branch else 'single'))
        if t == core.ALL and LL.flat(T) and pt.place.phase in STARTS:
            self.count('all|total')
            if path_has(path, 'ALL'):
                self.count('all|in_all')
            if path_has(path, 'OR'):
                self.count('all|in_or')
        st = LL.after_nested(pt)
        if st is not None:
            if t in (ALSO_TOK, M.END):
                self.count('or|after_nested|%s|close' % st)
            else:
                self.count('or|after_nested|%s|continue' % st)
                self.ex('or|after_nested|continue', before=self.before(pt, 10), token=self.name(t), position=st)
        if t in (ALSO_TOK, M.END):
            got = LL.or_close_counts(pt)
            if got is not None:
                missing, unread = got
                self.count('orb|closes')
                self.count('orb|missing|%d' % min(missing, 5))
                self.count('orb|unread|%d' % min(unread, 5))
                self.mx('orb|missing', missing)
                self.mx('orb|unread', unread)
                if missing:
                    self.ex('orb|missing', b=path[-1][2], before=self.before(pt))
                if unread:
                    self.ex('orb|unread', b=path[-1][2], before=self.before(pt))
            elif T.inkey and path and path[-1][1] == 'OR' and path[-1][2] >= 1:
                self.count('orb|key_body_closes')
        if t == M.END and path and path[-1][1] == 'ALL' and path[-1][2] == 1 and LL.flat(T):  # the END that closes an ALL's conclusion
            n = sum(1 for p, _ in T.texts if p == path) + bool(T.atom)
            self.count('all|conclusion_atoms|%d' % min(n, 4))

    # ---- an atom closes
    def close_atom(self, pt, t):
        T, core = pt.track, self.core
        atom, path = T.atom, T.path
        labs = [x for x in atom if core.is_label[x]]
        ja = int(bool(labs))
        js = int(bool(labs) and atom[0] not in CMP)
        mk = int(any(x in (M.STAR, M.CARET) for x in atom))
        port = pt.kind in writer.PORT_KINDS and not T.inkey
        keys = pt.labels.keys(pt) if port else frozenset()
        place = 'port' if port else 'rule' if pt.kind in ('RULE', 'DET') else 'other'
        cls, req = LL.unjoined_ctx(pt)
        cat = self.atom_cat(atom)
        if not path:
            k = T.top + 1
            ctx = 'top|%s|keyed%d|k%s' % (place, int(bool(keys)), '1' if k == 1 else '2+')
        else:
            kd, b = path[-1][1], path[-1][2]
            j = 1 + sum(1 for p, _ in T.texts if p == path)
            if kd == 'OR':
                ctx = 'or|%s|b%s|%s' % (place, '0' if b == 0 else '1+', 'j1' if j == 1 else 'j2+')
            elif kd == 'ALL':
                ctx = 'all|%s' % ('guard1' if b == 0 and j == 1 else 'guard2+' if b == 0 else 'concl')
            else:
                ctx = kd.lower()
        got = LL.all_guard_state(pt, core)
        if got is not None:
            self.count('allg|made%d|reads%d' % got)
            if got[0] and not got[1]:
                self.ex('allg', before=self.before(pt))
        if req:
            self.count('flc|%s|required' % cls)
            if LL.floating(pt, core):
                self.count('flc|%s|floating' % cls)
                self.ex('floating|' + cls, atom=' '.join(self.name(x) for x in atom), before=self.before(pt))
        self.atoms.append(dict(aid=len(T.firsts) - 1, ctx=ctx, req=int(req), js=js, ja=ja, mk=mk, cat=cat, n_top=T.top + 1))
        if req and not js:
            self.ex('unjoined|' + ctx, atom=' '.join(self.name(x) for x in atom), before=self.before(pt))

    # ---- the end of an INIT port body, and its head
    def port_end(self, pt, t, pt2):
        T = pt.track
        if t == M.END and LL.port_end_ctx(pt):
            sc = int(bool(getattr(pt.pg, 'written', None)))  # the scope holds a query, so a derived relation is there to read
            derived = LL.port_reads_derived(pt)
            unread = LL.port_unread(pt)
            comp = self.comp or '?'
            self.count('port|bodies')
            self.count('port|derived|scope%d|%d' % (sc, derived))
            self.count('port|comp|%s|scope%d|derived|%d' % (comp, sc, derived))
            self.count('port|unread_pre|%d' % min(len(unread), 9))
            self.mx('port|unread_pre', len(unread))
            if not derived:
                self.ex('port|no_derived|scope%d' % sc, comp=comp, texts=[x for _, x in T.texts][:4])
        if pt.place.phase == Phase.HEAD and T.where == 'head' and not T.inkey and not T.form and pt.kind == 'INIT' and pt2.track.where != 'head':  # the head ends
            post = len(LL.port_unread(pt2, True))
            self.count('port|unread_post|%d' % min(post, 9))
            self.mx('port|unread_post', post)
            if post > 1:
                self.ex('port|unread_post', before=self.before(pt, 16), post=post)


tasks = a.tasks[shard::nshard]
done = done_tasks()
outfile = open(out / f'shard-{shard}.jsonl.zst', 'ab')
cctx = zstandard.ZstdCompressor(level=6)
for task in tasks:
    if task in done:
        continue
    t0 = time.time()
    try:
        records = [json.loads(x) for x in (Path(a.skeleton) / f'{task}.jsonl').read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        core = writer.core_of(run)
        env = types.SimpleNamespace(live=live, run=run)
        dec_order = train_rows.order_env(run)
    except Exception as e:
        print(task, 'failed to open', type(e).__name__, str(e)[:100], flush=True)
        continue
    W = Walk(run)
    seen, orders = set(), collections.Counter()
    for sample in samples:
        todo = [h for h in sample['target_queries'] if h not in seen]
        if not todo:
            continue
        try:
            texts, label = pw.scope_of(sample['state']['queries'], queries)
            scope = tuple(texts)
            dec0, _ = run.scope(scope)
        except Exception:
            orders['scope failed'] += 1
            continue
        for h in todo:
            if a.targets and len(seen) >= a.targets:
                break
            seen.add(h)
            try:
                kind, stream = pw.query_stream(env, scope, pw.rewrite(queries[h], label, f'&r{len(scope)}'))
                walk, how, why = order.canonical_stream(dec_order, dec0, kind, stream, a.order_seconds)
            except Exception:
                orders['target failed'] += 1
                continue
            orders[how + (':' + why.split(':')[0] if why else '')] += 1
            walk = [int(x) for x in walk]
            if walk and walk[0] == live.KIND_TOK[kind]:
                walk = walk[1:]
            dec, pg = run.scope(scope)
            pg.new = []
            pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
            W.start_target(kind)
            W.count('targets')
            W.count('targets|' + kind)
            try:
                for t in walk:
                    if pt.track.where == 'done':
                        break
                    if t not in pt.ids_:
                        W.count('gold outside the engine mask')
                        break
                    pt2 = writer.step_point(pt, t)
                    W.step(pt, t, pt2)
                    pt = pt2
                W.flush_body()
            except Exception as e:
                W.count('walk error|' + type(e).__name__)
                W.ex('walk error', error=str(e)[:200])
    rec = dict(task=task, targets=len(seen), orders=dict(orders), seconds=round(time.time() - t0, 1), sums=dict(W.sums), maxes=dict(W.maxes),
               sets={k: sorted(v) for k, v in W.sets.items()}, examples={k: v for k, v in W.examples.items()})
    outfile.write(cctx.compress((json.dumps(rec) + '\n').encode()))
    outfile.flush()
    print(task, len(seen), 'targets', dict(orders), '%.0fs' % (time.time() - t0), flush=True)
