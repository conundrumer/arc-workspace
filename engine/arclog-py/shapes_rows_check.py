"""Checks that a table's stored rows give the shape vector that `TableShapes.vector` gives: shapes_rows_check.py TASK MUTANTS.json.zst --encoder FEATURE_ENCODER [options]

MUTANTS.json.zst is the task's file of the feature corpus (`all-merged/<set>/mutants/<task>.json.zst`), whose field `gold` is the standalone gold program. The program is decoded on a
closed-world session of the task, and `step_tables` is called at each model step. For each chosen table (one for each distinct TableHash):
- `TableShapes.rows()` is called twice and must give the same bytes. With `--digest-out FILE` the sha256 of each table's bytes is written, and with `--digest-in FILE` each is compared with
  the digest of an earlier run, which is how a run under `ARCLOG_MAP_SEED=1` is held to the bytes of one without.
- The tables' rows go to a rows file, whose header names the producers of the engine in use, and `feature-encoder shapes-refresh` reads them and writes the `shapes` records of the full
  vector, and of a list of shapes. The encoder reads the file only where the producers are its own, so the site and the encoder must come from one build.
- Each record must have the shape hashes, the f32 least, mean and most (`values[:, 0:3]`) and the `stopped` flag of `TableShapes.vector()` for the full vector and `vector(only=LIST)`, byte for byte.

Options:
  --known KNOWN.jsonl   the table that holds the shapes of `known_values.py`'s file is chosen (the most equal values under `only=`), and the list is those shapes.
  --tables N            the first N distinct tables by the size of their rows, the smallest first (default: 0 with --known, otherwise 3).
  --stopped             also the largest tables by the size of their rows, full-walked in that order until one has `stopped` or `--max-walks` have been walked (default 4).
  --repo DIR            where `data/tasks/<task>.json` stands (default: ARC_ROOT, or the main checkout).
  --work DIR            where the rows file and the records go (default: a new temporary folder).
  --threads N           the encoder's thread count (default 1).
  --export FILE         instead of the check, write the rows file (zstd JSON lines) of every distinct table of the program, or with --export-hashes H,H,.. of those tables (a TableHash as 32 hex digits
                        of its bytes), and stop. `feature-encoder shapes-refresh` names each table so.
It prints counts and seconds only: no row and no value. The exit status is 1 where any table differs. Run it with the runtime python of the engine, which has `arclog`, `numpy` and `zstandard`.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import zstandard

import arclog

LIST_SIZE = 200


def steps(task, task_text, gold):
    """The (step, row, TableShapes, TableHash bytes) of each table of each model step of the gold program, the first of each TableHash only."""
    sess = arclog.Session(arclog.Task.from_json(task_text, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
    ids, model, _ = arclog.StudyProgram.from_sexp(gold, sess.settings).decode_stream()
    dec = sess.decoder()
    before, seen, stepped = None, set(), 0
    try:
        for token, written in zip(ids, model):
            if not written:
                continue
            dec.step(token)
            before = arclog.step_tables(dec, task, 'solver', False, before, True, False)
            stepped += 1
            column = bytes(memoryview(before.tables['hash']))
            for row in range(len(before.tables['form'])):
                shapes = before.shapes(row)
                key = column[row * 16:(row + 1) * 16]
                if shapes is None or key in seen:
                    continue
                seen.add(key)
                yield stepped, row, shapes, key
    except Exception as error:  # the closing forms end the stepping
        print('stepping ended:', type(error).__name__)


def expected(vector):
    """(hashes bytes, f32 least/mean/most bytes, stopped) of a ShapeVector."""
    values = np.frombuffer(vector.values, np.float64).reshape(-1, 6)[:, :3].astype('<f4')
    return bytes(vector.hashes), values.tobytes(), bool(vector.stopped)


def known_pick(shapes_of, known):
    """Among (key, TableShapes), the table with the most values equal to the known ones under `only=`, and the known shapes' hashes."""
    texts = list(known['shapes'])
    want = np.array([known['shapes'][t] for t in texts], np.float64)
    hashes = [arclog.shape_hash(t) for t in texts]
    selection = arclog.ShapeSelection(hashes)
    best = None
    for key, ts in shapes_of:
        v = ts.vector(only=selection)
        values = np.frombuffer(v.values, np.float64).reshape(-1, 6)[:, :3]
        present = np.frombuffer(v.present, np.uint8) == 1
        same = (np.isclose(values, want, rtol=1e-9, atol=0, equal_nan=True).all(axis=1) & present).sum()
        if best is None or same > best[0]:
            best = (int(same), key, ts)
    return best, hashes


def rows_header(task):
    """The first line of a rows file: the format that `shapes-refresh` reads and the producers of the engine in use, its hash versions and the commit and flags of its
    build record (`engine-record.json` beside the loaded arclog). The encoder reads the file only where they are its own, so the check also holds the encoder and the
    site to one build. Stops where the site has no record."""
    path = os.path.join(os.path.dirname(arclog.__file__), 'engine-record.json')
    try:
        record = json.load(open(path))
    except OSError:
        print(f'no engine record at {path}: the site must be a build of scripts/engine_build.sh that writes one')
        sys.exit(2)
    header = {'record': 'header', 'schema': 'table-rows-1', 'task': task, 'table_hash_version': arclog.table_hash_version(),
              'query_hash_version': arclog.query_hash_version(), 'engine': {'commit': record['commit'], 'flags': dict(sorted(record['flags'].items()))}}
    return json.dumps(header, separators=(',', ':')).encode() + b'\n'


def encoder(binary, rows_file, task, out_file, tasks_dir, threads, list_file=None):
    args = [binary, 'shapes-refresh', rows_file, task, out_file, '--tasks', tasks_dir, '--threads', str(threads)]
    if list_file:
        args += ['--shapes', list_file]
    t = time.perf_counter()
    done = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if done.returncode != 0:
        print('shapes-refresh failed:', done.stderr.strip()[-300:])
        sys.exit(2)
    return time.perf_counter() - t


def records(path):
    with open(path, 'rb') as raw:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True), encoding='utf-8'):
            if line.strip():
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('mutants')
    ap.add_argument('--encoder')
    ap.add_argument('--known')
    ap.add_argument('--tables', type=int)
    ap.add_argument('--stopped', action='store_true')
    ap.add_argument('--max-walks', type=int, default=4)
    ap.add_argument('--repo', default=os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace'))
    ap.add_argument('--work')
    ap.add_argument('--threads', type=int, default=1)
    ap.add_argument('--export')
    ap.add_argument('--export-hashes')
    ap.add_argument('--digest-out')
    ap.add_argument('--digest-in')
    a = ap.parse_args()
    tasks_dir = os.path.join(a.repo, 'data', 'tasks')
    task_text = open(os.path.join(tasks_dir, a.task + '.json')).read()
    gold = json.load(zstandard.ZstdDecompressor().stream_reader(open(a.mutants, 'rb')))['gold']
    work = a.work or tempfile.mkdtemp(prefix='shapes_rows_check_')
    os.makedirs(work, exist_ok=True)

    t = time.perf_counter()
    tables = [(key, ts) for _, _, ts, key in steps(a.task, task_text, gold)]
    print(f'{len(tables)} distinct tables, {time.perf_counter() - t:.1f} s to step the gold program')
    sized = []
    for key, ts in tables:
        rows = ts.rows()
        sized.append((len(rows) if rows is not None else -1, key, ts))
    print(f'{sum(1 for size, _, _ in sized if size < 0)} tables without a stored form')
    sized = [item for item in sized if item[0] >= 0]
    sized.sort(key=lambda item: (item[0], item[1]))

    if a.export:
        wanted = set(a.export_hashes.split(',')) if a.export_hashes else None
        kept = [(key, ts.rows()) for _, key, ts in sized if wanted is None or key.hex() in wanted]
        with open(a.export, 'wb') as sink:
            sink.write(zstandard.ZstdCompressor(level=3).compress(rows_header(a.task) + b''.join(b'{"hash":"' + key.hex().encode() + b'","table":' + rows + b'}\n' for key, rows in kept)))
        print(f'wrote {len(kept)} tables to {a.export}')
        return
    if not a.encoder:
        sys.exit('--encoder is needed for the check')
    chosen, hashes = [], None
    if a.known:
        best, hashes = known_pick([(key, ts) for _, key, ts in sized], json.loads(open(a.known).readline()))
        print(f'known table: {best[0]} of {len(hashes)} equal')
        chosen.append(('known', best[1], best[2]))
    for _, key, ts in sized[:a.tables if a.tables is not None else (0 if a.known else 3)]:
        chosen.append(('small', key, ts))
    if a.stopped:
        walks = 0
        for size, key, ts in reversed(sized):
            if walks >= a.max_walks:
                break
            walks += 1
            t = time.perf_counter()
            stopped = ts.vector().stopped
            print(f'walked a table of {size} bytes: stopped {stopped}, {time.perf_counter() - t:.1f} s')
            if stopped:
                chosen.append(('stopped', key, ts))
                break
        else:
            print('no walked table stopped')
    seen, picked = set(), []
    for how, key, ts in chosen:
        if key not in seen:
            seen.add(key)
            picked.append((how, key, ts))

    rows_file, digests = os.path.join(work, 'rows.jsonl.zst'), {}
    lines = [rows_header(a.task)]
    for how, key, ts in picked:
        first, second = ts.rows(), ts.rows()
        assert first == second, 'rows() differs between two calls'
        digests[key.hex()] = hashlib.sha256(first).hexdigest()
        lines.append(b'{"hash":"' + key.hex().encode() + b'","table":' + first + b'}\n')
    with open(rows_file, 'wb') as sink:
        sink.write(zstandard.ZstdCompressor(level=3).compress(b''.join(lines)))
    bad = 0
    if a.digest_out:
        json.dump(digests, open(a.digest_out, 'w'))
    if a.digest_in:
        earlier = json.load(open(a.digest_in))
        differ = [h for h in digests if h in earlier and earlier[h] != digests[h]]
        print(f'bytes of rows() against the earlier run: {sum(h in earlier for h in digests) - len(differ)} equal, {len(differ)} differ, {sum(h not in earlier for h in digests)} not in it')
        bad += len(differ)

    # The full vectors.
    t = time.perf_counter()
    full = {key.hex(): expected(ts.vector()) for _, key, ts in picked}
    walk_seconds = time.perf_counter() - t
    out_full = os.path.join(work, 'full.zst')
    refresh_seconds = encoder(a.encoder, rows_file, a.task, out_full, tasks_dir, a.threads)
    got = {r['table']: r for r in records(out_full)}
    equal = 0
    for how, key, ts in picked:
        r = got.get(key.hex())
        h, v, stopped = full[key.hex()]
        same = r is not None and base64.b64decode(r['h']) == h and base64.b64decode(r['v']) == v and r['stopped'] == stopped
        equal += same
        bad += not same
        print(f'  full {how:8} {key.hex()[:8]}: shapes {len(h) // 8}, stopped {stopped}, {"equal" if same else "DIFFERENT"}')
    print(f'full vector: {equal} of {len(picked)} equal; TableShapes.vector {walk_seconds:.1f} s, shapes-refresh {refresh_seconds:.1f} s')

    # A list of shapes: the known ones, otherwise a spread of the first table's shapes and three that no table has.
    if hashes is None:
        h = np.frombuffer(full[picked[0][1].hex()][0], np.uint64)
        hashes = [int(x) for x in h[::max(1, len(h) // LIST_SIZE)]] + [1, 2, 3]
    selection = arclog.ShapeSelection(hashes)
    list_file = os.path.join(work, 'list.txt')
    open(list_file, 'w').write(''.join('%016x\n' % x for x in hashes))
    t = time.perf_counter()
    listed = {key.hex(): expected(ts.vector(only=selection)) for _, key, ts in picked}
    walk_seconds = time.perf_counter() - t
    out_list = os.path.join(work, 'list.zst')
    refresh_seconds = encoder(a.encoder, rows_file, a.task, out_list, tasks_dir, a.threads, list_file)
    got = {r['table']: r for r in records(out_list)}
    equal = 0
    for how, key, ts in picked:
        r = got.get(key.hex())
        h, v, stopped = listed[key.hex()]
        same = r is not None and base64.b64decode(r['h']) == h and base64.b64decode(r['v']) == v and r['stopped'] == stopped
        equal += same
        bad += not same
        print(f'  list {how:8} {key.hex()[:8]}: shapes {len(h) // 8}, stopped {stopped}, {"equal" if same else "DIFFERENT"}')
    print(f'list of {len(hashes)}: {equal} of {len(picked)} equal; TableShapes.vector {walk_seconds:.1f} s, shapes-refresh {refresh_seconds:.1f} s')
    print('differences:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
