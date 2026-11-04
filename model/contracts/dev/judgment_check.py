"""Dev labeling layer: the novelty and relevance judgments of OUT_DIR against the judgments of judgments.json, which were written by reading
each solver before any measure was computed. Prints, per measure, the AUC of the measure for the written labels, and each table with its
written label, its measure, and what the measure rests on: the features that the predictor recovers least, or the claims that rule out the
most near misses.

    python judgment_check.py OUT_DIR
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        for t in r['tables']:
            out[(r['task'], t['t'])] = t
    return out


def auc(pos, neg):
    if not pos or not neg:
        return float('nan')
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main(out_dir):
    written = json.loads((HERE / 'judgments.json').read_text())
    for label, path, key, yes, no, col, detail in (('novelty', 'novelty.jsonl', 'novelty', 'N', 'R', 0, 'unpredicted'),
                                                  ('relevance', 'relevance.jsonl', 'relevance', 'Y', 'N', 1, 'ruling')):
        meas = load(Path(out_dir) / path)
        pos, neg, rows, untested = [], [], [], []
        for task, tabs in written.items():
            if task.startswith('_'):
                continue
            for t, j in tabs.items():
                m = meas.get((task, t))
                if not m or m.get('status') != 'tested':
                    untested.append((task, t, m and m.get('status')))
                    continue
                (pos if j[col] == yes else neg if j[col] == no else []).append(m[key])
                rows.append((task, t, j[col], m[key], m.get(detail, [])))
        print('\n%s: written %s %d, written %s %d, unsure %d, without a judgment %d; AUC %.2f' % (label, yes, len(pos), no, len(neg),
              sum(r[2] == '?' for r in rows), len(untested), auc(pos, neg)))
        for task, t, j, v, d in sorted(rows, key=lambda r: (r[2], -r[3])):
            print('  %s %-26s written %s  measured %.2f   %s' % (task, t, j, v, [(str(a)[:50], round(b, 2) if isinstance(b, float) else b) for a, b in d[:2]]))


if __name__ == '__main__':
    main(sys.argv[1])
