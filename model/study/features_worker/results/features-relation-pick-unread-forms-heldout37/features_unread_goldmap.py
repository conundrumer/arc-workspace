"""Maps the lines of the census's base gold to the lines of the two golds of the pool run, by text with the names of forms taken out. Stdlib only.

  python3 features_unread_goldmap.py KIT_POINTS KIT_GOLD2

Writes gold-map.jsonl in this folder: one row per base line of the 35 tasks of the run, flushed, with `kit` (the line of the run's points-eval.json, which the `cover` events index) and `gold2` (the line of golds-factored.json, which the `cover2` events index), each None where no line has that text. `kit_loose` and `gold2_loose` mark a match of the second pass below.

Two lines match when their text is equal once each read of an earlier form is replaced by the matched name, or, in a second pass that repeats until nothing changes, when it is equal with every name of a form replaced by one mark and only one line on each side has that text.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
B = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
OUT_TASKS = ('269e22fb', 'cbebaa4b')
NAME = re.compile(r'&[A-Za-z_0-9]+')


def lines_of(sexp):
    return [x for x in sexp.splitlines() if x.strip()]


def strip(line, known):
    """The line with its head as &SELF, each name in known as its value, and every other name as &?."""
    head = NAME.search(line)[0]

    def sub(m):
        n = m[0]
        return '&SELF' if n == head else known.get(n, '&?')
    return NAME.sub(sub, line)


def blank(line):
    return NAME.sub('&?', line)


def align(a, b):
    """{index in a: index in b}. a and b are line lists; a name of b is mapped to the name of a."""
    out, known, loose = {}, {}, set()
    used = set()
    changed = True
    while changed:
        changed = False
        for i, x in enumerate(a):
            if i in out:
                continue
            ax = strip(x, {n: n for n in known.values()})
            hit = [j for j, y in enumerate(b) if j not in used and strip(y, known) == ax]
            if not hit:
                hit = [j for j, y in enumerate(b) if j not in used and blank(y) == blank(x)]
                if len(hit) != 1 or sum(blank(z) == blank(x) for k, z in enumerate(a) if k not in out) != 1:
                    continue
                loose.add(i)
            j = hit[0]
            out[i] = j
            used.add(j)
            known[NAME.search(b[j])[0]] = NAME.search(x)[0]
            changed = True
    return out, loose


def main():
    base = {p['task']: p['gold_sexp'] for p in json.load(open(B + 'points-base.json'))}
    kit = {p['task']: p['gold_sexp'] for p in json.load(open(sys.argv[1]))}
    gold2 = {p['task']: p['gold_sexp'] for p in json.load(open(sys.argv[2]))}
    held = [t for t in open(W + 'held/tasks.txt').read().split() if t not in OUT_TASKS]
    n = m = m2 = 0
    with open(HERE + 'gold-map.jsonl', 'w') as out:
        for t in held:
            a, b, c = lines_of(base[t]), lines_of(kit[t]), lines_of(gold2[t])
            (one, l1), (two, l2) = align(a, b), align(a, c)
            for i, x in enumerate(a):
                out.write(json.dumps(dict(task=t, line=i, kind=x.split()[0].lstrip('('), kit=one.get(i), kit_loose=i in l1, gold2=two.get(i), gold2_loose=i in l2, kit_text=b[one[i]] if i in one else None)) + '\n')
                n += 1
                m += i in one
                m2 += i in two
            out.flush()
            print(t, len(a), len(b), len(c), 'kit %d, gold2 %d' % (len(one), len(two)), [i for i in range(len(a)) if i not in one][:12], flush=True)
    print('%d base lines, %d in the kit gold, %d in the second gold' % (n, m, m2))


if __name__ == '__main__':
    main()
