"""The text-level union gold of one task set: every case of each task's solver and the pinned program, with forms merged by identity only (text with each read replaced by its ancestry, labels dropped), so equal tables made by different text stay apart and the table count is an upper bound. Writes union-identity-<set>.jsonl and its sha256 in GOLD_UNION_DIR (default work/lm/data-study/gold/gold-union). design.md gives the cases and the table fields.

  .venv/bin/python gold_union_identity.py SET      SET: train, dev or held-out
"""
import gzip, hashlib, json, os, re, sys
import gold_case_counts as K
from gold_union_fits import set_of
import study_zst as Z  # on the path since gold_union_fits is imported

OUT = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union')  # GOLD_UNION_DIR: the folder of the outputs
D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
W = D + 'sampler/sampler-worker/held/'
HEAD = re.compile(r'\((\w+) &([A-Za-z_][\w]*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')


def program(text):
    """[(identity, kind, line, read identities, depth)] of the program's non-OUT forms."""
    ident, depth, out = {}, {}, []
    for x in text.splitlines():
        m = HEAD.match(x)
        if not x.strip() or not m or x.startswith('(OUT'):
            continue
        body = x[m.end():]
        reads = sorted({ident[n[1]] for n in NAME.finditer(body) if n[1] in ident})
        key = hashlib.sha256((m[1] + NAME.sub(lambda n: '{%s}%s' % (ident[n[1]], n[2]) if n[1] in ident else '&_' + n[2], ' '.join(body.split()))).encode()).hexdigest()[:16]
        ident[m[2]] = key
        depth[key] = 1 + max((depth[r] for r in reads), default=-1)
        out.append((key, m[1], x, reads, depth[key]))
    return out


def main():
    want = sys.argv[1]
    pubs = K.publications()
    path = OUT + '/union-identity-%s.jsonl' % want
    with Z.open_text(path, 'w', atomic=True) as out:
        for t in K.union_tasks(pubs):
            if set_of(t) != want:
                continue
            progs = [('pinned', K.pinned(t))] if K.pinned(t) is not None else []
            if t in pubs:
                for c in pubs[t][1]['cases']:
                    progs.append((c['case'], c.get('filtered_program') or c.get('original_program') or ''))
            tables, order = {}, []
            for name, text in progs:
                for key, kind, line, reads, d in program(text):
                    if key not in tables:
                        tables[key] = dict(kind=kind, form=line, reads=reads, depth=d, cases=[])
                        order.append(key)
                    if name not in tables[key]['cases']:
                        tables[key]['cases'].append(name)
            index = {k: i for i, k in enumerate(order)}
            rows = [dict(key=index[k], kind=tables[k]['kind'], form=tables[k]['form'], reads=[index[r] for r in tables[k]['reads']], depth=tables[k]['depth'],
                         cases=[c for c in tables[k]['cases'] if c != 'pinned'], pinned='pinned' in tables[k]['cases']) for k in order]
            out.write(json.dumps(dict(task=t, set=want, merged='identity', cases=[n for n, _ in progs if n != 'pinned'], tables=rows)) + '\n')
    sha = Z.write_sidecar_sha256(path)  # the hash of the text
    print(want, sha)


if __name__ == '__main__':
    main()
