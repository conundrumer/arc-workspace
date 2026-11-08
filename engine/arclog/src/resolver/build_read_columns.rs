//! The columns that the reads of a `DET` decide: the labels of its clause
//! that a site of a read of its relation names, together with each label
//! one of its `ONE` marks names, and the check of a column of a clause
//! against them (`docs/arclog/arclog.md#sites`).

use super::Builder;
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodeRef};
use crate::program::{Clause, ClauseKeyword, ColumnName, ProgramRelation};
use crate::resolver::{add_columns, DependencyKind, GraphNodeIndex, Resolution};

/// A node whose relation has the columns that its reads name: the relation,
/// and the columns that its `ONE` marks name, which its relation keeps
/// whether or not a read names them.
pub(super) struct ReadNamed {
    pub(super) relation: ProgramRelation,
    marked: Vec<ColumnName>,
}

/// What `kind` gives for the read-named rule: a `DET` parameter, and a
/// chosen relation that a clause with the keyword `DET` gives, whose marks
/// are those of such clauses among `clauses`; `None` for every other node.
fn read_named<'c>(kind: &DependencyKind, clauses: impl Iterator<Item = &'c Clause>) -> Option<ReadNamed> {
    match kind {
        DependencyKind::Parameter(relation) => Some(ReadNamed { relation: relation.clone(), marked: Vec::new() }),
        DependencyKind::Chosen(name) => {
            let mut dets = clauses.filter(|clause| clause.keyword == ClauseKeyword::Det).peekable();
            dets.peek()?;
            let mut marked = Vec::new();
            for clause in dets {
                let labels = clause.ones.iter().flat_map(|mark| mark.key.iter());
                let names: Vec<&ColumnName> = labels.filter_map(|label| clause.columns.iter().find(|column| column.label == *label)).map(|column| &column.name).collect();
                add_columns(&mut marked, names);
            }
            Some(ReadNamed { relation: ProgramRelation::Declared(name.clone()), marked })
        }
        _ => None,
    }
}

impl Builder<'_> {
    /// What `node` gives for the read-named rule, as [`read_named`] gives
    /// it, over the forms of the node, a node of the earlier forms of a
    /// layered resolution included.
    pub(super) fn read_named(&self, node: usize) -> Option<ReadNamed> {
        let kind = &self.node_def(node).kind;
        if !matches!(kind, DependencyKind::Parameter(_) | DependencyKind::Chosen(_)) {
            return None;
        }
        let (program, forms) = match &self.earlier {
            Some(earlier) if node < self.offset() => (earlier.program.value(), earlier.forms_of(GraphNodeIndex(node as u32))),
            _ => (self.case.value(), self.forms_at(node)),
        };
        let root = NodeRef::Program(program);
        let clauses = forms.iter().filter_map(|form| match node_at(root, form) {
            Some(NodeRef::Clause(clause)) => Some(clause),
            _ => None,
        });
        read_named(kind, clauses)
    }

    /// The column names that the sites of the reads of each read-named node
    /// name, and the columns that its marks name: the reads of the case,
    /// then the reads across the solver's cases that
    /// [`SolverScope::read_columns`] gives.
    pub(super) fn read_columns(&mut self) {
        let nodes_read_named: Vec<Option<ReadNamed>> = (self.offset()..self.node_count()).map(|node| self.read_named(node)).collect();
        let mut named: Vec<Option<Vec<ColumnName>>> = vec![None; self.nodes.len()];
        let mut earlier_read_named: StableHashMap<usize, bool> = StableHashMap::default();
        for read in &self.atoms {
            let Resolution::Node(node) = self.resolutions[&read.path] else { continue };
            let read_named = match self.slot(node.0 as usize) {
                Some(slot) => nodes_read_named[slot].is_some(),
                None => *earlier_read_named.entry(node.0 as usize).or_insert_with(|| self.read_named(node.0 as usize).is_some()),
            };
            if read_named {
                if let Some(earlier) = self.earlier.as_ref().filter(|_| (node.0 as usize) < self.offset()) {
                    let held = earlier.read_columns_of(node);
                    let extra: Vec<ColumnName> = read.atom.sites.iter().map(|site| site.column.clone()).filter(|column| !held.is_some_and(|names| names.contains(column))).collect();
                    if !extra.is_empty() {
                        match self.widenings.iter_mut().find(|(widened, _)| *widened == node) {
                            Some((_, columns)) => add_columns(columns, &extra),
                            None => self.widenings.push((node, extra)),
                        }
                    }
                    continue;
                }
                let names = named[node.0 as usize - self.offset()].get_or_insert_with(Vec::new);
                add_columns(names, read.atom.sites.iter().map(|site| &site.column));
            }
        }
        for (index, found) in nodes_read_named.iter().enumerate() {
            let Some(found) = found else { continue };
            if let Some(columns) = self.solver_reads.get(&found.relation) {
                add_columns(named[index].get_or_insert_with(Vec::new), columns);
            }
            if let Some(names) = &mut named[index] {
                add_columns(names, &found.marked);
            }
        }
        self.read_columns = named;
    }

    /// Whether the relation of `node` keeps the column `column` of its
    /// clause: a column of a read-named node that an atom reads is kept
    /// where a site of a read of the relation names it, or a mark of the
    /// clause does, and every column of every other node is kept, those of
    /// a node of the earlier forms included.
    pub(super) fn keeps(&self, node: usize, column: &ColumnName) -> bool {
        self.slot(node).and_then(|slot| self.read_columns[slot].as_ref()).is_none_or(|names| names.contains(column))
    }
}
