#!/usr/bin/env python3
"""Stops by kind per task, from the `stops` lines of worker logs. It reads partial output. Each generation's counts restart, so a task's count is the sum of each generation's last line.

  python3 search_stop_kinds_report.py OUT_DIR/ARM
"""
import collections
import glob
import json
import os
import re
import sys

arm = sys.argv[1]
total, tasks, draws = collections.Counter(), collections.defaultdict(collections.Counter), 0
KEY = re.compile(r'stop (\S+) (\S+?),')
for t in sorted(os.listdir(arm)):
    last, end = {}, 0
    for path in glob.glob('%s/%s/work/*.log' % (arm, t)):
        for line in open(path, errors='replace'):
            if line.startswith('stops '):
                try:
                    r = json.loads(line[6:])
                except ValueError:
                    continue
                last[r['generation']] = r['c']
                end = max(end, r['draws'])
    draws += end
    for c in last.values():
        for k, v in c.items():
            if k.startswith('drop:table'):
                m = KEY.search(k)
                k = 'table:' + ('%s/%s' % m.groups() if m else k[12:80])
            tasks[t][k] += v
            total[k] += v
print('tasks', len(tasks), 'proposals', draws)
for k, v in total.most_common():
    print('%-42s %7d  %6.2f per 1,000 proposals  on %2d tasks' % (k, v, 1000 * v / max(draws, 1), sum(k in c for c in tasks.values())))
print('per task, TableWork and byte budget (RequestBytes, AssignmentBytes) table stops:')
for t, c in sorted(tasks.items()):
    tw = sum(v for k, v in c.items() if k.startswith('table:') and 'TableWork' in k)
    bb = sum(v for k, v in c.items() if k.startswith('table:') and ('RequestBytes' in k or 'AssignmentBytes' in k))
    print(' ', t, tw, bb, 'OUT stops', c['out:Stopped'], {k[12:]: v for k, v in c.items() if k.startswith('out:Stopped:')})
