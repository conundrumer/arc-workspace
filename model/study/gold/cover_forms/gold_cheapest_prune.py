"""The prune step of revision gold-v3-cheapest-round50: drops forms that no later form reads, on the test of `prune` in gold_cover_one.py, where the result passes the bar and costs fewer bits.

  <runtime python> gold_cheapest_prune.py run
  <runtime python> gold_cheapest_prune.py child STEM...

Reads each stem's text after the hand rewrite and case choice steps. One row per stem with such a form in round-out/prune-rows.jsonl; a row applies only to the text it read, named by `base`, so a stem runs again where a later step changed its text. A stem past 5 min or 8 GiB has a set_aside row, with no retry.
All such forms come out first, repeating as `prune` does. Where that breaks the bar they come out one at a time, last first, and a form whose removal breaks the bar stays, with its readers. The bar: every token passes at 2^20, the program ends Consistent, OUT rows and attempts equal the base's, and the normal form is a fixed point. A stem whose rows can't be read at the 2^20 cap keeps its text. A drop stands where the result ranks below the text: fewer undrawable forms, then the lower worst form, then the lower sum, in the all-earlier-forms context.
"""
import json, os, re, sys
from gold_cheapest_common import *
import gold_cheapest_case as C

OUT = HERE + 'round-out/prune-rows.jsonl'


def name_of(x):
    m = re.match(r'\(\w+ (&[A-Za-z_0-9]+)', x)
    return m[1] if m else None


def dead_lines(ls, keep=()):
    text = '\n'.join(ls)
    return [k for k, x in enumerate(ls) if name_of(x) and name_of(x) not in keep and len(re.findall(re.escape(name_of(x)) + r'(?=[ .)])', text)) == 1]


def stack(t, hand, case):
    """The stem's text after the hand rewrite and case choice steps."""
    return case[t]['program'] if t in case else C.base_of(t, hand)[0]


def holds(bar, ls, gold):
    """None where ls passes the bar against gold, else the reason, and its normal form."""
    try:
        rows, ended, att = bar.walk(ls)
    except Exception as e:  # noqa: BLE001
        return type(e).__name__ + ' ' + str(e)[:120], None
    if not ended:
        return 'does not end', None
    if rows != gold[0]:
        return 'OUT rows differ', None
    if att != gold[2]:
        return 'attempts differ', None
    norm, fixed = bar.normal('\n'.join(ls))
    if not fixed:
        return 'round trip', None
    return None, norm


def one(t, bits, hand, case):
    print('stem', t, flush=True)
    text = stack(t, hand, case)
    ls = program_lines(text)
    dead = dead_lines(ls)
    if not dead:
        return dict(stem=t, base=sha(text), dead=[], taken=None, why='no such form')
    row = dict(stem=t, base=sha(text), dead=[dict(line=k, kind=ls[k].split()[0][1:], form=ls[k]) for k in dead])
    bar = Bar(t)
    try:
        gold = bar.walk(ls)
    except Exception as e:  # noqa: BLE001
        return dict(row, at_cap=True, taken=None, why='rows unread: ' + str(e)[:120])
    if not gold[1]:
        return dict(row, taken=None, why='the text does not end')
    now, gone = list(ls), []
    while dead_lines(now):
        k = dead_lines(now)[-1]
        gone.append(now.pop(k))
    bad, norm = holds(bar, now, gold)
    verdicts = {}
    if bad:
        verdicts['all together'] = bad
        now, gone, kept = list(ls), [], set()
        while dead_lines(now, kept):
            k = dead_lines(now, kept)[-1]
            trial = now[:k] + now[k + 1:]
            why, n = holds(bar, trial, gold)
            if why:
                kept.add(name_of(now[k]))
                verdicts[now[k]] = why
            else:
                gone.append(now[k])
                now, norm = trial, n
        if not gone:
            return dict(row, verdicts=verdicts, taken=None, why='every drop breaks the bar')
    new = program_lines(norm)
    f0, f1 = bits.whole(t, ls), bits.whole(t, new)
    row.update(dropped=gone, verdicts=verdicts, before=f0, after=f1)
    say = 'worst %.2f to %.2f, sum %.2f to %.2f, undrawable %d to %d' % (f0['worst'], f1['worst'], f0['sum'], f1['sum'], len(f0['undrawable']), len(f1['undrawable']))
    if rank(f1) >= rank(f0):
        return dict(row, taken=None, why='not cheaper on rank: ' + say)
    return dict(row, taken=True, program=norm, why='%d forms out, %d stay: %s' % (len(gone), len(verdicts) - ('all together' in verdicts), say))


def child(stems):
    bits, hand, case = Bits(), C.hand_taken(), finished()
    for t in stems:
        print(json.dumps(one(t, bits, hand, case)), flush=True)


def finished():
    return {r['stem']: r for r in map(json.loads, open(C.OUT)) if r['taken']} if os.path.exists(C.OUT) else {}


def run():
    text = json.load(open(HERE + 'current-text.json'))
    stems = sorted(set(os.listdir(HERE + 'corpus-view')) | {t for t in text if t in HELD or t in EVAL})
    hand, case = C.hand_taken(), finished()
    done = set()  # a stem is done where a row read its text as it stands, or made it
    for r in map(json.loads, open(OUT) if os.path.exists(OUT) else ()):
        done.add((r['stem'], r.get('base')))
        if r.get('set_aside') or r.get('program'):
            done.add((r['stem'], sha(r['program'])) if r.get('program') else (r['stem'], None))
    left = [t for t in stems if (t, None) not in done and (t, sha(stack(t, hand, case))) not in done and dead_lines(program_lines(stack(t, hand, case)))]
    print(len(left), 'stems', flush=True)
    with open(OUT, 'a') as out:
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


if __name__ == '__main__':
    if sys.argv[1] == 'child':
        child(sys.argv[2:])
    else:
        run()
