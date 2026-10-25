//! A filter, an `OR`, `NOT`, `IF` or `ALL`, in the body of a `RIGID_DET`
//! form's `key` or `instance` clause, or of the key clause of an `INIT` or a
//! `DEMONSTRATED` form, compiles, and reads from the body around it the
//! labels it shares with the rest of its form.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::ir::{compile_instance_body, IrNode};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Form, KeyBody};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::resolve;

const RELATIONS: &str = "(RULE &cells (input *P *Col))\n(RULE &tips (input *P *Col))\n";

/// Forms whose one key clause or `instance` clause holds a filter, each
/// with the labels that filter shares with the rest of its form.
const FORMS: [(&str, &[&str]); 8] = [
    ("(RIGID_DET &piece\n\
       (instance ((OR ((&cells ^P *Col)) ((&tips P Col))))\n\
         (&cells P *Col)))\n", &["P", "Col"]),
    ("(RIGID_DET &piece\n\
       (key ((&cells *P ^Col) (NOT (&tips P Col)))\n\
         (&cells *P Col)))\n", &["P", "Col"]),
    ("(INIT &obj Connectivity\n\
       (key ((OR ((&cells *P ^Col)) ((&tips P Col))))\n\
         (node (P)\n\
           (&cells *P Col))))\n", &["P", "Col"]),
    ("(INIT &obj Connectivity\n\
       (key ((&cells *P ^Col) (NOT (&tips P Col)))\n\
         (node (P)\n\
           (&cells *P Col))))\n", &["P", "Col"]),
    ("(INIT &obj Connectivity\n\
       (key ((&cells *P ^Col) (IF ((&tips P Col)) ((&cells P Col)) ((&cells P Col))))\n\
         (node (P)\n\
           (&cells *P Col))))\n", &["P", "Col"]),
    ("(INIT &obj Connectivity\n\
       (key ((&cells *P ^Col) (ALL ((&tips (:P *Q) (:Col Col))) ((&cells (:P Q) (:Col Col)))))\n\
         (node (P)\n\
           (&cells *P Col))))\n", &["Col"]),
    ("(DEMONSTRATED &catalog\n\
       (key ((OR ((&cells *P ^Col)) ((&tips P Col))))\n\
         (value (P)\n\
           (&cells *P Col))))\n", &["P", "Col"]),
    ("(DEMONSTRATED &catalog\n\
       (key ((&cells *P ^Col) (NOT (&tips P Col)))\n\
         (value (P)\n\
           (&cells *P Col))))\n", &["P", "Col"]),
];

/// The checked concept case of the solver `text`.
fn checked(text: &str) -> CheckedProgram {
    let solver = read_solver("filter", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

#[test]
fn a_filter_in_a_key_body_compiles() {
    for (form, shared) in FORMS {
        let program = checked(&format!("{RELATIONS}{form}"));
        let index = program.program.program.value().forms.len() as u32 - 1;
        let path = NodePath(Box::new([PathStep(index)]));
        let (key, body): (&KeyBody, NodePath) = match program.program.program.value().forms.last().expect("the form") {
            Form::RigidDet(rigid) => {
                let rigid = rigid.value();
                (rigid.key.as_ref().or(rigid.instance.as_ref()).expect("a clause"), path.child(0))
            }
            Form::Instance(instance) => (&instance.value().key.as_ref().expect("a key clause").value().key, path.child(0).child(0)),
            Form::Demonstrated(demonstrated) => (&demonstrated.value().key.as_ref().expect("a key clause").value().key, path.child(0).child(0)),
            _ => panic!("no form with a key body: {form}"),
        };
        let columns: Vec<_> = key.columns.iter().map(|column| column.label).collect();
        let clause = compile_instance_body(&program, &path, &[(key.body.value(), body)], &columns);
        let clause = clause.unwrap_or_else(|fault| panic!("{form}: {fault:?}"));
        let read: Vec<usize> = clause
            .nodes
            .iter()
            .filter_map(|node| match node {
                IrNode::Not(filter) | IrNode::Counterexample(filter) => Some(filter.outer.len()),
                IrNode::Or(union) => Some(union.exported.len()),
                _ => None,
            })
            .collect();
        assert!(!read.is_empty() && read.iter().all(|&count| count == shared.len()), "{form}: each node of the filter reads the labels {shared:?} from the body around it, not {read:?}");
    }
}
