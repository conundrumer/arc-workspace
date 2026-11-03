# Written by gold_shapecut_make.py.
"""The stage's candidates, and the shapes of gold_shapecut_shapes.py as cuts of a form: key-project, split-groups, flat-copy, if-to-or, empty-port, and or-copy (a relation that a later branch of a whole-body OR reads again, through a RULE that copies it). Nothing here runs the engine.

  all_candidates(lines, i) gives Cut(shape, forms), as gold_orcut_cuts.candidates does.
"""
import re

from gold_chain import parse, show
from gold_orcut_cuts import Cut, Fresh, candidates
import gold_shapecut_shapes as X


def named(forms, ls):
    """forms with each name that shape_trials writes changed to a name that ls does not hold."""
    fresh, out, m = Fresh(ls), [], {}
    text = '\n'.join(forms)
    for n in sorted(set(re.findall(r'&(?:sg|fc|kp|oc)\d+', text))):
        m[n] = fresh()
        ls = ls + [m[n]]
        fresh = Fresh(ls)
    for n, v in m.items():
        text = re.sub(re.escape(n) + r'(?!\d)', v, text)
    return text.split('\n')


def or_copy(text):
    p = parse(text)
    if len(p) != 3 or not isinstance(p[2], list) or p[2][0] != 'OR':
        return None
    bs = p[2][1:]
    rels = {a[0] for a in bs[0] if isinstance(a, list) and isinstance(a[0], str) and not a[0].startswith('&') and a[0][0].islower()}
    for k, b in enumerate(bs[1:], 1):
        for j, a in enumerate(b):
            if isinstance(a, list) and a[0] in rels and all(len(s) == 2 and isinstance(s[1], str) for s in a[1:]):
                cols = [s[0] for s in a[1:]]
                first = next(x for x in bs[0] if x[0] == a[0])
                if {s[0] for s in first[1:]} != set(cols):
                    continue
                helper = '(RULE &oc1 (%s %s))' % (a[0], ' '.join('(%s *L%d)' % (c, n) for n, c in enumerate(cols)))
                b[j] = ['&oc1'] + [[':L%d' % n, s[1]] for n, s in enumerate(a[1:])]
                return [helper, show(p)]
    return None


def all_candidates(ls, i):
    out = list(candidates(ls, i))
    x = ls[i]
    if not x.startswith('(OUT'):
        got = []
        try:
            if x.startswith('(INIT') and '(OR ' in x:
                k = X.key_project(x)
                got.append(('key-project', k))
                if k:
                    got.append(('key-project+flat-copy', k[:1] + (X.flat_copy(k[1]) or k[1:])))
            if x.startswith(('(RULE', '(DET')) and 'ONE' not in x:
                got.append(('split-groups', X.split_groups(x, X.later_columns(ls, i, x.split()[1]))))
                got.append(('or-copy', or_copy(x)))
            if x.startswith('(INIT'):
                got.append(('flat-copy', X.flat_copy(x)))
                got.append(('empty-port', X.empty_port(x)))
            if '(IF ' in x:
                got.append(('if-to-or', X.if_to_or(x)))
        except (IndexError, ValueError, StopIteration, TypeError, KeyError, AttributeError):
            pass
        for shape, forms in got:
            if forms:
                out.append(Cut(shape, named(forms, ls)))
    return out
