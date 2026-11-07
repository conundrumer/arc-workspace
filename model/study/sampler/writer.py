#!/usr/bin/env python
"""The token-level writer of one query body (writer-spec.md, "Writer").

    start = start_point(run, pg, kind)            # a WritingPoint after the kind token
    got = write(start, plan, rng, cache)          # Finished, or Ended

At each writing point the writer takes the mask of the decoder (Decoder.admissible), lets the lookahead components of the plan remove or lower ids,
and gives the ids that are left to the distribution. Where two ids or more are left, the choice is a node of the search (Chooser.node). The
query is finished at the first writing point whose mask holds a kind token. Then the writer closes it (Run.close) and takes its QueryHash.

The Place, the atoms and the labels of a writing point are computed from the model tokens by `Core.advance` alone. A lookahead component and a
distribution are pure functions of the writing point. The decoder of a writing point is forked by anything that tests a step, and never stepped.
"""
import collections
import copy
import dataclasses
import enum
import importlib
import math
import os
import sys
import time
from collections.abc import Callable, Mapping
from typing import Protocol

import numpy as np

import assignment_summaries as AS
import live
from live import ANY_TYPE, KIND_TOK, SKIP_TOK, ALSO_TOK, M, S, arclog

type TokenId = int
type QueryHash = int  # u128, from Decoder.query_hash
type Name = str  # the output Name; '' for a RULE or DET
type ValueHash = int  # u128, the TableHash of a DET value's TableRows
type Assignment = tuple[tuple[QueryHash, ValueHash], ...]  # over D(t), sorted by QueryHash; () when D(t) is empty
type Table = tuple[QueryHash, Name] | str  # a query's table; a given table by its own name

REL_KINDS = S.RELATION_KINDS
GROUP_INITS = {'INIT': 1, 'RIGID_DET': 2, 'DEMONSTRATED': 1, 'CHOOSE': 1}  # kinds with port decisions, and the count of decisions that are key bodies (a CHOOSE's `for`)
PORT_KINDS = 'INIT', 'RIGID_DET', 'DEMONSTRATED'  # kinds whose bodies are ports, under the port caps
DEMO_TOKEN_FACTOR = 4  # a DEMONSTRATED query ends at this many times Limits.model_tokens; each of its forms, and its own key and inputs, at Limits.model_tokens. Gold's longest has 303 model tokens


def query_hash(dec, index=-1):
    """The QueryHash of the query at `index` of decoder dec: the decoder's `query_hash`, else its earlier names `definition_hash` and `form_id`."""
    got = getattr(dec, 'query_hash', None) or getattr(dec, 'definition_hash', None) or dec.form_id
    return got(index)


def ids_of(mask):
    """The ids of a Decoder.admissible mask, as a sorted uint32 array."""
    return np.flatnonzero(np.unpackbits(np.frombuffer(mask, np.uint8), bitorder='little')).astype(np.uint32)


class Phase(enum.Enum):
    KIND = 0
    PROPOSER = 1
    COMPONENT = 2
    PORT = 3
    KEY = 4
    ATOM_START = 5
    COLUMN = 6
    FIELD = 7
    VALUE = 8
    OPERAND = 9
    HEAD = 10


@dataclasses.dataclass(frozen=True, slots=True)
class Place:  # where the next model token goes
    phase: Phase
    port: int | None  # the input port of an INIT or a DEMONSTRATED form whose body holds the next token (its column position); None outside a port
    branch: tuple[int, ...]  # the branch index at each open OR, outermost first
    negated: bool  # the open atom stands under NOT
    atoms: int  # closed atoms of the current body (a closed OR or ALL counts as one)


@dataclasses.dataclass(frozen=True, slots=True)
class Label:
    tok: TokenId
    types: tuple[str, ...]  # the types of its sites, the site that made it first
    body: int  # the body that made it
    path: tuple  # the open OR, IF and ALL groups it was made in, as (group number, 'OR', 'IF' or 'ALL', branch or stage); an IF has the stages test, then, else (0, 1, 2)
    key: bool  # made by `^`
    reads: tuple  # (body, group path) of each atom that read it since
    hidden: bool  # its group closed and did not export it
    field: bool = False  # a field of a DEMO_RULE, which each form of the rule may read


@dataclasses.dataclass(frozen=True, slots=True)
class Labels:  # each label so far, with its types and the places that may use it
    items: tuple[Label, ...] = ()

    def __len__(self):
        return len(self.items)

    def usable(self, point):
        """The label tokens that the place of `point` may read."""
        T = point.track
        cur = {u: b for u, _, b in T.path}
        out = []
        for L in self.items:
            if L.hidden:
                continue
            if L.field:
                out.append(L.tok)
                continue
            if L.body != T.body:
                if (L.key and T.round == 0) or L.body == T.shared:
                    out.append(L.tok)
                continue
            ok = True
            for u, kd, b in L.path:
                cb = cur.get(u)
                if cb is None or (kd == 'OR' and cb != b and not (b == 0 and cb > b)):
                    ok = False
                    break
                if kd == 'IF' and cb != b and not (b == 0 and cb == 1) and not (b == 1 and cb == 2):  # the test's labels stand in the then; the then's, in the else
                    ok = False
                    break
            if ok:
                out.append(L.tok)
        return frozenset(out)

    def keys(self, point):
        """The key labels that the place may read."""
        use = self.usable(point)
        return frozenset(L.tok for L in self.items if L.key and L.tok in use)


@dataclasses.dataclass(slots=True)
class Track:
    """What `advance` keeps beyond Place: a mutable record that is copied at each step and never changed once a WritingPoint holds it."""
    where: str = 'body'  # start, group, body, head, rule (between the forms of a DEMONSTRATED form's rules), answer (the columns after a PREDICT body) or done
    body: int = 0
    decision: int = -1  # the port decision of an INIT, RIGID_DET or DEMONSTRATED form that the next token answers
    last_pos: int = -1
    round: int = 0  # 1 after the key group: the ports that come again outside it
    cur_pos: int | None = None  # the column position of the port at the decision
    port: int | None = None
    inkey: bool = False
    path: tuple = ()
    uid: int = 0
    atom: tuple = ()
    text: str = ''
    rtok: int | None = None
    col: int | None = None
    recpos: int | None = None
    rec: bool = False
    need: int = 0
    negated: bool = False
    top: int = 0
    texts: tuple = ()  # (group path, rendered text) of each closed atom of the body
    rels: tuple = ()  # the relation tokens that the decoder forced
    proposed: bool = False
    one: bool = False  # inside a ONE mark: its labels follow, then END
    uses: tuple = ()  # (label token, index in firsts of the atom that made or read it) for each use in the body
    past_atoms: tuple = ()  # the model tokens of the closed atoms of the bodies before the current one (an INIT's or RIGID_DET's key and earlier ports)
    past_texts: tuple = ()  # the texts of those, as texts
    firsts: tuple = ()  # (group path, first model token) of each atom or compound started in the body, in order (NOT, a comparison, ALL and OR count as atoms)
    end_atom: tuple = ()  # (body, top) of the last top-level atom, not negated, that had a COLUMN point
    end_ok: bool = False  # END was in the mask at the last COLUMN point of that atom
    absent: int = 0  # the count of those atoms in a row in the body with END absent at their last COLUMN point
    form: str = ''  # 'DEMONSTRATED' in a DEMONSTRATED query, else ''
    sub: str = ''  # the kind of the form of a DEMO_RULE that holds the next token ('RULE' for a PREDICT clause); '' outside one
    predict: bool = False  # the form of the DEMO_RULE is its PREDICT clause
    alt: bool = False  # the next form of the DEMO_RULE follows ALT_FORM: a label scope of its own
    base: int = 0  # the index in the tokens of the kind token of the form that holds the next token (a DEMO_RULE's form, else the query's)
    rules: int = 0  # the DEMO_RULEs of the DEMONSTRATED query so far
    rule_forms: int = 0  # the forms of the current DEMO_RULE so far, its PREDICT clause included
    rule_fields: int = 0  # the fields of the current DEMO_RULE
    predicted: bool = False  # the current DEMO_RULE's PREDICT clause has closed
    answered: bool = False  # a column of the PREDICT clause took a label
    no_targets: bool = False  # a PREDICT clause closed with no column to fill: the key and the `value` head give none, so no rule fills one and the form has no END
    shared: int = -1  # in a CHOOSE form, the body of its `from` once that body has started: its `never` bodies may read its labels; -1 elsewhere


@dataclasses.dataclass(frozen=True, slots=True)
class WritingPoint:
    dec: arclog.Decoder  # the writing point's decoder; a component forks it and never steps it
    pg: object  # the scope's Program (live.Program), one for all writing points of a try
    kind: str  # 'RULE', 'DET', 'INIT', 'CHOOSE', 'RIGID_DET' or 'DEMONSTRATED': the query's kind, or in a DEMO_RULE the kind of its form that holds the next token
    tokens: tuple[TokenId, ...]  # the query's model tokens so far, the kind token first
    place: Place
    atoms: tuple[tuple[TokenId, ...], ...]  # the model tokens of each closed atom of the current body
    labels: Labels
    run: object  # the Run that makes the query
    track: Track
    open_atom: tuple[TokenId, ...]  # the model tokens of the atom so far
    ids_: np.ndarray  # the mask, as ids
    memo: dict = dataclasses.field(default_factory=dict, compare=False)  # per writing point: factors, logits, features
    back: tuple | None = dataclasses.field(default=None, compare=False)  # (the decoder before the last token, its back), None at the first point: dec_at reads it


def dec_at(pt, i):
    """The decoder of writing point pt after its first i tokens (1 <= i <= len(pt.tokens)): a decoder of an earlier point of its path, which a caller forks and never steps."""
    d, back = pt.dec, pt.back
    for _ in range(len(pt.tokens) - i):
        d, back = back
    return d


@dataclasses.dataclass(frozen=True, slots=True)
class Limits:  # the loop's hard caps; a path past a cap ends
    model_tokens: int
    max_atoms: int = 16
    port_atoms: int = 12
    branch_atoms: int = 12
    port_absent: int = 6  # a port body of a PORT_KINDS form ends after this count of top-level atoms in a row with END absent (Track.absent); 0 turns it off
    demo_rules: int = 4  # the DEMO_RULEs of a DEMONSTRATED query; gold has at most 3
    rule_forms: int = 8  # the forms of a DEMO_RULE, its PREDICT clause included; gold has at most 5
    rule_fields: int = 4  # the fields of a DEMO_RULE; gold has at most 1


@dataclasses.dataclass(frozen=True, slots=True)
class Finished:
    dec: arclog.Decoder  # the decoder after the query's last token
    tokens: tuple[TokenId, ...]
    query_hash: QueryHash  # a query, never an assignment
    reads: list  # S.atom_uses(V, tokens)


@dataclasses.dataclass(frozen=True, slots=True)
class Ended:
    reason: str  # 'empty', a cap ('cap:tokens', 'cap:branch', 'cap:port', 'cap:body', 'cap:stuck', 'cap:demo'), or the name of the component that removed the last id


class Lookahead(Protocol):
    name: str

    def factors(self, point: WritingPoint, ids: np.ndarray) -> np.ndarray: ...
    # ids: uint32, sorted, the ids that earlier components left
    # result: float64, len(ids); -inf removes the id, 0 keeps it, a finite value below 0 lowers it


class Distribution(Protocol):
    name: str
    version: str  # in the search fingerprint
    uses: tuple[str, ...]  # the feature names it uses

    def logits(self, point: WritingPoint, ids: np.ndarray, x: 'Features') -> np.ndarray: ...
    # result: float64, len(ids), finite


class Cost(Protocol):
    def bits(self, point: WritingPoint, ids: np.ndarray) -> np.ndarray: ...
    # result: float64, len(ids), at least 0; bits off the search bound of each option


@dataclasses.dataclass(frozen=True, slots=True)
class Plan:
    lookahead: tuple[Lookahead, ...]  # applied in this order
    distribution: Distribution
    cost: Cost | None  # bits off the search bound per option; OrBits is one
    limits: Limits


# ---------------------------------------------------------------- the writer core

class Core:
    """The vocabulary's token classes, and `advance`. One per Run."""

    def __init__(self, run):
        V = run.V
        n = len(V)
        self.run, self.V = run, V
        self.kind = [V.kind(i) for i in range(n)]
        self.names = [V.name(i) for i in range(n)]
        self.is_rel = np.array([k in REL_KINDS for k in self.kind])
        self.is_label = np.array([k == 'label' for k in self.kind])
        self.is_column = np.array([k == 'column' for k in self.kind])
        self.is_proposer = np.array([k == 'proposer' for k in self.kind])
        self.colpos, self.label_tok = run.ff0.colpos, run.ff0.label_tok
        self.ALL = V.id('ALL')
        self.IF = V.id('IF')
        self.ONE = V.id('ONE')
        self.regtypes = run.pri['regtypes']
        live.bind_vocabulary(V)
        self.kind_ids = np.array(sorted(KIND_TOK.values()), np.uint32)  # the tokens that open a query
        self.demo = dict(live.DEMO_TOK)  # the ids of the DEMONSTRATED form's control tokens; empty for a vocabulary without them
        self.end_ids = np.array(sorted(set(KIND_TOK.values()) | set(self.demo.values())), np.uint32)  # a mask that holds one of these follows the end of a form
        self.form_kinds = {i: n for n, i in KIND_TOK.items()} | ({V.id('CHOOSE'): 'CHOOSE', self.demo['PREDICT']: 'RULE'} if self.demo else {})  # a token that opens a form of a DEMO_RULE -> the form's kind

    def col_type(self, pt, rtok, pos, field=None):
        """The type of column `pos` of table or relation token rtok, without the type's parameters; ANY_TYPE where unknown."""
        if rtok is None or pos is None:
            return ANY_TYPE
        name = self.names[rtok]
        if self.kind[rtok] == 'relation':
            t = pt.pg.colmaps.get('INIT' if pt.kind == 'CHOOSE' else pt.kind, pt.pg.colmaps['INIT']).get(M.slot_no(name), {}).get((pos, field))  # a CHOOSE reads as an INIT does
        else:
            ts = self.regtypes.get(name)
            t = str(ts[pos]) if ts and field is None and 0 <= pos < len(ts) else None
        return ANY_TYPE if t is None else str(t).split('(')[0]

    def start(self, run, pg, dec, kind):
        """The first WritingPoint of a query of `kind`, at decoder `dec` after the kind token."""
        T = Track(where='start' if kind == 'INIT' else 'group' if kind in ('RIGID_DET', 'DEMONSTRATED', 'CHOOSE') else 'body', form='DEMONSTRATED' if kind == 'DEMONSTRATED' else '')
        if kind in ('RIGID_DET', 'DEMONSTRATED', 'CHOOSE'):
            T.decision = 0
        pt = WritingPoint(dec, pg, kind, (KIND_TOK[kind],), None, (), Labels(), run, T, (), ids_of(dec.admissible()))
        return self._with_place(pt, T, (), Labels(), pt.tokens, ())

    def _with_place(self, pt, T, atoms, labels, tokens, ids):
        kind = self.kind_at(T, pt.kind)
        place = Place(self.phase_of(T, kind, len(tokens)), T.port if T.where in ('body', 'head') else T.cur_pos if T.where == 'group' and not self.inkey_next(T, kind) else None,
                      tuple(b for _, k, b in T.path if k == 'OR'), T.negated, T.top)
        return dataclasses.replace(pt, kind=kind, place=place, atoms=atoms, labels=labels, tokens=tokens, track=T, open_atom=T.atom)

    @staticmethod
    def kind_at(T, kind):
        """The kind of the form that holds the next token: a DEMO_RULE's form, else the query's."""
        return T.sub or T.form or kind

    @staticmethod
    def inkey_next(T, kind):
        return T.decision < GROUP_INITS.get(kind, 0)

    def phase_of(self, T, kind, ntok):
        w = T.where
        if w == 'start':
            return Phase.COMPONENT
        if w == 'group':
            return Phase.KEY if self.inkey_next(T, kind) else Phase.PORT
        if w == 'head':
            return Phase.HEAD
        if w in ('done', 'rule'):
            return Phase.KIND
        if w == 'answer':
            return Phase.HEAD
        if T.col is not None:
            return Phase.VALUE
        if T.need > 0 or T.one:
            return Phase.OPERAND
        if T.rec:
            return Phase.FIELD
        if T.atom:
            return Phase.COLUMN
        if kind in ('RULE', 'DET') and ntok - T.base == 1 and not T.predict:
            return Phase.PROPOSER
        return Phase.ATOM_START

    # ---- advance

    def advance(self, pt, t, forced, ids2):
        """The WritingPoint after model token t at `pt`; forced are the ids that the decoder forced after t, ids2 the mask after them. The
        decoder of the result is set by the caller."""
        T = copy.copy(pt.track)
        labs, atoms = list(pt.labels.items), pt.atoms
        kind, k = pt.kind, self.kind[t]
        T.rels += tuple(x for x in forced if self.kind[x] == 'relation')
        where = T.where
        if where == 'rule':
            self._rule(pt, T, t, forced, labs, ids2)
        elif where == 'answer':
            self._answer(T, t, labs, ids2)
        elif where == 'start':  # the INIT's component
            self._classify(T, kind, ids2, forced)
        elif where == 'group':
            if t == SKIP_TOK:
                self._classify(T, kind, ids2, forced)
            elif t == M.END:  # a port of no atoms: its head follows
                T.where, T.port = 'head', T.cur_pos
                self._classify(T, kind, ids2, forced, head=True)
            else:
                T.past_atoms, T.past_texts = T.past_atoms + atoms, T.past_texts + T.texts
                T.where, T.body, T.top, T.texts, T.firsts, T.uses, atoms = 'body', T.body + 1, 0, (), (), (), ()
                T.inkey = T.decision < GROUP_INITS.get(kind, 0)
                T.port = None if T.inkey else T.cur_pos
                T.path = ()
                if kind == 'CHOOSE' and T.decision == 1:  # the `from` body, after the `for` body or its SKIP
                    T.shared = T.body
                self._body(pt, T, t, k, forced, labs, ids2, atoms_box := [atoms])
                atoms = atoms_box[0]
        elif where == 'head':
            self._classify(T, kind, ids2, forced, head=True)
        else:
            box = [atoms]
            self._body(pt, T, t, k, forced, labs, ids2, box)
            atoms = box[0]
        if T.sub and T.where == 'done':  # a form of a DEMO_RULE ended
            self._to_rule(T)
        if T.where == 'body' and not T.path and not T.negated and self.phase_of(T, self.kind_at(T, kind), len(pt.tokens) + 1) == Phase.COLUMN:  # a top-level atom that may close: the run of atoms after which END is absent
            key = (T.body, T.top)
            if key != T.end_atom:
                T.absent = T.absent + 1 if T.end_atom[:1] == (T.body,) and not T.end_ok else 0
                T.end_atom = key
            T.end_ok = M.END in ids2
        return T, Labels(tuple(labs)), atoms

    def _classify(self, T, kind, ids2, forced, head=False):
        """Sets T after a step that left a body, a port decision or a head token: done, the next port decision, or a head. After the last input of a
        DEMONSTRATED form its rules follow."""
        if T.form and not T.sub and (ids2 == self.demo['DEMO_RULE']).any():
            T.where = 'rule'
            return
        if np.isin(ids2, self.end_ids).any():
            T.where = 'done'
            return
        if (ids2 == SKIP_TOK).any() or self.is_rel[ids2].any():
            T.where = 'group'
            T.decision += 1
            pos = next((self.colpos[x] for x in reversed(forced) if x in self.colpos), None)
            if pos is None and kind == 'CHOOSE' and T.decision >= 3:  # a CHOOSE's later `never` body follows ALSO, which forces no column: it is on the port of the first
                T.cur_pos, T.port = T.last_pos, None
                return
            if pos is not None:
                if pos <= T.last_pos:
                    T.round += 1
                T.last_pos = pos
            T.cur_pos, T.port = pos, None
        elif T.where in ('body', 'start', 'group') and not head:
            T.where = 'head'
        else:
            T.where = 'head'

    def _body(self, pt, T, t, k, forced, labs, ids2, box):
        """Token t at a body (T.where is body, or t is the first token of one)."""
        kind = pt.kind
        if T.one:  # a ONE mark: the labels it names, then its END
            if k == 'label':
                self._read(labs, t, T, ANY_TYPE)
            else:
                T.one = False
            return
        if T.col is not None and not (k == 'column' or k == 'label' or t in (M.STAR, M.CARET, M.ZERO)):  # the site has no value, which the decoder admits in some bodies, such as a DEMONSTRATED form's key and PREDICT clause: the token is read at the site's atom
            T.text += ')'
            T.col = None
        if T.col is not None:  # a value is due
            if k == 'column':  # a record's field
                if not T.rec:
                    T.recpos = T.col
                T.rec, T.col = True, self.colpos[t]
                T.atom += (t,)
                T.text += ' (:%d' % T.col
                return
            field = T.col if T.rec else None
            pos = T.recpos if T.rec else T.col
            ty = self.col_type(pt, T.rtok, pos, field)
            if t in (M.STAR, M.CARET):
                lab = next(x for x in forced if self.kind[x] == 'label')
                labs.append(Label(lab, (ty,), T.body, T.path, t == M.CARET, (), False))
                T.uses += ((lab, len(T.firsts) - 1),)
                shown = ('*' if t == M.STAR else '^') + self.names[lab]
            elif k == 'label':
                self._read(labs, t, T, ty)
                shown = self.names[t]
            else:
                shown = self.names[t]
            T.atom += (t,)
            T.text += ' %s)' % shown
            T.col = None
            return
        if T.need > 0:  # an operand of a comparison
            ty = ANY_TYPE
            if t == M.STAR:
                lab = next(x for x in forced if self.kind[x] == 'label')
                labs.append(Label(lab, (ty,), T.body, T.path, False, (), False))
                T.uses += ((lab, len(T.firsts) - 1),)
                shown = '*' + self.names[lab]
            else:
                if k == 'label':
                    self._read(labs, t, T, ty)
                shown = self.names[t]
            T.atom += (t,)
            T.text += ' ' + shown
            T.need -= 1
            return
        if T.rec:  # between the fields of a record
            if k == 'column':
                T.col = self.colpos[t]
                T.atom += (t,)
                T.text += ' (:%d' % T.col
            else:  # END
                T.rec, T.recpos = False, None
                T.atom += (t,)
                T.text += ')'
            return
        if T.atom:
            if k == 'column':
                T.col = self.colpos[t]
                T.atom += (t,)
                T.text += ' (:%d' % T.col
                return
            if t in (M.STAR, M.CARET, M.ZERO) or k == 'label':  # a further value of the last site, as a column of several values takes
                if t in (M.STAR, M.CARET):
                    lab = next(x for x in forced if self.kind[x] == 'label')
                    labs.append(Label(lab, (ANY_TYPE,), T.body, T.path, t == M.CARET, (), False))
                    T.uses += ((lab, len(T.firsts) - 1),)
                    shown = ('*' if t == M.STAR else '^') + self.names[lab]
                else:
                    if k == 'label':
                        self._read(labs, t, T, ANY_TYPE)
                    shown = self.names[t]
                T.atom += (t,)
                T.text = T.text[:-1] + ' %s)' % shown
                return
            self._close_atom(T, box)
        # an atom start, or a token of a compound or of the body
        if k in REL_KINDS:
            if not T.negated:
                T.firsts += ((T.path, t),)
            T.atom = (M.NOT, t) if T.negated else (t,)
            T.rtok, T.text = t, '(%s' % self.names[t]
        elif t == M.NOT:
            T.firsts += ((T.path, t),)
            T.negated = True
        elif t in M.CMP:
            T.firsts += ((T.path, t),)
            T.atom, T.rtok, T.need, T.text = (t,), None, 2, '(%s' % self.names[t]
        elif t == M.OR:
            T.firsts += ((T.path, t),)
            T.path += ((T.uid, 'OR', 0),)
            T.uid += 1
        elif t == self.ALL:
            T.firsts += ((T.path, t),)
            T.path += ((T.uid, 'ALL', 0),)
            T.uid += 1
        elif t == self.IF:
            T.firsts += ((T.path, t),)
            T.path += ((T.uid, 'IF', 0),)
            T.uid += 1
        elif t == self.ONE:
            T.one = True
        elif t == ALSO_TOK:
            u, kd, b = T.path[-1]
            T.path = T.path[:-1] + ((u, kd, b + 1),)
        elif t == M.END:
            if T.path:
                u, kd, b = T.path[-1]
                if (kd == 'ALL' and b == 0) or (kd == 'IF' and b < 2):
                    T.path = T.path[:-1] + ((u, kd, b + 1),)
                else:
                    T.path = T.path[:-1]
                    self._close_group(labs, u, kd, b)
                    if not T.path:
                        T.top += 1
            else:
                T.negated = False
                if T.predict:  # the engine names the columns that the clause fills, and each takes a label or SKIP
                    T.where = 'answer'
                    T.no_targets = not ((ids2 == SKIP_TOK).any() or self.is_label[ids2].any())
                    self._answered(T, ids2)
                elif kind in ('RULE', 'DET'):
                    T.where = 'done' if np.isin(ids2, self.end_ids).any() else 'body'
                else:
                    self._classify(T, kind, ids2, forced, head=not T.inkey)
                    if not T.inkey and T.where == 'head':
                        T.port = T.cur_pos
        elif k == 'proposer':
            T.proposed = True

    def _rule(self, pt, T, t, forced, labs, ids2):
        """Token t between the forms of a DEMONSTRATED form's rules: DEMO_RULE, a field's `*`, ALT_FORM, the token that opens a form or a PREDICT clause, or the END of a rule or of the form."""
        demo = self.demo
        if t == demo['DEMO_RULE']:  # a rule is a label scope
            labs.clear()
            T.alt, T.rules, T.rule_forms, T.rule_fields, T.predicted = False, T.rules + 1, 0, 0, False
        elif t == M.STAR:
            lab = next(x for x in forced if self.kind[x] == 'label')
            labs.append(Label(lab, (ANY_TYPE,), T.body, (), False, (), False, True))
            T.rule_fields += 1
        elif t == demo['ALT_FORM']:
            T.alt = True
        elif t == M.END:
            if np.isin(ids2, self.kind_ids).any():  # the form's END: the engine declared its relation
                T.where = 'done'
            else:  # the rule's END
                T.predicted = False
        else:
            sub = self.form_kinds[t]
            labs[:] = [] if T.alt else [L for L in labs if L.field]  # a label of an earlier form is made anew; a form after ALT_FORM has labels of its own alone
            fresh = Track(where='start' if sub == 'INIT' else 'group' if sub in ('RIGID_DET', 'CHOOSE') else 'body', decision=0 if sub in ('RIGID_DET', 'CHOOSE') else -1, body=T.body + 1, uid=T.uid,
                          rels=T.rels, form=T.form, sub=sub, predict=t == demo['PREDICT'], base=len(pt.tokens), rules=T.rules, rule_forms=T.rule_forms + 1,
                          rule_fields=T.rule_fields)
            for f in dataclasses.fields(Track):
                setattr(T, f.name, getattr(fresh, f.name))

    def _answer(self, T, t, labs, ids2):
        """Token t at a column that a PREDICT clause fills: a label of the clause or a field, or SKIP."""
        if self.kind[t] == 'label':
            self._read(labs, t, T, ANY_TYPE)
            T.answered = True
        self._answered(T, ids2)

    def _answered(self, T, ids2):
        """After a PREDICT body or one of its columns: the next column, else the rule's next form or its END."""
        if not ((ids2 == SKIP_TOK).any() or self.is_label[ids2].any()):
            self._to_rule(T)

    @staticmethod
    def _to_rule(T):
        T.predicted = T.predicted or T.predict
        T.where, T.sub, T.predict, T.alt, T.path, T.atom, T.negated = 'rule', '', False, False, (), (), False

    def _read(self, labs, tok, T, ty):
        for i, L in enumerate(labs):
            if L.tok == tok:
                T.uses += ((tok, len(T.firsts) - 1),)
                labs[i] = dataclasses.replace(L, reads=L.reads + ((T.body, T.path),), types=L.types if ty in L.types else L.types + (ty,))
                return

    def _close_atom(self, T, box):
        text = T.text + ')'
        if T.negated:
            text = '(NOT %s)' % text
        box[0] = box[0] + (T.atom,)
        T.texts += ((T.path, text),)
        if not T.path:
            T.top += 1
        T.atom, T.text, T.negated, T.rtok, T.need = (), '', False, None, 0

    @staticmethod
    def _close_group(labs, u, kd, b):
        """The labels after group u closes at branch (stage) b: those it did not export are hidden."""
        for i, L in enumerate(labs):
            idx = next((j for j, g in enumerate(L.path) if g[0] == u), None)
            if idx is None:
                continue
            if kd == 'ALL':
                hide = True
            elif kd == 'IF':  # the then's labels that the else names are exported (the test's and the else's are local)
                hide = not (L.path[idx][2] == 1 and any((u, 'IF', 2) in rp[1] for rp in L.reads))
            else:
                hide = not (L.path[idx][2] == 0 and all(any((u, 'OR', bb) in rp[1] for rp in L.reads) for bb in range(1, b + 1)))
            labs[i] = dataclasses.replace(L, path=L.path[:idx] + L.path[idx + 1:], hidden=L.hidden or hide)


def core_of(run):
    got = getattr(run, 'writer_core', None)
    if got is None:
        got = run.writer_core = Core(run)
    return got


def start_point(run, pg, dec, kind):
    """The first WritingPoint of a query of `kind`, at decoder `dec` after the kind token."""
    return core_of(run).start(run, pg, dec, kind)


def step_point(pt, t, cache=None):
    """The WritingPoint after id t of the mask of `pt`. With a cache (tokens -> WritingPoint), a point made before comes from it."""
    tokens = pt.tokens + (t,)
    if cache is not None:
        got = cache.get(tokens)
        if got is not None:
            return got if got.pg is pt.pg else dataclasses.replace(got, pg=pt.pg)
    core = core_of(pt.run)
    nxt = pt.dec.fork()
    forced = nxt.step(t)[0]
    ids2 = ids_of(nxt.fork().admissible())  # on a fork: a decoder keeps the mask it computes, with the state after each admitted id, and a cached point would keep that; a step from the point forks its decoder, and a fork keeps no mask
    T, labels, atoms = core.advance(pt, t, forced, ids2)
    child = dataclasses.replace(pt, dec=nxt, tokens=tokens, atoms=atoms, labels=labels, track=T, open_atom=T.atom, ids_=ids2, memo={}, back=(pt.dec, pt.back))
    child = core._with_place(child, T, atoms, labels, tokens, ids2)
    if cache is not None:
        if len(cache) >= getattr(pt.run, 'points_cap', 3000):
            cache.clear()
        cache[tokens] = child
    return child


# ---------------------------------------------------------------- features and distributions

PREFIX_FEATURES: dict[str, Callable] = {}


def prefix_feature(name, scope):
    """Registers a prefix feature. scope 'option': f(point, ids) gives one number per id. scope 'point': f(point, ids) gives one number for the point."""
    def put(f):
        f.scope = scope
        PREFIX_FEATURES[name] = f
        return f
    return put


for _name, _test in (('is_table', 'is_rel'), ('is_label', 'is_label'), ('is_column', 'is_column')):
    prefix_feature(_name, 'option')(lambda pt, ids, _t=_test: getattr(core_of(pt.run), _t)[ids].astype(np.float32))
prefix_feature('is_end', 'option')(lambda pt, ids: (ids == M.END).astype(np.float32))
prefix_feature('is_not', 'option')(lambda pt, ids: (ids == M.NOT).astype(np.float32))


@prefix_feature('atoms', 'point')
def _atoms_begun(pt, ids):
    """The items of the current body that are begun: the closed ones, and one more where an atom is open (or a NOT is waiting for its atom) or a group is open. A group closes
    at its END and an atom stays open until the next token, so the closed count alone would differ between two orders of the same set of atoms."""
    T = pt.track
    return np.float32(pt.place.atoms + (1 if T.path or T.atom or T.negated else 0))



prefix_feature('tokens', 'point')(lambda pt, ids: np.float32(len(pt.tokens) - pt.track.base))  # the tokens of the form that holds the next token: in a DEMONSTRATED query, of the rule's form
prefix_feature('labels', 'point')(lambda pt, ids: np.float32(len(pt.labels)))
prefix_feature('phase', 'point')(lambda pt, ids: np.float32(pt.place.phase.value))


# Table features: for an id that names a table of the scope, the AssignmentVector of the table's AssignmentSummaries.
TABLE_AGGS = ('min', 'mean', 'max')
_AGG = {'min': np.min, 'mean': np.mean, 'max': np.max}
_TABLE_NAMES = tuple(arclog.table_feature_names())
ASSIGNMENT_HEAD = ('count', 'capped', 'distinct', 'differ')


def assignment_vector_names():
    """The names of the AssignmentVector, in the order of assignment_vector: count, capped, distinct, differ, then <f>:min, <f>:mean and <f>:max for each TableVector feature <f>."""
    return ASSIGNMENT_HEAD + tuple('%s:%s' % (f, a) for f in _TABLE_NAMES for a in TABLE_AGGS)


def assignment_vector(items, capped):
    """The AssignmentVector of one parameterized table, as a float32 array in the order of assignment_vector_names().
    items: one (TableHash, TableVector) per assignment, at least one; a TableHash of None (no hash) counts as a hash of its own.
    capped: whether the engine's walk of the table stopped at the cap.
    count is the count of items; capped is 1 or 0; distinct is the count of distinct TableHashes divided by count; differ is 1 when there are two or more distinct TableHashes;
    then the min, mean and max over the TableVectors of each feature. The items are sorted first, so their order does not change the float32 mean."""
    if not items:
        raise ValueError('assignment_vector: no assignments')
    items = sorted(items, key=lambda it: (it[0] is None, '' if it[0] is None else str(it[0]), np.asarray(it[1], np.float32).tobytes()))
    n = len(items)
    seen = {h for h, _ in items if h is not None}
    distinct = len(seen) + sum(h is None for h, _ in items)
    m = np.stack([v for _, v in items]).astype(np.float32)
    head = np.array([n, 1 if capped else 0, distinct / n, 1 if distinct >= 2 else 0], np.float32)
    return np.concatenate([head, np.stack([_AGG[a](m, 0).astype(np.float32) for a in TABLE_AGGS], 1).reshape(-1)])


def _table_aggregates(pg):
    """{slot: AssignmentVector} for the tables of pg (see assignment_vector), from each table's AssignmentSummaries. Made once per pg.tables."""
    got = pg.__dict__.get('table_aggregates')
    tables = getattr(pg, 'tables', None) or {}
    if got is None or got[0] is not tables:
        out = {slot: assignment_vector([(r.hash, r.features) for r in rs], any(r.capped for r in rs)) for slot, rs in tables.items()}
        got = pg.table_aggregates = (tables, out)
    return got[1]


_TABLE_COL: dict[str, int] = {}  # the name of a table feature -> its column in the rows of _table_block; filled by the registrations below
_VEC_COL: list[tuple[int, int]] = []  # (column in a row, index in the AssignmentVector) for every table feature that the vector gives


def _slot_row(agg):
    """The row of an id whose table slot has `agg` (its AssignmentVector from _table_aggregates, or None where pg.tables holds no such slot): every table feature of the id, in the order of _TABLE_COL."""
    row = np.zeros(len(_TABLE_COL), np.float32)
    if agg is None:
        row[_TABLE_COL['table:missing']] = 1
    else:
        for c, k in _VEC_COL:
            row[c] = agg[k]
    return row


def _table_block(pt, ids):
    """(len(ids), len(_TABLE_COL)) float32: the table features of every id of `ids`. A row depends on the id and on pg.tables only, so it is made once per id and kept for the
    scope (in pg, with the aggregates); the block of the point's ids is kept in its memo."""
    got = pt.memo.get('table_block')
    if got is not None and got[0] is ids:
        return got[1]
    pg = pt.pg
    tables = getattr(pg, 'tables', None) or {}
    held = pg.__dict__.get('table_id_rows')
    if held is None or held[0] is not tables:
        held = pg.table_id_rows = (tables, {})
    rows = held[1]
    lst = ids.tolist()
    if any(i not in rows for i in lst):
        core = core_of(pt.run)
        aggs = _table_aggregates(pg)
        for i in lst:
            if i not in rows:
                rows[i] = _slot_row(aggs.get(int(M.slot_no(core.names[i]))) if core.kind[i] == 'relation' else None)
    block = np.stack([rows[i] for i in lst]) if lst else np.zeros((0, len(_TABLE_COL)), np.float32)
    pt.memo['table_block'] = ids, block
    return block


for _f in _TABLE_NAMES:
    for _a in TABLE_AGGS:
        _TABLE_COL['table:%s:%s' % (_f, _a)] = len(_TABLE_COL)
_TABLE_COL['table:count'] = len(_TABLE_COL)
_TABLE_COL['table:missing'] = len(_TABLE_COL)
for _h in ('capped', 'distinct', 'differ'):
    _TABLE_COL['table:' + _h] = len(_TABLE_COL)
_VEC_INDEX = {n: k for k, n in enumerate(assignment_vector_names())}
_VEC_COL.extend((c, _VEC_INDEX[n[len('table:'):]]) for n, c in _TABLE_COL.items() if n != 'table:missing')
for _name, _k in _TABLE_COL.items():
    prefix_feature(_name, 'option')(lambda pt, ids, _k=_k: _table_block(pt, ids)[:, _k])


def feature_names():
    """Every registered feature name, in registration order: the prefix features, then the table features (the min, mean and max columns, table:count, table:missing, then table:capped, table:distinct and table:differ)."""
    return tuple(PREFIX_FEATURES)


class Features:
    """The features of one writing point, made on the first call. Table features (names that start with `table:`) come from the AssignmentSummaries
    of the table that an id names, in `pg.tables`, combined over assignments as the AssignmentVector (see assignment_vector); they are 0 for an id that names no such table,
    and `table:missing` is 1 there.

    vectors() is the writing-point vector of every id (see "The writing-point vector" below), and names its column names."""

    def __init__(self, point, ids):
        self.point_, self.ids = point, ids
        pg = point.pg
        self.tables: Mapping[int, tuple] = getattr(pg, 'tables', {})
        self._vectors = None

    @property
    def body(self):
        """The AssignmentSummaries of the body table in progress at the point, or None where the engine gives none (see current_body)."""
        got = current_body(self.point_)
        return None if got is None else got.table.rows

    @property
    def names(self) -> tuple[str, ...]:
        return vector_names(self.point_.run)

    def vectors(self) -> np.ndarray:
        """(len(ids), len(names)) float32: one row for each admitted id, in the order of ids."""
        if self._vectors is None:
            self._vectors = vector_matrix(self.point_, self.ids)
        return self._vectors

    def option(self, names):
        cols = [np.asarray(PREFIX_FEATURES[n](self.point_, self.ids), np.float32).reshape(len(self.ids)) for n in names]
        return np.stack(cols, 1) if cols else np.zeros((len(self.ids), 0), np.float32)

    def point(self, names):
        return np.array([PREFIX_FEATURES[n](self.point_, self.ids) for n in names], np.float32)


# ---------------------------------------------------------------- the writing-point vector
#
# Features.vectors() gives each admitted id one row: the columns of the blocks in VECTOR_BLOCKS, in registration order. A column is named `<block>:<feature>`.
# A block that does not apply to an id has NaN in all its columns for that id. The point-scope blocks (pq, state, task, place) have one row for the point, which
# every id repeats.

TOKEN_CLASSES = ('kind', 'proposer', 'component', 'port', 'relation', 'table', 'column', 'field', 'label join', 'fresh label', 'key label', 'zero', 'operator',
                 'END', 'ALSO', 'OR', 'NOT', 'IF', 'ONE', 'other')
BASE_TABLES = ('input', 'ex_input', 'ex_output')
LIB_KINDS = ('lib relation', 'relation macro')
BODY_PHASES = (Phase.PROPOSER, Phase.ATOM_START, Phase.COLUMN)  # the phases at which a body table in progress can be read, by a probe token
ORACLE = collections.Counter()  # successor_tables and current_body: calls, ids, seconds and the reasons for undefined successors; reset by the caller


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class TableRef:
    """One parameterized table of a step_tables result (ct): its rows of ct.tables, one for each assignment, and their AssignmentSummaries (same order). The
    functions over tables (point_tables.py) read ct through `index`."""
    ct: object
    index: tuple[int, ...]
    rows: tuple


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Successor:
    """What the engine gives for the body after one token. kind is 'body' (the body table in progress), 'output' (the tables of the finished query) or '' where the
    engine gives no table (table is None; why says what happened). how is the kind that the engine's successor_tables gives the id (body, left_out, unchanged, finished, none
    or refused), empty from the oracle."""
    table: TableRef | None
    kind: str
    why: str = ''
    x: list = dataclasses.field(default_factory=list)  # the ExportTables of table.ct, once export() has read them
    c: list = dataclasses.field(default_factory=list)  # the columns of those tables (table_columns), once columns() has read them
    how: str = ''

    @property
    def defined(self):
        return self.table is not None

    def export(self):
        """[ExportTable] of the step's tables (point_tables reads this layout)."""
        if not self.x:
            self.x.append(export_tables(self.table.ct))
        return self.x[0]

    def columns(self):
        """[[(type, ident sources, frame)] for each column] for each table of export(), in its order (table_columns)."""
        if not self.c:
            self.c.append(table_columns(self.table.ct))
        return self.c[0]


class _Meta:
    """The vocabulary's classes for the vector: one per Run."""

    def __init__(self, run):
        core = core_of(run)
        V = run.V
        n = len(V)
        self.lib_ids = np.array([i for i in range(n) if core.kind[i] in LIB_KINDS], np.int64)
        self.lib_names = tuple(core.names[i] for i in self.lib_ids)
        self.lib_at = {int(i): k for k, i in enumerate(self.lib_ids)}
        self.state_ids = frozenset(i for i in range(n) if core.kind[i] == 'relation')
        self.base_at = {V.id(b): k for k, b in enumerate(BASE_TABLES) if b in core.names}
        cls = np.full(n, TOKEN_CLASSES.index('other'), np.int64)
        fixed = {SKIP_TOK: 'port', M.END: 'END', ALSO_TOK: 'ALSO', M.OR: 'OR', M.NOT: 'NOT', core.IF: 'IF', core.ONE: 'ONE', M.STAR: 'fresh label', M.CARET: 'key label', M.ZERO: 'zero'}
        by_kind = {'proposer': 'proposer', 'component': 'component', 'column': 'column', 'label': 'label join', 'relation': 'table', 'fact relation': 'table', 'lib relation': 'relation',
                   'relation macro': 'relation'}
        for i in range(n):
            c = by_kind.get(core.kind[i])
            if c is not None:
                cls[i] = TOKEN_CLASSES.index(c)
        for i in M.CMP:
            cls[i] = TOKEN_CLASSES.index('operator')
        for i in core.end_ids:  # the DEMONSTRATED form's DEMO_RULE, PREDICT and ALT_FORM are of the class of the kind tokens
            cls[i] = TOKEN_CLASSES.index('kind')
        for i, c in fixed.items():
            cls[i] = TOKEN_CLASSES.index(c)
        self.cls = cls
        self.column = np.array([k == 'column' for k in core.kind])
        self.field = TOKEN_CLASSES.index('field')


def meta_of(run):
    core = core_of(run)
    got = core.__dict__.get('vector_meta')
    if got is None:
        got = core.vector_meta = _Meta(run)
    return got


def token_classes(pt, ids):
    """The class of each id (an index of TOKEN_CLASSES). A column token is a 'field' where a record's field is due (the phases VALUE and FIELD)."""
    meta = meta_of(pt.run)
    out = meta.cls[ids]
    if pt.place.phase in (Phase.VALUE, Phase.FIELD):
        out = np.where(meta.column[ids], meta.field, out)
    return out


def point_ids(pt):
    """The ids of writing point pt that serving scores: the engine's mask with the legality rules applied (lookahead_legal.LegalMask, RULES), in the order of pt.ids_. Kept in pt.memo."""
    got = pt.memo.get('legal_ids')
    if got is None:
        import lookahead_legal
        run = pt.run
        mask = run.__dict__.get('legal_mask')
        if mask is None:
            mask = run.legal_mask = lookahead_legal.LegalMask(run)
        ids = pt.ids_
        got = pt.memo['legal_ids'] = ids[mask.factors(pt, ids) > -np.inf] if len(ids) else ids
    return got


# ---- point_tables: the functions over tables of model/study/samples/point_tables.py (Features-worker's), which the kit holds in model/study/samples/

_POINT_TABLES = []


def point_tables():
    """The module point_tables of model/study/samples/, or None where the kit has no such file. It is imported once, with that folder first on the path and with the folder's
    row_store (table_read binds one) in place of the kit's own while it loads, as build_tables.sampler_writer does."""
    if not _POINT_TABLES:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'samples')
        got = None
        if os.path.exists(os.path.join(d, 'point_tables.py')):
            own, path = sys.modules.pop('row_store', None), list(sys.path)
            sys.path.insert(0, d)
            try:
                importlib.import_module('build_tables')  # the kit's stand-in: sampler_writer() is this module
                got = importlib.import_module('point_tables')
            finally:
                sys.path[:] = path
                sys.modules.pop('row_store', None)
                if own is not None:
                    sys.modules['row_store'] = own
        _POINT_TABLES.append(got)
    return _POINT_TABLES[0]


class _AllTables:
    """The kit's M for table_export.read_export, with every table given a relation number of 0: read_export leaves out the tables of a negative relation, which the base tables
    of the first step_tables result are."""

    def __init__(self, m):
        self.m = m

    def col(self, ct, part, key):
        v = self.m.col(ct, part, key)
        return np.zeros(len(v), np.int64) if (part, key) == ('tables', 'relation') else v

    def __getattr__(self, k):
        return getattr(self.m, k)


def export_tables(ct, all_tables=False):
    """[table_export.ExportTable] of step_tables result ct (its tables of a relation number of 0 or more; with all_tables, every table), in the engine's order."""
    point_tables()
    return sys.modules['table_export'].read_export(_AllTables(M) if all_tables else M, ct)


def one_table(tabs):
    """One ExportTable for the list tabs: the table itself, or one that holds the assignments of all of them (the output tables of an INIT or RIGID_DET at its END)."""
    return tabs[0] if len(tabs) == 1 else dataclasses.replace(tabs[0], at=[a for t in tabs for a in t.at])


def table_columns(ct, all_tables=False):
    """[[(type, ident sources, frame)] for each column] for each table of export_tables(ct, all_tables), in its order: the facts of the step_tables result ct (column_types,
    column_ident_sources and column_frames of the table's first row), with the Example column left out. The Ident sources of a column are 32 hex digits each, joined by `,` for
    a record, and '' where none; a frame is 'input', 'output', a made frame, or '' where none."""
    T = ct.tables
    n = len(T['form'])
    if not n:
        return []
    rel, tnum = M.col(ct, 'tables', 'relation'), M.col(ct, 'tables', 'table')
    src = T['column_ident_sources'] if 'column_ident_sources' in T else None
    frm = T['column_frames'] if 'column_frames' in T else None
    out = {}
    for r in range(n):
        k = int(tnum[r])
        if k in out or (rel[r] < 0 and not all_tables):
            continue
        types = [str(t) for t in T['column_types'][r]]
        ids = [str(x) for x in src[r]] if src is not None else [''] * len(types)
        fr = [str(x) for x in frm[r]] if frm is not None else [''] * len(types)
        out[k] = [(t, i, f) for t, i, f in zip(types, ids, fr) if t != 'Example']
    return list(out.values())


# ---- the engine's tables for the body of a point

def _export_step(dec, tok, pg):
    """The Successor of token tok at decoder dec: a fork steps tok, and step_tables (bodies, by assignment, with rows) reads the step's tables; `before` is the Program's."""
    f = dec.fork()
    try:
        f.step(int(tok))
        ct = arclog.step_tables(f, *live.TABLES, True, pg.before, by_assignment=True, rows='cand' not in VECTOR_OFF)  # the summaries and the column facts read no rows; the cand block's export does
    except Exception as e:  # noqa: BLE001 - a refused step or an unreadable result is an undefined successor
        return Successor(None, '', type(e).__name__)
    T = ct.tables
    if not len(T['form']):
        return Successor(None, '', 'no table')
    if any(T['fault']):
        return Successor(None, '', 'fault')
    rows = tuple(AS.assignment_summaries(ct, pg.queries))
    return Successor(TableRef(ct, tuple(range(len(rows))), rows), 'body' if all(r.table is None for r in rows) else 'output')


SUCCESSOR = os.environ.get('WRITER_SUCCESSOR') or ('engine' if hasattr(arclog, 'successor_tables') else 'oracle')  # where successor_tables gets its tables: 'engine' or 'oracle'
ENGINE_KINDS = {'body': 'body', 'left_out': 'body', 'unchanged': 'body', 'finished': 'output'}  # the engine's kinds that give a table, and the Successor kind of each


def _engine_successor(pg, kind, ct, refs):
    """The Successor of one result of the engine's call. refs: {id(ct): (TableRef or why it has none, the Successor's x list, its c list)} of the call: the ids that share a CaseTables
    (read-only) share its TableRef and its reads (export_tables, table_columns), whatever their kinds."""
    if kind not in ENGINE_KINDS:  # none, refused
        return Successor(None, '', kind, how=kind)
    got = refs.get(id(ct))
    if got is None:
        T = ct.tables
        if not len(T['form']):
            ref = 'no table'
        elif any(T['fault']):
            ref = 'fault'
        else:
            rows = tuple(AS.assignment_summaries(ct, pg.queries))
            ref = TableRef(ct, tuple(range(len(rows))), rows)
        got = refs[id(ct)] = ref, [], []
    if isinstance(got[0], str):
        return Successor(None, '', got[0], how=kind)
    return Successor(got[0], ENGINE_KINDS[kind], x=got[1], c=got[2], how=kind)


def _engine_successors(point, lst):
    """[Successor] for the ids lst, from one arclog.successor_tables call. The ids that share a CaseTables (the unchanged ones) share one Successor."""
    pg = point.pg
    _, results = arclog.successor_tables(point.dec, lst, *live.TABLES, before=pg.before, rows=True)
    made, refs, out = {}, {}, []
    for kind, _, ct in results:
        key = kind, id(ct)
        s = made.get(key)
        if s is None:
            s = made[key] = _engine_successor(pg, kind, ct, refs)
        out.append(s)
    return out


def successor_tables(point, ids, source=None):
    """[Successor] for the ids of `ids`, in order: the body after each id. source 'engine' (default SUCCESSOR) is one arclog.successor_tables call for the ids not yet kept; 'oracle'
    is one forked step and one step_tables for each id. Every function that needs a successor body table calls this one. The kinds body, left_out and unchanged give a Successor of
    kind 'body' (an unchanged id has the body table of current_body), finished one of kind 'output' (the finished query's output tables); none and refused give an undefined one.
    Kept on the point, for each id, until drop_successors."""
    source = source or SUCCESSOR
    memo = point.memo.setdefault('succ' if source == 'engine' else 'succ_oracle', {})
    lst = ids.tolist()
    todo = [i for i in dict.fromkeys(lst) if i not in memo]
    t0 = time.perf_counter()
    if todo:
        got = _engine_successors(point, todo) if source == 'engine' else [_export_step(point.dec, i, point.pg) for i in todo]
        for i, s in zip(todo, got):
            memo[i] = s
            if not s.defined:
                ORACLE['undefined: ' + s.why] += 1
    ORACLE['successor ids'] += len(todo)
    ORACLE['successor seconds'] += time.perf_counter() - t0
    return [memo[i] for i in lst]


def drop_successors(pt):
    """Drops the Successors kept on point pt: each holds its step_tables result, rows included, so a path of points would keep one for every id."""
    pt.memo.pop('succ', None)
    pt.memo.pop('succ_oracle', None)


def current_body(point):
    """The Successor (kind 'body') for the body table in progress at the point, or None. The table is the one the engine gives after a probe token (live.LiveFrontier.probe: a token
    that starts a next atom, which closes the open atom), as Run.table reads it, so it exists at an atom start or with an open atom (the phases in BODY_PHASES) and where the
    engine can evaluate the open atom. Kept in point.memo['body_ref'], and its AssignmentSummaries in point.memo['body']."""
    memo = point.memo
    if 'body_ref' in memo:
        return memo['body_ref']
    ref = None
    t0 = time.perf_counter()
    if point.track.where == 'body' and point.place.phase in BODY_PHASES:
        p = point.run.ff0.probe(point.dec.fork())
        if p is not None:
            got = _export_step(point.dec, p, point.pg)
            ref = got if got.defined else None
    ORACLE['body seconds'] += time.perf_counter() - t0
    ORACLE['body points'] += 1
    memo['body_ref'], memo['body'] = ref, None if ref is None else ref.table.rows
    return ref


def base_tables(run):
    """{name: TableRef} of the base tables, once for a Run: from arclog.base_tables (input, ex_input and ex_output), else from the program's first step_tables result (no input)."""
    got = run.__dict__.get('vector_base')
    if got is None:
        if hasattr(arclog, 'base_tables'):
            ct = arclog.base_tables(run.root, *live.TABLES, rows=True)
        else:
            pg0 = live.Program()
            run.open_form(pg0, run.root, 'RULE')
            ct = pg0.before
        rows = AS.assignment_summaries(ct)
        by = collections.defaultdict(list)
        for k, r in enumerate(rows):
            by[r.table].append(k)
        got = run.vector_base = ({n: TableRef(ct, tuple(ix), tuple(rows[k] for k in ix)) for n, ix in by.items() if isinstance(n, str)}, ct)
    return got[0]


def base_export(run):
    """{name: ExportTable} of the base tables, for point_tables' `base`, once for a Run. Without arclog.base_tables the base tables are the first step_tables result's, which has
    no `input` table: then `input` is ex_input, which is the same train inputs with the Example column that point_tables drops."""
    got = run.__dict__.get('vector_base_x')
    if got is None:
        base_tables(run)
        got = {t.name: t for t in export_tables(run.vector_base[1], True)}
        if 'input' not in got and 'ex_input' in got:
            got['input'] = got['ex_input']
            ORACLE['base: input is ex_input'] += 1
        run.vector_base_x = got
    return got


def base_context(run):
    """point_tables' `base` for a Run: point_tables.base_context of base_export(run), made once for the Run; base_export(run) itself where point_tables has no base_context."""
    got = run.__dict__.get('vector_base_ctx')
    if got is None:
        PT = point_tables()
        got = run.vector_base_ctx = PT.base_context(base_export(run)) if hasattr(PT, 'base_context') else base_export(run)
    return got


def keep_state_tables(run):
    """Makes the Run keep each closed query's step_tables result (live.Run.keep_closed), which the state block reads; drops the scopes that it made before."""
    if not run.keep_closed:
        run.keep_closed = True
        run.scoped = None
        run.kept.clear()


def state_tables(run, pg):
    """([ExportTable], [kind]) of the parameterized tables of the state of pg, one kind for each table, or None where pg did not keep its queries' results (keep_state_tables)."""
    if len(pg.closed) != len(pg.kinds):
        return None
    cache = run.__dict__.setdefault('vector_closed', {})
    if len(cache) > 256:
        cache.clear()
    tabs, kinds = [], []
    for ct, kind in zip(pg.closed, pg.kinds):
        got = cache.get(id(ct))
        if got is None or got[0] is not ct:
            got = cache[id(ct)] = ct, export_tables(ct)
        tabs += got[1]
        kinds += [kind] * len(got[1])
    return tabs, kinds


def state_columns(run, pg):
    """{slot: [(type, ident sources, frame)]}: the columns of the tables of the state's parameterized tables (state_tables) by relation slot, or None where pg did not keep its
    queries' results."""
    if state_tables(run, pg) is None:
        return None
    cache = run.__dict__.setdefault('vector_closed_cols', {})
    if len(cache) > 256:
        cache.clear()
    out = {}
    for ct in pg.closed:
        got = cache.get(id(ct))
        if got is None or got[0] is not ct:
            tabs, cols = run.vector_closed[id(ct)][1], table_columns(ct)
            if len(tabs) != len(cols):
                raise ValueError('state_columns: %d tables and %d column lists' % (len(tabs), len(cols)))
            got = cache[id(ct)] = ct, [(t.slot, c) for t, c in zip(tabs, cols)]
        for slot, c in got[1]:
            out.setdefault(slot, []).extend(c)
    return out


def base_columns(run):
    """{name: [(type, ident sources, frame)]} of the base tables, once for a Run."""
    got = run.__dict__.get('vector_base_cols')
    if got is None:
        base_tables(run)
        tabs, cols = export_tables(run.vector_base[1], True), table_columns(run.vector_base[1], True)
        got = run.vector_base_cols = {t.name: c for t, c in zip(tabs, cols)}
    return got


# ---- the blocks

@dataclasses.dataclass(frozen=True, slots=True)
class VectorBlock:
    name: str
    scope: str  # 'option': value(point, ids) is (len(ids), k); 'point': (k,)
    names: Callable  # run -> the block's column names, each `<block>:<feature>`
    value: Callable


VECTOR_BLOCKS: dict[str, VectorBlock] = {}
VECTOR_OFF = frozenset(x for x in os.environ.get('WRITER_VECTOR_OFF', 'cand').split(',') if x)  # the blocks that the vector leaves out, by name; cand by default, for its memory (an empty value keeps every block)


def vector_block(name, scope, names):
    def put(f):
        if name not in VECTOR_OFF:
            VECTOR_BLOCKS[name] = VectorBlock(name, scope, names, f)
        return f
    return put


def _nan(*shape):
    return np.full(shape, np.nan, np.float32)


AV_NAMES = assignment_vector_names()
TV_NAMES = tuple(arclog.table_feature_names())


def _av_of(rows):
    """The AssignmentVector of the AssignmentSummaries `rows` of one parameterized table, or all NaN for no rows."""
    if not rows:
        return _nan(len(AV_NAMES))
    return assignment_vector([(r.hash, r.features) for r in rows], any(r.capped for r in rows))


def _prefixed(block, *parts):
    return tuple(':'.join((block,) + p) for p in parts)


# token: the token's class (an index of TOKEN_CLASSES) and its vocabulary id.
TOKEN_ID_NO_TABLE = os.environ.get('WRITER_TOKEN_ID_NO_TABLE') == '1'  # token:id reads 0 for a token that names a table of the state: its id is a place in the scope's order, which no read of a DAG holds


TRAINED_RELATIONS = 512  # the relation slots of the vocabulary that a training row's token ids count in: a session's default


def trained_ids(core, ids):
    """Token ids as a training row counts them. A session with more relation slots than TRAINED_RELATIONS, as a worker's is, puts every token after the slots further on, and a model that reads a token's id would read those tokens as others."""
    shift = core.__dict__.get('trained_shift')
    if shift is None:
        first = core.names.index('&r0')
        after = next(i for i in range(first, len(core.names)) if not core.names[i].startswith('&r'))
        shift = core.trained_shift = (after, max(0, after - first - TRAINED_RELATIONS))
    ids = np.asarray(ids)
    return np.where(ids >= shift[0], ids - shift[1], ids)


@vector_block('token', 'option', lambda run: ('token:class', 'token:id'))
def _block_token(pt, ids):
    named = trained_ids(core_of(pt.run), ids)
    if TOKEN_ID_NO_TABLE:
        graph = pt.pg.__dict__.get('tok_graph') or {}
        named = np.array([0 if i in graph else j for i, j in zip(ids.tolist(), named.tolist())], ids.dtype)
    return np.stack([token_classes(pt, ids), named], 1).astype(np.float32)


# tok: the AssignmentVector of the table that a token names, over the tables of every query of the state; 0 for a token that names none, as a fit's rows read it.
@vector_block('tok', 'option', lambda run: tuple('tok:' + n for n in AV_NAMES))
def _block_tok(pt, ids):
    pg, core = pt.pg, core_of(pt.run)
    rows = pg.__dict__.get('tok_rows') or {}
    memo = pt.run.__dict__.setdefault('tok_vectors', {})
    if len(memo) > 20000:
        memo.clear()
    out = np.zeros((len(ids), len(AV_NAMES)), np.float32)
    for k, i in enumerate(ids.tolist()):
        if core.kind[i] == 'relation':
            rs = rows.get(int(M.slot_no(core.names[i])))
            if rs:
                got = memo.get(id(rs))
                if got is None or got[0] is not rs:
                    got = memo[id(rs)] = rs, _av_of(rs)
                out[k] = got[1]
    return out


# tokg: a table token's place in the read graph of the state and against the atoms of the query so far; 0 for a token that names none.
TOKG_NAMES = ('table', 'read_by', 'unread', 'form_read_by', 'depth', 'ancestors', 'kind', 'port', 'used', 'form_used', 'ancestor_of_used', 'descendant_of_used', 'shares_ancestor', 'unused_reads')
_TOKG_AT = {n: i for i, n in enumerate(TOKG_NAMES)}


@vector_block('tokg', 'option', lambda run: tuple('tokg:' + n for n in TOKG_NAMES))
def _block_tokg(pt, ids):
    pg = pt.pg
    graph, readers = pg.__dict__.get('tok_graph') or {}, pg.__dict__.get('tok_readers') or {}
    out = np.zeros((len(ids), len(TOKG_NAMES)), np.float32)
    if not graph:
        return out
    held = pg.__dict__.get('tok_form_readers')
    if held is None or held[0] is not graph:
        counts = collections.Counter()
        for t, n in readers.items():
            counts[graph[t][0]] += n
        held = pg.tok_form_readers = graph, counts
    form_readers = held[1]
    atoms = pt.track.past_atoms + pt.atoms
    used = collections.Counter()
    for a in atoms:
        r = a[1] if a[0] == M.NOT and len(a) > 1 else a[0]
        if r in graph:
            used[r] += 1
    used_places, used_above = {graph[r][0] for r in used}, set()
    for r in used:
        used_above |= graph[r][2]
    for k, i in enumerate(ids.tolist()):
        got = graph.get(i)
        if got is None:
            continue
        place, depth, above, code, port = got
        read = readers.get(i, 0)
        row = out[k]
        row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7] = 1, read, read == 0, form_readers.get(place, 0), depth, len(above), code, port
        row[8], row[9], row[10], row[11], row[12] = used.get(i, 0), place in used_places, place in used_above, bool(above & used_places), bool(above & used_above or above & used_places)
        row[13] = len(above) - len(above & used_above)
    return out


# ctx: where the writer stands in the query, beyond place: the open atom's relation and its columns so far, the token before, the INIT's component and the labels at hand. tokc: what each token is against that:
# a column token's type in the open atom, a relation token's columns against the labels' types, a label token's reads. They read the query's canonical path and the decoder's types, and no table.
_TYPES = ('Position', 'Color', 'Ident', 'Number', 'Nat', 'Int', 'Box', 'Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'Offset', 'D4', 'C4', 'Sense', 'Sym', 'Pose', 'Example', 'Bool')
_TYPE_AT = {t: i + 1 for i, t in enumerate(_TYPES)}
_KIND_AT = {k: i + 1 for i, k in enumerate(('relation', 'column', 'label', 'proposer', 'lib relation', 'relation macro', 'control', 'component', 'fact relation'))}
_LABEL_TYPES = ('Position', 'Color', 'Ident', 'Number', 'Box', 'Dir')
CTX_NAMES = ('open_rel', 'open_table', 'open_taken', 'open_arity', 'last_tok', 'last_kind', 'component', 'decision', 'inkey', 'round', 'labels', 'labels_unread') + tuple('labels_' + t for t in _LABEL_TYPES) + ('col', 'col_type', 'col_labels')
TOKC_NAMES = ('col_type', 'col_labels', 'rel_arity', 'rel_match', 'rel_new', 'label_reads', 'label_type', 'label_rank', 'rel_used')


def _rel_types(pt, core, tok):
    """The types of the columns of relation token tok, with no parameters."""
    if core.kind[tok] == 'relation':
        ts = pt.pg.decl_types.get(M.slot_no(core.names[tok]))
    else:
        ts = core.regtypes.get(core.names[tok])
    return tuple(str(t).split('(')[0] for t in ts) if ts else ()


def _column_type(pt, core, rtok, pos, ids=None):
    """The type of column token position pos of relation token rtok at point pt, with no parameters, '' where unknown. A table's read in a RULE leaves out the Example column that its read in a DET or an INIT has first, so a position there is one past its place in the RULE's columns, where the table has that column; the first column point of an atom shows which, by the count of columns it admits."""
    if pos is None:
        return ''
    if core.kind[rtok] != 'relation':
        ts = core.regtypes.get(core.names[rtok])
        return str(ts[pos]).split('(')[0] if ts and 0 <= pos < len(ts) else ''
    slot = M.slot_no(core.names[rtok])
    rule = pt.pg.colmaps['RULE'].get(slot, {})
    if pt.kind == 'RULE':
        t = rule.get((pos, None))
    else:
        memo = pt.pg.__dict__.setdefault('col_offset', {})
        key = (pt.kind, slot)
        if key not in memo and not any(core.is_column[x] for x in pt.open_atom):
            admitted = sum(core.kind[x] == 'column' for x in pt.ids_.tolist())
            memo[key] = 1 if admitted == sum(f is None for _, f in rule) + 1 else 0
        offset = memo.get(key, 1)
        t = 'Example' if pos < offset else rule.get((pos - offset, None))
    return '' if t is None else str(t).split('(')[0]


def _labels_at(pt):
    """(the usable labels, {type: their count}), kept on the point. A label's type is the type of the site that made it."""
    got = pt.memo.get('ctx_labels')
    if got is None:
        use = pt.labels.usable(pt)
        items = [L for L in pt.labels.items if L.tok in use]
        counts = collections.Counter(str(L.types[0]).split('(')[0] for L in items if L.types)
        got = pt.memo['ctx_labels'] = items, counts
    return got


@vector_block('ctx', 'point', lambda run: tuple('ctx:' + n for n in CTX_NAMES))
def _block_ctx(pt, ids):
    core, T = core_of(pt.run), pt.track
    out = np.zeros(len(CTX_NAMES), np.float32)
    rtok = T.rtok if pt.open_atom else None
    if rtok is not None:
        table = core.kind[rtok] == 'relation'
        out[0], out[1] = -1 if table else rtok, table
        out[2] = sum(bool(core.is_column[t]) for t in pt.open_atom)
        out[3] = len(_rel_types(pt, core, rtok))
    last = pt.tokens[-1]
    out[4], out[5] = -1 if core.kind[last] == 'relation' else trained_ids(core, last), _KIND_AT.get(core.kind[last], 0)
    if pt.kind == 'INIT' and len(pt.tokens) > 1 and core.kind[pt.tokens[1]] == 'component':
        out[6] = pt.tokens[1]
    out[7], out[8], out[9] = T.decision, T.inkey, T.round
    items, counts = _labels_at(pt)
    out[10], out[11] = len(items), sum(not L.reads for L in items)
    for k, t in enumerate(_LABEL_TYPES):
        out[12 + k] = counts.get(t, 0)
    if rtok is not None and T.col is not None:
        t = _column_type(pt, core, rtok, T.col)
        out[18], out[19], out[20] = T.col + 1, _TYPE_AT.get(t, 0), counts.get(t, 0)
    return out


@vector_block('tokc', 'option', lambda run: tuple('tokc:' + n for n in TOKC_NAMES))
def _block_tokc(pt, ids):
    core, T = core_of(pt.run), pt.track
    out = np.zeros((len(ids), len(TOKC_NAMES)), np.float32)
    items, counts = _labels_at(pt)
    rtok = T.rtok if pt.open_atom else None
    rank = {L.tok: (len(items) - k, L) for k, L in enumerate(items)}
    used = collections.Counter(a[1] if a[0] == M.NOT and len(a) > 1 else a[0] for a in pt.track.past_atoms + pt.atoms)
    for k, i in enumerate(ids.tolist()):
        kind = core.kind[i]
        if kind == 'column':
            if rtok is not None:
                t = _column_type(pt, core, rtok, core.colpos.get(i))
                out[k, 0], out[k, 1] = _TYPE_AT.get(t, 0), counts.get(t, 0)
        elif kind in ('relation', 'lib relation', 'relation macro', 'fact relation'):
            ts = _rel_types(pt, core, i)
            match = sum(counts.get(t, 0) > 0 for t in ts)
            out[k, 2], out[k, 3], out[k, 4] = len(ts), match, len(ts) - match
            out[k, 8] = used.get(i, 0)
        elif kind == 'label':
            got = rank.get(i)
            if got is not None:
                out[k, 5], out[k, 6], out[k, 7] = len(got[1].reads), _TYPE_AT.get(str(got[1].types[0]).split('(')[0] if got[1].types else '', 0), got[0]
    return out


# tokm: a relation token's columns by type, and a table token's columns against the current body's and against the tables that the query's atoms name: how many share a type with its Ident sources, an Ident source and a frame (writer.match_vector). NaN where there is no body or no named table; 0 for a token that names no relation.
_TOKM_TYPES = (('position', ('Position',)), ('color', ('Color',)), ('ident', ('Ident',)), ('number', ('Number', 'Nat', 'Int')), ('box', ('Box',)), ('dir', ('Dir', 'Dir8', 'DiagDir')))
_TOKM_AT = {t: i for i, (_, ts) in enumerate(_TOKM_TYPES) for t in ts}
TOKM_NAMES = tuple('n_' + n for n, _ in _TOKM_TYPES) + ('n_other', 'body_type', 'body_ident', 'body_frame', 'used_type', 'used_ident', 'used_frame', 'none')


@vector_block('tokm', 'option', lambda run: tuple('tokm:' + n for n in TOKM_NAMES))
def _block_tokm(pt, ids):
    core = core_of(pt.run)
    out = np.zeros((len(ids), len(TOKM_NAMES)), np.float32)
    columns, targets = None, None
    for k, i in enumerate(ids.tolist()):
        kind = core.kind[i]
        if kind not in ('relation', 'lib relation', 'relation macro', 'fact relation'):
            continue
        for t in _rel_types(pt, core, i):
            out[k, _TOKM_AT.get(t, 6)] += 1
        if kind == 'relation':
            if columns is None:
                columns = state_columns(pt.run, pt.pg) or {}
                targets = _match_targets(pt, current_body(pt))
            cols = columns.get(int(M.slot_no(core.names[i])))
            if cols:
                out[k, 7:] = match_vector(cols, *targets)
    return out


# cand: for each id, whether the engine gives the body after it, then point_tables.successor_vector of that successor body table (NaN where the engine gives none),
# point_tables.body_delta from the current body table to it (at END: from nothing to the query's output tables; NaN too where there is no current body), and its matches.
# The matches (match_vector) count the columns of the successor table that share a type, an Ident source or a frame with a column of the current body table (match:body:*) and
# with a column of the tables that the atoms of the query so far name (match:used:*), and the columns with no match (match:none).
MATCH_KINDS = ('type', 'ident', 'frame')
MATCH_NAMES = tuple('match:%s:%s' % (t, k) for t in ('body', 'used') for k in MATCH_KINDS) + ('match:none',)


def _cand_names(run):
    PT = point_tables()
    return ('cand:defined',) + tuple('cand:' + n for n in (PT.successor_names() if PT else AV_NAMES)) + (tuple('cand:' + n for n in tuple(PT.delta_names()) + MATCH_NAMES) if PT else ())


def match_target(cols):
    """What the columns `cols` ([(type, ident sources, frame)]) offer a column to match: the (type, ident sources) pairs, the Ident sources, the frames. Two columns have the same
    type when the type and the Ident sources are equal; they share an Ident source when one of the sources is in both; they share a frame when it is equal and not empty."""
    return {(t, s) for t, s, _ in cols}, {x for _, s, _ in cols for x in s.split(',') if x}, {f for _, _, f in cols if f}


def match_vector(cols, body, used):
    """The values of MATCH_NAMES for the columns `cols` of a successor table, against the match_target of the current body table and the one of the used tables (None where there is
    none: its columns are NaN). match:none counts the columns that match in no target given; NaN where neither is given."""
    out = np.full(len(MATCH_NAMES), np.nan, np.float32)
    counts, none = np.zeros((2, len(MATCH_KINDS)), np.float32), 0
    for t, s, f in cols:
        srcs = [x for x in s.split(',') if x]
        hit = False
        for k, tg in enumerate((body, used)):
            if tg is not None:
                m = np.array([(t, s) in tg[0], any(x in tg[1] for x in srcs), bool(f) and f in tg[2]])
                counts[k] += m
                hit = hit or bool(m.any())
        none += not hit
    for k, tg in enumerate((body, used)):
        if tg is not None:
            out[k * len(MATCH_KINDS):(k + 1) * len(MATCH_KINDS)] = counts[k]
    if body is not None or used is not None:
        out[-1] = none
    return out


def used_columns(pt):
    """[(type, ident sources, frame)] of the tables that the atoms of the query so far name: the base tables, and the parameterized tables of the state (the closed atoms of earlier
    bodies and of this one, and the open atom). None where an atom names a state table and the Program kept none of its queries' results. Kept in pt.memo."""
    if 'used_columns' in pt.memo:
        return pt.memo['used_columns']
    meta, core = meta_of(pt.run), core_of(pt.run)
    names, slots = set(), set()
    for a in pt.track.past_atoms + pt.atoms + ((pt.open_atom,) if pt.open_atom else ()):
        r = a[1] if a[0] == M.NOT and len(a) > 1 else a[0]
        if r in meta.base_at:
            names.add(BASE_TABLES[meta.base_at[r]])
        elif r in meta.state_ids:
            slots.add(int(M.slot_no(core.names[r])))
    cols, base = [], base_columns(pt.run)
    for b in BASE_TABLES:
        if b in names:
            cols += base.get(b, [])
    if slots:
        got = state_columns(pt.run, pt.pg)
        if got is None:
            cols = None
        else:
            for s in sorted(slots):
                cols += got.get(s, [])
    pt.memo['used_columns'] = cols
    return cols


def _match_targets(pt, cur):
    """(match_target of the current body table Successor `cur` or None, match_target of the used tables or None)."""
    body = used = None
    try:
        if cur is not None:
            body = match_target([c for t in cur.columns() for c in t])
        got = used_columns(pt)
        used = None if got is None else match_target(got)
    except Exception as e:  # noqa: BLE001
        ORACLE['match targets error: ' + type(e).__name__] += 1
    return body, used


@vector_block('cand', 'option', _cand_names)
def _block_cand(pt, ids):
    PT = point_tables()
    ns, nd = (len(PT.successor_names()), len(PT.delta_names())) if PT else (len(AV_NAMES), 0)
    nm = len(MATCH_NAMES) if PT else 0
    out = _nan(len(ids), 1 + ns + nd + nm)
    succ = successor_tables(pt, ids)
    curx = base = body_t = used_t = None
    if PT:
        base = base_context(pt.run)
        cur = current_body(pt)
        curx = None if cur is None else one_table(cur.export())
        body_t, used_t = _match_targets(pt, cur)
    first = {}  # (id of the CaseTables, kind) -> the row of its first id: ids that share a CaseTables (read-only) have one row
    for j, s in enumerate(succ):
        if not s.defined:
            out[j, 0] = 0
            continue
        key = id(s.table.ct), s.kind
        if key in first:
            out[j] = out[first[key]]
            continue
        first[key] = j
        out[j, 0] = 1
        if not PT:
            out[j, 1:1 + ns] = _av_of(s.table.rows)
            continue
        try:
            xs = s.export()
            one = one_table(xs)
            out[j, 1:1 + ns] = PT.successor_vector(one)
        except Exception as e:  # noqa: BLE001
            ORACLE['export error: ' + type(e).__name__] += 1
            out[j, 0] = 0
            out[j, 1:] = np.nan
            continue
        try:
            out[j, 1 + ns + nd:] = match_vector([c for t in s.columns() for c in t], body_t, used_t)
        except Exception as e:  # noqa: BLE001
            ORACLE['match error: ' + type(e).__name__] += 1
        if s.kind == 'output':
            args = (None, xs)
        elif curx is not None:
            args = (curx, one)
        else:
            continue
        try:
            out[j, 1 + ns:1 + ns + nd] = PT.body_delta(*args, base)
        except Exception as e:  # noqa: BLE001
            ORACLE['delta error: ' + type(e).__name__] += 1
    return out


# pq: the closed atoms of the query as a set (of every body of an INIT or RIGID_DET written so far) (a count for each lib relation, for the atoms over state tables, over each base table, for comparisons, for negated atoms, and
# all of them), then the AssignmentVector of the body table in progress (NaN where the engine gives none).
def _pq_names(run):
    meta = meta_of(run)
    return (tuple('pq:lib:' + n for n in meta.lib_names) + ('pq:tables',) + tuple('pq:base:' + b for b in BASE_TABLES) + ('pq:compare', 'pq:negated', 'pq:atoms')
            + tuple('pq:body:' + n for n in AV_NAMES))


@vector_block('pq', 'point', _pq_names)
def _block_pq(pt, ids):
    meta = meta_of(pt.run)
    lib, base = np.zeros(len(meta.lib_ids), np.float32), np.zeros(len(BASE_TABLES), np.float32)
    tables = compare = 0
    atoms = pt.track.past_atoms + pt.atoms  # every body of the query so far
    for a in atoms:
        r = a[1] if a[0] == M.NOT and len(a) > 1 else a[0]
        if r in meta.lib_at:
            lib[meta.lib_at[r]] += 1
        elif r in meta.state_ids:
            tables += 1
        elif r in meta.base_at:
            base[meta.base_at[r]] += 1
        elif r in M.CMP:
            compare += 1
    negated = sum(1 for _, text in pt.track.past_texts + pt.track.texts if text.startswith('(NOT '))
    cur = current_body(pt)
    return np.concatenate([lib, np.array([tables], np.float32), base, np.array([compare, negated, len(atoms)], np.float32),
                           _av_of(None if cur is None else cur.table.rows)])


# state: point_tables.state_vector over the parameterized tables of the state (the outputs of the queries closed so far, with the kind of each query). NaN where the Program
# did not keep its queries' step_tables results (keep_state_tables); base is the base tables ({name: ExportTable}).
def _state_names(run):
    PT = point_tables()
    return tuple(PT.state_names()) if PT else ()


@vector_block('state', 'point', _state_names)
def _block_state(pt, ids):
    PT = point_tables()
    pg = pt.pg
    memo = pt.run.__dict__.setdefault('state_vectors', {})  # id(pg.closed) -> (pg.closed, its vector): the state changes only when a query closes, and each try forks the Program, so the Run keeps them
    held = memo.get(id(pg.closed))
    if held is not None and held[0] is pg.closed:
        return held[1]
    got = state_tables(pt.run, pg)
    if got is None:
        ORACLE['state: queries not kept'] += 1
        return _nan(len(PT.state_names()))
    v = PT.state_vector(got[0], base_context(pt.run), got[1])
    if len(memo) >= 64:
        memo.clear()
    memo[id(pg.closed)] = pg.closed, v
    return v


# task: the TableVectors of the base tables; NaN for a base table that the first step_tables result lacks (it has ex_input and ex_output).
@vector_block('task', 'point', lambda run: tuple('task:%s:%s' % (b, f) for b in BASE_TABLES for f in TV_NAMES))
def _block_task(pt, ids):
    base = base_tables(pt.run)
    return np.concatenate([base[b].rows[0].features.astype(np.float32) if b in base else _nan(len(TV_NAMES)) for b in BASE_TABLES])


# place: the phase (an index of Phase), the port (-1 outside a port), the branch depth, whether the open atom is negated, and the closed atoms of the body.
@vector_block('place', 'point', lambda run: _prefixed('place', ('phase',), ('port',), ('branch',), ('negated',), ('atoms',)))
def _block_place(pt, ids):
    p = pt.place
    return np.array([p.phase.value, -1 if p.port is None else p.port, len(p.branch), float(p.negated), p.atoms], np.float32)


def vector_names(run):
    """The column names of the writing-point vector, in column order. Fixed for one vocabulary and one set of hooks; kept on the Run."""
    return _names_by_block(run)[0]


def _names_by_block(run):
    """(all names, {block name: its names}), kept on the Run."""
    core = core_of(run)
    got = core.__dict__.get('vector_names')
    if got is None:
        by = {b.name: tuple(b.names(run)) for b in VECTOR_BLOCKS.values()}
        got = core.vector_names = (tuple(n for v in by.values() for n in v), by)
    return got


def vector_matrix(pt, ids):
    """(len(ids), len(vector_names(pt.run))) float32: the vector of each id at writing point pt. A block with no column adds none."""
    parts = []
    by = _names_by_block(pt.run)[1]
    for b in VECTOR_BLOCKS.values():
        k = len(by[b.name])
        if not k:
            continue
        if b.scope == 'point':
            v = pt.memo.get(('vector', b.name))
            if v is None:
                v = pt.memo[('vector', b.name)] = np.asarray(b.value(pt, ids), np.float32).reshape(k)
            parts.append(np.broadcast_to(v, (len(ids), k)))
        else:
            parts.append(np.asarray(b.value(pt, ids), np.float32).reshape(len(ids), k))
    drop_successors(pt)
    return np.concatenate(parts, 1) if parts else np.zeros((len(ids), 0), np.float32)


class Uniform:
    """The baseline distribution: every id that is left has the same chance."""
    name, version, uses = 'uniform', '1', ()

    def logits(self, point, ids, x):
        return np.zeros(len(ids))


class OrBits:
    """Bits off the search bound of the OR token: a path that takes an OR costs more CPU, so its queries come after plain ones of about the same chance."""

    def __init__(self, bits):
        self.b = bits

    def bits(self, point, ids):
        return np.where(ids == M.OR, self.b, 0.0)


def check_plan(plan, run):
    """Raises KeyError for a feature name of the distribution that no registry holds. The names of a distribution that reads the writing-point vector
    (a true `vector`) are its column names (vector_names)."""
    names = set(vector_names(run)) if getattr(plan.distribution, 'vector', False) else PREFIX_FEATURES
    for n in plan.distribution.uses:
        if n not in names:
            raise KeyError('no feature %r' % n)
    return plan


def default_plan(run, or_bits, lookahead=None, distribution=None):
    """The plan of a deployed job: every lookahead component, the Uniform distribution and the OR cost. lookahead names the components to use, in order; the rules of the writer
    plan (lookahead_legal.PLAN_RULES) follow them where no component holds them."""
    import lookahead as L
    import lookahead_legal
    comps = lookahead_legal.with_plan_rules(run, L.components(run, lookahead))
    if getattr(distribution, 'vector', False):  # its rows were made with the state block, so the Run keeps what that block reads
        keep_state_tables(run)
    return check_plan(Plan(tuple(comps), distribution or Uniform(), OrBits(or_bits) if or_bits else None, Limits(model_tokens=run.lim.max_atoms * 12 + 64,
                                                                                                         max_atoms=run.lim.max_atoms, port_atoms=run.lim.port_atoms,
                                                                                                         branch_atoms=run.lim.branch_atoms)), run)


# ---------------------------------------------------------------- the loop

def options(pt, plan):
    """(ids, factors, reason): the ids that the lookahead components of plan leave at writing point pt, with their summed factors, else reason that none is left.
    Kept on the point."""
    key = ('options', id(plan))
    got = pt.memo.get(key)
    if got is not None:
        return got
    ids = pt.ids_
    lim, T = plan.limits, pt.track
    cap = None  # the name of the cap that the point is at: 'cap:tokens', 'cap:branch' (branch_atoms), 'cap:port' (port_atoms), 'cap:body' (max_atoms), 'cap:stuck' (port_absent) or 'cap:demo' (_demo_caps)
    if len(pt.tokens) - T.base >= lim.model_tokens or len(pt.tokens) >= lim.model_tokens * DEMO_TOKEN_FACTOR:
        cap = 'cap:tokens'
    elif lim.port_absent and T.absent >= lim.port_absent and pt.kind in PORT_KINDS:  # END was absent after port_absent top-level atoms in a row: the head is taken as one that cannot be filled, and the path ends
        ids, cap = ids[:0], 'cap:stuck'
    elif T.where == 'body' and not T.negated:  # at a cap no atom starts: an open atom goes on with its values and closes, else only the tokens that close are left
        if T.path and T.path[-1][1] == 'OR':
            n, limit, closing, name = sum(1 for p, _ in T.texts if p == T.path) + bool(T.atom), lim.branch_atoms, (M.END, ALSO_TOK), 'cap:branch'
        elif not T.path:
            n, limit, closing = T.top + bool(T.atom), (lim.port_atoms if pt.kind in PORT_KINDS else lim.max_atoms), (M.END,)
            name = 'cap:port' if pt.kind in PORT_KINDS else 'cap:body'
        else:
            n = limit = name = closing = None
        if n is not None and n >= limit and (not T.atom or pt.place.phase == Phase.COLUMN):  # not inside an atom that a value or an operand is due in
            core = core_of(pt.run)
            if not T.atom or (~(core.is_column[ids] | core.is_label[ids] | (ids == M.STAR) | (ids == M.CARET) | (ids == M.ZERO))).any():  # an open atom that the mask cannot close yet takes its further value
                keep = np.isin(ids, closing)
                if T.atom:  # the open atom may take its other columns
                    keep |= core.is_column[ids]
                ids, cap = ids[keep], name
    if T.form and cap != 'cap:tokens' and len(ids):
        ids, cap = _demo_caps(pt, lim, ids, cap)
    fac = np.zeros(len(ids))
    reason = cap if cap == 'cap:tokens' else None
    if not reason and len(ids) == 0:
        reason = (cap or 'cap') if len(pt.ids_) else 'empty'
    if not reason:
        for comp in plan.lookahead:
            f = np.asarray(comp.factors(pt, ids), np.float64)
            keep = f > -np.inf
            if not keep.all():
                ids, fac, f = ids[keep], fac[keep], f[keep]
            fac = fac + f
            if len(ids) == 0:
                reason = comp.name
                break
    got = pt.memo[key] = (ids, fac, reason)
    return got


def _demo_caps(pt, lim, ids, cap):
    """(ids, cap) at a point of a DEMONSTRATED query, under the caps on its rules: a rule ends once its PREDICT clause closes, as each of gold's does, and the counts
    of rules, of a rule's forms and of its fields stay within Limits. A NOT does not follow a NOT, which no gold DEMONSTRATED form writes. The decoder admits each id that these
    caps take out, and the writer's distribution has no rows of such points, so without them the search's most likely path can repeat a token until cap:tokens.
    A PREDICT clause has a body, its first column takes a label, and each head column of the form's inputs takes a label of its body: the most likely path otherwise
    writes rules that fill no column, after which the decoder admits no END of the form. A path whose PREDICT clause has no column to fill ends."""
    T, demo = pt.track, core_of(pt.run).demo
    drop = []
    if T.no_targets:
        return ids[:0], 'cap:demo'
    if T.where == 'rule':
        if T.predicted:
            drop = [x for x in ids if x != M.END]
        else:
            if T.rules >= lim.demo_rules:
                drop.append(demo['DEMO_RULE'])
            if T.rule_forms >= lim.rule_forms:
                drop += [x for x in ids if x in core_of(pt.run).form_kinds and x != demo['PREDICT']] + [demo['ALT_FORM']]
            if T.rule_fields >= lim.rule_fields:
                drop.append(M.STAR)
    elif T.where == 'head' and not T.sub and pt.tokens[-1] == M.END:  # gold gives each head column of the form's inputs a label of its body
        drop += [M.END, M.STAR, M.ZERO]
    elif T.where == 'answer' and not T.answered:  # gold's PREDICT clauses fill each column with a label
        drop.append(SKIP_TOK)
    elif T.negated and pt.place.phase == Phase.ATOM_START and pt.tokens[-1] == M.NOT:
        drop.append(M.NOT)
    elif T.predict and T.where == 'body' and not (T.top or T.atom or T.path or T.negated):  # gold's PREDICT clauses each have a body
        drop.append(M.END)
    if drop:
        keep = ~np.isin(ids, np.array(drop, ids.dtype))
        if not keep.all():
            ids, cap = ids[keep], 'cap:demo'
    return ids, cap


def probabilities(pt, plan, ids, fac):
    """(probs, costs) at point pt over ids, kept on the point."""
    key = ('probs', id(plan))
    got = pt.memo.get(key)
    if got is None:
        x = Features(pt, ids)
        z = np.asarray(plan.distribution.logits(pt, ids, x), np.float64) + fac
        z = z - z.max()
        p = np.exp(z)
        p /= p.sum()
        costs = None if plan.cost is None else np.asarray(plan.cost.bits(pt, ids), np.float64)
        if costs is not None and not costs.any():
            costs = None
        got = pt.memo[key] = (p, costs)
    return got


def finish(pt):
    """Closes the query that writing point pt ends: Run.close, and the QueryHash."""
    run, pg, f = pt.run, pt.pg, pt.dec
    rels = pt.track.rels
    if pt.kind in ('INIT', 'RIGID_DET'):
        run.declare_methods(pg, rels)
    else:
        run.declared(pg, rels)
        pg.names = pg.names | {run.V.name(r): run.V.name(r) for r in rels}
    run.close(pg, f)
    return Finished(f, pt.tokens, query_hash(f), S.atom_uses(run.V, pt.tokens))


def write(start, plan, rng, cache=None, on_atom=None):
    """The query that the writer writes from writing point `start`, or Ended. Each choice of two ids or more goes through rng.node, so each is
    a node of the search. cache maps the tokens of a path to its WritingPoint. on_atom(ctx, point) is called at each atom close, with the path's hash
    (rng.hash) at the start of the body; it may raise to end the path."""
    pt = start
    body, ctx = pt.track.body, getattr(rng, 'hash', 0)
    atoms = None
    if os.environ.get('WRITER_ATOM_TREE') or os.environ.get('WRITER_ATOM_SOCKET'):
        import atom_writer as atoms
    whole, closing = atoms is not None, False  # whether the next atom is one choice; and, for an atom that goes by tokens, whether the search has chosen to close the one before it
    while True:
        if pt.track.where == 'done':
            return finish(pt)
        if atoms is not None:
            if not whole and pt.place.phase == Phase.ATOM_START and atoms.decision(pt):
                whole = True
            if whole and atoms.decision(pt):
                got = atoms.choose(pt, plan, rng)
                if got is not None:
                    before = len(pt.track.texts)
                    pt = got
                    if pt.track.body != body:
                        body, ctx = pt.track.body, getattr(rng, 'hash', 0)
                    if on_atom is not None and len(pt.track.texts) > before:
                        on_atom(ctx, pt)
                    continue
                whole, closing = False, pt.place.phase == Phase.COLUMN
        ids, fac, reason = options(pt, plan)
        if reason:
            return Ended(reason)
        if len(ids) == 1:
            j = 0
        else:
            probs, costs = probabilities(pt, plan, ids, fac)
            keys = getattr(rng, 'keys', None)
            tie = None if keys is None else (lambda i, pt=pt, ids=ids, keys=keys: keys.of(pt, int(ids[i])))
            if atoms is not None and not whole and atoms.closes_here(pt):
                j = atoms.token_choice(pt, ids, probs, costs, rng, closing)
                closing = False
                if j is None:  # the open atom closes: the next atom is one choice
                    whole = True
                    continue
            else:
                j = rng.node(probs, costs, tie)
        before = len(pt.track.texts)
        pt = step_point(pt, int(ids[j]), cache)
        if pt.track.body != body:
            body, ctx = pt.track.body, getattr(rng, 'hash', 0)
            whole, closing = atoms is not None, False
        if on_atom is not None and len(pt.track.texts) > before:
            on_atom(ctx, pt)
