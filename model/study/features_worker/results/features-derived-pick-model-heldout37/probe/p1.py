"""Probe 1: on N600 tasks, the recorded scopes that hold every relation a gold form reads (and not the form's own table), and build_target on them.

    bash ../../features-scope-loss-c-read-heldout37-ramp22/env.sh ../features-derived-pick-model-heldout37/probe/p1.py TASK[,TASK..]|all BUDGET [n600|c120]
One JSON line per task to probe/p1.jsonl (p1-c120.jsonl) (tasks already there are skipped): scopes, gold forms, gold keys seen in any scope, pairs, mapped pairs by status,
and per pair (scope index, g, kind, status, target).
"""
import collections
import json
import os
import sys
import time

sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/probe')
T0 = time.time()
import common as C  # noqa: E402

want, budget = sys.argv[1], float(sys.argv[2])
SRC = sys.argv[3] if len(sys.argv) > 3 else 'n600'
CTX = C.NCtx if SRC == 'n600' else C.CCtx
if want == 'all':
    tasks = sorted(os.listdir(C.N600)) if SRC == 'n600' else sorted(f[:8] for f in os.listdir(C.C120) if f.endswith('.events.jsonl') and f[:8] not in C.HELD)
else:
    tasks = want.split(',')
OUT = C.HERE + '/probe/p1%s.jsonl' % ('' if SRC == 'n600' else '-' + SRC)
done = {json.loads(l)['task'] for l in open(OUT)} if os.path.exists(OUT) else set()
for task in tasks:
    if task in done:
        continue
    if time.time() - T0 > budget:
        break
    t1 = time.time()
    try:
        c = CTX(task)
    except Exception as e:  # noqa: BLE001  a C120 task with no node records here, or no view-final gold
        print(task, 'skipped:', type(e).__name__, str(e)[:120], flush=True)
        continue
    sess, d, _ = C.D.session_of(task)
    gk = C.gold_read_keys(c, sess, d)
    allk = set()
    pairs, st = [], collections.Counter()
    tr = tb = 0.0
    for si, sc in enumerate(c.scopes):
        a = time.time()
        try:
            srel = C.relations(sc['texts'], sess, d)
        except Exception:  # noqa: BLE001  a scope that does not replay on this kit
            st['scope replay error'] += 1
            continue
        tr += time.time() - a
        skeys = {v['key'] for v in srel.values()}
        allk |= skeys
        for g, kind, keys, own in gk:
            if keys <= skeys and not own <= skeys:
                a = time.time()
                bt = C.ns['build_target'](c, g, kind, list(sc['texts']), sess, d)
                tb += time.time() - a
                st[bt['status']] += 1
                pairs.append([si, g, kind, sc['kind'], len(sc['texts']), bt['status'], bt.get('target')])
    readk = set().union(*[k for _, _, k, _ in gk]) if gk else set()
    row = dict(task=task, scopes=len(c.scopes), bank_forms=len(c.bank['forms']), gold_forms=len(c.lines), gold_with_keys=len(gk), read_keys=len(readk),
               read_keys_in_some_scope=len(readk & allk), forms_all_reads_in_some_scope=sum(1 for _, _, k, _ in gk if k <= allk),
               pairs=len(pairs), status=dict(st), forms_mapped=len({p[1] for p in pairs if p[5] == 'mapped'}), replay_s=round(tr, 2), target_s=round(tb, 2),
               wall=round(time.time() - t1, 2), pair_rows=pairs)
    with open(OUT, 'a') as f:
        f.write(json.dumps(row, default=str) + '\n')
    print(task, {k: v for k, v in row.items() if k != 'pair_rows'}, flush=True)
    C.MEMO.clear()
print('wall %.1fs' % (time.time() - T0))
