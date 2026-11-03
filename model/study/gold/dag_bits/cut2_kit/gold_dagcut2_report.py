"""Report on tool 2 version 2 rows (plain python3, no engine).

  python3 gold_dagcut2_report.py ROWS.jsonl... [--tiers TASKS.txt] [--v1 V1ROWS.jsonl...]

Reads the last row of each stem (by task, stage dagcut2) from every file; ROWS may be a glob in quotes. `before` and `after` read the working text W by or_q.walk; `after` is the last commit. Prints, by tier (a blank line in TASKS.txt separates tiers) and in all:
  stems, finished, skipped, at a cap (late, or an error), stems with a commit
  worst forms that fall (before.worst against after.worst), the fall's median, mean, maximum and total
  stems kept and steps kept (steps up to the last commit); steps tentative and dropped (after the last commit)
  falls by the shape of the committed steps
  program_fail by reason; rows_differ and rows_columns over the landed steps; start forms read again; forms read again with the field order of the tokens
  the replay of the step chains at margins 0, 1, 2, 3, 4, 5 (stems kept, steps kept, total fall); the chains stop after the run's tentative limit, so a margin under the run's can show fewer steps than a run at that margin would
With --v1: the stems that landed in the first pass rows, with their worst forms there and here.
"""
import collections, glob, json, statistics, sys

argv = sys.argv[1:]
tiers_path = argv[argv.index('--tiers') + 1] if '--tiers' in argv else None
v1 = []
if '--v1' in argv:
    k = argv.index('--v1')
    v1 = argv[k + 1:]
    argv = argv[:k]
if tiers_path:
    argv.remove('--tiers')
    argv.remove(tiers_path)
last = {}
for pat in argv:
    for p in glob.glob(pat):
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get('stage') == 'dagcut2' and 'task' in r:
                last[r['task']] = r
tiers = [x.split() for x in open(tiers_path).read().split('\n\n') if x.strip()] if tiers_path else []


def kept_steps(r):
    """The number of steps up to the last commit."""
    got = [k for k, s in enumerate(r.get('steps', [])) if s.get('committed')]
    return got[-1] + 1 if got else 0


def commit_falls(r):
    """(shape, fall) of each committed step, the fall from the state of the commit before."""
    base, out = r['before']['score'] if 'score' in r['before'] else r['before']['worst'], []
    for s in r.get('steps', []):
        if s.get('committed'):
            out.append((s['shape'], base - s['score']))
            base = s['score']
    return out


def replay(r, margin):
    """(committed steps, fall) of the chain at a margin."""
    b = (r['before']['undrawn'], r['before']['score'])
    got, last_k = 0, 0
    base = b
    for k, s in enumerate(r.get('steps', [])):
        new = (s['undrawn'], s['score'])
        if new[0] < base[0] or (new[0] == base[0] and base[1] - new[1] >= margin - 1e-6):
            base, last_k, got = new, k + 1, got + 1
    return last_k, b[1] - base[1]


def show(name, ts):
    rs = [last[t] for t in ts]
    ran = [r for r in rs if not r.get('skipped') and 'before' in r]
    capped = [r['task'] for r in ran if r.get('late') or r.get('error') or not r.get('finished')]
    kept = [r for r in ran if r.get('landed')]
    falls = [r['before']['worst'] - r['after']['worst'] for r in kept]
    steps = sum(len(r['steps']) for r in ran)
    keptn = sum(kept_steps(r) for r in ran)
    print('== %s: %d stems, %d finished, %d skipped, %d ran, %d at a cap or in error %s' % (name, len(rs), sum(1 for r in rs if r.get('finished')), len(rs) - len(ran), len(ran), len(capped), capped))
    print('   stems with a commit: %d | worst forms that fall: %d' % (len(kept), sum(1 for f in falls if f > 0.005)), end='')
    if falls:
        print(' | fall bits: median %.2f mean %.2f max %.2f total %.1f' % (statistics.median(falls), statistics.mean(falls), max(falls), sum(falls)))
    else:
        print()
    print('   steps landed %d: kept %d (up to the last commit), tentative and dropped %d' % (steps, keptn, steps - keptn))
    by = collections.defaultdict(list)
    for r in ran:
        for shape, f in commit_falls(r):
            by[shape].append(f)
    print('   falls by shape of the committed step: %s' % {k: (len(v), round(sum(v), 1)) for k, v in sorted(by.items())})
    print('   program_fail: %s' % dict(collections.Counter(r.get('program_fail') for r in kept)))
    allsteps = [s for r in ran for s in r.get('steps', [])]
    print('   rows_differ true: %d, rows_columns true: %d, of %d steps' % (sum(1 for s in allsteps if s.get('rows_differ')), sum(1 for s in allsteps if s.get('rows_columns')), len(allsteps)))
    print('   start forms read again: %d forms on %d stems | fields retried: %d, with bits: %d' % (sum(r.get('start_forms_read_again') or 0 for r in ran), sum(1 for r in ran if r.get('start_forms_read_again')), sum(r['counts'].get('fields retried', 0) for r in ran), sum(r['counts'].get('fields retried with bits', 0) for r in ran)))
    print('   cpu: %.1f s in all; %.1f s on stems with a commit' % (sum(r.get('cpu') or 0 for r in rs), sum(r.get('cpu') or 0 for r in kept)))
    print('   replay of the chains by margin (stems kept, steps kept, total fall):', end='')
    for m in (0, 1, 2, 3, 4, 5):
        got = [replay(r, m) for r in ran]
        print(' %d: %d, %d, %.1f |' % (m, sum(1 for k, _ in got if k), sum(k for k, _ in got), sum(f for _, f in got)), end='')
    print()
    for r in sorted(kept, key=lambda r: r['after']['worst'] - r['before']['worst'])[:8]:
        print('     %s %.2f -> %.2f (%s -> %s) steps %s committed %s' % (r['task'], r['before']['worst'], r['after']['worst'], r['before']['worst_status'], r['after']['worst_status'], [s['shape'] for s in r['steps']], [k for k, s in enumerate(r['steps']) if s['committed']]))


show('all', list(last))
for k, ts in enumerate(tiers):
    show('tier %d' % (k + 1), [t for t in ts if t in last])

if v1:
    old = {}
    for pat in v1:
        for p in glob.glob(pat):
            for l in open(p):
                try:
                    r = json.loads(l)
                except json.JSONDecodeError:
                    continue
                if 'task' in r and 'before' in r:
                    old[r['task']] = r
    print('== against the first pass rows: stems that landed there (their text may differ from lines.json: 29 stems of the 99)')
    both = [t for t in old if old[t].get('steps') and t in last and 'before' in last[t]]
    print('   landed in the first pass: %d, of which run here: %d, with a commit here: %d' % (sum(1 for r in old.values() if r.get('steps')), len(both), sum(1 for t in both if last[t].get('landed'))))
    for t in sorted(both):
        a, b = old[t], last[t]
        print('   %s first pass %.2f -> %.2f (%d steps) | here %.2f -> %.2f (%d steps, commits %s) | cpu %s against %s' % (t, a['before']['worst'], a['after']['worst'], len(a['steps']), b['before']['worst'], b['after']['worst'], len(b['steps']), [k for k, s in enumerate(b['steps']) if s['committed']], a.get('cpu'), b.get('cpu')))
    here = [t for t in last if last[t].get('landed') and t not in old or t in old and last[t].get('landed') and not old[t].get('steps')]
    print('   committed here and not landed in the first pass: %s' % sorted(here))
