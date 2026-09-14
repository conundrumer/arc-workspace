"""A `rule` alt in pair results and in a source profile: both peer
models' grids count, and both must be emitted."""

from dataclasses import dataclass

from dl import solve as solve_mod
from dl.facts import Candidate


@dataclass
class _Alt:
    kind: str
    grid: list[list[int]]


@dataclass
class _Ex:
    input: list[list[int]]
    output: list[list[int]]
    alt: _Alt | None = None


@dataclass
class _Task:
    train: list[_Ex]
    test: list[_Ex]


A = [[1]]
B = [[2]]
RULE_EX = _Ex(input=[[0]], output=A, alt=_Alt(kind="rule", grid=B))


def _run_pair(monkeypatch, ex, actuals, idx=0):
    monkeypatch.setattr(solve_mod, "run_dl", lambda *_a, **_k: actuals)
    monkeypatch.setattr(solve_mod, "res_out_stem", lambda _stem: False)
    return solve_mod.run_pair("s", "t", "train", idx, ex)


def test_rule_alt_grid_is_accepted(monkeypatch):
    both = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", B, [], [])]
    result = _run_pair(monkeypatch, RULE_EX, both)
    assert result.accepted == [A, B]
    assert result.ok


def test_rule_alt_pair_needs_every_accepted_grid(monkeypatch):
    one = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", A, [], [])]
    assert not _run_pair(monkeypatch, RULE_EX, one).ok


def test_a_case_flipping_slots_across_pairs_fails_the_task(monkeypatch):
    straight = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", B, [], [])]
    flipped = [Candidate("$CaseA", B, [], []), Candidate("$CaseB", A, [], [])]
    p0 = _run_pair(monkeypatch, RULE_EX, straight, idx=0)
    p1 = _run_pair(monkeypatch, RULE_EX, flipped, idx=1)
    assert p0.ok and p1.ok
    findings = solve_mod.case_coverage([p0, p1])
    assert findings == [
        "case $CaseA lands on slot 0 in train[0] and slot 1 in train[1]",
        "case $CaseB lands on slot 1 in train[0] and slot 0 in train[1]",
    ]
    assert not solve_mod.TaskResult(stem="s", pairs=[p0, p1]).all_pass


def _profile(monkeypatch, ex, actuals):
    monkeypatch.setattr(solve_mod, "res_out", lambda _src: False)
    monkeypatch.setattr(solve_mod, "build_source", lambda src: src)
    monkeypatch.setattr(solve_mod, "grid_to_facts", lambda rows: "")
    monkeypatch.setattr(solve_mod, "_run_source", lambda *_a, **_k: "")
    monkeypatch.setattr(solve_mod, "parse_output", lambda _out: actuals)
    return solve_mod._profile("src", [ex])


def test_profile_takes_the_rule_alt_grid(monkeypatch):
    both = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", B, [], [])]
    assert _profile(monkeypatch, RULE_EX, both) == [frozenset({"$CaseA", "$CaseB"})]


def test_profile_needs_every_accepted_grid_under_a_rule_alt(monkeypatch):
    one = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", A, [], [])]
    assert _profile(monkeypatch, RULE_EX, one) is None



def _cases(monkeypatch, per_pair: list[list], cases: bool):
    """One stub run per pair, and how many pairs ran: `_profile_cases` under
    `cases`, `_profile` without it."""
    runs = iter(per_pair)
    seen = []

    def parse(_out):
        actuals = next(runs)
        seen.append(actuals)
        return actuals

    monkeypatch.setattr(solve_mod, "res_out", lambda _src: False)
    monkeypatch.setattr(solve_mod, "build_source", lambda src: src)
    monkeypatch.setattr(solve_mod, "grid_to_facts", lambda rows: "")
    monkeypatch.setattr(solve_mod, "_run_source", lambda *_a, **_k: "")
    monkeypatch.setattr(solve_mod, "parse_output", parse)
    ex = _Ex(input=[[0]], output=A)
    examples = [ex] * len(per_pair)
    out = (solve_mod._profile_cases("src", examples) if cases
           else solve_mod._profile("src", examples))
    return out, len(seen)


MISS = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", B, [], [])]
BOTH = [Candidate("$CaseA", A, [], []), Candidate("$CaseB", A, [], [])]


def test_case_sets_need_every_pair(monkeypatch):
    (profile, passing), ran = _cases(monkeypatch, [MISS, BOTH], cases=True)
    assert profile is None
    assert passing == [frozenset({"$CaseA"}), frozenset({"$CaseA", "$CaseB"})]
    assert ran == 2


def test_a_profile_alone_stops_at_the_failing_pair(monkeypatch):
    profile, ran = _cases(monkeypatch, [MISS, BOTH], cases=False)
    assert profile is None
    assert ran == 1


def test_pair_work_takes_the_task_id_from_a_path_stem(monkeypatch):
    """A stem may name a path relative to the solvers directory."""
    task = _Task(train=[_Ex(input=[[0]], output=A)], test=[])
    monkeypatch.setattr(solve_mod, "load_task", lambda _id: task)
    stem = "../../.scratch/abcd1234/abcd1234_alt"
    assert solve_mod._pair_work(stem) == [(stem, "abcd1234", "train", 0, task.train[0])]


def test_task_id_of_takes_the_file_name_from_a_path_stem():
    assert solve_mod.task_id_of("../../.scratch/abcd1234/abcd1234_alt") == "abcd1234"
