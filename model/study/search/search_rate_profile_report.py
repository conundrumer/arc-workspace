#!/usr/bin/env python3
"""Proposals per second and seconds by part, by RSS band, from the `prof` lines of worker logs. It reads partial output.

  python3 search_rate_profile_report.py OUT_DIR [BAND_MIB]

OUT_DIR holds <arm>/<task>/work/*.log. Each row is a delta between two prof lines, in the band of the later line's RSS. Shares are of wall seconds: nxt is the search's clause step, take the pool's table work, setup the scope pick and search fetch, gc Python's collector. rest is wall seconds outside those.
"""
import collections
import glob
import json
import os
import sys

out = sys.argv[1]
band = int(sys.argv[2]) if len(sys.argv) > 2 else 500
for arm in sorted(os.listdir(out)):
    rows = collections.defaultdict(lambda: collections.Counter())
    for path in glob.glob('%s/%s/*/work/*.log' % (out, arm)):
        last = None
        for line in open(path, errors='replace'):
            if not line.startswith('prof '):
                continue
            try:
                r = json.loads(line[5:])
            except ValueError:
                continue
            if last and r['t'] > last['t']:
                b = rows[r['rss'] // band * band]
                b['wall'] += r['t'] - last['t']
                b['draws'] += r['draws'] - last['draws']
                for k in ('cpu', 'gc', 'nxt', 'take', 'setup', 'visits', 'gcn', 'notable', 'equal', 'nodes'):
                    b[k] += r[k] - last[k]
                b['demoted'] += r['mgr'].get('demoted', 0) - last['mgr'].get('demoted', 0)
                b['shed'] += r['mgr'].get('shed', 0) - last['mgr'].get('shed', 0)
            last = r
    print(arm)
    for k in sorted(rows):
        b = rows[k]
        w = b['wall'] or 1
        rest = w - b['nxt'] - b['take'] - b['setup'] - b['gc']
        print('  %5d MiB: %5.1f proposals/s over %4.0f s; nxt %2.0f%%, take %2.0f%%, setup %2.0f%%, gc %2.0f%% (%.0f passes, %.2f s each), rest %2.0f%%; cpu/wall %.2f; demoted %.1f/s, shed %.2f/s; visits %.2f/s; no table %.0f%%' % (
            k, b['draws'] / w, w, 100 * b['nxt'] / w, 100 * b['take'] / w, 100 * b['setup'] / w, 100 * b['gc'] / w, b['gcn'], b['gc'] / max(b['gcn'], 1), 100 * rest / w, b['cpu'] / w, b['demoted'] / w, b['shed'] / w, b['visits'] / w, 100 * b['notable'] / max(b['draws'], 1)))
