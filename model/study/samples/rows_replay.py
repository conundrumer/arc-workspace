#!/usr/bin/env python3
"""The row store of `row_store.py` for each task of a records file, on the engine and sampler code of a writer kit release (its
`model/study/sampler` and its site folder): one process a task, each task's file `OUT/SET/rows/<task>.jsonl.gz` written when that task ends.

  <runtime python> rows_replay.py SET [JOBS] [--tasks id,id] [--shard k/N] [--out DIR] [--release DIR] [--site DIR] [--records FILE]

The records file is `records-<SET>.jsonl` of `build_merged.py`, one task a line; the last line of a task counts, and a task that the union files
set aside is left out. A restart skips each task whose file is finished: its header has the record's src, the code sha of `row_store.py` and
`hash_version` engine@<site folder name>. Each finished task prints a line with the rate and an ETA.

The process of a task opens one session of the task, with no test output, at the release's decode settings with a
table work cap of TABLE_WORK_CAP, and session bytes SESSION_SHARE of RSS_MIB. It takes the union programs in record order:
- A program with a form whose QueryHash has no function yet is replayed with the release's `superdag.Run.scope`. Its forms' functions that no
  earlier program gave are written. Where the replay stops at a form (a bound stop of the table export included, whose message names the tables
  it left out), the forms before it are written, and an error line gives the union keys of that form and the forms after it.
- Any other program gives alias lines alone, with no replay.
The probe program `row_store.PROBE` then gives the given tables. A process past RSS_MIB exits with RSS_EXIT, and its task gets no file.
"""
import argparse
import concurrent.futures
import glob
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, '..'))  # model/study
import study_zst as Z  # the union files and the records are zstd streams or plain files, whichever is on disk
WORK = '/Users/davidlu/code/arc-workspace/work'
RELEASE = WORK + '/lm/data-study/sampler/sampler-worker/kits/writer-rel-534dec52f53c'
RECORDS = os.environ.get('UNION_REACH_OUT', WORK + '/synth-kaggle/kit-union-read')  # records-<set>.jsonl
UNION = os.environ.get('GOLD_UNION_DIR', WORK + '/lm/data-study/gold/gold-union').rstrip('/') + '/'  # the union files, for the tasks set aside
TASKS = '/Users/davidlu/code/arc-workspace/data/tasks'
OUT = WORK + '/lm/data-study/samples'
RSS_MIB = 3072  # a task's process exits past this
RSS_EXIT = 5
RSS_SECONDS = 0.5  # how often the process reads its memory
TABLE_WORK_CAP = 1 << 28  # the fits' bound; the live sampler's 2^21 loses the tables of programs that the fits finish
SESSION_SHARE = 0.65  # of RSS_MIB, the session's byte bound, as the release's kaggle_worker.py sets it
ERROR_CHARS = 600  # of the message of a program that does not replay
SEED = 1
CHILD_ENV = dict(ARCLOG_IDENT_SOURCE='value', ONE_REPAIR='0', CHOOSE_LIFT='0', SCOPE_REUSE='0', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1',
                 PYTHONDONTWRITEBYTECODE='1')  # SCOPE_REUSE 0: Run.scope steps every form, so each form has its own result
TASK_LINE = re.compile(rb'\{"task": "([^"]+)"')


# ---------------------------------------------------------------------- the process of one task

def watch_memory(rss_mib, limit):
    """Exits the process with RSS_EXIT once its memory passes limit MiB. The engine's table calls release the GIL, so the thread runs during them."""
    def loop():
        while True:
            if rss_mib() > limit:
                print('rows_replay: memory %.0f MiB past %d MiB' % (rss_mib(), limit), flush=True)
                os._exit(RSS_EXIT)
            time.sleep(RSS_SECONDS)
    threading.Thread(target=loop, daemon=True, name='rss').start()


def replay(a):
    """The row store of one task: a.record holds its record, a.out is its file."""
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != HERE]  # the sampler has a row_store module of its own, which table_adapter imports
    sys.path[:0] = [os.path.join(a.release, 'model/study/sampler'), a.site]
    for k, v in CHILD_ENV.items():
        os.environ[k] = v
    os.environ.pop('ROW_STORE_DIR', None)  # the sampler's dev row store stays off
    models = os.path.join(a.release, 'models-current')
    import kaggle_worker as KW  # pyright: ignore[reportMissingImports]
    KW.settings(models)
    watch_memory(KW.rss_mib, a.rss_mib)
    import superdag as D  # pyright: ignore[reportMissingImports]
    sys.path.append(HERE)
    spec = importlib.util.spec_from_file_location('samples_row_store', os.path.join(HERE, 'row_store.py'))
    assert spec is not None and spec.loader is not None
    RS = importlib.util.module_from_spec(spec)
    sys.modules['samples_row_store'] = RS
    spec.loader.exec_module(RS)
    t0 = time.monotonic()
    rec = json.load(open(a.record))
    tid = rec['task']
    task = json.load(open(a.task_file))
    for t in task['test']:
        t.pop('output', None)
    settings = D.arclog.DecodeSettings(relations=D.RELATIONS, **dict(D.SETTINGS, table_work_cap=a.table_work_cap))
    session = D.arclog.Session(D.arclog.Task.from_json(json.dumps(task), D.arclog.World.Open), settings, session_bytes=int(a.rss_mib * a.session_share) << 20)
    sampler = D.live.Sampler(models, steers=())
    run = D.Run(sampler.pri, session, SEED, time.monotonic() + 365 * 86400, task, D.live.Limits())
    run.want_rows = True  # close exports the rows
    sink = RS.RowSink(D, tid, rec, a.task_file, a.out, a.src, a.split)

    def steps_of(forms):
        """([(result by assignment, relation slots, None)] of the forms that replayed, the error or '')."""
        run.collect, run.scoped, err = [], None, ''
        try:
            run.scope(forms)
        except Exception as e:  # noqa: BLE001
            err = '%s: %s' % (type(e).__name__, str(e)[:ERROR_CHARS])
        steps = [(ct, sorted(tables), None) for ct, tables, _ in run.collect]
        run.collect, run.scoped = None, None
        if err and len(steps) == len(forms):  # every form gave its tables, and a step after them failed
            print('after the forms: %s' % err, flush=True)
            err = ''
        return steps, err

    replayed = failed = 0
    for prog in rec['programs']:
        forms = [str(f) for f in prog['sexp'].strip().split('\n') if not f.startswith('(OUT')]
        if not sink.pending(prog, forms):
            sink.aliases_of(prog, forms)
            continue
        replayed += 1
        steps, err = steps_of(forms)
        sink.program_steps(prog, forms, steps)
        if err:
            failed += 1
            print('union program %s does not replay at form %d: %s' % (prog['cases'][0], len(steps), err[:200]), flush=True)
            sink.failed(prog, err, len(steps))
        del steps
    steps, err = steps_of(RS.PROBE)
    if err:
        sink.errors += 1
        sink.put(dict(t='error', given=RS.GIVEN, error='the probe does not replay: ' + err))
    else:
        try:
            sink.given_steps([ct for ct, _, _ in steps])
        except Exception as e:  # noqa: BLE001
            sink.errors += 1
            sink.put(dict(t='error', given=RS.GIVEN, error='%s: %s' % (type(e).__name__, str(e)[:ERROR_CHARS])))
    del steps
    counts = dict(sink.counts, errors=sink.errors, programs=len(rec['programs']), replayed=replayed, failed=failed, seconds=round(time.monotonic() - t0, 1),
                  rss_mib=round(KW.rss_mib()))
    sink.close()
    print('rows_replay: ' + json.dumps(counts), flush=True)
    sys.stdout.flush()
    os._exit(0)  # the session's teardown can take long


# ---------------------------------------------------------------------- the run over a set

def set_aside(want):
    """The tasks of the set that the union files set aside, as build.py's merged_rows gives them, read one line at a time."""
    names = ['union-%s.jsonl' % want]
    if not Z.exists(UNION + names[0]):
        names = sorted((n for n in Z.listdir(UNION) if re.fullmatch(r'union-%s-\d+\.jsonl' % re.escape(want), n)), key=lambda n: int(n.rsplit('-', 1)[1][:-6]))
    aside, kept = set(), set()
    for name in names + ['union-%s-addendum.jsonl' % want]:
        if Z.exists(UNION + name):
            with Z.open_text(UNION + name) as f:
                for line in f:
                    r = json.loads(line)
                    (kept if 'tables' in r else aside).add(r['task'])
                    (aside if 'tables' in r else kept).discard(r['task'])
    man = UNION + 'union-%s.manifest.json' % want
    if os.path.exists(man):
        aside |= set(json.load(open(man)).get('set_aside', {})) - kept
    return aside


def last_lines(store, keep):
    """{task: handle of its last line} in the records file (a study_zst.LineStore), for the tasks that keep(task) admits."""
    at = {}
    for pos, line in store.scan():
        m = TASK_LINE.match(line)
        t = m[1].decode() if m else json.loads(line)['task']
        if keep(t):
            at[t] = pos
    return at


def line_at(store, pos):
    return store.get(pos)


def one(r: dict[str, Any], a: argparse.Namespace, tmp: str, outdir: str) -> dict[str, Any]:
    """Runs the process of task r; gives r with wall, and error or counts."""
    t = r['task']
    rec = os.path.join(tmp, t + '.json')
    with open(rec, 'wb') as f:
        f.write(line_at(a.store, r['pos']))
    log = os.path.join(tmp, t + '.log')
    out = '%s/%s.jsonl.gz' % (outdir, t)
    t0 = time.time()
    with open(log, 'w') as f:
        p = subprocess.run([sys.executable, '-u', os.path.abspath(__file__), '--replay', '--record', rec, '--task-file', '%s/%s.json' % (TASKS, t), '--out', out,
                            '--src', r['src'], '--split', r['split'], '--release', a.release, '--site', a.site, '--rss-mib', str(a.rss_mib),
                            '--table-work-cap', str(a.table_work_cap), '--session-share', str(a.session_share)], stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, **CHILD_ENV))
    for x in glob.glob(glob.escape(out) + '.*'):  # the temp file of a process that did not end
        os.remove(x)
    text = open(log, errors='replace').read()
    os.remove(log)
    os.remove(rec)
    got = dict(r, wall=round(time.time() - t0, 1))
    done = [line for line in text.splitlines() if line.startswith('rows_replay: {')]
    if p.returncode or not done or not os.path.exists(out):
        why = 'memory past %d MiB' % a.rss_mib if p.returncode == RSS_EXIT else 'exit %d' % p.returncode
        return dict(got, error='%s: %s' % (why, text[-600:]))
    return dict(got, counts=json.loads(done[-1][len('rows_replay: '):]))


def run_set(a):
    sys.path.insert(0, a.site)  # row_store's query_hash imports arclog
    import row_store as RS
    from split import split_of
    want, jobs = a.set, a.jobs
    outdir = '%s/%s/rows' % (a.out, want)
    os.makedirs(outdir, exist_ok=True)
    k, n = map(int, a.shard.split('/'))
    only = set(filter(None, a.tasks.split(',')))
    a.records = a.records or '%s/records-%s.jsonl' % (RECORDS, want)
    a.store = Z.LineStore(a.records)
    at = last_lines(a.store, lambda t: zlib.crc32(t.encode()) % n == k and (not only or t in only))
    aside = set_aside(want)
    code, version = RS.code_sha(), 'engine@' + os.path.basename(a.site.rstrip('/'))
    recs = []
    for t, pos in at.items():
        if t in aside:
            continue
        r = json.loads(line_at(a.store, pos))
        src = r.get('src') or hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]  # the record's own hash, where the union file gave it none
        recs.append(dict(task=t, pos=pos, src=str(src), split=split_of(t), size=sum(len(p['form_keys']) for p in r['programs']), programs=len(r['programs'])))
        del r
    total = len(recs)

    def finished(r):
        h = RS.header_of('%s/%s.jsonl.gz' % (outdir, r['task'])) or {}
        return h.get('src') == r['src'] and h.get('code') == code and h.get('hash_version') == version  # a new wheel makes the file stale

    recs = [r for r in recs if not finished(r)]
    recs.sort(key=lambda r: -r['size'])  # the longest first, so they overlap the rest
    print('%s shard %d/%d: %d tasks, %d set aside, %d finished, %d to run, %s, code %s, out %s' % (
        want, k, n, total + len(aside & set(at)), len(aside & set(at)), total - len(recs), len(recs), version, code, outdir), flush=True)
    size = {r['task']: r['size'] for r in recs}  # definitions to replay; the tasks run longest first, so the count of tasks says little
    left, wall, failed, t0 = sum(size.values()), 0.0, 0, time.time()
    with tempfile.TemporaryDirectory(dir=os.path.dirname(outdir), prefix='.rows-replay-') as tmp, concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for i, fut in enumerate(concurrent.futures.as_completed([pool.submit(one, r, a, tmp, outdir) for r in recs])):
            m = fut.result()
            el = time.time() - t0
            left, wall = left - size[m['task']], wall + m['wall']
            done = sum(size.values()) - left  # ETA: the process time per definition so far, over the definitions left, on `jobs` processes (tasks in flight count as left)
            rate = '%.2f tasks/min, %.1f ms a definition, ETA %.0f s' % (60 * (i + 1) / el, 1000 * wall / max(done, 1), wall / max(done, 1) * left / jobs)
            if 'error' in m:
                failed += 1
                print('%s %s %d/%d FAILED after %.1f s, %s: %s' % (want, m['task'], i + 1, len(recs), m['wall'], rate, m['error']), flush=True)
                continue
            c = m['counts']
            print('%s %s %d/%d: %d definitions, %d of %d programs replayed, %d failed, %d functions, %d entries, %d errors, wall %.1f s, rss %d MiB, %s%s' % (
                want, m['task'], i + 1, len(recs), size[m['task']], c['replayed'], c['programs'], c['failed'], c['functions'], c['entries'], c['errors'], m['wall'],
                c['rss_mib'], rate, '' if finished(m) else ', NOT FINISHED'), flush=True)
    print('%s shard %d/%d done: %d tasks in %.0f s, %d failed' % (want, k, n, len(recs), time.time() - t0, failed), flush=True)
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n\n')[0])
    ap.add_argument('set', nargs='?')
    ap.add_argument('jobs', nargs='?', type=int, default=4)
    ap.add_argument('--tasks', default='', help='id,id: these tasks alone')
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks whose crc32 is k mod N')
    ap.add_argument('--out', default=OUT, help='the files go to OUT/SET/rows/')
    ap.add_argument('--release', default=RELEASE)
    ap.add_argument('--site', default='', help='default: the site folder that the release manifest names')
    ap.add_argument('--records', default='', help='default: records-SET.jsonl under UNION_REACH_OUT')
    ap.add_argument('--rss-mib', type=int, default=RSS_MIB)
    ap.add_argument('--table-work-cap', type=int, default=TABLE_WORK_CAP)
    ap.add_argument('--session-share', type=float, default=SESSION_SHARE)
    ap.add_argument('--replay', action='store_true', help=argparse.SUPPRESS)  # the process of one task
    for x in ('--record', '--task-file', '--src', '--split'):
        ap.add_argument(x, help=argparse.SUPPRESS)
    a = ap.parse_args()
    a.site = a.site or os.path.join(a.release, json.load(open(os.path.join(a.release, 'manifest.json')))['site'])
    if a.replay:
        replay(a)
    if not a.set:
        ap.error('SET is required')
    sys.exit(run_set(a))


if __name__ == '__main__':
    main()
