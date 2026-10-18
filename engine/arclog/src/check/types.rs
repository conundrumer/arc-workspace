//! The type check, the inference of the types of a case program's labels
//! that it and the pose rule's check read, and the two functions through
//! which the type check hands its types to [`super::check_program`].

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;

use super::{Check, CheckId, CheckInput, CheckResult, ClauseEntry, FileScope, Prefix, PrefixResult, Refusal, SolverClauses};
use crate::hash::StableHashMap;
use crate::program::canonical::{canonical_labeling, form_scope, AsWritten, CanonicalOrder, LabelScope, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    Atom, Body, ColumnName, Conjunct, DemoRule, Constraint, ConstraintOp, DeclaredName, Form, Instance, InstanceInput, InstanceName,
    LabelId, NameScope, Negated, Node, Operand, OutputOwner, OutputStep, PortName, ProgramRelation, RelationColumn,
    RelationName, RelationRef, RigidDetName, Site, SiteArg,
};
use crate::registry::{Column, ColumnType, Component, LibEntry, Macro, Proposer, Registry, TypeParameter};
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram, Side, Signature};
use crate::types::{
    each_conjunct, each_site_label, label_fault_message, label_type, scope_list, use_label, AssemblyId, FieldName, FormTypes,
    KeyRow, LabelFault, ProgramTypes, ValueType,
};

/// [`CheckId::Types`].
pub struct TypesCheck;

impl Check for TypesCheck {
    fn id(&self) -> CheckId {
        CheckId::Types
    }

    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        infer_form(input, &CanonicalOrder::of(input.form, &mut SearchBudget::new())).0
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

/// The [`FormTypes`] of each label scope of a form, by the scope's
/// canonical path relative to the form, in the order of those paths, as
/// [`super::CheckCache`] keeps them.
pub type ScopeTypes = Box<[(NodePath, FormTypes)]>;

/// The type check's result on the form of `input`, and the [`FormTypes`] of
/// each label scope of the form that `order` gives, each by the scope's
/// canonical path, with each label at its canonical position in its scope.
///
/// A fault of a label whose sites give it a Pose type and another type is
/// the pose rule's, which [`super::pose`] refuses.
pub fn infer_form(input: &CheckInput<'_>, order: &CanonicalOrder) -> (CheckResult, ScopeTypes) {
    let cases = CaseInferences::new(input.scope.clauses, input.scope.registry);
    let inference = Inference::new(input.scope.program, &cases);
    let result = match inference.infer(input.path) {
        Some(form) => result(refusals(&form, order)),
        None => CheckResult::Pass,
    };
    let scopes = order.label_scopes().into_iter().map(|(source, _)| {
        let form = inference.infer(&input.path.join(&source)).expect("a form or a `DEMO_RULE` stands at the path of each label scope of the form");
        (order.canonical_path(&source), scope_types(&form, order, &source))
    });
    (result, scopes.collect())
}

/// The refusals of the type check on `form`, the own scope of a form whose
/// canonical order is `order`.
fn refusals(form: &FormInference<'_>, order: &CanonicalOrder) -> Vec<Refusal> {
    let mut refusals = Vec::new();
    for (label, ty) in &form.labels {
        let Err(fault) = ty else { continue };
        if pose_of_fault(fault).is_some() {
            continue;
        }
        let message = match fault {
            LabelFault::NoJoin(a, b) if form.zero_typed.contains(label) => {
                format!("the label here takes the types {a:?} and {b:?} from the other clauses of its relation, which have no join")
            }
            fault => format!("the label here {}", label_fault_message(fault.clone())),
        };
        refusals.push(Refusal { message: message.into(), at: order.canonical_path(form.walk.first_use(*label)) });
    }
    for (at, constraint) in &form.walk.constraints {
        if !matches!(constraint.op, ConstraintOp::Lt | ConstraintOp::Le | ConstraintOp::Gt | ConstraintOp::Ge) {
            continue;
        }
        let second = match constraint.second {
            Operand::Label(label) => Some(label.label),
            Operand::Zero => None,
        };
        for label in std::iter::once(constraint.first.label).chain(second) {
            if let Some(ty) = form.label(label).filter(|ty| !ty.admits_order()) {
                let message = format!("the constraint orders a label of the type {ty:?}, and only `Number` has an order");
                refusals.push(Refusal { message: message.into(), at: order.canonical_path(at) });
            }
        }
    }
    refusals
}

/// The types of the labels of `form`, the scope whose form stands at
/// `scope`, a source path relative to the form whose canonical order is
/// `order`, each label at its canonical position in that scope.
fn scope_types(form: &FormInference<'_>, order: &CanonicalOrder, scope: &NodePath) -> FormTypes {
    let position = |label: LabelId| LabelId(order.canonical_label(scope, label));
    let types = form.labels.iter().filter_map(|(label, ty)| match ty {
        Ok(Some(ty)) => Some((position(*label), map_labels(ty, &position))),
        Ok(None) | Err(_) => None,
    });
    types.collect()
}

/// The [`ProgramTypes`] of `program`: for each form of `forms`, at its path,
/// the types of each label scope of the form, at the scope's source path
/// joined to the form's path, each label mapped from its canonical position
/// to its own label through the form's order, and the type of each column
/// of each relation.
pub fn program_types(
    _program: &ResolvedProgram,
    _clauses: &SolverClauses,
    forms: &[(NodePath, Arc<ScopeTypes>, CanonicalOrder)],
) -> ProgramTypes {
    let mut types = ProgramTypes::default();
    for (path, scopes, order) in forms {
        for (canonical, form_types) in scopes.iter() {
            let source = order.source_path(canonical);
            let own = |position: LabelId| order.source_label(&source, position.0);
            let labels = form_types.labels().map(|(label, ty)| (own(label), map_labels(ty, &own)));
            types.insert_form(path.join(&source), Arc::new(labels.collect()));
        }
    }
    types
}

/// The signatures of the clauses that a label's type of `form` comes from,
/// as [`CheckId::Types`] gives, in the order [`SolverClauses`] gives.
pub fn type_clause_signatures<'a>(form: &Form, clauses: &'a SolverClauses) -> impl Iterator<Item = &'a Signature> {
    let entries = match form {
        Form::Clause(clause) if !zero_typed_heads(clause.value()).is_empty() => {
            clauses.of_relation(&FileScope::Program, &clause.value().derives)
        }
        _ => &[],
    };
    entries.iter().map(|entry| &entry.signature)
}

/// The head labels of `clause` that only `(= *X 0)` gives a type: each
/// stands at no site of an atom and is made by such a constraint.
fn zero_typed_heads(clause: &crate::program::Clause) -> Vec<LabelId> {
    let mut at_sites = Vec::new();
    let mut zeroed = Vec::new();
    each_conjunct(clause.body.value(), &mut |conjunct| match conjunct {
        Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
            for site in atom.value().sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, _| at_sites.extend(use_label(use_)));
            }
        }
        Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) if first.fresh => zeroed.push(first.label),
        _ => {}
    });
    let heads = clause.columns.iter().map(|column| column.label);
    heads.filter(|label| zeroed.contains(label) && !at_sites.contains(label)).collect()
}

/// A pass, or a refusal of each of `refusals`.
pub(super) fn result(refusals: Vec<Refusal>) -> CheckResult {
    if refusals.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Refuse(refusals.into())
    }
}

/// The Pose type of the label that `fault` is of, where one of its sites
/// gives it one.
pub(super) fn pose_of_fault(fault: &LabelFault) -> Option<&ValueType> {
    match fault {
        LabelFault::EmptyMeet(a, b) => [a, b].into_iter().find(|ty| matches!(ty, ValueType::Pose(_))),
        LabelFault::NoJoin(..) => None,
    }
}

/// `ty` with each label of a key row mapped by `map`.
fn map_labels(ty: &ValueType, map: &dyn Fn(LabelId) -> LabelId) -> ValueType {
    try_map_labels(ty, &|label| Some(map(label))).expect("a map of every label maps each label of a type")
}

/// `ty` with each label of a key row mapped by `map`, or `None` where
/// `map` gives no label for one.
fn try_map_labels(ty: &ValueType, map: &dyn Fn(LabelId) -> Option<LabelId>) -> Option<ValueType> {
    Some(match ty {
        ValueType::Pose(AssemblyId { name, canonical_form, key: KeyRow::Labels(labels) }) => ValueType::Pose(AssemblyId {
            name: name.clone(),
            canonical_form: canonical_form.clone(),
            key: KeyRow::Labels(labels.iter().map(|label| map(*label)).collect::<Option<_>>()?),
        }),
        ValueType::Record(fields) => {
            ValueType::Record(fields.iter().map(|(name, ty)| Some((name.clone(), try_map_labels(ty, map)?))).collect::<Option<_>>()?)
        }
        ty => ty.clone(),
    })
}

/// The column of a lifted read that holds the example,
/// `docs/arclog/arclog.md#program`.
const EXAMPLE: &str = "E";
/// The column of a `RIGID_DET` output that holds the pose,
/// `docs/arclog/rigid.md#semantics`.
const POSE: &str = "Pose";

fn written(name: &str) -> ColumnName {
    ColumnName::Written(name.into())
}

/// The type at `rest` of a value of type `ty`: a record's field for each
/// step, and `ty` itself past a type that is no record, as a bare label's
/// name after a column of a type parameter bound to one label's type.
fn project(ty: &ValueType, rest: &[ColumnName]) -> Option<ValueType> {
    match (ty, rest) {
        (ValueType::Record(fields), [field, rest @ ..]) => {
            let name = FieldName::of(field)?;
            project(&fields.iter().find(|(found, _)| *found == name)?.1, rest)
        }
        (ty, _) => Some(ty.clone()),
    }
}

/// How a site's column type reads the Pose type a lib column may take.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum PoseOr {
    /// A column of `(pose-or <type>)` gives no type, so its label takes its
    /// Pose type from its other sites.
    Open,
    /// Such a column gives its type, for a label that no other site gives
    /// one.
    Given,
}

/// The type a declared column of the type `ty` gives a site at `rest`
/// below the column, with `bindings` binding the type parameters.
fn column_type(ty: &ColumnType, rest: &[ColumnName], bindings: &StableHashMap<TypeParameter, ValueType>, pose_or: PoseOr) -> Option<ValueType> {
    match ty {
        ColumnType::Fixed(ty) => Some(ty.clone()),
        ColumnType::PoseOr(ty) => (pose_or == PoseOr::Given).then(|| ty.clone()),
        ColumnType::Pose | ColumnType::SharedPose => None,
        ColumnType::Parameter(parameter) => project(bindings.get(parameter)?, rest),
    }
}

/// The type the column at `path` of `columns` gives a site.
fn declared_type(columns: &[Column], path: &[ColumnName], pose_or: PoseOr) -> Option<ValueType> {
    let (first, rest) = path.split_first()?;
    column_type(&columns.iter().find(|column| column.name == *first)?.ty, rest, &StableHashMap::default(), pose_or)
}

/// The declared columns of the lib relation or the native proposer `name`.
fn lib_columns<'r>(registry: &'r Registry, name: &crate::registry::LibName) -> Option<&'r [Column]> {
    match registry.entry(name)? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
        LibEntry::Proposer(Proposer::Native { columns }) => Some(columns),
        LibEntry::Proposer(Proposer::Arclog { .. }) | LibEntry::Component(_) | LibEntry::Macro(Macro::CellInstance { .. }) => None,
    }
}

/// The component an `INIT` form names.
pub(super) fn component<'r>(registry: &'r Registry, name: &crate::registry::LibName) -> Option<&'r Component> {
    match registry.entry(name)? {
        LibEntry::Component(component) | LibEntry::Macro(Macro::CellInstance { component, .. }) => Some(component),
        LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(Macro::Relation { .. }) => None,
    }
}

/// The side of the form at `form` of `program`, the side of the first node
/// of the dependency graph that the form gives, or `None` where it gives
/// none.
pub(super) fn form_side(program: &ResolvedProgram, form: &NodePath) -> Option<Side> {
    let mut nodes = (0..program.graph.nodes.len() as u32).map(GraphNodeIndex);
    nodes.find(|found| program.form_of(*found) == form).map(|found| program.side(found))
}

/// The form at `path` of `program`: a top-level form, a form of a claim,
/// a form of an `ALT`, or a form of a `DEMO_RULE`.
fn form_at<'p>(program: &'p crate::program::Program, path: &NodePath) -> Option<&'p Form> {
    let (first, rest) = path.0.split_first()?;
    let mut form = program.forms.get(first.0 as usize)?;
    let mut steps = rest.iter();
    while let Some(step) = steps.next() {
        form = match form {
            Form::Claim(claim) => claim.value().forms.get(step.0 as usize)?,
            Form::Alts(alts) => {
                let mut alt = alts.value().alts.get(step.0 as usize)?.value();
                loop {
                    match alt.items.get(steps.next()?.0 as usize)? {
                        crate::program::AltItem::Form(form) => break form,
                        crate::program::AltItem::Alt(nested) => alt = nested.value(),
                    }
                }
            }
            Form::Demonstrated(demonstrated) => {
                let demonstrated = demonstrated.value();
                let before = demonstrated.key.iter().count() + demonstrated.inputs.len();
                let rule = demonstrated.rules.get((step.0 as usize).checked_sub(before)?)?;
                rule.value().forms.get(steps.next()?.0 as usize)?
            }
            _ => return None,
        };
    }
    Some(form)
}

/// The labels of `scope`, in the order of its canonical labeling.
fn scope_labels(scope: LabelScope<'_>) -> Vec<LabelId> {
    canonical_labeling(scope, &AsWritten, &mut SearchBudget::new()).positions.iter().map(|(label, _)| *label).collect()
}

/// Whether `form`, a form of a `DEMO_RULE`, stands in the rule's label
/// scope, as the form writer writes it: a claim, a `DEMONSTRATED` form and
/// an `ALTS` form are each a scope of their own.
fn shares_rule_scope(form: &Form) -> bool {
    match form {
        Form::Clause(_) | Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) => true,
        Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) => false,
    }
}

/// The `DEMO_RULE` form at `path` of `program`.
fn demo_rule<'p>(program: &'p crate::program::Program, path: &NodePath) -> Option<&'p crate::program::DemoRule> {
    let (rule, form) = path.0.split_last()?;
    let Form::Demonstrated(demonstrated) = form_at(program, &NodePath(form.into()))? else { return None };
    let demonstrated = demonstrated.value();
    let before = demonstrated.key.iter().count() + demonstrated.inputs.len();
    Some(demonstrated.rules.get((rule.0 as usize).checked_sub(before)?)?.value())
}

/// Each form that declares names in `scope`, with its path: the top-level
/// forms and the forms of claims for the program, and a `DEMO_RULE`'s forms
/// for its scope.
fn scope_forms<'p>(program: &'p crate::program::Program, scope: &NameScope) -> Vec<(NodePath, &'p Form)> {
    fn add<'p>(forms: &'p [Form], at: &NodePath, out: &mut Vec<(NodePath, &'p Form)>) {
        for (form, index) in forms.iter().zip(0u32..) {
            let path = at.child(index);
            if let Form::Claim(claim) = form {
                add(&claim.value().forms, &path, out);
            }
            out.push((path, form));
        }
    }
    let mut out = Vec::new();
    match scope {
        NameScope::Program => add(&program.forms, &NodePath::default(), &mut out),
        NameScope::DemoRule(rule) => {
            if let Some(found) = demo_rule(program, rule) {
                add(&found.forms, rule, &mut out);
            }
        }
    }
    out
}

/// The type of the value at `site` of a head or of a read: its one bare
/// label's type, or a record with a field per argument.
fn site_value_type(site: &Site, label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
    match &site.value.args[..] {
        [SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. }] => label(use_label(*use_)?),
        args => {
            let field = |arg: &SiteArg| match arg {
                SiteArg::NamedLabel { name, label: use_ } => Some((FieldName::of(name)?, label(use_label(*use_)?)?)),
                SiteArg::Field(field) => Some((FieldName::of(&field.column)?, site_value_type(field, label)?)),
                SiteArg::Label(_) => None,
            };
            Some(ValueType::Record(args.iter().map(field).collect::<Option<_>>()?))
        }
    }
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

/// The inputs an `INIT` or a `DEMONSTRATED` form writes: the keyed inputs,
/// then the others.
fn written_inputs<'f>(
    key: Option<&'f Node<crate::program::KeyClause>>,
    inputs: &'f [Node<InstanceInput>],
) -> impl Iterator<Item = &'f InstanceInput> {
    key.into_iter().flat_map(|key| key.value().inputs.iter()).chain(inputs.iter()).map(|input| input.value())
}

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
        let list = |body: &Node<Body>, conjuncts: &mut Vec<Conjunct>| conjuncts.extend(body.value().conjuncts.iter().cloned());
        let columns = |columns: &[RelationColumn], heads: &mut Vec<LabelId>| heads.extend(columns.iter().map(|column| column.label));
        let inputs = |inputs: &mut dyn Iterator<Item = &InstanceInput>, conjuncts: &mut Vec<Conjunct>| {
            for input in inputs {
                let head = Atom { relation: RelationRef::DefinedPort(input.name.clone()), sites: input.head.clone() };
                let branch = std::iter::once(Conjunct::Atom(Node::new(head))).chain(input.body.value().conjuncts.iter().cloned());
                conjuncts.push(Conjunct::Or(Arc::from([Node::new(Body { conjuncts: branch.collect() })])));
            }
        };
        let (mut found_component, mut found_instance) = (None, None);
        match form {
            Form::Clause(clause) => {
                let clause = clause.value();
                list(&clause.body, &mut conjuncts);
                columns(&clause.columns, &mut heads);
            }
            Form::Instance(instance) => {
                let instance = instance.value();
                if let Some(key) = &instance.key {
                    list(&key.value().key.body, &mut conjuncts);
                    columns(&key.value().key.columns, &mut heads);
                }
                inputs(&mut written_inputs(instance.key.as_ref(), &instance.inputs), &mut conjuncts);
                found_component = component(registry, &instance.component);
                found_instance = Some(instance);
            }
            Form::Choose(choose) => {
                let choose = choose.value();
                if let Some(rows) = &choose.rows {
                    list(&rows.body, &mut conjuncts);
                    columns(&rows.columns, &mut heads);
                }
                list(&choose.from, &mut conjuncts);
                columns(&choose.candidate_columns, &mut heads);
                conjuncts.extend(choose.never.iter().map(|never| Conjunct::Or(Arc::from([never.clone()]))));
            }
            Form::RigidDet(rigid) => {
                let rigid = rigid.value();
                for clause in rigid.key.iter().chain(rigid.instance.iter()) {
                    list(&clause.body, &mut conjuncts);
                    columns(&clause.columns, &mut heads);
                }
                conjuncts.extend(rigid.parts.iter().map(|part| Conjunct::Atom(part.clone())));
            }
            Form::Demonstrated(demonstrated) => {
                let demonstrated = demonstrated.value();
                if let Some(key) = &demonstrated.key {
                    list(&key.value().key.body, &mut conjuncts);
                    columns(&key.value().key.columns, &mut heads);
                }
                inputs(&mut written_inputs(demonstrated.key.as_ref(), &demonstrated.inputs), &mut conjuncts);
            }
            Form::Claim(_) | Form::Alts(_) => {}
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
/// claim and of a `DEMO_RULE` stand in scopes of their own.
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
        for (form, index) in rule.forms.iter().zip(0u32..) {
            if shares_rule_scope(form) {
                walk.node(NodeRef::from(form), NodePath::default().child(index));
            }
        }
        walk
    }

    fn node(&mut self, node: NodeRef<'a>, at: NodePath) {
        match node {
            NodeRef::Conjunct(Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) => return self.atom(atom.value(), at),
            NodeRef::Atom(atom) => return self.atom(atom, at),
            NodeRef::Claim(_) | NodeRef::DemoRule(_) => return,
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

/// The types of one label scope: a form's own scope, or a `DEMO_RULE`'s.
pub(super) struct FormInference<'a> {
    /// The form whose own scope this is, or `None` for a `DEMO_RULE`'s.
    pub form: Option<&'a Form>,
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
    zero_typed: Vec<LabelId>,
    /// The labels that take their type from a column of `(pose-or <type>)`
    /// alone, so that a column of a relation that such a label gives takes
    /// a Pose type as that column does.
    given: Vec<LabelId>,
}

impl FormInference<'_> {
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

/// The inferences of the case programs of a [`SolverClauses`] that the
/// check of one form reads, each program's once, so that a read through a
/// cycle of forms across those programs meets the guard of
/// [`Inference::infer`].
pub(super) struct CaseInferences<'a> {
    clauses: &'a SolverClauses,
    registry: &'a Registry,
    inferences: RefCell<StableHashMap<usize, Rc<Inference<'a>>>>,
}

impl<'a> CaseInferences<'a> {
    pub fn new(clauses: &'a SolverClauses, registry: &'a Registry) -> Self {
        CaseInferences { clauses, registry, inferences: RefCell::default() }
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
/// each form once, on its first read.
pub(super) struct Inference<'a> {
    program: &'a ResolvedProgram,
    registry: &'a Registry,
    cases: &'a CaseInferences<'a>,
    /// Each form inferred, or `None` while its inference runs, so that a
    /// read through a cycle of forms gives no type.
    forms: RefCell<StableHashMap<NodePath, Option<Rc<FormInference<'a>>>>>,
}

impl<'a> Inference<'a> {
    pub fn new(program: &'a ResolvedProgram, cases: &'a CaseInferences<'a>) -> Self {
        Inference { program, registry: cases.registry, cases, forms: RefCell::default() }
    }

    /// The types of the label scope whose form stands at `path`, a form or
    /// a `DEMO_RULE`, or `None` where no such form stands there or its
    /// inference runs.
    pub fn infer(&self, path: &NodePath) -> Option<Rc<FormInference<'a>>> {
        if let Some(found) = self.forms.borrow().get(path) {
            return found.clone();
        }
        let program = self.program.program.value();
        enum ScopeForm<'p> {
            Form(&'p Form),
            DemoRule(&'p DemoRule),
        }
        let scope = match form_at(program, path) {
            Some(form) => ScopeForm::Form(form),
            None => ScopeForm::DemoRule(demo_rule(program, path)?),
        };
        self.forms.borrow_mut().insert(path.clone(), None);
        let inferred = Rc::new(match scope {
            ScopeForm::Form(form) => self.infer_new(form, path),
            ScopeForm::DemoRule(rule) => self.infer_rule(rule, path),
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
        FormInference { form: Some(form), path: path.clone(), labels: types, bindings, walk, component: scope.component, zero_typed, given: given_labels }
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
        for (form, index) in rule.forms.iter().zip(0u32..) {
            if !shares_rule_scope(form) {
                continue;
            }
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
        FormInference { form: None, path: path.clone(), labels, bindings: no_bindings, walk: FormWalk::of_rule(rule), component: None, zero_typed: Vec::new(), given }
    }

    /// The type that the column at `path` of the relation `atom` reads gives
    /// a site of `atom`, a site of a form read under `reading`.
    pub fn site_type(&self, reading: SiteReading<'_, 'a>, atom: &Atom, path: &[ColumnName]) -> Option<ValueType> {
        if let RelationRef::DefinedPort(port) = &atom.relation {
            let (first, rest) = path.split_first()?;
            let input = reading.component?.inputs.iter().find(|input| input.port.name == *port)?;
            let column = input.port.columns.iter().find(|column| column.name == *first)?;
            return column_type(&column.ty, rest, reading.bindings, reading.pose_or);
        }
        let at = reading.path.join(reading.walk.atoms.get(&(atom as *const Atom))?);
        match self.program.resolution(&at)? {
            Resolution::Lib(name) => declared_type(lib_columns(self.registry, name)?, path, reading.pose_or),
            Resolution::Node(node) if path == [written(EXAMPLE)] && self.lifts(reading.path, *node) => Some(ValueType::Example),
            Resolution::Node(node) => self.node_type(*node, atom, path, reading.pose_or),
            Resolution::Undefined(_) | Resolution::Unresolved => None,
        }
    }

    /// Whether the form at `form` reads the relation of `node` in its lifted
    /// form, with the Example column first: where the form is task-wide and
    /// the relation is a per-input relation other than a fact relation
    /// (`docs/arclog/arclog.md#program`).
    fn lifts(&self, form: &NodePath, node: GraphNodeIndex) -> bool {
        let task_wide = form_side(self.program, form) == Some(Side::TaskWide);
        let fact = matches!(self.program.graph.nodes[node.0 as usize].kind, DependencyKind::Fact(_));
        task_wide && !fact && self.program.side(node) == Side::PerInput
    }

    /// Whether a site of `atom`, a site of a form read under `reading`, on
    /// the column at `path`, may hold a Pose label whatever its column's
    /// type: an instance input's head, a column of a relation the program
    /// derives or of an instance's input, or a lib column that takes a Pose
    /// type (`docs/arclog/rigid.md#the-pose`). A column of an instance's
    /// output or of a `RIGID_DET` form's output takes its type from such a
    /// column, so it holds a Pose label where the inference gives it no type.
    pub fn admits_pose(&self, reading: SiteReading<'_, 'a>, atom: &Atom, path: &[ColumnName]) -> bool {
        if let RelationRef::DefinedPort(_) = &atom.relation {
            return true;
        }
        let Some(at) = reading.walk.atoms.get(&(atom as *const Atom)) else { return false };
        match self.program.resolution(&reading.path.join(at)) {
            Some(Resolution::Lib(name)) => {
                let column = path.first().and_then(|first| lib_columns(self.registry, name)?.iter().find(|column| column.name == *first));
                column.is_some_and(|column| matches!(column.ty, ColumnType::Pose | ColumnType::SharedPose | ColumnType::PoseOr(_)))
            }
            Some(Resolution::Node(node)) => matches!(
                self.program.graph.nodes[node.0 as usize].kind,
                DependencyKind::Clause(_)
                    | DependencyKind::Parameter(_)
                    | DependencyKind::Chosen(_)
                    | DependencyKind::Demonstrated(_)
                    | DependencyKind::InstanceInput { .. }
                    | DependencyKind::InstanceOutput { .. }
                    | DependencyKind::RecursiveInstance(_)
                    | DependencyKind::RigidAssembly(_)
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
        let column = path.first().and_then(|first| lib_columns(self.registry, name)?.iter().find(|column| column.name == *first));
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
                    let choose = choose.value();
                    let columns = choose.rows.iter().flat_map(|rows| rows.columns.iter()).chain(choose.candidate_columns.iter());
                    let (first, rest) = path.split_first()?;
                    let column = columns.clone().find(|column| column.name == *first)?;
                    let ty = project(&self.infer(form_path)?.label_under(column.label, pose_or)?, rest)?;
                    try_map_labels(&ty, &|label| reader(&columns.clone().find(|column| column.label == label)?.name))
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
            DependencyKind::RigidAssembly(_) => self.rigid_output(form_path, atom, path),
            DependencyKind::Demonstrated(_) => self.demonstrated_column(form_path, path),
            DependencyKind::InstanceInput { .. } => None,
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

    /// The type of the label at `column` of `clause`, the clause at `path`,
    /// that only `(= *X 0)` gives a type: the join of the types that the
    /// other clauses of its relation in [`SolverClauses`] give that column,
    /// each in the case program it was found in, or the fault of two types
    /// with no join. A Pose type's key row names the labels of `clause`.
    fn other_clauses_type(&self, clause: &crate::program::Clause, path: &NodePath, column: &ColumnName) -> Result<Option<ValueType>, LabelFault> {
        let own = super::clause_signature(self.program, path);
        let target = |column: &ColumnName| clause.columns.iter().find(|found| found.name == *column).map(|found| found.label);
        let entries = self.cases.clauses.of_relation(&FileScope::Program, &clause.derives).iter();
        let types = entries.filter(|entry| entry.signature != own).filter_map(|entry| {
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
        });
        join_types(types)
    }

    /// The type that the clause at `at` gives the column at `path` of its
    /// relation under `pose_or`: its column's label's, its first proposer's
    /// column's, or the column's of the instance output it stands for.
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
        if !clause.columns.is_empty() {
            let column = clause.columns.iter().find(|column| column.name == *first)?;
            let ty = project(&self.infer(at)?.label_under(column.label, pose_or)?, rest)?;
            return try_map_labels(&ty, &|label| target(&clause.columns.iter().find(|column| column.label == label)?.name));
        }
        if let Some(proposer) = clause.proposers.first() {
            let columns = match lib_columns(self.registry, proposer) {
                Some(columns) => columns,
                None => &self.registry.derivation(proposer)?.columns,
            };
            return declared_type(columns, path, pose_or);
        }
        let ProgramRelation::Output(output) = &clause.derives else { return None };
        let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return None };
        let forms = scope_forms(self.program.program.value(), scope);
        let instance = forms.iter().find(|(_, form)| matches!(form, Form::Instance(instance) if instance.value().name == *name))?;
        self.instance_output(&instance.0, port, path)
    }

    /// The type of the column at `path` of the output `port` of the `INIT`
    /// form at `at`, its parameters bound as the form binds them. A type
    /// that names labels of the form's scope gives none.
    fn instance_output(&self, at: &NodePath, port: &PortName, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let (first, rest) = path.split_first()?;
        let output = inference.component?.outputs.iter().find(|output| output.name == *port)?;
        let column = output.columns.iter().find(|column| column.name == *first)?;
        let ty = column_type(&column.ty, rest, &inference.bindings, PoseOr::Open)?;
        try_map_labels(&ty, &|_| None)
    }

    /// The type of the column at `path` of the output of the `RIGID_DET`
    /// form at `at` that `atom` reads: the key's, `:Pose`, and a part's or
    /// the instance's (`docs/arclog/rigid.md#semantics`). The Pose type names
    /// the labels `atom` gives at the key's columns.
    fn rigid_output(&self, at: &NodePath, atom: &Atom, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let Some(form @ Form::RigidDet(rigid)) = inference.form else { return None };
        let rigid_value = rigid.value();
        let RelationRef::Output(output) = &atom.relation else { return None };
        let (first, rest) = path.split_first()?;
        let local = |ty: ValueType| try_map_labels(&ty, &|_| None);
        let key = written(crate::read::spelling::KEY);
        if *first == key {
            let Some(key_body) = &rigid_value.key else { return project(&ValueType::Unit, rest) };
            let field = |column: &RelationColumn| Some((FieldName::of(&column.name)?, inference.label(column.label)?));
            let record = ValueType::Record(key_body.columns.iter().map(field).collect::<Option<_>>()?);
            return local(project(&record, rest)?);
        }
        if *first == written(POSE) {
            let key_row = match &rigid_value.key {
                None => KeyRow::Unkeyed,
                Some(key_body) => KeyRow::Labels(key_body.columns.iter().map(|column| field_label(atom, &key, &column.name)).collect::<Option<_>>()?),
            };
            let canonical_form = super::canonical_form(form);
            return Some(ValueType::Pose(AssemblyId { name: rigid_value.name.clone(), canonical_form, key: key_row }));
        }
        if let [OutputStep::Pose] = &output.path[..] {
            let column = rigid_value.instance.iter().flat_map(|instance| instance.columns.iter()).find(|column| column.name == *first)?;
            return local(project(&inference.label(column.label)?, rest)?);
        }
        let part = rigid_value.parts.iter().find(|part| part_steps(&part.value().relation).as_deref() == Some(&output.path[..]))?;
        local(self.site_type(inference.reading(PoseOr::Given), part.value(), path)?)
    }

    /// The type of the column at `path` of the relation of the
    /// `DEMONSTRATED` form at `at`: the key's, then those the `value` input's
    /// head names (`docs/arclog/arclog.md#demonstrated`).
    fn demonstrated_column(&self, at: &NodePath, path: &[ColumnName]) -> Option<ValueType> {
        let inference = self.infer(at)?;
        let Some(Form::Demonstrated(demonstrated)) = inference.form else { return None };
        let demonstrated = demonstrated.value();
        let (first, rest) = path.split_first()?;
        let label = |label: LabelId| inference.label(label);
        let ty = if *first == written(crate::read::spelling::KEY) {
            match &demonstrated.key {
                None => ValueType::Unit,
                Some(key) => {
                    let field = |column: &RelationColumn| Some((FieldName::of(&column.name)?, label(column.label)?));
                    ValueType::Record(key.value().key.columns.iter().map(field).collect::<Option<_>>()?)
                }
            }
        } else {
            let value = written_inputs(demonstrated.key.as_ref(), &demonstrated.inputs).find(|input| &*input.name.0 == "value")?;
            site_value_type(value.head.iter().find(|site| site.column == *first)?, &label)?
        };
        try_map_labels(&project(&ty, rest)?, &|_| None)
    }
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

/// The path after a `RIGID_DET` form's name of the output for the part
/// that reads `relation`: `&marker.glyph` for a part that reads `&glyph`,
/// `&marker.bbox.box` for one that reads `&bbox.box`.
fn part_steps(relation: &RelationRef) -> Option<Vec<OutputStep>> {
    let (owner, rest): (&DeclaredName, &[OutputStep]) = match relation {
        RelationRef::Declared(RelationName(name)) => (name, &[]),
        RelationRef::Output(output) => match &output.of {
            OutputOwner::Instance(InstanceName(name)) | OutputOwner::RigidDet(RigidDetName(name)) => (name, &output.path[..]),
        },
        RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) | RelationRef::DefaultRows { .. } => return None,
    };
    Some(std::iter::once(OutputStep::Part(owner.clone())).chain(rest.iter().cloned()).collect())
}

/// The type each parameter of `component` takes by `instance`'s binding,
/// with `label` giving the type of each label of the instance: the key
/// clause binds the parameter of the `key` column to a record of its `^`
/// labels, and the first projection onto each other parameter binds it,
/// to its one label's type or to a record with a field per site, as
/// `docs/arclog/arclog.md#instance` gives. An instance with no key clause
/// binds the parameter of the `key` column, where no projection does, to
/// `Unit`.
fn bind(instance: &Instance, component: &Component, label: &dyn Fn(LabelId) -> Option<ValueType>) -> StableHashMap<TypeParameter, ValueType> {
    let key = written(crate::read::spelling::KEY);
    let key_parameter = component.inputs.iter().flat_map(|input| input.port.columns.iter()).find_map(|column| match &column.ty {
        ColumnType::Parameter(parameter) if column.name == key => Some(parameter.clone()),
        _ => None,
    });
    let mut bound: Vec<TypeParameter> = Vec::new();
    let mut bindings = StableHashMap::default();
    if let (Some(parameter), Some(key_clause)) = (&key_parameter, &instance.key) {
        let field = |column: &RelationColumn| Some((FieldName::of(&column.name)?, label(column.label)?));
        if let Some(fields) = key_clause.value().key.columns.iter().map(field).collect::<Option<_>>() {
            bindings.insert(parameter.clone(), ValueType::Record(fields));
        }
        bound.push(parameter.clone());
    }
    for input in written_inputs(instance.key.as_ref(), &instance.inputs) {
        let Some(port) = component.inputs.iter().find(|port| port.port.name == input.name) else { continue };
        for site in input.head.iter() {
            let Some(column) = port.port.columns.iter().find(|column| column.name == site.column) else { continue };
            let ColumnType::Parameter(parameter) = &column.ty else { continue };
            if bound.contains(parameter) {
                continue;
            }
            bound.push(parameter.clone());
            if let Some(ty) = site_value_type(site, label) {
                bindings.insert(parameter.clone(), ty);
            }
        }
    }
    if let (Some(parameter), None) = (key_parameter, &instance.key) {
        if !bound.contains(&parameter) {
            bindings.insert(parameter, ValueType::Unit);
        }
    }
    bindings
}
