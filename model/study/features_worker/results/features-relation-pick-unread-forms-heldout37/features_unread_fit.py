#!/usr/bin/env python
"""The mixture weight w, fit on non-held walks only: one compact row per relation pick, then w by definition of the set. Reads no held row.

  <runtime python, for zstandard> features_unread_fit.py rows    writes fit-picks.jsonl, one row per form, flushed; a rerun skips finished forms; prints a rate and an ETA
  <runtime python> features_unread_fit.py fit                    writes fit.json from fit-picks.jsonl

Walks: the rank record's walks/features-walk-test-before-0of1.jsonl.zst, the 161 test tasks, scope of all earlier forms. Their steered weights come from the steer in use, which was not fit on these tasks. The train walks' weights come from a steer that was fit on those tasks, so they give a fit-side figure only (`--train`), which no held read uses.

The mixture at a relation pick, for a set U: weight w uniform over U, 1-w on the steered prior. Every relation pick of a form pays under it, whatever its class. A pick with U empty stays as it is. Two versions of U:
- forms: U is the forms of the set, gold's target pays -log2(w/|U| + (1-w)p), a pick outside pays -log2((1-w)p).
- options: U is the relation options at the pick whose form is in the set, so a uniform pick is a real distribution over options.
"""
import io
import json
import math
import os
import sys
import time

import gzip

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = HERE + 'fit-picks.jsonl'
CORPUS = L.DIR + 'sampler/corpus-v3mix/'
WALKS = {'test': ['features-walk-test-before-0of1.jsonl.zst'], 'train': ['features-walk-train-before-%dof3.jsonl.zst' % i for i in range(3)]}


def gold_of(task, cache={}):
    if task not in cache:
        with gzip.open(CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
            cache[task] = L.Gold(L.lines_of(json.loads(f.readline())['gold_sexp']))
    return cache[task]


def pick_row(g, st, seen, p):
    """Compact row of a walk pick: bits, and for each usable set its counts and whether gold is inside."""
    sets = st.at(seen)
    gold_line = g.form_of_slot(p['gold'])
    rels = {}
    for name, kd, *_ in p['opts']:
        if kd == 'relation':
            rels[name] = g.form_of_slot(name)
    w = [x[2] for x in p['opts']]
    total = sum(w)
    idx = p['gold_idx']
    row = dict(phase=p['phase'], k=p['k'], q=p['q_bits'], share=None if idx is None else round(-math.log2(w[idx] / total), 4) if w[idx] > 0 else None, derived=gold_line is not None, n={}, o={}, inside={})
    for k in ('unread_later', 'unread_before', 'unread_so_far'):
        s = set(sets[k])
        row['n'][k] = len(s)
        row['o'][k] = sum(f in s for f in rels.values())
        row['inside'][k] = gold_line in s
    return row, gold_line


def form_rows(path, done, out):
    import zstandard
    cur, picks, n = None, [], 0
    t0 = time.time()
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            if line.startswith('{"rec": "form"'):
                d = json.loads(line)
                key = (d['task'], d['line'])
                if key not in done:
                    g = gold_of(d['task'])
                    st = L.Sets(g, d['line'])
                    seen = set()
                    rows = []
                    for p in picks:
                        r, t = pick_row(g, st, seen, p)
                        rows.append(r)
                        if t is not None and t != d['line']:
                            seen.add(t)
                    out.write(json.dumps(dict(task=d['task'], line=d['line'], valid=not d.get('bad') and d.get('dead') is None and not d.get('error'), total=d.get('total'), picks=rows, part=os.path.basename(path))) + '\n')
                    out.flush()
                picks = []
                n += 1
                if n % 200 == 0:
                    print('%s: %d forms, %.0f forms/s' % (os.path.basename(path), n, n / (time.time() - t0)), flush=True)
            else:
                picks.append(json.loads(line))


def rows(part):
    done = set()
    if os.path.exists(OUT):
        done = {(r['task'], r['line']) for r in map(json.loads, open(OUT))}
    with open(OUT, 'a') as out:
        for w in WALKS[part]:
            form_rows(L.RANK + 'walks/' + w, done, out)


def loss(picks, w, name, variant):
    t = 0.0
    for p in picks:
        n = p['n'][name] if variant == 'forms' else p['o'][name]
        t += L.mix_bits(p['q'], w, n, p['inside'][name] and n > 0)
    return t


def fit_one(picks, name, variant):
    """Golden section over w, on the log-odds of w: the mean bits have one minimum in w."""
    lo, hi = -9.0, 6.0
    g = (math.sqrt(5) - 1) / 2

    def f(x):
        return loss(picks, 1 / (1 + math.exp(-x)), name, variant)
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = f(a), f(b)
    for _ in range(40):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = f(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = f(b)
    x = (lo + hi) / 2
    return 1 / (1 + math.exp(-x))


def fit():
    rows_ = [json.loads(x) for x in open(OUT)]
    held = set(L.held_tasks())
    assert not {r['task'] for r in rows_} & held
    out = dict(source='walks of the rank record, scope of all earlier forms; RULE forms; valid forms only', w={})
    for part, keep in (('test', lambda r: 'test' in r['part']), ('train', lambda r: 'train' in r['part'])):
        picks = [p for r in rows_ if r['valid'] and keep(r) for p in r['picks']]
        if not picks:
            continue
        der = [p for p in picks if p['derived']]
        base = sum(p['q'] for p in picks)
        res = dict(tasks=len({r['task'] for r in rows_ if keep(r)}), forms=sum(1 for r in rows_ if r['valid'] and keep(r)), picks=len(picks), derived_picks=len(der), bits_per_pick=round(base / len(picks), 4))
        for name in ('unread_later', 'unread_before', 'unread_so_far'):
            for variant in ('forms', 'options'):
                w = fit_one(picks, name, variant)
                res['%s:%s' % (name, variant)] = dict(w=round(w, 5), saved_per_pick=round((base - loss(picks, w, name, variant)) / len(picks), 4), saved_per_derived_pick=round((sum(p['q'] for p in der) - loss(der, w, name, variant)) / len(der), 4), inside_derived=round(sum(p['inside'][name] for p in der) / len(der), 4), median_n=sorted(p['n'][name] for p in der)[len(der) // 2])
        out['w'][part] = res
        print(part, json.dumps(res), flush=True)
    json.dump(out, open(HERE + 'fit.json', 'w'), indent=1)


if __name__ == '__main__':
    if sys.argv[1] == 'rows':
        rows('train' if '--train' in sys.argv else 'test')
    else:
        fit()
