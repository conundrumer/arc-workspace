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
    Atom, Body, ColumnName, Conjunct, DemoRule, Constraint, ConstraintOp, Form, Instance, InstanceInput, LabelId, NameScope,
    Negated, Node, Operand, OutputOwner, OutputStep, PortName, ProgramRelation, RelationColumn, RelationRef, Site, SiteArg,
};
use crate::program::written_inputs;
use crate::registry::{binding_sites, key_parameter, Column, ColumnType, Component, ParameterSite, Registry, TypeParameter};
use crate::resolver::columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram, Side, Signature};
use crate::types::{
    each_conjunct, each_site_label, label_fault_message, label_type, scope_list, use_label, AssemblyId, FormRelation, FormTypes,
    GraphRelation, KeyRow, LabelFault, ProgramTypes, ValueType,
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
/// The result is the union of the refusals of the inference of each label
/// scope of the form, as [`CanonicalOrder::label_scopes`] gives them, each scope inferred
/// at its source path joined to the form's path, and, for a clause, of the
/// refusals at the columns of its relation. A fault of a label whose sites
/// give it a Pose type and another type is the pose rule's, which
/// [`super::pose`] refuses.
pub fn infer_form(input: &CheckInput<'_>, order: &CanonicalOrder) -> (CheckResult, ScopeTypes) {
    let cases = CaseInferences::new(input.scope.clauses, input.scope.registry);
    let inference = Inference::new(input.scope.program, &cases);
    let mut found = Vec::new();
    let mut scopes = Vec::new();
    for source in inferred_scopes(order) {
        let form = inference.infer(&input.path.join(&source)).expect(SCOPE_FORM);
        found.extend(refusals(&form, order, &source));
        let relations = scope_forms_within(input.form, &source).into_iter().flat_map(|(at, form)| {
            let relations = inference.form_relations(&input.path.join(&at), form);
            let canonical = order.canonical_path(&at);
            relations.into_iter().map(move |(output, columns)| (FormRelation { form: canonical.clone(), output }, columns))
        });
        scopes.push((order.canonical_path(&source), scope_types(&form, order, &source, relations.collect::<Vec<_>>())));
    }
    if let (Form::Clause(clause), Some(form)) = (input.form, inference.infer(input.path)) {
        found.extend(inference.column_refusals(&form, clause.value(), input.path, order));
    }
    (result(found), scopes.into())
}

/// What stands at the source path of each label scope of a form.
const SCOPE_FORM: &str = "a form or a `DEMO_RULE` stands at the path of each label scope of the form";

/// The source path of each label scope of a form whose canonical order is
/// `order`, relative to the form, in the order of
/// [`CanonicalOrder::label_scopes`]: the scopes that [`infer_form`] infers
/// and whose clauses [`type_clause_signatures`] reads.
fn inferred_scopes(order: &CanonicalOrder) -> Vec<NodePath> {
    order.label_scopes().into_iter().map(|(source, _)| source).collect()
}

/// The refusals of the type check on `form`, the label scope whose form
/// stands at `scope`, a source path relative to a form whose canonical
/// order is `order`, each at the canonical path of `scope` joined to its
/// place in the scope's form.
fn refusals(form: &FormInference<'_>, order: &CanonicalOrder, scope: &NodePath) -> Vec<Refusal> {
    let place = |at: &NodePath| order.canonical_path(&scope.join(at));
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
        refusals.push(Refusal { message: message.into(), at: place(form.walk.first_use(*label)) });
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
                refusals.push(Refusal { message: message.into(), at: place(at) });
            }
        }
    }
    refusals
}

/// The types of the labels of `form`, the scope whose form stands at
/// `scope`, a source path relative to the form whose canonical order is
/// `order`, each label at its canonical position in that scope, with the
/// column types of `relations`.
fn scope_types(
    form: &FormInference<'_>,
    order: &CanonicalOrder,
    scope: &NodePath,
    relations: impl IntoIterator<Item = (FormRelation, Box<[ValueType]>)>,
) -> FormTypes {
    let position = |label: LabelId| LabelId(order.canonical_label(scope, label));
    let types = form.labels.iter().filter_map(|(label, ty)| match ty {
        Ok(Some(ty)) => Some((position(*label), map_labels(ty, &position))),
        Ok(None) | Err(_) => None,
    });
    FormTypes::new(types, relations)
}

/// Each form that stands in the label scope at `scope`, a source path
/// relative to `form`, with its path relative to `form`: the scope's own
/// form, or each form of a `DEMO_RULE` that stands in the rule's scope.
fn scope_forms_within<'f>(form: &'f Form, scope: &NodePath) -> Vec<(NodePath, &'f Form)> {
    if let Some(found) = form_within(form, scope) {
        return vec![(scope.clone(), found)];
    }
    let rule = rule_within(form, scope).expect(SCOPE_FORM);
    let shared = rule.forms.iter().zip(0u32..).filter(|(found, _)| shares_rule_scope(found));
    shared.map(|(found, index)| (scope.child(index), found)).collect()
}

/// The [`ProgramTypes`] of `program`: for each form of `forms`, at its path,
/// the types of each label scope of the form, at the scope's source path
/// joined to the form's path, each label mapped from its canonical position
/// to its own label through the form's order, and the type of each column
/// of each relation.
///
/// A relation that clauses or a `CHOOSE` form give takes at each column, at
/// the position in its node's rows that
/// [`ResolvedProgram::label_position`] gives, the join of the types its
/// forms give the labels at that column, each label typed in its form's
/// label scope or, where the form shares a `DEMO_RULE`'s, in the rule's,
/// and a Pose type names its key row by the positions of the key's
/// columns. A relation whose columns a form's
/// declaration fixes takes the types that [`FormTypes::relations`] gives
/// it, in the order of the resolver's columns of it. A fact relation takes
/// the types of the columns that [`Registry::fact_columns`] gives it. A
/// relation a column of which no form types gets no column types.
pub fn program_types(
    program: &ResolvedProgram,
    registry: &Registry,
    _clauses: &SolverClauses,
    forms: &[(NodePath, Arc<ScopeTypes>, CanonicalOrder)],
) -> ProgramTypes {
    let mut types = ProgramTypes::default();
    let mut fixed: StableHashMap<(NodePath, Arc<[OutputStep]>), &[ValueType]> = StableHashMap::default();
    for (path, scopes, order) in forms {
        for (canonical, form_types) in scopes.iter() {
            let source = order.source_path(canonical);
            let own = |position: LabelId| order.source_label(&source, position.0);
            let labels = form_types.labels().map(|(label, ty)| (own(label), map_labels(ty, &own)));
            types.insert_form(path.join(&source), Arc::new(FormTypes::new(labels, [])));
            for (relation, columns) in form_types.relations() {
                fixed.insert((path.join(&order.source_path(&relation.form)), relation.output.clone()), columns);
            }
        }
    }
    let mut columns = Vec::new();
    for index in 0..program.graph.nodes.len() as u32 {
        let node = GraphNodeIndex(index);
        let form = program.form_of(node);
        let output = |port: &PortName| fixed.get(&(form.clone(), Arc::from([OutputStep::Port(port.clone())]))).copied();
        match &program.graph.nodes[index as usize].kind {
            DependencyKind::Fact(fact) => {
                let declared = registry.fact_columns(*fact);
                let column = |name: &ColumnName| declared_type(declared, std::slice::from_ref(name), PoseOr::Open);
                let found = relation_columns(declared.iter().map(|column| &column.name), &column);
                columns.extend(found.map(|found| (GraphRelation { node, output: None }, found)));
            }
            DependencyKind::Clause(_) | DependencyKind::Parameter(_) | DependencyKind::Chosen(_) => {
                columns.extend(given_columns(program, &types, &fixed, node).map(|found| (GraphRelation { node, output: None }, found)));
            }
            DependencyKind::InstanceInput { input: port, .. } | DependencyKind::InstanceOutput { output: port, .. } => {
                columns.extend(output(port).map(|found| (GraphRelation { node, output: None }, found.into())));
            }
            DependencyKind::Demonstrated(_) => {
                let own = fixed.get(&(form.clone(), Arc::from([])));
                columns.extend(own.map(|found| (GraphRelation { node, output: None }, (*found).into())));
            }
            DependencyKind::RecursiveInstance(_) | DependencyKind::RigidAssembly(_) => {
                let outputs = fixed.iter().filter(|((at, output), _)| at == form && !output.is_empty());
                columns.extend(outputs.map(|((_, output), found)| (GraphRelation { node, output: Some(output.clone()) }, (*found).into())));
            }
        }
    }
    for (relation, found) in columns {
        types.insert_columns(relation, found);
    }
    types
}

/// The types of the columns of `node`, a relation that clauses or a
/// `CHOOSE` form give, from the [`ProgramTypes::form`] of `types` and the
/// relations `fixed` holds, as [`program_types`] gives them, or `None`
/// where a form of the node gives a column no type or two forms give types
/// with no join.
fn given_columns(
    program: &ResolvedProgram,
    types: &ProgramTypes,
    fixed: &StableHashMap<(NodePath, Arc<[OutputStep]>), &[ValueType]>,
    node: GraphNodeIndex,
) -> Option<Box<[ValueType]>> {
    let mut joined: Option<Vec<ValueType>> = None;
    for form in program.forms_of(node) {
        let columns: Vec<ValueType> = match fixed.get(&(form.clone(), Arc::from([]))) {
            Some(found) => found.to_vec(),
            None => {
                let at = crate::program::path::node_at(NodeRef::Program(program.program.value()), form)?;
                let rule_scope = match &program.graph.nodes[node.0 as usize].scope {
                    NameScope::DemoRule(rule) => types.form(rule),
                    NameScope::Program => None,
                };
                let labels = types.form(form).or(rule_scope)?;
                let position = |label: LabelId| program.label_position(form, label).map(|position| position.0);
                let mut slots: Vec<Option<ValueType>> = Vec::new();
                for column in columns::form_columns(at) {
                    let Some(index) = position(column.label) else { continue };
                    let index = usize::from(index);
                    let key_row = |key: &[LabelId]| Some(KeyRow::Columns(key.iter().map(|label| position(*label)).collect::<Option<_>>()?));
                    let ty = try_map_key_rows(labels.label(column.label)?, &key_row)?;
                    slots.resize(slots.len().max(index + 1), None);
                    slots[index] = Some(ty);
                }
                let mut out = Vec::new();
                for slot in slots {
                    flatten(slot?, &mut out);
                }
                out
            }
        };
        joined = Some(match joined {
            None => columns,
            Some(prev) if prev.len() == columns.len() => prev.iter().zip(&columns).map(|(a, b)| a.join(b)).collect::<Option<_>>()?,
            Some(_) => return None,
        });
    }
    joined.map(Vec::into_boxed_slice)
}

/// The signatures of the clauses that the type check of `form`, a
/// top-level form whose canonical order is `order`, reads, as
/// [`CheckId::Types`] gives, each once: for a clause, those of the clauses
/// of its relation, then, for each clause form that stands in a label scope
/// of the form, as [`CanonicalOrder::label_scopes`] gives them, in their
/// order, where it has a head label that only `(= *X 0)` gives a type,
/// those of the clauses of its
/// relation, each relation's in the order [`SolverClauses`] gives.
pub fn type_clause_signatures<'a>(form: &Form, order: &CanonicalOrder, clauses: &'a SolverClauses) -> impl Iterator<Item = &'a Signature> {
    let mut signatures: Vec<&'a Signature> = Vec::new();
    let mut add = |clause: &crate::program::Clause| {
        for entry in clauses.of_relation(&FileScope::Program, &clause.derives) {
            if !signatures.contains(&&entry.signature) {
                signatures.push(&entry.signature);
            }
        }
    };
    if let Form::Clause(clause) = form {
        add(clause.value());
    }
    for source in inferred_scopes(order) {
        for (_, found) in scope_forms_within(form, &source) {
            if let Form::Clause(clause) = found {
                if !zero_typed_heads(clause.value()).is_empty() {
                    add(clause.value());
                }
            }
        }
    }
    signatures.into_iter()
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
    try_map_key_rows(ty, &|labels| Some(KeyRow::Labels(labels.iter().map(|label| map(*label)).collect::<Option<_>>()?)))
}

/// `ty` with each key row of labels replaced by the one `map` gives for
/// its labels, or `None` where `map` gives none.
fn try_map_key_rows(ty: &ValueType, map: &dyn Fn(&[LabelId]) -> Option<KeyRow>) -> Option<ValueType> {
    Some(match ty {
        ValueType::Pose(AssemblyId { name, canonical_form, key: KeyRow::Labels(labels) }) => {
            ValueType::Pose(AssemblyId { name: name.clone(), canonical_form: canonical_form.clone(), key: map(labels)? })
        }
        ValueType::Record(fields) => {
            ValueType::Record(fields.iter().map(|(name, ty)| Some((name.clone(), try_map_key_rows(ty, map)?))).collect::<Option<_>>()?)
        }
        ty => ty.clone(),
    })
}

/// The types of the columns that a value of type `ty` takes, in their
/// order: a record's fields, each a column of its own, or `ty`.
fn flatten(ty: ValueType, out: &mut Vec<ValueType>) {
    match ty {
        ValueType::Record(fields) => fields.into_vec().into_iter().for_each(|(_, field)| flatten(field, out)),
        ty => out.push(ty),
    }
}

/// The types of the columns of a relation whose columns are `names`, in
/// their order, each name's type as `column` gives it and a record's fields
/// each a column of its own, or `None` where `column` gives a name no type.
fn relation_columns<'n>(names: impl IntoIterator<Item = &'n ColumnName>, column: &dyn Fn(&ColumnName) -> Option<ValueType>) -> Option<Box<[ValueType]>> {
    let mut out = Vec::new();
    for name in names {
        flatten(column(name)?, &mut out);
    }
    Some(out.into())
}

/// The type at `rest` of a value of type `ty`: a record's field for each
/// step, and `ty` itself past a type that is no record, as a bare label's
/// name after a column of a type parameter bound to one label's type.
fn project(ty: &ValueType, rest: &[ColumnName]) -> Option<ValueType> {
    match (ty, rest) {
        (ValueType::Record(fields), [field, rest @ ..]) => project(&fields.iter().find(|(found, _)| found == field)?.1, rest),
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

pub(super) use columns::component;

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
    form_within(program.forms.get(first.0 as usize)?, &NodePath(rest.into()))
}

/// The form at `path`, a path relative to `form`: `form` itself at the
/// empty path, or a form of a claim, of an `ALT` or of a `DEMO_RULE`
/// within it.
fn form_within<'p>(form: &'p Form, path: &NodePath) -> Option<&'p Form> {
    let mut form = form;
    let mut steps = path.0.iter();
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
    let (first, rest) = path.0.split_first()?;
    rule_within(program.forms.get(first.0 as usize)?, &NodePath(rest.into()))
}

/// The `DEMO_RULE` form at `path`, a path relative to `form`.
fn rule_within<'p>(form: &'p Form, path: &NodePath) -> Option<&'p crate::program::DemoRule> {
    let (rule, prefix) = path.0.split_last()?;
    let Form::Demonstrated(demonstrated) = form_within(form, &NodePath(prefix.into()))? else { return None };
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
                SiteArg::NamedLabel { name, label: use_ } => Some((name.clone(), label(use_label(*use_)?)?)),
                SiteArg::Field(field) => Some((field.column.clone(), site_value_type(field, label)?)),
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
        if let Some(atom) = node.atom() {
            return self.atom(atom, at);
        }
        match node {
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
            Resolution::Lib(name) => declared_type(columns::lib_typed_columns(self.registry, name)?, path, reading.pose_or),
            Resolution::Node(_) if path == [columns::example()] && self.program.reads_lifted(&at) => Some(ValueType::Example),
            Resolution::Node(node) => self.node_type(*node, atom, path, reading.pose_or),
            Resolution::Undefined(_) | Resolution::Unresolved => None,
        }
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
                let column = path.first().and_then(|first| columns::lib_typed_columns(self.registry, name)?.iter().find(|column| column.name == *first));
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
        let column = path.first().and_then(|first| columns::lib_typed_columns(self.registry, name)?.iter().find(|column| column.name == *first));
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

    /// Where `clause`, a clause of `scope`, takes the columns of its
    /// relation from: its own columns, its first proposer's declared
    /// columns, or the instance output it stands for.
    fn clause_columns<'c>(&'c self, clause: &'c crate::program::Clause, scope: &NameScope) -> Option<ClauseColumns<'c>> {
        if !clause.columns.is_empty() {
            return Some(ClauseColumns::Own(&clause.columns));
        }
        if let Some(proposer) = clause.proposers.first() {
            let columns = match columns::lib_typed_columns(self.registry, proposer) {
                Some(columns) => columns,
                None => &self.registry.derivation(proposer)?.columns,
            };
            return Some(ClauseColumns::Declared(columns));
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
    /// [`CheckId::Types`] gives. Each stands at the first use of the
    /// clause's label at that column, or at the clause where it holds no
    /// columns.
    fn column_refusals(&self, form: &FormInference<'_>, clause: &crate::program::Clause, path: &NodePath, order: &CanonicalOrder) -> Vec<Refusal> {
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
    fn form_relations(&self, at: &NodePath, form: &'a Form) -> Vec<(Arc<[OutputStep]>, Box<[ValueType]>)> {
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
                let (Some(component), Some(Form::Instance(instance))) = (inference.component, inference.form) else { return Vec::new() };
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
        let Some(form @ Form::RigidDet(rigid)) = inference.form else { return None };
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
        let Some(Form::Demonstrated(demonstrated)) = inference.form else { return None };
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
