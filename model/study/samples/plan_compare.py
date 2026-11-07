"""The comparison of the two writer plans on dev samples (docs/sample-build/training-instances.md, "Comparison of the plans").

  python3 plan_compare.py SET --plan ordered|unordered --model FILE [--shard k/N] [--tasks T,T,...] [--samples-per-task K] [--seed S] [--steps N] [--sample-seconds X] [--out DIR]
  python3 plan_compare.py SET --plan ordered|unordered --model FILE --report

SET is ramp, 37 or training. FILE is the booster file that fit_trees.py wrote for the plan. Run it as points_write.py runs: the runtime python, PYTHONPATH with the extractor's folder
and the engine wheel's site folder, ARCLOG_IDENT_SOURCE=value. It measures dev tasks only (task splits come from OUTD/split.tsv, and a task that is not dev is not opened;
--include-train adds train tasks, for a pipeline check). A held-out task is never read.

The samples, the scope and `uses` are those of points_write.py. The tree scores the ids that the decoder's mask admits at each writing point (no lookahead factor), as
tree_dist.TreeDistribution does for serving, on the features of writer.Features. A query is written one kind at a time (the kind token is not a choice of the tree), so a
sample's values are computed for each kind that has targets, and the sample's value is the mean over those kinds (the values of each kind are in the record).

Values of a kind (the targets are the sample's distinct QueryHash values of that kind):
- v1: the sum over the targets of the chance of writing that query, summed over every path that writes it under the plan.
    - ordered: a query has one path, its canonical stream (order.canonical_stream; the stream as given where the rule gives none). The chance is the product of the tree's
      probabilities along it. A path of another order that writes the same query is not a path of the plan, and its chance is not counted.
    - unordered: paths are merged into the states of the extractor's search (order.set_key), and the chance of the states is carried forward over the search graph in topological
      order, summing at merges. The tree is evaluated once for a state, at the point of the state's first visit, as the training instances are. The graph follows only the tokens that
      continue some target's item set (the extractor's positives); the other tokens lead to queries that are no target. The sum is exact over that graph. --check also
      enumerates the paths one by one and compares.
- v2: whether the most probable completed query is a target. A completed query's chance is the sum over every path that writes it under the plan. v2 is a bound pair (v2_lo,
  v2_hi) and v2_found (the answer among the queries found), and the record says whether the answer is decided.
    - ordered: exact where the search finishes. The search is best-first on the probability of a path, which only falls along a path, so when the best path in hand that is
      a query's own path has the probability of the best path still to explore or more, no other query can beat it. A completed path counts when it is the canonical stream
      of its query. The search stops when the best unexplored path is no better than the best target, or after --steps steps (then the pair is the bound).
    - unordered: approximate, with a bound. A best-first search over states (merged by set_key; a prefix that set_key cannot read is a state of its own, merged with none)
      steps the unexplored edge of most chance first, from the extractor's graph. After the search the chance of each found completed query is exact over the graph found (a
      lower bound of its true chance), and U is the chance that sits on edges not stepped. A target's chance is taken as exact over the extractor's graph (every path that writes
      a target is an order of its item set). A non-target query's true chance is at most its found chance plus U. The answer is decided as target where the best found target
      beats the best found other query plus U, and as other where the best found other query beats the best found target. Else it is undecided, and v2_lo counts it as not a
      target and v2_hi as a target. v2_found is the answer among the queries found.

The result of a sample is one line of OUT/SET/plan_compare/PLAN/TAG/<task>.jsonl, written when the sample is made; a restart skips the samples that the file has. TAG is the
first 8 digits of the model file's sha256 unless --tag is given.
"""
import argparse
import hashlib
import heapq
import importlib
import itertools
import json
import math
import os
import sys
import time
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from points_write import OUTD, Reject, chosen, file_sha, module_file, rewrite, scope_of, why

ERR = '!'  # the kid of an edge whose step raised
NEG_INF = float('-inf')


@dataclass
class Target:
    hash: int
    text: str
    stream: list[int]


@dataclass
class Ctx:
    live: Any
    wr: Any
    tr: Any
    order: Any
    dist: Any
    uses: tuple[str, ...]
    args: argparse.Namespace
    run: Any = None
    scope: tuple[str, ...] = ()
    evals: int = 0  # tree evaluations of the sample


# ---------------------------------------------------------------- the tree at a writing point

def probs_at(ctx: Ctx, pt: Any) -> tuple[np.ndarray, np.ndarray]:
    """(ids, probabilities): the softmax of the tree's raw scores over the ids of the mask at `pt`."""
    ids = pt.ids_
    if len(ids) <= 1:
        return ids, np.ones(len(ids))
    ctx.evals += 1
    z = ctx.dist.logits(pt, ids, ctx.wr.Features(pt, ids))
    z = z - z.max()
    p = np.exp(z)
    p /= p.sum()
    return ids, p


def flow(adj: dict[str, list[tuple[str, float]]], root: str) -> dict[str, float]:
    """The chance that reaches each node from the root, carried forward in topological order and summed at merges. adj maps every node to its (child, probability) list."""
    indeg = dict.fromkeys(adj, 0)
    for outs in adj.values():
        for c, _ in outs:
            indeg[c] += 1
    mass = dict.fromkeys(adj, 0.0)
    mass[root] = 1.0
    queue = [k for k, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        k = queue.pop()
        seen += 1
        m = mass[k]
        for c, p in adj[k]:
            mass[c] += m * p
            indeg[c] -= 1
            if indeg[c] == 0:
                queue.append(c)
    if seen != len(adj):
        raise RuntimeError('the state graph has a cycle')
    return mass


# ---------------------------------------------------------------- targets

def decode_targets(ctx: Ctx, sample: dict, queries: dict[str, dict], scope: tuple[str, ...], label: dict[str, str], failures: Counter[str]) -> dict[str, list[Target]]:
    """The sample's distinct targets by kind, as points_write.process_sample reads them."""
    live, run = ctx.live, ctx.run
    out: dict[str, list[Target]] = {}
    seen: set[int] = set()
    for h in sample['target_queries']:
        try:
            hv = int(h, 16)
            if hv in seen:
                continue
            q = queries[h]
            text = rewrite(q, label, f'&r{len(scope)}')
            ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), run.session.settings).decode_stream()
            stream = [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
            kind = run.V.name(stream[0])
            if kind not in live.KIND_TOK:
                raise Reject(f'the kind {kind} is not written')
            if kind != q['kind']:
                raise Reject('the stream\'s kind differs from the query\'s kind')
        except Reject as e:
            failures[str(e)] += 1
            continue
        except Exception as e:
            failures['decode: ' + why(e)] += 1
            continue
        seen.add(hv)
        out.setdefault(kind, []).append(Target(hv, text, stream))
    return out


# ---------------------------------------------------------------- the ordered plan

def ordered_kind(ctx: Ctx, scope: tuple[str, ...], kind: str, targets: list[Target]) -> dict:
    run, wr, order, a = ctx.run, ctx.wr, ctx.order, ctx.args
    dec0, pg = run.scope(scope)
    pg.new = []
    start = wr.start_point(run, pg, run.open_form(pg, dec0, kind), kind)
    env = ctx.tr.order_env(run)
    cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

    def probs(pt: Any) -> tuple[np.ndarray, np.ndarray]:
        got = cache.get(pt.tokens)
        if got is None:
            got = cache[pt.tokens] = probs_at(ctx, pt)
        return got

    res: dict[str, Any] = dict(kind=kind, targets=len(targets))
    orders: Counter[str] = Counter()
    mass: dict[int, float] = {}  # target hash -> chance of its path
    problems: Counter[str] = Counter()
    t0 = time.perf_counter()
    for tg in targets:
        stream, o, _why = order.canonical_stream(env, dec0, kind, tg.stream, a.seconds)
        orders[o] += 1
        pt, logp, bad = start, 0.0, ''
        for t in stream:
            if pt.track.where == 'done':
                bad = 'the stream goes on past the end'
                break
            ids, p = probs(pt)
            j = np.flatnonzero(ids == t)
            if len(j) == 0:
                bad = 'left the mask'
                break
            logp += math.log(p[j[0]]) if p[j[0]] > 0 else NEG_INF
            pt = wr.step_point(pt, int(t))
        if not bad and pt.track.where != 'done':
            bad = 'the stream ends before the end of the query'
        if bad:
            problems[bad] += 1
            mass[tg.hash] = 0.0
        else:
            mass[tg.hash] = math.exp(logp)
    res['order'] = dict(orders)
    res['problems'] = dict(problems)
    res['v1'] = sum(mass.values())
    res['v1_by_target'] = {format(h, '032x'): m for h, m in mass.items()}
    res['seconds_v1'] = round(time.perf_counter() - t0, 3)
    # v2: best-first on the probability of a path
    t1 = time.perf_counter()
    target_hashes = set(mass)
    best_t = max(mass.values(), default=0.0)
    log_t = math.log(best_t) if best_t > 0 else NEG_INF
    heap: list[tuple[float, int, Any, int]] = []
    counter = itertools.count()
    lost = NEG_INF  # the best probability on an edge that raised

    def expand(pt: Any, logp: float) -> None:
        ids, p = probs(pt)
        for t, q in zip(ids.tolist(), p.tolist()):
            if q > 0:
                heapq.heappush(heap, (-(logp + math.log(q)), next(counter), pt, t))
    expand(start, 0.0)
    best_o, steps, completed, counted, other_order = NEG_INF, 0, 0, 0, 0
    errors: Counter[str] = Counter()
    over = ''
    while heap:
        top = max(-heap[0][0], lost)
        if top <= max(log_t, best_o) + 1e-9:
            break
        if steps >= a.steps:
            over = 'steps'
            break
        if time.perf_counter() - t1 > a.sample_seconds:
            over = 'seconds'
            break
        neg, _, pt, t = heapq.heappop(heap)
        steps += 1
        logp = -neg
        try:
            child = wr.step_point(pt, t)
        except Exception as e:
            errors[why(e)] += 1
            lost = max(lost, logp)
            continue
        if child.track.where == 'done':
            completed += 1
            if wr.query_hash(child.dec) in target_hashes:
                continue
            path = [int(x) for x in child.tokens[1:]]
            try:
                s, o, _why = order.canonical_stream(env, dec0, kind, path, a.seconds)
            except Exception as e:
                errors[why(e)] += 1
                continue
            if o == 'canonical' and [int(x) for x in s] != path:
                continue
            counted += 1
            other_order += o != 'canonical'
            best_o = max(best_o, logp)
            continue
        expand(child, logp)
    top = max(-heap[0][0], lost) if heap else lost
    if over and top <= max(log_t, best_o) + 1e-9:
        over = ''
    other = math.exp(best_o) if best_o > NEG_INF else 0.0
    rest = math.exp(top) if top > NEG_INF else 0.0  # no path still to explore has more than this
    found = best_t > other
    if over:
        lo = best_t > max(other, rest)
        hi = best_t > 0 and not other > best_t
    else:
        lo = hi = found
    res.update(v2_found=found, v2_lo=lo, v2_hi=hi, decided=lo == hi, over=over, best_target=best_t, best_other=other, unexplored_top=rest, steps=steps,
               completed=completed, counted=counted, other_without_rule=other_order, step_errors=dict(errors), evals=ctx.evals, seconds_v2=round(time.perf_counter() - t1, 3))
    return res


def check_ordered(ctx: Ctx, scope: tuple[str, ...], kind: str, targets: list[Target], res: dict) -> dict:
    """v1 again, from the extractor's own records of the ordered plan (train_rows.points_of_targets), scored on the booster directly."""
    dist = ctx.dist
    stats: Counter[str] = Counter()
    logs: defaultdict[int, float] = defaultdict(float)
    bad: set[int] = set()
    memo: dict[int, np.ndarray] = {}
    held: list[Any] = []
    for ti, rec in ctx.tr.points_of_targets(ctx.run, scope, kind, [t.stream for t in targets], ctx.uses, plan='ordered', seconds=ctx.args.seconds, stats=stats):
        if 'error' in rec or rec['left_mask']:
            bad.add(ti)
            continue
        if rec['next_id'] is None:
            continue
        ids = rec['ids']
        lp = memo.get(id(rec['option']))
        if lp is None:
            rows = np.empty((len(ids), len(ctx.uses)), np.float32)
            rows[:, dist.option_at] = rec['option']
            rows[:, dist.point_at] = rec['point']
            z = np.asarray(dist.booster.predict(rows, raw_score=True), np.float64).reshape(len(ids))
            z = z - z.max()
            lp = z - math.log(np.exp(z).sum())
            memo[id(rec['option'])] = lp
            held.append(rec['option'])
        logs[ti] += float(lp[int(np.flatnonzero(ids == rec['next_id'])[0])])
    alt = sum(math.exp(logs[i]) for i in range(len(targets)) if i not in bad)
    return dict(v1_records=alt, v1_difference=alt - res['v1'])


# ---------------------------------------------------------------- the unordered plan

@dataclass
class Node:
    pt: Any
    hash: int | None  # the QueryHash of a completed query
    ids: list[int]
    p: list[float]
    kids: dict[int, str] = field(default_factory=dict)  # token -> key of the state after it (ERR where the step raised); a token that is not here is not stepped
    est: float = 0.0  # the chance that took the first path to this node, to order the search


def build_walkers(ctx: Ctx, dec: Any, kind: str, targets: list[Target], errors: Counter[str]) -> dict[int, Any]:
    env = ctx.tr.order_env(ctx.run)
    walkers: dict[int, Any] = {}
    for i, tg in enumerate(targets):
        try:
            q = ctx.order.query_of(env, dec, kind, [int(t) for t in tg.stream])
            if q.unsupported:
                raise ValueError('unsupported: ' + q.unsupported)
            w = ctx.order.Unordered(env, q, seconds=ctx.args.seconds)
            if not w.ok:
                raise ValueError('no order of the items is written')
            w.gold_hash = q.gold_hash
            walkers[i] = w
        except Exception as e:
            errors[why(e)] += 1
    return walkers


def adjacency(nodes: dict[str, Node]) -> dict[str, list[tuple[str, float]]]:
    adj: dict[str, list[tuple[str, float]]] = {}
    for k, n in nodes.items():
        outs = []
        for t, pr in zip(n.ids, n.p):
            c = n.kids.get(t)
            if c is not None and c != ERR and c in nodes:
                outs.append((c, pr))
        adj[k] = outs
    return adj


def decide(nodes: dict[str, Node], root: str, target_hashes: set[int]) -> dict:
    """Chances over the graph found so far: the found chance of each completed query, U (the chance on edges not stepped), and the answer."""
    mass = flow(adjacency(nodes), root)
    by_hash: defaultdict[int, float] = defaultdict(float)
    unexplored, dead = 0.0, 0.0
    for k, n in nodes.items():
        m = mass[k]
        if n.hash is not None:
            by_hash[n.hash] += m
        elif not n.ids:
            dead += m
        else:
            unexplored += m * sum(pr for t, pr in zip(n.ids, n.p) if n.kids.get(t) in (None, ERR))
    best_t = max((m for h, m in by_hash.items() if h in target_hashes), default=0.0)
    best_o = max((m for h, m in by_hash.items() if h not in target_hashes), default=0.0)
    return dict(by_hash=by_hash, best_target=best_t, best_other=best_o, unexplored=unexplored, dead=dead, found=best_t > best_o,
                lo=best_t > best_o + unexplored, hi=best_t > 0 and not best_o > best_t)


def unordered_kind(ctx: Ctx, scope: tuple[str, ...], kind: str, targets: list[Target], check: bool) -> dict:
    run, wr, order, a = ctx.run, ctx.wr, ctx.order, ctx.args
    dec, pg = run.scope(scope)
    pg.new = []
    res: dict[str, Any] = dict(kind=kind, targets=len(targets))
    target_hashes = {t.hash for t in targets}
    t0 = time.perf_counter()
    werr: Counter[str] = Counter()
    walkers = build_walkers(ctx, dec, kind, targets, werr)
    res['walker_errors'] = dict(werr)
    if not walkers:
        res['error'] = 'no target can be searched'
        return res
    res['gold_hash_not_a_target'] = sum(w.gold_hash not in target_hashes for w in walkers.values())
    stats: Counter[str] = Counter()
    nodes: dict[str, Node] = {}
    edges: dict[str, list[tuple[int, str]]] = {}
    state_errors = 0
    for ev in ctx.tr._unordered_states(run, pg, dec, kind, walkers, stats):
        if 'error' in ev:
            state_errors += 1
            continue
        if len(nodes) >= a.max_states:
            res['error'] = f'the search has more than {a.max_states} states'
            return res
        pt, k = ev['pt'], ev['key']
        if 'nexts' not in ev:
            nodes[k] = Node(pt, wr.query_hash(pt.dec), [], [])
            edges[k] = []
        else:
            ids, p = probs_at(ctx, pt)
            nodes[k] = Node(pt, None, ids.tolist(), p.tolist())
            edges[k] = ev['edges']
    if not nodes:
        res['error'] = 'no state'
        return res
    root = min(nodes, key=lambda k: len(nodes[k].pt.tokens))
    for k, es in edges.items():
        nodes[k].kids = {t: c for t, c in es}
    # v1: the chance over the graph of the targets' item sets
    adj = adjacency(nodes)
    mass = flow(adj, root)
    done: defaultdict[int, float] = defaultdict(float)
    for k, n in nodes.items():
        if n.hash is not None:
            done[n.hash] += mass[k]
        n.est = mass[k]
    res['v1'] = sum(m for h, m in done.items() if h in target_hashes)
    res['v1_by_target'] = {format(t.hash, '032x'): done.get(t.hash, 0.0) for t in targets}
    res['v1_other_ends'] = sum(m for h, m in done.items() if h not in target_hashes)
    res['states'] = len(nodes)
    res['search'] = dict(stats)
    res['state_errors'] = state_errors
    res['seconds_v1'] = round(time.perf_counter() - t0, 3)
    if check:
        res.update(check_unordered(ctx, dec, pg, kind, walkers, nodes, adj, root, target_hashes, res['v1']))
    # v2: best-first over the states, from the graph above
    t1 = time.perf_counter()
    heap: list[tuple[float, int, str, int]] = []
    counter = itertools.count()
    for k, n in nodes.items():
        for t, pr in zip(n.ids, n.p):
            if t not in n.kids and pr > 0 and n.est > 0:
                heapq.heappush(heap, (-(n.est * pr), next(counter), k, t))
    steps, merges, over = 0, 0, ''
    errors: Counter[str] = Counter()
    keyless: Counter[str] = Counter()
    next_check = 200
    verdict = decide(nodes, root, target_hashes)
    while heap and verdict['lo'] != verdict['hi']:
        if steps >= a.steps:
            over = 'steps'
            break
        if time.perf_counter() - t1 > a.sample_seconds:
            over = 'seconds'
            break
        neg, _, k, t = heapq.heappop(heap)
        node = nodes[k]
        steps += 1
        try:
            child = wr.step_point(node.pt, t)
        except Exception as e:
            node.kids[t] = ERR
            errors[why(e)] += 1
            continue
        try:
            ck = order.set_key(child)
        except Exception as e:  # the key reader does not read this prefix: the state is its path, and it merges with none
            ck = 'T:' + ','.join(map(str, child.tokens))
            keyless[why(e)] += 1
        node.kids[t] = ck
        if ck in nodes:
            merges += 1
        else:
            if child.track.where == 'done':
                nodes[ck] = Node(child, wr.query_hash(child.dec), [], [], est=-neg)
            else:
                ids, p = probs_at(ctx, child)
                nn = nodes[ck] = Node(child, None, ids.tolist(), p.tolist(), est=-neg)
                for tt, pr in zip(nn.ids, nn.p):
                    if pr > 0:
                        heapq.heappush(heap, (neg * pr, next(counter), ck, tt))
        if steps >= next_check:
            next_check *= 2
            verdict = decide(nodes, root, target_hashes)
    verdict = decide(nodes, root, target_hashes)
    res.update(v2_found=verdict['found'], v2_lo=verdict['lo'], v2_hi=verdict['hi'], decided=verdict['lo'] == verdict['hi'],
               over=over, best_target=verdict['best_target'], best_other=verdict['best_other'], unexplored=verdict['unexplored'], dead=verdict['dead'],
               steps=steps, merges=merges, step_errors=dict(errors), keyless=dict(keyless), nodes=len(nodes), evals=ctx.evals, seconds_v2=round(time.perf_counter() - t1, 3))
    return res


def check_unordered(ctx: Ctx, dec: Any, pg: Any, kind: str, walkers: dict[int, Any], nodes: dict[str, Node], adj: dict[str, list[tuple[str, float]]], root: str,
                    target_hashes: set[int], v1: float) -> dict:
    """v1 again, by enumerating the paths one by one with no merging, at each path's own point. The graph's path count (every edge weighs 1) must equal the count of the paths
    that end at a target's QueryHash. The two chances differ where the tree's probabilities at the points of one state differ (the features of a point depend on its path)."""
    wr, order = ctx.wr, ctx.order
    cap = ctx.args.check_paths
    graph = flow({k: [(c, 1.0) for c, _ in outs] for k, outs in adj.items()}, root)
    graph_paths = sum(m for k, m in graph.items() if nodes[k].hash in target_hashes)
    start = wr.start_point(ctx.run, pg, ctx.run.open_form(pg, dec, kind), kind)
    stack = [(start, {i: w.start() for i, w in walkers.items()}, 1.0)]
    paths, own, visited, differ, other_ends = 0, 0.0, 0, 0, 0
    while stack:
        pt, cfgs, po = stack.pop()
        visited += 1
        if visited > 10 * cap:
            return dict(check='more than %d points' % (10 * cap), graph_paths=graph_paths)
        if pt.track.where == 'done':
            if wr.query_hash(pt.dec) in target_hashes:
                paths += 1
                own += po
                if paths > cap:
                    return dict(check='more than %d paths' % cap, graph_paths=graph_paths)
            else:
                other_ends += 1
            continue
        ids, p_own = probs_at(ctx, pt)
        st = nodes[order.set_key(pt)]
        differ += len(st.p) != len(p_own) or not np.allclose(np.sort(p_own), np.sort(np.asarray(st.p)), rtol=1e-6, atol=1e-12)
        own_of = dict(zip(ids.tolist(), p_own.tolist()))
        idset = set(own_of)
        nexts = {i: walkers[i].nexts(c) for i, c in cfgs.items()}
        positive = sorted(set().union(*nexts.values()) & idset)
        for t in positive:
            cc = {}
            for i, c in cfgs.items():
                if t in nexts[i]:
                    n = walkers[i].step(c, t)
                    if n:
                        cc[i] = n
            stack.append((wr.step_point(pt, t), cc, po * own_of[t]))
    return dict(check='paths', graph_paths=graph_paths, paths=paths, paths_other_ends=other_ends, v1_paths=own, v1_paths_minus_graph=own - v1, points_visited=visited,
                points_whose_probs_differ_from_state=differ)


# ---------------------------------------------------------------- one sample

def process_sample(ctx: Ctx, sample: dict, queries: dict[str, dict], check: bool) -> dict:
    t0 = time.perf_counter()
    ctx.evals = 0
    texts, label = scope_of(sample['state']['queries'], queries)
    scope = tuple(texts)
    ctx.scope = scope
    try:
        ctx.run.scope(scope)
    except Exception as e:
        raise Reject('the engine refused the scope: ' + why(e)) from e
    failures: Counter[str] = Counter()
    by_kind = decode_targets(ctx, sample, queries, scope, label, failures)
    kinds: dict[str, dict] = {}
    for kind, targets in by_kind.items():
        try:
            if ctx.args.plan == 'ordered':
                r = ordered_kind(ctx, scope, kind, targets)
                if check:
                    r.update(check_ordered(ctx, scope, kind, targets, r))
            else:
                r = unordered_kind(ctx, scope, kind, targets, check)
        except Exception as e:
            r = dict(kind=kind, targets=len(targets), error='error: ' + why(e))
        kinds[kind] = r
    good = [r for r in kinds.values() if 'error' not in r]
    out: dict[str, Any] = dict(record='sample', sample=sample['id'], targets=len(sample['target_queries']), failed_targets=dict(failures), kinds=kinds)
    if not good:
        out.update(status='excluded', reason=next(iter(failures), None) or next((r['error'] for r in kinds.values() if 'error' in r), 'no target'))
    else:
        def mean(key: str) -> float:
            return sum(float(r[key]) for r in good) / len(good)
        out.update(status='ok', v1=mean('v1'), v2_lo=mean('v2_lo'), v2_found=mean('v2_found'), v2_hi=mean('v2_hi'), kinds_done=len(good), kinds_failed=len(kinds) - len(good),
                   decided=all(r['decided'] for r in good))
    out['seconds'] = round(time.perf_counter() - t0, 3)
    return out


# ---------------------------------------------------------------- results

def read_results(path: Path) -> tuple[dict | None, dict[str, dict]]:
    """(the header, the samples by id) of a result file; a last line that is cut off is dropped."""
    head, got = None, {}
    if not path.exists():
        return None, got
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('record') == 'header':
            head = r
        elif r.get('record') == 'sample':
            got[r['sample']] = r
    return head, got


def mean_sd(xs: list[float]) -> tuple[float | None, float | None]:
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def report(folder: Path, tasks: list[str], plan: str) -> dict:
    keys = ('v1', 'v2_lo', 'v2_found', 'v2_hi')
    per_task, pooled, excluded, undecided, splits = [], defaultdict(list), 0, 0, Counter()
    for task in tasks:
        head, got = read_results(folder / f'{task}.jsonl')
        if head is None:
            continue
        splits[head['split']] += 1
        ok = [r for r in got.values() if r['status'] == 'ok']
        excluded += len(got) - len(ok)
        undecided += sum(not r['decided'] for r in ok)
        row: dict[str, Any] = dict(task=task, split=head['split'], samples=len(ok), excluded=len(got) - len(ok), expected=head.get('samples'))
        for k in keys:
            xs = [float(r[k]) for r in ok]
            pooled[k].extend(xs)
            m, s = mean_sd(xs)
            row[k] = None if m is None else float(f'{m:.6g}')
            row[k + '_sd'] = None if s is None else float(f'{s:.6g}')
        row['undecided'] = sum(not r['decided'] for r in ok)
        row['seconds_per_sample'] = round(sum(r['seconds'] for r in ok) / max(len(ok), 1), 2)
        per_task.append(row)
    overall: dict[str, Any] = dict(plan=plan, tasks=len(per_task), samples=len(pooled['v1']), excluded=excluded, undecided=undecided, splits=dict(splits))
    for k in keys:
        m, s = mean_sd(pooled[k])
        overall[k] = m
        overall[k + '_sd'] = s
        tm = [r[k] for r in per_task if r[k] is not None]
        overall[k + '_mean_of_task_means'] = sum(tm) / len(tm) if tm else None
    return dict(overall=overall, per_task=per_task)


def show(rep: dict) -> None:
    """The means over all samples first, then one line for each task."""
    print(json.dumps(rep['overall']))
    for row in rep['per_task']:
        print(json.dumps(row))


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set', choices=('train', 'dev', 'held-out'))
    ap.add_argument('--plan', choices=('ordered', 'unordered'), required=True)
    ap.add_argument('--model', type=Path, required=True, help='the booster file that fit_trees.py wrote for the plan')
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks with crc32(task) %% N == k')
    ap.add_argument('--tasks', help='comma-separated task ids')
    ap.add_argument('--samples-per-task', type=int, default=0, help='at most K samples of a task, chosen by a seeded hash of the sample id (0: all)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--seconds', type=float, default=10.0, help='the order or the automaton of one target (as points_write.py)')
    ap.add_argument('--max-states', type=int, default=20000, help='the most states of the extractor\'s unordered search')
    ap.add_argument('--steps', type=int, default=3000, help='the most edges that the search for value 2 steps, for one kind of one sample')
    ap.add_argument('--sample-seconds', type=float, default=120.0, help='the most time of the search for value 2, for one kind of one sample')
    ap.add_argument('--check', action='store_true', help='also compute value 1 a second way (unordered: enumerate the paths; ordered: the extractor\'s records) and write the difference')
    ap.add_argument('--check-paths', type=int, default=20000, help='--check: the most paths to enumerate')
    ap.add_argument('--include-train', action='store_true', help='also run train tasks (a pipeline check); a held-out task is never run')
    ap.add_argument('--tag', help='the folder name under the plan (default: the first 8 digits of the model file\'s sha256)')
    ap.add_argument('--report', action='store_true', help='print the means over the result files of the tasks and stop')
    ap.add_argument('--out', type=Path, default=OUTD)
    args = ap.parse_args()
    k, n = map(int, args.shard.split('/'))
    model_sha = hashlib.sha256(args.model.read_bytes()).hexdigest()
    folder = args.out / args.set / 'plan_compare' / args.plan / (args.tag or model_sha[:8])
    splits = {r.split('\t')[0]: r.split('\t')[1] for r in (OUTD / 'split.tsv').read_text().splitlines()[1:]}
    allowed = {'dev', 'train'} if args.include_train else {'dev'}
    wanted = set(args.tasks.split(',')) if args.tasks else None
    names = sorted(p.stem for p in (OUTD / args.set / 'skeleton').glob('*.jsonl') if zlib.crc32(p.stem.encode()) % n == k and (wanted is None or p.stem in wanted))
    tasks = [t for t in names if splits.get(t) in allowed]
    print(f'{args.set} {args.plan}: {len(tasks)} of {len(names)} tasks of shard {args.shard} are {"/".join(sorted(allowed))}', flush=True)
    if args.report:
        show(report(folder, tasks, args.plan))
        return 0
    tr = importlib.import_module('train_rows')
    wr = importlib.import_module('writer')
    live = importlib.import_module('live')
    live_try = importlib.import_module('live_try')
    order = importlib.import_module('order')
    tree_dist = importlib.import_module('tree_dist')
    live_try.P.REPO = os.environ.get('ARC_ROOT', str(Path(__file__).resolve().parents[3]))
    sampler_dir = module_file(tr).parent
    smp = live.Sampler(str(sampler_dir / '../../../models-current'), steers=())
    uses = tuple(wr.feature_names())
    dist = tree_dist.TreeDistribution(str(args.model), uses)
    meta = Path(str(args.model) + '.json')
    if meta.exists():
        names_in = json.loads(meta.read_text()).get('features', {}).get('uses')
        if names_in is not None and list(names_in) != list(uses):
            print('the model\'s feature names differ from the writer\'s', file=sys.stderr)
            return 2
    ctx = Ctx(live, wr, tr, order, dist, uses, args)
    shas = dict(extractor=file_sha(module_file(tr)), writer=file_sha(module_file(wr)), wheel=module_file(live.arclog).parent.parent.name, code=file_sha(Path(__file__)))
    folder.mkdir(parents=True, exist_ok=True)
    total = 0
    for task in tasks:
        count = sum(1 for line in (OUTD / args.set / 'skeleton' / f'{task}.jsonl').open() if line.startswith('{"record": "sample"'))
        total += min(count, args.samples_per_task) if args.samples_per_task > 0 else count
    t0, done, seen = time.time(), 0, 0
    last_print = 0.0
    for ti, task in enumerate(tasks, 1):
        skeleton = OUTD / args.set / 'skeleton' / f'{task}.jsonl'
        records = [json.loads(x) for x in skeleton.read_text().splitlines()]
        head = records[0]
        if head['split'] != splits[task]:
            print(f'task {task}: the skeleton says {head["split"]} and split.tsv says {splits[task]}; skipped', file=sys.stderr)
            continue
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = chosen([r for r in records if r['record'] == 'sample'], args.samples_per_task, args.seed)
        path = folder / f'{task}.jsonl'
        header = dict(record='header', task=task, set=args.set, split=head['split'], plan=args.plan, model=str(args.model), model_sha=model_sha, uses_sha=hashlib.sha256('\n'.join(uses).encode()).hexdigest(),
                      skeleton_sha=file_sha(skeleton), samples=len(samples), samples_per_task=args.samples_per_task, seed=args.seed, steps=args.steps, sample_seconds=args.sample_seconds,
                      max_states=args.max_states, seconds=args.seconds, check=args.check, check_paths=args.check_paths, extractor_sha=shas['extractor'], writer_sha=shas['writer'], wheel=shas['wheel'])
        old, finished = read_results(path)
        fixed = ('plan', 'set', 'task', 'split', 'model_sha', 'uses_sha', 'skeleton_sha', 'samples_per_task', 'seed', 'steps', 'sample_seconds', 'max_states', 'seconds', 'check', 'check_paths', 'wheel', 'writer_sha', 'extractor_sha')
        if old is not None and any(old.get(x) != header[x] for x in fixed):
            print(f'task {task}: {path} was made with other settings ({[x for x in fixed if old.get(x) != header[x]]}); remove it or give --tag. Skipped.', file=sys.stderr)
            continue
        todo = [s for s in samples if s['id'] not in finished]
        seen += len(samples) - len(todo)
        if not todo:
            continue
        sess, d, _ = live_try.session_of(task)
        ctx.run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        with path.open('a') as f:
            if old is None:
                f.write(json.dumps(header) + '\n')
            elif path.stat().st_size and path.read_bytes()[-1:] != b'\n':  # a line cut off by a stop: end it, and read_results drops it
                f.write('\n')
            for sample in todo:
                try:
                    r = process_sample(ctx, sample, queries, args.check)
                except Reject as e:
                    r = dict(record='sample', sample=sample['id'], status='excluded', reason=str(e), kinds={}, targets=len(sample['target_queries']), failed_targets={}, seconds=0.0)
                except Exception as e:
                    r = dict(record='sample', sample=sample['id'], status='excluded', reason='error: ' + why(e), kinds={}, targets=len(sample['target_queries']), failed_targets={}, seconds=0.0)
                f.write(json.dumps(r) + '\n')
                f.flush()
                done += 1
                seen += 1
                now = time.time()
                if now - last_print >= 5:
                    last_print = now
                    rate = done / max(now - t0, 1e-9)
                    print(f'{args.set} {args.plan} {task} ({ti}/{len(tasks)}) samples {seen}/{total} {rate:.3f} samples/s ETA {(total - seen) / max(rate, 1e-9):.0f}s', flush=True)
        now = time.time()
        print(f'{args.set} {args.plan} {task} ({ti}/{len(tasks)}) done: samples {seen}/{total} {done / max(now - t0, 1e-9):.3f} samples/s ETA {(total - seen) * (now - t0) / max(done, 1):.0f}s', flush=True)
    show(report(folder, tasks, args.plan))
    return 0


if __name__ == '__main__':
    sys.exit(main())
