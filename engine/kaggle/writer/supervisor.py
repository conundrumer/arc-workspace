#!/usr/bin/env python3
"""Runs one worker process per task under limits, and keeps submission.json valid from the first moment to the last.

This module imports the standard library alone, so no fault of the engine or of a model can reach it. A worker is expendable: what it
has found is on disk as soon as it finds it, and a worker that dies loses only its program bank. A task's remaining time goes to a new
worker with a new seed. A task whose workers die fast MAX_FAST_DEATHS times gets no more workers.

A worker gets: --task FILE --out FILE --beat FILE --seconds S --seed N --rss-limit-mib M. It writes one JSON object per line to --out,
each with attempts (per test input, a list of grids) and optionally score and size. It may write forms that its gate refused to <--out>.fill,
each with attempts and size; these fill attempt slots that the candidates leave open. It touches --beat while it works. It should exit
before --seconds end, and before its RSS reaches --rss-limit-mib. Exit status FULL_EXIT says that its bank has reached its bound: the task keeps it and gets no more workers.

Limits that the supervisor enforces with SIGKILL: a worker's RSS over its limit, a heartbeat older than --stale-seconds, a worker past
its end by GRACE_SECONDS, and the largest worker while memory in use is over the total limit. A worker over its RSS limit first gets SIGUSR1, and may write its stack.

  supervisor.py --challenges FILE --submission FILE --work DIR --seconds S [--workers N] --worker-cmd CMD...
"""
import argparse
import itertools
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

GRACE_SECONDS = 60
MAX_FAST_DEATHS = 5
BANK_DEATHS = 2  # fast deaths of a task after which its bank file is removed, since reading that file may be what ends its workers
FAST_SECONDS = 60
MIN_LIFE_SECONDS = 20
POLL_SECONDS = 2
WRITE_SECONDS = 300
STATUS_SECONDS = 60
MEMORY_SHARE = 0.75  # of the machine's limit, for all workers
STACK_SECONDS = 0.2  # what a worker over its limit gets to write its stack to its log
FILE_LIMIT_BYTES = 1 << 28  # the largest file a worker may write
MAX_LINES_READ = 5000  # candidates read per task
FULL_EXIT = 4  # a worker's exit status where its bank has reached its bound


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def valid_grid(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and isinstance(g[0], list) and 1 <= len(g[0]) <= 30
            and all(isinstance(r, list) and len(r) == len(g[0]) and all(type(c) is int and 0 <= c <= 9 for c in r) for r in g))


def fallback_grid(test):
    g = test.get('input') if isinstance(test, dict) else None
    return g if valid_grid(g) else [[0]]


def task_entry(task, candidates):
    """The submission entry of a task: per test input, the first two distinct valid grids over candidates, best first, then the fallback."""
    entry = []
    for i, test in enumerate(task['test']):
        got = []
        for c in candidates:
            attempts = c.get('attempts')
            for g in (attempts[i] if isinstance(attempts, list) and i < len(attempts) and isinstance(attempts[i], list) else ()):
                if valid_grid(g) and g not in got:
                    got.append(g)
            if len(got) >= 2:
                break
        got += [fallback_grid(test)] * 2
        entry.append(dict(attempt_1=got[0], attempt_2=got[1]))
    return entry


def read_candidates(path):
    """The candidates in path, best first. A line that a dying worker left unfinished is skipped."""
    out = []
    try:
        with open(path, errors='replace') as f:
            for line in f:
                if len(out) >= MAX_LINES_READ:
                    break
                try:
                    c = json.loads(line)
                except ValueError:
                    continue
                if isinstance(c, dict):
                    out.append(c)
    except OSError:
        pass

    def rank(c):
        s, z = c.get('score'), c.get('size')
        return (-s if isinstance(s, (int, float)) else 0, z if isinstance(z, (int, float)) else 1 << 30)
    return sorted(out, key=rank) + read_fills(path + '.fill')


def read_fills(path):
    """One entry per distinct attempts in a fill file, which holds the forms leave-one-out refused: most forms first, then fewest lines, then first found.
    An entry has `votes`, so it can be told from a candidate. A line that a dying worker left unfinished is skipped."""
    groups = {}
    try:
        with open(path, errors='replace') as f:
            for line in itertools.islice(f, MAX_LINES_READ):
                try:
                    c = json.loads(line)
                    size = c['size']
                    got = groups.setdefault(json.dumps(c['attempts']), dict(c, votes=0, first=len(groups)))
                except (ValueError, KeyError, TypeError):
                    continue
                got['votes'] += 1
                got['size'] = min(got['size'], size)
    except OSError:
        pass
    return sorted(groups.values(), key=lambda g: (-g['votes'], g['size'], g['first']))


def passed(candidates):
    """The candidates that passed the gate, without the fills."""
    return [c for c in candidates if 'votes' not in c]


def write_submission(path, challenges, results):
    """Replaces path with the submission of results, {task id: candidates}, in one step. The text is read back before it replaces path."""
    sub = {}
    for tid, task in challenges.items():
        try:
            sub[tid] = task_entry(task, results.get(tid, ()))
        except Exception as e:  # noqa: BLE001
            log('fallback for', tid, repr(e)[:200])
            sub[tid] = task_entry(task, ())
    text = json.dumps(sub)
    check = json.loads(text)
    assert set(check) == set(challenges) and all(len(check[t]) == len(challenges[t]['test']) for t in check)
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.submission')
    with os.fdopen(fd, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def read_int(path):
    try:
        with open(path) as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def memory_limit():
    """The machine's memory limit in bytes: the lowest of the cgroup's and the system's."""
    limits = [read_int('/sys/fs/cgroup/memory.max'), read_int('/sys/fs/cgroup/memory/memory.limit_in_bytes')]
    try:
        limits.append(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'))
    except (ValueError, OSError):
        pass
    return min((x for x in limits if x), default=16 << 30)


def used_mib():
    """The memory the cgroup has in use, less page cache, in MiB; None where it gives no figure."""
    now = read_int('/sys/fs/cgroup/memory.current') or read_int('/sys/fs/cgroup/memory/memory.usage_in_bytes')
    if not now:
        return None
    cache = 0
    for name in ('/sys/fs/cgroup/memory.stat', '/sys/fs/cgroup/memory/memory.stat'):
        try:
            with open(name) as f:
                for line in f:
                    k, v = line.split()
                    if k in ('inactive_file', 'total_inactive_file'):
                        cache = int(v)
        except (OSError, ValueError):
            pass
    return (now - cache) >> 20


def cpu_facts():
    """The CPUs this process may use, by each reading that can differ from the others."""
    facts = dict(count=os.cpu_count())
    try:
        facts['affinity'] = len(os.sched_getaffinity(0))
    except AttributeError:
        pass
    try:
        with open('/sys/fs/cgroup/cpu.max') as f:
            facts['cpu.max'] = f.read().strip()
    except OSError:
        pass
    return facts


def rss_bytes(pid):
    try:
        with open('/proc/%d/statm' % pid) as f:
            return int(f.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    except FileNotFoundError:
        pass
    except (OSError, ValueError, IndexError):
        return 0
    try:
        return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True, timeout=5).stdout.strip() or 0) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


class Job:
    def __init__(self, tid, end):
        self.tid, self.end, self.seed, self.fast_deaths, self.proc, self.started, self.lives = tid, end, 0, 0, None, 0.0, 0


class Supervisor:
    def __init__(self, a, challenges):
        self.a, self.challenges = a, challenges
        self.t0 = time.monotonic()
        self.deadline = self.t0 + a.seconds
        self.queue = list(challenges)
        self.jobs, self.results, self.running = {}, {}, []
        self.total_limit = int(memory_limit() * MEMORY_SHARE)
        self.rss_limit = a.rss_limit_mib << 20 if a.rss_limit_mib else self.total_limit // a.workers
        self.deaths = self.kills = 0
        self.last_write = self.last_status = 0.0
        self.jobs_seen = set()
        os.makedirs(a.work, exist_ok=True)
        log('tasks', len(challenges), 'workers', a.workers, 'seconds', a.seconds, 'total limit MiB', self.total_limit >> 20, 'worker limit MiB', self.rss_limit >> 20)
        log('cpus', cpu_facts())

    def paths(self, tid):
        w = self.a.work + '/' + tid
        return w + '.task.json', w + '.out.jsonl', w + '.beat', w + '.log'

    def limits(self):
        """Runs in a new worker before it execs."""
        import resource
        os.setsid()
        os.nice(5)
        for name, value in (('RLIMIT_CORE', 0), ('RLIMIT_FSIZE', FILE_LIMIT_BYTES), ('RLIMIT_AS', 3 * self.rss_limit)):
            try:
                resource.setrlimit(getattr(resource, name), (value, value))
            except (ValueError, OSError):
                pass
        try:
            with open('/proc/self/oom_score_adj', 'w') as f:
                f.write('1000')
        except OSError:
            pass

    def spawn(self, job):
        now = time.monotonic()
        task_p, out_p, beat_p, log_p = self.paths(job.tid)
        seconds = max(job.end - now, 1)
        if not os.path.exists(task_p):
            with open(task_p, 'w') as f:
                json.dump({'train': self.challenges[job.tid]['train'], 'test': self.challenges[job.tid]['test']}, f)
        with open(beat_p, 'w'):
            pass
        job.seed += 1
        job.lives += 1
        self.jobs_seen.add(job.tid)
        open(out_p, 'a').close()
        if job.fast_deaths >= BANK_DEATHS and os.path.exists(out_p + '.bank'):
            os.remove(out_p + '.bank')
            store = os.environ.get('ARC_STORE')
            shutil.rmtree(os.path.join(store, os.path.basename(task_p)) if store else out_p + '.store', ignore_errors=True)
        cmd = shlex.split(self.a.worker_cmd) + ['--task', task_p, '--out', out_p, '--beat', beat_p, '--seconds', '%.0f' % seconds,
                                                '--seed', str(job.seed), '--rss-limit-mib', str(self.rss_limit >> 20)]
        env = dict(os.environ, RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
        with open(log_p, 'ab') as lf:
            job.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, env=env, preexec_fn=self.limits)
        job.started = now

    def kill(self, job, why):
        self.kills += 1
        log('kill', job.tid, why)
        try:
            os.killpg(job.proc.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            try:
                job.proc.kill()
            except OSError:
                pass

    def stack(self, job):
        """Asks a worker over its RSS limit for its Python stack, which faulthandler writes to the worker's log whether or not the engine holds the GIL. The worker dies either way."""
        try:
            os.kill(job.proc.pid, signal.SIGUSR1)
            time.sleep(STACK_SECONDS)
        except (OSError, AttributeError):
            pass

    def start_next(self):
        while self.queue and len(self.running) < self.a.workers:
            now = time.monotonic()
            left = self.deadline - now
            if left < MIN_LIFE_SECONDS:
                return
            free = left * self.a.workers - sum(max(j.end - now, 0) for j in self.running)
            share = free / len(self.queue)
            job = Job(self.queue.pop(0), now + min(share, left))
            log('task', job.tid, 'allotted %.1f s, free %.1f, queued %d, left %.1f, at %d' % (min(share, left), free, len(self.queue) + 1, left, now - self.t0))
            self.running.append(job)
            self.safe_spawn(job)

    def safe_spawn(self, job):
        try:
            self.spawn(job)
        except Exception as e:  # noqa: BLE001
            log('cannot start', job.tid, repr(e)[:200])
            job.proc = None

    def finish(self, job):
        self.running.remove(job)
        self.results[job.tid] = read_candidates(self.paths(job.tid)[1])
        log('task', job.tid, 'lives', job.lives, 'candidates', len(passed(self.results[job.tid])), 'done', len(self.results), 'of', len(self.challenges), 'at', int(time.monotonic() - self.t0))

    def reap(self):
        now = time.monotonic()
        for job in list(self.running):
            code = 1 if job.proc is None else job.proc.poll()
            if code is None:
                continue
            life = now - job.started
            if code != 0:
                self.deaths += code != FULL_EXIT
                log('worker of', job.tid, 'exited', code, 'after %.0f s' % life)
            job.fast_deaths += code != FULL_EXIT and life < FAST_SECONDS and job.end - now >= MIN_LIFE_SECONDS
            if code == FULL_EXIT or job.end - now < MIN_LIFE_SECONDS or job.fast_deaths >= MAX_FAST_DEATHS:
                self.finish(job)
            else:
                self.safe_spawn(job)

    def watch(self):
        now = time.monotonic()
        sizes = []
        for job in self.running:
            if job.proc is None or job.proc.poll() is not None:
                continue
            rss = rss_bytes(job.proc.pid)
            sizes.append((rss, job))
            if rss > self.rss_limit:
                self.stack(job)
                self.kill(job, 'RSS %d MiB' % (rss >> 20))
            elif now > job.end + GRACE_SECONDS or now > self.deadline:
                self.kill(job, 'past its end')
            else:
                try:
                    stale = time.time() - os.stat(self.paths(job.tid)[2]).st_mtime
                except OSError:
                    stale = 0
                if stale > self.a.stale_seconds:
                    self.kill(job, 'no heartbeat for %.0f s' % stale)
        total = sum(s for s, _ in sizes)
        if total > self.total_limit and sizes:
            self.kill(max(sizes, key=lambda x: x[0])[1], 'total memory')
        if now - self.last_status >= STATUS_SECONDS:
            self.last_status = now
            rss = sorted(s >> 20 for s, _ in sizes)
            with_candidate = sum(1 for t in self.jobs_seen if os.path.getsize(self.paths(t)[1]) > 0) if self.a.status_candidates else 0
            log('status at %d s: running %d, queued %d, done %d, RSS MiB total %d, median %d, max %d, deaths %d, kills %d, load %.0f, disk free GiB %d, used MiB %s, tasks with a candidate %d' % (
                now - self.t0, len(self.running), len(self.queue), len(self.results), total >> 20, rss[len(rss) // 2] if rss else 0, rss[-1] if rss else 0,
                self.deaths, self.kills, os.getloadavg()[0], shutil.disk_usage(self.a.work).free >> 30, used_mib(), with_candidate))

    def write(self):
        for job in self.running:
            self.results[job.tid] = read_candidates(self.paths(job.tid)[1])
        write_submission(self.a.submission, self.challenges, self.results)
        self.last_write = time.monotonic()

    def step(self):
        self.reap()
        self.start_next()
        self.watch()
        if time.monotonic() - self.last_write > WRITE_SECONDS:
            self.write()

    def run(self):
        while (self.queue or self.running) and time.monotonic() < self.deadline + GRACE_SECONDS:
            if not self.running and self.deadline - time.monotonic() < MIN_LIFE_SECONDS:
                break
            try:
                self.step()
            except Exception as e:  # noqa: BLE001
                log('supervisor step failed', repr(e)[:300])
            time.sleep(POLL_SECONDS)

    def stop(self):
        for job in self.running:
            if job.proc is not None and job.proc.poll() is None:
                self.kill(job, 'the run ended')
        self.write()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--challenges', required=True)
    ap.add_argument('--submission', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--seconds', type=float, required=True)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--rss-limit-mib', type=int, default=0)
    ap.add_argument('--stale-seconds', type=float, default=600)
    ap.add_argument('--tasks', type=int, default=0, help='run only the first N tasks; the others get the fallback')
    ap.add_argument('--status-candidates', type=int, default=1)
    ap.add_argument('--worker-cmd', required=True)
    a = ap.parse_args()
    with open(a.challenges) as f:
        challenges = json.load(f)
    write_submission(a.submission, challenges, {})
    log('fallback submission written')
    if not a.workers:
        try:
            a.workers = len(os.sched_getaffinity(0))
        except AttributeError:
            a.workers = os.cpu_count() or 1
    sup = Supervisor(a, challenges)
    if a.tasks:
        sup.queue = sup.queue[:a.tasks]

    def on_term(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, on_term)
    try:
        sup.run()
    finally:
        sup.stop()
        log('submission written; deaths', sup.deaths, 'kills', sup.kills, 'tasks with a candidate', sum(bool(passed(v)) for v in sup.results.values()))
        try:
            print('disk free GiB', shutil.disk_usage(a.work).free >> 30, flush=True)
        except OSError:
            pass


if __name__ == '__main__':
    main()
