"""The run cache. A key that leaves out something the run reads returns a
stored result for a different run, and nothing in the output shows it."""

from pathlib import Path

import pytest

from engine import Engine, InputValue, Limits, Program, RelationName, Tuples, checkout
from souffle import SouffleEngine

LIMITS = Limits(5, 20)
OUT = RelationName((), "o")
IN = RelationName((), "i")


def _rows(engine: Engine, text: str, base: Path, inputs: dict[RelationName, InputValue]):
    program = engine.parse(text, base)
    assert isinstance(program, Program), program
    result = engine.run(program, inputs, [OUT], LIMITS)
    assert isinstance(result, Tuples), result
    return result.relations[OUT]


def test_an_included_file_and_the_input_facts_are_in_the_key(tmp_path: Path):
    engine = SouffleEngine(functor_dir=None, cache_dir=tmp_path / "cache")
    (tmp_path / "inc.dl").write_text(".decl k(x: number)\nk(1).\n")
    text = ('#include "inc.dl"\n.decl i(x: number)\n.decl o(x: number)\n'
            "o(X + Y) :- k(X), i(Y).\n")
    assert _rows(engine, text, tmp_path, {IN: ((10,),)}) == ((11,),)
    assert _rows(engine, text, tmp_path, {IN: ((20,),)}) == ((21,),)
    (tmp_path / "inc.dl").write_text(".decl k(x: number)\nk(2).\n")
    assert _rows(engine, text, tmp_path, {IN: ((20,),)}) == ((22,),)


def test_a_run_in_another_checkout_root_reads_the_stored_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    text = ('#include "inc.dl"\n.decl i(x: number)\n.decl o(x: number)\n'
            "o(X + Y) :- k(X), i(Y).\n")
    inc = ".decl k(x: number)\nk(1).\n"
    cache = tmp_path / "cache"
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "inc.dl").write_text(inc)

    def stored_in(root: Path, inc_text: str) -> list[Path]:
        (root / "inc.dl").write_text(inc_text)
        monkeypatch.setattr(checkout, "ROOT", root)
        engine = SouffleEngine(functor_dir=None, cache_dir=cache)
        _rows(engine, text, root, {IN: ((10,),)})
        return sorted(cache.glob("*/*.json.z"))

    first = stored_in(tmp_path / "a", inc)
    assert len(first) == 1
    assert stored_in(tmp_path / "b", inc) == first
    assert len(stored_in(tmp_path / "b", inc.replace("k(1)", "k(2)"))) == 2


def test_a_clause_is_in_the_key_and_a_comment_is_not(tmp_path: Path):
    engine = SouffleEngine(functor_dir=None, cache_dir=tmp_path / "cache")
    text = ".decl i(x: number)\n.decl o(x: number)\no(X + 1) :- i(X).\n"
    assert _rows(engine, text, tmp_path, {IN: ((10,),)}) == ((11,),)
    edited = text.replace("X + 1", "X + 2")
    assert _rows(engine, edited, tmp_path, {IN: ((10,),)}) == ((12,),)
    stored = sorted((tmp_path / "cache").glob("*/*.json.z"))
    commented = "// a comment\n\n" + edited.replace(".\n", ". // why\n")
    assert _rows(engine, commented, tmp_path, {IN: ((10,),)}) == ((12,),)
    assert sorted((tmp_path / "cache").glob("*/*.json.z")) == stored


# One process of the concurrency test: it writes and reads the shared keys
# with a prune on every write, under a cap that evicts. The keys all open
# with `ke`, so they stand in one shard, whose part of the cap is 400,000.
# A read finds the entry missing or finds the whole entry that key stands
# for.
WORKER = """
import hashlib, random, sys
from pathlib import Path
from souffle import run
run.CACHE_CAP_BYTES = 400_000 * 16 ** run.CACHE_SHARD_DIGITS
run.CACHE_PRUNE_EVERY = 1
runner = run.Runner(None, Path(sys.argv[1]))

def value(key):
    return {"out": "".join(hashlib.sha256(f"{key}{i}".encode()).hexdigest()
                           for i in range(800))}

keys = [f"key{i}" for i in range(50)]
for _ in range(150):
    key = random.choice(keys)
    if random.random() < 0.5:
        runner._write(key, value(key))
    else:
        assert runner._read(key) in (None, value(key))
"""


def test_concurrent_writers_never_leave_a_partial_entry(tmp_path: Path):
    import subprocess
    import sys

    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(tmp_path)],
                              stderr=subprocess.PIPE, text=True)
             for _ in range(20)]
    failed = [err for p in procs if (err := p.communicate()[1]) or p.returncode]
    assert failed == []
    # 50 entries of about 26 KB each overrun the cap, so the prunes evicted.
    assert len(list(tmp_path.glob("*/*.json.z"))) < 50
