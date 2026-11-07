"""The union forms under the target-form canonical text, with counts. Prints the counts and writes canonical-SET.json in work/lm/data-study/gold/gold-union.

  .venv/bin/python gold_union_canonical.py SET [SET ...]

The canonical text of a form:
- The form's own label is dropped.
- A reference is written as the state table it reads, `&T<i>`, with the output name where it reads an INIT output (`&T0.component`).
- `*` is dropped and `^` is kept.
- A column label of a derived relation is written as the field it came from. From union-keys-SET.jsonl, in each case's text, a derived column `V` of a RULE or DET takes the field of the first atom that binds `*V`, followed through derived relations to a lib relation, a given relation or an INIT output. Each case line with a union key is written this way, so the counts are over case lines, deduplicated per task.
- Variables are renamed `V<i>`.
- Body atoms, OR branches, the atoms of a branch or a NOT, and the atoms of an INIT port after its bindings are a set: they are written in sorted order.
- In each list of conjuncts, each NOT and ALL is placed after the conjuncts that bind: all of them follow the other conjuncts, each part in sorted order.
- Tables and variables are numbered by first appearance in the sorted text. The sort uses the text with every table written `&T` and every variable `V`, so two forms that differ only in names sort alike. This is a fixed order, not a full canonical labelling: two forms with the same join structure can, where the sort ties, number their tables or variables differently, so the count of distinct canonical texts is an upper bound.

Counts: forms (union identities per task), distinct written texts (the union's text with labels), distinct texts with only the own label and the reference names normalised (gold_union_texts.py's canonical), distinct canonical texts, and per form kind; tokens, atoms and the vocabulary on the canonical texts.
"""
import collections, json, re, sys
from gold_union_texts import BASE, CMP, OUT, TOKEN, canonical as simple, rows
import study_zst as Z  # on the path since gold_union_texts is imported

VAR = re.compile(r'\^?[A-Z]\w*')
WORDS = {'RULE', 'DET', 'INIT', 'CHOOSE', 'OR', 'NOT', 'OUT'}


def parse(text):
    toks = TOKEN.findall(text)
    stack = [[]]
    for x in toks:
        if x == '(':
            stack.append([])
        elif x == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(x)
    return stack[0][0]


def write(t):
    return '(' + ' '.join(write(x) if isinstance(x, list) else x for x in t) + ')' if isinstance(t, list) else t


def rename(t, comp):
    """References to &T, column labels to their field, variables to V, with * dropped."""
    if isinstance(t, list):
        return [rename(x, comp) for x in t]
    if t.startswith('&'):
        _, _, out = t[1:].partition('.')
        return '&T' + ('.' + out if out else '')
    if t.startswith(':'):
        return t
    if t.startswith('*'):
        return 'V'
    if t.startswith('^'):
        return '^V'
    if t != comp and t not in WORDS and VAR.fullmatch(t):
        return 'V'
    return t


def binding_last(xs):
    """The conjuncts in their sorted order, with each NOT and ALL after the conjuncts that bind."""
    late = lambda x: isinstance(x, list) and x and x[0] in ('NOT', 'ALL')  # noqa: E731
    return [x for x in xs if not late(x)] + [x for x in xs if late(x)]


def order(t, shape):
    """t with its set parts sorted by the text of `shape`, the same tree with names replaced."""
    if not isinstance(t, list) or not t:
        return t
    head = t[0] if isinstance(t[0], str) else None
    pairs = [(order(a, b), b) for a, b in zip(t, shape)]
    key = lambda p: write(p[1])  # noqa: E731
    if head in ('OR',):
        return [t[0]] + [x for x, _ in sorted(pairs[1:], key=key)]
    if head == 'NOT':
        return [t[0]] + [x for x, _ in sorted(pairs[1:], key=key)]
    if head is None:  # a branch: a list of atoms
        return binding_last([x for x, _ in sorted(pairs, key=key)])
    if head and re.fullmatch(r'[a-z_]\w*', head) and len(t) > 1 and isinstance(t[1], list) and t[1] and isinstance(t[1][0], list):
        return [t[0], pairs[1][0]] + binding_last([x for x, _ in sorted(pairs[2:], key=key)])  # an INIT port: bindings, then atoms
    return [x for x, _ in pairs]


def is_atom(t):
    return isinstance(t, list) and len(t) > 1 and isinstance(t[0], str) and all(isinstance(x, list) and x and isinstance(x[0], str) and x[0].startswith(':') for x in t[1:])


def atoms(t, positive=True):
    if is_atom(t):
        yield t, positive
    elif isinstance(t, list):
        for x in t:
            yield from atoms(x, positive and not (isinstance(t, list) and t and t[0] == 'NOT'))


def with_fields(lines):
    """The case's lines with each derived column label written as the field it came from."""
    origin, out = {}, []
    for line in lines:
        t = parse(line)
        if t[0] in ('RULE', 'DET') and len(t) > 2 and isinstance(t[1], str):
            own = t[1][1:]
            for a, pos in atoms(t[2:]):
                if a[0].startswith('&') and '.' not in a[0]:
                    m = origin.get(a[0][1:], {})
                    for x in a[1:]:
                        x[0] = m.get(x[0], x[0])
                if pos:
                    for x in a[1:]:
                        if len(x) == 2 and isinstance(x[1], str) and x[1].startswith('*'):
                            origin.setdefault(own, {}).setdefault(':' + x[1][1:], x[0])
        else:
            for a, _ in atoms(t[2:] if len(t) > 2 else []):
                if a[0].startswith('&') and '.' not in a[0]:
                    m = origin.get(a[0][1:], {})
                    for x in a[1:]:
                        x[0] = m.get(x[0], x[0])
        out.append(write(t))
    return out


def canonical(text):
    t = parse(text)
    kind = t[0]
    comp = t[2] if len(t) > 2 and isinstance(t[2], str) else None
    body = [kind] + ([comp] if comp else []) + t[3 if comp else 2:]
    original = body
    shape = rename(body, comp)
    head = len(body[:2]) if comp else 1
    rest = sorted(zip(original[head:], shape[head:]), key=lambda p: write(p[1]))
    ordered = original[:head] + binding_last([order(a, b) for a, b in rest])
    tables, variables = {}, {}

    def number(x):
        if isinstance(x, list):
            return [number(y) for y in x]
        if x.startswith('&'):
            label, _, out = x[1:].partition('.')
            return '&T%d%s' % (tables.setdefault(label, len(tables)), '.' + out if out else '')
        if x.startswith(':'):
            return x
        if x != comp and x not in WORDS and VAR.fullmatch(x.lstrip('*')):
            hat = '^' if x.startswith('^') else ''
            return '%sV%d' % (hat, variables.setdefault(x.lstrip('*^'), len(variables)))
        return x
    return write(number(ordered))


def main():
    for s in sys.argv[1:]:
        forms = []
        for r in rows(s):
            seen = set()
            for t in r.get('tables') or []:
                for f in t['forms']:
                    if f['ident'] not in seen:
                        seen.add(f['ident'])
                        forms.append((r['task'], t['kind'], f['text']))
        per_kind = collections.defaultdict(lambda: [0, set(), set()])
        for task, kind, text in forms:
            per_kind[kind][0] += 1
            per_kind[kind][1].add(simple(text))
        lines = set()
        for l in Z.open_text(OUT + 'union-keys-%s.jsonl' % s):
            c = json.loads(l)
            ls = [x for x in c['text'].splitlines() if x.strip() and not x.startswith('(OUT')]
            if len(ls) != len(c['keys']):
                continue
            for x, k in zip(with_fields(ls), c['keys']):
                if k is not None:
                    lines.add((c['task'], x.split()[0][1:], canonical(x)))
        canon = [c for _, _, c in lines]
        for task, kind, c in lines:
            per_kind[kind][2].add(c)
        groups = collections.Counter(canon)
        tasks = collections.defaultdict(set)
        for task, _, c in lines:
            tasks[c].add(task)
        voc = {k: collections.Counter() for k in ('relations', 'base', 'components', 'ports', 'references', 'labels', 'constants', 'operators')}
        ntok, natoms = [], []
        for c in canon:
            toks = TOKEN.findall(c)
            ntok.append(len(toks))
            n = 0
            for i, x in enumerate(toks):
                prev, nxt = toks[i - 1] if i else '', toks[i + 1] if i + 1 < len(toks) else ''
                after = toks[i + 2] if i + 2 < len(toks) else ''
                if prev == '(' and x.startswith('&') and nxt == '(' and after.startswith(':'):
                    n += 1
                    voc['references'][x] += 1
                elif prev == '(' and x in CMP:
                    n += 1
                    voc['operators'][x] += 1
                elif prev == '(' and re.fullmatch(r'[a-z_]\w*', x) and nxt == '(' and after.startswith(':'):
                    n += 1
                    voc['base' if x in BASE else 'relations'][x] += 1
                elif prev == '(' and re.fullmatch(r'[a-z_]\w*', x) and nxt == '(':
                    voc['ports'][x] += 1
                elif x in ('RULE', 'DET', 'INIT', 'CHOOSE', 'OR', 'NOT'):
                    voc['operators'][x] += 1
                elif i == 2 and re.fullmatch(r'[A-Z][a-z]\w*', x) and not re.fullmatch(r'V\d+', x):
                    voc['components'][x] += 1
                elif x.startswith(':'):
                    voc['labels'][x] += 1
                elif re.fullmatch(r'-?\d+', x):
                    voc['constants'][x] += 1
            natoms.append(n)

        def q(xs):
            xs = sorted(xs)
            at = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
            return dict(p25=at(.25), median=at(.5), p75=at(.75), p90=at(.9), max=xs[-1], mean=round(sum(xs) / len(xs), 2))
        out = dict(set=s, forms=len(forms), task_canonical=len(lines), written_texts=len({x for _, _, x in forms}), simple_canonical=len({simple(x) for _, _, x in forms}), canonical=len(groups),
                   forms_in_shared_canonical=sum(n for n in groups.values() if n >= 2), canonical_with_2_forms=sum(n >= 2 for n in groups.values()),
                   canonical_in_2_tasks=sum(len(v) >= 2 for v in tasks.values()), forms_whose_canonical_is_in_2_tasks=sum(len(tasks[c]) >= 2 for c in canon),
                   per_kind={k: dict(forms=v[0], simple_canonical=len(v[1]), canonical=len(v[2])) for k, v in sorted(per_kind.items())},
                   tokens=q(ntok), atoms=q(natoms),
                   vocabulary={k: dict(distinct=len(v), top=v.most_common(25)) for k, v in voc.items()},
                   most_shared=[[c[:200], n, len(tasks[c])] for c, n in groups.most_common(15)])
        json.dump(out, open(OUT + 'canonical-%s.json' % s, 'w'), indent=1)
        print(json.dumps({k: v for k, v in out.items() if k not in ('vocabulary', 'most_shared')}))
        print(' ', {k: v['distinct'] for k, v in out['vocabulary'].items()})


if __name__ == '__main__':
    main()
