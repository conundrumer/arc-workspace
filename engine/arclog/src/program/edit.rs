//! Edits of a program value. An edit adds, removes or replaces an atom or a
//! site, or adds a top-level form; it gives a new value and leaves the old
//! one. A partial atom, a
//! relation with the sites given so far, is a well-formed atom whose other
//! columns are projected away.

use std::collections::HashMap;
use std::sync::Arc;

use super::path::{node_at, NodePath, NodeRef, PathStep};
use super::*;
use crate::read::columns::{key_labels, made_labels};
use crate::read::is_type_parameter_column;
use crate::safety::each_label_use_at;

/// An edit of a program, at the node its path names, as [`Node::apply`]
/// applies it.
#[derive(Clone, Debug)]
pub enum Edit {
    /// Inserts `conjunct` into the body at `body`, at `index` of its source
    /// order.
    AddConjunct {
        body: NodePath,
        index: u32,
        conjunct: Conjunct,
    },
    /// Removes the conjunct at `at`.
    RemoveConjunct { at: NodePath },
    /// Replaces the conjunct at `at` with `conjunct`.
    ReplaceConjunct { at: NodePath, conjunct: Conjunct },
    /// Adds `site` to the node at `node`, at `index` of its sites in source
    /// order: an atom, a negated atom, a `RIGID_DET` part, an input, whose
    /// head takes it, or a site, which takes it as a field-site argument.
    ///
    /// On a site, `index` counts all of its arguments, bare labels and field
    /// sites alike, as the table in `engine/arclog/src/program/path.rs`
    /// gives them. A `node` that names a bare-label argument gives
    /// [`EditError::Path`].
    AddSite {
        node: NodePath,
        index: u32,
        site: Site,
    },
    /// Inserts `part` into the `RIGID_DET` form at `form`, at `index` of its
    /// parts in source order.
    AddPart {
        form: NodePath,
        index: u32,
        part: Node<Atom>,
    },
    /// Removes the part at `at`.
    RemovePart { at: NodePath },
    /// Replaces the part at `at` with `part`.
    ReplacePart { at: NodePath, part: Node<Atom> },
    /// Removes the site at `at`, of any node that `AddSite` names. Where `at`
    /// names an argument of a site, a bare label or a field site, the edit
    /// removes that argument. A site the removal leaves with no argument is
    /// removed too, as [`Node::apply`] gives.
    RemoveSite { at: NodePath },
    /// Replaces the site at `at` with `site`. Where `at` names an argument
    /// of a site, a bare label or a field site, `site` takes its place as a
    /// field site.
    ReplaceSite { at: NodePath, site: Site },
    /// Inserts `form` into the program's top-level forms, at `index` of
    /// their source order.
    AddForm { index: u32, form: Form },
}

/// An edit that [`Node::apply`] refuses, with the path of the node it names.
#[derive(Clone, Debug)]
pub enum EditError {
    /// A path of the edit names no node of the edit's kind.
    Path { path: NodePath },
    /// The program the edit gives holds at `path` a bare label that breaks
    /// the naming conditions of [`Node::apply`]: a
    /// [`super::SiteArg::Label`] other than `0` at a site on a column of a
    /// type parameter, a [`super::SiteArg::NamedLabel`] at a site on a
    /// fixed-type column or on a field, or a `NamedLabel` whose name is not
    /// the one name of its label over its scope.
    BareLabel { path: NodePath },
}

impl Node<Program> {
    /// The program that `edit` gives. `self` is left as it was, and the new
    /// value shares every node the edit does not change. The paths of `edit`
    /// name nodes as [`super::path::node_at`] walks them.
    ///
    /// Each node the edit changes, a clause, a key body, a `CHOOSE` form or
    /// a `DEMO_RULE` form, takes the columns of its new body: the labels the
    /// body keeps, in order of first appearance. A column whose label the
    /// edit removes is dropped. A column whose label the node keeps keeps its
    /// written name, and each other column is named by its slot, its position
    /// among the columns. The edit gives no diagnostic for a read elsewhere
    /// of a dropped column, which the resolver reports.
    ///
    /// Where a [`Edit::RemoveSite`] leaves a site with no argument, the
    /// edit removes that site too, and so on up each enclosing site it
    /// leaves with none, until the node that holds the removed site is no
    /// site: `RemoveSite` on `(:D D)` of `(:key (:C (:D D)))` gives the atom
    /// with `(:key ...)` left out. Each [`super::SiteValue`] of the program
    /// `apply` gives holds an argument.
    ///
    /// The program `apply` gives holds each bare label other than `0` as a
    /// [`super::SiteArg::NamedLabel`] at each site on a column of a type
    /// parameter, and as a [`super::SiteArg::Label`] at each other site, a
    /// site on a fixed-type column, on a column the node names by its slot,
    /// or on a field, as the doc of
    /// [`super::SiteArg`] gives the two variants. Each label of a scope has
    /// one name over its `NamedLabel` arguments. Each site of such a label,
    /// read by the join rule of `engine/arclog/src/read/labels.rs`, takes
    /// that label under that name. So two labels of one scope take one name only
    /// where that rule keeps them apart, as two locals of sibling `OR`
    /// branches. An edit whose result breaks this gives
    /// [`EditError::BareLabel`] at the site, and a path that names no node of
    /// the edit's kind gives [`EditError::Path`].
    pub fn apply(&self, edit: &Edit) -> Result<Node<Program>, EditError> {
        let refused = || EditError::Path { path: edit.path() };
        let split = |at: &NodePath| split_last(at).ok_or_else(refused);
        let (parent, change): (NodePath, Change) = match edit {
            Edit::AddConjunct { body, index, conjunct } => (body.clone(), Change::Insert { index: *index, child: Owned::Conjunct(conjunct.clone()) }),
            Edit::RemoveConjunct { at } | Edit::RemovePart { at } | Edit::RemoveSite { at } => {
                let (parent, index) = split(at)?;
                (parent, Change::Remove { index })
            }
            Edit::ReplaceConjunct { at, conjunct } => {
                let (parent, index) = split(at)?;
                (parent, Change::Replace { index, child: Owned::Conjunct(conjunct.clone()) })
            }
            Edit::ReplacePart { at, part } => {
                let (parent, index) = split(at)?;
                (parent, Change::Replace { index, child: Owned::Atom(part.clone()) })
            }
            Edit::ReplaceSite { at, site } => {
                let (parent, index) = split(at)?;
                (parent, Change::Replace { index, child: Owned::Site(site.clone()) })
            }
            Edit::AddSite { node, index, site } => (node.clone(), Change::Insert { index: *index, child: Owned::Site(site.clone()) }),
            Edit::AddPart { form, index, part } => (form.clone(), Change::Insert { index: *index, child: Owned::Atom(part.clone()) }),
            Edit::AddForm { index, form } => (NodePath::default(), Change::Insert { index: *index, child: Owned::Form(form.clone()) }),
        };
        let root = Owned::Program(self.clone());
        let Some(Rebuilt::Node(Owned::Program(program))) = rebuild(&root, &parent.0, &mut |node, children| change.apply(edit, node, children)) else {
            return Err(refused());
        };
        if let Some(added) = edit.added_at(program.value()) {
            let node = node_at(NodeRef::Program(program.value()), &added).expect("the node the edit adds");
            let on_field = matches!(node_at(NodeRef::Program(program.value()), &parent), Some(NodeRef::Site(_)));
            check_label_kinds(node, &added, on_field)?;
        }
        let top = edit.path().0.first().copied().ok_or_else(refused)?;
        if let Some(form) = program.value().forms.get(top.0 as usize) {
            check_label_names(NodeRef::from(form), &NodePath::top(top.0))?;
        }
        Ok(program)
    }
}

impl Edit {
    /// The path the edit names: the node it adds into, or the node it
    /// removes or replaces, or for [`Edit::AddForm`] the path the form takes.
    fn path(&self) -> NodePath {
        match self {
            Edit::AddConjunct { body: path, .. } | Edit::AddSite { node: path, .. } | Edit::AddPart { form: path, .. } => path.clone(),
            Edit::RemoveConjunct { at }
            | Edit::ReplaceConjunct { at, .. }
            | Edit::RemovePart { at }
            | Edit::ReplacePart { at, .. }
            | Edit::RemoveSite { at }
            | Edit::ReplaceSite { at, .. } => at.clone(),
            Edit::AddForm { index, .. } => NodePath::top(*index),
        }
    }

    /// The path of the node the edit puts into `program`, the program it
    /// gave, or `None` for an edit that removes.
    fn added_at(&self, program: &Program) -> Option<NodePath> {
        match self {
            Edit::AddConjunct { body: parent, index, .. } | Edit::AddSite { node: parent, index, .. } => Some(parent.child(*index)),
            Edit::AddPart { form, index, .. } => {
                let Some(NodeRef::RigidDet(rigid)) = node_at(NodeRef::Program(program), form) else { return None };
                Some(form.child(rigid.position(RigidDetPart::Part(*index as usize))))
            }
            Edit::ReplaceConjunct { at, .. } | Edit::ReplacePart { at, .. } | Edit::ReplaceSite { at, .. } => Some(at.clone()),
            Edit::AddForm { index, .. } => Some(NodePath::top(*index)),
            Edit::RemoveConjunct { .. } | Edit::RemovePart { .. } | Edit::RemoveSite { .. } => None,
        }
    }
}

/// The path of the parent of the node at `path`, and the index of that
/// node among its children, or `None` for the root.
fn split_last(path: &NodePath) -> Option<(NodePath, u32)> {
    let (last, parent) = path.0.split_last()?;
    Some((NodePath(parent.into()), last.0))
}

/// What an edit does to the children of the node it names.
enum Change {
    Insert { index: u32, child: Owned },
    Remove { index: u32 },
    Replace { index: u32, child: Owned },
}

impl Change {
    /// The children of `node` that `edit` gives, or `None` where `node` is
    /// not a node of the edit's kind or holds no child at the edit's index.
    fn apply(&self, edit: &Edit, node: &Owned, mut children: Vec<Owned>) -> Option<Vec<Owned>> {
        let holds_sites = matches!(node, Owned::Atom(_) | Owned::Input(_) | Owned::Site(_)) || matches!(node, Owned::Conjunct(conjunct) if conjunct.atom().is_some());
        let (index, kind_holds) = match (edit, node) {
            (Edit::AddConjunct { .. } | Edit::RemoveConjunct { .. } | Edit::ReplaceConjunct { .. }, Owned::Body(_)) => (self.index() as usize, true),
            (Edit::AddSite { .. } | Edit::RemoveSite { .. } | Edit::ReplaceSite { .. }, _) => (self.index() as usize, holds_sites),
            (Edit::AddPart { index, .. }, Owned::Form(Form::RigidDet(rigid))) => (part_position(rigid.value(), *index as usize)?, true),
            (Edit::RemovePart { .. } | Edit::ReplacePart { .. }, Owned::Form(Form::RigidDet(_))) => (self.index() as usize, true),
            (Edit::AddForm { .. }, Owned::Program(_)) => (self.index() as usize, true),
            _ => (0, false),
        };
        if !kind_holds {
            return None;
        }
        let sites = match node {
            Owned::Input(input) => input.value().head.len(),
            _ => children.len(),
        };
        match self {
            Change::Insert { child, .. } => {
                let bound = if holds_sites { sites } else { children.len() };
                if index > bound {
                    return None;
                }
                children.insert(index, child.clone());
            }
            Change::Remove { .. } | Change::Replace { .. } => {
                let kind = children.get(index)?;
                let same = match edit {
                    Edit::RemoveConjunct { .. } | Edit::ReplaceConjunct { .. } => matches!(kind, Owned::Conjunct(_)),
                    Edit::RemovePart { .. } | Edit::ReplacePart { .. } => matches!(kind, Owned::Atom(_)),
                    _ => matches!(kind, Owned::Site(_) | Owned::Arg(_)),
                };
                if !same {
                    return None;
                }
                match self {
                    Change::Replace { child, .. } => children[index] = child.clone(),
                    _ => {
                        children.remove(index);
                    }
                }
            }
        }
        Some(children)
    }

    fn index(&self) -> u32 {
        match self {
            Change::Insert { index, .. } | Change::Remove { index } | Change::Replace { index, .. } => *index,
        }
    }
}

/// The position among the children of `rigid` at which a part inserted at
/// `index` of its parts stands, or `None` past its last part.
fn part_position(rigid: &RigidDet, index: usize) -> Option<usize> {
    (index <= rigid.parts.len()).then(|| rigid.children().count() - rigid.parts.len() + index)
}

/// A node an edit rebuilds, owned: each kind of [`NodeRef`], a bare-label
/// argument of a site as [`Owned::Arg`].
#[derive(Clone)]
enum Owned {
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
enum Rebuilt {
    Node(Owned),
    Gone,
}

/// The node `node` with the node at `path` below it given the children that
/// `change` makes of its own, and each node above that given its new child,
/// or `None` where `path` names no node or `change` refuses it.
fn rebuild(node: &Owned, path: &[PathStep], change: &mut dyn FnMut(&Owned, Vec<Owned>) -> Option<Vec<Owned>>) -> Option<Rebuilt> {
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
        fn bodies<'a>(bodies: impl IntoIterator<Item = &'a Node<Body>>) -> Vec<Owned> {
            bodies.into_iter().cloned().map(Owned::Body).collect()
        }
        fn sites(sites: &[Site]) -> Vec<Owned> {
            sites.iter().cloned().map(Owned::Site).collect()
        }
        fn forms(forms: &[Form]) -> Vec<Owned> {
            forms.iter().cloned().map(Owned::Form).collect()
        }
        match self {
            Owned::Program(program) => forms(&program.value().forms),
            Owned::Form(Form::Claim(claim)) => forms(&claim.value().forms),
            Owned::Form(Form::Clause(clause)) => bodies([&clause.value().body]),
            Owned::Form(Form::Instance(instance)) => {
                let instance = instance.value();
                instance.key.iter().cloned().map(Owned::KeyClause).chain(instance.inputs.iter().cloned().map(Owned::Input)).collect()
            }
            Owned::Form(Form::Choose(choose)) => {
                let choose = choose.value();
                bodies(choose.rows.iter().map(|rows| &rows.body).chain([&choose.from]).chain(choose.never.iter()))
            }
            Owned::Form(Form::RigidDet(rigid)) => {
                let rigid = rigid.value();
                let clauses = bodies(rigid.key.iter().chain(rigid.instance.iter()).map(|clause| &clause.body));
                clauses.into_iter().chain(rigid.parts.iter().cloned().map(Owned::Atom)).collect()
            }
            Owned::Form(Form::Demonstrated(demonstrated)) => {
                let demonstrated = demonstrated.value();
                let key = demonstrated.key.iter().cloned().map(Owned::KeyClause);
                let inputs = demonstrated.inputs.iter().cloned().map(Owned::Input);
                key.chain(inputs).chain(demonstrated.rules.iter().cloned().map(Owned::DemoRule)).collect()
            }
            Owned::Form(Form::Alts(alts)) => alts.value().alts.iter().cloned().map(Owned::Alt).collect(),
            Owned::Alt(alt) => alt
                .value()
                .items
                .iter()
                .map(|item| match item {
                    AltItem::Form(form) => Owned::Form(form.clone()),
                    AltItem::Alt(alt) => Owned::Alt(alt.clone()),
                })
                .collect(),
            Owned::KeyClause(clause) => {
                let clause = clause.value();
                bodies([&clause.key.body]).into_iter().chain(clause.inputs.iter().cloned().map(Owned::Input)).collect()
            }
            Owned::Input(input) => {
                let input = input.value();
                sites(&input.head).into_iter().chain(bodies([&input.body])).collect()
            }
            Owned::DemoRule(rule) => forms(&rule.value().forms),
            Owned::Body(body) => body.value().conjuncts.iter().cloned().map(Owned::Conjunct).collect(),
            Owned::Conjunct(conjunct) => match conjunct {
                Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => sites(&atom.value().sites),
                Conjunct::Not(Negated::Form(form)) => vec![Owned::Conjunct(Conjunct::clone(form))],
                Conjunct::Constraint(_) => Vec::new(),
                Conjunct::Or(branches) => bodies(branches.iter()),
                Conjunct::If { test, then, otherwise } => bodies([test, then, otherwise]),
                Conjunct::All { domain, body } => bodies([domain, body]),
            },
            Owned::Atom(atom) => sites(&atom.value().sites),
            Owned::Site(site) => site
                .value
                .args
                .iter()
                .map(|arg| match arg {
                    SiteArg::Field(field) => Owned::Site(field.clone()),
                    SiteArg::Label(_) | SiteArg::NamedLabel { .. } => Owned::Arg(arg.clone()),
                })
                .collect(),
            Owned::Arg(_) => Vec::new(),
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

fn label_of(use_: LabelUse) -> Option<LabelId> {
    match use_ {
        LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => Some(label),
        LabelUse::Zero => None,
    }
}

/// Refuses each bare label at a site of `node`, at `at`, of the variant
/// that the naming conditions of [`Node::apply`] do not give it; `on_field`
/// where `node` is a field site.
fn check_label_kinds(node: NodeRef<'_>, at: &NodePath, on_field: bool) -> Result<(), EditError> {
    let NodeRef::Site(site) = node else {
        for (child, index) in node.children().into_iter().zip(0u32..) {
            check_label_kinds(child, &at.child(index), false)?;
        }
        return Ok(());
    };
    let named = !on_field && matches!(&site.column, ColumnName::Written(column) if is_type_parameter_column(column));
    for (arg, index) in site.value.args.iter().zip(0u32..) {
        let path = at.child(index);
        match arg {
            SiteArg::Field(field) => check_label_kinds(NodeRef::Site(field), &path, true)?,
            SiteArg::Label(LabelUse::Zero) => {}
            SiteArg::Label(_) if !named => {}
            SiteArg::NamedLabel { label, .. } if named && *label != LabelUse::Zero => {}
            SiteArg::Label(_) | SiteArg::NamedLabel { .. } => return Err(EditError::BareLabel { path }),
        }
    }
    Ok(())
}

/// Refuses, in the label scope at `at`, `root`, and in each scope below
/// it, a [`SiteArg::NamedLabel`] whose label takes another name in its
/// scope, and a join of a label whose name another label of the scope takes
/// where the join rule of `engine/arclog/src/read/labels.rs` joins it to a
/// site that makes that other label.
fn check_label_names(root: NodeRef<'_>, at: &NodePath) -> Result<(), EditError> {
    let mut scope = ScopeLabels::default();
    scope.walk(root, at, &mut Vec::new())?;
    scope.check_joins()
}

/// The labels of one scope as the text of the program writes them: the
/// name each label takes, and each use of a label with the lists of the text
/// that hold it.
#[derive(Default)]
struct ScopeLabels {
    names: HashMap<LabelId, ColumnName>,
    /// Each use, in source order.
    uses: Vec<Use>,
    lists: u32,
}

struct Use {
    /// The lists of the text that hold the use, outermost first.
    lists: Vec<u32>,
    label: LabelUse,
    path: NodePath,
}

/// A list of the text that holds some children of a node and not the
/// node's own other children, by what it holds.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Wrapper {
    /// An input's head.
    Head,
    /// The `for` clause of a `CHOOSE` form.
    For,
    /// The `key` clause of a `RIGID_DET` form.
    RigidKey,
    /// The `instance` clause of a `RIGID_DET` form.
    RigidInstance,
    /// A list of one child only, by its index.
    Own(u32),
}

impl ScopeLabels {
    fn list(&mut self) -> u32 {
        self.lists += 1;
        self.lists
    }

    /// Reads the uses and the names of `node`, at `at`, which `lists` hold,
    /// and checks each label scope below it apart.
    fn walk(&mut self, node: NodeRef<'_>, at: &NodePath, lists: &mut Vec<u32>) -> Result<(), EditError> {
        let depth = lists.len();
        for _ in 0..own_lists(node) {
            let list = self.list();
            lists.push(list);
        }
        match node {
            NodeRef::Label(use_) => self.uses.push(Use { lists: lists.clone(), label: *use_, path: at.clone() }),
            NodeRef::DemoRule(rule) => {
                let head = self.list();
                let lists: Vec<u32> = lists.iter().copied().chain([head]).collect();
                for field in rule.fields.iter() {
                    self.uses.push(Use { lists: lists.clone(), label: LabelUse::Fresh(field.label), path: at.clone() });
                }
            }
            NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
                let operands = [Some(constraint.first), constraint_second(constraint)];
                for operand in operands.into_iter().flatten() {
                    self.uses.push(Use { lists: lists.clone(), label: operand.into(), path: at.clone() });
                }
            }
            NodeRef::Site(site) => {
                for (arg, index) in site.value.args.iter().zip(0u32..) {
                    if let SiteArg::NamedLabel { name, label } = arg
                        && let Some(label) = label_of(*label)
                        && self.names.entry(label).or_insert_with(|| name.clone()) != name
                    {
                        return Err(EditError::BareLabel { path: at.child(index) });
                    }
                }
            }
            _ => {}
        }
        let mut wrappers: HashMap<Wrapper, u32> = HashMap::new();
        for (child, index) in node.children().into_iter().zip(0u32..) {
            let path = at.child(index);
            if opens_scope(node, index as usize, child) {
                check_label_names(child, &path)?;
                continue;
            }
            let outer = lists.len();
            for wrapper in wrappers_of(node, index, child) {
                let list = match wrappers.get(&wrapper) {
                    Some(list) => *list,
                    None => {
                        let list = self.list();
                        wrappers.insert(wrapper, list);
                        list
                    }
                };
                lists.push(list);
            }
            self.walk(child, &path, lists)?;
            lists.truncate(outer);
        }
        lists.truncate(depth);
        Ok(())
    }

    /// Refuses each join that the join rule gives a site that makes another
    /// label of its name.
    fn check_joins(&self) -> Result<(), EditError> {
        let named = |use_: &Use| label_of(use_.label).and_then(|label| self.names.get(&label).map(|name| (label, name)));
        for join in &self.uses {
            let (LabelUse::Join(label), Some((_, name))) = (join.label, named(join)) else { continue };
            let makers = self.uses.iter().enumerate().filter(|(_, maker)| {
                matches!(maker.label, LabelUse::Fresh(_) | LabelUse::Key(_)) && named(maker).is_some_and(|(_, other)| other == name)
            });
            let nearest = makers.min_by_key(|(order, maker)| {
                let common = maker.lists.iter().zip(&join.lists).take_while(|(a, b)| a == b).count();
                (usize::MAX - common, maker.lists.len() - common, *order)
            });
            if let Some((_, maker)) = nearest
                && label_of(maker.label) != Some(label)
            {
                return Err(EditError::BareLabel { path: join.path.clone() });
            }
        }
        Ok(())
    }
}

/// The number of lists of the text that `node` is written as and that
/// hold all of its children: a form's, a conjunct's, a site's, an input's;
/// `(NOT (<atom>))` is two.
fn own_lists(node: NodeRef<'_>) -> usize {
    match node {
        NodeRef::Program(_) | NodeRef::Body(_) | NodeRef::Label(_) => 0,
        NodeRef::Conjunct(Conjunct::Not(Negated::Atom(_))) => 2,
        _ => 1,
    }
}

/// The lists of the text that hold `child`, the child at `index` of
/// `parent`, inside the lists of `parent` itself, outermost first.
fn wrappers_of(parent: NodeRef<'_>, index: u32, child: NodeRef<'_>) -> Vec<Wrapper> {
    let own = Wrapper::Own(index);
    match (parent, child) {
        (NodeRef::Clause(_) | NodeRef::InstanceInput(_), NodeRef::Body(_)) => Vec::new(),
        (NodeRef::InstanceInput(_), _) => vec![Wrapper::Head],
        (NodeRef::Choose(choose), _) => match choose.parts().nth(index as usize) {
            Some(ChoosePart::For) => vec![Wrapper::For, own],
            Some(ChoosePart::From) if choose.from_inside_for => vec![Wrapper::For, own],
            _ => vec![own],
        },
        (NodeRef::RigidDet(rigid), _) => {
            let key = rigid.key.iter().map(|_| Wrapper::RigidKey);
            let instance = rigid.instance.iter().map(|_| Wrapper::RigidInstance);
            match rigid.children().nth(index as usize) {
                Some(RigidDetPart::Key) => vec![Wrapper::RigidKey, own],
                Some(RigidDetPart::Instance) => key.chain([Wrapper::RigidInstance, own]).collect(),
                _ => key.chain(instance).collect(),
            }
        }
        (_, NodeRef::Body(_)) => vec![own],
        _ => Vec::new(),
    }
}

/// Whether `child`, the child at `index` of `parent`, is a label scope of
/// its own, as [`LabelId`] gives scopes.
fn opens_scope(parent: NodeRef<'_>, index: usize, child: NodeRef<'_>) -> bool {
    match parent {
        NodeRef::Program(_) | NodeRef::Claim(_) | NodeRef::Alt(_) => !matches!(child, NodeRef::Alt(_)),
        NodeRef::Demonstrated(_) => matches!(child, NodeRef::DemoRule(_)),
        NodeRef::DemoRule(rule) => rule.forms.from_alt(index),
        _ => false,
    }
}

impl Node<Atom> {
    /// The atom with `site` added. Added to a positive atom, a site gives a
    /// subset of its rows.
    pub fn with_site(&self, site: Site) -> Node<Atom> {
        let atom = self.value();
        let sites = atom.sites.iter().cloned().chain([site]).collect();
        Node::new(Atom { relation: atom.relation.clone(), sites })
    }
}
