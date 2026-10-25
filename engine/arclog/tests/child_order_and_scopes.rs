//! The walks over a program value agree on the children of each node and
//! on the label scopes: an edit that puts a node back in place of itself
//! gives the program it edits, each label scope that the canonical order
//! of a form gives is one that `opens_scope` gives, and the labels the
//! reader puts in each scope are the labels the canonical order gives that
//! scope. The child of a node at an index is the child that its children
//! give at that index.

use std::collections::BTreeSet;

use arclog::program::canonical::{opens_scope, CanonicalOrder, SearchBudget};
use arclog::program::edit::Edit;
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{constraint_second, Conjunct, LabelId, LabelUse, Node, Program};
use arclog::read::read_solver;
use arclog::solver::Exclusion;

/// A solver whose file holds each node kind and each kind of label scope:
/// a claim, an `ALTS` form with nested `ALT` blocks, every conjunct kind,
/// field sites, an `INIT` form with a key clause, a `CHOOSE` form, a
/// `RIGID_DET` form, and a `DEMONSTRATED` form whose `DEMO_RULE` form holds
/// a claim, a nested `DEMONSTRATED` form and a clause that an `ALT`
/// rederives in its case programs.
const ARCLOG: &str = "
(INPUT cells \"the cells\"
  (RULE &cells (input *P *Col)))
(RULE &clause
  (&cells *P *Col)
  (NOT (&cells P 0))
  (NOT (OR ((&cells P Col)) ((&cells (:P (:A *Q)) Col))))
  (= *R P)
  (IF ((&cells P Col)) ((&cells P Col)) ((&cells P Col)))
  (ALL ((&cells (:P *S) (:Col Col))) ((&cells (:P S) (:Col Col)))))
(INIT &obj Connectivity
  (key ((&cells ^E *Q))
    (node (P)
      (&cells E *P))))
(CHOOSE &pick
  (for ((&cells *P))
    (from (&cells P (:Col ^X))))
  (never (&cells P X)))
(RIGID_DET &piece
  (key ((&cells (:P (:A ^X))))
    (&cells (:P (:A X)))))
(DEMONSTRATED &catalog
  (value ((:o P) (:v Col))
    (&cells *P *Col))
  (demonstration ((:o P) (:o2 P2))
    (&cells *P *Col)
    (&cells *P2 Col))
  (DEMO_RULE $Same
    (RULE &local (&cells *P *Col))
    (RULE &prediction (&local *P *Col))
    (INPUT inner \"the inner cells\"
      (RULE &inner (&cells *P *Col)))
    (DEMONSTRATED &nested
      (value ((:o P))
        (&cells *P *Col))
      (DEMO_RULE $Any
        (RULE &prediction (&cells *P *Col))))))
(ALTS $which \"which cells &local holds\" $All
  (ALT $All
    (RULE &extra (&cells *P *Col)))
  (ALT $Some
    (RULE &local (&cells *P *Col) (&cells P 0))
    (ALT $Fewer
      (RULE &fewer (&cells *P *Col)))))
";

/// The program of the file, and the program of each case.
fn programs() -> Vec<Node<Program>> {
    let solver = read_solver("scopes", ARCLOG, "", &|_| None).expect("the file reads").value;
    let cases = solver.cases(Exclusion::WithExcluded).map(|case| case.program);
    std::iter::once(solver.program.clone()).chain(cases).collect()
}

/// The path and the node of each node below `node`, at `at`, `node` too.
fn each_node<'a>(node: NodeRef<'a>, at: &NodePath, visit: &mut dyn FnMut(&NodePath, NodeRef<'a>)) {
    visit(at, node);
    for (child, index) in node.children().into_iter().zip(0u32..) {
        each_node(child, &at.child(index), visit);
    }
}

fn split_last(path: &NodePath) -> (NodePath, usize) {
    let (last, parent) = path.0.split_last().expect("a path below the root");
    (NodePath(parent.into()), last.0 as usize)
}

#[test]
fn the_child_at_an_index_is_the_child_the_children_give() {
    for program in programs() {
        each_node(NodeRef::Program(program.value()), &NodePath::default(), &mut |_, node| {
            let children = node.children();
            for (index, child) in children.iter().enumerate() {
                let found = node.child_at(index).expect("a child");
                assert!(std::mem::discriminant(&found) == std::mem::discriminant(child) && format!("{found:?}") == format!("{child:?}"));
            }
            assert!(node.child_at(children.len()).is_none());
        });
    }
}

#[test]
fn an_edit_that_puts_a_node_back_gives_the_program_it_edits() {
    for program in programs() {
        let root = NodeRef::Program(program.value());
        let mut edits = Vec::new();
        each_node(root, &NodePath::default(), &mut |at, node| {
            let parent = at.0.split_last().map(|_| node_at(root, &split_last(at).0).expect("the parent"));
            match (parent, node) {
                (Some(NodeRef::Body(_)), NodeRef::Conjunct(conjunct)) => edits.push(Edit::ReplaceConjunct { at: at.clone(), conjunct: conjunct.clone() }),
                (Some(NodeRef::RigidDet(rigid)), NodeRef::Atom(_)) => {
                    let part = rigid.parts.iter().find(|part| std::ptr::eq(part.value(), node.atom().expect("a part")));
                    edits.push(Edit::ReplacePart { at: at.clone(), part: part.expect("a part of the form").clone() });
                }
                (_, NodeRef::Site(site)) => edits.push(Edit::ReplaceSite { at: at.clone(), site: site.clone() }),
                _ => {}
            }
        });
        assert!(edits.len() > 40, "{}", edits.len());
        for edit in edits {
            let edited = program.apply(&edit).unwrap_or_else(|error| panic!("{edit:?}: {error:?}"));
            assert!(edited == program, "{edit:?}");
        }
    }
}

/// The label ids of each label use of `node`, at `at`, with its path: a
/// site's at its label, a constraint's at the constraint, and a `DEMO_RULE`
/// form's fields at the rule.
fn each_label(node: NodeRef<'_>, at: &NodePath, visit: &mut dyn FnMut(&NodePath, LabelId)) {
    each_node(node, at, &mut |at, node| match node {
        NodeRef::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label)) => visit(at, *label),
        NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
            for operand in [Some(constraint.first), constraint_second(constraint)].into_iter().flatten() {
                visit(at, operand.label);
            }
        }
        NodeRef::DemoRule(rule) => rule.fields.iter().for_each(|field| visit(at, field.label)),
        _ => {}
    });
}

#[test]
fn each_scope_of_the_canonical_order_is_a_scope_the_reader_and_opens_scope_give() {
    let mut scopes = 0;
    for program in programs() {
        let root = NodeRef::Program(program.value());
        for (form, index) in program.value().forms.iter().zip(0u32..) {
            let order = CanonicalOrder::of(form, &mut SearchBudget::new());
            let given: Vec<(NodePath, BTreeSet<u32>)> =
                order.label_scopes().into_iter().map(|(scope, labels)| (scope, labels.iter().map(|(label, _)| label.0).collect())).collect();
            for (scope, _) in &given {
                let at = NodePath::top(index).join(scope);
                let (parent, step) = split_last(&at);
                let parent = node_at(root, &parent).expect("the parent of the scope");
                let child = node_at(root, &at).expect("the node of the scope");
                assert!(opens_scope(parent, step, child), "{at:?}");
                scopes += 1;
            }
            let mut read: Vec<BTreeSet<u32>> = vec![BTreeSet::new(); given.len()];
            let mut outside = Vec::new();
            each_label(NodeRef::from(form), &NodePath::default(), &mut |at, label| {
                let within = given.iter().enumerate().filter(|(_, (scope, _))| at.0.starts_with(&scope.0));
                match within.max_by_key(|(_, (scope, _))| scope.0.len()) {
                    Some((scope, _)) => {
                        read[scope].insert(label.0);
                    }
                    None => outside.push(at.clone()),
                }
            });
            assert!(outside.is_empty(), "form {index}: labels outside each scope at {outside:?}");
            let given: Vec<BTreeSet<u32>> = given.into_iter().map(|(_, labels)| labels).collect();
            assert_eq!(read, given, "form {index}");
        }
    }
    assert!(scopes > 10, "{scopes}");
}

