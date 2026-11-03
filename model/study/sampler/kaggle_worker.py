#!/usr/bin/env python
"""One worker of engine/kaggle/synth/supervisor.py: grows a program bank on one task, and writes each candidate program as it is found.

Exit status 0: the time ended. Exit status 3: a renewal failed. The supervisor starts a new worker with a new seed in each case while the task has time left.
Exit status FULL_EXIT: the bank reached MAX_FORMS, or the bank alone fills the memory. The bank file stays, and the task gets no more workers.

The bank is the worker's state and a table is a cache of a form, so the bank lives in the bank file and the tables live only in the
process. Where RSS reaches RENEW_SHARE of the limit, the worker writes the bank file and replaces itself with execv, which frees all of
the tables whoever holds them. The new process reads the bank file and computes again the tables that later samples read. A worker that
a crash or a kill ended loses only the forms made since the last write of the bank file, since the worker that follows reads that file.

A merge key compares within one process, so a new process starts with no keys, and a clause an older process saw may enter the bank again.

POOL_CLAUSES gives the source of the pool's clauses: draws from Pool.draw, search from superdag_search.py, or state from state_search.py. A task file named <id>.draws.task.json or
<id>.search.task.json overrides it for that task. A search keeps its state under $ARC_STORE/<task file name>, so that the workers of a task go on from it.
"""
import argparse
import ctypes
import faulthandler
import json
import os
import pickle
import signal
import sys
import time

MAX_FORMS = 30000
FULL_EXIT = 4  # the exit status where the bank has reached its bound
RENEW_SHARE = 0.6  # of --rss-limit-mib, where the worker renews its process
BANK_SHARE = 0.8  # of the RSS that starts a renewal, the most a process may hold after it reads the bank file
SESSION_SHARE = 0.65  # of --rss-limit-mib, for the session's byte bound. The bound sits above the session bytes that a worker holds at the renewal line, so a worker renews before the bound stops its tables. A step that reaches the bound drops a clause, and the worker lives. The result cache takes half, under the DET memos, Python and one form's work
FOLD_SHARE = 0.07  # of --rss-limit-mib, for each leave-one-out session
ROOM_SHARE = 0.9  # of --rss-limit-mib: a table whose Python rows would take RSS past this is refused before it is parsed, and the worker lives
TABLE_MIB_SCALE = 1.77  # the median of the rise over the counts' estimate, on 33 peaks with a table of 64 MiB or more on the ramp soak of kernel-bundle-e8ded5733
TABLE_LINE_MIB = 64  # the estimate from which a table's parse reads RSS and is logged
PARTS_MIB = 64  # a rise of the peak inside a visit after which the worker reads the parts of its memory again
SLOW_TABLE_SECONDS = 0.05  # a step_tables call under this adds less than JUMP_MIB, so it reads no peak
ONE_REPAIR_SECONDS = '30'  # of the ONE repair of one candidate, 0 for none; live.py reads the environment when it is imported
P_DAG_SETTING = '1'  # live.set_steers reads P_DAG from the environment: P's value weights read no label number, the setting that the steers' rows were made under
ORDER_FREE_SETTING = 'col,tie,key'  # sample2_col.py reads ORDER_FREE when it is imported: tie orders options of one chance by their facts (search.py), key picks a key's labels by the types of their sites (live.Run.key_pick)
IDENT_SOURCE_SETTING = 'value'  # sample2_col.py reads ARCLOG_IDENT_SOURCE when it is imported, and the engine at its first use in a process: an Ident column has one source, and a table export gives an Ident the first 32 bits of its member digest
POOL_CLAUSES_SETTING = 'search'  # source() reads it: the pool search (superdag_search.py) writes the pool's queries, with the writer where WRITER is 1; state is the state search (state_search.py), which drafts with Run.form and so reads no WRITER_TREE
WRITER_SETTING = '1'  # search.py reads WRITER when it is imported: the token-level writer (writer.py) writes each query
WRITER_TREE_SETTING = ''  # search.py reads WRITER_TREE when it is imported: the writer's LightGBM model, with its feature names beside it (tree_dist.load); a path relative to --models; empty for the hand-set distribution
SEARCH_STATE_SCORE_SETTING = ''  # state_search.py reads it at install(): a module whose score(view) orders the frontier; a path relative to --models; empty for the default score
PATH_SETTINGS = ('WRITER_TREE', 'SEARCH_STATE_SCORE')  # the settings whose relative paths settings() resolves against --models
MAX_CANDIDATES = 2000
MAX_FILL_BYTES = 8 << 20  # of a task's fill file, over all its processes
BEAT_SECONDS = 20
PROGRESS_SECONDS = 10
JUMP_MIB = 100  # a change of RSS between two scopes that the log reports
SAVE_SECONDS = 120
RECORD_BYTES = 1 << 32  # the most one process writes to its record files, compressed
RECORD_FILE_BYTES = 1 << 27  # the most one record file holds, under the supervisor's limit on a file
RECORD_LEVEL = 3
RECORD_WINDOW_LOG = 24
MIN_RENEW_SECONDS = 30  # a process with less time left than this runs out its time
COUNT_PREFIXES = ('kept:', 'drop:', 'search:', 'choose', 'state:', 'scope:')  # the counters that a progress line and the end line print
POLICY_FIXED = ('names', 'ix', 'model', 'pairs', 'scope')  # attributes of a Policy that its constructor or superdag_search.py makes


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


def table_mib(rows, cells, wide, assigned):
    """An estimate of the peak of the Python copy of a table, from the counts alone: parse_table's rows and extents, its assignments' row sets, and the largest entry's set in table_key or its sort in rows_with_models.
    rows is the rows of each entry, cells the cells of a row, wide the Box, Position and Offset columns, assigned the rows of the DET assignments. The constants of the counts fit synthetic shapes within 15%, and TABLE_MIB_SCALE fits the soak."""
    return TABLE_MIB_SCALE * (sum(rows) * (170 + 11 * cells + 96 * wide) + assigned * 120 + max(rows, default=0) * (200 + 12 * cells)) / 2 ** 20


def glibc_used():
    """The bytes that glibc's malloc has given out and not taken back, or 0: CPython's objects over 512 bytes and numpy's arrays. The engine's allocator is mimalloc, so this holds none of the engine's bytes."""
    names = 'arena', 'ordblks', 'smblks', 'hblks', 'hblkhd', 'usmblks', 'fsmblks', 'uordblks', 'fordblks', 'keepcost'
    for call, field in (('mallinfo2', ctypes.c_size_t), ('mallinfo', ctypes.c_int)):
        try:
            info = type('Info', (ctypes.Structure,), dict(_fields_=[(n, field) for n in names]))
            fn = getattr(ctypes.CDLL(None), call)
            fn.restype = info
            got = fn()
            return got.uordblks + got.hblkhd
        except (OSError, AttributeError):
            pass
    return 0


class Meter:
    """The peak of resident memory inside one visit, the phase that reached it, and the parts of memory at the first mark after it. The kernel keeps the peak, so it holds for engine calls that keep the GIL.
    Where the system gives no peak, Meter says so once and does nothing. No failure of it reaches the worker."""

    def __init__(self, session, pool, status='/proc/self/status', clear='/proc/self/clear_refs'):
        self.session, self.pool = session, pool
        self.on, self.seconds, self.peak = True, 0.0, 0.0
        self.begin = self.top = self.parts_at = 0.0
        self.where, self.parts, self.big = None, None, (0, 0.0)
        try:
            self.status, self.clear = os.open(status, os.O_RDONLY), os.open(clear, os.O_WRONLY)
            self.field(b'VmHWM:')
        except (OSError, ValueError) as e:
            self.quit(e)

    def quit(self, e):
        self.on = False
        print('peak meter off:', repr(e)[:200], flush=True)

    def field(self, key):
        """The field key of the status file, in MiB."""
        text = os.pread(self.status, 4096, 0)
        at = text.index(key) + len(key)
        return int(text[at:text.index(b'kB', at)]) / 1024

    def open(self):
        """Starts the peak over at RSS now, for the next visit."""
        if not self.on:
            return
        t = time.perf_counter()
        try:
            self.peak = max(self.peak, self.field(b'VmHWM:'))
            os.write(self.clear, b'5')
            self.begin = self.top = self.parts_at = self.field(b'VmRSS:')
        except (OSError, ValueError) as e:
            self.quit(e)
        self.where, self.parts, self.big = None, None, (0, 0.0)
        self.seconds += time.perf_counter() - t

    def read_parts(self):
        """(RssAnon MiB, pymalloc blocks in use, glibc MiB in use, runs that searches keep, decoders in their memos, row sets in DROWS, cache_stats, memo_stats)."""
        manager = getattr(getattr(self.pool, 'sampler', None), 'search_manager', None)
        hot = [s for s in manager.scopes.values() if s.run is not None] if manager else []
        S = sys.modules.get('sample2_col')
        return (self.field(b'RssAnon:'), sys.getallocatedblocks(), glibc_used() / 2 ** 20, len(hot), sum(len(s.run.memo) for s in hot), len(getattr(S, 'DROWS', ())),
                self.session.cache_stats(), self.session.memo_stats())

    def mark(self, phase):
        """Ends a phase of the visit. The phase that raised the peak last holds it. The parts are read here after a rise of PARTS_MIB, so rows that the phase still holds count."""
        if not self.on:
            return
        t = time.perf_counter()
        try:
            top = self.field(b'VmHWM:')
            if top > self.top:
                self.top, self.where = top, phase
                if top - self.parts_at >= PARTS_MIB:
                    self.parts_at, self.parts = top, self.read_parts()
        except (OSError, ValueError) as e:
            self.quit(e)
        except Exception as e:  # noqa: BLE001
            print('parts not read:', repr(e)[:200], flush=True)
        self.seconds += time.perf_counter() - t

    def table(self, rows, mib):
        """Keeps the largest table the visit parsed, whether its clause is kept, equal or dropped."""
        if mib > self.big[1]:
            self.big = rows, mib

    def close(self):
        """Ends the visit, and logs it where its peak rose JUMP_MIB over the RSS it began at."""
        if not self.on:
            return
        self.mark('stop')
        if self.on and self.top - self.begin >= JUMP_MIB and self.parts:
            anon, blocks, heap, hot, memo, drows, cache, memos = self.parts
            print('peak %.0f in %s from %.0f, end %.0f, at %d samples, %d forms, anon %.0f, blocks %d, heap %.0f, table %d rows %.0f MiB, hot %d memo %d drows %d, cache %s, memos %s' % (
                self.top, self.where, self.begin, rss_mib(), self.pool.draws, len(self.pool.forms), anon, blocks, heap, *self.big, hot, memo, drows, cache, memos), flush=True)
            self.pool.run.c['memory:peak visits'] += 1


def table_check(a, pool, meter, fail):
    """S.ROW_CHECK of this worker: keeps the largest table of the visit, logs each large table once a process, and refuses a table with no room. fail is M.Fail, which each caller of parse_table takes."""
    logged = set()

    def check(rows, cells, wide, assigned):
        total, mib = sum(rows), table_mib(rows, cells, wide, assigned)
        meter.table(total, mib)
        if mib < TABLE_LINE_MIB:
            return None
        rss, where = rss_mib(), sys._getframe(2).f_code.co_name
        refused = mib > a.rss_limit_mib * ROOM_SHARE - rss
        if refused or (total, cells) not in logged:
            logged.add((total, cells))
            print('table %d rows, %d cells, %.0f MiB, rss %.0f, in %s%s' % (total, cells, mib, rss, where, ', refused' if refused else ''), flush=True)
        if refused:
            pool.run.c['memory:table refused'] += 1
            raise fail('table past the memory room')
        return lambda: meter.mark('parse_' + where)
    return check


def timed_tables(arclog, meter):
    """Has a long step_tables call read the peak when it ends."""
    step_tables = arclog.step_tables

    def timed(*args, **kw):
        t = time.monotonic()
        got = step_tables(*args, **kw)
        if time.monotonic() - t > SLOW_TABLE_SECONDS:
            meter.mark('tables')
        return got
    arclog.step_tables = timed


def write_bank(path, pool, found, generation):
    """Replaces the bank file in one step. Gives False where it could not, and the bank file stays as it was."""
    state = dict(forms=pool.forms, nodes=pool.nodes, draws=pool.draws, found=found, generation=generation,
                 policy={k: v for k, v in vars(pool.policy).items() if k not in POLICY_FIXED})
    state.update(getattr(pool, 'bank_extra', dict)())  # the state search's visited set
    try:
        with open(path + '.tmp', 'wb') as f:
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(path + '.tmp', path)
        return True
    except Exception as e:  # noqa: BLE001
        print('bank not written:', repr(e)[:300], flush=True)
        return False


def read_bank(path, pool):
    """Fills pool from the bank file. Gives (candidates found, generation), which are 0 where no bank file can be read."""
    try:
        with open(path, 'rb') as f:
            state = pickle.load(f)
        pool.forms, pool.nodes, pool.draws = state['forms'], state['nodes'], state['draws']
        pool.rebuild_maps()  # defs, keys and hash_count: a known query stays known after a renewal
        vars(pool.policy).update(state['policy'])
        pool.lineage = state.get('lineage', [])
        getattr(pool, 'bank_restore', lambda s: None)(state)
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
    argv[argv.index('--seed') + 1] = str(seed + 1)
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + argv[1:])


def source(a, sampler):
    """The superdag_search module where this task's clauses come from search, installed, else None. A search that cannot start leaves draws."""
    name = os.path.basename(a.task)
    path = next((p for p in ('search', 'draws') if '.%s.' % p in name), os.environ.get('POOL_CLAUSES', 'draws'))
    print('pool clauses:', path, flush=True)
    if path == 'state':
        import superdag_search
        import state_search
        superdag_search.is_panic = lambda e: False  # a panic ends the worker, as in the pool search
        state_search.install()
        return state_search
    if path != 'search':
        return None
    try:
        import superdag_search as search
        search.is_panic = lambda e: False  # a panic ends the worker, since the session is unusable after one, and the Journal skips its path
        search.attach(sampler, store_of(name, a.out), a.rss_limit_mib)
        search.load_rule()
        search.install('search')
        return search
    except Exception as e:  # noqa: BLE001
        print('pool clauses: draws, search failed:', repr(e)[:300], flush=True)
        return None


def store_of(name, out):
    return os.path.join(os.environ['ARC_STORE'], name) if os.environ.get('ARC_STORE') else out + '.store'


def settings(models):
    """Sets in the environment each setting that the models were made and read under, where the environment has none. live.py, sample2_col.py and search.py read them when
    they are imported, and the engine reads ARCLOG_IDENT_SOURCE once a process, at its first use, so this runs before superdag is imported. A relative path of PATH_SETTINGS
    becomes a path under models, the dataset folder. os.execv at a renewal keeps them."""
    for name, value in (('ONE_REPAIR', ONE_REPAIR_SECONDS), ('P_DAG', P_DAG_SETTING), ('ORDER_FREE', ORDER_FREE_SETTING), ('ARCLOG_IDENT_SOURCE', IDENT_SOURCE_SETTING),
                        ('POOL_CLAUSES', POOL_CLAUSES_SETTING), ('WRITER', WRITER_SETTING), ('WRITER_TREE', WRITER_TREE_SETTING), ('SEARCH_STATE_SCORE', SEARCH_STATE_SCORE_SETTING)):
        os.environ.setdefault(name, value)
    for name in PATH_SETTINGS:
        path = os.environ.get(name)
        if path and not os.path.isabs(path):
            os.environ[name] = os.path.join(models, path)


def main():
    faulthandler.enable()
    faulthandler.register(signal.SIGUSR1, all_threads=True)  # the supervisor asks for the stack of a worker that it is about to kill
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
    settings(a.models)
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
    print('sampler: P_DAG %s, order_free %s, ident %s %s, rel %s, choice %s, tilt %s, tilt thetas %d, unjoined %.3f, p_reexport %.3f, else_neg %.3f, mirror_not %.3f' % (
        live.S.P_DAG, ','.join(sorted(live.S.ORDER_FREE)) or '-', os.environ.get('ARCLOG_IDENT_SOURCE') or '-', live.S.IDENT_SOURCE, os.path.basename(live.S.STEER_REL),
        os.path.basename(live.S.STEER_CHOICE), live.S.TILT_TABLE is not None, sum(len(t['theta']) for t in (live.S.TILT_TABLE or {}).values()),
        live.S.UNJOINED, live.S.P_REEXPORT, live.ELSE_NEG, live.MIRROR_NOT), flush=True)
    beat()
    with open(a.task) as f:
        task = json.load(f)
    for t in task['test']:
        t.pop('output', None)
    decode_settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)

    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), decode_settings, session_bytes=D.SESSION_BYTES)
    run = D.Run(sampler.pri, session, a.seed, deadline, task, live.Limits())
    a.t0, a.out_path = t0, a.out
    out = open(a.out, 'a')
    fill = open(a.out + '.fill', 'a')
    count = [0]

    def event(x):
        if x.get('event') == 'candidate' and count[0] < MAX_CANDIDATES:
            count[0] += 1
            out.write(json.dumps({k: x.get(k) for k in ('attempts', 'score', 'size', 'program')}) + '\n')
            out.flush()
        elif x.get('event') == 'fill' and fill.tell() < MAX_FILL_BYTES:
            fill.write(json.dumps({k: x.get(k) for k in ('attempts', 'size', 'program')}) + '\n')
            fill.flush()
    try:
        policy = D.make_policy(a.policy, task)
    except Exception as e:  # noqa: BLE001
        print('uniform policy:', repr(e)[:300], flush=True)
        policy = D.UniformPolicy(task)
    search = source(a, sampler)
    record = os.environ.get('ARC_RECORD')
    write = recorder('%s/%s.%d' % (record, os.path.basename(a.task), a.seed)) if record else lambda r: None
    pool = D.Pool(os.path.basename(a.task), task, run, policy, {}, write, event, a)
    pool.keep_rows = False
    count[0], generation = read_bank(bank, pool)
    if search:
        search.read_slots(pool, bank)
    meter = Meter(session, pool)
    pool.mark, live.S.TA.ROW_CHECK = meter.mark, table_check(a, pool, meter, live.M.Fail)
    timed_tables(arclog, meter)
    if meter.on:
        D.rss_mib = lambda: max(meter.peak, meter.top)  # the peak of this process alone: a reset of VmHWM also lowers ru_maxrss, and ru_maxrss keeps the peak across execv
    meter.open()
    limit = a.rss_limit_mib * RENEW_SHARE
    rss = rss_mib()
    print('generation %d: rss %.0f after load, %d forms, %d nodes, %.0f s' % (generation, rss, len(pool.forms), len(pool.nodes), time.monotonic() - t0), flush=True)
    if rss > limit * BANK_SHARE:
        print('the bank alone fills the memory', flush=True)
        os._exit(FULL_EXIT)
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
        meter.close()
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
        meter.open()
        return None
    pool.tick, pool.stop, pool.save = tick, stop, save
    why = pool.grow(deadline, every=1000)
    pool.run.c['memory:meter seconds'] = meter.seconds
    print('end: %s, %d draws, %d forms, %d nodes, %d candidates, %.0f MiB, %.0f s' % (why, pool.draws, len(pool.forms), len(pool.nodes), len(pool.candidates), rss_mib(), time.monotonic() - t0), flush=True)
    print({k: v for k, v in sorted(pool.run.c.items()) if k.startswith(('error', 'loo', 'refused', 'out:', 'consistent', 'node:', 'search:manager', 'one', 'two stage', 'prefix score', 'kept:', 'resume', 'seconds:', 'drop:table', 'drop:stop', 'key:', 'memory:'))}, flush=True)
    out.close()
    fill.close()
    getattr(write, 'close', lambda: None)()
    sys.stdout.flush()
    left = deadline - time.monotonic()
    if why == 'forms':
        os._exit(FULL_EXIT)
    if why == 'memory':
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
