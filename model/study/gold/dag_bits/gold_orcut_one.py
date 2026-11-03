"""One stem of the extended cut: cuts OR branches, INIT ports and bodies, worst form first, and keeps a cut only where the bar holds and the stem gains. Prints one JSON row after each landing and one at the end; the last row is the stem's row.

  <runtime python> gold_orcut_one.py TASK LINES.json [SECONDS]

gold_combined_run.py imports this module, loads the sampler once and forks a child per stem; the child calls setup and main. gold_fork_reads.py holds the reads.
LINES.json maps the stem to its forms, the base text. A cut lands where the stem's worst form in the all-earlier-forms context falls, or the worst stays and the sum falls; a form with no bits counts above every form with bits. Only new forms and forms after the first change are read again.
The worst form goes first. Where none of its cuts land, the next forms are tried, to the bound TRY_FORMS, and a landing there has to take the sum down.
Bar for a cut: the program ends at table work cap 2^20 in the Closed world, on train and test, its attempts equal the base's on every test input, its OUT rows equal the base's by column label, its normal form is a fixed point of the round trip and steps to the same attempts, each new form walks with nothing refused. The row read takes one entry per example, so several DET assignments can differ in rows with no grid change: where rows differ and the attempts and train Consistent hold, the cut passes and the step has rows_differ true.

Cost: the checks of a cut run cheapest first: the reader's check of the text, then the bits, then the decode, then the OUT rows, and the first that fails ends the cut.
The bar's decodes share one closed-world session. A session past RESET_BYTES starts anew. The OUT rows run on a fresh session each.
"""
import collections, copy, hashlib, json, os, re, sys, time
import gold_fork_reads as F
from gold_fork_reads import MARGIN, OVER, Bound, counts, groups, load_sampler, memo, misses, read_form, timed, times
import arclog, live, live_try, or_q, search, superdag as D
from gold_extcut_cuts import candidates

TRY_FORMS, VERIFY = 5, 8  # forms tried in one pass; cuts of a form that go to the bar
KEPT_STATES, KEPT_BYTES = 512, 1 << 29  # the bar: form boundaries kept per session, and the bytes of their tables, which count against the session's byte bound
RESET_BYTES = 1 << 30  # the bar's session past RESET_BYTES of counted bytes starts anew, between decodes
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
    closed_text = text
    make = lambda: arclog.Session(arclog.Task.from_json(closed_text, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
    CS = Kept(make)


class Kept:
    """A session and the states kept at its form boundaries, least recently used first out."""

    def __init__(self, make):
        self.make, self.sess, self.states, self.peak = make, make(), collections.OrderedDict(), 0
        self.bytes = 0

    def guard(self):
        """Starts the session anew past RESET_BYTES. The kept decoders root interned terms, so a session can reach its byte bound, where tables stop and a read's bits change."""
        c = self.sess.cache_stats()
        self.peak = max(self.peak, c[2] + c[4] + c[5])
        if c[2] + c[4] + c[5] > RESET_BYTES:
            self.states.clear()
            self.bytes = 0
            self.sess = self.make()
            counts['session resets'] += 1

    def get(self, key):
        got = self.states.get(key)
        if got is None:
            return None
        self.states.move_to_end(key)
        return got[0]

    def put(self, key, value, ct):
        """Keeps value, whose tables are ct, and drops the oldest states past the bounds."""
        n = len(ct.values) if ct is not None else 0
        self.states[key] = value, n
        self.bytes += n
        while len(self.states) > KEPT_STATES or (self.bytes > KEPT_BYTES and len(self.states) > 1):
            self.bytes -= self.states.popitem(last=False)[1][1]
            counts['states dropped'] += 1


def stream(text):
    i, m, _ = arclog.StudyProgram.from_sexp(text, CS.sess.settings).decode_stream()
    return [int(x) for x in i], [int(bool(x)) for x in m]


def walk(ls):
    """The OUT rows of the program ls by example, by column label, on a session of its own: the table work that they count depends on what a session holds, and a shared session changes which cuts stop."""
    out = next(x for x in ls if x.startswith('(OUT'))
    names = re.findall(r'\^(\w+)', out)
    body = re.sub(r'\^(\w+)', r'(:\1 *\1)', out[5:-1])
    body = re.sub(r'\(:(\w+) \(:\w+ \*(\w+)\)\)', r'(:\1 *\2)', body)
    added = '(RULE &zz_out %s)' % body
    probe = '(OUT (&zz_out %s))' % ' '.join('^' + n for n in names)
    sess = CS.make()
    gs, _, _ = groups('\n'.join([x for x in ls if x is not out] + [added, probe]), sess.settings)
    assert gs[-1][0] == live.OUT_TOK
    d = sess.decoder()
    ct = None
    for g in gs[:-1]:
        for t in g:
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
    CS.guard()
    gs, keys, _ = groups(text, CS.sess.settings)
    if keys[-1] in directs:
        counts['decode memo hits'] += 1
        return directs[keys[-1]]
    k = len(gs) - 1
    while k > 0 and CS.get(keys[k - 1]) is None:
        k -= 1
    d = CS.get(keys[k - 1]).fork() if k else CS.sess.decoder()
    counts['decode forms kept'] += k
    for j in range(k, len(gs)):
        counts['decode forms stepped'] += 1
        for t in gs[j]:
            d.step(t)
        if j < len(gs) - 1:
            CS.put(keys[j], d, None)
            d = d.fork()
    with timed('attempts'):
        got = directs[keys[-1]] = bool(d.ended), d.attempts()
    return got


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
    """(forms with no bits, worst, sum) of ls, and the bits by line. With the state cur, stops and gives (None, None) at the first read that shows ls cannot gain over cur: gains reads forms with no bits, then worst, then sum, and each only grows as forms are read."""
    bits, got = {}, []
    undrawn = 0
    for i in forms_of(ls):
        limit = None
        if cur is not None and undrawn >= cur[0]:
            worst, total = max(got, default=0), sum(got)
            limit = cur[1] + MARGIN
            if worst >= cur[1] - 1e-6:
                limit = min(limit, cur[2] - total + MARGIN)
        b = read_form(ls, i, limit)
        if b is OVER:
            counts['states stopped'] += 1
            return None, None
        bits[i] = b
        if isinstance(b, (int, float)):
            got.append(b)
        elif b is None:
            undrawn += 1
        if cur is not None and (undrawn > cur[0] or (undrawn == cur[0] and got and (max(got) > cur[1] + 1e-6 or (max(got) >= cur[1] - 1e-6 and sum(got) >= cur[2] + MARGIN)))):
            counts['states stopped'] += 1
            return None, None
    return (undrawn, max(got, default=0), round(sum(got), 2)), bits


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
    first_clause = old is None or old >= cur[1] - 1e-6
    ranked = []
    with timed('candidates'):
        cuts = candidates(ls, i)
    for c in cuts:
        tick()
        now = ls[:i] + c.forms + ls[i + 1:]
        each = []
        for k in range(len(c.forms)):
            limit = None if old is None else old if first_clause else old - sum(each)
            b = read_form(now, i + k, limit)
            if b is OVER or not isinstance(b, (int, float)):
                each = b
                break
            each.append(b)
        if each is OVER:
            tally(kept, 'new form not under the form cut' if first_clause else 'new forms not under the form cut in sum')
        elif each is None:
            tally(kept, 'new form with no bits')
        elif old is not None and first_clause and max(each) >= old:
            tally(kept, 'new form not under the form cut')
        elif old is not None and not first_clause and sum(each) >= old:
            tally(kept, 'new forms not under the form cut in sum')
        else:
            ranked.append((max(each), sum(each), c, now))
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
        step = dict(shape=c.shape, kind=ls[i].split()[0][1:], form=i, bits=old, text=ls[i], worst=new[1], sum=new[2], undrawn=new[0], forms=len(forms_of(nl)), rows_differ=differ, new=[[nl[k], nb[k]] for k in fresh], clause='worst' if new[1] < cur[1] - 1e-6 else 'undrawn' if new[0] < cur[0] else 'sum')
        return nl, new, nb, step
    return None


def report(row, ls, st, bits, steps, kept, done):
    kinds = {}
    for i in forms_of(ls):
        if isinstance(bits[i], (int, float)):
            kinds.setdefault(ls[i].split()[0][1:], []).append(bits[i])
    row.update(after=dict(forms=len(forms_of(ls)), worst=st[1], sum=st[2], undrawn=st[0], bits=[bits[i] if bits[i] != 'none' else None for i in forms_of(ls)], kinds=[ls[i].split()[0][1:] for i in forms_of(ls)]), steps=steps, kept_out=kept, reads=misses[0], seconds=round(time.time() - t0, 1), cpu=round(time.process_time() + F.OS.cpu, 1), times={k: round(v, 2) for k, v in times.items()}, counts=dict(counts, peak_read_session=F.OS.peak, peak_bar_session=CS.peak), finished=done, landed=bool(steps))
    if steps:
        row['program'] = '\n'.join(ls)
    print(json.dumps(row), flush=True)


def main():
    global GOLD
    row = dict(task=task, base_sha=hashlib.sha256('\n'.join(base_lines).encode()).hexdigest()[:16])
    ls = list(base_lines)
    cur, bits = state(ls)
    row['before'] = dict(forms=len(forms_of(ls)), worst=cur[1], sum=cur[2], undrawn=cur[0], bits=[bits[i] if bits[i] != 'none' else None for i in forms_of(ls)], kinds=[ls[i].split()[0][1:] for i in forms_of(ls)])
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
    failed = set()  # forms whose cuts all failed, in the form's own text and the worst it had to beat
    try:
        while True:
            tick()
            order = sorted((i for i in forms_of(ls) if bits[i] != 'none'), key=lambda i: -(bits[i] if bits[i] is not None else 1e9))
            got = None
            tried = 0
            for rank, i in enumerate(order):
                if tried >= TRY_FORMS:
                    break
                if (ls[i], cur) in failed:
                    tried += 1
                    continue
                tried += 1
                got = try_form(ls, i, cur, bits, kept)
                if got:
                    break
                failed.add((ls[i], cur))
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
