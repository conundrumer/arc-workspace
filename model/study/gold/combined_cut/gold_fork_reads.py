"""The reads of a form's bits, for the cut stages. A stage calls load_sampler once, begin(stem) in the process that runs the stem, then read_form; `groups` is the token reader that both use.

A read's bits depend on what its session holds, since table work counts only the results that are not in the session's cache, and kept buffers count against the session's byte bound. So a read runs on a session that holds its scope's replay and no other read. Each kept form boundary is a parked process, a Node, which holds the session, decoder and Program after the replay of that prefix, and no walk. A process that steps past it is a fork of it, and a walk is a fork that exits with its answer. A read steps only the forms past the longest kept prefix. The token hash up to a boundary keys the Nodes, and it keys the bits too, so a helper's name does not matter. A walk stops at its first `bad`, and at the point where its bits can no longer land the cut.

A process that steps past a Node outlives it where the Node is dropped first, so a stem's runner has to reap orphans; gold_combined_run.py does.
"""
import collections, contextlib, copy, gc, hashlib, multiprocessing.connection as MC, multiprocessing.reduction as MR, os, resource, signal, socket, sys, time
os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import numpy as np
import arclog, live, live_try, or_q, search
import search_gold as G

KEPT_NODES = int(os.environ.get('ORCUT_KEPT_NODES', 64))  # parked processes per stem, least recently used first out
MARGIN = 0.02  # above a bound, so that a bound on unrounded bits holds for the rounded total that the checks compare
sampler = None
task = task_json = OS = None
memo, misses = {}, [0, 0]
last_parts = {}  # the bits by part of the last walk
times, counts = collections.Counter(), collections.Counter()


class Over(BaseException):
    """The walk's bits have passed its limit. A BaseException, since the walk's own handlers take Exception."""


class NoBits(BaseException):
    """The walk has a `bad`, which leaves the form with no bits."""


class Bound:
    """A memo entry for a walk that stopped at a limit: the form's bits, or the lack of them, are not under `low`."""

    def __init__(self, low):
        self.low = low


OVER = object()  # read_form's answer where the walk stopped at its limit


@contextlib.contextmanager
def timed(name):
    t = time.perf_counter()
    try:
        yield
    finally:
        times[name] += time.perf_counter() - t


def load_sampler():
    global sampler
    if sampler is None:
        with timed('sampler load'):
            sampler = live.Sampler(G.MODELS, tuple(live.STEERS))


def begin(stem):
    """The stem's root Node, in the process that runs the stem."""
    global task, task_json, OS
    task = stem
    times.clear()
    sess, task_json, _ = live_try.session_of(task)
    OS = Reads(sess)


class State:
    """The decode at a form boundary. pg is the Program before the end of a scope; ended is the Program that a walk starts from, made at the first read over this scope."""

    def __init__(self, dec, pg):
        self.dec, self.pg, self.ended = dec, pg, None


def groups(text, settings):
    """The model tokens of text by top-level form, and the rolling hash of the tokens through each form."""
    ids, model, paths = arclog.StudyProgram.from_sexp(text, settings).decode_stream()
    out, at, last, lasts = [], None, 0, {}
    for t, m, p in zip(ids, model, paths):
        if m:
            if p[0] != at:
                out.append([])
                at = p[0]
            out[-1].append(int(t))
            last = len(p)
            lasts[at] = last
    keys, h = [], b''
    for g in out:
        h = hashlib.blake2b(h + np.array(g, np.int64).tobytes(), digest_size=16).digest()
        keys.append(h)
    return out, keys, lasts


class Parts(collections.Counter):
    """Guide.parts, which tests the walk's limit where an atom's bits are whole: an atom's phases can sum past its total, and its join mix then takes the sum down to it."""

    guide = None

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if key.endswith('join mix'):
            self.guide.check()


class NoBad(list):
    def append(self, why):
        raise NoBits()


class Guide(or_q.Guide):
    """or_q's Guide that stops the walk at the first `bad`, and where the bits so far reach limit. The bits of a walk never fall, measured after each coin and each whole atom."""

    def __init__(self, run, rest, kind, limit):
        super().__init__(run, rest, kind)
        self.limit = limit
        self.bad = NoBad()
        self.parts = Parts()
        self.parts.guide = self

    def check(self):
        if self.limit is not None and sum(self.parts.values()) >= self.limit + MARGIN:
            raise Over()

    def add(self, name, p):
        super().add(name, p)
        self.check()


def copy_pg(pg):
    """A Program that a walk or an advance can change with no effect on pg."""
    g = pg.fork()
    g.record_cols = {k: dict(v) for k, v in pg.record_cols.items()}
    g.scope_grids, g.scope_colors, g.scope_positions = list(pg.scope_grids), list(pg.scope_colors), list(pg.scope_positions)
    return g


def advance(run, st, group):
    """The State after one form of tokens over State st, as live.Run.scope leaves it."""
    pg = copy_pg(st.pg)
    first, *toks = group
    kind = run.V.name(first)
    if kind not in live.KIND_TOK and kind not in live.REPLAYED:
        raise live.Drop('scope: a %s form' % kind)
    pg.new = []
    f = run.open_form(pg, st.dec, kind)
    for t in toks:
        rels = [x for x in f.step(t)[0] if run.V.kind(x) == 'relation']
        if rels:
            run.declared(pg, rels)
            at = live.M.slot_no(run.V.name(rels[0]))
            pg.names = pg.names | {run.V.name(x): '&r%d.%d' % (at, j) if kind in ('INIT', 'RIGID_DET') else run.V.name(x) for j, x in enumerate(rels)}
    pg.toks = pg.toks + toks
    pg.kinds = pg.kinds + [kind]
    run.close(pg, f)
    suits = run.gate.suits(pg.before)
    pg.suit = pg.suit | {s: (suits.get(s, 0.0), live.random.Random(s).random()) for s in pg.new}
    return State(f, pg)


def scope_end(run, st):
    """The State at st with its `ended` Program, as live.Run.scope ends a scope."""
    pg = copy_pg(st.pg)
    f = st.dec.fork()
    f.step(live.RULE_TOK)
    run.fill_columns(pg, f)
    run.scope_partners(pg, st.dec)
    st.ended = pg
    return st


def run_walk(run, st, rest, head, limit):
    """The walk of the tokens rest over State st: ('bits', a number or None), ('over',) or ('none',), and the Guide's parts."""
    g = run.rng = Guide(run, collections.deque(rest), head, limit)
    dead = None
    try:
        with timed('form walk'):
            run.form(copy_pg(st.ended), st.dec, head)
        if head in or_q.FORMS and all(t == live.SKIP_TOK for t in g.rest):
            g.rest.clear()
    except or_q.Stuck:
        pass
    except search.Dead as e:
        dead = str(e) or 'dead'
    except Exception as e:  # noqa: BLE001
        dead = type(e).__name__
    except Over:
        counts['walks stopped at the limit'] += 1
        return ('over',), g.parts
    except NoBits:
        counts['walks stopped at a bad'] += 1
        return ('none',), g.parts
    return ('bits', None if dead is not None or g.rest else round(sum(g.parts.values()), 2)), g.parts


def node_op(c, sess, st, msg):
    """Runs msg in a forked process of a Node, and answers on c. Never returns: a walk exits, and a step or a scope end stays as a Node."""
    gc.freeze()
    times.clear()
    counts.clear()
    t, cpu = time.perf_counter(), time.process_time()
    op, *args = msg
    answer = None
    parts = {}
    try:
        run = or_q.GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
        if op == 'advance':
            with timed('prefix step'):
                st = advance(run, st, args[0])
        elif op == 'end':
            with timed('scope end'):
                st = scope_end(run, st)
        else:
            answer, parts = run_walk(run, st, *args)
            parts = dict(parts)
    except Exception as e:  # noqa: BLE001
        c.send(dict(error=repr(e)[:300], cpu=time.process_time() - cpu, wall=time.perf_counter() - t, times=dict(times), counts=dict(counts)))
        os._exit(0)
    stats = sess.cache_stats()
    c.send(dict(answer=answer, parts=parts, cpu=time.process_time() - cpu, wall=time.perf_counter() - t, times=dict(times), counts=dict(counts), bytes=stats[2] + stats[4] + stats[5]))
    if op == 'walk':
        os._exit(0)
    node_loop(c, sess, st)


def node_loop(c, sess, st):
    """A Node: forks one process for each message on c, and ends with c."""
    while True:
        try:
            msg = c.recv()
        except (EOFError, OSError):
            os._exit(0)
        ours, theirs = socket.socketpair()
        if os.fork() == 0:
            c.close()
            ours.close()
            node_op(MC.Connection(theirs.detach()), sess, st, msg)
        theirs.close()
        MR.send_handle(c, ours.fileno(), None)
        ours.close()


class Reads:
    """The stem's Nodes under the token hash of their prefix, least recently used first out. b'end' after a hash is the Node of that prefix with its scope ended: an ended scope runs table work that a replay past it does not run, so walks fork from it and steps do not."""

    def __init__(self, sess):
        self.settings = sess.settings
        self.nodes, self.cpu, self.peak = collections.OrderedDict(), 0.0, 0
        want = min(resource.getrlimit(resource.RLIMIT_NOFILE)[1], 4 * KEPT_NODES + 64)
        if resource.getrlimit(resource.RLIMIT_NOFILE)[0] < want:
            resource.setrlimit(resource.RLIMIT_NOFILE, (want, resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
        ours, theirs = socket.socketpair()
        if os.fork() == 0:
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            ours.close()
            run = or_q.GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
            st = State(run.root, live.Program())
            st.ended = st.pg
            node_loop(MC.Connection(theirs.detach()), sess, st)
        theirs.close()
        self.root = MC.Connection(ours.detach())

    def ask(self, node, *msg):
        """The answer of the fork of node that runs msg, and the Connection to that fork. times['fork and pipe'] takes the wall time that the fork does not report."""
        t = time.perf_counter()
        node.send(msg)
        c = MC.Connection(MR.recv_handle(node))
        try:
            got = c.recv()
        except (EOFError, OSError):
            counts['read crashes'] += 1
            c.close()
            raise RuntimeError('the fork of %s ended with no answer' % msg[0]) from None
        times['fork and pipe'] += time.perf_counter() - t - got['wall']
        times.update(got['times'])
        counts.update(got['counts'])
        self.cpu += got['cpu']
        self.peak = max(self.peak, got.get('bytes', 0))
        if 'error' in got:
            c.close()
            raise RuntimeError(got['error'])
        return got, c

    def keep(self, key, node, *msg):
        """The Node at key, a fork of node that runs msg."""
        _, c = self.ask(node, *msg)
        self.nodes[key] = c
        while len(self.nodes) > KEPT_NODES:
            self.nodes.popitem(last=False)[1].close()
            counts['states dropped'] += 1
        return c

    def get(self, key):
        c = self.nodes.get(key)
        if c is not None:
            self.nodes.move_to_end(key)
        return c


def scope_node(gs, keys):
    """The Node at the end of the scope forms gs, from the longest prefix kept, ended."""
    n = len(gs)
    if n == 0:
        return OS.root
    ended = OS.get(keys[-1] + b'end')
    if ended is None:
        k = n
        while k > 0 and OS.get(keys[k - 1]) is None:
            k -= 1
        counts['read forms kept'] += k
        node = OS.get(keys[k - 1]) if k else OS.root
        for j in range(k, n):
            counts['read forms stepped'] += 1
            node = OS.keep(keys[j], node, 'advance', gs[j])
        ended = OS.keep(keys[-1] + b'end', node, 'end')
    return ended


def walked(scope, target, head, limit):
    """The bits of the target over the scope forms, a number or None, or OVER."""
    with timed('reader'):
        gs, keys, lasts = groups('\n'.join((*scope, target, live.READER_OUT)), OS.settings)
        rest = gs[len(scope)]
        assert rest[0] == live.KIND_TOK[head]
        if head not in or_q.FORMS:  # as or_q.gold_rest: a form with no last END of its own has no read
            assert rest[-1] == live.M.END and lasts[len(scope)] == 1
            rest = rest[:-1]
        rest = rest[1:]
    key = keys[len(scope)]
    got = memo.get(key, OVER)
    if got is not OVER and not isinstance(got, Bound):
        counts['read memo hits'] += 1
        return got, key
    if isinstance(got, Bound) and limit is not None and got.low >= limit:
        counts['read memo hits'] += 1
        return OVER, key
    with timed('reader'):
        gs2, keys2, _ = groups('\n'.join((*scope, live.READER_OUT)), OS.settings) if scope else ([], [], {})
    node = scope_node(gs2[:len(scope)], keys2[:len(scope)])
    counts['walks'] += 1
    a, c = OS.ask(node, 'walk', rest, head, limit)
    c.close()
    last_parts.clear()
    last_parts.update(a['parts'])
    a = a['answer']
    if a[0] == 'over':
        memo[key] = Bound(limit)
        return OVER, key
    got = memo[key] = None if a[0] == 'none' else a[1]
    return got, key


def read_form(ls, i, limit=None):
    """Bits of form i with the forms before it as context: a number, None for no bits, 'none' for a kind that has no draw, or OVER where the bits are not under limit."""
    text = hashlib.sha256('\n'.join(ls[:i + 1]).encode()).hexdigest()
    got = memo.get(text, OVER)
    if got is not OVER and not isinstance(got, Bound):
        return got
    if isinstance(got, Bound) and limit is not None and got.low >= limit:
        return OVER
    head = ls[i].split()[0][1:]
    if head not in live.KIND_TOK:
        got = 'none'
    else:
        misses[0] += 1
        try:
            got, _ = walked(ls[:i], ls[i], head, limit)
        except Exception:  # noqa: BLE001
            got = None
    memo[text] = Bound(limit) if got is OVER else got
    return got
