"""Report on tool 2 rows (plain python3, no engine).

  python3 gold_dagcut_report.py ROWS.jsonl... [--tiers TASKS.txt]

Reads the last row of each stem (by task) from every file. `before` and `after` are tool 1 figures on the same text rule, and the start text has had the written-order chain cuts, so a worst form that falls is a fall past what the written-order split gave. Prints, by tier (a blank line in TASKS.txt separates tiers) and in all:
  stems, finished, at a cap (late, or an error), landed stems
  worst forms that fall (after.worst under before.worst by more than 0.005), the fall's median, mean, maximum and total
  falls by the shape of the first landed step, and falls that hold a dag-split or dag-carry step
  worst forms whose before or after figure has status bound (a fall between two bounds is less sure than one between two exact figures)
  steps, and the rank of each landed split in the estimate
"""
import collections, glob, json, statistics, sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
tiers_path = sys.argv[sys.argv.index('--tiers') + 1] if '--tiers' in sys.argv else None
if tiers_path:
    args.remove(tiers_path)
last = {}
for pat in args:
    for p in glob.glob(pat):
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get('stage', 'dagcut') == 'dagcut' and 'task' in r:
                last[r['task']] = r
tiers = [x.split() for x in open(tiers_path).read().split('\n\n') if x.strip()] if tiers_path else []
groups = [('all', list(last))] + [('tier %d' % (k + 1), [t for t in ts if t in last]) for k, ts in enumerate(tiers)]
for name, ts in groups:
    rs = [last[t] for t in ts]
    fell = [r for r in rs if r.get('before') and r.get('after') and r['after']['worst'] < r['before']['worst'] - 0.005]
    falls = [r['before']['worst'] - r['after']['worst'] for r in fell]
    capped = [r['task'] for r in rs if r.get('late') or r.get('error') or not r.get('finished')]
    dag = [r for r in fell if any(s['shape'].startswith('dag-') for s in r['steps'])]
    first = collections.Counter(r['steps'][0]['shape'] for r in fell)
    allshapes = collections.Counter(s['shape'] for r in rs for s in r.get('steps', []))
    ranks = sorted(s['rank'] for r in rs for s in r.get('steps', []) if s.get('rank') is not None)
    bound_b = sum(1 for r in rs if r.get('before') and r['before'].get('worst_status') == 'bound')
    bound_a = sum(1 for r in fell if r['after'].get('worst_status') == 'bound' or r['before'].get('worst_status') == 'bound')
    print('== %s: %d stems, %d finished, %d landed, %d at a cap or in error %s' % (name, len(rs), sum(1 for r in rs if r.get('finished')), sum(1 for r in rs if r.get('landed')), len(capped), capped))
    print('   worst forms that fall: %d' % len(fell), end='')
    if falls:
        print(' | fall bits: median %.2f mean %.2f max %.2f total %.1f' % (statistics.median(falls), statistics.mean(falls), max(falls), sum(falls)))
    else:
        print()
    print('   of those, with a dag-split or dag-carry step: %d | first landed shape: %s' % (len(dag), dict(first)))
    print('   all landed steps by shape: %s' % dict(allshapes))
    print('   rank of landed splits in the estimate (sorted): %s' % ranks)
    print('   stems whose start worst form is bound: %d | falls where the before or after worst figure is bound: %d' % (bound_b, bound_a))
    for r in sorted(fell, key=lambda r: r['after']['worst'] - r['before']['worst'])[:8]:
        print('     %s %.2f -> %.2f (%s -> %s) steps %s' % (r['task'], r['before']['worst'], r['after']['worst'], r['before']['worst_status'], r['after']['worst_status'], [s['shape'] for s in r['steps']]))
