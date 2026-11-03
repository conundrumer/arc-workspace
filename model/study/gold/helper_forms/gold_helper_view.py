"""Builds the revision's files from the stem rows in pod-out: corpus-view/, points-eval.json, helpers.json, and prints the count. The view is built beside the old one and swapped in by rename.

  gold_helper_view.py
"""
import glob, gzip, json, os, shutil
D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
CORPUS = D + 'sampler/corpus-v3mix/'
rows = {}
for f in sorted(glob.glob('pod-out/rows-*.jsonl')) + sorted(glob.glob('mac-out/rows-*.jsonl')) + sorted(glob.glob('round-out/rows-*.jsonl'), key=os.path.getmtime):
    for l in open(f):
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        rows[r['task']] = r
crossing = json.load(open('crossing.json'))
for f in sorted(glob.glob('round-out/crossing-*.json'), key=os.path.getmtime):
    crossing.update(json.load(open(f)))
concept = json.load(open('concept-cases.json'))
good = {t: r for t, r in rows.items() if r.get('program') and r.get('applied')}
tmp = 'corpus-view.new'
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)
helpers = []
for t in sorted(os.listdir(CORPUS)):
    if not os.path.isdir(CORPUS + t):
        continue
    if t not in good:
        os.symlink(CORPUS + t, os.path.join(tmp, t))
        continue
    r = good[t]
    os.makedirs(os.path.join(tmp, t))
    with gzip.open(CORPUS + t + '/pairs.jsonl.gz', 'rt') as src, gzip.open(os.path.join(tmp, t, 'pairs.jsonl.gz'), 'wt') as dst:
        first = json.loads(src.readline())
        first.update(gold_sexp=r['program'], helper_forms=True)
        first['case'] = concept[t]
        dst.write(json.dumps(first) + '\n')
        shutil.copyfileobj(src, dst)
    shift = 0
    cuts = {c['line']: c['cuts'] for c in crossing[t]}
    for line in sorted(r['applied']):
        n = len(cuts[line])
        helpers += [dict(task=t, line=line + shift + k, source_line=line, last=k == n - 1) for k in range(n)]
        shift += n - 1
json.dump(helpers, open('helpers.json.new', 'w'))
os.replace('helpers.json.new', 'helpers.json')
ev = open(D + 'features-worker/arm/eval-tasks.txt').read().split()
pts = []
lines = json.load(open('lines.json'))
for t in ev:
    pts.append(dict(task=t, gold_sexp=good[t]['program'] if t in good else '\n'.join(lines[t])))
json.dump(pts, open('points-eval.json.new', 'w'))
os.replace('points-eval.json.new', 'points-eval.json')
if os.path.exists('corpus-view'):
    os.rename('corpus-view', 'corpus-view.old')
os.rename(tmp, 'corpus-view')
shutil.rmtree('corpus-view.old', ignore_errors=True)
print(len(rows), 'stems read', len(good), 'rewritten', len(helpers), 'helper rows')
