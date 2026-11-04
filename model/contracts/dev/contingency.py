"""Dev labeling layer: how each output postcondition of each table stands under the output variants. Not model input.

    CONTRACTS_OUT=OUT_DIR python3 contingency.py TASK [TASK ...]

Reads the variants and analyze.py's <task>.uses.jsonl, so it runs after analyze.py. An output variant edits cells of one train output and
leaves the input as it was. For each output postcondition of a table, each output variant that counts for the table (its preconditions hold,
as analyze.py gives them) either leaves the table's rows as they were or moves them, and either keeps the postcondition or breaks it. The
postcondition is:

- a prediction where some counted variant breaks it and leaves the table's rows as they were: the table's rows come from the input, and the
  match with the output could fail;
- circular where no such variant exists and some counted variant moves the table's rows: the table follows the output;
- vacuous where every counted variant keeps it and leaves the table's rows as they were: it holds for every output that the preconditions
  admit;
- untested where no output variant counts for the table.

Prints one line per table, then the totals of the task, as each task ends.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A  # noqa: E402
import jsonl as J  # noqa: E402

CLASSES = ('prediction', 'circular', 'vacuous', 'untested')


def classify(base, V, post, k, counted):
    """The class of output postcondition k, and the count of (rows moved, postcondition broken) over the output variants that count for its
    table."""
    t = k.split('|')[0]
    seen = Counter()
    for v in V:
        if t not in counted.get(v['id'], ()):
            continue
        moved = v['digests'].get(t) != base['digests'][v['source']].get(t)
        broke = not A.holds(post[k], v['features'].get(k, 'MISSING'))
        seen[moved, broke] += 1
    if not seen:
        return 'untested', seen
    if seen[False, True]:
        return 'prediction', seen
    if seen[True, False] or seen[True, True]:
        return 'circular', seen
    return 'vacuous', seen


def main(tasks):
    total = Counter()
    for task in tasks:
        lines = list(J.records(A.OUTDIR / (task + '.variants.jsonl')))
        base = next(l for l in lines if l['kind'] == 'base')
        V = [l for l in lines if l['kind'] == 'out' and 'features' in l]
        counted = {u['id']: set(u['counted']) for u in J.records(A.OUTDIR / (task + '.uses.jsonl'))}
        post = A.postconditions(base)
        per = {}
        for k in post:
            if A.is_output(k):
                c, _ = classify(base, V, post, k, counted)
                per.setdefault(k.split('|')[0], Counter())[c] += 1
        n = Counter()
        for t, c in sorted(per.items()):
            print('%s %-32s %s' % (task, t, '  '.join('%s %d' % (x, c[x]) for x in CLASSES)), flush=True)
            n.update(c)
        print('%s %-32s %s' % (task, 'all', '  '.join('%s %d' % (x, n[x]) for x in CLASSES)), flush=True)
        total.update(n)
    print('%-41s %s' % ('all tasks', '  '.join('%s %d' % (x, total[x]) for x in CLASSES)), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
