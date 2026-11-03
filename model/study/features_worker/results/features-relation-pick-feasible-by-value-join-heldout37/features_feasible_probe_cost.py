#!/usr/bin/env python
"""Ways to answer "any row" for a partial clause, timed on the same atoms, one thread, in this process.

  <runtime python> -u features_feasible_probe_cost.py --forms FORMS.json --golds POINTS.json --out probe-cost-rows.jsonl [--every N] [--budget S]

At each top-level pick after a first atom, for each relation option in pick order, it takes the option's first one-label atom and times:

- tables: arclog.step_tables(f, 'live', 'live', True, before), with `before` from the form's start, as the search calls it, then reading the row counts.
- no_before: the same call with before None, on each 8th option.
- projections: Decoder.projections() on a fork at the atom's end.
- fork: fork and the step of the token that starts the next atom.

A rerun skips the picks that have a row. Prints a rate and an ETA.
"""
import argparse
import json
import os
import statistics as st
import sys
import time

import features_feasible_walk as W

live, or_q, S, G, M, arclog = W.live, W.or_q, W.S, W.G, W.M, W.arclog
live_rows = W.live_rows
OUT = [None]
DONE = set()
NB_ERR = W.collections.Counter()
CTX = W.CTX
perf = time.perf_counter


def any_proj(pr, ntrain):
    """Whether Decoder.projections' result shows a row on the train examples, which come first in each projection's counts. None where it stopped or gives no count."""
    if pr is None or pr.stop is not None or not pr.projections:
        return None
    seen = False
    for p in pr.projections:
        for c in p.counts[:ntrain]:
            if c.stop is not None or any(v is None for v in c.values):
                return None
            seen = seen or any(v > 0 for v in c.values)
    return seen


class Cost(W.Instr):
    def snapshot(self, n, L, opts, weights):
        if self.rng.ctx != 'top' or L['k'] < 2 or n.phase != 'root':
            return None
        fr, V = self.fr, self.V
        before = self.pg.before
        n0 = S.FNode((), n.dec, n.phase, -1, 0, '', n.neg, n.labs, None)
        rows = []
        t_pick = perf()
        for i, o in enumerate(opts):
            if o in M.CMP or o == M.NOT:
                continue
            c = fr.child(n0, o)
            if c is None:
                continue
            x = next(W.join_maps(fr, c), None)
            if x is None:
                continue
            t0 = perf()
            f = x.dec.fork()
            p = fr.probe(f)
            if p is None:
                continue
            f.step(p)
            t1 = perf()
            res = {}

            def do_tables():
                t = perf()
                try:
                    ct = arclog.step_tables(f, *live.TABLES, True, before)
                    t2 = perf()
                    got, bad = W.read_counts(ct)
                    err = None
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException as e:  # noqa: BLE001
                    t2 = perf()
                    got, bad, err = None, None, type(e).__name__
                res.update(tab=t2 - t, parse=perf() - t2, got=got, bad=bad, err=err)

            def do_proj():
                g = x.dec.fork()
                t = perf()
                try:
                    res['pr'] = g.projections()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException as e:  # noqa: BLE001
                    res['pr'] = 'raised ' + type(e).__name__
                res['proj'] = perf() - t

            for fn in (do_tables, do_proj) if i % 2 else (do_proj, do_tables):  # the order of the two calls alternates, so a cache that they share favours neither
                fn()
            got, bad, err, pr = res['got'], res['bad'], res['err'], res['pr']
            ans = pr if isinstance(pr, str) else any_proj(pr, len(got or ()))
            nb = None
            if len(rows) % 8 == 0:
                h = x.dec.fork()
                h.step(p)
                t6 = perf()
                nb_failed = False
                try:
                    arclog.step_tables(h, *live.TABLES, True, None)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException as e:  # noqa: BLE001
                    NB_ERR[type(e).__name__ + ': ' + str(e)[:60]] += 1
                    nb_failed = True
                nb = None if nb_failed else round((perf() - t6) * 1e3, 3)
            rows.append([V.name(o), round((t1 - t0) * 1e3, 3), round(res['tab'] * 1e3, 3), round(res['parse'] * 1e3, 3), round(res['proj'] * 1e3, 3), nb, sum((got or {}).values()), bool(bad), err, ans])
        tp = (perf() - t_pick) * 1e3
        # decoder calls on the prefix
        d = n.dec
        t = perf()
        for _ in range(20):
            d.fork()
        fork_ms = (perf() - t) / 20 * 1e3
        tok = opts[:40]
        t = perf()
        d.admits(tok)
        adm_ms = (perf() - t) * 1e3
        t = perf()
        for o in opts[:10]:
            try:
                d.forced(o)
            except arclog.Refusal:
                pass
        forced_ms = (perf() - t) / 10 * 1e3
        return dict(rec='pick', task=CTX['task'], line=CTX['line'], ord=CTX['ord'], phase=n.phase, k=L['k'], pick_ms=round(tp, 1), fork_ms=round(fork_ms, 4), admits_ms=round(adm_ms, 3), admits_n=len(tok), forced_ms=round(forced_ms, 4), o=rows)


class RunC(W.Orig):
    drawer_class = Cost

    def drawer(self, pg, kind, dec, place=None, prior=None):
        dr = super().drawer(pg, kind, dec, place, prior)
        dr.pg = pg
        return dr


or_q.GuidedRun = RunC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', required=True)
    ap.add_argument('--golds', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--every', type=int, default=8)
    ap.add_argument('--budget', type=float, default=1e9)
    a = ap.parse_args()
    forms = json.load(open(a.forms))[::a.every]
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out):
            d = json.loads(line)
            if d['rec'] == 'form':
                done.add((d['task'], d['line']))
            else:
                W.DONE.add((d['task'], d['line'], d['ord'], d['phase']))
    todo = [r for r in forms if (r[4], r[5]) not in done]
    golds = {x['task']: x['gold_sexp'] for x in json.load(open(a.golds))}
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    W.OUT[0] = open(a.out, 'a')
    t0 = time.time()
    print('%d forms, %d to do' % (len(forms), len(todo)), flush=True)
    for c, row in enumerate(todo, 1):
        task, line = row[4], row[5]
        if time.time() - t0 > a.budget:
            print('budget ends the run', flush=True)
            break
        lines = [x for x in golds[task].splitlines() if x.strip()]
        target = lines[line]
        keep = live_rows.parents(lines, line)
        G.gold_of = lambda t, c_, p, ls=[lines[j] for j in keep] + [target]: (t, ls)
        CTX.clear()
        CTX.update(task=task, line=line, errs=W.collections.Counter(), pending=[], written=0)
        rows = []
        try:
            or_q.one(sampler, task, 'RULE', [len(keep), 0], 'RULE', rows)
        except Exception as e:  # noqa: BLE001
            print('error', task, line, repr(e)[:100], flush=True)
        W.OUT[0].write(json.dumps(dict(rec='form', task=task, line=line)) + '\n')
        W.OUT[0].flush()
        el = time.time() - t0
        print('[%d/%d %.0fs eta %.0fs] %s %s' % (c, len(todo), el, el / c * (len(todo) - c), task, line), flush=True)
    print('calls with before None that raised:', dict(NB_ERR), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
