"""The usage pace: how fast the operators spend the account's usage, as
`operate.py --help pace` gives it.

An `Op pace:` line names one or more presets with their arguments (`PARSER`),
joined by `;` (`every`) and with `FIVE_HOUR` where none reads the `five_hour`
window, or the path of a script that defines `paces` (`Script`), with
`FIVE_HOUR` held under it as well (`with_five_hour`). With no such
line, the pace is `DEFAULT`. A preset reads a `Usage` and gives the time
from which it admits a ticket (`Until`), with, for `even` and `by`, the cap on
the running agents of the session's operators (`cap`); a script gives whether
it admits one now (`Scripted`); a reading that gives neither is
`state.NotComputed`, under which the pace counts as past."""

import argparse
import math
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from controlled_markdown import mctx
from operations.constants import SUBAGENT_LIMIT
from operations.state import NotComputed


class WindowName(StrEnum):
    """The name of each window of the usage cache a preset may read."""
    FIVE_HOUR = "five_hour"
    SEVEN_DAY = "seven_day"
    FABLE_WEEKLY = "fable_weekly"


WINDOW_SECONDS: Mapping[WindowName, int] = {
    WindowName.FIVE_HOUR: 5 * 3600,
    WindowName.SEVEN_DAY: 7 * 86400,
    WindowName.FABLE_WEEKLY: 7 * 86400,
}
"""The length of each window of the usage cache a preset may read."""

EVEN_FACTOR = 1.0
"""The default of `even --factor`."""

DEFAULT_WINDOW = WindowName.SEVEN_DAY

BAND_PCT = 10.0
"""The slack, in percentage points, at which the cap reaches
`SUBAGENT_LIMIT`."""


@dataclass(frozen=True)
class Window:
    used_pct: float
    elapsed_pct: float
    resets_at: float


@dataclass(frozen=True)
class Usage:
    """The reading a pace takes: `now`, and each window of the usage cache
    that a fresh reading gives in full."""
    now: float
    windows: Mapping[str, Window]


@dataclass(frozen=True)
class Until:
    """A preset's pace: it admits a ticket from `time` on, and, where `cap`
    is given, starts agents only while fewer than `cap` agents of the
    session's operators run."""
    time: float
    cap: int | None = None


@dataclass(frozen=True)
class Capped:
    """A hold of agent starts by the cap `cap` of a pace that admits work."""
    cap: int


@dataclass(frozen=True)
class Scripted:
    """A script's pace: whether its `paces` admits a ticket now."""
    path: Path
    admits: bool


type Pace = Until | Scripted | NotComputed


def admits(pace: Pace, now: float) -> bool:
    """Whether `pace` admits a ticket at `now`."""
    match pace:
        case Until(time):
            return time <= now
        case Scripted(_, ok):
            return ok
        case NotComputed():
            return False


def cap(slack: float) -> int:
    """The cap at `slack`, the percentage points by which the pace's
    percentage exceeds the window's `used_pct`: `SUBAGENT_LIMIT` for each
    `BAND_PCT` points, rounded up, from 1 to `SUBAGENT_LIMIT`."""
    return min(SUBAGENT_LIMIT, max(1, math.ceil(round(SUBAGENT_LIMIT * slack / BAND_PCT, 9))))


def window_start(usage: Usage, name: WindowName) -> tuple[Window, float] | str:
    w = usage.windows.get(name)
    if w is None:
        return mctx("the usage cache gives no fresh reading of its `{window}` window").format(
            window=name)
    return w, w.resets_at - WINDOW_SECONDS[name]


def even(usage: Usage, factor: float, window: WindowName) -> Pace:
    """Within the pace while the used share is at most `factor` times the
    elapsed share, and otherwise from the time the elapsed share reaches
    the used share over `factor`."""
    found = window_start(usage, window)
    if isinstance(found, str):
        return NotComputed(found)
    w, start = found
    if w.used_pct <= factor * w.elapsed_pct:
        return Until(usage.now, cap(factor * w.elapsed_pct - w.used_pct))
    return Until(start + WINDOW_SECONDS[window] * w.used_pct / factor / 100)


def by(usage: Usage, end: float, window: WindowName) -> Pace:
    """Within the pace while the used share is at most the share of the
    time from the window's start to `end` that has passed, and from `end`
    on always."""
    found = window_start(usage, window)
    if isinstance(found, str):
        return NotComputed(found)
    w, start = found
    passed = 100.0 if end <= start else min(100.0, 100 * (usage.now - start) / (end - start))
    if w.used_pct <= passed or usage.now >= end:
        return Until(usage.now, cap(passed - w.used_pct))
    return Until(min(end, start + (end - start) * w.used_pct / 100))


def asap(usage: Usage) -> Pace:
    return Until(-math.inf)


class LineError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    """A parser that raises `LineError` in place of an exit."""

    def error(self, message: str) -> NoReturn:
        raise LineError(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        raise LineError(message or "")


def iso_time(text: str) -> float:
    t = datetime.fromisoformat(text)
    if t.tzinfo is None:
        raise ValueError(text)
    return t.timestamp()


type Preset = Callable[[Usage], Pace]


def parser() -> tuple[Parser, frozenset[str]]:
    """The parser of an `Op pace:` line's presets, whose defaults are the
    presets' defaults, with the presets' names. Each preset's parse gives
    as `build` the function that makes its `Preset` from the parse, and as
    `window` the window that preset reads."""
    p = Parser(prog="Op pace:", add_help=False)
    presets = p.add_subparsers(dest="preset", required=True, parser_class=Parser)
    e = presets.add_parser("even", add_help=False)
    e.add_argument("--factor", type=float, default=EVEN_FACTOR)
    e.add_argument("--window", type=WindowName, choices=list(WindowName), default=DEFAULT_WINDOW)
    e.set_defaults(build=lambda a: lambda u: even(u, a.factor, a.window))
    b = presets.add_parser("by", add_help=False)
    b.add_argument("end", type=iso_time)
    b.add_argument("--window", type=WindowName, choices=list(WindowName), default=DEFAULT_WINDOW)
    b.set_defaults(build=lambda a: lambda u: by(u, a.end, a.window))
    presets.add_parser("asap", add_help=False).set_defaults(build=lambda a: asap, window=None)
    return p, frozenset(presets.choices)


PARSER, PRESETS = parser()


def preset_window(words: list[str]) -> tuple[Preset, WindowName | None]:
    """The preset `words` give, with the window it reads, None for `asap`;
    `LineError` where they give none."""
    args = PARSER.parse_args(words)
    return args.build(args), args.window


def preset(words: list[str]) -> Preset:
    """The preset `words` give; `LineError` where they give none."""
    return preset_window(words)[0]


def uncapped(given: Preset) -> Preset:
    """`given`, with no cap."""
    def read(usage: Usage) -> Pace:
        pace = given(usage)
        return replace(pace, cap=None) if isinstance(pace, Until) else pace
    return read


def every(presets: Sequence[Preset]) -> Preset:
    """The preset that admits a ticket where each of `presets` admits one:
    from the latest of their times, with the smallest of their caps, or, where
    one of them gives no `Until`, with that one's pace."""
    def read(usage: Usage) -> Pace:
        paces = [given(usage) for given in presets]
        untils = [pace for pace in paces if isinstance(pace, Until)]
        if len(untils) < len(paces):
            return next(pace for pace in paces if not isinstance(pace, Until))
        caps = [u.cap for u in untils if u.cap is not None]
        return Until(max(u.time for u in untils), min(caps, default=None))
    return read


FIVE_HOUR: Preset = preset(["even", "--factor", "1", "--window", WindowName.FIVE_HOUR])
"""The pace an `Op pace:` line of presets holds where none of its presets reads
the `five_hour` window, and an `Op pace: <path>` line holds with its script's
(`with_five_hour`)."""

DEFAULT: Preset = uncapped(FIVE_HOUR)


def with_five_hour(given: Pace, usage: Usage) -> Pace:
    """`FIVE_HOUR` at `usage` where `given` is a `Scripted` that admits, so
    that its `Until` gives the time and the cap, or its `NotComputed` counts
    the pace as past; `given` otherwise, so that a script that refuses stands
    as itself."""
    if isinstance(given, Scripted) and given.admits:
        return FIVE_HOUR(usage)
    return given


def line_pace(rest: str, main_tree: Path) -> Preset | Path | None:
    """The preset or the script path an `Op pace:` line's text after the colon
    gives, a relative path taken from `main_tree`, or None where it is in
    neither form."""
    lexer = shlex.shlex(rest, posix=True, punctuation_chars=";")
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return None
    if not words:
        return None
    if words[0] in PRESETS:
        groups: list[list[str]] = [[]]
        for word in words:
            if word == ";":
                groups.append([])
            else:
                groups[-1].append(word)
        try:
            given = [preset_window(group) for group in groups]
        except LineError:
            return None
        five_hour = [] if any(w is WindowName.FIVE_HOUR for _, w in given) else [FIVE_HOUR]
        return every([p for p, _ in given] + five_hour)
    if len(words) != 1:
        return None
    path = Path(words[0])
    return path if path.is_absolute() else main_tree / path
