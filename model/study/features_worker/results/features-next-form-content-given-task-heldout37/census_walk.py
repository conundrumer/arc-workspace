#!/usr/bin/env python
"""Teacher-forced walks of the census's forms, every earlier form in scope, that keep at each relation pick every relation option and its steered weight.

  census_walk_env.sh census_walk.py --split held|dev --out DIR [--shard K/N]

Writes DIR/walk-<split>-<K>.jsonl, one row per form, flushed. A rerun skips the forms that have a row. It prints a rate and an ETA.
The walk is the one of frontier_q.py and or_q.py, unchanged: a Drawer subclass copies what pick is given. The row's total goes beside the census's bits.

A pick entry: phase, k, gold, q_bits, sum (of all weights at the pick, NOT and comparison included), and rels, [[name, kind code, weight]] of the relation options.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.environ['SAMPLER_CODE'])
import live  # noqa: E402
import or_q  # noqa: E402
import search_gold as G  # noqa: E402

M = live.M
PEND = []
CODE = {'lib relation': 'l', 'relation macro': 'm', 'fact relation': 'f', 'relation': 'd'}
D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
HELD = open(D + 'sampler/sampler-worker/held/tasks.txt').read().split()
EVAL = open(D + 'features-worker/arm/eval-tasks.txt').read().split()
TEXTS = json.load(open(D + 'census/census-bands-cheapest/texts.json'))['stems']


class Instr(or_q.GuidedDrawer):
    def pick(self, opts, weights):
        f = sys._getframe(1)
        while f is not None and f.f_code.co_name != 'atom':
            f = f.f_back
        rec = None
        if f is not None:
            n = f.f_locals['n']
            if n.phase in ('root', 'root2') and self.force:
                fr, V = self.fr, self.V
                rec = dict(phase=n.phase, k=f.f_locals['k'], ctx=self.rng.ctx, gold=V.name(self.force[0]), sum=sum(weights),
                           rels=[[V.name(o), CODE[fr.KIND[o]], round(w, 9)] for o, w in zip(opts, weights) if o not in M.CMP and o != M.NOT and fr.KIND[o] in CODE])
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
    ap.add_argument('--split', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k, n = map(int, a.shard.split('/'))
    names = HELD if a.split == 'held' else [t for t in EVAL if t not in HELD]
    todo = []
    for t in names:
        lines = [x for x in TEXTS[t]['lines'] if x.strip() and not x.startswith('(OUT')]
        for i, x in enumerate(lines):
            kind = x.split()[0].lstrip('(')
            if kind in ('RULE', 'DET', 'INIT'):
                todo.append((t, i, kind))
    todo = todo[k::n]
    out_path = '%s/walk-%s-%d.jsonl' % (a.out, a.split, k)
    done = set()
    if os.path.exists(out_path):
        text = open(out_path).read()
        if text and not text.endswith('\n'):
            open(out_path, 'w').write(text[:text.rfind('\n') + 1])
        done = {(r['task'], r['form']) for r in map(json.loads, open(out_path))}
    todo = [x for x in todo if (x[0], x[1]) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print('%d forms to do; models %s' % (len(todo), G.MODELS), flush=True)
    t0 = time.time()
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    print('load %.1f s' % (time.time() - t0), flush=True)
    t0, c = time.time(), 0
    with open(out_path, 'a') as out:
        for task, i, kind in todo:
            t1 = time.time()
            lines = [x for x in TEXTS[task]['lines'] if x.strip() and not x.startswith('(OUT')]
            G.gold_of = lambda t, c_, p, ls=lines[:i + 1]: (t, ls)
            PEND.clear()
            try:
                q = or_q.one(sampler, task, kind, [i, 0], kind)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            r = dict(task=task, form=i, kind=kind, total=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), left=q.get('left'), error=q.get('error'), picks=list(PEND), seconds=round(time.time() - t1, 2))
            out.write(json.dumps(r, separators=(',', ':')) + '\n')
            out.flush()
            c += 1
            if c % 20 == 0 or c == len(todo):
                rate = c / (time.time() - t0)
                print('%s %d %s total %s; %.2f forms/s, %d left, ETA %.0f s' % (task, i, kind, r['total'], rate, len(todo) - c, (len(todo) - c) / rate), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
