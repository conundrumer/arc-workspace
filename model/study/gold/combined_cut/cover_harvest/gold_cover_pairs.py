"""Pairs of the harvest: for each gold form that a search clause took the place of, the gold clause (view-before-harvest) and the covering clause (view-final), (the text of its harvest row, so a stem that went back is in), with their kinds, atoms, reads and builtins, the class of each read of the covering clause, the gold forms that went out with it and the forms brought in, and the bits of record of each side where reread4 has them. Writes pairs.jsonl in this folder.

  python3 gold_cover_pairs.py
"""
import glob, gzip, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
BITS = HERE + '/../../gold-v3-dag-bits/'
LABEL = re.compile(r'&[A-Za-z_0-9]+')
HEAD = re.compile(r'\((\w+) (&[A-Za-z_0-9]+)')
CALL = re.compile(r'\((?!:)([A-Za-z_][\w.]*|&[A-Za-z_0-9]+(?:\.\w+)?)(?= )')
GRID = {'input', 'ex_input', 'ex_output'}
WORDS = {'NOT', 'OR', 'RULE', 'INIT', 'DET', 'OUT'}


def text(v, t):
    with gzip.open(HERE + '/../' + v + '/' + t + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def shape(line):
    return ' '.join(LABEL.sub('&_', line).split())


def parts(line):
    """(kind, label, component or None, reads, builtins, atoms): reads are the labels it reads, without sub-relation; builtins the other relations and DET or INIT components; atoms the count of relation atoms in the body."""
    kind, label = HEAD.match(line).groups()
    rest = line[HEAD.match(line).end():]
    comp = None
    if kind in ('INIT', 'DET') and re.match(r' ([A-Z]\w*)\)?', rest) and not rest.startswith(' ('):
        comp = re.match(r' ([A-Z]\w*)', rest)[1]
    calls = [c for c in CALL.findall(rest) if c not in WORDS]
    # An INIT section opens as `(name ((:col ...` or `(name ()`: its name is not a relation.
    sections = set(re.findall(r'\((\w+) \(\(', rest)) | set(re.findall(r'\((\w+) \(\)', rest)) if kind == 'INIT' else set()
    calls = [c for c in calls if c not in sections]
    reads = sorted({c.split('.')[0] for c in calls if c.startswith('&')})
    builtins = sorted({c for c in calls if not c.startswith('&') and c not in GRID})
    grid = sorted({c for c in calls if c in GRID})
    return dict(kind=kind, label=label, component=comp, reads=reads, builtins=builtins, grid=grid, atoms=len(calls), negations=rest.count('(NOT '), ors=rest.count('(OR '))


def record():
    """{stem: [bits by form line]} from reread4 for the landed text, and from merged-before-reread4 for the text before."""
    after = {}
    for p in sorted(glob.glob(BITS + 'reread4-all/rows-*.jsonl')):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                if r.get('task') and r.get('forms') is not None:
                    after[r['task']] = {f['line']: f.get('bits') for f in r['forms']}
    before = {}
    for l in open(BITS + 'reread-kit/merged-before-reread4.jsonl'):
        r = json.loads(l)
        before[r['task']] = {f['line']: f.get('bits') for f in r.get('forms') or []}
    return before, after


def main():
    before, after = record()
    rows = {}
    for p in sorted(glob.glob(HERE + '/rows-*.jsonl')):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                rows[r['stem']] = r
    n = 0
    with open(HERE + '/pairs.jsonl', 'w') as out:
        for l in open(HERE + '/search-forms-all.jsonl'):
            s = json.loads(l)
            t = s['stem']
            old, new = text('view-before-harvest', t), [x for x in rows[t]['program'].splitlines() if x.strip()]
            oldf = [x for x in old if not x.startswith('(OUT')]
            newf = [x for x in new if not x.startswith('(OUT')]
            ob = {HEAD.match(x)[2]: before.get(t, {}).get(i) for i, x in enumerate(oldf)}
            nb = {HEAD.match(x)[2]: after.get(t, {}).get(i) for i, x in enumerate(newf)}
            search = {f['label']: f for f in s['forms']}
            # Each other form of the landed text is a gold form: match it to the text before by its shape, in order.
            to_old, left = {}, list(oldf)
            for x in newf:
                lab = HEAD.match(x)[2]
                if lab in search:
                    continue
                k = next((k for k, y in enumerate(left) if shape(y) == shape(x)), None)
                if k is None:
                    k = next((k for k, y in enumerate(left) if HEAD.match(y)[2] == lab), None)
                if k is not None:
                    to_old[lab] = HEAD.match(left.pop(k))[2]
            kept_old = set(to_old.values())
            r = rows[t]
            for f in s['forms']:
                if not f['covering']:
                    continue
                g = next(x for x in oldf if HEAD.match(x)[2] == f['in_place_of'])
                a, b = parts(g), parts(f['line'])
                v = next(v for v in r['verdicts'] if v['verdict'].startswith('stands') and v['run'] == f['run'] and str(v['node']) == str(f['node']))
                brought = [x for x, y in search.items() if not y['covering'] and y['run'] == f['run'] and str(y['node']) == str(f['node'])]
                cls = {}
                for x in b['reads']:
                    if x in search:
                        cls[x] = 'brought in'
                    elif to_old.get(x) in a['reads']:
                        cls[x] = "gold's read"
                    else:
                        cls[x] = 'other gold form'
                removed = [x for x in v.get('removed', []) if x not in kept_old]
                gb = [ob.get(x) for x in [a['label']] + [y for y in removed if y != a['label']]]
                sb = [nb.get(x) for x in [f['label']] + brought]
                row = dict(stem=t, set=s['set'], run=f['run'], node=f['node'], draw=f['draw'], gold=g, cover=f['line'], gold_parts=a, cover_parts=b, read_class=cls,
                           gold_out=[y for y in removed if y != a['label']], brought=[x for x in search if not search[x]['covering']],
                           gold_bits=ob.get(a['label']), cover_bits=nb.get(f['label']), gold_side_bits=None if None in gb else round(sum(gb), 2), cover_side_bits=None if None in sb else round(sum(sb), 2),
                           stem_before=r['before'], stem_after=r['after'])
                out.write(json.dumps(row) + '\n')
                n += 1
    print('pairs', n)


if __name__ == '__main__':
    main()
