"""The compare of order_check.sh (plain python3, no engine): the rows of tool 2 v2 on a start text T and on T:a (the same forms and atoms in another valid order), both with DAG_START_READ=1.

  python3 gold_dagcut2_cmp.py DIR STEM...      reads DIR/row-<stem>-T.jsonl, DIR/row-<stem>-A.jsonl and the texts DIR/lines-<stem>-T.json, -A.json

Compared, with names and atom order scrubbed (as K/scratch/cmp_steps.py): the figures of the start text by form name, the steps (shape, rank, the step's bits and worst, committed, the new forms), the committed `after` (forms with no bits, worst, sum, and the bits of each form by its name), and `program`.
Verdict for a stem:
  PASS             everything equal
  PASS (named)     every difference is on a form that has an OR and a `=`, and each is named
  CHECK            a difference on a form without an OR and a `=` (a form that reads a form with an OR and a `=` is marked `reads`); look at it
"""
import json, re, sys
sys.path.insert(0, '.')
from gold_chain import parse, show
from gold_dag_orders import plain

TOL = 0.011


def last(path):
    rows = [l for l in open(path) if l.startswith('{"task"')]
    return json.loads(rows[-1]) if rows else None


def scrub(text):
    f = parse(text)
    if f[0] not in ('RULE', 'DET'):
        return text
    return f[0] + ' ' + ' '.join(sorted(re.sub(r'&(r|wc)\d+', '&N', show(plain(x))) for x in f[2:]))


def head(text):
    f = parse(text)
    return f[1] if len(f) > 1 and isinstance(f[1], str) else None


def residue(text):
    """Whether the form has an OR and a `=`."""
    return '(OR' in text and '(=' in text


def near(a, b):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= TOL)


def named(lines, bits):
    """{head name: (text, bits)} of the forms of a block over the text lines (the OUT line left out)."""
    body = [x for x in lines if not x.startswith('(OUT')]
    return {head(x): (x, b) for x, b in zip(body, bits)}


def figures(what, fa, fb, notes, bad):
    resid = {h for h, (x, _) in fa.items() if residue(x)}
    for h in sorted(set(fa) | set(fb), key=str):
        if h not in fa or h not in fb:
            bad.append('%s: form %s only in %s' % (what, h, 'T' if h in fa else 'A'))
        elif not near(fa[h][1], fb[h][1]):
            x = fa[h][0]
            if residue(x):
                notes.append('%s: form %s T %s, A %s (OR and =)' % (what, h, fa[h][1], fb[h][1]))
            else:
                reads = any(r != h and r in x for r in resid)
                bad.append('%s: form %s T %s, A %s [no OR and =%s]' % (what, h, fa[h][1], fb[h][1], '; reads a form with OR and =' if reads else ''))


def compare(a, b, ta, tb):
    """(verdict, lines of what differs) for the rows a (T) and b (A) of a stem, with their start texts."""
    notes, bad, sums = [], [], []

    def diff(what, text):
        (notes if text and residue(text) else bad).append(what + (' (OR and =)' if text and residue(text) else ' [no OR and =]'))
    if not (a['finished'] and b['finished']) or a.get('error') or b.get('error'):
        return 'CHECK', ['a row did not finish: T finished %s error %s, A finished %s error %s' % (a['finished'], a.get('error'), b['finished'], b.get('error'))]
    figures('start', named(ta, a['before']['bits']), named(tb, b['before']['bits']), notes, bad)
    if len(a['steps']) != len(b['steps']):
        bad.append('steps: T %d, A %d' % (len(a['steps']), len(b['steps'])))
    for k, (s, t) in enumerate(zip(a['steps'], b['steps'])):
        for key in ('shape', 'rank', 'committed', 'undrawn'):
            if s[key] != t[key]:
                diff('step %d %s: T %s, A %s on %s' % (k, key, s[key], t[key], head(s['text'])), s['text'])
        for key in ('bits', 'worst'):
            if not near(s[key], t[key]):
                diff('step %d %s: T %s, A %s on %s' % (k, key, s[key], t[key], head(s['text'])), s['text'])
        if not near(s['sum'], t['sum']):
            sums.append('step %d sum: T %s, A %s' % (k, s['sum'], t['sum']))
        if sorted(scrub(n[0]) for n in s['new']) != sorted(scrub(n[0]) for n in t['new']):
            diff('step %d new forms differ on %s' % (k, head(s['text'])), s['text'])
    for key in ('undrawn', 'worst'):
        if not near(a['after'][key], b['after'][key]):
            bad.append('after %s: T %s, A %s' % (key, a['after'][key], b['after'][key]))
    if not near(a['after']['sum'], b['after']['sum']):
        sums.append('after sum: T %s, A %s' % (a['after']['sum'], b['after']['sum']))
    if a.get('landed') and b.get('landed'):
        figures('after', named(a['working'].split('\n'), a['after']['bits']), named(b['working'].split('\n'), b['after']['bits']), notes, bad)
    if a.get('program') != b.get('program'):
        pa, pb = (a.get('program') or '').split('\n'), (b.get('program') or '').split('\n')
        same = sorted(pa) == sorted(pb)
        notes.append('program: %s' % ('the same lines in another order' if same else '%d of %d lines differ' % (len(set(pa) ^ set(pb)) // 2, len(pa))))
        for x in sorted(set(pa) ^ set(pb)):
            if x.strip() and not x.startswith('(OUT'):
                diff('program line %s' % head(x), x)
    resid = bool(notes)  # a sum follows from the forms that are named
    (notes if resid else bad).extend(x + (' (follows from the named forms)' if resid else ' [no form named]') for x in sums)
    return ('CHECK' if bad else 'PASS (named)' if notes else 'PASS'), bad + notes


def main():
    d = sys.argv[1]
    worst = 'PASS'
    for t in sys.argv[2:]:
        a, b = last('%s/row-%s-T.jsonl' % (d, t)), last('%s/row-%s-A.jsonl' % (d, t))
        if a is None or b is None:
            print(t, 'CHECK no row: T %s, A %s' % (a is not None, b is not None))
            worst = 'CHECK'
            continue
        ta, tb = json.load(open('%s/lines-%s-T.json' % (d, t)))[t], json.load(open('%s/lines-%s-A.json' % (d, t)))[t]
        verdict, lines = compare(a, b, ta, tb)
        print(t, verdict, '| T: steps %d committed %s after %s sum %s | A: steps %d committed %s after %s sum %s' % (len(a['steps']), [k for k, s in enumerate(a['steps']) if s['committed']], a['after']['worst'], a['after']['sum'], len(b['steps']), [k for k, s in enumerate(b['steps']) if s['committed']], b['after']['worst'], b['after']['sum']))
        for x in lines:
            print('    ', x)
        if verdict == 'CHECK':
            worst = 'CHECK'
    print('order check', 'ok' if worst != 'CHECK' else 'needs a look')


if __name__ == '__main__':
    main()
