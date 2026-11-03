"""Cases of each task's solver, from the converter's empty-gold publications: the latest publication that holds the task (gen-rNN rounds over gen-v3), its cases, the concept case, the cases that gen-v3's excluded-case-files.tsv excludes (left out; a case $A $B is the file A+B.arclog), and the distinct forms across the cases by depth against the pinned program's. Writes case-counts.jsonl in this folder.

  python3 gold_case_counts.py

Forms are compared by text with each read replaced by the text of the form it reads, recursively, and labels dropped, so two forms with equal text and equal ancestry count once; equal tables made by different text count twice. Depth is 0 for a form that reads no form.
"""
import collections, glob, gzip, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/'
HEAD = re.compile(r'\((\w+) &([A-Za-z_][\w]*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')


def publications():
    """{task: record}, a later round's record over an earlier one."""
    paths = sorted(glob.glob(G + 'gen-v3-11f6a212c/publication*/gold.jsonl.zst'))
    paths += sorted(glob.glob(G + 'gen-r*/publication-*/gold.jsonl.zst'), key=lambda p: int(re.search(r'gen-r(\d+)', p)[1]))
    got = {}
    for p in paths:
        out = subprocess.run(['zstd', '-dc', p], capture_output=True, text=True).stdout
        for l in out.splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            res = r.get('result')
            res = json.loads(res) if isinstance(res, str) else res
            if r.get('task') and res and res.get('cases'):
                got[r['task']] = (p, res)
    return got


def forms(text):
    """[(identity, depth)] of the program's non-OUT forms."""
    lines = [x for x in text.splitlines() if x.strip() and HEAD.match(x) and not x.startswith('(OUT')]
    ident, depth, out = {}, {}, []
    for x in lines:
        lab = HEAD.match(x)[2]
        body = x[HEAD.match(x).end():]
        reads = [m[1] for m in NAME.finditer(body) if m[1] in ident]
        i = HEAD.match(x)[1] + NAME.sub(lambda m: '{%s}%s' % (ident[m[1]], m[2]) if m[1] in ident else '&_' + m[2], body)
        ident[lab] = str(hash(' '.join(i.split())))
        depth[lab] = 1 + max((depth[r] for r in reads), default=-1)
        out.append((ident[lab], depth[lab]))
    return out


def excluded():
    got = collections.defaultdict(set)
    for l in open(G + 'gen-v3-11f6a212c/excluded-case-files.tsv'):
        t, f = l.rstrip('\n').split('\t')
        if f.endswith('.arclog'):
            got[t].add(f[:-len('.arclog')])
    return got


def pinned(t):
    with gzip.open(G + 'gold-v3-combined-cut/view-final/%s/pairs.jsonl.gz' % t, 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def main():
    pubs, ex = publications(), excluded()
    with open(HERE + '/case-counts.jsonl', 'w') as out:
        for t in sorted(os.listdir(G + 'gold-v3-combined-cut/view-final')):
            if t not in pubs:
                out.write(json.dumps(dict(task=t, publication=None)) + '\n')
                continue
            p, res = pubs[t]
            cases = [c for c in res['cases'] if c['case'].replace('$', '').replace(' ', '+') not in ex[t]]
            texts = {c['case']: c.get('filtered_program') or c.get('original_program') or '' for c in cases}
            union = {}
            for text in set(texts.values()):
                for i, d in forms(text):
                    union[i] = min(d, union.get(i, d))
            pin = forms(pinned(t))
            out.write(json.dumps(dict(task=t, publication=p.replace(G, ''), cases=len(cases), excluded=len(res['cases']) - len(cases), concept=[c['case'] for c in cases if c.get('concept')], skipped=len(res.get('skipped_cases') or []),
                                      distinct_programs=len(set(texts.values())), union_by_depth=dict(collections.Counter(min(d, 7) for d in union.values())),
                                      pinned_by_depth=dict(collections.Counter(min(d, 7) for _, d in pin)))) + '\n')


if __name__ == '__main__':
    main()
