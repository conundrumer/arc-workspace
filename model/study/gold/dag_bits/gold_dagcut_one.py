"""One stem of the DAG split cut, tool 2: tries splits of the stem's worst form over its body as a DAG (gold_dag_cuts.py), and keeps a split only where the bar on the program holds and the stem's landing value falls. Prints one JSON row after each landing and one at the end; the last row is the stem's row.

  <runtime python> gold_dagcut_one.py TASK LINES.json [SECONDS]

LINES.json maps the stem to its forms, the start text. Every bits figure here is tool 1's (gold_dag_bits.py): the sum over a form's valid atom orders, over the form's canonical scope. `read(ls, canon, i)` is the one function that reads a form's reported bits, so that the order-free reader can be swapped there.
Steps. The target is the form with no bits if there is one, else the worst form. Only the target is tried in a step. Its candidates (gold_dag_cuts.dag_candidates), best estimate first, each take: the reader's check of the text; the screen, one walk of the canonical order of each new form over the canonical scope of the whole new program (a fork read, gold_fork_reads.py), with the limit of gold_shapecut_one.room plus DAG_SCREEN_SLACK bits, since one order's bits are an upper bound on the order sum; the landing read of the VERIFY best screened candidates, tool 1's figure on every form that the cut changes; then prune, legal and decoded of gold_shapecut_one.py. The first check that fails ends the cut. The first cut that gains (gold_shapecut_one.gains: fewer forms with no bits, else the worst form falls, else the sum falls) lands. The loop repeats from the new state, and stops where no cut of the target lands. LANDING is `worst` and BAR plays no part.
The bar is the shape stage's: table work cap 2^20 in the Closed world, on train and test; attempts equal the start text's on every test input; OUT rows equal by column label, or rows_differ true where attempts and train Consistent hold; the normal form is a fixed point of the round trip.
Environment: DAG_ORDER_CAP and DAG_DELTA (tool 1's, which set the reads), DAG_LAND_CAP (the order cap of every tool 1 read here, default DAG_ORDER_CAP), DAG_SCREEN_SLACK (default 8), DAG_BASE_ROWS (a glob of tool 1 rows: a finished row with the start text's base_sha, cap and delta gives the start text's figures without a read).
A row: task, base_sha, cap, delta, before and after (forms, worst, worst_line, worst_status, score, sum, undrawn, bits, status, kinds), steps (shape, rank and est of the landed cut, splits, text, bits, new forms with their bits and status, program), kept_out, cpu, counts, finished. The row streams, so a kill keeps the last landing.
"""
import glob, hashlib, json, os, sys, time
import gold_dag_bits as B
import gold_fork_reads as F
from gold_fork_reads import MARGIN, OVER, counts, load_sampler, misses, times, timed
import arclog, live
import gold_shapecut_one as S
from gold_dag_cuts import dag_candidates

SLACK = float(os.environ.get('DAG_SCREEN_SLACK', 8))
VERIFY = S.VERIFY
if os.environ.get('DAG_LAND_CAP'):
    B.CAP = int(os.environ['DAG_LAND_CAP'])
MEMO = {}  # (canonical scope, form text) -> (bits, status); bits is a number, None for no bits, or 'none' for a kind with no draw
GOLD = None
STARTED = False  # the start text's reads are not under the time limit


def read(ls, canon, i):
    """(bits, status) of form i of ls by tool 1, over the canonical scope of canon. The one reader of reported bits."""
    kind = ls[i].split()[0][1:]
    if kind not in live.KIND_TOK:
        return 'none', 'no draw'
    scope = B.scope_of(canon, i)
    key = (tuple(scope), ls[i])
    if key in MEMO:
        counts['dag reads memoized'] += 1
        return MEMO[key]
    if STARTED:
        S.tick()
    counts['dag reads'] += 1
    f = B.Form(ls, i, scope)
    f.plan()
    f.first()
    if f.error is None:
        try:
            f.orders()
        except Exception as e:  # noqa: BLE001
            f.error = '%s: %s' % (type(e).__name__, str(e)[:100])
    if f.status is None:
        f.status = 'written' if f.written is not None else 'none'
    r = f.row()
    got = MEMO[key] = (r['bits'], f.status)
    return got


def dag_state(ls, cur=None, first=()):
    """(state, bits, status) of ls: state is (forms with no bits, landing value, sum). With the state cur it stops and gives (None, None, None) at the first read that shows ls cannot gain over cur, as gold_shapecut_one.state does. The forms in first are read before the others."""
    canon = B.canonical(ls)[0]
    bits, status, got, undrawn = {}, {}, [], 0
    idx = list(first) + [i for i in S.forms_of(ls) if i not in first]
    for i in idx:
        b, s = read(ls, canon, i)
        bits[i], status[i] = b, s
        if isinstance(b, (int, float)):
            got.append(b)
        elif b is None:
            undrawn += 1
        if cur is not None and (undrawn > cur[0] or (undrawn == cur[0] and got and (S.landing(got) > cur[1] + 1e-6 or (S.landing(got) >= cur[1] - 1e-6 and sum(got) >= cur[2] + MARGIN)))):
            counts['states stopped'] += 1
            return None, None, None
    return (undrawn, S.landing(got), round(sum(got), 2)), bits, status


def base_rows(sha):
    """The finished tool 1 row of the start text, or None."""
    for p in glob.glob(os.environ.get('DAG_BASE_ROWS', '/nonexistent*')):
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get('task') == S.task and r.get('base_sha') == sha and r.get('finished') and not r.get('late') and r.get('cap') == B.CAP and float(r.get('delta')) == float(B.DELTA) and not r.get('error'):
                return r
    return None


def preload(ls, sha):
    """Puts the start text's figures from a tool 1 row in MEMO. Returns whether it did."""
    r = base_rows(sha)
    if r is None:
        return False
    canon = B.canonical(ls)[0]
    by = {f['line']: f for f in r['forms']}
    for i in S.forms_of(ls):
        f = by.get(i)
        if f is None:
            return False
        kind = ls[i].split()[0][1:]
        MEMO[(tuple(B.scope_of(canon, i)), ls[i])] = ('none', 'no draw') if kind not in live.KIND_TOK else (f['bits'], f['status'])
    counts['start text read from a tool 1 row'] += 1
    return True


def screen(canon, j, limit):
    """The walk of the canonical order of form j of the program canon, over its canonical scope: bits, None, or OVER."""
    kind = canon[j].split()[0][1:]
    try:
        got, _ = F.walked(B.scope_of(canon, j), canon[j], kind, limit)
    except Exception:  # noqa: BLE001
        return None
    return got


def tally(t, k):
    t[k] = t.get(k, 0) + 1


def largest(bits):
    return max((b for b in bits.values() if isinstance(b, (int, float))), default=0)


def target_of(bits):
    """The form with no bits, else the worst form."""
    no = [i for i, b in bits.items() if b is None]
    if no:
        return min(no)
    num = [(b, -i) for i, b in bits.items() if isinstance(b, (int, float))]
    return -max(num)[1] if num else None


def try_target(ls, i, cur, bits, kept):
    """The first cut of form i, best estimate first, that passes the bar and gains. Returns (lines, state, bits, status, step) or None."""
    was = S.dead(ls)
    old = bits[i]
    top = None if old is None else S.landing([old])
    moves = old is None or S.landing([b for k, b in bits.items() if k != i and isinstance(b, (int, float))]) < cur[1] - 1e-6
    ranked = []
    with timed('candidates'):
        cuts = dag_candidates(ls, i, old)
    nsplit = sum(c.rank is not None for c in cuts)
    for c in cuts:
        S.tick()
        now = ls[:i] + c.forms + ls[i + 1:]
        if not S.reader_takes(now, i + len(c.forms) - 1):
            tally(kept, 'refused by the reader')
            continue
        canon = B.canonical(now)[0]
        each = []
        for k in range(len(c.forms)):
            limit = None if old is None else S.room(each, top) if moves else old - sum(each)
            b = screen(canon, i + k, None if limit is None else limit + SLACK)
            if b is OVER or not isinstance(b, (int, float)):
                each = b
                break
            each.append(b)
        if each is OVER:
            tally(kept, 'new forms not under the form cut')
        elif each is None:
            tally(kept, 'new form with no bits')
        elif old is not None and (S.landing(each) >= top + SLACK if moves else sum(each) >= old + SLACK):
            tally(kept, 'new forms not under the form cut')
        else:
            ranked.append((S.landing(each), sum(each), c, now))
    ranked.sort(key=lambda r: r[:2])
    screened = [[c.rank, c.shape, round(l, 2), round(m, 2)] for l, m, c, _ in ranked[:VERIFY]]
    for _, _, c, now in ranked[:VERIFY]:
        S.tick()
        now = S.prune(now, was)
        nl, why = S.legal(now)
        if nl is None:
            tally(kept, why)
            continue
        fresh = [k for k in S.forms_of(nl) if i <= k < i + len(c.forms)]
        new, nb, nst = dag_state(nl, cur, fresh)
        if new is None or not S.gains(new, cur):
            tally(kept, 'no gain on the whole stem')
            continue
        if any(not isinstance(nb.get(k), (int, float)) for k in fresh):
            tally(kept, 'new form with no bits in normal form')
            continue
        differ, why = S.decoded(now, nl, GOLD)
        if why:
            tally(kept, why)
            continue
        step = dict(shape=c.shape, screened=screened, rank=c.rank, est=c.est, splits=nsplit, atoms=c.atoms, sites=c.sites, kind=ls[i].split()[0][1:], form=i, bits=old, text=ls[i], worst=largest(nb), score=new[1], sum=new[2], undrawn=new[0], forms=len(S.forms_of(nl)), rows_differ=differ,
                    new=[[nl[k], nb[k], nst[k]] for k in fresh], clause='score' if new[1] < cur[1] - 1e-6 else 'undrawn' if new[0] < cur[0] else 'sum')
        return nl, new, nb, nst, step
    return None


def block(ls, st, bits, status):
    idx = S.forms_of(ls)
    w = target_of(bits)
    return dict(forms=len(idx), worst=largest(bits), worst_line=w, worst_status=status.get(w), score=st[1], sum=st[2], undrawn=st[0], bits=[bits[i] if bits[i] != 'none' else None for i in idx], status=[status[i] for i in idx], kinds=[ls[i].split()[0][1:] for i in idx])


def report(row, ls, st, bits, status, steps, kept, done):
    row.update(after=block(ls, st, bits, status), steps=steps, kept_out=kept, reads=misses[0], seconds=round(time.time() - S.t0, 1), cpu=round(time.process_time() + F.OS.cpu, 1), times={k: round(v, 2) for k, v in times.items()}, counts=dict(counts, peak_read_session=F.OS.peak), finished=done, landed=bool(steps))
    if steps:
        row['program'] = '\n'.join(ls)
    print(json.dumps(row), flush=True)


def setup(stem, lines_path, seconds=840):
    S.setup(stem, lines_path, seconds)


def main():
    global GOLD, STARTED
    base_lines = S.base_lines
    sha = hashlib.sha256('\n'.join(base_lines).encode()).hexdigest()[:16]
    row = dict(task=S.task, base_sha=sha, cap=B.CAP, delta=B.DELTA, slack=SLACK, verify=VERIFY)
    ls = list(base_lines)
    row['start_from_row'] = preload(ls, sha)
    cur, bits, status = dag_state(ls)
    row['before'] = block(ls, cur, bits, status)
    steps, kept = [], {}
    report(row, ls, cur, bits, status, steps, kept, False)  # the start text's figures stand if a cap ends the stem in its own reads
    try:
        ended, att = S.direct('\n'.join(ls))
        row['base_ended'] = ended
    except (arclog.Refusal, arclog.Fault) as e:
        row.update(base_ended=False, base_fault=type(e).__name__ + ' ' + str(e)[:160])
        ended = False
    if not ended:
        report(row, ls, cur, bits, status, steps, kept, True)
        return
    try:
        rows = S.walk(ls)
    except Exception as e:  # noqa: BLE001
        rows = None
        row['base_rows'] = type(e).__name__ + ' ' + str(e)[:160]
    GOLD = dict(attempts=att, rows=rows)
    STARTED = True
    try:
        while True:
            S.tick()
            i = target_of(bits)
            if i is None:
                break
            got = try_target(ls, i, cur, bits, kept)
            if not got:
                break
            ls, cur, bits, status, step = got
            steps.append(step)
            step['program'] = '\n'.join(ls)
            report(row, ls, cur, bits, status, steps, kept, False)
    except S.Late:
        row['late'] = True
    report(row, ls, cur, bits, status, steps, kept, True)


if __name__ == '__main__':
    load_sampler()
    setup(*sys.argv[1:4])
    main()
