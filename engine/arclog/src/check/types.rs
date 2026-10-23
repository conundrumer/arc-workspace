//! The types of a case program: the type check in its module
//! `form_check`, the typing of a program's relations, which hands the
//! check's types to [`super::check_program`], the helpers that the check
//! and the inference of a case program's label types share, and, in its
//! module `within`, the lookups of forms and label scopes that they read.

use std::sync::Arc;

use super::{CheckResult, ClauseEntry, FileScope, HeldClauses, Refusal, SolverClauses};
use crate::hash::StableHashMap;
use crate::program::canonical::CanonicalOrder;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{
    ColumnName, Form, LabelId, NameScope, OutputStep, PortName, Site, SiteArg,
};
use crate::registry::{Column, ColumnType, Registry, TypeParameter};
use crate::resolver::form_columns;
use crate::resolver::registry_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, ResolvedProgram, Signature};
use crate::types::{
    use_label, AssemblyId, FormTypes,
    GraphRelation, KeyRow, LabelFault, ProgramTypes, ValueType, ZeroMade,
};
pub(super) use within::{demo_rule, form_at, form_within, rule_scope_forms, scope_forms};
use within::rule_within;

mod form_check;
mod within;

pub use form_check::{infer_form, ScopeTypes, TypesCheck};
use form_check::{inferred_scopes, scope_forms_within};

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
/// [`crate::check::CheckId::Types`] gives, each once: for a clause, those of the clauses
/// of its relation, then, for each clause form that stands in a label scope
/// of the form, as [`CanonicalOrder::label_scopes`] gives them, in their
/// order, where it has a head label that only `(= *X 0)` gives a type,
/// those of the clauses of its
/// relation in all of the solver's case programs, each relation's in the
/// order [`SolverClauses`] gives. Otherwise the clauses of a relation are
/// those that the case program of `held` holds.
pub fn type_clause_signatures<'a>(form: &Form, order: &CanonicalOrder, clauses: &'a SolverClauses, held: &'a HeldClauses) -> impl Iterator<Item = &'a Signature> {
    let mut signatures: Vec<&'a Signature> = Vec::new();
    let mut add = |entries: &mut dyn Iterator<Item = &'a ClauseEntry>| {
        for entry in entries {
            if !signatures.contains(&&entry.signature) {
                signatures.push(&entry.signature);
            }
        }
    };
    if let Form::Clause(clause) = form {
        add(&mut clauses.of_relation_in(&clause.value().derives, held));
    }
    for source in inferred_scopes(order) {
        for (_, found) in scope_forms_within(form, &source) {
            if let Form::Clause(clause) = found {
                if !zero_typed_heads(clause.value()).is_empty() {
                    add(&mut clauses.of_relation(&FileScope::Program, &clause.value().derives).iter());
                }
            }
        }
    }
    signatures.into_iter()
}

/// The head labels of `clause` that only `(= *X 0)` gives a type: each
/// stands at no site of an atom and is made by such a constraint.
pub(super) fn zero_typed_heads(clause: &crate::program::Clause) -> Vec<LabelId> {
    let ZeroMade { zeroed, at_sites } = ZeroMade::of(clause.body.value());
    let heads = clause.columns.iter().map(|column| column.label);
    heads.filter(|label| zeroed.contains(&(*label, true)) && !at_sites.contains(label)).collect()
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

/// The type of the value at `site` of a head or of a read: its one bare
/// label's type, or a record with a field per argument.
pub(super) fn site_value_type(site: &Site, label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
    site_value_type_or(site, &[], label, &|_| None)
}

/// [`site_value_type`], except that a label with no type, at the field path
/// `path` below `site`, takes the type `missing` gives that path.
pub(super) fn site_value_type_or(
    site: &Site,
    path: &[ColumnName],
    label: &dyn Fn(LabelId) -> Option<ValueType>,
    missing: &dyn Fn(&[ColumnName]) -> Option<ValueType>,
) -> Option<ValueType> {
    match &site.value.args[..] {
        [SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. }] => label(use_label(*use_)?).or_else(|| missing(path)),
        args => {
            let at = |name: &ColumnName| -> Vec<ColumnName> { path.iter().chain(std::iter::once(name)).cloned().collect() };
            let field = |arg: &SiteArg| match arg {
                SiteArg::NamedLabel { name, label: use_ } => Some((name.clone(), label(use_label(*use_)?).or_else(|| missing(&at(name)))?)),
                SiteArg::Field(field) => Some((field.column.clone(), site_value_type_or(field, &at(&field.column), label, missing)?)),
                SiteArg::Label(_) => None,
            };
            Some(ValueType::Record(args.iter().map(field).collect::<Option<_>>()?))
        }
    }
}
