"""Writes check-expected.json, the Mac's rows of the check stems, from measured/rows-0.jsonl (35ab12c3, all forms) and measured/e88/rows-0.jsonl (88bcf3b4, lines 56, 59 and 72 under POD_ORDER_CAP=4, POD_BUDGET=32, POD_PREFIX=0, POD_ONLY=56,59,72).

  python3 gold_pod_expect.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))


def last(path, task):
    got = None
    for l in open(path):
        r = json.loads(l)
        if r['task'] == task:
            got = r
    return got


a, b = last(HERE + '/measured/rows-0.jsonl', '35ab12c3'), last(HERE + '/measured/e88/rows-0.jsonl', '88bcf3b4')
json.dump([dict(task='35ab12c3', lines=None, row=a), dict(task='88bcf3b4', lines=[56, 59, 72], row=b)], open(HERE + '/check-expected.json', 'w'))
print('check-expected.json:', [(e['task'], len(e['row']['forms'])) for e in json.load(open(HERE + '/check-expected.json'))])
