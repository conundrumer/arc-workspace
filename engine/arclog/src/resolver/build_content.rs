//! The content and the columns of each node of the graph: the resolved
//! content of each of its forms, with no order, and the
//! columns of its rows, with the position in them of each column that
//! each of its forms gives.

use std::sync::Arc;

use super::super::columns::{ColumnOrders, Columns, Place};
use super::super::form_columns::{form_columns, row_columns};
use super::super::registry_columns;
use super::super::names::{form_bytes, node_form, Own, Writer};
use super::Builder;
use crate::program::canonical::{canonical_labeling, LabelScope, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Choose, Clause, ColumnName, LabelId, NameScope, OutputName, OutputOwner, OutputStep, ProgramRelation};
use crate::resolver::{DependencyNode, Resolution};

impl Builder<'_> {
    /// The content and the columns of each node, each node after the
    /// nodes it reads, and a `DEMONSTRATED` form's node after the nodes its
    /// rules declare ([`Builder::rule_nodes`]), where no cycle holds it.
    /// The content of a node of a layered resolution that no read of the
    /// last form resolves to is left to [`ResolvedProgram::node_content`],
    /// which writes it on its first read: no pass of the resolution reads
    /// it, and it gives the bytes that writing it here would.
    pub(super) fn contents(&mut self) {
        let offset = self.offset();
        let count = self.nodes.len();
        let unread = self.unread_nodes();
        self.names.contents = vec![None; count];
        self.names.node_columns = vec![None; count];
        self.names.node_orders = vec![ColumnOrders::default(); count];
        self.names.unwritten = unread.iter().map(|unread| unread.then(std::sync::OnceLock::new)).collect();
        let mut visited = vec![false; count];
        for slot in 0..count {
            self.content_of(offset + slot, &mut visited, &unread);
        }
    }

    /// [`Builder::contents`] for a resolution of the program of `earlier`, an
    /// exact resolution of that program, that differs from it in the columns
    /// the reads of some `DET` nodes name ([`SolverScope::read_columns`]): the
    /// content, the columns, the kept columns and the key ranks of each node
    /// that the difference does not reach are those of `earlier`, and the
    /// others are written as `contents` writes them. `None` where the
    /// argument below cannot be applied, so no entry of this build is used.
    ///
    /// Why the result is `contents`'s. The passes that run before this one are
    /// the passes of `resolve`, so the nodes, their forms, the targets of each
    /// name and the reads of each form are those that `earlier` has for the
    /// same program, whatever the columns of the reads: they are checked for
    /// each node that is taken, by its kind, its scope and its forms. What
    /// `contents` writes for a node is a function of these:
    /// - the forms of the node, and of an `INIT` form the whole form, since
    ///   each node of the form is written from all of it;
    /// - for each name that those forms read and that resolves to a node, the
    ///   content, the columns and their orders of that node, and, for a field of
    ///   a key, the rank that the node's `INIT` form gave it, which is made from
    ///   the content of what that form reads;
    /// - the columns that the node keeps, which are decided by the columns its
    ///   reads name ([`Builder::keeps`]).
    /// A name that resolves to no node holds the same columns in both
    /// resolutions. So the entries of a node are the same where the columns it
    /// keeps are the same, and the entries of each node it depends on are the
    /// same. The nodes with other columns are the seeds, found by comparing the
    /// columns that each node's reads name with `earlier`'s, and the affected
    /// nodes are the seeds, each node that reads an affected node by a name or
    /// by an edge of the graph, from a form of its own, each node of a form
    /// that an affected node has, and, by this rule again, each node that
    /// depends on those, until no node is added. Each other node depends on
    /// no node that differs, by induction on the order in which `contents`
    /// writes the nodes: it writes each node after the nodes it reads, and the
    /// check in [`Builder::affected_nodes`] shows that each node a node depends
    /// on has a lower index, so the nodes are written by increasing index, and a
    /// node that is taken finds, in every node before it, the entries that
    /// `contents` would have written.
    pub(super) fn contents_reusing(&mut self, earlier: &crate::resolver::ResolvedProgram) -> Option<()> {
        let count = self.nodes.len();
        if count != earlier.graph.nodes.len() {
            return None;
        }
        let affected = self.affected_nodes(earlier)?;
        self.names.contents = vec![None; count];
        self.names.node_columns = vec![None; count];
        self.names.node_orders = vec![ColumnOrders::default(); count];
        self.names.unwritten = (0..count).map(|_| None).collect();
        let unread = vec![false; count];
        let mut visited = vec![false; count];
        for node in 0..count {
            if affected[node] {
                self.content_of(node, &mut visited, &unread);
            } else {
                visited[node] = true;
                self.take_content(node, earlier)?;
            }
        }
        Some(())
    }

    /// Whether each node of this build, a resolution of the whole program,
    /// reads a node whose columns differ from those of `earlier`, as
    /// [`Builder::contents_reusing`] says, or `None` where a node reads a node
    /// of a higher index, or the program holds a `DEMONSTRATED` form, whose
    /// content reads the content of the nodes of its rules, or a `RIGID_DET`
    /// form, whose content reads the content of an instance's output that none
    /// of its atoms resolves to.
    fn affected_nodes(&self, earlier: &crate::resolver::ResolvedProgram) -> Option<Vec<bool>> {
        let count = self.nodes.len();
        let unhandled = |node: &crate::resolver::DependencyNode| {
            matches!(node.kind, crate::resolver::DependencyKind::Demonstrated(_) | crate::resolver::DependencyKind::RigidAssembly(_))
        };
        if self.nodes.iter().any(unhandled) {
            return None;
        }
        let same = |old: Option<&[ColumnName]>, new: Option<&Vec<ColumnName>>| match (old, new) {
            (None, None) => true,
            (Some(old), Some(new)) => old.len() == new.len() && new.iter().all(|column| old.contains(column)),
            _ => false,
        };
        let mut affected = vec![false; count];
        let mut open = Vec::new();
        for node in 0..count {
            if !same(earlier.read_columns_of(crate::resolver::GraphNodeIndex(node as u32)), self.read_columns[node].as_ref()) {
                affected[node] = true;
                open.push(node);
            }
        }
        if open.is_empty() {
            return Some(affected);
        }
        // The nodes of each form, found by the form's first step, and the nodes that read each node.
        let mut of_form: crate::hash::StableHashMap<u32, Vec<(&NodePath, Vec<usize>)>> = crate::hash::StableHashMap::default();
        for (node, forms) in self.forms.iter().enumerate() {
            for form in forms {
                let Some(top) = form.0.first() else { continue };
                let held = of_form.entry(top.0).or_default();
                match held.iter_mut().find(|(path, _)| *path == form) {
                    Some((_, nodes)) => nodes.push(node),
                    None => held.push((form, vec![node])),
                }
            }
        }
        let mut readers: Vec<Vec<usize>> = vec![Vec::new(); count];
        for atom in &self.atoms {
            let Some(Resolution::Node(read)) = self.resolutions.get(&atom.path) else { continue };
            let Some(top) = atom.path.0.first() else { continue };
            for (_, nodes) in of_form.get(&top.0).into_iter().flatten().filter(|(form, _)| atom.path.0.starts_with(&form.0)) {
                for &node in nodes {
                    if read.0 as usize > node {
                        return None;
                    }
                    readers[read.0 as usize].push(node);
                }
            }
        }
        for (node, reads) in self.reads.iter().enumerate() {
            for &read in reads {
                if read as usize > node {
                    return None;
                }
                readers[read as usize].push(node);
            }
        }
        while let Some(node) = open.pop() {
            let same_form = self.forms[node].iter().filter_map(|form| of_form.get(&form.0.first()?.0)?.iter().find(|(path, _)| *path == form)).flat_map(|(_, nodes)| nodes);
            for &other in readers[node].iter().chain(same_form) {
                if !std::mem::replace(&mut affected[other], true) {
                    open.push(other);
                }
            }
        }
        Some(affected)
    }

    /// Records the entries that [`Builder::content_of`] records for `node`,
    /// as `earlier` holds them, where the node is one that
    /// [`Builder::contents_reusing`] takes. `None` where `earlier` holds none
    /// of them or a different node.
    fn take_content(&mut self, node: usize, earlier: &crate::resolver::ResolvedProgram) -> Option<()> {
        let index = crate::resolver::GraphNodeIndex(node as u32);
        if earlier.graph.nodes[node] != self.nodes[node] || earlier.forms_of(index) != &self.forms[node][..] {
            return None;
        }
        for path in &self.forms[node] {
            if let Some(columns) = earlier.names.kept_at(path) {
                self.names.kept.insert(path.clone(), columns.clone());
            }
        }
        let scope = self.nodes[node].scope.clone();
        for path in &self.forms[node] {
            let Some(NodeRef::Instance(instance)) = node_at(NodeRef::Program(self.case.value()), path) else { continue };
            if instance.key.is_none() || self.names.key_ranks.get(&scope).is_some_and(|ranks| ranks.contains_key(&instance.name)) {
                continue;
            }
            let ranks = earlier.names.key_ranks_in(&scope, &instance.name)?;
            let own = earlier.names.own_key_ranks_in(&scope, &instance.name)?;
            self.names.own_key_ranks.entry(scope.clone()).or_default().insert(instance.name.clone(), own.into());
            self.names.key_ranks.entry(scope.clone()).or_default().insert(instance.name.clone(), ranks.into());
        }
        let content = earlier.written_content(node)?.cloned();
        let columns = earlier.names.node_columns_of(node).cloned();
        if let Some(columns) = &columns {
            self.label_positions(node, columns);
        }
        self.names.contents[node] = content;
        self.names.node_orders[node] = earlier.names.node_orders_of(node).into();
        self.names.node_columns[node] = columns;
        Some(())
    }

    /// Whether no read of the last form resolves to each node of this build, in
    /// the order of its nodes, for a node of a layered resolution of one form,
    /// and `false` for every node of another resolution. A node that only another node reads in the
    /// dependency graph counts as unread, as a write of a content reads no
    /// other node's content, apart from that of a `DEMONSTRATED` form,
    /// which reads the content of each node its rules declare
    /// ([`Builder::rule_nodes`]); such a node counts as read.
    fn unread_nodes(&self) -> Vec<bool> {
        let mut unread = vec![self.earlier.is_some(); self.nodes.len()];
        for resolution in self.resolutions.values() {
            if let Resolution::Node(node) = resolution {
                if let Some(slot) = self.slot(node.0 as usize) {
                    unread[slot] = false;
                }
            }
        }
        for (slot, forms) in self.forms.iter().enumerate() {
            unread[slot] &= forms.len() == 1;
        }
        for (slot, unread) in unread.iter_mut().enumerate() {
            *unread &= !matches!(self.nodes[slot].scope, NameScope::DemoRule(_));
        }
        unread
    }

    /// The nodes that the rules of the `DEMONSTRATED` form of `node`
    /// declare, none where `node` is the node of no such form. The form's
    /// content writes each of them by its content, whether or not a node
    /// reads it.
    fn rule_nodes(&self, node: usize) -> Vec<u32> {
        let local = node - self.offset;
        let DependencyNode { kind: crate::resolver::DependencyKind::Demonstrated(_), .. } = &self.nodes[local] else { return Vec::new() };
        let forms = &self.forms[local];
        let in_form = |scope: &NameScope| matches!(scope, NameScope::DemoRule(rule) if forms.iter().any(|form| rule.0.starts_with(&form.0)));
        // The rules of a form stand in the form's path, so no node of an earlier form's resolution is one of them.
        (0..self.nodes.len()).filter(|&other| in_form(&self.nodes[other].scope)).map(|other| (self.offset + other) as u32).collect()
    }

    /// Writes the content and the columns of `node`, a node of this build,
    /// after those of the nodes it reads; `visited` holds, by the position of
    /// each node of this build, whether it was reached. A node of the earlier
    /// forms' resolution holds its content already.
    fn content_of(&mut self, node: usize, visited: &mut Vec<bool>, unread: &[bool]) {
        let Some(local) = self.slot(node) else { return };
        if std::mem::replace(&mut visited[local], true) {
            return;
        }
        let mut reads: Vec<u32> = self.reads[local].iter().copied().collect();
        reads.extend(self.rule_nodes(node));
        for read in reads {
            self.content_of(read as usize, visited, unread);
        }
        self.record_kept(node);
        self.rank_keys(node);
        let (content, columns) = if unread[local] {
            (None, self.node_columns(node))
        } else {
            let (content, columns) = self.node_content(node);
            (Some(content), columns)
        };
        if let Some((columns, _)) = &columns {
            self.label_positions(node, columns);
        }
        self.pick_ranks(node);
        let (columns, orders) = columns.unzip();
        self.names.contents[local] = content;
        self.names.node_columns[local] = columns;
        self.names.node_orders[local] = orders.unwrap_or_default();
    }

    /// Records in [`super::super::names::Names::key_ranks`] the rank of each
    /// field of the `key` record of each `INIT` form of `node` that has a key
    /// clause, once for the form. The labeling of the form writes the
    /// relations its key reads by their content, which the nodes that
    /// `node` reads have, and writes its own outputs by their written
    /// names, so a form whose inputs read its own outputs needs no content
    /// of its own.
    fn rank_keys(&mut self, node: usize) {
        let scope = self.nodes[node - self.offset].scope.clone();
        let mut ranked = Vec::new();
        for path in &self.forms[node - self.offset] {
            let Some(NodeRef::Instance(instance)) = node_at(NodeRef::Program(self.case.value()), path) else { continue };
            let Some(key) = &instance.key else { continue };
            if self.names.key_ranks.get(&scope).is_some_and(|ranks| ranks.contains_key(&instance.name)) {
                continue;
            }
            let own = Own::of(NodeRef::Instance(instance));
            let ranks_in = |labeling: &crate::program::canonical::CanonicalLabeling| -> Box<[(ColumnName, u32)]> {
                let rank = |label| labeling.positions.iter().find(|(found, _)| *found == label).map_or(u32::MAX, |(_, position)| *position);
                key.value().key.columns.iter().map(|column| (column.name.clone(), rank(column.label))).collect()
            };
            // The labeling of the form writes its reads of its own outputs, whose `key` fields take their ranks
            // in the labeling of the key's body.
            let body = {
                let writer = Writer { names: &self.names, scope: &scope, own: own.as_ref() };
                ranks_in(&canonical_labeling(LabelScope::Body(key.value().key.body.value()), &writer, &mut SearchBudget::new()))
            };
            self.names.own_key_ranks.entry(scope.clone()).or_default().insert(instance.name.clone(), body);
            let writer = Writer { names: &self.names, scope: &scope, own: own.as_ref() };
            let labeling = canonical_labeling(LabelScope::Instance(instance), &writer, &mut SearchBudget::new());
            ranked.push((instance.name.clone(), ranks_in(&labeling)));
        }
        for (name, ranks) in ranked {
            self.names.key_ranks.entry(scope.clone()).or_default().insert(name, ranks);
        }
    }

    /// Records in `label_ranks` the rank of each column label of each form of
    /// `node`, a chosen relation's node, in the canonical labeling of the
    /// form, which writes each relation the form reads by its content and each
    /// column by its place, so that the ranks are the same where a file names
    /// the labels and where a decode names them by slots. A form of another
    /// kind of node has none.
    fn pick_ranks(&mut self, node: usize) {
        let local = node - self.offset;
        if !matches!(self.nodes[local].kind, crate::resolver::DependencyKind::Chosen(_)) {
            return;
        }
        let scope = self.nodes[local].scope.clone();
        let mut found = Vec::new();
        for path in &self.forms[local] {
            let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
            let scope_of = match form {
                NodeRef::Choose(choose) => LabelScope::Choose(choose),
                NodeRef::Clause(clause) => LabelScope::Clause(clause),
                _ => continue,
            };
            let own = Own::of(form);
            let writer = Writer { names: &self.names, scope: &scope, own: own.as_ref() };
            let labeling = canonical_labeling(scope_of, &writer, &mut SearchBudget::new());
            for column in form_columns(form) {
                if let Some(rank) = position(&labeling.positions, column.label) {
                    found.push(((path.clone(), column.label), rank));
                }
            }
        }
        self.label_ranks.extend(found);
    }

    /// Records the position in `columns`, the rows of `node`, of each
    /// column that each form of the node gives, by the form's path and the
    /// column's label: each column takes the position of the node's column
    /// of its name.
    fn label_positions(&mut self, node: usize, columns: &Columns) {
        for path in &self.forms[node - self.offset] {
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
    /// come from its form, with their orders where the node has one form.
    fn node_content(&self, node: usize) -> (crate::program::canonical::CanonicalForm, Option<(Columns, ColumnOrders)>) {
        let DependencyNode { kind, scope } = &self.nodes[node - self.offset];
        let mut parts: Vec<(Arc<[u8]>, Option<(Columns, ColumnOrders)>)> = Vec::new();
        for path in &self.forms[node - self.offset] {
            parts.push((form_bytes(&self.names, self.case.value(), scope, path), self.form_columns(node, path)));
        }
        parts.sort_by(|a, b| a.0.cmp(&b.0));
        let mut columns = parts.iter().find_map(|(_, columns)| columns.clone());
        // An order of one form's columns under which its content is the same need not be one of the node's.
        if parts.len() > 1 {
            columns = columns.map(|(columns, _)| (columns, ColumnOrders::default()));
        }
        (node_form(kind, parts.into_iter().map(|(bytes, _)| bytes)), columns)
    }

    /// The columns of `node`, a node of one form, as [`Builder::node_content`]
    /// gives them.
    fn node_columns(&self, node: usize) -> Option<(Columns, ColumnOrders)> {
        self.form_columns(node, &self.forms[node - self.offset][0])
    }

    /// The columns of the relation the form of `node` at `path` gives, with
    /// their orders under which the form's content is the same.
    fn form_columns(&self, node: usize, path: &NodePath) -> Option<(Columns, ColumnOrders)> {
        let scope = &self.nodes[node - self.offset].scope;
        let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
        let own = Own::of(form);
        let writer = Writer { names: &self.names, scope, own: own.as_ref() };
        match form {
            NodeRef::Clause(clause) => match self.concept_columns.get(path) {
                Some(columns) => columns.clone().map(|columns| (columns, ColumnOrders::default())),
                None => self.clause_columns(node, clause, scope, &writer),
            },
            NodeRef::Choose(choose) => Some((choose_columns(choose, &writer), ColumnOrders::default())),
            NodeRef::Out(out) => Some((Columns::of_names(out.key.columns.iter().map(|column| column.name.clone())), ColumnOrders::default())),
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
        let scope = &self.nodes[node - self.offset].scope;
        for path in &self.forms[node - self.offset] {
            if self.concept_columns.contains_key(path) {
                continue;
            }
            let Some(NodeRef::Clause(clause)) = node_at(NodeRef::Program(self.case.value()), path) else { continue };
            if let Some(columns) = self.kept_columns(node, clause) {
                let own = Own::of(NodeRef::Clause(clause));
                let writer = Writer { names: &self.names, scope, own: own.as_ref() };
                let (canonical, _) = canonical_columns(clause, &writer);
                let columns = self.in_kept_order(columns, &canonical);
                if !columns.names().eq(canonical.names()) {
                    // `kept` only enters a form's content, which holds each
                    // column by its canonical position, not by its name,
                    // since a decode names the columns by slots.
                    let positions = columns.names().map(|name| ColumnName::Slot(canonical.names().position(|other| other == name).map_or(u32::MAX, |position| position as u32)));
                    kept.push((path.clone(), Columns::of_names(positions)));
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
        if clause.columns.is_empty() || self.read_columns[node - self.offset].is_none() {
            return None;
        }
        let kept = clause.columns.iter().filter(|column| self.keeps(node, &column.name));
        Some(Columns::of_names(kept.map(|column| column.name.clone())))
    }

    /// `kept`, the columns a clause keeps in the order it writes them, in the
    /// order of `canonical`, the clause's columns in their canonical positions,
    /// where the content is to be free of the order the clause writes them.
    fn in_kept_order(&self, kept: Columns, canonical: &Columns) -> Columns {
        if !self.canonical_kept {
            return kept;
        }
        Columns::of_names(canonical.names().filter(|name| kept.names().any(|other| other == *name)).cloned())
    }

    /// The columns of the relation a clause of `node` derives: for a `DET`
    /// parameter node that an atom reads, as [`Builder::kept_columns`]
    /// gives them; for another clause, its labels in
    /// their canonical positions, with their orders under which the
    /// clause's content is the same; or, with no columns of its own, its
    /// first proposer's, or the output's of an instance it stands for.
    fn clause_columns(&self, node: usize, clause: &Clause, scope: &NameScope, writer: &Writer<'_>) -> Option<(Columns, ColumnOrders)> {
        let unordered = |columns: Columns| (columns, ColumnOrders::default());
        if let Some(kept) = self.kept_columns(node, clause) {
            let kept = if self.canonical_kept { self.in_kept_order(kept, &canonical_columns(clause, writer).0) } else { kept };
            return Some(unordered(kept));
        }
        if !clause.columns.is_empty() {
            return Some(canonical_columns(clause, writer));
        }
        if let Some(proposer) = clause.proposers.first() {
            return registry_columns::proposer_columns(self.registry, proposer).map(|names| unordered(Columns::of_names(names.into_vec())));
        }
        if let ProgramRelation::Output(OutputName { of: OutputOwner::Instance(name), path }) = &clause.derives {
            if let [OutputStep::Port(port)] = &path[..] {
                return self.instances.get(&(scope.clone(), name.clone())).and_then(|nodes| nodes.columns.get(port)).cloned().map(unordered);
            }
        }
        Some(unordered(Columns::default()))
    }
}

/// The columns of `clause` in their canonical positions, and their other
/// orders under which the clause's content is the same: those that each
/// other labeling of the clause whose form is the canonical form gives.
fn canonical_columns(clause: &Clause, writer: &Writer<'_>) -> (Columns, ColumnOrders) {
    let labeling = canonical_labeling(LabelScope::Clause(clause), writer, &mut SearchBudget::new());
    let rows = ranks(&clause.columns, &labeling.positions);
    let mut orders: Vec<Box<[u16]>> = Vec::new();
    for other in labeling.others.iter() {
        let mut order = vec![0; rows.len()].into_boxed_slice();
        for (row, rank) in rows.iter().zip(ranks(&clause.columns, other)) {
            order[usize::from(*row)] = rank;
        }
        let moved = order.iter().enumerate().any(|(position, other)| usize::from(*other) != position);
        if moved && !orders.contains(&order) {
            orders.push(order);
        }
    }
    (ordered(&clause.columns, &labeling.positions), orders.into())
}

/// `columns` in the order of their labels' positions in `positions`.
fn ordered(columns: &[crate::program::RelationColumn], positions: &[(LabelId, u32)]) -> Columns {
    let mut ordered: Vec<(Option<u32>, &ColumnName)> = columns.iter().map(|column| (position(positions, column.label), &column.name)).collect();
    ordered.sort_by_key(|(position, _)| *position);
    Columns::of_names(ordered.into_iter().map(|(_, name)| name.clone()))
}

/// The position of each of `columns` in the order [`ordered`] gives them.
fn ranks(columns: &[crate::program::RelationColumn], positions: &[(LabelId, u32)]) -> Vec<u16> {
    let mut order: Vec<usize> = (0..columns.len()).collect();
    order.sort_by_key(|&index| position(positions, columns[index].label));
    let mut ranks = vec![0; columns.len()];
    for (rank, index) in order.into_iter().enumerate() {
        ranks[index] = rank as u16;
    }
    ranks
}

/// The position of `label` in `positions`.
fn position(positions: &[(LabelId, u32)], label: LabelId) -> Option<u32> {
    positions.iter().find(|(found, _)| *found == label).map(|(_, position)| *position)
}

/// The columns of a chosen relation: the row's, in the order of the
/// `for` clause, then the candidate's, in their canonical positions,
/// `docs/arclog/constraints.md#choose`.
fn choose_columns(choose: &Choose, writer: &Writer<'_>) -> Columns {
    let labeling = canonical_labeling(LabelScope::Choose(choose), writer, &mut SearchBudget::new());
    let rows = row_columns(choose).map(|column| column.name.clone());
    let candidate = ordered(&choose.candidate_columns, &labeling.positions);
    Columns::of_names(rows.chain(candidate.names().cloned()))
}
