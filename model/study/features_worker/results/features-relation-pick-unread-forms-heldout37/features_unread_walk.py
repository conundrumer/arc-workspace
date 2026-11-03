#!/usr/bin/env python
"""Teacher-forced walks of the census's forms, every form before in scope, that keep at each relation pick the derived options and their steered weights.

  features_unread_env.sh features_unread_walk.py [--limit N]

Writes walk-held-before.jsonl in this folder: one row per form, flushed. A rerun skips the forms that have a row. It prints a rate and an ETA. The walk is frontier_q.py's and or_q.py's, unchanged: a Drawer subclass copies what pick is given.

A pick entry: phase, k, gold, q_bits, the sum of the weights, and [[name, weight]] of the options of kind `relation`. The form's bits go next to the census's in the row.
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.environ['SAMPLER_CODE'])
import live  # noqa: E402
import or_q  # noqa: E402
import search_gold as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = HERE + 'walk-held-before.jsonl'
M = live.M
PEND = []


class Instr(or_q.GuidedDrawer):
    def pick(self, opts, weights):
        f = sys._getframe(1)
        while f is not None and f.f_code.co_name != 'atom':
            f = f.f_back
        n = f.f_locals['n']
        rec = None
        if n.phase in ('root', 'root2') and self.force:
            fr, V = self.fr, self.V
            rec = dict(phase=n.phase, k=f.f_locals['k'], ctx=self.rng.ctx, gold=V.name(self.force[0]), sum=sum(weights),
                       rels=[[V.name(o), w] for o, w in zip(opts, weights) if o not in M.CMP and o != M.NOT and fr.KIND[o] == 'relation'])
        o, q = super().pick(opts, weights)
        if rec is not None:
            rec['q_bits'] = round(or_q.bits(q), 4)
            PEND.append(rec)
        return o, q


class RunX(or_q.GuidedRun):
    drawer_class = Instr


or_q.GuidedRun = RunX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    rows = json.load(open(os.environ['FORMS']))
    done = set()
    if os.path.exists(OUT):
        text = open(OUT).read()
        if text and not text.endswith('\n'):  # a run killed in a write leaves part of a line
            open(OUT, 'w').write(text[:text.rfind('\n') + 1])
        done = {(r['task'], r['line']) for r in map(json.loads, open(OUT))}
    todo = [r for r in rows if (r[4], r[5]) not in done]
    print('%d forms, %d done, %d to do; models %s' % (len(rows), len(done), len(todo), G.MODELS), flush=True)
    t0 = time.time()
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    print('load %.1f s' % (time.time() - t0), flush=True)
    t0, c = time.time(), 0
    with open(OUT, 'a') as out:
        for row in todo[:a.limit]:
            t1 = time.time()
            task, i = row[4], row[5]
            lines = [x for x in G.golds()[task].splitlines() if x.strip()]
            target = lines[i]
            kind = target.split()[0].lstrip('(')
            keep = list(range(i))
            G.gold_of = lambda t, c_, p, ls=[lines[j] for j in keep] + [target]: (t, ls)
            PEND.clear()
            try:
                q = or_q.one(sampler, task, kind, [len(keep), 0], kind)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            r = dict(task=task, line=i, kind=kind, total=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), left=q.get('left'), error=q.get('error'), atoms=q.get('atoms'), detail=q.get('detail'), picks=list(PEND), seconds=round(time.time() - t1, 2))
            out.write(json.dumps(r) + '\n')
            out.flush()
            c += 1
            rate = c / (time.time() - t0)
            print('%s %d %s total %s (%.2f s); %.2f forms/s, %d left, ETA %.0f s' % (task, i, kind, r['total'], r['seconds'], rate, len(todo) - c, (len(todo) - c) / rate), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
