//! An edit of a program value gives the program the reader gives for the
//! edited text, and leaves the old value as it was. An edit whose path names
//! no node of its kind, or whose result breaks the naming conditions of
//! `Node::apply`, is refused.

use std::sync::Arc;

use arclog::layout::SourceFile;
use arclog::program::edit::{Edit, EditError};
use arclog::program::path::{NodePath, NodeRef, PathStep, node_at};
use arclog::program::{Atom, ColumnName, Conjunct, Form, LabelId, LabelUse, Node, Program, Site, SiteArg, SiteValue};
use arclog::read::read_arclog;

fn read(text: &str) -> Node<Program> {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads as s-expressions");
    assert!(read.diagnostics.is_empty(), "{text}: {:?}", read.diagnostics);
    read.value.0
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|&step| PathStep(step)).collect())
}

fn node<'a>(program: &'a Node<Program>, steps: &[u32]) -> NodeRef<'a> {
    node_at(NodeRef::Program(program.value()), &path(steps)).expect("a node at the path")
}

fn conjunct(program: &Node<Program>, steps: &[u32]) -> Conjunct {
    let NodeRef::Conjunct(conjunct) = node(program, steps) else { panic!("a conjunct at {steps:?}") };
    conjunct.clone()
}

fn site(program: &Node<Program>, steps: &[u32]) -> Site {
    let NodeRef::Site(site) = node(program, steps) else { panic!("a site at {steps:?}") };
    site.clone()
}

/// The part at `index` of the `RIGID_DET` form at `form`.
fn part(program: &Node<Program>, form: &[u32], index: usize) -> Node<Atom> {
    let NodeRef::RigidDet(rigid) = node(program, form) else { panic!("a `RIGID_DET` form at {form:?}") };
    rigid.parts[index].clone()
}

fn form(program: &Node<Program>, index: usize) -> Form {
    program.value().forms[index].clone()
}

const RULE: &str = "(RULE &a (input *P *C))\n";

type MakeEdit = Box<dyn Fn(&Node<Program>) -> Edit>;

#[test]
fn each_edit_gives_the_program_of_the_edited_text() {
    let cases: Vec<(String, String, MakeEdit)> = vec![
        (
            RULE.into(),
            "(RULE &a (input *P *C) (input P C))".into(),
            Box::new(|after| Edit::AddConjunct { body: path(&[0, 0]), index: 1, conjunct: conjunct(after, &[0, 0, 1]) }),
        ),
        ("(RULE &a (input *P *C) (input P *D))".into(), RULE.into(), Box::new(|_| Edit::RemoveConjunct { at: path(&[0, 0, 1]) })),
        (
            "(RULE &a (input *P *C) (input P C))".into(),
            "(RULE &a (input *P *C) (NOT (input P C)))".into(),
            Box::new(|after| Edit::ReplaceConjunct { at: path(&[0, 0, 1]), conjunct: conjunct(after, &[0, 0, 1]) }),
        ),
        (
            "(RULE &a (input *P *C) (input P))".into(),
            "(RULE &a (input *P *C) (input P C))".into(),
            Box::new(|after| Edit::AddSite { node: path(&[0, 0, 1]), index: 1, site: site(after, &[0, 0, 1, 1]) }),
        ),
        ("(RULE &a (input *P *C) (input P C))".into(), "(RULE &a (input *P *C) (input P))".into(), Box::new(|_| Edit::RemoveSite { at: path(&[0, 0, 1, 1]) })),
        (
            "(RULE &a (input *P *C) (input P (:key (:C (:D C)))))".into(),
            "(RULE &a (input *P *C) (input P))".into(),
            Box::new(|_| Edit::RemoveSite { at: path(&[0, 0, 1, 1, 0, 0]) }),
        ),
        (
            "(RULE &a (input *P *C) (input P C))".into(),
            "(RULE &a (input *P *C) (input P (:Col C)))".into(),
            Box::new(|after| Edit::ReplaceSite { at: path(&[0, 0, 1, 1]), site: site(after, &[0, 0, 1, 1]) }),
        ),
        (
            format!("{RULE}(RIGID_DET &m (&a *P *C))"),
            format!("{RULE}(RIGID_DET &m (&a *P *C) (&a *Q *C))"),
            Box::new(|after| Edit::AddPart { form: path(&[1]), index: 1, part: part(after, &[1], 1) }),
        ),
        (format!("{RULE}(RIGID_DET &m (&a *P *C) (&a *Q *C))"), format!("{RULE}(RIGID_DET &m (&a *P *C))"), Box::new(|_| Edit::RemovePart { at: path(&[1, 1]) })),
        (
            format!("{RULE}(RIGID_DET &m (&a *P *C))"),
            format!("{RULE}(RIGID_DET &m (&a *Q *D))"),
            Box::new(|after| Edit::ReplacePart { at: path(&[1, 0]), part: part(after, &[1], 0) }),
        ),
        (RULE.into(), format!("{RULE}(RULE &b (&a *P *C))"), Box::new(|after| Edit::AddForm { index: 1, form: form(after, 1) })),
    ];
    for (before_text, after_text, edit) in cases {
        let before = read(&before_text);
        let after = read(&after_text);
        let edit = edit(&after);
        let edited = before.apply(&edit).unwrap_or_else(|error| panic!("{before_text}: {edit:?}: {error:?}"));
        assert!(edited == after, "{before_text}: {edit:?}");
        assert!(before == read(&before_text), "{before_text}: {edit:?} left the old value");
    }
}

#[test]
fn a_path_that_names_no_node_of_the_edit_kind_is_refused() {
    let program = read("(RULE &a (input *P *C) (input P C))");
    let a_site = site(&program, &[0, 0, 1, 1]);
    let edits = [
        Edit::RemoveConjunct { at: path(&[0, 0, 5]) },
        Edit::RemoveConjunct { at: path(&[0, 0, 1, 0]) },
        Edit::AddSite { node: path(&[0, 0, 1, 1, 0]), index: 0, site: a_site.clone() },
        Edit::AddSite { node: path(&[0, 0]), index: 0, site: a_site },
        Edit::RemovePart { at: path(&[0, 0]) },
        Edit::AddForm { index: 3, form: form(&program, 0) },
    ];
    for edit in edits {
        assert!(matches!(program.apply(&edit), Err(EditError::Path { .. })), "{edit:?}");
    }
}

#[test]
fn a_bare_label_of_the_wrong_variant_or_name_is_refused() {
    let program = read("(RULE &a (input *P *C) (input P (:key C)))");
    let NodeRef::Site(key) = node(&program, &[0, 0, 1, 1]) else { panic!("the `:key` site") };
    let SiteArg::NamedLabel { label, .. } = key.value.args[0] else { panic!("a named label at `:key`") };
    let at = |column: &str, arg: SiteArg| Site { column: ColumnName::Written(column.into()), value: SiteValue { args: Arc::new([arg]) } };
    let named = |name: &str, label| SiteArg::NamedLabel { name: ColumnName::Written(name.into()), label };
    let sites = [at("key", SiteArg::Label(label)), at("key", named("Other", label)), at("Col", named("C", LabelUse::Join(LabelId(1))))];
    for site in sites {
        let edit = Edit::AddSite { node: path(&[0, 0, 1]), index: 2, site };
        assert!(matches!(program.apply(&edit), Err(EditError::BareLabel { .. })), "{edit:?}");
    }
}

#[test]
fn an_edit_shares_each_form_it_does_not_change() {
    let before = read(&format!("{RULE}(RULE &b (&a *P *C))"));
    let after = read(&format!("{RULE}(RULE &b (&a *P *C) (&a P C))"));
    let edit = Edit::AddConjunct { body: path(&[1, 0]), index: 1, conjunct: conjunct(&after, &[1, 0, 1]) };
    let edited = before.apply(&edit).expect("the edit applies");
    let (Form::Clause(kept), Form::Clause(old)) = (form(&edited, 0), form(&before, 0)) else { panic!("two clauses") };
    assert!(std::ptr::eq(kept.value(), old.value()));
}

#[test]
fn an_atom_with_a_site_is_the_atom_of_the_text_with_that_site() {
    let before = read("(RULE &a (input *P *C) (input P))");
    let after = read("(RULE &a (input *P *C) (input P C))");
    let (Conjunct::Atom(atom), Conjunct::Atom(expected)) = (conjunct(&before, &[0, 0, 1]), conjunct(&after, &[0, 0, 1])) else { panic!("two atoms") };
    assert!(atom.with_site(site(&after, &[0, 0, 1, 1])) == expected);
}

#[test]
fn two_locals_of_sibling_branches_take_one_name() {
    let before = read("(RULE &a (input *P *C) (OR ((input P (:key *X))) ((input P))))");
    let after = read("(RULE &a (input *P *C) (OR ((input P (:key *X))) ((input P (:key *X)))))");
    let edit = Edit::AddSite { node: path(&[0, 0, 1, 1, 0]), index: 1, site: site(&after, &[0, 0, 1, 1, 0, 1]) };
    assert!(before.apply(&edit).expect("the edit applies") == after);
}

#[test]
fn a_join_that_the_join_rule_gives_another_label_is_refused() {
    let program = read("(RULE &a (input *P (:key *X)) (OR ((input P (:t *X))) ((input P))))");
    let join = |label: u32| Site {
        column: ColumnName::Written("key".into()),
        value: SiteValue { args: Arc::new([SiteArg::NamedLabel { name: ColumnName::Written("X".into()), label: LabelUse::Join(LabelId(label)) }]) },
    };
    let edit = |label| Edit::AddSite { node: path(&[0, 0, 1, 0, 0]), index: 2, site: join(label) };
    assert!(matches!(program.apply(&edit(1)), Err(EditError::BareLabel { .. })));
    assert!(program.apply(&edit(2)).is_ok());
}
