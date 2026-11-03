"""The state search: a best-first search over states (search-worker/state-search-spec.md), on the writer kit's tables.

A state is a set of queries closed under inputs. Each expansion pops the state with the highest score, scopes its program, has the writer
write one query at it, evaluates the query, and pushes the child state. The score and the writer are the only choices.

kaggle_worker.source installs it where POOL_CLAUSES=state. Settings:
  SEARCH_STATE_SCORE  the path of a Python file with score(view) -> float or None (None closes the state). Default: -bits - expansions.

The kit gives the rest:
  - the export by table: live.Run.close keeps each parameterized table's AssignmentSummaries (QueryHash, Name, assignment, TableHash, counts,
    TableVector), and superdag.Pool.add_query makes one TableAt per table;
  - the kept-scope reuse (live.SCOPE_REUSE): a state's program is given in append order, its parent's plus the query that led to it, so
    a child's scope extends its parent's by one query.
The kind is drawn uniformly from the kinds the decoder admits. With WRITER=1 the writer (writer.write) drafts the query, one draw per choice from
search.DISTRIBUTION (WRITER_TREE where it loads), and the query's bits are the draws' log chance; with WRITER unset, the pool's form drawer drafts it
and records no bits.

Files beside the worker's output: <out>.expansions (one JSON line per expansion). The visited set goes into the bank file (bank_extra,
bank_restore).
"""
import collections
import copy
import dataclasses
import hashlib
import heapq
import importlib.util
import json
import math
import os
import re
import time

import live
import superdag as D
import superdag_search as SS
from live import M

SCHEMA = 4
SCORE = None
DRAFT_LOG = os.environ.get('STATE_DRAFT_LOG')  # debug: a JSON line per draft with its whole program, written before the draft's close
EXPANSIONS_BYTES = 64 << 20  # the most <out>.expansions holds, under the supervisor's limit on a file; past it the records stop and the search goes on
WRITER = os.environ.get('WRITER', '0') == '1'  # the writer (writer.write, with search.DISTRIBUTION) drafts each query, in place of Run.form's per-atom draw


def default_score(view):
    return -(view.bits or 0.0) - view.expansions


def load_score():
    global SCORE
    path = os.environ.get('SEARCH_STATE_SCORE')
    if not path:
        SCORE = default_score
        return
    spec = importlib.util.spec_from_file_location('state_score', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    SCORE = mod.score


class State:
    __slots__ = ('id', 'qids', 'parent', 'via', 'depth', 'bits', 'expansions', 'children', 'version', 'score', 'closed')

    def __init__(self, sid, qids, parent, via, depth, bits):
        self.id, self.qids, self.parent, self.via, self.depth, self.bits = sid, qids, parent, via, depth, bits
        self.expansions = self.children = self.version = 0
        self.score, self.closed = None, False

    def row(self):
        return [self.id, sorted(self.qids), self.parent, self.via, self.depth, self.bits, self.expansions, self.children, self.version, self.score, self.closed]

    @classmethod
    def of_row(cls, r):
        s = cls(r[0], frozenset(r[1]), r[2], r[3], r[4], r[5])
        s.expansions, s.children, s.version, s.score, s.closed = r[6], r[7], r[8], r[9], r[10]
        return s


class View:
    """What the score sees of one state. Fields are computed on first use."""

    def __init__(self, pool, st):
        self._p, self._s = pool, st
        self.depth, self.bits, self.expansions, self.children = st.depth, st.bits, st.expansions, st.children

    @property
    def queries(self):
        F = self._p.forms
        return [dict(query=F[q].query_hash, kind=F[q].kind, bits=F[q].bits, depth=F[q].depth, vector=getattr(F[q], 'vector', None),
                     inputs=[F[p].query_hash for p in F[q].parents]) for q in sorted(self._s.qids)]

    @property
    def tables(self):
        P, out = self._p, []
        for q in sorted(self._s.qids):
            for n in P.forms[q].nodes:
                t = P.nodes[n]
                out.append(dict(query=P.forms[q].query_hash, name=t.table[1], at=t.at, hash=t.hash, vector=t.features, counts=t.examples,
                                same_in_state=t.same_in_state, seen_before=t.seen_before))
        return out

    @property
    def base(self):
        return self._p.task['train']


def program(pool, st):
    """The state's queries in append order: the path from the root that made the state first, so that a child's program is its parent's plus one."""
    out = []
    while st.via is not None:
        out.append(st.via)
        st = pool.states[st.parent]
    return out[::-1]


def written_names(line, names):
    """line with each engine name written as its stored name. A RIGID_DET's part is named by the parameterized table that the part reads, without its
    '&', step by step: the engine writes `&r4.r1` for the part that reads `&r1`, and `&r77.r4.r1` for a part of &r77 that reads the part
    `&r4.r1` of another RIGID_DET; this writes `&f4.f1` and `&f77.f4.f1`. A step that isn't an engine slot, such as an INIT output's name or
    `pose`, stays as it is."""
    def one(m):
        steps = [names.get(m[1], m[1])]
        for st in m[2].split('.')[1:] if m[2] else []:
            q = names.get('&' + st) if re.fullmatch(r'r\d+', st) else None
            steps.append(q[1:] if q else st)
        return '.'.join(steps)
    return re.sub(r'(&r\d+)((?:\.\w+)*)', one, line)


def push(pool, st):
    if st.closed:
        return
    st.score = SCORE(View(pool, st))
    if st.score is None:
        st.closed = True
        return
    st.version += 1
    heapq.heappush(pool.frontier, (-st.score, st.id, st.version))


def pop(pool):
    while pool.frontier:
        neg, sid, ver = heapq.heappop(pool.frontier)
        st = pool.states[sid]
        if ver == st.version and not st.closed:
            return st
    return None


def state_of(pool, qids, parent, via):
    """The state with query set qids, made where it is new. Gives (state, whether it is new)."""
    sid = pool.state_ids.get(qids)
    if sid is not None:
        return pool.states[sid], False
    F = pool.forms
    st = State(len(pool.states), qids, parent, via, max((F[q].depth for q in qids), default=0),
               (pool.states[parent].bits if parent is not None else 0.0) + ((F[via].bits or 0.0) if via is not None else 0.0))
    pool.states[st.id] = st
    pool.state_ids[qids] = st.id
    push(pool, st)
    return st, True


class Draw:
    """The rng of writer.write for one draft: each choice is a draw from the writer's probabilities with the run's random source, so one seed gives
    one draft. logp is the log chance of the choices taken."""

    keys = None  # writer.write reads it for ORDER_FREE tie; a draw takes the options' chances alone

    def __init__(self, rng, deadline):
        self.rng, self.deadline, self.logp = rng, deadline, 0.0

    def node(self, probs, costs=None, tie=None):
        if time.monotonic() > self.deadline:  # the expansion's time (run.deadline: CLAUSE_SECONDS, or the worker's end) ends the draft
            raise live.Spent('writer past the expansion deadline')
        u, at = self.rng.random(), 0.0
        for j, p in enumerate(probs):
            at += p
            if u < at:
                break
        else:
            j = max((i for i, p in enumerate(probs) if p > 0), default=0)  # rounding left u past the sum
        self.logp += math.log(probs[j])
        return j


def write_query(run, pg, dec, kind):
    """(decoder after a query of `kind` at dec, its bits) from the writer (writer.write), drawn again where the writer ends the path, as Run.form draws
    again where a draw fails."""
    import search
    import writer
    plan = getattr(run, 'writer_plan', None)
    if plan is None:
        plan = run.writer_plan = writer.default_plan(run, search.OR_BITS, search.WRITER_LOOKAHEAD, search.DISTRIBUTION)
    pg.forms = live.S.strata.sexprs(dec.program_form())
    if DRAFT_LOG and not hasattr(run, 'close_logged'):
        close = run.close

        def close_logged(pg, f):  # the program with the draft, written before the close's export
            with open(DRAFT_LOG, 'a') as dl:
                dl.write(json.dumps(dict(pid=os.getpid(), expansion=getattr(run, 'expansion', None), program=f.program_form())) + '\n')
            return close(pg, f)
        run.close = run.close_logged = close_logged
    for _ in range(run.lim.form_tries):
        pg.new = []
        saved = copy.copy(pg)
        draw, t0 = Draw(run.rng, run.deadline), time.perf_counter()
        try:
            got = writer.write(writer.start_point(run, pg, run.open_form(pg, dec, kind), kind), plan, draw)
        except live.Spent:
            run.c['state:writer seconds spent %s' % kind] += time.perf_counter() - t0
            raise
        except (live.Drop, live.arclog.Refusal) as e:  # a check that the engine makes at END, or the close of the query
            why = str(e) if isinstance(e, live.Drop) else 'refused: ' + re.sub(r'\d+', 'N', str(e))[:70]
            got = writer.Ended(why)
        if isinstance(got, writer.Finished):
            return got.dec, -draw.logp / math.log(2)
        pg.__dict__.update(saved.__dict__)
        run.c['state:writer ended %s %s' % (kind, got.reason)] += 1
        run.c['state:writer seconds ended %s %s' % (kind, got.reason)] += time.perf_counter() - t0
    raise live.Drop('%s: no query in %d writer tries' % (kind, run.lim.form_tries))


def take(pool, st, f, pg, kind, nscope, bits=None):
    """Evaluates the query at decoder f under state st. Gives (outcome, query id, new table ids, flags, child state), or ('no table', ...)."""
    run = pool.run
    line = f.program_form().split('\n')[nscope]
    qid_new = len(pool.forms)
    names = pg.written | {live.head_of(line): '&f%d' % qid_new}
    text = written_names(line, names)
    made = [(s, r, j) for s in pg.new for r, j in zip(pg.tables.get(s, ()), pg.indexes.get(s, ()))]
    if not made:
        run.c['state:no table'] += 1
        return 'no table', None, [], [], None
    for _, r, _ in made:
        if r.hash is None:
            raise M.Fail('table with no TableHash: %s' % (getattr(r, 'unhashed', None) or 'no reason'))
        if not isinstance(r.table, tuple):
            raise M.Fail('table with no QueryHash')
    if any(r.examples and all(k[2] == 0 for k in r.examples) for _, r, _ in made):  # no TableRows on any example
        run.c['state:no TableRows'] += 1
        return 'no table', None, [], [], None
    qh = made[0][1].table[0]
    qid, new_tables, flags = pool.defs.get(qh), [], []
    if qid is None:
        parents = sorted({int(x) for x in D.SPLIT_FORM.findall(text)} - {qid_new})
        depth = 1 + max((pool.forms[p].depth for p in parents), default=0)
        pool.scoped = sorted(st.qids)  # add_query's same_in_state compares with the tables of the state
        q = pool.add_query(qid_new, text, kind, depth, parents, len(run.reads), made, pg.before, pg)  # it stores the query last, so a raise leaves nothing behind
        q.query_hash, q.bits, q.seconds, q.expansion = '%032x' % qh, bits, round(time.monotonic() - pool.a.t0, 2), pool.expanded
        qid, new_tables = qid_new, list(q.nodes)
        flags = [[n, pool.nodes[n].same_in_state, pool.nodes[n].seen_before] for n in q.nodes]
        t0 = time.monotonic()
        pool.test(f, pg, q)
        run.c['state:seconds test'] += time.monotonic() - t0
        run.c['state:new query'] += 1
    child, fresh = state_of(pool, st.qids | {qid}, st.id, qid)
    return ('new state' if fresh else 'known state'), qid, new_tables, flags, child


TOKEN_LOG = os.environ.get('STATE_TOKEN_LOG')  # debug: a JSON line per new query with the token ids fed to its decoder from a fresh start
_REC = None  # while the writer runs: id(decoder) -> [decoder, [(fed id, forced ids)]], for the decoders forked from the scope's end


def _install_token_log():
    import arclog
    step0, fork0 = arclog.Decoder.step, arclog.Decoder.fork

    def step(self, t):
        got = step0(self, t)
        if _REC is not None:
            e = _REC.setdefault(id(self), [self, []])
            try:
                forced = [int(x) for x in got[0]]
            except Exception:  # noqa: BLE001
                forced = None
            e[1].append((int(t), forced))
        return got

    def fork(self):
        child = fork0(self)
        if _REC is not None:
            parent = _REC.get(id(self))
            _REC[id(child)] = [child, list(parent[1]) if parent else []]
        return child
    arclog.Decoder.step, arclog.Decoder.fork = step, fork


def scope_tokens(run, texts):
    """The model token ids that Run.scope steps from a fresh decoder for texts, in order."""
    import arclog
    if not texts:
        return []
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*texts, live.READER_OUT)), run.session.settings).decode_stream()
    return [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] < len(texts)]


def expand(pool, deadline):
    """One expansion. Gives False where the frontier is empty."""
    st = pop(pool)
    if st is None:
        return False
    run, c = pool.run, pool.run.c
    pool.draws += 1
    pool.expanded += 1
    run.expansion = pool.expanded
    run.rng.seed(int(hashlib.sha1(('%s %d %d' % (pool.id, pool.a.seed, pool.expanded)).encode()).hexdigest()[:12], 16))
    run.deadline = min(deadline, time.monotonic() + D.CLAUSE_SECONDS)
    c['draws'] += 1
    rec = dict(v=SCHEMA, n=pool.expanded, seconds=round(time.monotonic() - pool.a.t0, 2), state=st.id, score=st.score, query=None, kind=None, bits=None,
               outcome='failed', child=None, new=[], flags=[])
    texts = [pool.forms[q].text for q in program(pool, st)]
    try:
        t0 = time.perf_counter()
        c['state:replayed queries'] += len(texts)
        dec, pg = run.scope(texts)
        c['state:seconds scope'] += time.perf_counter() - t0
        kinds = [k for k in live.KIND_TOK if (WRITER or run.makes(k)) and dec.admits([live.KIND_TOK[k]])[0]]
        kind = run.rng.choice(kinds)
        t0 = time.perf_counter()
        global _REC
        if TOKEN_LOG:
            _REC = {}
        bits = None
        try:
            if WRITER:
                f, bits = write_query(run, pg, dec, kind)
            else:
                f = run.form(pg, dec, kind)
        finally:
            drawn, _REC = (_REC.get(id(f), [None, []])[1] if TOKEN_LOG and _REC is not None and 'f' in dir() else []), None
        t1 = time.perf_counter()
        c['state:seconds writer'] += t1 - t0
        out, qid, new, flags, child = take(pool, st, f, pg, kind, len(texts), bits)
        c['state:seconds evaluate'] += time.perf_counter() - t1
        rec['kind'] = kind
        rec['outcome'] = out
        if child is not None:
            rec.update(query=pool.forms[qid].query_hash, child=child.id, new=new, flags=flags)
            if TOKEN_LOG and new:
                sc = scope_tokens(run, texts)  # the scope's fed ids from a fresh decoder, also where the scope came from a kept one
                with open(TOKEN_LOG, 'a') as tl:
                    tl.write(json.dumps(dict(task=pool.id.split('.')[0], wheel=os.environ.get('EXTRA_PATH', ''), stored=pool.forms[qid].query_hash, text=pool.forms[qid].text,
                                             scope=texts, fed=sc + [t for t, _ in drawn], forced_drawn=[x for _, x in drawn], drawn_from=len(sc))) + '\n')
            if out == 'new state':
                st.children += 1
    except M.Fail as e:
        c['drop:table: ' + re.sub(r'\d+', 'N', str(e))[:40]] += 1
    except Exception as e:  # noqa: BLE001
        if SS.is_panic(e):
            c['panic'] += 1
        else:
            run.failed(e)
    except SS.PANIC as e:
        if not SS.is_panic(e):
            raise
        c['panic'] += 1
    c['state:' + rec['outcome']] += 1
    st.expansions += 1
    push(pool, st)
    if pool.expansions_out.tell() < EXPANSIONS_BYTES:
        pool.expansions_out.write(json.dumps(rec) + '\n')
        pool.expansions_out.flush()
    else:
        c['state:records not written'] += 1
    return True


def trim_records(pool):
    """Keeps the expansion records that the bank holds: a worker that ended after its last save left records past it."""
    path = pool.a.out_path + '.expansions'
    pool.expansions_out.close()
    keep = []
    with open(path) as f:
        for l in f:
            try:
                if json.loads(l)['n'] <= pool.expanded:
                    keep.append(l)
            except ValueError:
                pass
    with open(path + '.tmp', 'w') as f:
        f.writelines(keep)
    os.replace(path + '.tmp', path)
    pool.expansions_out = open(path, 'a')


def grow(self, deadline, every=50):
    """Pool.grow for the state search."""
    t0, last = time.monotonic(), self.expanded
    self.deadline = deadline
    if not self.states:
        state_of(self, frozenset(), None, None)
    trim_records(self)
    while time.monotonic() < deadline:
        if not expand(self, deadline):
            return None
        self.tick()
        self.save_before_end(deadline)
        why = self.stop and self.stop()
        if why:
            return why
        if self.expanded - last >= every:
            last = self.expanded
            t = time.monotonic() - t0
            print('%s %d s, %.0f s left: %d expansions, %.1f/s, %d queries, %d tables, %d states, %d open, depth %d, candidates %d, gold covered %d of %d, RSS %.0f MiB' % (
                self.id, t, deadline - time.monotonic(), self.expanded, self.expanded / max(t, 1e-9), len(self.forms), len(self.nodes), len(self.states),
                len(self.frontier), max((q.depth for q in self.forms.values()), default=0), len(self.candidates), len(self.covered), len(self.gold), D.rss_mib()), flush=True)
    return None


def pool_init(self, *args):
    _init(self, *args)
    self.run.want_rows = False  # the state search reads no rows: one rows=False export per step
    self.run.lim = dataclasses.replace(self.run.lim, one_repair=0.0)  # the ONE repair needs the rows of every table, and on the state search it fit none (search-worker/kit-decisions.md)
    self.states, self.state_ids, self.frontier, self.expanded = {}, {}, [], 0
    self.expansions_out = open(self.a.out_path + '.expansions', 'a')


def bank_extra(self):
    return dict(state_search=dict(v=SCHEMA, states=[s.row() for s in self.states.values()], expanded=self.expanded))


def bank_restore(self, state):
    """The visited set back from the bank. read_bank has rebuilt the pool's maps from its queries and tables (Pool.rebuild_maps), so a renewal resets nothing.
    A visited set of another schema, or one that cannot be read, leaves the search empty, and the worker goes on from the root state."""
    x = state.get('state_search')
    if not x:
        return
    try:
        if x.get('v') != SCHEMA:
            raise ValueError('schema %r, this worker reads %d' % (x.get('v'), SCHEMA))
        states = {r[0]: State.of_row(r) for r in x['states']}
        if any(q not in self.forms for s in states.values() for q in s.qids):
            raise ValueError('a state holds a query the bank does not')
        frontier = [(-s.score, s.id, s.version) for s in states.values() if not s.closed and s.score is not None]
        expanded = int(x['expanded'])
    except Exception as e:  # noqa: BLE001
        print('visited set not read, the search starts empty:', repr(e)[:300], flush=True)
        self.run.c['state:visited set not read'] += 1
        return
    heapq.heapify(frontier)
    self.states, self.frontier, self.expanded = states, frontier, expanded
    self.state_ids = {s.qids: s.id for s in states.values()}


def read_slots(pool, bank):  # kaggle_worker calls it after the bank is read; the visited set comes back through bank_restore
    return 0


def after_bank(pool, bank):
    return None


def install():
    """Patches superdag for the state search."""
    global _init
    load_score()
    if TOKEN_LOG:
        _install_token_log()
    _init = D.Pool.__init__
    D.Pool.__init__, D.Pool.grow = pool_init, grow
    D.Pool.bank_extra, D.Pool.bank_restore = bank_extra, bank_restore
