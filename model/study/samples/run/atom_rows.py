#!/usr/bin/env python
"""atom_rows.py OUT SET SKELETON TASK... [--negatives N] [--tree MODEL] [--samples K]: rows for scoring a whole atom at each point of a target's canonical path, with negatives that the tree ranks highest, for a read of what the table with the atom added says. 

Candidates are the tree's proposals of atom_writer.top_atoms, which the live writer uses. A decision is a point whose next token starts an item or ends a body. A candidate is a list of tokens from that point to the point where the atom could close. Its row holds the decision's point columns, the columns of its relation token, the atom's structure, and the AssignmentVector of the body with the atom added, with its difference from the body before. With --tree, a candidate also has the bits of its tokens under that tree. One zstd JSON line per decision, one file per task. A rerun skips the finished tasks.

Run with the kit's runtime python and with the overlay's sampler and samples folders first on PYTHONPATH."""
import argparse, base64, hashlib, heapq, io, json, os, random, sys, time, types
from pathlib import Path
import numpy as np
import zstandard
import live, live_try, writer, train_rows, order, lookahead
import importlib
from lookahead import closers, starts

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('set'); ap.add_argument('skeleton'); ap.add_argument('tasks', nargs='+'); ap.add_argument('--negatives', type=int, default=16); ap.add_argument('--tree'); ap.add_argument('--samples', type=int, default=6); ap.add_argument('--targets', type=int, default=8); ap.add_argument('--first-only', action='store_true', help='only the decisions at the first item of a body, with a file <task>.first.atoms.zst'); ap.add_argument('--tables', action='store_true', help='also write <task>.tables.zst, a line per decision in the order of the rows, with the body table and each candidate table')
a = ap.parse_args()
live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
pw = importlib.import_module('points_write')
M = writer.M
Phase = writer.Phase
import atom_writer as AW
STRUCT = AW.STRUCT
STARTS = AW.__dict__.get('START_PHASES', (Phase.ATOM_START,))
import tree_dist
TREE = tree_dist.load(a.tree)


COUNT = [0]
TABLES = [None]


def table_json(pt):
    """A body's table at a point, as plain lists; None where the engine gives none."""
    cur = writer.current_body(pt) if pt.track.where == 'body' else None
    if cur is None or cur.table is None:
        return None
    return [dict(slot=t.slot, name=t.name, labels=t.labels, types=t.types, at=[dict(hash=x.hash, capped=x.capped, entries=[[e.kind, e.index, e.model, e.complete, e.n, None if e.rows is None else e.rows.reshape(-1).tolist()] for e in x.entries]) for x in t.at]) for t in writer.export_tables(cur.table.ct, all_tables=True)]


def b64(x):
    return base64.b64encode(np.asarray(x, np.float32).tobytes()).decode()


def closes(core, t):
    return bool(closers(core, np.array([t]))[0])


def token_bits(pt, t, plan):
    ids, prob, _ = AW.token_probs(pt, plan)
    at = np.flatnonzero(ids == t)
    return float(-np.log2(max(float(prob[at].sum()), 1e-9))) if len(at) else 30.0


def close_bits(pt, core, plan):
    ids, prob, _ = AW.token_probs(pt, plan)
    return float(-np.log2(max(float(prob[closers(core, ids)].sum()), 1e-9))) if len(ids) else 0.0


def process_target(run, core, plan, sink, task, sample, scope, kind, stream, target):
    stream = [int(t) for t in stream]
    if stream and stream[0] == live.KIND_TOK[kind]:
        stream = stream[1:]
    dec, pg = run.scope(scope)
    pg.new = []
    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    i = 0
    n = 0
    inside = 0
    while i < len(stream):
        t = stream[i]
        if pt.track.where == 'done' or t not in pt.ids_:
            return n
        if i >= inside and AW.decision(pt) and (pt.place.phase in STARTS or closes(core, t)) and (not a.first_only or pt.place.phase == Phase.PROPOSER):
            ids = writer.point_ids(pt)
            if t in ids.tolist() and len(ids) >= 2:
                # the positive: its tokens up to the next decision on the path
                j = i + 1
                probe = writer.step_point(pt, t)
                pos_bits = token_bits(pt, t, plan)
                if pt.place.phase == Phase.COLUMN:  # the proposals' first tokens are the closers' chances, shared out to 1
                    pos_bits -= close_bits(pt, core, plan)
                if not AW.is_group_token(core, t):
                    while j < len(stream):
                        u = stream[j]
                        if probe.track.where != 'body' or u not in probe.ids_:
                            break
                        if probe.place.phase in STARTS and stream[i:j] != [M.NOT]:
                            break
                        if probe.place.phase == Phase.COLUMN and not probe.track.rec and probe.track.col is None and closes(core, u):
                            pos_bits += close_bits(probe, core, plan)
                            break
                        pos_bits += token_bits(probe, u, plan)
                        probe = writer.step_point(probe, u)
                        j += 1
                gold = stream[i:j]
                inside = j  # the atom holds no decision of its own, as after a NOT
                try:
                    tops = AW.top_atoms(pt, a.negatives, core, plan, skip={tuple(gold)})
                except Exception as e:
                    print('proposal failed', type(e).__name__, str(e)[:100], flush=True)
                    tops = []
                got = AW.rows_of(pt, [(gold, probe, pos_bits, 0.0)] + tops[:a.negatives], core)
                if got is not None and got[6][0][0] == gold:
                    point, tok, struct, defined, av, delta, keep = got
                    rec = dict(task=task, decision=COUNT[0], sample=sample, target=target, kind=kind, length=len(pt.tokens), n=len(keep), tokens=[c[0] for c in keep], point=b64(point), tok=b64(tok), struct=b64(struct), av=b64(av), delta=b64(delta),
                               defined=[float(x) for x in defined], bits=[c[2] for c in keep], admitted=len(ids), base_defined=float(AW.body_vector(pt)[1]))
                    sink.write(json.dumps(rec) + '\n')
                    if TABLES[0] is not None:
                        TABLES[0](dict(record='decision', task=task, decision=COUNT[0], sample=sample, target=target, kind=kind, length=len(pt.tokens), tokens=[c[0] for c in keep], bits=[c[2] for c in keep], body=table_json(pt), candidates=[table_json(c[1]) for c in keep]))
                    COUNT[0] += 1
                    n += 1
        pt = writer.step_point(pt, t)
        i += 1
    return n


def main():
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    smp = live.Sampler(str(Path(writer.__file__).resolve().parents[3] / 'models-current'), steers=())
    for task in a.tasks:
        path = out / (f'{task}.first.atoms.zst' if a.first_only else f'{task}.atoms.zst')
        if path.exists():
            continue
        t0 = time.time()
        records = [json.loads(x) for x in (Path(a.skeleton) / f'{task}.jsonl').read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        rng = random.Random(f'atoms:{task}')
        rng.shuffle(samples)
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        writer.keep_state_tables(run)
        core = writer.core_of(run)
        point_names, tok_names, _, _ = AW.names_of(run)
        plan = writer.default_plan(run, 3.0, ('legal',), TREE)  # the search's OR_BITS and its plan with a tree
        env = types.SimpleNamespace(live=live, run=run)
        tmp = path.with_suffix('.working')
        n = 0
        dec_order = train_rows.order_env(run)
        COUNT[0] = 0
        table_tmp = out / f'{task}.tables.working'
        table_raw = zstandard.ZstdCompressor(level=3).stream_writer(open(table_tmp, 'wb')) if a.tables else None
        if table_raw is not None:
            def put(record):  # one frame per line, so that a reader takes the finished lines of a file in progress
                table_raw.write((json.dumps(record) + '\n').encode())
                table_raw.flush(zstandard.FLUSH_FRAME)
            TABLES[0] = put
            put(dict(record='header', task=task, names=list(core.names), kinds=list(core.kind)))
        with io.TextIOWrapper(zstandard.ZstdCompressor(level=3).stream_writer(open(tmp, 'wb')), encoding='utf-8') as sink:
            sink.write(json.dumps(dict(record='header', task=task, point_names=point_names, tok_names=tok_names, struct_names=STRUCT, av_names=['a:' + x for x in writer.AV_NAMES])) + '\n')
            for sample in samples[:a.samples]:
                try:
                    texts, label = pw.scope_of(sample['state']['queries'], queries)
                    scope = tuple(texts)
                    dec0, _ = run.scope(scope)
                except Exception:
                    continue
                for h in sample['target_queries'][:a.targets]:
                    try:
                        kind, stream = pw.query_stream(env, scope, pw.rewrite(queries[h], label, f'&r{len(scope)}'))
                        walk, o, why = order.canonical_stream(dec_order, dec0, kind, stream, train_rows.ORDER_SECONDS)
                        n += process_target(run, core, plan, sink, task, sample['id'], scope, kind, walk, h[:8])
                    except Exception as e:
                        print('target failed', task, h[:8], type(e).__name__, str(e)[:120], flush=True)
                sink.flush()
        if table_raw is not None:
            table_raw.close()
            os.replace(table_tmp, out / f'{task}.tables.zst')
        os.replace(tmp, path)
        print(f'{task}: {n} decisions, {time.time() - t0:.1f}s, pops {AW.STATS["pops"]}, steps {AW.STATS["steps"]}', flush=True)


if __name__ == '__main__':
    main()
