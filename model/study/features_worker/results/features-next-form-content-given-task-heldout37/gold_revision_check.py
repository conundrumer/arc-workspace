"""Checks the replay rows against the node records: seeded gold forms of the 930 tasks, by text with names masked, and their row counts.

Writes gold-revision-check.json. A stem is 'changed' where a seeded form's masked text is not in the fit text of that stem. The fit rows of a changed stem read the cover view, so they stand; a reader can drop them with gold-revision-changed-stems.txt.
"""
import collections
import io
import json
import os
import re
import sys
import time

import zstandard as zstd

import next_form_facts as F

L = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search/'
NAME = re.compile(r'&[a-z]+\d+(\.\w+)?')


def mask(x):
    return NAME.sub('&', x)


def main():
    fit = F.load('fit')
    dz = zstd.ZstdDecompressor()
    names = sorted(e.name.split('.')[0] for e in os.scandir(L) if e.name.endswith('.nodes.jsonl.zst') and e.stat().st_size)
    t0 = time.time()
    same = changed = nofit = forms = hit = rows_same = rows_diff = 0
    bad = []
    for i, t in enumerate(names):
        if t not in fit:
            nofit += 1
            continue
        text = collections.defaultdict(list)
        for r in fit[t]:
            text[mask(r['text'])].append(r)
        ok = True
        with open(L + t + '.nodes.jsonl.zst', 'rb') as fh:
            for x in io.TextIOWrapper(dz.stream_reader(fh), encoding='utf8'):
                r = json.loads(x)
                if not r['tags'].get('seeded'):
                    break
                c = r.get('clause')
                if not c:
                    continue
                forms += 1
                m = text.get(mask(c))
                if m is None:
                    ok = False
                    continue
                hit += 1
                first = {}
                for e in r['x_rows'] or ():
                    if e[0][0] == 1:
                        first.setdefault(tuple(e[0]), e[2])
                n = sorted(first.values())
                ts = [sorted(t2.get('nrows') or ()) for x2 in m for t2 in x2.get('tables', ())]
                if n:
                    if n in ts:
                        rows_same += 1
                    else:
                        rows_diff += 1
        same += ok
        changed += not ok
        if not ok:
            bad.append(t)
        if (i + 1) % 100 == 0:
            rate = (i + 1) / (time.time() - t0)
            print('%d/%d, %.1f tasks/s, eta %.0f s' % (i + 1, len(names), rate, (len(names) - i - 1) / rate), flush=True)
    out = dict(stems_with_nodes=len(names), stems_outside_fit=nofit, stems_same_text=same, stems_changed=changed, seeded_forms=forms, seeded_forms_in_fit_text=hit, seeded_row_counts_equal=rows_same, seeded_row_counts_differ=rows_diff)
    json.dump(out, open(F.R + 'gold-revision-check.json', 'w'), indent=1)
    open(F.R + 'gold-revision-changed-stems.txt', 'w').write('\n'.join(bad) + '\n')
    print(out)


if __name__ == '__main__':
    main()
