"""The usage pace: how fast the operators spend the account's usage, as
`operate.py --help pace` gives it.

An `Op pace:` line names a preset with its arguments (`PARSER`) or the path
of a script that defines `paces` (`Script`). With no such line, the pace
is `DEFAULT`. A preset reads a `Usage` and gives the time
from which it admits a ticket (`Until`); a script gives whether it admits
one now (`Scripted`); a reading that gives neither is
`state.NotComputed`, under which the pace counts as past."""

import argparse
import math
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from controlled_markdown import mctx
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

EVEN_FACTOR = 2.0
"""The default of `even --factor`: the account's two Claude Code accounts
spend twice an even spread of one."""

DEFAULT_WINDOW = WindowName.SEVEN_DAY


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
    """A preset's pace: it admits a ticket from `time` on."""
    time: float


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
        return Until(usage.now)
    return Until(start + WINDOW_SECONDS[window] * w.used_pct / factor / 100)


def by(usage: Usage, end: float, window: WindowName) -> Pace:
    """Within the pace while the used share is at most the share of the
    time from the window's start to `end` that has passed, and from `end`
    on always."""
    found = window_start(usage, window)
    if isinstance(found, str):
        return NotComputed(found)
    w, start = found
    if end <= start:
        return Until(usage.now)
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
    as `build` the function that makes its `Preset` from the parse."""
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
    presets.add_parser("asap", add_help=False).set_defaults(build=lambda a: asap)
    return p, frozenset(presets.choices)


PARSER, PRESETS = parser()


def preset(words: list[str]) -> Preset:
    """The preset `words` give; `LineError` where they give none."""
    args = PARSER.parse_args(words)
    return args.build(args)


DEFAULT: Preset = preset(["even", "--factor", "1", "--window", WindowName.FIVE_HOUR])


def line_pace(rest: str, main_tree: Path) -> Preset | Path | None:
    """The preset or the script path an `Op pace:` line's text after the colon
    gives, a relative path taken from `main_tree`, or None where it is in
    neither form."""
    try:
        words = shlex.split(rest)
    except ValueError:
        return None
    if not words:
        return None
    if words[0] in PRESETS:
        try:
            return preset(words)
        except LineError:
            return None
    if len(words) != 1:
        return None
    path = Path(words[0])
    return path if path.is_absolute() else main_tree / path
