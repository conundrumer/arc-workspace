"""Compress a point store in place with APFS compression, task by task. Paths stay as they are. Each inode goes to afsctool once, because afsctool emptied hard-linked files when two of its threads reached one inode. A task is listed in <store>.squeezed when it ends, and a rerun skips it. A task stops the run if a file changes from non-empty to empty.

  squeeze.py STORE K N [TASK ...]
"""
import collections, os, shutil, stat, subprocess, sys, time

store, K, N = sys.argv[1].rstrip('/'), int(sys.argv[2]), int(sys.argv[3])
only = set(sys.argv[4:])
mark = f'{store}.squeezed'
done = set(open(mark).read().split()) if os.path.exists(mark) else set()
groups = collections.defaultdict(list)
for e in os.scandir(store):
    if e.name.startswith('.') or e.name.endswith('.building') or not e.is_dir(follow_symlinks=False):
        continue
    groups[e.name[:8]].append(e.path)
tasks = [t for t in sorted(groups) if t not in done and (not only or t in only)][K::N]
print('tasks', len(tasks), 'points', sum(len(groups[t]) for t in tasks), flush=True)
t0 = time.time()
pts = 0


def free():
    return shutil.disk_usage(store).free / 2 ** 30


def walk(folders):
    """Each file as (path, stat), one path per inode, and the count of paths."""
    seen, out = set(), []
    for d in folders:
        for r, _, fs in os.walk(d):
            for f in fs:
                p = os.path.join(r, f); st = os.lstat(p)
                if stat.S_ISREG(st.st_mode) and st.st_ino not in seen:
                    seen.add(st.st_ino); out.append((p, st))
    return out


for i, t in enumerate(tasks, 1):
    files = walk(groups[t])
    todo = [p for p, st in files if st.st_size and not st.st_flags & stat.UF_COMPRESSED]
    for b in range(0, len(todo), 2000):
        subprocess.run(['afsctool', '-c', '-T', 'LZFSE', '-J3', *todo[b:b + 2000]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sizes = {p: st.st_size for p, st in files}
    lost = [p for p in sizes if os.lstat(p).st_size != sizes[p]]
    if lost:
        print('SIZE CHANGED', t, len(lost), lost[:3], flush=True)
        sys.exit(1)
    with open(mark, 'a') as f:
        f.write(t + '\n')
    pts += len(groups[t])
    el = time.time() - t0
    print(f'{i}/{len(tasks)} {t} {len(groups[t])} points {len(todo)} files | {free():.1f} GiB free | {round(el)} s | {pts / el:.0f} points/s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
