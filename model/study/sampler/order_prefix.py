#!/usr/bin/env python
"""The `ordered` plan's order rule (order.py) in prefix form: at a writing point, the next tokens that no `ordered` path continues with.

    rule = rule_of(run)              # one per Run
    keep = rule.keep(pt, ids)        # bool over ids: False where the rule removes the id
    fl = rule.floors(pt)             # [Floor] of the open sets of pt, [] where no set is open, None where the query has no sets; rule.floors(pt, t): of the point after token t
    rule.below(bound, t)             # whether first token t is below a Floor's bound, so that the bound bars it

The `ordered` rule writes the items of a set (the atoms of a body, the branches of an OR, the atoms of a branch, the two lists of an ALL) one at a time: at each step, the item of least key
among the items that the decoder accepts at that step. The key of an item at a state is its model tokens under the state's naming: a label made before the state is its label token; a label
made after it is `*` (or `^`) where the item first names it, and then the label token of the state's next fresh index. So a written order is the rule's where, for each two items p and x of
one set, p written first, x is refused at the state before p or x's key at that state is not below p's key. Equal keys are a tie, and both orders stay.

The rule tests that condition as the tokens come, at the innermost open set:
  - A token that starts an atom of a free relation (one whose sites all take a new label: not a lib relation) is removed where it is below the first token of an earlier item of the
    set, and the decoder takes it at the state before that earlier item.
  - A token that goes on with an open atom of a free relation is removed where it makes the atom's key at the state before an earlier item fall below that item's key, and the
    decoder takes the atom so far and the token at that state.
  - A token that closes an atom is removed where the atom fails the condition against an earlier item (order.render at the earlier state).
  - The END of an OR or an ALL is removed where the written item is not one of the ways that order.render writes it from its first state, or it fails the condition against an earlier
    item of its set.
At a body's END every two items of the body have passed the condition, so the body is one of the ways that the rule writes it: in plain order.ordered, a step takes the least key, which is
the condition for each pair; and an item that the written body takes first can be completed, so the lookahead form of order.ordered takes it too.
A NOT, a comparison, an atom of a lib relation and a compound can be refused at the earlier state by tokens still to come, though the decoder takes their first tokens there: they read
labels that are bound there only later (a label made in between; in a later branch of an OR, a label of the first branch that a positive atom of the branch has to read first), or an
input site of a lib relation takes a label that is new there. So the first two tests keep their tokens, and the test at the close decides. They keep a free relation's tokens too where a
`^` label was made in between.

In a DEMONSTRATED query, the bodies of its key and inputs and of each form of a rule are sets as above, each read in its label scope (Rule._info). Its rules, and the forms of a rule
before its PREDICT clause, are sets too (see demo_keep): a rule's tokens are compared with each earlier rule's as they come, and a form is compared with each earlier form of its rule
where it closes.
In a CHOOSE query, the `for` body is a set as above, but an item x is not compared at its close with an earlier item p where x, written at the state before p, would make the
`^` labels in another order: they are the key's columns in order (order.caret_order_ok). (The tests at a start and inside an atom keep the token where a `^` label was made since p.)
Its `from` and `never` bodies are pinned ('seq': order.PINNED): the rule keeps their items as written, and only orders the operands of a symmetric comparison and the sets of an
OR, ALL or IF inside them.
A proposer body, a CHOOSE form of a DEMO_RULE, the group tokens of an INIT, a RIGID_DET or a CHOOSE and the parts of a RIGID_DET have no sets: the rule keeps every id there. A test that
passes SECONDS keeps the token.
"""
import bisect
import collections
import dataclasses
import os
import time
from typing import Any

import numpy as np

import live
import order
import writer
from live import ALSO_TOK, SKIP_TOK, M, arclog
from writer import Phase, core_of

STAR, CARET, END, NOT, OR_TOK, ZERO = M.STAR, M.CARET, M.END, M.NOT, M.OR, M.ZERO
EQ = M.CMP[0]
CMP = frozenset(M.CMP)
SYMMETRIC = (M.CMP[0], M.CMP[1])
SECONDS = float(os.environ.get('WRITER_ROW_TEST_SECONDS', 2.0))  # the budget of one test at a close, on the wall clock: rows lift it, so that load moves no candidate


class _List:
    """An open set of items: kind 'body', 'branch', 'dom' (an ALL's first list), 'allbody', 'if0', 'if1' or 'if2'; or 'parts', a RIGID_DET's parts, which are no set (each is an
    output slot by its position) and which the rule keeps in any order; or 'seq', a pinned body of a CHOOSE (its `from` or a `never`), whose items stay as written. items: [(start, end, kind)] of its closed items, token indexes
    (end excluded), kind 'atom', 'not', 'cmp', 'one', 'or', 'all' or 'if'. cur: the start of the open item, and cur_kind its kind."""
    __slots__ = ('kind', 'start', 'items', 'cur', 'cur_kind')

    def __init__(self, kind: str, start: int):
        self.kind, self.start = kind, start
        self.items: list[tuple] = []  # (start, end, kind)
        self.cur: int | None = None
        self.cur_kind: str | None = None


class _Or:
    """An open OR: branches [(start, end)] of its closed branches, cur the start of the open branch."""
    __slots__ = ('start', 'branches', 'cur')

    def __init__(self, start: int):
        self.start, self.cur = start, start
        self.branches: list[tuple[int, int]] = []


def parse(core, kind, tokens, start=0):
    """The open sets of a query's model tokens (the kind token first), outermost first: a list of _List and _Or; [] where no set is open (between the bodies of an INIT, a RIGID_DET or a CHOOSE,
    after a body's END); None for a proposer body. start: the index of the kind token of the form, where the form is a form of a DEMO_RULE, or the query's kind token."""
    rel, col, lab = core.is_rel, core.is_column, core.is_label
    ALLT, IFT, ONET = core.ALL, core.IF, core.ONE
    starts = (NOT, OR_TOK, ALLT, IFT, ONET)
    stack: list[Any] = []  # of _List and _Or
    if kind in ('RULE', 'DET'):
        if len(tokens) > start + 1 and core.kind[tokens[start + 1]] == 'proposer':
            return None
        stack.append(_List('body', start + 1))
    atom = one = notwait = due = rec = False
    need = 0
    decisions = 0  # the group-level decisions so far (a body or SKIP each; in a CHOOSE, an empty body's END too); a RIGID_DET's parts follow its first two, a CHOOSE's pinned bodies its first
    for i in range(start + 1, len(tokens)):
        t = tokens[i]
        if not stack:
            if kind in ('RULE', 'DET'):
                return []
            if not (rel[t] or t in CMP or t in starts):  # a group token of an INIT, a RIGID_DET or a CHOOSE
                decisions += t == SKIP_TOK or (kind == 'CHOOSE' and t == END)
                continue
            stack.append(_List('parts' if kind == 'RIGID_DET' and decisions >= 2 else 'seq' if kind == 'CHOOSE' and decisions >= 1 else 'body', i))
            decisions += 1
        top = stack[-1]
        if one:  # a ONE mark: its labels, then its END
            if t == END:
                top.items.append((top.cur, i + 1, 'one'))
                top.cur, one = None, False
            continue
        if atom:
            if notwait:
                if rel[t]:
                    notwait = False
                    continue
            elif due:
                if col[t]:
                    rec = True
                else:
                    due = False
                continue
            elif need > 0:
                need -= 1
                continue
            elif rec:
                if col[t]:
                    due = True
                else:
                    rec = False
                continue
            elif col[t]:
                due = True
                continue
            elif t in (STAR, CARET, ZERO) or lab[t]:
                continue
            top.items.append((top.cur, i, top.cur_kind))
            top.cur, atom = None, False
        if rel[t]:
            top.cur, top.cur_kind, atom, due, rec, need = i, 'atom', True, False, False, 0
        elif t == NOT:
            top.cur, top.cur_kind, atom, notwait, due, rec, need = i, 'not', True, True, False, False, 0
        elif t in CMP:
            top.cur, top.cur_kind, atom, due, rec, need = i, 'cmp', True, False, False, 2
        elif t == OR_TOK:
            top.cur, top.cur_kind = i, 'or'
            stack.append(_Or(i + 1))
            stack.append(_List('branch', i + 1))
        elif t == ALLT:
            top.cur, top.cur_kind = i, 'all'
            stack.append(_List('dom', i + 1))
        elif t == IFT:
            top.cur, top.cur_kind = i, 'if'
            stack.append(_List('if0', i + 1))
        elif t == ONET:
            top.cur, top.cur_kind, one = i, 'one', True
        elif t == ALSO_TOK and top.kind == 'branch':
            stack.pop()
            o: Any = stack[-1]  # the _Or of the branch
            o.branches.append((o.cur, i))
            o.cur = i + 1
            stack.append(_List('branch', i + 1))
        elif t == END:
            if top.kind in ('body', 'parts', 'seq'):
                stack.pop()
            elif top.kind == 'branch':
                stack.pop()
                o = stack.pop()
                o.branches.append((o.cur, i))
                p = stack[-1]
                p.items.append((p.cur, i + 1, 'or'))
                p.cur = None
            elif top.kind in ('dom', 'if0', 'if1'):
                stack[-1] = _List({'dom': 'allbody', 'if0': 'if1', 'if1': 'if2'}[top.kind], i + 1)
            else:  # allbody, if2
                stack.pop()
                p = stack[-1]
                p.items.append((p.cur, i + 1, p.cur_kind))
                p.cur = None
    return stack


@dataclasses.dataclass(frozen=True, slots=True)
class Floor:
    """The bound that the order puts on the first token of the next item started in one open set. depth: the set's place among the open sets, 0 outermost. kind: the set's kind
    (_List.kind). rel: the bound for an atom of a free relation (one whose sites all take a new label: not a lib relation), or None for no bound; it can fall only where a `^`
    label is made before that start. other: always None: the rule bars an atom of a lib relation, NOT, a comparison, OR and ALL at its close alone. The rule removes a first token below the bound (unless the decoder refuses it at the state before the earlier item that sets the bound); a
    first token above it is free of the bound; at the bound, the item's later tokens decide, since a key is the item's whole token string."""
    depth: int
    kind: str
    rel: int | None
    other: int | None


class Rule:
    def __init__(self, run):
        self.run = run
        self.core = core_of(run)
        self.env = order.Env(run.session)
        self.label_tok = self.env.run.ff0.label_tok  # label index -> token
        self.label_idx = {t: k for k, t in self.label_tok.items()}
        self.stats = collections.Counter()
        self.free = self.core.is_rel & np.array([k not in writer.LIB_KINDS for k in self.core.kind])  # relations whose sites all take a new label (a lib relation's input sites take bound labels alone)
        self.demo = dict(live.DEMO_TOK)
        self.form_starts = frozenset(self.core.form_kinds) | {self.demo[k] for k in ('ALT_FORM',) if k in self.demo}  # the tokens that start a form of a DEMO_RULE
        self.made = {}  # id of a decoder of a DEMONSTRATED query -> (the decoder, the count of relations that the query declared before it): decls

    # ---- the facts of a point

    def info(self, pt):
        got = pt.memo.get('order_prefix')
        if got is None:
            got = pt.memo['order_prefix'] = self._info(pt.kind, pt.tokens, pt.track)
        return got

    def _info(self, kind, tokens, T):
        """The open sets of the form that holds the next token (parse), mk: the indexes of its `*` and `^`, off: the index of the label that its first `*` or `^` makes, fields: the
        count of the labels that it reads from outside it (a DEMO_RULE's fields), base: the index of its kind token. In a DEMONSTRATED query, the form is its key and inputs or a form
        of a DEMO_RULE (a PREDICT clause as a RULE); None in a CHOOSE form, between the forms and in the PREDICT clause's answers."""
        base, off, fields = 0, 0, 0
        if T.form:
            if T.where not in ('body', 'group', 'start', 'head') or T.sub == 'CHOOSE':
                return None
            if T.sub:
                base, kind = T.base, T.sub
                rs = max(i for i in range(base) if tokens[i] == self.demo['DEMO_RULE'])
                fields, off = self.label_offset(tokens, rs, base)
            else:
                kind = 'INIT'  # the key and inputs of a DEMONSTRATED form are bodies of ports, as an INIT's
        elif kind not in ('RULE', 'DET', 'INIT', 'RIGID_DET', 'CHOOSE'):
            return None
        stack = parse(self.core, kind, tokens, base)
        if stack is None:
            return None
        mk = [i for i in range(base + 1, len(tokens)) if tokens[i] in (STAR, CARET)]
        return dict(stack=stack, mk=mk, off=off, fields=fields, base=base)

    def label_offset(self, tokens, rs, fs):
        """(fields, off) of the form of a DEMO_RULE whose first token is at fs, the rule's DEMO_RULE at rs: a rule is a label scope, its fields take its first labels and each `*` and `^`
        of its forms the next one; a form after ALT_FORM is a label scope of its own, from the first label, and the rule's later forms go on from where the rule's labels stood."""
        alt = self.demo.get('ALT_FORM')
        if tokens[fs - 1] == alt or tokens[fs] == alt:
            return 0, 0
        starts = [i for i in range(rs + 1, fs) if tokens[i] in self.form_starts and tokens[i - 1] != alt]
        fields = sum(tokens[i] == STAR for i in range(rs + 1, starts[0] if starts else fs))
        off, in_alt = 0, False
        for i in range(rs + 1, fs):
            if i in starts:
                in_alt = tokens[i] == alt
            if tokens[i] in (STAR, CARET) and not in_alt:
                off += 1
        return fields, off

    @staticmethod
    def made_before(info, i):
        """The count of labels made before token index i."""
        return bisect.bisect_left(info['mk'], i)

    def late_caret(self, info, tokens, lo, hi):
        """Whether a label of index lo..hi-1 was made by `^`."""
        return any(tokens[info['mk'][k]] == CARET for k in range(lo, hi))

    def rendered(self, info, tokens, a, b, mj):
        """(tokens, assign) of tokens[a:b] at a state with mj labels made: labels of index mj or above are named anew (assign: label index -> new index). A label index counts
        from the form's first label (info['off']); a field has an index below 0."""
        out, assign, nxt = [], {}, mj
        lab = self.core.is_label
        off = info['off']
        for p in range(a, b):
            t = tokens[p]
            if t in (STAR, CARET):
                assign[self.made_before(info, p)] = nxt
                nxt += 1
                out.append(t)
            elif lab[t]:
                k = self.label_idx[t] - off
                if k < mj:
                    out.append(t)
                elif k in assign:
                    out.append(self.label_tok[off + assign[k]])
                else:
                    assign[k] = nxt
                    nxt += 1
                    out.append(tokens[info['mk'][k]])
            else:
                out.append(t)
        return out, assign

    def render_tok(self, info, tokens, t, mj, assign):
        if self.core.is_label[t]:
            k = self.label_idx[t] - info['off']
            if k < mj:
                return t
            if k in assign:
                return self.label_tok[info['off'] + assign[k]]
            return tokens[info['mk'][k]]
        return t

    # ---- the rule

    def keep(self, pt, ids):
        out = np.ones(len(ids), bool)
        if not len(ids):
            return out
        if pt.track.form:
            out &= self.demo_keep(pt, ids)
        if pt.track.where == 'body':
            out &= self.body_keep(pt, ids)
        return out

    def body_keep(self, pt, ids):
        out = np.ones(len(ids), bool)
        T = pt.track
        info = self.info(pt)
        if not info or not info['stack']:
            return out
        L = info['stack'][-1]
        if not isinstance(L, _List) or L.kind == 'parts':
            return out
        ph = pt.place.phase
        if L.kind == 'seq':  # the items of a pinned body stay as written
            if ph == Phase.OPERAND and L.cur is not None:
                out &= self.operands(pt, ids)
            return out
        core = self.core
        if ph in (Phase.VALUE, Phase.OPERAND, Phase.FIELD):
            if L.cur is not None:
                out &= self.go_on(pt, info, L, ids)
                if ph == Phase.OPERAND:
                    out &= self.operands(pt, ids)
            return out
        if ph == Phase.ATOM_START and L.cur is not None and L.cur_kind == 'not':  # the relation of a NOT atom
            out &= self.go_on(pt, info, L, ids)
            return out
        if ph not in (Phase.COLUMN, Phase.ATOM_START):
            return out
        closing = np.ones(len(ids), bool)
        items = list(L.items)
        if ph == Phase.COLUMN and L.cur is not None:
            from lookahead import closers
            closing = closers(core, ids)
            if (~closing).any():
                sub = self.go_on(pt, info, L, ids[~closing])
                out[np.flatnonzero(~closing)[~sub]] = False
            if closing.any():
                x = (L.cur, len(pt.tokens), L.cur_kind)
                if not self.pair_ok(pt, info, L, x, pt.tokens):
                    out[closing] = False
                    return out
                items.append(x)
        from lookahead import starts
        st = starts(core, ids) & closing & out
        if st.any() and items:
            sub = self.new_ok(pt, info, items, ids[st])
            out[np.flatnonzero(st)[~sub]] = False
        e = closing & out & (ids == END)
        if e.any() and not self.end_ok(pt, info):
            out[e] = False
        e = closing & out & (ids == END)
        if e.any() and T.sub in ('RULE', 'DET') and not T.predict and len(info['stack']) == 1 and not self.form_ok(pt, pt.tokens + (END,)):  # the END of a form of a DEMO_RULE
            out[e] = False
        return out

    # ---- the rules and forms of a DEMONSTRATED query
    #
    # The rules of a DEMONSTRATED query are a set, and the forms of a rule before its PREDICT clause are a set (order.Group). The key of a rule or a form is its model tokens.
    # A rule is a label scope, and the decoder accepts it at any state of the rules; its relations take the next names (`&r` and a number) where it declares them. So a rule x,
    # written at the state before an earlier rule p, is x's tokens with each relation that x declares named as the one the decoder declares at its place after p's start; the
    # rule removes a token of x after which those tokens fall below p's tokens. A form x of a rule, written at the state before an earlier form p of the rule, is refused where x
    # reads a relation that p or a form after p declares; else it is x's tokens with each label that x makes moved to the labels from p's first one. A form that fails this
    # against an earlier form is removed at its END; an INIT, a RIGID_DET or a CHOOSE form, which has no END of its own, at the tokens after it.

    def decls(self, pt, i):
        """The count of relations that the query of pt declares with its first i tokens (1 <= i <= len(pt.tokens)). Kept by decoder (self.made); a count that is not kept comes
        from the steps after the last kept one."""
        n = len(pt.tokens)
        decs, d, back = [None] * (n + 1), pt.dec, pt.back
        for k in range(n, 0, -1):
            decs[k] = d
            if k > 1:
                d, back = back
        if len(self.made) > 20000:
            self.made.clear()
        self.made[id(pt.dec)] = (pt.dec, len(pt.track.rels))
        got = self.made.get(id(decs[i]))
        if got is not None and got[0] is decs[i]:
            return got[1]
        j = i
        while j > 1 and not ((e := self.made.get(id(decs[j]))) is not None and e[0] is decs[j]):
            j -= 1
        c = self.made[id(decs[j])][1] if j > 1 else 0
        for k in range(j, i):
            c += sum(self.core.kind[x] == 'relation' for x in decs[k].fork().step(pt.tokens[k])[0])
            self.made[id(decs[k + 1])] = (decs[k + 1], c)
        return c

    def rule_starts(self, tokens):
        return [i for i, t in enumerate(tokens) if t == self.demo['DEMO_RULE']]

    def form_starts_of(self, tokens, rs, n):
        """The indexes of the starts of the forms of the rule at rs, before index n: ALT_FORM, or a form's kind token that does not follow ALT_FORM."""
        alt = self.demo.get('ALT_FORM')
        return [i for i in range(rs + 1, n) if tokens[i] in self.form_starts and tokens[i - 1] != alt]

    def demo_keep(self, pt, ids):
        out = np.ones(len(ids), bool)
        tokens = pt.tokens
        n = len(tokens)
        starts = self.rule_starts(tokens)
        if not starts:
            return out
        self.decls(pt, n)
        xs = starts[-1]
        rels = pt.track.rels
        if len(starts) > 1:
            ax = self.decls(pt, xs)
            local = {r: k for k, r in enumerate(rels[ax:])}  # x's relations, by their place among them
            for ps, pe in zip(starts, starts[1:]):
                P = tokens[ps:pe]
                if n - xs >= len(P):
                    continue
                ap = self.decls(pt, ps)
                moved = lambda t: rels[ap + local[t]] if t in local else t  # noqa: E731
                X = tuple(moved(t) for t in tokens[xs:n])
                if X != P[:len(X)]:
                    continue
                bound = P[len(X)]
                low = np.array([moved(int(t)) < bound for t in ids], bool)
                if low.any():
                    self.stats['rule below'] += 1
                out &= ~low
        if pt.track.where == 'rule' and n - 1 > xs:  # the form before this point has ended: an INIT, a RIGID_DET or a CHOOSE has no END of its own
            fs = self.form_starts_of(tokens, xs, n)
            if fs:
                k = tokens[fs[-1] + 1] if tokens[fs[-1]] == self.demo.get('ALT_FORM') else tokens[fs[-1]]
                if self.core.form_kinds.get(k) in ('INIT', 'RIGID_DET', 'CHOOSE') and k != self.demo.get('PREDICT') and not self.form_ok(pt, tokens):
                    out[:] = False
        return out

    def form_ok(self, pt, toks):
        """Whether the last form of the current DEMO_RULE, closed by toks (pt's tokens and, where it ends with it, the next token), passes the order of the rule's forms against
        each earlier form of the rule."""
        key = ('order_prefix_form', len(toks))
        got = pt.memo.get(key)
        if got is None:
            got = pt.memo[key] = self._form_ok(pt, toks)
        return got

    def _form_ok(self, pt, toks):
        xs = self.rule_starts(toks)[-1]
        fs = self.form_starts_of(toks, xs, len(toks))
        if len(fs) < 2:
            return True
        x0 = fs[-1]
        rels = pt.track.rels
        _, offx = self.label_offset(toks, xs, x0)
        X = toks[x0:]
        ax = self.decls(pt, x0)
        for ps, pe in zip(fs, fs[1:]):
            later = set(rels[self.decls(pt, ps):ax])
            if any(t in later for t in X):  # x reads a relation of p or of a form after p: the decoder refuses x before p
                continue
            _, offp = self.label_offset(toks, xs, ps)
            lab = self.core.is_label
            moved = tuple(self.label_tok[self.label_idx[t] - offx + offp] if lab[t] and self.label_idx[t] >= offx else t for t in X)
            if moved < toks[ps:pe]:
                self.stats['form below'] += 1
                return False
        return True

    def operands(self, pt, ids):
        """The second operand of `=` or `!=` after a label: the operands of a symmetric comparison of two labels stand in the order of their label tokens, and a new label stands first."""
        keep = np.ones(len(ids), bool)
        oa = pt.open_atom
        if pt.track.need == 1 and len(oa) == 2 and oa[0] in SYMMETRIC and self.core.is_label[oa[1]]:
            keep &= ~((ids == STAR) | (ids == CARET) | (self.core.is_label[ids] & (ids < oa[1])))
        return keep

    def go_on(self, pt, info, L, ids):
        """Which ids, as the next token of the open atom of set L, keep the atom's key from falling below an earlier item's key at the state before that item."""
        keep = np.ones(len(ids), bool)
        tokens = pt.tokens
        a, n = L.cur, len(tokens)
        ma = self.made_before(info, a)
        for s, e, kd in L.items:
            if kd == 'one' or L.cur_kind == 'one':
                continue
            K = tokens[s:e]
            mj = self.made_before(info, s)
            late = ma > mj
            r, assign = self.rendered(info, tokens, a, n, mj)
            d = next((i for i in range(min(len(r), len(K))) if r[i] != K[i]), None)
            if d is not None or len(r) >= len(K):
                continue  # above K, or decided below it before this token (the close decides)
            kn = K[len(r)]
            rt = np.array([self.render_tok(info, tokens, int(t), mj, assign) for t in ids], np.int64)
            low = rt < kn
            if not low.any():
                continue
            if L.cur_kind != 'atom' or not self.free[tokens[a]] or (late and self.late_caret(info, tokens, mj, ma)):
                continue
            dec = writer.dec_at(pt, s).fork()
            try:
                for x in r:
                    dec.step(x)
            except arclog.Refusal:
                continue  # the atom is refused at that state
            adm = np.array(dec.admits([int(x) for x in rt[low]]), bool)
            keep[np.flatnonzero(low)[adm]] = False
        return keep

    def new_ok(self, pt, info, items, ids):
        """Which ids, starting an item of a set whose earlier items are `items`, are not below an earlier item's first token where the item is accepted at the state before it."""
        keep = np.ones(len(ids), bool)
        tokens = pt.tokens
        n = len(tokens)
        mn = self.made_before(info, n)
        free = self.free[ids]
        for s, e, kd in items:
            if kd == 'one':
                continue
            low = (ids < tokens[s]) & free  # only an atom of a free relation is decided at its first token
            if not low.any():
                continue
            mj = self.made_before(info, s)
            if mn > mj and self.late_caret(info, tokens, mj, mn):  # and not where a `^` label was made since
                continue
            adm = np.array(writer.dec_at(pt, s).fork().admits([int(x) for x in ids[low]]), bool)
            keep[np.flatnonzero(low)[adm]] = False
        return keep

    # ---- the tests at a close

    def symbolic(self, info, tokens, a, b):
        """The tokens a..b-1 in order.py's form: a label as order.sym of its label token, `*` and `^` with the label they make."""
        out = []
        for p in range(a, b):
            t = tokens[p]
            if t in (STAR, CARET):
                out.append(order.sym(self.label_tok[info['off'] + self.made_before(info, p)]))
            elif self.core.is_label[t]:
                out.append(order.sym(t))
            else:
                out.append(t)
        return out

    def setup(self, info, tokens, b):
        """(marks, total) of the labels of tokens[:b], and the env ready for a test."""
        env = self.env
        off = info['off']
        marks = {self.label_tok[off + k]: tokens[i] for k, i in enumerate(info['mk']) if i < b}
        total = collections.Counter()
        for p in range(info['base'] + 1, b):
            t = tokens[p]
            if t in (STAR, CARET):
                total[self.label_tok[off + self.made_before(info, p)]] += 1
            elif self.core.is_label[t]:
                total[t] += 1
        env.total = total
        env.rcache = {}
        env.lookahead = False
        env.deadline = time.monotonic() + SECONDS
        return marks, total

    def naming(self, info, i):
        """The labels bound before token index i: the fields, and the labels that the form made before i."""
        nm = {self.label_tok[k]: self.label_tok[k] for k in range(info['fields'])}
        nm.update((self.label_tok[info['off'] + k], self.label_tok[info['off'] + k]) for k in range(self.made_before(info, i)))
        return nm

    def set_needs(self, item, total):
        if isinstance(item, order.All):
            inside = order.labels_of(item)
            item.needs = frozenset(g for g in inside if total[g] > inside[g])
        for sub in self.subs(item):
            for it in sub.items:
                self.set_needs(it, total)

    @staticmethod
    def subs(item):
        if isinstance(item, order.Or):
            return item.branches
        if isinstance(item, order.All):
            return (item.dom, item.body)
        if isinstance(item, order.If):
            return (item.test, item.then, item.els)
        return ()

    def item_of(self, info, tokens, a, b, total):
        s = self.symbolic(info, tokens, a, b)
        item, j = order.parse_item(self.env, s, 0)
        if j != len(s):
            raise order.ParseError('the item ends early')
        self.set_needs(item, total)
        return item

    def pair_ok(self, pt, info, L, x, tokens):
        """Whether the closed item x = (start, end, kind) of set L passes the condition against each earlier item of L. tokens: pt's tokens, and the token after the point where
        x ends with it."""
        a, b, kd = x
        if kd == 'one' or L.kind == 'seq':
            return True
        ma = self.made_before(info, a)
        item = marks = None
        for s, e, kj in L.items:
            if kj == 'one':
                continue
            K = tuple(tokens[s:e])
            mj = self.made_before(info, s)
            if ma == mj and kd == 'atom' and self.free[tokens[a]]:  # no label made between: the atom is written at that state as it stands, and the decoder takes it there as here
                if tuple(tokens[a:b]) < K:
                    self.stats['pair below'] += 1
                    return False
                continue
            r = self.rendered(info, tokens, a, b, mj)[0]
            if tuple(r[:1]) > K[:1]:
                continue
            if pt.kind == 'CHOOSE' and not self.caret_order_kept(info, tokens, s, a, b, mj):  # x before p would make the key labels of a CHOOSE's `for` in another order
                continue
            try:
                if item is None:
                    marks, total = self.setup(info, tokens, b)
                    item = self.item_of(info, tokens, a, b, total)
                nm = self.naming(info, s)
                if not order.exports_ok(self.env, item, nm):  # order.walk_set does not take the OR at that state
                    continue
                outs, _ = order.render(self.env, marks, item, (writer.dec_at(pt, s), nm), 'min')
            except order.Overflow:
                self.stats['pair overflow'] += 1
                continue
            except Exception:  # noqa: BLE001 - an item that order.py cannot read: no test
                self.stats['pair error'] += 1
                continue
            finally:
                self.env.deadline = None
            if outs and min(o[0] for o in outs) < K:
                self.stats['pair below (renamed)'] += 1
                return False
        return True

    def caret_order_kept(self, info, tokens, s, a, b, mj):
        """Whether the item x = tokens[a:b], written at the state before the earlier item that starts at s (where mj labels were made), makes the `^` labels in the order of the
        tokens: in a CHOOSE's `for`, the `^` labels are the key's columns in order (order.caret_order_ok). At that state x makes, by `^`, its own `^` labels and the labels that it
        reads and that a `^` made since; the other labels that a `^` made since follow."""
        mk, off = info['mk'], info['off']
        before = [self.made_before(info, i) for i in range(s, a) if tokens[i] == CARET]
        written = before + [self.made_before(info, i) for i in range(a, b) if tokens[i] == CARET]
        moved = []
        for i in range(a, b):
            t = tokens[i]
            if t == CARET:
                k = self.made_before(info, i)
            elif self.core.is_label[t]:
                k = self.label_idx[t] - off
                if k < mj or tokens[mk[k]] != CARET:
                    continue
            else:
                continue
            if k not in moved:
                moved.append(k)
        return moved + [k for k in before if k not in moved] == written

    def end_ok(self, pt, info):
        """Whether END may close the innermost open set: for an ALL or an OR, the item is one of order.render's from its first state, and it passes the condition against the earlier
        items of its set. The END of a body or of an ALL's first list is always kept."""
        got = pt.memo.get('order_prefix_end')
        if got is None:
            got = pt.memo['order_prefix_end'] = self._end_ok(pt, info)
        return got

    def _end_ok(self, pt, info):
        stack, tokens = info['stack'], pt.tokens
        L, n = stack[-1], len(tokens)
        if L.kind in ('dom', 'if0', 'if1', 'body', 'seq'):
            return True
        P = stack[-3] if L.kind == 'branch' else stack[-2]
        a = P.cur
        written = tuple(tokens[a:n]) + (END,)
        toks = tokens + (END,)
        try:
            marks, total = self.setup(info, toks, n + 1)
            item = self.item_of(info, toks, a, n + 1, total)
            outs, _ = order.render(self.env, marks, item, (writer.dec_at(pt, a), self.naming(info, a)), 'min')
        except order.Overflow:
            self.stats['end overflow'] += 1
            return True
        except Exception:  # noqa: BLE001
            self.stats['end error'] += 1
            return True
        finally:
            self.env.deadline = None
        if outs and written not in {o[0] for o in outs}:
            self.stats['compound not canonical'] += 1
            return False
        return self.pair_ok(pt, info, P, (a, n + 1, P.cur_kind), toks)

    # ---- floors

    def has_sets(self, pt):
        """Whether the form of pt has sets that the rule orders: False for a proposer body, and in a DEMONSTRATED query outside the bodies of its key, inputs and forms."""
        return self.info(pt) is not None

    @staticmethod
    def below(bound, t):
        """Whether first token t is below a Floor's bound (rel or other), so that the bound bars it. False where the bound is None, at the bound (the later tokens decide) and above it.
        The rule keeps a barred start where the decoder refuses it at the state before the earlier item that sets the bound; keep(pt, ids) gives that exact verdict."""
        return bound is not None and int(t) < bound

    def floors(self, pt, t=None):
        """[Floor] of the open sets of pt, outermost first; with t, of the point after token t (no step is made). [] where no set is open (after a body's END, between the bodies
        of an INIT or a RIGID_DET); None where the query has no sets (has_sets), and in a DEMONSTRATED query."""
        if pt.track.form or not self.has_sets(pt):
            return None
        tokens = pt.tokens if t is None else pt.tokens + (int(t),)
        info = self.info(pt) if t is None else self._info(pt.kind, tokens, pt.track)
        if info is None:
            return None
        n = len(tokens)
        mn = self.made_before(info, n)
        out = []
        lists = [f for f in info['stack'] if isinstance(f, _List)]
        for depth, L in enumerate(lists):
            items = list(L.items) + ([(L.cur, n, L.cur_kind)] if L.cur is not None else [])
            rel = other = None
            if L.kind in ('parts', 'seq'):
                out.append(Floor(depth, L.kind, rel, other))
                continue
            for s, e, kd in items:
                if kd == 'one':
                    continue
                mj = self.made_before(info, s)
                f = tokens[s]
                if mn == mj or not self.late_caret(info, tokens, mj, mn):
                    rel = f if rel is None else max(rel, f)
            out.append(Floor(depth, L.kind, rel, other))
        return out


def rule_of(run):
    got = run.__dict__.get('order_prefix_rule')
    if got is None:
        got = run.order_prefix_rule = Rule(run)
    return got
