"""Archive a point store task by task: <store>-tar/<task>.tar.zst. A task's folders go only after its archive passes zstd -t and lists every point. A rerun skips finished tasks.

  pack_store.py STORE K N
"""
import collections, os, shutil, subprocess, sys, time

store, K, N = sys.argv[1].rstrip('/'), int(sys.argv[2]), int(sys.argv[3])
root, name = os.path.split(store)
out = f'{store}-tar'
os.makedirs(out, exist_ok=True)
groups = collections.defaultdict(list)
for e in os.scandir(store):
    if not e.name.startswith('.') and e.is_dir(follow_symlinks=False):
        groups[e.name[:8]].append(e.name)
tasks = sorted(groups)[K::N]
print('tasks', len(tasks), 'points', sum(len(groups[t]) for t in tasks), flush=True)
t0 = time.time()


def free():
    return shutil.disk_usage(store).free / 2 ** 30


for i, t in enumerate(tasks, 1):
    names = sorted(groups[t]); a = f'{out}/{t}.tar.zst'; tmp = a + '.new'
    if not os.path.exists(a):
        lst = f'{out}/.{t}.list'
        with open(lst, 'w') as f:
            f.write('\n'.join(names) + '\n')
        subprocess.run(f"tar -C '{store}' -cf - -T '{lst}' | zstd -q -3 -T2 -o '{tmp}' --force", shell=True, check=True)
        os.remove(lst)
        os.replace(tmp, a)
    subprocess.run(['zstd', '-q', '-t', a], check=True)
    listed = subprocess.run(f"zstd -dc '{a}' | tar -tf - | cut -d/ -f1 | sort -u", shell=True, check=True, capture_output=True, text=True).stdout.split()
    missing = set(names) - set(listed)
    if missing:
        print('NOT REMOVED', t, 'missing', len(missing), flush=True)
        continue
    for n in names:
        shutil.rmtree(f'{store}/{n}')
    print(f'{i}/{len(tasks)} {t} {len(names)} points -> {os.path.getsize(a) / 2 ** 20:.1f} MB | {free():.1f} GiB free | {round(time.time() - t0)} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
