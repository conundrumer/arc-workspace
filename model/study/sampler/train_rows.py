#!/usr/bin/env python
"""Training rows for the trees: the writing points of a query's token stream, with the writer's own features (writer.Features).

    for rec in points_of(run, forms, kind, stream, uses): ...
    for i, rec in points_of_targets(run, forms, kind, streams, uses): ...   # several targets of one kind over one scope, as a trie

The kind token is no choice point of the writer: `Run.next_kind` draws it from walk counts in `Run.program`, and `Run.open_form` steps it. So the first
point is the one after the kind token.

The plans (points_of_targets, plan=...; see order.py): a record then also has positive_ids (int32, the ids of the point that are positive, a subset of ids, sorted), live (the
number of live targets at the point) and order. Under `ordered` each target is walked in its canonical stream (order.canonical_stream; a target whose canonical stream does not give
its gold QueryHash is walked as given, and its order is 'gold' with order_why); the positives are the next tokens of the live targets. Under `unordered` the points are the states of a
search over the targets' item sets, merged by order.set_key, and the positives are every id that continues some live target's item set (order.Unordered).
A plan's records need the mask of that plan: `plan` must be the writer plan of the process (lookahead_legal.PLAN; lookahead_legal.check_plan), else points_of_targets raises.

vectors=True (points_of, points_of_targets, points_of_unordered): a record also has vectors (float32, len(ids) x width: the writing-point vector of each admitted id, in the order of ids; see
writer.Features.vectors and writer.VECTOR_BLOCKS) and names (the width column names, one tuple that every record shares: a file writes it once).

CLI check (prints counts only):
    python train_rows.py [--ramp prep.jsonl] [--uses all|NAME,...] TASK...
"""
import argparse
import collections
import json
import os
import sys
import time

import numpy as np

import live
import order
import writer
from live import KIND_TOK, M, arclog

PREP = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/canon-count/prep.jsonl'


def split_uses(uses):
    """(option names, point names): the names of `uses` by scope, each in the order of `uses`."""
    return (tuple(n for n in uses if writer.PREFIX_FEATURES[n].scope == 'option'), tuple(n for n in uses if writer.PREFIX_FEATURES[n].scope == 'point'))


def points_of(run, forms, kind, stream, uses, vectors=False):
    """The writing points of one query, over the scope `forms`, as dicts, in stream order.

    stream: the query's model tokens (the kind token first, as StudyProgram.decode_stream gives them for the query's line; it is dropped if there).
    uses: the feature names (writer.feature_names() holds every name). `option` has the columns of the option-scope names, `point` those of the point-scope
    names, each in the order of `uses` (split_uses gives both lists).
    A writing point with fewer than two ids, and the point after the last token (where the query is finished), give no record.
    A record has: index (the place of the next token in the stream, the kind token at 0), phase (name), ids (int32), option (ids x option names, float32), point (point names, float32),
    next_id (the stream's next model token, None at the end), tokens, atoms, open_atom (model tokens), place (dict: phase, atom_start, body_end, end_admitted, port, branch,
    negated, atoms, depth), left_mask False.
    If the next token is not in the mask, no step is made: the last record is {'left_mask': True, 'index', 'phase', 'token'}.
    """
    opt_names, pt_names = split_uses(tuple(uses))
    if vectors:
        writer.keep_state_tables(run)
    stream = [int(t) for t in stream]
    if stream and stream[0] == KIND_TOK[kind]:
        stream = stream[1:]
    dec, pg = run.scope(forms)
    pg.new = []
    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    for t in stream + [None]:
        if pt.track.where == 'done':  # the mask holds a kind token: the writer finishes here and chooses nothing
            return
        ids = writer.point_ids(pt)
        phase = pt.place.phase.name
        if t is not None and t not in pt.ids_:
            yield dict(left_mask=True, index=len(pt.tokens), phase=phase, token=t)
            return
        if len(ids) >= 2:
            x = writer.Features(pt, ids)
            yield _record(pt, ids, phase, x.option(opt_names), x.point(pt_names), t, *_vectors(x, vectors), cut=_cut(ids, [t]))
        if t is None:
            return
        pt = writer.step_point(pt, t)


def _vectors(x, vectors):
    """(vectors, names) of Features x, or (None, None) where vectors is off."""
    return (x.vectors(), x.names) if vectors else (None, None)


def _cut(ids, tokens):
    """The distinct tokens of `tokens` (None left out) that are in the engine's mask and that the legality rules removed, so that `ids` (writer.point_ids) lacks them: a fault, as the
    rules remove no gold token. Sorted."""
    return sorted(t for t in set(tokens) if t is not None and t not in ids)


def _record(pt, ids, phase, option, point, next_id, vectors=None, names=None, cut=()):
    """The record of a writing point with at least two ids (the fields of points_of). vectors and names are in the record where given. ids are the ids that serving scores
    (writer.point_ids); rule_removed (int32) are the next or positive ids that the engine's mask holds and the legality rules removed (a fault; none in a record without one)."""
    end_ok = bool((ids == M.END).any())
    atom_start = pt.place.phase is writer.Phase.ATOM_START
    extra = {} if vectors is None else dict(vectors=vectors, names=names)
    return dict(extra, rule_removed=np.array(cut, np.int32),
        left_mask=False, index=len(pt.tokens), phase=phase, ids=ids.astype(np.int32), option=option, point=point, next_id=next_id,
        tokens=pt.tokens, atoms=pt.atoms, open_atom=pt.open_atom,
        place=dict(phase=phase, atom_start=atom_start, body_end=atom_start and end_ok and not pt.track.path, end_admitted=end_ok, port=pt.place.port,
                   branch=pt.place.branch, negated=pt.place.negated, atoms=pt.place.atoms, depth=len(pt.track.path)))


class _Node:
    """A trie node: the stream prefix that leads here."""
    __slots__ = ('kids', 'ends', 'all')

    def __init__(self):
        self.kids = {}  # next token -> _Node
        self.ends = []  # the targets whose stream ends here
        self.all = []  # the targets whose stream passes through or ends here


_ENV = [None, None]


def order_env(run):
    """The order.Env of the run's session (one is kept, for the last session)."""
    if _ENV[0] is not run.session:
        _ENV[:] = [run.session, order.Env(run.session)]
    return _ENV[1]


PLANS = ('ordered', 'unordered')
ORDER_SECONDS = 60.0  # the `ordered` plan's time for the canonical stream of one target (order.canonical_stream)


def points_of_targets(run, forms, kind, streams, uses, prepare=None, plan=None, seconds=10.0, stats=None, max_states=20000, vectors=False, order_seconds=ORDER_SECONDS):
    """The writing points of several queries of one kind over one scope, walked as a trie of their streams: a prefix that targets share is stepped and featured once.

    streams: the targets' model tokens, each as `points_of` takes one. Yields (target index, record), where the target's records come in its stream order (records of
    different targets are interleaved). A target's records are those of `points_of(run, forms, kind, stream, uses)`, field by field. The records of targets at one point share their
    arrays and dicts (ids, option, point, tokens, atoms, place) and differ in next_id; do not change them in place.
    If a step or the features of a point raise, every target that goes on from there gets (index, {'error': exception}) in place of its next records, and the walk goes on with the others.
    prepare: if given, a function from a target's stream (the kind token first) to the stream that is walked, for example the stream in the writer's fixed atom order.
    plan: None (the records above), 'ordered' or 'unordered'. With a plan a record also has positive_ids (int32 array, sorted, a subset of ids), live (int) and order (str).
        'ordered': each target is walked in its canonical stream (order.canonical_stream, `order_seconds` for each); order is 'canonical', or 'gold' (with order_why) where the rule gives no
        stream with the gold QueryHash. positive_ids are the next tokens of the live targets (the ones whose stream has the point's token prefix) that the mask holds.
        'unordered': see points_of_unordered; the records are those of its states, one for each live target.
    stats: if given, a Counter that gets counts (plan keys start with 'ordered:' or 'unordered:').
    vectors: True adds vectors and names to each record (see the module docstring), under every plan.
    """
    if plan not in (None,) + PLANS:
        raise ValueError('plan: %r' % (plan,))
    if plan is not None:
        import lookahead_legal
        lookahead_legal.check_plan(plan)
    if plan is not None and prepare is not None:
        raise ValueError('prepare and plan do not go together')
    if vectors:
        writer.keep_state_tables(run)
    if plan == 'unordered':
        yield from points_of_unordered(run, forms, kind, streams, uses, max_states=max_states, seconds=seconds, stats=stats, vectors=vectors)
        return
    opt_names, pt_names = split_uses(tuple(uses))
    orders = [('', '')] * len(streams)
    walk_streams = list(streams)
    if plan == 'ordered':
        dec0, _ = run.scope(forms)
        env = order_env(run)
        for i, s in enumerate(streams):
            walk_streams[i], o, why = order.canonical_stream(env, dec0, kind, s, order_seconds)
            orders[i] = (o, why)
            if stats is not None:
                stats['ordered:' + o + (':' + why.split(':')[0] if why else '')] += 1
    root = _Node()
    for i, s in enumerate(walk_streams):
        s = [int(t) for t in (prepare(s) if prepare else s)]
        if s and s[0] == KIND_TOK[kind]:
            s = s[1:]
        node = root
        node.all.append(i)
        for t in s:
            node = node.kids.setdefault(t, _Node())
            node.all.append(i)
        node.ends.append(i)
    if not root.all:
        return
    dec, pg = run.scope(forms)
    pg.new = []
    start = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    todo = [(None, None, root)]  # (the point before, the token that steps it, the node); a child is stepped when it is taken, so a path holds its points only
    while todo:
        before, tok, node = todo.pop()
        if before is None:
            pt = start
        else:
            try:
                pt = writer.step_point(before, tok)
            except Exception as e:
                for i in node.all:
                    yield i, dict(error=e)
                continue
        if pt.track.where == 'done':  # the mask holds a kind token: the writer finishes here and chooses nothing
            continue
        ids = writer.point_ids(pt)
        phase = pt.place.phase.name
        take = [(None, node.ends, None)] if node.ends else []  # (next id, targets, child) of the ones that the engine's mask holds
        for t, kid in node.kids.items():
            if t in pt.ids_:
                take.append((t, kid.all, kid))
            else:
                if stats is not None:
                    stats['left the mask'] += 1
                for i in kid.all:
                    yield i, dict(left_mask=True, index=len(pt.tokens), phase=phase, token=t)
        cut = _cut(ids, [t for t, _, _ in take])
        if stats is not None and plan is not None:
            stats[plan + ':rule-removed next ids'] += len(cut)
            stats[plan + ':points with a rule-removed next id'] += bool(cut)
            stats[plan + ':points with no id left by the rules'] += bool(len(pt.ids_) and not len(ids))
        if len(ids) >= 2 and take:
            try:
                x = writer.Features(pt, ids)
                base = _record(pt, ids, phase, x.option(opt_names), x.point(pt_names), None, *_vectors(x, vectors), cut=cut)
            except Exception as e:
                for _, targets, _ in take:
                    for i in targets:
                        yield i, dict(error=e)
                continue
            if plan == 'ordered':
                base['positive_ids'] = np.array(sorted(t for t, _, _ in take if t is not None), np.int32)
                base['live'] = len(node.all)
            for t, targets, _ in take:
                for i in targets:
                    if plan == 'ordered':
                        yield i, dict(base, next_id=t, order=orders[i][0], order_why=orders[i][1])
                    else:
                        yield i, dict(base, next_id=t)
        todo.extend((pt, t, kid) for t, _, kid in reversed(take) if kid is not None)


def _unordered_states(run, pg, dec, kind, walkers, stats):
    """The states of the unordered search, depth first: dicts with pt, key (order.set_key), cfgs ({target: configurations} of the live targets), and, at a point that is not the end,
    nexts ({target: tokens}), positive (sorted ids of the mask that continue some live target), edges ([(token, key of the state after it)]). A step or a key that raises gives
    {'error', 'targets'}. A state is reached once for each key; the live targets of a state that is met again are compared with the first time."""
    start = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    cfg0 = {i: w.start() for i, w in walkers.items()}
    key0 = order.set_key(start)
    seen = {key0: frozenset(cfg0)}
    todo = [(start, cfg0, key0)]
    while todo:
        pt, cfgs, key = todo.pop()
        if pt.track.where == 'done':
            yield dict(pt=pt, key=key, cfgs=cfgs)
            continue
        idset = set(pt.ids_.tolist())  # the engine's mask: the search goes on along it, and writer.point_ids is cut from it in the records
        nexts = {i: walkers[i].nexts(c) for i, c in cfgs.items()}
        positive = sorted(set().union(*nexts.values()) & idset)
        children, edges = [], []
        for t in positive:
            cc = {}
            for i, c in cfgs.items():
                if t in nexts[i]:
                    n = walkers[i].step(c, t)
                    if n:
                        cc[i] = n
            try:
                child = writer.step_point(pt, t)
                k = order.set_key(child)
            except Exception as e:
                yield dict(error=e, targets=list(cc))
                continue
            edges.append((t, k))
            if k in seen:
                stats['unordered:merged'] += 1
                if seen[k] != frozenset(cc):
                    stats['unordered:merged states with other live targets'] += 1
            else:
                seen[k] = frozenset(cc)
                children.append((child, cc, k))
        yield dict(pt=pt, key=key, cfgs=cfgs, nexts=nexts, positive=positive, edges=edges, idset=idset)
        todo.extend(reversed(children))


def points_of_unordered(run, forms, kind, streams, uses, max_states=20000, seconds=10.0, stats=None, graph=None, vectors=False):
    """The writing points of several queries of one kind over one scope under the `unordered` plan: yields (target index, record) as points_of_targets does. Raises where the
    writer plan of the process is not `unordered` (lookahead_legal.check_plan).

    The points are the states of a search from the first point: at each state the positives are the ids of the mask that continue some live target's item set (order.Unordered:
    every order of the items that the decoder accepts, from which the whole query can be written), the search takes each positive, and two states with one order.set_key (the
    same items up to a renaming of the labels, and the same open item) are one state, written once with the token prefix of the first visit. A target is live at a state when its
    item set can still be written from there. A state with live targets gives one record for each: the fields of points_of, with next_id the target's own next token when the point's
    tokens are a prefix of the stream as given (else None), positive_ids (int32, sorted), live (the live targets at the state) and order 'unordered'.
    A target that cannot be read (order.Query.unsupported), or whose automaton passes `seconds` or 20000 boundaries, gets (index, {'error': exception}) before any record; if the search
    has more than max_states states, every target gets one error and no record.
    graph: if given, a dict that gets graph[key] = dict(edges=[(token, key)], hash=QueryHash or None, done=[targets that have written their whole query]) for each state.
    stats: if given, a Counter that gets counts.
    """
    import lookahead_legal
    lookahead_legal.check_plan('unordered')
    stats = collections.Counter() if stats is None else stats
    opt_names, pt_names = split_uses(tuple(uses))
    if vectors:
        writer.keep_state_tables(run)
    dec, pg = run.scope(forms)
    pg.new = []
    env = order_env(run)
    golds, walkers = {}, {}
    for i, s in enumerate(streams):
        s = [int(t) for t in s]
        golds[i] = s[1:] if s and s[0] == KIND_TOK[kind] else s
        try:
            q = order.query_of(env, dec, kind, s)
            if q.unsupported:
                raise ValueError('unsupported: ' + q.unsupported)
            w = order.Unordered(env, q, seconds=seconds)
            if not w.ok:
                raise ValueError('no order of the items is written')
            w.gold_hash = q.gold_hash
            walkers[i] = w
        except Exception as e:
            stats['unordered:target errors'] += 1
            yield i, dict(error=e)
    if not walkers:
        return
    n = 0
    for ev in _unordered_states(run, pg, dec, kind, walkers, collections.Counter()):
        n += 1
        if n > max_states:
            for i in walkers:
                yield i, dict(error=OverflowError('the search has more than %d states' % max_states))
            stats['unordered:over the state cap'] += 1
            return
    for ev in _unordered_states(run, pg, dec, kind, walkers, stats):
        if 'error' in ev:
            for i in ev['targets']:
                yield i, dict(error=ev['error'])
            continue
        pt, cfgs = ev['pt'], ev['cfgs']
        stats['unordered:states'] += 1
        if 'nexts' not in ev:  # the end of the query
            done = [i for i, c in cfgs.items() if walkers[i].done(c)]
            h = writer.query_hash(pt.dec)
            stats['unordered:end states'] += 1
            stats['unordered:end states with a target done'] += bool(done)
            stats['unordered:end states with the QueryHash of a target done'] += any(h == walkers[i].gold_hash for i in done)
            if graph is not None:
                graph[ev['key']] = dict(edges=[], hash=h, done=done, gold=[walkers[i].gold_hash for i in cfgs])
            continue
        ids, idset, positive = writer.point_ids(pt), ev['idset'], ev['positive']
        cut = _cut(ids, positive)
        stats['unordered:rule-removed positives'] += len(cut)
        stats['unordered:points with a rule-removed positive'] += bool(cut)
        stats['unordered:points with no id left by the rules'] += bool(len(pt.ids_) and not len(ids))
        phase = pt.place.phase.name
        stats['unordered:live targets'] += len(cfgs)
        if graph is not None:
            graph[ev['key']] = dict(edges=ev['edges'], hash=None, done=[i for i, c in cfgs.items() if walkers[i].done(c)], gold=[])
        if not positive:
            stats['unordered:states with no positive'] += 1
        for i, nx in ev['nexts'].items():
            for t in sorted(nx - idset):
                stats['unordered:left the mask'] += 1
                yield i, dict(left_mask=True, index=len(pt.tokens), phase=phase, token=t, tokens=pt.tokens)
        if len(ids) < 2:
            continue
        stats['unordered:points'] += 1
        try:
            x = writer.Features(pt, ids)
            base = _record(pt, ids, phase, x.option(opt_names), x.point(pt_names), None, *_vectors(x, vectors), cut=cut)
        except Exception as e:
            for i in cfgs:
                yield i, dict(error=e)
            continue
        base.update(positive_ids=np.array(positive, np.int32), live=len(cfgs), order='unordered', order_why='')
        stats['unordered:positives'] += len(positive)
        stats['unordered:ids'] += len(ids)
        m = len(pt.tokens) - 1
        for i in cfgs:
            g = golds[i]
            yield i, dict(base, next_id=g[m] if m < len(g) and tuple(g[:m]) == pt.tokens[1:] else None)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ramp', default=PREP)
    ap.add_argument('--uses', default='all')
    ap.add_argument('tasks', nargs='+')
    a = ap.parse_args(argv)
    import live_try
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    uses = writer.feature_names() if a.uses == 'all' else tuple(a.uses.split(','))
    opt, pt = split_uses(uses)
    smp = live.Sampler(os.environ['SAMPLER_CODE'] + '/../../../models-current', steers=())
    recs = {}
    for l in open(a.ramp):
        r = json.loads(l)
        if r['task'] in a.tasks:
            recs[r['task']] = r
    n_pts = n_ids = max_ids = bad = left = nq = nonfinite = 0
    t0 = time.time()
    for task in a.tasks:
        lines = recs[task]['programs'][0]['lines']
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 600, d, live.Limits())
        ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*lines, live.READER_OUT)), sess.settings).decode_stream()
        for i in range(len(lines)):
            toks = [t for t, m, p in zip(ids, model, paths) if m and p[0] == i]
            kind = run.V.name(toks[0])
            if kind not in KIND_TOK:
                continue
            nq += 1
            for rec in points_of(run, lines[:i], kind, toks, uses):
                if rec['left_mask']:
                    left += 1
                    print('left the mask', task, i, rec['index'], rec['phase'], run.V.name(rec['token']))
                    continue
                n = len(rec['ids'])
                n_pts += 1
                n_ids += n
                max_ids = max(max_ids, n)
                assert rec['option'].shape == (n, len(opt)) and rec['point'].shape == (len(pt),)
                nonfinite += int(not np.isfinite(rec['option']).all())
                if rec['next_id'] is not None and rec['next_id'] not in rec['ids']:
                    bad += 1
    print(json.dumps(dict(tasks=len(a.tasks), queries=nq, points=n_pts, ids_mean=round(n_ids / max(n_pts, 1), 2), ids_max=max_ids, next_not_in_ids=bad, left_mask=left,
                          option_features=len(opt), point_features=len(pt), nonfinite=nonfinite, seconds=round(time.time() - t0, 1))))


if __name__ == '__main__':
    main(sys.argv[1:])
