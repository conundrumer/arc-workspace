//! The content and the columns of each node of the graph: the resolved
//! content of each of its forms, with no order, and the
//! columns of its rows, with the position in them of each column that
//! each of its forms gives.

use std::sync::Arc;

use super::super::columns::{Columns, Place};
use super::super::form_columns::{form_columns, row_columns};
use super::super::registry_columns;
use super::super::names::{combined, Own, Writer};
use super::Builder;
use crate::program::canonical::{canonical_labeling, AsWritten, CanonicalWriter, LabelScope, NameWriter, SearchBudget};
use crate::program::path::{node_at, NodeRef};
use crate::program::{Choose, Clause, ColumnName, NameScope, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef};
use crate::resolver::{DependencyKind, DependencyNode};

impl Builder<'_> {
    /// The content and the columns of each node, each node after the
    /// nodes it reads, where no cycle holds it.
    pub(super) fn contents(&mut self) {
        let offset = self.offset();
        self.names.contents = vec![None; self.nodes.len() - offset];
        self.names.node_columns = vec![None; self.nodes.len() - offset];
        let mut visited = vec![false; self.nodes.len()];
        visited[..offset].fill(true);
        for node in offset..self.nodes.len() {
            self.content_of(node, &mut visited);
        }
    }

    fn content_of(&mut self, node: usize, visited: &mut Vec<bool>) {
        if std::mem::replace(&mut visited[node], true) {
            return;
        }
        let reads: Vec<u32> = self.reads[node].iter().copied().collect();
        for read in reads {
            self.content_of(read as usize, visited);
        }
        self.record_kept(node);
        let (content, columns) = self.node_content(node);
        if let Some(columns) = &columns {
            self.label_positions(node, columns);
        }
        let local = node - self.offset();
        self.names.contents[local] = Some(content);
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
        let mut tail = CanonicalWriter::default();
        match kind {
            DependencyKind::Fact(fact) => AsWritten.write_name(&RelationRef::Fact(*fact), &mut tail),
            DependencyKind::InstanceInput { input: port, .. } | DependencyKind::InstanceOutput { output: port, .. } => {
                tail.port_step(port)
            }
            _ => {}
        }
        let tail = tail.finish().bytes;
        let mut parts: Vec<(Arc<[u8]>, Option<Columns>)> = Vec::new();
        for path in &self.forms[node] {
            let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
            let own = Own::of(form);
            let writer = Writer { names: &self.names, scope, own: own.as_ref() };
            let bytes = self.names.form_content(self.case.value(), form, path, None, &writer).expect("a form has a canonical form").bytes;
            let columns = match form {
                NodeRef::Clause(clause) => match self.concept_columns.get(path) {
                    Some(columns) => columns.clone(),
                    None => self.clause_columns(node, clause, scope, &writer),
                },
                NodeRef::Choose(choose) => Some(choose_columns(choose, &writer)),
                _ => None,
            };
            parts.push((bytes, columns));
        }
        parts.sort_by(|a, b| a.0.cmp(&b.0));
        let columns = parts.iter().find_map(|(_, columns)| columns.clone());
        (combined(kind_tag(kind), parts.into_iter().map(|(bytes, _)| bytes), &tail), columns)
    }

    /// Records in [`super::super::names::Names::kept`] the columns that the
    /// relation of each clause of `node` keeps, as [`Builder::kept_columns`]
    /// gives them, where they are fewer than the clause gives and the
    /// clause does not resolve in the concept program.
    fn record_kept(&mut self, node: usize) {
        let mut kept = Vec::new();
        for path in &self.forms[node] {
            if self.concept_columns.contains_key(path) {
                continue;
            }
            let Some(NodeRef::Clause(clause)) = node_at(NodeRef::Program(self.case.value()), path) else { continue };
            if let Some(columns) = self.kept_columns(node, clause) {
                if columns.names().count() < clause.columns.len() {
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
            let labeling = canonical_labeling(LabelScope::Clause(clause), writer, &mut SearchBudget::new());
            return Some(ordered(&clause.columns, &labeling));
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

/// The tag of each kind of node in its content.
fn kind_tag(kind: &DependencyKind) -> u8 {
    match kind {
        DependencyKind::Fact(_) => 1,
        DependencyKind::Clause(_) => 2,
        DependencyKind::InstanceInput { .. } => 3,
        DependencyKind::InstanceOutput { .. } => 4,
        DependencyKind::Parameter(_) => 5,
        DependencyKind::Chosen(_) => 6,
        DependencyKind::RigidAssembly(_) => 7,
        DependencyKind::Demonstrated(_) => 8,
        DependencyKind::RecursiveInstance(_) => 9,
    }
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
