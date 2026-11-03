"""Gold tables first matched by sample count and by seconds, per arm, on the tasks both arms finished.

  curve.py ARM_A ARM_B
"""
import glob, json, os, sys
TH = [25, 50, 100, 200, 400, 800, 1600, 3200]; TS = [10, 30, 60, 120, 240, 600]
A = sys.argv[1:3]
tasks = set.intersection(*[{os.path.basename(f)[:8] for f in glob.glob(a + '/*.done.json')} for a in A])
print('tasks', len(tasks))
for a in A:
    D = []; gold = n = 0
    for t in tasks:
        d = json.load(open(f'{a}/{t}.done.json')); gold += d['gold']; n += d['draws']
        for l in open(f'{a}/{t}.events.jsonl'):
            e = json.loads(l)
            if e.get('event') == 'cover':
                D.append((e['draw'], e['seconds'], e['depth']))
    print(a, 'tables matched', len(D), 'of', gold, 'samples per task', round(n / max(len(tasks), 1)), 'by samples', [sum(d <= t for d, *_ in D) for t in TH], 'by seconds', [sum(s <= t for _, s, _ in D) for t in TS], 'last', sorted(d for d, *_ in D)[-4:])
