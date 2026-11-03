#!/usr/bin/env python
"""Teacher-forced census of gold's forms in the parents context, for tasks that have no census rows. It is the walk of frontier_q.py with one context.

  <runtime python> features_census.py TASKS_FILE OUT.jsonl K N

Environment, as frontier_q.py reads it: SAMPLER_CODE, SEARCH_GOLDS, SEARCH_MODELS. A row goes to OUT.jsonl per form; a restart skips finished forms. Prints one line per form, with a rate and an ETA.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.environ['SAMPLER_CODE'])
import live  # noqa: E402
import or_q  # noqa: E402
import search_gold as G  # noqa: E402

NAME = re.compile(r'&[A-Za-z_0-9]+')


def parents(lines, i):
    """The indexes before i of the forms that line i reads, directly or not, in order."""
    head = {NAME.search(x)[0]: j for j, x in enumerate(lines) if NAME.search(x)}
    got, todo = set(), [i]
    while todo:
        for n in NAME.findall(lines[todo.pop()]):
            j = head.get(n)
            if j is not None and j < i and j not in got:
                got.add(j)
                todo.append(j)
    return sorted(got)


def main():
    tasks = open(sys.argv[1]).read().split()
    out, K, N = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    done = {(r['task'], r['line']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    items = []
    for task in tasks:
        lines = [x for x in G.golds()[task].splitlines() if x.strip()]
        for i, x in enumerate(lines):
            if x.split()[0].lstrip('(') in live.KIND_TOK:
                items.append((task, lines, i))
    items = items[K::N]
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    t0 = time.time()
    n = 0
    with open(out, 'a') as f:
        for count, (task, lines, i) in enumerate(items, 1):
            if (task, i) in done:
                continue
            keep = parents(lines, i)
            target = lines[i]
            kind = target.split()[0].lstrip('(')
            G.gold_of = lambda t, c, p, ls=[lines[j] for j in keep] + [target]: (t, ls)
            try:
                q = or_q.one(sampler, task, kind, [len(keep), 0], kind)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            q.update(line=i, scope='parents', kind=kind, nscope=len(keep), task=task, target=target)
            f.write(json.dumps(q) + '\n')
            f.flush()
            n += 1
            rate = n / max(time.time() - t0, 1e-9)
            print(task, i, len(keep), q.get('total'), q.get('bad'), q.get('dead'), q.get('error', ''), f'{count}/{len(items)} {rate:.2f}/s ETA {(len(items) - count) / rate:.0f} s', flush=True)


if __name__ == '__main__':
    main()
