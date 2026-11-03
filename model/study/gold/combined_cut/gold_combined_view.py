"""Builds a corpus view of the cut stages as they stand: gold-v3-cheapest-round50's corpus-view, with each stem's first row taken from the last stage that landed on it. A stem in next-pod-stems.txt reads the combined rows; any other reads the shape cut's rows, then the extended cut's.

  python3 gold_combined_view.py OUT
"""
import collections, glob, gzip, hashlib, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = HERE + '/..'
out = sys.argv[1]


def rows_of(pattern):
    rows = {}
    for f in sorted(glob.glob(pattern)):
        for l in open(f):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get('task'):
                rows.setdefault(r.get('stage'), {})[r['task']] = r
    return rows


def program(row):
    p = (row or {}).get('program')
    if row and row.get('landed') is not False and p:
        return p if isinstance(p, str) else '\n'.join(p)


combined = rows_of(HERE + '/pod-out/rows-*.jsonl')
shape = rows_of(GOLD + '/gold-v3-shape-cut/pod-out/rows-*.jsonl').get(None, {})
ext = rows_of(GOLD + '/gold-v3-extended-cut/pod-out/rows-*.jsonl').get(None, {})
ext.update(rows_of(GOLD + '/gold-v3-extended-cut/mac-rows.jsonl').get(None, {}))
later = set(open(GOLD + '/gold-v3-shape-cut/next-pod-stems.txt').read().split())
regold = set(open(GOLD + '/gen-v3-11f6a212c/changed-gold-round51.txt').read().split()) | {'fd096ab6'}


def rank(row):
    after = row['after']
    return (float('inf') if after.get('undrawn') else after['worst'], after['sum'])


# The cheapest right text wins, worst form then sum. A regolded stem's older text is a past concept, so it stays out.
cheaper_old = {t for t in later - regold if t in ext and program(ext[t]) and t in combined.get('shape', {}) and rank(ext[t]) < rank(combined['shape'][t])}
rounds = {'ext': {}, 'shape': {}}
for f in sorted(glob.glob(HERE + '/mac-r*/rows-*.jsonl'), key=lambda f: int(f.split('/mac-r')[1].split('/')[0])):
    got = rows_of(f)
    for s in rounds:
        rounds[s].update(got.get(s, {}))
base = GOLD + '/gold-v3-cover-forms-a036da074/corpus-view'
new = out + '.new'
shutil.rmtree(new, ignore_errors=True)
os.makedirs(new)
held = set(open(GOLD + '/../features-worker/arm/eval-tasks.txt').read().split())
source = collections.Counter()
for t in sorted(os.listdir(base)):
    with gzip.open(os.path.realpath(os.path.join(base, t, 'pairs.jsonl.gz')), 'rt') as f:
        lines = f.read().splitlines()
    if t in later:
        chain = (('combined shape', combined.get('shape', {}).get(t)), ('combined ext', combined.get('ext', {}).get(t)))
        if t in cheaper_old:
            chain = (('ext, cheaper than the combined text', ext[t]),)
    else:
        chain = (('shape', shape.get(t)), ('ext', ext.get(t)))
    if t in rounds['shape'] or t in rounds['ext']:  # a later round's own text
        chain = (('round shape', rounds['shape'].get(t)), ('round ext', rounds['ext'].get(t)))
    name, text = next(((n, program(r)) for n, r in chain if program(r)), ('base', None))
    if text:
        first = json.loads(lines[0])
        first['gold_sexp'] = text
        lines[0] = json.dumps(first)
    source[name, t in held] += 1
    os.makedirs(os.path.join(new, t))
    with gzip.open(os.path.join(new, t, 'pairs.jsonl.gz'), 'wt') as f:
        f.write('\n'.join(lines) + '\n')
# Stems of the 99 that have no folder in corpus-view: gold-v3-cheapest-round50 holds them in points-eval.json.
mac = rows_of(HERE + '/mac-3/rows-*.jsonl')
points = {p['task']: p for p in json.load(open(GOLD + '/gold-v3-cover-forms-a036da074/points-eval.json'))}
for t, p in sorted(points.items()):
    if os.path.exists(os.path.join(base, t)):
        continue
    if t in mac.get('ext', {}):
        chain = [mac[s].get(t) for s in ('shape', 'ext') if program(mac[s].get(t))]
        if t not in regold and program(ext.get(t)):
            chain.append(ext[t])
        chain.sort(key=lambda r: rank(r))
        name = 'mac' if chain else 'base'
        text = program(chain[0]) if chain else p['gold_sexp']
    else:
        name = 'shape' if program(shape.get(t)) else 'ext' if program(ext.get(t)) else 'base'
        text = program(shape.get(t)) or program(ext.get(t)) or p['gold_sexp']
    source[name, True] += 1
    os.makedirs(os.path.join(new, t))
    with gzip.open(os.path.join(new, t, 'pairs.jsonl.gz'), 'wt') as f:
        f.write(json.dumps(dict(task=t, gold_sexp=text)) + '\n')
# DAG split rows on the 99: a landed row is the cheapest right program known for its stem.
dag = rows_of(GOLD + '/gold-v3-dag-bits/outcut99/rows-*.jsonl').get('dagcut', {})
dag.update({t: r for t, r in rows_of(GOLD + '/gold-v3-dag-bits/outcut99-fix/rows-*.jsonl').get('dagcut', {}).items() if r.get('landed')})  # the rerun on the fixed read
for t, r in sorted(dag.items()):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    text = program(r) if r.get('landed') and t not in rounds['ext'] else None  # a later round's stem read other text
    if text and os.path.exists(p):
        with gzip.open(p, 'rt') as f:
            lines = f.read().splitlines()
        first = json.loads(lines[0])
        first['gold_sexp'] = text
        lines[0] = json.dumps(first)
        with gzip.open(p, 'wt') as f:
            f.write('\n'.join(lines) + '\n')
        source['dag split', t in held] += 1
# DAG split second pass: a row replaces the text it started from, and only that text.
dag2 = rows_of(GOLD + '/gold-v3-dag-bits/cut2-*/rows-*.jsonl')
dag2 = {**dag2.get('dagcut2', {}), **dag2.get(None, {})}  # a round's rows (cut2-r<n>) have no stage field
for t, r in sorted(dag2.items()):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    text = program(r) if r.get('landed') else None
    if text and os.path.exists(p):
        with gzip.open(p, 'rt') as f:
            lines = f.read().splitlines()
        first = json.loads(lines[0])
        if hashlib.sha256('\n'.join(first['gold_sexp'].splitlines()).encode()).hexdigest()[:16] != r['base_sha']:
            source['dag split second pass, stale', t in held] += 1
            continue
        first['gold_sexp'] = text
        lines[0] = json.dumps(first)
        with gzip.open(p, 'wt') as f:
            f.write('\n'.join(lines) + '\n')
        source['dag split second pass', t in held] += 1
# Prune on the final text: a taken row replaces the text it read, and only that text.
for t, r in sorted({r['stem']: r for r in map(json.loads, open(HERE + '/prune-final/rows.jsonl'))}.items()):  # rows name their stem by `stem`
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    if not (r.get('taken') and r.get('program') and os.path.exists(p)):
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    first = json.loads(lines[0])
    if hashlib.sha256('\n'.join(first['gold_sexp'].splitlines()).encode()).hexdigest()[:16] != r['vsha']:
        source['prune on the final text, stale', t in held] += 1
        continue
    first['gold_sexp'] = r['program']
    lines[0] = json.dumps(first)
    with gzip.open(p, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    source['prune on the final text', t in held] += 1
# Projection helpers for INIT bodies: rows at the 3-bit margin, then bar-crossing commits (a step under the margin that takes the worst form under a bar, by more than the handover noise, on a reread of its handover text).
PROJ = GOLD + '/gold-projection-trial/'
proj = {}
for pat in (PROJ + 'trial99/out/rows-*.jsonl', GOLD + '/gold-projection-all/rows-*.jsonl'):
    for f in sorted(glob.glob(pat)):
        for l in open(f):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get('task') and r.get('landed') and r.get('program'):
                proj[r['task']] = (r['base_sha'], program(r), 'projection')
for f in sorted(glob.glob(PROJ + 'trial/out/rows-*.jsonl')):  # the trial ran at margin 0: only stems whose every commit fell 3 bits or more
    for l in open(f):
        r = json.loads(l)
        if r.get('task') in ('dd6b8c4b', 'b5ca7ac4') and r.get('landed') and r.get('program'):
            proj[r['task']] = (r['base_sha'], program(r), 'projection')
for f in sorted(glob.glob(PROJ + 'bar-commit/out-*.jsonl')):
    for l in open(f):
        r = json.loads(l)
        if r.get('decision') == 'commit' and r.get('handover_text'):
            proj[r['task']] = (r['base_sha'], r['handover_text'], 'projection, bar crossing')
for t, (base, text, name) in sorted(proj.items()):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    if not os.path.exists(p):
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    first = json.loads(lines[0])
    if hashlib.sha256('\n'.join(first['gold_sexp'].splitlines()).encode()).hexdigest()[:16] != base:
        source[name + ', stale', t in held] += 1
        continue
    first['gold_sexp'] = text
    lines[0] = json.dumps(first)
    with gzip.open(p, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    source[name, t in held] += 1
# Equal tables on the final text: a taken row drops later forms whose tables equal an earlier form's, and replaces the text it read, and only that text.
# A stem in revert.jsonl keeps its text: on the figures of record its worst form is higher after the cut.
DEDUP = sorted(glob.glob(HERE + '/dedup-final/rows*.jsonl'))
REVERT = HERE + '/dedup-final/revert.jsonl'
revert = {json.loads(l)['stem'] for l in open(REVERT)} if os.path.exists(REVERT) else set()
for t, r in sorted({r['stem']: r for r in map(json.loads, (l for p in DEDUP for l in open(p) if l.endswith('\n')))}.items()):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    if not (r.get('taken') and r.get('program') and os.path.exists(p)):
        continue
    if t in revert:
        source['equal tables on the final text, worst form higher on the record', t in held] += 1
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    first = json.loads(lines[0])
    if hashlib.sha256('\n'.join(first['gold_sexp'].splitlines()).encode()).hexdigest()[:16] != r['vsha']:
        source['equal tables on the final text, stale', t in held] += 1
        continue
    first['gold_sexp'] = r['program']
    lines[0] = json.dumps(first)
    with gzip.open(p, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    source['equal tables on the final text', t in held] += 1
# Search covers on the final text: a taken row puts a search run's covering clause, with the forms it reads, in place of gold forms, and replaces the text it read, and only that text. It applies to the sets in HARVEST_SETS.
HARVEST_SETS = {'training', '37', 'ramp'}
# A stem in the harvest's revert.jsonl keeps its text: on the figures of record its worst form is higher after the harvest.
HARVEST = sorted(glob.glob(HERE + '/cover-harvest/rows*.jsonl'))
HARVEST_REVERT = HERE + '/cover-harvest/revert.jsonl'
harvest_revert = {json.loads(l)['stem'] for l in open(HARVEST_REVERT)} if os.path.exists(HARVEST_REVERT) else set()
for t, r in sorted({r['stem']: r for r in map(json.loads, (l for p in HARVEST for l in open(p) if l.endswith('\n')))}.items()):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    if not (r.get('taken') and r.get('program') and os.path.exists(p)):
        continue
    if t in harvest_revert:
        source['search covers, worst form higher on the record', t in held] += 1
        continue
    if r['set'] not in HARVEST_SETS:
        source['search covers, set not applied', t in held] += 1
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    first = json.loads(lines[0])
    if hashlib.sha256('\n'.join(first['gold_sexp'].splitlines()).encode()).hexdigest()[:16] != r['vsha']:
        source['search covers, stale', t in held] += 1
        continue
    first['gold_sexp'] = r['program']
    lines[0] = json.dumps(first)
    with gzip.open(p, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    source['search covers', t in held] += 1
# Stems whose solver on master has `@approximated`: their first row gets `approximated: true`. Consumers leave them out by default.
approx = {f[:-3] for f in os.listdir(GOLD + '/../../../../programs/solvers') if f.endswith('.dl') and '@approximated' in open(GOLD + '/../../../../programs/solvers/' + f).read()}
for t in sorted(approx):
    p = os.path.join(new, t, 'pairs.jsonl.gz')
    if not os.path.exists(p):
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    first = json.loads(lines[0])
    first['approximated'] = True
    lines[0] = json.dumps(first)
    with gzip.open(p, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    source['approximated, flagged', t in held] += 1
shutil.rmtree(out, ignore_errors=True)
os.rename(new, out)
print({'%s, %s' % (n, 'the 99' if h else 'training'): c for (n, h), c in sorted(source.items())})
