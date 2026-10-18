//! A `RULE_OR_DET` line on a port of an instance gives that port one source
//! in each case: in the derived reading the instance, and the case holds no
//! clause of the line; in the stored reading the line's `DET`, which each
//! read of the port resolves to, and which the input's node reads where the
//! port is an input.

use std::sync::Arc;

use arclog::program::path::{NodePath, PathStep};
use arclog::program::{ClauseKeyword, DeclaredName, Form, Instance, InstanceName, OutputOwner, OutputStep, PortName, Program, ProgramRelation};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ConceptReads, DependencyKind, GraphNodeIndex, ResolvedProgram, Resolution};
use arclog::solver::{Case, Exclusion, Solver};

const ARCLOG: &str = "
(INIT &canvas Frame
  (extent (A N)
    (input *P *Col)
    (box_extent P P A *N)))

(RULE_OR_DET &canvas.extent)

(RULE &extent_read
  (&canvas.extent *A *N))

(INIT &ring Singleton
  (member ((:v Col))
    (input *P *Col)))

(RULE_OR_DET &ring.value)

(RULE &value_read
  (&ring.value (:v *Col)))
";

fn solver() -> Solver {
    read_solver("ports", ARCLOG, "", &|_| None).expect("the files read").value
}

fn instance_name(form: &Form) -> Option<&DeclaredName> {
    match form {
        Form::Instance(instance) => Some(&instance.value().name.0),
        _ => None,
    }
}

/// The `INIT` form of `name` in `program`.
fn instance<'p>(program: &'p Program, name: &str) -> &'p Instance {
    let form = program.forms.iter().find(|form| instance_name(form) == Some(&written(name))).expect("the instance's form");
    let Form::Instance(instance) = form else { unreachable!() };
    instance.value()
}

/// The keyword of each clause of `program` that derives `&<instance>.<port>`.
fn port_clauses(program: &Program, instance: &str, port: &str) -> Vec<ClauseKeyword> {
    let forms = program.forms.iter();
    let clauses = forms.filter_map(|form| match form {
        Form::Clause(clause) => Some(clause.value()),
        _ => None,
    });
    clauses.filter(|clause| is_port(&clause.derives, instance, port)).map(|clause| clause.keyword).collect()
}

fn is_port(relation: &ProgramRelation, instance: &str, port: &str) -> bool {
    let ProgramRelation::Output(output) = relation else { return false };
    matches!((&output.of, &output.path[..]), (OutputOwner::Instance(name), [OutputStep::Port(at)]) if name.0 == written(instance) && &*at.0 == port)
}

fn writes(instance: &Instance, port: &str) -> bool {
    instance.inputs.iter().any(|input| &*input.value().name.0 == port)
}

/// The case of `solver` whose name takes `alt`, and takes the concept
/// case's reading of every other line.
fn case_taking(solver: &Solver, alt: &str) -> Case {
    let concept = solver.concept_case();
    let differs = |case: &Case| case.name.0.iter().zip(concept.name.0.iter()).filter(|(a, b)| a != b).count();
    let mut cases = solver.cases(Exclusion::WithExcluded).filter(|case| case.name.0.iter().any(|name| &*name.0 == alt));
    cases.find(|case| differs(case) <= 1).expect("a case of the alt")
}

#[test]
fn a_derived_reading_holds_no_clause_of_the_line_and_a_stored_reading_holds_its_det() {
    let solver = solver();
    for case in solver.cases(Exclusion::WithExcluded) {
        let program = case.program.value();
        let taken = |alt: &str| case.name.0.iter().any(|name| &*name.0 == alt);
        if taken("&canvas.extent=$Derived") {
            assert_eq!(port_clauses(program, "canvas", "extent"), vec![], "{:?}", case.name);
            assert!(writes(instance(program, "canvas"), "extent"), "{:?}", case.name);
        } else {
            assert_eq!(port_clauses(program, "canvas", "extent"), vec![ClauseKeyword::Det], "{:?}", case.name);
            assert!(!writes(instance(program, "canvas"), "extent"), "{:?}", case.name);
        }
        if taken("&ring.value=$Derived") {
            assert_eq!(port_clauses(program, "ring", "value"), vec![], "{:?}", case.name);
        } else {
            assert_eq!(port_clauses(program, "ring", "value"), vec![ClauseKeyword::Det], "{:?}", case.name);
        }
        assert!(writes(instance(program, "ring"), "member"), "{:?}", case.name);
    }
}

/// `case` resolved, with the concept case's resolution its concept `DET`
/// forms read through.
fn resolved(solver: &Solver, case: &Case) -> ResolvedProgram {
    let registry = Registry::get();
    let derived = solver.derived_relations();
    let concept = Arc::new(resolve(&solver.concept_case().program, None, &derived, registry).value);
    let reads = ConceptReads { concept: &concept, determinations: case.concept_determinations() };
    resolve(&case.program, Some(reads), &derived, registry).value
}

fn node(program: &ResolvedProgram, kind: &DependencyKind) -> GraphNodeIndex {
    let index = program.graph.nodes.iter().position(|node| node.kind == *kind).expect("a node of the kind");
    GraphNodeIndex(index as u32)
}

fn parameter(program: &ResolvedProgram, instance: &str, port: &str) -> GraphNodeIndex {
    let index = program.graph.nodes.iter().position(|node| matches!(&node.kind, DependencyKind::Parameter(relation) if is_port(relation, instance, port)));
    GraphNodeIndex(index.expect("the parameter node of the line's `DET`") as u32)
}

/// What the atom of the clause that derives `reader` resolves to.
fn read_of(case: &Case, program: &ResolvedProgram, reader: &str) -> GraphNodeIndex {
    let forms = &case.program.value().forms;
    let derives = |form: &Form| matches!(form, Form::Clause(clause) if matches!(&clause.value().derives, ProgramRelation::Declared(name) if name.0 == written(reader)));
    let form = forms.iter().position(derives).expect("the reading clause") as u32;
    let atom = NodePath(Box::new([PathStep(form), PathStep(0), PathStep(0)]));
    match program.resolution(&atom) {
        Some(Resolution::Node(node)) => *node,
        other => panic!("the read resolves to a node, not {other:?}"),
    }
}

#[test]
fn a_stored_line_on_an_input_is_the_input_s_one_source() {
    let solver = solver();
    let case = case_taking(&solver, "&canvas.extent=$Stored");
    let program = resolved(&solver, &case);
    let det = parameter(&program, "canvas", "extent");
    assert_eq!(read_of(&case, &program, "extent_read"), det);
    let input = node(&program, &DependencyKind::InstanceInput { instance: name("canvas"), input: PortName("extent".into()) });
    assert_eq!(&program.graph.reads[input.0 as usize][..], &[det]);
}

#[test]
fn a_stored_line_on_an_output_is_the_output_s_one_source() {
    let solver = solver();
    let case = case_taking(&solver, "&ring.value=$Stored");
    let program = resolved(&solver, &case);
    let det = parameter(&program, "ring", "value");
    assert_eq!(read_of(&case, &program, "value_read"), det);
    let output = node(&program, &DependencyKind::InstanceOutput { instance: name("ring"), output: PortName("value".into()) });
    assert!(program.graph.reads.iter().all(|reads| !reads.contains(&output)), "a node reads the instance's output");
}

fn name(instance: &str) -> InstanceName {
    InstanceName(written(instance))
}

/// The declared name `&<name>`, as a file writes it.
fn written(name: &str) -> DeclaredName {
    DeclaredName::Written(format!("&{name}").into())
}
