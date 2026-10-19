//! The side of each node and of each form of a case program, each decided
//! once, and the columns of each node that hold an Example.

use std::sync::Arc;

use super::super::{column_sources, columns};
use super::super::registry_columns;
use super::{Builder, ExamplePath, GraphNodeIndex, Resolution, Side};
use crate::hash::StableHashMap;
use crate::program::canonical::{prediction, relation_of};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Atom, ClauseKeyword, FactRelation, LabelId, OutputStep};
use crate::resolver::DependencyKind;
use crate::types::{each_site_label, use_label};

impl Builder<'_> {
    /// The side of each node and of each form whose reads the case
    /// resolves.
    pub(super) fn sides(&mut self) {
        let mut reads: StableHashMap<NodePath, Vec<usize>> = StableHashMap::default();
        for (index, read) in self.atoms.iter().enumerate() {
            reads.entry(read.form.clone()).or_default().push(index);
        }
        let mut forms: Vec<NodePath> = reads.keys().cloned().collect();
        forms.sort();
        let mut sides = Sides { builder: self, reads, forms: StableHashMap::default(), examples: StableHashMap::default() };
        let decided = "a side that a call from outside the decision gives is decided";
        for form in &forms {
            sides.form(form).expect(decided);
        }
        let node_sides: Vec<Side> = (0..self.nodes.len()).map(|node| sides.node(node).expect(decided)).collect();
        let examples = (0..self.nodes.len()).map(|node| sides.examples(node, None)).collect();
        let mut output_examples = StableHashMap::default();
        for (node, relations) in self.relations.iter().enumerate() {
            for output in relations.iter().filter_map(|relation| relation.output.clone()) {
                let paths = sides.examples(node, Some(&output));
                output_examples.insert((GraphNodeIndex(node as u32), output), paths);
            }
        }
        let form_sides = sides.forms.into_iter().map(|(path, side)| (path, side.expect(decided))).collect();
        self.sides = node_sides;
        self.examples = examples;
        self.output_examples = output_examples;
        self.form_sides = form_sides;
    }
}

/// Whether a form of side `form` reads, in its lifted form, a relation
/// of side `read` that is a fact where `fact` holds.
pub(super) fn lifted(fact: bool, form: Side, read: Side) -> bool {
    !fact && form == Side::TaskWide && read == Side::PerInput
}

/// Whether `atom` has a site on the Example column of a lifted read.
fn reads_example(atom: &Atom) -> bool {
    atom.sites.iter().any(|site| site.column == columns::example())
}

/// The side of a clause of `keyword`.
fn keyword_side(keyword: ClauseKeyword) -> Side {
    match keyword {
        ClauseKeyword::Rule | ClauseKeyword::RuleOrDet => Side::PerInput,
        ClauseKeyword::Det | ClauseKeyword::DetOrRule => Side::TaskWide,
    }
}

/// The sides of the nodes of a case, each decided once, a form's after the
/// sides of the nodes it reads, as `docs/arclog/arclog.md#program` and
/// `docs/arclog/arclog.md#instance` give, and the columns of each node that
/// hold an Example, by which a key's Example labels are told.
struct Sides<'b, 'a> {
    builder: &'b Builder<'a>,
    /// The index in [`Builder::atoms`] of each atom of each form.
    reads: StableHashMap<NodePath, Vec<usize>>,
    /// The side of each form, `None` while it is being decided, so that a
    /// read on a cycle, which the checker refuses, decides nothing.
    forms: StableHashMap<NodePath, Option<Side>>,
    /// The columns of each node that hold an Example, in a relation by
    /// its output path or in each of its relations, empty while they are
    /// being decided, so that a read on a cycle gives none.
    examples: StableHashMap<(usize, Option<Arc<[OutputStep]>>), Arc<[ExamplePath]>>,
}

impl Sides<'_, '_> {
    fn node(&mut self, node: usize) -> Option<Side> {
        match &self.builder.nodes[node].kind {
            DependencyKind::Fact(FactRelation::Input) => Some(Side::PerInput),
            DependencyKind::Fact(FactRelation::ExInput | FactRelation::ExOutput) => Some(Side::TaskWide),
            _ => {
                let form = self.builder.forms[node].first().expect("a form of each node of the case that is no fact").clone();
                self.form(&form)
            }
        }
    }

    /// The side of the form at `path`. A clause takes the side of its
    /// keyword, apart from the `&prediction` clause of a `DEMO_RULE`,
    /// which takes the side of the `DEMONSTRATED` form that holds the
    /// rule, `docs/arclog/arclog.md#demonstrated`.
    fn form(&mut self, path: &NodePath) -> Option<Side> {
        if let Some(side) = self.forms.get(path) {
            return *side;
        }
        self.forms.insert(path.clone(), None);
        let program = NodeRef::Program(self.builder.case.value());
        let form = node_at(program, path).expect("the path of a form of the case");
        let side = match form {
            NodeRef::Clause(clause) if relation_of(&clause.derives) == prediction() && path.0.len() >= 2 => {
                let rule = NodePath(path.0[..path.0.len() - 1].into());
                let demonstrated = NodePath(path.0[..path.0.len() - 2].into());
                match node_at(program, &rule) {
                    Some(NodeRef::DemoRule(_)) => self.form(&demonstrated).expect(
                        "a `DEMONSTRATED` form's side is decided from its input bodies, which see no name of its rules",
                    ),
                    _ => keyword_side(clause.keyword),
                }
            }
            NodeRef::Clause(clause) => keyword_side(clause.keyword),
            NodeRef::RigidDet(_) => Side::TaskWide,
            _ => self.read_side(path),
        };
        self.forms.insert(path.clone(), Some(side));
        Some(side)
    }

    /// The side of an `INIT`, a `CHOOSE` or a `DEMONSTRATED` form at `path`.
    /// The side is the one `docs/arclog/arclog.md#instance` gives: a form
    /// whose key clause holds a label that holds an Example, as
    /// [`Sides::key_examples`] gives, is per example, and so task-wide,
    /// whatever its bodies read.
    fn read_side(&mut self, path: &NodePath) -> Side {
        let builder = self.builder;
        if self.key_examples(path) {
            return Side::TaskWide;
        }
        let mut per_input = false;
        for index in self.reads.get(path).cloned().unwrap_or_default() {
            let read = &builder.atoms[index];
            let Resolution::Node(read_node) = builder.resolutions[&read.path] else { continue };
            let node = read_node.0 as usize;
            if builder.forms[node].contains(path) {
                continue;
            }
            let fact = builder.is_fact(read_node);
            let reads_example = reads_example(read.atom);
            match self.node(node) {
                Some(Side::TaskWide) if fact => return Side::TaskWide,
                Some(Side::PerInput) if reads_example && !fact => return Side::TaskWide,
                Some(Side::PerInput) => per_input = true,
                Some(Side::TaskWide) | None => {}
            }
        }
        if per_input {
            Side::PerInput
        } else {
            Side::TaskWide
        }
    }

    /// The column paths of `node`, a node of the case, that hold an
    /// Example, in the relation at `output` after the form's name, or in
    /// each of its relations where `output` is `None`. A path holds an
    /// Example where the concept program gives it for a form that resolves
    /// there, and otherwise where, in the listing of a relation a form
    /// gives the node, of the columns [`Builder::keeps`] keeps, its declared
    /// type is `Example` or its label is one
    /// that its body binds at a site that holds an Example, as
    /// [`Sides::bound_examples`] gives.
    fn examples(&mut self, node: usize, output: Option<&[OutputStep]>) -> Arc<[ExamplePath]> {
        let key = (node, output.map(Arc::from));
        if let Some(found) = self.examples.get(&key) {
            return found.clone();
        }
        self.examples.insert(key.clone(), Arc::from([]));
        let builder = self.builder;
        let mut found: Vec<ExamplePath> = Vec::new();
        let mut bound: StableHashMap<NodePath, Vec<LabelId>> = StableHashMap::default();
        for relation in &builder.relations[node] {
            if output.zip(relation.output.as_deref()).is_some_and(|(read, given)| read != given) {
                continue;
            }
            let held: Vec<ExamplePath> = match builder.concept_examples.get(&relation.form) {
                Some(concept) => concept.to_vec(),
                None => {
                    let mut held = Vec::new();
                    for (path, source) in relation.listing.sources() {
                        if !path.first().is_some_and(|column| builder.keeps(node, column)) {
                            continue;
                        }
                        let holds = match source {
                            column_sources::Source::Declared(ty) => registry_columns::is_example(ty),
                            column_sources::Source::Label { label, body } => {
                                let body = relation.form.join(body);
                                if !bound.contains_key(&body) {
                                    let labels = self.bound_examples(&relation.form, &body);
                                    bound.insert(body.clone(), labels);
                                }
                                bound[&body].contains(label)
                            }
                        };
                        if holds {
                            held.push(path.clone());
                        }
                    }
                    held
                }
            };
            for path in held {
                if !found.contains(&path) {
                    found.push(path);
                }
            }
        }
        let found: Arc<[ExamplePath]> = found.into();
        self.examples.insert(key, found.clone());
        found
    }

    /// Whether the key clause of the form at `form` holds a label that its
    /// body binds at a site that holds an Example: the `key` of an `INIT`, a
    /// `DEMONSTRATED` or a `RIGID_DET` form, or the `for` of a `CHOOSE`
    /// form, as [`column_sources::key_clause`] gives it.
    fn key_examples(&mut self, form: &NodePath) -> bool {
        let Some(at) = node_at(NodeRef::Program(self.builder.case.value()), form) else { return false };
        let Some((key, body)) = column_sources::key_clause(at) else { return false };
        let bound = self.bound_examples(form, &form.join(&body));
        key.columns.iter().any(|column| bound.contains(&column.label))
    }

    /// The labels that the atoms of the form at `form` below `body`
    /// bind at a site that holds an Example: a site on a column of the
    /// type `Example` that [`registry_columns::typed_columns`] gives; on
    /// a column of a node that [`Sides::examples`] gives; or on the
    /// Example column that a lifted read adds. A read is lifted as
    /// [`lifted`] gives, and a read of the form whose side is being
    /// decided is lifted where it has a site on `E`, as
    /// [`Sides::read_side`] gives such a form the task-wide side.
    fn bound_examples(&mut self, form: &NodePath, body: &NodePath) -> Vec<LabelId> {
        let builder = self.builder;
        let mut labels = Vec::new();
        for index in self.reads.get(form).cloned().unwrap_or_default() {
            let read = &builder.atoms[index];
            if !read.path.0.starts_with(&body.0) {
                continue;
            }
            let typed = registry_columns::typed_columns(builder.registry, &read.atom.relation).unwrap_or_default();
            let mut held: Vec<ExamplePath> = registry_columns::examples(typed).map(|name| Box::from([name])).collect();
            if let Resolution::Node(read_node) = builder.resolutions[&read.path] {
                let node = read_node.0 as usize;
                held.extend(self.examples(node, super::super::output_of(&read.atom.relation)).iter().cloned());
                let fact = builder.is_fact(read_node);
                let lift = match (self.form(&read.form), self.node(node)) {
                    (Some(side), Some(read_side)) => lifted(fact, side, read_side),
                    (None, Some(Side::PerInput)) => !fact && reads_example(read.atom),
                    _ => false,
                };
                if lift {
                    held.push(Box::from([columns::example()]));
                }
            }
            for site in read.atom.sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                    if let Some(label) = use_label(use_) {
                        if held.iter().any(|example| path.starts_with(example)) && !labels.contains(&label) {
                            labels.push(label);
                        }
                    }
                });
            }
        }
        labels
    }
}
