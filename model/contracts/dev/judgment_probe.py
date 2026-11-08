"""Dev labeling layer: can a learner, from a table's features at the task's own examples alone, predict the table's novelty (novelty.py) and
its relevance (relevance.py), on tasks it did not train on? Not model input; the features it reads are.

    python judgment_probe.py OUT_DIR

Rows: each table with a judgment. Input: a readout of the table's features at the task's own examples (the base record of
OUT_DIR/<task>.worlds.jsonl). Each key's identity tokens become their kinds, C for a column and T for another table, which gives its template.
Per template and example, the numbers and bools give their least, greatest and mean values and their count, and a category gives the count
of its distinct values and the share of each value; over the examples (the train examples alone for a feature of the train output), each of
those gives its mean and whether it is the same at every example. A static feature (provenance, dependence) is read at one example.

The feature sets: the row features, the row features without those that read the train output, the static features, and every feature.
Learner: gradient-boosted regression trees over 6 task folds and 3 seeds, each task weighing one. Scores on the held-out tasks: the Spearman
correlation with the judgment, and the AUC for the judgment at or above its median, or above it where the median is its least value.
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import analyze as A  # noqa: E402
import jsonl as J  # noqa: E402
import schema as S  # noqa: E402

TOK = re.compile('(?:\\w+\\.)?⟨c:[^⟩]*⟩|⟨t:[^⟩]*⟩')


def template(k):
    return TOK.sub(lambda m: 'T' if m[0].startswith('⟨t') else 'C', k)


def group(feat):
    if S.DEPENDENCE.search(feat):
        return 'dependence'
    if feat.endswith(S.PROVENANCE) or S.TABLE_PROVENANCE.match(feat):
        return 'provenance'
    return 'rows'


def readout(feats_by_example, t, own, train):
    """({readout feature: value}, {template: group}) of table t, as the module's docstring gives."""
    per_ex, groups = {}, {}
    for e in own:
        g = defaultdict(list)
        for k, v in feats_by_example[e].items():
            owner, _, feat = k.partition('|')
            if owner != t or feat.endswith(' describe'):
                continue
            tp = template(feat)
            g[tp].append(v)
            gr = group(feat)
            if gr != 'rows' or tp not in groups:
                groups[tp] = gr
        per_ex[e] = g
    out = {}
    for tp in {tp for g in per_ex.values() for tp in g}:
        exs = [e for e in (train if A.is_output(tp) else own) if tp in per_ex[e]]
        if groups[tp] != 'rows':
            exs = exs[:1]
        stats, proportions = defaultdict(list), defaultdict(float)
        for e in exs:
            vs = [v for v in per_ex[e][tp] if v is not None]
            nums = [float(v) for v in vs if isinstance(v, (bool, int, float))]
            cats = [template(v) if isinstance(v, str) else repr(v) for v in vs if not isinstance(v, (bool, int, float))]
            if nums:
                stats['min'].append(min(nums)); stats['max'].append(max(nums)); stats['mean'].append(sum(nums) / len(nums))
                stats['count'].append(len(nums))
            if cats:
                stats['distinct'].append(len(set(cats)))
                for c, n in Counter(cats).items():
                    shares[c] += n / len(cats) / len(exs)
        for a, xs in stats.items():
            out['%s | %s mean' % (tp, a)] = sum(xs) / len(xs)
            if len(xs) > 1:
                out['%s | %s constant' % (tp, a)] = float(len(set(xs)) == 1)
        for c, sh in shares.items():
            out['%s = %s | share mean' % (tp, c)] = sh
    return out, groups


def judgments(path, key):
    out = {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        for t in r['tables']:
            if t.get('status') == 'tested':
                out[(r['task'], t['t'])] = t[key]
    return out


def readouts(out_dir, keys):
    rows = {}
    for task in sorted({k[0] for k in keys}):
        base = next((r for r in J.records(Path(out_dir) / (task + '.worlds.jsonl')) if r['id'] == 'base'), None)
        if base is None:
            continue
        own = sorted(base['examples'])
        train = [e for e in own if e.startswith('train/')]
        feats = {e: base['examples'][e]['features'] for e in own}
        for tk, t in keys:
            if tk == task:
                rows[(task, t)] = readout(feats, t, own, train)
    return rows


def folds(g, seed):
    tasks = sorted(set(g))
    fold = {t: i % 6 for i, t in enumerate(random.Random(seed).sample(tasks, len(tasks)))}
    return np.array([fold[t] for t in g])


def probe(lab, rd, label):
    from scipy.stats import spearmanr
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.metrics import roc_auc_score
    keys = [k for k in lab if k in rd]
    groups = {}
    for k in keys:
        groups.update(rd[k][1])
    seen = Counter(f for k in keys for f in rd[k][0])
    names = sorted(f for f, c in seen.items() if c >= 10)
    tp = lambda f: f.split(' | ')[0].split(' = ')[0]
    sets = {'row features': [f for f in names if groups.get(tp(f)) == 'rows'],
            'row features, no train output': [f for f in names if groups.get(tp(f)) == 'rows' and not A.is_output(tp(f))],
            'static features': [f for f in names if groups.get(tp(f)) in ('provenance', 'dependence')],
            'every feature': names}
    y = np.array([lab[k] for k in keys])
    g = np.array([k[0] for k in keys])
    n = Counter(g)
    w = np.array([1.0 / n[t] for t in g])
    med = np.median(y)
    high = y > med if med == y.min() else y >= med
    print('\n%s: %d tables, %d tasks; judgment median %.2f, mean %.2f' % (label, len(keys), len(n), med, y.mean()), flush=True)
    for sname, cols in sets.items():
        X = np.array([[rd[k][0].get(f, np.nan) for f in cols] for k in keys], dtype=float)
        rhos, aucs, imp = [], [], Counter()
        for seed in range(3):
            fold = folds(g, seed)
            p = np.zeros(len(y))
            for f in range(6):
                tr, te = fold != f, fold == f
                c = np.flatnonzero((~np.isnan(X[tr])).any(axis=0))
                m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=3, random_state=seed).fit(X[tr][:, c], y[tr], sample_weight=w[tr])
                p[te] = m.predict(X[te][:, c])
                for pred in m._predictors:
                    for node in pred[0].nodes:
                        if not node['is_leaf']:
                            imp[cols[c[node['feature_idx']]]] += node['gain']
            rhos.append(spearmanr(y, p).correlation)
            aucs.append(roc_auc_score(high, p, sample_weight=w) if 0 < high.sum() < len(y) else float('nan'))
        print('  %-32s %4d features: Spearman %s; AUC %s' % (sname, len(cols), ' '.join('%.2f' % r for r in rhos), ' '.join('%.2f' % a for a in aucs)), flush=True)
        tot = sum(imp.values()) or 1
        for f, v in imp.most_common(4):
            print('      %5.1f%%  %s' % (100 * v / tot, f[:110]), flush=True)


def main(out_dir):
    nov = judgments(Path(out_dir) / 'novelty.jsonl', 'novelty')
    rel = judgments(Path(out_dir) / 'relevance.jsonl', 'relevance')
    rd = readouts(out_dir, set(nov) | set(rel))
    probe(nov, rd, 'novelty')
    probe(rel, rd, 'relevance')


if __name__ == '__main__':
    main(sys.argv[1])
