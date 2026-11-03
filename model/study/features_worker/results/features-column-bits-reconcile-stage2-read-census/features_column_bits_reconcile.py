"""Reconcile two figures for the bits of a form's columns: the rest of the first atom of stage 2 (stage2-read-cost.jsonl) and the column bits per atom of a census of gold's RULE forms. Reads rows only. Prints the tables that the paragraph on results.md cites.

  python3 features_column_bits_reconcile.py > reconcile.txt
"""
import collections
import json
import re
import statistics as st

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
STAGE = W + 'features-worker/results/features-prefix-keep-score-stage49-heldout-e3021ada/stage2-read-cost.jsonl'
SPLITS = W + 'sampler/search-worker/runs/search-prefix-score-paired-heldout-rule-60cpus-mac-ship7/two-stage-bits.jsonl'
SW = W + 'sampler/sampler-worker/'
CENSUS = {
    'census-base gold-v3-helper-forms-a036da074': SW + 'sampler-helper-forms/gold-v3-helper-forms-a036da074/census-base.jsonl',
    'census-current 780f065f3 drawable-rewrite': SW + 'sampler-steer-census-heldout37-780f065f3/census-current.jsonl',
    'census-new 780f065f3 drawable-rewrite': SW + 'sampler-steer-census-heldout37-780f065f3/census-new.jsonl',
}
COL = re.compile(r'\(:\w+')
FRESH = re.compile(r'\(:\w+ \*')


def valid(r):
    return 'total' in r and not r.get('bad') and not r.get('dead') and not r.get('left')


def first_atom(form):
    """The first atom of a form's body, from the text of (RULE &head (atom) ...)."""
    i = form.index('(', 1)
    depth, j = 0, i
    while True:
        depth += {'(': 1, ')': -1}.get(form[j], 0)
        j += 1
        if depth == 0:
            return form[i:j]


def split_kinds(parts):
    c = collections.Counter()
    for k, v in parts.items():
        c[k.split(' atom: ')[-1] if ' atom: ' in k else k] += v
    return c


def show(name, xs):
    xs = list(xs)
    if xs:
        print('%-46s n %4d  mean %6.2f  median %6.2f' % (name, len(xs), st.mean(xs), st.median(xs)))
    else:
        print('%-46s n    0' % name)


def band(w):
    return str(w) if w < 7 else '7+'


def group(rows, key):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return g


def stage():
    print('## Figure A: the first atom of stage 2')
    two = {(r['task'], r['form'], r['split']): r for r in map(json.loads, open(SPLITS))}
    rows = []
    for r in map(json.loads, open(STAGE)):
        a = first_atom(two[r['task'], r['form'], r['split']]['second'])
        rows.append(dict(r, atom=a, width=len(COL.findall(a)), fresh=len(FRESH.findall(a)), rest=r['atom_bits'] - r['rel']['bits']))
    print('splits', len(rows), 'clauses', len({(r['task'], r['form']) for r in rows}), 'read atoms of &prefix_stage', sum(r['atom'].startswith('(&prefix_stage') for r in rows),
          'all columns fresh', sum(r['width'] == r['fresh'] for r in rows))
    show('atom bits', (r['atom_bits'] for r in rows))
    show('first relation pick', (r['rel']['bits'] for r in rows))
    show('rest of atom', (r['rest'] for r in rows))
    by = collections.defaultdict(list)
    for r in rows:
        by[r['task'], r['form']].append(r['rest'])
    show('rest of atom, mean of each clause', (st.mean(v) for v in by.values()))
    show('columns named by the read atom', (r['width'] for r in rows))
    print('rest of atom by columns named')
    for w, g in sorted(group(rows, lambda r: band(r['width'])).items()):
        show('  %s columns' % w, (r['rest'] for r in g))
    print('rest of atom per named column: %.3f' % (sum(r['rest'] for r in rows) / sum(r['width'] for r in rows)))
    print('rest of atom by clause')
    for k, v in sorted(by.items(), key=lambda x: -st.mean(x[1])):
        print('  %s %-3d splits %d mean %.2f' % (k[0], k[1], len(v), st.mean(v)))
    return rows


def census_atoms(rows):
    out = []
    for r in rows:
        for i, ((ctx, text, b), d) in enumerate(zip(r['atoms'], r['detail'])):
            cur = d['cur']
            first = cur.get('relation', cur.get('relation (op)', 0.0))
            out.append(dict(i=i, ctx=ctx, text=text, bits=b, cur=cur, rest=(b or 0.0) - first, width=len(COL.findall(text)), fresh=len(FRESH.findall(text)),
                            derived=text.startswith('(&r'), plain=not text.startswith('(NOT'), task=r['task'], line=r['line'], mix=(b or 0.0) - sum(cur.values())))
    return out


def row(name, atoms):
    if not atoms:
        print('%-40s n 0' % name)
        return
    n = len(atoms)
    c = collections.Counter()
    for a in atoms:
        for k, v in a['cur'].items():
            c[k] += v
        c['join mix'] += a['mix']
    print('%-40s n %4d width %.2f bits %6.2f rest %5.2f median %5.2f | column %.2f stop %.2f value %.2f fcol %.2f op %.2f mix %.2f rel %.2f relop %.2f' % (
        name, n, sum(a['width'] for a in atoms) / n, sum(a['bits'] or 0 for a in atoms) / n, sum(a['rest'] for a in atoms) / n, st.median(a['rest'] for a in atoms),
        c['column'] / n, c['column stop'] / n, (c['value: other'] + c['value: label']) / n, c['fcol'] / n, c['op'] / n, c['join mix'] / n, c['relation'] / n, c['relation (op)'] / n))


def census(name, path, reads):
    print('\n## ' + name)
    R = [json.loads(l) for l in open(path)]
    P = [r for r in R if r.get('kind') == 'RULE' and r['scope'] == 'parents' and 'total' in r]
    for label, G in (('RULE rows with a walk', P), ('valid RULE rows', [r for r in P if valid(r)])):
        n = sum(len(r['atoms']) for r in G)
        c = collections.Counter()
        for r in G:
            c.update(split_kinds(r['parts']))
        print(label, 'forms', len(G), 'tasks', len({r['task'] for r in G}), 'atoms', n, 'bits per atom %.3f' % (sum(c.values()) / n))
        print('  per atom:', {k: round(v / n, 3) for k, v in c.most_common(9)})
        ab = sum(a[2] or 0 for r in G for a in r['atoms'])
        print('  atom bits per atom %.3f; rest of atom per atom %.3f' % (ab / n, (ab - c['relation']) / n))
    A = census_atoms(P)
    row('all atoms', A)
    row('atoms with no column bits', [a for a in A if a['cur'].get('column', 0) < .005])
    row('first atoms', [a for a in A if a['i'] == 0])
    row('first atoms, derived', [a for a in A if a['i'] == 0 and a['derived']])
    D = [a for a in A if a['i'] == 0 and a['derived'] and a['width'] == a['fresh']]
    row('first atoms, derived, all columns fresh', D)
    row('all derived atoms, all columns fresh', [a for a in A if a['derived'] and a['plain'] and a['width'] == a['fresh']])
    for w, g in sorted(group(D, lambda a: band(a['width'])).items()):
        row('  first, derived, fresh, %s columns' % w, g)
    bins = group(D, lambda a: band(a['width']))
    miss = [r for r in reads if band(r['width']) not in bins]
    use = [bins[band(r['width'])] for r in reads if band(r['width']) in bins]
    mean = lambda f: st.mean(st.mean(f(a) for a in g) for g in use)
    print('those census atoms at the column counts of the 47 reads: rest %.2f, column %.2f, stop %.2f, value %.2f (reads with no census atom of that count: %d)' % (
        mean(lambda a: a['rest']), mean(lambda a: a['cur'].get('column', 0.0)), mean(lambda a: a['cur'].get('column stop', 0.0)),
        mean(lambda a: a['cur'].get('value: other', 0.0) + a['cur'].get('value: label', 0.0)), len(miss)))
    keys = {(r['task'], r['form']) for r in reads}
    C14 = [a for a in A if (a['task'][:8], a['line']) in keys]
    row('atoms of the 14 clauses', C14)
    row('first atoms of the 14 clauses', [a for a in C14 if a['i'] == 0])


if __name__ == '__main__':
    reads = stage()
    for k, v in CENSUS.items():
        census(k, v, reads)
