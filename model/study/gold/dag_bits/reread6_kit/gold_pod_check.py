"""The checks of check.sh. Each part prints what it read and `ok`, and exits 1 at the first failure.

  <runtime python> gold_pod_check.py limits SHARDS      the wheel, /proc, and the process, file and memory limits for SHARDS shards
  <runtime python> gold_pod_check.py group              the group memory count, the cap and the reaping, on test processes
  <runtime python> gold_pod_check.py rows ROWS EXPECTED the check rows against the rows that the Mac gave

On a Mac, the parts that read /proc are left out.
"""
import json, os, resource, signal, sys, tempfile, time
import gold_pod_run as R
import gold_pod_bits as P

LINUX = sys.platform == 'linux'
PROCS_A_SHARD = 3  # the shard's runner, the stem's process, and one in hand; the stem reads in its own process and forks nothing


def fail(why):
    print('FAIL', why, flush=True)
    sys.exit(1)


def read(path):
    try:
        return open(path).read().strip()
    except OSError:
        return None


def pids_limit():
    """The lowest of the limits on processes that hold here: the cgroup's pids.max and RLIMIT_NPROC, which does not bind root."""
    got = []
    for p in ('/sys/fs/cgroup/pids.max', '/sys/fs/cgroup/pids/pids.max'):
        x = read(p)
        if x and x != 'max':
            got.append((int(x), p))
    n = resource.getrlimit(resource.RLIMIT_NPROC)[0]
    if n != resource.RLIM_INFINITY and os.geteuid() != 0:
        got.append((n, 'ulimit -u'))
    return min(got, default=(None, 'none set'))


def limits(shards):
    R.check_wheel()
    print('wheel: arclog library hash', os.environ.get('ORCUT_SO_SHA256'), 'ok')
    P.load_sampler()
    threads = len(os.listdir('/proc/self/task')) if LINUX else 0
    need = shards * (PROCS_A_SHARD + threads)
    print('process need at %d shards: %d a shard, %d threads in a runner, %d in all; with a quarter over, %d' % (shards, PROCS_A_SHARD, threads, need, need * 5 // 4))
    lim, where = pids_limit()
    print('process limit:', lim, where)
    if lim is not None and lim < need * 5 // 4:
        fail('the process limit %d is under %d' % (lim, need * 5 // 4))
    hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    want = 256
    print('open files, hard limit:', hard, 'need', want)
    if hard != resource.RLIM_INFINITY and hard < want:
        fail('the hard limit on open files is under %d' % want)
    if not LINUX:
        print('limits ok (Mac: /proc not read)')
        return
    if R.one_bytes(os.getpid()) <= 0:
        fail('/proc/self/smaps_rollup gives no Pss')
    pid = os.fork()
    if pid == 0:
        os.setsid()
        time.sleep(1)
        os._exit(0)
    time.sleep(0.3)
    got, n = R.group_bytes(pid)
    os.waitpid(pid, 0)
    print('/proc: group count of a forked process:', got, 'bytes,', n, 'process')
    if got <= 0 or n != 1:
        fail('/proc does not give a forked process in its group, or its Pss')
    mem = read('/sys/fs/cgroup/memory.max') or read('/sys/fs/cgroup/memory/memory.limit_in_bytes')
    avail = next((int(l.split()[1]) << 10 for l in open('/proc/meminfo') if l.startswith('MemAvailable')), 0)
    room = min(avail, int(mem) if mem and mem != 'max' else avail)
    print('memory: available %.0f GiB, cgroup limit %s; all shards at their cap take %d GiB' % (avail / (1 << 30), mem, shards * 8))
    if room < shards * (8 << 30):
        print('WARNING: all shards at their cap would pass the memory here')
    print('limits ok')


def touch(n):
    a = bytearray(n)
    for i in range(0, n, 4096):
        a[i] = 1
    return a


class Spender:
    """A stage whose processes each stay under the cap while the group passes it. main forks four processes that each take a share and stay."""

    share = 0

    @staticmethod
    def sha(lines):
        return ''

    @staticmethod
    def setup(t, lines_path, seconds):
        pass

    @classmethod
    def main(cls):
        for _ in range(4):
            if os.fork() == 0:
                a = touch(cls.share)
                time.sleep(120)
                os._exit(len(a) and 0)
        time.sleep(120)


def group():
    # Shared pages count once: a process and six forks over one block, of which two write their own copy of a tenth.
    n = 1 << 30
    ready, go = os.pipe()  # the leader writes on go when its group stands
    leader = os.fork()
    if leader == 0:
        os.setsid()
        R.subreaper()
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        block = touch(n)
        for k in range(6):
            if os.fork() == 0:
                if k < 2:
                    for i in range(0, n // 10, 4096):
                        block[i] = 2
                time.sleep(30)
                os._exit(0)
        if os.fork() == 0:  # a process that ends and leaves a fork, as a dropped Node does
            if os.fork() == 0:
                time.sleep(1)
                os._exit(0)
            os._exit(0)
        os.write(go, b'x')
        time.sleep(30)
        os._exit(0)
    os.read(ready, 1)
    time.sleep(4)
    got, procs = R.group_bytes(leader)
    want = 1.2 * n
    print('group count: %.2f GiB over %d processes; the shared block and two tenths are %.2f GiB; the same pages counted in full in each process are over %.0f GiB' % (got / (1 << 30), procs, want / (1 << 30), 7 * n / (1 << 30)))
    if procs != 7:
        fail('the group has %d processes, not 7' % procs)
    if not 0.8 * want < got < 1.6 * want:
        fail('the group count is not the shared block once')
    if LINUX:
        zombies = [x for x in os.listdir('/proc') if x.isdigit() and (read('/proc/%s/stat' % x) or ') x x').rsplit(')', 1)[1].split()[0] == 'Z' and int(read('/proc/%s/stat' % x).rsplit(')', 1)[1].split()[2]) == leader]
        print('zombies of the group after an orphan ended:', len(zombies))
        if zombies:
            fail('an orphan of the group stayed as a zombie')
    os.killpg(leader, 9)
    os.waitpid(leader, 0)

    # The cap, set lower for the test: each process stays under it, and only the group's sum passes it.
    R.BYTES = 1 << 30
    Spender.share = 400 << 20
    R.STAGES['test'] = Spender
    d = tempfile.mkdtemp()
    t0 = time.time()
    row = R.run_stage('test', 'check', ['(OUT)'], d + '/rows-check.jsonl')
    print('cap: at 1 GiB, four processes of 0.4 GiB: error %s, peak %.2f GiB over %s processes, %.1f s' % (row.get('error'), row['peak_gib'], row['peak_procs'], time.time() - t0))
    if row.get('error') != 'memory':
        fail('the cap did not stop a group over it')
    if row['peak_gib'] <= 1 or row['peak_procs'] < 4:
        fail('the cap did not count the whole group')
    print('group ok')


def rows(path, expected):
    """Each expected entry is {task, lines, row}: `lines` the form lines that the run reads (POD_ONLY, or all where null), `row` the Mac's row of the stem. Per form: status and order count equal, bits within 0.05 (0.5 for a `bound` form), parts equal in key."""
    got = {}
    for l in open(path):
        try:
            r = json.loads(l)
            got[r['task']] = r
        except (json.JSONDecodeError, KeyError):
            continue
    for e in json.load(open(expected)):
        t, w = e['task'], e['row']
        r = got.get(t)
        if r is None:
            fail('no row for %s' % t)
        print(t, 'cpu', r.get('cpu'), 'wall', r.get('wall'), 'peak GiB', r.get('peak_gib'), 'processes', r.get('peak_procs'), 'error', r.get('error'), 'forms', len(r['forms']))
        if r.get('error') or not r.get('finished'):
            fail('%s did not finish' % t)
        if not r.get('peak_gib') or (r.get('peak_procs') or 0) < 1:
            fail('%s shows no memory count' % t)
        for k in ('base_sha', 'cap', 'budget', 'canon_kept'):
            if r.get(k) != w.get(k):
                fail('%s of %s is not the Mac\'s: %s against %s' % (k, t, r.get(k), w.get(k)))
        n = 0
        for wf in w['forms']:
            if wf['status'] == 'unread':
                continue
            f = next((x for x in r['forms'] if x['line'] == wf['line']), None)
            if f is None:
                fail('%s line %d has no form' % (t, wf['line']))
            tol = 0.5 if wf['status'] == 'bound' else 0.05
            if f['status'] != wf['status'] or f.get('orders') != wf.get('orders') and wf['status'] != 'bound' or (f['bits'] is None) != (wf['bits'] is None) or f['bits'] is not None and abs(f['bits'] - wf['bits']) > tol or sorted(f.get('parts') or ()) != sorted(wf.get('parts') or ()):
                fail('%s line %d is not the Mac\'s: %s against %s' % (t, wf['line'], {k: f.get(k) for k in ('status', 'orders', 'bits')}, {k: wf.get(k) for k in ('status', 'orders', 'bits')}))
            n += 1
        if any(x['status'] == 'unread' for x in r['forms'] if e['lines'] is None or x['line'] in e['lines']):
            fail('%s has forms unread' % t)
        print('  %d forms equal the Mac\'s' % n)
    print('rows ok')


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'limits':
        limits(int(sys.argv[2]))
    elif what == 'group':
        group()
    else:
        rows(sys.argv[2], sys.argv[3])
