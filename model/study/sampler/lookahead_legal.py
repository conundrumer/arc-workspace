#!/usr/bin/env python
"""The `legal` plan of the writer, and the parts of the lookahead components (lookahead.py).

A rule may remove a token only when each query that it excludes is refused by the engine (at that token or at the query's end), or has the QueryHash of
a query that stays writable under the plan. A rule that excludes a query that the engine accepts, and that no writable query equals, is a preference: a
learned model weighs it, and the `legal` plan leaves it out.

Each component of lookahead.ORDER is split by the condition it tests. PARTS maps a component to its parts; the parts of a component remove, together,
what the component removes. LEGAL names the parts and components that are legality rules. `lookahead.components(run, ['legal'])` makes them.
The verdict of each part, with its evidence, is in the report that goes with this file.

The parts of PARTS['DGates'] and KindsProposer and KindsComponent take their parameters from the train statistics that env WRITER_TRAIN_STATS names (derive_d_rules.py measures
train gold, combine_d_rules.py writes the file); without it they use the old sampler's strict form, or the priors' sets (Kinds), or remove nothing (ZeroBinder, UnreadPortEnd).

The writer plan of the process (PLAN, `ordered` or `unordered`: writer_plan.py says where it comes from) picks the rules of the plan (PLAN_RULES) that LegalMask adds to RULES: under
`ordered`, OrderRule (order_prefix.py) bars every order of the free choices but the `ordered` rule's; under `unordered`, every order stays. The training rows
(train_rows.points_of_targets, plan=) and the draw records (draw_record.py) read the same plan, and check_plan stops a run whose targets are of the other plan.
"""
import json
import os

import numpy as np

import live
import writer
import writer_plan
from live import M, S, arclog
from writer import Phase, core_of
import lookahead
from lookahead import BARRED_KINDS, HiddenLabels, Kinds, body_level, closers, starts
from live import ALSO_TOK as ALSO


# ---------------------------------------------------------------- parameters from train gold

DEFAULT_STATS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/d-rules/stats-train864.json'  # the train statistics of 864 train tasks that the default plan's D parts read where the environment names none
STATS_ENV = 'WRITER_TRAIN_STATS'  # the JSON file that combine_d_rules.py makes from derive_d_rules.py's lines: the parameters of the D parts
_STATS = {}


def train_stats():
    """The train statistics that the environment names (WRITER_TRAIN_STATS), else None."""
    path = os.environ.get(STATS_ENV) or DEFAULT_STATS
    if not path:
        return None
    got = _STATS.get(path)
    if got is None:
        with open(path) as f:
            got = _STATS[path] = json.load(f)
    return got


def param(group, name, default):
    """Parameter `name` of rule `group` in the train statistics; `default` (the old sampler's strict form) where the environment names no file or the file lacks it."""
    st = train_stats()
    return default if st is None else st.get(group, {}).get(name, default)


def _kinds_set(name):
    st = train_stats()
    got = None if st is None else st.get('kinds', {}).get(name)
    return None if got is None else frozenset(got)


def _kinds_or(name, default):
    got = _kinds_set(name)
    return default if got is None else got


STARTS = (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER)


def flat(T):
    """Whether the next token is not inside a value, an operand or a record."""
    return T.col is None and not T.need and not T.rec


# ---------------------------------------------------------------- Kinds


class _KindsPart(Kinds):
    def __init__(self, run):
        V, pri = run.V, run.pri
        self.bar = np.zeros(len(V), bool)
        for i in range(len(V)):
            self.bar[i] = self.test(V.kind(i), V.name(i), pri)


class KindsControl(_KindsPart):
    """IF, CHOOSE, ONE, SET and OUT."""
    name = 'KindsControl'
    test = staticmethod(lambda k, name, pri: k == 'control' and name in BARRED_KINDS)


class KindsProposer(_KindsPart):
    """A proposer that no train gold query uses. The proposers are those of the train statistics (WRITER_TRAIN_STATS: kinds.proposers); where the environment names no file,
    those of the corpus counts of the priors (run.pri['proposers'], fitted on every corpus task)."""
    name = 'KindsProposer'
    test = staticmethod(lambda k, name, pri: k == 'proposer' and name not in _kinds_or('proposers', pri['proposers']))


class KindsComponent(_KindsPart):
    """An INIT component that no train gold query uses, or that no train gold INIT gives a port. The components and their ports are those of the train statistics
    (kinds.comps and kinds.comp_ports); where the environment names no file, those of the priors (run.pri['comps'], run.pri['comp_ports'])."""
    name = 'KindsComponent'
    test = staticmethod(lambda k, name, pri: k == 'component' and not (name in _kinds_or('comps', pri['comps']) and name in _kinds_or('comp_ports', pri['comp_ports'])))


# ---------------------------------------------------------------- Grammar

class GrammarProposed:
    """After a proposer, only END."""
    name = 'GrammarProposed'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.track.proposed:
            out[ids != M.END] = -np.inf
        return out


class GrammarProposerFirst:
    """A proposer stands first in a body."""
    name = 'GrammarProposerFirst'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.PROPOSER and pt.track.where == 'body':
            out[core_of(pt.run).is_proposer[ids]] = -np.inf
        return out


class GrammarOneValue:
    """A site has one value: no value token where the decoder admits a further value."""
    name = 'GrammarOneValue'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase in (Phase.COLUMN, Phase.ATOM_START, Phase.PROPOSER):
            core = core_of(pt.run)
            out[core.is_label[ids] | (ids == M.STAR) | (ids == M.CARET) | (ids == M.ZERO)] = -np.inf
        return out


class GrammarCaret:
    """`^` stands only in key bodies."""
    name = 'GrammarCaret'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        ph, T = pt.place.phase, pt.track
        if (ph == Phase.VALUE and not T.inkey) or ph == Phase.OPERAND:
            out[ids == M.CARET] = -np.inf
        return out


class GrammarStar:
    """`*` is an operand of `=` alone."""
    name = 'GrammarStar'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase == Phase.OPERAND and not (pt.track.need == 2 and pt.open_atom and pt.open_atom[-1] == M.CMP[0]):
            out[ids == M.STAR] = -np.inf
        return out


# ---------------------------------------------------------------- NotSites

class NotStar:
    """A fresh or key label (`*`, `^`) at a site under NOT, a further value of a site included: a site of a NOT atom makes no label."""
    name = 'NotStar'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase in (Phase.VALUE, Phase.OPERAND, Phase.COLUMN) and pt.place.negated:
            out[(ids == M.STAR) | (ids == M.CARET)] = -np.inf
        return out


class EqSelf:
    """The label just made as the second operand of `=` whose first operand is fresh: `(= *X X)` leaves X unbound."""
    name = 'EqSelf'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase == Phase.OPERAND and pt.track.need == 1 and len(pt.open_atom) >= 2 and pt.open_atom[0] == M.CMP[0] and pt.open_atom[-1] == M.STAR and len(pt.labels):
            out[ids == pt.labels.items[-1].tok] = -np.inf
        return out


class CaretLocal:
    """A key label (`^`) inside an ALL, an IF's test or else, or an OR's later branch: no atom at the key body's top level binds it."""
    name = 'CaretLocal'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if T.where == 'body' and any(kd == 'ALL' or (kd == 'IF' and b != 1) or (kd == 'OR' and b > 0) for _, kd, b in T.path):
            out[ids == M.CARET] = -np.inf
        return out


class NotNoLabel:
    """NOT where no label can be joined."""
    name = 'NotNoLabel'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER) and not pt.place.negated and (ids == M.NOT).any() and not pt.labels.usable(pt):
            out[ids == M.NOT] = -np.inf
        return out


class NotSelf:
    """The second operand of a comparison is its first operand."""
    name = 'NotSelf'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.place.phase == Phase.OPERAND and T.need == 1 and pt.open_atom:
            last = pt.open_atom[-1]
            out[ids == last] = -np.inf
            if last == M.STAR and len(pt.labels):
                out[ids == pt.labels.items[-1].tok] = -np.inf
        return out


# ---------------------------------------------------------------- StopGates

def _stop_ctx(pt, ids):
    if not body_level(pt) or pt.place.phase not in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER):
        return None
    at = ids == M.END
    return at if at.any() else None


class StopEmpty:
    """A RULE's or DET's END with no atom and no proposer."""
    name = 'StopEmpty'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        at = _stop_ctx(pt, ids)
        if at is not None:
            T = pt.track
            if T.top + bool(T.atom) == 0 and pt.kind in S.MIN2_KINDS and not T.proposed:
                out[at] = -np.inf
        return out


class StopOneAtom:
    """A RULE's or DET's END after one atom, where that atom calls no method (MIN2_KINDS)."""
    name = 'StopOneAtom'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        at = _stop_ctx(pt, ids)
        if at is not None:
            T, run = pt.track, pt.run
            n = T.top + bool(T.atom)
            if pt.kind in S.MIN2_KINDS and not T.predict and n == 1 and sum(1 for p, _ in T.texts if p == ()) + bool(T.atom) == 1 and 'single' not in run.pri \
                    and not S.one_call(type('D', (), dict(prog_names=pt.pg.names)), [(T.text + ')') if T.atom else T.texts[0][1]]):
                out[at] = -np.inf
        return out


class StopKeysUnread:
    """A port body of a writer.PORT_KINDS form ends with none of its keys read."""
    name = 'StopKeysUnread'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        at = _stop_ctx(pt, ids)
        if at is not None:
            T = pt.track
            if pt.kind in writer.PORT_KINDS and not T.inkey and T.round == 0:
                keys = pt.labels.keys(pt)
                if keys:
                    read = {L.tok for L in pt.labels.items if any(b == T.body for b, _ in L.reads)}
                    if keys - read == keys:
                        out[at] = -np.inf
        return out


class StopKeysPartial:
    """A finite factor on END where some keys are unread: removes nothing."""
    name = 'StopKeysPartial'

    def factors(self, pt, ids):
        import math
        out = np.zeros(len(ids))
        at = _stop_ctx(pt, ids)
        if at is not None:
            T = pt.track
            if pt.kind in writer.PORT_KINDS and not T.inkey and T.round == 0:
                keys = pt.labels.keys(pt)
                if keys:
                    read = {L.tok for L in pt.labels.items if any(b == T.body for b, _ in L.reads)}
                    if keys - read and keys - read != keys:
                        out[at] = math.log(1 - live.KEY_ALL)
        return out


# ---------------------------------------------------------------- RepeatClash

def _atom_state(pt):
    """(text, mine, outer, exact, sub): the closing atom's text, the texts of its list and of the atoms around it, and whether the atom repeats one of them exactly,
    or holds nowhere with (or says nothing beside) one of them."""
    T = pt.track
    text = T.text + ')'
    if T.negated:
        text = '(NOT %s)' % text
    mine = [x for p, x in T.texts if p == T.path]
    outer = [x for p, x in T.texts if len(p) < len(T.path) and p == T.path[:len(p)]]
    neg, rel, sites = live.atom_parts(text)
    exact = sub = False
    for other in (*mine, *outer):
        neg2, rel2, theirs = live.atom_parts(other)
        if rel2 == rel and sites and theirs:
            if neg == neg2 and sites == theirs and other in mine:
                exact = True
            if neg != neg2 and (sites if neg else theirs) <= (theirs if neg else sites):
                sub = True
    return text, mine, outer, exact, sub


class RepeatSame:
    """The token that closes an atom that repeats an atom of its list, or of the atoms around it, exactly."""
    name = 'RepeatSame'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.COLUMN:
            return out
        text, mine, outer, exact, _ = _atom_state(pt)
        if text in mine or exact or (pt.track.path and text in outer):
            out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class RepeatSubset:
    """The token that closes an atom that holds nowhere with an atom of its list (the negation of it, or of a part of its sites), or says nothing beside it."""
    name = 'RepeatSubset'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.COLUMN:
            return out
        text, mine, outer, _, sub = _atom_state(pt)
        if sub or (pt.track.path and live.opposite(text) in outer + mine):
            out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class RepeatEndBody:
    """The token that closes an atom after which the body of a RULE or DET cannot end (Run.can_end)."""
    name = 'RepeatEndBody'
    in_branch = False

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.place.phase != Phase.COLUMN or pt.kind not in ('RULE', 'DET'):
            return out
        if bool(T.path) != self.in_branch or (T.path and T.path[-1][1] != 'OR'):
            return out
        key = 'closes'
        got = pt.memo.get(key)
        if got is None:
            got = pt.memo[key] = bool(pt.run.can_close(pt.dec) if T.path else pt.run.can_end(pt.dec))
        if not got:
            out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class RepeatEndBranch(RepeatEndBody):
    """The token that closes an atom of an OR branch after which the branch cannot close (Run.can_close)."""
    name = 'RepeatEndBranch'
    in_branch = True


# ---------------------------------------------------------------- HeadFill

class HeadFill:
    """A port body's END where the head cannot be filled: END is refused, or a search of the head's fills (each head token is END, a label or a column)
    ends with none that leaves the head. Where the search spends its nodes or reaches its depth, END stays."""
    name = 'HeadFill'
    NODES = 400
    DEPTH = 14

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.kind not in ('INIT', 'DEMONSTRATED') or pt.track.inkey or not body_level(pt) or pt.place.phase not in (Phase.ATOM_START, Phase.COLUMN):
            return out
        if not (ids == M.END).any():
            return out
        got = pt.memo.get('headfill')
        if got is None:
            got = pt.memo['headfill'] = self.fills(pt)
        if not got:
            out[ids == M.END] = -np.inf
        return out

    def fills(self, pt):
        core = core_of(pt.run)
        f = pt.dec.fork()
        try:
            f.step(M.END)
        except arclog.Refusal:
            return False
        budget = [self.NODES]
        open_ends = [False]

        def leaves(ids):
            return np.isin(ids, core.end_ids).any() or (ids == writer.SKIP_TOK).any() or core.is_rel[ids].any()

        def dfs(d, depth):
            ids = writer.ids_of(d.admissible())
            if leaves(ids):
                return True
            if depth >= self.DEPTH:
                open_ends[0] = True
                return False
            nxt = [int(x) for x in ids if x == M.END] + [int(x) for x in ids if core.is_label[x]] + [int(x) for x in ids if core.is_column[x]]
            for x in nxt:
                if budget[0] <= 0:
                    open_ends[0] = True
                    return False
                budget[0] -= 1
                g = d.fork()
                try:
                    g.step(x)
                except arclog.Refusal:
                    continue
                if dfs(g, depth + 1):
                    return True
            return False

        if dfs(f, 0):
            return True
        return open_ends[0]


# ---------------------------------------------------------------- AtomOrder

class AtomOrder:
    """Symmetry breaking (canonical.py): a body, an OR branch or a port body starts its atoms in the fixed order of their first model tokens. The token that
    starts an atom (a relation, NOT, a comparison, OR, ALL) is removed where its key is below the key of the atom started last in the same group. Atoms of one
    key are tied. No rule inside an ALL. Every other order has the QueryHash of an order that stays writable."""
    name = 'AtomOrder'
    OR_LATE = False

    def __init__(self, run):
        import canonical
        self.order = canonical.AtomOrder(run.V.id, self.OR_LATE)
        self.late = np.array(sorted(self.order.late), np.int64)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T, ph = pt.track, pt.place.phase
        if T.where != 'body' or T.col is not None or T.need or T.rec or ph not in (Phase.ATOM_START, Phase.COLUMN, Phase.PROPOSER):
            return out
        if ph == Phase.ATOM_START and T.negated:  # a relation completes the NOT that started the atom
            return out
        if any(g[1] == 'ALL' for g in T.path) or not T.firsts:
            return out
        last = next((t for p, t in reversed(T.firsts) if p == T.path), None)
        if last is None:
            return out
        go = lookahead.starts(core_of(pt.run), ids)
        if not go.any():
            return out
        keys = ids.astype(np.int64) + np.where(np.isin(ids, self.late), self.order.big, 0)
        out[go & (keys < self.order.key(last))] = -np.inf
        return out


class AtomOrderDep:
    """AtomOrder that loses no query: the atom B that a token closes may not stand before the atom A started just before it (same group) when B has a smaller key than A and
    uses no label that A (or an atom inside A) made or read. Then B and A swap, and the swapped query has the same QueryHash and the engine takes it (B reads what it read
    before; A reads nothing of B's). Where B reads a label of A, the engine needs A first, and the order stands. The rule removes the tokens that close B. No rule on a compound B (OR, ALL)
    or inside an ALL."""
    name = 'AtomOrderDep'
    OR_LATE = False

    def __init__(self, run):
        import canonical
        self.order = canonical.AtomOrder(run.V.id, self.OR_LATE, True)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.place.phase != Phase.COLUMN or T.where != 'body' or not T.atom or len(T.firsts) < 2:
            return out
        if any(g[1] == 'ALL' for g in T.path):
            return out
        ib = len(T.firsts) - 1
        pb, tb = T.firsts[ib]
        if pb != T.path or tb in (M.OR, core_of(pt.run).ALL):
            return out
        ia = next((j for j in range(ib - 1, -1, -1) if T.firsts[j][0] == T.path), None)
        if ia is None or self.order.key(tb) >= self.order.key(T.firsts[ia][1]):
            return out
        before = {tok for tok, j in T.uses if ia <= j < ib}
        if any(j == ib and tok in before for tok, j in T.uses):
            return out
        out[closers(core_of(pt.run), ids)] = -np.inf
        return out


class AtomOrderOrLate(AtomOrder):
    """AtomOrder with OR counted among the atoms that need their labels bound."""
    name = 'AtomOrderOrLate'
    OR_LATE = True


# ---------------------------------------------------------------- the order rule of the `ordered` plan

class OrderRule:
    """The `ordered` plan's order of the free choices (order_prefix.Rule): removes each id that no `ordered` path continues with."""
    name = 'OrderRule'

    def __init__(self, run):
        import order_prefix
        self.rule = order_prefix.rule_of(run)

    def factors(self, pt, ids):
        return np.where(self.rule.keep(pt, ids), 0.0, -np.inf)


PLAN, PLAN_SOURCE = writer_plan.of_environment()  # the writer plan of the process, and where it comes from: LegalMask, train_rows and draw_record read it
PLAN_RULES = {'ordered': ('OrderRule',), 'unordered': ()}  # the rules of each plan, after RULES


def check_plan(plan):
    """Raises where `plan` is not the process's writer plan (PLAN): the targets of one plan go with the mask of that plan alone."""
    if plan != PLAN:
        raise ValueError('plan %r, and the writer plan of the process is %r (from %s): the mask is the plan of the process' % (plan, PLAN, PLAN_SOURCE))


def with_plan_rules(run, comps):
    """comps (lookahead components) and, after them, each rule of the writer plan (PLAN_RULES) that no component of comps is or holds (as LegalMask holds its rules)."""
    have = {c.name for c in comps} | {r.name for c in comps for r in getattr(c, 'rules', ())}
    return list(comps) + [make(run, n) for n in PLAN_RULES[PLAN] if n not in have]


# ---------------------------------------------------------------- the legal plan

# ---------------------------------------------------------------- D gates: the redraw gates of the old per-atom draw (live.py Run.body, or_atom, all_form, branch; sample2_col.py)
#
# Each gate has a strict form (the old sampler's) and a parameter that derive_d_rules.py measures on train gold and combine_d_rules.py writes to the file of
# WRITER_TRAIN_STATS. Where train gold breaks the strict form, the parameter is the largest value that train gold has, so that no train gold path loses a token.
# A function here that gives a statistic is the one that derive_d_rules.py calls, so that the measure and the part agree.

CMP = tuple(M.CMP)


def unjoined_ctx(pt):
    """(class, required) of the open atom: class is 'top' (an atom of a body), 'or' (of an OR branch), 'all' (of an ALL) or another group's name; required says that the old
    sampler's draw redraws the atom where it joins no label: a body's atom after the first, or any atom of a keyed port body (Run.body), a branch atom after the first
    atom of the body's first item (Run.branch: k + j > 2, or the first branch of a keyed port), a guard atom after the first, and the conclusion (Run.all_form)."""
    T = pt.track
    port = pt.kind in writer.PORT_KINDS and not T.inkey
    keys = port and bool(pt.labels.keys(pt))
    if not T.path:
        return 'top', T.top + 1 > 1 or keys
    kd, b = T.path[-1][1], T.path[-1][2]
    j = 1 + sum(1 for p, _ in T.texts if p == T.path)
    if kd == 'OR':
        return 'or', (T.top + 1 + j > 2) or (keys and b == 0)
    if kd == 'ALL':
        return 'all', (j > 1) if b == 0 else True
    return kd.lower(), False


def floating(pt, core):
    """Whether the open atom is a relation atom (not a comparison) that has a column and reads no label and makes none: its sites hold constants alone."""
    atom = pt.track.atom
    if not atom or atom[0] in CMP:
        return False
    return any(core.is_column[x] for x in atom) and not any(core.is_label[x] or x in (M.STAR, M.CARET) for x in atom)


def port_end_ctx(pt):
    """Whether the next token is at the top of a port body (not a key body) of an INIT that is not a DEMONSTRATED form's: where the body may end."""
    T = pt.track
    return pt.kind == 'INIT' and not T.form and not T.inkey and body_level(pt) and pt.place.phase in STARTS


def port_reads_derived(pt):
    """Whether an atom of the port body so far, the open one included, reads a derived relation (a name that starts with `&`), as an atom or under NOT."""
    T = pt.track
    return any('(&' in x for x in [x for _, x in T.texts] + ([T.text] if T.atom else []))


def port_unread(pt, head=False):
    """The labels that the port body made and none of its atoms reads; with head, those that the head tokens so far do not read either."""
    T = pt.track
    out = [L.tok for L in pt.labels.items if L.body == T.body and not any(b == T.body for b, _ in L.reads)]
    return [x for x in out if x not in T.head_labels] if head else out


def or_open(pt):
    """(ors, in_all, in_branch): at a token that opens an OR, the ORs and whether an ALL is open around it, and whether its branch holds an OR already."""
    T = pt.track
    inb = [f for f in T.firsts if f[0] == T.path]
    return sum(1 for g in T.path if g[1] == 'OR'), any(g[1] == 'ALL' for g in T.path), any(f[1] == M.OR for f in inb)


def after_nested(pt):
    """'first' or 'notfirst' at the point right after an OR closed in an OR branch (the OR was the first item of the branch, or not), else None."""
    T = pt.track
    if T.where != 'body' or not T.path or T.path[-1][1] != 'OR' or T.atom or T.negated or not flat(T):
        return None
    inb = [f for f in T.firsts if f[0] == T.path]
    if inb and inb[-1][1] == M.OR:
        return 'first' if len(inb) == 1 else 'notfirst'
    return None


def or_close_counts(pt):
    """(missing, unread) where a later branch (the second or after) of an OR in a body that is not a key may close here, else None. missing: the labels that the first branch
    made, did not read itself, and the later branches before this one all read (the labels that the OR exports), which this branch does not read. unread: the labels that
    this branch made (visible ones) and does not read. The old sampler (Run.branch) closes a later branch where both are 0, except with chance P_UNNAMED and P_UNREAD_LOCAL."""
    T = pt.track
    if T.where != 'body' or T.inkey or not T.path or T.path[-1][1] != 'OR' or T.path[-1][2] < 1 or not flat(T) or pt.place.phase not in (Phase.COLUMN, Phase.ATOM_START):
        return None
    u, _, b = T.path[-1]

    def read_in(L, bb):
        return any((u, 'OR', bb) in rp[1] for rp in L.reads)
    exported = [L for L in pt.labels.items if not L.hidden and (u, 'OR', 0) in L.path and not read_in(L, 0) and all(read_in(L, bb) for bb in range(1, b))]
    made = [L for L in pt.labels.items if not L.hidden and (u, 'OR', b) in L.path]
    return sum(1 for L in exported if not read_in(L, b)), sum(1 for L in made if not read_in(L, b))


def all_guard_state(pt, core):
    """(guard labels made, reads a guard label) of the open atom of an ALL's conclusion, else None."""
    T = pt.track
    if T.where != 'body' or not T.path or T.path[-1][1] != 'ALL' or T.path[-1][2] != 1 or not T.atom:
        return None
    guard = {L.tok for L in pt.labels.items if (T.path[-1][0], 'ALL', 0) in L.path}
    return bool(guard), bool(guard & {x for x in T.atom if core.is_label[x]})


class UnjoinedAtom:
    """try:unjoined. The token that closes an atom that holds no label and makes none (a relation atom whose sites are constants), where the old sampler redraws an
    atom that joins no label (unjoined_ctx: a body's atom after the first, a keyed port's atoms, a branch's, an ALL's). The strict form refuses any atom that reads no label;
    train gold has such atoms that make a label (a binder that a later atom reads), so the part refuses the atoms that make none either. Parameter unjoined.enforce:
    {class: bool}, true where no train gold atom of that class is floating."""
    name = 'UnjoinedAtom'

    def __init__(self, run):
        self.enforce = param('unjoined', 'enforce', dict(top=True, **{'or': True}, all=True))

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if pt.place.phase != Phase.COLUMN:
            return out
        core = core_of(pt.run)
        if not floating(pt, core):
            return out
        cls, req = unjoined_ctx(pt)
        if req and self.enforce.get(cls):
            out[closers(core, ids)] = -np.inf
        return out


class DerivedPort:
    """DERIVED_GROUPS = {'INIT port'}: the END of an INIT port body whose atoms read no derived relation, where the scope holds a query (so one can be read). The strict form refuses it
    in every INIT port; train gold has port bodies that read none, so the part refuses it for the components in parameter derived_port.comps (those whose train gold
    port bodies, over a non-empty scope, always read one, at least derived_port.min_n of them); a list of null means every component."""
    name = 'DerivedPort'

    def __init__(self, run):
        got = param('derived_port', 'comps', None)
        self.comps = None if got is None else frozenset(got)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if not port_end_ctx(pt) or not (ids == M.END).any() or not getattr(pt.pg, 'written', None):
            return out
        if self.comps is not None and core_of(pt.run).names[pt.tokens[1]] not in self.comps:
            return out
        if not port_reads_derived(pt):
            out[ids == M.END] = -np.inf
        return out


class UnreadPortEnd:
    """MAX_UNREAD at the END of a port body: END where more labels of the body are unread than parameter unread_port.max_end, the largest count that train gold has at a port body's
    END (its head may read some, which this point cannot see: UnreadPortHead counts them). Without the parameter: no removal."""
    name = 'UnreadPortEnd'

    def __init__(self):
        self.max = param('unread_port', 'max_end', 10 ** 9)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if port_end_ctx(pt) and (ids == M.END).any() and len(port_unread(pt)) > self.max:
            out[ids == M.END] = -np.inf
        return out


class UnreadPortHead:
    """MAX_UNREAD: a head token of an INIT port body that ends the head where more labels of the body are unread than parameter unread_port.max_head (old sampler: 1; the
    largest count that train gold has), counting the labels that the head reads. A label that the body does not read and the head does not read is unread."""
    name = 'UnreadPortHead'

    def __init__(self):
        self.max = param('unread_port', 'max_head', 1)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.place.phase != Phase.HEAD or T.where != 'head' or T.inkey or T.form or pt.kind != 'INIT':
            return out
        unread = set(port_unread(pt, True))
        if len(unread) <= self.max:
            return out
        for i, t in enumerate(ids):
            if len(unread - {int(t)}) > self.max and writer.step_point(pt, int(t)).track.where != 'head':
                out[i] = -np.inf
        return out


class OrNesting:
    """The OR structure of the old sampler (Run.or_form, branch): an OR nests one level deep (parameter or_nesting.max_depth, 2 in gold), at most one OR in a branch
    (second_in_branch), and an OR that is not the first item of its branch is the branch's last item (continue_notfirst: where false, no atom starts after it; continue_first
    likewise for an OR that is the first item). No OR inside an ALL (in_all). A parameter is true where train gold has the case."""
    name = 'OrNesting'

    def __init__(self, run):
        d = dict(max_depth=2, second_in_branch=False, continue_first=True, continue_notfirst=False, in_all=False)
        self.p = {k: param('or_nesting', k, v) for k, v in d.items()}

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T, core = pt.track, core_of(pt.run)
        if T.where != 'body':
            return out
        p = self.p
        if (ids == M.OR).any() and flat(T) and pt.place.phase in STARTS:
            ors, in_all, in_branch = or_open(pt)
            if ors + 1 > p['max_depth'] or (in_all and not p['in_all']) or (in_branch and not p['second_in_branch']):
                out[ids == M.OR] = -np.inf
        st = after_nested(pt)
        if st is not None and not p['continue_' + st]:
            out[starts(core, ids)] = -np.inf
        return out


class AllNesting:
    """An ALL holds plain atoms (Run.all_form): no ALL or OR inside an ALL, where train gold has none (parameter all.in_all)."""
    name = 'AllNesting'

    def __init__(self):
        self.allow = param('all', 'in_all', False)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if not self.allow and T.where == 'body' and any(g[1] == 'ALL' for g in T.path) and flat(T) and pt.place.phase in STARTS:
            out[(ids == M.OR) | (ids == core_of(pt.run).ALL)] = -np.inf
        return out


class OrBranchClose:
    """The token that closes a later branch of an OR (ALSO or END), where the branch leaves more of the OR's exported labels unnamed than parameter or_close.missing_max, or
    makes more labels that it does not read than or_close.unread_max (or_close_counts). The old sampler's strict form is 0 and 0; train gold has later branches that
    break each, so the parameters are the largest counts that train gold has. Not in a key body."""
    name = 'OrBranchClose'

    def __init__(self):
        self.missing, self.unread = param('or_close', 'missing_max', 0), param('or_close', 'unread_max', 0)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        at = (ids == ALSO) | (ids == M.END)
        if not at.any():
            return out
        got = or_close_counts(pt)
        if got is not None and (got[0] > self.missing or got[1] > self.unread):
            out[at] = -np.inf
        return out


class AllGuardRead:
    """The ALL guard (Run.all_form): the token that closes the conclusion atom of an ALL whose guard made a label, where that atom reads no guard label. Parameter all.guard_read:
    true where train gold's conclusions always read one."""
    name = 'AllGuardRead'

    def __init__(self, run):
        self.enforce = param('all', 'guard_read', True)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        if not self.enforce or pt.place.phase != Phase.COLUMN:
            return out
        core = core_of(pt.run)
        got = all_guard_state(pt, core)
        if got is not None and got[0] and not got[1]:
            out[closers(core, ids)] = -np.inf
        return out


class RigidDetPlain:
    """plain_parts: the parts of a RIGID_DET (its port bodies) hold plain atoms. Refused, by class, in a RIGID_DET's port body: NOT, `=`, another comparison, the relation `input`,
    OR, ALL, and a relation that an earlier atom of the body has already. The old sampler refuses every class; the part refuses those in parameter rigid_det.refuse
    (the classes with no train gold token)."""
    name = 'RigidDetPlain'
    CLASSES = ('not', 'eq', 'cmp_other', 'input', 'or', 'all', 'dup_rel')

    def __init__(self, run):
        self.refuse = frozenset(param('rigid_det', 'refuse', self.CLASSES))
        self.input = run.V.id('input')

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T, core, r = pt.track, core_of(pt.run), self.refuse
        if pt.kind != 'RIGID_DET' or T.inkey or T.where != 'body' or not flat(T) or pt.place.phase not in STARTS:
            return out
        if 'not' in r:
            out[ids == M.NOT] = -np.inf
        if 'eq' in r:
            out[ids == M.CMP[0]] = -np.inf
        if 'cmp_other' in r:
            out[np.isin(ids, CMP[1:])] = -np.inf
        if 'input' in r:
            out[ids == self.input] = -np.inf
        if 'or' in r:
            out[ids == M.OR] = -np.inf
        if 'all' in r:
            out[ids == core.ALL] = -np.inf
        if 'dup_rel' in r:
            had = {f[1] for f in T.firsts if f[0] == T.path}
            if had:
                out[core.is_rel[ids] & np.isin(ids, list(had))] = -np.inf
        return out


class ZeroBinder:
    """Zero-count binder priors as hard zeros (sample2_col.py ckind, zero_ok): at a column of a library relation that train gold writes (zero_binder.table, at least zero_binder.min_n
    values), the value kind that train gold never writes there: `*` (fresh), an existing label (join), or 0 (zero). The table is keyed 'relation|column'. Without the table: no removal."""
    name = 'ZeroBinder'

    def __init__(self):
        self.table = param('zero_binder', 'table', {})
        self.min_n = param('zero_binder', 'min_n', 1)

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.place.phase != Phase.VALUE or T.rtok is None or T.rec or not T.atom or not self.table:
            return out
        core = core_of(pt.run)
        if not core.is_column[T.atom[-1]]:
            return out
        c = self.table.get('%s|%s' % (core.names[T.rtok], core.names[T.atom[-1]]))
        if not c or sum(c.values()) < self.min_n:
            return out
        if not c.get('fresh'):
            out[ids == M.STAR] = -np.inf
        if not c.get('join'):
            out[core.is_label[ids]] = -np.inf
        if not c.get('zero'):
            out[ids == M.ZERO] = -np.inf
        return out



PARTS = {
    'Kinds': ('KindsControl', 'KindsProposer', 'KindsComponent'),
    'Grammar': ('GrammarProposed', 'GrammarProposerFirst', 'GrammarOneValue', 'GrammarCaret', 'GrammarStar'),
    'NotSites': ('NotStar', 'NotNoLabel', 'NotSelf'),
    'StopGates': ('StopEmpty', 'StopOneAtom', 'StopKeysUnread', 'StopKeysPartial'),
    'RepeatClash': ('RepeatSame', 'RepeatSubset', 'RepeatEndBody', 'RepeatEndBranch'),
    'HeadGate': ('HeadFill',),
    'DGates': ('UnjoinedAtom', 'DerivedPort', 'UnreadPortEnd', 'UnreadPortHead', 'OrNesting', 'AllNesting', 'OrBranchClose', 'AllGuardRead', 'RigidDetPlain', 'ZeroBinder'),
}
ALL_PARTS = tuple(p for ps in PARTS.values() for p in ps) + ('AtomOrder', 'AtomOrderOrLate', 'AtomOrderDep')
NEEDS_RUN = ('KindsControl', 'KindsProposer', 'KindsComponent', 'UnjoinedAtom', 'DerivedPort', 'OrNesting', 'AllGuardRead', 'RigidDetPlain', 'AtomOrder', 'AtomOrderOrLate', 'AtomOrderDep', 'LegalMask', 'LegalMaskStrict', 'OrderRule')

# The legality rules and legal parts, in order. They are the rules that LegalMask composes.
RULES = ('NotStar', 'HeadFill', 'RepeatSame', 'HiddenLabels', 'CaretLocal', 'EqSelf')
# The corpus gates that remove no dev gold token with parameters from train gold (rule_audit.py on 161 dev tasks), in the shared plan, so that rows' masks and serving masks are one
RULES = RULES + ('UnjoinedAtom', 'OrBranchClose', 'AllNesting', 'AllGuardRead', 'KindsComponent', 'UnreadPortEnd', 'UnreadPortHead', 'RigidDetPlain', 'StopOneAtom')
# Parts the probe found no removal for, so it could not judge them (lg_probe.py); name them after 'legal' to add them: WRITER_LOOKAHEAD=legal,RepeatEndBranch
class ReadsScope:
    """A RULE's or DET's END at the top of its body, over a non-empty scope, while the query names no query of the scope. Such a query's tables
    depend on no query of the scope, so it belongs to the root slot, whose search writes it; each query then has one slot that writes it."""
    name = 'ReadsScope'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.kind not in ('RULE', 'DET') or T.form or T.path or T.where != 'body' or not (ids == M.END).any():
            return out
        names = getattr(pt.pg, 'written', None)
        if not names:  # the root slot: an empty scope
            return out
        V = pt.run.V
        if not any(V.kind(t) == 'relation' and V.name(t) in names for t in pt.tokens):
            out[ids == M.END] = -np.inf
        return out


class ReadsScopeFirst:
    """Over a non-empty scope, the first atom of a RULE's or DET's body: every id but a relation that names a query of the scope. A query reads the scope
    exactly where some atom does, and the engine takes the atoms of a body in any order, so the query can be written with that atom first; a query
    that reads no query of the scope belongs to the root slot. The rule ends a path at its first token where ReadsScope would let it run to a cap."""
    name = 'ReadsScopeFirst'

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        T = pt.track
        if pt.kind not in ('RULE', 'DET') or T.form or T.firsts or not body_level(pt) or pt.place.phase not in (Phase.PROPOSER, Phase.ATOM_START):
            return out
        names = getattr(pt.pg, 'written', None)
        if not names:  # the root slot: an empty scope
            return out
        V = pt.run.V
        keep = np.array([V.kind(int(t)) == 'relation' and V.name(int(t)) in names for t in ids], bool)
        out[~keep] = -np.inf
        return out


class ReadsScopeAny:
    """Over a non-empty scope, under the `ordered` plan's order rule (order_prefix.py), a RULE's or DET's tokens while the query reads no query of the scope: every id after which no
    completion of the query can read one. A query of the scope is a relation of the decoder's `&r` names: a declaration of the scope, or an output of one of its INITs. After a token, a
    completion can read the scope where some open set of the query can still start an atom of a scope relation, or an OR, ALL or NOT, whose first token the set's Floor does not put
    below its bound (a tie counts as possible). The scope relations that can start an atom are those of the engine's mask at a start point of the scope, kept per scope; before one is
    seen, every `&r` relation counts. A query that reads no query of the scope belongs to the root slot. A search rule, not a legality rule: gold writes queries that read no scope at
    non-empty states. Where the query has no sets (order_prefix.Rule.has_sets), the rule keeps every id."""
    name = 'ReadsScopeAny'
    CACHE = 64  # the scopes whose relation ids it keeps

    def __init__(self):
        self.vocab = {}  # id of the vocabulary -> (sorted ids of its `&r` relations, set of them)
        self.scopes = {}  # (id of the vocabulary, the scope's written names) -> the largest `&r` relation id of the mask at a start point

    def rel_ids(self, V):
        got = self.vocab.get(id(V))
        if got is None:
            ids = np.array([i for i in range(len(V)) if V.kind(i) == 'relation' and V.name(i).startswith('&r')], np.int64)
            got = self.vocab[id(V)] = (ids, frozenset(int(i) for i in ids))
        return got

    @staticmethod
    def level_ok(rel, other, top_s, top_w):
        """Whether a set with these bounds can still start a scope relation (top_s, the largest such id) or a wrapper (top_w, the largest of OR, ALL and NOT)."""
        return (top_s is not None and (rel is None or top_s >= rel)) or (other is None or top_w >= other)

    def possible(self, fl, top_s, top_w):
        return any(self.level_ok(f.rel, f.other, top_s, top_w) for f in fl)

    def factors(self, pt, ids):
        import order_prefix
        ids = np.asarray(ids, np.int64)
        out = np.zeros(len(ids))
        names = getattr(pt.pg, 'written', None)
        if pt.kind not in ('RULE', 'DET') or not names or not len(ids):
            return out
        V = pt.run.V
        rids, rset = self.rel_ids(V)
        if not len(rids) or any(int(t) in rset for t in pt.tokens):
            return out
        start = pt.place.phase in (Phase.PROPOSER, Phase.ATOM_START)
        key = (id(V), frozenset(names.items()))
        if key not in self.scopes and start:
            here = [int(t) for t in pt.ids_ if int(t) in rset]
            if here:
                self.scopes[key] = max(here)
                if len(self.scopes) > self.CACHE:
                    self.scopes.pop(next(iter(self.scopes)))
        top_s = self.scopes.get(key, int(rids.max()))
        rule = order_prefix.rule_of(pt.run)
        fl = rule.floors(pt)
        if not fl:  # None: no sets; []: no set open
            return out
        wrap = np.array([M.OR, M.NOT, V.id('ALL')], np.int64)
        top_w = int(wrap.max())
        free = ~(np.isin(ids, rids) | np.isin(ids, wrap))  # ids that are neither a scope relation nor a wrapper
        is_end = ids == M.END
        if is_end.any():
            after = rule.floors(pt, M.END)
            if not after or not self.possible(after, top_s, top_w):
                out[is_end] = -np.inf
        starts = free & ~is_end
        if start and starts.any():
            t0 = int(ids[starts].max())  # the largest: where it is above the inner bound, the probe tells a new item of the innermost set from a token inside an item; where it is not, both give the same bounds
            f0 = rule.floors(pt, t0)
            inner = fl[-1]
            if f0 and len(f0) == len(fl) and f0[-1].rel == max(inner.rel if inner.rel is not None else t0, t0):  # a start token begins an item of the innermost set
                if not self.possible(fl[:-1], top_s, top_w):
                    t = ids[starts]
                    rel = np.maximum(t, inner.rel if inner.rel is not None else -1)
                    other = np.maximum(t, inner.other if inner.other is not None else -1)
                    ok = (top_s >= rel) | (top_w >= other)
                    idx = np.flatnonzero(starts)
                    out[idx[~ok]] = -np.inf
            elif not self.possible(fl, top_s, top_w):
                out[starts] = -np.inf
        return out


CANDIDATES = ('RepeatEndBranch', 'ReadsScope', 'ReadsScopeFirst', 'ReadsScopeAny')
ADD = tuple(x for x in os.environ.get('WRITER_LEGAL_ADD', '').split(',') if x)  # candidates that a check adds to RULES


class LegalMask:
    """The legality rules, and the rules of the writer plan (PLAN_RULES), as one mask. The writer applies it as a lookahead component; `allowed(pt)` gives the mask for the model: the engine's mask with the rules
    applied, over the whole vocabulary, so that a later step can move a settled rule into the engine's admissible(). `removed(pt, ids)` says which rule removed each id."""
    name = 'LegalMask'

    def __init__(self, run, rules=None):
        self.rules = [make(run, n) for n in (rules or RULES + ADD + PLAN_RULES[PLAN])]

    def removed(self, pt, ids):
        """{rule name: bool array over ids} for the rules that remove an id."""
        out = {}
        for r in self.rules:
            hit = np.asarray(r.factors(pt, ids)) == -np.inf
            if hit.any():
                out[r.name] = hit
        return out

    def factors(self, pt, ids):
        out = np.zeros(len(ids))
        for r in self.rules:
            out[np.asarray(r.factors(pt, ids)) == -np.inf] = -np.inf
        return out

    def allowed(self, pt):
        """A bool array over the vocabulary: the ids of the engine's mask that no rule removes."""
        ids = pt.ids_
        keep = self.factors(pt, ids) > -np.inf
        out = np.zeros(len(pt.run.V), bool)
        out[ids[keep]] = True
        return out


class LegalMaskStrict(LegalMask):
    """LegalMask with the order of the ruling: the sort by first token alone, which makes some queries unwritable (the engine takes their atoms in the order of their labels only)."""
    name = 'LegalMaskStrict'

    def __init__(self, run):
        super().__init__(run, ('AtomOrder', 'RepeatSame', 'HeadFill'))


LEGAL_PLANS = {'legal': ('LegalMask',), 'legal_strict': ('LegalMaskStrict',)}


def make(run, name):
    if name in NEEDS_RUN:
        return globals()[name](run)
    return globals()[name]()
