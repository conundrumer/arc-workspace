"""For each task file given, steps a one-proposer DET (DET, proposer, END) on an empty program, as live.Run.proposed draws it, and prints the verdict of each proposer.

  <python> proposer_probe.py TASK_JSON...
"""
import json
import sys
import time

import arclog

SETTINGS = dict(rule_tests=False, table_work_cap=1 << 21, static_pruning=True)
DET_TOK, END_NAME = 1, 'END'

for path in sys.argv[1:]:
    with open(path) as f:
        d = json.load(f)
    t0 = time.perf_counter()
    session = arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), arclog.DecodeSettings(relations=4096, **SETTINGS), session_bytes=2 << 30)
    V = session.vocabulary
    names = [V.name(i) for i in range(len(V))]
    end = names.index(END_NAME)
    root = session.decoder()
    root.step(DET_TOK)
    proposers = [i for i in range(len(V)) if V.kind(i) == 'proposer']
    ok = root.admits(proposers)
    out = {}
    for p, y in zip(proposers, ok):
        if not y:
            out[names[p]] = 'not admitted'
            continue
        f = root.fork()
        f.step(p)
        try:
            f.step(end)
            out[names[p]] = 'admitted'
        except arclog.Refusal as e:
            out[names[p]] = 'refused: %s' % e
    print(json.dumps(dict(task=path.rsplit('/', 1)[-1], seconds=round(time.perf_counter() - t0, 2), verdicts=out)))
