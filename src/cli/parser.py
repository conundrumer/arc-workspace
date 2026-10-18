"""The parser of the commands: each subcommand, its options and its help
text, and the function its command runs."""

import argparse
from collections.abc import Callable
from functools import partial
from typing import Any

from checker.render import Section
from checker.render.built import GROUP_WIDTH
from checker.render.recording import COUNT_LINE
from checker.render.commands import SLOWEST
from checker.render.surveys import PLAN_HELP
from checker.store.survey import ROW_CAP
from checker.sweep import MAX_CANDIDATES, TIME_LIMIT_SECONDS
from cli import Command, audit, grid, lint, record, run, survey, text
from controlled_markdown import mctx

SWEEP_LIMIT_HELP = mctx("wall-clock limit in seconds on the sweep's solver "
                       "runs")

GRID_HELP = mctx("""
    - Grid format: one line per row, one digit 0-9 per cell.
        - Spaces and commas between cells are optional.
        - Blank lines and lines starting with `#` are skipped.
        - Text starting with `[` is read as JSON.
    """)

STEM_HELP = mctx("a task id, or the path, in any directory, to a solver file "
                 "whose name starts with the task id")

ASSIGN_HELP = mctx("an `assign` object, in the shape that "
                   "[Witness file](docs/handbook/solver-file.md#witness-file) "
                   "gives")

def unwritten(kind: Section) -> str:
    """Which witnesses the command `kind`, `derive` or `store`, does not
    write, and what it prints for each."""
    return mctx("- Where the branch's `@{word}` line records the verdict "
                "`other`, the command writes no witness for the branch, and "
                "prints the input and the `record` command that writes the "
                "witness with the judged output.").format(word=kind.value)


STEM_OR_ALL_HELP = mctx("{stem}, or every solver when omitted").format(
    stem=STEM_HELP)

RUN_HELP = mctx("""
    - To profile one grid by hand, write a file that includes the lib, and link the functor library that the lib's relations call:
        ```
        { echo '#include "lib.dl"'
          cat programs/solvers/<stem>.dl
          echo '.input in(IO=stdin)'
          echo '.output out(IO=stdout)'
        } > programs/solvers/.tmp.dl
        souffle -D- -w -I programs -L programs -lfunctors programs/solvers/.tmp.dl
        ```
    - Souffle reads one fact line per cell on stdin: `[top, bottom, left, right]` edge distances, a tab, then the color.
    - For a solver with GRID calls or RIGID blocks, put the `expand` command's output in place of the include line and the `cat` line.
    - Add `-p <file>` for a profile that souffleprof reads.
    """)


type Handler = Callable[[argparse.Namespace], int]


def parser() -> argparse.ArgumentParser:
    """The parser, with a subparser for each `Command`. Each subparser
    holds, as `handler`, the function its command runs."""
    top = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=mctx("""
            - Run Souffle solvers and their checks.
            - The commands follow, each with what it runs.
            - `uv run python scripts/run_dl.py <command> --help` prints a command's arguments.
            - A stem, which the commands take, is {stem}.
            """).format(stem=STEM_HELP),
    )
    sub = top.add_subparsers(dest="cmd", required=True, title="commands",
                             metavar="<command>")

    def command(name: Command, handler: Handler, **kwargs: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(
            name, formatter_class=argparse.RawDescriptionHelpFormatter, **kwargs)
        p.set_defaults(handler=handler)
        return p

    run_p = command(
        Command.RUN, run.dispatch,
        help=mctx("pairs, lint and determination checks, the command run when "
                  "the first argument is not a command"),
        epilog=RUN_HELP,
    )
    lint_p = command(
        Command.LINT, lambda a: lint.cmd_lint(a.stems or None, a.hints),
        help=mctx("lint only, no pair runs"),
        description=mctx("A hint changes neither the verdict nor the exit "
                         "code."),
    )
    run_p.add_argument("stems", nargs="*",
                       help=mctx("the solvers to run, each {stem}, or every "
                                 "solver when omitted; more than one gives "
                                 "the report of a run over every solver, "
                                 "for those solvers alone").format(stem=STEM_HELP))
    lint_p.add_argument("stems", nargs="*",
                      help=mctx("the solvers to lint, each {stem}, or every "
                                "solver when omitted").format(stem=STEM_HELP))
    for p in (run_p, lint_p):
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help=mctx("include the hints section"))
    run_p.add_argument("--time", action="store_true", dest="timed",
                       help=mctx("print wall times: per phase for one solver, "
                                 "the slowest {n} for more than one").format(
                                     n=SLOWEST))
    run_p.add_argument("--json", action="store_true", dest="as_json",
                       help=mctx("print the report of a run over the solvers "
                                 "given as one JSON object, which for one "
                                 "solver takes the place of the one-solver "
                                 "output"))
    run_p.add_argument("--pairs", metavar="FILE",
                       help=mctx("run the one solver given against the pairs "
                                 "of this JSON file in place of the task's, "
                                 "printing the grids the solver emits for a "
                                 'pair without "output"'))

    grid_p = command(
        Command.GRID,
        lambda a: grid.cmd_grid(a.stem, a.file, a.every, a.cases, a.assign),
        help=mctx("run one solver on a grid you write, printing what each "
                  "witnessed case emits"),
        description=mctx("""
            - Prints the output of the concept case, of each branch's model, and of each other witnessed case, by the names `record` writes.
                - When the case of a branch's model or of a `--case` name is no witnessed case, the witnessed cases that take its branches and differ from the concept case at the fewest choice points are printed in its place.
                - When no witnessed case takes the branches of a `--case` name, the command prints `` {refusal} `` and nothing else.
            - Cases that emit the same output are listed together above that output: on one line, joined by `, ` and ending in `:`, or, when that line would pass {width} characters, one per indented line and then a line of `:`.
            - After them, each case that emits no grid is listed on one line:
                - `<case>: emits nothing` for a case whose reason is `NoOutput`, and for a case that gives no reason and takes no `@derive` or `@store` branch.
                - `<case>: undefined` for each other case that emits no grid, which includes a case whose reason is `NoDerivedValue` and a case that gives no reason and takes such a branch.
            - After those comes the count line, `{count}`: the count of the witnessed cases, of the solver's cases, and of the distinct grids the witnessed cases emit.
            - After the count line comes `no case takes $<Ctor>` for each constructor of `Choice`, at any depth, that no case of the solver takes.
            """).format(width=GROUP_WIDTH,
                 refusal=text.NO_WITNESSED_TAKES.format(name="<name>"),
                 count=COUNT_LINE.format(n="<n>", m="<m>", g="<g>")),
        epilog=GRID_HELP,
    )
    grid_p.add_argument("stem", help=STEM_HELP)
    grid_p.add_argument("file", nargs="?",
                      help=mctx("grid file, or stdin when omitted or `-`"))
    shown = grid_p.add_mutually_exclusive_group()
    shown.add_argument("--all", action="store_true", dest="every",
                       help=mctx("list each case of the solver under its own "
                                 "name, in place of the fewest names that "
                                 "cover a group's cases"))
    shown.add_argument("--case", action="append", dest="cases",
                       metavar="CASE",
                       help=mctx("print only this case, with the option given "
                                 "once for each case to print"))
    grid_p.add_argument("--assign", metavar="JSON", dest="assign",
                      help=ASSIGN_HELP)

    relation = command(
        Command.RELATION, lambda a: grid.cmd_relation(a.stem, a.args, a.assign),
        help=mctx("run one solver on a grid you write, printing the rows of "
                  "each relation the arguments give"),
        description=mctx("""
            - Prints each relation's rows as Souffle writes them, one fact per line, under the relation's attribute names.
            - The last argument is the grid file when it is `-` or the path of a file, and otherwise the grid is read from stdin.
            """),
        epilog=GRID_HELP,
    )
    relation.add_argument("stem", help=STEM_HELP)
    relation.add_argument("args", nargs="+", metavar="relation",
                          help=mctx("a relation, `inst.rel` for one of an "
                                    "instance, and after the relations the "
                                    "grid file, if any"))
    relation.add_argument("--assign", metavar="JSON", dest="assign",
                          help=ASSIGN_HELP)

    record_p = command(
        Command.RECORD, record.dispatch,
        help=mctx("run one solver on a grid you write and write the run into "
                  "the task's witness file"),
        description=mctx("""
            - The witness replaces a witness with the same id.
            - For an `other` verdict, put the judged output after a `---` line of the grid text.
            - Without `--separates` or `--assign`, record runs the witness of that id again on the input and `assign` the file holds for it, and writes only its groups.
                - Where each line that records the witness's verdict gives `other`, the witness keeps its judged output.
                - Where each line that records the witness's verdict gives another verdict, the witness's groups replace its judged output.
                - Where no line records the witness's verdict, the witness's groups replace its judged output.
                - Where the lines that record the witness's verdict give `other` and another verdict both, the run fails.
            - Where `file` is omitted, a new id reads the grid from stdin, and an id the witness file holds keeps its input: `--separates` alone then keeps its groups and takes the new text, and `--assign` runs it again at the new `assign`.
            """),
        epilog=GRID_HELP,
    )
    record_p.add_argument("stem", help=STEM_HELP)
    record_p.add_argument("id", nargs="?",
                          help=mctx("the witness's id, required unless "
                                    "`--format` or `--all`"))
    record_p.add_argument("file", nargs="?",
                          help=mctx("grid file, or `-` for stdin"))
    record_p.add_argument("--separates",
                          help=mctx("what the witness separates, required "
                                    "for a new witness"))
    record_p.add_argument("--assign", metavar="JSON", dest="assign",
                          help=mctx("the witness's `assign` object"))
    record_p.add_argument("--remove", action="store_true", dest="remove",
                          help=mctx("take the witness of the id out of the "
                                    "file"))
    record_p.add_argument("--all", action="store_true", dest="every",
                          help=mctx("run every witness of the file again, "
                                    "writing the file only when every run "
                                    "succeeds"))
    record_p.add_argument("--witness-file", metavar="PATH",
                          dest="witness_file",
                          help=mctx("a witness file to read and write in "
                                    "place of the task's"))
    record_p.add_argument("--format", action="store_true", dest="as_format",
                          help=mctx("rewrite the task's witness file through "
                                    "the serializer and add no witness"))

    sweep = command(
        Command.SWEEP,
        lambda a: survey.cmd_sweep(a.stem, a.cap, a.sweep_limit),
        help=mctx("parameter value sweep only"),
        description=mctx("""
            - For each Params parameter, the values of its domain that reproduce every train pair, and for a parameter whose value is a set of rows, how many single-row changes of its stored set reproduce them.
            - A ✓ marks a parameter that a whole sweep finds the train pairs fix to its stored value.
            - Where a parameter has more candidates than `cap`, the sweep tries only single-column changes of the stored facts, up to `cap`.
            """),
    )
    sweep.add_argument("stem", help=STEM_HELP)
    sweep.add_argument("cap", nargs="?", type=int, default=MAX_CANDIDATES,
                       help=mctx("the most candidates the sweep tries for one "
                                 "parameter, or, for a parameter swept as a "
                                 "set, the most single-row changes of its "
                                 "stored set it tries"))
    sweep.add_argument("--sweep-limit", type=float, dest="sweep_limit",
                       default=TIME_LIMIT_SECONDS, help=SWEEP_LIMIT_HELP)

    command(
        Command.DELETIONS, lambda a: survey.cmd_deletions(a.stem),
        help=mctx("deletion report only"),
        description=mctx("The clauses and facts of the solver that no train "
                         "pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    audit_p = command(
        Command.AUDIT,
        lambda a: audit.cmd_audit(a.stem, a.witness_file),
        help=mctx("witness report + dropped case report + derive report + "
                  "store report + open values report, writing no "
                  "witness"),
    )
    audit_p.add_argument("stem", help=STEM_HELP)
    audit_p.add_argument("--witness-file", metavar="PATH",
                         dest="witness_file",
                         help=mctx("a witness file to read in place of the "
                                   "task's"))
    command(
        Command.DROP_ONE, lambda a: survey.cmd_drop_one(a.stem),
        help=mctx("which stored facts of a multi-fact parameter no train pair "
                  "needs"),
        description=mctx("A fact that only the test pairs need is reported "
                         "apart from one that no pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    command(
        Command.DERIVED_CONSTANT, lambda a: survey.cmd_derived_constant(a.stem),
        help=mctx("program relations that hold the same tuples on every "
                  "example"),
        description=mctx("""
            - The examples are the train and test examples.
            - A relation that is empty on every example is left out, and so is one that keeps its tuples on grids made from each example's palette.
            """),
    ).add_argument("stem", help=STEM_HELP)
    witness = command(
        Command.WITNESS,
        lambda a: audit.cmd_witness(a.stem, a.file, a.every_case,
                                    a.witness_file, a.try_path,
                                    a.dropped_from),
        help=mctx("run the task's witness grids and report where the solver "
                  "and the witness file disagree"),
        description=mctx("""
            - The report checks the file's shape first.
            - With `--file` and no stem, the shape check is the whole report, and it needs no solver.
            - A `stem` given as a path reads the witness file of its task id too.
            - With `--try`, the command runs, on the grid file, the cases `record` would run, as if the grid file were added to the witness file; it writes nothing, and prints:
                - the groups of the grid file;
                - the unseparated branch differences whose pairs it separates;
                - the subsumed branch differences whose pairs it shows defined and differing;
                - the subsumed branch differences that the cases it newly witnesses bring.
            """),
    )
    witness.add_argument("stem", nargs="?",
                         help=STEM_HELP)
    file_or_every = witness.add_mutually_exclusive_group()
    file_or_every.add_argument(
        "--file", metavar="PATH",
        help=mctx("a witness file to read in place of the task's, with a "
                  "report of only the findings on its witnesses"))
    witness.add_argument("--witness-file", metavar="PATH",
                         dest="witness_file",
                         help=mctx("a witness file to read in place of the "
                                   "task's, with the report the task's "
                                   "file gets"))
    witness.add_argument("--try", metavar="PATH", dest="try_path",
                         help=mctx("a grid file read as a candidate witness"))
    file_or_every.add_argument(
        "--every-case", action="store_true",
        help=mctx("run with `impl_choice` holding every case of `Choice`, "
                  "and for each dropped case print the first of these "
                  "the runs show: it fails Fit, no witness "
                  "separates it from another case, it fails Subsumption, "
                  "or it fails none of them"))
    witness.add_argument(
        "--dropped-from", metavar="PATH", dest="dropped_from",
        help=mctx("with `--every-case`, a solver file of the same task "
                  "whose dropped cases, the cases of the solver's `Choice` "
                  "it does not hold, take the place of the solver's own"))
    derive = command(
        Command.DERIVE, partial(audit.derive_or_store, audit.cmd_derive),
        help=mctx("the built-in derivations of stored parameters that fit, "
                  "each a branch, with each witness it builds, which it "
                  "writes into the task's witness file"),
        # The first item says at which assignment the witness stands, which
        # docs/handbook/principles.md#witnesses states: without it, refine
        # pass b2862040 (ticket 10-292) read a witness at a changed parameter
        # as wrong and rebuilt it by hand, and a later run (ticket 6-963)
        # grepped src, scripts, docs and prompts for what "the stored value
        # there" means.
        description=mctx("""
            - Each built-in derivation of a stored parameter, a proposer of [proposers.dl](programs/proposers.dl), for which some case of the solver that takes its branch fits the task, with the witness that separates the cases that take the branch from the cases that take the stored value there and the same branches elsewhere, at the assignment that changes the fewest parameters at which they differ.
            - A derivation is listed with no witness in each of these cases:
                - Its `@ignore: derive <Proposer> — <reason>` line, or its parameter's `@ignore: derive — <reason>` line, stands.
                - The `@ignore: derive <name>` lines exclude every case that takes its branch.
                - The concept case fits, and no case takes its branch.
            - The command writes each witness it builds into the task's witness file, as `record` writes one, with the `@derive` line standing, and keeps a witness the file already holds for the branch.
            """)
        + "\n" + unwritten(Section.DERIVE),
    )
    store = command(
        Command.STORE, partial(audit.derive_or_store, audit.cmd_store),
        help=mctx("the program relations that hold one value on every "
                  "input, with each witness it builds, which it writes into "
                  "the task's witness file"),
        # The first item says at which assignment the witness stands, which
        # docs/handbook/principles.md#witnesses states. The user's words,
        # session 7fd429fb, 2026-10-13T02:58:03Z: "that should use
        # clarification, but like improving the wording, not like adding new
        # lines."
        description=mctx("""
            - Each program relation between `in` and `out`, and each one a `@store` line names that the derivation of `out` reads, whose value over a subset of its columns is the same on every input of the task, with the witness that separates the cases that take its `<rel>=stored` branch from the cases that take the derived value there and the same branches elsewhere, at the assignment that changes the fewest parameters at which they differ.
            - The command writes each witness it builds into the task's witness file, as `record` writes one, with the `@store` line standing, and keeps a witness the file already holds for the branch.
            """)
        + "\n" + unwritten(Section.STORE) + "\n" + mctx(
            "- A relation with more than {cap} rows on some input is not "
            "checked."
        ).format(cap=ROW_CAP),
    )
    for p in (derive, store):
        p.add_argument("stem", nargs="?",
                       help=mctx("{stem}, or, when omitted, every solver, with "
                                 "nothing written").format(stem=STEM_HELP))
        p.add_argument("--witness-file", metavar="PATH", dest="witness_file",
                       help=mctx("a witness file to read and write in place "
                                 "of the task's"))
    plan = command(
        Command.DETERMINATION_PLAN,
        lambda a: survey.cmd_determination_plan(a.stem, a.verdicts),
        help=mctx("which Params parameters need determination relations"),
        description=PLAN_HELP,
    )
    plan.add_argument("stem", help=STEM_HELP)
    plan.add_argument("--verdicts", action="store_true",
                      help=mctx("append each proposer's verdict on each "
                                "parameter"))

    size = command(
        Command.SIZE, lambda a: survey.cmd_size(a.stem),
        help=mctx("literal count per solver"),
        description=mctx("Prints each solver's literal count, count "
                         "first."),
    )
    size.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)

    keywords = command(
        Command.KEYWORDS, lambda a: survey.cmd_keywords(a.stem),
        help=mctx("how many solvers list each keyword of "
                  "[Keywords](docs/handbook/keywords.md)"),
        description=mctx("Counts, for each keyword of "
                         "[Keywords](docs/handbook/keywords.md), the "
                         "solvers whose `// @keywords:` line lists it, and "
                         "lists each header keyword that doc does not "
                         "list."),
    )
    keywords.add_argument("stem", nargs="*",
                          help=mctx("solvers to read, or all of them when "
                                    "omitted"))

    since = command(
        Command.SINCE, lambda a: survey.cmd_since(a.when),
        help=mctx("the solvers that the commits since a date-time touch"),
        description=mctx("""
            - Prints the stem of each solver that the commits since the given date-time touch, and of each solver whose working-tree content differs from HEAD.
            - A commit that touches more than half the solvers gives no stems.
            - When the other commits together touch more than half, only the solvers that those commits add are printed from them.
            """),
    )
    since.add_argument("when", help=mctx("a date-time git reads, e.g. "
                                         '"2026-09-08 14:30"'))

    command(
        Command.EXPAND, lambda a: survey.cmd_expand(a.stem),
        help=mctx("the source after GRID and RIGID expansion, as Souffle "
                  "sees it"),
        description=mctx("Prints the solver source with each GRID call and "
                         "RIGID block replaced by what it emits and nothing else "
                         "changed."),
    ).add_argument("stem", help=STEM_HELP)
    assert sub.choices.keys() == set(Command)
    return top
