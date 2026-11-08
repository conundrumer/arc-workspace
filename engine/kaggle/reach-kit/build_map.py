#!/usr/bin/env python3
"""The shipped union maps: for each task of records-<set>.jsonl, runs the kit's worker in map mode (ARC_UNION_MAP_OUT) with the bundle settings, one process a task, and streams its map to maps-<set>.jsonl next to this script. A restart skips tasks it has.

  python3 build_map.py SET [JOBS]

With --rows it writes the row store of model/study/samples/row_store.py instead of the maps: one file per task under OUTD/SET/rows/, each
(table, assignment) with its TableHash and Set of Rows. It leaves maps-<set>.jsonl alone, skips tasks whose file is finished, prints each
task's completion with a rate and an ETA, and runs text-level records too.

  python3 build_map.py SET [JOBS] --rows [--shard k/N] [--tasks id,id] [--site DIR]
"""
import concurrent.futures, fcntl, hashlib, json, os, shutil, subprocess, sys, tempfile, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('UNION_REACH_OUT', '/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read')  # the kit, its records and its maps; the scripts live in the repo
KIT = OUT + '/kit-union-read-79af0a4f2'
PY = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
SITE = '/Users/davidlu/code/arc-workspace/work/synth-kaggle/macsite13'
SAMPLES = '/Users/davidlu/code/arc-workspace/model/study/samples'
OUTD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples'
SITE_ROWS = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp11'  # arclog with the export by assignment, and arclog_features
ROWS_RSS_MIB = 3072  # the row store run's worker stops past 3 GiB
ROWS_DEADLINE_SECONDS = 600  # the row store run's replay deadline per request: the run is offline, and the search's 10 s loses slow programs' tables
ENV = dict(P_DAG='1', ORDER_FREE='col,tie,key', ARCLOG_IDENT_SOURCE='value', ARC_SESSION_SHARE='.9', SEARCH_LIMIT_SHARE='.65', ONE_REPAIR='30', CHOOSE_LIFT='0',
           POOL_CLAUSES='search', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')  # the job lines of the source kit


def one(rec, tmp, rows_out=None):
    t = rec['task']
    d = os.path.join(tmp, t)
    os.makedirs(d, exist_ok=True)
    task = d + '/%s.search.task.json' % t
    src = KIT + '/data/tasks/%s.json' % t
    json.dump(json.load(open(src if os.path.exists(src) else '/Users/davidlu/code/arc-workspace/data/tasks/%s.json' % t)), open(task, 'w'))  # the kit holds the eval tasks only
    json.dump([rec], open(d + '/gold.json', 'w'))
    out = d + '/map.json'
    open(d + '/beat', 'w').close()
    env = dict(os.environ, **ENV, PYTHONPATH=KIT + '/model/study/sampler:' + SITE, ARC_MODELS=KIT + '/models-cf', ARC_POLICY=KIT + '/policy',
               POLICY_MODEL=KIT + '/policy/policy_model.pkl', ARC_STORE=d + '/store', ARC_GOLD_UNION=d + '/gold.json', ARC_UNION_MAP_OUT=out)
    if rows_out:
        env.update(ARC_DEADLINE_SECONDS=str(ROWS_DEADLINE_SECONDS), ARC_SAMPLES_PATH=SAMPLES, ARC_UNION_ROWS_OUT=rows_out, ARC_UNION_ROWS_SRC=str(rec.get('src')), ARC_UNION_ROWS_SPLIT=rec['split'], PYTHONPATH=env['PYTHONPATH'] + ':' + SAMPLES)
    t0 = time.time()
    p = subprocess.run([PY, '-u', KIT + '/model/study/sampler/kaggle_worker.py', '--task', task, '--out', d + '/out.jsonl', '--beat', d + '/beat',
                        '--seconds', '86400', '--seed', '1', '--rss-limit-mib', str(ROWS_RSS_MIB if rows_out else 8000)], env=env, capture_output=True, text=True)
    if p.returncode or not os.path.exists(out) or (rows_out and not os.path.exists(rows_out)):
        return dict(task=t, error='exit %d: %s' % (p.returncode, (p.stdout + p.stderr)[-400:]), wall=round(time.time() - t0, 1))
    m = json.load(open(out))
    m['wall'], m['src'] = round(time.time() - t0, 1), rec.get('src')
    return m


def rows_main(want, jobs, shard, only):
    """The row store run: one worker process a task, each task's file written whole when it ends."""
    import build as B
    sys.path.insert(0, SAMPLES)
    import row_store as RS
    from split import split_of
    outdir = '%s/%s/rows' % (OUTD, want)
    os.makedirs(outdir, exist_ok=True)
    k, n = shard
    recs = [r for r in B.records(want) if zlib.crc32(r['task'].encode()) % n == k and (not only or r['task'] in only)]
    total = len(recs)
    for r in recs:  # the record's own hash, where the union file gave it none
        r['src'] = r.get('src') or hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]
    for r in recs:  # every task is processed, held ones included; the split goes in the file's header
        r['split'] = split_of(r['task'])
    code = RS.code_sha()

    def finished(r):
        h = RS.header_of('%s/%s.jsonl.gz' % (outdir, r['task'])) or {}
        return h.get('src') == r['src'] and h.get('code') == code and h.get('hash_version') == 'engine@' + os.path.basename(SITE.rstrip('/')) and h.get('table_hash_version') == RS.DH.arclog.table_hash_version()  # a new wheel or a new TableHash version makes the file stale

    recs = [r for r in recs if not finished(r)]
    recs.sort(key=lambda r: -sum(len(p['form_keys']) for p in r['programs']))  # the longest first, so they overlap the rest
    print('%s shard %d/%d: %d tasks, %d finished, %d to run' % (want, k, n, total, total - len(recs), len(recs)), flush=True)
    t0, failed = time.time(), 0
    size = {r['task']: sum(len(p['form_keys']) for p in r['programs']) for r in recs}  # definitions to replay; the tasks run longest first, so the count of tasks says little
    left, wall = sum(size.values()), 0.0
    with tempfile.TemporaryDirectory(dir=OUT) as tmp, concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for i, fut in enumerate(concurrent.futures.as_completed([pool.submit(one, r, tmp, '%s/%s.jsonl.gz' % (outdir, r['task'])) for r in recs])):
            m = fut.result()
            el = time.time() - t0
            if 'error' in m:
                failed += 1
                print('%s %s FAILED %s' % (want, m['task'], m['error']), flush=True)
                continue
            f = RS.header_of('%s/%s.jsonl.gz' % (outdir, m['task'])) or {}
            left, wall = left - size[m['task']], wall + m['wall']
            done = sum(size.values()) - left  # ETA: the worker time per definition so far, over the definitions left, on `jobs` workers (in flight tasks count as left)
            print('%s %s %d/%d: %d definitions, wall %.1f s, %.2f tasks/min, %.1f ms a definition, ETA %.0f s%s' % (
                want, m['task'], i + 1, len(recs), size[m['task']], m['wall'], 60 * (i + 1) / el, 1000 * wall / done, wall / done * left / jobs, '' if f else ', NO HEADER'), flush=True)
    print('%s shard %d/%d done: %d tasks in %.0f s, %d failed' % (want, k, n, len(recs), time.time() - t0, failed), flush=True)
    sys.exit(1 if failed else 0)


def main():
    argv = []
    for a in sys.argv[1:]:
        if argv and argv[-1] in ('--shard', '--tasks', '--site'):  # `--shard k/N` as well as `--shard=k/N`
            argv[-1] += '=' + a
        else:
            argv.append(a)
    args = [a for a in argv if not a.startswith('--')]
    opts = {a.split('=')[0]: a.split('=')[1] if '=' in a else '' for a in argv if a.startswith('--')}
    want, jobs = args[0], int(args[1]) if len(args) > 1 else 4
    if '--rows' in opts:  # --shard=k/N  --tasks=id,id
        k, n = map(int, opts.get('--shard', '0/1').split('/'))
        global SITE
        SITE = opts.get('--site') or SITE_ROWS
        rows_main(want, jobs, (k, n), set(filter(None, opts.get('--tasks', '').split(','))))
    path = OUT + '/maps-%s.jsonl' % want
    lock = open(path + '.lock', 'w')  # one build of a set at a time; a second waits here, and then builds what the first left
    fcntl.flock(lock, fcntl.LOCK_EX)
    part = path + '.part'  # the build writes here and renames it to path at the end, so a reader sees the old file or the new one
    if not os.path.exists(part):
        shutil.copyfile(path, part) if os.path.exists(path) else open(part, 'w').close()
    done = {m['task']: m.get('src') for m in map(json.loads, open(part))}
    import build as B
    recs = [r for r in B.records(want) if done.get(r['task'], '') != r.get('src') and r['merged'] != 'text']  # a text-level record gets no map; a changed record gets a new one
    recs.sort(key=lambda r: -sum(len(p['form_keys']) for p in r['programs']))  # the longest first, so they overlap the rest
    t0 = time.time()
    with tempfile.TemporaryDirectory(dir=OUT) as tmp, open(part, 'a') as f, concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for i, fut in enumerate(concurrent.futures.as_completed([pool.submit(one, r, tmp) for r in recs])):  # each map is written when it ends
            m = fut.result()
            if 'error' in m:
                print('%s %s FAILED %s' % (want, m['task'], m['error']), flush=True)
                continue
            f.write(json.dumps(m) + '\n')
            f.flush()
            print('%s %s %d/%d: %d merge keys, %d union outputs left out, %d failed programs, replay %.1f s, wall %.1f s, %.0f s in' % (
                want, m['task'], i + 1, len(recs), len(m['map']), len(m.get('left', ())), m['failed'], m['seconds'], m['wall'], time.time() - t0), flush=True)
    last = {m['task']: m for m in map(json.loads, open(part))}
    if all(last.get(r['task'], {}).get('src', '') == r.get('src') for r in recs):  # every task has its map: the last line of each task, renamed into place
        with open(path + '.tmp', 'w') as f:
            for m in last.values():
                f.write(json.dumps(m) + '\n')
        os.replace(path + '.tmp', path)
        os.remove(part)
    else:
        print('%s: some tasks failed; %s keeps the maps so far, and %s is unchanged' % (want, part, path), flush=True)


if __name__ == '__main__':
    main()
