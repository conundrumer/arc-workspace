"""Gold text only, the 37 held tasks: for each INIT X and each gold reader R of X, the share of X's reads of earlier forms that R also reads (R's side
tables, which a reader with hole X holds), by key body and by port body, and the size of R's side set. A DAG fact: no written order is read.
  python3 diamond_probe.py POINTS HELD_TASKS_FILE"""
import collections, json, re, sys, statistics as st
NAME = re.compile(r'&r\d+')
gold = {x['task']: x['gold_sexp'] for x in json.load(open(sys.argv[1]))}
held = open(sys.argv[2]).read().split()
def key_part(text):
    i = text.find('(key (')
    if i < 0:
        return '', text
    d = 0
    for j in range(i, len(text)):
        d += text[j] == '('; d -= text[j] == ')'
        if d == 0:
            break
    # the key clause's body is its first list; the keyed ports follow inside the key clause
    k = text.index('(', i + 1); d = 0
    for e in range(k, len(text)):
        d += text[e] == '('; d -= text[e] == ')'
        if d == 0:
            break
    return text[k:e + 1], text[:k] + text[e + 1:]
c = collections.Counter(); side_sizes = []; per_form = []
for t in held:
    if t not in gold:
        continue
    lines = gold[t].strip().split('\n')
    forms = [x for x in lines if not x.startswith('(OUT')]
    head = [NAME.search(x)[0] for x in forms]
    idx = {h: i for i, h in enumerate(head)}
    reads = [{idx[m] for m in NAME.findall(x) if m in idx and m != h} for x, h in zip(forms, head)]
    readers = collections.defaultdict(set)
    for i, rs in enumerate(reads):
        for r in rs:
            readers[r].add(i)
    for x, text in enumerate(forms):
        if not text.startswith('(INIT') or not reads[x] or not readers[x]:
            continue
        kb, rest = key_part(text)
        kr = {idx[m] for m in NAME.findall(kb) if m in idx}
        pr = {idx[m] for m in NAME.findall(rest) if m in idx and m != x}
        best = max(readers[x], key=lambda r: len(reads[x] & (reads[r] - {x})))
        side = reads[best] - {x}
        side_sizes.append(len(side))
        c['INIT forms with reads and a reader'] += 1
        c['key reads'] += len(kr); c['key reads in side'] += len(kr & side)
        c['port reads'] += len(pr); c['port reads in side'] += len(pr & side)
        c['forms with every read in side'] += reads[x] <= side
        c['forms with some read in side'] += bool(reads[x] & side)
        c['keyed forms'] += bool(kb)
        c['keyed forms, key reads in side'] += bool(kr) and kr <= side
        per_form.append(len(reads[x] & side) / len(reads[x]))
print(dict(c)); print('side set size: median %s, quartiles %s' % (st.median(side_sizes), st.quantiles(side_sizes, n=4)))
print('share of a form\'s reads in side: mean %.2f, median %.2f' % (st.mean(per_form), st.median(per_form)))
