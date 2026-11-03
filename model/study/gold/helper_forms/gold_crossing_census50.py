"""Writes round-out/crossing-census50.json from the rows of gold_stage_census.py in round-out/stage-census50.jsonl, at the rule of crossing.json: whole past 25 bits and worst stage under 25. Clauses that the census read and that don't cross go to round-out/uncrossed-census50.json.

  gold_crossing_census50.py
"""
import json
rows = [json.loads(l) for l in open('round-out/stage-census50.jsonl')]
stems = open('tasks-census50.txt').read().split()
crossing, uncrossed = {t: [] for t in stems}, {t: [] for t in stems}
for r in rows:
    if 'skip' in r:
        uncrossed[r['task']].append(dict(line=r['line'], skip=r['skip']))
    elif r['whole'] > 25 and r['worst'] < 25:
        crossing[r['task']].append(dict(line=r['line'], cuts=r['cuts'], whole=r['whole'], worst=r['worst']))
    elif r['whole'] > 25:
        uncrossed[r['task']].append(dict(line=r['line'], cuts=r['cuts'], whole=r['whole'], worst=r['worst']))
json.dump(crossing, open('round-out/crossing-census50.json', 'w'))
json.dump(uncrossed, open('round-out/uncrossed-census50.json', 'w'))
print(json.dumps(crossing))
print(json.dumps(uncrossed))
