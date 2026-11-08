"""Cases of each task's solver, from the converter's empty-gold publications: the latest publication that holds the task (gen-rNN rounds over gen-v3), or, where GOLD_PUBLICATION_SELECT names a selection file, the line that the selection names (publications()), its cases, the concept case and the distinct forms across the cases by depth against the pinned program's. Writes case-counts.jsonl in this folder.

  python3 gold_case_counts.py

Forms are compared by text with each read replaced by the text of the form it reads, recursively, and labels dropped, so two forms with equal text and equal ancestry count once; equal tables made by different text count twice. Depth is 0 for a form that reads no form.
"""
import collections, glob, gzip, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/'
HEAD = re.compile(r'\((\w+) &([A-Za-z_][\w]*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')


def publication_paths():
    """The publication files, earlier rounds first (gen-v3, then gen-rNN by NN)."""
    paths = sorted(glob.glob(G + 'gen-v3-11f6a212c/publication*/gold.jsonl.zst'))
    return paths + sorted(glob.glob(G + 'gen-r*/publication-*/gold.jsonl.zst'), key=lambda p: int(re.search(r'gen-r(\d+)', p)[1]))


def publication_lines():
    """(path, record, result) of each line of each publication file in the order of publication_paths(); result is the record's result as a dict. A line that does not parse is left out."""
    for p in publication_paths():
        out = subprocess.run(['zstd', '-dc', p], capture_output=True, text=True).stdout
        for l in out.splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            res = r.get('result')
            yield p, r, (json.loads(res) if isinstance(res, str) else res)


def selection():
    """The round's choice of publication lines, or None where GOLD_PUBLICATION_SELECT is not set. The variable names a JSON file {"tasks": {task: {"publication": path under G, "resume_key": key}}, "refused": {task: reason}}, which a round's selection step writes (gen-r71: tools/round_select.py). A file that does not exist, or one that refuses any task, stops the program."""
    path = os.environ.get('GOLD_PUBLICATION_SELECT')
    if not path:
        return None
    if not os.path.exists(path):
        raise SystemExit('GOLD_PUBLICATION_SELECT names %s, which does not exist' % path)
    sel = json.load(open(path))
    if sel.get('refused'):
        raise SystemExit('%s refuses %d tasks (%s ...); no case is taken from another publication line' % (path, len(sel['refused']), ' '.join(sorted(sel['refused'])[:5])))
    return sel


def publications():
    """{task: (path, result)}: the latest publication line that holds the task and has cases, a later file over an earlier one (gen-rNN rounds over gen-v3). With GOLD_PUBLICATION_SELECT set (selection()), a task that the selection names takes the line the selection names (the file and the resume_key), whichever is later, and the program stops if that line is not there."""
    sel = selection()
    want = {(v['publication'], v['resume_key']): t for t, v in sel['tasks'].items()} if sel else {}
    got, chosen = {}, {}
    for p, r, res in publication_lines():
        if r.get('task') and res and res.get('cases'):
            got[r['task']] = (p, res)
            if want.get((p.replace(G, ''), r.get('resume_key'))) == r['task']:
                chosen[r['task']] = (p, res)
    if sel:
        lost = sorted(set(sel['tasks']) - set(chosen))
        if lost:
            raise SystemExit('the selection names a publication line that is not there, for %d tasks: %s ...' % (len(lost), ' '.join(lost[:5])))
        got.update(chosen)
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


def pinned(t):
    """The pinned program of the task, or None where gold-v3's view-final has none (a solver written after it)."""
    p = G + 'gold-v3-combined-cut/view-final/%s/pairs.jsonl.gz' % t
    if not os.path.exists(p):
        return None
    with gzip.open(p, 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def union_tasks(pubs):
    """The tasks of the union gold: those with a pinned program, and those with a publication."""
    return sorted(set(os.listdir(G + 'gold-v3-combined-cut/view-final')) | set(pubs))


def main():
    pubs = publications()
    with open(HERE + '/case-counts.jsonl', 'w') as out:
        for t in sorted(os.listdir(G + 'gold-v3-combined-cut/view-final')):
            if t not in pubs:
                out.write(json.dumps(dict(task=t, publication=None)) + '\n')
                continue
            p, res = pubs[t]
            cases = res['cases']
            texts = {c['case']: c.get('filtered_program') or c.get('original_program') or '' for c in cases}
            union = {}
            for text in set(texts.values()):
                for i, d in forms(text):
                    union[i] = min(d, union.get(i, d))
            pin = forms(pinned(t))
            out.write(json.dumps(dict(task=t, publication=p.replace(G, ''), cases=len(cases), concept=[c['case'] for c in cases if c.get('concept')], skipped=len(res.get('skipped_cases') or []),
                                      distinct_programs=len(set(texts.values())), union_by_depth=dict(collections.Counter(min(d, 7) for d in union.values())),
                                      pinned_by_depth=dict(collections.Counter(min(d, 7) for _, d in pin)))) + '\n')


if __name__ == '__main__':
    main()
