//! The retarget of a layered resolution from one lib atom to another: the
//! entries that the relation of an atom of no site gives, rewritten in
//! place.

use super::sites::signature;
use crate::program::path::{node_at, NodePath, NodeRef};
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
    /// last form is a clause whose columns are empty, and each node of the
    /// last form has its content unwritten. Otherwise it changes nothing
    /// and gives `false`.
    pub fn retarget_lib_atom(&mut self, program: &Node<Program>, at: &NodePath, relation: &RelationRef, registry: &Registry) -> bool {
        let Some(old) = self.lib_atom_at(at) else { return false };
        let Some(new) = site_less_atom_at(program, at) else { return false };
        let Some(Form::Clause(clause)) = program.value().forms.last() else { return false };
        let RelationRef::Lib(lib) = relation else { return false };
        if self.names.earlier.is_none()
            || !clause.value().columns.is_empty()
            || !self.names.unwritten.iter().all(Option::is_some)
            || new.relation != *relation
            || registry.entry(lib).is_none()
        {
            return false;
        }
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
        true
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

fn site_less_atom_at<'a>(program: &'a Node<Program>, at: &NodePath) -> Option<&'a Atom> {
    node_at(NodeRef::Program(program.value()), at)?.atom().filter(|atom| atom.sites.is_empty())
}
