"""Stream the built points whose case the gold step excluded (no case file under cases/<task>/) or whose gold does not
fit TRAIN (gold-not-fitting-train.tsv). Writes one line per such point: dir, task, case, reason. Resumes from its output."""
import json, os, sys
from pathlib import Path
P = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points')
G = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gen-v3-11f6a212c')
OUT = Path(sys.argv[1])
unfit = {tuple(l.split('\t', 1)) for l in (G / 'gold-not-fitting-train.tsv').read_text().splitlines() if '\t' in l}
stems = {}
def shipped(task):
    if task not in stems:
        d = G / 'corpus/gen/cases' / task
        stems[task] = {p.stem for p in d.glob('*.arclog')} if d.is_dir() else None
    return stems[task]
done = set()
if OUT.exists():
    done = {l.split('\t', 1)[0] for l in OUT.read_text().splitlines() if l and not l.startswith('#')}
names = sorted(n for n in os.listdir(P) if not n.startswith('.') and not n.endswith('.building'))
mark = OUT.with_suffix('.scanned')
start = int(mark.read_text()) if mark.exists() else 0
with open(OUT, 'a') as out:
    for i in range(start, len(names)):
        n = names[i]
        try:
            head = open(P / n / 'point.json').read(4000)
            j = head.index('"case"'); t = head.index('"task"')
            case = json.loads('{' + head[j:head.index('",', j) + 1] + '}')['case']
            task = json.loads('{' + head[t:head.index('",', t) + 1] + '}')['task']
        except Exception as e:
            out.write(f'# {n}\tunreadable: {e}\n'); continue
        s = shipped(task)
        reason = ('excluded' if s is not None and case.replace('$', '').replace(' ', '+') not in s
                  else 'unfit' if (task, case) in unfit else None)
        if reason and n not in done:
            out.write(f'{n}\t{task}\t{case}\t{reason}\n')
        if i % 5000 == 0:
            out.flush(); mark.write_text(str(i)); print(f'{i}/{len(names)}', flush=True)
mark.write_text(str(len(names))); print('done', len(names))
