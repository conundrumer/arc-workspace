"""The files of `gen/` one run of the survey reads, each read once: the
arclog and arcdata trees of each solver and the bodies of each arclog
file."""

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from arclog_convert.readback import read_checked
from study.corpus_survey import trees
from study.corpus_survey.bodies import Body, bodies
from study.corpus_survey.trees import Node


@dataclass(frozen=True, eq=False)
class Corpus:
    gen: Path
    stems: tuple[str, ...]
    arclog: dict[str, list[Node]]
    text: dict[str, str]
    """The text of each arclog file, for its comments, which the trees
    do not hold."""

    def bodies(self) -> list[Body]:
        return [b for s in self.stems for b in bodies_of(self, s)]

    def arcdata(self, stem: str) -> list[Node]:
        return arcdata_of(self, stem)

    def nodes(self, stem: str) -> Iterator[list[Node]]:
        """Each list node of the arclog file of `stem`, in the order of
        the text."""
        for f in self.arclog[stem]:
            yield from trees.nodes(f)

    def files(self) -> str:
        """The inputs line's account of the arclog files read."""
        return f"the {len(self.stems)} `.arclog` files of `programs/arclog/`"


@cache
def corpus() -> Corpus:
    gen = trees.gen_dir()
    stems = tuple(trees.stems(gen))
    text = {s: read_checked(gen / f"{s}.arclog") for s in stems}
    return Corpus(gen, stems, {s: trees.arclog(gen, s) for s in stems}, text)


@cache
def bodies_of(c: Corpus, stem: str) -> list[Body]:
    return bodies(stem, c.arclog[stem])


@cache
def arcdata_of(c: Corpus, stem: str) -> list[Node]:
    return trees.arcdata(c.gen, stem)
