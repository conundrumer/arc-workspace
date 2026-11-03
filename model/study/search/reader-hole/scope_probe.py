"""Gold forms a reader with one hole could serve, on gold text and the covers of a 600 s run. A form X counts when the run didn't cover it, its own reads are all
covered (so a forward draw can give its table), and some reader R of X has every read other than X covered (R is a reader with one hole, X). For INIT X it also
says whether R's atom on X has a key site, and whether that key site joins a label made by another atom of R.
  python3 scope_probe.py POINTS RUN_OUT_DIR ARM..."""
import collections, json, re, sys, os
NAME = re.compile(r'&r\d+')
points, out, arms = sys.argv[1], sys.argv[2], sys.argv[3:]
gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
def atoms_on(text, name):
    """The atoms of text whose relation is name or a method of it, as text: from '(' + name to its closing paren."""
    got = []
    for m in re.finditer(r'\((%s)(\.\w+)?[ )]' % re.escape(name), text):
        i, d = m.start(), 0
        for j in range(i, len(text)):
            d += text[j] == '('
            d -= text[j] == ')'
            if d == 0:
                got.append(text[i:j + 1]); break
    return got
for arm in arms:
    c = collections.Counter(); tasks = collections.Counter()
    for t in sorted(os.listdir('%s/%s' % (out, arm))):
        lines = gold[t].strip().split('\n')
        forms = [x for x in lines if not x.startswith('(OUT')]
        head = [NAME.search(x)[0] for x in forms]
        idx = {h: i for i, h in enumerate(head)}
        kind = [x[1:x.index(' ')] for x in forms]
        reads = [sorted({idx[m] for m in NAME.findall(x) if m in idx and m != h}) for x, h in zip(forms, head)]
        readers = collections.defaultdict(list)
        for i, rs in enumerate(reads):
            for r in rs:
                readers[r].append(i)
        cov = {json.loads(l)['gold'] for l in open('%s/%s/%s/work/%s.out.jsonl.cover' % (out, arm, t, t))}
        for x in range(len(forms)):
            if x in cov or not all(r in cov for r in reads[x]):
                continue
            c['ready ' + kind[x]] += 1
            one = [r for r in readers[x] if r not in cov and all(q in cov for q in reads[r] if q != x)]
            if not one:
                continue
            c['ready, one-hole reader ' + kind[x]] += 1
            tasks[t] += kind[x] != 'DET'
            if kind[x] == 'INIT':
                ats = [a for r in one for a in atoms_on(forms[r], head[x])]
                keyed = [a for a in ats if '(:key' in a]
                c['INIT hole atoms'] += len(ats)
                c['INIT hole atoms with a key site'] += len(keyed)
                c['INIT X with a keyed hole atom'] += bool(keyed)
    print(arm, dict(sorted(c.items())), 'tasks with a non-DET such form', len(tasks))
