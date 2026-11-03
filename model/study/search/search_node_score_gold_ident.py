"""Writes which gold forms of the kit's tasks have only Ident tables.

  KIT=<kit folder> EXTRA_PATH=<arclog path> ARCLOG_IDENT_SOURCE=value RAYON_NUM_THREADS=1 <engine python> search_node_score_gold_ident.py SECONDS [OUT]

For each task of the kit's manifest task_set, the script replays the forms of the task's gold (the gold_sexp in KIT/points-eval.json, without the (OUT lines) in
one session with collect on, as superdag.gold_keys does. Gold form g is the g-th non-empty line that does not start with (OUT.
Form g is Ident-only where its tables, those of relation_tables(run.collect[g]), number at least one and each has a column of type Ident. The column types are read from the
table header, so a table whose entries are incomplete still counts.
OUT (default gold-ident-only-kit50.json) is {task: {forms: N, ident_only: [g], no_table: [g], unparsed: [g], error: text or null}}. A form
whose table header cannot be read is in unparsed, and in neither of the other two lists. A task that OUT already holds is skipped, and the file is written after
each task. The script stops before a task when SECONDS have passed; run it again to go on. It prints per task set the counts of forms, Ident-only forms and forms with no table.
"""
import json
import os
import sys
import time

KIT = os.environ['KIT']
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler'] + [p for p in os.environ.get('EXTRA_PATH', '').split(':') if p]
import superdag as D  # noqa: E402
from live import arclog  # noqa: E402
import live  # noqa: E402

TASK_SECONDS = 60
SESSION_BYTES = 1 << 30
FOLD_TASKS = 13  # the last tasks of the manifest's task_set are the fold tasks


def gold_forms(sexp):
    return [str(f) for f in sexp.strip().split('\n') if f.strip() and not f.startswith('(OUT')]


def one_task(sampler, task_id, sexp):
    task = json.load(open('%s/data/tasks/%s.json' % (KIT, task_id)))
    for t in task['test']:
        t.pop('output', None)
    forms = gold_forms(sexp)
    got = dict(forms=len(forms), ident_only=[], no_table=[], unparsed=[], error=None)
    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS), session_bytes=SESSION_BYTES)
    run = D.Run(sampler.pri, session, 0, time.monotonic() + TASK_SECONDS, task, live.Limits())
    run.collect = []
    try:
        run.scope(forms)
    except Exception as e:  # noqa: BLE001
        got['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
        return got
    for g, ct in enumerate(run.collect):
        types = []
        try:
            for _, j in D.relation_tables(ct):
                types.append([str(t) for t in D.OneTable(ct, j).tables['column_types'][0]])
        except Exception:  # noqa: BLE001
            got['unparsed'].append(g)
            continue
        if not types:
            got['no_table'].append(g)
        elif all('Ident' in t for t in types):
            got['ident_only'].append(g)
    if len(run.collect) != len(forms):
        got['error'] = 'replayed %d of %d forms' % (len(run.collect), len(forms))
    return got


def main():
    seconds = float(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else 'gold-ident-only-kit50.json'
    t0 = time.monotonic()
    manifest = json.load(open(KIT + '/manifest.json'))
    tasks = manifest['task_set']
    gold = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
    done = json.load(open(out)) if os.path.exists(out) else {}
    sampler = None
    for k, t in enumerate(tasks):
        if t in done:
            continue
        if time.monotonic() - t0 > seconds:
            print('stopped at the limit; run again to go on')
            break
        sampler = sampler or live.Sampler(KIT + '/models-final')
        done[t] = one_task(sampler, t, gold[t])
        with open(out + '.tmp', 'w') as f:
            json.dump(done, f)
        os.replace(out + '.tmp', out)
        d = done[t]
        print('%s: %d forms, %d Ident-only, %d no table, %d unparsed%s' % (t, d['forms'], len(d['ident_only']), len(d['no_table']), len(d['unparsed']), ', ' + d['error'] if d['error'] else ''), flush=True)
    for name, part in (('37 tasks', tasks[:-FOLD_TASKS]), ('13 tasks', tasks[-FOLD_TASKS:])):
        have = [done[t] for t in part if t in done]
        print('%s: %d of %d tasks, forms %d, Ident-only %d, no table %d' % (name, len(have), len(part), sum(d['forms'] for d in have),
                                                                         sum(len(d['ident_only']) for d in have), sum(len(d['no_table']) for d in have)))
    print('tasks in file: %d' % len(done))


if __name__ == '__main__':
    main()
