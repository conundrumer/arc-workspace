//! The tree that an edit rebuilds. An edit changes the children of one node;
//! [`rebuild`] gives the node with them in place of its own, and each node
//! above it given its new child, sharing every node the edit does not change.
//! A node that takes new children takes the columns of its new body again.

use std::sync::Arc;

use super::super::path::{Handle, NodeRef, NodePath, PathStep};
use super::super::*;
use super::label_of;
use crate::read::columns::{key_labels, made_labels};
use crate::safety::each_label_use_at;

/// A node an edit rebuilds, owned: each kind of [`NodeRef`], a bare-label
/// argument of a site as [`Owned::Arg`].
#[derive(Clone)]
pub(super) enum Owned {
    Program(Node<Program>),
    Form(Form),
    Alt(Node<Alt>),
    KeyClause(Node<KeyClause>),
    Input(Node<InstanceInput>),
    DemoRule(Node<DemoRule>),
    Body(Node<Body>),
    Conjunct(Conjunct),
    /// A part of a `RIGID_DET` form.
    Atom(Node<Atom>),
    Site(Site),
    /// A [`SiteArg::Label`] or a [`SiteArg::NamedLabel`].
    Arg(SiteArg),
}

/// What a rebuild of a node gives: the node, or none where it is a site
/// left with no argument.
pub(super) enum Rebuilt {
    Node(Owned),
    Gone,
}

/// The node `node` with the node at `path` below it given the children that
/// `change` makes of its own, and each node above that given its new child,
/// or `None` where `path` names no node or `change` refuses it.
pub(super) fn rebuild(node: &Owned, path: &[PathStep], change: &mut dyn FnMut(&Owned, Vec<Owned>) -> Option<Vec<Owned>>) -> Option<Rebuilt> {
    let mut children = node.children();
    match path.split_first() {
        None => children = change(node, children)?,
        Some((step, rest)) => {
            let index = step.0 as usize;
            match rebuild(children.get(index)?, rest, change)? {
                Rebuilt::Node(child) => children[index] = child,
                Rebuilt::Gone => {
                    children.remove(index);
                }
            }
        }
    }
    node.with_children(children)
}

impl Owned {
    /// The node's children, in the order of [`NodeRef::children`].
    fn children(&self) -> Vec<Owned> {
        self.node().handles().into_iter().map(Owned::from).collect()
    }

    /// The node, borrowed.
    fn node(&self) -> NodeRef<'_> {
        match self {
            Owned::Program(program) => NodeRef::Program(program.value()),
            Owned::Form(form) => Handle::Form(form).node(),
            Owned::Alt(alt) => Handle::Alt(alt).node(),
            Owned::KeyClause(clause) => Handle::KeyClause(clause).node(),
            Owned::Input(input) => Handle::Input(input).node(),
            Owned::DemoRule(rule) => Handle::DemoRule(rule).node(),
            Owned::Body(body) => Handle::Body(body).node(),
            Owned::Conjunct(conjunct) => Handle::Conjunct(conjunct).node(),
            Owned::Atom(atom) => Handle::Atom(atom).node(),
            Owned::Site(site) => Handle::Site(site).node(),
            Owned::Arg(arg) => Handle::Arg(arg).node(),
        }
    }

    /// The node with `children` in place of its own, in the order of
    /// [`Owned::children`], and the columns of each clause, key body,
    /// `CHOOSE` form and `DEMO_RULE` form it is computed again from them;
    /// [`Rebuilt::Gone`] for a site left with no argument, and `None` where
    /// a child is not of the kind its place holds.
    fn with_children(&self, children: Vec<Owned>) -> Option<Rebuilt> {
        let node = match self {
            Owned::Program(_) => Owned::Program(Node::new(Program { forms: all(children, as_form)? })),
            Owned::Form(form) => Owned::Form(form_with(form, children)?),
            Owned::Alt(alt) => {
                let items = all(children, |child| match child {
                    Owned::Form(form) => Some(AltItem::Form(form)),
                    Owned::Alt(alt) => Some(AltItem::Alt(alt)),
                    _ => None,
                })?;
                Owned::Alt(Node::new(Alt { name: alt.value().name.clone(), items }))
            }
            Owned::KeyClause(clause) => {
                let mut children = children.into_iter();
                let key = key_body(&clause.value().key, as_body(children.next()?)?);
                Owned::KeyClause(Node::new(KeyClause { key, inputs: all(children, as_input)? }))
            }
            Owned::Input(input) => {
                let mut children = children;
                let body = as_body(children.pop()?)?;
                let input = input.value();
                Owned::Input(Node::new(InstanceInput { name: input.name.clone(), head: all(children, as_site)?, body }))
            }
            Owned::DemoRule(rule) => {
                let rule = rule.value();
                if children.len() != rule.forms.len() {
                    return None;
                }
                let forms: RuleForms = children.into_iter().enumerate().map(|(index, child)| Some((as_form(child)?, rule.forms.from_alt(index)))).collect::<Option<_>>()?;
                let fields = demo_rule_fields(rule, &forms);
                Owned::DemoRule(Node::new(DemoRule { name: rule.name.clone(), fields, text: rule.text.clone(), forms }))
            }
            Owned::Body(_) => Owned::Body(Node::new(Body { conjuncts: all(children, |child| match child {
                Owned::Conjunct(conjunct) => Some(conjunct),
                _ => None,
            })? })),
            Owned::Conjunct(conjunct) => Owned::Conjunct(conjunct_with(conjunct, children)?),
            Owned::Atom(atom) => Owned::Atom(atom_with(atom, children)?),
            Owned::Site(site) => {
                if children.is_empty() {
                    return Some(Rebuilt::Gone);
                }
                let args = all(children, |child| match child {
                    Owned::Site(field) => Some(SiteArg::Field(field)),
                    Owned::Arg(arg) => Some(arg),
                    _ => None,
                })?;
                Owned::Site(Site { column: site.column.clone(), value: SiteValue { args } })
            }
            Owned::Arg(arg) => {
                if !children.is_empty() {
                    return None;
                }
                Owned::Arg(arg.clone())
            }
        };
        Some(Rebuilt::Node(node))
    }
}

impl From<Handle<'_>> for Owned {
    fn from(handle: Handle<'_>) -> Owned {
        match handle {
            Handle::Form(form) => Owned::Form(form.clone()),
            Handle::Alt(alt) => Owned::Alt(alt.clone()),
            Handle::KeyClause(clause) => Owned::KeyClause(clause.clone()),
            Handle::Input(input) => Owned::Input(input.clone()),
            Handle::DemoRule(rule) => Owned::DemoRule(rule.clone()),
            Handle::Body(body) => Owned::Body(body.clone()),
            Handle::Conjunct(conjunct) => Owned::Conjunct(conjunct.clone()),
            Handle::Atom(atom) => Owned::Atom(atom.clone()),
            Handle::Site(site) => Owned::Site(site.clone()),
            Handle::Arg(arg) => Owned::Arg(arg.clone()),
        }
    }
}

/// Each of `children` as `convert` gives it, or `None` where one is not of
/// its kind.
fn all<T>(children: impl IntoIterator<Item = Owned>, convert: impl FnMut(Owned) -> Option<T>) -> Option<Arc<[T]>> {
    children.into_iter().map(convert).collect()
}

fn as_form(child: Owned) -> Option<Form> {
    match child {
        Owned::Form(form) => Some(form),
        _ => None,
    }
}

fn as_body(child: Owned) -> Option<Node<Body>> {
    match child {
        Owned::Body(body) => Some(body),
        _ => None,
    }
}

fn as_input(child: Owned) -> Option<Node<InstanceInput>> {
    match child {
        Owned::Input(input) => Some(input),
        _ => None,
    }
}

fn as_site(child: Owned) -> Option<Site> {
    match child {
        Owned::Site(site) => Some(site),
        _ => None,
    }
}

/// `form` with `children` in place of its own.
fn form_with(form: &Form, children: Vec<Owned>) -> Option<Form> {
    let mut children = children.into_iter().peekable();
    let form = match form {
        Form::Claim(claim) => Form::Claim(Node::new(Claim { forms: all(children, as_form)?, ..claim.value().clone() })),
        Form::Clause(clause) => {
            let clause = clause.value();
            let body = as_body(children.next()?)?;
            if children.next().is_some() {
                return None;
            }
            let columns = columns_of(&clause.columns, made_labels(body.value()));
            Form::Clause(Node::new(Clause { body, columns, ..clause.clone() }))
        }
        Form::Instance(instance) => {
            let instance = instance.value();
            let key = match instance.key {
                Some(_) => match children.next()? {
                    Owned::KeyClause(key) => Some(key),
                    _ => return None,
                },
                None => None,
            };
            Form::Instance(Node::new(Instance { key, inputs: all(children, as_input)?, ..instance.clone() }))
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let rows = match &choose.rows {
                Some(rows) => Some(key_body(rows, as_body(children.next()?)?)),
                None => None,
            };
            let from = as_body(children.next()?)?;
            let candidate_columns = columns_of(&choose.candidate_columns, made_labels(from.value()));
            Form::Choose(Node::new(Choose { rows, candidate_columns, from, never: all(children, as_body)?, ..choose.clone() }))
        }
        Form::RigidDet(rigid) => {
            let rigid = rigid.value();
            let mut clause = |old: &Option<KeyBody>| -> Option<Option<KeyBody>> {
                match old {
                    Some(old) => Some(Some(key_body(old, as_body(children.next()?)?))),
                    None => Some(None),
                }
            };
            let key = clause(&rigid.key)?;
            let instance = clause(&rigid.instance)?;
            let parts = all(children, |child| match child {
                Owned::Atom(atom) => Some(atom),
                _ => None,
            })?;
            Form::RigidDet(Node::new(RigidDet { name: rigid.name.clone(), key, instance, parts }))
        }
        Form::Out(out) => {
            let body = as_body(children.next()?)?;
            if children.next().is_some() {
                return None;
            }
            Form::Out(Node::new(Out { key: key_body(&out.value().key, body) }))
        }
        Form::Demonstrated(demonstrated) => {
            let demonstrated = demonstrated.value();
            let key = match demonstrated.key {
                Some(_) => match children.next()? {
                    Owned::KeyClause(key) => Some(key),
                    _ => return None,
                },
                None => None,
            };
            let mut inputs = Vec::new();
            while let Some(Owned::Input(_)) = children.peek() {
                inputs.extend(children.next().and_then(as_input));
            }
            let rules = all(children, |child| match child {
                Owned::DemoRule(rule) => Some(rule),
                _ => None,
            })?;
            Form::Demonstrated(Node::new(Demonstrated { name: demonstrated.name.clone(), key, inputs: inputs.into(), rules }))
        }
        Form::Alts(alts) => {
            let alts_value = alts.value();
            let blocks = all(children, |child| match child {
                Owned::Alt(alt) => Some(alt),
                _ => None,
            })?;
            Form::Alts(Node::new(Alts { alts: blocks, ..alts_value.clone() }))
        }
    };
    Some(form)
}

/// `conjunct` with `children` in place of its own.
fn conjunct_with(conjunct: &Conjunct, children: Vec<Owned>) -> Option<Conjunct> {
    let bodies = || -> Option<Vec<Node<Body>>> { children.iter().cloned().map(as_body).collect() };
    let conjunct = match conjunct {
        Conjunct::Atom(atom) => Conjunct::Atom(atom_with(atom, children)?),
        Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(atom_with(atom, children)?)),
        Conjunct::Not(Negated::Form(_)) => match <[Owned; 1]>::try_from(children).ok()? {
            [Owned::Conjunct(form)] => Conjunct::Not(Negated::Form(Arc::new(form))),
            _ => return None,
        },
        Conjunct::Constraint(constraint) => {
            if !children.is_empty() {
                return None;
            }
            Conjunct::Constraint(*constraint)
        }
        Conjunct::Or(_) => {
            let branches = bodies()?;
            if branches.is_empty() {
                return None;
            }
            Conjunct::Or(branches.into())
        }
        Conjunct::If { .. } => {
            let [test, then, otherwise] = <[Node<Body>; 3]>::try_from(bodies()?).ok()?;
            Conjunct::If { test, then, otherwise }
        }
        Conjunct::All { .. } => {
            let [domain, body] = <[Node<Body>; 2]>::try_from(bodies()?).ok()?;
            Conjunct::All { domain, body }
        }
    };
    Some(conjunct)
}

/// `atom` with `children`, sites, in place of its sites.
fn atom_with(atom: &Node<Atom>, children: Vec<Owned>) -> Option<Node<Atom>> {
    Some(Node::new(Atom { relation: atom.value().relation.clone(), sites: all(children, as_site)? }))
}

/// The key body `old` with `body` in place of its body, and its columns
/// the `^` labels of `body`.
fn key_body(old: &KeyBody, body: Node<Body>) -> KeyBody {
    let columns = columns_of(&old.columns, key_labels(body.value()));
    KeyBody { body, columns }
}

/// The columns of `labels`, in their order: a column of `old` keeps its
/// name, and each other is named by its slot.
fn columns_of(old: &[RelationColumn], labels: Vec<LabelId>) -> Arc<[RelationColumn]> {
    let column = |(slot, label): (usize, LabelId)| match old.iter().find(|column| column.label == label) {
        Some(column) => column.clone(),
        None => RelationColumn { name: ColumnName::Slot(slot as u32), label },
    };
    labels.into_iter().enumerate().map(column).collect()
}

/// The fields of `rule` once its forms are `forms`: each field but those
/// whose label its forms read and `forms` no longer read.
fn demo_rule_fields(rule: &DemoRule, forms: &[Form]) -> Arc<[RelationColumn]> {
    let read = |forms: &[Form]| {
        let mut labels = Vec::new();
        for (form, index) in forms.iter().zip(0u32..) {
            each_label_use_at(NodeRef::from(form), &NodePath::top(index), &mut |_, use_| labels.extend(label_of(use_)));
        }
        labels
    };
    let (before, after) = (read(&rule.forms), read(forms));
    let kept = rule.fields.iter().filter(|field| !before.contains(&field.label) || after.contains(&field.label));
    let labels: Vec<LabelId> = kept.map(|field| field.label).collect();
    columns_of(&rule.fields, labels)
}
