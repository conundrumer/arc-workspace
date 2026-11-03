"""Reads second-order rows: gold signal against gold plumbing, and gold plumbing against junk plumbing. Plumbing is a RULE that reads one table, with no negation and no union. Signal is every other seeded RULE or INIT. Medians and AUC pooled over tables, since one task rarely holds both."""
import glob, json, os, statistics as st
H = os.path.dirname(os.path.abspath(__file__))
R = []
for f in glob.glob(H + '/second-*.jsonl'):
    for l in open(f):
        try:
            R.append(json.loads(l))
        except ValueError:
            pass
pl = lambda r: r['kind'] == 'RULE' and r['distinct'] <= 1 and not r['negated'] and not r['union']
G = [r for r in R if r['seeded'] and r['kind'] in ('RULE', 'INIT')]
gp = [r for r in G if pl(r)]
gs = [r for r in G if not pl(r)]
jp = [r for r in R if not r['gold'] and pl(r)]
js = [r for r in R if not r['gold'] and r['kind'] in ('RULE', 'INIT') and not pl(r)]
print('tasks', len({r['task'] for r in R}), 'rows', len(R), 'gold plumbing', len(gp), 'gold signal', len(gs), 'junk plumbing', len(jp), 'junk other', len(js))


def auc(a, b):
    a, b = sorted(a), sorted(b)
    if not a or not b:
        return None
    s, lo, hi = 0.0, 0, 0
    for x in a:
        while lo < len(b) and b[lo] < x:
            lo += 1
        while hi < len(b) and b[hi] <= x:
            hi += 1
        s += lo + (hi - lo) / 2
    return round(s / (len(a) * len(b)), 3)


def med(v):
    return round(st.median(v), 3) if v else None


F = ['gain', 'parent_gain', 'reader_gain', 'lift', 'step', 'share', 'share_spread', 'label_overlap', 'readers', 'parents', 'columns']
print('%-14s %8s %8s %8s %8s | %7s %7s %7s' % ('fact', 'g plumb', 'g signal', 'j plumb', 'j other', 'gp-gs', 'gp-jp', 'gs-js'))
for k in F:
    a, b, c, d = ([r[k] for r in x if r.get(k) is not None] for x in (gp, gs, jp, js))
    print('%-14s %8s %8s %8s %8s | %7s %7s %7s   n %d %d' % (k, med(a), med(b), med(c), med(d), auc(a, b), auc(a, c), auc(b, d), len(a), len(b)))
for name, x in (('gold plumbing', gp), ('gold signal', gs), ('junk plumbing', jp), ('junk other', js)):
    n = max(len(x), 1)
    print(name, 'gain above 0 %.3f, lift above 0 %.3f, no reader %.3f' % (sum((r['gain'] or 0) > 0 for r in x) / n, sum((r['lift'] or 0) > 0 for r in x) / n, sum(r['readers'] == 0 for r in x) / n))
