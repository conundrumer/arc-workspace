"""Reads the output of check2.sh: the `first pass` events of the worker log, and the gold forms that the cover file shows.

  <python> -I search_pass_check2.py OUTDIR TASK PASS_CPU [GOLD ...]

Prints each `first pass` line. Exits 0 where the log has the three events INIT, RULE and DET, each with by_cpu true, budget PASS_CPU and cpu at most PASS_CPU + SLACK, and where the gold
indices given (the roots to cover) are in the `covered` list of the DET event. Exit 2 otherwise.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_pass_read as PR  # noqa: E402


def main():
    out, task, budget = sys.argv[1], sys.argv[2], float(sys.argv[3])
    want = [int(x) for x in sys.argv[4:]]
    log = open(out + '/worker.log', errors='replace').read()
    evs = PR.events(log)
    for e in evs:
        print('first pass', json.dumps(e))
    problems = PR.why(dict(first=dict(seconds=budget, rule=budget, cpu=True)), evs)
    if len(evs) != 3:
        problems.append('%d first pass events, want 3' % len(evs))
    got = PR.first_set(evs)
    covered = set(got['DET']['covered']) if 'DET' in got else set()
    cover_file = [json.loads(x) for x in open('%s/%s.out.jsonl.cover' % (out, task))] if os.path.exists('%s/%s.out.jsonl.cover' % (out, task)) else []
    t0 = float(open(out + '/start').read().split()[0]) if os.path.exists(out + '/start') else None
    print('gold covered when the pass ended: %s' % sorted(covered))
    print('cover file: %s' % ' '.join('g%d@%.1fs' % (c['gold'], c['time'] - t0) for c in sorted(cover_file, key=lambda c: c['time'])))
    for g in want:
        if g not in covered:
            problems.append('gold %d not covered when the pass ended' % g)
    for line in problems:
        print('FAIL: ' + line)
    print('check 2 ' + ('FAILED' if problems else 'passed'))
    return 2 if problems else 0


sys.exit(main())
