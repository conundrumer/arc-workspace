"""Stop on any case file of <corpus gen dir>/cases that an `exclude` record of the task's arcdata in <converted gen dir> leaves out.
usage: check_excluded.py <corpus gen dir> <converted gen dir>"""
import os, re, sys
corpus, conv = sys.argv[1:]
cases = f'{corpus}/cases'
bad = 0
for t in sorted(os.listdir(cases)) if os.path.isdir(cases) else []:
    p = f'{conv}/{t}.arcdata'
    exc = [{x.replace('$', '') for x in m.group(1).split()} for m in re.finditer(r'\(exclude \(([^()]*)\)', open(p).read())] if os.path.exists(p) else []
    for f in os.listdir(f'{cases}/{t}'):
        if f.endswith('.arclog') and any(e <= set(f[:-7].split('+')) for e in exc):
            bad += 1; print('EXCLUDED CASE FILE', t, f, flush=True)
print(f'check_excluded: {bad} excluded case files in {corpus}')
sys.exit(1 if bad else 0)
