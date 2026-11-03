#!/usr/bin/env python
"""Teacher-forced walks of a form in valid orders, one pick row per relation pick.

  features_dagc_env.sh 1 features_dagc_walk.py --part PART --steers off|live [--content] --shard K/N [--seconds S] [--priors-fold TEMPLATE] [--limit N]

Reads points-PART.jsonl and the orders-*.jsonl of the part's gold (features_dagc_orders.py). Each point walks its first K orders (K is 8 on held-parents, 4 on held-pool, 2 elsewhere), and a walk that ends in `bad`, `dead`, `left`, an error or a
misaligned walk is dropped for the next spare order. The walk is or_q.walk of the pin, with the steers `off` (live.Sampler(models, ()): no steer reads any order) or `live` (the steers in use, a comparator that reads lexical order).
Writes walks/PART-STEERS-KofN.jsonl.zst, one zstd frame per walk: its pick rows, then a `form` line (total, parts, drops, seconds). A rerun skips the walks it holds. Prints a rate and an ETA.
A pick row: part, steers, task, line_id, form (the content key), kind, scope_rule, scope_id, order_id, phase, place (top, key, port, outside, branch, all), under, dsize, nsize, d_depth, downset (sorted atom ids), atom (id), nscope, opts
([name, kind, weight, dead by join, own]), rowopts (option_info and rel_dag_fill of the drawer), gold_idx, q_bits, form_atoms, form_not, form_or, and with --content (RULE only) cont and pre. No row holds ord, k, a prefix in walk order, point_group or census ctx.
"""
import argparse
import collections
import glob
import io
import json
import os
import pickle
import sys
import time
from pathlib import Path

import zstandard

import features_dagc_lib as L

PARTS = {  # part -> (orders form set, K, corpus, models, scope_rule)
    'held-parents': ('held', 8, 'held'), 'held-cut': ('held', 2, 'held'), 'dev-cut': ('dev', 2, 'held'), 'held-pool': ('pass1', 4, 'held'), 'held-wide': ('pass1', 2, 'held'),
    'test-parents': ('fit', 2, 'fit'), 'test-cut': ('fit', 2, 'fit'), 'fit-cut': ('fit', 1, 'fit'), 'fit-pool': ('fit', 1, 'fit'), 'parents': ('fit', 2, 'fit'),
}


def short_ids(ids):
    import features_dag_order as D
    return D.short('|'.join(sorted(ids)), 12)


class Env:
    """The engine objects of one process: sampler, session cache, and the Instr drawer that records picks."""

    def __init__(self, source, steers, content, priors_fold):
        if source == 'fit':
            L.setup_engine(L.FIT_CORPUS, L.STEER_MODELS)
        else:
            L.setup_engine(L.HELD_CORPUS, L.BASE / 'models-base')
        L.check_engine_loaded()
        os.environ.setdefault('SAMPLER_CODE', str(L.SAMPLER_CODE))
        import live
        import live_try
        import or_q
        import search
        import search_gold as G
        import sampler_paths as P
        import features_rel_walk as RW
        import features_dag_order as D
        import features_dagc_modes as M
        self.live, self.live_try, self.or_q, self.search, self.G, self.P, self.RW, self.D, self.M = live, live_try, or_q, search, G, P, RW, D, M
        self.content = content
        self.priors_fold = priors_fold
        self.pri = {}
        self.sampler = live.Sampler(G.MODELS, tuple(live.STEERS) if steers == 'live' else ())
        self.cache = {}  # (task, scope_id) -> (tabs, optrows) of the first walk of a form on that scope
        self.depth_cache = {}
        self.canon_progs = {}
        self.CTX = RW.CTX
        env = self
        CTX = self.CTX
        M_ = live.M
        REL_KINDS = ('lib relation', 'relation macro', 'fact relation', 'relation')

        class Instr(or_q.GuidedDrawer):
            """The drawer of or_q.py, with a record of each relation pick (the census's, with the options of rel_walk's snapshot). The record reads the walk and changes nothing in it."""

            def atom(self, fr, k, scope_types=(), key=()):
                CTX['leaf'] = CTX['next']
                CTX['next'] += 1
                res = super().atom(fr, k, scope_types, key)
                if res[0] is not None:
                    CTX['atom_leaf'].append(CTX['leaf'])
                return res

            def pick(self, opts, weights):
                f = sys._getframe(1)
                while f is not None and f.f_code.co_name != 'atom':
                    f = f.f_back
                Lc = f.f_locals
                n = Lc['n']
                rec = None
                if n.phase in ('root', 'root2') and self.force:
                    t0 = time.process_time()
                    rec = self.snapshot(n, Lc, opts, weights)
                    CTX['content_cpu'] += time.process_time() - t0
                o, q = super().pick(opts, weights)
                if rec is not None:
                    rec['q_bits'] = round(or_q.bits(q), 4)
                    CTX['picks'].append(rec)
                return o, q

            def snapshot(self, n, Lc, opts, weights):
                fr, V = self.fr, self.V
                k, key, scope = Lc['k'], Lc['key'], tuple(Lc['scope_types'])
                gold = self.force[0]
                use_content = CTX['content'] and CTX['kind'] == 'RULE'
                if use_content and n.phase == 'root' and not CTX.get('first_done'):
                    CTX['first_done'] = True
                    got = env.cache.get(CTX['cache_key'])
                    if got is None:
                        got = env.RW.option_tables(self, fr, opts)
                        env.cache[CTX['cache_key']] = got
                    CTX['tabs'], CTX['optrows'] = got
                pre = None
                if use_content:
                    if n.phase == 'root':
                        if k > 1:
                            tb, _e = env.RW.S.body_table(fr, *live.TABLES, n.dec, self.pg.before)
                            pre = env.RW.load(tb)
                        CTX['pre'] = pre
                    pre = CTX.get('pre')
                jset = None
                if k > 1:
                    jset = Lc.get('jset')
                    if jset is None:
                        jset = self.joinable(n, opts, scope, key)
                gk = fr.KIND[gold] if gold not in M_.CMP and gold != M_.NOT else ('NOT' if gold == M_.NOT else 'CMP')
                own = gold in key and gk in REL_KINDS
                tot = sum(weights) or 1.0
                row = dict(k=k, phase=n.phase, scope=list(scope), prefix=[], point_group=self.rel_pg, options=[self.option_info(x, round(w / tot, 6)) for x, w in zip(opts, weights)])
                self.rel_dag_fill(row, key)
                canon = CTX['canon']
                rowopts = [dict(tok=o['tok'], kind=o['kind'], p=o['p'], types=o.get('types'), cols=o.get('columns'), dag=o.get('dag'), name=canon(self.prog_names, o['tok']) if o['kind'] == 'derived' else o['tok']) for o in row['options']]
                optl, cont = [], []
                nop = [0.0] * (len(env.RW.C.OPTION) + len(env.RW.C.JOIN))
                for o, w in zip(opts, weights):
                    kd = fr.KIND[o] if o not in M_.CMP and o != M_.NOT else ('NOT' if o == M_.NOT else 'CMP')
                    isrel = kd not in ('NOT', 'CMP')
                    dj = bool(isrel and jset is not None and o not in jset)
                    optl.append([canon(self.prog_names, V.name(o)) if kd == 'relation' else V.name(o), kd, w, dj, o in key])
                    if use_content:
                        if not isrel:
                            cont.append(nop)
                            continue
                        base = CTX['optrows'].get(V.name(o))
                        t = None if base is None else CTX['tabs'].get(V.name(o))
                        base = [0.0] * len(env.RW.C.OPTION) if base is None else base
                        j = env.RW.C.join_row(t, pre)
                        cont.append(base + [round(j[x], 4) for x in env.RW.C.JOIN])
                rec = dict(leaf=CTX['leaf'], phase=n.phase, nscope=len(scope), scope=[str(x) for x in scope], opts=optl, rowopts=rowopts, gold_idx=opts.index(gold) if gold in opts else None, gold_kind=gk, own=own)
                if use_content:
                    p = env.RW.C.prefix_row(pre, CTX['grids'])
                    rec.update(cont=cont, pre=[round(p[x], 4) for x in env.RW.C.PREFIX])
                return rec

        class Run(RW.RunX):
            drawer_class = Instr

        class Guide(or_q.Guide):
            def randrange(self, n):  # the else negation: an atom that the walk takes with no pick
                CTX['else'].append(CTX['next'])
                CTX['next'] += 1
                return super().randrange(n)

        or_q.GuidedRun, or_q.Guide = Run, Guide

    def prior(self, task):
        if not self.priors_fold:
            return
        import live_rows
        fold = live_rows.fold_of(task, live_rows.FOLDS)
        if fold not in self.pri:
            with open(self.priors_fold.format(fold), 'rb') as f:
                self.pri[fold] = pickle.load(f)
        self.sampler.pri = self.pri[fold]

    def walk(self, task, kind, scope, target, scope_id):
        """(q, pick rows, aligned, heads_ok, seconds) of the walk of the target text on the scope. Rows lack the point's fields."""
        D, CTX = self.D, self.CTX
        self.prior(task)
        sess, task_json, _ = self.live_try.session_of(task)
        if task not in self.RW.LIB:
            self.RW.LIB.clear()
            self.cache.clear()
        cp = self.canon_progs.get((task, tuple(scope)))  # one scope id can hold two texts, whose forms have other names
        if cp is None:
            self.canon_progs.clear()
            cp = self.canon_progs[task, tuple(scope)] = D.ProgramDag(list(scope))
        keys_in_order = [cp.content[D.parse(x)[1]] for x in scope]
        named: dict = {}

        def canon(prog_names, slot):
            """A derived option's name without the scope's place. The engine names a form by its first slot (`&r3.0` is the first port of the form whose slots start at 3), so the forms of the scope, in the scope's order,
            take the distinct bases in the order of their numbers. The name is the content key of that form and the port; a base past the scope's forms is the target's own."""
            pname = prog_names.get(slot)
            if pname is None:
                return 'D:?'
            if id(prog_names) not in named:
                named[id(prog_names)] = sorted({n.partition('.')[0] for n in prog_names.values()}, key=lambda b: int(b[2:]) if b[2:].isdigit() else -1)
            bases = named[id(prog_names)]
            base, _, port = pname.partition('.')
            i = bases.index(base) if base in bases else -1
            return 'D:%s%s' % (keys_in_order[i] if 0 <= i < len(keys_in_order) else 'self', '.' + port if port else '')
        CTX.clear()
        CTX.update(canon=canon, next=0, leaf=None, atom_leaf=[], picks=[], content_cpu=0.0, errs=collections.Counter(), task=task, kind=kind, content=self.content, cache_key=(task, scope_id),
                   grids=self.RW.C.grids_of(json.load(open('%s/data/tasks/%s.json' % (self.P.REPO, task)))), **{'else': []})
        t1 = time.time()
        try:
            q = self.or_q.walk(self.sampler, task, kind, [len(scope), 0], list(scope), target, sess, task_json, kind)
        except Exception as e:  # noqa: BLE001
            q = dict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
        sec = round(time.time() - t1, 3)
        dag = D.FormDag(target)
        leaves = dag.leaves(dag.written_order())
        aligned = CTX['next'] == len(leaves)
        heads_ok = None
        if aligned and q.get('atoms') is not None:
            want = [dag.atoms[leaves[i]].tree[0] for i in CTX['atom_leaf']]
            got = [a[1].split()[0].lstrip('(') if isinstance(a[1], str) else '?' for a in q['atoms']]
            heads_ok = len(want) == len(got) and all(w == g or g in ('NOT', w) or w in ('NOT', g) or g.startswith('&') or w.startswith('&') for w, g in zip(want, got))
        return q, list(CTX['picks']), aligned, heads_ok, sec, dag, leaves, dict(CTX['else'] and {'else': list(CTX['else'])} or {}), CTX['content_cpu']


def place_of(dag, body):
    top = body.path.split('/')[0]
    root = next(b for b in dag.bodies if b.path == top)
    if body is not root:
        return 'branch' if body.role == 'branch' else 'all' if body.role in ('guard', 'conclusion') else 'outside'
    return 'top' if body.role == 'top' else 'key' if body.role == 'key' else 'port' if body.role.startswith('port:') else 'outside'


def pick_rows(env, point, part, steers, order_text, order_id, scope_id, q, picks, dag, leaves):
    D, M = env.D, env.M
    leaf_body = {x.id: b for b in dag.all_bodies for a in b.items for x in a.leaves()}
    n_not = sum(a.kind == 'not' for a in dag.atoms.values())
    n_or = sum(1 for _ in dag.ors())
    out = []
    for p in picks:
        if p['leaf'] >= len(leaves):
            continue
        atom = leaves[p['leaf']]
        down = leaves[:p['leaf']]
        key = (id(dag), frozenset(down))
        if key not in env.depth_cache:
            env.depth_cache[key] = M.mode_rounds([D.strip_marks(dag.atoms[i].tree) for i in down])
        body = leaf_body[atom]
        a = dag.atoms[atom]
        under = sorted(({'or'} if '/or' in body.path else set()) | ({'all'} if '/all' in body.path else set()) | ({'not'} if a.kind == 'not' else set()))
        row = dict(rec='pick', part=part, steers=steers, task=point['task'], line_id=point['line_id'], form=point.get('form_key') or point['form'], kind=point['kind'], scope_rule=point.get('scope_rule') or ('wide' if 'wide' in part else 'pool' if 'pool' in part else part), scope_id=scope_id,
                   order_id=order_id, phase=p['phase'], place=place_of(dag, body), under=under, dsize=len(down), nsize=len(leaves), d_depth=env.depth_cache[key], downset=sorted(down), atom=atom, nscope=p['nscope'],
                   opts=p['opts'], rowopts=p['rowopts'], gold_idx=p['gold_idx'], q_bits=p['q_bits'], form_atoms=len(leaves), form_not=n_not, form_or=n_or)
        row['scope'] = p['scope']
        if 'cont' in p:
            row.update(cont=p['cont'], pre=p['pre'])
        out.append(row)
    return out


def load_orders(source):
    out = {}
    for p in sorted(glob.glob(str(L.OUT_DIR / ('orders-%s-shard*.jsonl' % source)))):
        for line in open(p):
            r = json.loads(line)
            out[r['task'], r['line_id']] = r
    return out


def held_frames(path):
    """{(point line, order index) -> ok} of the walks that the file holds."""
    got = {}
    if os.path.exists(path):
        try:
            with open(path, 'rb') as f:
                for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                    if line.startswith('{"rec": "form"'):
                        d = json.loads(line)
                        got[d['point'], d['order_idx']] = d['ok']
        except zstandard.ZstdError:
            pass
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--part', required=True, choices=sorted(PARTS))
    ap.add_argument('--steers', required=True, choices=['off', 'live'])
    ap.add_argument('--content', action='store_true')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--priors-fold', default='')
    ap.add_argument('--limit', type=int, default=None, help='stop after this many walks')
    ap.add_argument('--out', default=str(L.OUT_DIR / 'walks'))
    ap.add_argument('--points', default=None)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    shard, shards = map(int, a.shard.split('/'))
    source, K, corpus = PARTS[a.part]
    points_path = a.points or str(L.OUT_DIR / ('points-%s.jsonl' % a.part))
    points = [json.loads(x) for x in open(points_path)]
    if a.part == 'fit-cut':
        points = [p for p in points if p['target_seed'] == 0]  # one seed and one order per form: these two parts past their time
    orders = load_orders(source)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, '%s-%s-%dof%d.jsonl.zst' % (a.part, a.steers, shard, shards))
    tasks = sorted({p['task'] for p in points})
    keep = {t for j, t in enumerate(tasks) if j % shards == shard}  # a shard holds whole tasks, as rel_walk does
    todo = [p for p in points if p['task'] in keep]
    held = held_frames(path)
    print('%s %s: %d points over all shards, %d in shard %d/%d, %d walks held, K %d, orders %d forms' % (a.part, a.steers, len(points), len(todo), shard, shards, len(held), K, len(orders)), flush=True)
    if a.dry:
        return
    env = Env('fit' if corpus == 'fit' else 'held', a.steers, a.content, a.priors_fold)
    import features_dag_order as D
    cz = zstandard.ZstdCompressor(level=6)
    t0, walked, drops, drop_msgs = time.time(), 0, 0, collections.Counter()
    progs = {}
    # an estimate for the ETA: the number of walks still wanted
    want = 0
    for p in todo:
        r = orders.get((p['task'], p['line_id']))
        n_ok = sum(1 for i in range(len(r['orders'])) if held.get((p['line'], i))) if r else 0
        want += max(0, min(K, len(r['orders'])) - n_ok) if r else 0
    print('%d walks to do' % want, flush=True)
    with open(path, 'ab') as out:
        for p in todo:
            if (a.seconds and time.time() - t0 > a.seconds) or (a.limit and walked >= a.limit):
                print('stopped: budget spent', flush=True)
                break
            r = orders.get((p['task'], p['line_id']))
            if r is None:
                continue  # a form in no-order.tsv has no rows in any arm
            n_ok = sum(1 for i in range(len(r['orders'])) if held.get((p['line'], i)))
            for i, text in enumerate(r['orders']):
                if n_ok >= K:
                    break
                if (p['line'], i) in held:
                    continue
                if a.seconds and time.time() - t0 > a.seconds:
                    break
                if p['task'] not in progs:
                    progs.clear()
                    progs[p['task']] = None
                scope = p['scope']
                scope_id = p.get('scope_id') or D.short(''.join(sorted(D.ProgramDag(scope).content.values())), 16)
                q, picks, aligned, heads_ok, sec, dag, leaves, extra, ccpu = env.walk(p['task'], p['kind'], scope, text, scope_id)
                why = q.get('error') or (q.get('bad') or [''])[0] if (q.get('error') or q.get('bad')) else q.get('dead') or ('left %d' % q['left'] if q.get('left') else None) or (None if aligned else 'misaligned') or (None if heads_ok is not False else 'heads differ')
                ok = why is None
                order_id = D.short('|'.join(leaves), 12)
                rows = pick_rows(env, p, a.part, a.steers, text, order_id, scope_id, q, picks, dag, leaves) if ok else []
                msg = ' '.join(str(why).split()[:6]) if why else None
                form = dict(rec='form', part=a.part, steers=a.steers, point=p['line'], order_idx=i, task=p['task'], line_id=p['line_id'], kind=p['kind'], form=p.get('form_key') or p['form'], order_id=order_id, ok=ok,
                            drop=msg, total=q.get('total'), parts=q.get('parts'), seconds=sec, content_cpu=round(ccpu, 3), picks=len(picks), aligned=aligned, heads_ok=heads_ok, nscope=len(scope), scope_id=scope_id)
                out.write(cz.compress(('\n'.join(json.dumps(x) for x in [*rows, form]) + '\n').encode()))
                out.flush()
                held[p['line'], i] = ok
                walked += 1
                if ok:
                    n_ok += 1
                else:
                    drops += 1
                    drop_msgs[msg] += 1
                if walked % 25 == 0:
                    el = time.time() - t0
                    print('[%d/%d %.0fs %.2f walks/s eta %.0fs] drops %d %s' % (walked, want, el, walked / el, el / walked * max(0, want - walked), drops, dict(drop_msgs.most_common(3))), flush=True)
    el = time.time() - t0
    print('done: %d walks in %.0f s (%.2f walks/s), %d dropped %s' % (walked, el, walked / max(el, 1e-9), drops, dict(drop_msgs)), flush=True)


if __name__ == '__main__':
    main()
