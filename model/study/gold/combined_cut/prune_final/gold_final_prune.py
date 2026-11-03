"""Prune on the final text: runs the prune step of gold_cheapest_prune.py on view-final, on the stems with a form that no other form reads. Rows in rows.jsonl; gold_combined_view.py takes a row with `taken` whose `vsha` is its stem's text.

  <runtime python> gold_final_prune.py run
  <runtime python> gold_final_prune.py child STEM...
"""
import gzip, hashlib, json, os, sys
import gold_cheapest_prune as P
from gold_cheapest_prune import C, dead_lines, program_lines

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = HERE + '/../view-final/'
OUT = HERE + '/rows.jsonl'


def text_of(t):
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def vsha(text):
    return hashlib.sha256('\n'.join(text.splitlines()).encode()).hexdigest()[:16]


def child(stems):
    bits, hand = P.Bits(), {}
    for t in stems:
        text = text_of(t)
        print(json.dumps(dict(P.one(t, bits, hand, {t: dict(program=text)}), vsha=vsha(text))), flush=True)


def run():
    done = {(r['stem'], r.get('vsha')) for r in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
    stems = sorted(t for t in os.listdir(VIEW) if os.path.exists(VIEW + t + '/pairs.jsonl.gz'))
    left = [t for t in stems if (t, vsha(text_of(t))) not in done and dead_lines(program_lines(text_of(t)))]
    print(len(left), 'stems', flush=True)
    with open(OUT, 'a') as out:
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


if __name__ == '__main__':
    child(sys.argv[2:]) if sys.argv[1] == 'child' else run()
