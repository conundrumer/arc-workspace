"""Recall of the wrapper run on the current gold and on round 50, by arm and kind, on the worker path. It reads partial output: a task counts once its log has an `end:` line.

  python3 -I search_wrapper_report.py POINTS.json POINTS2.json OUT_FOLDER

POINTS.json is the gold of ARC_GOLD, POINTS2.json that of SEARCH_GOLD2. The cover file's `gold` is a form's index in its program, in gold's non-OUT lines.
"""
import collections
import glob
import json
import os
import sys


def kinds(path):
    """{task: [kind of each gold line that is a form]}"""
    return {x['task']: [ln.split()[0][1:] for ln in x['gold_sexp'].strip().split('\n') if ln.strip() and not ln.startswith('(OUT')] for x in json.load(open(path))}


def main(points, points2, out):
    G, G2 = kinds(points), kinds(points2)
    rows = collections.defaultdict(lambda: collections.Counter())
    for d in sorted(glob.glob(out + '/*/*')):
        arm, t = d.split('/')[-2:]
        log = f'{d}/work/{t}.log'
        if not os.path.exists(log) or not any(x.startswith('end:') for x in open(log, errors='replace')):
            rows[arm]['open'] += 1
            continue
        r = rows[arm]
        r['tasks'] += 1
        for suffix, gold, tag in (('cover', G, 'now'), ('cover2', G2, 'r50')):
            f = f'{d}/work/{t}.out.jsonl.{suffix}'
            got = {json.loads(x)['gold'] for x in open(f) if x.strip()} if os.path.exists(f) else set()
            forms = gold.get(t, [])
            r[tag + ' all'] += len(forms)
            r[tag + ' whole'] += bool(forms) and len(got) >= len(forms)
            for g in got:
                kind = forms[g] if isinstance(g, int) and g < len(forms) else 'other'
                r[f"{tag} {'DET' if kind in ('DET', 'RIGID_DET') else 'non-DET'}"] += 1
        c = [x for x in open(f'{d}/work/{t}.log', errors='replace') if x.startswith('counts ')]
        r['draws'] += int(json.loads(c[-1][7:]).get('search:visits', 0)) if c else 0
    print('| arm | tasks | open | non-DET now | DET now | of | whole | non-DET r50 | DET r50 | of | whole | visits |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for a, r in sorted(rows.items()):
        print(f"| {a} | {r['tasks']} | {r['open']} | {r['now non-DET']} | {r['now DET']} | {r['now all']} | {r['now whole']} | {r['r50 non-DET']} | {r['r50 DET']} | {r['r50 all']} | {r['r50 whole']} | {r['draws']} |")


main(*sys.argv[1:4])
