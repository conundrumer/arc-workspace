"""The base text of each stem for the extended cut, and the hash that keys a row.

  python3 gold_orcut_base.py OUT.json [STEM...]     writes {stem: forms} for the stems, or for every stem of the view with no stems given

A stem with a folder of its own in the view takes the first row of pairs.jsonl.gz. A stem whose entry is a link into the old corpus, or that the view lacks, takes points-eval.json where that holds it: the first row of a link can predate the round text that points-eval.json holds. A training stem that is a link takes the link's first row. A stem in neither has no text and no row.
"""
import gzip, hashlib, json, os, sys, time

G = os.environ.get('ORCUT_VIEW_ROOT', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-cover-forms-a036da074/')


def sha(lines):
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()[:16]


def split(text):
    return [x for x in text.splitlines() if x.strip()]


def first(path):
    with gzip.open(path, 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def points():
    for _ in range(5):  # the view's revision may swap a file while this reads it
        try:
            return {p['task']: p['gold_sexp'] for p in json.load(open(G + 'points-eval.json'))}
        except (OSError, json.JSONDecodeError):
            time.sleep(2)
    return {}


def text_of(stem, pts):
    d = G + 'corpus-view/' + stem
    for _ in range(5):
        try:
            if os.path.isdir(d) and not os.path.islink(d):
                return split(first(d + '/pairs.jsonl.gz'))
            if stem in pts:
                return split(pts[stem])
            if os.path.exists(d + '/pairs.jsonl.gz'):
                return split(first(d + '/pairs.jsonl.gz'))
            return None
        except (OSError, EOFError, json.JSONDecodeError):
            time.sleep(2)
    return None


def stems_of_view():
    return sorted(t for t in os.listdir(G + 'corpus-view') if os.path.isdir(G + 'corpus-view/' + t))


def main():
    out, stems = sys.argv[1], sys.argv[2:] or stems_of_view()
    pts = points()
    got = {t: text_of(t, pts) for t in sorted(set(stems) | (set(pts) if len(sys.argv) == 2 else set()))}
    json.dump({t: v for t, v in got.items() if v}, open(out, 'w'))
    print(sum(1 for v in got.values() if v), 'stems with text,', sum(1 for v in got.values() if not v), 'without')


if __name__ == '__main__':
    main()
