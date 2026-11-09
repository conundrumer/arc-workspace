//! The placement of each site of each atom read, the signature of each
//! name read, the stored column of each proposer's column, and the
//! assembly of the resolved program from the builder's state.

use super::super::columns::{Columns, Place};
use super::super::registry_columns;
use super::super::names::write_output_path;
use super::sides::lifted;
use super::{AtomRead, Builder};
use crate::diagnostic::WithDiagnostics;
use crate::hash::StableHashMap;
use crate::program::canonical::{AsWritten, CanonicalWriter, NameWriter};
use crate::program::path::{node_at, NodePath};
use crate::program::{Atom, Body, ColumnName, Conjunct, FactRelation, LabelUse, Program, RelationRef, SiteArg};
use crate::program::path::NodeRef;
use crate::resolver::columns;
use super::super::names::Names;
use crate::resolver::{ConceptForms, DependencyGraph, GraphNodeIndex, NodeList, ResolvedProgram, Resolution, Signature};
use std::sync::Arc;

impl Builder<'_> {
    /// The position and the group of each site of each atom read, and
    /// the signature of each name read.
    pub(super) fn sites(&mut self) {
        let atoms = std::mem::take(&mut self.atoms);
        for AtomRead { path, atom, scope, form } in &atoms {
            let lifts = self.lifts(form, &self.resolutions[path]);
            if lifts {
                self.lifted.insert(path.clone());
                if binds_train_examples(self.case.value(), path, atom) {
                    self.train_lifted.insert(path.clone());
                }
            }
            let found = self.names.columns(scope, &atom.relation);
            let lifted = found.filter(|_| lifts).map(Columns::lifted);
            let columns = if lifts { lifted.as_ref() } else { found };
            if let Some(columns) = columns {
                for (index, site) in atom.sites.iter().enumerate() {
                    place_site(&mut self.positions, &mut self.groups, columns, site, path.child(index as u32));
                }
            }
            if self.signed {
                let signature = signature(&self.names, &self.resolutions[path], &atom.relation, columns);
                self.signatures.insert(path.clone(), signature);
            }
        }
    }

    /// Whether the form at `form` reads, in its lifted form
    /// (`docs/arclog/arclog.md#program`), the relation a read that resolves
    /// to `resolution` reads.
    fn lifts(&self, form: &NodePath, resolution: &Resolution) -> bool {
        let Resolution::Node(read) = resolution else { return false };
        lifted(self.is_fact(*read), self.form_sides[form], self.side_of(read.0 as usize))
    }
    /// The stored parameter's column that each column of each proposer
    /// of each clause stands for, by position: the clause's columns in
    /// the order it gives them, or, with none, its first proposer's.
    pub(super) fn proposers(&mut self) {
        for (path, clause) in std::mem::take(&mut self.clauses) {
            let first = clause.proposers.first().and_then(|proposer| registry_columns::proposer_columns(self.registry, proposer));
            let stored: Box<[ColumnName]> = if clause.columns.is_empty() {
                first.unwrap_or_default()
            } else {
                clause.columns.iter().map(|column| column.name.clone()).collect()
            };
            for (index, proposer) in clause.proposers.iter().enumerate() {
                if let Some(own) = registry_columns::proposer_columns(self.registry, proposer) {
                    let mapped = own.iter().zip(stored.iter()).map(|(_, name)| name.clone()).collect();
                    self.proposer_columns.insert((path.clone(), index), mapped);
                }
            }
        }
    }

    /// The resolved program of this build. A layered build gives a graph that
    /// shares the graph of `earlier`, and the entries of its own nodes alone.
    pub(super) fn finish(mut self, concept: Option<ConceptForms>) -> WithDiagnostics<ResolvedProgram> {
        let offset = self.offset();
        let reads: Vec<Box<[GraphNodeIndex]>> = self.reads.drain(..).map(|reads| reads.into_iter().map(GraphNodeIndex).collect()).collect();
        let graph = match &self.earlier {
            Some(earlier) => DependencyGraph::over(&earlier.graph, self.nodes, reads),
            None => DependencyGraph { nodes: Arc::new(NodeList::new(self.nodes)), reads: Arc::new(NodeList::new(reads)) },
        };
        let sides = self.sides;
        let examples = self.examples;
        let read_columns = self.read_columns;
        let mut form_nodes: StableHashMap<NodePath, Vec<GraphNodeIndex>> = StableHashMap::default();
        for (node, forms) in self.forms.iter().enumerate() {
            for form in forms {
                form_nodes.entry(form.clone()).or_default().push(GraphNodeIndex((node + offset) as u32));
            }
        }
        let form_nodes = form_nodes.into_iter().map(|(form, nodes)| (form, Box::from(nodes))).collect();
        let forms = self.forms.into_iter().map(Box::from).collect();
        WithDiagnostics {
            value: ResolvedProgram {
                program: self.case.clone(),
                graph,
                forms,
                form_nodes,
                sides: sides.into(),
                form_sides: self.form_sides,
                examples: examples.into(),
                read_columns: read_columns.into(),
                widened: Default::default(),
                output_examples: self.output_examples,
                resolutions: self.resolutions,
                signatures: self.signatures,
                positions: self.positions,
                label_positions: self.label_positions,
                label_ranks: self.label_ranks,
                groups: self.groups,
                proposer_columns: self.proposer_columns,
                lifted: self.lifted,
                train_lifted: self.train_lifted,
                names: self.names,
                concept,
                depths: Default::default(),
                node_index: Default::default(),
            },
            diagnostics: self.diagnostics,
        }
    }
}

/// The signature of a read of `relation` that resolves to `resolution`:
/// the content of what it resolves to, and its columns.
pub(super) fn signature(names: &Names, resolution: &Resolution, relation: &RelationRef, columns: Option<&Columns>) -> Signature {
    let mut out = CanonicalWriter::default();
    match resolution {
        Resolution::Node(node) => {
            out.write(&[0]);
            let content = names.node_content(node.0 as usize).flatten().expect("the content of each node");
            out.write(&content.hash.0.to_le_bytes());
            write_output_path(&mut out, relation);
        }
        Resolution::Lib(_) => out.write(&[1]),
        Resolution::Undefined(_) => out.write(&[2]),
        Resolution::Unresolved => out.write(&[3]),
    }
    if !matches!(resolution, Resolution::Node(_)) {
        AsWritten.write_name(relation, &mut out);
    }
    match columns {
        Some(columns) => {
            out.write(&[1]);
            columns.write(&mut out);
        }
        None => out.write(&[0]),
    }
    Signature(out.finish())
}

/// Records in `positions` and `groups` where the site at `path` stands in `columns`.
fn place_site(positions: &mut StableHashMap<NodePath, crate::resolver::ColumnPosition>, groups: &mut StableHashMap<NodePath, crate::relations::ColumnGroup>, columns: &Columns, site: &crate::program::Site, path: NodePath) {
    use crate::program::SiteArg;
    match columns.place(std::slice::from_ref(&site.column)) {
        Some(Place::Column(position)) => {
            for (index, arg) in site.value.args.iter().enumerate() {
                if let SiteArg::NamedLabel { .. } = arg {
                    positions.insert(path.child(index as u32), position);
                }
            }
            positions.insert(path, position);
        }
        Some(Place::Group(group)) => {
            for (index, arg) in site.value.args.iter().enumerate() {
                let field = match arg {
                    SiteArg::NamedLabel { name, .. } => name,
                    SiteArg::Field(field) => &field.column,
                    SiteArg::Label(_) => continue,
                };
                if let Some(Place::Field(position, _)) = columns.place(&[site.column.clone(), field.clone()]) {
                    positions.insert(path.child(index as u32), position);
                }
            }
            groups.insert(path, group);
        }
        Some(Place::Field(..)) | None => {}
    }
}

/// Whether the lifted read `atom` at `path` of `program` has a site on the
/// Example column that holds a label which a positive `ex_output` atom binds,
/// in the read's own conjunction or in the guard of the `ALL` form the read
/// stands in.
fn binds_train_examples(program: &Program, path: &NodePath, atom: &Atom) -> bool {
    let example = columns::example();
    let label_of = |atom: &Atom| {
        let site = atom.sites.iter().find(|site| site.column == example)?;
        match &site.value.args[..] {
            [SiteArg::Label(LabelUse::Fresh(id) | LabelUse::Join(id))] => Some(*id),
            _ => None,
        }
    };
    let Some(label) = label_of(atom) else { return false };
    let binds = |body: &Body| {
        body.conjuncts.iter().any(|conjunct| match conjunct {
            Conjunct::Atom(other) => other.value().relation == RelationRef::Fact(FactRelation::ExOutput) && label_of(other.value()) == Some(label),
            _ => false,
        })
    };
    let root = NodeRef::Program(program);
    let Some((body_at, _)) = path.0.split_last().map(|(_, rest)| (NodePath(rest.into()), ())) else { return false };
    let Some(NodeRef::Body(body)) = node_at(root, &body_at) else { return false };
    if binds(body) {
        return true;
    }
    let Some((all_at, _)) = body_at.0.split_last().map(|(_, rest)| (NodePath(rest.into()), ())) else { return false };
    match node_at(root, &all_at) {
        Some(NodeRef::Conjunct(Conjunct::All { domain, body: inner })) => std::ptr::eq(inner.value(), body) && binds(domain.value()),
        _ => false,
    }
}
