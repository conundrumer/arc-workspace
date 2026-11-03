"""One stem of the shape cut, the second cut stage over gold: cuts each form at or over the bar, worst first, and keeps a cut only where the bar on the program holds and the stem's landing value falls. Prints one JSON row after each landing and one at the end; the last row is the stem's row.

  <runtime python> gold_shapecut_one.py TASK LINES.json [SECONDS]

LINES.json maps the stem to its forms, the base text.
A cut lands where the stem has fewer forms with no bits, or as many and `landing` of its forms' bits falls, or that value stays and the sum of bits falls. `landing` is the one place that states the rule. Only new forms and forms after the first change are read again.
Run-time settings, in the environment: BAR, the bits at or over which a form is tried (default 13), and LANDING, `worst` (default: the largest bits of a form) or `above` (the sum of the bits above BAR).
Every form at or over BAR is tried in a pass, worst first; a form with no bits comes first. A form whose cuts all failed in its own text is not tried again.
A cut's new forms have to pass a form test. Where the form moves the landing value, `landing` of the new forms has to be under `landing` of the form. Where it does not, as a form that is not the worst under `worst`, their sum of bits has to be under the form's.
Bar for a cut: the program ends at table work cap 2^20 in the Closed world, on train and test, its attempts equal the base's on every test input, its OUT rows equal the base's by column label, its normal form is a fixed point of the round trip and steps to the same attempts, each new form walks with nothing refused. The row read takes one entry per example, so several DET assignments can differ in rows with no grid change: where rows differ and the attempts and train Consistent hold, the cut passes and the step has rows_differ true.

Cost: the checks of a cut run cheapest first: the reader's check of the text, then the bits, then the decode, then the OUT rows, and the first that fails ends the cut.
gold_fork_reads.py holds the reads. Each decode and OUT row walk has a new closed-world session, so bits and table work do not depend on an earlier read. A decode of a token stream seen before takes no step. The OUT rows run on a fresh session, since the table work that they count depends on what the session has cached.

In a row, `worst` of a state is the largest bits of a form, and `score` is the landing value.
"""
import collections, copy, hashlib, json, os, re, sys, time, types
import gold_fork_reads as F
from gold_fork_reads import MARGIN, OVER, Bound, counts, groups, load_sampler, memo, misses, read_form, timed, times
import arclog, live, live_try, or_q, search, superdag as D
from gold_shapecut_cuts import all_candidates as candidates

BAR, RULE = float(os.environ.get('BAR', 13)), os.environ.get('LANDING', 'worst')
VERIFY = 8  # cuts of a form that go to the bar
ROOT = os.environ.get('ARC_ROOT', '.')
task = base_lines = t0 = SECONDS = CS = None


class Late(Exception):
    pass


def setup(stem, lines_path, seconds=840):
    """The stem's state, in the process that runs the stem."""
    global task, base_lines, t0, SECONDS, CS
    task, SECONDS = stem, float(seconds)
    base_lines = [x for x in json.load(open(lines_path))[task] if x.strip()]
    t0 = time.time()
    text = open('%s/data/tasks/%s.json' % (ROOT, task)).read()
    F.begin(task)
    CS = types.SimpleNamespace(text=text)
    CS.sess = session()


def session():
    return arclog.Session(arclog.Task.from_json(CS.text, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))


def stream(text):
    i, m, _ = arclog.StudyProgram.from_sexp(text, CS.sess.settings).decode_stream()
    return [int(x) for x in i], [int(bool(x)) for x in m]


def walk(ls):
    """The OUT rows of the program ls by example, by column label. Each model token of the forms past the longest kept prefix is stepped with its tables, on a session of its own."""
    out = next(x for x in ls if x.startswith('(OUT'))
    names = re.findall(r'\^(\w+)', out)
    body = re.sub(r'\^(\w+)', r'(:\1 *\1)', out[5:-1])
    body = re.sub(r'\(:(\w+) \(:\w+ \*(\w+)\)\)', r'(:\1 *\2)', body)
    added = '(RULE &zz_out %s)' % body
    probe = '(OUT (&zz_out %s))' % ' '.join('^' + n for n in names)
    sess = session()
    a, b = stream('\n'.join([x for x in ls if x is not out] + [added, probe]))
    toks = [t for t, k in zip(a, b) if k]
    d = sess.decoder()
    i = max(j for j, t in enumerate(toks) if t == live.OUT_TOK)
    ct = None
    for t in toks[:i]:
        d.step(t)
        ct = arclog.step_tables(d, *live.TABLES, True, ct)
    tb = [D.S.parse_table(D.OneTable(ct, j)) for _, j in D.relation_tables(ct)][-1]
    start = [sum(tb['widths'][:k]) for k in range(len(tb['widths']))]
    cols = sorted(range(len(start)), key=tb['labels'].__getitem__)
    by_label = lambda r: tuple(x for k in cols for x in r[start[k]:start[k] + tb['widths'][k]])
    return {str(tuple(e[0])): sorted(str(by_label(r)) for r in e[2]) for e in tb['entries']}


directs = {}


def direct(text):
    """Steps the program text as it stands: whether it ended, its attempts. The steps start at the longest prefix kept, and a stream seen before takes no step."""
    gs, keys, _ = groups(text, CS.sess.settings)
    if keys[-1] in directs:
        counts['decode memo hits'] += 1
        return directs[keys[-1]]
    d = session().decoder()
    counts['decode forms stepped'] += len(gs)
    for g in gs:
        for t in g:
            d.step(t)
    with timed('attempts'):
        got = directs[keys[-1]] = bool(d.ended), d.attempts()
    return got


def landing(bits):
    """The value that a landing takes down, for a list of bits. A rule here must not fall where a form is added or a form's bits rise, since the walks stop on that. `above` reads BAR. A later rule: log2 of the sum of 2^bits."""
    if RULE == 'above':
        return round(sum(max(0.0, b - BAR) for b in bits), 2)
    if RULE == 'worst':
        return max(bits, default=0)
    raise ValueError(RULE)


def room(got, top):
    """The bits b of one more form at which landing(got + [b]) reaches top, or None where no bits reach it. landing is the only rule that this reads."""
    lo, hi = 0.0, 1000.0
    if landing(got + [hi]) < top:
        return None
    if landing(got + [lo]) >= top:
        return lo
    for _ in range(26):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if landing(got + [mid]) >= top else (mid, hi)
    return hi


def forms_of(ls):
    return [i for i, x in enumerate(ls) if not x.startswith('(OUT')]


def gains(new, old):
    """Whether state new lands over state old, and by which clause."""
    if new[0] != old[0]:
        return new[0] < old[0]
    return new[1] < old[1] - 1e-6 or (new[1] <= old[1] + 1e-6 and new[2] < old[2] - 1e-6)


def name_of(x):
    m = re.match(r'\(\w+ (&[A-Za-z_0-9]+)', x)
    return m[1] if m else None


def dead(ls):
    text = '\n'.join(ls)
    return {x for x in ls if name_of(x) and not x.startswith('(DET') and len(re.findall(re.escape(name_of(x)) + r'(?=[ .)])', text)) == 1}


def prune(ls, was):
    """ls without the forms that the cut left unread. Forms unread before the cut stay."""
    ls = list(ls)
    while True:
        new = dead(ls) - was
        if not new:
            return ls
        ls = [x for x in ls if x not in new]


def state(ls, cur=None):
    """(forms with no bits, landing value, sum) of ls, and the bits by line. With the state cur, stops and gives (None, None) at the first read that shows ls cannot gain over cur: gains reads forms with no bits, then the landing value, then the sum, and each only grows as forms are read."""
    bits, got = {}, []
    undrawn = 0
    for i in forms_of(ls):
        limit = None
        if cur is not None and undrawn >= cur[0]:
            limit = room(got, cur[1] + MARGIN)
            if landing(got) >= cur[1] - 1e-6:
                left = cur[2] - sum(got) + MARGIN
                limit = left if limit is None else min(limit, left)
        b = read_form(ls, i, limit)
        if b is OVER:
            counts['states stopped'] += 1
            return None, None
        bits[i] = b
        if isinstance(b, (int, float)):
            got.append(b)
        elif b is None:
            undrawn += 1
        if cur is not None and (undrawn > cur[0] or (undrawn == cur[0] and got and (landing(got) > cur[1] + 1e-6 or (landing(got) >= cur[1] - 1e-6 and sum(got) >= cur[2] + MARGIN)))):
            counts['states stopped'] += 1
            return None, None
    return (undrawn, landing(got), round(sum(got), 2)), bits


def reader_takes(ls, last):
    """Whether the reader takes the forms of ls up to line last. A form that it refuses has no bits, as or_q.gold_rest reads the same text."""
    try:
        arclog.StudyProgram.from_sexp('\n'.join(ls[:last + 1] + [live.READER_OUT]), F.OS.settings).decode_stream()
        return True
    except Exception:  # noqa: BLE001
        return False


def legal(ls):
    """The normal form of ls and None, or None and why: the reader's checks alone, with no decode."""
    try:
        text = '\n'.join(ls)
        norm = arclog.StudyProgram.from_stream(CS.sess, *stream(text)).sexp()
        if arclog.StudyProgram.from_stream(CS.sess, *stream(norm)).sexp() != norm:
            return None, 'round trip'
        return [x for x in norm.splitlines() if x.strip()], None
    except (arclog.Refusal, arclog.Fault) as e:
        return None, type(e).__name__
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ in ('Fail', 'ValueError', 'StopIteration', 'IndexError'):
            return None, type(e).__name__
        raise


def decoded(ls, nl, gold):
    """The bar's decode on ls, whose normal form is nl. Returns (rows_differ, None), or (None, why)."""
    try:
        with timed('decode'):
            ended, att = direct('\n'.join(ls))
            if not ended:
                return None, 'does not end'
            if att != gold['attempts']:
                return None, 'attempts differ'
            e2, a2 = direct('\n'.join(nl))
            if not e2 or a2 != gold['attempts']:
                return None, 'normal form differs'
        differ = None
        if gold['rows'] is not None:
            with timed('OUT rows'):
                differ = walk(ls) != gold['rows']
        return differ, None
    except (arclog.Refusal, arclog.Fault) as e:
        return None, type(e).__name__
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ in ('Fail', 'ValueError', 'StopIteration', 'IndexError'):
            return None, type(e).__name__
        raise


def tick():
    if time.time() - t0 > SECONDS:
        raise Late()


def tally(t, k):
    t[k] = t.get(k, 0) + 1


def try_form(ls, i, cur, bits, kept):
    """The first cut of form i, cheapest worst first, that passes the bar and gains. Returns (lines, state, bits, step) or None."""
    was = dead(ls)
    old = bits[i]
    top = None if old is None else landing([old])
    moves = old is None or landing([b for k, b in bits.items() if k != i and isinstance(b, (int, float))]) < cur[1] - 1e-6
    ranked = []
    with timed('candidates'):
        cuts = candidates(ls, i)
    for c in cuts:
        tick()
        now = ls[:i] + c.forms + ls[i + 1:]
        if not reader_takes(now, i + len(c.forms) - 1):
            tally(kept, 'refused by the reader')
            continue
        each = []
        for k in range(len(c.forms)):
            limit = None if old is None else room(each, top) if moves else old - sum(each)
            b = read_form(now, i + k, limit)
            if b is OVER or not isinstance(b, (int, float)):
                each = b
                break
            each.append(b)
        if each is OVER:
            tally(kept, 'new forms not under the form cut')
        elif each is None:
            tally(kept, 'new form with no bits')
        elif old is not None and (landing(each) >= top if moves else sum(each) >= old):
            tally(kept, 'new forms not under the form cut')
        else:
            ranked.append((landing(each), sum(each), c, now))
    ranked.sort(key=lambda r: r[:2])
    for _, _, c, now in ranked[:VERIFY]:
        tick()
        now = prune(now, was)
        nl, why = legal(now)
        if nl is None:
            tally(kept, why)
            continue
        new, nb = state(nl, cur)
        if new is None or not gains(new, cur):
            tally(kept, 'no gain on the whole stem')
            continue
        fresh = [k for k in forms_of(nl) if k >= i and k < i + len(c.forms)]
        if any(not isinstance(nb.get(k), (int, float)) for k in fresh):
            tally(kept, 'new form with no bits in normal form')
            continue
        differ, why = decoded(now, nl, GOLD)
        if why:
            tally(kept, why)
            continue
        step = dict(shape=c.shape, kind=ls[i].split()[0][1:], form=i, bits=old, text=ls[i], worst=largest(nb), score=new[1], sum=new[2], undrawn=new[0], forms=len(forms_of(nl)), rows_differ=differ, new=[[nl[k], nb[k]] for k in fresh], clause='score' if new[1] < cur[1] - 1e-6 else 'undrawn' if new[0] < cur[0] else 'sum')
        return nl, new, nb, step
    return None


def largest(bits):
    return max((b for b in bits.values() if isinstance(b, (int, float))), default=0)


def report(row, ls, st, bits, steps, kept, done):
    row.update(after=dict(forms=len(forms_of(ls)), worst=largest(bits), score=st[1], sum=st[2], undrawn=st[0], bits=[bits[i] if bits[i] != 'none' else None for i in forms_of(ls)], kinds=[ls[i].split()[0][1:] for i in forms_of(ls)]), steps=steps, kept_out=kept, reads=misses[0], seconds=round(time.time() - t0, 1), cpu=round(time.process_time() + F.OS.cpu, 1), times={k: round(v, 2) for k, v in times.items()}, counts=dict(counts, peak_read_session=F.OS.peak), finished=done, landed=bool(steps))
    if steps:
        row['program'] = '\n'.join(ls)
    print(json.dumps(row), flush=True)


def main():
    global GOLD
    row = dict(task=task, base_sha=hashlib.sha256('\n'.join(base_lines).encode()).hexdigest()[:16], bar=BAR, rule=RULE)
    ls = list(base_lines)
    cur, bits = state(ls)
    row['before'] = dict(forms=len(forms_of(ls)), worst=largest(bits), score=cur[1], sum=cur[2], undrawn=cur[0], bits=[bits[i] if bits[i] != 'none' else None for i in forms_of(ls)], kinds=[ls[i].split()[0][1:] for i in forms_of(ls)])
    steps, kept = [], {}
    report(row, ls, cur, bits, steps, kept, False)  # the base's bits stand if a cap ends the stem in the base's own walk
    text = '\n'.join(ls)
    try:
        ended, att = direct(text)
        row['base_ended'] = ended
    except (arclog.Refusal, arclog.Fault) as e:
        row.update(base_ended=False, base_fault=type(e).__name__ + ' ' + str(e)[:160])
        ended = False
    if not ended:
        report(row, ls, cur, bits, steps, kept, True)
        return
    try:
        rows = walk(ls)
    except Exception as e:  # noqa: BLE001
        rows = None
        row['base_rows'] = type(e).__name__ + ' ' + str(e)[:160]
    GOLD = dict(attempts=att, rows=rows)
    failed = set()  # forms whose cuts all failed, by the form's own text
    try:
        while True:
            tick()
            order = sorted((i for i in forms_of(ls) if bits[i] != 'none' and (bits[i] is None or bits[i] >= BAR)), key=lambda i: -(bits[i] if bits[i] is not None else 1e9))
            got = None
            for i in order:
                if ls[i] in failed:
                    continue
                got = try_form(ls, i, cur, bits, kept)
                if got:
                    break
                failed.add(ls[i])
            if not got:
                break
            ls, cur, bits, step = got
            steps.append(step)
            row['program_steps'] = row.get('program_steps', []) + [hashlib.sha256('\n'.join(ls).encode()).hexdigest()[:16]]
            step['program'] = '\n'.join(ls)
            report(row, ls, cur, bits, steps, kept, False)
    except Late:
        row['late'] = True
    report(row, ls, cur, bits, steps, kept, True)


if __name__ == '__main__':
    load_sampler()
    setup(*sys.argv[1:4])
    main()
