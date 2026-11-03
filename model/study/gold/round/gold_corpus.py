"""Write a gold-only AST corpus from an empty-gold publication: <out>/<task>/pairs.jsonl.gz with one line,
{"task", "case", "gold_sexp"}, the gold of the case that corpus-v11's first line names, its derived relations
renamed &r0, &r1, ... in definition order as corpus-v11 writes them. Skips tasks already written.
usage: gold_corpus.py <publication.jsonl.zst> <corpus-v11 dir> <out dir>"""
import gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/judge3')
from framed_jsonl import iter_json

HEAD = re.compile(r'^\((?:DET|RULE|INIT|OUT)\s+&([A-Za-z_][\w]*)', re.M)
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')
RIGID = re.compile(r'^\(RIGID_DET\s+&([A-Za-z_]\w*)', re.M)


def anonymize(text):
    names = {}
    for n in HEAD.findall(text):
        names.setdefault(n, f'r{len(names)}')
    rigid = set(RIGID.findall(text))

    def renamed(m):
        owner, rest = m.group(1), m.group(2)
        if owner in rigid and rest:   # &marker.glyph names the part &glyph, and &marker.pose names no relation
            first, *others = rest[1:].split('.')
            rest = '.' + '.'.join([first if first == 'pose' else names.get(first, first), *others])
        return '&' + names.get(owner, owner) + rest

    return NAME.sub(renamed, text)


publication, reference, out = map(Path, sys.argv[1:])
done = wrote = missing = 0
for record in iter_json(publication):
    task = record['task']
    target = out / task / 'pairs.jsonl.gz'
    if target.exists():
        done += 1
        continue
    first = reference / task / 'pairs.jsonl.gz'
    want = None
    if first.exists():
        with gzip.open(first, 'rt') as f:
            line = f.readline()
        want = json.loads(line).get('case') if line.strip() else None
    cases = record['result'].get('cases') or []
    case = next((c for c in cases if c['case'] == want), cases[0] if cases else None)
    if case is None:
        missing += 1
        print(task, 'no case', flush=True)
        continue
    text = case.get('filtered_program') or case.get('original_program')
    if not text:
        missing += 1
        print(task, 'no program text:', str(record['result'].get('reason'))[:120], flush=True)
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.tmp')
    with gzip.open(tmp, 'wt') as f:
        f.write(json.dumps(dict(task=task, case=case['case'], gold_sexp=anonymize(text))) + '\n')
    tmp.rename(target)
    wrote += 1
print(f'wrote {wrote}, already {done}, no case {missing}', flush=True)
