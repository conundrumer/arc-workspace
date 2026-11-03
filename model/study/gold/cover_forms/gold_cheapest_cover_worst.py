"""For each cover stem, whether its swap raised the stem's worst form against the helper text, in the all-earlier-forms context. It changes no stem.

  <runtime python> gold_cheapest_cover_worst.py run
  <runtime python> gold_cheapest_cover_worst.py child STEM...

One row per stem in round-out/cover-worst.jsonl: helper and cover figures, and `raised`. The cover text is the stem's row program in corpus-view, the helper text the first row of the helper view. A stem past 5 min or 8 GiB has a set_aside row.
"""
import json, os, sys
from gold_cheapest_common import *
import gold_cheapest_case as C

OUT = HERE + 'round-out/cover-worst.jsonl'


def child(stems):
    bits = Bits()
    tick = lambda: print('tick', flush=True)
    for t in stems:
        print('stem', t, flush=True)
        h, c = bits.whole(t, program_lines(first_row(HELP + 'corpus-view/%s/pairs.jsonl.gz' % t)['gold_sexp']), tick), bits.whole(t, program_lines(view_row(t)['gold_sexp']), tick)
        print(json.dumps(dict(stem=t, helper=h, cover=c, raised=c['worst'] > h['worst'], taken=None, why='worst %.2f to %.2f, sum %.2f to %.2f' % (h['worst'], c['worst'], h['sum'], c['sum']))), flush=True)


def run():
    done = {json.loads(l)['stem'] for l in open(OUT)} if os.path.exists(OUT) else set()
    left = [r['stem'] for r in map(json.loads, open(HERE + 'view-stems.jsonl')) if r['source'] == 'cover' and r['stem'] not in done]
    print(len(left), 'stems', flush=True)
    with open(OUT, 'a') as out:
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


if __name__ == '__main__':
    child(sys.argv[2:]) if sys.argv[1] == 'child' else run()
