"""Bar commit over the rows of the narrowing stage (gold_dagcut2_one.py).

  gold_narrow_env.sh bar_commit.py ROWS_GLOB LINES.json OUT.jsonl [--stems a,b] [--margin 3] [--tentative 3] [--bars 32,28,25,21.5] [--stem-seconds 3600] [--list]

ROWS_GLOB is a quoted glob of rows-*.jsonl files. Per stem the row with the most steps is used (rows are streamed, so an unfinished row counts for its steps so far). LINES.json maps the stem to its start text (the one that the stage ran on). OUT.jsonl gets one row per decided step, flushed at once; a step already decided in OUT (same stem, step index and working text) is skipped. A row with decision `error` does not count as decided.

Steps. The commit rule of the stage is replayed at --margin over the recorded states of the steps (the stage's `commits`, `Chain`): a step that commits is not a candidate. Steps after --tentative tentative steps in a row are left out, as the stage would have stopped. A candidate step is one whose working worst (step `worst`) is under a bar that the start's worst (`before.worst`) is not under.

Rule. The handover text of the step is rebuilt as the stage builds it at a commit (`handover(W, nf)` of gold_dagcut2_one.py, on the step's recorded `working` text and S.legal of it). Its forms are read by the stage's own `read` (gold_pod_bits.read, or_q.walk), form by form, over the canonical scope of the handover text. A read stops once a form is at or over the highest bar that the start is not under: no bar can hold then.
  bars    = the bars b with handover worst < b <= start worst
  noise   = |handover worst - working worst of the step|
  commit  = bars is not empty, no more forms with no bits than the step's, and (start worst - handover worst) > noise
  bar     = the lowest of bars

--list prints the candidate steps and their form counts, and loads nothing heavy.
"""
import argparse, glob, hashlib, json, os, signal, sys, time, warnings

EPS = 1e-6
READER = 'gold_dagcut2_one.read (gold_pod_bits.read, or_q.walk)'
CHILD = None


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def latest_rows(pattern):
    """task -> the row with most steps (the later one on a tie), over the files of the glob."""
    best = {}
    for p in sorted(glob.glob(pattern)):
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if 'steps' not in r or 'before' not in r:
                continue
            if r['task'] not in best or len(r['steps']) >= len(best[r['task']]['steps']):
                best[r['task']] = r
    return best


def commits(new, base, margin):
    return new[0] < base[0] or (new[0] == base[0] and base[1] - new[1] >= margin - EPS)


def candidates(row, margin, tentative, bars):
    """[(step index, step, bars crossed by the working worst)] of a row."""
    b = row['before']
    start = b['worst']
    base, run, out = (b['undrawn'], b['score'], b['sum']), 0, []
    for j, s in enumerate(row['steps']):
        new = (s['undrawn'], s['score'], s['sum'])
        if commits(new, base, margin):
            base, run = new, 0
            continue
        run += 1
        crossed = [x for x in bars if s['worst'] < x <= start]
        if crossed:
            out.append((j, s, crossed))
        if run >= tentative:
            break
    return out


def decided(out):
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get('decision') in ('commit', 'no'):
                done.add((r['task'], r['step'], r['working_sha']))
    return done


def emit(f, row):
    f.write(json.dumps(row) + '\n')
    f.flush()


def work(task, lines_path, row, todo, out, args):
    """The decisions of the steps in todo, in this process (a fork of the one that loaded the sampler)."""
    import gold_dagcut2_one as D
    D.setup(task, lines_path, args.stem_seconds)
    start = row['before']['worst']
    top = max(x for x in args.bars if x <= start)
    f = open(out, 'a')

    def base(j, s):
        return dict(task=task, step=j, working_sha=sha(s['working']), start_worst=start, working_worst=s['worst'], margin=args.margin, committed_row=s.get('committed'), base_sha=row['base_sha'], reader=READER)

    if D.sha(D.S.base_lines) != row['base_sha']:
        for j, s, _ in todo:
            emit(f, dict(base(j, s), decision='error', reason='the start text of LINES.json is not the row base_sha'))
        return
    W0 = D.body_of(D.S.base_lines) + [x for x in D.S.base_lines if x.startswith('(OUT')]
    ended, att = D.S.direct('\n'.join(W0))
    if not ended:
        for j, s, _ in todo:
            emit(f, dict(base(j, s), decision='error', reason='start text does not end'))
        return
    try:
        rows = D.S.walk(W0)
    except Exception:  # noqa: BLE001
        rows = None
    D.GOLD = dict(attempts=att, rows=rows)
    D.STARTED = False
    for j, s, crossed in todo:
        t = time.time()
        r = dict(base(j, s), bars_working=crossed, undrawn_working=s['undrawn'])
        try:
            W = s['working'].split('\n')
            nf, why = D.S.legal(W)
            if nf is None:
                emit(f, dict(r, decision='error', reason='S.legal of the working text: %s' % why))
                continue
            program, why = D.handover(W, nf)
            if why:
                emit(f, dict(r, decision='no', reason=why, handover_worst=None, noise=None, bar=None, bars=[]))
                continue
            body = D.body_of(program)
            canon = D.canon_lines(body, D.SESS)[0]
            n0 = D.counts['dag reads']
            bits, undrawn, over = [], 0, None
            for i in D.S.forms_of(body):
                b, st = D.read(body, canon, i)
                if isinstance(b, (int, float)):
                    bits.append(b)
                    if b >= top:
                        over = b
                        break
                elif b is None:
                    undrawn += 1
            r.update(handover_forms=len(D.S.forms_of(body)), forms_read=len(bits) + undrawn, reads=D.counts['dag reads'] - n0, undrawn_handover=undrawn, handover_bits=bits, seconds=round(time.time() - t, 1))
            if over is not None:
                emit(f, dict(r, decision='no', reason='a handover form is at or over %s, the highest bar that the start is not under' % top, handover_worst=None, handover_worst_at_least=over, noise=None, bar=None, bars=[]))
                continue
            hw = max(bits, default=0)
            bars = [x for x in args.bars if hw < x <= start]
            noise, drop = abs(hw - s['worst']), start - hw
            r.update(handover_worst=hw, noise=round(noise, 3), drop=round(drop, 3), bars=bars, bar=min(bars) if bars else None)
            if not bars:
                emit(f, dict(r, decision='no', reason='handover worst is under no bar that the start is not under'))
            elif undrawn > s['undrawn']:
                emit(f, dict(r, decision='no', reason='handover text has more forms with no bits than the working text'))
            elif drop > noise:
                emit(f, dict(r, decision='commit', reason='drop over noise', handover_text='\n'.join(program)))
            else:
                emit(f, dict(r, decision='no', reason='drop not over noise'))
        except Exception as e:  # noqa: BLE001
            emit(f, dict(r, decision='error', reason='%s: %s' % (type(e).__name__, str(e)[:200])))


def run_child(task, lines_path, row, todo, out, args):
    global CHILD
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            work(task, lines_path, row, todo, out, args)
            code = 0
        except BaseException:  # noqa: BLE001
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            os._exit(code)
    CHILD = pid
    t = time.time()
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            CHILD = None
            return os.waitstatus_to_exitcode(status)
        if time.time() - t > args.stem_seconds + 60:
            os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)


def on_term(*_):
    if CHILD:
        try:
            os.kill(CHILD, signal.SIGKILL)
        except ProcessLookupError:
            pass
    os._exit(143)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rows')
    ap.add_argument('lines')
    ap.add_argument('out')
    ap.add_argument('--stems', default='')
    ap.add_argument('--margin', type=float, default=3.0)
    ap.add_argument('--tentative', type=int, default=3)
    ap.add_argument('--bars', default='32,28,25,21.5')
    ap.add_argument('--stem-seconds', type=float, default=3600.0)
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()
    args.bars = sorted(float(x) for x in args.bars.split(','))
    args.rows, args.lines, args.out = (os.path.abspath(x) for x in (args.rows, args.lines, args.out))
    only = {x for x in args.stems.split(',') if x}
    rows = latest_rows(args.rows)
    done = decided(args.out)
    plan = []
    for task in sorted(rows):
        if only and task not in only:
            continue
        todo = [(j, s, c) for j, s, c in candidates(rows[task], args.margin, args.tentative, args.bars) if (task, j, sha(s['working'])) not in done]
        if todo:
            plan.append((task, todo))
    if args.list:
        for task, todo in plan:
            print(task, 'start %.2f' % rows[task]['before']['worst'], [(j, s['worst'], c, len([x for x in s['working'].split('\n') if not x.startswith('(OUT')])) for j, s, c in todo])
        print(len(plan), 'stems,', sum(len(t) for _, t in plan), 'steps,', sum(len([x for x in s['working'].split('\n') if not x.startswith('(OUT')]) for _, t in plan for _, s, _ in t), 'working forms', file=sys.stderr)
        return
    if not plan:
        print('nothing to decide', file=sys.stderr)
        return
    warnings.filterwarnings('ignore', 'This process .* is multi-threaded', DeprecationWarning)
    signal.signal(signal.SIGTERM, on_term)
    import gold_dagcut2_one as D
    D.load_sampler()
    for task, todo in plan:
        t = time.time()
        code = run_child(task, args.lines, rows[task], todo, args.out, args)
        print(task, 'steps', len(todo), 'exit', code, '%.1fs' % (time.time() - t), flush=True)


if __name__ == '__main__':
    main()
