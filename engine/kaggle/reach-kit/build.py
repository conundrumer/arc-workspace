#!/usr/bin/env python3
"""Builds a reach measurement kit with union gold: a copy of the kit of the current bundle, whose worker also keys every case's tables and writes a .cover-union line per covered union table.

  python3 build.py SETS...      SETS: ramp, 37, training

The kit is kit-union-read-79af0a4f2/ next to this script. gold-union.json holds, per task, each distinct program of the union (the pinned program and every non-excluded case), the union key of each of its forms, and the union tables. The union keys and their order are those of gold/gold-union/union-identity-<set>.jsonl, which the build checks task by task.
"""
import hashlib, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('UNION_REACH_OUT', '/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read')  # the kit, its records and its maps; the scripts live in the repo
SRC = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-colfix-value-79af0a4f2'
KIT = OUT + '/kit-union-read-79af0a4f2'
UNION = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union').rstrip('/') + '/'  # the union files' folder
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/gold/reads/union')
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../../model/study'))  # study_zst.py
import study_zst as Z  # noqa: E402  the union files and the records are zstd streams or plain files, whichever is on disk
import gold_case_counts as K  # noqa: E402
import gold_union_identity as I  # noqa: E402

WORKER_GOLD = """        gold = D.gold_keys(run, specs[tid]) if tid in specs else {}
"""
WORKER_UNION = """        gold = D.gold_keys(run, specs[tid]) if tid in specs else {}
    if os.environ.get('ARC_GOLD_UNION'):  # a reach measurement kit's union gold: every case's tables, each named by its union key; ARC_GOLD stays the pinned index
        tid = os.path.basename(a.task).split('.')[0]
        rec = next((x for x in json.load(open(os.environ['ARC_GOLD_UNION'])) if x['task'] == tid), None)
        if rec is not None:
            t_u = time.monotonic()

            def union_keys(progs):
                \"\"\"({merge key: {(union key, output, engine index)}}, programs that fail) over the programs, replayed in this session. output is
                the place of the table among the form's relation tables; engine index is the part after the dot of the replay's pg.names['&r<slot>'],
                '' for a form that names its relation by itself.\"\"\"
                got, bad = {}, 0
                union_keys.left = {}  # (union key, output) -> why the replay gives no merge key: 'not finished', or 'not collected'
                for prog in progs:
                    forms = [str(f) for f in prog['sexp'].strip().split('\\n') if not f.startswith('(OUT')]
                    run.collect, names, err = [], {}, ''
                    if sink is not None:
                        row_store.ACTIVE[0] = sink.pending(prog, forms)
                    try:
                        names = run.scope(forms)[1].names
                    except Exception as e:  # noqa: BLE001
                        bad, err = bad + 1, '%s: %s' % (type(e).__name__, str(e)[:120])
                        print('union program %s does not replay: %s' % (prog['cases'][0], str(e)[:160]), flush=True)
                    for i in range(len(run.collect or []), len(prog['form_keys'])):
                        if prog['form_keys'][i] is not None:
                            union_keys.left.setdefault((prog['form_keys'][i], None), 'not collected: the program does not replay: ' + err if err else 'not collected')
                    for i, ct in enumerate(run.collect or []):
                        for o, (s, j) in enumerate(D.relation_tables(ct)):
                            try:
                                k = D.table_key(D.S.parse_table(D.OneTable(ct, j)))[0]
                            except D.M.Fail as e:
                                run.c['gold:union table not finished'] += 1
                                if prog['form_keys'][i] is not None:
                                    union_keys.left.setdefault((prog['form_keys'][i], o), 'not finished: %s' % str(e)[:120])
                                continue
                            if prog['form_keys'][i] is not None:
                                got.setdefault(k, set()).add((prog['form_keys'][i], o, names.get('&r%d' % s, '&r%d' % s).partition('.')[2]))
                    if sink is not None:
                        row_store.ACTIVE[0] = False
                        if not err:
                            sink.program(prog, forms, list(run.collect or []), names)
                        else:
                            sink.failed(prog, err)
                        row_store.prune()
                    run.collect, run.scoped = None, None
                return got, bad

            sink = None
            if os.environ.get('ARC_UNION_ROWS_OUT'):  # the row store: each table at each assignment, with its TableHash and Set of Rows (model/study/samples/row_store.py)
                sys.path.insert(0, os.environ['ARC_SAMPLES_PATH'])
                import row_store
                row_store.install(D.arclog)
                sink = row_store.RowSink(D, tid, rec, a.task, os.environ['ARC_UNION_ROWS_OUT'], os.environ.get('ARC_UNION_ROWS_SRC'))
            pinned = [p for p in rec['programs'] if 'pinned' in p['cases']]
            if os.environ.get('ARC_UNION_MAP_OUT'):  # map mode, at kit build: replay every program, write the map and the pinned program's keys, and stop
                umap, failed = union_keys(rec['programs'])
                got = {u[:2] for v in umap.values() for u in v}
                keys = {k for k, _ in got}
                left = [[k, o, why] for (k, o), why in sorted(union_keys.left.items(), key=str) if (k, o) not in got and (o is not None or k not in keys)]
                check, _ = union_keys(pinned)
                if sink is not None:
                    sink.given(run)
                    sink.close()
                with open(os.environ['ARC_UNION_MAP_OUT'], 'w') as f:
                    json.dump(dict(task=tid, map=[[list(k[0]), k[1], [list(u) for u in sorted(v)]] for k, v in umap.items()], check=[[list(k[0]), k[1]] for k in check],
                                   left=left, failed=failed, seconds=round(time.monotonic() - t_u, 1)), f)
                print('union map: %d merge keys, %d failed, %.1f s' % (len(umap), failed, time.monotonic() - t_u), flush=True)
                sys.exit(0)
            if 'map' in rec:  # the shipped map; the pinned program alone is replayed, to check that its keys are those of the map
                umap = {(tuple(t), b): {tuple(x) for x in u} for t, b, u in rec['map']}
                failed = 0
                check, _ = union_keys(pinned)
                want = {(tuple(t), b) for t, b in rec['check']}
                miss = sorted(set(check) ^ want)
                print('union map check: %d of %d pinned keys equal the shipped map, %d differ' % (len(set(check) & want), len(want), len(miss)), flush=True)
                if miss:
                    print('union map mismatch: %s' % json.dumps([[list(k[0]), k[1]] for k in miss[:5]]), flush=True)
            else:
                umap, failed = union_keys(rec['programs'])
            gold = {k: dict(p=gold.get(k), u=sorted(umap.get(k, ()))) for k in set(gold) | set(umap)}
            print('union gold: %d union tables, %d programs, %d failed, %d merge keys, %d keyed outputs, %.1f s' % (
                len(rec['tables']), len(rec['programs']), failed, len(gold), len({u for v in umap.values() for u in v}), time.monotonic() - t_u), flush=True)
"""
WORKER_OPEN = """    covers2 = open(a.out + '.cover2', 'a')
"""
WORKER_OPEN_U = """    covers2 = open(a.out + '.cover2', 'a')
    covers_u = open(a.out + '.reach', 'a') if os.environ.get('ARC_GOLD_UNION') else None
"""
WORKER_COVER = """        if x.get('event') == 'cover':
            covers.write(json.dumps(dict(gold=x['gold'], node=x['node'], proc=PROC, depth=x['depth'], draw=x['draw'], time=time.time())) + '\\n')
            covers.flush()
"""
WORKER_COVER_U = """        if x.get('event') == 'cover' and isinstance(x['gold'], dict):  # union gold: the ARC_GOLD index to .cover as before, the reached union tables to .reach
            if x['gold']['p'] is not None:
                covers.write(json.dumps(dict(gold=x['gold']['p'], node=x['node'], proc=PROC, depth=x['depth'], draw=x['draw'], time=time.time())) + '\\n')
                covers.flush()
            if x['gold']['u']:  # reached: the pool node's table equals these union tables
                covers_u.write(json.dumps(dict(tables=x['gold']['u'], node=x['node'], proc=PROC, depth=x['depth'], draw=x['draw'], time=time.time())) + '\\n')
                covers_u.flush()
        elif x.get('event') == 'cover':
            covers.write(json.dumps(dict(gold=x['gold'], node=x['node'], proc=PROC, depth=x['depth'], draw=x['draw'], time=time.time())) + '\\n')
            covers.flush()
"""
RUN_ENV = 'env ARC_GOLD=$KIT/points-eval.json '
RUN_ENV_U = 'env ARC_GOLD=$KIT/points-eval.json ARC_GOLD_UNION=$KIT/gold-union.json '


def union_record(t, want):
    """The kit's union record of task t, checked against union-identity-<want>.jsonl."""
    progs = [('pinned', K.pinned(t))]
    pubs, ex = PUBS
    if t in pubs:
        for c in pubs[t][1]['cases']:
            if c['case'].replace('$', '').replace(' ', '+') not in ex[t]:
                progs.append((c['case'], c.get('filtered_program') or c.get('original_program') or ''))
    order, tables, distinct = [], {}, {}
    for name, text in progs:
        forms = I.program(text)
        for key, kind, line, reads, d in forms:
            if key not in tables:
                tables[key] = dict(kind=kind, form=line, reads=reads, depth=d, cases=[])
                order.append(key)
            if name not in tables[key]['cases']:
                tables[key]['cases'].append(name)
        sig = tuple(k for k, *_ in forms)
        if sig and sig not in distinct:
            distinct[sig] = dict(cases=[name], sexp=text)
        elif sig:
            distinct[sig]['cases'].append(name)
    index = {k: i for i, k in enumerate(order)}
    programs = [dict(cases=v['cases'], sexp=v['sexp'], form_keys=[index[k] for k in sig]) for sig, v in distinct.items()]
    rows = [dict(key=index[k], kind=tables[k]['kind'], depth=tables[k]['depth'], reads=[index[r] for r in tables[k]['reads']],
                 pinned='pinned' in tables[k]['cases'], cases=[c for c in tables[k]['cases'] if c != 'pinned'], form=tables[k]['form']) for k in order]
    return dict(task=t, set=want, programs=programs, tables=rows)


def merged_rows(want):
    """({task: merged union record}, [file names], {task: why it is set aside}) of the set, from union-<set>.jsonl and then
    union-<set>-addendum.jsonl, a later line of a task in place of an earlier one; while union-<set>.jsonl is missing, from the part files
    union-<set>-<n>.jsonl that the union run writes. A line with no tables (an error, or set_aside) sets its task aside, as does
    the set_aside of union-<set>.manifest.json. Each record gets src, a hash of its line, so that a changed line is built again."""
    rows, files, aside = {}, [], {}
    names = ['union-%s.jsonl' % want]
    if not Z.exists(UNION + names[0]):
        names = sorted((n for n in Z.listdir(UNION) if re.fullmatch(r'union-%s-\d+\.jsonl' % re.escape(want), n)), key=lambda n: int(n.rsplit('-', 1)[1][:-6]))
    for name in names + ['union-%s-addendum.jsonl' % want]:
        if Z.exists(UNION + name):
            files.append(name)
            for line in Z.open_text(UNION + name):
                r = json.loads(line)
                r['src'] = hashlib.sha256(line.strip().encode()).hexdigest()[:16]
                rows.pop(r['task'], None), aside.pop(r['task'], None)
                if 'tables' in r:
                    rows[r['task']] = r
                else:
                    aside[r['task']] = r.get('error') or r.get('set_aside') or 'no tables'
    man = UNION + 'union-%s.manifest.json' % want  # the manifest's set_aside: tasks that have no line in the union files
    if os.path.exists(man):
        files.append(os.path.basename(man))
        for t, why in json.load(open(man)).get('set_aside', {}).items():
            if t not in rows:
                aside.setdefault(t, why)
    return rows, files, aside


def task_order(want):
    """The set's tasks, in the order of union-identity-<set>.jsonl; while that file is missing, the tasks of the union lines so far, in their order."""
    if not Z.exists(UNION + 'union-identity-%s.jsonl' % want):
        return list(merged_rows(want)[0])
    return [json.loads(l)['task'] for l in Z.open_text(UNION + 'union-identity-%s.jsonl' % want)]


def records(want):
    """The last record of each task in records-<set>.jsonl that is not set aside, in task_order."""
    last = {r['task']: r for r in map(json.loads, Z.open_text(OUT + '/records-%s.jsonl' % want))}
    aside = merged_rows(want)[2]
    return [last[t] for t in task_order(want) if t in last and t not in aside]


LIVE_DEADLINE = "SETTINGS = dict(deadline_seconds=10.0,"
LIVE_DEADLINE_ENV = "SETTINGS = dict(deadline_seconds=float(os.environ.get('ARC_DEADLINE_SECONDS', 10.0)),"  # build_map's row store run sets a larger one


def patch(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:60])
    open(path, 'w').write(s.replace(old, new))


def main():
    sets = sys.argv[1:]
    global PUBS
    PUBS = K.publications(), K.excluded()
    if not os.path.exists(KIT):
        shutil.copytree(SRC, KIT, ignore=shutil.ignore_patterns('out', 'store', '__pycache__'), symlinks=True)
        os.makedirs(KIT + '/out')
    for f in ('model/study/sampler/kaggle_worker.py', 'model/study/sampler/live_try.py', 'run3600.sh', 'run14.sh'):  # the patched files, from the source kit each build
        shutil.copy2(SRC + '/' + f, KIT + '/' + f)
    patch(KIT + '/model/study/sampler/kaggle_worker.py', WORKER_GOLD, WORKER_UNION)
    patch(KIT + '/model/study/sampler/kaggle_worker.py', WORKER_OPEN, WORKER_OPEN_U)
    patch(KIT + '/model/study/sampler/kaggle_worker.py', WORKER_COVER, WORKER_COVER_U)
    for r in ('run3600.sh', 'run14.sh'):
        patch(KIT + '/' + r, RUN_ENV, RUN_ENV_U)
    patch(KIT + '/model/study/sampler/live_try.py', LIVE_DEADLINE, LIVE_DEADLINE_ENV)
    if sets == ['--code']:
        return
    recs, sources = [], {}
    for want in sets:  # records-<set>.jsonl, which build_merged.py writes
        rows = records(want)
        merged, files, aside = merged_rows(want)
        assert [r['task'] for r in rows] == [t for t in task_order(want) if t not in aside], want
        stale = [r['task'] for r in rows if r['merged'] == 'text' and r['task'] in merged]
        assert not stale, ('records older than the merged file; run build_merged.py', want, stale)
        if any(r['merged'] == 'text' for r in rows):
            files.append('union-identity-%s.jsonl' % want)
        maps = {}
        if os.path.exists(OUT + '/maps-%s.jsonl' % want):  # build_map.py's shipped maps
            maps = {m['task']: m for m in map(json.loads, open(OUT + '/maps-%s.jsonl' % want))}
            for r in rows:
                if r['task'] in maps:
                    r['map'], r['check'] = maps[r['task']]['map'], maps[r['task']]['check']
        recs += rows
        sources[want] = dict(tasks=len(rows), set_aside={t: str(v)[:200] for t, v in sorted(aside.items())}, merged_tasks=sum(r['merged'] != 'text' for r in rows), files={n: Z.sha256(UNION + n) for n in files},
                             forms_unkeyed=sum(r.get('forms_unkeyed', 0) for r in rows), mapped=sum('map' in r for r in rows),
                             map_seconds=round(sum(m['seconds'] for m in maps.values()), 1), map_failed_programs=sum(m['failed'] for m in maps.values()))
    with open(KIT + '/gold-union.json.part', 'w') as f:  # renamed into place, so a reader sees the old file or the new one
        json.dump(recs, f)
    os.replace(KIT + '/gold-union.json.part', KIT + '/gold-union.json')
    gsha = hashlib.sha256(open(KIT + '/gold-union.json', 'rb').read()).hexdigest()
    m = json.load(open(KIT + '/manifest.json'))
    m['union_read'] = dict(
        what='A reach measurement kit: the kit of sampler-pool-colfix-value-79af0a4f2 (models-cf is the 8ed4fe634 bundle set) whose worker, with ARC_GOLD_UNION set, takes the shipped map from merge key to union keys (or, for a task with no map, replays every program of the union gold), replays the pinned union program to check its keys against the map (a "union map check" line, and a "union map mismatch" line where they differ), and writes <out>.reach, one line each time a pool node first equals a union table: tables ([union key, output, engine index] of each union table output it equals), node, proc, depth, draw, time. .cover keeps its lines for ARC_GOLD as before. run3600.sh and run14.sh set ARC_GOLD_UNION=$KIT/gold-union.json. Not for the Kaggle bundle.',
        gold_union=dict(file='gold-union.json', sha256=gsha, sources=sources,
                        record='per task: programs (each kept program once, in normal form: cases, sexp, form_keys = union key of each non-OUT form, null where the union gave the form no union key), tables (key, kind, component, depth = least over the cases from 0, depths, reads = the union keys of the tables the form uses, pinned, cases, form). Keys are those of the source file.'),
        pinned='ARC_GOLD is points-eval.json as in the source kit, a different text from the union pinned program (gold-v3-combined-cut/view-final) on some tasks.',
        map='map: [[column types, body hash, [[union key, output, engine index]]]]: output is the place of the table among its form\'s relation tables (the output of search-worker\'s outmap), engine index the part after the dot of the replay\'s pg.names["&r<slot>"] (outmap\'s engine_index), "" for a form that names its relation by itself; and check: the merge keys of the pinned union program, from build_map.py, which runs this worker in map mode (ARC_UNION_MAP_OUT) on the Mac with the bundle settings. A merge key is superdag.table_key: column types and a hash of ints, so it is the same in each process.',
        cost='With a map the worker replays the pinned union program only; without one it replays every program, inside the task deadline. The worker prints its seconds on its union gold line.')
    with open(KIT + '/manifest.json.part', 'w') as f:
        json.dump(m, f, indent=1)
    os.replace(KIT + '/manifest.json.part', KIT + '/manifest.json')
    print('gold-union.json', gsha, len(recs), 'tasks', sum(len(r['tables']) for r in recs), 'tables', sum(len(r['programs']) for r in recs), 'programs')


if __name__ == '__main__':
    main()
