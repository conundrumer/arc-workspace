"""Scope facts: one definition used on gold scopes and on a live search's scopes.

A form is a dict: i (order number), kind, depth, parents (order numbers of the forms it reads), head, key, cols (set of column types of its relations).

Facts of a scope S, a set of forms, in the order Pool.scope gives it, by depth and then order number:

  last     the kind of the last form of S, or none where S is empty
  kinds    counts of the kinds in S: RULE, DET, INIT, each capped at 2, RIGID_DET capped at 1
  leaves   the same counts over the forms of S that no form of S reads, with RIGID_DET counted as DET
  head     the head of the last form of S that isn't a RULE: an INIT's pattern name, a DET's proposer name, `det-atoms` for a DET with a body, `rigid` for a RIGID_DET. Names outside the fit's HEADS list are `other`, and `none` where S has no such form.
  cols     for the last form of S: P where it has a Position column, C where it has a Color column, PC for both, `-` for neither, none where S is empty
  key      1 where a form of S has a key group
  ident    1 where a form of S has an Ident column
  stage    the greatest depth in S, capped at 6. Depth is Pool.take's: 1 + the greatest depth of the forms read, 1 with none, 0 for the empty scope.
  size     forms in S in buckets: 0, 1, 2, 3-4, 5-8, 9-16, 17+
"""
import re

FACTS = ('last', 'kinds', 'leaves', 'head', 'cols', 'key', 'ident', 'stage', 'size')
TOK = re.compile(r'[()]|[^\s()]+')
NAME = re.compile(r'&[rf]\d+')


def sexp(text):
    stack, top = [], []
    cur = top
    for t in TOK.findall(text):
        if t == '(':
            n = []
            cur.append(n)
            stack.append(cur)
            cur = n
        elif t == ')':
            cur = stack.pop()
        else:
            cur.append(t)
    return top[0]


def head_of(x):
    """The head name of a parsed form: see the module text. A RULE has no head name here: its head is read through cols."""
    kind = x[0]
    if kind == 'INIT':
        return x[2]
    if kind == 'RIGID_DET':
        return 'rigid'
    if kind == 'DET':
        names = [y for y in x[2:] if isinstance(y, str)]
        return names[0] if names else 'det-atoms'
    return None


def has_key(x):
    return any(isinstance(y, list) and y and y[0] == 'key' for y in x[2:])


def parse_form(line):
    """(kind, head, key) of one form's text."""
    x = sexp(line)
    return x[0], head_of(x), has_key(x)


def gold_forms(sexp_text, types):
    """The forms of one gold program, without OUT, and the kinds of forms. types maps a form's line number to its set of column types."""
    lines = [l for l in sexp_text.strip().split('\n')]
    forms, seen = [], {}
    for n, line in enumerate(lines):
        if line.startswith('(OUT'):
            continue
        names = NAME.findall(line)
        h = names[0]
        kind, head, key = parse_form(line)
        parents = sorted({seen[m] for m in names[1:] if m in seen and m != h})
        i = len(forms)
        forms.append(dict(i=i, kind=kind, head=head, key=key, cols=set(types.get(n, ())), parents=parents, depth=1 + max((forms[p]['depth'] for p in parents), default=0)))
        seen[h] = i
    return forms


def closure(forms, start):
    """The forms start with their ancestors, as order numbers."""
    got, todo = set(), list(start)
    while todo:
        f = todo.pop()
        if f not in got:
            got.add(f)
            todo += forms[f]['parents']
    return got


CAP_R = 2
KEYS = ('RULE', 'DET', 'INIT')


def facts(S):
    """The facts of S, a list of form dicts."""
    S = sorted(S, key=lambda f: (f['depth'], f['i']))
    read = set()
    ids = {f['i'] for f in S}
    for f in S:
        read |= set(f['parents']) & ids
    n = dict.fromkeys(('RULE', 'DET', 'INIT', 'RIGID_DET'), 0)
    l = dict.fromkeys(KEYS, 0)
    head, key, ident, depth = 'none', 0, 0, 0
    for f in S:
        k = f['kind']
        if k in n:
            n[k] += 1
        if f['i'] not in read:
            q = 'DET' if k == 'RIGID_DET' else k
            if q in l:
                l[q] += 1
        if k != 'RULE' and f['head'] is not None:
            head = f['head']
        key |= int(f['key'])
        ident |= int('Ident' in f['cols'])
        depth = max(depth, f['depth'])
    if S:
        c = S[-1]['cols']
        cols = ('P' if 'Position' in c else '') + ('C' if 'Color' in c else '') or '-'
    else:
        cols = 'none'
    size = len(S)
    sb = next(name for lim, name in ((0, '0'), (1, '1'), (2, '2'), (4, '3-4'), (8, '5-8'), (16, '9-16'), (1 << 40, '17+')) if size <= lim)
    return dict(last=S[-1]['kind'] if S else 'none', kinds='R%dD%dI%dX%d' % (min(n['RULE'], 2), min(n['DET'], 2), min(n['INIT'], 2), min(n['RIGID_DET'], 1)),
                leaves='R%dD%dI%d' % tuple(min(l[k], 2) for k in KEYS), head=head, cols=cols, key=key, ident=ident, stage=min(depth, 6), size=sb)
