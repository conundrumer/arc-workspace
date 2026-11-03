"""Per main-DAG form on each task: its depth, gold or not, grid-only or not, whether a second-DAG table met it, and the depth of that table within the second DAG. Prints Spearman correlations."""
import ast, collections, os, re, sys
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agree_tables.py'); __file__ = f; sys.argv = [f, 'x']
exec(open(f).read().split("if sys.argv[1] == 'one'")[0])
def text_forms(s):
    out = {}
    for h in ('(RULE ', '(INIT ', '(DET ', '(DET_OR_RULE '):
        for a, b in forms(s, h):
            c = s[a:b]; n = c.split()[1]
            if n.startswith('&'): out[n] = out.get(n, '') + c
    return out
def own_depth(fs):
    memo = {}
    def d(h):
        if h in memo: return memo[h]
        memo[h] = 1; rs = {x.split('.')[0] for x in re.findall(r'&[\w.]+', fs[h])} - {h}
        memo[h] = 1 + max([d(r) for r in rs if r in fs], default=0); return memo[h]
    return {h: d(h) for h in fs}
def closure(h, fs, s):
    if h in s or h not in fs: return s
    s.add(h)
    for x in re.findall(r'&[\w.]+', fs[h]): closure(x.split('.')[0], fs, s)
    return s
pts = []
for T in ('1f642eb9', 'e2092e0c', 'e1d2900e'):
    prog = open(f'{W}/{T}/second/{T}.arclog').read(); fs = text_forms(prog)
    sec = {h: c for h, c in fs.items() if h.startswith(('&b_', '&g_'))}; sd = own_depth(sec)
    c = arclog.corpus_tables(f'{W}/{T}/second', f'{W}/{T}/real', task_ids=[T], all_cases=False, table_work_cap=1 << 36)[0][0]
    dep = array.array('I'); dep.frombytes(c.tables['depth']); md = collections.defaultdict(int)
    for i, n in enumerate(c.tables['relation_name']):
        if n: md[n.split('.')[0]] = max(md[n.split('.')[0]], dep[i])
    p = f'{W}/{T}.second.txt' if os.path.exists(f'{W}/{T}.second.txt') else f'{W}/second.txt'
    forms_ = {}
    for l in open(p):
        m = re.match(r'(gold|node) (\S+) (.*)', l)
        if not m: continue
        h = m[2].split('.')[0]; e = forms_.setdefault(h, {'gold': m[1] == 'gold', 'met': 0, 'part': 0, 'd2': []})
        if m[3].startswith('['):
            hits = ast.literal_eval(m[3]); e['met'] = 1
            whole = [x for x in hits if 'some columns' not in x] or hits
            e['d2'].append(min(sd.get(x.split()[0].split('.')[0], 99) for x in whole))
        elif 'columns' in m[3]: e['part'] = 1
    for h, e in forms_.items():
        grid = 0 if e['gold'] else int(not any(re.search(r'\bCol|color|_Col|ex_input', fs.get(x, '')) for x in closure(h, fs, set())))
        pts.append(dict(task=T, form=h, gold=int(e['gold']), grid=grid, main_depth=md[h], met=e['met'], part=int(e['met'] or e['part']), second_depth=min(e['d2']) if e['d2'] else None))
def rank(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r
def sp(a, b):
    ra, rb = rank(a), rank(b); ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    sa = sum((x - ma) ** 2 for x in ra) ** .5; sb = sum((x - mb) ** 2 for x in rb) ** .5
    return None if not sa or not sb else sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / sa / sb
V = ['gold', 'grid', 'main_depth', 'met', 'part']
def matrix(ps, name):
    print(f'\n{name}: forms {len(ps)}'); print(' ' * 12 + ''.join(f'{v:>11}' for v in V))
    for a in V:
        print(f'{a:12}' + ''.join(f'{(lambda r: "." if r is None else f"{r:+.2f}")(sp([p[a] for p in ps], [p[b] for p in ps])):>11}' for b in V))
for T in ('1f642eb9', 'e2092e0c', 'e1d2900e', None):
    ps = [p for p in pts if T is None or p['task'] == T]; matrix(ps, T or 'pooled')
    m = [p for p in ps if p['second_depth'] is not None]; r = sp([p['main_depth'] for p in m], [p['second_depth'] for p in m]) if len(m) > 2 else None
    print('main depth against second depth, met forms:', len(m), 'spearman', None if r is None else round(r, 2))
    for s, k in (('gold', lambda p: p['gold']), ('non-gold, content', lambda p: not p['gold'] and not p['grid']), ('non-gold, grid-only', lambda p: not p['gold'] and p['grid'])):
        q = [p for p in ps if k(p)]
        if q:
            mq = [p for p in q if p['second_depth'] is not None]; avg = lambda x: round(sum(x) / len(x), 2) if x else None
            print(f'  {s:20} forms {len(q):3}  main depth mean {avg([p["main_depth"] for p in q])} max {max(p["main_depth"] for p in q)}  met {len(mq):3}  met or part {sum(p["part"] for p in q):3}  second depth mean {avg([p["second_depth"] for p in mq])} max {max([p["second_depth"] for p in mq], default=None)}')
    if T:
        by = collections.defaultdict(lambda: [0, 0])
        for p in ps: by[p['main_depth']][0] += 1; by[p['main_depth']][1] += p['met']
        print('  depth: forms/met', ' '.join(f'{d}:{a}/{b}' for d, (a, b) in sorted(by.items())))
