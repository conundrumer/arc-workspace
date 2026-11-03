"""Move each task that the second pass finished (points-ta.cache/done/<task>.json) into points-t: the task's kept-only points go to
points-t-keptonly/, then the new points move in. Polls every 60 s; stops after the pass log prints 'finished' and every done task is moved."""
import os
import sys
import time

FX = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3'
LOG = sys.argv[1]
OLD = f'{FX}/points-t-keptonly'
os.makedirs(OLD, exist_ok=True)
moved = set()
while True:
    finished = 'finished:' in open(LOG).read().split('=== second pass')[-1]
    done = {f[:-5] for f in os.listdir(f'{FX}/points-ta.cache/done')} - moved
    if done:
        new = {}
        for e in os.scandir(f'{FX}/points-ta'):
            if e.name[:8] in done and not e.name.endswith('.building'):
                new.setdefault(e.name[:8], []).append(e.name)
        old = {}
        for e in os.scandir(f'{FX}/points-t'):
            if e.name[:8] in done and not e.name.endswith('.building'):
                old.setdefault(e.name[:8], []).append(e.name)
        for t in sorted(done):
            for n in old.get(t, []):
                os.rename(f'{FX}/points-t/{n}', f'{OLD}/{n}')
            for n in new.get(t, []):
                os.rename(f'{FX}/points-ta/{n}', f'{FX}/points-t/{n}')
            moved.add(t)
            print(f'{time.strftime("%H:%M:%S")} {t}: {len(old.get(t, []))} out, {len(new.get(t, []))} in', flush=True)
    if finished and not ({f[:-5] for f in os.listdir(f'{FX}/points-ta.cache/done')} - moved):
        break
    time.sleep(60)
print('swap done', len(moved), 'tasks', flush=True)
