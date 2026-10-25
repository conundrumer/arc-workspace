//! The retarget of a layered resolution from one lib atom to another: the
//! entries that the relation of an atom of no site gives, rewritten in
//! place.

use super::sites::signature;
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::{Atom, Form, NameScope, Node, Program, RelationRef};
use crate::registry::Registry;
use super::super::registry_columns;
use crate::resolver::{Resolution, ResolvedProgram};

impl ResolvedProgram {
    /// Retargets this resolution, a layered one (`resolve_last`)
    /// of a program whose last form holds, at `at`, an atom of a lib
    /// relation and no site, to `program`, which is that program but for
    /// the relation of that atom, now `relation`, and gives `true`. It
    /// then gives what `resolve_last` gives for `program`, as the
    /// atom's relation is all the last form's resolution reads of it: the
    /// last form is a clause whose columns are empty, or an instance whose
    /// key columns are empty where `at` is in its key body, and each node
    /// that holds the atom, and each node that reads such a node, has its
    /// content written again. Otherwise it changes nothing
    /// and gives `false`.
    pub fn retarget_lib_atom(&mut self, program: &Node<Program>, at: &NodePath, relation: &RelationRef, registry: &Registry) -> bool {
        let Some(old) = self.lib_atom_at(at) else { return false };
        let Some(new) = site_less_atom_at(program, at) else { return false };
        let Some(form) = program.value().forms.last() else { return false };
        let RelationRef::Lib(lib) = relation else { return false };
        if self.names.earlier.is_none()
            || !columns_unwritten(form, at)
            || new.relation != *relation
            || registry.entry(lib).is_none()
        {
            return false;
        }
        let Some(nodes) = self.atom_nodes(at) else { return false };
        let shared = self.signatures.keys().any(|path| path != at && path.0.first() == at.0.first() && self.reads_relation(path, &old));
        if !shared {
            self.names.lib.remove(&old);
        }
        match registry_columns::lib_columns(registry, lib) {
            Some(columns) => {
                self.names.lib.insert(relation.clone(), columns);
            }
            None => {
                self.names.lib.remove(relation);
            }
        }
        let columns = self.names.columns(&NameScope::Program, relation).cloned();
        let signature = signature(&self.names, &Resolution::Lib(lib.clone()), relation, columns.as_ref());
        self.signatures.insert(at.clone(), signature);
        self.resolutions.insert(at.clone(), Resolution::Lib(lib.clone()));
        for cell in self.names.unwritten.iter_mut().flatten() {
            *cell = std::sync::OnceLock::new();
        }
        self.program = program.clone();
        for slot in nodes {
            if self.names.unwritten[slot].is_none() {
                self.names.contents[slot] = Some(self.unwritten_content(slot));
            }
        }
        true
    }

    /// The slots of the nodes of the last form that hold the atom at `at`
    /// or read such a node, each after the nodes it reads, where the
    /// content of each that is written can be written again; `None` where
    /// a cycle holds one of them or a written one has no content.
    fn atom_nodes(&self, at: &NodePath) -> Option<Vec<usize>> {
        let first = self.names.first_node();
        let mut affected: Vec<bool> = self.forms.iter().map(|paths| paths.iter().any(|path| at.0.starts_with(&path.0))).collect();
        let reads = |slot: usize| self.graph.reads[first + slot].iter().filter_map(move |read| (read.0 as usize).checked_sub(first));
        loop {
            let mut grew = false;
            for slot in 0..affected.len() {
                if !affected[slot] && reads(slot).any(|read| affected[read]) {
                    affected[slot] = true;
                    grew = true;
                }
            }
            if !grew {
                break;
            }
        }
        let mut order = Vec::new();
        let mut done = vec![false; affected.len()];
        while order.len() < affected.iter().filter(|&&node| node).count() {
            let ready = (0..affected.len()).find(|&slot| affected[slot] && !done[slot] && reads(slot).all(|read| !affected[read] || done[read]))?;
            done[ready] = true;
            order.push(ready);
        }
        order.iter().all(|&slot| self.names.unwritten[slot].is_some() || self.names.contents[slot].is_some()).then_some(order)
    }

    /// The relation of the atom at `at` of this program, where it holds no
    /// site and resolves to a lib name.
    fn lib_atom_at(&self, at: &NodePath) -> Option<RelationRef> {
        let atom = site_less_atom_at(&self.program, at)?;
        matches!(self.resolutions.get(at), Some(Resolution::Lib(_))).then(|| atom.relation.clone())
    }

    /// Whether the atom at `path` of this program reads `relation`.
    fn reads_relation(&self, path: &NodePath, relation: &RelationRef) -> bool {
        node_at(NodeRef::Program(self.program.value()), path).and_then(NodeRef::atom).is_some_and(|atom| atom.relation == *relation)
    }
}

/// Whether the column list of `form` that gives the order of the body that
/// holds the atom at `at` is empty, as a form in progress holds it: a
/// clause's columns, or an instance's key columns, which only a key body
/// reads. Any other form gives `false`.
fn columns_unwritten(form: &Form, at: &NodePath) -> bool {
    match form {
        Form::Clause(clause) => clause.value().columns.is_empty(),
        Form::Instance(instance) => {
            let in_key_body = instance.value().key.is_some() && at.0.get(1..3) == Some(&[PathStep(0), PathStep(0)][..]);
            !in_key_body || instance.value().key.as_ref().is_some_and(|key| key.value().key.columns.is_empty())
        }
        _ => false,
    }
}

fn site_less_atom_at<'a>(program: &'a Node<Program>, at: &NodePath) -> Option<&'a Atom> {
    node_at(NodeRef::Program(program.value()), at)?.atom().filter(|atom| atom.sites.is_empty())
}
