"""The counts of instructions of the adopt step: those a gate run wrote,
written into the machine's accepted ones, as `scripts/gate.py --help`
gives."""

from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from gating.commands import ACCEPTED, COMMANDS, GateCommand
from gating.lines import Line, slow
from gating.records import (
    AcceptedCount,
    Counts,
    Tracing,
    count_file,
    keep_counts,
    read_counts,
    standing,
)
from gating.run import RUN_COUNTS


def adopted(accepted: Counts, run: Counts) -> tuple[Counts, list[Line]]:
    """`accepted` with each count of `run` adopted, and the `SLOW` line of
    each that grew past the accepted one."""
    judged: dict[str, tuple[GateCommand, str]] = {c.key(s): (c, s) for c in COMMANDS.values()
                                                  for s in c.stems}
    out = {t: dict(accepted[t]) for t in Tracing}
    grown: list[Line] = []
    for t in Tracing:
        for key, count in sorted(run[t].items()):
            if key not in judged:
                raise ValueError(f"the run's count of {key} names no command on its stem")
            cmd, stem = judged[key]
            stands = standing(accepted[t], key, count.after)
            line = None if stands is None else slow(cmd.name, stem, count.instructions, stands)
            if stands is None or line is not None:
                out[t][key] = count
            else:
                out[t][key] = AcceptedCount(min(count.instructions, stands), count.after)
            if line is not None:
                grown.append(line)
    return out, grown


@dataclass(frozen=True)
class Adoption:
    """The accepted counts at `to` with those of the run at `run` adopted,
    and the `SLOW` lines of that run."""

    run: Path
    to: Path
    counts: Counts
    grown: list[Line]

    def keep(self) -> None:
        """Write `counts` to `to`."""
        keep_counts(self.to, self.counts)
        print(mctx("instructions: the counts of {path} are adopted into {to}").format(
            path=self.run, to=self.to))


def adopt_counts(out: Path) -> Adoption | None:
    """The adoption of the counts of the run under `out`, where it wrote
    them; it writes no count."""
    path = out.resolve() / "gate" / RUN_COUNTS
    to = count_file(ACCEPTED)
    if not path.exists():
        print(mctx("instructions: no {path} stands, so the accepted counts at {to} stay as "
                   "they are").format(path=path, to=to))
        return None
    counts, grown = adopted(read_counts(to), read_counts(path))
    return Adoption(path, to, counts, grown)
