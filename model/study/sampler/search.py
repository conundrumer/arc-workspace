#!/usr/bin/env python
"""Best-first search over the clauses that Sampler.clause draws (live.py): the same walk, with each random choice a branch of a tree.

    search = sampler.search(session, seed, deadline, task, forms, kind='RULE', **limits)
    for clause in search: ...        # Clauses with distinct text, in about descending q, until the deadline
    search = sampler.search(session, seed, later, task, forms, kind='RULE', **limits)   # the same search, on from where it stopped

A draw is a list of choices. Here each choice is a node whose options are sorted by chance, and a path of option ranks (0 is the most
likely) names one run of the walk. A run takes the ranks of its path, and then rank 0 at each choice it makes past them, so one run
gives one path to the end of a clause. At each choice from the last of the path on, the run puts the next rank of that choice in the
frontier, with the chance of the path up to it times that option's chance, which is an upper bound on every clause below it. The
frontier is a heap on those bounds. A run that ends in a clause puts the clause there with its own chance; the clause is given
when it is the best entry (with eager, it is given at once, and the order is only about descending: a clause is out of place
by the gap between its chance and the best bound at its run). The run replays its path from the empty clause: S's caches (S.Drawer) hold the decoder's answers and the
steers' scores, so a replay costs less than a draw.

A choice is any call of the walk's `rng`: Chooser stands in for the random.Random of the Run, so `rng.random() < p` is a coin with chance p,
`rng.choices`, `rng.choice`, `rng.randrange` and `rng.sample` are categorical, and LiveDrawer.pick (SearchDrawer.pick here) takes the options of
S.Drawer's picks. Where a draw refuses a try and tries again (an atom that fails a gate, a stop that a gate refuses, a form that the
decoder refuses), the path ends: the clause that a retry reaches is also reached by the path that makes the right choice at first
(the gates read the clause alone), and that path has the greater chance. A clause q counts the first try's chances alone, as
the estimate of a clause's rank does. The counts of the Run name each refusal (REJECTS), and Counts ends the path at the count.

With OR_BITS above 0, the bound of a path that takes a body's OR is lower by that many bits (a clause's logq too), so a run that takes an OR
comes after plain runs of about the same chance. The order of the options at a choice stays the order of their chances.

A path's ranks give the same options only under the same weights, so a Search reads the forms that UNREAD_BETA raises once, when it is made, and keeps them (Search.unread).

A clause whose atoms, read as a set with their labels renamed, were reached by another path stops there (Run.seen). clause_key
gives the same key to a clause whatever the order of its atoms and the names of its labels.

A worker restarts, and has memory for few searches. So the state of a search is small and in a file, and a Manager (one per Sampler) decides
which searches keep their caches:
    sampler.search_store(directory, hot=64, limit_mib=None, save_every=10.0, keep_cold=4, retries=0)   # before the first search
The state is the frontier (a heap entry is a run's ranks and the index of a choice in them), the seen atom sets, the answers of
Run.jc (a walk reads them, so a path gives the same clause only with them), Search.unread, the keys of the clauses given, and the paths that
a death ended. Everything else (the caches of the Drawers, the decoders in memo, the Clauses waiting in the heap) is made again from the
state, at the cost of the first runs being slower. Keys are numbers that stable() makes, the same in every process. The Journal keeps
what a death would lose, so that a restart does not try the path of the run in flight, keeps that run's siblings, and does not give a clause
twice. Search.skip(clause) is for a caller whose own step on a clause failed.
"""
import collections
import functools
import gc
import hashlib
import heapq
import io
import itertools
import json
import math
import mmap
import os
import re
import struct
import sys
import zlib

import numpy as np

import live
from live import ALSO_TOK, Clause, Drop, LiveDrawer, M, Run, S, Spent, arclog

REJECTS = ('try:', 'gate:', 'or:try:', 'or:fail', 'or:branch retry', 'or:empty', 'or:unsafe', 'form:')  # the names, in Run.c, of a refused try
FRONTIER_CAP = 400000  # entries of the frontier, the lowest bounds dropped first
SEEN_CAP = 2000000  # atom sets that Search.seen keeps
OR_BITS = 3.0  # bits taken off the bound of a path for each OR it takes: a run that takes an OR costs more CPU, so its clauses come after plain ones of about the same q
LN2 = math.log(2)
TOKEN = re.compile(r'\(|\)|[^\s()]+')
MASK = (1 << 64) - 1


def stable(text):
    """A 64-bit number of the text that is the same in every process (hash() of a str is not)."""
    return int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), 'little')


class Dead(BaseException):
    """The path ends: a refused try, or an atom set that another path reached. BaseException, so that no `except Exception` of the walk takes it."""


class Mismatch(Exception):
    """A replay found fewer options at a choice than its path says: the walk was not the same."""


# ---------------------------------------------------------------- a clause as a key

def parse(text):
    """The s-expression of text as nested lists of strings."""
    stack = [[]]
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]


def flat(x):
    for y in x:
        if isinstance(y, list):
            yield from flat(y)
        else:
            yield y


def draw(x, color, mark=None):
    """x as a string: a label by its color, and the label mark as '@'. The children of a node that are all lists, as the sites of an
    atom or the atoms of a branch, are in sorted order."""
    if isinstance(x, str):
        s = x.lstrip('*')
        if s in color:
            return '@' if s == mark else '#%d' % color[s]
        return x
    parts = [draw(y, color, mark) for y in x]
    if parts and all(isinstance(y, list) for y in x):
        parts.sort()
    elif len(x) > 1 and isinstance(x[0], str) and all(isinstance(y, list) for y in x[1:]):
        parts = parts[:1] + sorted(parts[1:])
    return '(' + ' '.join(parts) + ')'


def atoms_key(atoms):
    """A hashable key of atoms, the texts or parsed atoms of a conjunction: the same for any order of the atoms and any names of the
    labels (a label is a name that a '*' marks once at least). The labels get colors by refining the multiset of the atoms around
    each; two labels with the same neighbours get one color, so the key can be the same for clauses that differ."""
    parsed = [x if isinstance(x, list) else (parse(x) or [[]])[0] for x in atoms]
    labels = {t[1:] for a in parsed for t in flat(a) if t.startswith('*') and len(t) > 1}
    color = dict.fromkeys(labels, 0)
    where = {l: [a for a in parsed if any(t.lstrip('*') == l for t in flat(a))] for l in labels}
    for _ in range(3):
        color = {l: zlib.crc32('\x1f'.join(sorted(draw(a, color, l) for a in where[l])).encode()) for l in labels}
    return tuple(sorted(draw(a, color) for a in parsed))


@functools.lru_cache(maxsize=1 << 12)
def _key(text):
    forms = parse(text)
    if not forms or not forms[0]:
        return ()
    form = forms[0]
    return (form[0],) + atoms_key(form[2:])


def clause_key(text):
    """A key of the clause text, a form such as (RULE &head atom ...): its kind and atoms, with no head name; the same for any order
    of the atoms and any names of the labels."""
    return _key(text)


# ---------------------------------------------------------------- the choices of a run

class Coin:
    """What `rng.random()` gives: a comparison with p is a choice with chance p of being less."""

    def __init__(self, chooser):
        self.ch = chooser

    def __lt__(self, p):
        return self.ch.coin(p)

    def __le__(self, p):
        return self.ch.coin(p)

    def __gt__(self, p):
        return not self.ch.coin(p)

    def __ge__(self, p):
        return not self.ch.coin(p)


class Chooser:
    """The rng of a Run in a search. start(path) begins a run, which takes the ranks of path and then rank 0; `taken` gets the rank
    taken at each choice, and `sibs` gets the next rank at each choice from the path's last on, as (index of the choice, log bound):
    its path is the ranks taken before the choice and then rank + 1. `jr`, where a Journal is set, gets each of those."""

    jr = None

    or_bits = 0.0  # OR_BITS of the run
    or_next = False  # the next coin is a body's OR coin (SearchRun.p_or)

    def start(self, path):
        self.ranks, self.i, self.logp, self.taken, self.hash, self.sibs = path, 0, 0.0, [], 0, []
        self.or_next = False

    def node(self, probs, cost=0.0):
        """The index in probs (chances that sum to 1, as a list) of the option that the run takes here. cost is the bits off the bound of
        option 0, which is the OR of an OR coin; the order of the options stays that of their chances."""
        i, ranks = self.i, self.ranks
        self.i = i + 1
        n = len(probs)
        if n == 2:
            order = (0, 1) if probs[0] >= probs[1] else (1, 0)
        else:
            order = sorted(range(n), key=lambda j: -probs[j]) if n < 40 else np.argsort(-np.asarray(probs), kind='stable').tolist()
        r = ranks[i] if i < len(ranks) else 0
        if r >= n or probs[order[r]] <= 0:
            raise Mismatch
        if i >= len(ranks) - 1 and r + 1 < n and probs[order[r + 1]] > 0:
            logb = self.logp + math.log(probs[order[r + 1]]) - (cost * LN2 if order[r + 1] == 0 else 0.0)
            self.sibs.append((i, logb))
            if self.jr is not None:
                self.jr.sib(i, logb)
        self.logp += math.log(probs[order[r]]) - (cost * LN2 if order[r] == 0 else 0.0)
        self.taken.append(r)
        self.hash = (self.hash * 1099511628211 + r + 1) & MASK  # a number that is the same in every process
        return order[r]

    def coin(self, p):
        cost, self.or_next = (self.or_bits if self.or_next else 0.0), False
        if p >= 1:
            return True
        if p <= 0:
            return False
        return self.node([p, 1.0 - p], cost) == 0

    def pick(self, opts, weights):
        """S.Drawer.pick's (option, its share of the weights)."""
        tot = sum(weights)
        if not tot > 0:
            raise Dead
        if len(opts) == 1:
            return opts[0], 1.0
        j = self.node([w / tot for w in weights])
        return opts[j], weights[j] / tot

    def random(self):
        return Coin(self)

    def seed(self, *_):
        pass

    def choices(self, population, weights=None, k=1):
        assert k == 1
        return [self.pick(list(population), list(weights) if weights is not None else [1.0] * len(population))[0]]

    def choice(self, seq):
        return seq[self.node([1.0 / len(seq)] * len(seq))] if len(seq) > 1 else seq[0]

    def randrange(self, n):
        return self.node([1.0 / n] * n) if n > 1 else 0

    def sample(self, population, k):
        """k of the population as a set is, in the order of the population."""
        combos = list(itertools.combinations(range(len(population)), k))
        got = combos[self.node([1.0 / len(combos)] * len(combos))] if len(combos) > 1 else combos[0]
        return [population[j] for j in got]


class Counts(collections.Counter):
    """Run.c: the count of a refused try ends the path."""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if isinstance(key, str) and key.startswith(REJECTS):
            raise Dead(key)


SHARED = 'rel_pre', 'srel_cache', 'rel_dag_f', 'rel_dag_p'  # the Drawer caches that the Drawers of one scope and kind share
SHARED_HIDDEN = 'rel_cache', 'choice_cache', 'roots'  # those whose entries also depend on the labels that a frontier hides
MEMO_CAP = 3000  # decoders whose table, or whose END check, Run keeps
INIT_STORES = 64  # paths to INIT bodies whose caches the run keeps
ROOT_CAP = 512  # atom-start frontiers that the Drawers of a scope share


class Hidden:
    """A Drawer's view of a cache that Drawers share: its keys have the labels that the Drawer's frontier hides, which the nodes and the
    options of an atom start depend on."""

    def __init__(self, store, fr):
        self.store, self.fr = store, fr

    def get(self, key, default=None):
        return self.store.get((key, self.fr.hidden), default)

    def __setitem__(self, key, value):
        self.store[key, self.fr.hidden] = value

    def __len__(self):
        return len(self.store)

    def clear(self):
        self.store.clear()


class SearchDrawer(LiveDrawer):
    """LiveDrawer with the picks of the search."""

    cache_cap = 1 << 20

    def pick(self, opts, weights):
        if self.force is not None:
            return super().pick(opts, weights)
        return self.rng.pick(opts, weights)

    def pick_complete(self, n, opts, weights, key, alt=None):
        """S's, where a start that completable refuses ends the path in place of a pick over the rest."""
        self.alt_q = None
        o, q = self.pick(opts, weights)
        if self.force is None and S.COMPLETE and o not in M.CMP and not self.completable(n, o, key):
            self.complete_drops += 1
            raise Dead('complete')
        return o, q

    def pick_reach(self, n, opts, weights, alt=None):
        """S's, where an option that cannot reach the atom's end ends the path."""
        self.alt_q = None
        o, q = self.pick(opts, weights)
        if self.force is None and S.REACH and self.fr.KIND[o] != 'column':
            ch = self.fr.child(n, o)
            if ch is None or not self.reach(ch):
                self.reach_drops += 1
                raise Dead('reach')
        return o, q


class SearchRun(Run):
    """A Run whose rng is a Chooser."""

    drawer_class = SearchDrawer

    def __init__(self, pri, session, deadline, task, limits):
        super().__init__(pri, session, 0, deadline, task, limits)
        self.rng = Chooser()
        self.rng.or_bits = OR_BITS
        self.c = Counts(self.c)
        self.seen = {}  # stable number of (body context, atoms as a set) -> low 32 bits of the hash of the path that reached it
        self.shared = collections.defaultdict(dict)  # (kind, place, path) -> the caches that Drawers of one scope share
        self.memo = {}  # (what, id of a decoder) -> (the decoder, the answer): a decoder of a node that a shared root keeps stays the same one

    def drawer(self, pg, kind, dec, place=None, prior=None):
        dr = super().drawer(pg, kind, dec, place, prior)
        dr.ctx = self.rng.hash
        if kind == 'INIT':  # an INIT body reads what its component and the bodies before it fixed, so a store is for one path to the body
            if len(self.shared) >= INIT_STORES:
                self.shared = collections.defaultdict(dict, {k: v for k, v in self.shared.items() if k[0] != 'INIT'})
            sh = self.shared['INIT', place, dr.ctx]
        else:
            sh = self.shared[kind, None, None]
        for name in SHARED:
            if name in sh:
                setattr(dr, name, sh[name])
            else:
                sh[name] = getattr(dr, name)
        for name in SHARED_HIDDEN:
            setattr(dr, name, Hidden(sh.setdefault(name, {}), dr.fr))
        dr.root_cap, dr.node_cap = ROOT_CAP, 1 << 30
        return dr

    def forget_slots(self):
        """Run's drops what the Drawers keep of relation slots when the scope changes. A search has one scope, and the answers in jc are state
        (a walk reads them), which a Search keeps and sets again after its run is made anew."""

    def memoed(self, what, dec, make):
        key = what, id(dec)
        got = self.memo.get(key)
        if got is None:
            if len(self.memo) >= MEMO_CAP:
                self.memo.clear()
            got = self.memo[key] = dec, make()
        return got[1]

    def table(self, fr, dec, pg):
        return self.memoed('table', dec, lambda: super(SearchRun, self).table(fr, dec, pg))

    def can_end(self, d):
        return self.memoed('end', d, lambda: super(SearchRun, self).can_end(d))

    def can_close(self, d):
        return self.memoed('close', d, lambda: super(SearchRun, self).can_close(d))

    def p_or(self, o, k):
        self.rng.or_next = True  # the coin that compares with this chance is the OR coin
        return super().p_or(o, k)

    def set_key(self, dr, atoms, toks):
        return stable(repr((dr.ctx, atoms_key(atoms), tuple(t for t in toks if t in (M.OR, ALSO_TOK, M.END)))))

    def stop_chance(self, dr, k, h, toks, got, tb):
        """Run's, and the end of a path whose atoms as a set another path reached."""
        key = self.set_key(dr, dr.drawn, toks)
        prior, here = self.seen.get(key), self.rng.hash & 0xffffffff
        if prior is None:
            if len(self.seen) >= SEEN_CAP:
                self.seen.clear()
            self.seen[key] = here
        elif prior != here:
            self.c['dup:atoms'] += 1
            raise Dead('atoms')
        return super().stop_chance(dr, k, h, toks, got, tb)


# ---------------------------------------------------------------- the search

REMAT = True  # the clause of a heap entry that has to be made again, by running its path
VERSION = 1  # of the state file
PATH_MAX, SIB_MAX, HAND_MAX, EMIT_MAX = 2048, 2048, 8192, 1 << 13  # what the Journal keeps


@functools.cache
def fingerprint():
    """A number for the code and the data that a walk reads: a state of another one does not fit this process's walk."""
    parts = [VERSION, S.UNREAD_BETA]
    for mod in (sys.modules[__name__], live, live.S):
        with open(mod.__file__, 'rb') as f:
            parts.append(hashlib.blake2b(f.read(), digest_size=8).hexdigest())
    return stable(repr(parts))


def path_of(base, j):
    """The path that a heap entry names: the first j ranks of base and then base[j] + 1, or base itself where j is None."""
    return base if j is None else base[:j] + (base[j] + 1,)


def jx_encode(x):
    """x, a key of Run.jc, as json: a tuple as ['t', ...], a frozenset as ['f', ...]."""
    if isinstance(x, tuple):
        return ['t'] + [jx_encode(y) for y in x]
    if isinstance(x, frozenset):
        return ['f'] + sorted((jx_encode(y) for y in x), key=json.dumps)
    if x is None or isinstance(x, (bool, int, str, float)):
        return x
    raise TypeError(type(x))


def jx_decode(x):
    if isinstance(x, list):
        return tuple(jx_decode(y) for y in x[1:]) if x[0] == 't' else frozenset(jx_decode(y) for y in x[1:])
    return x


def jc_encode(d):
    """Run.jc's dict of one kind as json: [[key, answer]]. An entry whose key has a type that json cannot hold is left out."""
    out = []
    for k, v in d.items():
        try:
            out.append([jx_encode(k), v])
        except TypeError:
            pass
    return out


def jc_decode(rows):
    return {jx_decode(k): v for k, v in rows}


class Search:
    """The frontier of one scope and kind. Iterating gives Clauses until `deadline`; a later iteration goes on.

    A heap entry is (-log bound, tie, base, j, clause). Where clause is None the entry is a path to run: base is the ranks that a run
    took (all its choices), and path_of(base, j) is the path. Where clause is a Clause the entry is that clause, waiting for its turn,
    and base is the path that made it; where clause is REMAT the Clause is to be made again by running base.

    With a Disk, save() writes the state to a file, and the next Search of the scope starts from it (Manager). Between saves a Journal
    keeps the run in flight with the siblings it made so far, and the number of each clause given, so that a process that dies loses
    none of them: the path of the run in flight is never run again (poison), the siblings it made are kept, and the clause that was in
    the caller's hand is never given again (`casualties` names them).
    """

    def __init__(self, run, forms, kind, cap, eager=True, unread=None):
        self.run, self.forms, self.kind, self.cap, self.eager = run, tuple(forms), kind, cap or FRONTIER_CAP, eager
        self.unread = unread  # Run.unread of each run of this Search
        self.deadline = run.deadline
        self.heap = [(0.0, 0, (), None, None)]
        self.nties = 0
        self.floor = -math.inf  # entries with a log bound below this are not kept
        self.dropped = -math.inf  # the greatest log bound of an entry dropped for the cap
        self.emitted = set()  # stable numbers of the keys of the clauses given
        self.pending = {}  # stable number of a clause key -> log q of its entry in the heap
        self.stats = collections.Counter()
        self.on_leaf = None  # a function of each new clause's key, called when its run ends
        self.poison = set()  # paths whose run ended in a death: never run
        self.strikes = {}  # a path -> the deaths it was in at the loads so far
        self.retries = 0  # the deaths a path is in before it is not tried again
        self.casualties = []  # what the deaths left: ['path', ranks] or ['clause', text]
        self.seen_kept = self.jc_kept = None  # run.seen and run.jc, while the Search has no run
        self.ctx = None  # (pri, session, task, limits) while it has a run
        self.mgr = self.disk = self.jr = None
        self.fp = 0  # fingerprint of the code and data of the walk (Manager)
        self.dirty = 0  # runs and gives since the last save
        self.last_save = 0.0

    def __iter__(self):
        return self.clauses()

    @property
    def exhausted(self):
        return not self.heap and self.dropped == -math.inf

    def push(self, logb, base, j, clause=None):
        if logb < self.floor:
            self.dropped = max(self.dropped, logb)
            return
        self.nties += 1
        heapq.heappush(self.heap, (-logb, self.nties, base, j, clause))
        if len(self.heap) > self.cap * 1.25:
            self.heap = heapq.nsmallest(self.cap, self.heap)  # a sorted list is a heap
            self.floor = -self.heap[-1][0]
            self.stats['dropped'] += 1

    def skip(self, clause):
        """Never gives the clause again: a Clause, its text, or its key. For a caller whose step on that clause failed."""
        key = clause.key if isinstance(clause, live.Clause) else clause_key(clause) if isinstance(clause, str) else clause
        kd = stable(repr(key))
        self.emitted.add(kd)
        self.dirty += 1
        if self.jr is not None:
            self.jr.emit(kd)

    def clauses(self):
        st = self.stats
        if self.run is None:
            raise RuntimeError('this Search gave up its run (Manager.demote): ask Sampler.search again')
        self.run.deadline = self.deadline
        try:
            while self.heap:
                if self.run is None:  # another call gave this scope's run up
                    return
                entry = self.heap[0]
                nb, tie, base, j, clause = entry
                if clause is not None and clause is not REMAT:
                    heapq.heappop(self.heap)
                    if clause.kd in self.emitted:
                        continue
                    yield from self.give(clause)
                    continue
                if time_up(self.deadline):
                    return self.leave()
                heapq.heappop(self.heap)
                path = path_of(base, j)
                if path in self.poison:
                    st['poison'] += 1
                    continue
                ok, new = self.step(path, clause is REMAT)
                if not ok:
                    heapq.heappush(self.heap, entry)
                    return self.leave()
                if new is not None:
                    yield from self.give(new)
                self.dirty += 1
                if self.mgr is not None and not self.dirty & 15:
                    self.mgr.tick(self)
            self.leave()
        except GeneratorExit:
            # A caller that dies with a clause in hand ends this generator as the stack of its frame unwinds, as a caller that breaks off a
            # loop does: the Journal keeps the clause (release() frees it), and the state is not saved here.
            if self.jr is None or self.jr.mm.closed or self.jr.mm[8] != Journal.HAND:
                self.leave()
            raise

    def give(self, clause):
        """Yields the clause, with the Journal holding it while the caller does."""
        self.emitted.add(clause.kd)
        self.pending.pop(clause.kd, None)
        self.stats['clauses'] += 1
        jr = self.jr
        if jr is not None:
            jr.hand(clause.kd, clause.text)
        yield clause
        if jr is not None:
            jr.free()

    def release(self):
        """The caller is done with the clause it was given. A worker that renews its process calls this first: the Journal otherwise
        keeps the clause as one that a death found in the caller's hand, and the next process does not give it again."""
        if self.jr is not None:
            self.jr.free()

    def leave(self):
        """At the end of a call: saves where the state changed."""
        if self.mgr is not None:
            self.mgr.leave(self)

    def execute(self, path):
        """Runs the path: (False, None) where the deadline passed in it, else (True, the clause it made or None)."""
        run, ch, st, jr = self.run, self.run.rng, self.stats, self.jr
        run.unread = self.unread
        ch.start(path)
        ch.jr = jr
        st['runs'] += 1
        if jr is not None:
            jr.begin(path)
        clause = None
        t0 = live.time.process_time()
        try:
            dec, pg = run.scope(self.forms)
            f = run.form(pg, dec, self.kind)
            clause = run.clause_of(self.forms, pg, f)
        except Dead as e:
            st['dead'] += 1
            st['dead:' + re.sub(r'\d+', 'N', str(e))[:30]] += 1
            st['seconds dead'] += live.time.process_time() - t0
            st['seconds dead:' + re.sub(r'\d+', 'N', str(e))[:30]] += live.time.process_time() - t0
        except live.Deadline:
            st['runs'] -= 1
            if jr is not None:
                jr.end()
            return False, None
        except Mismatch:
            st['mismatch'] += 1
        except (Drop, arclog.Refusal, arclog.Fault) as e:
            st['failed'] += 1
            run.failed(e)
        except Exception as e:  # noqa: BLE001
            st['error'] += 1
            run.failed(e)
        except (KeyboardInterrupt, SystemExit):
            if jr is not None:
                jr.end()
            raise
        # any other BaseException, as a panic of the engine is, leaves the Journal holding this run, for the next process
        if jr is not None:
            jr.end()
        st['seconds'] += live.time.process_time() - t0
        if clause is not None:
            st['seconds clause'] += live.time.process_time() - t0
        return True, clause

    def step(self, path, remat=False):
        """Runs path: (False, None) where the deadline passed in it, else (True, the clause to give now or None). A run again (remat)
        makes no entries."""
        ok, clause = self.execute(path)
        if not ok:
            return False, None
        ch, st = self.run.rng, self.stats
        if not remat:
            base = tuple(ch.taken)
            for j, logb in ch.sibs:
                self.push(logb, base, j)
        if clause is None:
            return True, None
        key = clause.key = clause_key(clause.text)
        kd = clause.kd = stable(repr(key))
        clause.logq = ch.logp
        if self.on_leaf:
            self.on_leaf(key)
        if kd in self.emitted or (not self.eager and not remat and self.pending.get(kd, -math.inf) >= ch.logp):
            st['dup clause'] += 1
        elif self.eager or remat:
            if '(OR ' in clause.text:
                st['or clauses'] += 1
            return True, clause
        else:
            self.pending[kd] = ch.logp
            self.push(ch.logp, base, None, clause)
        return True, None

    # ---------------------------------------------------------------- giving up a run, and the state in a file

    def attach(self, run, ctx=None):
        """Makes run the Search's, with the seen atom sets the Search kept."""
        self.run, self.ctx = run, ctx
        if self.seen_kept is not None:
            run.seen, run.jc = self.seen_kept, self.jc_kept
            self.seen_kept = self.jc_kept = None
        run.deadline = self.deadline
        if self.jr is not None:
            run.rng.jr = self.jr

    def demote(self):
        """Gives up the run, and so its caches, its decoders and its session. What stays is the frontier, the seen atom sets and the keys of
        the clauses given. A Clause waiting in the heap is made again, by its path, when its turn comes."""
        if self.run is None:
            return
        self.seen_kept, self.jc_kept = getattr(self.run, 'seen', {}), getattr(self.run, 'jc', None)
        self.heap = [(nb, tie, base, j, REMAT if clause is not None else None) for nb, tie, base, j, clause in self.heap]
        self.run = self.ctx = None

    def encode(self, gen):
        """The state as bytes: arrays in an npz, and the rest as json."""
        bases, ids = [], {}
        n = len(self.heap)
        negb, tie, bid, jj, isclause = np.empty(n, '<f8'), np.empty(n, '<i8'), np.empty(n, '<i4'), np.empty(n, '<i4'), np.empty(n, 'u1')
        for i, (nb, t, base, j, clause) in enumerate(self.heap):
            b = ids.get(id(base))
            if b is None:
                b = ids[id(base)] = len(bases)
                bases.append(base)
            negb[i], tie[i], bid[i], jj[i], isclause[i] = nb, t, b, -1 if j is None else j, clause is not None
        lens = np.fromiter(map(len, bases), '<u4', len(bases))
        flat = np.fromiter(itertools.chain.from_iterable(bases), '<u4', int(lens.sum()))
        if len(flat) and int(flat.max()) < 1 << 16:
            flat = flat.astype('<u2')
        seen = (self.run.seen if self.run is not None else self.seen_kept) or {}
        jc = (self.run.jc if self.run is not None else self.jc_kept) or {}
        meta = dict(v=VERSION, scope=self.disk.scope, gen=gen, nties=self.nties, floor=None if self.floor == -math.inf else self.floor,
                    dropped=None if self.dropped == -math.inf else self.dropped, stats=dict(self.stats), fp=self.fp,
                    poison=[list(x) for x in self.poison], casualties=self.casualties,
                    strikes=[[list(k), n] for k, n in self.strikes.items()], jc={kind: jc_encode(d) for kind, d in jc.items()}, unread=self.unread)
        buf = io.BytesIO()
        np.savez_compressed(buf, meta=np.frombuffer(json.dumps(meta).encode(), 'u1'), negb=negb, tie=tie, bid=bid, j=jj, kind=isclause, lens=lens, flat=flat,
                            seen_k=np.fromiter(seen.keys(), '<u8', len(seen)), seen_v=np.fromiter(seen.values(), '<u4', len(seen)),
                            emitted=np.fromiter(self.emitted, '<u8', len(self.emitted)),
                            pend_k=np.fromiter(self.pending.keys(), '<u8', len(self.pending)), pend_v=np.fromiter(self.pending.values(), '<f8', len(self.pending)))
        return buf.getvalue()

    def decode(self, data):
        """Sets the state from encode's bytes; gives the generation of the file."""
        z = np.load(io.BytesIO(data), allow_pickle=False)
        meta = json.loads(z['meta'].tobytes())
        if meta['v'] != VERSION or meta['scope'] != self.disk.scope:
            raise ValueError('state of another scope or version')
        lens, flat = z['lens'].tolist(), z['flat'].tolist()
        bases, at = [], 0
        for k in lens:
            bases.append(tuple(flat[at:at + k]))
            at += k
        heap = [(nb, t, bases[b], None if j < 0 else j, REMAT if k else None)
                for nb, t, b, j, k in zip(z['negb'].tolist(), z['tie'].tolist(), z['bid'].tolist(), z['j'].tolist(), z['kind'].tolist())]
        emitted, pending = set(z['emitted'].tolist()), dict(zip(z['pend_k'].tolist(), z['pend_v'].tolist()))
        seen = dict(zip(z['seen_k'].tolist(), z['seen_v'].tolist()))
        poison = {tuple(x) for x in meta['poison']}
        strikes = {tuple(k): n for k, n in meta['strikes']}
        jc = collections.defaultdict(dict, {kind: jc_decode(d) for kind, d in meta['jc'].items()})
        heapq.heapify(heap)
        self.heap, self.emitted, self.pending, self.seen_kept, self.poison = heap, emitted, pending, seen, poison
        self.nties = meta['nties']
        self.floor = -math.inf if meta['floor'] is None else meta['floor']
        self.dropped = -math.inf if meta['dropped'] is None else meta['dropped']
        self.stats = collections.Counter(meta['stats'])
        self.casualties = meta['casualties']
        self.strikes, self.jc_kept = strikes, jc
        if meta['fp'] != self.fp:  # the walk may be another one: only what was given and what died stays
            self.stats['state rejected'] += 1
            self.heap, self.floor, self.dropped, self.pending, self.nties = [(0.0, 0, (), None, None)], -math.inf, -math.inf, {}, 0
            self.seen_kept, self.jc_kept = {}, collections.defaultdict(dict)
        else:
            self.unread = meta['unread']
        return meta['gen']

    def save(self):
        """Writes the state to the Disk's file, and starts its Journal over."""
        if self.disk is None:
            return
        t0 = live.time.perf_counter()
        self.disk.write(self.encode(self.disk.gen + 1))
        self.jr = self.disk.open_journal()
        if self.run is not None:
            self.run.rng.jr = self.jr
        self.dirty = 0
        self.last_save = live.time.monotonic()
        self.stats['saves'] += 1
        self.stats['save seconds'] += live.time.perf_counter() - t0
        self.stats['save bytes'] = self.disk.size

    def recover(self):
        """Reads the Journal that the last process left, and keeps what it holds: the clauses given; after a death in a run, the path
        of that run in the poison and the siblings it made in the heap; after a death with a clause in the caller's hand, that clause
        in the keys given. Where `retries` allows, the path is tried once more instead."""
        old = self.disk.read_journal()
        if old is None:
            return
        emits = old['emits']
        if old['state'] == Journal.RUN:
            self.stats['deaths'] += 1
            path = old['path']
            if path is None:
                self.casualties.append(['path', None])
            else:
                self.strikes[path] = self.strikes.get(path, 0) + 1
                if self.strikes[path] > self.retries:
                    self.casualties.append(['path', list(path)])
                    self.poison.add(path)
                    last = max((j for j, _ in old['sibs']), default=-1)
                    base = path + (0,) * (last + 1 - len(path))
                    for j, logb in old['sibs']:
                        self.push(logb, base, j)
        elif old['state'] == Journal.HAND:  # its number is in the emits
            self.stats['deaths'] += 1
            self.casualties.append(['clause', old['hand'][1]])
        self.emitted.update(emits)
        self.dirty += 1


class Journal:
    """What a process writes as it runs, in a file that it maps into memory: a write to the map is in the system at once, so a process
    that dies (SIGKILL, a panic of the engine) leaves it whole. It holds, since the last save of the state: the run in flight (its path
    and the siblings it made so far), the clause in the caller's hand, and the number of each clause given. A write costs about a microsecond."""

    MAGIC = b'BSJ1'
    IDLE, RUN, HAND = 0, 1, 2
    PATH = 40
    SIB = PATH + 4 * PATH_MAX
    TEXT = SIB + 12 * SIB_MAX
    EMIT = TEXT + HAND_MAX
    SIZE = EMIT + 8 * EMIT_MAX

    def __init__(self, path, gen):
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
        os.ftruncate(fd, self.SIZE)
        self.mm = mmap.mmap(fd, self.SIZE)
        os.close(fd)
        struct.pack_into('<4sI', self.mm, 0, self.MAGIC, gen)
        self.nsib = self.nemit = 0

    @property
    def full(self):
        return self.nemit >= EMIT_MAX - 1

    def begin(self, path):
        mm, n = self.mm, len(path)
        if n <= PATH_MAX:
            mm[self.PATH:self.PATH + 4 * n] = struct.pack('<%dI' % n, *path)
        struct.pack_into('<II', mm, 12, n if n <= PATH_MAX else 0xFFFFFFFF, 0)
        self.nsib = 0
        mm[8] = self.RUN

    def sib(self, j, logb):
        k = self.nsib
        if k < SIB_MAX:
            struct.pack_into('<Id', self.mm, self.SIB + 12 * k, j, logb)
            self.nsib = k + 1
            struct.pack_into('<I', self.mm, 16, k + 1)

    def end(self):
        if not self.mm.closed:
            self.mm[8] = self.IDLE

    def emit(self, kd):
        k = self.nemit
        if k < EMIT_MAX:
            struct.pack_into('<Q', self.mm, self.EMIT + 8 * k, kd)
            self.nemit = k + 1
            struct.pack_into('<I', self.mm, 32, k + 1)

    def hand(self, kd, text):
        mm = self.mm
        raw = text.encode()[:HAND_MAX]
        mm[self.TEXT:self.TEXT + len(raw)] = raw
        struct.pack_into('<IQ', mm, 20, len(raw), kd)
        self.emit(kd)
        mm[8] = self.HAND

    def free(self):
        if not self.mm.closed:
            self.mm[8] = self.IDLE

    def close(self):
        self.mm.close()

    @classmethod
    def read(cls, path, gen):
        """What the journal of generation gen holds, or None where there is none or it is of another generation."""
        try:
            with open(path, 'rb') as f:
                head = f.read(cls.PATH)
                if len(head) < cls.PATH or head[:4] != cls.MAGIC or struct.unpack_from('<I', head, 4)[0] != gen:
                    return None
                state = head[8]
                plen, nsib, hlen, hdig, nemit = struct.unpack_from('<IIIQI', head, 12)
                out = dict(state=state, path=None, sibs=[], hand=None, emits=[])
                if state == cls.RUN and plen <= PATH_MAX:
                    out['path'] = struct.unpack('<%dI' % plen, f.read(4 * plen))
                    f.seek(cls.SIB)
                    raw = f.read(12 * nsib)
                    out['sibs'] = [struct.unpack_from('<Id', raw, 12 * k) for k in range(nsib)]
                elif state == cls.HAND:
                    f.seek(cls.TEXT)
                    out['hand'] = hdig, f.read(min(hlen, HAND_MAX)).decode(errors='replace')
                f.seek(cls.EMIT)
                out['emits'] = list(struct.unpack('<%dQ' % nemit, f.read(8 * nemit)))
                return out
        except (OSError, struct.error):
            return None


class Disk:
    """The files of one scope: the state, and the Journal beside it."""

    def __init__(self, directory, scope):
        self.scope = scope
        self.path = os.path.join(directory, scope + '.bss')
        self.jpath = os.path.join(directory, scope + '.bsj')
        self.gen = 0
        self.size = 0
        self.journal = None

    def exists(self):
        return os.path.exists(self.path)

    def write(self, data):
        tmp = '%s.%d.tmp' % (self.path, os.getpid())
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, self.path)
        self.gen += 1
        self.size = len(data)

    def read(self):
        with open(self.path, 'rb') as f:
            return f.read()

    def open_journal(self):
        if self.journal is not None:
            self.journal.close()
        self.journal = Journal(self.jpath, self.gen)
        return self.journal

    def read_journal(self):
        return Journal.read(self.jpath, self.gen)

    def close(self):
        if self.journal is not None:
            self.journal.close()
            self.journal = None


# ---------------------------------------------------------------- the searches of a process

def rss_mib():
    """The resident memory of this process, in MiB, or None where it cannot be read."""
    try:
        with open('/proc/self/statm') as f:
            return int(f.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 2 ** 20
    except (OSError, ValueError):
        pass
    try:  # macOS: task_info(MACH_TASK_BASIC_INFO)
        import ctypes
        libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
        info = (ctypes.c_uint64 * 12)()
        count = ctypes.c_uint32(12)
        libc.mach_task_self.restype = ctypes.c_uint32
        if libc.task_info(libc.mach_task_self(), 20, ctypes.byref(info), ctypes.byref(count)) == 0:
            return info[1] / 2 ** 20
    except (OSError, AttributeError):
        pass
    return None


def trim_heap():
    """Gives free heap memory back to the system where the C library can."""
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except (OSError, AttributeError):
        pass


class Manager:
    """The searches of one Sampler (Sampler.searches, the least recently asked for first): which of them keep a run, and so their
    caches, and where the others keep their state.

    hot: the most searches that keep a run; asking for one more gives up the run of the least recently asked for (Search.demote).
    limit_mib: where the resident memory of the process passes it, the least recently asked for search that keeps a run gives it up;
        where only the search in hand is left, it starts over with empty caches (once in TRIM_EVERY seconds at most).
    directory: where a search keeps its state file and its Journal. It saves every save_every seconds (or 20 times as long as a save
        takes, if that is more) and at the end of each call. A search that gave up its run, beyond keep_cold of them, is saved and let
        go from memory, and the next ask for its scope reads the file, as a new process asking for a scope with a file does.
        One process at a time uses a directory.
    retries: how many deaths a path can be in before it is skipped for good. With 0, a death costs that one path, and the clause it
        would have made. With 1, a path that a kill from outside ended is tried again and loses nothing, and a path that makes the
        engine panic costs two deaths. A clause that was in the caller's hand at a death is never given again, whatever `retries` is.
    """

    TRIM_EVERY = 5.0

    def __init__(self, sampler, directory=None, hot=64, limit_mib=None, save_every=10.0, keep_cold=4, retries=0):
        self.sampler, self.scopes = sampler, sampler.searches
        self.directory, self.hot, self.limit_mib, self.save_every, self.keep_cold, self.retries = directory, hot, limit_mib, save_every, keep_cold, retries
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.tasks = {}  # id(task) -> (task, its stable number)
        self.fp = stable(repr((fingerprint(), sorted((k, len(v)) for k, v in sampler.pri.items() if hasattr(v, '__len__')))))
        self.checked = self.trimmed = 0.0
        self.counts = collections.Counter()  # demoted, shed, trimmed

    def digest(self, task):
        got = self.tasks.get(id(task))
        if got is None or got[0] is not task:
            if len(self.tasks) >= 64:
                self.tasks.clear()
            got = self.tasks[id(task)] = task, stable(json.dumps(task, sort_keys=True))
        return got[1]

    def get(self, session, deadline, task, forms, kind, lim, cap, eager, unread=None):
        """Sampler.search's Search: the one of the scope, or a new one that goes on from the scope's file."""
        forms = tuple(forms)
        key = self.digest(task), forms, kind, lim, eager
        got = self.scopes.pop(key, None)
        ctx = self.sampler.pri, session, task, lim
        if got is not None and got.run is not None and got.run.session is not session:
            got.demote()
        if got is None:
            got = Search(SearchRun(self.sampler.pri, session, deadline, task, lim), forms, kind, cap, eager, unread)
            got.mgr, got.ctx, got.retries, got.fp = self, ctx, self.retries, self.fp
            if self.directory:
                got.disk = Disk(self.directory, '%016x' % stable(repr((key[0], forms, kind, lim, eager, VERSION))))
                self.open_disk(got)
        elif got.run is None:
            got.attach(SearchRun(self.sampler.pri, session, deadline, task, lim), ctx)
            if got.disk is not None and got.jr is None:
                got.jr = got.disk.open_journal()
                got.run.rng.jr = got.jr
        self.scopes[key] = got
        got.deadline = deadline
        got.run.deadline = deadline
        self.balance(got)
        return got

    def open_disk(self, got):
        """Sets a new Search from its file where there is one, and writes the file."""
        d = got.disk
        if d.exists():
            try:
                d.gen = got.decode(d.read())
                got.recover()
                got.attach(got.run, got.ctx)
            except Exception:  # noqa: BLE001 - a file that cannot be read is no reason for the worker to stop
                got.stats['state unreadable'] += 1
                os.replace(d.path, d.path + '.bad')
                d.gen = 0
        got.save()

    def balance(self, cur):
        """Gives up the runs beyond `hot`, and saves and lets go the states beyond keep_cold."""
        hot = [s for s in self.scopes.values() if s.run is not None and s is not cur]
        while len(hot) >= self.hot:
            self.demote(hot.pop(0))
        if self.directory:
            cold = [k for k, s in self.scopes.items() if s.run is None]
            for k in cold[:max(len(cold) - self.keep_cold, 0)]:
                s = self.scopes.pop(k)
                s.save()
                s.disk.close()

    def demote(self, s, collect=False):
        """Saves s and gives up its run (with collect, the process also gives its free memory back at once)."""
        s.save()
        s.demote()
        self.counts['demoted'] += 1
        if s.jr is not None:
            s.disk.close()
            s.jr = None
        if collect:
            trim_heap()

    def due(self, s, now):
        """Whether s is to be saved: save_every seconds, or 20 times as long as a save takes, since the last, or its Journal is full."""
        return s.disk is not None and (now - s.last_save >= max(self.save_every, 20 * s.stats['save seconds'] / max(s.stats['saves'], 1))
                                       or (s.jr is not None and s.jr.full))

    def tick(self, cur):
        """Every few runs of cur: saves it where due, and gives memory back where the process is over its limit."""
        now = live.time.monotonic()
        if self.due(cur, now):
            cur.save()
        if self.limit_mib and now - self.checked >= 1.0:
            self.checked = now
            rss = rss_mib()
            if rss is not None and rss > self.limit_mib:
                self.shed(cur)

    def shed(self, cur):
        others = [s for s in self.scopes.values() if s.run is not None and s is not cur]
        self.counts['shed'] += 1
        if others:
            self.demote(others[0], True)
            return
        now = live.time.monotonic()
        if cur.run is not None and now - self.trimmed >= self.TRIM_EVERY:
            self.trimmed = now
            self.counts['trimmed'] += 1
            ctx = cur.ctx
            cur.demote()
            trim_heap()
            cur.attach(SearchRun(ctx[0], ctx[1], cur.deadline, ctx[2], ctx[3]), ctx)

    def leave(self, s):
        """At the end of a call of s: saves it where due and it changed."""
        if s.dirty and self.due(s, live.time.monotonic()):
            s.save()


def time_up(deadline):
    return live.time.monotonic() >= deadline


def configure(sampler, directory=None, **options):
    """Sets the Manager of the sampler's searches (see Manager)."""
    sampler.search_manager = Manager(sampler, directory, **options)
    return sampler.search_manager


def search(sampler, session, deadline, task, forms, kind, lim, cap, eager=True, unread=None):
    """Sampler.search: the Search of the scope, new or the earlier one with the new deadline."""
    mgr = getattr(sampler, 'search_manager', None) or configure(sampler)
    return mgr.get(session, deadline, task, forms, kind, lim, cap, eager, unread)
