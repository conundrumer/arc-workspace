//! The content and the columns of each node of the graph: the resolved
//! content of each of its forms, with no order, and the
//! columns of its rows, with the position in them of each column that
//! each of its forms gives.

use std::sync::Arc;

use super::super::columns::{Columns, Place};
use super::super::form_columns::{form_columns, row_columns};
use super::super::registry_columns;
use super::super::names::{form_bytes, node_form, Own, Writer};
use super::Builder;
use crate::program::canonical::{canonical_labeling, LabelScope, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Choose, Clause, ColumnName, NameScope, OutputName, OutputOwner, OutputStep, ProgramRelation};
use crate::resolver::{DependencyNode, Resolution};

impl Builder<'_> {
    /// The content and the columns of each node, each node after the
    /// nodes it reads, where no cycle holds it. The content of a node of a
    /// layered resolution that no read of the last form resolves to is
    /// left to [`ResolvedProgram::node_content`], which writes it on its
    /// first read: no pass of the resolution reads it, and it gives the
    /// bytes that writing it here would.
    pub(super) fn contents(&mut self) {
        let offset = self.offset();
        let unread = self.unread_nodes();
        self.names.contents = vec![None; self.nodes.len() - offset];
        self.names.node_columns = vec![None; self.nodes.len() - offset];
        self.names.unwritten = (offset..self.nodes.len()).map(|node| unread[node].then(std::sync::OnceLock::new)).collect();
        let mut visited = vec![false; self.nodes.len()];
        visited[..offset].fill(true);
        for node in offset..self.nodes.len() {
            self.content_of(node, &mut visited, &unread);
        }
    }

    /// Whether no read of the last form resolves to each node, for a node
    /// of a layered resolution of one form, and `false` for every node of
    /// another resolution. A node that only another node reads in the
    /// dependency graph counts as unread, as a write of a content reads no
    /// other node's content.
    fn unread_nodes(&self) -> Vec<bool> {
        let mut unread = vec![self.earlier.is_some(); self.nodes.len()];
        for resolution in self.resolutions.values() {
            if let Resolution::Node(node) = resolution {
                unread[node.0 as usize] = false;
            }
        }
        for (node, forms) in self.forms.iter().enumerate() {
            unread[node] &= forms.len() == 1;
        }
        unread
    }

    fn content_of(&mut self, node: usize, visited: &mut Vec<bool>, unread: &[bool]) {
        if std::mem::replace(&mut visited[node], true) {
            return;
        }
        let reads: Vec<u32> = self.reads[node].iter().copied().collect();
        for read in reads {
            self.content_of(read as usize, visited, unread);
        }
        self.record_kept(node);
        let local = node - self.offset();
        let (content, columns) = if unread[node] {
            (None, self.node_columns(node))
        } else {
            let (content, columns) = self.node_content(node);
            (Some(content), columns)
        };
        if let Some(columns) = &columns {
            self.label_positions(node, columns);
        }
        self.names.contents[local] = content;
        self.names.node_columns[local] = columns;
    }

    /// Records the position in `columns`, the rows of `node`, of each
    /// column that each form of the node gives, by the form's path and the
    /// column's label: each column takes the position of the node's column
    /// of its name.
    fn label_positions(&mut self, node: usize, columns: &Columns) {
        for path in &self.forms[node] {
            let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
            for column in form_columns(form) {
                if let Some(Place::Column(position)) = columns.place(std::slice::from_ref(&column.name)) {
                    self.label_positions.insert((path.clone(), column.label), position);
                }
            }
        }
    }

    /// The content of `node`: its kind and the content of each of its
    /// forms, as [`super::super::names::Names::form_content`] gives it,
    /// with no order; and its
    /// columns, those of its form of least content, where its columns
    /// come from its form.
    fn node_content(&self, node: usize) -> (crate::program::canonical::CanonicalForm, Option<Columns>) {
        let DependencyNode { kind, scope } = &self.nodes[node];
        let mut parts: Vec<(Arc<[u8]>, Option<Columns>)> = Vec::new();
        for path in &self.forms[node] {
            parts.push((form_bytes(&self.names, self.case.value(), scope, path), self.form_columns(node, path)));
        }
        parts.sort_by(|a, b| a.0.cmp(&b.0));
        let columns = parts.iter().find_map(|(_, columns)| columns.clone());
        (node_form(kind, parts.into_iter().map(|(bytes, _)| bytes)), columns)
    }

    /// The columns of `node`, a node of one form, as [`Builder::node_content`]
    /// gives them.
    fn node_columns(&self, node: usize) -> Option<Columns> {
        self.form_columns(node, &self.forms[node][0])
    }

    /// The columns of the relation the form of `node` at `path` gives.
    fn form_columns(&self, node: usize, path: &NodePath) -> Option<Columns> {
        let scope = &self.nodes[node].scope;
        let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
        let own = Own::of(form);
        let writer = Writer { names: &self.names, scope, own: own.as_ref() };
        match form {
            NodeRef::Clause(clause) => match self.concept_columns.get(path) {
                Some(columns) => columns.clone(),
                None => self.clause_columns(node, clause, scope, &writer),
            },
            NodeRef::Choose(choose) => Some(choose_columns(choose, &writer)),
            NodeRef::Out(out) => Some(Columns::of_names(out.key.columns.iter().map(|column| column.name.clone()))),
            _ => None,
        }
    }

    /// Records in [`super::super::names::Names::kept`] the columns that the
    /// relation of each clause of `node` keeps, as [`Builder::kept_columns`]
    /// gives them, where they differ, in count or in order, from the
    /// clause's columns in their canonical positions, and the clause does
    /// not resolve in the concept program.
    fn record_kept(&mut self, node: usize) {
        let mut kept = Vec::new();
        let scope = &self.nodes[node].scope;
        for path in &self.forms[node] {
            if self.concept_columns.contains_key(path) {
                continue;
            }
            let Some(NodeRef::Clause(clause)) = node_at(NodeRef::Program(self.case.value()), path) else { continue };
            if let Some(columns) = self.kept_columns(node, clause) {
                let own = Own::of(NodeRef::Clause(clause));
                let writer = Writer { names: &self.names, scope, own: own.as_ref() };
                if !columns.names().eq(canonical_columns(clause, &writer).names()) {
                    kept.push((path.clone(), columns));
                }
            }
        }
        self.names.kept.extend(kept);
    }

    /// The columns of the relation a clause of `node` derives, where
    /// `node` is a `DET` parameter node that an atom reads: its labels that
    /// a site of a read of the relation names, in the order the clause
    /// gives them, as [`Builder::keeps`] gives them.
    fn kept_columns(&self, node: usize, clause: &Clause) -> Option<Columns> {
        if clause.columns.is_empty() || self.read_columns[node].is_none() {
            return None;
        }
        let kept = clause.columns.iter().filter(|column| self.keeps(node, &column.name));
        Some(Columns::of_names(kept.map(|column| column.name.clone())))
    }

    /// The columns of the relation a clause of `node` derives: for a `DET`
    /// parameter node that an atom reads, as [`Builder::kept_columns`]
    /// gives them; for another clause, its labels in
    /// their canonical positions; or, with no columns of its own, its first
    /// proposer's, or the output's of an instance it stands for.
    fn clause_columns(&self, node: usize, clause: &Clause, scope: &NameScope, writer: &Writer<'_>) -> Option<Columns> {
        if let Some(kept) = self.kept_columns(node, clause) {
            return Some(kept);
        }
        if !clause.columns.is_empty() {
            return Some(canonical_columns(clause, writer));
        }
        if let Some(proposer) = clause.proposers.first() {
            return registry_columns::proposer_columns(self.registry, proposer).map(|names| Columns::of_names(names.into_vec()));
        }
        if let ProgramRelation::Output(OutputName { of: OutputOwner::Instance(name), path }) = &clause.derives {
            if let [OutputStep::Port(port)] = &path[..] {
                return self.instances.get(&(scope.clone(), name.clone())).and_then(|nodes| nodes.columns.get(port)).cloned();
            }
        }
        Some(Columns::default())
    }
}

/// The columns of `clause` in their canonical positions.
fn canonical_columns(clause: &Clause, writer: &Writer<'_>) -> Columns {
    let labeling = canonical_labeling(LabelScope::Clause(clause), writer, &mut SearchBudget::new());
    ordered(&clause.columns, &labeling)
}

/// `columns` in the order of their labels' positions in `labeling`.
fn ordered(columns: &[crate::program::RelationColumn], labeling: &crate::program::canonical::CanonicalLabeling) -> Columns {
    let position = |label| labeling.positions.iter().find(|(found, _)| *found == label).map(|(_, position)| *position);
    let mut ordered: Vec<(Option<u32>, &ColumnName)> = columns.iter().map(|column| (position(column.label), &column.name)).collect();
    ordered.sort_by_key(|(position, _)| *position);
    Columns::of_names(ordered.into_iter().map(|(_, name)| name.clone()))
}

/// The columns of a chosen relation: the row's, in the order of the
/// `for` clause, then the candidate's, in their canonical positions,
/// `docs/arclog/constraints.md#choose`.
fn choose_columns(choose: &Choose, writer: &Writer<'_>) -> Columns {
    let labeling = canonical_labeling(LabelScope::Choose(choose), writer, &mut SearchBudget::new());
    let rows = row_columns(choose).map(|column| column.name.clone());
    let candidate = ordered(&choose.candidate_columns, &labeling);
    Columns::of_names(rows.chain(candidate.names().cloned()))
}
