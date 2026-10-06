"""The run cache. A key that leaves out something the run reads returns a
stored result for a different run, and nothing in the output shows it."""

from pathlib import Path

from engine import Engine, InputValue, Limits, Program, RelationName, Tuples
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


def test_a_clause_is_in_the_key_and_a_comment_is_not(tmp_path: Path):
    engine = SouffleEngine(functor_dir=None, cache_dir=tmp_path / "cache")
    text = ".decl i(x: number)\n.decl o(x: number)\no(X + 1) :- i(X).\n"
    assert _rows(engine, text, tmp_path, {IN: ((10,),)}) == ((11,),)
    edited = text.replace("X + 1", "X + 2")
    assert _rows(engine, edited, tmp_path, {IN: ((10,),)}) == ((12,),)
    stored = sorted((tmp_path / "cache").glob("*.json.z"))
    commented = "// a comment\n\n" + edited.replace(".\n", ". // why\n")
    assert _rows(engine, commented, tmp_path, {IN: ((10,),)}) == ((12,),)
    assert sorted((tmp_path / "cache").glob("*.json.z")) == stored


# One process of the concurrency test: it writes and reads the shared keys
# with a prune on every write, under a cap that evicts. A read finds the
# entry missing or finds the whole entry that key stands for.
WORKER = """
import hashlib, random, sys
from pathlib import Path
from souffle import run
run.CACHE_CAP_BYTES = 400_000
run.CACHE_PRUNE_EVERY = 1
run.CACHE_PRUNE_INTERVAL_SECONDS = 0
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
    import fcntl
    import subprocess
    import sys

    from souffle import run

    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(tmp_path)],
                              stderr=subprocess.PIPE, text=True)
             for _ in range(20)]
    failed = [err for p in procs if (err := p.communicate()[1]) or p.returncode]
    assert failed == []
    # A prune runs on past its writer, and holds its lock until it ends.
    with open(tmp_path / run.CACHE_PRUNE_LOCK) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
    # 50 entries of about 26 KB each overrun the cap, so the prune evicted.
    assert len(list(tmp_path.glob("*.json.z"))) < 50
