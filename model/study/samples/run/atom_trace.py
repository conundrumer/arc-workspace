#!/usr/bin/env python
"""atom_trace.py OUT SET SKELETON TASK... [--samples K] [--targets N] [--decisions D] [--max-columns C] [--seconds S]: at a target's decisions, every atom that the mask and the order rule admit, found by walking the writer's points, or with --proposals N --tree MODEL the N atoms that the tree ranks highest, with the body table before and the table of each candidate.

A decision is a point of a target's canonical path whose next token starts an item or ends a body. A file per task, as streamable zstd JSON lines, one frame per line: a header {record: 'header', task, names, kinds} of the tokens, then {record: 'decision', task, sample, kind, length, atoms closed, body: TABLE, positive: index in candidates of the gold atom or null, gold, count of atoms found, nodes, counts by first token's kind, truncated, seconds, seconds_tables, candidates: [{tokens, text, table: TABLE or null}]}, where candidates holds at most --max-tables atoms, chosen at random, and the gold atom. TABLE is a list of {slot, name, labels, types, at: [{hash, capped, entries: [[example kind (0 task, 1 train, 2 test), example index, model, complete, row count, cells as a flat int list or null]]}]}, as table_export.read_export gives them. It prints the count and whether the gold atom was found. Run with the kit's runtime python and the overlay's folders first on PYTHONPATH."""
import argparse, collections, importlib, io, json, os, random, time, types
from pathlib import Path
import numpy as np
import zstandard
import live, live_try, writer, train_rows, order
from lookahead import closers

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('set'); ap.add_argument('skeleton'); ap.add_argument('tasks', nargs='+'); ap.add_argument('--samples', type=int, default=3); ap.add_argument('--targets', type=int, default=3); ap.add_argument('--decisions', type=int, default=6); ap.add_argument('--max-columns', type=int, default=4); ap.add_argument('--seconds', type=float, default=120.0); ap.add_argument('--no-tables', action='store_true'); ap.add_argument('--max-tables', type=int, default=300); ap.add_argument('--proposals', type=int, default=0); ap.add_argument('--tree'); ap.add_argument('--hashes', action='store_true', help='count the distinct tables over the candidates, and keep no tables')
a = ap.parse_args()
live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
pw = importlib.import_module('points_write')
M, Phase = writer.M, writer.Phase


def closes(core, t):
    return bool(closers(core, np.array([t]))[0])


def table_json(cur):
    """A body's table as plain lists; None where the engine gives none."""
    if cur is None or cur.table is None:
        return None
    out = []
    for t in writer.export_tables(cur.table.ct, all_tables=True):
        out.append(dict(slot=t.slot, name=t.name, labels=t.labels, types=t.types, at=[dict(hash=x.hash, capped=x.capped, entries=[[e.kind, e.index, e.model, e.complete, e.n, None if e.rows is None else e.rows.reshape(-1).tolist()] for e in x.entries]) for x in t.at]))
    return out


def sites_ascending(core, tokens):
    """Whether an atom's sites are in ascending column order. A column followed by a column opens a record, which an END closes."""
    depth, last = 0, [-1]
    for i, t in enumerate(tokens):
        name = core.names[t]
        if name == 'END' and depth:
            depth -= 1
            last.pop()
        elif core.is_column[t]:
            k = int(name[1:])
            if k <= last[-1]:
                return False
            last[-1] = k
            if i + 1 < len(tokens) and core.is_column[tokens[i + 1]]:
                depth += 1
                last.append(-1)
    return True


STEPS = []


def enumerate_atoms(pt, core, deadline, cap):
    """[(tokens, the point at its end)] of every atom from pt through the mask and the order rule, depth first, ids ascending. An atom ends at a column point that can close."""
    out, nodes = [], [0]
    truncated = [False]

    def walk(cur, tokens, columns):
        if time.monotonic() > deadline:
            truncated[0] = True
            return
        if cur.track.where != 'body' or (cur.place.phase == Phase.ATOM_START and tokens != [M.NOT]):  # the atom has ended, or a group has started
            out.append((tokens, cur))
            return
        ids = writer.point_ids(cur)
        nodes[0] += 1
        if not len(ids):
            return
        ph = cur.place.phase
        if ph == Phase.COLUMN and not cur.track.rec and cur.track.col is None:
            cl = closers(core, ids)
            if cl.any():
                out.append((tokens, cur))
            ids = ids[~cl]
            if columns >= cap:
                return
            next_columns = columns + 1
        else:
            next_columns = columns
        for t in ids.tolist():
            if time.monotonic() > deadline:
                truncated[0] = True
                return
            t_step = time.perf_counter()
            try:
                nxt = writer.step_point(cur, int(t))
            except Exception:
                continue
            STEPS.append((time.perf_counter() - t_step, tokens + [int(t)]))
            walk(nxt, tokens + [int(t)], next_columns)

    ids = writer.point_ids(pt)
    if pt.place.phase == Phase.COLUMN:
        ids = ids[closers(core, ids)]
    for t in ids.tolist():
        if time.monotonic() > deadline:
            truncated[0] = True
            break
        t = int(t)
        if t == M.END or t == M.OR or t == core.ALL or t == core.IF or t == live.ALSO_TOK:
            try:
                out.append(([t], writer.step_point(pt, t)))
            except Exception:
                pass
            continue
        if not (core.is_rel[t] or t == M.NOT or t in M.CMP):
            continue
        try:
            walk(writer.step_point(pt, t), [t], 0)
        except Exception:
            continue
    return out, nodes[0], truncated[0]


def main():
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    smp = live.Sampler(str(Path(writer.__file__).resolve().parents[3] / 'models-current'), steers=())
    for task in a.tasks:
        path = out / f'{task}.trace.zst'
        if path.exists():
            continue
        records = [json.loads(x) for x in (Path(a.skeleton) / f'{task}.jsonl').read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        rng = random.Random(f'trace:{task}')
        rng.shuffle(samples)
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 864000, d, live.Limits())
        writer.keep_state_tables(run)
        core = writer.core_of(run)
        env = types.SimpleNamespace(live=live, run=run)
        dec_order = train_rows.order_env(run)
        plan = None
        if a.proposals:
            import atom_writer as AW, tree_dist
            plan = writer.default_plan(run, 3.0, None, tree_dist.load(a.tree))
        tmp = path.with_suffix('.working')
        done = 0
        with zstandard.ZstdCompressor(level=3).stream_writer(open(tmp, 'wb')) as raw:
            def put(record):  # one frame per line, so that a reader takes the finished lines of a file in progress
                raw.write((json.dumps(record) + '\n').encode())
                raw.flush(zstandard.FLUSH_FRAME)
            put(dict(record='header', task=task, names=list(core.names), kinds=list(core.kind)))
            print(f'{task}: session ready', flush=True)
            for sample in samples[:a.samples]:
                if done >= a.decisions:
                    break
                texts, label = pw.scope_of(sample['state']['queries'], queries)
                scope = tuple(texts)
                dec0, _ = run.scope(scope)
                for h in sample['target_queries'][:a.targets]:
                    if done >= a.decisions:
                        break
                    kind, stream = pw.query_stream(env, scope, pw.rewrite(queries[h], label, f'&r{len(scope)}'))
                    t_order = time.monotonic()
                    walk, _, _ = order.canonical_stream(dec_order, dec0, kind, stream, min(train_rows.ORDER_SECONDS, 30.0))
                    print(f'{task} {kind}: canonical order {time.monotonic() - t_order:.1f} s, {len(walk)} tokens', flush=True)
                    walk = [int(t) for t in walk]
                    if walk and walk[0] == live.KIND_TOK[kind]:
                        walk = walk[1:]
                    dec, pg = run.scope(scope)
                    pg.new = []
                    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
                    i = 0
                    while i < len(walk) and done < a.decisions:
                        t = walk[i]
                        if pt.track.where == 'done' or t not in pt.ids_:
                            break
                        ph = pt.place.phase
                        decision = pt.track.where == 'body' and ph in (Phase.ATOM_START, Phase.COLUMN) and (ph == Phase.ATOM_START or closes(core, t)) and not pt.track.rec and pt.track.col is None
                        if decision:
                            j, probe = i + 1, writer.step_point(pt, t)
                            while j < len(walk) and t not in (M.END, M.OR, core.ALL, core.IF, live.ALSO_TOK):
                                u = walk[j]
                                if probe.track.where == 'done' or u not in probe.ids_:
                                    break
                                if probe.place.phase == Phase.COLUMN and not probe.track.rec and probe.track.col is None and closes(core, u):
                                    break
                                probe = writer.step_point(probe, u)
                                j += 1
                            gold = walk[i:j]
                            t0 = time.monotonic()
                            if a.proposals:
                                cands, nodes, truncated = [(c[0], c[1]) for c in AW.top_atoms(pt, a.proposals, core, plan, branch=8)], 0, False
                            else:
                                cands, nodes, truncated = enumerate_atoms(pt, core, t0 + a.seconds, a.max_columns)
                            spent = time.monotonic() - t0
                            at = next((k for k, c in enumerate(cands) if c[0] == gold), None)
                            kinds = collections.Counter(core.kind[c[0][0]] for c in cands)
                            hashes = None
                            if a.hashes:
                                t1 = time.monotonic()
                                keys, instances, none, per, unhashed = set(), set(), 0, [], 0
                                for tokens, end in cands:
                                    cur = writer.current_body(end) if end.track.where == 'body' else None
                                    if cur is None or cur.table is None:
                                        none += 1
                                        continue
                                    T = cur.table.ct.tables
                                    n = len(T['form'])
                                    hash_bytes, flag = bytes(memoryview(T['hash']).cast('B')), bytes(memoryview(T['hashed']).cast('B'))
                                    held = [hash_bytes[r * 16:r * 16 + 16] for r in range(n)]
                                    unhashed += sum(1 for r in range(n) if not flag[r])
                                    keys.add(tuple(sorted(held)))
                                    instances.update(held)
                                    per.append(n)
                                hashes = dict(atoms=len(cands), not_ascending=sum(not sites_ascending(core, c[0]) for c in cands), no_table=none, distinct_tables=len(keys), distinct_instances=len(instances), mean_instances=float(np.mean(per)) if per else 0.0, unhashed=unhashed, seconds=time.monotonic() - t1)
                                print(task, kind, 'atoms closed', pt.place.atoms, hashes, 'walk points', nodes, 'walk seconds', round(spent, 1), 'truncated', truncated, flush=True)
                            t1 = time.monotonic()
                            chosen = range(len(cands)) if not a.hashes else []
                            if len(cands) > a.max_tables:
                                chosen = sorted(set(rng.sample(range(len(cands)), a.max_tables)) | ({at} if at is not None else set()))
                            rows = [dict(tokens=cands[k][0], text=' '.join(core.names[x] for x in cands[k][0]), table=None if a.no_tables or cands[k][1].track.where != 'body' else table_json(writer.current_body(cands[k][1]))) for k in chosen]
                            spent_tables = time.monotonic() - t1
                            put(dict(record='decision', task=task, sample=sample['id'], kind=kind, length=len(pt.tokens), atoms=pt.place.atoms, body=table_json(writer.current_body(pt)), positive=None if at is None or a.hashes else list(chosen).index(at), gold=gold, hashes=hashes, count=len(cands), nodes=nodes, counts=dict(kinds), truncated=truncated, seconds=spent, seconds_tables=spent_tables, candidates=rows))
                            print(f'{task} {kind} atoms closed {pt.place.atoms}: {len(cands)} candidates, {nodes} points walked, {spent:.1f} s, {len(rows)} tables {spent_tables:.1f} s, gold {"found" if at is not None else "NOT found: " + " ".join(core.names[x] for x in gold)}{", truncated" if truncated else ""}', flush=True)
                            if STEPS and os.environ.get('TRACE_SLOW'):
                                STEPS.sort(key=lambda x: -x[0])
                                print('steps', len(STEPS), 'seconds', round(sum(x[0] for x in STEPS), 2), 'median ms', round(1000 * STEPS[len(STEPS) // 2][0], 2))
                                for sec, toks in STEPS[:14]:
                                    print('  %.0f ms: %s' % (1000 * sec, ' '.join(core.names[x] for x in toks)))
                                STEPS.clear()
                            done += 1
                        pt = writer.step_point(pt, t)
                        i += 1
        os.replace(tmp, path)


if __name__ == '__main__':
    main()
