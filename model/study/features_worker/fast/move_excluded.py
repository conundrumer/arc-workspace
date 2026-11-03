"""Move the built points of cases in excluded-case-files.tsv from points/ to held-excluded-cases/, logging each move."""
import os, sys
S, FX, G = sys.argv[1:4]
ex = {(t, f.rsplit('.', 1)[0]) for t, f in (l.split('\t') for l in open(G + '/excluded-case-files.tsv').read().splitlines() if '\t' in l)}
rows = [l.split('\t') for l in open(S + '/fast/bad_case_points.tsv').read().splitlines() if l and not l.startswith('#')]
log = open(S + '/fast/move_excluded.log', 'a'); n = 0
for d, t, c, _ in rows:
    if (t, c.replace('$', '').replace(' ', '+')) not in ex:
        continue
    src, dst = f'{FX}/points/{d}', f'{FX}/held-excluded-cases/{d}'
    if os.path.isdir(src) and not os.path.exists(dst):
        os.rename(src, dst); log.write(d + '\n'); n += 1
        if n % 2000 == 0:
            log.flush(); print(n, flush=True)
print('moved', n)
