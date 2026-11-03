"""Sums the arrow rows and the replay rows written so far."""
import collections, glob, json, os, statistics as st
H = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for f in glob.glob(H + '/arrows-*.jsonl') for l in open(f)]
print('arrow tasks', len(rows))
if rows:
    C = sum(r['classes'] for r in rows)
    for name in ('all', 'without_chance'):
        x = [r[name] for r in rows]
        G, g = sum(a['gold'] for a in x), sum(a['gold_generators'] for a in x)
        lv = collections.Counter()
        for a in x:
            lv.update(a['gold_levels'])
        print(' ', name, 'generators / nodes %.3f, lone generators / generators %.3f, mutual merged / classes %.4f, median generators %.0f, covering edges per node %.2f, longest path median %.0f, below a generator median %.1f, gold that are generators %d/%d, gold levels %s' % (
            sum(a['generators'] for a in x) / sum(a['nodes'] for a in x), sum(a['generators_alone'] for a in x) / sum(a['generators'] for a in x), sum(a['mutual_merged'] for a in x) / C,
            st.median(a['generators'] for a in x), sum(a['covering_edges'] for a in x) / sum(a['nodes'] for a in x), st.median(a['longest_path'] for a in x), st.median(a['median_below_generator'] for a in x), g, G, sorted(lv.items())))
    print('  arrows per class %.2f, also seen with wrong examples %.3f' % (sum(r['arrows'] for r in rows) / C, sum(r['arrows_chance'] for r in rows) / sum(r['arrows'] for r in rows)))
    print('  families per task median %.0f, size median %.1f, largest %d, classes in a family %.3f, gold in a family %.3f' % (st.median(r['families'] for r in rows), st.median(r['family_median'] for r in rows), max(r['family_max'] for r in rows),
          sum(r['in_family'] for r in rows) / C, sum(r['gold_in_family'] for r in rows) / max(sum(r['gold_classes'] for r in rows), 1)))
    print('  projection lattice present %.3f' % (sum(r['lattice_have'] for r in rows) / sum(r['lattice_total'] for r in rows)))
out = collections.defaultdict(dict)
for f in glob.glob(H + '/q3/out/*-k6/*.json'):
    d = json.load(open(f))
    out[f.split('/')[-2]][d['task']] = d
credit = out.pop('credit-k6', {})
both = set.intersection(*(set(v) for v in out.values())) if len(out) > 1 else set()
print('replay tasks with every rule', len(both))
for rule, by in sorted(out.items()):
    c = collections.defaultdict(list)
    forms = 0
    for t in both:
        d = by[t]
        forms = max(forms, d['forms'])
        for r in d['rows']:
            b = '1' if r['parents'] == 1 else '2' if r['parents'] == 2 else '3+'
            c[b].append((r['hold'] / max(d['visits'], 1), r['by_class'] / max(d['visits'], 1), r['hold'] > 0, r['by_class'] > 0))
    print(' ', rule, 'median forms', st.median(by[t]['forms'] for t in both) if both else 0, {b: dict(forms=len(v), hold=round(st.mean(x[0] for x in v), 4), by_class=round(st.mean(x[1] for x in v), 4), any=sum(x[2] for x in v), any_class=sum(x[3] for x in v)) for b, v in sorted(c.items())})
c = collections.defaultdict(list)
for t, d in credit.items():
    for r in d['rows']:
        b = '1' if r['parents'] == 1 else '2' if r['parents'] == 2 else '3+'
        c[b].append((r['hold'] / max(d['visits'], 1), r['by_arrow'] / max(d['visits'], 1), r['hold'] > 0, r['by_arrow'] > 0))
print('credit by one arrow, tasks', len(credit), {b: dict(forms=len(v), hold=round(st.mean(x[0] for x in v), 4), by_arrow=round(st.mean(x[1] for x in v), 4), any=sum(x[2] for x in v), any_arrow=sum(x[3] for x in v)) for b, v in sorted(c.items())})
