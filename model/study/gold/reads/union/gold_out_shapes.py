"""The shapes of the last steps of the pinned programs: each form that a task's OUT line reads, abstracted. Writes out-shapes.jsonl (one line per task) in work/lm/data-study/gold/gold-union and prints the summary.

  python3 gold_out_shapes.py [LAYER]

- LAYER 0 (the default) takes the forms that the OUT line reads. LAYER k takes the forms that the forms of layer k-1 read, and writes out-shapes-k.jsonl.

- Programs: gold-export/flat/<task>.arclog.
- A form's shape: its kind (and component, for an INIT or a DET without a body); for an OR body, the count of top-level branches; whether the body holds NOT; whether a branch of the OR reads `input` and, outside its NOT parts, no form of the program (a default branch); the count of relation atoms; and the sorted kinds of what it reads: `input`, `ex_output`, `output`, a lib relation (`lib`), or a form of the program by kind (`RULE`, `DET`, or `INIT:<component>.<output>`).
- `coarse` is the shape without the atom count.
- A task is covered by a set of shapes when each form its OUT line reads has a shape in the set.
"""
import collections, json, os, re, sys

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FLAT = D + 'gold/gold-export/flat/'
OUT = D + 'gold/gold-union/'
HEAD = re.compile(r'\((\w+) &([A-Za-z_]\w*)')
READ = re.compile(r'\((&[A-Za-z_]\w*(?:\.\w+)*|[a-z_]\w*) ')
KEYWORDS = {'key', 'member', 'node', 'cell', 'source', 'score', 'probe', 'equivalent', 'secondary_score', 'before', 'dir', 'parts', 'side', 'gap'}


def top(s):
    out, d, start = [], 0, None
    for i, c in enumerate(s):
        if c == '(':
            if d == 1:
                start = i
            d += 1
        elif c == ')':
            d -= 1
            if d == 1:
                out.append(s[start:i + 1])
    return out


def or_branches(body):
    """The top-level branches of the first OR in the body, as texts."""
    i = body.find('(OR ')
    if i < 0:
        return []
    d, j = 0, i
    for j in range(i, len(body)):
        d += body[j] == '('
        d -= body[j] == ')'
        if d == 0:
            break
    return top(body[i:j + 1])


def positive(branch):
    """The branch without its NOT parts."""
    while (i := branch.find('(NOT ')) >= 0:
        d = 0
        for j in range(i, len(branch)):
            d += branch[j] == '('
            d -= branch[j] == ')'
            if d == 0:
                break
        branch = branch[:i] + branch[j + 1:]
    return branch


def shape(line, kinds):
    m = HEAD.match(line)
    kind = m[1]
    body = line[m.end():]
    comp = body.split()[0].rstrip(')') if kind == 'INIT' or (kind == 'DET' and not body.lstrip().startswith('(')) else None
    reads = []
    for x in READ.findall(body):
        if x.startswith('&'):
            label, _, out = x[1:].partition('.')
            k, c = kinds.get(label, ('?', None))
            reads.append('INIT:%s.%s' % (c, out.split('.')[0]) if k == 'INIT' else k)
        elif x in ('input', 'ex_output', 'output', 'ex_input'):
            reads.append(x)
        elif x not in KEYWORDS:
            reads.append('lib')
    branches = or_branches(body)
    default = any('(input ' in p and '&' not in p for p in map(positive, branches))
    atoms = len(re.findall(r'\((?:&\w+(?:\.\w+)*|[a-z_]\w*) \(:', body))
    coarse = dict(kind=kind, component=comp, or_branches=len(branches), has_not='(NOT ' in body, default_input=default, reads=sorted(set(reads)))
    return dict(coarse, atoms=atoms), coarse


def main():
    layer = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rows = []
    for f in sorted(os.listdir(FLAT)):
        ls = [x for x in open(FLAT + f).read().splitlines() if x.strip()]
        kinds = {m[2]: (m[1], x[m.end():].split()[0] if m[1] == 'INIT' else None) for x in ls if (m := HEAD.match(x))}
        by_label = {HEAD.match(x)[2]: x for x in ls if HEAD.match(x)}
        out = next((x for x in ls if x.startswith('(OUT')), '')
        goal = [g for g in dict.fromkeys(re.findall(r'&([A-Za-z_]\w*)', out)) if g in by_label]
        for _ in range(layer):
            goal = [g for g in dict.fromkeys(re.findall(r'&([A-Za-z_]\w*)', ' '.join(by_label[g][HEAD.match(by_label[g]).end():] for g in goal))) if g in by_label]
        shapes = [shape(by_label[g], kinds) for g in goal]
        rows.append(dict(task=f[:-7], shapes=[s for s, _ in shapes], coarse=[c for _, c in shapes]))
    with open(OUT + ('out-shapes-%d.jsonl' % layer if layer else 'out-shapes.jsonl'), 'w') as fo:
        fo.writelines(json.dumps(r) + '\n' for r in rows)
    for field in ('shapes', 'coarse'):
        key = lambda s: json.dumps(s, sort_keys=True)
        count = collections.Counter(key(s) for r in rows for s in r[field])
        tasks = collections.Counter()
        for r in rows:
            for k in {key(s) for s in r[field]}:
                tasks[k] += 1
        ranked = [k for k, _ in tasks.most_common()]
        print('%s: %d tasks (%d with no form), %d forms, %d distinct, %d used by one task' % (field, len(rows), sum(not r[field] for r in rows), sum(count.values()), len(count), sum(v == 1 for v in tasks.values())))
        for n in (5, 10, 20, 50, 100):
            top_n = set(ranked[:n])
            print('  top %d: %.0f%% of tasks covered' % (n, 100 * sum(all(key(s) in top_n for s in r[field]) for r in rows) / len(rows)))
        for k in ranked[:12]:
            print('   %4d tasks  %s' % (tasks[k], k))


if __name__ == '__main__':
    main()
