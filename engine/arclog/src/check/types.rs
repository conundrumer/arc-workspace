//! The type check, the two functions through which it hands its types to
//! [`super::check_program`], the helpers that it and the inference of a
//! case program's label types share, and, in its module `within`, the
//! lookups of forms and label scopes that they read.

use std::sync::Arc;

use super::inference::FormInference;
use super::{Check, CheckId, CheckInput, CheckResult, FileScope, Prefix, PrefixResult, Refusal, SolverClauses};
use crate::hash::StableHashMap;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    ColumnName, Conjunct, Constraint, ConstraintOp, Form, LabelId, NameScope, Operand, OutputStep, PortName, Site, SiteArg,
};
use crate::registry::{Column, ColumnType, Registry, TypeParameter};
use crate::resolver::form_columns;
use crate::resolver::registry_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, ResolvedProgram, Side, Signature};
use crate::types::{
    each_conjunct, each_site_label, label_fault_message, use_label, AssemblyId, FormRelation, FormTypes,
    GraphRelation, KeyRow, LabelFault, ProgramTypes, ValueType,
};
pub(super) use within::{demo_rule, form_at, form_within, rule_scope_forms, scope_forms};
use within::rule_within;

mod within;

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
    let inference = input.scope.inference;
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
    rule_scope_forms(rule).map(|(index, found)| (scope.child(index), found)).collect()
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
                for column in form_columns::form_columns(at) {
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
pub(super) fn zero_typed_heads(clause: &crate::program::Clause) -> Vec<LabelId> {
    let mut at_sites = Vec::new();
    let mut zeroed = Vec::new();
    each_conjunct(clause.body.value(), &mut |conjunct| match conjunct {
        Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) if first.fresh => zeroed.push(first.label),
        _ => {
            if let Some(atom) = conjunct.atom() {
                for site in atom.value().sites.iter() {
                    each_site_label(site, &mut Vec::new(), &mut |use_, _| at_sites.extend(use_label(use_)));
                }
            }
        }
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
pub(super) fn try_map_labels(ty: &ValueType, map: &dyn Fn(LabelId) -> Option<LabelId>) -> Option<ValueType> {
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
pub(super) fn relation_columns<'n>(names: impl IntoIterator<Item = &'n ColumnName>, column: &dyn Fn(&ColumnName) -> Option<ValueType>) -> Option<Box<[ValueType]>> {
    let mut out = Vec::new();
    for name in names {
        flatten(column(name)?, &mut out);
    }
    Some(out.into())
}

/// The type at `rest` of a value of type `ty`: a record's field for each
/// step, and `ty` itself past a type that is no record, as a bare label's
/// name after a column of a type parameter bound to one label's type.
pub(super) fn project(ty: &ValueType, rest: &[ColumnName]) -> Option<ValueType> {
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
pub(super) fn column_type(ty: &ColumnType, rest: &[ColumnName], bindings: &StableHashMap<TypeParameter, ValueType>, pose_or: PoseOr) -> Option<ValueType> {
    match ty {
        ColumnType::Fixed(ty) => Some(ty.clone()),
        ColumnType::PoseOr(ty) => (pose_or == PoseOr::Given).then(|| ty.clone()),
        ColumnType::Pose | ColumnType::SharedPose => None,
        ColumnType::Parameter(parameter) => project(bindings.get(parameter)?, rest),
    }
}

/// The type the column at `path` of `columns` gives a site.
pub(super) fn declared_type(columns: &[Column], path: &[ColumnName], pose_or: PoseOr) -> Option<ValueType> {
    let (first, rest) = path.split_first()?;
    column_type(&columns.iter().find(|column| column.name == *first)?.ty, rest, &StableHashMap::default(), pose_or)
}

pub(super) use registry_columns::component;

/// The side of the form at `form` of `program`, the side of the first node
/// of the dependency graph that the form gives, or `None` where it gives
/// none.
pub(super) fn form_side(program: &ResolvedProgram, form: &NodePath) -> Option<Side> {
    let mut nodes = (0..program.graph.nodes.len() as u32).map(GraphNodeIndex);
    nodes.find(|found| program.form_of(*found) == form).map(|found| program.side(found))
}

/// The type of the value at `site` of a head or of a read: its one bare
/// label's type, or a record with a field per argument.
pub(super) fn site_value_type(site: &Site, label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
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
