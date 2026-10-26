//! The Ident columns of a `RIGID_DET` assembly's parts and key that are the
//! assembly's own (`docs/arclog/rigid.md#the-pose`): a column is the
//! assembly's own where no label at it stands at an Ident site outside the
//! assembly's parts and key and the relations that take their types from
//! them, other than a site in the body of a determination relation that a
//! `key` or `instance` clause of the assembly reads, directly or through
//! the bodies of the determination relations those read.
//!
//! The analysis joins places that hold one Ident: a label of a form's
//! label scope, a column of a relation that a clause, a `CHOOSE` form or an
//! instance's input or output gives, a column of an assembly's output, and
//! a field of a type parameter of an `INIT` form. A label joins the column
//! at each site it stands at, and two labels join at `=`. A site of a
//! relation that no form of the program derives, such as a lib relation, a
//! fact, a column of an instance's output that its component declares with
//! a fixed type, or the head of an instance's input at such a column, joins
//! a place that stands outside every assembly. The own Idents of an
//! assembly are the part and key labels whose joined places hold no such
//! outside place, and no part or key label of another assembly.

use std::collections::BTreeSet;
use std::sync::Arc;

use crate::hash::{StableHashMap, StableHashSet};
use crate::program::canonical::shares_rule_scope;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, ColumnName, Conjunct, ConstraintOp, InstanceName, LabelId, NameScope, Operand, OutputStep, PortName, ProgramRelation, RigidDet,
    RigidDetName, Site,
};
use crate::registry::{binding_sites, is_key, ColumnType, Component, ParameterSite, Registry, TypeParameter};
use crate::resolver::{columns, form_columns, registry_columns, DependencyKind, Resolution, ResolvedProgram};
use crate::types::{each_site_label, use_label};

/// The labels at the part sites and key columns of each `RIGID_DET` form
/// of `program`, by the form's path, that are the assembly's own Idents.
pub fn own_idents(program: &ResolvedProgram, registry: &Registry) -> StableHashMap<NodePath, StableHashSet<LabelId>> {
    let mut places = Places::new(program, registry);
    let root = NodeRef::Program(program.program.value());
    for (child, index) in root.children().into_iter().zip(0u32..) {
        places.visit(child, &NodePath::top(index), &Context::top(index));
    }
    places.assemblies()
}

/// A place that holds one Ident.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum Place {
    /// A place outside every assembly.
    Outside,
    /// A label of the label scope that the path names.
    Label(NodePath, LabelId),
    /// The column of a relation a clause or a `CHOOSE` form derives.
    Column(ProgramRelation, NameScope, ColumnName),
    /// The column of an output of a `RIGID_DET` form.
    Output(RigidDetName, Arc<[OutputStep]>, ColumnName),
    /// The field at the path of a value of a type parameter of an `INIT`
    /// form's component, where the form's key, inputs and outputs all name
    /// the value.
    Parameter(InstanceName, TypeParameter, Box<[ColumnName]>),
}

/// Two places that hold one Ident, and, for a join that a read in the body
/// of a clause makes, the relation that clause derives.
struct Join {
    a: usize,
    b: usize,
    in_body_of: Option<ProgramRelation>,
}

/// The part and key labels of one `RIGID_DET` form.
struct Parts {
    form: NodePath,
    labels: Vec<(LabelId, usize)>,
    /// The relations that its `key` and `instance` clauses read.
    reads: Vec<ProgramRelation>,
}

/// Where a visited node stands.
#[derive(Clone)]
struct Context {
    /// The path of the label scope.
    scope: NodePath,
    names: NameScope,
    /// The relation of the clause whose body the node stands in, for a
    /// clause of the program's name scope.
    body_of: Option<ProgramRelation>,
    /// The index among the program's `RIGID_DET` forms whose `key` or
    /// `instance` clause the node stands in.
    read_by: Option<usize>,
}

impl Context {
    fn top(index: u32) -> Self {
        Context { scope: NodePath::top(index), names: NameScope::Program, body_of: None, read_by: None }
    }
}

struct Places<'a> {
    program: &'a ResolvedProgram,
    registry: &'a Registry,
    ids: StableHashMap<Place, usize>,
    joins: Vec<Join>,
    parts: Vec<Parts>,
    instances: StableHashMap<InstanceName, &'a Component>,
    /// Each pair of relations where a clause's body of the first reads the
    /// second.
    calls: Vec<(ProgramRelation, ProgramRelation)>,
}

impl<'a> Places<'a> {
    fn new(program: &'a ResolvedProgram, registry: &'a Registry) -> Self {
        let mut places = Places { program, registry, ids: StableHashMap::default(), joins: Vec::new(), parts: Vec::new(), instances: StableHashMap::default(), calls: Vec::new() };
        places.id(Place::Outside);
        places.find_instances(NodeRef::Program(program.program.value()));
        places
    }

    /// The number of `place`.
    fn id(&mut self, place: Place) -> usize {
        let next = self.ids.len();
        *self.ids.entry(place).or_insert(next)
    }

    fn join(&mut self, a: usize, b: usize, ctx: &Context) {
        self.joins.push(Join { a, b, in_body_of: ctx.body_of.clone() });
    }

    /// Joins `label` of the context's scope with `place`.
    fn join_label(&mut self, ctx: &Context, label: LabelId, place: Place) {
        let label = self.id(Place::Label(ctx.scope.clone(), label));
        let place = self.id(place);
        self.joins.push(Join { a: label, b: place, in_body_of: None });
    }

    /// The component of each `INIT` form under `node`, by the form's name.
    fn find_instances(&mut self, node: NodeRef<'a>) {
        if let NodeRef::Instance(instance) = node {
            if let Some(component) = registry_columns::component(self.registry, &instance.component) {
                self.instances.insert(instance.name.clone(), component);
            }
        }
        for child in node.children() {
            self.find_instances(child);
        }
    }

    fn visit(&mut self, node: NodeRef<'a>, at: &NodePath, ctx: &Context) {
        if let Some(atom) = node.atom() {
            return self.atom(atom, at, ctx);
        }
        let mut ctx = ctx.clone();
        match node {
            NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
                if let (ConstraintOp::Eq, Operand::Label(second)) = (constraint.op, constraint.second) {
                    let (a, b) = (self.id(Place::Label(ctx.scope.clone(), constraint.first.label)), self.id(Place::Label(ctx.scope.clone(), second.label)));
                    self.joins.push(Join { a, b, in_body_of: None });
                }
                return;
            }
            NodeRef::Clause(clause) => {
                let scope = self.names_of(at);
                for column in clause.columns.iter() {
                    self.join_label(&ctx, column.label, Place::Column(clause.derives.clone(), scope.clone(), column.name.clone()));
                }
                ctx.body_of = (scope == NameScope::Program).then(|| clause.derives.clone());
            }
            NodeRef::Choose(choose) => {
                let scope = self.names_of(at);
                for column in form_columns::form_columns(node) {
                    let relation = ProgramRelation::Declared(choose.name.clone());
                    self.join_label(&ctx, column.label, Place::Column(relation, scope.clone(), column.name.clone()));
                }
            }
            NodeRef::Instance(instance) => self.instance(instance, &ctx),
            NodeRef::RigidDet(rigid) => return self.rigid(node, rigid, at, &ctx),
            NodeRef::DemoRule(rule) => {
                ctx.names = NameScope::DemoRule(at.clone());
                for (form, index) in rule.forms.iter().zip(0u32..) {
                    let scope = if shares_rule_scope(rule, index as usize) { at.clone() } else { at.child(index) };
                    self.visit(NodeRef::from(form), &at.child(index), &Context { scope, ..ctx.clone() });
                }
                return;
            }
            _ => {}
        }
        self.children(node, at, &ctx);
    }

    fn children(&mut self, node: NodeRef<'a>, at: &NodePath, ctx: &Context) {
        for (child, index) in node.children().into_iter().zip(0u32..) {
            self.visit(child, &at.child(index), ctx);
        }
    }

    /// The name scope of the form at `at`.
    fn names_of(&self, at: &NodePath) -> NameScope {
        match self.program.nodes_of(at).first() {
            Some(node) => self.program.graph.nodes[node.0 as usize].scope.clone(),
            None => NameScope::Program,
        }
    }

    /// The part and key labels of a `RIGID_DET` form, and the reads of its
    /// `key` and `instance` clauses.
    fn rigid(&mut self, node: NodeRef<'a>, rigid: &'a RigidDet, at: &NodePath, ctx: &Context) {
        let form = self.parts.len();
        let mut parts = Parts { form: at.clone(), labels: Vec::new(), reads: Vec::new() };
        for part in rigid.parts.iter() {
            let part = part.value();
            let Some(steps) = form_columns::part_steps(&part.relation) else { continue };
            let steps: Arc<[OutputStep]> = steps.into();
            for site in part.sites.iter().filter(|site| !form_columns::at_instance(rigid, site)) {
                each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                    let Some(label) = use_label(use_) else { return };
                    let label = self.id(Place::Label(ctx.scope.clone(), label));
                    let output = self.id(Place::Output(rigid.name.clone(), steps.clone(), path[0].clone()));
                    self.joins.push(Join { a: label, b: output, in_body_of: None });
                    parts.labels.push((use_label(use_).expect("a label use"), label));
                });
            }
        }
        for column in rigid.instance.iter().flat_map(|instance| instance.columns.iter()) {
            self.join_label(ctx, column.label, Place::Output(rigid.name.clone(), Arc::from([OutputStep::Pose]), column.name.clone()));
        }
        let outputs = rigid.parts.iter().filter_map(|part| form_columns::part_steps(&part.value().relation)).map(Arc::<[OutputStep]>::from).chain([Arc::from([OutputStep::Pose])]);
        let outputs: Vec<_> = outputs.collect();
        for column in rigid.key.iter().flat_map(|key| key.columns.iter()) {
            let label = self.id(Place::Label(ctx.scope.clone(), column.label));
            for steps in &outputs {
                let output = self.id(Place::Output(rigid.name.clone(), steps.clone(), columns::key()));
                self.joins.push(Join { a: label, b: output, in_body_of: None });
            }
            parts.labels.push((column.label, label));
        }
        self.parts.push(parts);
        let instance_child = u32::from(rigid.key.is_some());
        for (child, index) in node.children().into_iter().zip(0u32..) {
            let reads = (rigid.key.is_some() && index == 0) || (rigid.instance.is_some() && index == instance_child);
            self.visit(child, &at.child(index), &Context { read_by: reads.then_some(form).or(ctx.read_by), ..ctx.clone() });
        }
    }

    /// The joins of an `INIT` form's key and input heads with the fields of
    /// the type parameters of its component.
    fn instance(&mut self, instance: &'a crate::program::Instance, ctx: &Context) {
        let Some(&component) = self.instances.get(&instance.name) else { return };
        let sites = binding_sites(instance, &component.inputs);
        for sites in &sites {
            let heads: Vec<&Site> = match sites.binding {
                ParameterSite::Key(key) => {
                    for column in key.key.columns.iter() {
                        let place = Place::Parameter(instance.name.clone(), sites.parameter.clone(), Box::from([column.name.clone()]));
                        self.join_label(ctx, column.label, place);
                    }
                    Vec::new()
                }
                ParameterSite::Head { site, .. } => vec![site],
            };
            for site in heads.into_iter().chain(sites.later.iter().map(|(_, site)| *site)) {
                each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                    if let Some(label) = use_label(use_) {
                        let place = Place::Parameter(instance.name.clone(), sites.parameter.clone(), path[1..].into());
                        self.join_label(ctx, label, place);
                    }
                });
            }
        }
        let bound = |input: &crate::program::InstanceInput, site: &Site| {
            component.inputs.iter().find(|port| port.port.name == input.name).and_then(|port| port.port.columns.iter().find(|column| column.name == site.column)).is_some_and(|column| matches!(column.ty, ColumnType::Parameter(_)))
        };
        for input in crate::program::written_inputs(instance.key.as_ref(), &instance.inputs) {
            for site in input.head.iter().filter(|site| !bound(input, site)) {
                each_site_label(site, &mut Vec::new(), &mut |use_, _| {
                    if let Some(label) = use_label(use_) {
                        self.join_label(ctx, label, Place::Outside);
                    }
                });
            }
        }
        if let Some(key) = &instance.key {
            let keyed = component.inputs.iter().flat_map(|input| input.port.columns.iter()).any(|column| is_key(column) && matches!(column.ty, ColumnType::Parameter(_)));
            if !keyed {
                for column in key.value().key.columns.iter() {
                    self.join_label(ctx, column.label, Place::Outside);
                }
            }
        }
    }

    /// The joins of the labels at the sites of the atom at `at`.
    fn atom(&mut self, atom: &'a Atom, at: &NodePath, ctx: &Context) {
        let Some(read) = self.read(atom, at) else { return };
        if let (Some(form), Some(relation)) = (ctx.read_by, &read.relation) {
            self.parts[form].reads.push(relation.clone());
        }
        if let (Some(from), Some(to)) = (&ctx.body_of, &read.relation) {
            self.calls.push((from.clone(), to.clone()));
        }
        let mut sites = Vec::new();
        for site in atom.sites.iter() {
            each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                if let Some(label) = use_label(use_) {
                    sites.push((label, path.to_vec()));
                }
            });
        }
        for (label, path) in sites {
            let place = self.place_at(&read, &path);
            let (label, place) = (self.id(Place::Label(ctx.scope.clone(), label)), self.id(place));
            self.join(label, place, ctx);
        }
    }

    /// What the atom at `at` reads, or `None` where it reads a relation no
    /// form derives and no lib or fact gives.
    fn read(&self, atom: &Atom, at: &NodePath) -> Option<Read> {
        use crate::program::RelationRef;
        match &atom.relation {
            RelationRef::Fact(_) | RelationRef::Lib(_) => return Some(Read { kind: ReadKind::Outside, relation: None }),
            RelationRef::DefinedPort(_) => return None,
            RelationRef::Declared(_) | RelationRef::Output(_) => {}
        }
        let (program, resolution) = match self.program.concept().zip(self.program.concept_path(at)) {
            Some((concept, path)) => (concept, concept.resolution(&path)?),
            None => (self.program, self.program.resolution(at)?),
        };
        let node = match resolution {
            Resolution::Lib(_) => return Some(Read { kind: ReadKind::Outside, relation: None }),
            Resolution::Node(node) => &program.graph.nodes[node.0 as usize],
            Resolution::Undefined(_) | Resolution::Unresolved => return None,
        };
        let output = |relation: &RelationRef| match relation {
            RelationRef::Output(output) => Some(output.clone()),
            _ => None,
        };
        let derived = |relation: &ProgramRelation| Read { kind: ReadKind::Column(relation.clone(), node.scope.clone()), relation: Some(relation.clone()) };
        Some(match &node.kind {
            DependencyKind::Fact(_) | DependencyKind::Demonstrated(_) => Read { kind: ReadKind::Outside, relation: None },
            DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => derived(relation),
            DependencyKind::Chosen(name) => derived(&ProgramRelation::Declared(name.clone())),
            DependencyKind::RigidAssembly(name) => {
                let output = output(&atom.relation)?;
                Read { kind: ReadKind::Output(name.clone(), output.path), relation: None }
            }
            DependencyKind::InstanceInput { instance, input: port } | DependencyKind::InstanceOutput { instance, output: port } => {
                Read { kind: ReadKind::Port(instance.clone(), port.clone()), relation: None }
            }
            DependencyKind::RecursiveInstance(instance) => match output(&atom.relation).as_ref().map(|output| &output.path[..]) {
                Some([OutputStep::Port(port)]) => Read { kind: ReadKind::Port(instance.clone(), port.clone()), relation: None },
                _ => Read { kind: ReadKind::Outside, relation: None },
            },
        })
    }

    /// The place at the column path `path` of a site of a read.
    fn place_at(&self, read: &Read, path: &[ColumnName]) -> Place {
        match &read.kind {
            ReadKind::Outside => Place::Outside,
            ReadKind::Column(relation, scope) => Place::Column(relation.clone(), scope.clone(), path[0].clone()),
            ReadKind::Output(name, steps) => Place::Output(name.clone(), steps.clone(), path[0].clone()),
            ReadKind::Port(instance, port) => {
                let columns = self.instances.get(instance).and_then(|component| {
                    let output = component.outputs.iter().find(|output| output.name == *port);
                    let input = component.inputs.iter().map(|input| &input.port).find(|input| input.name == *port);
                    output.or(input).map(|port| &port.columns)
                });
                match columns.and_then(|columns| columns.iter().find(|column| column.name == path[0])).map(|column| &column.ty) {
                    Some(ColumnType::Parameter(parameter)) => Place::Parameter(instance.clone(), parameter.clone(), path[1..].into()),
                    _ => Place::Outside,
                }
            }
        }
    }

    /// The relations in `reads` and those that the body of a clause of one
    /// of them reads, at any depth.
    fn reached<'r>(&'r self, reads: &'r [ProgramRelation]) -> StableHashSet<&'r ProgramRelation> {
        let mut reached: StableHashSet<&ProgramRelation> = reads.iter().collect();
        let mut pending: Vec<&ProgramRelation> = reads.iter().collect();
        while let Some(relation) = pending.pop() {
            for (_, to) in self.calls.iter().filter(|(from, _)| from == relation) {
                if reached.insert(to) {
                    pending.push(to);
                }
            }
        }
        reached
    }

    /// For each `RIGID_DET` form, the labels at its part sites and key
    /// columns that are the assembly's own Idents.
    fn assemblies(&self) -> StableHashMap<NodePath, StableHashSet<LabelId>> {
        let mut own = StableHashMap::default();
        for (form, parts) in self.parts.iter().enumerate() {
            let exempt = self.reached(&parts.reads);
            let mut classes = Classes::new(self.ids.len());
            for join in &self.joins {
                if !join.in_body_of.as_ref().is_some_and(|relation| exempt.contains(relation)) {
                    classes.union(join.a, join.b);
                }
            }
            let outside = classes.find(self.ids[&Place::Outside]);
            let mut owners: StableHashMap<usize, BTreeSet<usize>> = StableHashMap::default();
            for (other, other_parts) in self.parts.iter().enumerate() {
                for &(_, place) in &other_parts.labels {
                    owners.entry(classes.find(place)).or_default().insert(other);
                }
            }
            let labels = parts
                .labels
                .iter()
                .filter(|&&(_, place)| {
                    let class = classes.find(place);
                    class != outside && owners[&class].len() == 1 && owners[&class].contains(&form)
                })
                .map(|&(label, _)| label)
                .collect();
            own.insert(parts.form.clone(), labels);
        }
        own
    }
}

/// What an atom reads.
struct Read {
    kind: ReadKind,
    /// The relation a clause derives, where the atom reads one.
    relation: Option<ProgramRelation>,
}

enum ReadKind {
    Outside,
    Column(ProgramRelation, NameScope),
    Output(RigidDetName, Arc<[OutputStep]>),
    Port(InstanceName, PortName),
}

/// The classes of places that hold one Ident.
struct Classes(Vec<usize>);

impl Classes {
    fn new(places: usize) -> Self {
        Classes((0..places).collect())
    }

    fn find(&mut self, place: usize) -> usize {
        let mut root = place;
        while self.0[root] != root {
            root = self.0[root];
        }
        let mut at = place;
        while self.0[at] != root {
            at = std::mem::replace(&mut self.0[at], root);
        }
        root
    }

    fn union(&mut self, a: usize, b: usize) {
        let (a, b) = (self.find(a), self.find(b));
        self.0[a.max(b)] = a.min(b);
    }
}
