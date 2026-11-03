"""The forms of view-final whose clause came from a search run: for each stem where the harvest landed, each form of the landed text that a standing trial put in, with the run, node and draw of its cover and the label of the gold form it took the place of in the text before the harvest. Writes search-forms.jsonl in this folder.

  python3 gold_cover_forms.py [all]

With `all`, every taken row counts, on the text of its row, and the output is search-forms-all.jsonl: the stems that went back to their text before the harvest are in it too.
"""
import glob, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = HERE + '/../view-final/'
BEFORE = HERE + '/../view-before-harvest/'
LABEL = re.compile(r'&[A-Za-z_0-9]+')


def text(v, t):
    with gzip.open(v + t + '/pairs.jsonl.gz', 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def shape(line):
    """The line with each label as &_ and spaces made single: two lines with the same shape differ only in labels."""
    return ' '.join(LABEL.sub('&_', line).split())


rows = {}
for p in sorted(glob.glob(HERE + '/rows-*.jsonl')):
    for l in open(p):
        if l.endswith('\n'):
            r = json.loads(l)
            rows[r['stem']] = r
ALL = sys.argv[1:] == ['all']
got, missing = 0, 0
with open(HERE + ('/search-forms-all.jsonl' if ALL else '/search-forms.jsonl'), 'w') as out:
    for t, r in sorted(rows.items()):
        if not r.get('taken') or not os.path.exists(VIEW + t) or not ALL and text(VIEW, t) != r['program']:
            continue
        old = [x for x in text(BEFORE, t).splitlines() if x.strip() and not x.startswith('(OUT')]
        new = [x for x in r['program'].splitlines() if x.strip() and not x.startswith('(OUT')]
        free = list(range(len(new)))
        forms = []
        for v in r['verdicts']:
            if not v['verdict'].startswith('stands'):
                continue
            c = next(c for c in r['candidates'] if c['run'] == v['run'] and str(c['node']) == str(v['node']))
            swap = dict(v.get('replaced', []))
            for line in c['clauses']:
                head = LABEL.search(line)[0]
                if head not in v.get('brought', []):
                    continue
                s = shape(LABEL.sub(lambda m: swap.get(m[0], m[0]), line))
                i = next((i for i in free if shape(new[i]) == s), None)
                if i is None:
                    missing += 1
                    continue
                free.remove(i)
                forms.append(dict(label=LABEL.search(new[i])[0], line=new[i], run=c['run'], node=c['node'], draw=c['draw'], covering=line == c['clauses'][-1], in_place_of=re.match(r'\(\w+ (&\w+)', old[int(v['g'])])[1]))
        got += len(forms)
        out.write(json.dumps(dict(stem=t, set=r['set'], forms=forms)) + '\n')
print('forms', got, 'not found in the landed text', missing)
