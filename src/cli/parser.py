"""The parser of the commands: each subcommand, its options and its help
text, and the function its command runs."""

import argparse
from collections.abc import Callable, Collection
from functools import partial
from typing import Any

from checker.sweep import MAX_CANDIDATES, TIME_LIMIT_SECONDS
from cli import audit, record, run, survey
from controlled_markdown import mctx

TIME_LIMIT_HELP = mctx("wall-clock limit in seconds on the sweep's solver "
                       "runs; once they take that long, the parameter in "
                       "progress reports as cut, and each parameter not yet "
                       "started reports as not swept")

GRID_HELP = mctx("Grid format: one line per row, one digit 0-9 per cell. "
                 "Spaces and commas between cells are optional; blank lines "
                 "and lines starting with `#` are skipped. Text starting with "
                 "`[` is read as JSON.")

STEM_HELP = mctx("a task id, or the path to a solver file whose name starts "
                 "with the task id")

ASSIGN_HELP = mctx("an `assign` object, in the witness file's shape")

STEM_OR_ALL_HELP = mctx("a task id, or the path to a solver file whose name "
                        "starts with the task id; every solver when omitted")

RUN_HELP = mctx("""
    - To profile one grid by hand, write a file beside the solvers, so that `#include "../lib.dl"` resolves, and link the functor library that the lib's relations call:
        ```
        { echo '#include "../lib.dl"'
          cat programs/solvers/<stem>.dl
          echo '.input in(IO=stdin)'
          echo '.output out(IO=stdout)'
        } > programs/solvers/.tmp.dl
        souffle -D- -w -L programs -lfunctors programs/solvers/.tmp.dl
        ```
    - Souffle reads one fact line per cell on stdin: `[top, bottom, left, right]` edge distances, a tab, then the color. In a 3x3 grid the top-left cell, in color 7, is `[0, 2, 0, 2]<TAB>7`.
    - For a solver with GRID calls or RIGID blocks, put the `expand` command's output in place of the `cat` line.
    - Add `-p <file>` for a profile that souffleprof reads.
    """)


type Handler = Callable[[argparse.Namespace], int]


def parser() -> tuple[argparse.ArgumentParser, Collection[str]]:
    """The parser, and the command names its subparsers take. Each
    subparser carries, as `handler`, the function its command runs."""
    top = argparse.ArgumentParser(
        description=mctx("Run Souffle solvers and their checks."),
    )
    sub = top.add_subparsers(dest="cmd", required=True)

    def command(name: str, handler: Handler,
                **kwargs: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(name, **kwargs)
        p.set_defaults(handler=handler)
        return p

    run_p = command(
        "run", run.dispatch,
        help=mctx("pairs, lint and determination checks; the command run when "
                  "the first argument is not a command"),
        epilog=RUN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lint = command(
        "lint", lambda a: run.cmd_lint(a.stem, a.hints),
        help=mctx("lint only, no pair runs"),
        description=mctx("A hint changes neither the verdict nor the exit "
                         "code."),
    )
    run_p.add_argument("stems", nargs="*",
                       help=mctx("the solvers to run, each a stem or a path to "
                                 "a solver file whose name starts with the task "
                                 "id. One solver runs its pairs, lint and "
                                 "determination check; several give the report "
                                 "of a run over every solver, over those "
                                 "solvers; none runs every solver."))
    lint.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)
    for p in (run_p, lint):
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help=mctx("include the hints section"))
    run_p.add_argument("--time", action="store_true", dest="timed",
                       help=mctx("print wall times: per phase for one solver, "
                                 "the slowest 15 for more than one"))
    run_p.add_argument("--json", action="store_true", dest="as_json",
                       help=mctx("print the report of a run over several "
                                 "solvers as one JSON object; with one solver, "
                                 "print that report in place of the "
                                 "one-solver output"))
    run_p.add_argument("--pairs", metavar="FILE",
                       help=mctx("run the one solver given against the pairs "
                                 "of this JSON file in place of the task's; "
                                 'for a pair without "output", print the '
                                 "grids the solver emits"))

    grid = command(
        "grid",
        lambda a: record.cmd_grid(a.stem, a.file, a.every, a.cases, a.assign),
        help=mctx("run one solver on a grid you write, printing what each "
                  "case the runner holds emits"),
        description=mctx("Prints the output of the concept case, of each "
                         "branch's model, and of each other case the runner "
                         "holds, by the names `record` writes. When "
                         "`impl_choice` does not contain the case of a branch's "
                         "model or of a `--case` name, the cases "
                         "`impl_choice` contains that take its branches and "
                         "differ from the concept case at the fewest choice "
                         "points are printed in its place. Cases that emit "
                         "the same output are listed "
                         "together above that output: on one line, joined by "
                         "`, ` and ending in `:`, or, when that line would "
                         "pass 100 characters, one per indented line and "
                         "then a line of `:`. After them come `<case>: emits "
                         "nothing` for each case that emits no grid, and "
                         "`<case>: undefined` for each case that takes a "
                         "`@derive` or `@store` branch and emits none."),
        epilog=GRID_HELP,
    )
    grid.add_argument("stem", help=STEM_HELP)
    grid.add_argument("file", nargs="?",
                      help=mctx("grid file; stdin when omitted or `-`"))
    shown = grid.add_mutually_exclusive_group()
    shown.add_argument("--all", action="store_true", dest="every",
                       help=mctx("name each case of the solver on its own, "
                                 "in place of the fewest names that cover "
                                 "a group's cases"))
    shown.add_argument("--case", action="append", dest="cases",
                       metavar="CASE",
                       help=mctx("print only this case; repeat for each "
                                 "case"))
    grid.add_argument("--assign", metavar="JSON", dest="assign",
                      help=ASSIGN_HELP)

    relation = command(
        "relation", lambda a: record.cmd_relation(a.stem, a.args, a.assign),
        help=mctx("run one solver on a grid you write, printing the rows of "
                  "each relation the arguments give"),
        description=mctx("Prints each relation's rows as Souffle writes "
                         "them, one fact per line, under the relation's "
                         "attribute names. A column of type `Choice` holds "
                         "each case by its shortest name. The last argument "
                         "is the grid file when it is `-` or the path of a "
                         "file; otherwise the grid is read from stdin."),
        epilog=GRID_HELP,
    )
    relation.add_argument("stem", help=STEM_HELP)
    relation.add_argument("args", nargs="+", metavar="relation",
                          help=mctx("a relation, `inst.rel` for one of an "
                                    "instance; then the grid file, if any"))
    relation.add_argument("--assign", metavar="JSON", dest="assign",
                          help=ASSIGN_HELP)

    record_p = command(
        "record", record.dispatch,
        help=mctx("run one solver on a grid you write and write the run into "
                  "the task's witness file"),
        description=mctx("The witness replaces a witness with the same id. "
                         "For an `other` verdict, put the judged output "
                         "after a `---` line of the grid text. Without "
                         "`--separates`, record runs the witness of that id "
                         "again on the input and `assign` the file holds "
                         "for it, and writes only its groups; `--all` does "
                         "this for every witness of the file. A witness "
                         "with verdict `other` keeps its judged output."),
        epilog=GRID_HELP,
    )
    record_p.add_argument("stem", help=STEM_HELP)
    record_p.add_argument("id", nargs="?",
                          help=mctx("the witness's id; required unless "
                                    "`--format` or `--all`"))
    record_p.add_argument("file", nargs="?",
                          help=mctx("grid file; stdin when omitted or `-`"))
    record_p.add_argument("--separates",
                          help=mctx("what the witness separates; required "
                                    "for a new witness"))
    record_p.add_argument("--assign", metavar="JSON", dest="assign",
                          help=mctx("the witness's `assign` object"))
    record_p.add_argument("--all", action="store_true", dest="every",
                          help=mctx("run every witness of the file again; the "
                                    "file is written only when every run "
                                    "succeeds"))
    record_p.add_argument("--witness-file", metavar="PATH",
                          dest="witness_file",
                          help=mctx("a witness file to read and write in "
                                    "place of the task's"))
    record_p.add_argument("--format", action="store_true", dest="as_format",
                          help=mctx("rewrite the task's witness file through "
                                    "the serializer and add no witness"))

    sweep = command(
        "sweep",
        lambda a: survey.cmd_sweep(a.stem, a.cap, a.time_limit),
        help=mctx("parameter value sweep only"),
        description=mctx("For each Params parameter, the values of its "
                         "domain that reproduce every train pair. A ✓ marks "
                         "a parameter that a whole sweep finds the train "
                         "pairs fix to its stored value."),
    )
    sweep.add_argument("stem", help=STEM_HELP)
    sweep.add_argument("cap", nargs="?", type=int, default=MAX_CANDIDATES,
                       help=mctx("the most candidates the sweep tries for one "
                                 "parameter; when a parameter has more, the "
                                 "sweep tries only single-column changes of "
                                 "the stored facts, or single-row changes "
                                 "for a parameter swept as a set, up to that "
                                 "count"))
    sweep.add_argument("--time-limit", type=float, dest="time_limit",
                       default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)

    command(
        "deletions", lambda a: survey.cmd_deletions(a.stem),
        help=mctx("deletion report only"),
        description=mctx("The clauses and facts of the solver that no train "
                         "pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    audit_p = command(
        "audit",
        lambda a: audit.cmd_audit(a.stem, a.time_limit, a.witness_file),
        help=mctx("parameter value sweep + deletion report + witness report "
                  "+ dropped case report + derive report + store report; writes no "
                  "witness"),
    )
    audit_p.add_argument("stem", help=STEM_HELP)
    audit_p.add_argument("--time-limit", type=float, dest="time_limit",
                         default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)
    audit_p.add_argument("--witness-file", metavar="PATH",
                         dest="witness_file",
                         help=mctx("a witness file to read in place of the "
                                   "task's"))
    command(
        "drop-one", lambda a: survey.cmd_drop_one(a.stem),
        help=mctx("which stored facts of a multi-fact parameter no train pair "
                  "needs"),
        description=mctx("A fact that only the test pairs need is reported "
                         "apart from one that no pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    command(
        "derived-constant", lambda a: survey.cmd_derived_constant(a.stem),
        help=mctx("program relations that hold the same tuples on every "
                  "example"),
        description=mctx("The examples are the train and test examples. A "
                         "relation that is empty on every example is left "
                         "out, and so is one that keeps its tuples on "
                         "grids made from each example's palette."),
    ).add_argument("stem", help=STEM_HELP)
    witness = command(
        "witness",
        lambda a: audit.cmd_witness(a.stem, a.file, a.every_case,
                                    a.witness_file, a.try_path),
        help=mctx("run the task's witness grids and report where the solver "
                  "and the witness file disagree"),
        description=mctx("The report checks the file's shape first. With "
                         "--file and no stem, the shape check is the whole "
                         "report, and it needs no solver."),
    )
    witness.add_argument("stem", nargs="?",
                         help=mctx("a task id, or the path to a solver file "
                                   "whose name starts with the task id; a "
                                   "path run reads that task id's witness "
                                   "file too"))
    witness.add_argument("--file", metavar="PATH",
                         help=mctx("a witness file to read in place of the "
                                   "task's; the report has only the findings "
                                   "on its witnesses"))
    witness.add_argument("--witness-file", metavar="PATH",
                         dest="witness_file",
                         help=mctx("a witness file to read in place of the "
                                   "task's; the report is the one the "
                                   "task's file gets"))
    witness.add_argument("--try", metavar="PATH", dest="try_path",
                         help=mctx("a grid file read as a candidate "
                                   "witness: run the solver's cases on it "
                                   "as `record` would, and print its "
                                   "groups, the unseparated branch "
                                   "differences whose pairs it separates, "
                                   "and the subsumed ones whose pairs it "
                                   "shows defined and differing; nothing "
                                   "is written"))
    witness.add_argument("--every-case", action="store_true",
                         help=mctx("run with `impl_choice` holding every "
                                   "case of `Choice`; for each case the "
                                   "solver drops, print the first of these "
                                   "the runs show: it fails Fit, no witness "
                                   "separates it from another case, it "
                                   "fails Subsumption, or it fails none of "
                                   "them"))
    derive = command(
        "derive", partial(audit.derive_or_store, audit.cmd_derive),
        help=mctx("the built-in derivations of stored parameters that fit, "
                  "each a branch; writes each witness it builds into the "
                  "task's witness file"),
        description=mctx("Each built-in derivation of a stored parameter, "
                         "a proposer of `programs/proposers.dl`, for which "
                         "some case of the solver that takes its branch fits the "
                         "task. With each, the witness that separates the "
                         "cases that take the branch from the cases that "
                         "take the stored value there and the same branches "
                         "elsewhere; a derivation whose "
                         "`@ignore: derive — <reason>` line stands gets "
                         "none. A derivation whose branch no case takes is "
                         "listed where the concept case fits, and one is "
                         "listed where the `@ignore: derive <name>` lines "
                         "exclude every case that takes its branch, each "
                         "with no witness. The "
                         "command writes each witness it builds into the "
                         "task's witness file, as `record` writes one, with "
                         "the `@derive` line standing, and keeps a witness "
                         "the file already holds for the branch."),
    )
    store = command(
        "store", partial(audit.derive_or_store, audit.cmd_store),
        help=mctx("the program relations that hold one value on every "
                  "input; writes each witness it builds into the task's "
                  "witness file"),
        description=mctx("Each program relation between `in` and `out` whose "
                         "value over a subset of its columns is the same on "
                         "every input of the task, with the witness that "
                         "separates the cases that take its `<rel>=stored` "
                         "branch from the cases that take the derived value "
                         "there and the same branches elsewhere. The command "
                         "writes each witness it builds into the task's "
                         "witness file, as `record` writes one, with the `@store` "
                         "line standing, and keeps a witness the file "
                         "already holds for the branch. A relation with "
                         "more than 20000 rows on some input is not checked: "
                         "that is too many rows to be a stored value."),
    )
    for p in (derive, store):
        p.add_argument("stem", nargs="?",
                       help=mctx("a task id, or the path to a solver file "
                                 "whose name starts with the task id; every "
                                 "solver when omitted, and then the command "
                                 "writes nothing"))
        p.add_argument("--witness-file", metavar="PATH", dest="witness_file",
                       help=mctx("a witness file to read and write in place "
                                 "of the task's"))
    plan = command(
        "determination-plan",
        lambda a: survey.cmd_determination_plan(a.stem, a.verdicts),
        help=mctx("which Params parameters need determination relations"),
    )
    plan.add_argument("stem", help=STEM_HELP)
    plan.add_argument("--verdicts", action="store_true",
                      help=mctx("append each proposer's verdict on each "
                                "parameter"))

    size = command(
        "size", lambda a: survey.cmd_size(a.stem),
        help=mctx("literal count per solver"),
        description=mctx("Print each solver's literal count, count first."),
    )
    size.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)

    keywords = command(
        "keywords", lambda a: survey.cmd_keywords(a.stem),
        help=mctx("how many solvers carry each keyword of the Keywords doc"),
        description=mctx("Count, for each keyword of the Keywords doc, the "
                         "solvers whose `// @keywords:` line carries it, and "
                         "list each header keyword the doc does not."),
    )
    keywords.add_argument("stem", nargs="*",
                          help=mctx("solvers to read; all of them when "
                                    "omitted"))

    since = command(
        "since", lambda a: survey.cmd_since(a.when),
        help=mctx("the solvers in scope for a delta survey since a date-time"),
        description=mctx("Print the stem of each solver that the commits "
                         "since the given date-time touch, and of each "
                         "solver whose working-tree content differs from "
                         "HEAD. A commit that touches more than half the "
                         "solvers gives no stems. When the other commits "
                         "together touch more than half, only the solvers "
                         "that those commits create are printed from "
                         "them."),
    )
    since.add_argument("when", help=mctx("a date-time git reads, e.g. "
                                         '"2026-09-08 14:30"'))

    command(
        "expand", lambda a: survey.cmd_expand(a.stem),
        help=mctx("the source after GRID and RIGID expansion, as Souffle "
                  "sees it"),
        description=mctx("Print the solver source with each GRID call and "
                         "RIGID block replaced by what it emits and nothing else "
                         "changed."),
    ).add_argument("stem", help=STEM_HELP)
    return top, sub.choices
