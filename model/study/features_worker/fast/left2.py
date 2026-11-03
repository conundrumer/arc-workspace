import collections, os, re, sys
s = sys.argv[1]; fx = 'work/lm/data-study/feat-exp/fstore-gen3'
old = collections.Counter(e.name[:8] for e in os.scandir(fx + '/points'))
new = collections.Counter(e.name[:8] for e in os.scandir(fx + '/points-t'))
built = {}; run = False
for l in open(s + '/fast/gen3_build_t.log'):
    if l.startswith('=== merged run'):
        run = True; built = {}
    m = re.match(r'(\w{8}) built=(\d+) skipped=(\d+) failed=(\d+)', l)
    if m and run:
        built[m[1]] = int(m[2]) + int(m[3])
want = list(dict.fromkeys(t.strip() for t in open(s + '/fast/gen3_merged_tasks.txt') if t.strip()))
pairs = [(old[t], built[t]) for t in built if old[t]]
print('done in this run', len(built), 'old points', sum(a for a, _ in pairs), 'new points', sum(b for _, b in pairs), 'ratio', round(sum(b for _, b in pairs) / max(sum(a for a, _ in pairs), 1), 2))
left = [t for t in want if t not in built and new[t] == 0]
print('tasks left with no points in points-t', len(left), 'old points for them', sum(old[t] for t in left), 'with none', sum(old[t] == 0 for t in left), 'first', left[:6])
