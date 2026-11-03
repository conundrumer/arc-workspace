"""Writes concept-cases.json: each stem's concept case name. usage: gold_helper_cases.py GEN"""
import json, sys
import arclog
tasks = open('tasks.txt').read().split()
got = {}
for t in tasks:
    streams, _ = arclog.corpus_streams(sys.argv[1], all_cases=True, task_ids=[t])
    c = [s.case for s in streams if s.concept]
    if c:
        got[t] = c[0]
json.dump(got, open('concept-cases.json', 'w'))
print(len(got))
