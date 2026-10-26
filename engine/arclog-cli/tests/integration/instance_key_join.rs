//! A keyed input's read of an output of another `INIT` form keyed by the
//! same labels joins on the key in scope by a key site that it writes
//! (`docs/arclog/arclog.md#instance`).

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::{Cancellation, Caps, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Example};

/// The input grid of the one train pair, whose sides give several keys.
const GRID: &[&[u8]] = &[&[1, 2, 0, 3], &[2, 2, 1, 0], &[0, 1, 1, 2], &[3, 0, 2, 1]];

/// A `Frame` and a `Cardinality` keyed by a side `N`, whose members are the
/// cells of the frame, read at the key by a key site.
const SOLVER: &str = "(RULE &trial\n\
  (input *P)\n\
  (axis_elem *A)\n\
  (OR ((sub_extent P A (:K *N)))\n\
      ((frame_extent P A N))))\n\
(INIT &frame Frame\n\
  (key ((&trial ^N))\n\
    (extent (A N)\n\
      (axis_elem *A))))\n\
(INIT &card Cardinality\n\
  (key ((&trial ^N))\n\
    (member ((:m P))\n\
      (&frame.cell (:key N) *P))))\n";

fn checked(text: &str) -> CheckedProgram {
    let solver = read_solver("join", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

/// The count of rows of the last rule of `SOLVER` followed by `rule`, whose
/// body holds `conjuncts` conjuncts, on the train pair.
fn rule_rows(rule: &str, conjuncts: u32) -> u64 {
    let program = checked(&format!("{SOLVER}{rule}"));
    let rows = GRID.iter().map(|row| row.iter().map(|&digit| Color::from_digit(digit).expect("a color digit")).collect()).collect();
    let input = Grid::from_rows(rows).expect("a grid");
    let task = Task { train: Box::new([TrainPair { input: input.clone(), output: input }]), test: Box::new([]) };
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let registry = Registry::get();
    let parameters = ParameterValues::default();
    let limits = Limits::new(None, Cancellation::default());
    let evaluation = Evaluation { program: &program, concept: None, task: &task, parameters: &parameters, session: &session, registry, constructions: arclog_constructions::shared().expect("the table of constructions"), limits: &limits };
    let path = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let value = evaluation.body(&path, &(0..conjuncts).collect::<Vec<_>>(), Some(Example::at(0))).unwrap_or_else(|fault| panic!("{fault:?}"));
    match &value.0 {
        RelationValue::Rows(_) => value.count().expect("a count"),
        other => panic!("{other:?}"),
    }
}

#[test]
fn a_read_by_a_key_site_of_an_instance_keyed_by_the_same_labels_joins_on_the_key() {
    let keys = rule_rows("(RULE &keys (&card.size (:key *N) (:N *S)))\n", 1);
    assert!(keys > 1, "the grid gives several keys");
    let equal = rule_rows("(RULE &equal (&card.size (:key (:N *N1)) (:N *S)) (&card.size (:key (:N *N2)) (:N S)))\n", 2);
    assert_eq!(equal, keys, "`&card.size` is the cells of the frame at each key, N x N, so no two keys give one size");
}
