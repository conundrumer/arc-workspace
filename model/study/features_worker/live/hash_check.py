"""Do the row hashes in a node record equal the hashes of the same gold table replayed in another session?"""
import collections, json, os, subprocess, sys, time, glob
A = os.path.dirname(os.path.abspath(__file__)) + '/../policy2/arm'
sys.path.insert(0, A + '/bundle-code/model/study/sampler')
import superdag as D
from live import S, M
import live
STORE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points-t'
REC = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/runs/kaggle-v5/record'
LAB = os.path.dirname(os.path.abspath(__file__)) + '/labels'
sampler = live.Sampler('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/models')
index = collections.defaultdict(list)
for e in os.scandir(STORE):
    index[e.name[:8]].append(e.path)
same = diff = 0; cap = 0
for lab in sorted(glob.glob(LAB + '/*.json'))[:12]:
    v = json.load(open(lab)); task = v['task']; c = v['best']
    want = {h['token']: h for h in v['hits'] if any(cc == c for cc, _ in h['hit'])}
    if not want:
        continue
    text = next(open(d + '/gold.arclog').read() for d in index[task] if json.load(open(d + '/point.json'))['case'] == c)
    sess, d, _ = D.session_of(task)
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
    forms = [str(f) for f in text.strip().split('\n') if not f.startswith('(OUT')]
    run.collect = []; run.scope(forms); gold = collections.defaultdict(set)
    for i, ct in enumerate(run.collect):
        for _, j in D.relation_tables(ct):
            try:
                gold[i].add(json.dumps(D.table_key(S.parse_table(D.OneTable(ct, j)))[1]))
            except M.Fail:
                pass
    src = subprocess.Popen(['zstd', '-dcq', glob.glob(f'{REC}/{task}*.zst')[0]], stdout=subprocess.PIPE)
    for raw in src.stdout:
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        h = want.get(r['token'])
        if h:
            ok = any(json.dumps(r['examples']) in gold[i] for cc, i in h['hit'] if cc == c)
            same += ok; diff += not ok
            cap += any(e[2] > 2000 for e in r['examples'])
print('hit nodes with equal row hashes', same, 'unequal', diff, 'over 2000 rows', cap)
