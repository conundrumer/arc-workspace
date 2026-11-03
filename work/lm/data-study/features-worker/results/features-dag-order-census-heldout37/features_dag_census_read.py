#!/usr/bin/env python
"""Reads the census rows of a folder as they stand, finished or partial: writes form-bits.tsv, part3.json and partial.md there.

  python features_dag_census_read.py [DIR] [--revision NAME] [--resamples 10000]

form-bits.tsv has one row per form and scope, with the bits of the written order, the canonical order and the random orders.
part3.json compares bits per relation pick on written order with the mean over topological orders, on RULE forms with the parents scope. It streams per-pick-dag*.tsv and census-dag*.jsonl, plain or .zst. Intervals are 95%, from resamples of tasks.
"""
import argparse
import collections
import glob
import json
import math
import os
import random
import statistics
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS_BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/census-base.jsonl'
BASE_REVISION = 'gold-v3-helper-forms-a036da074-base'


def lines_of(path):
    if path.endswith('.zst'):
        p = subprocess.Popen(['zstd', '-dc', path], stdout=subprocess.PIPE, text=True)
        yield from p.stdout
        p.wait()
    else:
        with open(path) as f:
            yield from f


JOIN = False  # read the rows of mode join in place of those of mode binder


def rows_of(d, stem, ext):
    return sorted(p for p in glob.glob(os.path.join(d, stem + '*' + ext + '*')) if ('-join' in os.path.basename(p)) == JOIN)


def bad(r):
    return bool(r.get('error') or r.get('bad') or r.get('dead') or r.get('left'))


def why_refused(r):
    if r.get('error'):
        return 'error: ' + r['error'][:90]
    if r.get('dead'):
        return 'dead: ' + r['dead'][:90]
    if r.get('bad'):
        return 'bad: ' + r['bad'][0][:90]
    return 'left %s tokens' % r.get('left')


def read_forms(d, revision):
    """(task, line, scope) -> order -> a row with total, parts split, refusal."""
    forms = collections.defaultdict(dict)
    for p in rows_of(d, 'census-dag', '.jsonl'):
        for line in lines_of(p):
            r = json.loads(line)
            if r['revision'] != revision:
                continue
            forms[r['task'], r['line'], r['scope']][r['order']] = dict(total=None if bad(r) else r['total'], kind=r['kind'], why=why_refused(r) if bad(r) else None, n_orders=r.get('n_orders'),
                                                                       topological=r.get('written_topological'), match=r.get('match'), nscope=r['nscope'], same_clause=r.get('same_clause'))
    return forms


def read_picks(d, revision):
    """(task, line) -> order -> [(option, phase, alive, bits, ok)] of RULE forms with the parents scope."""
    picks = collections.defaultdict(lambda: collections.defaultdict(dict))
    for p in rows_of(d, 'per-pick-dag', '.tsv'):
        head = None
        for line in lines_of(p):
            cells = line.rstrip('\n').split('\t')
            if head is None:
                head = {c: i for i, c in enumerate(cells)}
                continue
            if cells[head['revision']] != revision or cells[head['kind']] != 'RULE' or cells[head['scope']] != 'parents':
                continue
            key = cells[head['task']], int(cells[head['line']])
            picks[key][cells[head['order']]][int(cells[head['pick']])] = (cells[head['option']], cells[head['phase']], cells[head['gold_alive']] == '1', float(cells[head['bits']]), cells[head['form_ok']] == '1')
    return picks


def boot(per_task, fn, n, seed=0):
    """(point, low, high) of fn over the sums of resampled tasks. per_task maps a task to a list of numbers that add."""
    tasks = sorted(per_task)
    rng = random.Random(seed)
    size = len(next(iter(per_task.values())))
    got = []
    for _ in range(n):
        total = [0.0] * size
        for _ in tasks:
            row = per_task[tasks[rng.randrange(len(tasks))]]
            for i in range(size):
                total[i] += row[i]
        got.append(fn(total))
    got.sort()
    total = [sum(per_task[t][i] for t in tasks) for i in range(size)]
    return fn(total), got[int(.025 * n)], got[int(.975 * n)]


def part3(picks, n):
    arms = {'random topological orders, scope and body': [o for o in {x for f in picks.values() for x in f} if o.startswith('seed-')],
            'random topological orders, body only': [o for o in {x for f in picks.values() for x in f} if o.startswith('body-seed-')],
            'canonical order, scope and body': ['canonical']}
    out = {}
    valid = {}
    for key, orders in picks.items():
        w = orders.get('written')
        if w and all(x[4] for x in w.values()):
            valid[key] = w
    out['forms'] = len(valid)
    out['tasks'] = len({k[0] for k in valid})
    out['written_picks'] = sum(len(v) for v in valid.values())
    out['written_alive_picks'] = sum(sum(x[2] for x in v.values()) for v in valid.values())
    for name, names in arms.items():
        per = collections.defaultdict(lambda: [0.0] * 10)  # written alive bits, picks; order's alive bits, picks; written all bits, picks; order's all bits, picks; paired bits, paired picks
        forms = refused = kept = single = 0
        for key, w in valid.items():
            walks = [picks[key][o] for o in names if o in picks[key]]
            good = [o for o in walks if all(x[4] for x in o.values())]
            refused += len(walks) - len(good)
            if not good:
                continue
            forms += 1
            kept += len(good)
            alive_w = [x for x in w.values() if x[2]]
            row = per[key[0]]
            row[0] += sum(x[3] for x in alive_w)
            row[1] += len(alive_w)
            row[2] += statistics.fmean(sum(x[3] for x in o.values() if x[2]) for o in good)
            row[3] += statistics.fmean(sum(1 for x in o.values() if x[2]) for o in good)
            row[4] += sum(x[3] for x in w.values())
            row[5] += len(w)
            row[6] += statistics.fmean(sum(x[3] for x in o.values()) for o in good)
            row[7] += statistics.fmean(len(o) for o in good)
            index = [{(x[0], x[1]): x[3] for x in o.values()} for o in good]
            for x in alive_w:
                got = [ix[x[0], x[1]] for ix in index if (x[0], x[1]) in ix]
                if got:
                    row[8] += statistics.fmean(got)
                    row[9] += 1
        if not per:
            continue
        ratio = lambda a, b: (lambda t: t[a] / t[b] if t[b] else float('nan'))  # noqa: E731
        diff = lambda a, b, c, e: (lambda t: t[a] / t[b] - t[c] / t[e] if t[b] and t[e] else float('nan'))  # noqa: E731
        share = lambda t: (t[0] / t[1] - t[2] / t[3]) / (t[0] / t[1]) if t[1] and t[3] else float('nan')  # noqa: E731
        paired_diff = lambda t: t[0] / t[1] - t[8] / t[9] if t[1] and t[9] else float('nan')  # noqa: E731
        out[name] = dict(forms=forms, orders_kept=kept, orders_refused=refused, tasks=len(per),
                         alive_written=boot(per, ratio(0, 1), n), alive_order=boot(per, ratio(2, 3), n), alive_written_minus_order=boot(per, diff(0, 1, 2, 3), n), alive_share_of_written=boot(per, share, n),
                         all_written=boot(per, ratio(4, 5), n), all_order=boot(per, ratio(6, 7), n), all_written_minus_order=boot(per, diff(4, 5, 6, 7), n),
                         paired_order_bits_at_written_alive_picks=boot(per, ratio(8, 9), n), paired_written_minus_order=boot(per, paired_diff, n),
                         picks_alive_written=sum(r[1] for r in per.values()), picks_alive_order=sum(r[3] for r in per.values()))
    return out


def form_table(d, forms, tail=''):
    path = os.path.join(d, 'form-bits%s.tsv' % tail)
    cols = ('task', 'line', 'kind', 'scope', 'nscope', 'n_orders', 'written_topological', 'written', 'canonical', 'random_mean', 'random_sd', 'random_min', 'random_max', 'random_ok', 'random_refused', 'refusal')
    rows = []
    for (t, i, sc), orders in sorted(forms.items()):
        rnd = {k: v for k, v in orders.items() if k.startswith('seed-')}
        ok = [v['total'] for v in rnd.values() if v['total'] is not None]
        any_row = next(iter(orders.values()))
        w, c = orders.get('written', {}), orders.get('canonical', {})
        why = sorted({v['why'] for v in orders.values() if v['why']})
        rows.append((t, i, any_row['kind'], sc, any_row['nscope'], any_row['n_orders'], any_row['topological'], w.get('total'), c.get('total'), round(statistics.fmean(ok), 3) if ok else None,
                     round(statistics.pstdev(ok), 3) if ok else None, min(ok, default=None), max(ok, default=None), len(ok), len(rnd) - len(ok), why[0] if why else ''))
    with open(path, 'w') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join('' if x is None else str(x) for x in r) + '\n')
    return rows


def totals(forms):
    """Per kind and scope: forms with a written figure and random figures, mean written bits and mean of the forms' means."""
    out = {}
    g = collections.defaultdict(list)
    for (t, i, sc), orders in forms.items():
        w = orders.get('written', {}).get('total')
        rnd = [v['total'] for k, v in orders.items() if k.startswith('seed-') and v['total'] is not None]
        if w is not None and rnd:
            g[next(iter(orders.values()))['kind'], sc].append((t, w, statistics.fmean(rnd), orders.get('canonical', {}).get('total')))
    for k, v in sorted(g.items()):
        out['%s %s' % k] = dict(forms=len(v), written=round(statistics.fmean(x[1] for x in v), 2), random_mean=round(statistics.fmean(x[2] for x in v), 2),
                                canonical=round(statistics.fmean(x[3] for x in v if x[3] is not None), 2) if any(x[3] is not None for x in v) else None,
                                forms_written_at_or_under_mean=sum(x[1] <= x[2] + 1e-9 for x in v))
    return out


def census_check(forms, revision):
    if revision != BASE_REVISION or not os.path.exists(CENSUS_BASE):
        return None
    c, diff = collections.Counter(), []
    for line in open(CENSUS_BASE):
        r = json.loads(line)
        got = forms.get((r['task'], r['line'], r['scope']), {}).get('written')
        if got is None:
            continue
        if bad(r) or got['total'] is None:
            c['either has no figure'] += 1
            if bad(r) != (got['total'] is None):
                c['one has no figure'] += 1
                diff.append((r['task'], r['line'], r['scope'], None if bad(r) else r['total'], got['total']))
        elif abs(r['total'] - got['total']) < 0.011 and r['nscope'] == got['nscope']:
            c['equal'] += 1
        else:
            c['differ'] += 1
            diff.append((r['task'], r['line'], r['scope'], r['total'], got['total']))
    return dict(c), diff[:20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir', nargs='?', default=str(HERE))
    ap.add_argument('--revision', default=BASE_REVISION)
    ap.add_argument('--resamples', type=int, default=10000)
    ap.add_argument('--join', action='store_true', help='the rows of mode join; the outputs end in -join')
    a = ap.parse_args()
    global JOIN
    JOIN = a.join
    tail = '-join' if a.join else ''
    forms = read_forms(a.dir, a.revision)
    rows = form_table(a.dir, forms, tail)
    picks = read_picks(a.dir, a.revision)
    res = part3(picks, a.resamples)
    res['revision'] = a.revision
    res['totals'] = totals(forms)
    res['census_check'] = census_check(forms, a.revision)
    refused = collections.Counter()
    refused_forms = collections.defaultdict(set)
    for k, orders in forms.items():
        for o, v in orders.items():
            if v['why']:
                short = v['why'][:70]
                refused[short] += 1
                refused_forms[short].add('%s:%d' % k[:2])
    res['refused_orders'] = refused.most_common(30)
    res['refused_forms'] = {k: sorted(v)[:12] for k, v in refused_forms.items()}
    res['arm_rows'] = sum(len(v) for v in forms.values())
    res['clause_key_differs'] = sum(1 for v in forms.values() for x in v.values() if x['same_clause'] is False)
    res['init_match_false'] = sum(1 for v in forms.values() for x in v.values() if x['match'] is False)
    json.dump(res, open(os.path.join(a.dir, 'part3%s.json' % tail), 'w'), indent=1)
    with open(os.path.join(a.dir, 'partial%s.md' % tail), 'w') as f:
        f.write('# DAG order census: partial\n\nRevision %s, mode %s. %d rows of form and arm, over %d forms of scope and %d forms in the relation pick read. This file is rewritten by features_dag_census_read.py, and part3.json holds the same numbers.\n\n' % (
            a.revision, 'join' if a.join else 'binder', res['arm_rows'], len(rows), res['forms']))
        f.write('Written rows against census-base: %s\n\n' % (res['census_check'],))
        f.write('Written order, RULE, parents: %d forms, %d tasks, %d picks, %d picks where gold is alive.\n\n' % (res['forms'], res['tasks'], res['written_picks'], res['written_alive_picks']))
        for name in [k for k, v in res.items() if isinstance(v, dict) and 'alive_written' in v]:
            v = res[name]
            fmt = lambda x: '%.3f (%.3f to %.3f)' % tuple(x)  # noqa: E731
            f.write('## %s\n\n%d forms, %d tasks, %d orders kept, %d orders refused.\n\n' % (name, v['forms'], v['tasks'], v['orders_kept'], v['orders_refused']))
            f.write('- Bits per gold-alive pick: written %s, orders %s.\n- Written minus orders: %s. As a share of written: %s.\n- All picks: written %s, orders %s, written minus orders %s.\n- At the picks alive in written order: orders %s, written minus orders %s.\n\n' % (
                fmt(v['alive_written']), fmt(v['alive_order']), fmt(v['alive_written_minus_order']), fmt(v['alive_share_of_written']), fmt(v['all_written']), fmt(v['all_order']), fmt(v['all_written_minus_order']),
                fmt(v['paired_order_bits_at_written_alive_picks']), fmt(v['paired_written_minus_order'])))
        f.write('## Form totals\n\n| kind and scope | forms | written | random mean | canonical | forms with written at or under the random mean |\n|---|---|---|---|---|---|\n')
        for k, v in res['totals'].items():
            f.write('| %s | %d | %s | %s | %s | %d |\n' % (k, v['forms'], v['written'], v['random_mean'], v['canonical'], v['forms_written_at_or_under_mean']))
        f.write('\n## Orders refused\n\n%s\n' % json.dumps(res['refused_orders'], indent=0))
    print(open(os.path.join(a.dir, 'partial%s.md' % tail)).read())


if __name__ == '__main__':
    main()
