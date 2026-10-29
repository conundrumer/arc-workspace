"""Write foreign clauses as sampler lines: each is a RULE clause of a corpus case of another task, transplanted to a
branch point of this task.

    work/lm/.venv/bin/python work/lm/data-study/foreign.py [--tasks T ...] [--per-point K] [--max-tries N]
        [--point-seconds S] [--seed S] [--empty-prefix] [--samples DIR] [--data DIR] [--out DIR] [--seconds S]
        [--max-points N] [--depth D] [--points source|all] [--world W] [--stamps FILE] [--queue DIR]

A source clause is a RULE clause of a case in `--data`'s cases.npz (default work/lm/data-full-4663b88a) whose task
is not the target's: the case's model-written tokens from the clause's first token (a RULE) up to and including the
token after which the engine declares a relation. A clause starts at the stream's first model-written token and at
the first one after the engine declares a relation; its index is its place among the case's clauses, from 0.

A branch point (task, case, prefix_tokens) comes from a gold line of the task in `--samples` (default
work/lm/rollouts-s2/samples), as in mutants.py. With `--points all`, the branch points and their gold lines are those
of points.py instead (every rule boundary of each task's first case in `--data`), under `--world` (default Closed),
and the tasks default to every task of `--data`; it takes neither `--empty-prefix` nor `--depth`. A task whose gold stream the engine refuses, faults or panics on is
logged, its counts give {case: {"refused": the message}}, and it writes no lines; a branch point whose prefix replay
raises is logged and counted as {"error": the message}. With `--empty-prefix`, the task has one branch point instead: the
empty prefix of the case of its first gold line in `--samples`, whose gold line is that case's whole stream from
cases.npz with prefix_tokens 0 and prefix_rules 0, and whose `rules` come from one replay of the stream.

At a branch point, a fork of the task's root decoder is stepped through the prefix. A source clause is transplanted
on a fork of that decoder, token by token in the clause's order:
- an out token (a keyword, a color, a number, a lib component) is kept;
- a token that refers to an identifier (a relation or a label) is replaced by the identifier that the source
  identifier maps to. Where it maps to none yet, it is mapped to an identifier of the same kind that the target's
  stream has declared and the mask admits, drawn uniformly;
- each identifier that the engine declares after a token of the source clause maps to the identifier of the same
  kind that the engine declares at the same place after the target's token (the k-th of that kind to the k-th).
  The engine declares every identifier, so a source declaration takes the target engine's fresh identifier.
A candidate is completable where every token is admitted by the mask, no step faults, the decode does not end
before the clause's end, and the first relation the engine declares is declared after the clause's last token. A
candidate is otherwise counted by its reason: "out inadmissible" (an out token outside the mask), "no identifier"
(no declared identifier of the kind that the mask admits), "identifier inadmissible" (the identifier mapped earlier
in the clause is outside the mask), "fault" (the engine panics or refuses a step), "ends elsewhere" (the clause ends
before or after the source's end, or the decode ends early).

Source clauses are drawn uniformly without replacement from the pool of every other task's RULE clauses, by a
generator seeded by `--seed`, the task and prefix_tokens, which also draws the identifiers. A branch point stops at
`--per-point` completable clauses, at `--max-tries` candidates, or at `--point-seconds` of wall time, whichever comes
first. A foreign continuation's stream is the gold's prefix, the transplanted clause and the ids the engine emits
after its tokens; it stops at the clause's end.

With `--depth D` (D of 2 or more), the gold lines of `--samples` are the branch points: each is a program of depth
D-1 (a gold line of compose.py's `prefixes`, whose prefix_tokens is its whole stream and whose branch numbers it),
and a candidate is completable only where, beside the above, some identifier token of the source clause maps to the
prefix's last relation, the relation the engine declares last in the prefix. A candidate is otherwise counted as "no
reference", as soon as no later token of the clause is a relation not yet mapped. The generator's seed takes the
branch in place of prefix_tokens.

`--out` (default work/lm/rollouts-foreign) gets samples/<task>.jsonl for each task: a settings line, the gold lines
(copied from the source file, the empty-prefix gold line, or those of points.py), and one line per foreign continuation with the fields
of model/sample.py's `record` (end "foreign"), a rollout index counted per branch point from 0, and `foreign` {task,
case, clause (the source clause's index in its case), tokens (its model-written token count)}. The lines are
written as they are made, so a run cut by a bound leaves the lines made before it. The settings line has the
source's `settings` and `world` (with `--points all`, the engine's defaults and `--world`); its `args` give `model` null (no LM wrote the lines), `prefix` "random" (the
source's branch points) or "0" (with --empty-prefix), `points`, and `data`, the source's data export (with `--points all`, `--data`); its `model_meta` gives
`fold` null. It also gets counts/<task>.json: per branch point, the candidates by outcome, the lines written and the
seconds taken. A task stops starting branch points after `--seconds` from its start. With `--stamps`, a JSON file of {task: stamp}, the stamp of each task it gives is written to `samples/<task>.stamp` once the task's lines and counts are written. With `--queue`, the tasks come from a queue that several processes share (`points.queued`) in place of `--tasks`.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, json, random, sys, time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = MAIN_ROOT
GEN_VERSION = 2   # raise by hand on any change to how this script makes its lines; allpoints.py reads it into the stamp of a task's samples
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned model/ modules (pinned.py)
import arclog   # noqa: E402
import points   # noqa: E402
from sample import gold as gold_line, hash_seed, kind_name, record   # noqa: E402
from train import KIND_OF   # noqa: E402

REASONS = ("out inadmissible", "no identifier", "identifier inadmissible", "fault", "ends elsewhere", "no reference")


def step(d, i):
    """Step decoder d by id i: (forced ids, consistency), or None where the engine faults or refuses."""
    r = arclog.step_batch([d], [i])[0]
    if isinstance(r, (arclog.Fault, Exception)):
        return None
    return list(r[0]), r[1]


def admits(mask, i):
    return bool(mask[i // 8] >> (i % 8) & 1)


def rule_clauses(ids, model, names, kinds):
    """[(clause index, [(model-written id, [the ids the engine emits after it])])] of the RULE clauses of a stream."""
    out, cur, idx = [], [], 0
    for i, m in zip(ids, model):
        if m:
            cur.append((i, []))
        elif cur:
            cur[-1][1].append(i)
            if kinds[i] == "relation":
                if names[cur[0][0]] == "RULE":
                    out.append((idx, cur))
                cur, idx = [], idx + 1
    return out


def drawn(items, rng):
    """The items in a uniform random order, drawn one at a time by `rng` (a Fisher-Yates step per draw, with the
    swapped places in a dict), so a caller that stops early draws only what it takes."""
    swapped = {}
    for i in range(len(items)):
        j = rng.randrange(i, len(items))
        swapped[i], swapped[j] = swapped.get(j, j), swapped.get(i, i)
        yield items[swapped.pop(i)]


def pool_of(data, names, kinds):
    """Every RULE clause of the cases of `data`: [(task, case, clause index, clause)]."""
    z = np.load(Path(data) / "cases.npz")
    ids, model, off = z["ids"], z["model"], z["offsets"]
    pool = []
    for c, (task, case) in enumerate(zip(z["task"].tolist(), z["case"].tolist())):
        for k, cl in rule_clauses(ids[off[c]:off[c + 1]].tolist(), model[off[c]:off[c + 1]].tolist(), names, kinds):
            pool.append((task, str(case), k, cl))
    return pool


def transplant(d, declared, clause, kinds, rng, ref=None):
    """Step a fork of d through a source clause: (reason or None, the fork, ids, model flags, last consistency).
    Where `ref` is given, some identifier token of the clause must map to it."""
    e = d.fork()
    decl = set(declared)
    amap = {}
    s_ids, s_model, cons = [], [], None
    last = len(clause) - 1
    for k, (tok, src_emit) in enumerate(clause):
        if e.ended:
            return "ends elsewhere", None, None, None, None
        mask = e.admissible()
        kd = KIND_OF.get(kinds[tok])
        if kd is None:
            if not admits(mask, tok):
                return "out inadmissible", None, None, None, None
            t = tok
        elif tok in amap:
            t = amap[tok]
            if not admits(mask, t):
                return "identifier inadmissible", None, None, None, None
        else:
            cands = sorted(i for i in decl if kinds[i] == kinds[tok] and admits(mask, i))
            if not cands:
                return "no identifier", None, None, None, None
            t = amap[tok] = rng.choice(cands)
        f = step(e, t)
        if f is None:
            return "fault", None, None, None, None
        emitted, cons = f
        s_ids += [t] + emitted
        s_model += [1] + [0] * len(emitted)
        for kind in ("relation", "label"):
            for a, b in zip([x for x in src_emit if kinds[x] == kind], [x for x in emitted if kinds[x] == kind]):
                amap[a] = b
        decl |= {x for x in emitted if KIND_OF.get(kinds[x])}
        if ref is not None and ref not in amap.values() and \
                not any(kinds[x] == "relation" and x not in amap for x, _ in clause[k + 1:]):
            return "no reference", None, None, None, None
        if any(kinds[x] == "relation" for x in emitted):
            return (None if k == last else "ends elsewhere"), e, s_ids, s_model, cons
    return "ends elsewhere", None, None, None, None


def replay_prefix(root, ids, n, kinds, where):
    d = root.fork()
    declared = set()
    j = 0
    while j < n:
        f = step(d, ids[j])
        assert f is not None and f[0] == ids[j + 1:j + 1 + len(f[0])], f"{where}: prefix replay"
        declared |= {x for x in f[0] if KIND_OF.get(kinds[x])}
        j += 1 + len(f[0])
    assert j == n and not d.ended, f"{where}: the prefix does not end at a token boundary of a live decode"
    return d, declared


def rule_kinds(root, ids, model):
    """The consistency kind of each RULE clause's END in a whole stream, from one replay."""
    d = root.fork()
    out = []
    for i, m in zip(ids, model):
        if not m:
            continue
        _, cons = d.step(i)
        if cons is not None:
            out.append(kind_name(cons))
        if d.ended:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tasks", nargs="*", help="default: every held-out task of --data with a source file; with --points all, every task of --data")
    ap.add_argument("--per-point", type=int, default=4)
    ap.add_argument("--max-tries", type=int, default=400)
    ap.add_argument("--point-seconds", type=float, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--empty-prefix", action="store_true")
    ap.add_argument("--samples", default=str(ROOT / "work/lm/rollouts-s2/samples"))
    ap.add_argument("--data", default=str(ROOT / "work/lm/data-full-4663b88a"))
    ap.add_argument("--out", default=str(ROOT / "work/lm/rollouts-foreign"))
    ap.add_argument("--seconds", type=float, default=600, help="per task, from the pool's load")
    ap.add_argument("--max-points", type=int, default=None, help="the task's first N branch points only")
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--points", choices=["source", "all"], default="source")
    ap.add_argument("--world", choices=["Closed", "Open"], default="Closed", help="with --points all")
    ap.add_argument("--stamps", help="a JSON file of {task: stamp}: each task's stamp is written to samples/<task>.stamp once its lines and counts are")
    ap.add_argument("--queue", help="a queue directory of points.queued: the tasks come from it in place of --tasks")
    a = ap.parse_args()
    stamps = json.loads(Path(a.stamps).read_text()) if a.stamps else None
    if a.points == "all" and (a.empty_prefix or a.depth > 1):
        ap.error("--points all takes neither --empty-prefix nor --depth")
    z = np.load(Path(a.data) / "cases.npz")
    held = sorted({t for t, h in zip(z["task"].tolist(), z["heldout"].tolist()) if h})
    if a.points == "all":
        first = points.first_cases(a.data)
        tasks = a.tasks or sorted(first)
    else:
        tasks = a.tasks or [t for t in held if (Path(a.samples) / f"{t}.jsonl").exists()]
    vocab = json.load(open(Path(a.data) / "vocab.json"))
    out = Path(a.out); (out / "samples").mkdir(parents=True, exist_ok=True)
    (out / "counts").mkdir(exist_ok=True)
    pool = None
    for task in points.queued(a.queue) if a.queue else tasks:
        t0 = time.time()
        task_json = json.load(open(ROOT / "data/tasks" / f"{task}.json"))
        tests = [t["output"] for t in task_json["test"]] if all("output" in t for t in task_json["test"]) else None
        if a.points == "all":
            session, head = points.head(task, a.world, a.data)
        else:
            head, *lines = [json.loads(l) for l in open(Path(a.samples) / f"{task}.jsonl") if l.strip()]
            golds = [s for s in lines if s["rollout"] == "gold"]
            session = arclog.Session(arclog.Task.from_json(json.dumps(task_json), getattr(arclog.World, head["world"])),
                                     arclog.DecodeSettings(**head["settings"]))
        v = session.vocabulary
        names = [v.name(i) for i in range(len(v))]
        kinds = [v.kind(i) for i in range(len(v))]
        assert names == vocab["names"], f"{task}: the engine's vocabulary differs from {a.data}'s"
        if pool is None:
            pool = pool_of(a.data, names, kinds)
            print(f"pool: {len(pool)} RULE clauses", flush=True)
        mine = [x for x in range(len(pool)) if pool[x][0] != task]
        t0 = time.time()
        root = session.decoder()
        if a.points == "all":
            try:
                golds = points.golds(task, root, *first[task])
            except BaseException as e:
                if not points.caught(e):
                    raise
                points.refused(out, task, first[task][0], e, t0)
                points.write_stamp(out, task, stamps); continue
        if a.empty_prefix:
            c = next(c for c, (t, cs) in enumerate(zip(z["task"].tolist(), z["case"].tolist()))
                     if t == task and str(cs) == golds[0]["case"])
            ids_c = z["ids"][z["offsets"][c]:z["offsets"][c + 1]].tolist()
            model_c = z["model"][z["offsets"][c]:z["offsets"][c + 1]].tolist()
            golds = [gold_line(task, golds[0]["case"], ids_c, model_c, 0, 0, rule_kinds(root, ids_c, model_c))]
        settings = {"settings": head["settings"], "world": head["world"],
                    "args": {"model": None, "prefix": "0" if a.empty_prefix else "random", "data": head["args"]["data"],
                             "source": None if a.points == "all" else str(Path(a.samples) / f"{task}.jsonl"),
                             "points": a.points, "per_point": a.per_point,
                             "max_tries": a.max_tries, "point_seconds": a.point_seconds, "seed": a.seed,
                             "empty_prefix": a.empty_prefix, "depth": a.depth, "maker": "work/lm/data-study/foreign.py"},
                    "model_meta": {"fold": None}}
        task_counts = {}
        with open(out / "samples" / f"{task}.jsonl", "w") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in [settings] + golds)); fh.flush()
            for g in golds[:a.max_points]:
                key = f"{g['case']} {g['prefix_tokens']}" + (f" b{g['branch']}" if a.depth > 1 else "")
                if time.time() - t0 > a.seconds:
                    task_counts[key] = dict(skipped="time"); continue
                tp = time.time()
                n = int(g["prefix_tokens"])
                try:
                    d, declared = replay_prefix(root, g["ids"], n, kinds, f"{task} {g['case']}")
                except BaseException as e:
                    if a.points != "all" or not points.caught(e):
                        raise
                    task_counts[key] = dict(error=points.message(e))
                    print(f"{task} {key}: error, {points.message(e)}", flush=True); continue
                ref = None
                if a.depth > 1:
                    ref = next(x for x in reversed(g["ids"][:n]) if kinds[x] == "relation")
                rng = random.Random(hash_seed(a.seed, task, n if a.depth == 1 else int(g["branch"])))
                cnt = Counter()
                written = 0
                for x in drawn(mine, rng):
                    if written >= a.per_point or cnt["candidates"] >= a.max_tries or time.time() - tp > a.point_seconds:
                        break
                    s_task, s_case, s_k, clause = pool[x]
                    cnt["candidates"] += 1
                    reason, e, s_ids, s_model, cons = transplant(d, declared, clause, kinds, rng, ref)
                    if reason is not None:
                        cnt[reason] += 1; continue
                    cnt["completable"] += 1
                    ids_f, model_f = g["ids"][:n] + s_ids, g["model"][:n] + s_model
                    rec = record(task, g["case"], g["prefix_rules"], written, ids_f, model_f, n, e, cons, tests,
                                 end="foreign", rules=[kind_name(cons)] if cons is not None else [],
                                 model_steps=sum(s_model), refusals=0, max_steps_used=None, max_cont_used=None,
                                 max_clause_used=None, panic=None,
                                 foreign={"task": s_task, "case": s_case, "clause": s_k, "tokens": len(clause)})
                    fh.write(json.dumps(rec) + "\n"); fh.flush()
                    written += 1
                task_counts[key] = dict(cnt, written=written, seconds=round(time.time() - tp, 1))
                (out / "counts" / f"{task}.json").write_text(json.dumps(task_counts, indent=1))
        (out / "counts" / f"{task}.json").write_text(json.dumps(task_counts, indent=1))
        points.write_stamp(out, task, stamps)
        tot = Counter()
        for c in task_counts.values():
            tot.update({k: v for k, v in c.items() if isinstance(v, int)})
        print(f"{task}: {len(task_counts)} branch points, {dict(tot)}, {time.time() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    main()
