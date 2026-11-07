#!/usr/bin/env python
"""atom_rows_full.py OUT SET SKELETON TASK... [--samples K] [--targets N]: whole-atom rows over a decision's full candidate set: every atom that Decoder.atoms lists, with its table from arclog.atom_tables, and the mask's tokens that start no atom in the list (group tokens, proposers, the first token of a comparison).

A file per task, <task>.full.zst, streamable zstd JSON lines. The first line is the header: {record: 'header', task, point_names, tok_names, av_names}. Each other line is one decision: {task, decision, sample, target, kind, length, phase, positive: the true candidate's place or null, n, tokens: [a token list per candidate], first: [each distinct first token], first_of: [per candidate, its place in first], table_of: [per candidate, its place in tables or -1], point: base64 f4, tok: base64 f4 (first x tok columns), tables: base64 f4 (tables x av columns), base: base64 f4 (the body's av), base_defined, first_bits: [the token tree's bits per entry of first], truncated, over_cap, walk_seconds, table_seconds}. A true atom is matched by its tokens, then by the same tokens in another site order, which is counted in `twin`. A rerun skips the finished tasks. Run with the kit's runtime python, the overlay's folders and a site with Decoder.atoms first on PYTHONPATH."""
import argparse, base64, importlib, io, json, os, random, time, types
from pathlib import Path
import numpy as np
import zstandard
import live, live_try, writer, train_rows, order, tree_dist
import atom_writer as AW
from lookahead import closers

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('set'); ap.add_argument('skeleton'); ap.add_argument('tasks', nargs='+'); ap.add_argument('--tree', required=True); ap.add_argument('--samples', type=int, default=4); ap.add_argument('--targets', type=int, default=6); ap.add_argument('--first-only', action='store_true', help='only the first item of a body; a state and kind is written once, and each other target there gives a short line with same_as')
a = ap.parse_args()
live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
pw = importlib.import_module('points_write')
M, Phase = writer.M, writer.Phase
arclog = live.arclog
TREE = tree_dist.load(a.tree)
COUNT = [0]


def b64(x):
    return base64.b64encode(np.asarray(x, '<f4').tobytes()).decode()


def closes(core, t):
    return bool(closers(core, np.array([t]))[0])


def av_of(summary):
    """The AssignmentVector of a summary (capped, hashes, features): one row per assignment."""
    capped, hashes, features = summary
    width = len(writer.ENGINE_FEATURES) if hasattr(writer, 'ENGINE_FEATURES') else None
    f = np.frombuffer(features, '<f4')
    n = len(hashes) // 16
    if n == 0:
        return writer._nan(len(writer.AV_NAMES))
    f = f.reshape(n, -1)
    rows = [(hashes[i * 16:i * 16 + 16].hex() if any(hashes[i * 16:i * 16 + 16]) else None, f[i]) for i in range(n)]
    return writer.assignment_vector(rows, bool(capped))


def candidates(pt, core):
    """(atoms as token lists, the tokens of the mask that start no atom of the list)."""
    atoms, states, truncated = pt.dec.fork().atoms()
    atoms = [list(x) for x in atoms]
    ids = writer.point_ids(pt)
    if pt.place.phase == Phase.COLUMN:
        ids = ids[closers(core, ids)]
    starts = {x[0] for x in atoms} | {x[1] for x in atoms if x[0] == M.NOT and len(x) > 1}
    others = [[int(t)] for t in ids.tolist() if int(t) not in starts]
    return atoms, others, truncated


def process_target(run, core, plan, sink, task, sample, scope, kind, stream, target, seen):
    stream = [int(t) for t in stream]
    if stream and stream[0] == live.KIND_TOK[kind]:
        stream = stream[1:]
    dec, pg = run.scope(scope)
    pg.new = []
    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    _, _, point_at, tok_at = AW.names_of(run)
    i = inside = n = 0
    while i < len(stream):
        t = stream[i]
        if pt.track.where == 'done' or t not in pt.ids_:
            return n
        if i >= inside and AW.decision(pt) and (pt.place.phase in AW.START_PHASES or closes(core, t)):
            j, probe = i + 1, writer.step_point(pt, t)
            if not AW.is_group_token(core, t):
                while j < len(stream):
                    u = stream[j]
                    if probe.track.where != 'body' or u not in probe.ids_:
                        break
                    if probe.place.phase in AW.START_PHASES and stream[i:j] != [M.NOT]:
                        break
                    if probe.place.phase == Phase.COLUMN and not probe.track.rec and probe.track.col is None and closes(core, u):
                        break
                    probe = writer.step_point(probe, u)
                    j += 1
            gold = stream[i:j]
            inside = j
            key = (sample, kind, pt.tokens)
            if a.first_only and key in seen:
                held = seen[key]
                positive, twin = held['place'].get(tuple(gold)), False
                if positive is None:
                    positive = held['sorted'].get(tuple(sorted(gold)))
                    twin = positive is not None
                if positive is None and (gold[0] in M.CMP or (gold[0] == M.NOT and len(gold) > 1 and gold[1] in M.CMP)):
                    positive = held['place'].get((gold[0],))
                sink.write(json.dumps(dict(task=task, decision=COUNT[0], same_as=held['decision'], sample=sample, target=target, kind=kind, positive=positive, twin=twin, gold=gold)) + '\n')
                COUNT[0] += 1
                return n + 1
            t0 = time.process_time()
            atoms, others, truncated = candidates(pt, core)
            t1 = time.process_time()
            index, summaries, by_program, over = arclog.atom_tables(pt.dec.fork(), atoms, *live.TABLES, before=pg.before) if atoms else ([], [], 0, [])
            t2 = time.process_time()
            tokens = atoms + others
            place = {tuple(x): k for k, x in enumerate(tokens)}
            positive, twin = place.get(tuple(gold)), False
            if positive is None:
                by_sorted = {}
                for k, x in enumerate(tokens):
                    by_sorted.setdefault(tuple(sorted(x)), k)
                positive = by_sorted.get(tuple(sorted(gold)))
                twin = positive is not None
            if positive is None and (gold[0] in M.CMP or (gold[0] == M.NOT and len(gold) > 1 and gold[1] in M.CMP)):  # a comparison's first token stands for it
                positive = place.get((gold[0],))
            ids = writer.point_ids(pt)
            X = writer.Features(pt, ids).vectors()
            at = {int(x): k for k, x in enumerate(ids.tolist())}
            first_token = lambda x: x[1] if x[0] == M.NOT and len(x) > 1 else x[0]
            first = sorted({first_token(x) for x in tokens if first_token(x) in at} | {x[0] for x in tokens if x[0] in at})
            first_place = {x: k for k, x in enumerate(first)}
            keep = [k for k, x in enumerate(tokens) if x[0] in first_place]
            remap = {old: new for new, old in enumerate(keep)}
            tokens = [tokens[k] for k in keep]
            table_of = [(-1 if k >= len(atoms) or index[k] is None else int(index[k])) for k in keep]
            used = sorted({x for x in table_of if x >= 0})
            table_place = {x: k for k, x in enumerate(used)}
            table_of = [table_place.get(x, -1) for x in table_of]
            base, base_defined = AW.body_vector(pt)
            if base is None:
                base = writer._nan(len(writer.AV_NAMES))
            prob_ids, prob, _ = AW.token_probs(pt, plan)
            chance = dict(zip(prob_ids.tolist(), prob.tolist()))
            first_bits = [float(-np.log2(max(chance.get(x, 0.0), 1e-9))) for x in first]
            if a.first_only:
                by_sorted = {}
                for k, x in enumerate(tokens):
                    by_sorted.setdefault(tuple(sorted(x)), k)
                seen[key] = dict(decision=COUNT[0], place={tuple(x): k for k, x in enumerate(tokens)}, sorted=by_sorted)
            sink.write(json.dumps(dict(task=task, decision=COUNT[0], sample=sample, target=target, kind=kind, length=len(pt.tokens), phase=pt.place.phase.name, positive=None if positive is None else remap.get(positive), twin=twin, gold=gold, n=len(tokens), tokens=tokens, first=first, first_of=[first_place[first_token(x) if first_token(x) in first_place else x[0]] for x in tokens], table_of=table_of, point=b64(X[0][point_at]), tok=b64(X[[at[x] for x in first]][:, tok_at]), tables=b64(np.stack([av_of(summaries[x]) for x in used])) if used else '', base=b64(base), base_defined=float(base_defined), first_bits=first_bits, truncated=bool(truncated), over_cap=len(over), walk_seconds=t1 - t0, table_seconds=t2 - t1)) + '\n')
            COUNT[0] += 1
            n += 1
            if a.first_only:
                return n
        pt = writer.step_point(pt, t)
        i += 1
    return n


def load_verdicts():
    """The walk's verdicts that earlier batches kept (WRITER_ROW_VERDICTS), so that a new process doesn't walk cold."""
    path = os.environ.get('WRITER_ROW_VERDICTS')
    if path and os.path.exists(path):
        arclog.add_atom_verdicts(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')).read())


def keep_verdicts():
    path = os.environ.get('WRITER_ROW_VERDICTS')
    if path:
        tmp = '%s.%d' % (path, os.getpid())
        with open(tmp, 'wb') as f:
            f.write(zstandard.ZstdCompressor(level=3).compress(arclog.atom_verdicts()))
        os.replace(tmp, path)


def main():
    load_verdicts()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    smp = live.Sampler(str(Path(writer.__file__).resolve().parents[3] / 'models-current'), steers=())
    for task in a.tasks:
        path = out / f'{task}.full.zst'
        if path.exists():
            continue
        t0 = time.time()
        records = [json.loads(x) for x in (Path(a.skeleton) / f'{task}.jsonl').read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        random.Random(f'atoms:{task}').shuffle(samples)
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        writer.keep_state_tables(run)
        core = writer.core_of(run)
        plan = writer.default_plan(run, 3.0, ('legal',), TREE)
        point_names, tok_names, _, _ = AW.names_of(run)
        env = types.SimpleNamespace(live=live, run=run)
        tmp = path.with_suffix('.working')
        n = 0
        COUNT[0] = 0
        seen = {}
        dec_order = train_rows.order_env(run)
        with io.TextIOWrapper(zstandard.ZstdCompressor(level=3).stream_writer(open(tmp, 'wb')), encoding='utf-8') as sink:
            sink.write(json.dumps(dict(record='header', task=task, point_names=point_names, tok_names=tok_names, struct_names=AW.STRUCT, av_names=['a:' + x for x in writer.AV_NAMES])) + '\n')
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
                        walk, _, _ = order.canonical_stream(dec_order, dec0, kind, stream, train_rows.ORDER_SECONDS)
                        n += process_target(run, core, plan, sink, task, sample['id'], scope, kind, walk, h[:8], seen)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException as e:  # noqa: BLE001 - the engine's panic is a BaseException
                        print('target failed', task, h[:8], type(e).__name__, str(e)[:160], flush=True)
                sink.flush()
        os.replace(tmp, path)
        print(f'{task}: {n} decisions, {time.time() - t0:.1f}s', flush=True)
    keep_verdicts()


if __name__ == '__main__':
    main()
