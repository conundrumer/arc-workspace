#!/usr/bin/env python
"""The bundle's superdag with an arm whose pool gets its clauses from Sampler.search. Same command line as superdag.py, with one more flag:

  --clauses draws    superdag.py unchanged: Pool.grow draws draws_per_scope clauses over each scope (the default).
  --clauses search   Pool.grow visits (scope, kind) searches. The environment variable POOL_CLAUSES gives the default of --clauses.

With draws, only Pool.grow is wrapped, to count its CPU seconds, so the arm runs superdag.py's own code. With search, the patches are Pool.grow, one_task (which keeps the
Sampler) and the methods of search.SearchRun (which keep, on each Clause it makes, the Program and the atoms it read). Pool.take and Pool.test run as
they are, on the Clause's decoder and Program. A clause counts as one draw: pool.draws, run.c['draws'], and the events' draw field.

A visit is one (scope, kind) search, run until PATIENCE tries in a row give no new node, or VISIT_SECONDS pass, or the search has no
clause left. A search goes on where it stopped, so a later visit of the same (scope, kind) gets the clauses after the earlier ones.
After a visit, the next one is a parked search with probability RESUME (the one whose last visit gave the most new nodes per second, among
those whose last visit gave any), and else a new scope from the policy, with a kind drawn as Pool.kind does. The searches are best-first and
deterministic, so a new scope's first clauses are the clauses that read no form of the scope, which the pool has: a try that gives a known
QueryHash counts as state:known, and is split into search:equal scope-free (the clause reads no form of the scope) and search:equal reads scope.

Counts added to the done file's counts (and the events' last line):
  search:scope refused, search:visits, search:new scope, search:resume, search:exhausted, search:clause deadline   the visits and their ends
  search:end patience, search:end seconds, search:end exhausted, search:end deadline
  search:manager demoted, search:manager shed, search:manager trimmed   the Manager's counts of searches that gave up a run, and of memory limit hits
  search:equal scope-free, search:equal reads scope, search:no table tries, search:failed tries
  search:seconds next, search:seconds take, search:seconds test, search:seconds visit setup     wall seconds in the search, take, test and the scope
  search:seconds new, search:seconds equal       the wall seconds (search + take + test) of tries that gave a new node, and of tries that did not
  cpu seconds grow   CPU seconds of the first pass and growth
  panic   engine panics that cost one path or one draw
  search.<name>   the sum of Search.stats (runs, dead, seconds, dup clause, ...)
  sr:<name>       the sum of the SearchRun's own counts

With FIRST_PASS_SECONDS above 0, in either arm, the pool starts with a first pass: search over the empty scope for that many seconds of each
kind in FIRST_KINDS, with no patience. Its forms come in through Pool.take and test as any other, and add_query marks them seeded. An event `first
pass` for each kind has its seconds, CPU seconds, tries, new nodes and the gold forms covered so far. In the search arm, a later visit of the empty
scope goes on where the pass stopped. install() puts the pass under another wrapper's Pool.grow.

With SEARCH_READ_SCOPE=1, a search over a non-empty scope gives only clauses that read a form of the scope. In a RULE or a DET body, a stop is barred until an atom
reads a relation, so the path goes on past a body that would read none. Any other clause that reads no form of the scope ends its path. Use it with a first pass: the empty
scope's search is then the source of clauses that read no form, and a later visit reaches it by the resume rule.

With SEARCH_READ_PICK=1, a search over a non-empty scope gives only clauses that read a form the policy picked for that scope, not only the picks' ancestors: a clause that
reads only ancestors could come from an earlier scope. The stop is barred, or the path ends, as with SEARCH_READ_SCOPE. Use it with a first pass too.

With SEARCH_ORACLE_CONTEXT=1 and --seed-level, each new visit's scope is the read forms of a gold form that the seed makes ready, and its kind is that form's. This reads
gold, so it bounds what a policy's pick can give, and it is never for a real run. With 2, the scope is those forms with the policy's other picks, up to --k picks in all.
With SEARCH_GOLD2=FILE, a file of task and gold_sexp, an event `cover2` gives each form of that second gold when a node first has its table.
With SEARCH_LOG_VISITS=1, an event `visit` gives each visit's scope, kind, tries and new nodes.

A table in SearchRun.memo keeps no CaseTables, except where SEARCH_NEW_TABLE, a SEARCH_PREFIX_SCORE module or SearchRun.trace reads its rows. ARC_MEMO_NO_CT=0 keeps them in each table.
Slot.run_seen keeps a run's number in place of the run. ARC_SLOT_NO_RUN=0 keeps the run.

VISIT_FORMS (env, as `RIGID_DET=3,KIND=N`; empty for none; default RIGID_DET=3): a visit of a listed kind ends when it has that many new forms, and the slot parks with last_rate 0, so
next_slot never resumes it. The nodes of the forms that the visits of one slot made get their score cut by the log of the slot's count of forms in the policy's pick of a scope, so that
the slot's forms weigh as one form there (picked_scope). The oldest-among-least-used share of a pick is not weighted.

With SEARCH_PREFIX_SCORE=FILE, a file with install() and score(tb, ctx), and SEARCH_PREFIX_BETA, a run adds beta x score, in nats, to its log chance at each prefix of a kind in
SEARCH_PREFIX_KINDS, in place of the parent prefix's score. Entries pushed below the prefix carry it, so the score orders subtrees, one atom after the prefix.

With SEARCH_FREE_STOP=1, the stop coin after a RULE or DET prefix costs nothing: the stop and the path that goes on both keep the prefix's bound, so a search gives each prefix as a
clause. A caller keeps the prefixes it wants as forms.

With SEARCH_NEW_TABLE=1, a search bars the stop of a RULE or DET prefix whose table has the TableHashes (at all its assignments) of a pool table of that kind, so the path goes on past it. Such a stop would give a query with
tables of known TableHash. The barred prefix's extensions stay in the search.

  Environment: FIRST_PASS_SECONDS (0), FIRST_PASS_RULE (seconds of the RULE pass, default FIRST_PASS_SECONDS), POOL_CLAUSES, SEARCH_PATIENCE (default 8), SEARCH_VISIT_SECONDS (4), SEARCH_RESUME (0.3), SEARCH_HOT (6, searches that keep a run),
  SEARCH_LIMIT_MIB (2048, resident memory past which a search gives up its run), SEARCH_READ_SCOPE (0), SEARCH_READ_PICK (0), SEARCH_NEW_TABLE (0), SEARCH_GOLD2, SEARCH_SCOPE_RULE (a file with picks(pool, k, rng); search arm only), SEARCH_TRACE (1: a line per visit).

  RAYON_NUM_THREADS=1 <runtime python> -u superdag_search.py TASK ... --clauses search --seconds 60 --policy DIR --models DIR --points FILE --out DIR
"""
import collections
import hashlib
import itertools
import json
import math
import os
import re
import sys
import time

A = os.path.dirname(os.path.abspath(__file__)) + '/model/study/sampler'
sys.path.insert(0, A)
import live  # noqa: E402
import search  # noqa: E402
import superdag as D  # noqa: E402
from live import M  # noqa: E402

PATIENCE = int(os.environ.get('SEARCH_PATIENCE', 8))
VISIT_SECONDS = float(os.environ.get('SEARCH_VISIT_SECONDS', 4))
RESUME = float(os.environ.get('SEARCH_RESUME', 0.3))
HOT = int(os.environ.get('SEARCH_HOT', 6))
LIMIT_MIB = float(os.environ.get('SEARCH_LIMIT_MIB', 2048))
LIMIT_SHARE = float(os.environ.get('SEARCH_LIMIT_SHARE', 0.65))  # of a worker's RSS limit, where its Manager starts giving up runs: over the line where a worker renews, so that a worker renews before the Manager sheds
SAVE_SECONDS = float(os.environ.get('SEARCH_SAVE_SECONDS', 60))
KEEP_COLD = int(os.environ.get('SEARCH_KEEP_COLD', 2))
DISK_MIB = float(os.environ.get('SEARCH_DISK_MIB', 2048))  # state files of one task
TRACE = int(os.environ.get('SEARCH_TRACE', 0) or 0)
FIRST_PASS = float(os.environ.get('FIRST_PASS_SECONDS', 0))
FIRST_RULE = float(os.environ.get('FIRST_PASS_RULE', FIRST_PASS))
READ_SCOPE = int(os.environ.get('SEARCH_READ_SCOPE', 0) or 0)
NEW_TABLE = int(os.environ.get('SEARCH_NEW_TABLE', 0) or 0)
READ_PICK = int(os.environ.get('SEARCH_READ_PICK', 0) or 0)
ORACLE = int(os.environ.get('SEARCH_ORACLE_CONTEXT', 0) or 0)
LOG_VISITS = int(os.environ.get('SEARCH_LOG_VISITS', 0) or 0)
VISIT_FORMS = {k: int(v) for k, v in (x.split('=') for x in os.environ.get('VISIT_FORMS', 'RIGID_DET=3').split(',') if x)}  # kind -> the new forms that end a visit of the kind
FREE_STOP = int(os.environ.get('SEARCH_FREE_STOP', 0) or 0)
SLOT_NO_RUN = os.environ.get('ARC_SLOT_NO_RUN') != '0'  # Slot.run_seen keeps a run's number in place of the run, so a run that its Search gave up can go; 0 keeps the run
SCOPE_RULE = None  # the module of SEARCH_SCOPE_RULE
PREFIX_SCORE = None  # the module of SEARCH_PREFIX_SCORE
PREFIX_BETA = float(os.environ.get('SEARCH_PREFIX_BETA', 0))  # nats of chance per unit of score
PREFIX_KINDS = tuple(os.environ.get('SEARCH_PREFIX_KINDS', 'RULE').split(','))
POOL = []  # the Pool of the task
FIRST_KINDS = 'INIT', 'RULE', 'DET'
SAMPLER = []  # the Sampler of one_task


def patch_search_run():
    """Wraps methods of search.SearchRun so that it keeps, on each Clause it makes, the Program at the query's end and the atoms the query
    read (D.Run's reads). The class stays the one that search.py names, since its methods call super(SearchRun, self).

    With search.WRITER, the query writer (writer.py) writes each query, and the reads come from its Finished (S.atom_uses over the query's model tokens). The
    stop bars of SEARCH_READ_SCOPE and SEARCH_READ_PICK are then two more lookahead components on END (ReadScope, ReadPick, added to the plan through
    search.EXTRA_COMPONENTS). The prefix fields of the Clause (prefix_tb, prefix_text, prefix_table_hash, go_on) are None: they come from the stop coin of the
    old per-atom draw, which the writer does not have; SEARCH_PREFIX_SCORE, SEARCH_NEW_TABLE and SEARCH_FREE_STOP need it and are refused with the writer."""
    cls = search.SearchRun
    if search.WRITER:
        if PREFIX_SCORE is not None or NEW_TABLE or FREE_STOP:
            sys.exit('WRITER=1 does not take SEARCH_PREFIX_SCORE, SEARCH_NEW_TABLE or SEARCH_FREE_STOP: they hang on the stop coin of Run.body')
        if READ_SCOPE:
            search.EXTRA_COMPONENTS.append(ReadScope)
        if READ_PICK:
            search.EXTRA_COMPONENTS.append(ReadPick)
    init, open_form, body, clause_of, failed, stop_barred, table, keeps_ct = cls.__init__, cls.open_form, cls.body, cls.clause_of, cls.failed, cls.stop_barred, cls.table, cls.keeps_ct

    def must_read(self):
        return READ_SCOPE and self.scoped is not None and bool(self.scoped[0])

    def stop_barred_(self, dr, kind, k, top, nlab, toks, text, scope, need, keys):
        if kind != 'INIT' and k < top and must_read(self) and not any(self.V.kind(t) == 'relation' for t in toks):
            self.c['read scope:stop barred'] += 1
            return True
        if kind != 'INIT' and k < top and self.picks and not reads_pick(self, ' '.join(text)):
            self.c['read pick:stop barred'] += 1
            return True
        if PREFIX_SCORE is not None and PREFIX_BETA and kind in PREFIX_KINDS and self.cur_tb is not None:
            shift_bound(self, dr, kind, k, toks, text)
        self.cur_text = list(text)
        if NEW_TABLE and kind != 'INIT' and k < top and table_known(self, kind):
            self.c['new table:stop barred'] += 1
            return True
        barred = stop_barred(self, dr, kind, k, top, nlab, toks, text, scope, need, keys)
        if FREE_STOP and not barred and kind != 'INIT':
            self.rng.free_next = True
        return barred

    def table_(self, fr, dec, pg):
        got = table(self, fr, dec, pg)
        self.cur_tb = got[0]
        if cls.trace is not None and got[0] is not None:
            cls.trace.append(got[0])
        return got

    def __init__(self, *args):
        init(self, *args)
        self.reads = []
        self.cur_tb = None
        self.picks = frozenset()  # the numbers of the forms that a clause must read (SEARCH_READ_PICK)

    def open_form_(self, pg, dec, kind):
        self.reads = []
        self.rng.scored = 0.0
        return open_form(self, pg, dec, kind)

    def body_(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        got = body(self, pg, dr, dec, kind, nlab, need, keys)
        self.reads += [t for t, _ in D.S.atom_uses(self.V, got[1])]
        return got

    def clause_of_(self, forms, pg, f):
        fin = self.finished if search.WRITER else None  # the writer's Finished, which clause_of takes
        clause = clause_of(self, forms, pg, f)
        if fin is not None:
            self.reads = [t for t, _ in fin.reads]
        if must_read(self) and not D.SPLIT_FORM.search(clause.text):
            self.c['read scope:clause refused'] += 1
            raise search.Dead('reads no scope')
        if self.picks and not self.picks & set(D.SPLIT_FORM.findall(clause.text)):
            self.c['read pick:clause refused'] += 1
            raise search.Dead('reads no pick')
        clause.pg, clause.reads, clause.prefix_key = pg, list(self.reads), prefix_key(self.cur_tb) if NEW_TABLE and self.cur_tb is not None else None
        clause.prefix_tb, clause.prefix_text = (None, None) if fin is not None else (self.cur_tb, getattr(self, 'cur_text', None))
        at = getattr(self.rng, 'free_at', None)
        clause.go_on = None if at is None or at >= len(self.rng.taken) or self.rng.taken[at] != 0 else tuple(self.rng.taken[:at]) + (1,)  # the path that goes on past the free stop
        return clause

    def failed_(self, e):
        if TRACE and isinstance(e, RecursionError) and not getattr(cls, 'shown', 0):
            import traceback
            cls.shown = 1
            print(''.join(traceback.format_exception(e)[-12:]), flush=True)
        failed(self, e)

    def keeps_ct_(self):
        """The readers of rows on memoized tables: prefix_key under NEW_TABLE, a PREFIX_SCORE module, and whoever reads the tables that cls.trace collects."""
        return keeps_ct(self) or bool(NEW_TABLE) or PREFIX_SCORE is not None or cls.trace is not None

    cls.__init__, cls.open_form, cls.body, cls.clause_of, cls.failed, cls.stop_barred, cls.table, cls.keeps_ct = __init__, open_form_, body_, clause_of_, failed_, stop_barred_, table_, keeps_ct_
    cls.trace = None  # a list that a caller sets to collect each table a walk makes
    coin = search.Chooser.coin

    def coin_(self, p):
        """With FREE_STOP, the coin after a prefix takes no chance from either side: the stop and the path that goes on both keep the prefix's bound, so each prefix gives a clause."""
        if not getattr(self, 'free_next', False):
            return coin(self, p)
        self.free_next = False
        logp, n = self.logp, len(self.sibs)
        got = coin(self, 0.5)
        self.logp = logp
        self.free_at = len(self.taken) - 1
        if len(self.sibs) > n:
            self.sibs[-1] = self.sibs[-1][0], logp
        return got

    search.Chooser.coin = coin_


class ReadScope:
    """The stop bar of SEARCH_READ_SCOPE, as a lookahead component of the writer: over a non-empty scope, a RULE's or DET's END is removed until a table is read."""
    name = 'ReadScope'

    def __init__(self, run):
        self.run = run

    def factors(self, point, ids):
        import numpy as np
        out = np.zeros(len(ids))
        if must_read_scope(self.run) and point.kind != 'INIT' and (ids == M.END).any() and not any(self.run.V.kind(t) == 'relation' for t in point.tokens):
            out[ids == M.END] = -np.inf
            self.run.c['read scope:stop barred'] += 1
        return out


class ReadPick:
    """The stop bar of SEARCH_READ_PICK, as a lookahead component of the writer: a RULE's or DET's END is removed until an atom reads a table that the policy picked."""
    name = 'ReadPick'

    def __init__(self, run):
        self.run = run

    def factors(self, point, ids):
        import numpy as np
        out = np.zeros(len(ids))
        T = point.track
        if self.run.picks and point.kind != 'INIT' and (ids == M.END).any() and not T.path:
            text = [x for _, x in T.texts] + ([T.text + ')'] if T.atom else [])
            if not reads_pick(self.run, ' '.join(text)):
                out[ids == M.END] = -np.inf
                self.run.c['read pick:stop barred'] += 1
        return out


def must_read_scope(run):
    return READ_SCOPE and run.scoped is not None and bool(run.scoped[0])


def shift_bound(run, dr, kind, k, toks, text):
    """Moves the run's log chance by the change in beta x score at this prefix, so each entry pushed below it carries the prefix's score in place of its parent's. The
    order of the options at a choice doesn't change, and a replay gets the same score from the table's memo."""
    tb, ch = run.cur_tb, run.rng
    if type(ch) is not search.Chooser:  # the teacher-forced walk of or_q has no bound
        return
    got = tb.get('prefix score')
    if got is None:
        t0 = time.process_time()
        try:
            got = float(PREFIX_SCORE.score(tb, dict(run=run, task=POOL[0].task, text=text, atoms=k)))
        except M.Fail:
            got = 0.0
        tb['prefix score'] = got
        run.c['prefix score:cpu'] += time.process_time() - t0
        run.c['prefix score:calls'] += 1
    ch.logp += PREFIX_BETA * (got - ch.scored)
    ch.scored = got


def reads_pick(run, text):
    """Whether atom texts read a form of run.picks, with the names that Run.clause_of writes."""
    names = run.scoped[2].written
    named = re.sub(r'&r\d+', lambda m: names.get(m[0], m[0]), text)
    return bool(run.picks & set(D.SPLIT_FORM.findall(named)))


def prefix_key(tb):
    """The TableHashes of a prefix's table at its assignments, sorted. They stay on the table, which the search's memo keeps, so a replay pays for it once."""
    key = tb.get('TableHashes')
    if key is None:
        rows = tb['assignment_summaries']
        if any(r.hash is None for r in rows):
            raise M.Fail('table with no TableHash')
        key = tb['TableHashes'] = tuple(sorted(r.hash for r in rows))
    return key


def table_known(run, kind):
    """Whether the pool has a node of the kind with the current prefix's table. A DET and a RULE with one table are different relations, so only the same kind bars the
    stop. The answer is kept per path, since the stop coin is a choice of the path: a replay must make the same choices, though the pool has grown. run.seen stays with the
    Search when it gives up its run."""
    tb, at = run.cur_tb, ('new table', run.rng.hash)
    got = run.seen.get(at)
    if got is None:
        if tb is None:
            got = False
        else:
            t0 = time.process_time()
            try:
                pool = POOL[0]
                node = pool.table_sets.get(prefix_key(tb))
                got = node is not None and pool.forms[pool.nodes[node].form].kind == kind
            except M.Fail:
                got = False
            run.c['new table:cpu'] += time.process_time() - t0
        run.seen[at] = got
    return got


PANIC = BaseException  # an engine panic is pyo3_runtime.PanicException, a BaseException


def is_panic(e):
    return type(e).__name__ == 'PanicException'


def draw_guarded(self, fids, deadline):
    """Pool.draw, where an engine panic costs one draw."""
    try:
        _draw(self, fids, deadline)
    except PANIC as e:
        if not is_panic(e):
            raise
        self.run.c['panic'] += 1


def guard_saves():
    """A write of a search's state that fails ends the saves of every search, and not the worker: each search goes on in memory."""
    save = search.Search.save

    def save_(self):
        try:
            save(self)
        except OSError as e:
            mgr = self.mgr
            print('search state: no more saves: %r' % (e,), flush=True)
            for s in list(mgr.scopes.values()) + [self]:
                if s.run is not None:
                    s.run.rng.jr = None
                if s.disk is not None:
                    try:
                        os.remove('%s.%d.tmp' % (s.disk.path, os.getpid()))
                    except OSError:
                        pass
                    s.disk.close()
                s.disk = s.jr = None
            mgr.directory = None
            mgr.counts['saves ended'] += 1
    search.Search.save = save_


class Slot:
    """The state of one (scope, kind) search that the pool keeps: what its visits gave."""

    def __init__(self, fids, texts, kind, picks=frozenset()):
        self.fids, self.texts, self.kind, self.picks = fids, texts, kind, picks
        self.visits = self.tries = self.new = 0
        self.resumes = 0  # the resumes of this generation, which the slots file leaves out
        self.seconds = 0.0
        self.last_rate = 0.0  # new nodes per second in the last visit; 0 after a visit that the form cap ended
        self.made = []  # the ids of the forms of a VISIT_FORMS kind that this slot's visits made
        self.exhausted = False
        self.stats_seen = {}  # the Search.stats and the SearchRun counts already added to the run's counts
        self.run_seen = (None, {})


def add_delta(c, prefix, now, seen):
    """Adds to counter c the growth of the numbers in dict now since dict seen, and returns the new seen."""
    for k, v in now.items():
        if isinstance(v, (int, float)) and v - seen.get(k, 0):
            c[prefix + k] += v - seen.get(k, 0)
    return {k: v for k, v in now.items() if isinstance(v, (int, float))}


def pool_init(self, *args):
    _init(self, *args)
    self.slots, self.parked, self.seeding, self.oracle = {}, [], False, None
    self.grouped, self.visiting = [], None  # the slots that made forms of a VISIT_FORMS kind; the slot in a visit
    self.sampler = SAMPLER[0]
    POOL[:] = [self]
    self.picks = []
    self.gold2 = {}
    path = os.environ.get('SEARCH_GOLD2')
    if path:  # a second gold of the same task, for a second cover count
        sexp = {x['task']: x['gold_sexp'] for x in json.load(open(path))}.get(self.id)
        if sexp:
            self.gold2 = D.gold_keys(self.run, sexp)


def kind_of(self, fids):
    """A kind for the scope, as Pool.kind draws it. The pool's own Run replays the scope for what the decoder admits."""
    dec, _ = self.run.scope([self.forms[f].text for f in fids])
    return self.kind(dec)


def picked_scope(self):
    """Pool.scope, keeping the policy's picks in self.picks. The wrapper of the policy's scope lasts for this call, since the worker pickles the policy's state."""
    pick = self.policy.scope

    def scope(k, rng):
        score, shifted = getattr(self.policy, 'score', None), {}
        if score is not None:  # the score of the nodes that one slot's forms made, less the log of the slot's forms: together they weigh as one form
            for slot in self.grouped:
                if len(slot.made) > 1:
                    cut = math.log(len(slot.made))
                    for f in slot.made:
                        for n in self.forms[f].nodes:
                            if n in score and n not in shifted:
                                shifted[n] = score[n]
                                score[n] -= cut
        try:
            self.picks = list(SCOPE_RULE.picks(self, k, rng) or pick(k, rng) if SCOPE_RULE else pick(k, rng))
        finally:
            if score is not None:
                score.update(shifted)  # the policy's scores are pickled with the bank, so they are put back
        return self.picks
    self.policy.scope = scope
    try:
        return self.scope()
    finally:
        del self.policy.scope


def oracle_targets(self):
    """[(scope, kind)]: for each gold form past the seed cut whose read forms are all seeded, those forms with their ancestors, and its kind. Oracle context: this
    reads gold, for a test of the policy's pick and for nothing else."""
    if self.oracle is None:
        lines = [x for x in self.a.gold_sexp.strip().split('\n') if not x.startswith('(OUT')]
        heads = [live.head_of(x) for x in lines]
        depth, reads = {}, {}
        for h, x in zip(heads, lines):
            reads[h] = {m for m in D.NAME.findall(x) if m in depth and m != h}
            depth[h] = 1 + max((depth[r] for r in reads[h]), default=0)
        cut = -(-max(depth.values()) * self.a.seed_level // self.a.levels)
        ids = {h: i for i, h in enumerate(h for h in heads if depth[h] <= cut)}
        self.oracle = []
        for h, x in zip(heads, lines):
            if h not in ids and all(r in ids for r in reads[h]):
                got, todo = set(), list(reads[h])
                while todo:
                    r = todo.pop()
                    if r not in got:
                        got.add(r)
                        todo += reads[r]
                self.oracle.append((sorted((ids[r] for r in got), key=lambda f: (self.forms[f].depth, f)), x[1:x.index(' ')], len(reads[h])))
    return self.oracle or [([], 'RULE', 0)]


def next_slot(self):
    """A parked slot with chance RESUME, else a new scope and kind from the policy. Gives (slot, whether it is new)."""
    rng = self.rng
    live_parked = [s for s in self.parked if not s.exhausted and s.last_rate > 0]
    if live_parked and rng.random() < RESUME:
        slot = max(live_parked, key=lambda s: (s.last_rate, -s.visits))
        slot.resumes += 1
        c = self.run.c
        c['resume:' + slot.kind] += 1
        c['resume top:' + slot.kind] = max(c['resume top:' + slot.kind], slot.resumes)
        return slot, False
    if ORACLE:
        fids, kind, parents = rng.choice(oracle_targets(self))
        if ORACLE == 2 and parents < self.a.k:  # the parents, with the policy's other picks up to k
            k, self.a.k = self.a.k, self.a.k - parents
            try:
                fids = sorted(set(fids) | set(self.scope()), key=lambda f: (self.forms[f].depth, f))
            finally:
                self.a.k = k
        texts = tuple(self.forms[f].text for f in fids)
        slot = self.slots.get((texts, kind))
        if slot is None:
            slot = self.slots[texts, kind] = Slot(fids, texts, kind)
            self.parked.append(slot)
        return slot, True
    fids = picked_scope(self)
    picks = frozenset(str(self.nodes[n].form) for n in self.picks) if READ_PICK else frozenset()
    kind = kind_of(self, fids)
    texts = tuple(self.forms[f].text for f in fids)
    slot = self.slots.get((texts, kind))
    if slot is None:
        slot = self.slots[texts, kind] = Slot(fids, texts, kind, picks)
        self.parked.append(slot)
    return slot, True


def try_clause(self, clause, texts, kind):
    """Pool.draw for a clause the search gave: seeds the Run, keeps the clause where it gives a new node, tests its OUT candidates.
    Gives 'new', 'equal' or 'none'."""
    run = self.run
    self.draws += 1
    run.rng.seed(int(hashlib.sha1(('%s %d %d' % (self.id, self.a.seed, self.draws)).encode()).hexdigest()[:12], 16))
    run.deadline = min(self.deadline, time.monotonic() + D.CLAUSE_SECONDS)
    run.c['draws'] += 1
    run.reads = clause.reads
    free = not D.SPLIT_FORM.search(clause.text)
    equal0, out = run.c['state:known'], 'none'
    try:
        kept = self.take(clause.decoder, clause.pg, kind, len(texts))
        self.mark('keep')
        if clause.prefix_key is not None:
            run.c['new table:prefix key ' + ('is a table' if clause.prefix_key in self.table_sets else 'is no table')] += 1
        if run.c['state:known'] > equal0:
            out = 'equal'
            run.c['search:equal ' + kind] += 1
            run.c['search:equal ' + ('scope-free' if free else 'reads scope')] += 1
        elif kept:
            out = 'new'
            t0 = time.monotonic()
            self.test(clause.decoder, clause.pg, kept)
            self.mark('test')
            run.c['search:seconds test'] += time.monotonic() - t0
        else:
            run.c['search:no table tries'] += 1
    except M.Fail as e:
        self.mark('keep')
        D.count_drop(run.c, e)
        run.c['search:failed tries'] += 1
    except Exception as e:  # noqa: BLE001
        run.failed(e)
        run.c['search:failed tries'] += 1
    except PANIC as e:
        if not is_panic(e):
            raise
        run.c['panic'] += 1
    return out


def visit(self, slot, deadline, patience=PATIENCE):
    """Pulls clauses from the slot's search until a stop rule ends the visit. Gives the new nodes of the visit."""
    run, c = self.run, self.run.c
    t_start = time.monotonic()
    self.visiting = slot
    vdead = min(deadline, t_start + VISIT_SECONDS)
    s = self.sampler.search(run.session, 0, vdead, self.task, slot.texts, slot.kind)
    s.run.picks = slot.picks
    self.scoped = slot.fids
    self.mark('setup')
    c['search:seconds visit setup'] += time.monotonic() - t_start
    c['search:visits'] += 1
    it, miss, new, tries, trace, end = iter(s), 0, 0, 0, [], 'deadline'
    while True:
        now = time.monotonic()
        if now >= vdead:
            end = 'deadline' if vdead >= deadline else 'seconds'
            break
        s.run.deadline = min(vdead, now + D.CLAUSE_SECONDS)
        s.run.picks = slot.picks  # the Manager may have made its run anew
        try:
            clause = next(it)
        except StopIteration:
            self.mark('next')
            c['search:seconds next'] += time.monotonic() - now
            if s.exhausted or not s.heap:
                slot.exhausted, end = True, 'exhausted'
                c['search:exhausted'] += 1
                break
            if time.monotonic() < vdead:  # the runs since the last clause passed CLAUSE_SECONDS: the path of the run that hit it is never run again, as Pool.draw drops a clause that takes so long
                nb, _, base, j, entry = s.heap[0]
                s.poison.add(search.path_of(base, j))
                c['search:clause deadline'] += 1
                it = iter(s)
                continue
            end = 'deadline' if vdead >= deadline else 'seconds'
            break
        except PANIC as e:
            if not is_panic(e):
                raise
            c['panic'] += 1  # the path in flight is lost; the search goes on from its frontier
            it = iter(s)
            continue
        t1 = time.monotonic()
        c['search:seconds next'] += t1 - now
        self.mark('next')
        out = try_clause(self, clause, slot.texts, slot.kind)
        if TRACE > 1:
            print('    %s %s' % (out, clause.text[:300]), flush=True)
        t2 = time.monotonic()
        c['search:seconds ' + ('new' if out == 'new' else 'equal')] += t2 - now
        c['search:seconds take'] += t2 - t1
        tries += 1
        trace.append({'new': 'N', 'equal': 'e' if D.SPLIT_FORM.search(clause.text) else 'f', 'none': 'x'}[out])
        if out == 'new':
            new, miss = new + 1, 0
            if new >= VISIT_FORMS.get(slot.kind, math.inf):
                end = 'forms'
                break
        else:
            miss += 1
            if miss >= patience:
                end = 'patience'
                break
    it = None
    c['search:end ' + end] += 1
    for k, v in self.sampler.search_manager.counts.items():
        c['search:manager ' + k] = v
    if PREFIX_SCORE is not None:
        c['prefix score:failed'] = PREFIX_SCORE.failed[0]
    seen = slot.stats_seen
    slot.stats_seen = add_delta(c, 'search.', s.stats, seen)
    r = s.run
    if r is not None:
        tag = r.number if SLOT_NO_RUN else r
        base = slot.run_seen[1] if slot.run_seen[0] == tag else {}
        slot.run_seen = tag, add_delta(c, 'sr:', r.c, base)
    secs = time.monotonic() - t_start
    slot.visits, slot.tries, slot.new, slot.seconds = slot.visits + 1, slot.tries + tries, slot.new + new, slot.seconds + secs
    slot.last_rate = 0.0 if end == 'forms' else new / max(secs, 1e-9)  # a capped visit is short, and its rate would win the resumes
    self.visiting = None
    c['seconds:' + slot.kind] += secs
    if LOG_VISITS:
        self.event(dict(event='visit', fids=slot.fids, kind=slot.kind, tries=tries, new=new, seconds=round(time.monotonic() - self.a.t0, 1)))
    if TRACE:
        print('  visit %d: %d forms %s, %d tries, %d new, %.1f s, end %s: %s' % (slot.visits, len(slot.texts), slot.kind, tries, new, secs, end, ''.join(trace)), flush=True)
    return new


def grow_search(self, deadline, every=50):
    """Pool.grow with visits in place of draws_per_scope draws over a scope."""
    last, t0, c = 0, time.monotonic(), self.run.c
    self.deadline = deadline
    while time.monotonic() < deadline:
        t1 = time.monotonic()
        try:
            slot, fresh = next_slot(self)
        except Exception as e:  # noqa: BLE001  # a scope that the engine refuses, as Pool.draw counts it
            self.run.failed(e)
            c['search:scope refused'] += 1
            continue
        self.mark('slot')
        c['search:seconds visit setup'] += time.monotonic() - t1
        c['search:new scope' if fresh else 'search:resume'] += 1
        visit(self, slot, deadline)
        self.tick()
        self.save_before_end(deadline)
        why = self.stop and self.stop()
        if why:
            return why
        if self.draws - last >= every:
            last = self.draws
            t = time.monotonic() - t0
            print('%s %d s, %.0f s left: %d tries, %.1f tries/s, %d forms, %d nodes, depth %d, candidates %d, gold covered %d of %d, equal %d, visits %d, RSS peak %.0f MiB' % (
                self.id, t, deadline - time.monotonic(), self.draws, self.draws / max(t, 1e-9), len(self.forms), len(self.nodes),
                max((f.depth for f in self.forms.values()), default=0), len(self.candidates), len(self.covered), len(self.gold), c['state:known'], c['search:visits'],
                D.rss_mib()), flush=True)


def first_pass(self, deadline):
    """Search over the empty scope for FIRST_PASS seconds of each kind."""
    self.deadline, self.seeding = deadline, True
    for kind in FIRST_KINDS:
        t0, c0, tries0, nodes0 = time.monotonic(), time.process_time(), self.draws, len(self.nodes)
        end = min(deadline, t0 + (FIRST_RULE if kind == 'RULE' else FIRST_PASS))
        slot = self.slots.get(((), kind))
        if slot is None:
            slot = self.slots[(), kind] = Slot([], (), kind)
            self.parked.append(slot)
        while time.monotonic() < end and not slot.exhausted:
            visit(self, slot, end, math.inf)
            self.tick()
            why = self.stop and self.stop()
            if why:
                self.seeding = False
                return why
        self.event(dict(event='first pass', kind=kind, seconds=round(time.monotonic() - t0, 2), cpu=round(time.process_time() - c0, 2), tries=self.draws - tries0,
                        nodes=len(self.nodes) - nodes0, covered=sorted({self.gold[k] for k in self.covered})))
    self.seeding = False
    return None


def add_query(self, fid, text, kind, depth, parents, reads, made, ct, pg, seeded=False):
    for _, r, _ in made:
        if r.hash in self.gold2:
            self.event(dict(event='cover2', gold=self.gold2[r.hash], draw=self.draws, seconds=round(time.monotonic() - self.a.t0, 1)))
    query = _add_form(self, fid, text, kind, depth, parents, reads, made, ct, pg, seeded=seeded or self.seeding)
    slot = self.visiting
    if slot is not None and kind in VISIT_FORMS and not self.seeding:
        if not slot.made:
            self.grouped.append(slot)
        slot.made.append(fid)
    return query


def grow_first(self, deadline, every=50):
    c0 = time.process_time()
    try:
        why = first_pass(self, deadline) if FIRST_PASS and not self.forms else None  # a process that read a bank file goes on from it
        return why or _grow(self, deadline, every)
    finally:
        self.run.c['cpu seconds grow'] = time.process_time() - c0


def one_task(sampler, task_id, gold_sexp, a):
    SAMPLER[:] = [sampler]
    sampler.searches.clear()
    sampler.search_store(None, hot=HOT, limit_mib=LIMIT_MIB)
    a.gold_sexp = gold_sexp
    return _one_task(sampler, task_id, gold_sexp, a)


def attach(sampler, directory=None, rss_limit_mib=None):
    """Sets the Sampler that the pool's searches use, for a caller that doesn't run through one_task. directory holds the searches' state, one process at a time;
    rss_limit_mib is the process's limit, of which the Manager keeps LIMIT_SHARE."""
    if directory and NEW_TABLE:
        raise ValueError('SEARCH_NEW_TABLE keeps keys that a state file cannot hold')
    SAMPLER[:] = [sampler]
    sampler.searches.clear()
    limit = rss_limit_mib * LIMIT_SHARE if rss_limit_mib else LIMIT_MIB
    sampler.search_store(directory, hot=HOT, limit_mib=limit, save_every=SAVE_SECONDS, keep_cold=KEEP_COLD)


def after_bank(pool, bank):
    """Call after each write of the bank file: the slots go beside it, the state of each search that changed goes to its file, and the oldest state files past DISK_MIB
    go. A search whose file went starts over if a later visit asks for it, and its clauses give equal nodes until it passes where it was."""
    mgr = pool.sampler.search_manager
    if not mgr.directory:
        return
    rows = [[slot.fids, slot.kind, sorted(slot.picks), slot.visits, slot.tries, slot.new, slot.seconds, slot.last_rate, slot.exhausted, slot.made] for slot in pool.slots.values()]
    try:
        with open(bank + '.slots.tmp', 'w') as f:
            json.dump(rows, f)
        os.replace(bank + '.slots.tmp', bank + '.slots')
    except OSError as e:
        print('slots not written: %r' % (e,), flush=True)
    for s in list(mgr.scopes.values()):
        if s.disk is not None and s.dirty:
            s.save()
    if mgr.directory:
        files = sorted((e.stat().st_mtime, e.stat().st_size, e.path) for e in os.scandir(mgr.directory) if e.name.endswith('.bss'))
        total = sum(x[1] for x in files)
        for _, size, path in files:
            if total <= DISK_MIB * 2 ** 20:
                break
            total -= size
            for name in (path, path[:-1] + 'j'):
                if os.path.exists(name):
                    os.remove(name)
            pool.run.c['search:state files removed'] += 1


def read_slots(pool, bank):
    """Fills pool.slots and pool.parked from the file that after_bank wrote, for a pool that read its bank file. A slot that names a form the bank lacks is left out."""
    try:
        with open(bank + '.slots') as f:
            rows = json.load(f)
    except (OSError, ValueError):
        return 0
    for fids, kind, picks, visits, tries, new, seconds, last_rate, exhausted, *made in rows:
        if all(x in pool.forms for x in fids):
            texts = tuple(pool.forms[x].text for x in fids)
            slot = pool.slots[texts, kind] = Slot(fids, texts, kind, frozenset(picks))
            slot.visits, slot.tries, slot.new, slot.seconds, slot.last_rate, slot.exhausted = visits, tries, new, seconds, last_rate, exhausted
            slot.made = [f for f in (made[0] if made else []) if f in pool.forms]
            if slot.made:
                pool.grouped.append(slot)
            pool.parked.append(slot)
    return len(pool.slots)


def install(mode):
    """Patches superdag for the arm: mode is draws or search. With draws and no first pass, nothing changes."""
    global _init, _one_task, _add_form
    if READ_SCOPE and not FIRST_PASS:
        sys.exit('SEARCH_READ_SCOPE needs FIRST_PASS_SECONDS above 0: with no pass, no search gives a clause that reads no form')
    global _grow, _draw
    _draw, D.Pool.draw = D.Pool.draw, draw_guarded
    if mode == 'draws' and not FIRST_PASS:
        _grow, D.Pool.grow = D.Pool.grow, grow_first
    elif mode == 'search' or FIRST_PASS:
        _init, _one_task, _add_form = D.Pool.__init__, D.one_task, D.Pool.add_query
        _grow = grow_search if mode == 'search' else D.Pool.grow
        D.Pool.__init__, D.Pool.grow, D.Pool.add_query, D.one_task = pool_init, grow_first, add_query, one_task
        patch_search_run()
        guard_saves()


def load_rule():
    """SEARCH_SCOPE_RULE is the path of a Python file with picks(pool, k, rng), which gives the node ids of a scope, or nothing to leave the pick to the policy."""
    global SCOPE_RULE, PREFIX_SCORE
    import importlib.util

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    if os.environ.get('SEARCH_SCOPE_RULE'):
        SCOPE_RULE = load('scope_rule', os.environ['SEARCH_SCOPE_RULE'])
    if os.environ.get('SEARCH_PREFIX_SCORE'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(os.environ['SEARCH_PREFIX_SCORE'])))
        PREFIX_SCORE = load('features_prefix_score', os.environ['SEARCH_PREFIX_SCORE'])
        PREFIX_SCORE.install()


def main():
    load_rule()
    mode = os.environ.get('POOL_CLAUSES', 'draws')
    argv, rest = sys.argv[1:], []
    while argv:
        x = argv.pop(0)
        if x == '--clauses':
            mode = argv.pop(0)
        elif x.startswith('--clauses='):
            mode = x.split('=', 1)[1]
        else:
            rest.append(x)
    sys.argv[1:] = rest
    if mode not in ('draws', 'search'):
        sys.exit('--clauses: draws or search')
    install(mode)
    print('pool clauses: %s' % mode, flush=True)
    D.main()


if __name__ == '__main__':
    main()
