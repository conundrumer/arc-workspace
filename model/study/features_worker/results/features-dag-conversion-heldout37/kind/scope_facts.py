"""Scope facts: one definition used on gold scopes and on a live search's scopes. Every fact is a function of the set S, with no order of S and no order of a form's text.

A form is a dict: i (a number that names the form; its value means no order), kind, depth, parents (the numbers of the forms it reads), head, key, cols (set of column types of its relations).

Facts of a scope S, a set of forms:

  kinds       counts of the kinds in S: RULE, DET, INIT, each capped at 2, RIGID_DET capped at 1
  leaves      the same counts over the leaves of S, the forms of S that no form of S reads, with RIGID_DET counted as DET
  leaf_kinds  the set of kinds of the leaves of S, sorted and joined with `+`, or `none` for an empty S
  leaf_heads  the set of heads of the leaves of S that are not a RULE: an INIT's pattern name, a DET's proposer name, `det-atoms` for a DET with a body, `rigid` for a RIGID_DET. Sorted and joined with `+`; `none` where no leaf has a head.
              Names outside the fit's HEADS list become `other` at the fit.
  leaf_cols   the column kinds over the leaves of S: P where a leaf has a Position column, C where a leaf has a Color column, in the order PC; `-` where S has leaves and none has either; `none` for an empty S
  key         1 where a form of S has a key group
  ident       1 where a form of S has an Ident column
  stage       the greatest depth in S, capped at 6. Depth is Pool.take's: 1 + the greatest depth of the forms read, 1 with none, 0 for the empty scope.
  size        forms in S in buckets: 0, 1, 2, 3-4, 5-8, 9-16, 17+

The facts `last`, `head` and `cols` of the earlier definition read the last form of S in the pool's order. They are gone, and so is any fact of a place in S.
"""
import re

FACTS = ('kinds', 'leaves', 'leaf_kinds', 'leaf_heads', 'leaf_cols', 'key', 'ident', 'stage', 'size')
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
    """The head name of a parsed form: see the module text. A RULE has no head name here."""
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
    """The forms of one gold program, without OUT, and the kinds of forms. types maps a form's line number to its set of column types. A form has `name`, its head name, for the form DAG."""
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
        forms.append(dict(i=i, name=h, kind=kind, head=head, key=key, cols=set(types.get(n, ())), parents=parents, depth=1 + max((forms[p]['depth'] for p in parents), default=0)))
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


def descendants(forms, i):
    """The numbers of the forms that read form i, directly or not."""
    got, todo = set(), [i]
    while todo:
        f = todo.pop()
        for g in forms:
            if f in g['parents'] and g['i'] not in got:
                got.add(g['i'])
                todo.append(g['i'])
    return got


def non_descendants(forms, i):
    """The forms that form i could read: all but itself and its descendants."""
    return [g['i'] for g in forms if g['i'] != i and g['i'] not in descendants(forms, i)]


CAP_R = 2
KEYS = ('RULE', 'DET', 'INIT')


def facts(S):
    """The facts of S, a list of form dicts. S holds each form with the forms that it reads; a form that it reads and S lacks counts as unread by S's members only."""
    ids = {f['i'] for f in S}
    read = set()
    for f in S:
        read |= set(f['parents']) & ids
    n = dict.fromkeys(('RULE', 'DET', 'INIT', 'RIGID_DET'), 0)
    l = dict.fromkeys(KEYS, 0)
    key, ident, depth = 0, 0, 0
    leaf = [f for f in S if f['i'] not in read]
    for f in S:
        k = f['kind']
        if k in n:
            n[k] += 1
        if f['i'] not in read:
            q = 'DET' if k == 'RIGID_DET' else k
            if q in l:
                l[q] += 1
        key |= int(f['key'])
        ident |= int('Ident' in f['cols'])
        depth = max(depth, f['depth'])
    heads = sorted({f['head'] for f in leaf if f['kind'] != 'RULE' and f['head'] is not None})
    colset = set().union(*[f['cols'] for f in leaf]) if leaf else set()
    cols = ('P' if 'Position' in colset else '') + ('C' if 'Color' in colset else '') or '-'
    size = len(S)
    sb = next(name for lim, name in ((0, '0'), (1, '1'), (2, '2'), (4, '3-4'), (8, '5-8'), (16, '9-16'), (1 << 40, '17+')) if size <= lim)
    return dict(kinds='R%dD%dI%dX%d' % (min(n['RULE'], 2), min(n['DET'], 2), min(n['INIT'], 2), min(n['RIGID_DET'], 1)), leaves='R%dD%dI%d' % tuple(min(l[k], 2) for k in KEYS),
                leaf_kinds='+'.join(sorted({f['kind'] for f in leaf})) if leaf else 'none', leaf_heads='+'.join(heads) or 'none', leaf_cols=cols if leaf else 'none',
                key=key, ident=ident, stage=min(depth, 6), size=sb)
