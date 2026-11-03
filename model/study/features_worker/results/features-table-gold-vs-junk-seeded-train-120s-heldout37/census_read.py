"""Reads the census rows: what the classes are, gold beside junk, and each fact's AUC of gold against junk inside a task."""
import collections, json, os, random, statistics as st, sys
H = os.path.dirname(os.path.abspath(__file__))


def rows(name):
    p = os.path.join(H, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def bar(rs, f, top=14):
    g = [r for r in rs if r['gold']]
    j = [r for r in rs if not r['gold']]
    c, d = collections.Counter(map(f, j)), collections.Counter(map(f, g))
    print('  %-34s %7s %7s %7s' % ('', 'junk', 'gold', 'gold/junk'))
    for k, v in (c + d).most_common(top):
        a, b = c[k] / max(len(j), 1), d[k] / max(len(g), 1)
        print('  %-34s %7.3f %7.3f %7.2f' % (str(k)[:34], a, b, b / a if a else float('inf')))


def auc(rs, f):
    by = collections.defaultdict(lambda: ([], []))
    for r in rs:
        v = f(r)
        if v is not None:
            by[r['task']][r['gold']].append(v)
    out = []
    for j, g in by.values():
        if not j or not g:
            continue
        s = 0
        for x in g:
            s += sum((x > y) + .5 * (x == y) for y in j)
        out.append(s / (len(g) * len(j)))
    return (round(st.mean(out), 3), len(out)) if out else (None, 0)


def sort(r):
    """First match, in this order."""
    if r.get('into'):
        return 'restates another by an arrow'
    if not r['sources']:
        return 'no task input: grammar only'
    if r['sources'] == ['shape']:
        return 'grid shape only'
    if r['product']:
        return 'product of two tables'
    if r['kind'] == 'INIT':
        return 'INIT component on task data'
    if r.get('distinct_reads', 0) <= 1 and not r['negated']:
        return 'one read of task data'
    return 'combines two or more reads'


FACTS = {
    'product': lambda r: int(r['product'] > 0), 'no task input': lambda r: int(not r['sources']), 'shape only': lambda r: int(r['sources'] == ['shape']), 'reads output': lambda r: int('output' in r['sources']),
    'depth': lambda r: r['depth'], 'parents': lambda r: r['parents'], 'columns': lambda r: r['columns'], 'rows': lambda r: r['rows'], 'reads': lambda r: r['reads'], 'distinct reads': lambda r: r.get('distinct_reads'),
    'fixed atoms': lambda r: r['fixed'], 'negated reads': lambda r: r['negated'], 'union': lambda r: r['union'], 'same in each example': lambda r: r['same_each_example'],
    'share of grid': lambda r: r.get('of_grid'), 'share of grid, near half': lambda r: None if r.get('of_grid') is None else -abs(r['of_grid'] - .5), 'jaccard with changed cells': lambda r: r.get('jaccard'), 'covers changed cells': lambda r: r.get('covers_changed'),
    'share that changed': lambda r: r.get('share_changed'), 'readers': lambda r: r['readers'], 'members': lambda r: r['members'], 'early draw': lambda r: -(r['draw'] or 0),
}


def main():
    a = rows('census-plain.jsonl')
    b = rows('census-order.jsonl')
    print('plain: tasks', len({r['task'] for r in a}), 'classes', len(a), 'gold', sum(r['gold'] for r in a))
    print('sort, without arrows')
    bar(a, sort)
    print('sort, non-DET')
    bar([r for r in a if r['kind'] != 'DET'], sort)
    print('sources')
    bar(a, lambda r: tuple(r['sources']))
    print('kind')
    bar(a, lambda r: r['kind'])
    print('built by, non-DET')
    nd = [r for r in a if r['kind'] not in ('DET',)]
    bar(nd, lambda r: (r['kind'], r['op']), 22)
    print('RULE body shape')
    ru = [r for r in a if r['kind'] == 'RULE' and r['op'] == 'body']
    bar(ru, lambda r: ('reads %d' % min(r.get('distinct_reads', 0), 3), 'neg' if r['negated'] else '', 'or' if r['union'] else '', 'fixed' if r['fixed'] else ''), 14)
    print('AUC of gold against junk inside a task, mean over tasks with both')
    for name, sub in (('all', a), ('non-DET', nd), ('RULE', [r for r in a if r['kind'] == 'RULE']), ('INIT', [r for r in a if r['kind'] == 'INIT'])):
        print(' ', name, 'gold', sum(r['gold'] for r in sub), {k: auc(sub, f) for k, f in FACTS.items()})
    print('order: tasks', len({r['task'] for r in b}), 'classes', len(b), 'gold', sum(r['gold'] for r in b))
    if b:
        gen = [r for r in b if r['into'] == 0]
        below = [r for r in b if r['into'] > 0]
        print(' reached by no arrow %.3f, of gold %.3f' % (len(gen) / len(b), sum(r['gold'] for r in gen) / max(sum(r['gold'] for r in b), 1)))
        print(' sort, with arrows')
        bar(b, sort)
        print(' no arrow in, by kind')
        bar(gen, lambda r: r['kind'])
        print(' no arrow in, built by')
        bar(gen, lambda r: (r['kind'], r['op']), 18)
        print(' arrows in, built by')
        bar(below, lambda r: (r['kind'], r['op']), 10)
        random.seed(1)
        print(' junk with no arrow in, a sample')
        pick = random.sample([r for r in gen if not r['gold'] and r['kind'] != 'DET'], min(16, len(gen)))
        for r in pick:
            print('   ', r['task'], r['types'], 'rows', r['rows'], 'grid', r.get('of_grid'), 'jac', r.get('jaccard'), r['clause'][:170])
        print(' gold with no arrow in')
        for r in [r for r in gen if r['gold'] and r['kind'] != 'DET'][:10]:
            print('   ', r['task'], r['types'], 'rows', r['rows'], 'grid', r.get('of_grid'), 'jac', r.get('jaccard'), r['clause'][:170])


main()
