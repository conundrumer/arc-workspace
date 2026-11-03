"""Whether the store by swap holds the right reader, on a 600 s bank. For each keyed in-scope INIT X (uncovered, ready, with a reader R whose only
uncovered read is X, R's atom on X with a key site of bare labels), it looks for a bank form that reads some pool INIT at a key site and whose other
atoms match R's other atoms by relation and column names, labels ignored, with R's covered reads mapped to the pool forms that covered them. Labels
are ignored, so a match is an upper bound on a right sketch.
  python3 right_sketch_probe.py POINTS RUN_OUT_DIR ARM"""
import collections, json, re, sys, os
sys.argv, args = sys.argv[:1] + ['x'], sys.argv[1:]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sketch_count.py')).read().split('rows = []')[0]
exec(src)
points, out, arm = args
NAME = re.compile(r'&r\d+')
gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
def atoms(text):
    """Top-level-or-nested atom texts of a clause: every list whose head is a relation name (not a keyword or a site)."""
    got = []
    for m in re.finditer(r'\((&[rf]\d+(?:\.\w+)?|[a-z_][a-z0-9_]*)[ )]', text):
        d = 0
        for j in range(m.start(), len(text)):
            d += text[j] == '('; d -= text[j] == ')'
            if d == 0:
                got.append((m[1], text[m.start():j + 1])); break
    return got
def shape(rel, atom):
    cols = tuple(sorted(re.findall(r'\(:(\w+)', atom)))
    return rel, cols
c = collections.Counter()
for t in sorted(os.listdir('%s/%s' % (out, arm))):
    lines = gold[t].strip().split('\n')
    forms = [x for x in lines if not x.startswith('(OUT')]
    head = [NAME.search(x)[0] for x in forms]
    idx = {h: i for i, h in enumerate(head)}
    kind = [x[1:x.index(' ')] for x in forms]
    reads = [{idx[m] for m in NAME.findall(x) if m in idx and m != h} for x, h in zip(forms, head)]
    readers = collections.defaultdict(set)
    for i, rs in enumerate(reads):
        for r in rs:
            readers[r].add(i)
    w = '%s/%s/%s/work/%s.out.jsonl' % (out, arm, t, t)
    cov = {}
    for l in open(w + '.cover'):
        e = json.loads(l); cov.setdefault(e['gold'], e['node'])
    with open(w + '.bank', 'rb') as fh:
        bank = Safe(fh).load()
    nodes, bforms = bank['nodes'], bank['forms']
    gmap = {'&r%s' % head[g][2:]: '&f%d' % nodes[n].form for g, n in cov.items() if n in nodes}
    inits = {'&f%d' % f.id for f in bforms.values() if f.kind == 'INIT'}
    # bank sketches: (multiset of other-atom shapes) for each form that reads a pool INIT at a bare key site
    store = collections.Counter()
    for f in bforms.values():
        ats = atoms(f.text)
        for rel, a in ats:
            base = rel.split('.')[0]
            if base in inits and '.' in rel:
                ks = key_sites(a)
                if ks and '*' not in ks and '^' not in ks:
                    other = tuple(sorted(shape(r2, a2) for r2, a2 in ats if r2.split('.')[0] != base and r2 != head[0]))
                    store[other] += 1
    for x in range(len(forms)):
        if kind[x] != 'INIT' or x in cov or not reads[x] <= set(cov):
            continue
        for r in readers[x]:
            if r in cov or not reads[r] - {x} <= set(cov):
                continue
            ats = atoms(forms[r])[1:] if forms[r].startswith('(INIT') else atoms(forms[r])
            hole = [a for rel, a in ats if rel.split('.')[0] == head[x]]
            if not any((ks := key_sites(a)) and '*' not in ks and '^' not in ks for a in hole):
                continue
            other = tuple(sorted(shape(gmap.get(rel.split('.')[0], rel.split('.')[0]) + ('.' + rel.split('.')[1] if '.' in rel else ''), a)
                                 for rel, a in ats if rel.split('.')[0] != head[x] and rel != head[r]))
            c['keyed one-hole readers of in-scope INITs'] += 1
            c['a bank sketch with the same other atoms'] += other in store
            c['readers whose other atoms are lib or input only'] += all(not s[0].startswith('&') for s in other)
    c['bank sketches'] += sum(store.values())
print(arm, dict(c))
