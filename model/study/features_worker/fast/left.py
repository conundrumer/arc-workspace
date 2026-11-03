import collections, os, re, sys
s = sys.argv[1]; fx = 'work/lm/data-study/feat-exp/fstore-gen3/points'
c = collections.Counter(e.name[:8] for e in os.scandir(fx))
done = set(); run = False
for l in open(s + '/fast/gen3_build_t.log'):
    if l.startswith('=== merged run'):
        run = True; done = set()
    m = re.match(r'(\w{8}) built=', l)
    if m and run:
        done.add(m[1])
want = [t.strip() for t in open(s + '/fast/gen3_merged_tasks.txt') if t.strip()]
left = [t for t in dict.fromkeys(want) if t not in done]
n = [c[t] for t in left]
tot = sum(n)
print('store tasks', len(c), 'points', sum(c.values()), '| listed', len(set(want)), 'left', len(left), 'points in store for those', tot, 'with none', sum(x == 0 for x in n))
for cap in (500, 1000, 2000, 3000):
    print('cap', cap, 'points', sum(min(x, cap) for x in n), 'share', round(sum(min(x, cap) for x in n) / max(tot, 1), 2))
print('top', sorted(n)[-8:])
