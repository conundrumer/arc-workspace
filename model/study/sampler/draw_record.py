"""Draw records of the pool search, for the training rows' negative ids (docs/sample-build/training-rows.md, "Search draws").

kaggle_worker.source installs it where ARC_DRAW_RECORD names a file. Each draw (superdag_search.try_clause: one query the writer wrote
at a slot's scope) appends one JSON line to that file as it ends:

  run fields   task, run (ARC_DRAW_RUN), draw (the pool's draw count), seed, plan ('ordered' or 'unordered', from the tree file's
               name), release (ARC_DRAW_RELEASE), model_sha256 (of WRITER_TREE), site (ARC_DRAW_SITE)
  steps        one entry per query of the program: the scope's queries (with every query they read, ordered by query id), then the
               drawn query. Each has text (as the pool writes it, with &fN names), query_hash (32 hex digits, or null) and state (the
               query_hash of each step before it).
  tables       on a 'new' draw, the drawn query's tables as the pool kept them (superdag.Pool.take), one entry per output: name, dets (the
               QueryHash of each DET its assignments name, 32 hex digits, or the engine's name where it gives none), and at, one row per
               assignment: the value hash of each DET of dets (32 hex digits of its 16 bytes, as the row store writes a value hash), then the
               TableHash (32 hex digits). Null on other draws: an 'equal' draw's QueryHash is a known query's, which gives its tables.
  outcome      ran (the drawn query reached its tables), result ('new', 'equal' or 'none'), failed (null, or the reason the draw ended:
               the counters it raised, such as drop:..., state:no table, error:...), outs (the OUT tries of the draw's OUT search, as
               {kind: count}), best (the kind and message of the best OUT try, Consistent first), per_example (null: the engine's
               Consistency gives no per-example result), solves (an OUT try was Consistent, which holds on every train example)

A draw whose steps' query hashes equal an earlier draw's of the same process writes {"repeat": draw of the first, "draw": its own}
in place of a record, so the count of identical draws is the record plus its repeats.
"""
import collections
import hashlib
import json
import os
import time

import live
import superdag as D
import superdag_search as SS

ORDER = ('Consistent', 'SeveralValues', 'NotConsistent', 'Stopped', 'Fault')  # the best OUT try first
FAILED = ('drop:', 'state:no table', 'state:no TableRows', 'error:', 'panic', 'refused')  # counters whose rise says why a draw ended
STATE = dict(f=None, seen={}, outs=None, fixed=None, tables=None)


def fixed_fields():
    tree = os.environ.get('WRITER_TREE') or ''
    sha = None
    if tree and os.path.exists(tree):
        with open(tree, 'rb') as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    base = os.path.basename(tree)
    plan = 'unordered' if 'unordered' in base else 'ordered' if 'ordered' in base else None
    return dict(run=os.environ.get('ARC_DRAW_RUN'), plan=plan, release=os.environ.get('ARC_DRAW_RELEASE'), model_sha256=sha,
                site=os.environ.get('ARC_DRAW_SITE'))


def hex_of(qh):
    return None if qh is None else '%032x' % qh if isinstance(qh, int) else str(qh)


def scope_steps(pool):
    """The scope's queries and every query they read, by query id, as (text, query hash)."""
    by_id = {fid: qh for qh, fid in pool.defs.items()}
    ids, todo = set(), list(pool.scoped or ())
    while todo:
        f = todo.pop()
        if f in ids or f not in pool.forms:
            continue
        ids.add(f)
        todo.extend(pool.forms[f].parents)
    return [(pool.forms[f].text, hex_of(by_id.get(f))) for f in sorted(ids)]


def drawn_text(pool, clause, nscope):
    """The drawn query's text as take() writes it: the head named &f<next id>, the scope's names as the scope writes them."""
    try:
        line = clause.decoder.program_form().split('\n')[nscope]
        return D.written_names(line, clause.pg.written | {live.head_of(line): '&f%d' % len(pool.forms)})
    except Exception:  # noqa: BLE001
        return clause.text


def try_clause(self, clause, texts, kind):
    c = self.run.c
    before = {k: v for k, v in c.items() if k.startswith(FAILED)}
    nforms, t0 = len(self.forms), time.monotonic()
    text = drawn_text(self, clause, len(texts))
    STATE['outs'], STATE['tables'] = [], None
    try:
        out = _try_clause(self, clause, texts, kind)
    finally:
        outs, STATE['outs'] = STATE['outs'], None
    try:
        write(self, clause, kind, text, out, nforms, before, outs, time.monotonic() - t0)
    except Exception as e:  # noqa: BLE001
        c['draw record:error %s' % type(e).__name__] += 1
    return out


def write(pool, clause, kind, text, out, nforms, before, outs, seconds):
    c = pool.run.c
    steps = scope_steps(pool)
    qh = getattr(clause, 'query_hash', None)
    if qh is None and len(pool.forms) > nforms:
        qh = next((h for h, f in pool.defs.items() if f == nforms), None)
    steps.append((pool.forms[nforms].text if len(pool.forms) > nforms else text, hex_of(qh)))
    key = tuple(h for _, h in steps)
    first = STATE['seen'].get(key) if None not in key else None
    if first is not None:
        line = dict(repeat=first, draw=pool.draws)
    else:
        if None not in key:
            STATE['seen'][key] = pool.draws
        rose = sorted(k for k, v in c.items() if k.startswith(FAILED) and v > before.get(k, 0))
        kinds = collections.Counter(k for k, _ in outs)
        best = min(outs, key=lambda x: ORDER.index(x[0]) if x[0] in ORDER else len(ORDER), default=None)
        line = dict(task=pool.id.split('.')[0], draw=pool.draws, seed=pool.a.seed, kind=kind, **STATE['fixed'],
                    steps=[dict(text=t, query_hash=h, state=[s for _, s in steps[:i]]) for i, (t, h) in enumerate(steps)],
                    ran=out in ('new', 'equal'), result=out, failed=rose or None, outs=dict(kinds),
                    best=dict(kind=best[0], message=best[1]) if best else None, per_example=None,
                    solves=kinds.get('Consistent', 0) > 0, seconds=round(seconds, 3),
                    tables=tables_of(STATE['tables']) if out == 'new' and STATE['tables'] else None)
    STATE['f'].write(json.dumps(line) + '\n')
    STATE['f'].flush()


def qhex(d):
    return '%032x' % d if isinstance(d, int) else str(d)


def tables_of(made):
    """The record's tables field from the AssignmentSummaries of the drawn query, in their order."""
    outs = {}
    for r in made:
        name = r.table[1] if isinstance(r.table, tuple) else str(r.table)
        o = outs.setdefault(name, dict(name=name, dets=[], at=[]))
        for d, _ in r.at:
            if qhex(d) not in o['dets']:
                o['dets'].append(qhex(d))
    for r in made:
        o = outs[r.table[1] if isinstance(r.table, tuple) else str(r.table)]
        vals = {qhex(d): v.to_bytes(16, 'little').hex() if isinstance(v, int) else str(v) for d, v in r.at}
        o['at'].append([vals.get(d) for d in o['dets']] + [None if r.hash is None else '%032x' % r.hash])
    return list(outs.values())


def take(self, f, pg, kind, nscope):
    if STATE['outs'] is not None:  # within a draw: the tables that take keeps for the drawn query
        STATE['tables'] = [r for s in pg.new for r in pg.tables.get(s, ())]
    return _take(self, f, pg, kind, nscope)


def judged(self, f, cons, label):
    if STATE['outs'] is not None:
        kind = str(getattr(cons, 'kind', None)).rsplit('.', 1)[-1]
        STATE['outs'].append((kind, (getattr(cons, 'message', None) or '')[:300]))
    yield from _judged(self, f, cons, label)


def install(path):
    """Patches superdag_search.try_clause, superdag.Pool.take and live.Run.judged to write the draw records to path."""
    global _try_clause, _judged, _take
    STATE['f'], STATE['fixed'] = open(path, 'a'), fixed_fields()
    _try_clause, SS.try_clause = SS.try_clause, try_clause
    _judged, live.Run.judged = live.Run.judged, judged
    _take, D.Pool.take = D.Pool.take, take
