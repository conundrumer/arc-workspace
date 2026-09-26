"""A stored Souffle run stands only for the inputs it was made from."""

from dl import souffle


def test_a_hit_returns_the_stored_run_and_a_changed_include_misses(
        tmp_path, monkeypatch):
    solvers = tmp_path / "solvers"
    solvers.mkdir()
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib.dl").write_text('#include "lib/cells.dl"\n')
    cells = tmp_path / "lib" / "cells.dl"
    cells.write_text(".decl cell(x: number)\n")
    monkeypatch.setattr(souffle, "SOLVERS_DIR", solvers)
    monkeypatch.setattr(souffle, "CACHE_DIR", tmp_path / "cache")
    calls = []

    def invoke(path):
        calls.append(path)
        return souffle._Ran(0, f"run {len(calls)}", "")

    built = '#include "../lib.dl"\n'
    first = souffle._cached_run(built, ["-D-"], "facts", invoke)
    again = souffle._cached_run(built, ["-D-"], "facts", invoke)
    assert (first.stdout, again.stdout, len(calls)) == ("run 1", "run 1", 1)

    cells.write_text(".decl cell(x: symbol)\n")
    changed = souffle._cached_run(built, ["-D-"], "facts", invoke)
    assert changed.stdout == "run 2"


# One process of the concurrency test: it writes and reads the shared keys
# with a prune on every write, under a cap that evicts. A read of the file
# either finds it missing or finds the whole entry that key stands for.
WORKER = """
import hashlib, json, random, sys, zlib
from pathlib import Path
from dl import souffle
souffle.CACHE_DIR = Path(sys.argv[1])
souffle.CACHE_CAP_BYTES = 400_000
souffle.CACHE_PRUNE_EVERY = 1
souffle.CACHE_PRUNE_INTERVAL_SECONDS = 0

def value(key):
    text = "".join(hashlib.sha256(f"{key}{i}".encode()).hexdigest()
                   for i in range(800))
    return souffle._Ran(0, text, "")

keys = [f"key{i}" for i in range(50)]
for _ in range(150):
    key = random.choice(keys)
    if random.random() < 0.5:
        souffle._cache_write(key, value(key))
        continue
    try:
        raw = (souffle.CACHE_DIR / f"{key}.json.z").read_bytes()
    except FileNotFoundError:
        continue
    assert souffle._Ran(**json.loads(zlib.decompress(raw))) == value(key)
    assert souffle._cache_read(key) in (None, value(key))
"""


def test_concurrent_writers_never_leave_a_partial_entry(tmp_path):
    import subprocess
    import sys

    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(tmp_path)],
                              stderr=subprocess.PIPE, text=True)
             for _ in range(20)]
    failed = [err for p in procs if (err := p.communicate()[1]) or p.returncode]
    assert failed == []
    # 50 entries of about 26 KB each overrun the cap, so the prune evicted.
    assert len(list(tmp_path.glob("*.json.z"))) < 50


def test_a_cpu_limit_end_replays_under_its_own_limit_alone(
        tmp_path, monkeypatch):
    monkeypatch.setattr(souffle, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(souffle, "CACHE_DIR", tmp_path / "cache")
    calls = []

    def limited(path):
        calls.append(path)
        raise souffle._CpuLimit(f"limit on run {len(calls)}")

    def finished(path):
        calls.append(path)
        return souffle._Ran(0, "done", "")

    def ended(invoke, limit):
        try:
            return souffle._cached_run("p.\n", ["-D-"], "", invoke, limit)
        except souffle._CpuLimit as e:
            return str(e)

    assert ended(limited, 5) == "limit on run 1"
    assert ended(finished, 5) == "limit on run 1"
    ran = ended(finished, 50)
    assert isinstance(ran, souffle._Ran) and ran.stdout == "done"
    assert len(calls) == 2
