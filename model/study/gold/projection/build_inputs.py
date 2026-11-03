"""Writes the inputs of a run in OUT (default trial/): lines.json (view-final text of each stem, OUT line included), base-rows.json (the start figures of
record from reread-kit/merged.jsonl, in the form gold_dagcut2_kit.entry gives), tasks.txt (one tier, heaviest first) and weights.json.

  python3 build_inputs.py [--out DIR] [--eval99 --less STEM,...] [STEM...]

--eval99 takes the 99 evaluation stems, less those of --less. A stem whose view-final text is not the text of its figures of record is left out and named.
"""
import glob, gzip, hashlib, json, os, sys

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
G = D + 'gold/gold-v3-dag-bits/'
VIEW = D + 'gold/gold-v3-combined-cut/view-final/'
args = sys.argv[1:]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trial')
less = set()
if '--out' in args:
    k = args.index('--out'); OUT = os.path.abspath(args[k + 1]); del args[k:k + 2]
if '--less' in args:
    k = args.index('--less'); less = set(args[k + 1].split(',')); del args[k:k + 2]
if '--eval99' in args:
    args.remove('--eval99')
    args += open(D + 'features-worker/arm/eval-tasks.txt').read().split()
stems = [t for t in dict.fromkeys(args) if t not in less]
merged = {json.loads(l)['task']: json.loads(l) for l in open(G + 'reread-kit/merged.jsonl')}
cpu = {}
for p in glob.glob(G + 'pod-all/rows-*.jsonl') + glob.glob(G + 'reread-all/rows-*.jsonl'):
    for l in open(p):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get('task') in stems and r.get('cpu') is not None:
            cpu[r['task']] = r['cpu']
lines, base = {}, {}
for t in list(stems):
    ls = [x for x in json.loads(gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt').readline())['gold_sexp'].splitlines() if x.strip()]
    sha = hashlib.sha256('\n'.join(ls).encode()).hexdigest()[:16]
    if sha != merged[t]['base_sha']:
        print('left out, view-final text is not the text of the figures of record:', t)
        continue
    lines[t] = ls
    base[t] = dict(base_sha=sha, forms=[[f['line'], f['bits'], f['status'], f.get('scope_sha'), False] for f in merged[t]['forms']])
os.makedirs(OUT, exist_ok=True)
json.dump(lines, open(OUT + '/lines.json', 'w'))
json.dump(base, open(OUT + '/base-rows.json', 'w'))
stems = [t for t in stems if t in lines]
json.dump({t: cpu.get(t, 60.0) for t in stems}, open(OUT + '/weights.json', 'w'))
open(OUT + '/tasks.txt', 'w').write('\n'.join(sorted(stems, key=lambda t: -cpu.get(t, 60.0))) + '\n')
print('wrote', OUT, len(stems), 'stems; pod cpu of their start text, s: sum %.0f, largest %s' % (sum(cpu.get(t, 60.0) for t in stems), sorted(((round(cpu.get(t, 60.0)), t) for t in stems), reverse=True)[:6]))
