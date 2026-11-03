"""One stem of the covering clause revision: takes the cheapest covering clause of each form that keeps gold's OUT rows and attempts, cuts the crossing clauses left, and checks the program under the helper-form bar. Prints one JSON row.

  <runtime python> gold_cover_one.py TASK LINES.json CROSSING.json COVERS.json
COVERS.json maps a task to its candidates, each {line, forms, source}: the forms a clause reads, then the clause in gold's names, in place of the form at line. A form that no form reads after a swap comes out. A candidate stays out unless its forms cost fewer bits in all than the forms it removes. The bar's code is gold_helper_one.py.
"""
import json, os, sys
task, lines_path, crossing_path, covers_path = sys.argv[1:5]
here = os.path.dirname(os.path.abspath(__file__))
sys.argv = ['x', task, lines_path, crossing_path]
exec(open(here + '/gold_helper_one.py').read().split('t0 = time.time()')[0].replace('json.load(open(crossing_path))[task]', 'json.load(open(crossing_path)).get(task, [])'))
covers = json.load(open(covers_path)).get(task, [])
old_text = list(lines)


def form_bits(ls, i):
    global sampler
    if sampler is None:
        sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    head = ls[i].split()[0][1:]
    G.gold_of = lambda t, c_, p, x=ls[:i + 1]: (t, x)
    try:
        q = or_q.one(sampler, task, head, [i, 0], head)
    except Exception:  # noqa: BLE001
        return None
    return None if q.get('bad') or q.get('dead') is not None or q.get('total') is None else round(q['total'], 2)


def name_of(x):
    m = re.match(r'\(\w+ (&[A-Za-z_0-9]+)', x)
    return m[1] if m else None


def prune(ls):
    """ls without the forms that no later form reads, and those removed. The items are (gold line or None, text)."""
    ls, gone = list(ls), []
    while True:
        text = '\n'.join(x for _, x in ls)
        dead = [k for k, (_, x) in enumerate(ls) if name_of(x) and len(re.findall(re.escape(name_of(x)) + r'(?=[ .)])', text)) == 1]
        if not dead:
            return ls, gone
        gone.append(ls.pop(dead[-1]))


t0 = time.time()
row = dict(task=task, candidates=len(covers))
gold = walk(lines)
base = list(enumerate(lines))
start = list(base)
swapped, tally = [], dict(rows=0, attempts=0, ended=0, bits=0, refused=0, gone=0)
for line in sorted({c['line'] for c in covers}, reverse=True):
    at = next((k for k, (o, _) in enumerate(base) if o == line), None)
    if at is None:
        tally['gone'] += 1
        continue
    texts = [x for _, x in base]
    best = None
    for c in {tuple(c['forms']): c for c in covers if c['line'] == line}.values():
        ls, gone = prune(base[:at] + [(None, f) for f in c['forms']] + base[at + 1:])
        now = [x for _, x in ls]
        try:
            rows, ended, att = walk(now)
        except (arclog.Refusal, arclog.Fault, ValueError, StopIteration):
            tally['refused'] += 1
            continue
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ != 'Fail':
                raise
            tally['refused'] += 1
            continue
        if not ended:
            tally['ended'] += 1
        elif rows != gold[0]:
            tally['rows'] += 1
        elif att != gold[2]:
            tally['attempts'] += 1
        else:
            added = [k for k, (o, _) in enumerate(ls) if o is None and ls[k][1] in c['forms']]
            each = [form_bits(now, k) for k in added]
            old = [form_bits(texts, at)] + [form_bits(texts, texts.index(x)) for o, x in gone if o is not None]
            if None in each or None in old or sum(each) >= sum(old):
                tally['bits'] += 1
            elif best is None or sum(each) - sum(old) < best[0]:
                best = (sum(each) - sum(old), ls, dict(line=line, before=old, after=each, removed=[o for o, _ in gone if o is not None], source=c['source']))
    if best:
        base = best[1]
        swapped.append(best[2])
if covers:  # every candidate in at once: a shared form comes out only when all its readers swap
    joint = start
    for line in sorted({c['line'] for c in covers}, reverse=True):
        c = min((c for c in covers if c['line'] == line), key=lambda c: len(c['forms']))
        at = next(k for k, (o, _) in enumerate(joint) if o == line)
        joint = joint[:at] + [(None, f) for f in c['forms']] + joint[at + 1:]
    joint, _ = prune(joint)
    now, texts = [x for _, x in joint], [x for _, x in start]
    try:
        rows, ended, att = walk(now)
        same = ended and rows == gold[0] and att == gold[2]
    except Exception as e:  # noqa: BLE001
        same = False
    if same:
        a, b = [form_bits(now, k) for k in range(len(now) - 1)], [form_bits(texts, k) for k in range(len(texts) - 1)]
        row['joint'] = dict(gold=round(sum(x or 0 for x in b), 2), swap=round(sum(x or 0 for x in a), 2), undrawn=a.count(None) - b.count(None))
        single = sum(sum(s['before']) - sum(s['after']) for s in swapped)
        row['joint']['pays'] = None not in a and None not in b and sum(a) < sum(b)
        if row['joint']['pays'] and sum(b) - sum(a) > single:
            base = joint
            swapped = [dict(line=-1, before=b, after=a, source='joint')]
    else:
        row['joint'] = 'rows differ'
lines[:] = [x for _, x in base]
where = {o: k for k, (o, _) in enumerate(base) if o is not None}
crossing = [dict(c, line=where[c['line']]) for c in crossing if c['line'] in where and lines[where[c['line']]] == old_text[c['line']]]
got, why = check(crossing, gold)
if got is None and crossing:
    crossing = []
    got, why = check([], gold)
row.update(swapped=swapped, kept_out=tally, cuts=[c['line'] for c in crossing], failed=why, seconds=round(time.time() - t0, 1))
if got:
    row.update(got)
print(json.dumps(row))
