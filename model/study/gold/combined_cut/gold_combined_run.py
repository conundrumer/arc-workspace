"""Runs the two cut stages on a shard of the stems: the extended cut, then the shape cut on the extended cut's result. Each stage of each stem is one process group under 900 s and 8 GiB over the group, with no retry at a higher bound. The sampler loads once here, and each stage of a stem is a fork of this process. One row per stage per stem, streamed.

  <runtime python> gold_combined_run.py TASKS.txt LINES.json WEIGHTS.json OUT.jsonl SHARD SHARDS

TASKS.txt lists the stems in the order they run, with a blank line between tiers. A tier goes to the shards by stem weight, heaviest first, each stem to the shard with the least weight so far, so each tier is balanced and a shard runs the tiers in order. WEIGHTS.json maps a stem to its weight. LINES.json maps a stem to its forms, the extended cut's start text.
Each row has `stage`, `ext` or `shape`, and `base_sha`, the hash of that stage's start text. The shape cut's start text is the `program` of the stem's ext row, or the extended cut's start text where that row has no program. A stem past a cap keeps the state of its last landing, which passed the bar, with `error` set, and the shape cut starts from that state.
A restart skips a stage whose row is in OUT or in a rows-*.jsonl beside it, with the same start text and, for the shape cut, the same BAR and LANDING. So a stage whose text or settings changed runs again, and the same shard count is not needed.
Environment: COMBINED_STAGES, the stages to run (default `ext shape`; with `shape` alone, LINES.json is the shape cut's start text). ORCUT_SO_SHA256, where set, is the hash that the arclog library has to have. BAR, LANDING and ORCUT_KEPT_NODES go to the stages.
"""
import ctypes, glob, hashlib, json, os, resource, signal, subprocess, sys, tempfile, time, traceback, warnings
warnings.filterwarnings('ignore', 'This process .* is multi-threaded', DeprecationWarning)  # the forks of the stages step no thread of this process
import gold_fork_reads as F
import gold_orcut_base as B
import gold_orcut_one as E
import gold_shapecut_one as S

SECONDS, SOFT, BYTES = 900, 840, 8 << 30
SCAN_EVERY, SCAN_SHARE = 2.0, 0.1  # a memory scan runs at most this often, and takes at most this share of one CPU
STAGES = {'ext': E, 'shape': S}
here = os.path.dirname(os.path.abspath(__file__))


def assign(tiers, weights, n):
    """The stems of each shard, tier by tier, in tier order."""
    load, shards = [0.0] * n, [[] for _ in range(n)]
    for tier in tiers:
        got = [[] for _ in range(n)]
        for t in sorted(tier, key=lambda t: (-weights.get(t, 1.0), t)):
            k = min(range(n), key=lambda j: (load[j], j))
            load[k] += weights.get(t, 1.0)
            got[k].append(t)
        for k in range(n):
            shards[k] += [t for t in tier if t in set(got[k])]
    return shards


def tiers_of(path):
    return [x.split() for x in open(path).read().split('\n\n') if x.strip()]


def sampler_hash():
    c = os.environ['SAMPLER_CODE']
    return hashlib.sha256(b''.join(open(os.path.join(c, f), 'rb').read() for f in ('live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py'))).hexdigest()[:12]


def stage_hash():
    files = ('gold_fork_reads.py', 'gold_orcut_one.py', 'gold_extcut_cuts.py', 'gold_shapecut_one.py', 'gold_shapecut_cuts.py', 'gold_shapecut_shapes.py', 'gold_orcut_cuts.py')
    return hashlib.sha256(b''.join(open(os.path.join(here, f), 'rb').read() for f in files)).hexdigest()[:12]


def key_of(stage, task, sha):
    return (stage, task, sha) + ((S.BAR, S.RULE) if stage == 'shape' else ())


def rows_done(out):
    """The stages done, each key with the row's program. A row cut short by a kill does not parse and counts as not done."""
    done = {}
    for p in {os.path.abspath(out)} | {os.path.abspath(x) for x in glob.glob(os.path.join(os.path.dirname(os.path.abspath(out)), 'rows-*.jsonl'))}:
        if os.path.exists(p):
            for l in open(p):
                try:
                    r = json.loads(l)
                    done[key_of(r['stage'], r['task'], r.get('base_sha'))] = r.get('program')
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def end_line(path):
    """Ends a line that a kill left open, so that the next row starts on a line of its own."""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, 'rb+') as f:
            f.seek(-1, 2)
            if f.read(1) != b'\n':
                f.write(b'\n')


def subreaper():
    """Makes this process the parent of the orphans under it. A Node that is dropped leaves its forks as orphans, and the PID 1 of a container may never reap them, so their zombies would count against the process limit."""
    if sys.platform == 'linux':
        ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER


def child(M, t, lines_path, outp, out):
    """The stage of stem t, in a forked process, with its rows in outp. Never returns."""
    code = 1
    try:
        os.setsid()
        subreaper()
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)  # this process never waits, so its orphans go at once
        os.chdir(here)
        if sys.platform == 'linux':
            resource.setrlimit(resource.RLIMIT_AS, (2 * BYTES, 2 * BYTES))
        os.dup2(os.open(outp, os.O_WRONLY | os.O_APPEND), 1)
        os.dup2(os.open(out + '.log', os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644), 2)
        M.setup(t, lines_path, SOFT)
        M.main()
        code = 0
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        os._exit(code)


def one_bytes(pid):
    """The bytes that count against process pid, with a page shared by forks not counted in full: PSS on Linux, the physical footprint on the Mac. 0 where the process has gone."""
    try:
        if sys.platform == 'linux':
            for l in open('/proc/%d/smaps_rollup' % pid):
                if l.startswith('Pss:'):
                    return int(l.split()[1]) * 1024
            return 0
        info = (ctypes.c_uint64 * 40)()
        lib = ctypes.CDLL('/usr/lib/libproc.dylib')
        return info[9] if lib.proc_pid_rusage(pid, 0, info) == 0 else 0  # rusage_info_v0: ri_phys_footprint is word 9
    except (OSError, IndexError, ValueError):
        return 0


def group_bytes(leader):
    """The bytes of the process group of leader, and its count of processes."""
    if sys.platform == 'linux':
        q = []
        for x in os.listdir('/proc'):
            try:
                if x.isdigit() and int(open('/proc/%s/stat' % x).read().rsplit(')', 1)[1].split()[2]) == leader:
                    q.append(x)
            except (OSError, IndexError, ValueError):
                pass
    else:
        q = subprocess.run(['pgrep', '-g', str(leader)], capture_output=True, text=True).stdout.split()
    return sum(one_bytes(int(x)) for x in q), len(q)


def reap(leader):
    """Reaps every child that has ended, the orphans that this process adopted among them. The wait status of leader, or None."""
    status = None
    while True:
        try:
            pid, st = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return status
        if pid == 0:
            return status
        if pid == leader:
            status = st


def sweep(leader):
    """Ends what is left of the group of leader, and reaps it."""
    try:
        os.killpg(leader, 9)
    except (ProcessLookupError, PermissionError):
        pass
    until = time.time() + 5
    while time.time() < until:
        reap(leader)
        try:
            os.killpg(leader, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.02)


def run_stage(stage, t, lines, out):
    """One stage of one stem under the caps: its row."""
    M = STAGES[stage]
    t0, peak, procs, killed, scan_at = time.time(), 0, 0, None, 0.0
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump({t: lines}, f)
        lp = f.name
    outp = lp + '.out'
    open(outp, 'w').close()
    sys.stdout.flush()
    pid = os.fork()
    if pid == 0:
        child(M, t, lp, outp, os.path.abspath(out))
    status = None
    while status is None and killed is None:
        time.sleep(0.2)
        status = reap(pid)
        now = time.time()
        if status is None and now >= scan_at:
            got, n = group_bytes(pid)
            scan_at = time.time() + max(SCAN_EVERY, (time.time() - now) / SCAN_SHARE)
            peak, procs = max(peak, got), max(procs, n)
        killed = 'time' if now - t0 > SECONDS else 'memory' if peak > BYTES else None
    sweep(pid)
    if status is None:
        status = reap(pid)
    rows = [l for l in open(outp) if l.startswith('{"task"')]
    os.remove(lp)
    os.remove(outp)
    row = None
    if rows:
        try:
            row = json.loads(rows[-1])
        except json.JSONDecodeError:
            row = json.loads(rows[-2]) if len(rows) > 1 else None
    if row is None:
        row = dict(task=t, base_sha=B.sha(lines), error=killed or 'no row, exit %s' % (None if status is None else os.waitstatus_to_exitcode(status)))
        if stage == 'shape':
            row.update(bar=S.BAR, rule=S.RULE)
    elif killed or not row.get('finished'):
        row['error'] = killed or 'exit %s' % (None if status is None else os.waitstatus_to_exitcode(status))
    row.update(stage=stage, wall=round(time.time() - t0, 1), peak_gib=round(peak / (1 << 30), 2), peak_procs=procs, code=sampler_hash(), stage_code=stage_hash())
    return row


def check_wheel():
    want = os.environ.get('ORCUT_SO_SHA256')
    if want:
        import arclog
        if hashlib.sha256(open(os.path.join(os.path.dirname(arclog.__file__), 'arclog.abi3.so'), 'rb').read()).hexdigest() != want:
            sys.exit('arclog is not the wheel of the manifest')


def main():
    tasks, lines_path, weights_path, out, k, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
    stages = os.environ.get('COMBINED_STAGES', 'ext shape').split()
    check_wheel()
    subreaper()
    done = rows_done(out)
    text = json.load(open(lines_path))
    mine = assign(tiers_of(tasks), json.load(open(weights_path)), n)[k]
    F.load_sampler()
    end_line(out)
    with open(out, 'a') as f:
        for t in mine:
            lines = text.get(t)
            if not lines:
                continue
            for stage in stages:
                key = key_of(stage, t, B.sha(lines))
                if key in done:
                    program = done[key]
                else:
                    row = run_stage(stage, t, lines, out)
                    f.write(json.dumps(row) + '\n')
                    f.flush()
                    a, b = row.get('before') or {}, row.get('after') or {}
                    print(t, stage, row.get('error', ''), 'landed' if row.get('landed') else '', a.get('worst'), b.get('worst'), row['wall'], flush=True)
                    program = row.get('program')
                if program:
                    lines = B.split(program)


if __name__ == '__main__':
    main()
