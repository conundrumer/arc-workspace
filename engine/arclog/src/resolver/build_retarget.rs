//! The retarget of a layered resolution from one atom of no site to
//! another's relation: the entries that the relation of the atom gives,
//! rewritten in place.

use super::sides::lifted;
use super::sites::signature;
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::{Atom, Form, NameScope, Node, Program, ProgramRelation, RelationRef};
use crate::registry::{LibName, Registry};
use super::super::registry_columns;
use super::super::columns::example;
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram, Side};

/// What a name read by an atom resolves to, where a retarget handles it: a
/// lib name, or a node of the forms before the last.
enum Target {
    Lib(LibName),
    Node(GraphNodeIndex),
}

impl ResolvedProgram {
    /// Retargets this resolution, a layered one (`resolve_last`)
    /// of a program whose last form holds, at `at`, an atom of no site that
    /// reads a lib relation, a relation macro, a proposer, or a relation
    /// of a node of the forms before the last, to `program`, which is that
    /// program but for the relation of that atom, now `relation`, a name
    /// of one of those kinds, and gives `true`. It then gives what
    /// `resolve_last` gives for `program`, as the atom's relation is all
    /// the last form's resolution reads of it: the last form is a clause
    /// whose columns are empty, or an instance whose key columns are empty
    /// where `at` is in its key body; and each node that holds the atom,
    /// and each node that reads such a node, has its content written
    /// again, on its first read: no write of a content reads the content of
    /// a node of the last form, as the form's own relations are written
    /// by a mark and no other read resolves to such a node. A read of a node
    /// changes the graph's reads, and the retarget handles it where the
    /// last form is a clause that derives a declared relation. It gives
    /// `false` where another read of the last form resolves to a node of
    /// the last form. Otherwise it changes nothing and gives `false`.
    pub fn retarget_atom(&mut self, program: &Node<Program>, at: &NodePath, relation: &RelationRef, registry: &Registry) -> bool {
        let Some(old) = self.atom_target(at) else { return false };
        let Some(old_relation) = site_less_atom_at(&self.program, at).map(|atom| atom.relation.clone()) else { return false };
        let Some(new) = site_less_atom_at(program, at) else { return false };
        let Some(form) = program.value().forms.last() else { return false };
        if self.names.earlier.is_none() || !columns_unwritten(form, at) || new.relation != *relation {
            return false;
        }
        let Some(target) = self.target_of(relation, registry) else { return false };
        let first = self.names.first_node();
        if self.resolutions.iter().any(|(path, resolution)| path != at && matches!(resolution, Resolution::Node(node) if node.0 as usize >= first)) {
            return false;
        }
        let form_path = NodePath(at.0[..1].into());
        let resolution = match &target {
            Target::Lib(lib) => Resolution::Lib(lib.clone()),
            Target::Node(node) => Resolution::Node(*node),
        };
        let reads_node = matches!(old, Target::Node(_)) || matches!(target, Target::Node(_));
        let readers = if reads_node {
            if matches!(form, Form::Clause(clause) if !matches!(clause.value().derives, ProgramRelation::Declared(_))) {
                return false;
            }
            let Some(readers) = self.readers_of(program, at) else { return false };
            if matches!(form, Form::Instance(_) | Form::Choose(_)) && self.read_side(program, &form_path, at, None) != self.read_side(program, &form_path, at, Some(&resolution)) {
                return false;
            }
            Some(readers)
        } else {
            None
        };
        let lift = match (&target, self.form_side(&form_path)) {
            (Target::Node(node), Some(side)) => lifted(matches!(self.graph.nodes[node.0 as usize].kind, DependencyKind::Fact(_)), side, self.side(*node)),
            (Target::Node(_), None) => return false,
            (Target::Lib(_), _) => false,
        };
        let Some(nodes) = self.atom_nodes(at) else { return false };
        let shared = self.signatures.keys().any(|path| path != at && path.0.first() == at.0.first() && self.reads_relation(path, &old_relation));
        if let Some(readers) = readers {
            for reader in readers {
                let mut reads = self.graph.reads[reader.0 as usize].to_vec();
                if let Target::Node(old) = old {
                    let held = self.resolutions.iter().any(|(path, resolution)| {
                        path != at && matches!(resolution, Resolution::Node(read) if *read == old) && self.readers_of(&self.program, path).is_some_and(|others| others.contains(&reader))
                    });
                    if !held {
                        reads.retain(|read| *read != old);
                    }
                }
                if let Target::Node(new) = target {
                    if !reads.contains(&new) {
                        reads.push(new);
                        reads.sort_by_key(|read| read.0);
                    }
                }
                self.graph.reads[reader.0 as usize] = reads.into();
            }
        }
        if matches!(old, Target::Lib(_)) && !shared {
            self.names.lib.remove(&old_relation);
        }
        if let Target::Lib(lib) = &target {
            match registry_columns::lib_columns(registry, lib) {
                Some(columns) => {
                    self.names.lib.insert(relation.clone(), columns);
                }
                None => {
                    self.names.lib.remove(relation);
                }
            }
        }
        let mut columns = self.names.columns(&NameScope::Program, relation).cloned();
        if lift {
            columns = columns.map(|found| found.lifted());
            self.lifted.insert(at.clone());
        } else {
            self.lifted.remove(at);
        }
        let signature = signature(&self.names, &resolution, relation, columns.as_ref());
        self.signatures.insert(at.clone(), signature);
        self.resolutions.insert(at.clone(), resolution);
        for cell in self.names.unwritten.iter_mut().flatten() {
            *cell = std::sync::OnceLock::new();
        }
        self.depths = std::sync::OnceLock::new();
        self.program = program.clone();
        for &slot in &nodes {
            self.names.contents[slot] = None;
            self.names.unwritten[slot] = Some(std::sync::OnceLock::new());
        }
        true
    }

    /// The nodes of the last form that read the atom at `at` of
    /// `program`, as the resolver gives its reads: the node of a clause, a
    /// `CHOOSE` or a `RIGID_DET` form; of an `INIT` form, every node of
    /// the form for an atom of its key body, and the node that reads the
    /// input for an atom of an input. `None` for another form.
    fn readers_of(&self, program: &Node<Program>, at: &NodePath) -> Option<Vec<GraphNodeIndex>> {
        let form_path = NodePath(at.0[..1].into());
        let nodes = self.form_nodes.get(&form_path)?;
        let root = NodeRef::Program(program.value());
        match node_at(root, &form_path)? {
            NodeRef::Clause(_) | NodeRef::Choose(_) | NodeRef::RigidDet(_) => match &nodes[..] {
                [node] => Some(vec![*node]),
                _ => None,
            },
            NodeRef::Instance(_) => {
                let at_depth = |depth: usize| at.0.get(..depth).and_then(|prefix| node_at(root, &NodePath(prefix.into())));
                if let Some(NodeRef::InstanceInput(input)) = at_depth(2).filter(|node| matches!(node, NodeRef::InstanceInput(_))).or_else(|| at_depth(3)) {
                    let reader = nodes.iter().find(|node| match &self.graph.nodes[node.0 as usize].kind {
                        DependencyKind::InstanceInput { input: port, .. } => *port == input.name,
                        DependencyKind::RecursiveInstance(_) => true,
                        _ => false,
                    })?;
                    return Some(vec![*reader]);
                }
                matches!((at_depth(2), at_depth(3)), (Some(NodeRef::KeyClause(_)), Some(NodeRef::Body(_)))).then(|| nodes.to_vec())
            }
            _ => None,
        }
    }

    /// The side of the `INIT` or `CHOOSE` form at `form` of `program`, by
    /// what its reads read ([`Builder::sides`]'s rule), where the atom at
    /// `at` reads `resolution` in place of what this resolution gives it,
    /// where one is given.
    fn read_side(&self, program: &Node<Program>, form: &NodePath, at: &NodePath, resolution: Option<&Resolution>) -> Side {
        let root = NodeRef::Program(program.value());
        let mut per_input = false;
        for (path, held) in &self.resolutions {
            let Resolution::Node(node) = resolution.filter(|_| path == at).unwrap_or(held) else { continue };
            if self.forms_of(*node).contains(form) {
                continue;
            }
            let fact = matches!(self.graph.nodes[node.0 as usize].kind, DependencyKind::Fact(_));
            let reads_example = node_at(root, path).and_then(NodeRef::atom).is_some_and(|atom| atom.sites.iter().any(|site| site.column == example()));
            match self.side(*node) {
                Side::TaskWide if fact => return Side::TaskWide,
                Side::PerInput if reads_example && !fact => return Side::TaskWide,
                Side::PerInput => per_input = true,
                Side::TaskWide => {}
            }
        }
        if per_input {
            Side::PerInput
        } else {
            Side::TaskWide
        }
    }

    /// What the name read by the atom at `at` of this program resolves to,
    /// where the atom holds no site and the retarget handles it.
    fn atom_target(&self, at: &NodePath) -> Option<Target> {
        site_less_atom_at(&self.program, at)?;
        match self.resolutions.get(at)? {
            Resolution::Lib(lib) => Some(Target::Lib(lib.clone())),
            Resolution::Node(node) if (node.0 as usize) < self.names.first_node() => Some(Target::Node(*node)),
            _ => None,
        }
    }

    /// What `relation`, read in the program's scope, resolves to, where
    /// the retarget handles it.
    fn target_of(&self, relation: &RelationRef, registry: &Registry) -> Option<Target> {
        match relation {
            RelationRef::Lib(lib) => registry.entry(lib).is_some().then(|| Target::Lib(lib.clone())),
            RelationRef::Declared(_) | RelationRef::Output(_) => {
                let node = self.names.find(&NameScope::Program, relation)?.node;
                ((node.0 as usize) < self.names.first_node()).then_some(Target::Node(node))
            }
            RelationRef::Fact(_) | RelationRef::DefinedPort(_) => None,
        }
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
