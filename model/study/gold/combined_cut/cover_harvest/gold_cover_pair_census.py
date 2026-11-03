"""Census bits (Bits.read, the reader the harvest ranked on) of each side of each pair in pairs.jsonl: the gold form and the gold forms that went out with it, in the text before the harvest, and the covering form and the forms brought in, in view-final. Writes pair-census.jsonl in this folder, one line per pair, streamed; a restart skips pairs it has.

  <runtime python> gold_cover_pair_census.py
"""
import gzip, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import gold_cheapest_prune as P

OUT = HERE + '/pair-census.jsonl'
HEAD = re.compile(r'\((\w+) (&[A-Za-z_0-9]+)')


def text(v, t):
    with gzip.open(HERE + '/../' + v + '/' + t + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def side(bits, t, ls, labels):
    got = {}
    for i, x in enumerate(ls):
        m = HEAD.match(x)
        if m and m[2] in labels:
            got[m[2]] = bits.read(t, ls[:i + 1])['bits']
    return got


def main():
    done = set()
    if os.path.exists(OUT):
        done = {(r['stem'], r['gold_label']) for r in map(json.loads, open(OUT))}
    bits = P.Bits()
    with open(OUT, 'a', buffering=1) as out:
        for l in open(HERE + '/pairs.jsonl'):
            p = json.loads(l)
            key = (p['stem'], p['gold_parts']['label'])
            if key in done:
                continue
            t = p['stem']
            g = side(bits, t, text('view-before-harvest', t), {p['gold_parts']['label'], *p['gold_out']})
            c = side(bits, t, text('view-final', t), {p['cover_parts']['label'], *p['brought']})
            out.write(json.dumps(dict(stem=t, gold_label=key[1], cover_label=p['cover_parts']['label'], gold=g, cover=c)) + '\n')
            print(t, key[1], flush=True)


if __name__ == '__main__':
    main()
