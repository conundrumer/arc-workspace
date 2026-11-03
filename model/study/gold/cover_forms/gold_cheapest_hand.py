"""The hand rewrite step of revision gold-v3-cheapest-round50. Each rewrite is a whole program: the row programs of gold-v3-kind-forms-a036da074 and the golds of gold-or-rewrite-heldout7. The stem's crossing clauses and cover candidates move onto the program by masked text, gold_cover_one.py runs on it, and the result is compared with the stem's view text. On c7f57c3e, where both sources hold a rewrite, a third candidate has both.

  <runtime python> gold_cheapest_hand.py [rejudge]
One row per candidate in round-out/hand-rewrites.jsonl. The taken row of a stem is the one with `taken` true. A stem takes the candidate that passes and ranks below the view text: fewer undrawable forms, then the lower worst form, then the lower sum, in the all-earlier-forms context. A candidate passes where it ends, its normal form is a fixed point of the round trip, its attempts equal the view's, and its OUT rows equal the view's. Where a row table stops at the 2^20 cap the row check can't be read, so ended and attempts decide, and the row says rows_unread. Where the program comes from another case of the task, rows may differ: `other_case` says so, and ended and attempts decide, the rule for a different case.
"""
import json, os, sys
from gold_cheapest_common import *

sys.path.insert(0, D + 'gold/gold-v3-kind-forms-a036da074')
import kind_rewrites

OUT = HERE + 'round-out/hand-rewrites.jsonl'


def candidates():
    kind = {}
    for l in open(D + 'gold/gold-v3-kind-forms-a036da074/rows.jsonl'):
        r = json.loads(l)
        kind[r['task']] = r
    ors = {g['task']: g for g in json.load(open(D + 'gold/gold-or-rewrite-heldout7/final/golds.json'))}
    for t, r in kind.items():
        yield t, 'kind', None, program_lines(r['program'])
    for t, g in ors.items():
        yield t, 'or', g['case'], program_lines(g['gold_sexp'])
    yield 'c7f57c3e', 'kind and or', ors['c7f57c3e']['case'], kind_rewrites.rewrite('c7f57c3e', program_lines(ors['c7f57c3e']['gold_sexp']))


def view_text(t):
    r = view_row(t)
    if r:
        return r['gold_sexp'], r['case']
    p = {x['task']: x for x in json.load(open(HERE + 'points-eval.json'))}
    return p[t]['gold_sexp'], json.load(open(HERE + 'current-text.json'))[t]['case']


def judge(t, source, case, lines, bits):
    row = dict(stem=t, source=source, case=case)
    bar = Bar(t)
    text, vcase = view_text(t)
    vl = program_lines(text)
    row.update(view_case=vcase, other_case=bool(case and case != vcase))
    done = finish(t, lines)
    row.update(cuts=done.get('cuts'), swapped=done.get('swapped'), failed=done.get('failed'), error=done.get('error'), crossing=len(done['crossing']), covers=len(done['covers']), kept_out=done.get('kept_out'))
    program = done.get('program') or '\n'.join(lines)
    try:
        norm, fixed = bar.normal(program)
    except (arclog.Refusal, arclog.Fault) as e:
        return dict(row, taken=False, why='refused: %s' % str(e)[:160])
    now = program_lines(norm)
    ended, att = bar.direct(norm)
    gold_ended, gold_att = bar.direct(text)
    same_rows = None
    try:
        same_rows = bar.walk(now)[0] == bar.walk(vl)[0]
    except Exception as e:  # noqa: BLE001
        row['rows_unread'] = str(e)[:160]
    row.update(ended=ended, gold_ended=gold_ended, fixed_point=fixed, same_attempts=att == gold_att, same_rows=same_rows, forms=len(now), view_forms=len(vl), program=norm)
    row['now'] = bits.whole(t, now)
    row['view'] = bits.whole(t, vl)
    if not ended or not fixed or att != gold_att:
        return dict(row, passes=False, why='ended %s, fixed point %s, attempts equal %s' % (ended, fixed, att == gold_att))
    if same_rows is False and not row['other_case']:
        return dict(row, passes=False, why='OUT rows differ')
    return dict(row, passes=True)


def decide(r):
    """Sets `better` and `why` of a passing row."""
    a, b = r['now'], r['view']
    say = 'undrawable %d to %d, worst %.2f to %.2f, sum %.2f to %.2f' % (len(b['undrawable']), len(a['undrawable']), b['worst'], a['worst'], b['sum'], a['sum'])
    r['better'] = rank(a) < rank(b)
    r['why'] = ('taken on rank: ' if r['better'] else 'not cheaper on rank: ') + say


def settle(rows):
    for r in rows:
        r['taken'] = False
        if r.get('passes'):
            decide(r)
    for t in {r['stem'] for r in rows}:
        good = [r for r in rows if r['stem'] == t and r.get('better')]
        if good:
            min(good, key=lambda r: rank(r['now']))['taken'] = True
    tmp = OUT + '.new'
    with open(tmp, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    os.replace(tmp, OUT)
    for r in rows:
        print({k: v for k, v in r.items() if k in ('stem', 'source', 'taken', 'why', 'passes')}, flush=True)


def rejudge():
    """Rank again from the rows, on their programs: the bits come from the cache."""
    bits, rows = Bits(), [json.loads(l) for l in open(OUT)]
    source = {(t, s): lines for t, s, _, lines in candidates()}
    for r in rows:
        r['crossing_list'] = crossing_on(r['stem'], source[r['stem'], r['source']])
        if 'program' in r:
            text = view_text(r['stem'])[0]
            r['now'], r['view'] = bits.whole(r['stem'], program_lines(r['program'])), bits.whole(r['stem'], program_lines(text))
            for k in ('sum', 'undrawable', 'view_sum', 'view_undrawable'):
                r.pop(k, None)
    settle(rows)


def main():
    bits = Bits()
    settle([judge(t, source, case, lines, bits) for t, source, case, lines in candidates()])


if __name__ == '__main__':
    rejudge() if sys.argv[1:] == ['rejudge'] else main()
