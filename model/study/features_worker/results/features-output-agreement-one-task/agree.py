"""One task: non-gold node tables added to gold's program, run on the real task and on the copy with inputs replaced by outputs. Prints how many tables agree, gold's against the nodes'."""
import json, os, re, subprocess, sys, random
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-output-side-parse-hand-clauses-5tasks')
from lib import *
T = sys.argv[1]; K = int(sys.argv[2]); R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-output-side-parse-hand-clauses-5tasks'; W = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-output-agreement-one-task'; N = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search'
norm = lambda r: frozenset(((n if not n[1:].isdigit() else ''), v) for n, v in r)
rows = [json.loads(l) for l in subprocess.run(['zstd', '-dcq', f'{N}/{T}.nodes.jsonl.zst'], capture_output=True, text=True).stdout.splitlines()]
by = {str(r['token']): r for r in rows}; seed = {t for t, r in by.items() if (r.get('tags') or {}).get('seeded')}
kind = lambda r: (r['clause'] or '')[1:].split(' ')[0]
def closure(t, s):
    if t in s: return True
    r = by[t]
    if t not in seed and kind(r) == 'DET': return False
    s.add(t)
    return all(closure(p, s) for p in r['parents'])
pick, heads = [], set(); random.seed(0); ids = [t for t in by if t not in seed and kind(by[t]) in ('RULE', 'INIT')]; random.shuffle(ids)
keep = set()
for t in ids:
    s = set()
    if closure(t, s):
        h = by[t]['clause'].split()[1]
        if h not in heads:
            keep |= s; heads.add(h); pick.append(t)
    if len(pick) == K: break
order = sorted(keep, key=int); seen = set(); extra = []
for t in order:
    c = by[t]['clause']; h = c.split()[1]
    if h not in seen: seen.add(h); extra.append(c)
g = open(f'{R}/f3cdc58f/naive/{T}.arclog').read()
i = g.index('(OUT')
extra = [re.sub(r'\(:(\w+) (\*?\^?)\1\)', r'\2\1', c) for c in extra]
prog = g[:i] + '\n'.join(extra) + '\n\n' + g[i:]
d = f'{W}/prog'; open(f'{d}/{T}.arclog', 'w').write(prog)
subprocess.run(['cp', f'{R}/f3cdc58f/naive/{T}.arcdata', d])
swap(f'{R}/tasks/{T}.json', f'{W}/{T}.swapped.json')
os.makedirs(f'{W}/t', exist_ok=True); subprocess.run(['cp', f'{W}/{T}.swapped.json', f'{W}/t/{T}.json'])
a = tables(d, f'{R}/tasks', T); b = tables(d, f'{W}/t', T)
print('tables real', len(a), 'swapped', len(b), 'clauses added', len(extra))
same = lambda n: n in b and a[n] and all({norm(r) for r in a[n][i]} == {norm(r) for r in b[n].get(i, ())} for i in a[n])
nonempty = lambda n: any(a[n][i] for i in a[n])
G = [n for n in a if not re.match(r'&f\d+', n) and n.startswith('&') and nonempty(n)]
P = [n for n in a if re.match(r'&f\d+', n) and nonempty(n)]
gold_rows = {tuple(sorted((i, frozenset(norm(r) for r in a[n][i])) for i in a[n])) for n in G}
dup = [n for n in P if tuple(sorted((i, frozenset(norm(r) for r in a[n][i])) for i in a[n])) in gold_rows]
print('gold tables', len(G), 'agree', sum(map(bool, map(same, G))), sorted(n for n in G if same(n))[:12])
print('node tables', len(P), 'agree', sum(map(bool, map(same, P))), 'of which equal a gold table', len(dup), 'agree among those', sum(map(bool, map(same, dup))))
