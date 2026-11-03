#!/usr/bin/env python
"""The lookahead components of the writer (writer-spec.md, "Lookahead components"), ported from the gates of Run.form's draw (live.py) and its Drawer
(sample2_col.py). Each component has `name` and `factors(point, ids)`: -inf removes an id, 0 keeps it, a finite value below 0 lowers it.

A component forks point.dec where it tests a step and never steps it. A component is a function of the writing point, except Completable, whose
True answers are shared by all writing points of a try as Drawer.completable shares them (a stale True only lets a path go on to a dead end).
"""
import copy
import math
import re

import numpy as np

import live
import writer
from live import ANY_TYPE, M, S, arclog
from writer import Phase, core_of

ORDER = ('Kinds', 'Grammar', 'HiddenLabels', 'NotSites', 'SoftCaps', 'StopGates', 'RepeatClash', 'EmptyPrefix', 'HeadGate', 'Completable')
BARRED_KINDS = ('ONE', 'SET', 'CHOOSE', 'OUT', 'IF')  # control tokens that no draw makes: marks, a replayed kind, a searched kind


def starts(core, ids):
    """Which of ids start an atom or a compound."""
    return core.is_rel[ids] | (ids == M.NOT) | np.isin(ids, M.CMP) | (ids == M.OR) | (ids == core.ALL)


def closers(core, ids):
    """Which of ids close the open atom: not a column and not a further value of the last site."""
    return ~(core.is_column[ids] | core.is_label[ids] | (ids == M.STAR) | (ids == M.CARET) | (ids == M.ZERO))


def body_level(pt):
    """Whether the next token is at the top of a body (not in an OR or an ALL, a record, a value or an operand)."""
    T = pt.track
    return T.where == 'body' and not T.path and not T.rec and T.col is None and T.need == 0


class Kinds:
    """IF, CHOOSE, ONE, SET and OUT; proposers and INIT components that the corpus counts never give."""
    name = 'Kinds'

    def __init__(self, run):
        V, pri = run.V, run.pri
        n = len(V)
        self.bar = np.zeros(n, bool)
        for i in range(n):
            k, name = V.kind(i), V.name(i)
            if (k == 'control' and name in BARRED_KINDS) or (k == 'proposer' and name not in pri['proposers']) \
                    or (k == 'component' and not (name in pri['comps'] and name in pri['comp_ports'])):
                self.bar[i] = True

    def factors(self, pt, ids):
        return np.where(self.bar[ids], -np.inf, 0.0)


class Grammar:
    """The narrower grammar of FastFrontier.candidates (decoding-interface.md, "Legal next choices"): a body has one proposer, and it stands first; a site has one value, so no value token follows a closed
    site (the decoder admits a repeated value after a value, without bound); `^` stands only in key bodies; `*` is an operand of `=` alone."""
    name = 'Grammar'

    def factors(self, pt, ids):
        T, ph = pt.track, pt.place.phase
        core = core_of(pt.run)
        out = np.zeros(len(ids))
        value = core.is_label[ids] | (ids == M.STAR) | (ids == M.CARET) | (ids == M.ZERO)
        if T.proposed:  # a proposer is the whole body: only its END follows
            out[ids != M.END] = -np.inf
            return out
        if ph != Phase.PROPOSER and T.where == 'body':
            out[core.is_proposer[ids]] = -np.inf
        if ph in (Phase.COLUMN, Phase.ATOM_START, Phase.PROPOSER):
            out[value] = -np.inf  # where only values are admitted, a site of several values is half written: the path ends, as an atom that cannot close is redrawn in Run.body
        elif ph == Phase.VALUE:
            if not T.inkey:
                out[ids == M.CARET] = -np.inf
        elif ph == Phase.OPERAND:
            out[ids == M.CARET] = -np.inf
            if not (T.need == 2 and pt.open_atom and pt.open_atom[-1] == M.CMP[0]):
                out[ids == M.STAR] = -np.inf
        return out


class HiddenLabels:
    """Labels that the place cannot read: another port's labels, and labels local to an OR branch or an ALL."""
    name = 'HiddenLabels'

    def factors(self, pt, ids):
        core = core_of(pt.run)
        out = np.zeros(len(ids))
        lab = core.is_label[ids]
        if lab.any():
            use = pt.labels.usable(pt)
            out[lab & ~np.isin(ids, list(use))] = -np.inf
        return out


class NotSites:
    """A fresh label at a NOT site, NOT with no label to join, and the comparison of an operand with itself."""
    name = 'NotSites'

    def factors(self, pt, ids):
        T, ph = pt.track, pt.place.phase
        out = np.zeros(len(ids))
        if ph in (Phase.VALUE, Phase.OPERAND) and pt.place.negated:
            out[ids == M.STAR] = -np.inf
        elif ph in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER) and not pt.place.negated and (ids == M.NOT).any() and not pt.labels.usable(pt):
            out[ids == M.NOT] = -np.inf
        if ph == Phase.OPERAND and T.need == 1 and pt.open_atom:
            last = pt.open_atom[-1]
            out[ids == last] = -np.inf
            if last == M.STAR and len(pt.labels):
                out[ids == pt.labels.items[-1].tok] = -np.inf
        return out


class RepeatClash:
    """The token that closes an atom that repeats or clashes with an atom of the body, or after which the body (a RULE's or DET's, or an OR branch) cannot close
    (the unsafe-end gate of Run.body, live.py:1324, and Run.branch_atom)."""
    name = 'RepeatClash'

    def factors(self, pt, ids):
        T = pt.track
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.COLUMN:
            return out
        text = T.text + ')'
        if T.negated:
            text = '(NOT %s)' % text
        mine = [x for p, x in T.texts if p == T.path]
        outer = [x for p, x in T.texts if len(p) < len(T.path) and p == T.path[:len(p)]]
        bad = text in mine or live.clash(text, mine, outer)
        if T.path:
            bad = bad or text in outer or live.opposite(text) in outer + mine
        if not bad and pt.kind in ('RULE', 'DET') and (not T.path or T.path[-1][1] == 'OR'):
            got = pt.memo.get('closes')
            if got is None:
                got = pt.memo['closes'] = bool(pt.run.can_close(pt.dec) if T.path else pt.run.can_end(pt.dec))
            bad = not got
        if bad:
            out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class EmptyPrefix:
    """The token that closes an atom whose body table is empty on every input (the engine's body table, as Run.table gives it)."""
    name = 'EmptyPrefix'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.COLUMN or pt.kind not in ('RULE', 'DET') or pt.track.path or pt.track.form:  # a form of a DEMO_RULE has no body table of its own
            return out
        got = pt.memo.get('empty')
        if got is None:
            tb = pt.run.table(pt.run.ff0, pt.dec, pt.pg)[0]
            sm = S.summary(tb)
            got = pt.memo['empty'] = bool(sm is not None and sm['empty_inputs'])
        if got:
            out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class StopGates:
    """A body's END under MIN2_KINDS, with a key unused, or with a key partly used (KEY_ALL, a factor of log .1)."""
    name = 'StopGates'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if not body_level(pt) or pt.place.phase not in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER):
            return out
        at = ids == M.END
        if not at.any():
            return out
        T, run = pt.track, pt.run
        n = T.top + bool(T.atom)
        if n == 0 and pt.kind in S.MIN2_KINDS and not T.proposed:  # a RULE or DET with no atom and no proposer
            out[at] = -np.inf
            return out
        if pt.kind in S.MIN2_KINDS and not T.predict and n == 1 and sum(1 for p, _ in T.texts if p == ()) + bool(T.atom) == 1 and 'single' not in run.pri \
                and not S.one_call(type('D', (), dict(prog_names=pt.pg.names)), [(T.text + ')') if T.atom else T.texts[0][1]]):
            out[at] = -np.inf
            return out
        if pt.kind in writer.PORT_KINDS and not T.inkey and T.round == 0:
            keys = pt.labels.keys(pt)
            if keys:
                read = {L.tok for L in pt.labels.items if any(b == T.body for b, _ in L.reads)}
                unread = keys - read
                if unread == keys:
                    out[at] = -np.inf
                elif unread:
                    out[at] = math.log(1 - live.KEY_ALL)
        return out


class SoftCaps:
    """Lowers the go-on tokens past PORT_SHORT atoms of a port by PORT_LONG, and past bind_atoms atoms of a later branch whose exported labels are unbound by BIND_QUIT."""
    name = 'SoftCaps'

    def factors(self, pt, ids):
        T = pt.track
        out = np.zeros(len(ids))
        if T.where != 'body' or T.rec or T.col is not None or T.need:
            return out
        go = starts(core_of(pt.run), ids)
        if pt.kind in writer.PORT_KINDS and not T.path and T.top + bool(T.atom) == live.PORT_SHORT:
            out[go] += math.log(live.PORT_LONG)
        if T.path and T.path[-1][1] == 'OR' and T.path[-1][2] > 0:
            u, _, b = T.path[-1]
            n = sum(1 for p, _ in T.texts if p == T.path) + bool(T.atom)
            if n >= pt.run.lim.bind_atoms:
                exported = [L for L in pt.labels.items if any(g[0] == u and g[2] == 0 for g in L.path)]
                if any(not any((u, 'OR', b) in rp[1] for rp in L.reads) for L in exported):
                    out[go] += math.log(1 - live.BIND_QUIT)
        return out


class HeadGate:
    """A port body's END where the labels made so far cannot fill the head columns, or the decoder's head search spent its budget: a fork steps END, and then
    each head column must take END or a label."""
    name = 'HeadGate'
    STEPS = 24

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.kind not in ('INIT', 'DEMONSTRATED') or pt.track.inkey or not body_level(pt) or pt.place.phase not in (Phase.ATOM_START, Phase.COLUMN):
            return out
        if not (ids == M.END).any():
            return out
        got = pt.memo.get('head')
        if got is None:
            got = pt.memo['head'] = self.fills(pt)
        if not got:
            out[ids == M.END] = -np.inf
        return out

    def fills(self, pt):
        core = core_of(pt.run)
        f = pt.dec.fork()
        try:
            forced = f.step(M.END)[0]
        except arclog.Refusal:
            return False
        labs = [L.tok for L in pt.labels.items if not L.hidden and L.body == pt.track.body]
        for _ in range(self.STEPS):
            ids = writer.ids_of(f.admissible())
            if np.isin(ids, core.end_ids).any() or (ids == writer.SKIP_TOK).any() or core.is_rel[ids].any():
                return True
            if (ids == M.END).any():
                f.step(M.END)
                continue
            some = [x for x in labs if (ids == x).any()]
            col = ids[core.is_column[ids]]
            if some:
                f.step(some[0])
            elif len(col):
                f.step(int(col[0]))
            else:
                return False
        return True


class Completable:
    """An atom-start table from which no atom end is reached through values that the corpus counts give mass: a bounded depth-first search over forks of
    point.dec (COMPLETE_BUDGET nodes)."""
    name = 'Completable'

    def __init__(self, run):
        self.run, self.true, self.false = run, {}, {}
        pri = run.pri
        self.counts = {k: pri['atoms'].get(k, pri['atoms']['INIT']) for k in ('RULE', 'DET', 'INIT', 'RIGID_DET', 'DEMONSTRATED', 'CHOOSE')}  # a kind that the priors do not count takes INIT's

    def frontier(self, pt):
        run = pt.run
        fr = copy.copy(run.ff0)
        decl = list(range(run.rel0, run.rel0 + pt.pg.ndecl))
        fr.starts_list = run.lib_starts + decl + run.fact_starts
        fr.starts = set(fr.starts_list)
        fr.arity, fr.record_col, fr.root, fr.created = pt.pg.arity, pt.pg.record_cols[pt.kind if pt.kind in pt.pg.record_cols else 'INIT'], None, 0
        use = pt.labels.usable(pt)
        fr.hidden = frozenset(L.tok for L in pt.labels.items if L.tok not in use)
        return fr

    def zero_ok(self, pt, rel, last, fr):
        """Whether the binder prior gives a literal 0 any mass at this column."""
        c = self.counts[pt.kind]
        names = self.run.pri['regcols'].get(rel)
        col = names[last] if names and 0 <= last < len(names) else None
        if col is not None and sum(c['ckind'][(rel, col, x)] for x in ('fresh', 'join', 'rep', 'zero')) > 0:
            return c['ckind'][(rel, col, 'zero')] > 0
        return c['kind'][(rel, 'zero')] > 0

    def rel_name(self, fr, o):
        if fr.KIND[o] == 'relation':
            return 'declared'
        name = self.run.V.name(o)
        return live.S.OPS.get(name, name)

    def reaches(self, pt, fr, o):
        neg = pt.place.negated
        nl = len(pt.labels)
        root = S.FNode((), pt.dec, 'root2' if neg else 'root', -1, 0, '', neg, nl, None)
        fr.root = root
        budget = [S.COMPLETE_BUDGET]
        rel = self.rel_name(fr, o) if o != M.NOT else None

        def dfs(n):
            if budget[0] <= 0:
                return True
            budget[0] -= 1
            if fr.is_leaf(n):
                return True
            skip = (lambda t: t == M.CARET or (t == M.ZERO and not self.zero_ok(pt, rel, n.last, fr))) if n.phase in ('val', 'fval') else None
            for t in fr.admitted(n, skip):
                ch = fr.child(n, t)
                if ch is not None and dfs(ch):
                    return True
            return False
        ch = fr.child(root, o)
        return ch is not None and dfs(ch)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if not S.COMPLETE or pt.place.phase not in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER) or pt.track.where != 'body':
            return out
        core = core_of(pt.run)
        cand = [(i, int(o)) for i, o in enumerate(ids) if core.is_rel[o] or o == M.NOT]
        if not cand:
            return out
        fr = None
        neg, labs = pt.place.negated, len(pt.labels) > 0
        for i, o in cand:
            kt = (o, neg, labs, pt.kind)
            if kt in self.true:
                continue
            kf = (o, neg, pt.tokens)
            hit = self.false.get(kf)
            if hit is None:
                fr = fr or self.frontier(pt)
                hit = self.reaches(pt, fr, o)
                (self.true.__setitem__(kt, True) if hit else self.false.__setitem__(kf, False))
            if not hit:
                out[i] = -np.inf
        return out


DEFAULT = tuple(n for n in ORDER if n != 'Completable')  # Completable costs 10 to 100 ms a writing point, past the budget of 2 to 5 ms: it is in the plan only where named


def components(run, names=None):
    """The components of `names` (default: DEFAULT, in ORDER), made for run. names may hold 'all'."""
    if names and 'all' in names:
        names = ORDER
    if names and any(n in ('legal', 'legal_strict') or n not in globals() for n in names):  # the `legal` plan and the parts of the components (lookahead_legal.py)
        import lookahead_legal
        names = [x for n in names for x in lookahead_legal.LEGAL_PLANS.get(n, (n,))]
        return [lookahead_legal.make(run, n) if n in lookahead_legal.ALL_PARTS or n in ('LegalMask', 'LegalMaskStrict') else (globals()[n](run) if n in ('Kinds', 'Completable') else globals()[n]()) for n in names]
    made = []
    for n in names or DEFAULT:
        cls = globals()[n]
        made.append(cls(run) if n in ('Kinds', 'Completable') else cls())
    return made
