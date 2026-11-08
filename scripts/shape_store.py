#!/usr/bin/env python3
"""The `shapes` records of a task's tables, from a store of walked values, with a walk of only the values that the store lacks.

Usage: scripts/shape_store.py refresh ENCODER ROWS_FILE TASK OUT [--shapes FILE] [--threads N] [--tasks DIR] [--store DIR]
       scripts/shape_store.py carry NEW BASE [--threads N] [--jobs N] [--tasks DIR] [--store DIR]
       scripts/shape_store.py version ENCODER [--store DIR]

`refresh` writes OUT with the lines that `ENCODER shapes-refresh ROWS_FILE TASK OUT [--shapes FILE]` writes, in the same order. A value is
the least, the mean and the most over the examples of one shape of one table of the task. The store keeps the values of each walk that
did not stop, under the build's value version, and a refresh walks only the tables and shapes that the store lacks. The store keeps
nothing of a walk that stopped at the cell budget, and of a table that has too many columns: the encoder walks such a table with the
whole request, and its record goes to OUT as the encoder writes it. A refresh with an environment variable set that changes the
encoder's values (see VALUE_VARIABLES) is refused.

A value version names the values that a build gives. A build has a version of its own, from the hash of its binary, unless an entry of
`value-versions.jsonl` in the store gives its binary another. `carry NEW BASE` writes such an entry: it runs both builds on each rows
file of the check set, and where the records of every file are identical, NEW takes BASE's version. So a change that keeps the values
keeps the store, and any other change starts a new one.

The store is a folder, work/shape-store by default, of `<version>/<task>-<hash of the task file>.jsonl.zst`. Each line is
`{"table":HASH,"complete":FLAG,"h":B,"v":B}`, with `h` and `v` as in a `shapes` record. `complete` is true where a walk listed no shapes,
so the line holds each shape of the table, and a shape that it lacks has 0. The check set is `check-rows/<task>.rows.zst` in the store.
"""
import argparse
import base64
import concurrent.futures
import contextlib
import datetime
import fcntl
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import zstandard

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / 'work' / 'shape-store'
TASKS = ROOT / 'data' / 'tasks'
# The bytes of one shape's values: the least, the mean and the most, each a little-endian f32.
VALUE_BYTES = 12
ZERO = bytes(VALUE_BYTES)
# The encoder's environment variables that change its values, and the prefixes of such variables.
VALUE_VARIABLES = ('GENERATE_NO_RULES', 'GENERATE_FAMILIES_BUILD')
VALUE_PREFIXES = ('GOLD_PRUNE_',)
# The most encoder calls a refresh makes for the tables that the store holds in part. Past it, those tables are walked in one call,
# with each shape that one of them lacks.
MOST_GROUPS = 8


class Refused(Exception):
    pass


def lines_of(path: Path):
    """The lines of a file, zstd where its name ends in `.zst`, as the encoder reads it."""
    with open(path, 'rb') as raw:
        if path.suffix == '.zst':
            yield from io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True), encoding='utf-8')
        else:
            yield from io.TextIOWrapper(raw, encoding='utf-8')


def write_lines(path: Path, lines):
    """Writes the lines, each with its newline, through a temporary file, zstd where the name ends in `.zst`, as the encoder writes."""
    temporary = path.with_name(path.name + '.tmp')
    with open(temporary, 'wb') as raw:
        if path.suffix == '.zst':
            with zstandard.ZstdCompressor(level=3).stream_writer(raw, closefd=False) as writer:
                for line in lines:
                    writer.write(line.encode('utf-8') + b'\n')
        else:
            for line in lines:
                raw.write(line.encode('utf-8') + b'\n')
    os.replace(temporary, path)


def digest_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as held:
        for block in iter(lambda: held.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def ledger_of(store: Path) -> Path:
    return store / 'value-versions.jsonl'


def version_of(encoder: Path, store: Path) -> tuple[str, str]:
    """The build's value version and the hash of its binary."""
    digest = digest_of(encoder)
    version = 'b' + digest[:16]
    ledger = ledger_of(store)
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                if entry['binary'] == digest:
                    version = entry['version']
    return version, digest


def refuse_value_variables():
    named = [name for name in os.environ if name in VALUE_VARIABLES or name.startswith(VALUE_PREFIXES)]
    if named:
        raise Refused(f'{", ".join(sorted(named))} changes the encoder\'s values, and the store holds none for it')


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def hashes_of(text: str) -> list[int]:
    data = base64.b64decode(text)
    return list(struct.unpack(f'<{len(data) // 8}Q', data))


def shape_list(path: Path) -> list[int]:
    """The shape hashes of a `--shapes` file: one hexadecimal hash on each line, before any tab."""
    hashes = []
    for line in path.read_text().splitlines():
        field = line.split('\t')[0].strip()
        if not field:
            continue
        digits = field[2:] if field.startswith('0x') else field
        if len(digits) > 16:
            raise Refused(f'{path}: {field} is not a hexadecimal hash of at most 16 digits')
        try:
            hashes.append(int(digits, 16))
        except ValueError:
            raise Refused(f'{path}: {field} is not a hexadecimal hash') from None
    return hashes


class Held:
    """The values that the store holds for one table."""

    def __init__(self):
        self.complete = False
        self.values: dict[int, bytes] = {}

    def add(self, hashes: list[int], values: bytes, complete: bool):
        for at, shape in enumerate(hashes):
            self.values[shape] = values[at * VALUE_BYTES:(at + 1) * VALUE_BYTES]
        self.complete = self.complete or complete

    def line(self, table: str) -> str:
        shapes = sorted(self.values)
        data = struct.pack(f'<{len(shapes)}Q', *shapes)
        return json.dumps({'table': table, 'complete': self.complete, 'h': b64(data), 'v': b64(b''.join(self.values[s] for s in shapes))}, separators=(',', ':'))


def load(path: Path) -> dict[str, Held]:
    held: dict[str, Held] = {}
    if path.exists():
        for line in lines_of(path):
            if line.strip():
                record = json.loads(line)
                held.setdefault(record['table'], Held()).add(hashes_of(record['h']), base64.b64decode(record['v']), record['complete'])
    return held


@contextlib.contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + '.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def record_line(table: str, hashes: list[int], values: bytes) -> str:
    """A `shapes` record, written as the encoder writes it."""
    data = struct.pack(f'<{len(hashes)}Q', *hashes)
    return f'{{"record":"shapes","table":"{table}","h":"{b64(data)}","v":"{b64(values)}","stopped":false}}'


def needs_of(held: Held | None, only: list[int] | None) -> list[int] | None:
    """The shapes that a walk of the table must give: none where the store holds the request, every shape (an empty list) for a
    request with no list, or the listed shapes that the store lacks, in the list's order."""
    if held is not None and held.complete:
        return None
    if only is None:
        return []
    have = held.values if held is not None else {}
    missing = [shape for shape in dict.fromkeys(only) if shape not in have]
    return missing or None


def walk(encoder: Path, task: str, lines: list[str], shapes: list[int] | None, threads: int, tasks: Path, work: Path, name: str) -> list[str]:
    """The encoder's records for the rows lines, with the listed shapes or with each shape."""
    rows = work / f'{name}.rows.jsonl'
    out = work / f'{name}.out.jsonl'
    write_lines(rows, lines)
    command = [str(encoder), 'shapes-refresh', str(rows), task, str(out), '--tasks', str(tasks), '--threads', str(threads)]
    if shapes is not None:
        listed = work / f'{name}.shapes.txt'
        listed.write_text(''.join(f'{shape:016x}\n' for shape in shapes))
        command += ['--shapes', str(listed)]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f'{encoder.name} shapes-refresh failed for {task}: {done.stderr.strip()[-400:]}')
    return [line.rstrip('\n') for line in lines_of(out) if line.strip()]


def refresh(args) -> str:
    refuse_value_variables()
    begun = time.monotonic()
    encoder, store, tasks = Path(args.encoder).resolve(), Path(args.store).resolve(), Path(args.tasks).resolve()
    version, _ = version_of(encoder, store)
    task_digest = digest_of(tasks / f'{args.task}.json')[:12]
    path = store / version / f'{args.task}-{task_digest}.jsonl.zst'
    only = shape_list(Path(args.shapes)) if args.shapes else None
    tables: list[tuple[str, str]] = []
    for line in lines_of(Path(args.rows)):
        if not line.strip():
            continue
        try:
            hash_ = json.loads(line).get('hash')
        except json.JSONDecodeError:
            raise Refused(f'{args.rows}: a line that is not JSON') from None
        if not isinstance(hash_, str) or not hash_ or any(c not in '0123456789abcdefABCDEF' for c in hash_):
            raise Refused(f'{args.rows}: a line with no hash')
        tables.append((hash_, line.rstrip('\n')))
    held = load(path)
    groups: dict[tuple, list[int]] = {}
    for at, (table, _) in enumerate(tables):
        needs = needs_of(held.get(table), only)
        if needs is not None:
            groups.setdefault(tuple(needs) if only is not None else ('every',), []).append(at)
    if len(groups) > MOST_GROUPS:
        union = list(dict.fromkeys(shape for key in groups for shape in key))
        groups = {tuple(union): sorted(at for ats in groups.values() for at in ats)}
    direct: dict[int, str] = {}  # table place -> the encoder's record line, as OUT holds it
    fresh: dict[str, Held] = {}
    again: list[int] = []
    with tempfile.TemporaryDirectory(prefix='shape-store-') as work:
        for number, (key, ats) in enumerate(groups.items()):
            shapes = None if key == ('every',) else list(key)
            whole = shapes is None or shapes == only
            by_table = {json.loads(line)['table']: line for line in walk(encoder, args.task, [tables[at][1] for at in ats], shapes, args.threads, tasks, Path(work), f'g{number}')}
            for at in ats:
                table = tables[at][0]
                line = by_table.get(table)
                if line is None:
                    continue  # a table that the encoder gives no record
                record = json.loads(line)
                if record['stopped']:
                    if whole:
                        direct[at] = line
                    else:
                        again.append(at)
                    continue
                fresh.setdefault(table, Held()).add(hashes_of(record['h']), base64.b64decode(record['v']), shapes is None)
                if whole:
                    direct[at] = line
        if again:
            by_table = {json.loads(line)['table']: line for line in walk(encoder, args.task, [tables[at][1] for at in sorted(again)], only, args.threads, tasks, Path(work), 'again')}
            for at in again:
                line = by_table.get(tables[at][0])
                if line is not None:
                    direct[at] = line
                    record = json.loads(line)
                    if not record['stopped']:
                        fresh.setdefault(tables[at][0], Held()).add(hashes_of(record['h']), base64.b64decode(record['v']), only is None)
    if fresh:
        with locked(path):
            stored = load(path)
            for table, values in fresh.items():
                stored.setdefault(table, Held()).add(sorted(values.values), b''.join(values.values[s] for s in sorted(values.values)), values.complete)
            write_lines(path, [stored[table].line(table) for table in sorted(stored)])
    for table, values in fresh.items():
        held.setdefault(table, Held()).add(sorted(values.values), b''.join(values.values[s] for s in sorted(values.values)), values.complete)
    out_lines = []
    served = 0
    walked_at = {at for ats in groups.values() for at in ats}
    for at, (table, _) in enumerate(tables):
        if at in direct:
            out_lines.append(direct[at])
            continue
        values = held.get(table)
        if values is None:
            continue  # a table that the encoder gives no record
        if only is None:
            shapes = sorted(values.values)
        else:
            shapes = only
        out_lines.append(record_line(table, shapes, b''.join(values.values.get(shape, ZERO) for shape in shapes)))
        if at not in walked_at:
            served += 1
    write_lines(Path(args.out), out_lines)
    walked = len(walked_at)
    return (f'{args.task}: {len(out_lines)} records, {served} tables wholly from the store ({version}), {walked} tables walked in {len(groups)} calls, '
            f'{len(again)} walked again with the whole request, {len(fresh)} tables stored, {time.monotonic() - begun:.1f} s')


def carry(args) -> str:
    refuse_value_variables()
    new, base, store, tasks = Path(args.new).resolve(), Path(args.base).resolve(), Path(args.store).resolve(), Path(args.tasks).resolve()
    base_version, base_digest = version_of(base, store)
    new_version, new_digest = version_of(new, store)
    if new_version == base_version:
        return f'{new.name} already has the value version {base_version}'
    rows_files = sorted((store / 'check-rows').glob('*.rows.zst'), key=lambda path: -path.stat().st_size)
    if not rows_files:
        raise Refused(f'{store / "check-rows"} holds no rows file')

    # On macOS, `/usr/bin/time -l` gives each run's instructions retired and peak memory footprint, which the load on the machine
    # changes little.
    timed = ['/usr/bin/time', '-l'] if sys.platform == 'darwin' and Path('/usr/bin/time').exists() else []

    def cost(error: str, seconds: float) -> str:
        found = {}
        for line in error.splitlines():
            parts = line.split()
            if len(parts) >= 2 and line.strip().endswith('instructions retired'):
                found['instructions'] = int(parts[0])
            elif len(parts) >= 2 and line.strip().endswith('peak memory footprint'):
                found['footprint'] = int(parts[0])
        text = f'{seconds:.1f} s'
        if 'instructions' in found:
            text += f' {found["instructions"] / 1e9:.1f} Ginstr'
        if 'footprint' in found:
            text += f' {found["footprint"] // 1048576} MB'
        return text

    def one(rows: Path) -> tuple[str, bool, str, str]:
        task = rows.name[:-len('.rows.zst')]
        with tempfile.TemporaryDirectory(prefix='shape-carry-') as work:
            outs, costs = [], []
            started = []
            for build, name in ((base, 'base'), (new, 'new')):
                out = Path(work) / f'{name}.jsonl'
                outs.append(out)
                started.append((time.monotonic(), subprocess.Popen(timed + [str(build), 'shapes-refresh', str(rows), task, str(out), '--tasks', str(tasks), '--threads', str(args.threads)],
                                                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)))
            for begun, process in started:
                _, error = process.communicate()
                costs.append(cost(error, time.monotonic() - begun))
                if process.returncode != 0:
                    raise Refused(f'shapes-refresh failed for {task}: {error.strip()[-400:]}')
            same = outs[0].read_bytes() == outs[1].read_bytes()
        return task, same, costs[0], costs[1]

    verdicts = []
    with concurrent.futures.ThreadPoolExecutor(max(1, args.jobs)) as pool:
        for task, same, base_cost, new_cost in pool.map(one, rows_files):
            verdicts.append(same)
            print(f'{task}: records {"IDENTICAL" if same else "DIFFER"}; base {base_cost}; new {new_cost}', flush=True)
    if not all(verdicts):
        return f'{new.name} keeps its value version {new_version}: {verdicts.count(False)} of {len(verdicts)} rows files differ'
    entry = {'binary': new_digest, 'version': base_version, 'name': new.name, 'base_binary': base_digest, 'base_name': base.name,
             'check': {'rows_files': len(verdicts), 'identical': len(verdicts)}, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    with locked(ledger_of(store)):
        with open(ledger_of(store), 'a') as ledger:
            ledger.write(json.dumps(entry, separators=(',', ':')) + '\n')
    return f'{new.name} carries the value version {base_version} of {base.name}: {len(verdicts)} of {len(verdicts)} rows files identical'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    one = commands.add_parser('refresh')
    one.add_argument('encoder')
    one.add_argument('rows')
    one.add_argument('task')
    one.add_argument('out')
    one.add_argument('--shapes')
    one.add_argument('--threads', type=int, default=1)
    one.add_argument('--tasks', default=str(TASKS))
    one.add_argument('--store', default=str(STORE))
    two = commands.add_parser('carry')
    two.add_argument('new')
    two.add_argument('base')
    two.add_argument('--threads', type=int, default=2)
    two.add_argument('--jobs', type=int, default=2)
    two.add_argument('--tasks', default=str(TASKS))
    two.add_argument('--store', default=str(STORE))
    three = commands.add_parser('version')
    three.add_argument('encoder')
    three.add_argument('--store', default=str(STORE))
    args = parser.parse_args()
    try:
        if args.command == 'refresh':
            print(refresh(args), file=sys.stderr)
        elif args.command == 'carry':
            print(carry(args))
        else:
            version, digest = version_of(Path(args.encoder).resolve(), Path(args.store).resolve())
            print(f'{version}\t{digest}')
    except Refused as why:
        print(f'shape_store.py: {why}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
