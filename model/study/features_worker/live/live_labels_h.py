"""Cover labels for node records from another session: which nodes hold a table of a gold program of the task. Row hashes compare only within a session, so this replays each gold case here and compares column types and the row count and row hash of each example, which cover every row of a table. Streams one file per task to labels/; a rerun skips finished tasks.

  live_labels.py K N NODES_FILE ...
"""
import collections, io, json, os, subprocess, sys, time
ARM = os.path.dirname(os.path.abspath(__file__)) + '/../policy2/arm'
sys.path.insert(0, ARM + '/bundle-code/model/study/sampler')
import superdag as D  # noqa: E402
from live import S, M  # noqa: E402
import live  # noqa: E402

STORE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points-t'
OUT = os.environ.get('LABELS') or os.path.dirname(os.path.abspath(__file__)) + '/labels'
os.makedirs(OUT, exist_ok=True)
K, N = int(sys.argv[1]), int(sys.argv[2])
files = sorted(sys.argv[3:])[K::N]
index = collections.defaultdict(list)
for e in os.scandir(STORE):
    if not e.name.endswith('.building'):
        index[e.name[:8]].append(e.path)


def cases(task):
    """{case: gold text} of a task, read from its points."""
    out = {}
    for d in index[task]:
        p = json.load(open(d + '/point.json'))
        if p['case'] not in out:
            out[p['case']] = open(d + '/gold.arclog').read()
    return out


def key(types, examples):
    """What identifies a table across sessions: its column types and its examples' row counts and row hashes."""
    return tuple(sorted(types)), json.dumps(examples)


def gold_tables(run, text):
    """[(form index, table key)] of a gold program's relations in the session of run."""
    forms = [str(f) for f in text.strip().split('\n') if not f.startswith('(OUT')]
    run.collect = []
    got = []
    try:
        run.scope(forms)
        for i, ct in enumerate(run.collect):
            for _, j in D.relation_tables(ct):
                try:
                    tb = S.parse_table(D.OneTable(ct, j))
                    got.append((i, key([str(t) for t in tb['types']], D.table_key(tb)[1])))
                except M.Fail:
                    run.c['gold:table not finished'] += 1
    except Exception as e:  # noqa: BLE001
        print('no replay:', str(e)[:160], flush=True)
    run.collect = None
    run.scoped = None
    return got, forms


def lines(f):
    """Parsed records of a raw or zstd file, as a stream. A last line that was cut is left out."""
    src = subprocess.Popen(['zstd', '-dcq', f], stdout=subprocess.PIPE) if f.endswith('.zst') else None
    fh = io.TextIOWrapper(src.stdout) if src else open(f)
    for l in fh:
        try:
            yield json.loads(l)
        except ValueError:
            pass


sampler = live.Sampler('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/models')
t0 = time.time()
for n, f in enumerate(files, 1):
    task = os.path.basename(f)[:8]
    o = f'{OUT}/{task}.json'
    if os.path.exists(o):
        continue
    gold = cases(task)
    tables = collections.defaultdict(list); sizes = {}
    sess, d, _ = D.session_of(task)
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
    for c, text in gold.items():
        got, forms = gold_tables(run, text)
        sizes[c] = len(forms)
        for i, k in got:
            tables[k].append((c, i))
    hits, seen = [], 0
    for r in lines(f):
        seen += 1
        hit = tables.get(key(r['table_types'], r['examples']))
        if hit:
            hits.append(dict(token=r['token'], draw=(r.get('tags') or {}).get('draw'), depth=r['depth'], hit=[list(x) for x in hit]))
    covered = collections.defaultdict(set)
    for h in hits:
        for c, i in h['hit']:
            covered[c].add(i)
    best = max(gold, key=lambda c: len(covered[c]) / max(sizes[c], 1)) if gold else None
    v = dict(task=task, nodes=seen, cases=len(gold), sizes=sizes, hits=hits, covered={c: sorted(s) for c, s in covered.items()}, best=best)
    json.dump(v, open(o + '.new', 'w')); os.replace(o + '.new', o)
    el = time.time() - t0
    print(f'{n}/{len(files)} {task} nodes {seen} cases {len(gold)} hits {len(hits)} best {len(covered[best]) if best else 0}/{sizes.get(best, 0)} | {el:.0f} s | ETA {el / n * (len(files) - n):.0f} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
