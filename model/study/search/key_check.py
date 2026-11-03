#!/usr/bin/env python
"""Whether gold's table has one merge key across sessions. step4/tp.py takes gold's key in the session of or_q.one and compares it in another
session, so a key that differs between sessions gives a miss in every job on that form.

  <runtime python> key_check.py OUT.jsonl KEY VARIANT [KEY VARIANT ...]      from a kit's top folder, with step4/ beside it

Each pair walks gold's form twice, in two sessions, and writes one line with whether the keys are equal. A line in OUT.jsonl is not done again.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd() + '/step4')
import tp  # noqa: E402

Pt, G, or_q, live = tp.Pt, tp.G, tp.or_q, tp.live


def main():
    out, rest = sys.argv[1], sys.argv[2:]
    done = {(r['key'], r['variant']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    recs = {r['key']: r for r in json.load(open('step4/POINTS.json'))}
    sampler = live.Sampler(Pt.MODELS)
    with open(out, 'a') as f:
        for key, variant in zip(rest[::2], rest[1::2]):
            if (key, variant) in done:
                continue
            rec = recs[key]
            _, golds, case, point = next(j for j in Pt.jobs(rec, Pt.HERE) if j[0] == variant)
            G.GOLDS = golds
            G.golds.cache_clear()
            keys = []
            for _ in range(2):
                tp.st.last = None
                q = or_q.one(sampler, rec['task'], case, point)
                keys.append(tp.st.last)
            row = dict(key=key, variant=variant, same=keys[0] == keys[1], has=keys[0] is not None, bad=q.get('bad'), dead=q.get('dead'), types=list(keys[0][0]) if keys[0] else None)
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(key, variant, row['same'], row['has'], flush=True)


if __name__ == '__main__':
    main()
