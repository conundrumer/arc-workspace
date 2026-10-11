"""The print of agent run profiles, as the HELP of `profile_runs` gives
it."""

import math
import time

from controlled_markdown import mctx
from run_records import Group, Key, Part, Run
from ticketing.times import MINUTE_FORM

# The characters of a call's command or of an agent's text output that
# `--running` prints.
COMMAND_WIDTH = 160


def minutes(s: float) -> str:
    return f"{s / 60:.1f}m"


def clock(t: float | None) -> str:
    return time.strftime(MINUTE_FORM, time.gmtime(t)) if t is not None else "?"


def one_line(text: str, tail: bool = False) -> str:
    """`text` on one line, cut to its first COMMAND_WIDTH characters, or
    with `tail` to its last."""
    line = " ".join(text.split())
    if len(line) <= COMMAND_WIDTH:
        return line
    if tail:
        return "..." + line[3 - COMMAND_WIDTH:]
    return line[:COMMAND_WIDTH - 3] + "..."


def percentile(values: list[float], p: float) -> float:
    """The nearest-rank percentile of a list of numbers."""
    v = sorted(values)
    return v[max(0, min(len(v) - 1, math.ceil(len(v) * p / 100) - 1))]


def by_agent_type(runs: list[Run]) -> dict[str, list[Run]]:
    by_type: dict[str, list[Run]] = {}
    for r in runs:
        by_type.setdefault(r.agent_type, []).append(r)
    return by_type


def dollars(cost: float | None) -> str:
    return f"${cost:.2f}" if cost is not None else "?"


def print_costs(by_type: dict[str, list[Run]], order: list[str]) -> None:
    """Per agent type, the total token cost of its priced runs, its share of
    the total over all priced runs, the median cost of a priced run, and the
    number of runs whose cost is unknown."""
    priced = {k: [r.cost for r in by_type[k] if r.cost is not None] for k in order}
    whole = sum(sum(c) for c in priced.values())
    print(f"\n{'type':<18} {'cost':>9} {'share':>6} {'p50':>8} {'unpriced':>8}")
    for kind in order:
        costs = priced[kind]
        total = sum(costs)
        share = f"{100 * total / whole:5.0f}%" if whole else "     -"
        median = dollars(percentile(costs, 50)) if costs else "?"
        print(f"{kind:<18} {dollars(total):>9} {share} {median:>8} "
              f"{len(by_type[kind]) - len(costs):>8}")


def print_split(runs: list[Run], split: float, undecided: list[str]) -> None:
    """The print of `--split`, as the HELP of `profile_runs` gives it."""
    sides: dict[str, tuple[list[Run], list[Run]]] = {}
    for r in runs:
        if r.start is None:
            undecided.append(mctx("{run}: its start is unknown, so it joins "
                                  "no side of the split").format(run=r.label))
            continue
        side = sides.setdefault(r.agent_type, ([], []))
        side[r.start >= split].append(r)
    print(f"\n{'type':<18} {'side':<6} {'runs':>4} {'ctx p50':>8} "
          f"{'first p50':>9} {'cost p50':>8}")
    for kind in sorted(sides):
        for name, rs in zip(("before", "after"), sides[kind]):
            if not rs:
                print(f"{kind:<18} {name:<6} {'-':>4} {'-':>8} {'-':>9} {'-':>8}")
                continue
            contexts = [c for r in rs for c in r.request_contexts]
            firsts = [r.request_contexts[0] for r in rs if r.request_contexts]
            costs = [r.cost for r in rs if r.cost is not None]
            print(f"{kind:<18} {name:<6} {len(rs):>4} "
                  f"{median_tokens(contexts):>8} {median_tokens(firsts):>9} "
                  f"{dollars(percentile(costs, 50)) if costs else '?':>8}")


def median_tokens(values: list[int]) -> str:
    return f"{percentile([float(v) for v in values], 50):.0f}" if values else "?"


def part_split(parts: dict[Part, float]) -> str:
    return "  ".join(f"{p.value} {minutes(parts[p])}" for p in Part)


def print_groups(groups: dict[Key, Group], top: int, wall: float,
                 present: dict[Key, int] | None = None) -> None:
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1].time, kv[0][0].value, kv[0][1]))
    for (part, label), g in ranked[:top or None]:
        pct = f"{100 * g.time / wall:3.0f}%" if wall else "   -"
        ran = f"  ran {minutes(g.ran)}" if g.ran else ""
        runs = f"  in {present[(part, label)]} runs" if present else ""
        print(f"  {part.value:<5} {minutes(g.time):>8} {pct}  {g.calls:>4}x  {label}{ran}{runs}")


def print_types(runs: list[Run], pct: float, top: int) -> None:
    by_type = by_agent_type(runs)
    order = sorted(by_type, key=lambda k: (-sum(r.wall for r in by_type[k]), k))
    print(f"{'type':<18} {'runs':>4} {'min':>7} {'p50':>7} {f'p{pct:g}':>7} "
          f"{'max':>7} {'total':>8} {'act p50':>8} {f'act p{pct:g}':>8}  "
          + "  ".join(f"{p.value:>6}" for p in Part))
    for kind in order:
        rs = by_type[kind]
        walls = [r.wall for r in rs]
        active = [r.active for r in rs]
        total = sum(walls)
        shares = "  ".join(
            f"{(100 * sum(r.parts[p] for r in rs) / total if total else 0):5.0f}%"
            for p in Part)
        print(f"{kind:<18} {len(rs):>4} {minutes(min(walls)):>7} "
              f"{minutes(percentile(walls, 50)):>7} {minutes(percentile(walls, pct)):>7} "
              f"{minutes(max(walls)):>7} {minutes(total):>8} "
              f"{minutes(percentile(active, 50)):>8} {minutes(percentile(active, pct)):>8}  {shares}")
    print_costs(by_type, order)
    if top == 0:
        return
    for kind in order:
        rs = by_type[kind]
        merged: dict[Key, Group] = {}
        present: dict[Key, int] = {}
        for r in rs:
            for k, g in r.groups.items():
                m = merged.setdefault(k, Group())
                m.time += g.time
                m.calls += g.calls
                m.ran += g.ran
                present[k] = present.get(k, 0) + 1
        total = sum(r.wall for r in rs)
        print(f"\n{kind}: {minutes(total)} over {len(rs)} runs")
        print_groups(merged, top, total, present)
