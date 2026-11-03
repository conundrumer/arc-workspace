"""Where each gold form stands at the end of a Kaggle record: covered; frontier (every gold form it reads is covered); or blocked (one it reads is not). For a frontier form, how many written draws had all the forms it needs in scope. Only draws that wrote a node show their scope, so counts are lower bounds. Streams one file per task to front/; a rerun skips finished tasks.

  frontier.py RECORD_DIR K N
"""
import collections, glob, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
STORE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points-t'
OUT = HERE + '/front'
os.makedirs(OUT, exist_ok=True)
N = re.compile(r'&[A-Za-z_]\w*')
SC = re.compile(r'"scope": ?\[([^\]]*)\]')
CL = re.compile(r'"clause": ?"\(\w+ &f(\d+)')
TK = re.compile(r'"token": ?"(\d+)"')
index = collections.defaultdict(list)
for e in os.scandir(STORE):
    index[e.name[:8]].append(e.path)


def gold(task, case):
    for d in index[task]:
        if json.load(open(d + '/point.json'))['case'] == case:
            lines = [l for l in open(d + '/gold.arclog').read().strip().split('\n') if not l.startswith('(OUT')]
            dep, reads = {}, []
            heads = [l.split()[1] for l in lines]
            at = {h: i for i, h in enumerate(heads)}
            for l, h in zip(lines, heads):
                r = {at[m] for m in N.findall(l) if m in at and at[m] < at[h]}
                dep[at[h]] = 1 + max((dep[x] for x in r), default=0)
                reads.append(r)
            return [(dep[i], l[1:l.index(' ')], reads[i]) for i, l in enumerate(lines)]


rec, K, M = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = sorted(glob.glob(rec + '/*.zst'))[K::M]
t0 = time.time()
for n, f in enumerate(files, 1):
    task = os.path.basename(f)[:8]
    o = f'{OUT}/{task}.json'
    lab = f'{HERE}/labels/{task}.json'
    if os.path.exists(o) or not os.path.exists(lab):
        continue
    v = json.load(open(lab)); c = v['best']
    forms = gold(task, c) if c else None
    if not forms:
        continue
    hit = collections.defaultdict(set)  # gold index -> tokens
    for h in v['hits']:
        for cc, i in h['hit']:
            if cc == c:
                hit[i].add(h['token'])
    tok = {t for s in hit.values() for t in s}
    form_of, scopes = {}, []
    src = subprocess.Popen(['zstd', '-dcq', f], stdout=subprocess.PIPE)
    for raw in src.stdout:
        s = raw.decode('utf8', 'ignore')
        m, q, k = TK.search(s), SC.search(s), CL.search(s)
        if m and m[1] in tok and k:
            form_of[m[1]] = k[1]
        if q and q[1].strip():
            scopes.append({x.strip().strip('"') for x in q[1].split(',')})
    out = []
    for i, (d, kind, r) in enumerate(forms):
        st = 'covered' if i in hit else ('blocked' if any(x not in hit for x in r) else 'frontier')
        seen = 0
        if st == 'frontier' and r:
            seen = sum(all(hit[x] & sc for x in r) for sc in scopes)  # a scope lists node tokens
        out.append(dict(i=i, depth=d, kind=kind, state=st, nreads=len(r), scopes=seen))
    json.dump(dict(task=task, case=c, draws_seen=len(scopes), forms=out), open(o + '.new', 'w')); os.replace(o + '.new', o)
    print(f'{n}/{len(files)} {task} scopes {len(scopes)} {collections.Counter(x["state"] for x in out)} | {time.time() - t0:.0f} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
