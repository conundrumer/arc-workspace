#!/usr/bin/env python
"""S from an empty prefix on a task it has never seen: whole programs through a live decoder.

    sampler = Sampler(models_dir)            # loads the frozen priors (live_priors.py) once
    for result in sampler.draws(session, seed, deadline, task, **limits): ...
    clause = sampler.clause(session, seed, deadline, task, forms, kind, **limits)

The worker makes the arclog.Session and passes it in; a session on Kaggle data is World.Open, and draws make no second
session. task is the task's JSON as a dict, with no test outputs. deadline is a time.monotonic() value. limits are Limits' fields. A Result is yielded as soon as it exists: a decoder
that ended at a consistent OUT with its attempts, and a last Result with no decoder when the deadline passes. Each has the
counts so far: draws, finished programs, drops by reason, errors by type, and the limits.

clause draws one clause of the kind over a scope that the caller picks: forms, the text of one form each in dependency order, with
no OUT. The forms are replayed into a decoder and a Program as if this module had drawn them, so what a clause reads of the scope
comes from the decoder. A form's relation slot is its place among the scope's declarations, so the written name of a relation
means nothing to a decoder: two forms need two head names, any names, and a Clause's text uses the names of forms. The Run stays
between calls on one session, seed sets its draws for each call, and sampler.run.c has the counts of its calls.

A draw walks the program form by form. Clause order does not matter: what a step of the walk reads is what the program has. The
next clause's kind, or the stop, comes from corpus counts (P alone) keyed by how many clauses of each kind exist (live_priors.py
counts them over random dependency orders of gold). A RULE's atoms and a DET's come from S's Drawer, a DET may take a proposer, an
INIT takes a component, and each of its ports takes
a body and a head. The body of a RULE, a key or a port may hold an OR, from that place's counts: in a key the branches share the keys
alone, and other labels stay in their branch. A key's count of ^ labels comes from the priors, and a keyed port goes on until it reads
each key, or stops with chance 1 - KEY_ALL. A head column of a type parameter may take a record of several labels, its count from the
priors, and the port's body goes on until it makes that many or reaches its last atom; the column that first binds a type parameter
sets that count and the labels' types for the INIT's other columns of that type, and their ports' bodies then need those types. The decoder gives every read of the task: its checks, and tables through step_tables;
this module reads no gold and no path but the priors.

OUT is a search, not a draw. A decode ends at its first consistent OUT, so each candidate runs on a fork of the form's end and
the draw goes on past it. At each form end, for each relation R the form declared, the best suited first (Gate.suits): R over the
input (R plus the
input's cells where R has none), R alone, then for a Position column with no Color column, the same with a Color relation's
value or the input's color, then unions with earlier relations, again the best suited. A fit counts where it passes Gate, in two steps. The cheap step reads
the attempts on the test inputs: GATE_RULES refuse it, and the counts have refused:<rule> for each rule of Gate that the OUT breaks,
GATE_RULES or not, so each rule's count is its own. The second step is leave-one-out: for each train pair e, the program runs on the
task with e's output removed, so e is one more test input, and its attempt on e is compared with e's output. That run sees e as a real
test input is seen, so its grid there is a function of e's input and the other pairs, and no program can pass on e by reading e's
output. A fit needs a pass on one pair at least, since a gold program can lose a pair: a DET determined by all pairs may not be
determined by fewer. A task with one train pair has no such run. The counts have loo:<outcome> per pair.

A table request that runs to the session's deadline ends the draw (Spent), and a candidate that does ends the OUT search at that form:
each later read of what it read costs one more deadline. A table that the table work cap stopped goes on, since gold has them: of 284
gold programs, 6 have OUT read such a relation, and body prefixes hit the cap 62 times.

The steers of S's proposal (README: Proposal) run on these draws, each from its file in the models directory. STEERS names them,
and Sampler's steers argument picks them; S's P settings that their fits had ('struct') go with them. A row's fields come from the
program drawn so far. A RULE's point group takes its depth as 1 + the deepest clause so far (gold's RULE on dev has that depth in
2961 of 3144 clauses, where 'RULE depth 3+' counts as one depth), and a relation's dag fields read the drawn forms. An INIT body has
the tilt alone, as S's ports have.
"""
import collections
import copy
import dataclasses
import gc
import itertools
import json
import math
import os
import pickle
import random
import re
import statistics
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('STRUCT_B', '1')  # S imports the terms of STRUCT_B only under this setting; set_steers sets the flag itself
import sample2_col as S  # noqa: E402
from fractions import Fraction  # noqa: E402

from sample2_col import M, arclog  # noqa: E402

S.ADMITS = True  # one Decoder.admits call per node, with no mask and no per-token call
S.REACH = False  # no look-ahead below a column or a value: an atom that cannot close is redrawn, which costs less

RULE_TOK, DET_TOK, INIT_TOK, OUT_TOK, SKIP_TOK, ALSO_TOK = 0, 1, 2, 7, 12, 13
KIND_TOK = dict(RULE=RULE_TOK, DET=DET_TOK, INIT=INIT_TOK)
EXAMPLE_TASK, EXAMPLE_TRAIN = 0, 1  # the example_kind of a task-wide table entry, and of a train pair's
TABLES = 'live', 'live'  # step_tables' task and case names; a decoder holds neither, and they only label its result
READER_OUT = '(OUT (input ^P ^Col))'  # the reader takes whole programs; this closes a scope's text and is not stepped
NEED_RESCUE = 64.0  # a port's boost for those types after a stop that the head's needs refused
NEED_STOP = 0.1  # the factor on an atom's stop chance where it holds a column of a type that the head needs
ANY_TYPE = '?'  # the type in a body's scope of a label whose type is not known
BRANCHES = 'RULE', 'key', 'port'  # the places of a body that may hold an OR, each with its counts in the priors
BIND_QUIT = 0.8  # the chance that a later branch with an unbound exported label fails, at each atom past bind_atoms
KEY_ALL = 0.9  # the chance that a keyed port with an unread key goes on: 830 of 907 gold ports of keys of two or more labels read them all
EXAMPLE_READ = dict(DET=0.2, INIT=0.03)  # the factor on a declared relation's Example column in a body of the kind: gold's atoms on declared relations read it in 32% of DETs' and 3.9% of INITs'; draws read it in 41% and 8% at these factors
FIELD_AGAIN = 0.01  # the factor on a field that a record site repeats: 15 of 1570 gold record sites have one
HEAD_FITS = dict(Position={'Position', 'Box'}, Offset={'Offset', 'Box'}, Axis={'Axis', 'Axis4'}, DiagAxis={'DiagAxis', 'Axis4'}, Dir={'Dir', 'Dir8'}, DiagDir={'DiagDir', 'Dir8'},
                 Point={'Position', 'Offset', 'Box'})  # the label types that a head column of a type takes, where a family's other members do not: the engine's lattice has no value in both of two siblings
NEED_BOOST = 4.0  # a port's boost for the types its head needs, as S's at the clause that OUT reads
KIND_BACKOFF = 2.0  # the weight of the walk counts over all states, against those of the program's state
GRID_RULES = 'malformed', 'equals input', 'same size', 'fixed size', 'size ratio', 'colors'  # Gate.holds reads these
GATE_RULES = frozenset(('no attempt', 'malformed', 'equals input', 'same size', 'colors'))  # the rules of Gate that refuse a fit (live_try.py --gold runs them on gold)
FOLD_BYTES = 1 << 30  # a leave-one-out session's cap
DEADLINE_SHARE = 0.9  # a request that took this share of the session's deadline ran to it
SUIT_COLUMNS = 2  # a relation's Position columns, and its Color columns, that Gate.suits reads
STEERS = 'struct', 'tilt', 'rel', 'choice'
STEER_FILES = dict(tilt='tilt_v1.json', rel='relR4_o.pkl', choice='choice5_o.pkl')


def size(grid):
    return len(grid), len(grid[0]) if grid else 0


def head_of(form):
    """The relation name that form text declares."""
    return S.strata.sexprs(form)[0][1]


def cell_masks(pair):
    """{mask size: (the cells a train pair wants, the cells that are right)}. A cell is a key: (y, x, color), (y, x) or color, by
    the mask's size. Where input and output have one size, the wanted cells are those that differ, since a relation can overlay the
    input; else they are the output's. A position or a color alone is right where it is wanted."""
    x, y = pair['input'], pair['output']
    want, right = np.zeros(9000, bool), np.zeros(9000, bool)
    for i, row in enumerate(y):
        for j, c in enumerate(row):
            right[300 * i + 10 * j + c] = True
            want[300 * i + 10 * j + c] = size(x) != size(y) or x[i][j] != c
    cells = want.reshape(900, 10)
    wp, wc = cells.any(1), cells.any(0)
    return {9000: (want, right), 900: (wp, wp), 10: (wc, wc)}


def overlap(rows, p, c, masks):
    """How well rows, an array with one row per table row, suit a train pair: wanted cells hit / (cells wanted + wrong cells). p is
    the column of a Position or Box's top, whose left is two columns on, and c that of a Color; either may be None. 1 means an
    overlay of the rows gives the pair's output."""
    ok, key, n = np.ones(len(rows), bool), 0, 1
    if p is not None:
        i, j = rows[:, p], rows[:, p + 2]
        ok, key, n = (i >= 0) & (i < 30) & (j >= 0) & (j < 30), 30 * i + j, 900
    if c is not None:
        ok, key, n = ok & (rows[:, c] >= 0) & (rows[:, c] < 10), 10 * key + rows[:, c], 10 * n
    seen = np.zeros(n, bool)
    seen[key[ok]] = True
    want, right = masks[n]
    return int((seen & want).sum()) / max(int(want.sum() + (seen & ~right).sum() + (~ok).sum()), 1)


class Gate:
    """What a task's train pairs say of a program. refused gives the rules that attempts break. A rule on the grids reads each test
    input, and holds there where a grid of its attempts passes it, since an attempt has up to two grids. leave_one_out gives the
    outcome on each train pair. suits ranks relations by their rows."""

    def __init__(self, task, settings):
        self.task, self.settings, self.folds = task, settings, None
        self.inputs = [t['input'] for t in task['test']]
        pairs = [(size(p['input']), size(p['output'])) for p in task['train']]
        self.identity = any(p['input'] == p['output'] for p in task['train'])  # a train output that equals its input
        self.same_size = all(a == b for a, b in pairs)
        self.fixed_size = pairs[0][1] if len({b for _, b in pairs}) == 1 else None
        ratios = {(Fraction(b[0], a[0]), Fraction(b[1], a[1])) for a, b in pairs}
        self.ratio = next(iter(ratios)) if len(ratios) == 1 else None
        self.out_colors = {c for p in task['train'] for row in p['output'] for c in row}
        self.masks = [cell_masks(p) for p in task['train']]

    def holds(self, rule, g, x):
        """Whether grid g, an attempt on test input x, passes the rule."""
        if rule == 'malformed':
            w = size(g)[1]
            return 1 <= len(g) <= 30 and 1 <= w <= 30 and all(len(r) == w and all(isinstance(c, int) and 0 <= c <= 9 for c in r) for r in g)
        if rule == 'equals input':
            return self.identity or g != x
        if rule == 'same size':
            return not self.same_size or size(g) == size(x)
        if rule == 'fixed size':
            return self.fixed_size is None or size(g) == self.fixed_size
        if rule == 'size ratio':
            return self.ratio is None or (self.ratio[0] * len(x), self.ratio[1] * len(x[0])) == size(g)
        return {c for r in g for c in r} <= self.out_colors | {c for r in x for c in r}  # 'colors'

    def refused(self, attempts):
        got = [] if all(any(size(g)[0] and size(g)[1] for g in att) for att in attempts) else ['no attempt']
        return got + [r for r in GRID_RULES if not all(any(self.holds(r, g, x) for g in att) for att, x in zip(attempts, self.inputs) if att)]

    def suits(self, ct):
        """{relation slot: how well its rows suit the train outputs} over step_tables result ct, at its best pair of columns: the mean
        overlap over its train entries. A task-wide table has an entry per DET assignment, of which one holds, so it takes the
        best entry, with the mean overlap over the train pairs. An entry with no rows to read counts for nothing."""
        T, base, out = ct.tables, ct.base_tables or 0, {}
        rel = M.col(ct, 'tables', 'relation') if isinstance(T['relation'], (bytes, bytearray, memoryview)) else T['relation']
        V = np.frombuffer(ct.values, np.int32)
        et, ex, ei = M.col(ct, 'entries', 'table'), M.col(ct, 'entries', 'example_kind'), M.col(ct, 'entries', 'example_index')
        ek, er, eo = M.col(ct, 'entries', 'kind'), M.col(ct, 'entries', 'rows'), M.col(ct, 'entries', 'offset')
        stop, vstop, fault = ct.entries['stop_bound'], ct.entries['value_stop_bound'], ct.entries['fault']
        train = collections.defaultdict(list)  # a table -> its entries
        for e in range(len(et)):
            if ex[e] in (EXAMPLE_TASK, EXAMPLE_TRAIN) and ek[e] == 0 and not (stop[e] or vstop[e] or fault[e]):
                train[et[e] - base].append(e)
        for j, es in train.items():
            types = [str(t) for t in T['column_types'][j]]
            at = list(itertools.accumulate((4 if t in M.WIDE else 1 for t in types), initial=0))
            ps = [a for a, t in zip(at, types) if t in ('Position', 'Box')][:SUIT_COLUMNS]
            cs = [a for a, t in zip(at, types) if t == 'Color'][:SUIT_COLUMNS]
            if rel[j] < 0 or not ps + cs:
                continue
            tabs = [(self.masks if ex[e] == EXAMPLE_TASK else [self.masks[ei[e]]], V[eo[e]:eo[e] + er[e] * at[-1]].reshape(-1, at[-1])) for e in es]
            pick = max if ex[es[0]] == EXAMPLE_TASK else statistics.fmean
            sites = [(p, c) for p in ps or [None] for c in cs or [None]]
            out[int(rel[j])] = max(pick([statistics.fmean(overlap(v, p, c, m) for m in ms) for ms, v in tabs]) for p, c in sites)
        return out

    def fold_sessions(self):
        """[(a session of the task with train pair e's output removed, e's output)] for each train pair e; none with one train pair,
        where no pair is left to fit."""
        if self.folds is None:
            train, self.folds = self.task['train'], []
            for i, e in enumerate(train if len(train) > 1 else ()):
                d = dict(self.task, train=train[:i] + train[i + 1:], test=self.task['test'] + [dict(input=e['input'])])
                self.folds.append((arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), self.settings, session_bytes=FOLD_BYTES), e['output']))
        return self.folds

    def leave_one_out(self, text):
        """The outcome of program text on each train pair: 'pass', 'wrong' (a grid that is not the pair's output), 'no attempt',
        'refused' (the decoder refuses it, or it faults, on the fewer pairs) or 'not ended' (it is not consistent on them)."""
        ids, model, _ = arclog.StudyProgram.from_sexp(text, self.settings).decode_stream()
        return [fold_outcome(sess, ids, model, y) for sess, y in self.fold_sessions()]


def fold_outcome(session, ids, model, y):
    dec = session.decoder()
    try:
        for t, m in zip(ids, model):
            if m:
                dec.step(t)
    except (arclog.Refusal, arclog.Fault):
        return 'refused'
    if not dec.ended:
        return 'not ended'
    att = dec.attempts()[-1]
    return 'pass' if y in att else 'wrong' if att else 'no attempt'


def sites(atom):
    """[(column, field or None, value)] of atom text: a site on a record column has a field."""
    out = []
    for p, record, v in re.findall(r'\(:(\d+) (?:((?:\(:\d+ [^()]+\) ?)+)\)|([^()]+)\))', atom):
        if record:
            out += [(int(p), int(q), x) for q, x in re.findall(r'\(:(\d+) ([^()]+)\)', record)]
        else:
            out.append((int(p), None, v))
    return out


def atom_parts(atom):
    """(negated, relation, {(column, field, value with no *)}) of atom text."""
    rel = re.match(r'\((?:NOT \()?([^\s()]*)', atom + '(')
    return atom.startswith('(NOT '), rel and rel[1], {(p, q, v.lstrip('*')) for p, q, v in sites(atom)}


def clash(atom, atoms, outer=()):
    """Whether atom text says nothing beside atoms, the texts of its list, or holds nowhere with them and outer, the atoms around that
    list: another atom of the list has its sites on its relation, or NOT of a part of an atom's sites stands beside that atom."""
    neg, rel, mine = atom_parts(atom)
    for other in (*atoms, *outer):
        neg2, rel2, theirs = atom_parts(other)
        if rel2 == rel and mine and theirs:
            if neg == neg2 and mine == theirs and other in atoms:
                return True
            if neg != neg2 and (mine if neg else theirs) <= (theirs if neg else mine):
                return True
    return False


def opposite(atom):
    """The text of NOT of atom text, or of the atom that a NOT holds: both in one list hold nowhere."""
    return atom[5:-1] if atom.startswith('(NOT ') else '(NOT %s)' % atom


def or_counts(cc):
    """What a draw of an OR reads of the compound counts cc (S.compound_counts): a body's chance of one, the part counts, the stop
    hazard of a branch, the chance that a later branch opens with a negation and the chance that an atom follows the OR."""
    shapes = {x[1]: v for x, v in cc.items() if x[0] == 'shape'}
    lens = {x[1]: v for x, v in cc.items() if x[0] == 'blen'}
    both = lambda name: {k: cc[(name, False, k)] + cc[(name, True, k)] for k in {x[2] for x in cc if x[0] == name}}  # noqa: E731
    comp = both('comp')
    return dict(comp=comp, reach=both('reach'), share=sum(v for k, v in shapes.items() if k.startswith('OR')) / sum(shapes.values()),
                shapes=[(int(k[2:]), v) for k, v in shapes.items() if k.startswith('OR') and v > 0],
                hazard={j: (lens.get(j, 0) + 0.5) / (sum(v for n, v in lens.items() if n >= j) + 1.0) for j in lens},
                neg1=(cc[('neg1',)] + 0.5) / (cc[('later',)] + 1.0), after=(cc[('after',)] + 0.5) / (sum(comp.values()) + 1.0))


def set_steers(models_dir, on):
    """S's module settings of the steers in on, a subset of STEERS; the others are off. One process has one set."""
    S.COL_FREQ = S.STRUCT_P = S.STRUCT_B = S.STRUCT_C = 'struct' in on
    for w in S.REL_W, S.REL_WB, S.VAL_W:  # a relation's or label's recency is written order, which a DAG does not have
        w.update({k: 0.0 for k in ('recency0', 'recency_log', 'newest') if k in w})
    path = {k: os.path.join(models_dir, f) if k in on else '' for k, f in STEER_FILES.items()}
    S.STEER_REL, S.STEER_CHOICE = path['rel'], path['choice']
    S.TILT_STOP = 'lw'
    S.TILT_TABLE = json.load(open(path['tilt']))['groups'] if path['tilt'] else None
    for tab in (S.TILT_TABLE or {}).values():  # pos: and bi: read an atom's written place and its predecessor; a body's atoms have no order
        tab['theta'] = {k: v for k, v in tab['theta'].items() if not k.startswith(('pos:', 'bi:'))}
    if S.STEER_REL:  # the models load here, before a deadline runs
        S.rel_scorer()
    if S.STEER_CHOICE:
        S.choice_scorer()


@dataclasses.dataclass(frozen=True)
class Limits:
    root_cap: int = S.ROOT_CAP  # atom-start frontiers a clause keeps
    node_cap: int = S.NODE_CAP  # nodes made since the frontiers were last dropped, at which a clause drops them
    atom_tries: int = S.ATOM_TRIES  # redraws of an atom
    cheap_tries: int = S.CHEAP_TRIES  # further redraws for a repeated or unjoined atom
    max_atoms: int = S.MAX_ATOMS  # atoms of a body
    branch_atoms: int = 12  # atoms of an OR's branch, the most that gold has
    bind_atoms: int = 6  # atoms of a later branch by which 98% of gold's bind the exported labels; past them a branch ends with chance BIND_QUIT
    port_atoms: int = 6  # atoms of a port's body; 0.4% of gold's are longer, and the checks of a long one cost most
    max_forms: int = 40  # clauses of a program before OUT is the only kind
    form_tries: int = 4  # draws of a clause that a gate or the decoder refuses
    out_pairs: int = 6  # (Position, Color) column pairs of a relation that the OUT search tries
    out_colors: int = 4  # the best suited Color relations, that a Position column is painted with
    out_unions: int = 3  # the best suited earlier relations, that a relation is joined with in a union
    out_cands: int = 40  # candidates of the OUT search at one form end


@dataclasses.dataclass
class Result:
    decoder: object  # a decoder that ended at a consistent OUT; None on the last Result
    attempts: object  # decoder.attempts()
    program: str  # decoder.program_form()
    counts: dict  # the draw counts so far
    seconds: float  # since draws began


@dataclasses.dataclass
class Clause:
    text: str  # the clause, reading the scope by the names of forms; its head is a name forms do not use
    decoder: object  # the decoder at the clause's end; its slots are the scope's
    tables: object  # arclog.step_tables' result at that decoder


class Drop(Exception):
    """A draw that cannot go on; the message is the reason."""


class Spent(Drop):
    """A table request ran to the session's deadline: the draw ends, as the next read of what it read costs one more deadline."""


class Deadline(Exception):
    """The deadline passed inside a draw."""


class LiveDrawer(S.Drawer):
    """S's Drawer with the limits as arguments."""

    labs_wanted = 0  # the count of labels of the clause at which a port's body has as many as its head takes
    example_read = 1.0  # the factor on the weight of a declared relation's Example column

    def __init__(self, V, counts, rng, regcols, fr, regtypes, limits):
        super().__init__(V, counts, rng, regcols, fr, regtypes)
        self.root_cap, self.node_cap = limits.root_cap, limits.node_cap

    def weights(self, n, os, rel, joined, leaf, steer, jset=None, must_join=False):
        """S's, with the field that a record site repeats at gold's share, and a declared relation's Example column, which S's column
        weights take for the first column, at example_read."""
        ws = super().weights(n, os, rel, joined, leaf, steer, jset, must_join)
        if n.phase == 'fcol':
            return [w * FIELD_AGAIN if self.fr.colpos.get(o) == n.need else w for o, w in zip(os, ws)]
        if n.phase == 'cols':
            return [w * self.example_read if self.example_column(n, o) else w for o, w in zip(os, ws)]
        return ws

    def example_column(self, n, o):
        """Whether column token o at cols node n is a declared relation's Example column: colmap has the relation's other columns."""
        known = self.colmap.get(M.slot_no(self.V.name(n.rtok))) if self.fr.KIND[n.rtok] == 'relation' else None
        return bool(known) and not any(p == self.fr.colpos[o] for p, _ in known)

    def steer_choice(self, fr, n, popts, opts, k, rel, joined, leaf, stop, key):
        """S's, with an atom going on where the port's head wants more labels, or where it holds a column of a needed type: a stop here
        leaves the port's head with no label."""
        fm, stq = super().steer_choice(fr, n, popts, opts, k, rel, joined, leaf, stop, key)
        if stop is not None and (n.labs < self.labs_wanted or any(self.col_needed(n.rtok, fr.colpos[o]) for o in opts)):
            stq *= NEED_STOP
        if stop is not None and opts and all(self.example_column(n, o) for o in opts):  # weights rank columns, so a lone Example column is read unless the atom stops
            stq = 1 - (1 - stq) * self.example_read
        return fm, stq


class LiveFrontier(S.FastFrontier):
    """S's FastFrontier less the tokens that the decoder refuses only at the body's END, which would end the draw of the body
    there: a fresh label at a site of a NOT atom, and a label of the form that this body cannot read."""

    hidden = frozenset()  # the label tokens of the form that this body cannot read

    def candidates(self, n):
        c = super().candidates(n)
        if n.phase in ('val', 'fval', 'op'):
            drop = self.hidden | {M.STAR} if n.neg else self.hidden
            c = [t for t in c if t not in drop and not (n.phase == 'op' and n.need == 1 and t == n.toks[-1])]  # a comparison of an operand with itself says nothing
        elif n.phase == 'root' and M.NOT in c and n.labs == len(self.hidden):  # no label for a NOT atom to join
            c.remove(M.NOT)
        elif n.phase == 'fcol':  # a key's record may hold one column name twice, and no gold site repeats one twice
            named = re.findall(r'\(:(\d+) [^(]', n.text[[m.start() for m in re.finditer(r'\(:\d+ \(:', n.text)][-1] + 1:])
            if len(named) == len(set(named)):
                c = [self.col_by_pos[n.need]] + c
        return c


class Program:
    """The state of one draw at a form boundary: its decoder's relations and the last step_tables result."""

    def __init__(self):
        self.ndecl = 0
        self.before = None
        self.decl_types, self.decl_slots = {}, {}
        self.colmaps = {k: {} for k in KIND_TOK}  # a form kind -> column_positions there: a RULE's column tokens leave out the Example column that a DET's or an INIT's read has
        self.colmap = self.colmaps['RULE']
        self.arity, self.names = {}, {}
        self.record_cols = {k: {} for k in KIND_TOK}  # a form kind -> FastFrontier.record_col there
        self.pending = {k: {} for k in KIND_TOK}  # a form kind -> relation slot -> (table slot, type) of a relation that its colmap lacks
        self.forms = []  # the parsed forms before the clause being drawn
        self.toks = []  # the model tokens of the bodies so far, for prior_uses
        self.new = []  # the relation slots the last form declared, with their tables
        self.grids, self.colors = [], []  # the OUT search's relations so far, the best suited first: (slot, Position token, Color token); (slot, Color token)
        self.suit = {}  # relation slot -> its rank in the OUT search: (Gate.suits, a random tie break)
        self.kinds = []  # the kind of each clause, which only next_kind reads, as counts
        self.written = {}  # a relation's head in the decoder -> its head in the forms of a scope

    def fork(self):
        """A copy whose dicts can change with no effect on this Program."""
        g = copy.copy(self)
        g.decl_types, g.decl_slots, g.arity = dict(self.decl_types), dict(self.decl_slots), dict(self.arity)
        g.colmaps, g.pending = {k: dict(v) for k, v in self.colmaps.items()}, {k: dict(v) for k, v in self.pending.items()}
        g.colmap = g.colmaps['RULE']
        return g


class Sampler:
    def __init__(self, models_dir, steers=STEERS):
        set_steers(models_dir, steers)
        with open(os.path.join(models_dir, 'live_priors.pkl'), 'rb') as f:
            self.pri = pickle.load(f)
        gc.set_threshold(100000, 50, 100)  # as S: the data is long-lived and holds few cycles
        self.run = None  # the Run of the last clause call, kept for the next call on its session

    def draws(self, session, seed, deadline, task, **limits):
        run = Run(self.pri, session, seed, deadline, task, Limits(**limits))
        while time.monotonic() < deadline:
            for got in run.one():
                yield run.result(got)
        yield run.result(None)

    def clause(self, session, seed, deadline, task, forms, kind='RULE', **limits):
        """A Clause of the kind over the scope forms, or None if no clause came (the module docstring has the rest)."""
        lim = Limits(**limits)
        if self.run is None or self.run.session is not session or self.run.lim != lim:
            self.run = Run(self.pri, session, seed, deadline, task, lim)
        return self.run.clause(seed, deadline, forms, kind)


class Run:
    """One task's draws."""

    def __init__(self, pri, session, seed, deadline, task, limits):
        self.pri, self.session, self.deadline, self.gate, self.lim = pri, session, deadline, Gate(task, session.settings), limits
        self.V = V = session.vocabulary
        self.spent_after = DEADLINE_SHARE * (session.settings.deadline_seconds or math.inf)
        self.root = session.decoder()
        self.rng = random.Random(seed)
        self.orcs = {'RULE': or_counts(pri['compound'])} | {k: or_counts(v) for k, v in pri['compounds'].items()}
        self.key_labels = sorted(pri.get('key_labels', {1: 1}).items())  # a key's count of ^ labels, and its gold count
        self.t0 = time.monotonic()
        self.c = collections.Counter()
        self.steer_stats = dict(rel=collections.Counter(), choice=collections.Counter())  # the Drawers' rel_stats and choice_stats
        self.ff0 = LiveFrontier(V, 0, pri['regcols'])
        self.first = {}  # a kind's token -> the decoder after it as a program's first token, and its step_tables result
        self.jc = collections.defaultdict(dict)  # a kind -> Drawer.jcache: its True entries on lib relations hold at every state of the run
        self.stopped = False  # whether an OUT candidate over the relation that the OUT search is at hit a limit
        self.scoped = None  # (forms, decoder, Program) of the last scope
        self.walk = pri['walk']
        self.walk_all = sum(self.walk['after'].values(), collections.Counter())
        nv = len(V)
        self.rel0 = V.id('&r0')
        self.tok = {V.name(i): i for i in range(nv) if V.kind(i) in ('component', 'proposer')}
        self.columns = sorted(self.ff0.colpos, key=self.ff0.colpos.get)
        facts = {i for i in self.ff0.starts_list if V.kind(i) == 'fact relation'}
        self.lib_starts = [i for i in self.ff0.starts_list if i not in facts]
        self.fact_starts = [i for i in self.ff0.starts_list if i in facts]

    def result(self, dec):
        counts = dict(self.c, limits=dataclasses.asdict(self.lim), steer_stats={k: dict(v) for k, v in self.steer_stats.items()})
        t = time.monotonic() - self.t0
        return Result(None, None, None, counts, t) if dec is None else Result(dec, dec.attempts(), dec.program_form(), counts, t)

    def one(self):
        """One draw, yielding the decoder of each consistent program it finds."""
        self.c['draws'] += 1
        try:
            yield from self.program()
        except Exception as e:  # noqa: BLE001
            self.failed(e)

    def failed(self, e):
        """Counts exception e, the end of a draw."""
        if isinstance(e, Deadline):
            self.c['drop:deadline'] += 1
        elif isinstance(e, Drop):
            self.c['drop:' + str(e)] += 1
        elif isinstance(e, arclog.Refusal):
            self.c['drop:refused'] += 1
        else:
            self.c['error:%s: %s' % (type(e).__name__, re.sub(r'\d+', 'N', str(e))[:60])] += 1

    def clause(self, seed, deadline, forms, kind):
        """One clause of the kind over the scope forms: a Clause, or None with the reason counted."""
        self.rng.seed(seed)
        self.deadline = deadline
        self.c['draws'] += 1
        try:
            dec, pg = self.scope(forms)
            f = self.form(pg, dec, kind)
        except Exception as e:  # noqa: BLE001
            self.failed(e)
            return None
        self.c['forms'] += 1
        line = f.program_form().split('\n')[len(forms)]
        head, used = head_of(line), set(pg.written.values())
        free = next(x for x in itertools.chain([head], ('&r%d' % i for i in itertools.count())) if x not in used)
        names = pg.written | {head: free}
        return Clause(re.sub(r'&r\d+', lambda m: names.get(m[0], m[0]), line), f, pg.before)

    # ---------------------------------------------------------------- a program

    def pick(self, opts, weights):
        return self.rng.choices(opts, weights=weights)[0]

    def next_kind(self, pg, dec):
        """The next clause's kind at dec, or None for the stop, from how many clauses of each kind pg has. The empty program has no stop."""
        w, top = self.walk, sum(self.walk_all.values())
        here = w['after'].get(tuple(min(pg.kinds.count(k), w['top']) for k in w['kinds']), {})
        names = [k for k in KIND_TOK if dec.admits([KIND_TOK[k]])[0]] + ['stop'] * bool(pg.kinds)
        ws = [here.get(k, 0) + KIND_BACKOFF * self.walk_all[k] / top + 0.01 for k in names]
        kind = self.pick(names, ws)
        return None if kind == 'stop' else kind

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

    def forget_slots(self):
        """Drops what the Drawers keep of relation slots, which mean another relation in another program."""
        for k, j in self.jc.items():
            self.jc[k] = {x: v for x, v in j.items() if v and max(t for t in x if isinstance(t, int)) < self.rel0}

    def scope(self, forms):
        """(decoder, Program) at the end of forms, as a draw of those forms leaves them. The last scope's stay, so more clauses over
        one scope replay it once."""
        t0, forms = time.perf_counter(), tuple(forms)
        if self.scoped is not None and self.scoped[0] == forms:
            return self.scoped[1], self.scoped[2].fork()
        self.forget_slots()
        pg, dec = Program(), self.root
        if forms:
            ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*forms, READER_OUT)), self.session.settings).decode_stream()
            stream = [(p[0], t) for t, m, p in zip(ids, model, paths) if m]
            for i, group in itertools.groupby(stream, lambda x: x[0]):
                if i == len(forms):
                    break
                first, *toks = [t for _, t in group]
                kind = self.V.name(first)
                if kind not in KIND_TOK:  # a form that no draw makes
                    raise Drop('scope: a %s form' % kind)
                f = self.open_form(pg, dec, kind)
                for t in toks:
                    rels = [x for x in f.step(t)[0] if self.V.kind(x) == 'relation']
                    if rels:
                        self.declared(pg, rels)
                        at = M.slot_no(self.V.name(rels[0]))
                        pg.names = pg.names | {self.V.name(x): '&r%d.%d' % (at, j) if kind == 'INIT' else self.V.name(x) for j, x in enumerate(rels)}
                pg.toks = pg.toks + toks
                pg.kinds = pg.kinds + [kind]
                dec = f
                self.close(pg, f)
            pg.written = {head_of(a): head_of(b) for a, b in zip(dec.program_form().split('\n'), forms)}
            f = dec.fork()
            f.step(RULE_TOK)
            self.fill_columns(pg, f)
        self.c['scope_seconds'] += time.perf_counter() - t0
        self.scoped = forms, dec, pg
        return dec, pg.fork()

    def program(self):
        pg, dec = Program(), self.root.fork()
        self.forget_slots()
        while len(pg.kinds) < self.lim.max_forms and (kind := self.next_kind(pg, dec)):
            pg.kinds = pg.kinds + [kind]
            dec = self.form(pg, dec, kind)
            self.c['forms'] += 1
            t0 = time.perf_counter()
            yield from self.search(pg, dec)
            self.c['search_seconds'] += time.perf_counter() - t0
        self.c['programs'] += 1

    def form(self, pg, dec, kind):
        """The decoder after a clause of the kind at dec, redrawn where a draw of it fails."""
        pg.forms = S.strata.sexprs(dec.program_form())
        for attempt in range(self.lim.form_tries):
            pg.new = []
            saved = copy.copy(pg)
            try:
                f = self.open_form(pg, dec, kind)
                return self.rule(pg, f) if kind == 'RULE' else self.det(pg, f) if kind == 'DET' else self.init(pg, f)
            except Spent:
                raise
            except (Drop, arclog.Refusal) as e:
                pg.__dict__.update(saved.__dict__)
                why = str(e) if isinstance(e, Drop) else 'refused: ' + re.sub(r'\d+', 'N', str(e))[:70]
                self.c['form:%s %s' % (kind, why)] += 1
        raise Drop('%s: no clause in %d tries' % (kind, self.lim.form_tries))

    def close(self, pg, f):
        """Records the form that the last step of decoder f ended: its relations' tables, for types and columns."""
        t0 = time.monotonic()
        pg.before = b = arclog.step_tables(f, *TABLES, True, pg.before)
        T = b.tables
        if not len(T['form']):
            self.spent(t0)
        rel = M.col(b, 'tables', 'relation') if isinstance(T['relation'], (bytes, bytearray, memoryview)) else T['relation']
        for j in range(len(T['form'])):
            if T['fault'][j]:
                raise Drop('relation table fault')
            if rel[j] >= 0:
                s, ts, cs = int(rel[j]), [str(t) for t in T['column_types'][j]], [int(c) for c in T['column_slots'][j]]
                pg.decl_types[s], pg.decl_slots[s] = ts, cs
                pg.new.append(s)
                if cs:
                    for k in KIND_TOK:
                        pg.pending[k][s] = list(zip(cs, ts))

    def spent(self, t0):
        """Raises Spent where a table request that began at t0 ran to the session's deadline. A step that gives no table in less time
        is no stop: 17 steps of gold's bodies give none, and the longest table call of 284 gold programs took 2.65 s of 10 s."""
        if time.monotonic() - t0 >= self.spent_after:
            raise Spent('table past the deadline')

    def table(self, fr, dec, pg):
        """S.body_table's (table, error) at decoder dec, with Spent where it ran to the deadline."""
        t0 = time.monotonic()
        got = S.body_table(fr, *TABLES, dec, pg.before)
        if got[0] is None:
            self.spent(t0)
        return got

    def declared(self, pg, forced):
        for t in forced:
            if self.V.kind(t) == 'relation':
                pg.ndecl = max(pg.ndecl, M.slot_no(self.V.name(t)) + 1)

    def end(self, pg, cur):
        """The decoder after the END of the clause at cur, with the clause's relation recorded."""
        f = cur.fork()
        forced = f.step(M.END)[0]
        self.declared(pg, forced)
        pg.names = pg.names | {self.V.name(t): self.V.name(t) for t in forced if self.V.kind(t) == 'relation'}
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
        pg.names = pg.names | {'&r%d' % s: '&r%d.%d' % (slots[0], i) for i, s in enumerate(slots)}  # a '.' tells a method (one_call)
        params, ports = pri['comp_ports'][comp]
        keyed = rng.random() < pri['keyed'][comp] / pri['comps'][comp]
        nlab, keys, fields = 0, {}, {}
        if keyed:  # the key port: one label of its body becomes the key
            dr = self.drawer(pg, 'INIT', f, 'key')
            dr.key_labels = self.pick(*zip(*self.key_labels))
            cur, toks = self.body(pg, dr, f, 'INIT', 0)[:2]
            stars = [i for i, t in enumerate(toks) if t == M.STAR]
            free = [j for j in range(len(stars)) if self.ff0.label_tok[j] not in dr.fr.hidden]  # a label local to a branch is no key
            if not free:
                raise Drop('key body makes no label')
            picked = rng.sample(free, min(len(free), dr.key_labels))
            types = self.label_types(dr, dr.drawn)
            keys = {self.ff0.label_tok[n]: types.get('L%d' % n) for n in picked}
            carets = {stars[n] for n in picked}
            g = f.fork()
            for j, t in enumerate(toks):
                g.step(M.CARET if j in carets else t)
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
            f, nlab = self.port(pg, f, comp, name, cols, params, nlab, keys, fields)
        for _ in ports:  # a key group's ports come again after it, for a port that reads no key
            if f.admits([RULE_TOK])[0]:
                break
            f = f.fork()
            f.step(SKIP_TOK)
        if not f.admits([RULE_TOK])[0]:
            raise Drop('%s did not end' % comp)
        self.close(pg, f)
        return f

    def head_need(self, bound, params, fields):
        """[set of types] that a port's body needs for its head columns bound: (column, type) pairs. fields has each type parameter's
        label types so far."""
        family = lambda t: HEAD_FITS.get(t) or next((set(x) for x in self.pri['families'] if t in x), {t})  # noqa: E731
        return [family(t) for _, t in bound if t not in params or t == 'Point'] + [family(x) for _, t in bound for x in fields.get(t, ()) if x != ANY_TYPE]

    def record_size(self, comp, name, c):
        """A head column's count of labels, from the priors."""
        sizes = self.pri.get('head_labels', {}).get((comp, name, c))
        return self.pick(*zip(*sizes.items())) if sizes else 1

    def head_column(self, f, labs, n):
        """(decoder after a head column at f that takes n labels of the label tokens labs, labels taken). Two labels or more are a record:
        each field's token, then its label."""
        f, got = f.fork(), []
        for j in range(n):
            if n > 1:
                f.step(self.ff0.col_by_pos[j])
            some = [x for x, y in zip(labs, f.admits(labs)) if y]
            if not some:
                raise Drop('head: no label for a field')
            got.append(self.rng.choice([x for x in some if x not in got] or some))
            f.step(got[-1])
        f.step(M.END)
        if n > 1:
            f.step(M.END)
        return f, got

    def port(self, pg, f, comp, name, cols, params, nlab, keys, fields):
        """The decoder after port name's body and head at f, with the labels of the INIT so far. fields has each type parameter's label
        types so far, and gets those of the columns that this head binds first."""
        pri, rng = self.pri, self.rng
        uses = sum(pri['ports'][comp, k, name] for k in (False, True))
        bound = [(c, t) for c, t in cols if rng.random() < (pri['heads'][comp, name, c] + 0.1) / (uses + 0.2)]
        need = self.head_need(bound, params, fields)
        sizes = {}  # a type -> the count of labels that a head column of it takes
        for c, t in bound:
            sizes[t] = len(fields[t]) if t in fields else sizes.get(t) or self.record_size(comp, name, c)
        dr = self.drawer(pg, 'INIT', f, 'port')
        dr.labs_wanted = nlab + max(sizes.values(), default=0)
        dr.want, dr.want_types = set(keys), frozenset(t for t in keys.values() if t)
        dr.fr.hidden = frozenset(self.ff0.label_tok[i] for i in range(nlab)) - dr.want  # a port's body reads its own labels and the key
        cur, toks, _, _ = self.body(pg, dr, f, 'INIT', nlab, need, keys)
        made = list(range(nlab, nlab + toks.count(M.STAR)))
        nlab = made[-1] + 1 if made else nlab
        f = cur.fork()
        f.step(M.END)
        names, labs = {c for c, _ in bound}, [self.ff0.label_tok[i] for i in made if i in self.ff0.label_tok]
        types = self.label_types(dr, dr.drawn)
        for c, t in cols:
            ok = f.admits(labs + [M.END])
            some = [x for x, y in zip(labs, ok) if y]
            if some and (c in names or not ok[-1]):  # the decoder refuses END at a column whose type an earlier port bound
                n = len(fields[t]) if t in fields else min(sizes.get(t, 1), len(some))
                f, got = self.head_column(f, some, n)
                if t in params:
                    fields[t] = [types.get(self.V.name(x), ANY_TYPE) for x in got]
            elif ok[-1]:
                f = f.fork()
                f.step(M.END)
            else:
                raise Drop('head: no label for %s' % name)
        return f, nlab

    # ---------------------------------------------------------------- a body

    def fill_columns(self, pg, dec, kind='RULE'):
        """colmap of the form kind and arity of the relations that lack them, at decoder dec, an atom start of that kind."""
        pending, cm = pg.pending[kind], pg.colmaps[kind]
        if pending:
            cm.update(S.column_positions(dec, self.V, pending, pg.ndecl))
            rest = {s: [x for x in e if x[1] != 'Example'] for s, e in pending.items() if s not in cm}  # the decoder refuses a read of a table's Example column here, so column_positions counts one column too few
            cm.update(S.column_positions(dec, self.V, rest, pg.ndecl))
            for s, e in pending.items():
                pg.arity[self.rel0 + s] = len({c for c, _ in e}) + 2
            pg.pending[kind] = {}

    def drawer(self, pg, kind, dec, place=None):
        """A Drawer of one body at decoder dec, an atom start, over the relations pg declares. place is the kind of body within an
        INIT, 'key' or 'port'; its Drawer has that place's OR counts, as orc, or None where the place has no OR."""
        ff = copy.copy(self.ff0)
        decl = list(range(self.rel0, self.rel0 + pg.ndecl))
        ff.starts_list = self.lib_starts + decl + self.fact_starts
        ff.starts = set(ff.starts_list)
        ff.arity, ff.record_col, ff.root, ff.created = pg.arity, pg.record_cols[kind], None, 0
        self.fill_columns(pg, dec, kind)
        dr = LiveDrawer(self.V, self.pri['atoms'][kind], self.rng, self.pri['regcols'], ff, self.pri['regtypes'], self.lim)
        dr.prog_names, dr.decl_types, dr.colmap, dr.jcache = pg.names, pg.decl_types, pg.colmaps[kind], self.jc[kind]
        dr.need_boost, dr.want_boost = NEED_BOOST, NEED_BOOST
        dr.place, dr.example_read = place or kind, EXAMPLE_READ.get(kind, 1.0)
        dr.orc = self.orcs.get(dr.place)
        self.steer(pg, dr, kind)
        return dr

    def closed(self, d, ends):
        """The program text that decoder d gives when `ends` END tokens close it, or None where the decoder refuses."""
        f = d.fork()
        try:
            for _ in range(ends):
                f.step(M.END)
        except arclog.Refusal:
            return None
        return f.program_form()

    def steer(self, pg, dr, kind):
        """The fields that the steers read on Drawer dr of a body of the kind, from the forms drawn so far."""
        fields, adj = S.dag_info(pg.forms, len(pg.forms))
        depth = 1 + max((fields(f[1])['depth'] for f in pg.forms), default=0)
        group = 'INIT port' if kind == 'INIT' else kind if kind == 'DET' else 'RULE depth %s' % (depth if depth < 3 else '3+')
        tab = (S.TILT_TABLE or {}).get(group)
        dr.tilt, dr.stop_tab = (tab['theta'], tab) if tab else (None, None)
        dr.rel_closed, dr.rel_base, dr.rel_off = self.closed, len(pg.forms), kind == 'INIT'
        dr.rel_pg, dr.row_pg = dict(point_group=group, depth=depth, d_out=None), dict(kind=kind)
        dr.rel_dag, dr.rel_stats, dr.choice_stats = (fields, adj), self.steer_stats['rel'], self.steer_stats['choice']
        dr.hist = collections.defaultdict(list)
        for t, cols in S.atom_uses(self.V, pg.toks):
            dr.hist[t].append(dict(same_clause=False, cols=cols))

    def can_end(self, d):
        try:
            d.forced(M.END)
            return True
        except arclog.Refusal:
            return False

    def port_can_end(self, d):
        """can_end at a port's END, where a head search that spent its budget ends the body: each atom after it gives the search more
        labels, and a new draw of the body costs less than the atoms that a pass would take."""
        try:
            d.forced(M.END)
            return True
        except arclog.Refusal as e:
            if 'spent its budget' in str(e):
                raise Drop('body: head search spent') from None
            return False

    def label_types(self, dr, atoms):
        """{label name: type} of the labels that drawn atom texts make, where the engine gives no table (inside a port). A relation
        with no known columns, as a proposer's or a component's output, or a library column of no one type, gives ANY_TYPE, so that the
        decoder judges its labels at the head. A label of a declared relation's Example column has no type here."""
        out = {}
        for atom in atoms:
            m = re.match(r'\((?:NOT \()?(\S+)', atom)
            rtok = self.V.id(m[1]) if m else None
            if rtok is not None:
                unknown = self.ff0.KIND[rtok] == 'relation' and M.slot_no(m[1]) not in dr.colmap
                for p, field, v in sites(atom):
                    t = ANY_TYPE if unknown else dr.col_type(rtok, p, field) or (None if self.ff0.KIND[rtok] == 'relation' else ANY_TYPE)
                    if t is not None and v[0] == '*':
                        out[v[1:]] = t
        return out

    def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        """Atoms at decoder dec (with nlab labels before them) until the hazard stops them: (decoder, tokens, atom texts,
        types in scope). Each atom passes the gates that read the decoder alone; a stop passes MIN2_KINDS and the head's needs."""
        lim, c, hz = self.lim, self.c, self.pri['hazard'][kind]
        cur, toks, text, scope = dec, [], [], ()
        top = lim.port_atoms if kind == 'INIT' else lim.max_atoms
        labels = None
        dr.drawn = []  # the text of each atom drawn, an OR's by its branches' atoms
        for k in range(1, top + 1):
            if time.monotonic() >= self.deadline:
                raise Deadline
            dr.need = set().union(*[x for x in need if not x & set(scope)]) if need else set()
            dr.want = (set(keys) - set(toks) or set(keys)) if keys else dr.want  # a port reads each key
            ored = None
            if dr.orc and self.rng.random() < self.p_or(dr.orc, k):
                dr.p_labels = labels
                ored = self.or_atom(pg, dr, cur, toks, text, scope, nlab, k)
            if ored is not None:  # the body goes on after the OR, or ends there
                c['or:drawn'] += 1
                cur, ctoks, ctext, scope, labels = ored
                toks += ctoks
                text.append(ctext)
                stop = self.rng.random() >= dr.orc['after']
            else:
                fr = dr.frontier(cur, nlab + toks.count(M.STAR), tuple(toks))
                got, free = None, 0
                for n_try in range(lim.atom_tries + lim.cheap_tries):
                    if n_try - free >= lim.atom_tries:
                        break
                    dr.p_k, dr.p_scope, dr.p_key, dr.p_last, dr.p_labels = k, tuple(scope), tuple(toks), (), labels
                    res, why = dr.atom(fr, max(k, 2) if keys else k, tuple(dr.want_types) + tuple(scope), tuple(toks))  # 98% of gold's keyed ports read the key, and a body's atoms have no order, so the atom drawn first joins it
                    if res is None:
                        c['try:construct:' + re.sub(r'refused .*', 'refused', why)] += 1
                        continue
                    if (k > 1 or keys) and not res[4] and res[5]:
                        c['try:unjoined'] += 1
                        free += 1
                        continue
                    if res[3] in text or clash(res[3], text):
                        c['try:repeat'] += 1
                        free += 1
                        continue
                    if kind != 'INIT' and not self.can_end(res[0].dec):  # at a port's END this check runs a search over head sites
                        c['try:unsafe'] += 1
                        continue
                    tb = None if kind == 'INIT' else self.table(fr, res[0].dec, pg)[0]  # the engine gives no table inside a port
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
                dr.drawn.append(got[3])
                scope = [str(t) for t in tb['types']] if tb is not None else list(scope) + list(self.label_types(dr, [got[3]]).values())
                labels = tb.get('labels') if tb is not None else None
                stop = self.rng.random() < self.stop_chance(dr, k, hz.get(k, hz[max(hz)]), toks, got, tb)
            if not stop and k < top:
                continue
            if nlab + toks.count(M.STAR) < dr.labs_wanted and k < top:
                c['gate:head labels'] += 1
                continue
            if need and ANY_TYPE not in scope and any(not x & set(scope) for x in need):
                c['gate:port head'] += 1
                dr.need_boost = NEED_RESCUE
                continue
            if kind == 'INIT' and not self.port_can_end(cur):
                c['gate:unsafe'] += 1
                continue
            if k == 1 and kind in S.MIN2_KINDS and ored is None and not S.one_call(dr, text):
                c['gate:one atom'] += 1
                continue
            if keys and not set(keys) & set(toks):
                c['gate:key unread'] += 1
                continue
            if set(keys) - set(toks) and self.rng.random() < KEY_ALL:
                c['gate:key partly read'] += 1
                continue
            pg.toks = pg.toks + toks
            return cur, toks, text, scope
        raise Drop('body: no stop in %d atoms' % top)

    def stop_chance(self, dr, k, h, toks, got, tb):
        """q's stop hazard after atom k: P's hazard h, its odds shifted by the tilt and the choice steer, as S's draw has it. got is
        the atom's result, toks the clause's tokens with it, tb the prefix table with it."""
        if k >= self.lim.max_atoms:
            return h
        hq = h
        if dr.stop_tab and 0 < h < 1:
            hq = h / (h + (1 - h) * math.exp(-S.tilt_stop_odds(dr.stop_tab, k)))
        d = dr.stop_shift(got[0].dec, tuple(toks), k, list(got[0].toks), got[2], got[3], tb, h)
        return hq * math.exp(d) / (1 - hq + hq * math.exp(d))

    # ---------------------------------------------------------------- an OR

    def p_or(self, o, k):
        """P(the body's k-th atom is an OR | it has a k-th atom) by the counts o. The counts have an IF among the compounds."""
        return (o['comp'].get(k, 0)) / (o['reach'].get(k, 0) + 1.0) * o['share']

    def or_atom(self, pg, dr, cur, toks, text, scope, nlab, k):
        """An OR at decoder cur that passes the gates of a body's table, where the body has one: (decoder, tokens, text, types in
        scope, labels of the table), or None."""
        done = self.or_form(dr, cur, toks, text, scope, nlab, k)
        if done is None:
            return None
        d, ctoks, ctext, hide, atoms = done
        if dr.place != 'RULE':  # the engine gives no table inside a port: the types are those of the labels the OR keeps
            seen = self.label_types(dr, atoms)
            kept = [t for x, t in seen.items() if self.ff0.label_tok.get(int(x[1:])) not in hide]
            types, labels = list(scope) + kept, None
        else:
            tb = self.table(dr.fr, d, pg)[0]
            sm = S.summary(tb)
            if sm is not None and sm['empty_inputs']:
                self.c['or:empty'] += 1
                return None
            if not self.can_end(d):
                self.c['or:unsafe'] += 1
                return None
            types = [str(t) for t in tb['types']] if tb is not None else list(scope)
            labels = tb.get('labels') if tb is not None else None
        dr.fr.hidden = dr.fr.hidden | hide
        dr.drawn += atoms
        return d, ctoks, ctext, types, labels

    def can_close(self, d):
        """Whether a branch can close at decoder d."""
        for t in (ALSO_TOK, M.END):
            try:
                d.forced(t)
                return True
            except arclog.Refusal:
                pass
        return False

    def negated(self, d, atom, local):
        """NOT of the first branch's atom tokens atom at decoder d, as S's negation_of: the sites that read a label from outside the
        branch or 0 stay and the others drop. (decoder, tokens, text), or None where the atom has a record site, no site stays, or
        the decoder refuses it."""
        V, rel, rest = self.V, atom[0], atom[1:]
        if V.kind(rel) not in S.RELATION_KINDS or len(rest) % 2:
            return None
        keep = []
        for c, v in zip(rest[::2], rest[1::2]):
            if V.kind(c) != 'column' or V.kind(v) == 'column':
                return None
            if v == M.ZERO or (V.kind(v) == 'label' and int(V.name(v)[1:]) not in local):
                keep += [c, v]
        if not keep:
            return None
        out = [M.NOT, rel] + keep
        f = d.fork()
        try:
            for t in out:
                f.step(t)
        except arclog.Refusal:
            return None
        if not self.can_close(f):
            return None
        return f, out, '(NOT (%s %s))' % (V.name(rel), ' '.join('(%s %s)' % (V.name(c), V.name(v)) for c, v in zip(keep[::2], keep[1::2])))

    def branch_atom(self, dr, d, labs, pkey, k, types, scope, outer, text, joins):
        """One atom of a branch at decoder d, with labs labels in the clause: (Drawer.atom's result, or None) after its tries. text is
        the branch's atoms and outer the body's. joins says that the atom may not stand unjoined."""
        lim, c, free = self.lim, self.c, 0
        fr = dr.frontier(d, labs)
        for n_try in range(lim.atom_tries + lim.cheap_tries):
            if n_try - free >= lim.atom_tries:
                break
            dr.p_k, dr.p_scope, dr.p_key, dr.p_last = k, tuple(scope), pkey, ()
            res, why = dr.atom(fr, max(k, 2) if types else k, types or scope, pkey)
            if res is None:
                c['or:try:construct:' + re.sub(r'refused .*', 'refused', why)] += 1
            elif not self.can_close(res[0].dec):
                c['or:try:unsafe'] += 1
            elif joins and not res[4] and res[5]:
                c['or:try:unjoined'] += 1
                free += 1
            elif res[3] in outer + text or opposite(res[3]) in outer + text or clash(res[3], text, outer):
                c['or:try:repeat'] += 1
                free += 1
            else:
                return res
        return None

    def branch(self, dr, d, labs, pkey, k, scope, outer, exported, first, local, want, want_types):
        """One branch at decoder d: (decoder, tokens, atom texts, label numbers made, numbers bound) or (None, reason). It holds S's
        rules of draw_compound: a branch may stop only where it can close, and a later branch closes where it binds every exported
        label and reads every label it makes, or with S's small chance where it breaks one of those. With exported None, the
        branch is the first and first takes its atoms' tokens. A key's labels are its keys alone, so a key's later branch may leave the
        labels it makes unread. want and want_types are the labels and types that the body wants: a
        port's key, which the first branch's first atom joins, as a body's first atom does."""
        hz, later = dr.orc['hazard'], exported is not None
        strict = dr.place != 'key'
        toks, text, made, read, bound, types = [], [], [], collections.Counter(), set(), {}
        start = 1
        if later and first and self.rng.random() < dr.orc['neg1']:  # the else branch: NOT of a first-branch atom
            got = self.negated(d, first[self.rng.randrange(len(first))], local)
            if got is not None:
                d, ntoks, ntext = got
                toks += ntoks
                text.append(ntext)
                read.update(int(x) for x in re.findall(r'(?<![*\w])L(\d+)', ntext))
                bound |= set(read) & exported
                start = 2
                self.c['or:else negation'] += 1
        for j in range(start, self.lim.branch_atoms + 1):
            if time.monotonic() >= self.deadline:
                raise Deadline
            wanted = (exported - bound) | ({x for x in made if not read[x]} if strict else set()) if later else set()
            dr.want = want | {self.ff0.label_tok[i] for i in wanted if i in self.ff0.label_tok}
            wtypes = [types[i] for i in wanted if types.get(i, ANY_TYPE) != ANY_TYPE] + list(want_types)
            dr.want_types = frozenset(wtypes)
            joins = k + j > 2 or (bool(want) and not later)
            res = self.branch_atom(dr, d, labs + toks.count(M.STAR), pkey + tuple(toks), k + j - 1, wtypes, scope, outer, text, joins)
            if res is None:
                return None, 'no atom'
            d = res[0].dec
            toks += list(res[0].toks)
            text.append(res[3])
            fresh = [int(x) for x in re.findall(r'\*L(\d+)', res[3])]
            joins = [int(x) for x in re.findall(r'(?<![*\w])L(\d+)', res[3])]
            types.update({int(x[1:]): t for x, t in self.label_types(dr, [res[3]]).items()})
            made += fresh
            read.update(joins)
            if not later and not res[3].startswith('(NOT'):
                first.append(list(res[0].toks))
            bound |= set(fresh) | (set(joins) & (exported or set()))
            named, unread = not later or exported <= bound, later and strict and any(not read[x] for x in made)
            if not named and j >= self.lim.bind_atoms and self.rng.random() < BIND_QUIT:
                return None, 'unbound'
            soft = None if named and not unread else S.P_UNREAD_LOCAL if named else S.P_UNNAMED if not unread else 0.0
            if self.rng.random() < hz.get(j, 1.0) and (soft is None or self.rng.random() < soft):
                self.c['or:soft close'] += soft is not None
                return d, toks, text, made, read, bound
        if soft is None:
            return d, toks, text, made, read, bound
        return None, 'unbound' if not named else 'unread'

    def or_form(self, dr, dec, toks, text, scope, nlab, k):
        """An OR at decoder dec, the k-th atom of a body with tokens toks and atom texts text, by S's rules (draw_compound): (decoder
        after its END, tokens, text, the label tokens that are local to a branch, the branches' atom texts), or None. The labels the
        first branch makes and does not read again are exported, and each label it reads again with chance P_REEXPORT. In a key, the
        key's labels alone are exported."""
        rng, c = self.rng, self.c
        nparts = self.pick(*zip(*dr.orc['shapes']))
        d = dec.fork()
        d.step(M.OR)
        ctoks, parts, exported, first, first_made, base = [M.OR], [], None, [], set(), nlab + toks.count(M.STAR)
        closed = dr.rel_closed
        hidden0, want, want_types = dr.fr.hidden, dr.want, dr.want_types
        dr.rel_closed = lambda x, ends: self.closed(x, ends + 1)  # one more END closes the OR
        all_made = set()
        try:
            for b in range(nparts):
                for attempt in range(S.BRANCH_TRIES if b else 1):
                    if attempt:
                        c['or:branch retry'] += 1
                    got = self.branch(dr, d, base + ctoks.count(M.STAR), tuple(toks + ctoks), k, scope, list(text), exported, first, first_made, want, want_types)
                    if got[0] is not None:
                        break
                    c['or:fail branch %d %s' % (min(b + 1, 3), got[1])] += 1
                else:
                    return None
                d, btoks, btext, made, read, bound = got
                sep = M.END if b == nparts - 1 else ALSO_TOK
                try:
                    d = d.fork()
                    d.step(sep)
                except arclog.Refusal:
                    c['or:fail close'] += 1
                    return None
                ctoks += btoks + [sep]
                parts.append(btext)
                all_made |= set(made)
                if b:
                    exported &= bound
                else:
                    first_made = set(made)
                    exported = {x for x in made if not read[x] or rng.random() < S.P_REEXPORT} if dr.place != 'key' else set(rng.sample(made, min(len(made), dr.key_labels)))
                dr.fr.hidden = hidden0 | frozenset(self.ff0.label_tok[i] for i in all_made - exported if i in self.ff0.label_tok)
        finally:
            dr.rel_closed, dr.fr.hidden = closed, hidden0
            dr.want, dr.want_types = want, want_types
        hide = frozenset(self.ff0.label_tok[i] for i in all_made - exported if i in self.ff0.label_tok)
        return d, ctoks, '(OR %s)' % ' '.join('(%s)' % ' '.join(p) for p in parts), hide, [a for p in parts for a in p]

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
                try:
                    g.step(p)
                    g.step(M.CARET)
                except arclog.Refusal:  # a column OUT admits alone: the engine asks for a Position or Box column first
                    self.c['out:column refused'] += 1
                    continue
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
        yield from self.judged(f, f.step(M.END)[1], label)

    def judged(self, f, cons, label):
        """Counts the consistency cons of the OUT that decoder f ended: yields f where it is a fit that counts."""
        kind = str(getattr(cons, 'kind', None)).rsplit('.', 1)[-1]
        self.c['out:%s' % kind] += 1
        self.stopped = self.stopped or kind == 'Stopped'
        if not f.ended:
            return
        broken = self.gate.refused(f.attempts())
        self.c.update('refused:' + r for r in broken)
        if GATE_RULES.intersection(broken):
            self.c['refused'] += 1
            return
        got = self.gate.leave_one_out(f.program_form())
        self.c.update('loo:' + r for r in got)
        self.c['loo:all pairs'] += all(r == 'pass' for r in got)
        if got and 'pass' not in got:
            self.c['refused'] += 1
            self.c['refused:loo'] += 1
            return
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
            rtok = next((t for t in forced if self.V.kind(t) == 'relation'), None)
            if rtok is None:
                self.c['out:no relation ' + label] += 1
                return
            yield from self.finish(f, rtok, label)
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
        suits = self.gate.suits(pg.before)
        pg.suit = pg.suit | {s: (suits.get(s, 0.0), self.rng.random()) for s in pg.new}
        best = lambda rels: sorted(rels, key=lambda r: pg.suit[r[0]], reverse=True)  # noqa: E731
        for s in sorted(pg.new, key=pg.suit.get, reverse=True):
            ts = pg.decl_types.get(s, ())
            if 'Color' in ts and not ({'Position', 'Box'} & set(ts)):
                if len(ts) == 1 and (0, None) in pg.colmap.get(s, {}):
                    pg.colors = best(pg.colors + [(s, self.ff0.col_by_pos[0])])
                continue
            if not {'Position', 'Box'} & set(ts):
                continue
            pairs = self.out_pairs(dec, self.rel0 + s, lim.out_pairs)
            self.stopped = False
            for p, c in pairs:
                for label, toks in self.cands(pg, s, p, c):
                    if self.stopped:  # the candidates after it read the same table, and hit the same limit at the same cost
                        self.c['out:after a stop'] += 1
                        break
                    if n >= lim.out_cands:
                        self.c['out:capped'] += 1
                        return
                    if time.monotonic() >= self.deadline:
                        raise Deadline
                    n += 1
                    t0 = time.monotonic()
                    if toks is None:
                        yield from self.finish_pair(dec, self.rel0 + s, p, c, label)
                    else:
                        yield from self.candidate(dec, toks, label)
                    if time.monotonic() - t0 >= self.spent_after:  # the next candidate reads the same tables
                        self.c['out:past the deadline'] += 1
                        return
            full = [(p, c) for p, c in pairs if c is not None]
            if full:
                pg.grids = best(pg.grids + [(s, *full[0])])

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
        yield from self.judged(f, cons, label)
