"""Stages of a no-OR RULE clause, in gold's atom order: each stage reads the stage before it and only the columns that later atoms or readers need.

  gold_chain.py stages CHOSEN.json OUT.jsonl     one row per candidate stage, with its context
  gold_chain.py best CHOSEN.json STAGES.jsonl CENSUS.jsonl OUT.json    the partition with the least worst stage, as whole programs
"""
import json, re, sys

VAR = re.compile(r'^[*^]?([A-Z][A-Za-z0-9_]*)$')
KEYWORDS = {'NOT', 'OR', 'ALL', 'RULE', 'INIT', 'DET', 'OUT'}


def parse(s):
    toks = re.findall(r'\(|\)|[^\s()]+', s)
    def read(i):
        if toks[i] == '(':
            out, i = [], i + 1
            while toks[i] != ')':
                x, i = read(i)
                out.append(x)
            return out, i + 1
        return toks[i], i + 1
    return read(0)[0]


def show(x):
    return '(' + ' '.join(show(y) for y in x) + ')' if isinstance(x, list) else x


def flat(x):
    return [z for y in x for z in flat(y)] if isinstance(x, list) else [x]


def names(atom):
    """The variables of an atom, and those it binds."""
    used, bound = [], []
    for t in flat(atom):
        m = VAR.match(t)
        if m and m[1] not in KEYWORDS:
            used.append(m[1])
            if t[0] == '*':
                bound.append(m[1])
    return used, bound


def reads(lines, head):
    """The column labels that the forms after the clause read of head."""
    got = set()
    def walk(x):
        if isinstance(x, list):
            if x and x[0] == head:
                for y in x[1:]:
                    if isinstance(y, list) and str(y[0]).startswith(':'):
                        got.add(y[0][1:])
                    elif isinstance(y, str) and VAR.match(y):
                        got.add(VAR.match(y)[1])
            for y in x:
                walk(y)
    for l in lines:
        walk(parse(l))
    return got


class Clause:
    def __init__(self, row):
        self.lines = row['gold_sexp'].split('\n')
        self.line = row['line']
        c = parse(self.lines[self.line])
        self.head, self.atoms = c[1], c[2:]
        self.keep = reads(self.lines[self.line + 1:], self.head)
        self.task = row['task']

    def stage(self, s, e, name, prev):
        """The form of atoms s to e, reading the form prev that holds atoms before s."""
        bound = [v for a in self.atoms[:s] for v in names(a)[1]]
        later = {v for a in self.atoms[s:] for v in names(a)[0]} | self.keep
        read = [v for v in dict.fromkeys(bound) if v in later]
        first = '(%s %s)' % (prev, ' '.join('(:%s *%s)' % (v, v) for v in read)) if s else None
        return '(RULE %s %s)' % (name, ' '.join(([first] if first else []) + [show(a) for a in self.atoms[s:e]]))

    def chain(self, cuts, prefix='&w'):
        """The forms of the partition at cuts, ascending, ending at len(atoms). prefix keeps the helper names of two clauses apart."""
        forms, s = [], 0
        for k, e in enumerate(cuts):
            name = self.head if e == len(self.atoms) else '%s%d' % (prefix, k)
            forms.append(self.stage(s, e, name, '%s%d' % (prefix, k - 1)))
            s = e
        return forms


def main():
    if sys.argv[1] == 'stages':
        with open(sys.argv[3], 'w') as f:
            for row in json.load(open(sys.argv[2])):
                c = Clause(row)
                n = len(c.atoms)
                print(row['task'], n, sorted(c.keep), flush=True)
                for s in range(n):
                    for e in range(s + 1, n + 1):
                        context = c.lines[:c.line] + ([c.stage(0, s, '&w0', None)] if s else [])
                        f.write(json.dumps(dict(task=c.task, key=[s, e], context=context, target=c.stage(s, e, c.head if e == n else '&w1', '&w0'))) + '\n')
    else:
        chosen, stages, census, out = sys.argv[2:6]
        cost = {}
        for l in open(census):
            r = json.loads(l)
            cost[r['task'], tuple(r['key'])] = r.get('total') if not r.get('bad') and r.get('dead') is None and r.get('total') is not None else float('inf')
        res = []
        for row in json.load(open(chosen)):
            c = Clause(row)
            n = len(c.atoms)
            best = {0: (0, 0, [])}  # end -> (worst, sum, cuts)
            for e in range(1, n + 1):
                best[e] = min(((max(best[s][0], cost.get((c.task, (s, e)), float('inf'))), best[s][1] + cost.get((c.task, (s, e)), float('inf')), best[s][2] + [e]) for s in range(e)), key=lambda x: x[:2])
            worst, total, cuts = best[n]
            forms = c.chain(cuts)
            res.append(dict(arm=c.task + '-chain', task=c.task, case=row['case'], line=c.line, n=len(forms), atoms=n, cuts=cuts, predicted=worst, gold_bits=row['bits'],
                            gold_sexp='\n'.join(c.lines[:c.line] + forms + c.lines[c.line + 1:])))
            print(c.task, n, cuts, round(worst, 1), round(total, 1), row['bits'], flush=True)
        json.dump(res, open(out, 'w'))


if __name__ == '__main__':
    main()
