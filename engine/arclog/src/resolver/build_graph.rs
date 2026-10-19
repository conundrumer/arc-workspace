//! The declarations and the reads of a case program: the nodes that each
//! form declares in its scope, the concept program's `DET` forms that the
//! case takes, and each read resolved to its node, as an edge of the graph.

use std::sync::Arc;

use super::columns;
use super::registry_columns;
use std::collections::BTreeSet;

use super::{rebase, AtomRead, Builder, ColumnsOf, ConceptReads, DependencyKind, DependencyNode, FormRelation, GraphNodeIndex, InstanceNodes, Resolution, Target};
use crate::hash::StableHashMap;
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::program::canonical::{prediction, relation_of};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, Clause, ClauseKeyword, Form, Instance, NameScope, OutputName, OutputOwner, OutputStep, PortName, ProgramRelation, RelationRef,
};
use crate::program::DemonstratedPart;

/// The node kind of a clause: a chosen relation where it has `ONE`
/// marks, a parameter where it is a `DET` with none, and a clause
/// relation otherwise.
fn clause_kind(clause: &Clause) -> DependencyKind {
    match (&clause.derives, clause.ones.is_empty(), clause.keyword) {
        (ProgramRelation::Declared(name), false, _) => DependencyKind::Chosen(name.clone()),
        (relation, _, ClauseKeyword::Det) => DependencyKind::Parameter(relation.clone()),
        (relation, _, _) => DependencyKind::Clause(relation.clone()),
    }
}

impl<'a> Builder<'a> {
    /// The node of `kind` in `scope`, made on its first use, with the
    /// form at `form` among its forms.
    pub(super) fn node(&mut self, kind: DependencyKind, scope: &NameScope, form: Option<&NodePath>) -> GraphNodeIndex {
        let key = DependencyNode { kind, scope: scope.clone() };
        let node = match self.index.get(&key) {
            Some(node) => *node,
            None => {
                let node = GraphNodeIndex(self.nodes.len() as u32);
                self.index.insert(key.clone(), node);
                self.nodes.push(key);
                self.forms.push(Vec::new());
                self.relations.push(Vec::new());
                self.reads.push(BTreeSet::new());
                node
            }
        };
        if let Some(form) = form {
            self.forms[node.0 as usize].push(form.clone());
        }
        node
    }

    /// Records that the form at `form` gives `node` the relation of
    /// `listing`, at `output` where the form gives several relations.
    pub(super) fn relate(&mut self, node: GraphNodeIndex, form: &NodePath, output: Option<Arc<[OutputStep]>>, listing: columns::Listing) {
        self.relations[node.0 as usize].push(FormRelation { form: form.clone(), output, listing });
    }

    pub(super) fn target(&mut self, scope: &NameScope, relation: RelationRef, target: Target) {
        self.names.scopes.entry(scope.clone()).or_default().insert(relation, target);
    }

    pub(super) fn read(&mut self, reader: GraphNodeIndex, read: GraphNodeIndex) {
        self.reads[reader.0 as usize].insert(read.0);
    }

    pub(super) fn unresolved(&mut self, path: &NodePath, name: &str) -> Resolution {
        self.diagnostics.push(Diagnostic {
            kind: DiagnosticKind::Check(crate::check::CheckId::Scope),
            severity: Severity::Error,
            message: format!("`{name}` names nothing visible here").into(),
            location: Location::Path(path.clone()),
            cases: Box::default(),
        });
        Resolution::Unresolved
    }

    /// Finds in the concept program each `DET` form that the case takes
    /// from it.
    pub(super) fn take_concept(&mut self, concept: ConceptReads<'_>) {
        let concept_forms = &concept.concept.program.value().forms;
        for path in concept.determinations {
            let Some(Form::Clause(clause)) = path.0.first().and_then(|step| self.case.value().forms.get(step.0 as usize)) else { continue };
            let Some(index) = concept_forms.iter().position(|form| matches!(form, Form::Clause(other) if other == clause)) else { continue };
            let concept_path = NodePath::top(index as u32);
            let Some(content) = concept.concept.content(&concept_path) else { continue };
            let relation = relation_of(&clause.value().derives);
            let columns = concept.concept.names.columns(&NameScope::Program, &relation).cloned();
            if let Some(target) = concept.concept.names.find(&NameScope::Program, &relation) {
                self.concept_examples.insert(path.clone(), concept.concept.examples[target.node.0 as usize].clone());
            }
            self.names.fixed.insert(path.clone(), content.form);
            self.concept_columns.insert(path.clone(), columns);
            self.concept_forms.insert(path.clone(), concept_path);
        }
    }

    /// Copies from the concept program what each form that resolves
    /// there resolves to, apart from its nodes, which are the concept
    /// program's.
    pub(super) fn copy_concept(&mut self, concept: ConceptReads<'_>) {
        let concept = concept.concept;
        let mut forms: Vec<(&NodePath, &NodePath)> = self.concept_forms.iter().collect();
        forms.sort();
        for (path, concept_path) in forms {
            for (at, resolution) in &concept.resolutions {
                if matches!(resolution, Resolution::Node(_)) {
                    continue;
                }
                if let Some(at) = rebase(at, concept_path, path) {
                    self.resolutions.insert(at, resolution.clone());
                }
            }
            for (at, signature) in &concept.signatures {
                if let Some(at) = rebase(at, concept_path, path) {
                    self.signatures.insert(at, signature.clone());
                }
            }
            for (at, position) in &concept.positions {
                if let Some(at) = rebase(at, concept_path, path) {
                    self.positions.insert(at, *position);
                }
            }
            for (at, group) in &concept.groups {
                if let Some(at) = rebase(at, concept_path, path) {
                    self.groups.insert(at, *group);
                }
            }
            for ((at, index), columns) in &concept.proposer_columns {
                if let Some(at) = rebase(at, concept_path, path) {
                    self.proposer_columns.insert((at, *index), columns.clone());
                }
            }
        }
    }

    /// Declares what `form` at `path` declares in `scope`. The relations
    /// that a clause, a `CHOOSE` or a `DEMONSTRATED` form declares go to
    /// `pending`, so that a clause on an output of an instance, such as
    /// a `RULE_OR_DET` line on `&ring.value`, stands for that output.
    pub(super) fn declare(&mut self, form: &'a Form, path: NodePath, scope: &NameScope, pending: &mut Vec<(NameScope, RelationRef, Target)>) {
        match form {
            Form::Claim(claim) => {
                for (index, form) in claim.value().forms.iter().enumerate() {
                    self.declare(form, path.child(index as u32), scope, pending);
                }
            }
            Form::Alts(_) => {}
            Form::Clause(clause) => {
                let clause = clause.value();
                let node = self.node(clause_kind(clause), scope, Some(&path));
                self.form_node.insert(path.clone(), node);
                self.relate(node, &path, None, columns::form_listing(NodeRef::Clause(clause)));
                pending.push((scope.clone(), relation_of(&clause.derives), Target { node, columns: ColumnsOf::OfNode }));
                if !self.concept_forms.contains_key(&path) {
                    self.clauses.push((path, clause));
                }
            }
            Form::Choose(choose) => {
                let name = &choose.value().name;
                let node = self.node(DependencyKind::Chosen(name.clone()), scope, Some(&path));
                self.relate(node, &path, None, columns::form_listing(NodeRef::Choose(choose.value())));
                self.form_node.insert(path, node);
                pending.push((scope.clone(), RelationRef::Declared(name.clone()), Target { node, columns: ColumnsOf::OfNode }));
            }
            Form::Demonstrated(demonstrated) => {
                let demonstrated = demonstrated.value();
                let node = self.node(DependencyKind::Demonstrated(demonstrated.name.clone()), scope, Some(&path));
                self.form_node.insert(path.clone(), node);
                let listing = columns::demonstrated_listing(demonstrated);
                let columns = ColumnsOf::Fixed(listing.columns());
                self.relate(node, &path, None, listing);
                pending.push((scope.clone(), RelationRef::Declared(demonstrated.name.clone()), Target { node, columns }));
                for (rule_path, rule) in super::super::demo_rules(demonstrated, &path) {
                    let rule_scope = NameScope::DemoRule(rule_path.clone());
                    for (index, form) in rule.forms.iter().enumerate() {
                        self.declare(form, rule_path.child(index as u32), &rule_scope, pending);
                    }
                }
            }
            Form::RigidDet(rigid) => {
                let rigid = rigid.value();
                let node = self.node(DependencyKind::RigidAssembly(rigid.name.clone()), scope, Some(&path));
                self.form_node.insert(path.clone(), node);
                for (steps, listing) in columns::rigid_listings(rigid) {
                    let relation = RelationRef::Output(OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path: steps.clone() });
                    self.target(scope, relation, Target { node, columns: ColumnsOf::Fixed(listing.columns()) });
                    self.relate(node, &path, Some(steps), listing);
                }
            }
            Form::Instance(instance) => self.declare_instance(instance.value(), path, scope),
        }
    }

    /// Declares the nodes of an `INIT` form: one node for an instance
    /// whose inputs read its outputs, and otherwise a node per input it
    /// writes and per output, each output reading every input.
    pub(super) fn declare_instance(&mut self, instance: &'a Instance, path: NodePath, scope: &NameScope) {
        let Some(component) = registry_columns::component(self.registry, &instance.component) else {
            let resolution = self.unresolved(&path, &instance.component.0);
            self.resolutions.insert(path, resolution);
            return;
        };
        self.resolutions.insert(path.clone(), Resolution::Lib(instance.component.clone()));
        let name = &instance.name;
        let written: Vec<_> = crate::program::written_inputs(instance.key.as_ref(), &instance.inputs).collect();
        let mut inputs = Vec::new();
        let mut outputs = Vec::new();
        if component.reads_outputs() {
            let node = self.node(DependencyKind::RecursiveInstance(name.clone()), scope, Some(&path));
            inputs.extend(written.iter().map(|input| (input.name.clone(), node)));
            outputs.extend(component.outputs.iter().map(|output| (output.name.clone(), node)));
        } else {
            for input in &written {
                let kind = DependencyKind::InstanceInput { instance: name.clone(), input: input.name.clone() };
                inputs.push((input.name.clone(), self.node(kind, scope, Some(&path))));
            }
            for output in component.outputs.iter() {
                let kind = DependencyKind::InstanceOutput { instance: name.clone(), output: output.name.clone() };
                let node = self.node(kind, scope, Some(&path));
                for (_, input) in &inputs {
                    self.read(node, *input);
                }
                outputs.push((output.name.clone(), node));
            }
        }
        let bindings = columns::bindings(instance, component);
        let mut port_columns = StableHashMap::default();
        let relation = |port: &PortName| {
            RelationRef::Output(OutputName { of: OutputOwner::Instance(name.clone()), path: Arc::from([OutputStep::Port(port.clone())]) })
        };
        for input in component.inputs.iter() {
            let columns = columns::port_columns(&input.port, &bindings).columns();
            let read = inputs.iter().find(|(port, _)| *port == input.port.name);
            if let Some((port, node)) = read.filter(|(port, _)| !component.outputs.iter().any(|output| output.name == *port)) {
                self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
            }
            port_columns.insert(input.port.name.clone(), columns);
        }
        for (output, (port, node)) in component.outputs.iter().zip(&outputs) {
            let listing = columns::port_columns(output, &bindings);
            let columns = listing.columns();
            self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
            port_columns.insert(port.clone(), columns);
            self.relate(*node, &path, Some(Arc::from([OutputStep::Port(port.clone())])), listing);
        }
        self.instances.insert((scope.clone(), name.clone()), InstanceNodes { form: path, inputs, outputs, columns: port_columns, component });
    }

    /// Resolves the reads of `form` at `path` in `scope`, and adds each
    /// to the graph as an edge from the node read to the node that reads
    /// it.
    pub(super) fn read_form(&mut self, form: &'a Form, path: NodePath, scope: &NameScope) {
        match form {
            Form::Claim(claim) => {
                for (index, form) in claim.value().forms.iter().enumerate() {
                    self.read_form(form, path.child(index as u32), scope);
                }
            }
            Form::Alts(_) => {}
            Form::Clause(clause) => {
                if self.concept_forms.contains_key(&path) {
                    return;
                }
                let clause = clause.value();
                let node = self.form_node[&path];
                for proposer in clause.proposers.iter() {
                    if !registry_columns::is_proposer(self.registry, proposer) {
                        self.unresolved(&path, &proposer.0);
                    }
                }
                self.read_below(NodeRef::Body(clause.body.value()), path.child(0), scope, &[node], &path);
                self.read_instance_line(clause, node, scope);
            }
            Form::Instance(instance) => {
                let instance = instance.value();
                let Some(nodes) = self.instances.get(&(scope.clone(), instance.name.clone())) else { return };
                let every = nodes.every();
                let reader = |input: &PortName| nodes.input(input).expect("a node of each input the form writes");
                let mut readers: Vec<(NodeRef<'a>, NodePath, Vec<GraphNodeIndex>)> = Vec::new();
                let mut before = 0;
                if let Some(key) = &instance.key {
                    let key = key.value();
                    let key_path = path.child(0);
                    readers.push((NodeRef::Body(key.key.body.value()), key_path.child(0), every.clone()));
                    for (index, input) in key.inputs.iter().enumerate() {
                        readers.push((NodeRef::InstanceInput(input.value()), key_path.child(1 + index as u32), vec![reader(&input.value().name)]));
                    }
                    before = 1;
                }
                for (index, input) in instance.inputs.iter().enumerate() {
                    readers.push((NodeRef::InstanceInput(input.value()), path.child(before + index as u32), vec![reader(&input.value().name)]));
                }
                for (node, at, readers) in readers {
                    self.read_below(node, at, scope, &readers, &path);
                }
            }
            Form::Choose(_) | Form::RigidDet(_) => {
                let node = self.form_node[&path];
                self.read_below(NodeRef::from(form), path.clone(), scope, &[node], &path);
            }
            Form::Demonstrated(demonstrated) => {
                let demonstrated = demonstrated.value();
                let node = self.form_node[&path];
                if let Some(key) = &demonstrated.key {
                    let at = path.child(demonstrated.position(DemonstratedPart::Key));
                    self.read_below(NodeRef::KeyClause(key.value()), at, scope, &[node], &path);
                }
                for (index, input) in demonstrated.inputs.iter().enumerate() {
                    let at = path.child(demonstrated.position(DemonstratedPart::Input(index)));
                    self.read_below(NodeRef::InstanceInput(input.value()), at, scope, &[node], &path);
                }
                for (rule_path, rule) in super::super::demo_rules(demonstrated, &path) {
                    let rule_scope = NameScope::DemoRule(rule_path.clone());
                    for (index, form) in rule.forms.iter().enumerate() {
                        self.read_form(form, rule_path.child(index as u32), &rule_scope);
                    }
                    let prediction = self.names.scopes.get(&rule_scope).and_then(|names| names.get(&prediction())).map(|target| target.node);
                    if let Some(prediction) = prediction {
                        self.read(node, prediction);
                    }
                }
            }
        }
    }

    /// Adds the edges of a clause on a port of an instance. The instance
    /// reads a clause on one of its inputs, as a `DET_OR_RULE` line on
    /// `&canvas.extent`, and a clause on one of its outputs, as a
    /// `RULE_OR_DET` line on `&ring.value`, reads that output. For a `DET` on
    /// a port, on an input the input's node reads the `DET`'s parameter
    /// node, made where the `INIT` form writes no clause of that input, and
    /// on an output the `DET` reads nothing of the instance, as
    /// `docs/arclog/arclog.md#the-alts-form` gives.
    pub(super) fn read_instance_line(&mut self, clause: &Clause, node: GraphNodeIndex, scope: &NameScope) {
        let ProgramRelation::Output(output) = &clause.derives else { return };
        let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return };
        let Some(nodes) = self.instances.get(&(scope.clone(), name.clone())) else { return };
        let on_input = nodes.component.inputs.iter().any(|input| input.port.name == *port);
        let stored = matches!(self.nodes[node.0 as usize].kind, DependencyKind::Parameter(_));
        let edges: Vec<(GraphNodeIndex, GraphNodeIndex)> = match (on_input, stored) {
            (true, true) => {
                let input = match nodes.input(port) {
                    Some(input) => input,
                    None => {
                        let (form, outputs) = (nodes.form.clone(), nodes.outputs.clone());
                        let kind = DependencyKind::InstanceInput { instance: name.clone(), input: port.clone() };
                        let input = self.node(kind, scope, Some(&form));
                        for (_, output) in outputs {
                            self.read(output, input);
                        }
                        let nodes = self.instances.get_mut(&(scope.clone(), name.clone())).expect("the instance's nodes");
                        nodes.inputs.push((port.clone(), input));
                        input
                    }
                };
                vec![(input, node)]
            }
            (true, false) => nodes.outputs.iter().map(|(_, output)| (*output, node)).collect(),
            (false, true) => Vec::new(),
            (false, false) => nodes.outputs.iter().filter(|(name, _)| name == port).map(|(_, output)| (node, *output)).collect(),
        };
        for (reader, read) in edges {
            if reader != read {
                self.read(reader, read);
            }
        }
    }

    /// Resolves each atom below `node`, at `path`, as read by each node
    /// of `readers` in the form at `form`.
    pub(super) fn read_below(&mut self, node: NodeRef<'a>, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex], form: &NodePath) {
        if let Some(atom) = node.atom() {
            return self.read_atom(atom, path, scope, readers, form);
        }
        match node {
            NodeRef::DemoRule(_) => {}
            _ => {
                for (index, child) in node.children().into_iter().enumerate() {
                    self.read_below(child, path.child(index as u32), scope, readers, form);
                }
            }
        }
    }

    pub(super) fn read_atom(&mut self, atom: &'a Atom, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex], form: &NodePath) {
        let resolution = self.resolve_name(scope, &atom.relation, &path);
        if let Resolution::Node(read) = resolution {
            for &reader in readers {
                let recursive = matches!(self.nodes[reader.0 as usize].kind, DependencyKind::RecursiveInstance(_));
                if !(recursive && reader == read) {
                    self.read(reader, read);
                }
            }
        }
        self.resolutions.insert(path.clone(), resolution);
        self.atoms.push(AtomRead { path, atom, scope: scope.clone(), form: form.clone() });
    }

    pub(super) fn resolve_name(&mut self, scope: &NameScope, relation: &RelationRef, path: &NodePath) -> Resolution {
        let name = || crate::write::relation_ref(relation);
        let program_relation = match relation {
            RelationRef::Lib(lib) => {
                if self.registry.entry(lib).is_none() {
                    return self.unresolved(path, &name());
                }
                if let Some(columns) = registry_columns::lib_columns(self.registry, lib) {
                    self.names.lib.insert(relation.clone(), columns);
                }
                return Resolution::Lib(lib.clone());
            }
            RelationRef::DefinedPort(_) => return self.unresolved(path, &name()),
            RelationRef::Fact(_) => None,
            RelationRef::Declared(declared) => Some(ProgramRelation::Declared(declared.clone())),
            RelationRef::Output(output) => Some(ProgramRelation::Output(output.clone())),
        };
        if let Some(target) = self.names.find(scope, relation) {
            return Resolution::Node(target.node);
        }
        match program_relation {
            Some(program_relation) if self.derived.contains(&program_relation) => Resolution::Undefined(program_relation),
            _ => self.unresolved(path, &name()),
        }
    }
}
