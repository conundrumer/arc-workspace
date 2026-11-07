"""Whole-atom writing, as tonight's experiment: at a point where the next token starts an item or ends a body, a token tree proposes its top atoms, the engine gives each one's body table, and a learned model scores them as one choice of the search.

Rows and the live writer share this module, so a model reads at serving what it read in its fit. A candidate's row is the point's columns, the columns of its first token, the atom's structure, whether the engine gave a body table, the token tree's bits for the atom and their gap to the best proposal's, the AssignmentVector of the body with the atom added, and its difference from the body before. A server's rows hold the bits and their gap, each over 10, after the rest.

  WRITER_ATOM_TREE     a LightGBM text model over those columns (with its .uses.json), or
  WRITER_ATOM_SOCKET   the socket of a server, whose Client.score(point, cands) gives one logit per candidate; WRITER_ATOM_SERVER_DIR holds atom_serve.py
  WRITER_ATOM_K        the atoms a decision proposes (default 8)
  WRITER_ATOM_ENOUGH   the token tree's mass at which a proposal walk ends (default: no limit)
  WRITER_ATOM_POPS     the items that a proposal walk takes off its heap, per atom wanted (default 12)

A share of the mass that the token tree gives to atoms outside the proposals (WRITER_ATOM_ESCAPE) stays as one more option of the choice, and a search that takes it writes that atom by tokens, so each atom stays reachable. The next atom is one choice again.

Time blocked on a server counts toward a job's budget, through time.blocked_seconds where the CPU clock is on (cpu_clock/sitecustomize.py)."""
import collections
import heapq
import json
import os
import sys
import time

import numpy as np

import writer
from lookahead import closers

M, Phase = writer.M, writer.Phase
STRUCT = ('n_tokens', 'n_columns', 'n_fresh', 'n_key', 'n_join', 'n_zero', 'negated', 'is_end', 'is_group', 'is_comparison')
K = int(os.environ.get('WRITER_ATOM_K', 8))
ESCAPE = float(os.environ.get('WRITER_ATOM_ESCAPE', 0.25))  # the share of the mass outside the proposals that stays with token writing: the true atom lies outside them far less often than the tree's mass there says
SET_NAMES = ['atom:bits_rank', 'atom:bits_share', 'atom:same_first', 'atom:first_share']
ENOUGH = float(os.environ.get('WRITER_ATOM_ENOUGH', 2.0))  # a walk ends once the atoms it has found hold this much of the token tree's mass
POPS = int(os.environ.get('WRITER_ATOM_POPS', 12))  # the items that a walk takes off its heap, per atom wanted
FINISHED = -1  # an item of the walk that is an atom with its closing share counted
MIN_CHANCE = 1e-5  # a token below this chance at a point goes on no heap
ROUND = 1e-4  # a logit's precision: a batch's shape can move a server's last bits, and the search compares chances
POINT_BLOCKS = ('pq', 'state', 'task', 'place', 'ctx')
TOKEN_BLOCKS = ('token', 'tok', 'tokg', 'tokc', 'tokm')


def names_of(run):
    """(point names, token names, their columns in the writing-point vector), kept on the Run."""
    got = run.__dict__.get('atom_names')
    if got is None:
        names = writer.vector_names(run)
        by = writer._names_by_block(run)[1]
        point = [n for b in POINT_BLOCKS for n in by.get(b, ())]
        token = [n for b in TOKEN_BLOCKS for n in by.get(b, ())]
        at = {n: i for i, n in enumerate(names)}
        got = run.atom_names = point, token, np.array([at[n] for n in point]), np.array([at[n] for n in token])
    return got


STATS = collections.Counter()
LOG_DIR = os.environ.get('WRITER_ATOM_LOG_DIR')  # a process writes its counters here as <pid>.json, each hundred decisions


def is_group_token(core, t):
    return t == M.END or t == M.OR or t == core.ALL or t == core.IF or t == writer.ALSO_TOK


def decision(pt):
    """Whether the next token at pt starts an item or ends a body, or may: at a column point, the open atom may close."""
    T = pt.track
    return T.where == 'body' and not T.form and not T.rec and T.col is None and (pt.place.phase == Phase.ATOM_START or (pt.place.phase == Phase.COLUMN and bool(pt.open_atom)))


def closes_here(pt):
    """Whether an atom that goes by tokens may close at pt."""
    T = pt.track
    return T.where == 'body' and not T.form and not T.rec and T.col is None and pt.place.phase == Phase.COLUMN and bool(pt.open_atom)


def token_choice(pt, ids, probs, costs, rng, closing):
    """The place in ids of the token that an atom going by tokens takes at pt, or None where the atom closes, since the tokens that close it share one option and the next atom is one choice. With closing, the search has chosen to close the atom before this one, and the tokens that close it are the options."""
    cl = closers(writer.core_of(pt.run), ids)
    if closing:
        at = np.flatnonzero(cl)
        p = probs[at] / probs[at].sum()
        return int(at[0 if len(at) == 1 else rng.node(p, None if costs is None else costs[at], None)])
    rest = np.flatnonzero(~cl)
    if not cl.any():
        return int(rest[rng.node(probs, costs, None)])
    if not len(rest):
        return None
    p = np.append(probs[rest], probs[cl].sum())
    j = rng.node(p, None if costs is None else np.append(costs[rest], 0.0), None)
    return None if j == len(rest) else int(rest[j])


def structure(core, tokens):
    n = dict.fromkeys(STRUCT, 0)
    n['n_tokens'] = len(tokens)
    for t in tokens:
        if core.is_column[t]:
            n['n_columns'] += 1
        elif t == M.STAR:
            n['n_fresh'] += 1
        elif t == M.CARET:
            n['n_key'] += 1
        elif core.is_label[t]:
            n['n_join'] += 1
        elif t == M.ZERO:
            n['n_zero'] += 1
    first = tokens[0]
    n['negated'] = first == M.NOT
    n['is_end'] = first == M.END
    n['is_group'] = first == M.OR or first == core.ALL or first == core.IF
    n['is_comparison'] = first in M.CMP
    return [float(n[k]) for k in STRUCT]


def body_vector(pt):
    """The AssignmentVector of the body at pt, and whether the engine gives one."""
    if pt.track.where != 'body':
        return None, False
    cur = writer.current_body(pt)
    return writer._av_of(None if cur is None else cur.table.rows), cur is not None


def token_probs(cur, plan):
    """(ids, chance of each, bits off the bound of each or None) at point cur, as the token writer gives them: after the plan's caps and lookahead. No ids at a cap."""
    ids, fac, reason = writer.options(cur, plan)
    if reason or not len(ids):
        return ids[:0], np.ones(0), None
    if len(ids) == 1:
        return ids, np.ones(1), None
    return (ids, *writer.probabilities(cur, plan, ids, fac))


def top_atoms(pt, want, core, plan, skip=frozenset()):
    """The atoms that the token tree ranks highest from decision pt, most likely first: [(tokens, the point at its end, bits, bits off the bound)]. A best-first walk over tokens, where an atom ends at a column point that can close, at the next atom start, or where the body ends. It steps a token only when the token comes off the heap, so the walk pays for no point that it doesn't reach. An item is (bound, count, token or FINISHED, tokens, the point at them, bits, cost)."""
    heap, count, out, pops, stepped, found = [(0.0, 0, None, (), pt, 0.0, 0.0)], 1, [], 0, 0, 0.0
    while heap and len(out) < want and pops < want * POPS and found < ENOUGH:
        _, _, t, tokens, cur, bits, cost = heapq.heappop(heap)
        pops += 1
        if t == FINISHED:
            out.append((list(tokens), cur, bits, cost))
            found += 2.0 ** -bits
            continue
        if t is not None:
            try:
                cur = writer.step_point(cur, t)
            except Exception:  # noqa: BLE001 - a refused token: no candidate there
                continue
            stepped += 1
            tokens = tokens + (t,)
            if cur.track.where != 'body' or (len(tokens) == 1 and is_group_token(core, t)) or (cur.place.phase == Phase.ATOM_START and tokens != (M.NOT,)):
                if tokens not in skip:
                    out.append((list(tokens), cur, bits, cost))
                    found += 2.0 ** -bits
                continue
        ids, prob, costs = token_probs(cur, plan)
        if not len(ids):
            continue
        if not tokens and cur.place.phase == Phase.COLUMN:  # the decision closes the open atom: its candidates start another item or end the body
            cl = closers(core, ids)
            if not cl.any():
                continue
            ids, prob, costs = ids[cl], prob[cl] / prob[cl].sum(), None if costs is None else costs[cl]
        elif tokens and cur.place.phase == Phase.COLUMN and not cur.track.rec and cur.track.col is None:
            cl = closers(core, ids)
            if cl.any():
                if tokens not in skip:
                    b = bits - float(np.log2(max(float(prob[cl].sum()), 1e-9)))
                    heapq.heappush(heap, (b + cost, count, FINISHED, tokens, cur, b, cost))
                    count += 1
                ids, prob, costs = ids[~cl], prob[~cl], None if costs is None else costs[~cl]
        for j in np.flatnonzero(prob >= MIN_CHANCE).tolist():
            nb, nc = bits - float(np.log2(float(prob[j]))), cost + (0.0 if costs is None else float(costs[j]))
            heapq.heappush(heap, (nb + nc, count, int(ids[j]), tokens, cur, nb, nc))
            count += 1
    out.sort(key=lambda x: x[2] + x[3])
    STATS['pops'] += pops
    STATS['steps'] += stepped
    return out


def rows_of(pt, cands, core):
    """(the decision's point columns, tok, struct, defined, av, delta) of candidates [(tokens, end point, ...)], leaving out a candidate whose first token isn't scored at pt. Also the candidates kept."""
    run = pt.run
    _, _, point_at, tok_at = names_of(run)
    ids = writer.point_ids(pt)
    X = writer.Features(pt, ids).vectors()
    base, base_defined = body_vector(pt)
    if base is None:
        base = np.zeros(len(writer.AV_NAMES), np.float32)
    keep, tok, struct, defined, av, delta = [], [], [], [], [], []
    for c in cands:
        at = np.flatnonzero(ids == c[0][0])
        if not len(at):
            continue
        v, d = body_vector(c[1])
        if v is None:
            v, d = base, base_defined
        keep.append(c); tok.append(X[at[0]][tok_at]); struct.append(structure(core, c[0])); defined.append(float(d)); av.append(v); delta.append(v - base)
    if not keep:
        return None
    return X[0][point_at], np.stack(tok), np.array(struct, np.float32), np.array(defined, np.float32), np.stack(av), np.stack(delta), keep


def set_columns(bits, first):
    """A candidate's place in its set: its rank by the tree's bits, its share of the set's mass, the candidates with its first token, and their share. n x len(SET_NAMES)."""
    share = 2.0 ** -(bits - bits.min())
    share = share / share.sum()
    rank = np.argsort(np.argsort(bits, kind='stable'), kind='stable')
    first = np.asarray(first)
    same = first[:, None] == first[None, :]
    return np.stack([rank, share, same.sum(1), (same * share[None, :]).sum(1)], 1).astype(np.float32)


class TreeScore:
    def __init__(self, path):
        import tree_dist
        lightgbm = tree_dist.import_lightgbm()
        self.booster = lightgbm.Booster(model_file=path)
        self.uses = json.load(open(os.path.splitext(path)[0] + '.uses.json'))
        self.columns = None

    def score(self, run, point, tok, struct, defined, av, delta, bits, first):
        if self.columns is None:
            point_names, token_names, _, _ = names_of(run)
            names = point_names + token_names + ['atom:' + x for x in STRUCT] + ['atom:defined', 'atom:bits', 'atom:bits_gap'] + SET_NAMES + ['a:' + x for x in writer.AV_NAMES] + ['d:' + x for x in writer.AV_NAMES] + ['r:' + x for x in writer.AV_NAMES]
            at = {n: i for i, n in enumerate(names)}
            self.columns = np.array([at[n] for n in self.uses])
        n = len(tok)
        rows = np.concatenate([np.broadcast_to(point, (n, len(point))), tok, struct, defined[:, None], bits[:, None], (bits - bits.min())[:, None], set_columns(bits, first), av, delta, av - av.mean(0, keepdims=True)], 1)
        return np.asarray(self.booster.predict(rows[:, self.columns], raw_score=True, num_threads=1), np.float64)


class ServerScore:
    def __init__(self, socket):
        sys.path.insert(0, os.environ['WRITER_ATOM_SERVER_DIR'])
        from atom_serve import Client
        self.client = Client(socket)

    def score(self, run, point, tok, struct, defined, av, delta, bits, first):
        cands = np.concatenate([tok, struct, defined[:, None], av, delta, bits[:, None] / 10.0, (bits - bits.min())[:, None] / 10.0], 1)
        wall, cpu = time.perf_counter(), time.process_time()
        got = np.asarray(self.client.score(point, cands), np.float64)
        blocked = max(0.0, (time.perf_counter() - wall) - (time.process_time() - cpu))
        if hasattr(time, 'blocked_seconds'):
            time.blocked_seconds += blocked
            os.environ['ARC_BLOCKED_SECONDS'] = repr(time.blocked_seconds)
        STATS['blocked seconds'] += blocked
        STATS['requests'] += 1
        STATS['rows'] += len(cands)
        return got


MODEL = []


def model():
    if not MODEL:
        if os.environ.get('WRITER_ATOM_TREE'):
            MODEL.append(TreeScore(os.environ['WRITER_ATOM_TREE']))
        elif os.environ.get('WRITER_ATOM_SOCKET'):
            MODEL.append(ServerScore(os.environ['WRITER_ATOM_SOCKET']))
        else:
            MODEL.append(None)
    return MODEL[0]


def choose(pt, plan, rng):
    """The point after the atom that the search takes at decision pt, or None where this atom goes by tokens: there's no atom to choose among, or the search takes the mass outside the proposals. The model shares out among the proposals all the mass but that option's."""
    run = pt.run
    core = writer.core_of(run)
    held = pt.memo.get('atoms')
    if held is None:
        t0 = time.process_time()
        cands = top_atoms(pt, K, core, plan)
        got = rows_of(pt, cands, core) if cands else None
        if got is None:
            pt.memo['atoms'] = held = ()
            STATS['no candidates'] += 1
        else:
            point, tok, struct, defined, av, delta, keep = got
            s = model().score(run, point, tok, struct, defined, av, delta, np.array([c[2] for c in keep], np.float32), [c[0][0] for c in keep])
            s = np.round(s / ROUND) * ROUND
            e = np.exp(s - s.max())
            covered = min(1.0, sum(2.0 ** -c[2] for c in keep))
            outside = ESCAPE * (1.0 - covered)
            probs = e / e.sum() * (1.0 - outside)
            costs = [c[3] for c in keep]
            if outside > 0.0:  # a path that writes a proposed atom by tokens dies at its close, so the bound of an atom outside is ESCAPE times its chance under the tree
                probs, costs = np.append(probs, outside), costs + [float(np.log2(1.0 - covered))]
            held = pt.memo['atoms'] = (keep, probs, np.array(costs) if any(costs) else None)
            STATS['decisions'] += 1
            STATS['candidates'] += len(keep)
            STATS['covered'] += covered
            STATS['seconds'] += time.process_time() - t0
            if LOG_DIR and STATS['decisions'] % 100 == 1:
                with open(os.path.join(LOG_DIR, '%d.json' % os.getpid()), 'w') as f:
                    json.dump(dict(argv=sys.argv[1:], stats=STATS, cpu=time.process_time()), f)
    if not held:
        return None
    keep, probs, costs = held
    j = 0 if len(probs) == 1 else rng.node(probs, costs, None)
    if j == len(keep):
        STATS['by tokens'] += 1
        return None
    return keep[j][1]
