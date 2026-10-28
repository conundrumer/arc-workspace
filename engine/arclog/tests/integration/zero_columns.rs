//! A case program read alone drops each column that is `0` in every clause of
//! its relation in the case, through the readers that the other `ALTS` form
//! gives, at a key site as well, and keeps a column that `0` may not stand
//! for, as `docs/arclog/arclog.md#negation-and-constraints` gives.

use std::sync::Arc;

use arclog::check::{check_program, check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::instance::{Construction, ConstructionContext, Constructions, GroupInputs, GroupOutputs};
use arclog::eval::ReachedBound;
use arclog::relations::RowSet;
use arclog::hash::StableHash;
use arclog::eval::{relation_of, Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::{AltsName, Clause, ColumnName, Conjunct, DeclaredName, Form, Instance, Node, Program, ProgramRelation, RelationName};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, SolverScope};
use arclog::session::{SessionBound, TaskSession};
use arclog::solver::{Case, Solver};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example};

/// `&host` is the box that the frame of the cells makes; `$Whole` makes it
/// `0`, the whole grid. `&tint` is keyed by the host that a cell lies in, and
/// `&seen` reads its value at that key. `$Count` rederives `&seen` to read
/// `&host` itself, and `$Differs` adds a clause that compares the host with
/// the frame, `B` the first label of a constraint.
const ARCLOG: &str = "
(INPUT cells \"every cell is tinted by the host it lies in\"
  (INIT &frame BoundingBox
    (cell (P)
      (input *P)))

  (RULE &host
    (&frame.box *B))

  (RULE &cell
    (&host *B)
    (input *P *Col))

  (INIT &tint Singleton
    (key ((&cell ^B *P))
      (member ((:v Col))
        (&cell B *P)
        (input P *Col))))

  (RULE &seen
    (&tint.value (:key (:B *B)) (:v *Col)))

  (RULE &colors
    (&seen (:Col *C))))

(ALTS $frame \"where the host comes from\" $Shape
  (ALT $Whole
    (INPUT cells \"the host is the whole grid\"
      (RULE &host
        (= *B 0)))))

(ALTS $report \"how the tint is read\" $Plain
  (ALT $Count
    (INPUT cells \"the tint is read at each host\"
      (RULE &seen
        (&host *B)
        (&tint.value (:key (:B B)) (:v *Col)))))
  (ALT $Differs
    (INPUT cells \"a host that is not the frame is reported\"
      (RULE &flag
        (&host *B)
        (&frame.box (:B *B2))
        (!= B B2)))))
";

fn solver() -> Solver {
    read_solver("zero", ARCLOG, "", &|_| None).unwrap_or_else(|error| panic!("{error:?}")).value
}

fn case(solver: &Solver, alts: &[&str]) -> Case {
    let wanted: Vec<AltsName> = alts.iter().map(|alt| AltsName((*alt).into())).collect();
    let names = solver.case_names(arclog::solver::Exclusion::WithExcluded);
    let name = names.into_iter().find(|name| wanted.iter().all(|alt| name.0.contains(alt))).expect("a case of these alts");
    solver.case(&name).expect("the case builds")
}

fn clause<'a>(program: &'a Node<Program>, relation: &str) -> &'a Clause {
    clause_deriving(program, &ProgramRelation::Declared(RelationName(DeclaredName::Written(relation.into()))))
}

fn clause_deriving<'a>(program: &'a Node<Program>, derives: &ProgramRelation) -> &'a Clause {
    let found = program.value().forms.iter().find_map(|form| match form {
        Form::Clause(clause) if clause.value().derives == *derives => Some(clause.value()),
        _ => None,
    });
    found.unwrap_or_else(|| panic!("a clause that derives {derives:?}"))
}

fn instance<'a>(program: &'a Node<Program>, name: &str) -> &'a Instance {
    let found = program.value().forms.iter().find_map(|form| match form {
        Form::Instance(instance) if instance.value().name.0 == DeclaredName::Written(name.into()) => Some(instance.value()),
        _ => None,
    });
    found.unwrap_or_else(|| panic!("an instance {name}"))
}

fn spelled(columns: &[arclog::program::RelationColumn]) -> Vec<String> {
    columns
        .iter()
        .map(|column| match &column.name {
            ColumnName::Written(name) => name.to_string(),
            ColumnName::Slot(slot) => format!("slot {slot}"),
        })
        .collect()
}

fn makes_zero(clause: &Clause) -> bool {
    clause.body.value().conjuncts.iter().any(|conjunct| matches!(conjunct, Conjunct::Constraint(_)))
}

#[test]
fn a_column_that_is_zero_in_every_clause_drops_through_a_reader_of_the_other_alts_form() {
    let solver = solver();
    let case = case(&solver, &["$Whole", "$Count"]);
    let own = clause(&case.program, "&host");
    assert_eq!(spelled(&own.columns), ["B"]);
    assert!(makes_zero(own));
    let alone = case.program_alone();
    let host = clause(alone, "&host");
    assert!(host.columns.is_empty() && !makes_zero(host), "the host drops its column and the line that made it");
    assert_eq!(spelled(&clause(alone, "&cell").columns), ["P", "Col"], "a reader whose head column is then zero drops it in turn");
    assert_eq!(spelled(&clause(alone, "&seen").columns), ["Col"], "the reader of the other ALTS form drops it too");
}

/// A `Singleton` whose member holds one row.
struct OneMember;

impl Construction for OneMember {
    fn name(&self) -> &'static str {
        "Singleton"
    }

    fn evaluate(&self, group: &GroupInputs<'_>, _: &mut ConstructionContext<'_, '_>) -> Result<GroupOutputs, ReachedBound> {
        Ok(GroupOutputs { outputs: Box::new([group.inputs[0].clone(), RowSet::empty(0)]) })
    }
}

/// The rows of `&colors` in `checked`, one program of a case of `solver`.
fn colors(solver: &Solver, checked: &CheckedProgram) -> (u16, u64, StableHash) {
    let registry = Registry::get();
    let rows = [[3, 3], [3, 3]].map(|row| row.map(|digit| Color::from_digit(digit).expect("a color digit")).into_iter().collect::<Box<[Color]>>());
    let grid = Grid::from_rows(rows.into_iter().collect()).expect("a grid");
    let task = Task { train: Box::new([TrainPair { input: grid.clone(), output: grid }]), test: Box::new([]) };
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let limits = Limits::new(None, Cancellation::default());
    let constructions = Constructions::new(vec![Box::new(OneMember)], registry).expect("a table of one construction");
    let evaluation = Evaluation { program: checked, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let relation = relation_of(checked, &ProgramRelation::Declared(RelationName(DeclaredName::Written("&colors".into())))).expect("the relation");
    match evaluation.relation(&relation, Some(Example::at(0))) {
        Ok(RelationValue::Rows(rows)) => (rows.arity(), rows.len(), rows.rows_hash()),
        other => panic!("`&colors` gives {other:?}"),
    }
}

/// The checked program of `program` read alone, as the stream writer reads
/// it, or the refusals of the checker.
fn checked_alone(program: &Node<Program>) -> Result<CheckedProgram, Vec<arclog::diagnostic::Diagnostic>> {
    let resolved = Arc::new(resolve(program, None, &SolverScope::default(), Registry::get()).value);
    let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
    check_shared_program(resolved, &clauses, Registry::get(), &mut CheckCache::default())
}

#[test]
fn a_key_site_at_the_label_drops_the_key_column_and_the_outputs_stay() {
    let solver = solver();
    let case = case(&solver, &["$Whole", "$Plain"]);
    assert_eq!(spelled(&instance(&case.program, "&tint").key.as_ref().expect("a key").value().key.columns), ["B"]);
    let alone = case.program_alone();
    let tint = instance(alone, "&tint");
    let key = tint.key.as_ref().expect("the key clause stays").value();
    assert!(key.key.columns.is_empty(), "a key of one such column becomes a key of no column");
    assert!(key.inputs.is_empty() && !tint.inputs.is_empty(), "the inputs of a key of no column stand after it");
    let registry = Registry::get();
    let resolved = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let keyed = check_program(resolved, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let unkeyed = checked_alone(alone).expect("the program read alone checks");
    let (keyed, unkeyed) = (colors(&solver, &keyed), colors(&solver, &unkeyed));
    assert_eq!(keyed.1, 1);
    assert_eq!(keyed, unkeyed, "the instance of the key of no column gives the outputs of the keyed instance");
}

#[test]
fn a_label_that_reaches_the_first_label_of_a_constraint_keeps_its_column() {
    let solver = solver();
    let case = case(&solver, &["$Whole", "$Differs"]);
    let alone = case.program_alone();
    let host = clause(alone, "&host");
    assert_eq!(spelled(&host.columns), ["B"]);
    assert!(makes_zero(host), "the column keeps its `(= *B 0)`");
    assert!(!instance(alone, "&tint").key.as_ref().expect("a key").value().key.columns.is_empty());
    assert!(checked_alone(alone).is_err(), "the program read alone is refused, so the writer gives no stream");
}
