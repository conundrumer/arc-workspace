"""Figures of record at b8e52e249: pod-all rows with the forms of reread-all over them. Prints the bands of the worst form of each stem of view-final, without the stems flagged `approximated` and then with them, and writes merged.jsonl (one row per stem).

  python3 gold_reread_bands.py
A stem whose text is neither pod-all's nor reread-all's has no row. Takes reread-prune rows over both where their text is the stem's. Works on a part of reread-all: a form not reread yet keeps its pod-all figure and counts in `old`.
"""
import glob, gzip, hashlib, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
O = HERE + '/..'
G = O + '/..'
BANDS = 13, 18, 21.5, 25, 28, 32
VIEW = G + '/gold-v3-combined-cut/view-final/'
EVAL = set(open(G + '/../features-worker/arm/eval-tasks.txt').read().split())
HELD = set(open(G + '/../features-worker/arm/held-tasks.txt').read().split())


def rows_of(pat):
    rows = {}
    for p in glob.glob(pat):
        for l in open(p):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            rows[r['task']] = r
    return rows


def sha(t):
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        return hashlib.sha256('\n'.join(x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()).encode()).hexdigest()[:16]


old, new = rows_of(O + '/pod-all/rows-*.jsonl'), rows_of(O + '/reread-all/rows-*.jsonl')
# Whole reads of later texts, kept by the text each read, so a stem whose text goes back to an earlier one finds its row.
prune = {}
for pat in ('/reread-prune/rows-*.jsonl', '/reread2-all/rows-*.jsonl', '/reread3-all/rows-*.jsonl', '/reread4-all/rows-*.jsonl'):  # the prune on the final text; the projection helpers; the equal-table cuts; the search covers
    for t, r in rows_of(O + pat).items():
        prune.setdefault(t, {})[r['base_sha']] = r
out = []
for t in sorted(os.listdir(VIEW)):
    if not os.path.exists(VIEW + t + '/pairs.jsonl.gz'):
        continue
    s, a, b = sha(t), old.get(t), new.get(t)
    if s in prune.get(t, {}):
        a, b = None, prune[t][s]
    forms = {}
    if a and a['base_sha'] == s:
        forms = {f['line']: dict(f, pin='0099a0c17') for f in a['forms']}
    if b and b['base_sha'] == s:
        forms.update({f['line']: dict(f, pin='b8e52e249') for f in b['forms'] if f['status'] != 'unread' or not forms.get(f['line'])})
    bits = [f['bits'] for f in forms.values() if f['status'] != 'no draw']
    known = [x for x in bits if isinstance(x, (int, float))]
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        approx = bool(json.loads(f.readline()).get('approximated'))
    out.append(dict(task=t, base_sha=s, approximated=approx, read=bool(forms), worst=max(known) if known else None, sum=round(sum(known), 2), blank=len(bits) - len(known), old=sum(f['pin'] == '0099a0c17' for f in forms.values()), forms=list(forms.values())))
with open(HERE + '/merged.jsonl', 'w') as f:
    for r in out:
        f.write(json.dumps(r) + '\n')


def line(name, rows):
    ok = [r for r in rows if r['read']]
    full = sorted(r['worst'] for r in ok if not r['blank'] and r['worst'] is not None)
    print(name, len(rows), 'stems,', len(rows) - len(ok), 'no row,', sum(1 for r in ok if r['blank']), 'with a form with no figure |', ' '.join('%s: %d' % (b, sum(x < b for x in full)) for b in BANDS), '| median', round(full[len(full) // 2], 1) if full else None)


for name, keep in (('', lambda r: not r['approximated']), (' with approximated stems', lambda r: True)):
    line('the 99' + name, [r for r in out if r['task'] in EVAL and keep(r)])
    line('held 37' + name, [r for r in out if r['task'] in HELD and keep(r)])
    line('training' + name, [r for r in out if r['task'] not in EVAL and keep(r)])
print('reread rows', len(new))
