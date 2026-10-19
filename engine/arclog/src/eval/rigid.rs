//! A `RIGID_DET` assembly at its stored records: its outputs
//! `&marker.<part>` and `&marker.pose`, as `docs/arclog/rigid.md#semantics`
//! gives.
//!
//! The stored record of a part, `&marker.<part>`, holds its common reading:
//! the key's columns, where the form has a key, then the part's columns.
//! A part's site that holds a bare label of the `instance` clause selects
//! the part's rows at an instance and gives the part no column, so an
//! instance's reading of the part is the part's rows at that instance's
//! row, without those columns.

use std::sync::Arc;

use super::join::{self, Budget};
use super::{ir, Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::algebra::boxes::apply;
use crate::algebra::orientation::{D4Element, Geometry};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Atom, Body, Conjunct, LabelId, Node, OutputName, OutputOwner, OutputStep, ProgramRelation, RigidDet};
use crate::relations::{Row, RowSet};
use crate::resolver::form_columns;
use crate::terms::{Constant, Example, Term, TermId};
use crate::types::{each_site_label, use_label, FormTypes, ValueType};

/// The value of `output`, an output of the `RIGID_DET` form at `form`:
/// [`OutputStep::Part`] for `&marker.<part>`, and [`OutputStep::Pose`] for
/// `&marker.pose`, with the columns `docs/arclog/rigid.md#semantics` gives,
/// on `example`, or task-wide where it is `None`, with the form's bodies
/// evaluated through `bodies`.
///
/// A part's columns leave out each site that holds a bare label of the
/// `instance` clause. A part's site that holds a label of the `instance`
/// clause inside a term of other labels, a part whose
/// stored record is absent or does not read at the part's column types,
/// and an output step that more than one part's path begins with give a
/// [`RunFault`].
pub fn evaluate_assembly(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &OutputStep,
    example: Option<Example>,
    budget: &mut Budget<'_>,
) -> Outcome<RelationValue> {
    let root = NodeRef::Program(evaluation.program.program.program.value());
    let Some(NodeRef::RigidDet(rigid)) = node_at(root, form) else { panic!("a `RIGID_DET` form at the form of an assembly output") };
    let assembly = Assembly::of(evaluation, form, rigid)?;
    let rows = match output {
        OutputStep::Pose => assembly.poses(bodies, example, budget)?,
        step => assembly.placements(assembly.part(step)?, budget)?,
    };
    Ok(rows.map_or_else(|value| value, |rows| RelationValue::Rows(Arc::new(join::one_part(rows)))))
}

/// One part of an assembly: its atom with its path, the labels of its
/// sites that give it a column, in the order of its columns, and their
/// types.
struct Part<'p> {
    atom: &'p Node<Atom>,
    path: NodePath,
    labels: Vec<LabelId>,
    types: Vec<ValueType>,
}

/// What a `RIGID_DET` form gives the evaluation of its assembly: its key
/// and instance clauses with their paths and labels, and its parts.
struct Assembly<'e, 'p> {
    evaluation: &'e Evaluation<'p>,
    form: &'e NodePath,
    rigid: &'p RigidDet,
    key: Option<(&'p Body, NodePath)>,
    key_labels: Vec<LabelId>,
    key_types: Vec<ValueType>,
    instance: Option<(&'p Body, NodePath)>,
    instance_labels: Vec<LabelId>,
    parts: Vec<Part<'p>>,
}

impl<'e, 'p> Assembly<'e, 'p> {
    /// The assembly of `rigid`, the `RIGID_DET` form at `form`.
    fn of(evaluation: &'e Evaluation<'p>, form: &'e NodePath, rigid: &'p RigidDet) -> Outcome<Self> {
        let fault = |message: String| fault(form, message);
        let types = ir::label_types(evaluation.program, form);
        let typed = |labels: &[LabelId]| -> Outcome<Vec<ValueType>> {
            labels.iter().map(|&label| label_type(types, label).map_err(&fault)).collect()
        };
        let mut clauses = 0u32;
        let mut clause = |body: &'p Option<crate::program::KeyBody>| {
            body.as_ref().map(|key| {
                let path = form.child(clauses);
                clauses += 1;
                ((key.body.value(), path), key.columns.iter().map(|column| column.label).collect::<Vec<_>>())
            })
        };
        let (key, key_labels) = clause(&rigid.key).unzip();
        let (instance, instance_labels) = clause(&rigid.instance).unzip();
        let (key_labels, instance_labels) = (key_labels.unwrap_or_default(), instance_labels.unwrap_or_default());
        let mut parts = Vec::with_capacity(rigid.parts.len());
        for (atom, index) in rigid.parts.iter().zip(clauses..) {
            let mut labels = Vec::new();
            for site in atom.value().sites.iter().filter(|site| !form_columns::at_instance(rigid, site)) {
                each_site_label(site, &mut Vec::new(), &mut |use_, _| labels.extend(use_label(use_)));
            }
            if labels.iter().any(|label| instance_labels.contains(label)) {
                return Err(fault("a part's site holds a label of the `instance` clause inside a term of other labels, whose column `docs/arclog/rigid.md#semantics` gives no value in the part's output".into()));
            }
            let types = typed(&labels)?;
            parts.push(Part { atom, path: form.child(index), labels, types });
        }
        let key_types = typed(&key_labels)?;
        Ok(Assembly { evaluation, form, rigid, key, key_labels, key_types, instance, instance_labels, parts })
    }

    fn fault(&self, message: String) -> RunFault {
        fault(self.form, message)
    }

    /// The value of the assembly's output where `budget` reached `bound`.
    fn stopped(&self, bound: super::ReachedBound) -> RelationValue {
        RelationValue::Stopped(Stop { bound, form: self.form.clone() })
    }

    /// The count of an output row's key columns.
    fn key_width(&self) -> usize {
        if self.key.is_some() { self.key_labels.len() } else { 1 }
    }

    /// The one part whose output's path begins with `step`.
    fn part(&self, step: &OutputStep) -> Outcome<&Part<'p>> {
        let mut found = self.parts.iter().filter(|part| self.steps(part).first() == Some(step));
        match (found.next(), found.next()) {
            (Some(part), None) => Ok(part),
            (Some(_), Some(_)) => Err(self.fault(format!("more than one part's output begins with the step {step:?}"))),
            (None, _) => panic!("an output step of a part of the assembly"),
        }
    }

    /// The path after the form's name of `part`'s output.
    fn steps(&self, part: &Part<'_>) -> Vec<OutputStep> {
        form_columns::part_steps(&part.atom.value().relation).expect("a part that reads a relation")
    }

    /// The key columns of an output row at the key `key`: the key's columns,
    /// or the one `Unit` column of a form with no key.
    fn key_columns<'k>(&self, key: &'k [TermId]) -> std::borrow::Cow<'k, [TermId]> {
        if self.key.is_some() {
            key.into()
        } else {
            vec![Term::Constant(Constant::Unit).encode().expect("a Unit has a term id")].into()
        }
    }

    /// The common reading of `part` from its stored record, by key: each
    /// key's rows of the part's columns.
    fn common_reading(&self, part: &Part<'_>) -> Outcome<StableHashMap<Row, RowSet>> {
        let evaluation = self.evaluation;
        let name = ProgramRelation::Output(OutputName { of: OutputOwner::RigidDet(self.rigid.name.clone()), path: self.steps(part).into() });
        let value = evaluation.parameters.get(&name).ok_or_else(|| self.fault("no stored record gives a part's common reading".into()))?;
        let types: Vec<ValueType> = self.key_types.iter().chain(&part.types).cloned().collect();
        let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
        let rows = crate::terms::encode_param_value(value, &types, evaluation.registry, &mut table)
            .map_err(|error| self.fault(format!("a part's stored rows do not read at its column types: {error:?}")))?;
        let mut by_key: StableHashMap<Row, RowSet> = StableHashMap::default();
        for row in rows {
            let (key, values) = row.split_at(self.key_labels.len());
            by_key.entry(key.into()).or_insert_with(|| RowSet::empty(part.labels.len() as u16)).insert(values.into());
        }
        Ok(by_key)
    }

    /// The rows of `&marker.<part>`: at each key, at each D4 element, the
    /// image of the part's common reading under it, or the value of a stop.
    fn placements(&self, part: &Part<'_>, budget: &mut Budget<'_>) -> Outcome<Result<RowSet, RelationValue>> {
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let mut rows = RowSet::empty((self.key_width() + 1 + part.labels.len()) as u16);
        for (key, reading) in self.common_reading(part)? {
            if let Err(bound) = budget.charge_rows((elements.len() * reading.len()) as u64) {
                return Ok(Err(self.stopped(bound)));
            }
            for &element in elements {
                let g = geometry.element(element);
                for values in reading.rows() {
                    let mut row = self.key_columns(&key).into_owned();
                    row.push(element);
                    row.extend(image(geometry, g, values, &part.types));
                    rows.insert(row.into());
                }
            }
        }
        Ok(Ok(rows))
    }

    /// The rows of `&marker.pose`: for each instance, each D4 element that
    /// takes the common reading onto the instance's reading at every part
    /// at once, or the value of a body of the form that is `undefined` or
    /// stopped, or of a stop.
    fn poses(&self, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<RowSet, RelationValue>> {
        let prefix: Vec<LabelId> = self.key_labels.iter().chain(&self.instance_labels).copied().collect();
        let clauses: Vec<&(&Body, NodePath)> = self.key.iter().chain(&self.instance).collect();
        let instances = match clauses.is_empty() {
            true => vec![Row::default()],
            false => match self.rows(bodies, &clauses, None, &prefix, example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            },
        };
        let mut readings: Vec<(StableHashMap<Row, RowSet>, StableHashMap<Row, RowSet>)> = Vec::with_capacity(self.parts.len());
        for part in &self.parts {
            let columns: Vec<LabelId> = prefix.iter().chain(&part.labels).copied().collect();
            let rows = match self.rows(bodies, &clauses, Some(part), &columns, example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            };
            let mut by_instance: StableHashMap<Row, RowSet> = StableHashMap::default();
            for row in rows {
                let (at, values) = row.split_at(prefix.len());
                by_instance.entry(at.into()).or_insert_with(|| RowSet::empty(part.labels.len() as u16)).insert(values.into());
            }
            readings.push((self.common_reading(part)?, by_instance));
        }
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let mut rows = RowSet::empty((self.key_width() + self.instance_labels.len() + 1) as u16);
        for instance in &instances {
            if let Err(bound) = budget.charge_work(elements.len() as u64) {
                return Ok(Err(self.stopped(bound)));
            }
            let (key, at) = instance.split_at(self.key_labels.len());
            for &element in elements {
                let g = geometry.element(element);
                let takes = self.parts.iter().zip(&readings).all(|(part, (common, observed))| {
                    let images: StableHashSet<Row> = common
                        .get(key)
                        .into_iter()
                        .flat_map(|common| common.rows())
                        .map(|values| image(geometry, g, values, &part.types).collect())
                        .collect();
                    let observed = observed.get(&instance[..]);
                    images.len() == observed.map_or(0, RowSet::len) && observed.into_iter().flat_map(|o| o.rows()).all(|values| images.contains(values))
                });
                if takes {
                    let mut row = self.key_columns(key).into_owned();
                    row.extend_from_slice(at);
                    row.push(element);
                    rows.insert(row.into());
                }
            }
        }
        Ok(Ok(rows))
    }

    /// The rows of `clauses`, the key and instance bodies, joined with the
    /// atom of `part` where it is given, at the labels `columns`, or the
    /// value of the join where it is `undefined` or stopped.
    fn rows(
        &self,
        bodies: &FormBodies<'_>,
        clauses: &[&(&Body, NodePath)],
        part: Option<&Part<'_>>,
        columns: &[LabelId],
        example: Option<Example>,
    ) -> Outcome<Result<Vec<Row>, RelationValue>> {
        let atom = part.map(|part| (Conjunct::Atom(part.atom.clone()), part.path.clone()));
        let conjuncts = clauses
            .iter()
            .flat_map(|(body, path)| body.conjuncts.iter().zip(0u32..).map(move |(conjunct, index)| (conjunct, path.child(index))))
            .chain(atom.iter().map(|(conjunct, path)| (conjunct, path.clone())))
            .collect();
        let clause = ir::compile_grounded(self.evaluation.program, self.form, conjuncts, columns)
            .map_err(|compile| self.fault(format!("a body of the form does not compile: {compile:?}")))?;
        let relation = match bodies.relation(self.form, &clause, example)? {
            RelationValue::Rows(relation) => relation,
            value => return Ok(Err(value)),
        };
        if relation.arity() as usize != columns.len() {
            return Err(self.fault(format!("a body gives {} columns, where {} are read", relation.arity(), columns.len())));
        }
        let mut rows = Vec::new();
        join::each_row(&relation, &mut |row| rows.push(row.into()));
        Ok(Ok(rows))
    }
}

/// The fault `message` at the form at `form`.
fn fault(form: &NodePath, message: String) -> RunFault {
    RunFault { message: message.into(), form: form.clone() }
}

/// The type of `label`, or the fault of a label with none.
fn label_type(types: &FormTypes, label: LabelId) -> Result<ValueType, String> {
    types.label(label).cloned().ok_or_else(|| format!("the label {label:?} has no type"))
}

/// The image under `g` of `values`, whose columns take `types`, each value
/// acted on by its type, as `docs/arclog/rigid.md#semantics` gives.
fn image<'v>(geometry: &'v Geometry, g: D4Element, values: &'v [TermId], types: &'v [ValueType]) -> impl Iterator<Item = TermId> + 'v {
    values.iter().zip(types).map(move |(&value, ty)| match ty {
        ValueType::Box => {
            Term::Box(apply(g, Term::decode_box(value))).encode().expect("a Box's margins, moved among its edges, each fit a signed byte")
        }
        ValueType::Dir | ValueType::DiagDir | ValueType::Dir8 | ValueType::Axis | ValueType::DiagAxis | ValueType::Axis4 | ValueType::Sense => {
            geometry.under(g, value)
        }
        ValueType::Number
        | ValueType::Color
        | ValueType::Example
        | ValueType::Unit
        | ValueType::Ident
        | ValueType::C4
        | ValueType::D4
        | ValueType::Sym
        | ValueType::Pose(_) => value,
        ValueType::Record(_) => unreachable!("a label's type is no record"),
    })
}
