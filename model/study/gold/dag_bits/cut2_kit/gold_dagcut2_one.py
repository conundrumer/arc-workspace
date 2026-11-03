"""One stem of the DAG split cut, tool 2, version 2: tries splits of the stem's worst form over its body as a DAG (gold_dag_cuts.py). Every figure is read by `or_q.walk` of the pinned sampler (gold_pod_bits.read), the reader of the pod rows. Prints one JSON row after each landing and one at the end; the last row is the stem's row.

  <runtime python> gold_dagcut2_one.py TASK LINES.json [SECONDS]

Text. W is the working text: the start text with its OUT line last, then the text of each landing with its dead forms pruned. W is not put in normal form or in canonical text. Line numbers are indexes in the OUT-free list, as in the pod rows. The cuts of a target come from `canon[i]`, the canonical text of the target (or_q.canonical_lines), put in a copy of W.
Start figures. `BASE_ROWS[task]` (base-rows.json) holds the pod row of each form of the start text: its figure goes in MEMO if the form's scope_sha is the same and the form is not a `none` at `fcol`. DAG_START_READ=1 reads the whole start text instead.
Steps. As gold_dagcut_one: the target is the form with no bits, else the worst form, with ties to the least text. A candidate takes the reader's check, the screen (one order of each new form over its canonical scope, a limit of room plus DAG_SCREEN_SLACK), then the VERIFY best screened candidates take prune, the reader's check, the normal form (S.legal), the state on W', and the decode. The first cut that gains (S.gains) lands as a tentative step. A step lands from the state of the step before, tentative or committed.
Commit. A step commits where the state has fewer forms with no bits than the last commit, or as many and the worst form is DAG_MARGIN (default 3) bits under the last commit's. At a commit the working text goes to `handover`: the canonical forms sorted by (depth in the read graph, text), OUT last, then S.legal. The loop stops after DAG_TENTATIVE (default 3) tentative steps in a row. The stem's result is the last commit.
The bar. GOLD is read on the start text once. At each landing: S.reader_takes, S.legal, S.decoded(W', nf, GOLD). At each commit: S.decoded(C, N, GOLD) on the handover text; if it fails, `program` is the normal form of W and `program_fail` says why.
Rows. `before` and `after` read W. `after_reads` is `working`. `program` is N, whose figures are not W's.
Environment: DAG_MARGIN, DAG_TENTATIVE, DAG_SCREEN_SLACK, DAG_START_READ, POD_FORM_SECONDS (default 120), POD_ORDER_CAP, POD_BUDGET (gold_pod_bits.py).
"""
import ast, gc, itertools, json, os, sys, time
import gold_pod_bits as P
import gold_fork_reads as F
import gold_shapecut_one as S
import gold_dag_bits
from gold_dag_cuts import dag_candidates
import arclog, live, live_try, or_q, search
import form_orders as O

sha = P.sha
counts, times, timed, misses = F.counts, F.times, F.timed, F.misses
VERIFY = 3
SLACK = float(os.environ.get('DAG_SCREEN_SLACK', 8))
MARGIN = float(os.environ.get('DAG_MARGIN', 3))
TENTATIVE = int(os.environ.get('DAG_TENTATIVE', 3))
FORM_SECONDS = float(os.environ.get('POD_FORM_SECONDS', 120))
START_READ = os.environ.get('DAG_START_READ') == '1'
EPS = 1e-6
BASE_ROWS = {}  # task -> {base_sha, forms: [[line, bits, status, scope_sha, fcol], ...]}; set by the runner
CANON = {}  # (form text, its canonical scope) -> (its canonical text, 1 if it kept its text)
MEMO = {}  # (scope tuple, form text) -> (bits, status); bits is a number, None for no bits, or 'none' for a kind with no draw
RETRY = {}  # form text -> 'bits' or 'none': the form was read again with the field order of the tokens
LAST = {}  # form text -> the last bits read
SESS = GOLD = None
STARTED = False  # the start text's reads are not under the time limit
WALKED = {}  # the rows of the last S.walk


def load_sampler():
    P.load_sampler()
    F.sampler = P.sampler


def setup(stem, lines_path, seconds=840):
    global SESS
    S.setup(stem, lines_path, seconds)
    SESS = live_try.session_of(S.task)[0]


def keep_walk(walk):
    def walked(ls):
        got = walk(ls)
        WALKED['rows'] = got
        return got
    return walked


S.walk = keep_walk(S.walk)


def body_of(W):
    return [x for x in W if not x.startswith('(OUT')]


def canon_lines(lines, sess):
    """or_q.canonical_lines with one answer per (form text, scope), so that a program one form away from a known one costs only its new forms and their readers."""
    out, kept = list(lines), 0
    parsed = live.S.strata.sexprs('\n'.join(lines))
    size = {i: len(live.S.ancestor_order(parsed, i)) for i in range(len(lines))}
    for i in sorted(range(len(lines)), key=lambda i: size[i]):
        kind = lines[i].split()[0].lstrip('(')
        if kind not in live.KIND_TOK:
            continue
        scope = [out[j] for j in live.S.ancestor_order(parsed, i)]
        key = (lines[i], tuple(scope))
        if key not in CANON:
            check, form = or_q.decoder_check(sess, scope, kind), O.Form(or_q.sorted_fields(lines[i], sess, scope))
            got = None
            for order in itertools.islice(form.orders(), or_q.CANON_TRIES):
                res = check(form.text(order))
                if res is None:
                    got = form.text(order)
                    break
                if res[0].startswith(O.RULE_REASONS):
                    form.refuse(order, res[1])
            CANON[key] = (got, 0) if got is not None else (lines[i], 1)
        out[i], k = CANON[key]
        kept += k
        parsed[i] = live.S.strata.sexprs(out[i])[0]
    return out, kept


def screen(task, scope, target, kind, limit):
    """The bits of the one order `target` over scope on a new session: a number, None for no bits, or F.OVER where the bits reach limit."""
    try:
        gc.collect()
        sess, task_json, _ = live_try.session_of(task)
        run = or_q.GuidedRun(P.sampler.pri, sess, time.monotonic() + 60, task_json, live.Limits(form_tries=1))
        dec, pg = run.scope(scope)
        g = run.rng = F.Guide(run, or_q.gold_rest(sess, scope, target, kind), kind, limit)
    except Exception:  # noqa: BLE001
        return None
    dead = None
    try:
        run.form(pg, dec, kind)
        if kind in or_q.FORMS and all(t == live.SKIP_TOK for t in g.rest):
            g.rest.clear()
    except or_q.Stuck:
        pass
    except search.Dead as e:
        dead = str(e) or 'dead'
    except Exception as e:  # noqa: BLE001
        dead = type(e).__name__
    except F.Over:
        return F.OVER
    except F.NoBits:
        return None
    return None if dead is not None or g.rest else round(sum(g.parts.values()), 2)


def fcol(f):
    return f['status'] == 'none' and any('fcol' in str(b) for b in f.get('bad') or ())


def read(body, canon, i):
    """(bits, status) of form i of body, by or_q.walk over the canonical scope of canon, behind MEMO. Where the walk gives no bits at `fcol`, the form is read once more with its fields in the order of its tokens (gold_dag_bits.portsort), for that call only."""
    kind = body[i].split()[0][1:]
    if kind not in live.KIND_TOK:
        return 'none', 'no draw'
    scope = or_q.canonical_scope(canon, i)
    key = (tuple(scope), body[i])
    if key in MEMO:
        counts['dag reads memoized'] += 1
        return MEMO[key]
    if STARTED:
        S.tick()
    counts['dag reads'] += 1
    left = S.SECONDS - (time.time() - S.t0)
    seconds = min(FORM_SECONDS, max(left, 1.0))
    f = P.read(P.sampler, S.task, body, i, canon, seconds)
    if fcol(f):
        counts['fields retried'] += 1
        was = or_q.sorted_fields
        or_q.sorted_fields = lambda text, sess, scope: gold_dag_bits.portsort(scope, text)
        try:
            f = P.read(P.sampler, S.task, body, i, canon, seconds)
        finally:
            or_q.sorted_fields = was
        RETRY[body[i]] = 'bits' if f['bits'] is not None else 'none'
        if f['bits'] is not None:
            counts['fields retried with bits'] += 1
    got = MEMO[key] = (f['bits'], f['status'])
    LAST[body[i]] = f['bits']
    return got


def preload(body, canon):
    """Puts the start text's figures from the pod row in MEMO. A form with another scope_sha, or a `none` at fcol, is read again."""
    by = {f[0]: f for f in BASE_ROWS[S.task]['forms']}
    for i, text in enumerate(body):
        if text.split()[0][1:] not in live.KIND_TOK:
            continue
        scope = or_q.canonical_scope(canon, i)
        f = by.get(i)
        if f is None or P.sha(scope) != f[3] or f[4]:
            counts['start forms read again'] += 1
            continue
        MEMO[(tuple(scope), text)] = (f[1], f[2])
        LAST[text] = f[1]
        counts['start forms from the pod row'] += 1


def read_order(body, canon, first):
    """The order of the reads of a state: `first`, then forms with a MEMO hit, then the rest by last known bits, largest first."""
    first = list(first)
    rest = [i for i in S.forms_of(body) if i not in first]
    hit = [i for i in rest if body[i].split()[0][1:] not in live.KIND_TOK or (tuple(or_q.canonical_scope(canon, i)), body[i]) in MEMO]
    miss = [i for i in rest if i not in hit]

    def key(i):
        if body[i] not in LAST:
            return (1, 0, i)
        b = LAST[body[i]]
        return (0, -1e9 if b is None else -b, i)
    return first + hit + sorted(miss, key=key)


def dag_state(W, cur=None, first=()):
    """(state, bits, status) of W: state is (forms with no bits, landing value, sum). With the state cur it stops and gives (None, None, None) at the first read that shows W cannot gain over cur, as gold_shapecut_one.state does."""
    body = body_of(W)
    canon = canon_lines(body, SESS)[0]
    bits, status, got, undrawn = {}, {}, [], 0
    for i in read_order(body, canon, first):
        b, s = read(body, canon, i)
        bits[i], status[i] = b, s
        if isinstance(b, (int, float)):
            got.append(b)
        elif b is None:
            undrawn += 1
        if cur is not None and (undrawn > cur[0] or (undrawn == cur[0] and got and (S.landing(got) > cur[1] + EPS or (S.landing(got) >= cur[1] - EPS and sum(got) >= cur[2] + F.MARGIN)))):
            counts['states stopped'] += 1
            return None, None, None
    return (undrawn, S.landing(got), round(sum(got), 2)), bits, status


def target_of(bits, body):
    """The form with no bits that has the least text, else the worst form, with ties to the least text."""
    no = [i for i, b in bits.items() if b is None]
    if no:
        return min(no, key=lambda i: (body[i], i))
    num = [(b, i) for i, b in bits.items() if isinstance(b, (int, float))]
    if not num:
        return None
    top = max(b for b, _ in num)
    return min((i for b, i in num if b == top), key=lambda i: (body[i], i))


def commits(new, base, margin=None):
    """Whether the state new commits over the state base of the last commit: fewer forms with no bits, or as many and a worst form `margin` bits lower."""
    margin = MARGIN if margin is None else margin
    return new[0] < base[0] or (new[0] == base[0] and base[1] - new[1] >= margin - EPS)


class Chain:
    """The commit rule over the states of the steps in order."""

    def __init__(self, base, margin=None, tentative=None):
        self.base, self.run = base, 0
        self.margin = MARGIN if margin is None else margin
        self.tentative = TENTATIVE if tentative is None else tentative

    def land(self, new):
        """Takes the state of a landed step. Whether it commits."""
        if commits(new, self.base, self.margin):
            self.base, self.run = new, 0
            return True
        self.run += 1
        return False

    def stop(self):
        return self.run >= self.tentative


def tally(t, k):
    t[k] = t.get(k, 0) + 1


def largest(bits):
    return max((b for b in bits.values() if isinstance(b, (int, float))), default=0)


def rows_norm(rows):
    """The OUT rows with each row parsed and its cells sorted."""
    out = {}
    for k, v in rows.items():
        got = []
        for r in v:
            try:
                t = ast.literal_eval(r)
                got.append(tuple(sorted(t, key=repr)) if isinstance(t, (tuple, list)) else t)
            except Exception:  # noqa: BLE001
                got.append(r)
        out[k] = sorted(got, key=repr)
    return out


def rows_flags(differ):
    """(rows_differ, rows_columns) from the plain compare of S.decoded and the compare of sorted cells."""
    if differ is None:
        return None, None
    if not differ:
        return False, False
    try:
        same = rows_norm(WALKED['rows']) == rows_norm(GOLD['rows'])
    except Exception:  # noqa: BLE001
        return True, False
    return (not same), same


def try_target(W, i, cur, bits, kept):
    """The first cut of form i, best estimate first, that passes the bar and gains. Returns (W', state, bits, status, step, nf) or None."""
    body = body_of(W)
    canon = canon_lines(body, SESS)[0]
    was = S.dead(W)
    old = bits[i]
    top = None if old is None else S.landing([old])
    moves = old is None or S.landing([b for k, b in bits.items() if k != i and isinstance(b, (int, float))]) < cur[1] - EPS
    ranked = []
    with timed('candidates'):
        cuts = dag_candidates(W[:i] + [canon[i]] + W[i + 1:], i, old)
    nsplit = sum(c.rank is not None for c in cuts)
    for c in cuts:
        S.tick()
        now = W[:i] + c.forms + W[i + 1:]
        if not S.reader_takes(now, i + len(c.forms) - 1):
            tally(kept, 'refused by the reader')
            continue
        cnow = canon_lines(body_of(now), SESS)[0]
        each = []
        for k in range(len(c.forms)):
            j = i + k
            kind = cnow[j].split()[0][1:]
            limit = None if old is None else S.room(each, top) if moves else old - sum(each)
            b = screen(S.task, or_q.canonical_scope(cnow, j), cnow[j], kind, None if limit is None else limit + SLACK)
            if b is F.OVER or not isinstance(b, (int, float)):
                each = b
                break
            each.append(b)
        if each is F.OVER:
            tally(kept, 'new forms not under the form cut')
        elif each is None:
            tally(kept, 'new form with no bits')
        elif old is not None and (S.landing(each) >= top + SLACK if moves else sum(each) >= old + SLACK):
            tally(kept, 'new forms not under the form cut')
        else:
            ranked.append((S.landing(each), sum(each), c, now))
    ranked.sort(key=lambda r: (r[0], r[1], '\n'.join(r[2].forms)))
    screened = [[c.rank, c.shape, round(l, 2), round(m, 2)] for l, m, c, _ in ranked[:VERIFY]]
    for _, _, c, now in ranked[:VERIFY]:
        S.tick()
        now = S.prune(now, was)
        if not S.reader_takes(now, len(body_of(now)) - 1):
            tally(kept, 'refused by the reader')
            continue
        nl, why = S.legal(now)
        if nl is None:
            tally(kept, why)
            continue
        fresh = [k for k, x in enumerate(now) if x in c.forms]
        new, nb, nst = dag_state(now, cur, fresh)
        if new is None or not S.gains(new, cur):
            tally(kept, 'no gain on the whole stem')
            continue
        if any(not isinstance(nb.get(k), (int, float)) for k in fresh):
            tally(kept, 'new form with no bits')
            continue
        differ, why = S.decoded(now, nl, GOLD)
        if why:
            tally(kept, why)
            continue
        rows_differ, rows_columns = rows_flags(differ)
        step = dict(shape=c.shape, screened=screened, rank=c.rank, est=c.est, splits=nsplit, atoms=c.atoms, sites=c.sites, kind=W[i].split()[0][1:], form=i, bits=old, text=W[i], worst=largest(nb), score=new[1], sum=new[2], undrawn=new[0], forms=len(S.forms_of(now)),
                    rows_differ=rows_differ, rows_columns=rows_columns, new=[[now[k], nb[k], nst[k]] for k in fresh], clause='score' if new[1] < cur[1] - EPS else 'undrawn' if new[0] < cur[0] else 'sum')
        return now, new, nb, nst, step, nl
    return None


def topo(canon):
    """The canonical forms sorted by (depth in the read graph, text)."""
    forms = live.S.strata.sexprs('\n'.join(canon))
    heads = {f[1]: j for j, f in enumerate(forms) if len(f) > 1 and isinstance(f[1], str) and f[1].startswith('&')}
    depth = {}

    def d(j):
        if j not in depth:
            depth[j] = 1 + max((d(heads[r]) for r in live.S.strata.reads_of(forms[j][2:], set()) - {forms[j][1]} if r in heads), default=0)
        return depth[j]
    return [canon[j] for j in sorted(range(len(canon)), key=lambda j: (d(j), canon[j]))]


def handover(W, nf):
    """(program lines, why not): N, the normal form of the sorted canonical text C of W, where S.legal and the decode of C and N hold; else the normal form nf of W, and why."""
    body, out = body_of(W), [x for x in W if x.startswith('(OUT')]
    try:
        C = topo(canon_lines(body, SESS)[0]) + out
        N, why = S.legal(C)
        if N is None:
            return nf, 'handover: ' + str(why)
        _, why = S.decoded(C, N, GOLD)
        if why:
            return nf, 'handover: ' + str(why)
        return N, None
    except S.Late:
        raise
    except Exception as e:  # noqa: BLE001
        return nf, 'handover: %s' % type(e).__name__


def block(W, st, bits, status):
    body = body_of(W)
    idx = S.forms_of(W)
    w = target_of(bits, body)
    return dict(forms=len(idx), worst=largest(bits), worst_line=w, worst_status=status.get(w), score=st[1], sum=st[2], undrawn=st[0], bits=[bits[i] if bits[i] != 'none' else None for i in idx], status=[status[i] for i in idx], kinds=[W[i].split()[0][1:] for i in idx],
                fields_retry=[RETRY.get(W[i]) for i in idx])


def report(row, done):
    row.update(reads=misses[0], seconds=round(time.time() - S.t0, 1), cpu=round(time.process_time() + F.OS.cpu, 1), times={k: round(v, 2) for k, v in times.items()},
               counts=dict(counts, peak_read_session=F.OS.peak), start_forms_read_again=counts['start forms read again'], finished=done)
    print(json.dumps(row), flush=True)


def main():
    global GOLD, STARTED
    base_lines = S.base_lines
    W = body_of(base_lines) + [x for x in base_lines if x.startswith('(OUT')]
    row = dict(task=S.task, base_sha=sha(base_lines), cap=P.CAP, budget=P.BUDGET, form_seconds=FORM_SECONDS, margin=MARGIN, tentative=TENTATIVE, verify=VERIFY, slack=SLACK, after_reads='working', landed=False, skipped=None, program_fail=None)
    entry = BASE_ROWS.get(S.task)
    if not START_READ and (entry is None or entry.get('base_sha') != row['base_sha']):
        row.update(skipped='no pod row for this text', steps=[], kept_out={}, commit=dict(step=None, count=0), cpu=round(time.process_time(), 1), counts=dict(counts), finished=True)
        print(json.dumps(row), flush=True)
        return
    body = body_of(W)
    if not START_READ:
        preload(body, canon_lines(body, SESS)[0])
    cur, bits, status = dag_state(W)
    row['before'] = block(W, cur, bits, status)
    row['after'] = row['before']
    steps, kept = [], {}
    row.update(steps=steps, kept_out=kept, commit=dict(step=None, count=0), tentative_after=None)
    report(row, False)  # the start text's figures stand if a cap ends the stem in its own reads
    try:
        ended, att = S.direct('\n'.join(W))
        row['base_ended'] = ended
    except (arclog.Refusal, arclog.Fault) as e:
        row.update(base_ended=False, base_fault=type(e).__name__ + ' ' + str(e)[:160])
        ended = False
    if not ended:
        report(row, True)
        return
    try:
        rows = S.walk(W)
    except Exception as e:  # noqa: BLE001
        rows = None
        row['base_rows'] = type(e).__name__ + ' ' + str(e)[:160]
    GOLD = dict(attempts=att, rows=rows)
    STARTED = True
    chain = Chain(cur)
    try:
        while True:
            S.tick()
            i = target_of(bits, body_of(W))
            if i is None:
                break
            got = try_target(W, i, cur, bits, kept)
            if not got:
                break
            W, cur, bits, status, step, nf = got
            steps.append(step)
            step['working'] = '\n'.join(W)
            step['committed'] = chain.land(cur)
            if step['committed']:
                program, why = handover(W, nf)
                row.update(after=block(W, cur, bits, status), working='\n'.join(W), program='\n'.join(program), program_fail=why, landed=True, commit=dict(step=len(steps) - 1, count=row['commit']['count'] + 1), tentative_after=None)
            else:
                row['tentative_after'] = block(W, cur, bits, status)
            report(row, False)
            if chain.stop():
                break
    except S.Late:
        row['late'] = True
    report(row, True)


if __name__ == '__main__':
    if os.environ.get('DAG_BASE_ROWS'):
        BASE_ROWS.update(json.load(open(os.environ['DAG_BASE_ROWS'])))
    load_sampler()
    setup(*sys.argv[1:4])
    main()
