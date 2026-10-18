//! The passes of [`super::resolve`]: the declarations of each scope, the reads and
//! the graph, the content and the columns of each node, then the columns of
//! each site.

use std::collections::BTreeSet;
use std::sync::Arc;

use super::columns::{self, Columns, Place};
use super::names::{combined, write_output_path, ColumnsOf, Names, Own, Target, Writer};
use super::{
    ColumnPosition, ConceptReads, DependencyGraph, DependencyKind, DependencyNode, ExamplePath, GraphNodeIndex,
    ResolvedProgram, Resolution, Side, Signature,
};
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity, WithDiagnostics};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::canonical::{canonical_labeling, prediction, relation_of, AsWritten, CanonicalWriter, LabelScope, NameWriter, SearchBudget};
use crate::program::path::{child_index, node_at, NodePath, NodeRef};
use crate::program::{
    Atom, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, FactRelation, Form, Instance, InstanceName, NameScope,
    Negated, Node, OutputName, OutputOwner, OutputStep, PortName, Program, ProgramRelation, RelationRef,
};
use crate::program::{Demonstrated, InstanceInput, LabelId, RigidDet, Site};
use crate::registry::{binding_sites, ColumnType, Component, ParameterSite, Registry};
use crate::relations::ColumnGroup;
use crate::types::{each_site_label, use_label};

/// The nodes of one `INIT` form: the node that reads each input it
/// writes, the node of each output, and its component.
struct InstanceNodes<'r> {
    inputs: Vec<(PortName, GraphNodeIndex)>,
    outputs: Vec<(PortName, GraphNodeIndex)>,
    columns: StableHashMap<PortName, Columns>,
    component: &'r Component,
}

impl InstanceNodes<'_> {
    fn input(&self, name: &PortName) -> Option<GraphNodeIndex> {
        self.inputs.iter().find(|(port, _)| port == name).map(|(_, node)| *node)
    }

    fn every(&self) -> Vec<GraphNodeIndex> {
        let nodes: BTreeSet<u32> = self.inputs.iter().chain(self.outputs.iter()).map(|(_, node)| node.0).collect();
        nodes.into_iter().map(GraphNodeIndex).collect()
    }
}

/// An atom that a form of the case reads: its path, its name scope, and
/// the path of the form whose body holds it.
struct AtomRead<'a> {
    path: NodePath,
    atom: &'a Atom,
    scope: NameScope,
    form: NodePath,
}

struct Builder<'a> {
    case: &'a Node<Program>,
    registry: &'a Registry,
    derived: &'a StableHashSet<ProgramRelation>,
    nodes: Vec<DependencyNode>,
    index: StableHashMap<DependencyNode, GraphNodeIndex>,
    /// The paths of the forms of each node.
    forms: Vec<Vec<NodePath>>,
    reads: Vec<BTreeSet<u32>>,
    /// The node of each form that gives one node.
    form_node: StableHashMap<NodePath, GraphNodeIndex>,
    instances: StableHashMap<(NameScope, InstanceName), InstanceNodes<'a>>,
    names: Names,
    /// The path in the concept program of each form that resolves there.
    concept_forms: StableHashMap<NodePath, NodePath>,
    /// The columns of each relation that a form resolving in the concept
    /// program derives, as the concept program gives them.
    concept_columns: StableHashMap<NodePath, Option<Columns>>,
    /// The columns that hold an Example of each relation that a form
    /// resolving in the concept program derives, as the concept program
    /// gives them.
    concept_examples: StableHashMap<NodePath, Arc<[ExamplePath]>>,
    atoms: Vec<AtomRead<'a>>,
    /// The side of each node, by its index.
    sides: Vec<Side>,
    /// The columns of each node that hold an Example, by its index.
    examples: Vec<Arc<[ExamplePath]>>,
    /// The side of each form whose reads the case resolves.
    form_sides: StableHashMap<NodePath, Side>,
    clauses: Vec<(NodePath, &'a Clause)>,
    resolutions: StableHashMap<NodePath, Resolution>,
    signatures: StableHashMap<NodePath, Signature>,
    positions: StableHashMap<NodePath, ColumnPosition>,
    groups: StableHashMap<NodePath, ColumnGroup>,
    proposer_columns: StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
    diagnostics: Vec<Diagnostic>,
}

pub(super) fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    derived: &StableHashSet<ProgramRelation>,
    registry: &Registry,
) -> WithDiagnostics<ResolvedProgram> {
    let mut builder = Builder {
        case,
        registry,
        derived,
        nodes: Vec::new(),
        index: StableHashMap::default(),
        forms: Vec::new(),
        reads: Vec::new(),
        form_node: StableHashMap::default(),
        instances: StableHashMap::default(),
        names: Names::default(),
        concept_forms: StableHashMap::default(),
        concept_columns: StableHashMap::default(),
        concept_examples: StableHashMap::default(),
        atoms: Vec::new(),
        sides: Vec::new(),
        examples: Vec::new(),
        form_sides: StableHashMap::default(),
        clauses: Vec::new(),
        resolutions: StableHashMap::default(),
        signatures: StableHashMap::default(),
        positions: StableHashMap::default(),
        groups: StableHashMap::default(),
        proposer_columns: StableHashMap::default(),
        diagnostics: Vec::new(),
    };
    for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput] {
        let node = builder.node(DependencyKind::Fact(fact), &NameScope::Program, None);
        let columns = Columns::of_names(registry.fact_columns(fact).iter().map(|column| column.name.clone()));
        builder.target(&NameScope::Program, RelationRef::Fact(fact), Target { node, columns: ColumnsOf::Fixed(columns) });
    }
    if let Some(concept) = concept {
        builder.take_concept(concept);
    }
    let forms = &case.value().forms;
    let mut pending = Vec::new();
    for (index, form) in forms.iter().enumerate() {
        builder.declare(form, top(index), &NameScope::Program, &mut pending);
    }
    for (scope, relation, target) in pending {
        builder.target(&scope, relation, target);
    }
    for (index, form) in forms.iter().enumerate() {
        builder.read_form(form, top(index), &NameScope::Program);
    }
    builder.sides();
    builder.contents();
    builder.sites();
    builder.proposers();
    if let Some(concept) = concept {
        builder.copy_concept(concept);
    }
    builder.finish()
}

fn top(index: usize) -> NodePath {
    NodePath(Box::new([crate::program::path::PathStep(index as u32)]))
}

/// `path` with its prefix `from` replaced by `to`, where `from` is a
/// prefix of it.
fn rebase(path: &NodePath, from: &NodePath, to: &NodePath) -> Option<NodePath> {
    path.0.strip_prefix(&from.0[..]).map(|rest| to.join(&NodePath(rest.into())))
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
    fn node(&mut self, kind: DependencyKind, scope: &NameScope, form: Option<&NodePath>) -> GraphNodeIndex {
        let key = DependencyNode { kind, scope: scope.clone() };
        let node = match self.index.get(&key) {
            Some(node) => *node,
            None => {
                let node = GraphNodeIndex(self.nodes.len() as u32);
                self.index.insert(key.clone(), node);
                self.nodes.push(key);
                self.forms.push(Vec::new());
                self.reads.push(BTreeSet::new());
                node
            }
        };
        if let Some(form) = form {
            self.forms[node.0 as usize].push(form.clone());
        }
        node
    }

    fn target(&mut self, scope: &NameScope, relation: RelationRef, target: Target) {
        self.names.scopes.entry(scope.clone()).or_default().insert(relation, target);
    }

    fn read(&mut self, reader: GraphNodeIndex, read: GraphNodeIndex) {
        self.reads[reader.0 as usize].insert(read.0);
    }

    fn unresolved(&mut self, path: &NodePath, name: &str) -> Resolution {
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
    fn take_concept(&mut self, concept: ConceptReads<'_>) {
        let concept_forms = &concept.concept.program.value().forms;
        for path in concept.determinations {
            let Some(Form::Clause(clause)) = path.0.first().and_then(|step| self.case.value().forms.get(step.0 as usize)) else { continue };
            let Some(index) = concept_forms.iter().position(|form| matches!(form, Form::Clause(other) if other == clause)) else { continue };
            let concept_path = top(index);
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
    fn copy_concept(&mut self, concept: ConceptReads<'_>) {
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
    fn declare(&mut self, form: &'a Form, path: NodePath, scope: &NameScope, pending: &mut Vec<(NameScope, RelationRef, Target)>) {
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
                pending.push((scope.clone(), relation_of(&clause.derives), Target { node, columns: ColumnsOf::OfNode }));
                if !self.concept_forms.contains_key(&path) {
                    self.clauses.push((path, clause));
                }
            }
            Form::Choose(choose) => {
                let name = &choose.value().name;
                let node = self.node(DependencyKind::Chosen(name.clone()), scope, Some(&path));
                self.form_node.insert(path, node);
                pending.push((scope.clone(), RelationRef::Declared(name.clone()), Target { node, columns: ColumnsOf::OfNode }));
            }
            Form::Demonstrated(demonstrated) => {
                let demonstrated = demonstrated.value();
                let node = self.node(DependencyKind::Demonstrated(demonstrated.name.clone()), scope, Some(&path));
                self.form_node.insert(path.clone(), node);
                let columns = ColumnsOf::Fixed(columns::demonstrated_columns(demonstrated));
                pending.push((scope.clone(), RelationRef::Declared(demonstrated.name.clone()), Target { node, columns }));
                for (rule_path, rule) in super::demo_rules(demonstrated, &path) {
                    let rule_scope = NameScope::DemoRule(rule_path.clone());
                    for (index, form) in rule.forms.iter().enumerate() {
                        self.declare(form, rule_path.child(index as u32), &rule_scope, pending);
                    }
                }
            }
            Form::RigidDet(rigid) => {
                let rigid = rigid.value();
                let node = self.node(DependencyKind::RigidAssembly(rigid.name.clone()), scope, Some(&path));
                self.form_node.insert(path, node);
                for (steps, columns) in columns::rigid_outputs(rigid) {
                    let relation = RelationRef::Output(OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path: steps });
                    self.target(scope, relation, Target { node, columns: ColumnsOf::Fixed(columns) });
                }
            }
            Form::Instance(instance) => self.declare_instance(instance.value(), path, scope),
        }
    }

    /// Declares the nodes of an `INIT` form: one node for an instance
    /// whose inputs read its outputs, and otherwise a node per input it
    /// writes and per output, each output reading every input.
    fn declare_instance(&mut self, instance: &'a Instance, path: NodePath, scope: &NameScope) {
        let Some(component) = columns::component(self.registry, &instance.component) else {
            let resolution = self.unresolved(&path, &instance.component.0);
            self.resolutions.insert(path, resolution);
            return;
        };
        self.resolutions.insert(path.clone(), Resolution::Lib(instance.component.clone()));
        let name = &instance.name;
        let written: Vec<_> = crate::program::written_inputs(instance.key.as_ref(), &instance.inputs).collect();
        let mut inputs = Vec::new();
        let mut outputs = Vec::new();
        if component.inputs.iter().any(|input| input.reads_outputs) {
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
            let columns = columns::port_columns(&input.port, &bindings);
            let read = inputs.iter().find(|(port, _)| *port == input.port.name);
            if let Some((port, node)) = read.filter(|(port, _)| !component.outputs.iter().any(|output| output.name == *port)) {
                self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
            }
            port_columns.insert(input.port.name.clone(), columns);
        }
        for (output, (port, node)) in component.outputs.iter().zip(&outputs) {
            let columns = columns::port_columns(output, &bindings);
            self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
            port_columns.insert(port.clone(), columns);
        }
        self.instances.insert((scope.clone(), name.clone()), InstanceNodes { inputs, outputs, columns: port_columns, component });
    }

    /// Resolves the reads of `form` at `path` in `scope`, and adds each
    /// to the graph as an edge from the node read to the node that reads
    /// it.
    fn read_form(&mut self, form: &'a Form, path: NodePath, scope: &NameScope) {
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
                    if !columns::is_proposer(self.registry, proposer) {
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
                let mut before = 0;
                if let Some(key) = &demonstrated.key {
                    self.read_below(NodeRef::KeyClause(key.value()), path.child(0), scope, &[node], &path);
                    before = 1;
                }
                for (index, input) in demonstrated.inputs.iter().enumerate() {
                    self.read_below(NodeRef::InstanceInput(input.value()), path.child(before + index as u32), scope, &[node], &path);
                }
                for (rule_path, rule) in super::demo_rules(demonstrated, &path) {
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

    /// Adds the edges of a clause on a port of an instance: the
    /// instance reads a clause on one of its inputs, as a
    /// `DET_OR_RULE` line on `&canvas.extent`, and a clause on one of its
    /// outputs, as a `RULE_OR_DET` line on `&ring.value`, reads that
    /// output.
    fn read_instance_line(&mut self, clause: &Clause, node: GraphNodeIndex, scope: &NameScope) {
        let ProgramRelation::Output(output) = &clause.derives else { return };
        let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return };
        let Some(nodes) = self.instances.get(&(scope.clone(), name.clone())) else { return };
        let edges: Vec<(GraphNodeIndex, GraphNodeIndex)> = if nodes.component.inputs.iter().any(|input| input.port.name == *port) {
            nodes.outputs.iter().map(|(_, output)| (*output, node)).collect()
        } else {
            nodes.outputs.iter().filter(|(name, _)| name == port).map(|(_, output)| (node, *output)).collect()
        };
        for (reader, read) in edges {
            if reader != read {
                self.read(reader, read);
            }
        }
    }

    /// Resolves each atom below `node`, at `path`, as read by each node
    /// of `readers` in the form at `form`.
    fn read_below(&mut self, node: NodeRef<'a>, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex], form: &NodePath) {
        match node {
            NodeRef::Conjunct(Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) => self.read_atom(atom.value(), path, scope, readers, form),
            NodeRef::Atom(atom) => self.read_atom(atom, path, scope, readers, form),
            NodeRef::DemoRule(_) => {}
            _ => {
                for (index, child) in node.children().into_iter().enumerate() {
                    self.read_below(child, path.child(index as u32), scope, readers, form);
                }
            }
        }
    }

    fn read_atom(&mut self, atom: &'a Atom, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex], form: &NodePath) {
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

    fn resolve_name(&mut self, scope: &NameScope, relation: &RelationRef, path: &NodePath) -> Resolution {
        let name = || crate::write::relation_ref(relation);
        let program_relation = match relation {
            RelationRef::Lib(lib) => {
                if self.registry.entry(lib).is_none() {
                    return self.unresolved(path, &name());
                }
                if let Some(columns) = columns::lib_columns(self.registry, lib) {
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

    /// The content and the columns of each node, each node after the
    /// nodes it reads, where no cycle holds it.
    fn contents(&mut self) {
        self.names.contents = vec![None; self.nodes.len()];
        self.names.node_columns = vec![None; self.nodes.len()];
        let mut visited = vec![false; self.nodes.len()];
        for node in 0..self.nodes.len() {
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
        let (content, columns) = self.node_content(node);
        self.names.contents[node] = Some(content);
        self.names.node_columns[node] = columns;
    }

    /// The content of `node`: its kind and its forms, each written
    /// through the resolver's name writer, with no order; and its
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
            let bytes = match self.names.fixed.get(path) {
                Some(content) => content.bytes.clone(),
                None => super::names::written(form, path, None, &writer).expect("a form has a canonical form").bytes,
            };
            let columns = match form {
                NodeRef::Clause(clause) => match self.concept_columns.get(path) {
                    Some(columns) => columns.clone(),
                    None => self.clause_columns(clause, scope, &writer),
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

    /// The columns of the relation a clause derives: its labels in their
    /// canonical positions; or, with no columns of its own, its first
    /// proposer's, or the output's of an instance it stands for.
    fn clause_columns(&self, clause: &Clause, scope: &NameScope, writer: &Writer<'_>) -> Option<Columns> {
        if !clause.columns.is_empty() {
            let labeling = canonical_labeling(LabelScope::Clause(clause), writer, &mut SearchBudget::new());
            return Some(ordered(&clause.columns, &labeling));
        }
        if let Some(proposer) = clause.proposers.first() {
            return columns::proposer_columns(self.registry, proposer).map(|names| Columns::of_names(names.into_vec()));
        }
        if let ProgramRelation::Output(OutputName { of: OutputOwner::Instance(name), path }) = &clause.derives {
            if let [OutputStep::Port(port)] = &path[..] {
                return self.instances.get(&(scope.clone(), name.clone())).and_then(|nodes| nodes.columns.get(port)).cloned();
            }
        }
        Some(Columns::default())
    }

    /// The position and the group of each site of each atom read, and
    /// the signature of each name read.
    fn sites(&mut self) {
        let atoms = std::mem::take(&mut self.atoms);
        for AtomRead { path, atom, scope, form } in &atoms {
            let mut columns = self.names.columns(scope, &atom.relation).cloned();
            if self.lifts(form, &self.resolutions[path]) {
                columns = columns.map(|found| found.lifted());
            }
            if let Some(columns) = &columns {
                for (index, site) in atom.sites.iter().enumerate() {
                    self.place_site(columns, site, path.child(index as u32));
                }
            }
            let signature = self.signature(&self.resolutions[path], &atom.relation, columns.as_ref());
            self.signatures.insert(path.clone(), signature);
        }
    }

    /// Whether the form at `form` reads, in its lifted form, the relation
    /// a read that resolves to `resolution` reads: where the form is
    /// task-wide and that relation is a per-input relation of the case.
    fn lifts(&self, form: &NodePath, resolution: &Resolution) -> bool {
        let Resolution::Node(read) = resolution else { return false };
        lifted(self.is_fact(*read), self.form_sides[form], self.sides[read.0 as usize])
    }

    fn is_fact(&self, node: GraphNodeIndex) -> bool {
        matches!(self.nodes[node.0 as usize].kind, DependencyKind::Fact(_))
    }

    /// The side of each node and of each form whose reads the case
    /// resolves.
    fn sides(&mut self) {
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
        let examples = (0..self.nodes.len()).map(|node| sides.examples(node)).collect();
        let form_sides = sides.forms.into_iter().map(|(path, side)| (path, side.expect(decided))).collect();
        self.sides = node_sides;
        self.examples = examples;
        self.form_sides = form_sides;
    }

    fn place_site(&mut self, columns: &Columns, site: &crate::program::Site, path: NodePath) {
        use crate::program::SiteArg;
        match columns.place(std::slice::from_ref(&site.column)) {
            Some(Place::Column(position)) => {
                for (index, arg) in site.value.args.iter().enumerate() {
                    if let SiteArg::NamedLabel { .. } = arg {
                        self.positions.insert(path.child(index as u32), position);
                    }
                }
                self.positions.insert(path, position);
            }
            Some(Place::Group(group)) => {
                for (index, arg) in site.value.args.iter().enumerate() {
                    let field = match arg {
                        SiteArg::NamedLabel { name, .. } => name,
                        SiteArg::Field(field) => &field.column,
                        SiteArg::Label(_) => continue,
                    };
                    if let Some(Place::Field(position, group)) = columns.place(&[site.column.clone(), field.clone()]) {
                        self.positions.insert(path.child(index as u32), position);
                        self.groups.insert(path.child(index as u32), group);
                    }
                }
                self.groups.insert(path, group);
            }
            Some(Place::Field(..)) | None => {}
        }
    }

    /// The signature of a read of `relation` that resolves to
    /// `resolution`: the content of what it resolves to, and its
    /// columns.
    fn signature(&self, resolution: &Resolution, relation: &RelationRef, columns: Option<&Columns>) -> Signature {
        let mut out = CanonicalWriter::default();
        match resolution {
            Resolution::Node(node) => {
                out.write(&[0]);
                let content = self.names.contents[node.0 as usize].as_ref().expect("the content of each node");
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

    /// The stored parameter's column that each column of each proposer
    /// of each clause stands for, by position: the clause's columns in
    /// the order it gives them, or, with none, its first proposer's.
    fn proposers(&mut self) {
        for (path, clause) in std::mem::take(&mut self.clauses) {
            let first = clause.proposers.first().and_then(|proposer| columns::proposer_columns(self.registry, proposer));
            let stored: Box<[ColumnName]> = if clause.columns.is_empty() {
                first.unwrap_or_default()
            } else {
                clause.columns.iter().map(|column| column.name.clone()).collect()
            };
            for (index, proposer) in clause.proposers.iter().enumerate() {
                if let Some(own) = columns::proposer_columns(self.registry, proposer) {
                    let mapped = own.iter().zip(stored.iter()).map(|(_, name)| name.clone()).collect();
                    self.proposer_columns.insert((path.clone(), index), mapped);
                }
            }
        }
    }

    fn finish(self) -> WithDiagnostics<ResolvedProgram> {
        let graph = DependencyGraph {
            nodes: self.nodes.into(),
            reads: self.reads.into_iter().map(|reads| reads.into_iter().map(GraphNodeIndex).collect()).collect(),
        };
        let forms = self.forms.into_iter().map(|forms| forms.into_iter().next().unwrap_or_default()).collect();
        WithDiagnostics {
            value: ResolvedProgram {
                program: self.case.clone(),
                graph,
                forms,
                sides: self.sides.into(),
                examples: self.examples.into(),
                resolutions: self.resolutions,
                signatures: self.signatures,
                positions: self.positions,
                groups: self.groups,
                proposer_columns: self.proposer_columns,
                names: self.names,
            },
            diagnostics: self.diagnostics,
        }
    }
}

/// Whether a form of side `form` reads, in its lifted form, a relation
/// of side `read` that is a fact where `fact` holds.
fn lifted(fact: bool, form: Side, read: Side) -> bool {
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

/// The sides of the nodes of a case, each decided once, a form's after
/// the sides of the nodes it reads, as `docs/arclog/arclog.md#program`
/// and `#instance` give, and the columns of each node that hold an
/// Example, by which a key's Example labels are told.
struct Sides<'b, 'a> {
    builder: &'b Builder<'a>,
    /// The index in [`Builder::atoms`] of each atom of each form.
    reads: StableHashMap<NodePath, Vec<usize>>,
    /// The side of each form, `None` while it is being decided, so that a
    /// read on a cycle, which the checker refuses, decides nothing.
    forms: StableHashMap<NodePath, Option<Side>>,
    /// The columns of each node that hold an Example, empty while they
    /// are being decided, so that a read on a cycle gives none.
    examples: StableHashMap<usize, Arc<[ExamplePath]>>,
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

    /// The side of an `INIT`, a `CHOOSE` or a `DEMONSTRATED` form at
    /// `path`. A form whose key holds a label that
    /// [`Sides::key_examples`] gives is per example, and task-wide,
    /// whatever its bodies read. Any other form takes its side by what
    /// its bodies read: task-wide where they read
    /// `ex_input`, `ex_output`, or a per-input relation at a site on `E`;
    /// per input where they read, with no such read, `input` or a
    /// per-input relation; and task-wide otherwise, pooled over the
    /// examples. A read of the form's own nodes, as an `Unfold`
    /// instance's of its outputs, counts toward neither side.
    fn read_side(&mut self, path: &NodePath) -> Side {
        let builder = self.builder;
        if !self.key_examples(path).is_empty() {
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

    /// The columns of `node`, a node of the case, that hold an Example: a
    /// clause relation's columns whose label a body of its clause binds
    /// at a site that holds an Example, as [`Sides::bound_examples`]
    /// gives; those the concept program gives a relation that a form
    /// resolving there derives; those [`Sides::choose_examples`] gives
    /// of a chosen relation; those [`Sides::instance_examples`] gives of
    /// an instance output; the fields that [`Sides::key_examples`] gives
    /// of the key record of a `DEMONSTRATED` relation and of a
    /// `RIGID_DET` output; and those [`Sides::head_examples`] gives of
    /// each column of a `DEMONSTRATED` relation after the key.
    fn examples(&mut self, node: usize) -> Arc<[ExamplePath]> {
        if let Some(found) = self.examples.get(&node) {
            return found.clone();
        }
        self.examples.insert(node, Arc::from([]));
        let builder = self.builder;
        let program = NodeRef::Program(builder.case.value());
        let DependencyNode { kind, scope } = &builder.nodes[node];
        let mut found: Vec<ExamplePath> = Vec::new();
        match kind {
            DependencyKind::InstanceOutput { instance, output } => found.extend(self.instance_examples(scope, instance, Some(output))),
            DependencyKind::RecursiveInstance(instance) => found.extend(self.instance_examples(scope, instance, None)),
            DependencyKind::Chosen(_) if matches!(builder.forms[node].first().and_then(|form| node_at(program, form)), Some(NodeRef::Choose(_))) => {
                let form = builder.forms[node].first().expect("a form of each chosen relation").clone();
                found.extend(self.choose_examples(&form));
            }
            DependencyKind::Demonstrated(_) => {
                let form = builder.forms[node].first().expect("a form of each node of a `DEMONSTRATED` form").clone();
                found.extend(self.key_examples(&form).into_iter().map(|field| Box::from([columns::key(), field])));
                let Some(NodeRef::Demonstrated(demonstrated)) = node_at(program, &form) else {
                    unreachable!("the form of a `DEMONSTRATED` relation is a `DEMONSTRATED` form")
                };
                if let Some(value) = columns::demonstrated_value(demonstrated) {
                    for site in value.head.iter() {
                        let paths = self.head_examples(&form, value, site);
                        found.extend(paths.into_iter().map(|path| prefixed(&site.column, path)));
                    }
                }
            }
            DependencyKind::RigidAssembly(_) => {
                let form = builder.forms[node].first().expect("a form of each node of a `RIGID_DET` form").clone();
                found.extend(self.key_examples(&form).into_iter().map(|field| Box::from([columns::key(), field])));
            }
            _ => {
                for path in &builder.forms[node] {
                    if let Some(concept) = builder.concept_examples.get(path) {
                        found.extend(concept.iter().cloned());
                        continue;
                    }
                    let Some(NodeRef::Clause(clause)) = node_at(program, path) else { continue };
                    let labels = self.bound_examples(path, &path.child(0));
                    let held = clause.columns.iter().filter(|column| labels.contains(&column.label));
                    found.extend(held.map(|column| Box::from([column.name.clone()])));
                }
            }
        }
        let mut distinct: Vec<ExamplePath> = Vec::new();
        for path in found {
            if !distinct.contains(&path) {
                distinct.push(path);
            }
        }
        let found: Arc<[ExamplePath]> = distinct.into();
        self.examples.insert(node, found.clone());
        found
    }

    /// The columns of the relation of the `CHOOSE` form at `form` that
    /// hold an Example: each row column whose label the `for` body binds
    /// at a site that holds an Example, and each candidate column whose
    /// label the `from` body binds at one.
    fn choose_examples(&mut self, form: &NodePath) -> Vec<ExamplePath> {
        let Some(NodeRef::Choose(choose)) = node_at(NodeRef::Program(self.builder.case.value()), form) else { return Vec::new() };
        let from = match &choose.rows {
            Some(_) => form.child(1),
            None => form.child(0),
        };
        let mut parts: Vec<(&[crate::program::RelationColumn], NodePath)> = vec![(&choose.candidate_columns[..], from)];
        if let Some(rows) = &choose.rows {
            parts.insert(0, (&rows.columns[..], form.child(0)));
        }
        let mut found = Vec::new();
        for (columns, body) in parts {
            let bound = self.bound_examples(form, &body);
            found.extend(columns.iter().filter(|column| bound.contains(&column.label)).map(|column| Box::from([column.name.clone()])));
        }
        found
    }

    /// The columns of the output `output` of the instance `instance` in
    /// `scope`, or of each of its outputs where `output` is `None`, that
    /// hold an Example: below each column of a type parameter, the paths
    /// that [`Sides::binding_examples`] gives of the parameter's binding.
    fn instance_examples(&mut self, scope: &NameScope, instance: &InstanceName, output: Option<&PortName>) -> Vec<ExamplePath> {
        let builder = self.builder;
        let Some(nodes) = builder.instances.get(&(scope.clone(), instance.clone())) else { return Vec::new() };
        let Some(form) = nodes.outputs.first().and_then(|(_, node)| builder.forms[node.0 as usize].first()) else { return Vec::new() };
        let form = form.clone();
        let Some(NodeRef::Instance(written)) = node_at(NodeRef::Program(builder.case.value()), &form) else { return Vec::new() };
        let mut found = Vec::new();
        for sites in binding_sites(written, &nodes.component.inputs) {
            let paths = self.binding_examples(&form, sites.binding);
            let ports = nodes.component.outputs.iter().filter(|port| output.is_none_or(|output| port.name == *output));
            let bound = ports.flat_map(|port| port.columns.iter()).filter(|column| column.ty == ColumnType::Parameter(sites.parameter.clone()));
            for column in bound {
                found.extend(paths.iter().map(|path| prefixed(&column.name, path.clone())));
            }
        }
        found
    }

    /// The paths below a column of the type parameter that `binding` of
    /// the `INIT` form at `form` binds that hold an Example: each field
    /// of the key that [`Sides::key_examples`] gives, where the key
    /// clause binds it, and those [`Sides::head_examples`] gives, where
    /// a head site binds it.
    fn binding_examples(&mut self, form: &NodePath, binding: ParameterSite<'_>) -> Vec<ExamplePath> {
        match binding {
            ParameterSite::Key(_) => self.key_examples(form).into_iter().map(|field| Box::from([field])).collect(),
            ParameterSite::Head { input, site } => self.head_examples(form, input, site),
        }
    }

    /// The paths below the column of the head site `site` of the input
    /// `input` of the form at `form` that hold an Example, by the
    /// labels that the input's body binds at a site that holds one, as
    /// [`Sides::bound_examples`] gives: the whole column, where the
    /// site projects one such label, and each field whose label is one,
    /// where it projects a record, `docs/arclog/arclog.md#instance`.
    fn head_examples(&mut self, form: &NodePath, input: &InstanceInput, site: &Site) -> Vec<ExamplePath> {
        let program = NodeRef::Program(self.builder.case.value());
        let bound = self.bound_examples(form, &input_body(program, form, input));
        let whole = columns::projection(site).is_none();
        let mut found = Vec::new();
        each_site_label(site, &mut Vec::new(), &mut |use_, path| {
            if use_label(use_).is_some_and(|label| bound.contains(&label)) {
                let path: ExamplePath = if whole { Box::from([]) } else { path[1..].into() };
                if !found.contains(&path) {
                    found.push(path);
                }
            }
        });
        found
    }

    /// The fields of the key of the `INIT`, `DEMONSTRATED` or
    /// `RIGID_DET` form at `form` whose label the key's body binds at a
    /// site that holds an Example; none where the form has no key.
    fn key_examples(&mut self, form: &NodePath) -> Vec<ColumnName> {
        let (key, body) = match node_at(NodeRef::Program(self.builder.case.value()), form) {
            Some(NodeRef::Instance(Instance { key: Some(key), .. })) | Some(NodeRef::Demonstrated(Demonstrated { key: Some(key), .. })) => {
                (&key.value().key, form.child(0).child(0))
            }
            Some(NodeRef::RigidDet(RigidDet { key: Some(key), .. })) => (key, form.child(0)),
            _ => return Vec::new(),
        };
        let bound = self.bound_examples(form, &body);
        key.columns.iter().filter(|column| bound.contains(&column.label)).map(|column| column.name.clone()).collect()
    }

    /// The labels that the atoms of the form at `form` below `body`
    /// bind at a site that holds an Example: a site on a column of the
    /// type `Example` that [`columns::typed_columns`] gives; on
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
            let typed = columns::typed_columns(builder.registry, &read.atom.relation).unwrap_or_default();
            let mut held: Vec<ExamplePath> = columns::examples(typed).map(|name| Box::from([name])).collect();
            if let Resolution::Node(read_node) = builder.resolutions[&read.path] {
                let node = read_node.0 as usize;
                held.extend(self.examples(node).iter().cloned());
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

/// `path` below the column `column`.
fn prefixed(column: &ColumnName, path: ExamplePath) -> ExamplePath {
    std::iter::once(column.clone()).chain(path).collect()
}

/// The path of the body of `input`, an input of the form at `form`
/// below `program`, written after the form's key clause or inside it.
fn input_body(program: NodeRef<'_>, form: &NodePath, input: &InstanceInput) -> NodePath {
    let child = NodeRef::InstanceInput(input);
    let at = |path: &NodePath| node_at(program, path).expect("the path of a form of the case or of its key clause");
    let path = match child_index(at(form), child) {
        Some(index) => form.child(index),
        None => {
            let key = form.child(0);
            key.child(child_index(at(&key), child).expect("an input of the form, after its key clause or inside it"))
        }
    };
    path.child(u32::try_from(input.head.len()).expect("a head of fewer than 2^32 sites"))
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
    let rows = choose.rows.iter().flat_map(|rows| rows.columns.iter()).map(|column| column.name.clone());
    let candidate = ordered(&choose.candidate_columns, &labeling);
    Columns::of_names(rows.chain(candidate.names().cloned()))
}
