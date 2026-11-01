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

A clause whose atoms, read as a set with their labels renamed, were reached by another path stops there (Search.seen). clause_key
gives the same key to a clause whatever the order of its atoms and the names of its labels.
"""
import collections
import functools
import heapq
import itertools
import math
import re

import numpy as np

import live
from live import ALSO_TOK, Clause, Drop, LiveDrawer, M, Run, S, Spent, arclog

REJECTS = ('try:', 'gate:', 'or:try:', 'or:fail', 'or:branch retry', 'or:empty', 'or:unsafe', 'form:')  # the names, in Run.c, of a refused try
FRONTIER_CAP = 400000  # entries of the frontier, the lowest bounds dropped first
SEEN_CAP = 2000000  # atom sets that Search.seen keeps
TOKEN = re.compile(r'\(|\)|[^\s()]+')


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
        color = {l: hash(tuple(sorted(draw(a, color, l) for a in where[l]))) & 0xffffffff for l in labels}
    return tuple(sorted(draw(a, color) for a in parsed))


@functools.lru_cache(maxsize=1 << 16)
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
    """The rng of a Run in a search. start(path) begins a run, which takes the ranks of path and then rank 0; `sibs` gets the next rank
    at each choice from the path's last on, as (path before the choice, rank, log bound)."""

    def start(self, path):
        self.ranks, self.i, self.logp, self.chain, self.hash, self.sibs = path, 0, 0.0, None, 0, []

    def node(self, probs):
        """The index in probs (chances that sum to 1, as a list) of the option that the run takes here."""
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
            self.sibs.append((self.chain, r + 1, self.logp + math.log(probs[order[r + 1]])))
        self.logp += math.log(probs[order[r]])
        self.chain = (self.chain, r)
        self.hash = hash((self.hash, r))
        return order[r]

    def coin(self, p):
        if p >= 1:
            return True
        if p <= 0:
            return False
        return self.node([p, 1.0 - p]) == 0

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
        self.c = Counts(self.c)
        self.seen = {}  # hash of (body context, atoms as a set) -> hash of the path that reached it
        self.shared = collections.defaultdict(dict)  # (kind, place, path) -> the caches that Drawers of one scope share
        self.memo = {}  # (what, id of a decoder) -> (the decoder, the answer): a decoder of a node that a shared root keeps stays the same one

    def drawer(self, pg, kind, dec, place=None):
        dr = super().drawer(pg, kind, dec, place)
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

    def set_key(self, dr, atoms, toks):
        return hash((dr.ctx, atoms_key(atoms), tuple(t for t in toks if t in (M.OR, ALSO_TOK, M.END))))

    def stop_chance(self, dr, k, h, toks, got, tb):
        """Run's, and the end of a path whose atoms as a set another path reached."""
        key = self.set_key(dr, dr.drawn, toks)
        prior = self.seen.get(key)
        if prior is None:
            if len(self.seen) >= SEEN_CAP:
                self.seen.clear()
            self.seen[key] = self.rng.hash
        elif prior != self.rng.hash:
            self.c['dup:atoms'] += 1
            raise Dead('atoms')
        return super().stop_chance(dr, k, h, toks, got, tb)


# ---------------------------------------------------------------- the search

class Search:
    """The frontier of one scope and kind. Iterating gives Clauses until `deadline`; a later iteration goes on."""

    def __init__(self, run, forms, kind, cap, eager=True):
        self.run, self.forms, self.kind, self.cap, self.eager = run, tuple(forms), kind, cap or FRONTIER_CAP, eager
        self.deadline = run.deadline
        self.heap = [(0.0, 0, None, None)]  # (-log bound, tie, path, clause): a path to run, or a clause
        self.tie = itertools.count(1)
        self.floor = -math.inf  # entries with a log bound below this are not kept
        self.dropped = -math.inf  # the greatest log bound of an entry dropped for the cap
        self.emitted = set()
        self.pending = {}  # clause key -> log q of its entry in the heap
        self.stats = collections.Counter()
        self.on_leaf = None  # a function of each new clause's key, called when its run ends

    def __iter__(self):
        return self.clauses()

    @property
    def exhausted(self):
        return not self.heap and self.dropped == -math.inf

    def push(self, logb, chain, clause=None):
        if logb < self.floor:
            self.dropped = max(self.dropped, logb)
            return
        heapq.heappush(self.heap, (-logb, next(self.tie), chain, clause))
        if len(self.heap) > self.cap * 1.25:
            self.heap = heapq.nsmallest(self.cap, self.heap)  # a sorted list is a heap
            self.floor = -self.heap[-1][0]
            self.stats['dropped'] += 1

    def clauses(self):
        run, st = self.run, self.stats
        run.deadline = self.deadline
        while self.heap:
            nb, tie, chain, clause = self.heap[0]
            if clause is not None:
                heapq.heappop(self.heap)
                key = clause.key
                if key in self.emitted:
                    continue
                self.emitted.add(key)
                self.pending.pop(key, None)
                st['clauses'] += 1
                yield clause
                continue
            if time_up(self.deadline):
                return
            heapq.heappop(self.heap)
            ok, new = self.step(chain)
            if not ok:
                heapq.heappush(self.heap, (nb, tie, chain, None))
                return
            if new is not None:
                yield new

    def step(self, chain):
        """Runs the path that chain is the end of: (False, None) where the deadline passed in it, else (True, the clause to give now or None)."""
        run, ch, st = self.run, self.run.rng, self.stats
        path = []
        while chain is not None:
            path.append(chain[1])
            chain = chain[0]
        path.reverse()
        ch.start(path)
        st['runs'] += 1
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
            return False, None
        except Mismatch:
            st['mismatch'] += 1
        except (Drop, arclog.Refusal, arclog.Fault) as e:
            st['failed'] += 1
            run.failed(e)
        except Exception as e:  # noqa: BLE001
            st['error'] += 1
            run.failed(e)
        st['seconds'] += live.time.process_time() - t0
        if clause is not None:
            st['seconds clause'] += live.time.process_time() - t0
        for parent, r, logb in ch.sibs:
            self.push(logb, (parent, r))
        if clause is not None:
            key = clause.key = clause_key(clause.text)
            clause.logq = ch.logp
            if self.on_leaf:
                self.on_leaf(key)
            if key in self.emitted or (not self.eager and self.pending.get(key, -math.inf) >= ch.logp):
                st['dup clause'] += 1
            elif self.eager:
                self.emitted.add(key)
                st['clauses'] += 1
                return True, clause
            else:
                self.pending[key] = ch.logp
                self.push(ch.logp, None, clause)
        return True, None


def time_up(deadline):
    return live.time.monotonic() >= deadline


def search(sampler, session, deadline, task, forms, kind, lim, cap, eager=True):
    """Sampler.search: the Search of the scope, new or the earlier one with the new deadline."""
    key = id(session), tuple(forms), kind, lim, eager
    got = sampler.searches.get(key)
    if got is None or got.run.session is not session:
        if len(sampler.searches) >= 64:
            sampler.searches.clear()
        run = SearchRun(sampler.pri, session, deadline, task, lim)
        got = sampler.searches[key] = Search(run, forms, kind, cap, eager)
    got.deadline = deadline
    return got
