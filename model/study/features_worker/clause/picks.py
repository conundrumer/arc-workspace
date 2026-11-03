#!/usr/bin/env python
"""Gold's relation picks at the points of a stems file, one JSON line per pick: the option row the relation steer scores, gold's name and q's share of it. Uses or_q's forced walk, so this is gold-prefix data. A restart skips finished points.

  <runtime python> picks.py STEMS OUT.jsonl
"""
import json, math, os, sys, time
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/.claude/worktrees/search-arm3/model/study/sampler')
import live, live_try, or_q, relsteer, search  # noqa: E402,E401
import search_gold as G  # noqa: E402
from live import M  # noqa: E402

CUR = {}
_f = relsteer.Scorer.f


def f(self, row):
    CUR['row'] = row
    return _f(self, row)


relsteer.Scorer.f = f


class Drawer(or_q.GuidedDrawer):
    log = None

    def rel_factors(self, *a, **k):
        self.rel_cache.clear(); CUR.pop('row', None)
        return super().rel_factors(*a, **k)

    def pick(self, opts, weights):
        o, q = super().pick(opts, weights)
        f_ = sys._getframe(1)
        while f_ is not None and f_.f_code.co_name != 'atom':
            f_ = f_.f_back
        ph = f_.f_locals['n'].phase
        if ph in ('root', 'root2') and self.log is not None:
            s = sum(weights) or 1.0
            self.log.append(dict(ctx=self.rng.ctx, phase=ph, n=len(opts), gold=self.V.name(o), q=round(q, 6), top=sorted((round(w / s, 4) for w in weights), reverse=True)[:5], row=CUR.get('row')))
        return o, q


class Run(or_q.GuidedRun):
    drawer_class = Drawer


def one(sampler, task, case, point):
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    sess, task_json, _ = live_try.session_of(task)
    run = Run(sampler.pri, sess, time.monotonic() + 60, task_json, live.Limits(form_tries=1))
    dec, pg = run.scope(scope)
    g = run.rng = or_q.Guide(run, or_q.gold_rest(sess, scope, target))
    Drawer.log = log = []
    try:
        run.form(pg, dec, case)
    except (search.Dead, Exception):  # noqa: BLE001
        pass
    return dict(task=task, case=case, point=point, scope=len(scope), target=target, picks=log)


def main():
    stems, out = sys.argv[1:3]
    done = {(r['task'], r['case'], tuple(r['point'])) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    pts = G.points(stems); t0 = time.time()
    with open(out, 'a') as fh:
        for n, (task, case, point) in enumerate(pts, 1):
            if (task, case, tuple(point)) in done:
                continue
            try:
                r = one(sampler, task, case, point)
            except (search.Dead, Exception) as e:  # noqa: BLE001
                r = dict(task=task, case=case, point=point, picks=[], error=repr(e))
            fh.write(json.dumps(r) + '\n'); fh.flush()
            print(n, len(pts), task, point, len(r['picks']), r.get('error', '')[:100], round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
