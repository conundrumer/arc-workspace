//! The inference of the types of a case program's labels, form by form,
//! which the type check and the pose rule's check read: the scope of a
//! form, the walk of its sites, the types each form gives its labels, and
//! the inferences of a solver's case programs that a read of another
//! clause of a relation reaches.

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::sync::Arc;

use super::grounding::{bodies, BodyPlace};
use super::types::{
    column_type, component, declared_type, demo_rule, form_at, pose_of_fault, project, relation_columns, rule_scope_forms, scope_forms, scope_labels, site_value_type,
    try_map_labels, zero_typed_heads, PoseOr,
};
use super::{ClauseEntry, FileScope, Refusal, SolverClauses};
use crate::hash::StableHashMap;
use crate::program::canonical::{form_scope, CanonicalOrder, LabelScope};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, Body, ColumnName, Conjunct, DemoRule, Constraint, Form, Instance, LabelId, NameScope, Node, Operand, OutputOwner, OutputStep, PortName, ProgramRelation, RelationColumn, RelationRef, Site, SiteArg,
};
use crate::program::written_inputs;
use crate::registry::{binding_sites, key_parameter, Column, ColumnType, Component, ParameterSite, Registry, TypeParameter};
use crate::resolver::columns;
use crate::resolver::registry_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram};
use crate::types::{label_type, scope_list, use_label, AssemblyId, KeyRow, LabelFault, ValueType};

/// The labels of a form's own scope, with the list each label's sites stand
/// in: the conjuncts of the form's bodies, each instance input a branch of
/// its own, after an atom of its head on the input's port, and the labels
/// of the form's columns, whose scope is the whole list.
struct ScopeBody<'a> {
    body: Body,
    heads: Vec<LabelId>,
    /// The component whose input ports the head atoms read.
    component: Option<&'a Component>,
    /// The `INIT` form whose binding types the component's parameters.
    instance: Option<&'a Instance>,
}

impl<'a> ScopeBody<'a> {
    fn of(form: &'a Form, registry: &'a Registry) -> Self {
        let mut conjuncts: Vec<Conjunct> = Vec::new();
        let mut heads: Vec<LabelId> = Vec::new();
        for form_body in bodies(NodeRef::from(form)) {
            match form_body.place {
                BodyPlace::Input(input, _) => {
                    let head = Atom { relation: RelationRef::DefinedPort(input.name.clone()), sites: input.head.clone() };
                    let branch = std::iter::once(Conjunct::Atom(Node::new(head))).chain(input.body.value().conjuncts.iter().cloned());
                    conjuncts.push(Conjunct::Or(Arc::from([Node::new(Body { conjuncts: branch.collect() })])));
                }
                BodyPlace::Branch => conjuncts.push(Conjunct::Or(Arc::from([form_body.body.clone()]))),
                BodyPlace::List => {
                    conjuncts.extend(form_body.body.value().conjuncts.iter().cloned());
                    heads.extend(form_body.columns);
                }
            }
        }
        let (mut found_component, mut found_instance) = (None, None);
        match form {
            Form::Instance(instance) => {
                let instance = instance.value();
                found_component = component(registry, &instance.component);
                found_instance = Some(instance);
            }
            Form::RigidDet(rigid) => conjuncts.extend(rigid.value().parts.iter().map(|part| Conjunct::Atom(part.clone()))),
            Form::Clause(_) | Form::Choose(_) | Form::Demonstrated(_) | Form::Claim(_) | Form::Alts(_) => {}
        }
        ScopeBody { body: Body { conjuncts: conjuncts.into() }, heads, component: found_component, instance: found_instance }
    }

    /// The list of the scope of `label`.
    fn list(&self, label: LabelId) -> &Body {
        if self.heads.contains(&label) {
            &self.body
        } else {
            scope_list(&self.body, label)
        }
    }
}

/// One label at one site of a form: the site's path relative to the form,
/// the atom whose site it is, or `None` at an instance input's head, and
/// the column path.
pub(super) struct SiteUse<'a> {
    pub at: NodePath,
    pub atom: Option<&'a Atom>,
    pub column: Vec<ColumnName>,
    pub label: LabelId,
}

/// The nodes of the own scope of one form that the inference reads by
/// their paths relative to the form: the path of each atom, each label's
/// first use, each constraint, and each label at a site. The forms of a
/// `DEMO_RULE` stand in scopes of their own.
pub(super) struct FormWalk<'a> {
    atoms: StableHashMap<*const Atom, NodePath>,
    first_use: StableHashMap<LabelId, NodePath>,
    pub constraints: Vec<(NodePath, &'a Constraint)>,
    pub uses: Vec<SiteUse<'a>>,
}

impl<'a> FormWalk<'a> {
    fn of(form: &'a Form) -> Self {
        let mut walk = FormWalk { atoms: StableHashMap::default(), first_use: StableHashMap::default(), constraints: Vec::new(), uses: Vec::new() };
        walk.node(NodeRef::from(form), NodePath::default());
        walk
    }

    /// The walk of the scope of `rule`: each of its forms that stands in its
    /// scope, at its path relative to the rule.
    fn of_rule(rule: &'a DemoRule) -> Self {
        let mut walk = FormWalk { atoms: StableHashMap::default(), first_use: StableHashMap::default(), constraints: Vec::new(), uses: Vec::new() };
        for (index, form) in rule_scope_forms(rule) {
            walk.node(NodeRef::from(form), NodePath::default().child(index));
        }
        walk
    }

    fn node(&mut self, node: NodeRef<'a>, at: NodePath) {
        if let Some(atom) = node.atom() {
            return self.atom(atom, at);
        }
        match node {
            NodeRef::DemoRule(_) => return,
            NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
                let second = match constraint.second {
                    Operand::Label(label) => Some(label.label),
                    Operand::Zero => None,
                };
                for label in std::iter::once(constraint.first.label).chain(second) {
                    self.first_use.entry(label).or_insert_with(|| at.clone());
                }
                self.constraints.push((at, constraint));
                return;
            }
            NodeRef::InstanceInput(input) => {
                for (site, index) in input.head.iter().zip(0u32..) {
                    self.site(None, site, at.child(index), &mut Vec::new());
                }
                let body = input.head.len() as u32;
                return self.node(NodeRef::Body(input.body.value()), at.child(body));
            }
            _ => {}
        }
        for (child, index) in node.children().into_iter().zip(0u32..) {
            self.node(child, at.child(index));
        }
    }

    fn atom(&mut self, atom: &'a Atom, at: NodePath) {
        self.atoms.insert(atom as *const Atom, at.clone());
        for (site, index) in atom.sites.iter().zip(0u32..) {
            self.site(Some(atom), site, at.child(index), &mut Vec::new());
        }
    }

    fn site(&mut self, atom: Option<&'a Atom>, site: &'a Site, at: NodePath, column: &mut Vec<ColumnName>) {
        column.push(site.column.clone());
        for (arg, index) in site.value.args.iter().zip(0u32..) {
            let at = at.child(index);
            let (use_, name) = match arg {
                SiteArg::Label(use_) => (use_, None),
                SiteArg::NamedLabel { name, label } => (label, Some(name)),
                SiteArg::Field(field) => {
                    self.site(atom, field, at, column);
                    continue;
                }
            };
            let Some(label) = use_label(*use_) else { continue };
            self.first_use.entry(label).or_insert_with(|| at.clone());
            let mut path = column.clone();
            path.extend(name.cloned());
            self.uses.push(SiteUse { at, atom, column: path, label });
        }
        column.pop();
    }

    /// The path of the first use of `label`, a label of the form.
    pub fn first_use(&self, label: LabelId) -> &NodePath {
        self.first_use.get(&label).expect("each label of a form's scope stands at a site or a constraint of the form")
    }
}

/// The owner of a label scope: a form, of its own scope, or a `DEMO_RULE`.
#[derive(Clone, Copy)]
pub(super) enum ScopeOwner<'a> {
    Form(&'a Form),
    DemoRule(&'a DemoRule),
}

/// The types of one label scope.
pub(super) struct FormInference<'a> {
    pub owner: ScopeOwner<'a>,
    pub path: NodePath,
    /// Each label of the scope, in the order of its canonical labeling, with
    /// its type or its fault.
    pub labels: Vec<(LabelId, Result<Option<ValueType>, LabelFault>)>,
    /// The type each parameter of an `INIT` form's component is bound to.
    pub bindings: StableHashMap<TypeParameter, ValueType>,
    pub walk: FormWalk<'a>,
    component: Option<&'a Component>,
    /// The head labels that take their type from the relation's other
    /// clauses.
    pub(super) zero_typed: Vec<LabelId>,
    /// The labels that take their type from a column of `(pose-or <type>)`
    /// alone, so that a column of a relation that such a label gives takes
    /// a Pose type as that column does.
    given: Vec<LabelId>,
}

impl<'a> FormInference<'a> {
    /// The types of this inference, of a form of the concept program, given
    /// to `owner`, the same scope at `path` in a case, whose sites `walk`
    /// walks.
    fn at(&self, owner: ScopeOwner<'a>, path: &NodePath, walk: FormWalk<'a>) -> Self {
        FormInference {
            owner,
            path: path.clone(),
            labels: self.labels.clone(),
            bindings: self.bindings.clone(),
            walk,
            component: self.component,
            zero_typed: self.zero_typed.clone(),
            given: self.given.clone(),
        }
    }

    /// The type of `label` read under `pose_or`, where the form gives it
    /// one.
    fn label_under(&self, label: LabelId, pose_or: PoseOr) -> Option<ValueType> {
        if pose_or == PoseOr::Open && self.given.contains(&label) {
            return None;
        }
        self.label(label)
    }

    /// The type of `label`, where the form gives it one.
    pub fn label(&self, label: LabelId) -> Option<ValueType> {
        typed(&self.labels, label)
    }

    /// The Pose type of `label`, where one of its sites gives it one.
    pub fn pose_of(&self, label: LabelId) -> Option<&ValueType> {
        match &self.labels.iter().find(|(found, _)| *found == label)?.1 {
            Ok(Some(ty @ ValueType::Pose(_))) => Some(ty),
            Ok(_) => None,
            Err(fault) => pose_of_fault(fault),
        }
    }
}

/// What a site of a form reads its column types under.
#[derive(Clone, Copy)]
pub(super) struct SiteReading<'r, 'a> {
    pub path: &'r NodePath,
    pub walk: &'r FormWalk<'a>,
    pub component: Option<&'a Component>,
    pub bindings: &'r StableHashMap<TypeParameter, ValueType>,
    pub pose_or: PoseOr,
}

impl<'a> FormInference<'a> {
    /// What the form's sites read their column types under.
    pub fn reading(&self, pose_or: PoseOr) -> SiteReading<'_, 'a> {
        SiteReading { path: &self.path, walk: &self.walk, component: self.component, bindings: &self.bindings, pose_or }
    }
}

/// The type that each clause of a [`SolverClauses`] gives one of its
/// columns, or that it adds no type, as [`Inference::other_clauses_type`]
/// reads it for a clause of the same relation, kept over every
/// [`super::check_program`] call on that value, so that the check of a
/// solver infers each such read once, and not once per case program it
/// checks, where the read meets no cycle of forms. A key is the clause, by its case program and its path there,
/// the column, and the columns of the clause that reads it, whose head
/// labels name a Pose type's key row.
#[derive(Debug, Default)]
pub(super) struct ClauseColumnReads(RefCell<StableHashMap<(usize, NodePath, ColumnName, Arc<[RelationColumn]>), Option<ValueType>>>);

impl ClauseColumnReads {
    /// The type that the clause of `entry` gives `column`, or `None` where
    /// it adds no type, read for a clause whose columns are `reader`, from
    /// `read`. A read is kept unless `cycle_reads`, the count of reads
    /// through a cycle of forms, grows while it runs, since its type then
    /// depends on the forms whose inference runs.
    fn get_or_read(
        &self,
        entry: &ClauseEntry,
        column: &ColumnName,
        reader: &Arc<[RelationColumn]>,
        cycle_reads: &Cell<usize>,
        read: impl FnOnce() -> Option<ValueType>,
    ) -> Option<ValueType> {
        let key = (entry.program, entry.at.clone(), column.clone(), Arc::clone(reader));
        if let Some(found) = self.0.borrow().get(&key) {
            return found.clone();
        }
        let before = cycle_reads.get();
        let found = read();
        if cycle_reads.get() == before {
            self.0.borrow_mut().insert(key, found.clone());
        }
        found
    }
}

/// The inferences of the case programs of a [`SolverClauses`] that one
/// [`super::check_program`] call reads, each program's once, so that a read through a
/// cycle of forms across those programs meets the guard of
/// [`Inference::infer`].
pub(super) struct CaseInferences<'a> {
    clauses: &'a SolverClauses,
    registry: &'a Registry,
    inferences: RefCell<StableHashMap<usize, Rc<Inference<'a>>>>,
    /// The inference of each concept program that a case program read
    /// resolves its concept forms in, by the program's address.
    concepts: RefCell<StableHashMap<*const ResolvedProgram, Rc<Inference<'a>>>>,
    /// The number of reads so far of a form whose inference runs, each a
    /// read through a cycle of forms.
    cycle_reads: Cell<usize>,
}

impl<'a> CaseInferences<'a> {
    pub fn new(clauses: &'a SolverClauses, registry: &'a Registry) -> Self {
        CaseInferences { clauses, registry, inferences: RefCell::default(), concepts: RefCell::default(), cycle_reads: Cell::default() }
    }

    /// The inference of `concept`, a concept program.
    fn concept(&'a self, concept: &'a ResolvedProgram) -> Rc<Inference<'a>> {
        let mut concepts = self.concepts.borrow_mut();
        let inference = concepts.entry(concept as *const ResolvedProgram).or_insert_with(|| Rc::new(Inference::new(concept, self)));
        Rc::clone(inference)
    }

    /// The inference of the case program `entry` was found in.
    fn of(&'a self, entry: &ClauseEntry) -> Rc<Inference<'a>> {
        let program = self.clauses.program(entry);
        let mut inferences = self.inferences.borrow_mut();
        let inference = inferences.entry(entry.program).or_insert_with(|| Rc::new(Inference::new(program, self)));
        Rc::clone(inference)
    }
}

/// The inference of the types of one case program's labels, form by form,
/// each form once, on its first read. A form at or under a `DET` form that
/// the case takes from the concept program is inferred, and its sites
/// typed, by the inference of the concept program at its path there, as
/// [`ResolvedProgram::concept_path`] gives it.
pub(super) struct Inference<'a> {
    program: &'a ResolvedProgram,
    registry: &'a Registry,
    cases: &'a CaseInferences<'a>,
    /// The inference of [`ResolvedProgram::concept`].
    concept: Option<Rc<Inference<'a>>>,
    /// Each form inferred, or `None` while its inference runs, so that a
    /// read through a cycle of forms gives no type.
    forms: RefCell<StableHashMap<NodePath, Option<Rc<FormInference<'a>>>>>,
}

impl std::fmt::Debug for Inference<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Inference").finish_non_exhaustive()
    }
}

impl<'a> Inference<'a> {
    pub fn new(program: &'a ResolvedProgram, cases: &'a CaseInferences<'a>) -> Self {
        let concept = program.concept().map(|concept| cases.concept(concept));
        Inference { program, registry: cases.registry, cases, concept, forms: RefCell::default() }
    }

    /// The inference of the concept program and the path there of `path`,
    /// where `path` stands at or under a form the case takes from it.
    fn in_concept(&self, path: &NodePath) -> Option<(&Inference<'a>, NodePath)> {
        let concept = self.concept.as_deref()?;
        Some((concept, self.program.concept_path(path)?))
    }

    /// The types of the label scope whose form stands at `path`, a form or
    /// a `DEMO_RULE`, or `None` where no such form stands there or its
    /// inference runs.
    pub fn infer(&self, path: &NodePath) -> Option<Rc<FormInference<'a>>> {
        if let Some(found) = self.forms.borrow().get(path) {
            if found.is_none() {
                self.cases.cycle_reads.set(self.cases.cycle_reads.get() + 1);
            }
            return found.clone();
        }
        let program = self.program.program.value();
        let owner = match form_at(program, path) {
            Some(form) => ScopeOwner::Form(form),
            None => ScopeOwner::DemoRule(demo_rule(program, path)?),
        };
        if let Some((concept, at)) = self.in_concept(path) {
            let walk = match owner {
                ScopeOwner::Form(form) => FormWalk::of(form),
                ScopeOwner::DemoRule(rule) => FormWalk::of_rule(rule),
            };
            let inferred = Rc::new(concept.infer(&at)?.at(owner, path, walk));
            self.forms.borrow_mut().insert(path.clone(), Some(Rc::clone(&inferred)));
            return Some(inferred);
        }
        self.forms.borrow_mut().insert(path.clone(), None);
        let inferred = Rc::new(match owner {
            ScopeOwner::Form(form) => self.infer_new(form, path),
            ScopeOwner::DemoRule(rule) => self.infer_rule(rule, path),
        });
        self.forms.borrow_mut().insert(path.clone(), Some(Rc::clone(&inferred)));
        Some(inferred)
    }

    fn infer_new(&self, form: &'a Form, path: &NodePath) -> FormInference<'a> {
        let scope = ScopeBody::of(form, self.registry);
        let walk = FormWalk::of(form);
        let labels: Vec<LabelId> = form_scope(form).map(scope_labels).unwrap_or_default();
        let no_bindings = StableHashMap::default();
        let type_all = |bindings: &StableHashMap<TypeParameter, ValueType>, pose_or: PoseOr| -> Vec<(LabelId, Result<Option<ValueType>, LabelFault>)> {
            let reading = SiteReading { path, walk: &walk, component: scope.component, bindings, pose_or };
            let site_type = |atom: &Atom, column: &[ColumnName]| self.site_type(reading, atom, column);
            labels.iter().map(|label| (*label, label_type(scope.list(*label), *label, &site_type))).collect()
        };
        let mut types = type_all(&no_bindings, PoseOr::Open);
        let mut bindings = StableHashMap::default();
        if let (Some(instance), Some(component)) = (scope.instance, scope.component) {
            if !component.type_parameters.is_empty() {
                bindings = bind(instance, component, &|label| typed(&types, label));
                types = type_all(&bindings, PoseOr::Open);
            }
        }
        let mut given_labels = Vec::new();
        if types.iter().any(|(_, ty)| matches!(ty, Ok(None))) {
            let given = type_all(&bindings, PoseOr::Given);
            for ((label, ty), (_, given)) in types.iter_mut().zip(given) {
                if matches!(ty, Ok(None)) {
                    *ty = given;
                    given_labels.push(*label);
                }
            }
        }
        let mut zero_typed = Vec::new();
        if let Form::Clause(clause) = form {
            let clause = clause.value();
            for label in zero_typed_heads(clause) {
                let Some((_, ty)) = types.iter_mut().find(|(found, _)| *found == label) else { continue };
                let Some(column) = clause.columns.iter().find(|column| column.label == label) else { continue };
                *ty = self.other_clauses_type(clause, path, &column.name);
                zero_typed.push(label);
            }
        }
        FormInference { owner: ScopeOwner::Form(form), path: path.clone(), labels: types, bindings, walk, component: scope.component, zero_typed, given: given_labels }
    }

    /// The types of the scope of `rule`, the `DEMO_RULE` at `path`: each
    /// label of its fields and of its forms that stand in its scope takes
    /// the meet of the types that the inference of each such form, at its
    /// own path, gives it, so that its type comes from each of its sites in
    /// the rule.
    fn infer_rule(&self, rule: &'a DemoRule, path: &NodePath) -> FormInference<'a> {
        let mut labels: Vec<(LabelId, Result<Option<ValueType>, LabelFault>)> =
            scope_labels(LabelScope::DemoRule(rule)).into_iter().map(|label| (label, Ok(None))).collect();
        let mut given = Vec::new();
        for (index, _) in rule_scope_forms(rule) {
            let Some(inferred) = self.infer(&path.child(index)) else { continue };
            for (label, ty) in labels.iter_mut() {
                let Some((_, form_ty)) = inferred.labels.iter().find(|(found, _)| found == label) else { continue };
                *ty = match (ty.clone(), form_ty.clone()) {
                    (Err(fault), _) | (_, Err(fault)) => Err(fault),
                    (Ok(a), Ok(b)) => crate::types::meet(a, b),
                };
                if inferred.given.contains(label) && !given.contains(label) {
                    given.push(*label);
                }
            }
        }
        let no_bindings = StableHashMap::default();
        FormInference { owner: ScopeOwner::DemoRule(rule), path: path.clone(), labels, bindings: no_bindings, walk: FormWalk::of_rule(rule), component: None, zero_typed: Vec::new(), given }
    }

    /// The type that the column at `path` of the relation `atom` reads gives
    /// a site of `atom`, a site of a form read under `reading`.
    pub fn site_type(&self, reading: SiteReading<'_, 'a>, atom: &Atom, path: &[ColumnName]) -> Option<ValueType> {
        if let Some((concept, at)) = self.in_concept(reading.path) {
            return concept.site_type(SiteReading { path: &at, ..reading }, atom, path);
        }
        if let RelationRef::DefinedPort(port) = &atom.relation {
            let (first, rest) = path.split_first()?;
            let input = reading.component?.inputs.iter().find(|input| input.port.name == *port)?;
            let column = input.port.columns.iter().find(|column| column.name == *first)?;
            return column_type(&column.ty, rest, reading.bindings, reading.pose_or);
        }
        let at = reading.path.join(reading.walk.atoms.get(&(atom as *const Atom))?);
        match self.program.resolution(&at)? {
            Resolution::Lib(name) => declared_type(registry_columns::lib_typed_columns(self.registry, name)?, path, reading.pose_or),
            Resolution::Node(_) if path == [columns::example()] && self.program.reads_lifted(&at) => Some(ValueType::Example),
            Resolution::Node(node) => self.node_type(*node, atom, path, reading.pose_or),
            Resolution::Undefined(_) | Resolution::Unresolved => None,
        }
    }

    /// Whether a site of `atom`, a site of a form read under `reading`, on
    /// the column at `path`, may hold a Pose label whatever its column's
    /// type: an instance input's head, a column of a relation the program
    /// derives or of an instance's input, or a lib column that takes a Pose
    /// type (`docs/arclog/rigid.md#the-pose`).
    pub fn admits_pose(&self, reading: SiteReading<'_, 'a>, atom: &Atom, path: &[ColumnName]) -> bool {
        if let RelationRef::DefinedPort(_) = &atom.relation {
            return true;
        }
        if let Some((concept, at)) = self.in_concept(reading.path) {
            return concept.admits_pose(SiteReading { path: &at, ..reading }, atom, path);
        }
        let Some(at) = reading.walk.atoms.get(&(atom as *const Atom)) else { return false };
        match self.program.resolution(&reading.path.join(at)) {
            Some(Resolution::Lib(name)) => {
                let column = path.first().and_then(|first| registry_columns::lib_typed_columns(self.registry, name)?.iter().find(|column| column.name == *first));
                column.is_some_and(|column| matches!(column.ty, ColumnType::Pose | ColumnType::SharedPose | ColumnType::PoseOr(_)))
            }
            Some(Resolution::Node(node)) => matches!(
                self.program.graph.nodes[node.0 as usize].kind,
                DependencyKind::Clause(_)
                    | DependencyKind::Parameter(_)
                    | DependencyKind::Chosen(_)
                    | DependencyKind::Demonstrated(_)
                    | DependencyKind::InstanceInput { .. }
                    | DependencyKind::RecursiveInstance(_)
            ),
            _ => false,
        }
    }

    /// Whether the column at `path` of the lib relation `atom` reads, a site
    /// of a form read under `reading`, is of the type Pose that each column
    /// of its relation shares.
    pub fn shares_pose(&self, reading: SiteReading<'_, 'a>, atom: &Atom, path: &[ColumnName]) -> bool {
        let Some(at) = reading.walk.atoms.get(&(atom as *const Atom)) else { return false };
        let Some(Resolution::Lib(name)) = self.program.resolution(&reading.path.join(at)) else { return false };
        let column = path.first().and_then(|first| registry_columns::lib_typed_columns(self.registry, name)?.iter().find(|column| column.name == *first));
        column.is_some_and(|column| column.ty == ColumnType::SharedPose)
    }

    /// The type of the column at `path` of the relation of `node`, read by
    /// `atom`.
    fn node_type(&self, node: GraphNodeIndex, atom: &Atom, path: &[ColumnName], pose_or: PoseOr) -> Option<ValueType> {
        let graph_node = &self.program.graph.nodes[node.0 as usize];
        let form_path = self.program.form_of(node);
        let reader = |column: &ColumnName| column_label(atom, column);
        match &graph_node.kind {
            DependencyKind::Fact(fact) => declared_type(self.registry.fact_columns(*fact), path, PoseOr::Open),
            DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => {
                self.relation_type(&graph_node.scope, relation, path, &reader, pose_or).ok().flatten()
            }
            DependencyKind::Chosen(name) => match form_at(self.program.program.value(), form_path)? {
                Form::Choose(choose) => {
                    let columns: Vec<&RelationColumn> = columns::form_columns(NodeRef::Choose(choose.value())).collect();
                    let (first, rest) = path.split_first()?;
                    let column = columns.iter().find(|column| column.name == *first)?;
                    let ty = project(&self.infer(form_path)?.label_under(column.label, pose_or)?, rest)?;
                    try_map_labels(&ty, &|label| reader(&columns.iter().find(|column| column.label == label)?.name))
                }
                _ => {
                    let relation = ProgramRelation::Declared(name.clone());
                    self.relation_type(&graph_node.scope, &relation, path, &reader, pose_or).ok().flatten()
                }
            },
            DependencyKind::InstanceOutput { output, .. } => self.instance_output(form_path, output, path),
            DependencyKind::RecursiveInstance(_) => match &atom.relation {
                RelationRef::Output(output) => match &output.path[..] {
                    [OutputStep::Port(port)] => self.instance_output(form_path, port, path),
                    _ => None,
                },
                _ => None,
            },
            DependencyKind::RigidAssembly(_) => {
                let RelationRef::Output(output) = &atom.relation else { return None };
                let key = columns::key();
                let key_row = |key_columns: &[RelationColumn]| {
                    Some(KeyRow::Labels(key_columns.iter().map(|column| field_label(atom, &key, &column.name)).collect::<Option<_>>()?))
                };
                self.rigid_output(form_path, &output.path, path, &key_row)
            }
            DependencyKind::Demonstrated(_) => self.demonstrated_column(form_path, path),
            DependencyKind::InstanceInput { input, .. } => self.instance_input(form_path, input, path),
        }
    }

    /// The type that the clauses of `relation` in `scope` give its column at
    /// `path`, the join of each clause's, or the fault of two types with no
    /// join, read under `pose_or`. A Pose type's key row names the labels
    /// that `target` gives at the columns of the key.
    fn relation_type(
        &self,
        scope: &NameScope,
        relation: &ProgramRelation,
        path: &[ColumnName],
        target: &dyn Fn(&ColumnName) -> Option<LabelId>,
        pose_or: PoseOr,
    ) -> Result<Option<ValueType>, LabelFault> {
        let forms = scope_forms(self.program.program.value(), scope);
        let clauses = forms.iter().filter_map(|(at, form)| match form {
            Form::Clause(clause) if clause.value().derives == *relation => Some((at, clause.value())),
            _ => None,
        });
        join_types(clauses.filter_map(|(at, clause)| self.clause_column(at, clause, scope, path, target, pose_or)))
    }

    /// The join of the types that the other clauses of the relation of
    /// `clause`, the clause at `path`, in [`SolverClauses`] give its
    /// `column`, each in the case program it was found in, or the fault of
    /// two types with no join. A clause whose label at that column only
    /// `(= *X 0)` gives a type adds no type. A Pose type's key row names
    /// the labels of `clause`.
    fn other_clauses_type(&self, clause: &crate::program::Clause, path: &NodePath, column: &ColumnName) -> Result<Option<ValueType>, LabelFault> {
        let own = super::clause_signature(self.program, path);
        let target = |column: &ColumnName| head_label(clause, column);
        let entries = self.cases.clauses.of_relation(&FileScope::Program, &clause.derives).iter();
        let types = entries.filter(|entry| entry.signature != own).filter_map(|entry| {
            self.cases.clauses.column_reads().get_or_read(entry, column, &clause.columns, &self.cases.cycle_reads, || {
                let inference = self.cases.of(entry);
                let Some(Form::Clause(other)) = form_at(inference.program.program.value(), &entry.at) else {
                    unreachable!("an entry of a relation in the program's scope stands at a clause of the program it was found in")
                };
                let other = other.value();
                let zero_typed = zero_typed_heads(other);
                if other.columns.iter().any(|found| found.name == *column && zero_typed.contains(&found.label)) {
                    return None;
                }
                inference.clause_column(&entry.at, other, &NameScope::Program, std::slice::from_ref(column), &target, PoseOr::Given)
            })
        });
        join_types(types)
    }

    /// Where `clause`, a clause of `scope`, takes the columns of its
    /// relation from: its own columns, its first proposer's declared
    /// columns, or the instance output it stands for.
    fn clause_columns<'c>(&'c self, clause: &'c crate::program::Clause, scope: &NameScope) -> Option<ClauseColumns<'c>> {
        if !clause.columns.is_empty() {
            return Some(ClauseColumns::Own(&clause.columns));
        }
        if let Some(proposer) = clause.proposers.first() {
            return registry_columns::lib_typed_columns(self.registry, proposer).map(ClauseColumns::Declared);
        }
        let ProgramRelation::Output(output) = &clause.derives else { return None };
        let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return None };
        let forms = scope_forms(self.program.program.value(), scope);
        let instance = forms.into_iter().find(|(_, form)| matches!(form, Form::Instance(instance) if instance.value().name == *name))?;
        Some(ClauseColumns::InstanceOutput(instance.0, port))
    }

    /// The names of the columns of the relation of `clause`, a clause of
    /// `scope`, as the clause gives them.
    fn clause_column_names(&self, clause: &crate::program::Clause, scope: &NameScope) -> Vec<ColumnName> {
        match self.clause_columns(clause, scope) {
            None => Vec::new(),
            Some(ClauseColumns::Own(columns)) => columns.iter().map(|column| column.name.clone()).collect(),
            Some(ClauseColumns::Declared(columns)) => columns.iter().map(|column| column.name.clone()).collect(),
            Some(ClauseColumns::InstanceOutput(instance, port)) => {
                let Some(component) = self.infer(&instance).and_then(|inference| inference.component) else { return Vec::new() };
                let output = component.outputs.iter().find(|output| output.name == *port);
                output.map(|output| output.columns.iter().map(|column| column.name.clone()).collect()).unwrap_or_default()
            }
        }
    }

    /// The refusals of `clause`, the top-level clause at `path` whose
    /// inference is `form`, a form whose canonical order is `order`, at each
    /// column of its relation to which it gives a type with no join with
    /// the types that the relation's other clauses give that column, as
    /// [`CheckId::Types`] gives.
    pub(super) fn column_refusals(&self, form: &FormInference<'_>, clause: &crate::program::Clause, path: &NodePath, order: &CanonicalOrder) -> Vec<Refusal> {
        let target = |column: &ColumnName| head_label(clause, column);
        let mut refusals = Vec::new();
        for name in self.clause_column_names(clause, &NameScope::Program) {
            let label = target(&name);
            if label.is_some_and(|label| form.zero_typed.contains(&label)) {
                continue;
            }
            let column = std::slice::from_ref(&name);
            let Some(own) = self.clause_column(path, clause, &NameScope::Program, column, &target, PoseOr::Given) else { continue };
            match self.other_clauses_type(clause, path, &name) {
                Ok(None) => continue,
                Ok(Some(others)) if own.join(&others).is_some() => continue,
                Ok(Some(_)) | Err(_) => {}
            }
            let message = format!("the clause gives the column {name:?} of its relation the type {own:?}, which has no join with the types that the relation's other clauses give it");
            let at = label.map_or_else(NodePath::default, |label| order.canonical_path(form.walk.first_use(label)));
            refusals.push(Refusal { message: message.into(), at });
        }
        refusals
    }

    /// The type that the clause at `at` gives the column at `path` of its
    /// relation under `pose_or`, from the columns [`Self::clause_columns`]
    /// gives.
    fn clause_column(
        &self,
        at: &NodePath,
        clause: &crate::program::Clause,
        scope: &NameScope,
        path: &[ColumnName],
        target: &dyn Fn(&ColumnName) -> Option<LabelId>,
        pose_or: PoseOr,
    ) -> Option<ValueType> {
        let (first, rest) = path.split_first()?;
        match self.clause_columns(clause, scope)? {
            ClauseColumns::Own(columns) => {
                let column = columns.iter().find(|column| column.name == *first)?;
                let ty = project(&self.infer(at)?.label_under(column.label, pose_or)?, rest)?;
                try_map_labels(&ty, &|label| target(&columns.iter().find(|column| column.label == label)?.name))
            }
            ClauseColumns::Declared(columns) => declared_type(columns, path, pose_or),
            ClauseColumns::InstanceOutput(instance, port) => self.instance_output(&instance, port, path),
        }
    }

    /// The type of each column of each relation that the form `form` at `at`
    /// gives whose columns its declaration fixes, by the path after the
    /// form's name of the output, the empty path for the form's own
    /// relation, in the order of the resolver's columns of it: a clause's
    /// with no columns of its own, each input that an `INIT` form writes and
    /// each output, each output of a `RIGID_DET` form, and a `DEMONSTRATED`
    /// form's. A relation a column of which takes no type has no entry.
    pub(super) fn form_relations(&self, at: &NodePath, form: &'a Form) -> Vec<(Arc<[OutputStep]>, Box<[ValueType]>)> {
        let mut relations: Vec<(Arc<[OutputStep]>, Option<Box<[ValueType]>>)> = Vec::new();
        match form {
            Form::Clause(clause) if clause.value().columns.is_empty() => {
                let clause = clause.value();
                let mut nodes = (0..self.program.graph.nodes.len() as u32).map(GraphNodeIndex);
                let node = nodes.find(|node| self.program.forms_of(*node).contains(at)).expect("the resolver gives each clause a node");
                let scope = &self.program.graph.nodes[node.0 as usize].scope;
                let names = self.clause_column_names(clause, scope);
                let column = |name: &ColumnName| self.clause_column(at, clause, scope, std::slice::from_ref(name), &|_| None, PoseOr::Given);
                if !names.is_empty() {
                    relations.push((Arc::from([]), relation_columns(&names, &column)));
                }
            }
            Form::Instance(_) => {
                let Some(inference) = self.infer(at) else { return Vec::new() };
                let (Some(component), ScopeOwner::Form(Form::Instance(instance))) = (inference.component, inference.owner) else { return Vec::new() };
                let written: Vec<&PortName> = written_inputs(instance.value().key.as_ref(), &instance.value().inputs).map(|input| &input.name).collect();
                let inputs = component.inputs.iter().map(|input| &input.port).filter(|port| written.contains(&&port.name));
                let outputs = component.outputs.iter();
                let mut ports: Vec<&crate::registry::Port> = outputs.collect();
                ports.extend(inputs.filter(|port| !component.outputs.iter().any(|output| output.name == port.name)));
                for port in ports {
                    let column = |name: &ColumnName| port_column(&inference, port, std::slice::from_ref(name));
                    relations.push((Arc::from([OutputStep::Port(port.name.clone())]), relation_columns(port.columns.iter().map(|column| &column.name), &column)));
                }
            }
            Form::RigidDet(rigid) => {
                let key_row = |key: &[RelationColumn]| Some(KeyRow::Columns((0..key.len() as u16).collect()));
                for (output, names) in columns::rigid_outputs(rigid.value()) {
                    let column = |name: &ColumnName| self.rigid_output(at, &output, std::slice::from_ref(name), &key_row);
                    let types = relation_columns(names.names(), &column);
                    relations.push((output, types));
                }
            }
            Form::Demonstrated(demonstrated) => {
                let names = columns::demonstrated_columns(demonstrated.value());
                let column = |name: &ColumnName| self.demonstrated_column(at, std::slice::from_ref(name));
                relations.push((Arc::from([]), relation_columns(names.names(), &column)));
            }
            Form::Clause(_) | Form::Choose(_) | Form::Claim(_) | Form::Alts(_) => {}
        }
        relations.into_iter().filter_map(|(output, columns)| Some((output, columns?))).collect()
    }

    /// The type of the column at `path` of the output `port` of the `INIT`
    /// form at `at`, its parameters bound as the form binds them. A type
    /// that names labels of the form's scope gives none.
    fn instance_output(&self, at: &NodePath, port: &PortName, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let output = inference.component?.outputs.iter().find(|output| output.name == *port)?;
        port_column(&inference, output, path)
    }

    /// The type of the column at `path` of the input `port` of the `INIT`
    /// form at `at`, its parameters bound as the form binds them. A type
    /// that names labels of the form's scope gives none.
    fn instance_input(&self, at: &NodePath, port: &PortName, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let input = inference.component?.inputs.iter().find(|input| input.port.name == *port)?;
        port_column(&inference, &input.port, path)
    }

    /// The type of the column at `path` of the output `output`, the path
    /// after the form's name, of the `RIGID_DET` form at `at`
    /// (`docs/arclog/rigid.md#semantics`). The Pose type of a keyed form names
    /// its key row as `key_row` gives it from the key's columns.
    fn rigid_output(
        &self,
        at: &NodePath,
        output: &[OutputStep],
        path: &[ColumnName],
        key_row: &dyn Fn(&[RelationColumn]) -> Option<KeyRow>,
    ) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let ScopeOwner::Form(form @ Form::RigidDet(rigid)) = inference.owner else { return None };
        let rigid_value = rigid.value();
        let (first, rest) = path.split_first()?;
        let local = |ty: ValueType| try_map_labels(&ty, &|_| None);
        let key = columns::key();
        if *first == key {
            let Some(key_body) = &rigid_value.key else { return project(&ValueType::Unit, rest) };
            let field = |column: &RelationColumn| Some((column.name.clone(), inference.label(column.label)?));
            let record = ValueType::Record(key_body.columns.iter().map(field).collect::<Option<_>>()?);
            return local(project(&record, rest)?);
        }
        if *first == columns::pose() {
            let key_row = match &rigid_value.key {
                None => KeyRow::Unkeyed,
                Some(key_body) => key_row(&key_body.columns)?,
            };
            let canonical_form = super::canonical_form(form);
            return Some(ValueType::Pose(AssemblyId { name: rigid_value.name.clone(), canonical_form, key: key_row }));
        }
        if let [OutputStep::Pose] = output {
            let column = rigid_value.instance.iter().flat_map(|instance| instance.columns.iter()).find(|column| column.name == *first)?;
            return local(project(&inference.label(column.label)?, rest)?);
        }
        let part = rigid_value.parts.iter().find(|part| columns::part_steps(&part.value().relation).as_deref() == Some(output))?;
        local(self.site_type(inference.reading(PoseOr::Given), part.value(), path)?)
    }

    /// The type of the column at `path` of the relation of the `DEMONSTRATED`
    /// form at `at` (`docs/arclog/arclog.md#demonstrated`).
    fn demonstrated_column(&self, at: &NodePath, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let ScopeOwner::Form(Form::Demonstrated(demonstrated)) = inference.owner else { return None };
        let demonstrated = demonstrated.value();
        let (first, rest) = path.split_first()?;
        let label = |label: LabelId| inference.label(label);
        let ty = if *first == columns::key() {
            match &demonstrated.key {
                None => ValueType::Unit,
                Some(key) => {
                    let field = |column: &RelationColumn| Some((column.name.clone(), label(column.label)?));
                    ValueType::Record(key.value().key.columns.iter().map(field).collect::<Option<_>>()?)
                }
            }
        } else {
            let value = columns::demonstrated_value(demonstrated)?;
            site_value_type(value.head.iter().find(|site| site.column == *first)?, &label)?
        };
        try_map_labels(&project(&ty, rest)?, &|_| None)
    }
}

/// The type of the column at `path` of `port`, a port of the component of
/// the `INIT` form whose inference is `inference`, its parameters bound as
/// the form binds them. A type that names labels of the form's scope gives
/// none.
fn port_column(inference: &FormInference<'_>, port: &crate::registry::Port, path: &[ColumnName]) -> Option<ValueType> {
    let (first, rest) = path.split_first()?;
    let column = port.columns.iter().find(|column| column.name == *first)?;
    let ty = column_type(&column.ty, rest, &inference.bindings, PoseOr::Open)?;
    try_map_labels(&ty, &|_| None)
}

/// Where a clause takes the columns of its relation from, as
/// [`Inference::clause_columns`] gives it.
enum ClauseColumns<'c> {
    /// The clause's own columns.
    Own(&'c [RelationColumn]),
    /// The declared columns of the clause's first proposer.
    Declared(&'c [Column]),
    /// The output `port` of the `INIT` form at the path.
    InstanceOutput(NodePath, &'c PortName),
}

/// The label of `clause` at its `column`, where the clause holds that
/// column.
fn head_label(clause: &crate::program::Clause, column: &ColumnName) -> Option<LabelId> {
    clause.columns.iter().find(|found| found.name == *column).map(|found| found.label)
}

/// The join of `types`, or the fault of the first two with no join.
fn join_types(types: impl Iterator<Item = ValueType>) -> Result<Option<ValueType>, LabelFault> {
    let mut joined: Option<ValueType> = None;
    for ty in types {
        joined = Some(match joined {
            None => ty,
            Some(prev) => prev.join(&ty).ok_or_else(|| LabelFault::NoJoin(prev.clone(), ty.clone()))?,
        });
    }
    Ok(joined)
}

/// The type `types` gives `label`, where it gives one.
fn typed(types: &[(LabelId, Result<Option<ValueType>, LabelFault>)], label: LabelId) -> Option<ValueType> {
    match types.iter().find(|(found, _)| *found == label)? {
        (_, Ok(ty)) => ty.clone(),
        (_, Err(_)) => None,
    }
}

/// The type each parameter of `component` takes by `instance`'s binding
/// (`docs/arclog/arclog.md#instance`), at the places that [`binding_sites`]
/// gives, with `label` giving the type of each label of the instance.
fn bind(instance: &Instance, component: &Component, label: &dyn Fn(LabelId) -> Option<ValueType>) -> StableHashMap<TypeParameter, ValueType> {
    let sites = binding_sites(instance, &component.inputs);
    let mut bindings = StableHashMap::default();
    for sites in &sites {
        let ty = match sites.binding {
            ParameterSite::Key(key) => {
                let field = |column: &RelationColumn| Some((column.name.clone(), label(column.label)?));
                key.key.columns.iter().map(field).collect::<Option<_>>().map(ValueType::Record)
            }
            ParameterSite::Head { site, .. } => site_value_type(site, label),
        };
        if let Some(ty) = ty {
            bindings.insert(sites.parameter.clone(), ty);
        }
    }
    if let Some(parameter) = key_parameter(&component.inputs).filter(|parameter| sites.iter().all(|sites| sites.parameter != *parameter)) {
        bindings.insert(parameter.clone(), ValueType::Unit);
    }
    bindings
}

/// The label that `atom` gives the field `field` of its site on the column
/// `column`, a record.
fn field_label(atom: &Atom, column: &ColumnName, field: &ColumnName) -> Option<LabelId> {
    let site = atom.sites.iter().find(|site| site.column == *column)?;
    site.value.args.iter().find_map(|arg| match arg {
        SiteArg::NamedLabel { name, label } if name == field => use_label(*label),
        SiteArg::Field(inner) if inner.column == *field => inner.value.args.iter().find_map(|arg| arg.label().and_then(use_label)),
        _ => None,
    })
}

/// The label that `atom` gives at its site on `column`, a column of one
/// label.
fn column_label(atom: &Atom, column: &ColumnName) -> Option<LabelId> {
    let site = atom.sites.iter().find(|site| site.column == *column)?;
    match &site.value.args[..] {
        [arg] => arg.label().and_then(use_label),
        _ => None,
    }
}
