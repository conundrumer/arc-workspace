//! Edits of a program value. An edit adds, removes or replaces an atom or a
//! site, or adds a top-level form; it gives a new value and leaves the old
//! one. A partial atom, a relation with the sites given so far, is a
//! well-formed atom whose other columns are projected away.
//!
//! This module holds the edits, [`Edit`] and [`EditError`], and
//! [`Node::apply`], which applies one: it names the children of a node that
//! the edit changes, has `rebuild` build the tree that results, and has
//! `labels` check the naming conditions of the labels of the result. The
//! submodules hold the rest. `rebuild` holds the tree an edit rebuilds,
//! `labels` the naming conditions, and `partial` the partial atom. The public
//! items of the package are those of this module and [`Node::with_site`];
//! the rebuild and the checks run only from [`Node::apply`].

mod labels;
mod partial;
mod rebuild;

use super::path::{node_at, NodePath, NodeRef};
use super::*;
use labels::{check_label_kinds, check_label_names};
use rebuild::{rebuild, Owned, Rebuilt};

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

fn label_of(use_: LabelUse) -> Option<LabelId> {
    match use_ {
        LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => Some(label),
        LabelUse::Zero => None,
    }
}
