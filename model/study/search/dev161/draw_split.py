"""Splits the draw records of a recorded run (sampler/draw_record.py) by where the draw was and whether its query reads the scope.

    draw_split.py DRAWS.jsonl [DRAWS.jsonl ...]

Per file, a count of draws by (root or scope, reads or free, result), and for the draws that gave a known query ('equal'), whether its text
repeats the first new draw of that QueryHash. A draw is at the root where it has one step. Its query reads the scope where its body names a
query (&fN).
"""
import collections
import json
import re
import sys


def split(path):
    recs = [json.loads(l) for l in open(path) if '"repeat"' not in l]
    by, first, same = collections.Counter(), {}, collections.Counter()
    for r in recs:
        d = r['steps'][-1]
        body = d['text'].split(' ', 2)[2] if d['text'].count(' ') >= 2 else ''
        where = 'scope' if len(r['steps']) > 1 else 'root'
        reads = 'reads' if re.search(r'&f\d+', body) else 'free'
        by[where, reads, r['result']] += 1
        norm = re.sub(r'^\((\w+) &f\d+', r'(\1 &H', d['text'])
        if r['result'] == 'new':
            first.setdefault(d['query_hash'], norm)
        elif r['result'] == 'equal':
            got = first.get(d['query_hash'])
            same['no new draw before' if got is None else 'same text' if got == norm else 'other text'] += 1
    return len(recs), by, same


def main():
    for p in sys.argv[1:]:
        n, by, same = split(p)
        print(p, n, 'draws')
        for k, v in sorted(by.items()):
            print('  %-5s %-5s %-5s %5d  %4.1f%%' % (*k, v, 100 * v / n))
        print('  equal draws:', dict(same))


if __name__ == '__main__':
    main()
