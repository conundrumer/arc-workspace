#!/usr/bin/env python
"""The order table: for each form, up to 2K rendered texts of its body in valid orders.

  features_dagc_env.sh 1 features_dagc_orders.py PART [--shard K/N] [--seconds S] [--task T] [--dry]

PART is a form set: held (the 37 held tasks, base gold, K 8), pass1 (the 37 held tasks, the pool gold of view-pass1, K 4: the text that held-pool and held-wide index), dev (the 62 dev tasks, K 2), fit (the 1,011 fit tasks of corpus-v3mix, K 2). init77 is item 15's.
Per form, the orders are every order where the form has at most 256 (features_dag_order.FormDag.all_orders), else the first 256 distinct random orders. Each goes through the engine's check
on the `parents` scope (the scope of seed k for the k-th order, or the draw's seed): a rendered form that StudyProgram.from_sexp(...).decode_stream() accepts is valid. 2K of the accepted orders
are drawn with no repeat by random.Random('pick|<content key>'); law `uniform` (law `cap` where a body passed EXTENSION_CAP, where a random order is a uniform pick among ready items). A form with no accepted
order takes the second tier (law `step`): 8 tries per order wanted, each a uniform pick among the items whose join DAG parents stand and for which atom_binds is not None. A form with none after that is a row of
no-order.tsv and has no row here.
Writes orders-PART-shardKofN.jsonl, one row per form: task, line_id, key, form (the content key), kind, n_orders, tried, accepted, refused, law, k, orders, seconds. A rerun skips the forms of orders-PART-*.jsonl.
"""
import argparse
import collections
import glob
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import features_dagc_lib as L

PATH = re.compile(r'Path\(NodePath\(\[.*?\]\)\)|\bat Places\(\[.*?\]\)|\d+')
DRAWS = 256


def refusal(e: Exception) -> str:
    """The message's first words: its kind and the start of its reason, with no path and no number."""
    text = str(e).replace('\n', ' ')
    head, _, reason = text.partition('): ')
    head = PATH.sub('', head + ')' if reason else head).replace('  ', ' ').strip()
    reason = PATH.sub('', reason or '')
    return ('%s: %s' % (head, ' '.join(reason.split()[:8]))) if reason else ' '.join(head.split()[:10])


def draws(D, dag, n: int):
    """(seed or None, order) pairs: every order once where the count is at most n, else the first n distinct random orders."""
    if dag.n_orders is not None and dag.n_orders <= n:
        for o in dag.all_orders():
            yield None, o
        return
    seen, got = set(), 0
    for s in range(4 * n):
        o = dag.random_order(s)
        key = json.dumps(o, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        got += 1
        yield s, o
        if got >= n:
            return


def outer_labels(D, M, dag):
    """Body path -> the labels of the bodies that enclose it, and for a port the labels of the key groups."""
    parent = {}
    for b in dag.all_bodies:
        for a in b.items:
            for c in a.bodies:
                parent[c.path] = b
    out = {}
    for body in dag.all_bodies:
        outer0, up = set(), parent.get(body.path)
        while up is not None:
            outer0 |= M.atom_labels([a.tree for a in up.items])
            up = parent.get(up.path)
        if body.role.startswith('port') or body.role == 'parts':
            for other in dag.bodies:
                if other.role == 'key':
                    outer0 |= M.atom_labels([a.tree for a in other.items])
        out[body.path] = outer0
    return out


def admitted(D, M, trees, preds, done, bound, outer0):
    """[(item id, labels it binds)] of the items whose DAG parents stand and for which atom_binds is not None."""
    opts = []
    for i in sorted(trees):
        if i in done or not preds[i] <= done:
            continue
        got = M.atom_binds(trees[i], bound, M.atom_labels([trees[j] for j in trees if j != i]) | outer0)
        if got is not None:
            opts.append((i, got))
    return opts


def step_order(D, M, dag, rng):
    """One order by the second tier: per body, a uniform pick among the ready items that atom_binds admits. None on a dead end."""
    out = {}
    outers = outer_labels(D, M, dag)
    for body in dag.all_bodies:
        path, outer0 = body.path, outers[body.path]
        preds = dag.item_preds[path]
        trees = {a.id: D.strip_marks(a.tree) for a in body.items}
        bound, done, order = set(outer0), set(), []
        while len(order) < len(trees):
            opts = admitted(D, M, trees, preds, done, bound, outer0)
            if not opts:
                return None
            i, got = opts[rng.randrange(len(opts))]
            done.add(i)
            order.append(i)
            bound |= got
        out[path] = order
    for a in dag.ors():
        paths = sorted(b.path for b in a.bodies)
        rng.shuffle(paths)
        out['or|' + a.id] = paths
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('part', choices=['held', 'dev', 'fit', 'pass1'])
    ap.add_argument('--out', default=str(L.OUT_DIR))
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--task', default=None)
    ap.add_argument('--limit', type=int, default=None, help='stop after this many forms (a check)')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    shard, shards = map(int, a.shard.split('/'))
    K = L.ORDER_PARTS[a.part]
    import features_dag_order as D
    if a.part == 'fit':
        gold, corpus, models = L.fit_gold(), L.FIT_CORPUS, L.STEER_MODELS
    elif a.part == 'pass1':
        gold, corpus, models = L.pass1_gold(), L.HELD_CORPUS, L.BASE / 'models-base'
    else:
        allg = L.base_gold()
        keep = L.held_tasks() if a.part == 'held' else L.dev_tasks()
        gold, corpus, models = {t: allg[t] for t in keep}, L.HELD_CORPUS, L.BASE / 'models-base'
    L.setup_engine(corpus, models)
    L.check_engine_loaded()
    import live
    import live_try
    import features_dagc_modes as M
    arclog = live.arclog
    code = L.code_hash()
    out_path = Path(a.out) / ('orders-%s-shard%dof%d.jsonl' % (a.part, shard, shards))
    done = set()
    for p in glob.glob(str(Path(a.out) / ('orders-%s-shard*.jsonl' % a.part))) + glob.glob(str(Path(a.out) / ('no-order-%s*.tsv' % a.part))):
        for line in open(p):
            if p.endswith('.jsonl'):
                r = json.loads(line)
                done.add((r['task'], r['line_id']))
            elif line.strip():
                f = line.split('\t')
                done.add((f[0], int(f[1])))
    todo, forms = [], 0
    for t, lines in gold.items():
        if a.task not in (None, t):
            continue
        for i, text in enumerate(lines):
            kind = L.kind_of(text)
            if kind not in L.KINDS or kind not in live.KIND_TOK:
                continue
            forms += 1
            if (forms - 1) % shards == shard and (t, i) not in done:
                todo.append((t, i, kind))
    print('%s: %d forms over all shards, %d to do on shard %d/%d, %d done, K %d, code %s' % (a.part, forms, len(todo), shard, shards, len(done), K, code), flush=True)
    if a.dry:
        return
    t0, n_done, n_checks, tally = time.time(), 0, 0, collections.Counter()
    session, progs = (None, None), {}
    noorder = open(Path(a.out) / ('no-order-%s-shard%dof%d.tsv' % (a.part, shard, shards)), 'a')
    with open(out_path, 'a') as f:
        for w, (t, i, kind) in enumerate(todo, 1):
            if (a.seconds and time.time() - t0 > a.seconds) or (a.limit and n_done >= a.limit):
                print('stopped: budget spent', flush=True)
                break
            t1 = time.time()
            lines = gold[t]
            if session[0] != t:
                session = (t, live_try.session_of(t)[0])
                progs = {}
            sess = session[1]
            text = lines[i]
            dag = D.FormDag(text)
            dag.n_orders = dag.count_orders()
            prog = D.ProgramDag(lines)
            key = D.parse(text)[1]
            parents = prog.ancestors(key)
            scopes: dict[int, list[str]] = {}
            accepted_texts, tried, refused = [], 0, collections.Counter()

            def check(s, order):
                nonlocal tried
                if s not in scopes:
                    scopes[s] = prog.texts(prog.random_order(s, parents))
                target = dag.render(order)
                tried += 1
                try:
                    arclog.StudyProgram.from_sexp('\n'.join((*scopes[s], target, live.READER_OUT)), sess.settings).decode_stream()
                    return target
                except Exception as e:  # noqa: BLE001
                    refused[refusal(e)] += 1
                    return None
            for k, (seed, order) in enumerate(draws(D, dag, DRAWS)):
                got = check(k if seed is None else seed, order)
                if got is not None and got not in accepted_texts:
                    accepted_texts.append(got)
            n_acc = len(accepted_texts)
            law = 'uniform' if dag.n_orders is not None else 'cap'
            chosen = list(accepted_texts)
            random.Random('pick|%s' % prog.content[key]).shuffle(chosen)
            chosen = chosen[:2 * K]
            if not chosen:
                law, rng, seen = 'step', random.Random('step|%s' % prog.content[key]), set()
                for k in range(8 * 2 * K):
                    order = step_order(D, M, dag, rng)
                    if order is None:
                        continue
                    got = check(k, order)
                    if got is not None and got not in seen:
                        seen.add(got)
                        chosen.append(got)
                    if len(chosen) >= 2 * K:
                        break
            n_checks += tried
            sec = round(time.time() - t1, 2)
            if not chosen:
                noorder.write('\t'.join(map(str, (t, i, kind, prog.content[key], dag.n_orders, tried, json.dumps(dict(refused.most_common(3)))))) + '\n')
                noorder.flush()
                tally['no order'] += 1
            else:
                f.write(json.dumps(dict(task=t, line_id=i, key=key, form=prog.content[key], kind=kind, n_orders=dag.n_orders, tried=tried, accepted=n_acc, refused=dict(refused.most_common()),
                                        law=law, k=K, orders=chosen, seconds=sec, code=code)) + '\n')
                f.flush()
            tally[law if chosen else 'none'] += 1
            n_done += 1
            if n_done % 25 == 0 or w == len(todo):
                el = time.time() - t0
                print('[%d/%d %ds %.2f forms/s %.0f checks/s eta %ds] %s' % (w, len(todo), el, n_done / el, n_checks / el, el / n_done * (len(todo) - w), dict(tally)), flush=True)
    print('done: %d forms, %d checks in %.0f s; %s' % (n_done, n_checks, time.time() - t0, dict(tally)), flush=True)


if __name__ == '__main__':
    main()
