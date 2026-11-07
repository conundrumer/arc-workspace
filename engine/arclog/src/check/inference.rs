//! The inference of the types of a case program's labels, form by form,
//! which the type check and the pose rule's check read: the scope of a
//! form, the walk of its sites, the types each form gives its labels, and
//! the inferences of a solver's case programs that a read of another
//! clause of a relation reaches.

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::sync::Arc;

mod state;

pub(super) use state::HeldState;

use super::frames::{FormGrids, GridCache, SharedGrids};
use super::safety::{bodies, BodyPlace};
use super::types::{
    column_type, component, declared_type, demo_rule, form_at, pose_of_fault, project, relation_columns, rule_scope_forms, scope_forms, site_value_type, site_value_type_or,
    try_map_key_rows, try_map_labels, zero_typed_heads, PoseOr,
};
use super::{ClauseEntry, FileScope, HeldClauses, Refusal, SolverClauses};
use crate::hash::{StableHash, StableHashMap, StableHashSet, StableHasher};
use crate::program::canonical::{form_scope_labels, one_scope_labels, scope_labels, LabelScope};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, Body, ColumnName, Conjunct, DemoRule, Constraint, Form, Instance, LabelId, NameScope, Node, Operand, OutputOwner, OutputStep, PortName, ProgramRelation, RelationColumn, RelationRef, Site, SiteArg,
};
use crate::program::written_inputs;
use crate::registry::{at_or_under, binding_sites, ruled_type, unbound, Column, ColumnType, Component, LibName, ParameterSite, Registry, TypeParameter};
use crate::resolver::columns;
use crate::resolver::form_columns;
use crate::resolver::registry_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram, Signature};
use crate::types::{column_label, each_site_label, flat_label_types, fresh_in_nested_form, label_type_cached, list_class, settle_label_types, sources_on, typed, TypedLabels, WalkCache, scope_lists, use_label, AssemblyId, IdentSource, KeyRow, LabelFault, SourceId, ValueType};

/// The labels of a form's own scope, with the list each label's sites stand
/// in: the conjuncts of the form's bodies, each instance input a branch of
/// its own, after an atom of its head on the input's port, and the labels
/// of the form's columns, whose scope is the whole list.
pub(super) struct ScopeBody<'a> {
    body: Body,
    heads: Vec<LabelId>,
    /// The component whose input ports the head atoms read.
    component: Option<&'a Component>,
    /// The `INIT` form whose binding types the component's parameters.
    instance: Option<&'a Instance>,
}

impl<'a> ScopeBody<'a> {
    pub(super) fn of(form: &'a Form, registry: &'a Registry) -> Self {
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
            Form::Clause(_) | Form::Choose(_) | Form::Demonstrated(_) | Form::Claim(_) | Form::Alts(_) | Form::Out(_) => {}
        }
        ScopeBody { body: Body { conjuncts: conjuncts.into() }, heads, component: found_component, instance: found_instance }
    }

    /// The list of the scope of each of `labels`, in their order.
    pub(super) fn lists(&self, labels: &[LabelId]) -> Vec<&Body> {
        let mut lists = scope_lists(&self.body, labels);
        for (label, list) in labels.iter().zip(&mut lists) {
            if self.heads.contains(label) {
                *list = &self.body;
            }
        }
        lists
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
    /// A hash of the owner form's resolved content, kept for
    /// [`FormInference::ident_source`].
    source_base: std::cell::OnceCell<StableHash>,
    /// The program in which the owner stands at `path`, which gives the
    /// owner form's resolved content.
    program: &'a ResolvedProgram,
    registry: &'a Registry,
}

/// The types of one label scope that a [`FormInference`] holds beyond its
/// owner and its walk, which two forms that differ in an atom of no site
/// alone have in common.
#[derive(Clone, Debug)]
pub(super) struct InferredTypes {
    labels: Vec<(LabelId, Result<Option<ValueType>, LabelFault>)>,
    bindings: StableHashMap<TypeParameter, ValueType>,
    zero_typed: Vec<LabelId>,
    given: Vec<LabelId>,
}

impl<'a> FormInference<'a> {
    /// The inference of `form`, a form at `path`, whose types are `types`:
    /// those of `form` itself, or of a form that differs from `form` in an
    /// atom of no site alone.
    fn of_types(types: InferredTypes, form: &'a Form, path: &NodePath, program: &'a ResolvedProgram, registry: &'a Registry) -> Self {
        let component = match form {
            Form::Instance(instance) => component(registry, &instance.value().component),
            _ => None,
        };
        let InferredTypes { labels, bindings, zero_typed, given } = types;
        FormInference { owner: ScopeOwner::Form(form), path: path.clone(), labels, bindings, walk: FormWalk::of(form), component, zero_typed, given, source_base: Default::default(), program, registry }
    }

    /// The inference of the scope of `owner` at `path` whose types are
    /// `types`, those that [`Inference::infer_form`] or
    /// [`Inference::infer_rule`] gave that scope.
    fn of_owner_types(types: InferredTypes, owner: ScopeOwner<'a>, path: &NodePath, program: &'a ResolvedProgram, registry: &'a Registry) -> Self {
        match owner {
            ScopeOwner::Form(form) => Self::of_types(types, form, path, program, registry),
            ScopeOwner::DemoRule(rule) => {
                let InferredTypes { labels, bindings, zero_typed, given } = types;
                FormInference { owner, path: path.clone(), labels, bindings, walk: FormWalk::of_rule(rule), component: None, zero_typed, given, source_base: Default::default(), program, registry }
            }
        }
    }

    /// The hash of the owner form's resolved content: that of the query at
    /// its top-level position ([`ResolvedProgram::query_content`]), which
    /// one query has in every program, or else its content in this program
    /// ([`ResolvedProgram::content`]). Neither holds a name that the program
    /// declares. A form of a case that the concept program holds too has the
    /// query content it has there ([`Self::concept_query_content`]).
    fn content_hash(&self) -> Option<StableHash> {
        let top = match &self.path.0[..] {
            [top] => self.concept_query_content().or_else(|| self.program.query_content(top.0 as usize, self.registry)),
            _ => None,
        };
        Some(top.or_else(|| self.program.content(&self.path))?.content_hash())
    }

    /// The query content that the concept program gives a form equal to the
    /// owner form, where the program is a case's. A `DET` that a case takes
    /// from the concept program has its types there, so the Idents it reads
    /// have sources of the concept program. It also resolves its reads there,
    /// so the case's graph holds none of them, and the case's own closure of
    /// a form that reads such a `DET` leaves them out.
    fn concept_query_content(&self) -> Option<crate::resolver::ResolvedContent> {
        let ScopeOwner::Form(form) = self.owner else { return None };
        let concept = self.program.concept()?;
        let position = concept.program.value().forms.iter().position(|other| crate::solver::equal_forms(other, form))?;
        concept.query_content(position, self.registry)
    }

    /// The source of the Ident values that the form makes at the output
    /// `port`, or at its declared columns where `port` is `None`:
    /// [`IdentSource::Open`] while sources are off.
    fn ident_source(&self, port: Option<&PortName>) -> IdentSource {
        use std::hash::Hash;
        let ScopeOwner::Form(form) = self.owner else { return IdentSource::Open };
        if !sources_on() {
            return IdentSource::Open;
        }
        // The resolved content, so that one query has one source in every program, and two forms of one content in one program make
        // equal Idents and have one source. A form with no content takes its name and its canonical form.
        let base = self.source_base.get_or_init(|| {
            let mut hasher = StableHasher::new();
            if let Some(content) = self.content_hash() {
                1u8.hash(&mut hasher);
                content.hash(&mut hasher);
                return hasher.finish128();
            }
            0u8.hash(&mut hasher);
            match form {
                Form::Instance(instance) => instance.value().name.hash(&mut hasher),
                Form::Clause(clause) => clause.value().derives.hash(&mut hasher),
                _ => {}
            }
            super::canonical_form(form).hash.hash(&mut hasher);
            hasher.finish128()
        });
        let mut hasher = StableHasher::new();
        base.hash(&mut hasher);
        port.hash(&mut hasher);
        IdentSource::Form(SourceId(hasher.finish128()))
    }

    /// The types of this inference, see [`InferredTypes`].
    fn types(&self) -> InferredTypes {
        InferredTypes { labels: self.labels.clone(), bindings: self.bindings.clone(), zero_typed: self.zero_typed.clone(), given: self.given.clone() }
    }

    /// The types of this inference, of a form of the concept program, given
    /// to `owner`, the same scope at `path` in a case, whose sites `walk`
    /// walks.
    fn at(&self, owner: ScopeOwner<'a>, path: &NodePath, walk: FormWalk<'a>, program: &'a ResolvedProgram) -> Self {
        FormInference {
            owner,
            path: path.clone(),
            labels: self.labels.clone(),
            bindings: self.bindings.clone(),
            walk,
            component: self.component,
            zero_typed: self.zero_typed.clone(),
            given: self.given.clone(),
            source_base: Default::default(),
            program,
            registry: self.registry,
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

    /// Whether `label` takes its type from a column of `(pose-or <type>)`
    /// alone.
    pub fn is_given(&self, label: LabelId) -> bool {
        self.given.contains(&label)
    }

    /// The field of the record bound to the type parameter of a column of
    /// type `ty` that holds `label`, a label of the form, where the form
    /// is an `INIT` form: the key's column at the label, or the field that
    /// the head site of the parameter's first projection gives the label.
    fn bound_field(&self, ty: &ColumnType, label: LabelId) -> Option<ColumnName> {
        let (ColumnType::Parameter(parameter), ScopeOwner::Form(Form::Instance(instance)), Some(component)) = (ty, self.owner, self.component) else { return None };
        let places = binding_sites(instance.value(), &component.inputs);
        match places.iter().find(|places| places.parameter == parameter)?.binding {
            ParameterSite::Key(key) => key.key.columns.iter().find(|column| column.label == label).map(|column| column.name.clone()),
            ParameterSite::Head { site, .. } => site.value.args.iter().find_map(|arg| match arg {
                SiteArg::NamedLabel { name, label: use_ } if use_label(*use_) == Some(label) => Some(name.clone()),
                SiteArg::Field(field) => match &field.value.args[..] {
                    [arg] if arg.label().and_then(use_label) == Some(label) => Some(field.column.clone()),
                    _ => None,
                },
                _ => None,
            }),
        }
    }

    /// The faults of the form's bindings of its component's bounded type
    /// parameters: for each parameter whose projections have no join, at the
    /// first site whose type has none with the sites before it, and for each
    /// parameter bound to a type that is neither the parameter's bound nor
    /// under it, the path of the place that binds it,
    /// relative to the form, and the message.
    pub fn bound_faults(&self) -> Vec<(NodePath, String)> {
        let (ScopeOwner::Form(Form::Instance(instance)), Some(component)) = (self.owner, self.component) else { return Vec::new() };
        let root = NodeRef::Instance(instance.value());
        let mut faults = Vec::new();
        for sites in binding_sites(instance.value(), &component.inputs) {
            if let ParameterSite::Head { site: first, .. } = sites.binding {
                let fields = columns::projection(first);
                let misfit = sites.later.iter().map(|(_, site)| *site).find(|site| !reads_binding(fields.as_deref(), site));
                if let Some(second) = misfit {
                    if let Some(at) = path_to(root, NodeRef::Site(second), NodePath::default()) {
                        let message = format!("a head site onto the type parameter `{}` takes more than the one label that the first site onto it binds", sites.parameter.name);
                        faults.push((at, message));
                    }
                    continue;
                }
            }
            if let (Some(_), ParameterSite::Head { site, .. }) = (&sites.parameter.bound, sites.binding) {
                let later: Vec<&Site> = sites.later.iter().map(|(_, site)| *site).collect();
                if let Err(second) = joined_projections(site, &later, &|label| self.label(label)) {
                    if let Some(at) = path_to(root, NodeRef::Site(second), NodePath::default()) {
                        faults.push((at, format!("the projections onto the type parameter `{}` give types with no join", sites.parameter.name)));
                    }
                    continue;
                }
            }
            if let (None, ParameterSite::Head { site, .. }) = (&sites.parameter.bound, sites.binding) {
                let projections: Vec<(&Site, ValueType)> = std::iter::once(site)
                    .chain(sites.later.iter().map(|(_, site)| *site))
                    .filter_map(|site| Some((site, site_value_type(site, &|label| self.label(label))?)))
                    .collect();
                let second = (1..projections.len()).find(|&at| projections[..at].iter().any(|(_, earlier)| ident_sources_clash(earlier, &projections[at].1)));
                if let Some(second) = second {
                    if let Some(at) = path_to(root, NodeRef::Site(projections[second].0), NodePath::default()) {
                        faults.push((at, format!("the projections onto the type parameter `{}` give Ident columns of two sources", sites.parameter.name)));
                    }
                    continue;
                }
            }
            let (Some(bound), Some(ty)) = (&sites.parameter.bound, self.bindings.get(sites.parameter)) else { continue };
            if at_or_under(ty, bound) {
                continue;
            }
            let place = match sites.binding {
                ParameterSite::Key(key) => NodeRef::KeyClause(key),
                ParameterSite::Head { site, .. } => NodeRef::Site(site),
            };
            let Some(at) = path_to(root, place, NodePath::default()) else { continue };
            let message = format!("the type parameter `{}` is bound to {ty:?}, which is not under its bound {bound:?}", sites.parameter.name);
            faults.push((at, message));
        }
        faults
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
    /// The types of the form's labels that the rules of a relation read, none
    /// before the first run of [`Inference::infer_new`].
    pub labels: &'r [(LabelId, Result<Option<ValueType>, LabelFault>)],
    pub component: Option<&'a Component>,
    pub bindings: &'r StableHashMap<TypeParameter, ValueType>,
    pub pose_or: PoseOr,
    /// Whether two of the form's labels stand in one grid, where the reading
    /// is of a run of [`Inference::infer_new`] that gives it; none for the
    /// reading of a finished form, whose sites then read the types that the
    /// other rules give.
    pub grids: Option<&'r dyn SharedGrids>,
}

impl<'a> FormInference<'a> {
    /// What the form's sites read their column types under.
    pub fn reading(&self, pose_or: PoseOr) -> SiteReading<'_, 'a> {
        SiteReading { path: &self.path, walk: &self.walk, labels: &self.labels, component: self.component, bindings: &self.bindings, pose_or, grids: None }
    }
}

/// The type that each clause of a [`SolverClauses`] gives one of its
/// columns, or that it adds no type, as [`Inference::other_clauses_type`]
/// reads it for a clause of the same relation, and the join of those types
/// for each clause that reads them, kept over every
/// [`super::check_program`] call on that value, so that the check of a
/// solver infers each such read once, and not once per case program it
/// checks, where the read meets no cycle of forms.
#[derive(Debug, Default)]
pub(super) struct ClauseColumnReads {
    /// A key is the clause, by its case program and its path there, the
    /// column, and the columns of the clause that reads it, whose head
    /// labels name a Pose type's key row.
    reads: RefCell<StableHashMap<(usize, NodePath, ColumnName, Arc<[RelationColumn]>), Kept<Option<ValueType>>>>,
    /// A key is the relation, the signature of the clause that reads its
    /// other clauses, the signatures of those other clauses, the column,
    /// and the columns of that clause.
    joins: RefCell<StableHashMap<(ProgramRelation, Signature, Box<[Signature]>, ColumnName, Arc<[RelationColumn]>), Kept<Result<Option<ValueType>, LabelFault>>>>,
}

impl ClauseColumnReads {
    /// The type that the clause of `entry` gives `column`, or `None` where
    /// it adds no type, read for a clause whose columns are `reader`, from
    /// `read`, kept as [`cached_unless_cycle`] gives.
    fn get_or_read(
        &self,
        entry: &ClauseEntry,
        column: &ColumnName,
        reader: &Arc<[RelationColumn]>,
        reads: &CycleReads,
        read: impl FnOnce() -> Option<ValueType>,
    ) -> Option<ValueType> {
        cached_unless_cycle(&self.reads, (entry.program, entry.at.clone(), column.clone(), Arc::clone(reader)), reads, read)
    }

    /// The join of the types that the clauses of `relation` of signatures
    /// `others`, read for the clause of signature `own`, whose columns are
    /// `reader`, give `column`, from `join`, kept as
    /// [`cached_unless_cycle`] gives.
    fn get_or_join(
        &self,
        (relation, own, others): (&ProgramRelation, Signature, Box<[Signature]>),
        column: &ColumnName,
        reader: &Arc<[RelationColumn]>,
        reads: &CycleReads,
        join: impl FnOnce() -> Result<Option<ValueType>, LabelFault>,
    ) -> Result<Option<ValueType>, LabelFault> {
        cached_unless_cycle(&self.joins, (relation.clone(), own, others, column.clone(), Arc::clone(reader)), reads, join)
    }
}

/// The types of the label scopes of the case programs of a
/// [`SolverClauses`], kept over every inference of those programs that
/// reads that value, so that a scope is inferred once and not once per
/// inference. A key is the case program, by its index in the
/// [`SolverClauses`], the address of the registry, and the path of the
/// scope's form or `DEMO_RULE` there.
///
/// An inference of a case program from the start, with no earlier layer,
/// no shared last form and not in mask mode, gives a scope the types that
/// these alone fix: the program, the registry, and the clauses and the
/// programs of the [`SolverClauses`], which holds each program by its `Arc`
/// for as long as it keeps the types. The reads of the inference are fixed
/// by those, but for the order in which it infers forms where the reads
/// meet a cycle of forms: a read of a form whose inference runs gives no
/// type. So the types of a scope are kept only where no read of their
/// inference depends on that order ([`CycleReads::ordered`]); the forms the
/// inference reads then stand on no cycle of reads, and any inference of
/// the program gives the scope the same types.
#[derive(Debug, Default)]
pub(super) struct KeptScopes {
    scopes: RefCell<StableHashMap<(usize, usize, NodePath), InferredTypes>>,
}

impl KeptScopes {
    /// The types kept of the scope at `path` of the case program of index
    /// `program`, inferred under `registry`.
    fn get(&self, program: usize, registry: &Registry, path: &NodePath) -> Option<InferredTypes> {
        self.scopes.borrow().get(&(program, registry as *const Registry as usize, path.clone())).cloned()
    }

    /// Keeps `types`, the types of the scope at `path` of the case program
    /// of index `program`, inferred under `registry`.
    fn keep(&self, program: usize, registry: &Registry, path: &NodePath, types: InferredTypes) {
        self.scopes.borrow_mut().insert((program, registry as *const Registry as usize, path.clone()), types);
    }
}

/// A value of [`cached_unless_cycle`], with whether a read of the run that
/// gave it depends on the order of inference ([`CycleReads::ordered`]).
type Kept<V> = (V, bool);

/// The reads of the inferences of one [`CaseInferences`] whose value depends
/// on the order in which forms are inferred.
#[derive(Debug, Default)]
pub(super) struct CycleReads {
    /// The number of reads so far of a form whose inference runs, each a
    /// read through a cycle of forms.
    cycles: Cell<usize>,
    /// The number of reads so far whose value depends on the order of
    /// inference: each read through a cycle of forms, and each read of a
    /// value kept from a run during which such a read was made.
    ordered: Cell<usize>,
}

impl CycleReads {
    /// Counts a read through a cycle of forms.
    fn cycle(&self) {
        self.cycles.set(self.cycles.get() + 1);
        self.order();
    }

    /// Counts a read whose value depends on the order of inference.
    fn order(&self) {
        self.ordered.set(self.ordered.get() + 1);
    }
}

/// The value `map` keeps under `key`, or else the value of `read`, which
/// it keeps there unless `reads` counts a read through a cycle of forms
/// while `read` runs, since the value then depends on the forms whose
/// inference runs. The value is kept with whether `reads` counts a read
/// that depends on the order of inference while `read` runs, and a read of
/// such a kept value counts as one.
pub(super) fn cached_unless_cycle<K: std::hash::Hash + Eq, V: Clone>(map: &RefCell<StableHashMap<K, Kept<V>>>, key: K, reads: &CycleReads, read: impl FnOnce() -> V) -> V {
    let found = map.borrow().get(&key).cloned();
    if let Some((found, ordered)) = found {
        if ordered {
            reads.order();
        }
        return found;
    }
    let (cycles, ordered) = (reads.cycles.get(), reads.ordered.get());
    let found = read();
    if reads.cycles.get() == cycles {
        map.borrow_mut().insert(key, (found.clone(), reads.ordered.get() != ordered));
    }
    found
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
    reads: CycleReads,
}

impl<'a> CaseInferences<'a> {
    pub fn new(clauses: &'a SolverClauses, registry: &'a Registry) -> Self {
        CaseInferences { clauses, registry, inferences: RefCell::default(), concepts: RefCell::default(), reads: CycleReads::default() }
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
    /// The inference of the forms before the last, where `program` is
    /// [`crate::resolver::resolve_last`]'s: it infers each form there, as
    /// [`Inference::in_concept`] gives a form the case takes from the concept
    /// program.
    earlier: Option<&'a dyn EarlierForms<'a>>,
    /// The clauses `program` holds, over which a read of the relation's
    /// other clauses runs, made on the first read.
    held: std::cell::OnceCell<HeldClauses>,
    /// Each form inferred, or `None` while its inference runs, so that a
    /// read through a cycle of forms gives no type.
    forms: RefCell<StableHashMap<NodePath, Option<Rc<FormInference<'a>>>>>,
    /// The paths of the forms inferred whose types depend on the order in
    /// which forms are inferred ([`CycleReads::ordered`]).
    ordered: RefCell<StableHashSet<NodePath>>,
    /// The signature of each clause of the program read so far, by its
    /// path, as [`super::clause_signature`] gives it.
    signatures: RefCell<StableHashMap<NodePath, Signature>>,
    /// The types of the last form of a layered inference, where the last
    /// forms of several programs differ in an atom of no site alone: the
    /// first inference of the last form leaves its types here, and each
    /// other takes them.
    shared: Option<&'a RefCell<Option<InferredTypes>>>,
    /// The form in progress at the state of the mask whose candidates
    /// this inference is `earlier` for, once held.
    state: std::cell::OnceCell<HeldState>,
    /// Whether a form may take the types of the held state: false for the
    /// inference of the state itself.
    splits: bool,
    /// Whether the inference serves a mask: a form of atoms alone takes
    /// [`Inference::flat_form`].
    fast: bool,
    /// Whether the labels of a form may stand in any order: a mask reads a
    /// form's types by label, and takes no canonical order for them.
    any_label_order: bool,
    /// The grids of the columns of the relations that this program's forms
    /// give, each read once (`check/frames.rs`).
    grids: GridCache,
}

impl std::fmt::Debug for Inference<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Inference").finish_non_exhaustive()
    }
}

/// The inference of the forms of a program, as an inference of a program
/// whose last form follows them reads it.
pub(super) trait EarlierForms<'a> {
    /// [`Inference::infer`].
    fn infer(&self, path: &NodePath) -> Option<Rc<FormInference<'a>>>;

    /// The form in progress at the mask's state, where it is held.
    fn held_state(&self) -> Option<&HeldState>;
}

impl<'a, 'e: 'a> EarlierForms<'a> for Inference<'e> {
    fn infer(&self, path: &NodePath) -> Option<Rc<FormInference<'a>>> {
        Inference::infer(self, path)
    }

    fn held_state(&self) -> Option<&HeldState> {
        self.state.get()
    }
}

impl<'a> Inference<'a> {
    /// This inference in mask mode where `enabled`, as [`Inference::is_mask`]
    /// gives.
    pub(super) fn mask(mut self, enabled: bool) -> Self { self.fast = enabled; self.any_label_order = enabled; self }

    /// Whether the inference serves a mask: it types a form of atoms alone
    /// by [`Inference::flat_form`], and its type check collects no types
    /// of relations.
    pub(in crate::check) fn is_mask(&self) -> bool { self.fast }

    /// The program this inference types.
    pub(super) fn program(&self) -> &'a ResolvedProgram {
        self.program
    }

    /// The registry the inference reads.
    pub(super) fn registry(&self) -> &'a Registry {
        self.registry
    }

    /// The count of reads so far of a form whose inference runs, as
    /// [`cached_unless_cycle`] reads it.
    pub(super) fn cycle_reads(&self) -> &CycleReads {
        &self.cases.reads
    }

    /// The grids of the columns of the relations that this program's forms
    /// give.
    pub(super) fn grid_cache(&self) -> &GridCache {
        &self.grids
    }

    /// The inference that resolves the read `atom` of a form read under
    /// `reading`, and the path of the read there: the inference of the concept
    /// program where the form stands at or under a form the case takes from
    /// it.
    pub(super) fn atom_place(&self, reading: SiteReading<'_, 'a>, atom: &Atom) -> Option<(&Inference<'a>, NodePath)> {
        if let Some((concept, at)) = self.in_concept(reading.path) {
            return concept.atom_place(SiteReading { path: &at, ..reading }, atom);
        }
        Some((self, reading.path.join(reading.walk.atoms.get(&(atom as *const Atom))?)))
    }

    /// The inference of a form whose bodies hold atoms alone, in mask mode:
    /// such a body has no `NOT`, constraint, `OR`, `IF` or `ALL`, so the type
    /// of a label is the meet of the types of all its sites
    /// ([`crate::types::label_type`]), which [`flat_label_types`] takes in
    /// one pass over the sites. The binding of the component's type
    /// parameters and the pose-or pass are as [`Inference::infer_new`] gives
    /// them. It gives `None` where a meet is empty, the form is no form of
    /// atoms alone, or it holds a site at a column that a rule types, and
    /// `infer_new` runs.
    fn flat_form(&self, form: &'a Form, path: &NodePath) -> Option<FormInference<'a>> {
        let component = match form {
            Form::Instance(instance) => {
                let c = component(self.registry, &instance.value().component)?;
                Some(c)
            }
            Form::Clause(_) | Form::Choose(_) | Form::RigidDet(_) | Form::Out(_) => None,
            _ => return None,
        };
        if !bodies(NodeRef::from(form)).iter().all(|b| b.body.value().conjuncts.iter().all(|c| matches!(c, Conjunct::Atom(_)))) { return None; }
        let walk = FormWalk::of(form);
        if self.holds_ruled_site(&walk) { return None; }
        let mut bindings = StableHashMap::default();
        let type_all = |pose_or, bindings: &StableHashMap<TypeParameter, ValueType>| -> Option<StableHashMap<LabelId, Option<ValueType>>> {
            let reading = SiteReading { path, walk: &walk, labels: &[], component, bindings, pose_or, grids: None };
            let sites = walk.uses.iter().map(|site| {
                let head;
                let atom = match site.atom {
                    Some(atom) => atom,
                    None => {
                        // Head sites read their input's declared port.
                        let mut at = site.at.clone();
                        let port = loop {
                            if let Some(NodeRef::InstanceInput(input)) = crate::program::path::node_at(NodeRef::from(form), &at) { break &input.name; }
                            if at.0.is_empty() { return None; }
                            at = NodePath(at.0[..at.0.len() - 1].into());
                        };
                        head = Atom { relation: RelationRef::DefinedPort(port.clone()), sites: Arc::from([]) };
                        &head
                    }
                };
                Some((site.label, self.site_type(reading, atom, &site.column)))
            });
            flat_label_types(sites.collect::<Option<Vec<_>>>()?)
        };
        let mut all = type_all(PoseOr::Open, &bindings)?;
        if let (Form::Instance(instance), Some(component)) = (form, component) {
            if !component.type_parameters.is_empty() {
                bindings = bind(instance.value(), component, &|label| all.get(&label).cloned().flatten());
                all = type_all(PoseOr::Open, &bindings)?;
            }
        }
        let members = self.scope_labels_of(form);
        let mut given = if members.iter().any(|label| all.get(label).and_then(Option::as_ref).is_none()) { type_all(PoseOr::Given, &bindings)? } else { StableHashMap::default() };
        let mut given_labels = Vec::new();
        let mut labels: Vec<_> = members.iter().map(|label| {
            let open = all.remove(label).flatten();
            let ty = open.or_else(|| {
                let ty = given.remove(label).flatten();
                if ty.is_some() { given_labels.push(*label); }
                ty
            });
            (*label, Ok(ty))
        }).collect();
        self.share_pose(SiteReading { path, walk: &walk, labels: &[], component, bindings: &bindings, pose_or: PoseOr::Open, grids: None }, &mut labels);
        Some(FormInference { owner: ScopeOwner::Form(form), path: path.clone(), labels, bindings, walk, component, zero_typed: Vec::new(), given: given_labels, source_base: Default::default(), program: self.program, registry: self.registry })
    }

    /// A scalar column type fixed by the already finished forms. No type
    /// bound by the candidate's in-progress instance is read here.
    pub(in crate::check) fn fixed_column_type(&self, relation: &RelationRef, column: &ColumnName) -> Option<ValueType> {
        let ty = match relation {
            RelationRef::Lib(_) | RelationRef::Fact(_) => {
                let column = registry_columns::typed_columns(self.registry, relation)?.iter().find(|found| found.name == *column)?;
                let ColumnType::Fixed(ty) = &column.ty else { return None };
                ty.clone()
            }
            _ => {
                let node = self.program.program_read(relation)?;
                let atom = Atom { relation: relation.clone(), sites: Arc::from([]) };
                self.node_type(node, &atom, std::slice::from_ref(column), PoseOr::Open)?
            }
        };
        ty.is_scalar().then_some(ty)
    }

    pub fn new(program: &'a ResolvedProgram, cases: &'a CaseInferences<'a>) -> Self {
        let concept = program.concept().map(|concept| cases.concept(concept));
        Inference { program, registry: cases.registry, cases, concept, earlier: None, held: std::cell::OnceCell::new(), forms: RefCell::default(), ordered: RefCell::default(), signatures: RefCell::default(), shared: None, state: std::cell::OnceCell::new(), splits: true, fast: false, any_label_order: false, grids: GridCache::default() }
    }

    /// The inference of `program`, a resolution by [`crate::resolver::resolve_last`]
    /// over the forms that `earlier` infers.
    pub fn layered(program: &'a ResolvedProgram, cases: &'a CaseInferences<'a>, earlier: &'a dyn EarlierForms<'a>) -> Self {
        Inference { earlier: Some(earlier), ..Inference::new(program, cases) }
    }

    /// This inference of a layered program, with the types of its last form
    /// in `shared`: the programs whose inferences share `shared` differ in
    /// an atom of no site of their last forms alone, and an atom reads the
    /// types of a form only through its sites.
    pub fn sharing_last(self, shared: &'a RefCell<Option<InferredTypes>>) -> Self {
        Inference { shared: Some(shared), ..self }
    }

    /// The types of the form `form` at `path`: [`Inference::infer_new`], or
    /// the types of the last form that the inference shares, where `form`
    /// is the program's last form. A resolution that is not layered leaves
    /// the forms before the last to this inference too, each a top-level
    /// form of types of its own.
    fn infer_form(&self, form: &'a Form, path: &NodePath) -> FormInference<'a> {
        let last = self.program.program.value().forms.len().checked_sub(1);
        let is_last = matches!(&path.0[..], [top] if Some(top.0 as usize) == last);
        let Some(shared) = self.shared.filter(|_| is_last) else { return self.infer_new(form, path) };
        if let Some(types) = shared.borrow().as_ref() {
            return FormInference::of_types(types.clone(), form, path, self.program, self.registry);
        }
        let inferred = self.infer_new(form, path);
        *shared.borrow_mut() = Some(inferred.types());
        inferred
    }

    /// The signature of the clause at `path` of the program.
    fn signature(&self, path: &NodePath) -> Signature {
        let mut signatures = self.signatures.borrow_mut();
        signatures.entry(path.clone()).or_insert_with(|| super::clause_signature(self.program, path)).clone()
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
        if let Some(earlier) = self.earlier.filter(|_| self.program.in_earlier_forms(path)) {
            return earlier.infer(path);
        }
        if let Some(found) = self.forms.borrow().get(path) {
            if found.is_none() {
                self.cases.reads.cycle();
            } else if self.ordered.borrow().contains(path) {
                self.cases.reads.order();
            }
            return found.clone();
        }
        let program = self.program.program.value();
        let owner = match form_at(program, path) {
            Some(form) => ScopeOwner::Form(form),
            None => ScopeOwner::DemoRule(demo_rule(program, path)?),
        };
        let ordered = self.cases.reads.ordered.get();
        if let Some((concept, at)) = self.in_concept(path) {
            let walk = match owner {
                ScopeOwner::Form(form) => FormWalk::of(form),
                ScopeOwner::DemoRule(rule) => FormWalk::of_rule(rule),
            };
            let inferred = Rc::new(concept.infer(&at)?.at(owner, path, walk, self.program));
            self.forms.borrow_mut().insert(path.clone(), Some(Rc::clone(&inferred)));
            if self.cases.reads.ordered.get() != ordered {
                self.ordered.borrow_mut().insert(path.clone());
            }
            return Some(inferred);
        }
        let kept = self.kept_program().map(|program| (program, self.cases.clauses.kept_scopes()));
        if let Some(types) = kept.and_then(|(program, scopes)| scopes.get(program, self.registry, path)) {
            crate::stats::tick(crate::stats::Phase::InferFormKept);
            let inferred = Rc::new(FormInference::of_owner_types(types, owner, path, self.program, self.registry));
            self.forms.borrow_mut().insert(path.clone(), Some(Rc::clone(&inferred)));
            return Some(inferred);
        }
        self.forms.borrow_mut().insert(path.clone(), None);
        let inferred = Rc::new(match owner {
            ScopeOwner::Form(form) => self.infer_form(form, path),
            ScopeOwner::DemoRule(rule) => self.infer_rule(rule, path),
        });
        self.forms.borrow_mut().insert(path.clone(), Some(Rc::clone(&inferred)));
        if self.cases.reads.ordered.get() != ordered {
            self.ordered.borrow_mut().insert(path.clone());
        } else if let Some((program, scopes)) = kept {
            scopes.keep(program, self.registry, path, inferred.types());
        }
        Some(inferred)
    }

    /// The labels of the scope of `form`: in their canonical order, or in
    /// any order where the inference allows it and takes no labeling for it.
    fn scope_labels_of<'f>(&self, form: &'f Form) -> std::borrow::Cow<'f, [LabelId]> {
        match self.any_label_order.then(|| one_scope_labels(form)).flatten() {
            Some(labels) => labels.into(),
            None => form_scope_labels(form).into(),
        }
    }

    /// The index in the [`SolverClauses`] of this inference's program, where
    /// the types this inference gives are those that [`KeptScopes`] keeps:
    /// an inference of a case program of the [`SolverClauses`] from the
    /// start, with no earlier layer, no shared last form and not in mask
    /// mode.
    fn kept_program(&self) -> Option<usize> {
        if self.earlier.is_some() || self.shared.is_some() || self.fast {
            return None;
        }
        self.cases.clauses.index_of(self.program)
    }

    fn infer_new(&self, form: &'a Form, path: &NodePath) -> FormInference<'a> {
        // A layered inference infers only the forms its earlier layer does not hold: the form in progress.
        let _timed = crate::stats::span(if self.earlier.is_some() { crate::stats::Phase::InferFormOpen } else { crate::stats::Phase::InferFormFinished });
        if self.fast {
            if let Some(inferred) = self.flat_form(form, path) { return inferred; }
        }
        let scope = ScopeBody::of(form, self.registry);
        let walk = FormWalk::of(form);
        let all_labels = self.scope_labels_of(form);
        let ruled = self.holds_ruled_site(&walk);
        let framed = self.holds_framed_site(&walk);
        let split = if ruled { None } else { self.state_split(form, path, &all_labels) };
        let labels = match &split {
            Some((_, own)) => own.clone(),
            None => all_labels.to_vec(),
        };
        let lists = scope.lists(&labels);
        let key = scope.instance.and_then(|instance| instance.key.as_ref()).map(|key| key.value().key.body.value());
        let no_bindings = StableHashMap::default();
        let type_all = |bindings: &StableHashMap<TypeParameter, ValueType>, pose_or: PoseOr, prior: &TypedLabels| -> TypedLabels {
            let reading = SiteReading { path, walk: &walk, labels: prior, component: scope.component, bindings, pose_or, grids: None };
            let grids = framed.then(|| FormGrids::new(self, reading, &scope));
            let reading = SiteReading { grids: grids.as_ref().map(|grids| grids as &dyn SharedGrids), ..reading };
            let site_type = |atom: &Atom, column: &[ColumnName]| self.site_type(reading, atom, column);
            // With no key clause, the labels of one class in one scope list
            // that are fresh in no form nested in it take one walk.
            let cache = WalkCache::default();
            let mut walked: Vec<(&Body, Vec<LabelId>, Result<Option<ValueType>, LabelFault>)> = Vec::new();
            let mut types = Vec::with_capacity(labels.len());
            for (label, list) in labels.iter().zip(&lists) {
                let shared = key.is_none() && !fresh_in_nested_form(list, *label, &cache);
                let found = shared.then(|| walked.iter().find(|(l, class, _)| std::ptr::eq(*l, *list) && class.contains(label))).flatten();
                let ty = match found {
                    Some((_, _, ty)) => ty.clone(),
                    None => {
                        let ty = label_type_cached(list, *label, &site_type, key, &cache);
                        if shared {
                            walked.push((list, list_class(list, *label), ty.clone()));
                        }
                        ty
                    }
                };
                types.push((*label, ty));
            }
            types
        };
        // The types that the rules of a relation give a site read the types of
        // the other labels, so a form with such a site is typed again under
        // the last run's types while a site gives its label a narrower type.
        let settle = |bindings: &StableHashMap<TypeParameter, ValueType>, prior: &TypedLabels| -> TypedLabels {
            let first = type_all(bindings, PoseOr::Open, prior);
            if !ruled {
                return first;
            }
            let narrows = |prior: &TypedLabels| {
                let reading = SiteReading { path, walk: &walk, labels: prior, component: scope.component, bindings, pose_or: PoseOr::Open, grids: None };
                let grids = framed.then(|| FormGrids::new(self, reading, &scope));
                let reading = SiteReading { grids: grids.as_ref().map(|grids| grids as &dyn SharedGrids), ..reading };
                let ruled_uses = walk.uses.iter().filter(|site| self.is_ruled_use(site));
                ruled_uses.filter_map(|site| Some((site.label, self.site_type(reading, site.atom?, &site.column)?))).any(|(label, site)| !typed(prior, label).is_some_and(|label| at_or_under(&label, &site)))
            };
            settle_label_types(first, narrows, |prior| type_all(bindings, PoseOr::Open, prior))
        };
        let mut types = settle(&no_bindings, &Vec::new());
        let mut bindings = StableHashMap::default();
        if let (Some(instance), Some(component)) = (scope.instance, scope.component) {
            if !component.type_parameters.is_empty() {
                bindings = bind(instance, component, &|label| typed(&types, label));
                types = settle(&bindings, &types);
            }
        }
        let mut given_labels = Vec::new();
        if types.iter().any(|(_, ty)| matches!(ty, Ok(None))) {
            let given = type_all(&bindings, PoseOr::Given, &types);
            for ((label, ty), (_, given)) in types.iter_mut().zip(given) {
                if matches!(ty, Ok(None)) && !matches!(given, Ok(None)) {
                    *ty = given;
                    given_labels.push(*label);
                }
            }
        }
        if let Some((state, _)) = &split {
            let own = std::mem::take(&mut types);
            types = all_labels
                .iter()
                .map(|label| match own.iter().find(|(found, _)| found == label) {
                    Some(found) => found.clone(),
                    None => (*label, state.label(*label).expect("a label the split leaves to the state's inference").clone()),
                })
                .collect();
        }
        let mut zero_typed = Vec::new();
        if let (Form::Clause(clause), None) = (form, &split) {
            let clause = clause.value();
            for label in zero_typed_heads(clause) {
                let Some((_, ty)) = types.iter_mut().find(|(found, _)| *found == label) else { continue };
                let Some(column) = clause.columns.iter().find(|column| column.label == label) else { continue };
                *ty = match self.other_clauses_type(clause, path, &column.name) {
                    Ok(None) => Ok(self.solver_clauses_type(clause, &column.name)),
                    others => others,
                };
                zero_typed.push(label);
            }
        }
        // A label local to alternatives can have no whole-list restriction:
        // one alternative does not produce it. Its produced values still
        // need a concrete storage type in every checked IR compile. Infer
        // those binding types separately after parameter/header inference;
        // never let an absent branch erase a known value type.
        if types.iter().any(|(_,ty)|matches!(ty,Ok(None))) {
            let prior=types.clone();
            let reading=SiteReading {path,walk:&walk,labels:&prior,component:scope.component,bindings:&bindings,pose_or:PoseOr::Given,grids:None};
            let grids=framed.then(||FormGrids::new(self,reading,&scope));
            let reading=SiteReading {grids:grids.as_ref().map(|g|g as &dyn SharedGrids),..reading};
            let site_type=|atom:&Atom,column:&[ColumnName]|self.site_type(reading,atom,column);
            let cache=WalkCache::default();
            for ((label,ty),list) in types.iter_mut().zip(scope.lists(&all_labels)) {
                if matches!(ty,Ok(None)) && !scope.heads.contains(label) {
                    *ty=crate::types::label_binding_type_cached(list,*label,&site_type,key,&cache);
                }
            }
        }
        self.share_pose(SiteReading { path, walk: &walk, labels: &[], component: scope.component, bindings: &bindings, pose_or: PoseOr::Open, grids: None }, &mut types);
        FormInference { owner: ScopeOwner::Form(form), path: path.clone(), labels: types, bindings, walk, component: scope.component, zero_typed, given: given_labels, source_base: Default::default(), program: self.program, registry: self.registry }
    }

    /// The types of the scope of `rule`, the `DEMO_RULE` at `path`: each
    /// label of its fields and of its forms that stand in its scope takes
    /// the meet of the types that the inference of each such form, at its
    /// own path, gives it, so that its type comes from each of its sites in
    /// the rule.
    fn infer_rule(&self, rule: &'a DemoRule, path: &NodePath) -> FormInference<'a> {
        let mut labels: Vec<(LabelId, Result<Option<ValueType>, LabelFault>)> =
            scope_labels(LabelScope::DemoRule(rule)).iter().map(|label| (*label, Ok(None))).collect();
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
        FormInference { owner: ScopeOwner::DemoRule(rule), path: path.clone(), labels, bindings: no_bindings, walk: FormWalk::of_rule(rule), component: None, zero_typed: Vec::new(), given, source_base: Default::default(), program: self.program, registry: self.registry }
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
            Resolution::Lib(name) => {
                let declared = declared_type(registry_columns::lib_typed_columns(self.registry, name)?, path, reading.pose_or)?;
                Some(self.ruled(reading, atom, name, path, declared))
            }
            Resolution::Node(_) if path == [columns::example()] && self.program.reads_lifted(&at) => Some(ValueType::Example),
            Resolution::Node(node) => self.node_type(*node, atom, path, reading.pose_or),
            Resolution::Undefined(_) | Resolution::Unresolved => None,
        }
    }

    /// The type that the column at `path` of the lib relation `name` gives a
    /// site of `atom`, a site of a form read under `reading`, where it
    /// declares `declared`: the declared type, or the type that the rules
    /// of the relation give the column, read under the types of the labels
    /// that `reading` holds.
    fn ruled(&self, reading: SiteReading<'_, 'a>, atom: &Atom, name: &LibName, path: &[ColumnName], declared: ValueType) -> ValueType {
        let ([column], Some(relation)) = (path, self.registry.algebra_relation(name)) else { return declared };
        ruled_type(declared, &relation.rules, column, atom, &|label| typed(reading.labels, label), &|a, b| reading.grids.is_some_and(|grids| grids.share(a, b)))
    }

    /// Whether `site` stands at a column that a rule of its relation gives a
    /// type.
    fn is_ruled_use(&self, site: &SiteUse<'_>) -> bool {
        self.relation_of_use(site).is_some_and(|(relation, column)| relation.is_ruled(column))
    }

    /// The algebra relation `site` stands in, and the column it stands at,
    /// where its atom reads a lib relation and the site is on one column.
    fn relation_of_use<'s>(&self, site: &'s SiteUse<'_>) -> Option<(&'a crate::registry::AlgebraRelation, &'s ColumnName)> {
        let (Some(Atom { relation: RelationRef::Lib(name), .. }), [column]) = (site.atom, &site.column[..]) else { return None };
        Some((self.registry.algebra_relation(name)?, column))
    }

    /// Whether a site of `walk` stands at a column that a rule of its
    /// relation with a `same-frame` condition gives a type.
    fn holds_framed_site(&self, walk: &FormWalk<'_>) -> bool {
        let framed = |site: &SiteUse<'_>| self.relation_of_use(site).is_some_and(|(relation, column)| relation.is_framed(column));
        walk.uses.iter().any(framed)
    }

    /// Whether a site of `walk` stands at a column that a rule of its
    /// relation gives a type.
    fn holds_ruled_site(&self, walk: &FormWalk<'_>) -> bool {
        walk.uses.iter().any(|site| self.is_ruled_use(site))
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

    /// Gives each label of `labels` that stands at no type, and at a column
    /// of a lib relation of type Pose that each column of its relation
    /// shares, the Pose type of the labels at the other such columns of the
    /// same atom, where those labels have one Pose type: `pose_difference(a,
    /// b, d)` reads two poses of one assembly
    /// (`docs/arclog/rigid.md#the-pose`). A label that takes a type here
    /// shares it with the labels at such columns of each other atom it
    /// stands at. `labels` holds the types of the form read under `reading`.
    fn share_pose(&self, reading: SiteReading<'_, 'a>, labels: &mut [(LabelId, Result<Option<ValueType>, LabelFault>)]) {
        let mut atoms: Vec<(*const Atom, Vec<LabelId>)> = Vec::new();
        for site in &reading.walk.uses {
            let Some(atom) = site.atom else { continue };
            if !self.shares_pose(reading, atom, &site.column) {
                continue;
            }
            let key = atom as *const Atom;
            match atoms.iter_mut().find(|(found, _)| *found == key) {
                Some((_, group)) if !group.contains(&site.label) => group.push(site.label),
                Some(_) => {}
                None => atoms.push((key, vec![site.label])),
            }
        }
        let mut changed = true;
        while std::mem::take(&mut changed) {
            for (_, group) in &atoms {
                let shared = group.iter().filter_map(|label| typed(labels, *label)).try_fold(None, |met, ty| crate::types::meet(met, Some(ty)));
                let Ok(Some(pose @ ValueType::Pose(_))) = shared else { continue };
                for (_, ty) in labels.iter_mut().filter(|(label, ty)| group.contains(label) && matches!(ty, Ok(None))) {
                    *ty = Ok(Some(pose.clone()));
                    changed = true;
                }
            }
        }
    }

    /// The type of the column at `path` of the relation of `node`, read by
    /// `atom`.
    fn node_type(&self, node: GraphNodeIndex, atom: &Atom, path: &[ColumnName], pose_or: PoseOr) -> Option<ValueType> {
        let graph_node = &self.program.graph.nodes[node.0 as usize];
        let form_path = self.program.form_of(node);
        let reader = |column: &ColumnName| column_label(atom, column);
        let key_row = |column: &ColumnName, fields: &[ColumnName]| {
            Some(KeyRow::Labels(fields.iter().map(|field| field_label(atom, column, field)).collect::<Option<_>>()?))
        };
        match &graph_node.kind {
            DependencyKind::Fact(fact) => declared_type(self.registry.fact_columns(*fact), path, PoseOr::Open),
            DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => {
                self.relation_type(&graph_node.scope, relation, path, &reader, pose_or).ok().flatten()
            }
            DependencyKind::Chosen(name) => match form_at(self.program.program.value(), form_path)? {
                Form::Choose(choose) => {
                    let columns: Vec<&RelationColumn> = form_columns::form_columns(NodeRef::Choose(choose.value())).collect();
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
            DependencyKind::InstanceOutput { output, .. } => self.instance_output(form_path, output, path, &key_row),
            DependencyKind::RecursiveInstance(_) => match &atom.relation {
                RelationRef::Output(output) => match &output.path[..] {
                    [OutputStep::Port(port)] => self.instance_output(form_path, port, path, &key_row),
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
            DependencyKind::InstanceInput { input, .. } => self.instance_input(form_path, input, path, &key_row),
            DependencyKind::Out(_) => None,
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
        let (scope_at, forms) = scope_forms(self.program.program.value(), scope);
        let clauses = forms.filter_map(|(index, form)| match form {
            Form::Clause(clause) if clause.value().derives == *relation => Some((index, clause.value())),
            _ => None,
        });
        join_types(clauses.filter_map(|(index, clause)| self.clause_column(&scope_at.child(index), clause, scope, path, target, pose_or)))
    }

    /// The join of the types that the other clauses of the relation of
    /// `clause`, the clause at `path`, in [`SolverClauses`] that this
    /// inference's case program holds give its `column`, each in the case
    /// program it was found in, or the fault of
    /// two types with no join. A clause whose label at that column only
    /// `(= *X 0)` gives a type adds no type. A Pose type's key row names
    /// the labels of `clause`.
    fn other_clauses_type(&self, clause: &crate::program::Clause, path: &NodePath, column: &ColumnName) -> Result<Option<ValueType>, LabelFault> {
        // A relation of no clause in the programs has no other clause to read,
        // and this clause's signature, which a read compares, takes a write of it.
        if self.cases.clauses.of_relation(&FileScope::Program, &clause.derives).is_empty() {
            return Ok(None);
        }
        let own = self.signature(path);
        let reads = self.cases.clauses.column_reads();
        let entries: Vec<&ClauseEntry> = self.cases.clauses.of_relation_in(&clause.derives, self.held.get_or_init(|| HeldClauses::of(self.program))).filter(|entry| entry.signature != own).collect();
        let others: Box<[Signature]> = entries.iter().map(|entry| entry.signature.clone()).collect();
        reads.get_or_join((&clause.derives, own, others), column, &clause.columns, &self.cases.reads, || {
            let target = |column: &ColumnName| head_label(clause, column);
            let types = entries.iter().filter_map(|entry| self.entry_column_type(entry, clause, column, &target));
            join_types(types)
        })
    }

    /// The join of the types that the clauses of the relation of `clause`
    /// in the solver's other case programs, those that the case program
    /// under check does not hold, give its `column`, each in the case
    /// program it was found in, or `None` where they give none or have no
    /// join.
    fn solver_clauses_type(&self, clause: &crate::program::Clause, column: &ColumnName) -> Option<ValueType> {
        let held = self.held.get_or_init(|| HeldClauses::of(self.program));
        let in_program: Vec<&Signature> = self.cases.clauses.of_relation_in(&clause.derives, held).map(|entry| &entry.signature).collect();
        let target = |column: &ColumnName| head_label(clause, column);
        let entries = self.cases.clauses.of_relation(&FileScope::Program, &clause.derives).iter().filter(|entry| !in_program.contains(&&entry.signature));
        join_types(entries.filter_map(|entry| self.entry_column_type(entry, clause, column, &target))).ok().flatten()
    }

    /// The type that the clause of `entry`, typed in the case program it
    /// was found in, gives `column`, read for `reader`, or `None` where it
    /// adds no type: a clause whose label at that column only `(= *X 0)`
    /// gives a type adds none.
    fn entry_column_type(&self, entry: &ClauseEntry, reader: &crate::program::Clause, column: &ColumnName, target: &dyn Fn(&ColumnName) -> Option<LabelId>) -> Option<ValueType> {
        let reads = self.cases.clauses.column_reads();
        reads.get_or_read(entry, column, &reader.columns, &self.cases.reads, || {
            let inference = self.cases.of(entry);
            let Some(Form::Clause(other)) = form_at(inference.program.program.value(), &entry.at) else {
                unreachable!("an entry of a relation in the program's scope stands at a clause of the program it was found in")
            };
            let other = other.value();
            let zero_typed = zero_typed_heads(other);
            if other.columns.iter().any(|found| found.name == *column && zero_typed.contains(&found.label)) {
                return None;
            }
            inference.clause_column(&entry.at, other, &NameScope::Program, std::slice::from_ref(column), target, PoseOr::Given)
        })
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
        let (scope_at, mut forms) = scope_forms(self.program.program.value(), scope);
        let (index, _) = forms.find(|(_, form)| matches!(form, Form::Instance(instance) if instance.value().name == *name))?;
        Some(ClauseColumns::InstanceOutput(scope_at.child(index), port))
    }

    /// The names of the columns of the relation of `clause`, a clause of
    /// `scope`, as the clause gives them.
    fn clause_column_names(&self, clause: &crate::program::Clause, scope: &NameScope) -> Vec<ColumnName> {
        match self.clause_columns(clause, scope) {
            None => Vec::new(),
            Some(ClauseColumns::Own(columns)) => columns.iter().map(|column| column.name.clone()).collect(),
            Some(ClauseColumns::Declared(columns)) => columns.iter().map(|column| column.name.clone()).collect(),
            Some(ClauseColumns::InstanceOutput(instance, port)) => {
                let Some(inference) = self.infer(&instance) else { return Vec::new() };
                let (Some(component), ScopeOwner::Form(Form::Instance(owner))) = (inference.component, inference.owner) else { return Vec::new() };
                let output = component.outputs.iter().find(|output| output.name == *port);
                output.map(|output| output.columns_at(owner.value().key.is_some()).map(|column| column.name.clone()).collect()).unwrap_or_default()
            }
        }
    }

    /// The refusals of `clause`, the top-level clause at `path` whose
    /// inference is `form`, a form whose canonical order is `order`, at each
    /// column of its relation to which it gives a type with no join with
    /// the types that the relation's other clauses give that column, as
    /// [`CheckId::Types`] gives.
    pub(super) fn column_refusals(&self, form: &FormInference<'_>, clause: &crate::program::Clause, path: &NodePath, place: &dyn Fn(&NodePath) -> NodePath) -> Vec<Refusal> {
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
            let at = label.map_or_else(NodePath::default, |label| place(form.walk.first_use(label)));
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
            ClauseColumns::Declared(columns) => match declared_type(columns, path, pose_or)? {
                ValueType::Ident(IdentSource::Open) if sources_on() => Some(ValueType::Ident(self.infer(at)?.ident_source(None))),
                ty => Some(ty),
            },
            ClauseColumns::InstanceOutput(instance, port) => self.instance_output(&instance, port, path, &|_, _| None),
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
                let node = self.program.nodes_of(at).first().expect("the resolver gives each clause a node");
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
                for port in component.relation_ports(&written) {
                    relations.push((Arc::from([OutputStep::Port(port.name.clone())]), port_relation(&inference, port, instance.value().key.is_some())));
                }
            }
            Form::RigidDet(rigid) => {
                let key_row = |key: &[RelationColumn]| Some(KeyRow::Columns((0..key.len() as u16).collect()));
                for (output, names) in form_columns::rigid_outputs(rigid.value()) {
                    let column = |name: &ColumnName| self.rigid_output(at, &output, std::slice::from_ref(name), &key_row);
                    let types = relation_columns(names.names(), &column);
                    relations.push((output, types));
                }
            }
            Form::Demonstrated(demonstrated) => {
                let names = form_columns::demonstrated_columns(demonstrated.value());
                let column = |name: &ColumnName| self.demonstrated_column(at, std::slice::from_ref(name));
                relations.push((Arc::from([]), relation_columns(names.names(), &column)));
            }
            Form::Clause(_) | Form::Choose(_) | Form::Claim(_) | Form::Alts(_) | Form::Out(_) => {}
        }
        relations.into_iter().filter_map(|(output, columns)| Some((output, columns?))).collect()
    }

    /// The type of the column at `path` of the output `port` of the `INIT`
    /// form at `at`, its parameters bound as the form binds them, as
    /// [`port_column`] gives it for the `key_row` it is given.
    fn instance_output(&self, at: &NodePath, port: &PortName, path: &[ColumnName], key_row: &dyn Fn(&ColumnName, &[ColumnName]) -> Option<KeyRow>) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let output = inference.component?.outputs.iter().find(|output| output.name == *port)?;
        port_column(&inference, output, path, key_row)
    }

    /// The type of the column at `path` of the input `port` of the `INIT`
    /// form at `at`, its parameters bound as the form binds them, as
    /// [`port_column`] gives it for the `key_row` it is given.
    fn instance_input(&self, at: &NodePath, port: &PortName, path: &[ColumnName], key_row: &dyn Fn(&ColumnName, &[ColumnName]) -> Option<KeyRow>) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let input = inference.component?.inputs.iter().find(|input| input.port.name == *port)?;
        port_column(&inference, &input.port, path, key_row)
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
        // A form with no key clause has no `key` column of its own, so a
        // `key` column there is a part's, such as a keyed `INIT` output's.
        if let (true, Some(key_body)) = (*first == key, &rigid_value.key) {
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
        let part = rigid_value.parts.iter().find(|part| form_columns::part_steps(&part.value().relation).as_deref() == Some(output))?;
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
                None => return None,
                Some(key) => {
                    let field = |column: &RelationColumn| Some((column.name.clone(), label(column.label)?));
                    ValueType::Record(key.value().key.columns.iter().map(field).collect::<Option<_>>()?)
                }
            }
        } else {
            let value = form_columns::demonstrated_value(demonstrated)?;
            site_value_type(value.head.iter().find(|site| site.column == *first)?, &label)?
        };
        try_map_labels(&project(&ty, rest)?, &|_| None)
    }
}

/// The type of the column at `path` of `port`, a port of the component of
/// the `INIT` form whose inference is `inference`, its parameters bound as
/// the form binds them. A Pose type of a keyed assembly names labels of the
/// form's scope: where each of them stands at a field of the record that the
/// column's parameter is bound to, the type names its key row as `key_row`
/// gives it from the column and those fields (`docs/arclog/rigid.md#the-pose`);
/// a type that names any other label of the scope gives none.
fn port_column(
    inference: &FormInference<'_>,
    port: &crate::registry::Port,
    path: &[ColumnName],
    key_row: &dyn Fn(&ColumnName, &[ColumnName]) -> Option<KeyRow>,
) -> Option<ValueType> {
    let (first, rest) = path.split_first()?;
    let column = port.columns.iter().find(|column| column.name == *first)?;
    let ty = column_type(&column.ty, rest, &inference.bindings, PoseOr::Open)?;
    let makes = inference.component.is_some_and(|component| component.outputs.iter().any(|output| output.name == port.name));
    let ty = match ty {
        ValueType::Ident(IdentSource::Open) if makes && matches!(column.ty, ColumnType::Fixed(_)) => ValueType::Ident(inference.ident_source(Some(&port.name))),
        ty => ty,
    };
    try_map_key_rows(&ty, &|labels| key_row(first, &labels.iter().map(|label| inference.bound_field(&column.ty, *label)).collect::<Option<Vec<_>>>()?))
}

/// The types of the columns of the relation of `port`, a port of the
/// component of the `INIT` form whose inference is `inference`, at an
/// instance that has a key clause where `keyed` holds, each name's type as
/// [`port_column`] gives it, with a Pose type's key row naming the positions
/// of the relation's columns that hold the key, as [`KeyRow::Columns`] gives
/// them.
fn port_relation(inference: &FormInference<'_>, port: &crate::registry::Port, keyed: bool) -> Option<Box<[ValueType]>> {
    let names: Vec<&ColumnName> = port.columns_at(keyed).map(|column| &column.name).collect();
    let bare = |name: &ColumnName| port_column(inference, port, std::slice::from_ref(name), &|_, _| Some(KeyRow::Unkeyed));
    let mut starts: Vec<(&ColumnName, usize)> = Vec::new();
    let mut at = 0;
    for name in &names {
        starts.push((name, at));
        at += relation_columns([*name], &bare)?.len();
    }
    let key_row = |column: &ColumnName, fields: &[ColumnName]| {
        let start = starts.iter().find(|(name, _)| *name == column)?.1;
        let ValueType::Record(record) = bare(column)? else { return None };
        let position = |field: &ColumnName| {
            let index = record.iter().position(|(name, _)| name == field)?;
            let before = relation_columns(record[..index].iter().map(|(name, _)| name), &|name| record.iter().find(|(found, _)| found == name).map(|(_, ty)| ty.clone()))?;
            u16::try_from(start + before.len()).ok()
        };
        Some(KeyRow::Columns(fields.iter().map(position).collect::<Option<_>>()?))
    };
    relation_columns(names, &|name| port_column(inference, port, std::slice::from_ref(name), &key_row))
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

/// Whether `site`, a head site onto a type parameter after the site that
/// binds it, takes one label where the binding site projects one label
/// (`fields` none), as the evaluation of the form reads it. A site after a
/// binding record is not tested: the search for the completions of a head
/// site (`Decoder::completes_projection`) finds a record's fields only after
/// a search that its budget does not cover.
fn reads_binding(fields: Option<&[ColumnName]>, site: &Site) -> bool {
    if fields.is_some() {
        return true;
    }
    let mut labels = 0;
    each_site_label(site, &mut Vec::new(), &mut |use_, _| labels += usize::from(use_label(use_).is_some()));
    labels == 1
}

/// The path of the node `target` among the descendants of `root`, which stands
/// at `at`, or `None` where `root` does not hold it.
fn path_to(root: NodeRef<'_>, target: NodeRef<'_>, at: NodePath) -> Option<NodePath> {
    use crate::program::path::PathNode;
    for (child, index) in root.children().into_iter().zip(0u32..) {
        let at = at.child(index);
        if std::mem::discriminant(&child) == std::mem::discriminant(&target) && child.address() == target.address() {
            return Some(at);
        }
        if let Some(found) = path_to(child, target, at) {
            return Some(found);
        }
    }
    None
}

/// Whether `a` and `b` hold Ident types of two different sources at one
/// place: two such types, or two records that have such types in fields of
/// one name.
fn ident_sources_clash(a: &ValueType, b: &ValueType) -> bool {
    match (a, b) {
        (ValueType::Ident(IdentSource::Form(x)), ValueType::Ident(IdentSource::Form(y))) => x != y,
        (ValueType::Record(a), ValueType::Record(b)) => a.iter().any(|(name, a)| b.iter().any(|(other, b)| name == other && ident_sources_clash(a, b))),
        _ => false,
    }
}

/// The type each parameter of `component` takes by `instance`'s binding
/// (`docs/arclog/arclog.md#instance`), at the places that [`binding_sites`]
/// gives, with `label` giving the type of each label of the instance, and
/// its bound, or an empty record where it has none, for each parameter onto which no
/// place projects.
fn bind(instance: &Instance, component: &Component, label: &dyn Fn(LabelId) -> Option<ValueType>) -> StableHashMap<TypeParameter, ValueType> {
    let sites = binding_sites(instance, &component.inputs);
    let mut bindings = StableHashMap::default();
    for sites in &sites {
        let ty = match sites.binding {
            ParameterSite::Key(key) => {
                let field = |column: &RelationColumn| Some((column.name.clone(), label(column.label)?));
                key.key.columns.iter().map(field).collect::<Option<_>>().map(ValueType::Record)
            }
            ParameterSite::Head { site, .. } => {
                let later: Vec<&Site> = sites.later.iter().map(|(_, site)| *site).collect();
                match (&sites.parameter.bound, joined_projections(site, &later, label)) {
                    (Some(_), Ok(Some(joined))) => Some(joined),
                    _ => binding_type(site, &later, label),
                }
            }
        };
        if let Some(ty) = ty {
            bindings.insert(sites.parameter.clone(), ty);
        }
    }
    for parameter in unbound(&component.type_parameters, &sites) {
        bindings.insert(parameter.clone(), parameter.bound.clone().unwrap_or_else(|| ValueType::Record(Box::new([]))));
    }
    bindings
}

/// The join of the types that `first` and `later`, the head sites that
/// project onto a type parameter in the order of the form, give their values
/// as [`site_value_type`] gives them, none for a site whose label has no
/// type; or the first of the sites whose type has no join with the types of
/// the sites before it.
fn joined_projections<'s>(first: &'s Site, later: &[&'s Site], label: &dyn Fn(LabelId) -> Option<ValueType>) -> Result<Option<ValueType>, &'s Site> {
    let mut joined: Option<ValueType> = None;
    for site in std::iter::once(first).chain(later.iter().copied()) {
        let Some(ty) = site_value_type(site, label) else { continue };
        joined = Some(match joined {
            None => ty,
            Some(prev) => prev.join(&ty).ok_or(site)?,
        });
    }
    Ok(joined)
}

/// The type of the value at `site`, the first projection onto a type
/// parameter, as [`site_value_type`] gives it, except that a field, or the
/// single label, whose label has no type takes the join of the types that
/// `later`, the later sites onto the parameter, give the field at the same
/// path (`docs/arclog/arclog.md#instance`).
fn binding_type(site: &Site, later: &[&Site], label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
    let from_later = |at: &[ColumnName]| join_types(later.iter().filter_map(|site| field_type(site, at, label))).ok().flatten();
    site_value_type_or(site, &[], label, &from_later)
}

/// The type that `site` gives its field at `path`, `site` itself at an
/// empty `path`.
fn field_type(site: &Site, path: &[ColumnName], label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
    let Some((first, rest)) = path.split_first() else { return site_value_type(site, label) };
    site.value.args.iter().find_map(|arg| match arg {
        SiteArg::NamedLabel { name, label: use_ } if name == first && rest.is_empty() => label(use_label(*use_)?),
        SiteArg::Field(inner) if inner.column == *first => field_type(inner, rest, label),
        _ => None,
    })
}

/// The label that `atom` gives the field `field` of its site on the column
/// `column`, a record.
pub(super) fn field_label(atom: &Atom, column: &ColumnName, field: &ColumnName) -> Option<LabelId> {
    let site = atom.sites.iter().find(|site| site.column == *column)?;
    site.value.args.iter().find_map(|arg| match arg {
        SiteArg::NamedLabel { name, label } if name == field => use_label(*label),
        SiteArg::Field(inner) if inner.column == *field => inner.value.args.iter().find_map(|arg| arg.label().and_then(use_label)),
        _ => None,
    })
}
