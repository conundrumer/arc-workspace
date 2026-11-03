#!/usr/bin/env python
"""One worker of engine/kaggle/synth/supervisor.py: grows a program bank on one task, and writes each candidate program as it is found.

Exit status 0: the time ended, or the bank reached MAX_FORMS, which leaves no bank file. Exit status 3: the bank alone fills the memory, or
a renewal failed. The supervisor starts a new worker with a new seed in each case while the task has time left.

The bank is the worker's state and a table is a cache of a form, so the bank lives in the bank file and the tables live only in the
process. Where RSS reaches RENEW_SHARE of the limit, the worker writes the bank file and replaces itself with execv, which frees all of
the tables whoever holds them. The new process reads the bank file and computes again the tables that later samples read. A worker that
a crash or a kill ended loses only the forms made since the last write of the bank file, since the worker that follows reads that file.

A merge key compares within one process, so a new process starts with no keys, and a clause an older process saw may enter the bank again.

POOL_CLAUSES gives the source of the pool's clauses: draws from Pool.draw, or search from superdag_search.py. A task file named <id>.draws.task.json or
<id>.search.task.json overrides it for that task. A search keeps its state under $ARC_STORE/<task file name>, so that the workers of a task go on from it.
"""
import argparse
import ctypes
import faulthandler
import json
import os
import pickle
import sys
import time

MAX_FORMS = 30000
RENEW_SHARE = float(os.environ.get('ARC_RENEW_SHARE', 0.6))  # of --rss-limit-mib, where the worker renews its process
BANK_SHARE = 0.8  # of the RSS that starts a renewal, the most a process may hold after it reads the bank file
SESSION_SHARE = float(os.environ.get('ARC_SESSION_SHARE', 0.4))  # of --rss-limit-mib, for the session's byte bound; the result cache takes half, under the DET memos, Python and one form's work
FOLD_SHARE = 0.07  # of --rss-limit-mib, for each leave-one-out session
MAX_CANDIDATES = 2000
BEAT_SECONDS = 20
PROGRESS_SECONDS = 10
JUMP_MIB = 100  # a change of RSS between two scopes that the log reports
SAVE_SECONDS = 120
RECORD_BYTES = 1 << 32  # the most one process writes to its record files, compressed
RECORD_FILE_BYTES = 1 << 27  # the most one record file holds, under the supervisor's limit on a file
RECORD_LEVEL = 3
RECORD_WINDOW_LOG = 24
MIN_RENEW_SECONDS = 30  # a process with less time left than this runs out its time
COUNT_PREFIXES = ('kept:', 'drop:', 'search:', 'choose')  # the counters that a progress line and the end line print
POLICY_FIXED = ('names', 'ix', 'model', 'pairs', 'scope')  # attributes of a Policy that its constructor or superdag_search.py makes
PROC = '%x-%x' % (os.getpid(), time.time_ns())  # names this process; renew() starts a process with execv, which imports this module again, so that process has a new name
PICKS = [0]  # the scope picks this process has written to the picks file


def rss_mib():
    try:
        with open('/proc/self/statm') as f:
            return int(f.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 2 ** 20
    except OSError:
        return mac_footprint() / 2 ** 20


def mac_footprint():
    """The process's physical footprint on macOS, which counts compressed pages where RSS does not."""
    buf = (ctypes.c_uint64 * 64)()
    ctypes.CDLL('libproc.dylib').proc_pid_rusage(os.getpid(), 0, buf)  # RUSAGE_INFO_V0: ri_phys_footprint follows 16 bytes of uuid and 7 counters
    return buf[9]


def write_bank(path, pool, found, generation):
    """Replaces the bank file in one step. Gives False where it could not, and the bank file stays as it was."""
    pool.lineage[-1].update(nodes1=len(pool.nodes), picks1=PICKS[0])
    state = dict(forms=pool.forms, nodes=pool.nodes, draws=pool.draws, found=found, generation=generation, lineage=pool.lineage,
                 policy={k: v for k, v in vars(pool.policy).items() if k not in POLICY_FIXED})
    try:
        with open(path + '.tmp', 'wb') as f:
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(path + '.tmp', path)
        return True
    except Exception as e:  # noqa: BLE001
        print('bank not written:', repr(e)[:300], flush=True)
        return False


def read_bank(path, pool):
    """Fills pool from the bank file. Gives (candidates found, generation), which are 0 where no bank file can be read. Sets pool.lineage to the processes
    that wrote the file, a dict each with the node and pick counts it ended with, and to [] where no bank file can be read."""
    pool.lineage = []
    try:
        with open(path, 'rb') as f:
            state = pickle.load(f)
        pool.forms, pool.nodes, pool.draws = state['forms'], state['nodes'], state['draws']
        pool.rebuild_maps()  # defs, keys and hash_count: a known query stays known after a renewal
        vars(pool.policy).update(state['policy'])
        pool.lineage = state.get('lineage', [])
        return state['found'], state['generation'] + 1
    except FileNotFoundError:
        return 0, 0
    except Exception as e:  # noqa: BLE001
        print('bank not read:', repr(e)[:300], flush=True)
        return 0, 0


def compression():
    """The record files' suffix and a function that gives a new file's (compress, finish). Each record is flushed, so a process that dies leaves whole records up to the last
    one it wrote, in a frame with no end, which a stream reader reads. Plain text where zstandard cannot load."""
    try:
        import zstandard as z
        params = z.ZstdCompressionParameters.from_level(RECORD_LEVEL, window_log=RECORD_WINDOW_LOG, enable_ldm=True)

        def stream():
            c = z.ZstdCompressor(compression_params=params).compressobj()
            return (lambda data: c.compress(data) + c.flush(z.COMPRESSOBJ_FLUSH_BLOCK)), c.flush
        return '.zst', stream
    except Exception as e:  # noqa: BLE001
        print('records not compressed:', repr(e)[:300], flush=True)
        return '', lambda: ((lambda data: data), (lambda: b''))


def recorder(path):
    """A function that appends each node record to the numbered files path.NNN.nodes.jsonl.zst, each up to RECORD_FILE_BYTES. Its close attribute ends the last file. No failure
    of it reaches the worker: after the first failure it writes nothing."""
    suffix, stream = compression()
    room, f, part, left, pack, finish = RECORD_BYTES, None, 0, 0, None, None

    def close():
        nonlocal f
        if f:
            f.write(finish())
            f.close()
            f = None

    def write(record):
        nonlocal room, f, part, left, pack, finish
        if room <= 0:
            return
        try:
            if left <= 0:
                close()
                f = open('%s.%03d.nodes.jsonl%s' % (path, part, suffix), 'ab')
                pack, finish = stream()
                part, left = part + 1, RECORD_FILE_BYTES
            data = pack((json.dumps(record) + '\n').encode())
            room, left = room - len(data), left - len(data)
            f.write(data)
            f.flush()
        except Exception as e:  # noqa: BLE001
            room = 0
            print('record stopped:', repr(e)[:300], flush=True)

    def close_safely():
        try:
            close()
        except Exception as e:  # noqa: BLE001
            print('record not closed:', repr(e)[:300], flush=True)
    write.close = close_safely
    return write


def renew(seconds, seed):
    """Replaces this process with a new worker that has the time left and the next seed. The process id, the log and the limits stay."""
    argv = list(sys.orig_argv)
    argv[argv.index('--seconds') + 1] = '%.0f' % seconds
    argv[argv.index('--seed') + 1] = str(seed if os.environ.get('ARC_RENEW_SAME_SEED') else seed + 1)
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + argv[1:])


def source(a, sampler):
    """The superdag_search module where this task's clauses come from search, installed, else None. A search that cannot start leaves draws."""
    name = os.path.basename(a.task)
    path = next((p for p in ('search', 'draws') if '.%s.' % p in name), os.environ.get('POOL_CLAUSES', 'draws'))
    print('pool clauses:', path, flush=True)
    if path != 'search':
        return None
    try:
        import superdag_search as search
        search.is_panic = lambda e: False  # a panic ends the worker, since the session is unusable after one, and the Journal skips its path
        search.attach(sampler, store_of(name, a.out), a.rss_limit_mib)
        search.install('search')
        return search
    except Exception as e:  # noqa: BLE001
        print('pool clauses: draws, search failed:', repr(e)[:300], flush=True)
        return None


def store_of(name, out):
    return os.path.join(os.environ['ARC_STORE'], name) if os.environ.get('ARC_STORE') else out + '.store'


def main():
    faulthandler.enable()
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--beat', required=True)
    ap.add_argument('--bank', default='', help='the bank file; default: --out with .bank added')
    ap.add_argument('--seconds', type=float, required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--rss-limit-mib', type=int, required=True)
    ap.add_argument('--models', default=os.environ.get('ARC_MODELS', ''))
    ap.add_argument('--policy', default=os.environ.get('ARC_POLICY', ''))
    ap.add_argument('--k', type=int, default=6)
    ap.add_argument('--draws-per-scope', type=int, default=4)
    a = ap.parse_args()
    bank = a.bank or a.out + '.bank'
    t0 = time.monotonic()
    deadline = t0 + a.seconds

    def beat():
        os.utime(a.beat)
    beat()
    import superdag as D
    live, arclog = D.live, D.arclog
    live.FOLD_BYTES = int(a.rss_limit_mib * FOLD_SHARE) << 20
    D.SESSION_BYTES = int(a.rss_limit_mib * SESSION_SHARE) << 20
    try:
        if os.environ.get('ARC_STEERS_OFF'):
            raise RuntimeError('steers off by request')
        sampler = live.Sampler(a.models)
    except Exception as e:  # noqa: BLE001
        print('steers off:', repr(e)[:300], flush=True)
        sampler = live.Sampler(a.models, steers=())
    beat()
    with open(a.task) as f:
        task = json.load(f)
    for t in task['test']:
        t.pop('output', None)
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)

    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=D.SESSION_BYTES)
    run = D.Run(sampler.pri, session, a.seed, deadline, task, live.Limits())
    a.t0, a.out_path = t0, a.out
    out = open(a.out, 'a')
    count = [0]

    search = source(a, sampler)  # before gold_keys: source() installs the order-free table_key that the pool uses, so gold keys come after it
    gold = {}
    if os.environ.get('ARC_GOLD'):  # the cover check of a study run, which reads gold and writes only to the cover file
        tid = os.path.basename(a.task).split('.')[0]
        specs = {x['task']: x['gold_sexp'] for x in json.load(open(os.environ['ARC_GOLD']))}
        gold = D.gold_keys(run, specs[tid]) if tid in specs else {}
    covers = open(a.out + '.cover', 'a')
    covers2 = open(a.out + '.cover2', 'a')
    visits = open(a.out + '.visits', 'a')
    picks = open(a.out + '.picks', 'a')

    def event(x):
        if x.get('event') == 'cover2':
            covers2.write(json.dumps(dict(gold=x['gold'], draw=x['draw'], time=time.time())) + '\n')
            covers2.flush()
        if x.get('event') == 'visit':  # with SEARCH_LOG_VISITS: the slot's forms, its kind, whether it resumed a parked slot
            visits.write(json.dumps(dict(fids=x['fids'], kind=x['kind'], resume=x['resume'], tries=x['tries'], new=x['new'], seconds=x['seconds'], time=time.time())) + '\n')
            visits.flush()
        if x.get('event') == 'cover':
            covers.write(json.dumps(dict(gold=x['gold'], node=x['node'], proc=PROC, depth=x['depth'], draw=x['draw'], time=time.time())) + '\n')
            covers.flush()
        if x.get('event') == 'picks':  # the node ids of one scope pick, in order, with the count of scored nodes and the draw count
            picks.write(json.dumps(dict(proc=PROC, seq=PICKS[0], draw=x['draw'], n=x['n'], picks=x['picks'], time=time.time())) + '\n')
            picks.flush()
            PICKS[0] += 1
        if x.get('event') == 'candidate' and count[0] < MAX_CANDIDATES:
            count[0] += 1
            out.write(json.dumps({k: x.get(k) for k in ('attempts', 'score', 'size', 'program')}) + '\n')
            out.flush()
    try:
        policy = D.make_policy(a.policy, task)
    except Exception as e:  # noqa: BLE001
        print('uniform policy:', repr(e)[:300], flush=True)
        policy = D.UniformPolicy(task)
    record = os.environ.get('ARC_RECORD')
    write = recorder('%s/%s.%d' % (record, os.path.basename(a.task), a.seed)) if record else lambda r: None
    pool = D.Pool(os.path.basename(a.task), task, run, policy, gold, write, event, a)
    pool.keep_rows = False
    count[0], generation = read_bank(bank, pool)
    pool.lineage.append(dict(proc=PROC, draws0=pool.draws, nodes0=len(pool.nodes), nodes1=len(pool.nodes), picks1=0))
    if search:
        search.read_slots(pool, bank)
    limit = a.rss_limit_mib * RENEW_SHARE
    rss = rss_mib()
    print('generation %d: rss %.0f after load, %d forms, %d nodes, %.0f s' % (generation, rss, len(pool.forms), len(pool.nodes), time.monotonic() - t0), flush=True)
    if rss > limit * BANK_SHARE:
        print('the bank alone fills the memory', flush=True)
        os._exit(3)
    last, saved, shown = [time.monotonic()], [time.monotonic()], [time.monotonic(), pool.draws]

    def stats():
        try:
            return 'cache %s, memos %s' % (session.cache_stats(), session.memo_stats())
        except Exception as e:  # noqa: BLE001
            return 'no stats: %r' % e

    def tick():
        now = time.monotonic()
        if now - shown[0] > PROGRESS_SECONDS:
            print('rss %.0f at %.0f s of %.0f, cpu %.0f s, %d samples, %.1f samples/s, %d forms, %d nodes, generation %d, %s' % (
                rss_mib(), now - t0, a.seconds, time.process_time(), pool.draws, (pool.draws - shown[1]) / (now - shown[0]), len(pool.forms), len(pool.nodes), generation, stats()), flush=True)
            shown[:] = now, pool.draws
            print('counts', json.dumps({k: v for k, v in sorted(pool.run.c.items()) if k.startswith(COUNT_PREFIXES)}), flush=True)
            ds = getattr(sys.modules.get('sample2_col'), 'DERIVED_STATS', None)
            if ds:  # STEER_DERIVED: the derived-pick steer's calls, cache misses and CPU seconds
                print('derived', json.dumps(dict(ds)), flush=True)
            mgr = getattr(sampler, 'search_manager', None)
            if mgr is not None:
                print('manager', dict(mgr.counts), 'searches', len(sampler.searches), flush=True)
        if now - last[0] > BEAT_SECONDS:
            last[0] = now
            beat()

    seen = [rss]

    def save():
        if write_bank(bank, pool, count[0], generation) and search:
            try:
                search.after_bank(pool, bank)
            except Exception as e:  # noqa: BLE001
                print('search state not saved:', repr(e)[:300], flush=True)

    def stop():
        now = rss_mib()
        if abs(now - seen[0]) > JUMP_MIB:
            print('rss %.0f from %.0f at %d samples, %d forms, %s' % (now, seen[0], pool.draws, len(pool.forms), stats()), flush=True)
        seen[0] = now
        if len(pool.forms) >= MAX_FORMS:
            return 'forms'
        if now > limit:
            return 'memory'
        if time.monotonic() - saved[0] > SAVE_SECONDS:
            save()
            saved[0] = time.monotonic()
        return None
    pool.tick, pool.stop, pool.save = tick, stop, save
    why = pool.grow(deadline, every=1000)
    print('end: %s, %d draws, %d forms, %d nodes, %d candidates, %.0f MiB, %.0f s' % (why, pool.draws, len(pool.forms), len(pool.nodes), len(pool.candidates), rss_mib(), time.monotonic() - t0), flush=True)
    print({k: v for k, v in sorted(pool.run.c.items()) if k.startswith(('error', 'loo', 'refused', 'out:', 'consistent', 'cpu', 'one', 'node:') + COUNT_PREFIXES)}, flush=True)
    out.close()
    getattr(write, 'close', lambda: None)()
    sys.stdout.flush()
    left = deadline - time.monotonic()
    if why == 'forms':
        os.remove(bank) if os.path.exists(bank) else None
    elif why is None:  # the time ended: the bank file gets what this process made since its last write
        save()
    elif why == 'memory':
        t = time.monotonic()
        save()
        print('bank file %.1f MiB in %.1f s' % (os.path.getsize(bank) / 2 ** 20, time.monotonic() - t) if os.path.exists(bank) else 'no bank file', flush=True)
        if left > MIN_RENEW_SECONDS:
            try:
                renew(left, a.seed)
            except (OSError, ValueError) as e:
                print('no renewal:', repr(e)[:300], flush=True)
                os._exit(3)
    os._exit(0)  # the session's teardown can take long; the supervisor has what it needs


if __name__ == '__main__':
    main()
