"""Stage `pod`: the order-free bits of each form of a stem, by `or_q.walk` of the pinned sampler (master e1434cf72). One row per stem goes to stdout after the canonical pass, every EVERY seconds, and at the end; the last row is the stem's row. gold_pod_run.py runs many stems.

  <runtime python> gold_pod_bits.py TASK LINES.json [SECONDS]

LINES.json maps the stem to its forms, one form to a line. A stem is a task id, or `<task>~<program sha>`; the engine and the sampler get the part before `~`.

`read` is the one reader. The text without its OUT line is `ls`, and a form's `line` is its index in `ls`. The scope of a form is `or_q.canonical_scope` over `or_q.canonical_lines(ls)`, the forms that it reads in their first order that the decoder takes, with fields in column order. The target is the written text, with its fields in column order (`or_q.sorted_fields`). The walk is `or_q.walk`: -log2 of the summed chance over the target's valid atom orders, on a new session for each order walk, with `parts` that sum to `bits`.
A form's name is in the text that the scope's sort reads, so slot numbers can depend on helper names, not on written position.

Form row fields, as gold_dag_bits.py: line, kind, nscope, sizes (items of each free set), orders, tried (orders walked), refused (orders that the decoder or the walk refused), valid, dropped (0), none, status, bits, best, written, tight, prefix, partial, error. New: parts, orders_exact, stopped, only_written, walked_bits, se_bits, ess, bad, dead, fell_back, scope_sha, seconds.
status: `exact` (every valid order walked, at least 2), `one` (one order), `bound` (more orders than the cap: `bits` is the estimate that or_q.walk gives, with `se_bits`; or the form's seconds ran out, `stopped` true: the sum over the orders walked), `written` (more orders than the cap and none walked is valid, or the text does not read back as itself: `bits` is the written order's), `none` (no order has bits; `bits` null, `partial` the written walk's bits before its refusal), `no draw` (CHOOSE, which the walk does not draw; bits null), `unread` (the stem's seconds ran out before this form; bits null).
Stem row fields: task, base_sha (of the text with its OUT line), cap, budget, form_seconds, canon_kept, forms, worst, sum, seconds, cpu, times (CPU seconds of the sampler load, the canonical pass, the walks and the prefix reads), late, finished.
`prefix` is the bits of the written order over every written line before the form (or_q.walk_order), the figure that the cut stages and dag_bits.py's `other_context_written` give. POD_PREFIX=0 leaves it out.

Environment: POD_ORDER_CAP, POD_BUDGET, POD_FORM_SECONDS (defaults or_q.ORDER_CAP, ORDER_BUDGET, ORDER_SECONDS), POD_PREFIX (default 1), POD_ONLY (comma-separated line indices: read only those, for a check).
"""
import gc, hashlib, json, os, sys, time
os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import arclog, live, live_try, or_q
import form_orders as O
import search_gold as G

CAP = int(os.environ.get('POD_ORDER_CAP', or_q.ORDER_CAP))
BUDGET = int(os.environ.get('POD_BUDGET', or_q.ORDER_BUDGET))
FORM_SECONDS = float(os.environ.get('POD_FORM_SECONDS', or_q.ORDER_SECONDS))
PREFIX = os.environ.get('POD_PREFIX', '1') != '0'
ONLY = {int(x) for x in os.environ.get('POD_ONLY', '').split(',') if x}  # lines to read; the others stay `unread`
EVERY = 20.0  # seconds between rows
sampler = None
task = base_lines = t0 = SECONDS = None
times = {}


def load_sampler():
    global sampler
    if sampler is None:
        t = time.perf_counter()
        sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
        times['sampler load'] = time.perf_counter() - t


def setup(stem, lines_path, seconds=840):
    global task, base_lines, t0, SECONDS
    task, SECONDS = stem, float(seconds)
    base_lines = [x for x in json.load(open(lines_path))[task] if x.strip()]
    t0 = time.time()


def task_of(stem):
    """The task id of a stem: a stem is `<task>~<program sha>` or a plain task id. The engine and the sampler take the task id; lines.json and the row's `task` take the stem."""
    return stem.split('~')[0]


def sha(lines):
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()[:16]


def kind_of(text):
    return text.split()[0].lstrip('(')


def status_of(q, valid):
    """The status of a form from its record."""
    o = q['orders']
    if not valid:
        return 'none'
    if o.get('why') or o.get('only_written'):
        return 'written'
    if o['exact']:
        return 'one' if o['orders'] == 1 else 'exact'
    return 'bound'


def rnd(x):
    return None if x is None else round(x, 3)


def sizes_of(text):
    try:
        return [len(n.items) for n in O.Form(text).sets()]
    except Exception:  # noqa: BLE001
        return []


def read(sampler, task, ls, i, canon, seconds):
    """The row of form i of ls (the text without its OUT line), over the canonical forms canon, with at most `seconds` for its orders."""
    target = ls[i]
    kind = kind_of(target)
    f = dict(line=i, kind=kind, nscope=None, sizes=[], orders=None, tried=0, refused=0, valid=0, dropped=0, none=0, status=None, bits=None, best=None, written=None, tight=None, prefix=None, partial=None)
    if kind not in live.KIND_TOK:
        f['status'] = 'no draw'
        return f
    t = time.time()
    try:
        scope = or_q.canonical_scope(canon, i)
        f['nscope'] = len(scope)
        f['scope_sha'] = sha(scope)
        gc.collect()
        sess, task_json, _ = live_try.session_of(task_of(task))
        walked = or_q.sorted_fields(target, sess, scope)
        f['sizes'] = sizes_of(walked)
        q = or_q.walk(sampler, task_of(task), kind, [len(scope), 0], scope, walked, sess, task_json, kind, CAP, BUDGET, seconds)
        del sess
        o = q['orders']
        valid = or_q.clean(q)
        f['status'] = status_of(q, valid)
        f.update(orders=o['orders'], orders_exact=o['orders_exact'], tried=o['walked'], valid=o['valid'], refused=sum(o.get('refused', {}).values()), none=o['walked'] - o['valid'],
                 best=rnd(o.get('best')), written=rnd(o.get('written')), tight=rnd(o.get('tight')), stopped=o.get('stopped', False), only_written=o.get('only_written', False),
                 parts=q['parts'], fell_back=q['fell_back'])
        if o.get('why'):
            f['error'] = 'the text does not read back as itself: %s' % o['why']
        if f['status'] == 'bound' and o.get('walked_bits') is not None:
            f.update(walked_bits=o['walked_bits'], se_bits=o.get('se_bits'), ess=o.get('ess'))
        if valid:
            f['bits'] = q['total']
        else:
            f['bad'], f['dead'] = [str(x)[:160] for x in q['bad']], None if q['dead'] is None else str(q['dead'])[:160]
            f['partial'] = q['total'] if q['parts'] else None
        if kind in or_q.FORMS and 'text_differs' in o:
            f['text_differs'] = o['text_differs']
    except Exception as e:  # noqa: BLE001
        f['status'] = 'none'
        f['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    f['seconds'] = round(time.time() - t, 2)
    return f


def prefix_of(sampler, task, ls, i):
    """The written order's bits over every written line before form i, or None."""
    try:
        gc.collect()
        sess, task_json, _ = live_try.session_of(task_of(task))
        w = or_q.walk_order(sampler, task_of(task), kind_of(ls[i]), [i, 0], ls[:i], ls[i], sess, task_json, kind_of(ls[i]))
        return w['total'] if or_q.clean(w) else None
    except Exception:  # noqa: BLE001
        return None


def report(row, forms, done):
    with_bits = [f['bits'] for f in forms if f['bits'] is not None]
    row.update(forms=forms, worst=max(with_bits, default=None), sum=round(sum(with_bits), 3), seconds=round(time.time() - t0, 1), cpu=round(time.process_time(), 1), times={k: round(v, 2) for k, v in times.items()}, finished=done)
    print(json.dumps(row), flush=True)


def main():
    global ONLY
    if os.path.exists('only.json') and not ONLY:  # the reread: each stem's lines, in the kit's folder; a stem with an empty list reads all its forms
        ONLY = set(json.load(open('only.json')).get(task, []))
    load_sampler()
    row = dict(task=task, base_sha=sha(base_lines), cap=CAP, budget=BUDGET, form_seconds=FORM_SECONDS)
    ls = [x for x in base_lines if not x.startswith('(OUT')]
    t = time.perf_counter()
    gc.collect()
    sess, _, _ = live_try.session_of(task_of(task))
    try:
        canon, row['canon_kept'] = or_q.canonical_lines(ls, sess)
    except Exception as e:  # noqa: BLE001
        canon, row['canon_kept'] = list(ls), None
        row['canon_error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    del sess
    times['canonical'] = time.perf_counter() - t
    forms = [dict(line=i, kind=kind_of(x), status='no draw' if kind_of(x) not in live.KIND_TOK else 'unread', bits=None) for i, x in enumerate(ls)]
    report(row, forms, False)

    def cost(i):  # forms with fewer orders first, so that a stem that runs out of seconds leaves the form with most orders unread or stopped
        try:
            return O.Form(ls[i]).count(CAP) if kind_of(ls[i]) in live.KIND_TOK else 0
        except Exception:  # noqa: BLE001
            return CAP + 1
    todo = sorted((i for i in range(len(ls)) if kind_of(ls[i]) in live.KIND_TOK and (not ONLY or i in ONLY)), key=lambda i: (cost(i), i))
    last = time.time()
    for i in todo:
        left = SECONDS - (time.time() - t0)
        if left <= 0:
            row['late'] = True
            break
        t = time.process_time()
        forms[i] = read(sampler, task, ls, i, canon, min(FORM_SECONDS, left))
        times['walk'] = times.get('walk', 0) + time.process_time() - t
        if PREFIX and SECONDS - (time.time() - t0) > 0:
            t = time.process_time()
            forms[i]['prefix'] = prefix_of(sampler, task, ls, i)
            times['prefix'] = times.get('prefix', 0) + time.process_time() - t
        if time.time() - last > EVERY:
            report(row, forms, False)
            last = time.time()
    report(row, forms, True)


if __name__ == '__main__':
    setup(*sys.argv[1:4])
    main()
