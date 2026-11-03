#!/usr/bin/env python
"""Recount of table recall and of pool duplicates under the table key whose order of tied columns doesn't matter, from a pool run's saved node records. One row per task, streamed;
finished tasks are skipped.

  <runtime python> search_key_recount.py OUT.jsonl ARM_DIR      from a kit's top folder, with PYTHONPATH on the kit's sampler and SEARCH_MODELS set

Both keys read a node's saved rows, capped at S.X_ROWS_CAP per entry, and gold's tables go through the same cap, so the two sides compare. Equal tables stay equal under the cap.
Fields: nodes, distinct_old, distinct_new (nodes minus distinct is duplicates), forms (gold forms with a table), hits_old, hits_new, new_forms (forms that only the new key finds).
"""
import collections
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'model', 'study', 'sampler'))
import live  # noqa: E402
import superdag as D  # noqa: E402
import superdag_search as SS  # noqa: E402

S = D.S
OLD, NEW = SS.BASE_TABLE_KEY, SS.table_key
WIDE = D.M.WIDE


def as_table(types, entries):
    """A table that the key functions read, from x_rows entries: [[kind, index], rows, count, ...]."""
    return dict(types=types, widths=[4 if str(t) in WIDE else 1 for t in types], entries=[(tuple(e[0]), None, [tuple(r) for r in e[1]], None, None) for e in entries])


def keys(tb):
    return OLD(tb)[0], NEW(tb)[0]


def main():
    out, arm = sys.argv[1:3]
    specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
    done = {r['task'] for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    sampler = live.Sampler(os.environ['SEARCH_MODELS'])
    with open(out, 'a') as f:
        for path in sorted(glob.glob(arm + '/*.nodes.jsonl.zst')):
            task = os.path.basename(path).split('.')[0]
            if task in done or task not in specs:
                continue
            text = subprocess.run(['zstd', '-dc', path], capture_output=True, check=False).stdout.decode(errors='replace')
            old, new = set(), set()
            n = 0
            for line in text.splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not r.get('x_rows') or not r.get('table_types'):
                    continue
                n += 1
                a, b = keys(as_table(r['table_types'], r['x_rows']))
                old.add(a)
                new.add(b)
            sess, d, _ = D.session_of(task)
            run = D.Run(sampler.pri, sess, 0, 1e12, d, live.Limits())
            forms = [str(x) for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
            run.collect = []
            per = collections.defaultdict(list)
            try:
                run.scope(forms)
            except Exception as e:  # noqa: BLE001
                f.write(json.dumps(dict(task=task, error=repr(e)[:200], nodes=n)) + '\n')
                f.flush()
                continue
            for i, ct in enumerate(run.collect):
                for _, j in D.relation_tables(ct):
                    try:
                        tb = S.parse_table(D.OneTable(ct, j))
                    except D.M.Fail:
                        continue
                    per[i].append(keys(as_table([str(t) for t in tb['types']], S.rows_with_models(tb, S.X_ROWS_CAP))))
            hits_old = sorted(i for i, ks in per.items() if any(a in old for a, _ in ks))
            hits_new = sorted(i for i, ks in per.items() if any(b in new for _, b in ks))
            row = dict(task=task, nodes=n, distinct_old=len(old), distinct_new=len(new), forms=len(per), hits_old=len(hits_old), hits_new=len(hits_new), new_forms=sorted(set(hits_new) - set(hits_old)), lost_forms=sorted(set(hits_old) - set(hits_new)))
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(task, n, len(old), len(new), len(hits_old), len(hits_new), flush=True)


if __name__ == '__main__':
    main()
