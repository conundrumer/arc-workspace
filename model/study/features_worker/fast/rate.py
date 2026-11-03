import re, sys
s = sys.argv[1]
rows = []
run = False
for l in open(s + '/fast/gen3_build_t.log'):
    if l.startswith('=== merged run'):
        run = True; rows = []
    m = re.match(r'(\w{8}) built=(\d+) skipped=(\d+) failed=(\d+) in ([\d.]+)s', l)
    if m and run:
        rows.append((m[1], int(m[2]), int(m[3]), int(m[4]), float(m[5])))
T = sum(r[4] for r in rows); B = sum(r[1] for r in rows); n = len(rows)
print('tasks', n, 'built', B, 'failed', sum(r[3] for r in rows), 'worker-hours', round(T / 3600, 1), 'worker-s per built point', round(T / max(B, 1), 3))
rows.sort(key=lambda r: -r[4])
c = 0
for i, r in enumerate(rows[:12]):
    c += r[4]; print(r, round(r[4] / max(r[1], 1), 2), 's/pt', 'cum share', round(c / T, 2))
z = [r for r in rows if r[1] == 0]; print('tasks with nothing built', len(z), 'sec', round(sum(r[4] for r in z)))
