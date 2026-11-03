"""Flags the tables that depend only on the grid's size: a table's rows on each train input equal its rows on a blank grid of that size, filled with that input's commonest color."""
import collections, json, os, sys
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agree_tables.py'); __file__ = f; T = sys.argv[1]; sys.argv = [f, 'x']
exec(open(f).read().split("if sys.argv[1] == 'one'")[0])
d = f'{W}/{T}'; j = json.load(open(f'{ROOT}/data/tasks/{T}.json')); n = len(j['train'])
blank = lambda g: [[collections.Counter(c for r in g for c in r).most_common(1)[0][0]] * len(g[0]) for _ in g]
os.makedirs(f'{d}/blank', exist_ok=True)
json.dump({'train': j['train'], 'test': [{'input': blank(p['input']), 'output': blank(p['input'])} for p in j['train']]}, open(f'{d}/blank/{T}.json', 'w'))
tb, amb = tables(f'{d}/prog', f'{d}/blank', T)
want = [t['table'] for t in json.load(open(f'{W}/{T}.one.json'))['tables']]
flags = {x: x in tb and all(tb[x].get((1, e), frozenset()) == tb[x].get((2, e), frozenset()) for e in range(n)) for x in want}
json.dump(flags, open(f'{W}/{T}.gridonly.json', 'w')); print(T, [x for x, v in flags.items() if v])
print(T, 'targets', len(want), 'with rows on blank', sum(any(tb.get(x, {}).get((2, e)) for e in range(n)) for x in want), 'in tables', sum(x in tb for x in want), 'ambiguous', len(amb), 'relations', len(tb))
