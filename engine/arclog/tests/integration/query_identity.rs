//! The identity of a query ([`arclog::resolver::ResolvedProgram::query_identity`]) is free of the
//! names a program declares and of the order of its conjuncts and columns: its content, the
//! canonical position of each label of its form and the canonical path of each atom are equal in
//! two programs that differ by those.

use std::sync::Arc;

use arclog::layout::SourceFile;
use arclog::program::path::{NodePath, NodeRef};
use arclog::program::{Form, Node, Program};
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::{resolve, QueryIdentity};

fn read(text: &str) -> Node<Program> {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    read.value.0
}

/// The identity of the query at `position` of `text`, and the program.
fn identity(text: &str, position: usize) -> (QueryIdentity, Node<Program>) {
    let program = read(text);
    let resolved = resolve(&program, None, &Default::default(), Registry::get());
    assert!(resolved.diagnostics.is_empty(), "{:?}", resolved.diagnostics);
    (resolved.value.query_identity(position, Registry::get()).expect("the query has an identity"), program)
}

/// The paths of the conjuncts below `node` that are an atom or a negated atom, relative to the form,
/// in source order.
fn atom_paths(node: NodeRef<'_>, at: &NodePath, out: &mut Vec<NodePath>) {
    if matches!(node, NodeRef::Conjunct(conjunct) if conjunct.atom().is_some()) {
        out.push(at.clone());
    }
    for (index, child) in node.children().into_iter().enumerate() {
        atom_paths(child, &at.child(index as u32), out);
    }
}

/// The canonical positions of the labels of the columns of the clause at `position`, in the
/// order the clause writes the columns.
fn column_positions(identity: &QueryIdentity, program: &Node<Program>, position: usize) -> Vec<(String, u32)> {
    let Form::Clause(clause) = &program.value().forms[position] else { panic!("a clause") };
    clause.value().columns.iter().map(|column| (format!("{:?}", column.name), identity.order.label_position(&NodePath::default(), column.label).expect("a column's label has a position"))).collect()
}

const FIRST: &str = "(RULE &cell (input *P *Col))\n(RULE &twin (&cell *P *Col) (&cell (:P *Q) (:Col Col)) (NOT (input (:P Q))))\n";
/// `FIRST` with each relation and label renamed, the conjuncts of `&twin` in another order.
const SECOND: &str = "(RULE &px (input (:P *X) (:Col *C)))\n(RULE &py (NOT (input (:P Y))) (&px (:X *Y) (:C C)) (&px *X *C))\n";

#[test]
fn a_query_has_one_content_and_one_canonical_order_under_a_rename_and_a_reorder() {
    let (first, first_program) = identity(FIRST, 1);
    let (second, second_program) = identity(SECOND, 1);
    assert_eq!(first.content, second.content);
    // P is X, Col is C and Q is Y: the label of a column has one canonical position, whatever its name.
    let (first_columns, second_columns) = (column_positions(&first, &first_program, 1), column_positions(&second, &second_program, 1));
    let named = |columns: &[(String, u32)], name: &str| columns.iter().find(|(found, _)| found.contains(name)).expect("the column").1;
    assert_eq!(first_columns.len(), 3);
    assert_eq!(named(&first_columns, "\"P\""), named(&second_columns, "\"X\""));
    assert_eq!(named(&first_columns, "\"Col\""), named(&second_columns, "\"C\""));
    assert_eq!(named(&first_columns, "\"Q\""), named(&second_columns, "\"Y\""));
    let (mut first_atoms, mut second_atoms) = (Vec::new(), Vec::new());
    atom_paths(NodeRef::from(&first_program.value().forms[1]), &NodePath::default(), &mut first_atoms);
    atom_paths(NodeRef::from(&second_program.value().forms[1]), &NodePath::default(), &mut second_atoms);
    assert_eq!(first_atoms.len(), 3);
    assert_eq!(second_atoms.len(), 3);
    let canonical = |identity: &QueryIdentity, path: &NodePath| identity.order.try_canonical_path(path).expect("an atom has a canonical path");
    // The atoms of FIRST are the two reads of `&cell` and the read of `input` in the `NOT`; SECOND writes them in the reverse order.
    let paired = [(0, 2), (1, 1), (2, 0)];
    for (first_at, second_at) in paired {
        assert_eq!(canonical(&first, &first_atoms[first_at]), canonical(&second, &second_atoms[second_at]), "atoms {first_at} and {second_at}");
    }
    assert_ne!(canonical(&first, &first_atoms[0]), canonical(&first, &first_atoms[1]));
}

#[test]
fn a_query_that_reads_another_relation_has_another_content() {
    let (first, _) = identity(FIRST, 1);
    let other = "(RULE &cell (input *P *Col) (= *Q 0))\n(RULE &twin (&cell *P *Col) (&cell (:P *Q) (:Col Col)) (NOT (input (:P Q))))\n";
    let (second, _) = identity(other, 1);
    assert_ne!(first.content, second.content);
}

#[test]
fn a_form_alone_in_a_program_that_declares_nothing_else_has_an_identity() {
    let program = Node::new(Program { forms: Arc::from([read(FIRST).value().forms[0].clone()]) });
    let resolved = resolve(&program, None, &Default::default(), Registry::get());
    assert!(resolved.value.query_identity(0, Registry::get()).is_some());
}

/// A `DET` keeps the columns that a read names in the order its clause writes them, so the order
/// of the clause's labels is in the content of a read of it, but not in the identity of the read.
#[test]
fn a_determination_read_in_another_column_order_gives_its_reader_one_identity() {
    let reader = "(DET &mismatch (&src *E *Diag) (d4_elem (:D *D4)) (NOT (diag_dir_elem (:D Diag))))\n";
    let first = format!("(DET &src (ex_input *E (:P *P)) (diag_dir_elem (:D *Diag)))\n{reader}");
    let second = format!("(DET &src (diag_dir_elem (:D *Diag)) (ex_input *E (:P *P)))\n{reader}");
    let (first_identity, _) = identity(&first, 1);
    let (second_identity, _) = identity(&second, 1);
    assert_eq!(first_identity.content, second_identity.content);
    let content = |text: &str| {
        let program = read(text);
        resolve(&program, None, &Default::default(), Registry::get()).value.query_content(1, Registry::get()).expect("a content")
    };
    assert_ne!(content(&first), content(&second));
}

/// The order of the head sites of an instance's input, and of the field sites of a key, are
/// outside the identity of a query, though they are in its content.
#[test]
fn the_order_of_head_sites_and_of_field_sites_is_outside_the_identity() {
    let pre = "(RULE &ink (input *P *Col))\n(INIT &count Cardinality (key ((&ink (:P ^Kp) (:Col ^Kc))) (member ((:m Kp)) (&ink (:P Kp) (:Col Kc)))))\n";
    let order = |score: &str| format!("{pre}(INIT &body Order (member ((:t Col)) (&count.size (:key *Col *Kp))) (score {score} (&count.size (:key *Col *Kp) *N)))\n");
    let (first, second) = (order("((:t Col) (:S N))"), order("((:S N) (:t Col))"));
    assert_eq!(identity(&first, 2).0.content, identity(&second, 2).0.content);
    let reader = |key: &str| format!("{pre}(RULE &read (&count.size (:key {key}) *N))\n");
    let (first, second) = (reader("*Kp *Kc"), reader("*Kc *Kp"));
    assert_eq!(identity(&first, 2).0.content, identity(&second, 2).0.content);
}
