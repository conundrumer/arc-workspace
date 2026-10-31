#!/usr/bin/env python
"""S from an empty prefix on a task it has never seen: whole programs through a live decoder.

    sampler = Sampler(models_dir)            # loads the frozen priors (live_priors.py) once
    for result in sampler.draws(session, seed, deadline, **limits): ...

The worker makes the arclog.Session and passes it in; a session on Kaggle data is World.Open, and draws make no second
session. deadline is a time.monotonic() value. limits are Limits' fields. A Result is yielded as soon as it exists: a decoder
that ended at a consistent OUT with its attempts, and a last Result with no decoder when the deadline passes. Each has the
counts so far: draws, finished programs, drops by reason, errors by type, and the limits.

A draw walks the program form by form. The next clause's kind and the program's length come from corpus counts (P alone), a
RULE's atoms and a DET's come from S's Drawer, a DET may take a proposer, an INIT takes a component, and each of its ports takes
a body and a head. The decoder gives every read of the task: its checks, and tables through step_tables; this module reads no
gold and no path but the priors.

OUT is a search, not a draw. A decode ends at its first consistent OUT, so each candidate runs on a fork of the form's end and
the draw goes on past it. At each form end, for each relation R the form declared, in this order: R over the input (R plus the
input's cells where R has none), R alone, then for a Position column with no Color column, the same with a Color relation's
value or the input's color, then unions with earlier relations. Any fit counts.
"""
import collections
import copy
import dataclasses
import gc
import math
import os
import pickle
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sample2_col as S  # noqa: E402
from sample2_col import M, arclog  # noqa: E402

S.ADMITS = True  # one Decoder.admits call per node, with no mask and no per-token call
S.REACH = False  # no look-ahead below a column or a value: an atom that cannot close is redrawn, which costs less

RULE_TOK, DET_TOK, INIT_TOK, OUT_TOK, SKIP_TOK, ALSO_TOK = 0, 1, 2, 7, 12, 13
KIND_TOK = dict(RULE=RULE_TOK, DET=DET_TOK, INIT=INIT_TOK)
TABLES = 'live', 'live'  # step_tables' task and case names; a decoder holds neither, and they only label its result
NEED_BOOST = 4.0  # a port's boost for the types its head needs, as S's at the clause that OUT reads
KIND_BACKOFF = 2.0  # the weight of the next-kind counts over all buckets, against those of the clause count's bucket


@dataclasses.dataclass(frozen=True)
class Limits:
    root_cap: int = S.ROOT_CAP  # atom-start frontiers a clause keeps
    node_cap: int = S.NODE_CAP  # nodes made since the frontiers were last dropped, at which a clause drops them
    atom_tries: int = S.ATOM_TRIES  # redraws of an atom
    cheap_tries: int = S.CHEAP_TRIES  # further redraws for a repeated or unjoined atom
    max_atoms: int = S.MAX_ATOMS  # atoms of a body
    max_forms: int = 40  # clauses of a program before OUT is the only kind
    form_tries: int = 4  # draws of a clause that a gate or the decoder refuses
    out_pairs: int = 6  # (Position, Color) column pairs of a relation that the OUT search tries
    out_colors: int = 4  # Color relations a Position column is painted with
    out_unions: int = 3  # earlier relations a relation is joined with in a union
    out_cands: int = 40  # candidates of the OUT search at one form end


@dataclasses.dataclass
class Result:
    decoder: object  # a decoder that ended at a consistent OUT; None on the last Result
    attempts: object  # decoder.attempts()
    program: str  # decoder.program_form()
    counts: dict  # the draw counts so far
    seconds: float  # since draws began


class Drop(Exception):
    """A draw that cannot go on; the message is the reason."""


class Deadline(Exception):
    """The deadline passed inside a draw."""


class LiveDrawer(S.Drawer):
    """S's Drawer with the limits as arguments."""

    def __init__(self, V, counts, rng, regcols, fr, regtypes, limits):
        super().__init__(V, counts, rng, regcols, fr, regtypes)
        self.root_cap, self.node_cap = limits.root_cap, limits.node_cap


class Program:
    """The state of one draw at a form boundary: its decoder's relations and the last step_tables result."""

    def __init__(self):
        self.ndecl = 0
        self.before = None
        self.decl_types, self.decl_slots = {}, {}
        self.colmap, self.arity, self.record_col, self.names = {}, {}, {}, {}
        self.pending = {}  # relation slot -> (table slot, type) of a relation that colmap lacks
        self.new = []  # the relation slots the last form declared, with their tables
        self.grids, self.colors = [], []  # the OUT search's relations so far: (slot, Position token, Color token); (slot, Color token)
        self.kinds = []


class Sampler:
    def __init__(self, models_dir):
        with open(os.path.join(models_dir, 'live_priors.pkl'), 'rb') as f:
            self.pri = pickle.load(f)
        gc.set_threshold(100000, 50, 100)  # as S: the data is long-lived and holds few cycles

    def draws(self, session, seed, deadline, **limits):
        run = Run(self.pri, session, seed, deadline, Limits(**limits))
        while time.monotonic() < deadline:
            for got in run.one():
                yield run.result(got)
        yield run.result(None)


class Run:
    """One task's draws."""

    def __init__(self, pri, session, seed, deadline, limits):
        self.pri, self.session, self.deadline, self.lim = pri, session, deadline, limits
        self.V = V = session.vocabulary
        self.root = session.decoder()
        self.rng = random.Random(seed)
        self.t0 = time.monotonic()
        self.c = collections.Counter()
        self.ff0 = S.FastFrontier(V, 0, pri['regcols'])
        self.first = {}  # a kind's token -> the decoder after it as a program's first token, and its step_tables result
        self.jc = collections.defaultdict(dict)  # a kind -> Drawer.jcache: its True entries on lib relations hold at every state of the run
        nv = len(V)
        self.rel0 = V.id('&r0')
        self.tok = {V.name(i): i for i in range(nv) if V.kind(i) in ('component', 'proposer')}
        self.columns = sorted(self.ff0.colpos, key=self.ff0.colpos.get)
        facts = {i for i in self.ff0.starts_list if V.kind(i) == 'fact relation'}
        self.lib_starts = [i for i in self.ff0.starts_list if i not in facts]
        self.fact_starts = [i for i in self.ff0.starts_list if i in facts]

    def result(self, dec):
        counts = dict(self.c, limits=dataclasses.asdict(self.lim))
        t = time.monotonic() - self.t0
        return Result(None, None, None, counts, t) if dec is None else Result(dec, dec.attempts(), dec.program_form(), counts, t)

    def one(self):
        """One draw, yielding the decoder of each consistent program it finds."""
        self.c['draws'] += 1
        try:
            yield from self.program()
        except Deadline:
            self.c['drop:deadline'] += 1
        except Drop as e:
            self.c['drop:' + str(e)] += 1
        except arclog.Refusal:
            self.c['drop:refused'] += 1
        except Exception as e:  # noqa: BLE001
            self.c['error:%s: %s' % (type(e).__name__, re.sub(r'\d+', 'N', str(e))[:60])] += 1

    # ---------------------------------------------------------------- a program

    def pick(self, opts, weights):
        return self.rng.choices(opts, weights=weights)[0]

    def next_kind(self, dec, prev, n):
        pri = self.pri
        names = [k for k in KIND_TOK if dec.admits([KIND_TOK[k]])[0]]
        here, all_ = pri['kinds'].get((prev, min(n // 2, 12)), {}), pri['kinds1'].get(prev, {})
        tot = sum(all_.values()) or 1
        ws = [here.get(k, 0) + KIND_BACKOFF * all_.get(k, 0) / tot + 0.01 for k in names]
        return self.pick(names, ws)

    def open_form(self, pg, dec, kind):
        """The decoder after kind's token at dec, a fork. A program's first model step has step_tables' first result."""
        tok = KIND_TOK[kind]
        if pg.before is not None:
            f = dec.fork()
            f.step(tok)
            return f
        if tok not in self.first:
            f = self.root.fork()
            f.step(tok)
            self.first[tok] = f, arclog.step_tables(f, *TABLES, True, None)
        f, pg.before = self.first[tok]
        return f.fork()

    def program(self):
        pg, dec, prev, n = Program(), self.root.fork(), '^', 0
        stop = self.pri['stop']
        for k, j in self.jc.items():
            self.jc[k] = {x: v for x, v in j.items() if v and max(t for t in x if isinstance(t, int)) < self.rel0}
        while n < self.lim.max_forms and not (n and self.rng.random() < stop.get(n, 1.0)):
            kind = self.next_kind(dec, prev, n)
            pg.kinds.append(kind)
            dec = self.form(pg, dec, kind)
            prev, n = kind, n + 1
            self.c['forms'] += 1
            t0 = time.perf_counter()
            yield from self.search(pg, dec)
            self.c['search_seconds'] += time.perf_counter() - t0
        self.c['programs'] += 1

    def form(self, pg, dec, kind):
        """The decoder after a clause of the kind at dec, redrawn where a draw of it fails."""
        for attempt in range(self.lim.form_tries):
            pg.new = []
            saved = copy.copy(pg)
            try:
                f = self.open_form(pg, dec, kind)
                return self.rule(pg, f) if kind == 'RULE' else self.det(pg, f) if kind == 'DET' else self.init(pg, f)
            except (Drop, arclog.Refusal) as e:
                pg.__dict__.update(saved.__dict__)
                why = str(e) if isinstance(e, Drop) else 'refused: ' + re.sub(r'\d+', 'N', str(e))[:70]
                self.c['form:%s %s' % (kind, why)] += 1
        raise Drop('%s: no clause in %d tries' % (kind, self.lim.form_tries))

    def close(self, pg, f):
        """Records the form that the last step of decoder f ended: its relations' tables, for types and columns."""
        pg.before = b = arclog.step_tables(f, *TABLES, True, pg.before)
        T = b.tables
        rel = M.col(b, 'tables', 'relation') if isinstance(T['relation'], (bytes, bytearray, memoryview)) else T['relation']
        for j in range(len(T['form'])):
            if T['fault'][j]:
                raise Drop('relation table fault')
            if rel[j] >= 0:
                s, ts, cs = int(rel[j]), [str(t) for t in T['column_types'][j]], [int(c) for c in T['column_slots'][j]]
                pg.decl_types[s], pg.decl_slots[s] = ts, cs
                pg.new.append(s)
                if cs:
                    pg.pending[s] = list(zip(cs, ts))

    def declared(self, pg, forced):
        for t in forced:
            if self.V.kind(t) == 'relation':
                pg.ndecl = max(pg.ndecl, M.slot_no(self.V.name(t)) + 1)

    def end(self, pg, cur):
        """The decoder after the END of the clause at cur, with the clause's relation recorded."""
        f = cur.fork()
        forced = f.step(M.END)[0]
        self.declared(pg, forced)
        self.close(pg, f)
        return f

    def rule(self, pg, f):
        dr = self.drawer(pg, 'RULE', f)
        return self.end(pg, self.body(pg, dr, f, 'RULE', 0)[0])

    def det(self, pg, f):
        pri = self.pri
        if self.rng.random() < pri['det']['proposer'] / (pri['det']['proposer'] + pri['det']['atoms']):
            names = [p for p in pri['proposers'] if p in self.tok]
            ok = f.admits([self.tok[p] for p in names])
            names = [p for p, y in zip(names, ok) if y]
            if not names:
                raise Drop('no proposer')
            f = f.fork()
            f.step(self.tok[self.pick(names, [pri['proposers'][p] for p in names])])
            return self.end(pg, f)
        dr = self.drawer(pg, 'DET', f)
        return self.end(pg, self.body(pg, dr, f, 'DET', 0)[0])

    def init(self, pg, f):
        pri, rng = self.pri, self.rng
        names = [c for c in pri['comps'] if c in self.tok and c in pri['comp_ports']]
        ok = f.admits([self.tok[c] for c in names])
        names = [c for c, y in zip(names, ok) if y]
        if not names:
            raise Drop('no component')
        comp = self.pick(names, [pri['comps'][c] for c in names])
        f = f.fork()
        forced = f.step(self.tok[comp])[0]
        self.declared(pg, forced)
        slots = [M.slot_no(self.V.name(t)) for t in forced if self.V.kind(t) == 'relation']
        pg.names.update({'&r%d' % s: '&r%d.%d' % (slots[0], i) for i, s in enumerate(slots)})  # a '.' tells a method (one_call)
        params, ports = pri['comp_ports'][comp]
        keyed = rng.random() < pri['keyed'][comp] / pri['comps'][comp]
        nlab, keys = 0, []
        if keyed:  # the key port: one label of its body becomes the key
            dr = self.drawer(pg, 'INIT', f)
            cur, toks = self.body(pg, dr, f, 'INIT', 0)[:2]
            stars = [i for i, t in enumerate(toks) if t == M.STAR]
            if not stars:
                raise Drop('key body makes no label')
            i = stars[rng.randrange(len(stars))]
            keys = [self.ff0.label_tok[stars.index(i)]]
            g = f.fork()
            for j, t in enumerate(toks):
                g.step(M.CARET if j == i else t)
            g.step(M.END)
            f, nlab = g, len(stars)
        else:
            f = f.fork()
            f.step(SKIP_TOK)
        uses = pri['keyed'][comp] if keyed else pri['comps'][comp] - pri['keyed'][comp]
        for name, cols in ports:
            p = (pri['ports'][comp, keyed, name] + 0.1) / (uses + 0.5)
            if rng.random() >= p and f.admits([SKIP_TOK])[0]:
                f = f.fork()
                f.step(SKIP_TOK)
                continue
            f, nlab = self.port(pg, f, comp, name, cols, params, nlab, keys)
        for _ in ports:  # a key group's ports come again after it, for a port that reads no key
            if f.admits([RULE_TOK])[0]:
                break
            f = f.fork()
            f.step(SKIP_TOK)
        if not f.admits([RULE_TOK])[0]:
            raise Drop('%s did not end' % comp)
        self.close(pg, f)
        return f

    def port(self, pg, f, comp, name, cols, params, nlab, keys):
        """The decoder after port name's body and head at f, with the labels of the INIT so far."""
        pri, rng = self.pri, self.rng
        uses = sum(pri['ports'][comp, k, name] for k in (False, True))
        bound = [(c, t) for c, t in cols if rng.random() < (pri['heads'][comp, name, c] + 0.1) / (uses + 0.2)]
        need = [{'Position', 'Box'} if t == 'Point' else next((set(x) for x in pri['families'] if t in x), {t})
                for _, t in bound if t not in params or t == 'Point']
        dr = self.drawer(pg, 'INIT', f)
        dr.want = set(keys)
        cur, toks, _, _ = self.body(pg, dr, f, 'INIT', nlab, need, keys)
        made = list(range(nlab, nlab + toks.count(M.STAR)))
        nlab = made[-1] + 1 if made else nlab
        f = cur.fork()
        f.step(M.END)
        names = {c for c, _ in bound}
        for c, _ in cols:
            labs = [self.ff0.label_tok[i] for i in made if i in self.ff0.label_tok] if c in names else []
            ok = f.admits(labs + [M.END])
            labs = [x for x, y in zip(labs, ok) if y]
            f = f.fork()
            if labs:  # a label of the body, the newest last to be read
                f.step(rng.choice(labs))
                f.step(M.END)
            elif ok[-1]:
                f.step(M.END)
            else:
                raise Drop('head: no label for %s' % name)
        return f, nlab

    # ---------------------------------------------------------------- a body

    def fill_columns(self, pg, dec):
        """colmap and arity of the relations that lack them, at decoder dec, an atom start."""
        if pg.pending:
            pg.colmap.update(S.column_positions(dec, self.V, pg.pending, pg.ndecl))
            for s, e in pg.pending.items():
                pg.arity[self.rel0 + s] = len({c for c, _ in e}) + 2
            pg.pending = {}

    def drawer(self, pg, kind, dec):
        """A Drawer of one body at decoder dec, an atom start, over the relations pg declares."""
        ff = copy.copy(self.ff0)
        decl = list(range(self.rel0, self.rel0 + pg.ndecl))
        ff.starts_list = self.lib_starts + decl + self.fact_starts
        ff.starts = set(ff.starts_list)
        ff.arity, ff.record_col, ff.root, ff.created = pg.arity, pg.record_col, None, 0
        self.fill_columns(pg, dec)
        dr = LiveDrawer(self.V, self.pri['atoms'][kind], self.rng, self.pri['regcols'], ff, self.pri['regtypes'], self.lim)
        dr.prog_names, dr.decl_types, dr.colmap, dr.jcache = pg.names, pg.decl_types, pg.colmap, self.jc[kind]
        dr.need_boost, dr.want_boost = NEED_BOOST, NEED_BOOST
        return dr

    def can_end(self, d):
        try:
            d.forced(M.END)
            return True
        except arclog.Refusal:
            return False

    def atom_scope(self, dr, atom):
        """The types of the labels that drawn atom text makes, where the engine gives no table (inside a port)."""
        m = re.match(r'\((?:NOT \()?(\S+)', atom)
        rtok = self.V.id(m[1]) if m else None
        return [t for p, _ in re.findall(r'\(:(\d+) \*(L\d+)\)', atom) if (t := dr.col_type(rtok, int(p))) is not None] if rtok is not None else []

    def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        """Atoms at decoder dec (with nlab labels before them) until the hazard stops them: (decoder, tokens, atom texts,
        types in scope). Each atom passes the gates that read the decoder alone; a stop passes MIN2_KINDS and the head's needs."""
        lim, c, hz = self.lim, self.c, self.pri['hazard'][kind]
        cur, toks, text, scope = dec, [], [], ()
        for k in range(1, lim.max_atoms + 1):
            if time.monotonic() >= self.deadline:
                raise Deadline
            fr = dr.frontier(cur, nlab + toks.count(M.STAR), tuple(toks))
            dr.need = set().union(*[x for x in need if not x & set(scope)]) if need else set()
            got, free = None, 0
            for n_try in range(lim.atom_tries + lim.cheap_tries):
                if n_try - free >= lim.atom_tries:
                    break
                dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k, tuple(scope), tuple(toks), ()
                res, why = dr.atom(fr, k, scope, tuple(toks))
                if res is None:
                    c['try:construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                    continue
                if k > 1 and not res[4] and res[5]:
                    c['try:unjoined'] += 1
                    free += 1
                    continue
                if res[3] in text:
                    c['try:repeat'] += 1
                    free += 1
                    continue
                if kind != 'INIT' and not self.can_end(res[0].dec):  # at a port's END this check runs a search over head sites
                    c['try:unsafe'] += 1
                    continue
                tb = None if kind == 'INIT' else S.body_table(fr, *TABLES, res[0].dec, pg.before)[0]  # the engine gives no table inside a port
                sm = S.summary(tb)
                if sm is not None and sm['empty_inputs']:
                    c['try:empty'] += 1
                    continue
                got = res
                break
            if got is None:
                raise Drop('atom: no atom in tries')
            cur = got[0].dec
            toks += list(got[0].toks)
            text.append(got[3])
            scope = [str(t) for t in tb['types']] if tb is not None else list(scope) + self.atom_scope(dr, got[3])
            if not self.rng.random() < hz.get(k, hz[max(hz)]) and k < lim.max_atoms:
                continue
            if need and any(not x & set(scope) for x in need):
                c['gate:port head'] += 1
                continue
            if kind == 'INIT' and not self.can_end(cur):
                c['gate:unsafe'] += 1
                continue
            if k == 1 and kind in S.MIN2_KINDS and not S.one_call(dr, text):
                c['gate:one atom'] += 1
                continue
            if keys and not set(keys) & set(toks):
                c['gate:key unread'] += 1
                continue
            return cur, toks, text, scope
        raise Drop('body: no stop in %d atoms' % lim.max_atoms)

    # ---------------------------------------------------------------- the OUT search

    def out_pairs(self, dec, rtok, cap):
        """[(first column token, second column token or None)] that OUT admits on relation token rtok at dec, a form's end."""
        f = dec.fork()
        f.step(OUT_TOK)
        if not f.admits([rtok])[0]:
            return []
        f.step(rtok)
        out = []
        for p, ok in zip(self.columns, f.admits(self.columns)):
            if ok and len(out) < cap:
                g = f.fork()
                g.step(p)
                g.step(M.CARET)
                cs = [c for c, y in zip(self.columns, g.admits(self.columns)) if y]
                out += [(p, c) for c in cs] or [(p, None)]
        return out[:cap]

    def finish(self, dec, rtok, label):
        """OUT over rtok's first pair on a fork of dec: yields the fork where it ends consistent."""
        self.c['out:tried'] += 1
        pairs = [x for x in self.out_pairs(dec, rtok, 1) if x[1] is not None]
        if not pairs:
            self.c['out:no pair'] += 1
            return
        f = dec.fork()
        for t in (OUT_TOK, rtok, pairs[0][0], M.CARET, pairs[0][1], M.CARET):
            f.step(t)
        cons = f.step(M.END)[1]
        self.c['out:%s' % str(getattr(cons, 'kind', None)).rsplit('.', 1)[-1]] += 1
        if f.ended:
            self.c['consistent'] += 1
            self.c['consistent:' + label] += 1
            yield f

    def candidate(self, dec, toks, label):
        """The clause of tokens toks at dec, then OUT over its relation."""
        f = dec.fork()
        try:
            forced = []
            for t in toks:
                forced = f.step(t)[0]
            yield from self.finish(f, next(t for t in forced if self.V.kind(t) == 'relation'), label)
        except arclog.Refusal:
            self.c['out:refused ' + label] += 1
        except arclog.Fault:
            self.c['out:fault ' + label] += 1

    def site(self, pos, value):
        return [self.ff0.col_by_pos[pos], value]

    def cands(self, pg, s, p, c):
        """(label, tokens) of the clauses over relation slot s at column tokens p and c (c None: a Position column alone), by rank."""
        col, lab, inp = self.ff0.colpos, self.ff0.label_tok, self.V.id('input')
        rtok = self.rel0 + s
        cover = [M.NOT, rtok, p, lab[0]]  # (NOT R) at the Position label, which is L0 where p comes first
        if c is not None:
            first, second = (p, c) if col[p] < col[c] else (c, p)
            lp, lc = (lab[0], lab[1]) if first == p else (lab[1], lab[0])
            head = [rtok, first, M.STAR, second, M.STAR]
            cover = [M.NOT, rtok, p, lp]
            read = [inp, self.site(0, lp)[0], lp, self.site(1, lc)[0], lc]
            yield 'overlay', [RULE_TOK, M.OR] + head + [ALSO_TOK] + read + cover + [M.END, M.END]
            yield 'plain', None
            for s2, p2, c2 in pg.grids[:self.lim.out_unions]:
                if s2 != s:
                    other = [self.rel0 + s2] + sum(sorted(([p2, lp], [c2, lc]), key=lambda x: col[x[0]]), [])
                    yield 'union', [RULE_TOK, M.OR] + head + [ALSO_TOK] + other + [M.END, M.END]
                    yield 'overlay2', [RULE_TOK, M.OR] + head + [ALSO_TOK] + other + [ALSO_TOK] + read + cover + [M.NOT, self.rel0 + s2, p2, lp] + [M.END, M.END]
            return
        head = [rtok, p, M.STAR]
        read0 = [inp, self.site(0, lab[0])[0], lab[0]]
        yield 'keep', [RULE_TOK] + head + read0 + [self.site(1, M.STAR)[0], M.STAR, M.END]
        for s2, c2 in pg.colors[:self.lim.out_colors]:
            paint = head + [self.rel0 + s2, c2, M.STAR]
            yield 'paint over', [RULE_TOK, M.OR] + paint + [ALSO_TOK] + read0 + [self.site(1, lab[1])[0], lab[1]] + cover + [M.END, M.END]
            yield 'paint', [RULE_TOK] + paint + [M.END]

    def search(self, pg, dec):
        """The OUT search at a form's end, dec: yields each consistent decoder."""
        lim, n = self.lim, 0
        f = dec.fork()
        f.step(RULE_TOK)
        self.fill_columns(pg, f)
        for s in reversed(pg.new):
            ts = pg.decl_types.get(s, ())
            if 'Color' in ts and not ({'Position', 'Box'} & set(ts)):
                if len(ts) == 1 and (0, None) in pg.colmap.get(s, {}):
                    pg.colors.insert(0, (s, self.ff0.col_by_pos[0]))
                continue
            if not {'Position', 'Box'} & set(ts):
                continue
            pairs = self.out_pairs(dec, self.rel0 + s, lim.out_pairs)
            for p, c in pairs:
                for label, toks in self.cands(pg, s, p, c):
                    if n >= lim.out_cands:
                        self.c['out:capped'] += 1
                        return
                    if time.monotonic() >= self.deadline:
                        raise Deadline
                    n += 1
                    if toks is None:
                        yield from self.finish_pair(dec, self.rel0 + s, p, c, label)
                    else:
                        yield from self.candidate(dec, toks, label)
            full = [(p, c) for p, c in pairs if c is not None]
            if full:
                pg.grids.insert(0, (s, *full[0]))
                pg.grids = [g for i, g in enumerate(pg.grids) if g[0] != s or not i]

    def finish_pair(self, dec, rtok, p, c, label):
        """OUT over rtok at the column tokens p and c, on a fork of dec."""
        self.c['out:tried'] += 1
        f = dec.fork()
        try:
            for t in (OUT_TOK, rtok, p, M.CARET, c, M.CARET):
                f.step(t)
            cons = f.step(M.END)[1]
        except arclog.Refusal:
            self.c['out:refused ' + label] += 1
            return
        except arclog.Fault:
            self.c['out:fault ' + label] += 1
            return
        self.c['out:%s' % str(getattr(cons, 'kind', None)).rsplit('.', 1)[-1]] += 1
        if f.ended:
            self.c['consistent'] += 1
            self.c['consistent:' + label] += 1
            yield f
