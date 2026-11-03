"""Move the old points of the tasks with changed gold to a held folder, and their done records, so a build makes them again."""
import os, sys, time
FX = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3'
TASKS = set(sys.argv[2:]); HELD = f'{FX}/{sys.argv[1]}'
for st in ('points', 'points-t', 'points-ta'):
    os.makedirs(f'{HELD}/{st}', exist_ok=True)
    names = [e.name for e in os.scandir(f'{FX}/{st}') if e.name[:8] in TASKS]
    busy = [n for n in names if n.endswith('.building')]
    if busy:
        sys.exit(f'{st}: build in progress: {busy[:3]}')
    for n in names:
        os.rename(f'{FX}/{st}/{n}', f'{HELD}/{st}/{n}')
    print(time.strftime('%H:%M:%S'), st, {t: sum(n[:8] == t for n in names) for t in TASKS}, flush=True)
for t in TASKS:
    p = f'{FX}/points-t.cache/done/{t}.json'
    if os.path.exists(p):
        os.rename(p, f'{HELD}/{t}.done.json')
        print('done record moved', t, flush=True)
