//! The types of a checked case program, as the type check hands them on:
//! [`FormTypes`], the types of the labels of one label scope and the
//! columns its forms fix, and [`ProgramTypes`], those of every scope of the
//! program and of every relation's columns. The lattice and the walk that
//! infers a label's type are in [`super`].

use super::ValueType;

/// The types the type check infers for the labels of one label scope of a
/// form, as [`crate::program::LabelId`] gives scopes, which the check cache
/// keeps beside the form's type check, so that the cases that share a form
/// share its types. In the check cache a label is its canonical position in
/// its scope, as `LabelId(position)`, and a key row's labels are the same.
/// [`ProgramTypes`] holds the scope's own labels.
///
/// In the check cache it holds as well the type of each column of each
/// relation that a form of the scope gives whose columns the form's
/// declaration fixes, each by its [`FormRelation`]. Those types name no
/// label, and a Pose type among them names its key row by
/// [`super::KeyRow::Columns`].
///
/// For a `RIGID_DET` form it holds as well the labels at its parts' sites
/// and key columns that are the assembly's own Idents
/// (`docs/arclog/rigid.md#semantics`), which a renaming of Idents moves
/// when it takes the common reading onto an instance's.
#[derive(Clone, Debug, Default)]
pub struct FormTypes {
    labels: crate::hash::StableHashMap<crate::program::LabelId, ValueType>,
    relations: crate::hash::StableHashMap<FormRelation, Box<[ValueType]>>,
    own_idents: crate::hash::StableHashSet<crate::program::LabelId>,
}

/// A relation that a form gives: the form's canonical path relative to the
/// top-level form whose scopes the check cache keeps, and the path after the form's name of the output,
/// such as `.value` of an instance or `&glyph` of a `RIGID_DET` form, or the
/// empty path for the form's own relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FormRelation {
    pub form: crate::program::path::NodePath,
    pub output: std::sync::Arc<[crate::program::OutputStep]>,
}

impl FormTypes {
    /// The types of `labels`, and the column types of `relations`.
    pub(crate) fn new(
        labels: impl IntoIterator<Item = (crate::program::LabelId, ValueType)>,
        relations: impl IntoIterator<Item = (FormRelation, Box<[ValueType]>)>,
    ) -> Self {
        FormTypes { labels: labels.into_iter().collect(), relations: relations.into_iter().collect(), own_idents: Default::default() }
    }

    /// These types with `labels` the labels at the form's parts' sites and
    /// key columns that are the assembly's own Idents.
    pub(crate) fn with_own_idents(mut self, labels: impl IntoIterator<Item = crate::program::LabelId>) -> Self {
        self.own_idents = labels.into_iter().collect();
        self
    }

    /// Whether `label` stands at a site of a part or a key column of the
    /// `RIGID_DET` form, and is the assembly's own Ident there.
    pub fn is_own_ident(&self, label: crate::program::LabelId) -> bool {
        self.own_idents.contains(&label)
    }

    /// Each relation whose columns the declaration of a form of the scope
    /// fixes, with the type of each of its columns.
    pub fn relations(&self) -> impl Iterator<Item = (&FormRelation, &[ValueType])> + '_ {
        self.relations.iter().map(|(relation, columns)| (relation, &columns[..]))
    }

    /// The type of `label`, or `None` where the form has no such label.
    pub fn label(&self, label: crate::program::LabelId) -> Option<&ValueType> {
        self.labels.get(&label)
    }

    /// Each label with its type.
    pub fn labels(&self) -> impl Iterator<Item = (crate::program::LabelId, &ValueType)> + '_ {
        self.labels.iter().map(|(label, ty)| (*label, ty))
    }
}

/// A relation of a case program: the node of the dependency graph that holds
/// it, and, for an output of a node with several, such as an instance, a
/// `RIGID_DET` form or a recursive instance, the output's path. Two
/// relations of one name in two name scopes are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct GraphRelation {
    pub node: crate::resolver::GraphNodeIndex,
    pub output: Option<std::sync::Arc<[crate::program::OutputStep]>>,
}

/// The types the type check infers for a checked case program: the type of
/// each label of each clause, and the type of each column of each relation.
/// The types are static: a row has no type tag.
///
/// `0` takes the type of the label or the column it stands at, so it has no
/// entry of its own.
#[derive(Clone, Debug, Default)]
pub struct ProgramTypes {
    forms: crate::hash::StableHashMap<crate::program::path::NodePath, std::sync::Arc<FormTypes>>,
    columns: crate::hash::StableHashMap<GraphRelation, Box<[ValueType]>>,
    /// The nodes whose relations have an Example column.
    example_nodes: crate::hash::StableHashSet<crate::resolver::GraphNodeIndex>,
}

impl ProgramTypes {
    /// The types of the labels of the label scope whose form stands at
    /// `form`, a path of the program, as [`crate::program::LabelId`] gives
    /// scopes.
    pub fn form(&self, form: &crate::program::path::NodePath) -> Option<&FormTypes> {
        self.forms.get(form).map(|types| &**types)
    }

    /// Sets the types of the labels of the scope at `form`.
    pub(crate) fn insert_form(&mut self, form: crate::program::path::NodePath, types: std::sync::Arc<FormTypes>) {
        self.forms.insert(form, types);
    }

    /// The type of each column of `relation`, one per column, a record's
    /// fields each a column of its own, or `None` where the type check
    /// gives a column of the relation no type.
    pub fn columns(&self, relation: &GraphRelation) -> Option<&[ValueType]> {
        self.columns.get(relation).map(|columns| &columns[..])
    }

    /// Every typed graph relation, including output ports of shared nodes.
    pub fn relations(&self) -> impl Iterator<Item = (&GraphRelation, &[ValueType])> + '_ {
        self.columns.iter().map(|(relation, columns)| (relation, &columns[..]))
    }

    /// Sets the type of each column of `relation`.
    pub(crate) fn insert_columns(&mut self, relation: GraphRelation, columns: Box<[ValueType]>) {
        self.columns.insert(relation, columns);
    }

    /// Whether `relation` has an Example column, as the checker decides it
    /// by [`crate::check::reads::example_relations`].
    pub fn has_example_column(&self, relation: &GraphRelation) -> bool {
        self.example_nodes.contains(&relation.node)
    }

    /// Sets the nodes whose relations have an Example column.
    pub(crate) fn set_example_nodes(&mut self, nodes: crate::hash::StableHashSet<crate::resolver::GraphNodeIndex>) {
        self.example_nodes = nodes;
    }
}
