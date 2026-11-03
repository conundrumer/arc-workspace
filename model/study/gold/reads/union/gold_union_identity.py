"""The text-level union gold of one task set: every non-excluded case of each task's solver and the pinned program, with forms merged by identity only (text with each read replaced by its ancestry, labels dropped), so equal tables made by different text stay apart and the table count is an upper bound. Writes union-identity-<set>.jsonl and its sha256 in this folder. design.md gives the cases and the table fields.

  python3 gold_union_identity.py SET      SET: ramp, 37, 62 or training
"""
import gzip, hashlib, json, os, re, sys
import gold_case_counts as K

HERE = os.path.dirname(os.path.abspath(__file__))
D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
W = D + 'sampler/sampler-worker/held/'
HEAD = re.compile(r'\((\w+) &([A-Za-z_][\w]*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')


def set_of(t, sets):
    return next((n for n, s in sets if t in s), 'training')


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
    sets = [('ramp', set(open(W + 'ramp-fold.txt').read().split())),
            ('37', set(open(W + 'tasks.txt').read().split())), ('62', set(open(W + 'leave_out.txt').read().split()))]
    pubs, ex = K.publications(), K.excluded()
    path = HERE + '/union-identity-%s.jsonl' % want
    with open(path, 'w') as out:
        for t in sorted(os.listdir(D + 'gold/gold-v3-combined-cut/view-final')):
            if set_of(t, sets) != want:
                continue
            progs = [('pinned', K.pinned(t))]
            if t in pubs:
                for c in pubs[t][1]['cases']:
                    if c['case'].replace('$', '').replace(' ', '+') not in ex[t]:
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
    sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    open(path + '.sha256', 'w').write('%s  %s\n' % (sha, os.path.basename(path)))
    print(want, sha)


if __name__ == '__main__':
    main()
