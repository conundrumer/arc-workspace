"""The union identities as text: counts for a model that writes a form as text. Prints the counts and writes texts-SET.json in work/lm/data-study/gold/gold-union.

  python3 gold_union_texts.py SET [SET ...]

- A form is one union identity of a task: a `forms` entry of union-SET.jsonl (with its addendum), whose `text` is the union's normal form.
- Canonical text: the form's own label becomes `&H`, and each other label of the program becomes `&R<i>`, i by the order of first reference in the form, keeping an output suffix such as `.cell`. Two forms of different tasks with the same canonical text are a repeat.
- Tokens: a simple split into parentheses, `&` references, `:` column labels, `*` and `^` markers with their variable, operators, names, and constants.
- Atoms: each list whose head is a relation, a reference or a comparison, and whose arguments are column lists or values.
- Vocabulary, with counts over forms:
  - relations: lowercase names in atom position, base relations (`input`, `ex_output`, `output`, `ex_input`) apart;
  - components: a capitalized name right after the form's own label;
  - ports: lowercase names that head a list of lists inside an INIT (such as `key`, `member`);
  - references: by position `&R<i>`, with the output suffix;
  - column labels, markers (`*`, `^`) and constants (numbers).
"""
import collections, json, re, sys

OUT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
TOKEN = re.compile(r'\(|\)|&[A-Za-z_]\w*(?:\.\w+)*|:\w+|[*^]\w+|>=|<=|!=|=|<|>|[A-Za-z_]\w*|-?\d+|\S')
BASE = {'input', 'ex_output', 'output', 'ex_input'}
OPS = {'RULE', 'DET', 'INIT', 'CHOOSE', 'OR', 'NOT', 'OUT'}
CMP = {'=', '>=', '<=', '!=', '<', '>'}


def rows(s):
    got = {}
    for p in (OUT + 'union-%s.jsonl' % s, OUT + 'union-%s-addendum.jsonl' % s):
        try:
            for l in open(p):
                r = json.loads(l)
                got[r['task']] = r
        except FileNotFoundError:
            pass
    return got.values()


def canonical(text):
    toks = TOKEN.findall(text)
    own = toks[2].lstrip('&') if len(toks) > 2 else ''
    pos = {}

    def ref(m):
        label, _, out = m[1].partition('.')
        if label == own and not out:
            return '&H'
        i = pos.setdefault(label, len(pos))
        return '&R%d%s' % (i, '.' + out if out else '')
    return re.sub(r'&([A-Za-z_]\w*(?:\.\w+)*)', ref, text)


def main():
    for s in sys.argv[1:]:
        forms, seen = [], set()
        for r in rows(s):
            for t in r.get('tables') or []:
                for f in t['forms']:
                    if (r['task'], f['ident']) not in seen:
                        seen.add((r['task'], f['ident']))
                        forms.append((r['task'], f['text']))
        voc = {k: collections.Counter() for k in ('relations', 'base', 'components', 'ports', 'references', 'labels', 'markers', 'constants', 'operators')}
        atoms, ntok, canon_tasks = [], [], collections.defaultdict(set)
        for task, text in forms:
            c = canonical(text)
            canon_tasks[c].add(task)
            toks = TOKEN.findall(c)
            ntok.append(len(toks))
            n = 0
            for i, x in enumerate(toks):
                prev, nxt = toks[i - 1] if i else '', toks[i + 1] if i + 1 < len(toks) else ''
                after = toks[i + 2] if i + 2 < len(toks) else ''
                if prev == '(' and (x.startswith('&R') or x == '&H') and nxt == '(' and after.startswith(':'):
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
                elif x in OPS:
                    voc['operators'][x] += 1
                elif re.fullmatch(r'[A-Z]\w*', x) and i == 3:
                    voc['components'][x] += 1
                elif x.startswith(':'):
                    voc['labels'][x] += 1
                elif x[0] in '*^':
                    voc['markers'][x[0]] += 1
                elif re.fullmatch(r'-?\d+', x):
                    voc['constants'][x] += 1
            atoms.append(n)

        def q(xs):
            xs = sorted(xs)
            at = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
            return dict(p25=at(.25), median=at(.5), p75=at(.75), p90=at(.9), max=xs[-1], mean=round(sum(xs) / len(xs), 2))
        out = dict(set=s, forms=len(forms), canonical_texts=len(canon_tasks),
                   canonical_in_2_tasks=sum(len(v) >= 2 for v in canon_tasks.values()),
                   forms_whose_canonical_is_in_2_tasks=sum(len(canon_tasks[canonical(t)]) >= 2 for _, t in forms),
                   atoms=q(atoms), tokens=q(ntok),
                   vocabulary={k: dict(distinct=len(v), top=v.most_common(25)) for k, v in voc.items()},
                   most_repeated=[[c[:200], len(v)] for c, v in sorted(canon_tasks.items(), key=lambda x: -len(x[1]))[:15]])
        json.dump(out, open(OUT + 'texts-%s.json' % s, 'w'), indent=1)
        print(json.dumps({k: v for k, v in out.items() if k not in ('vocabulary', 'most_repeated')}))
        print(' ', {k: v['distinct'] for k, v in out['vocabulary'].items()})


if __name__ == '__main__':
    main()
