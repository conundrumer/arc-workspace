"""One stem of the helper-form revision: cuts each crossing clause at its census partition, and checks the program under the bar. Prints one JSON row.

  <runtime python> gold_helper_one.py TASK LINES.json CROSSING.json
Bar: every token passes at table work cap 2^20 in the Closed world, the program ends `Consistent`, its OUT rows equal gold's on each train and test input, its attempts equal gold's, its normal form is a fixed point of the round trip, and each new form walks in the census with nothing refused. A clause that breaks the bar stays as gold writes it.
"""
import json, os, re, sys, time
os.environ['ARCLOG_THREADS'] = '1'
from pathlib import Path
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import arclog, live, or_q, superdag as D
import search_gold as G
from gold_chain import Clause
task, lines_path, crossing_path = sys.argv[1:4]
ROOT = Path(os.environ.get('ARC_ROOT', '.'))
lines = json.load(open(lines_path))[task]
crossing = sorted(json.load(open(crossing_path))[task], key=lambda c: c['line'])
text_task = (ROOT / 'data/tasks' / f'{task}.json').read_text()
sampler = None


def session():
    return arclog.Session(arclog.Task.from_json(text_task, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))


def stream(sess, text):
    i, m, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    return [int(x) for x in i], [int(bool(x)) for x in m]


def walk(ls):
    """The OUT rows of the program ls by example, whether it ended, and its attempts."""
    out = next(x for x in ls if x.startswith('(OUT'))
    names = re.findall(r'\^(\w+)', out)
    body = re.sub(r'\^(\w+)', r'(:\1 *\1)', out[5:-1])
    body = re.sub(r'\(:(\w+) \(:\w+ \*(\w+)\)\)', r'(:\1 *\2)', body)
    added = '(RULE &zz_out %s)' % body
    probe = '(OUT (&zz_out %s))' % ' '.join('^' + n for n in names)
    sess = session()
    a, b = stream(sess, '\n'.join([x for x in ls if x is not out] + [added, probe]))
    toks = [t for t, k in zip(a, b) if k]
    d = sess.decoder()
    i = max(j for j, t in enumerate(toks) if t == live.OUT_TOK)
    ct = None
    for t in toks[:i]:
        d.step(t)
        ct = arclog.step_tables(d, *live.TABLES, True, ct)
    tb = [D.S.parse_table(D.OneTable(ct, j)) for _, j in D.relation_tables(ct)][-1]
    for t in toks[i:]:
        d.step(t)
    start = [sum(tb['widths'][:k]) for k in range(len(tb['widths']))]
    cols = sorted(range(len(start)), key=tb['labels'].__getitem__)
    by_label = lambda r: tuple(x for k in cols for x in r[start[k]:start[k] + tb['widths'][k]])
    return {str(tuple(e[0])): sorted(str(by_label(r)) for r in e[2]) for e in tb['entries']}, bool(d.ended), d.attempts()


def direct(text):
    """Steps the program text as it stands: whether it ended, and its attempts."""
    sess = session()
    a, b = stream(sess, text)
    d = sess.decoder()
    for t, k in zip(a, b):
        if k:
            d.step(t)
    return bool(d.ended), d.attempts()


def apply(chosen):
    """The program with the clauses chosen cut; returns its lines and the spans of new forms."""
    ls, spans = list(lines), []
    for c in sorted(chosen, key=lambda c: -c['line']):
        cl = Clause(dict(task=task, line=c['line'], gold_sexp='\n'.join(lines)))
        forms = cl.chain(c['cuts'], '&w%d_' % c['line'])
        ls[c['line']:c['line'] + 1] = forms
        spans.append((c['line'], len(forms)))
    return ls, spans


def drawable(text, chosen):
    global sampler
    if sampler is None:
        sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    ls = [x for x in text.splitlines() if x.strip()]
    shift, bits = 0, []
    for c in sorted(chosen, key=lambda c: c['line']):
        n = len(c['cuts'])
        for k in range(n):
            i = c['line'] + shift + k
            G.gold_of = lambda t, c_, p, x=ls[:i + 1]: (t, x)
            q = or_q.one(sampler, task, 'RULE', [i, 0], 'RULE')
            if q.get('bad') or q.get('dead') is not None or q.get('total') is None:
                return False, bits, 'form %d: %s %s' % (i, q.get('bad'), q.get('dead'))
            bits.append(q['total'])
        shift += n - 1
    return True, bits, None


def check(chosen, gold):
    ls, _ = apply(chosen)
    try:
        rows, ended, att = walk(ls)
        if not ended:
            return None, 'does not end'
        if rows != gold[0]:
            return None, 'OUT rows differ'
        if att != gold[2]:
            return None, 'attempts differ'
        sess = session()
        norm = arclog.StudyProgram.from_stream(sess, *stream(sess, '\n'.join(ls))).sexp()
        if arclog.StudyProgram.from_stream(sess, *stream(sess, norm)).sexp() != norm:
            return None, 'round trip'
        e2, a2 = direct(norm)
        if not e2 or a2 != gold[2]:
            return None, 'normal form differs'
        ok, bits, why = drawable(norm, chosen)
        if not ok:
            return None, 'not drawable: ' + str(why)[:120]
        return dict(program=norm, bits=bits), None
    except (arclog.Refusal, arclog.Fault) as e:
        return None, type(e).__name__ + ' ' + str(e)[:120]


t0 = time.time()
row = dict(task=task, clauses=len(crossing))
gold = walk(lines)
row['gold_ended'] = gold[1]
got, why = check(crossing, gold) if gold[1] else (None, 'gold does not end')
kept, failed = crossing, []
if got is None and len(crossing) > 1 and gold[1]:
    kept, got = [], None
    for c in crossing:
        g, w = check(kept + [c], gold)
        if g is None:
            failed.append(dict(line=c['line'], why=w))
        else:
            kept, got = kept + [c], g
elif got is None:
    kept, failed = [], [dict(line=c['line'], why=why) for c in crossing]
row.update(applied=[c['line'] for c in kept], failed=failed, seconds=round(time.time() - t0, 1))
if got:
    row.update(got)
print(json.dumps(row))
