"""The lint hint on a determination relation whose clauses keep a guessed
value by a test that reads the inputs and the outputs together."""

from engine import RelationName
from engine.program import Atom, Variable, Wildcard, body_atoms, own
from engine.quotes import quotes
from checker.finding import Finding, LintNamed, LintSentence
from checker.lint.view import lint, literal_vars, view
from checker.runs import Runs
from solver.aggregate import Solver
from solver.category import Category
from solver.determine import run_program
from solver.graph import Graph, InstancePath
from solver.vocabulary import DETERMINE_SCOPE, EX_IN, EX_OUT


def _scope_read(atom: Atom) -> bool:
    """`ex_out(E, _, _)`: a read of the examples that have outputs, with
    only the example bound, which reads no fact of the outputs."""
    return atom.relation == EX_OUT and all(
        isinstance(a, Wildcard) for a in atom.args[1:])


def _sides(graph: Graph) -> tuple[frozenset[RelationName],
                                  frozenset[RelationName]]:
    """The relations derived from `ex_in`, and those derived from
    `ex_out` by a read other than a scope read (`_scope_read`)."""
    return (graph.depending(EX_IN, lambda _atom: True),
            graph.depending(EX_OUT, lambda atom: not _scope_read(atom)))


def _guess_test(graph: Graph, at: InstancePath, head: Atom,
                body: list[tuple[Atom, bool]],
                inputs: frozenset[RelationName],
                outputs: frozenset[RelationName]) -> Atom | None:
    """The first negated atom of a body that reads both sides and filters
    a guess: a variable of it and of the head that no positive atom read
    from both sides binds, and that no conversion fixes, a conversion
    being an atom read from neither side that holds it with a variable a
    positive atom read from a side binds."""
    both = inputs & outputs
    sided = inputs | outputs
    kept = literal_vars(head)
    placed = [(a, neg, graph.place(at, a.relation)) for a, neg in body]
    evidence = {v for a, neg, p in placed
                if not neg and p is not None and p in sided
                for v in literal_vars(a)}
    converters = [literal_vars(a) for a, neg, p in placed
                  if not neg and p is not None and p not in sided]

    def converted(var: str) -> bool:
        return any(var in vs and (vs - {var}) & evidence
                   for vs in converters)

    def bound_by_both(var: str) -> bool:
        return any(not neg and p is not None and p in both
                   and var in literal_vars(a) for a, neg, p in placed)

    for a, neg, p in placed:
        if neg and p is not None and p in both and any(
                isinstance(t, Variable) and not converted(t.name)
                and not bound_by_both(t.name)
                and t.name in kept for t in a.args):
            return a
    return None


@quotes("principles.md", "Models and tasks",
        "A determination's clauses read the value from the whole evidence, or keep "
        "each value at which a fact of the inputs alone, or of the outputs "
        "alone, holds.")
def check_determine_prediction(solver: Solver, runs: Runs) -> list[Finding]:
    """A determination relation of a determined parameter whose
    derivation holds a clause of the solver's own text that keeps a guess
    by a negated test (`_guess_test`) read from both `ex_in` and `ex_out`:
    the hint names the relation and the test. The derivation is followed
    through the relations read from both sides, comp instances among them,
    and not into another determination relation, which is judged on its
    own."""
    run = run_program(solver)
    if run.determine is None:
        return []
    v = view(solver, runs)
    graph = Graph(run.program, solver.engine)
    inputs, outputs = _sides(graph)
    both = inputs & outputs
    determined = {p.name for p in solver.params.parameters if p.determined}
    places = {n: p for n in determined
              if (p := graph.place(run.determine.path, RelationName((), n)))
              is not None}

    def others(name: str) -> set[RelationName]:
        """The other determination relations, each judged on its own."""
        return {p for n, p in places.items() if n != name}

    out: list[Finding] = []
    for d in v.program.relations:
        if d.scope != DETERMINE_SCOPE or not own(d.span) \
                or d.name not in determined:
            continue
        root = places.get(d.name)
        if root is None:
            continue
        seen = {root} | others(d.name)
        work = [root]
        test: Atom | None = None
        while work and test is None:
            for u, at in graph.feeding(work.pop()):
                body = list(body_atoms(u.body or ()))
                test = _guess_test(graph, at, u.head, body, inputs, outputs) \
                    if own(u.span) else None
                if test is not None:
                    break
                for a, _neg in body:
                    p = graph.place(at, a.relation)
                    if p is not None and p in both and p not in seen:
                        seen.add(p)
                        work.append(p)
        if test is not None:
            out.append(lint(d.span.first, LintNamed(
                Category.DETERMINE_PREDICTION,
                LintSentence.DETERMINE_PREDICTION,
                (d.name, test.relation.text), on_relation=True)))
    return out
