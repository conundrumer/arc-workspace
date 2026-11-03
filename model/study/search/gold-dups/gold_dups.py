"""Gold duplicate map: for each task, which gold forms share a table key, by the replay that the pool uses.

  ENV=... <mac python> gold_dups.py [--budget SECONDS] [TASK...]

It runs the worker's set-up (sampler, order-free table_key from superdag_search.install, Run on the task) and then D.gold_keys of the PATCHED superdag.py
(gold-dups.patch applied to a copy of the kit in kit-patched/), which keeps every index per key. A key with 2 or more indices is a duplicate group.
Streams to dups.jsonl, one line per task, and skips the tasks that have a line (resume). It stops starting new tasks once --budget seconds have passed.
At the end it writes dups.json {task: [[i, j, ...], ...]} of all tasks in dups.jsonl.
Reads no atom order, atom index or last-atom fact: a key is the merge key of the table.
"""
import argparse
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/joint/search-joint-r1-kit-0729e4943'
FOLD13 = ['2c0b0aff', '74dd1130', 'aa18de87', 'b9b7f026', 'd23f8c26', '5b37cb25', '8e2edd66', 'b2862040', '4df5b0ae', '94133066', 'c35c1b4c', 'd0f5fe59', 'e69241bd']
RSS_LIMIT_MIB = 2888

for k, v in dict(ARCLOG_IDENT_SOURCE='value', P_DAG='1', ORDER_FREE='tie,key', ARC_SESSION_SHARE='.9', SEARCH_LIMIT_SHARE='.65', ONE_REPAIR='30', CHOOSE_LIFT='0',
                 POOL_CLAUSES='search', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ARC_GOLD=KIT + '/points-eval.json').items():
    os.environ.setdefault(k, v)
os.chdir(KIT)
sys.path.insert(0, HERE + '/kit-patched/model/study/sampler')  # the kit's sampler folder with gold-dups.patch and gold-dups-search.patch applied
import superdag as D  # noqa: E402
import superdag_search as search  # noqa: E402

assert D.__file__.startswith(HERE + '/kit-patched/') and search.__file__.startswith(HERE + '/kit-patched/'), (D.__file__, search.__file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='*')
    ap.add_argument('--budget', type=float, default=10)
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--gold', default=KIT + '/points-eval.json')
    a = ap.parse_args()
    t0 = time.monotonic()
    tasks = a.tasks or json.load(open(KIT + '/refit-tasks.json'))['heldout37'] + FOLD13
    path = a.out + '/dups.jsonl'
    done = set()
    if os.path.exists(path):
        done = {json.loads(x)['task'] for x in open(path) if x.strip()}
    todo = [t for t in tasks if t not in done]
    print('%d tasks, %d done, %d to do' % (len(tasks), len(done), len(todo)), flush=True)
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(a.gold))}
    live, arclog = D.live, D.arclog
    live.FOLD_BYTES = int(RSS_LIMIT_MIB * 0.07) << 20
    D.SESSION_BYTES = int(RSS_LIMIT_MIB * float(os.environ['ARC_SESSION_SHARE'])) << 20
    sampler = live.Sampler(KIT + '/models-tk')
    search.attach(sampler, None, RSS_LIMIT_MIB)
    search.install('search')  # installs the order-free table_key, as kaggle_worker.source does
    assert D.table_key is search.table_key
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
    n = 0
    for t in todo:
        if time.monotonic() - t0 > a.budget:
            break
        task = json.load(open('%s/data/tasks/%s.json' % (KIT, t)))
        for x in task['test']:
            x.pop('output', None)
        session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=D.SESSION_BYTES)
        run = D.Run(sampler.pri, session, 0, time.monotonic() + 600, task, live.Limits())
        s0 = time.monotonic()
        keys = D.gold_keys(run, specs[t])
        groups = sorted(v for v in keys.values() if len(v) >= 2)
        nforms = len([f for f in specs[t].strip().split('\n') if not f.startswith('(OUT')])
        rec = dict(task=t, forms=nforms, keys=len(keys), groups=groups, all_keys=sorted(keys.values()),counts={k: v for k, v in run.c.items() if k.startswith('gold:')}, seconds=round(time.monotonic() - s0, 1))
        with open(path, 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(json.dumps(rec), flush=True)
        n += 1
    rows = [json.loads(x) for x in open(path) if x.strip()]
    out = {r['task']: r['groups'] for r in rows}
    with open(a.out + '/dups.json', 'w') as f:
        json.dump(out, f, indent=0)
    print('did %d; dups.jsonl has %d of %d tasks' % (n, len(out), len(tasks)), flush=True)


main()
