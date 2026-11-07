//! The types of the columns of a case program's relations, from the types
//! of its forms' labels: [`program_types`] gives [`ProgramTypes`] its
//! forms' label types and every relation's column types.

use std::sync::Arc;

use super::own_idents::own_idents;
use super::{declared_type, flatten, map_labels, relation_columns, try_map_key_rows, PoseOr, ScopeTypes};
use crate::hash::StableHashMap;
use crate::program::canonical::CanonicalOrder;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{ColumnName, LabelId, NameScope, OutputStep, PortName};
use crate::registry::Registry;
use crate::resolver::form_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, ResolvedProgram};
use crate::types::{FormTypes, GraphRelation, KeyRow, ProgramTypes, ValueType};
use super::SolverClauses;
use crate::check::earlier::Kept;

/// A top-level form of a program for [`program_types`]: its path, the types
/// of each of its label scopes, its canonical order, and what the check of
/// the finished forms kept of it.
pub(in crate::check) struct FormScopes<'p> {
    pub(in crate::check) path: NodePath,
    pub(in crate::check) scopes: Arc<ScopeTypes>,
    pub(in crate::check) order: &'p CanonicalOrder,
    pub(in crate::check) kept: Option<Arc<Kept>>,
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
/// relation a column of which no form types gets no column types. The types
/// of a `RIGID_DET` form hold the labels at its parts' sites and key columns that are
/// the assembly's own Idents, as `own_idents` gives them.
pub(in crate::check) fn program_types(
    program: &ResolvedProgram,
    registry: &Registry,
    _clauses: &SolverClauses,
    forms: &[FormScopes<'_>],
) -> ProgramTypes {
    let _timed = crate::stats::span(crate::stats::Phase::CheckProgramTypes);
    crate::stats::units(crate::stats::Phase::CheckProgramTypes, program.graph.nodes.len());
    let mut types = ProgramTypes::default();
    let own_idents = own_idents(program, registry);
    let mut fixed: StableHashMap<(NodePath, Arc<[OutputStep]>), &[ValueType]> = StableHashMap::default();
    for FormScopes { path, scopes, order, kept } in forms {
        let entries = || -> Vec<(NodePath, Arc<FormTypes>)> {
            scopes
                .iter()
                .map(|(canonical, form_types)| {
                    let source = order.source_path(canonical);
                    let own = |position: LabelId| order.source_label(&source, position.0);
                    let labels = form_types.labels().map(|(label, ty)| (own(label), map_labels(ty, &own)));
                    let at = path.join(&source);
                    let own = own_idents.get(&at).into_iter().flatten().copied();
                    (at, Arc::new(FormTypes::new(labels, []).with_own_idents(own)))
                })
                .collect()
        };
        // With no own Ident in the program, the types of a form's scopes read the form's own types alone, which the form keeps.
        let held;
        let entries = match kept.as_ref().filter(|_| own_idents.is_empty()) {
            Some(kept) => kept.scopes.get_or_init(entries),
            None => {
                held = entries();
                &held
            }
        };
        for (at, form_types) in entries {
            types.insert_form(at.clone(), Arc::clone(form_types));
        }
        for (_, form_types) in scopes.iter() {
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
            DependencyKind::Clause(_) | DependencyKind::Parameter(_) | DependencyKind::Chosen(_) | DependencyKind::Out(_) => {
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
