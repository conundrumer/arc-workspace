//! A `RIGID_DET` assembly: its outputs `&marker.<part>` and
//! `&marker.pose`, as `docs/arclog/rigid.md#semantics` gives, computed from
//! its instances' readings by the method of
//! `docs/arclog/rigid.md#implementation`.
//!
//! An assembly's instances are the rows of its `instance` clause, and a form
//! with none has one instance at each key. An instance's reading is its
//! rows of each part, in the form's order of parts. At each key, the frame,
//! the common reading of the key's instances, is the reading of the instance
//! whose reading is least by content, as `docs/engine/determination.md#rigid_det`
//! gives, so the frame depends on no order of encodings. An element takes a
//! frame onto an instance's reading where, for some one-to-one renaming of
//! the assembly's own Idents, the same at every part, the frame's image
//! under the element, with those Idents renamed, is the reading
//! (`docs/arclog/rigid.md#semantics`). Where some instance has no D4
//! element that does, the assembly has no value, and each output is
//! `undefined`.
//!
//! A part's site that holds a bare label of the `instance` clause selects
//! the part's rows at an instance and gives the part no column, so an
//! instance's reading of the part is the part's rows at that instance's
//! row, without those columns.

pub mod renaming;

use std::cmp::Ordering;
use std::sync::Arc;

use self::renaming::{renaming_between, IdentRowsBuilder};
use super::join::{self, Budget};
use super::{ir, Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::algebra::boxes::apply;
use crate::algebra::geometry::{D4Element, Geometry};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Atom, Body, Conjunct, LabelId, Node, OutputStep, RigidDet};
use crate::relations::{Row, RowSet};
use crate::resolver::form_columns;
use crate::terms::{Example, Term, TermId};
use crate::types::{each_site_label, use_label, FormTypes, ValueType};

/// The value of `output`, an output of the `RIGID_DET` form at `form`:
/// [`OutputStep::Part`] for `&marker.<part>`, and [`OutputStep::Pose`] for
/// `&marker.pose`, with the columns `docs/arclog/rigid.md#semantics` gives,
/// on `example`, or task-wide where it is `None`, with the form's bodies
/// evaluated through `bodies`.
///
/// A part's columns leave out each site that holds a bare label of the
/// `instance` clause. A part's site that holds a label of the `instance`
/// clause inside a term of other labels, and an output step that more than one part's path begins with give a
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
        step => assembly.placements(assembly.part(step)?, bodies, example, budget)?,
    };
    Ok(rows.map_or_else(|value| value, |rows| RelationValue::Rows(Arc::new(join::one_part(rows)))))
}

/// One part of an assembly: its atom with its path, the labels of its
/// sites that give it a column, in the order of its columns, their types,
/// and whether each column holds the assembly's own Idents.
struct Part<'p> {
    atom: &'p Node<Atom>,
    path: NodePath,
    labels: Vec<LabelId>,
    types: Vec<ValueType>,
    own: Vec<bool>,
}

/// An instance of an assembly: its row of the key and instance clauses,
/// and its reading, its rows of each part in the order of the parts.
struct Instance {
    row: Row,
    reading: Vec<RowSet>,
}

/// What [`Assembly::solve`] gives: each key's frame, a reading in the order
/// of the parts, and each instance's row with its D4 elements.
struct Solution {
    frames: StableHashMap<Row, Vec<RowSet>>,
    poses: Vec<(Row, Vec<TermId>)>,
}

/// What a `RIGID_DET` form gives the evaluation of its assembly: its key
/// and instance clauses with their paths and labels, and its parts.
struct Assembly<'e, 'p> {
    evaluation: &'e Evaluation<'p>,
    form: &'e NodePath,
    key: Option<(&'p Body, NodePath)>,
    key_labels: Vec<LabelId>,
    instance: Option<(&'p Body, NodePath)>,
    instance_labels: Vec<LabelId>,
    parts: Vec<Part<'p>>,
}

impl<'e, 'p> Assembly<'e, 'p> {
    /// The assembly of `rigid`, the `RIGID_DET` form at `form`.
    fn of(evaluation: &'e Evaluation<'p>, form: &'e NodePath, rigid: &'p RigidDet) -> Outcome<Self> {
        let fault = |message: String| fault(form, message);
        let types_of = ir::label_types(evaluation.program, form);
        let types = types_of;
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
            let own = labels.iter().zip(&types).map(|(&label, ty)| *ty == ValueType::Ident && types_of.is_own_ident(label)).collect();
            parts.push(Part { atom, path: form.child(index), labels, types, own });
        }
        Ok(Assembly { evaluation, form, key, key_labels, instance, instance_labels, parts })
    }

    fn fault(&self, message: String) -> RunFault {
        fault(self.form, message)
    }

    /// The value of the assembly's output where `budget` reached `bound`.
    fn stopped(&self, bound: super::ReachedBound) -> RelationValue {
        RelationValue::Stopped(Stop { bound, form: self.form.clone() })
    }

    /// The count of key columns of the assembly's output rows: the key
    /// clause's columns, and none where the form has no key clause.
    fn key_width(&self) -> usize {
        if self.key.is_some() { self.key_labels.len() } else { 0 }
    }

    /// The index among the parts of the one part whose output's path
    /// begins with `step`.
    fn part(&self, step: &OutputStep) -> Outcome<usize> {
        let mut found = self.parts.iter().enumerate().filter(|(_, part)| self.steps(part).first() == Some(step)).map(|(index, _)| index);
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

    /// The instances of the assembly, each with its reading of each part,
    /// in the order of the parts, or the value of a body of the form that
    /// is `undefined` or stopped.
    fn readings(&self, bodies: &FormBodies<'_>, example: Option<Example>) -> Outcome<Result<Vec<Instance>, RelationValue>> {
        let prefix: Vec<LabelId> = self.key_labels.iter().chain(&self.instance_labels).copied().collect();
        let clauses: Vec<&(&Body, NodePath)> = self.key.iter().chain(&self.instance).collect();
        let rows = match clauses.is_empty() {
            true => vec![Row::default()],
            false => match self.rows(bodies, &clauses, None, &prefix, example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            },
        };
        let mut by_part: Vec<StableHashMap<Row, RowSet>> = Vec::with_capacity(self.parts.len());
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
            by_part.push(by_instance);
        }
        Ok(Ok(rows
            .into_iter()
            .map(|row| {
                let reading = self.parts.iter().zip(&mut by_part).map(|(part, by_instance)| by_instance.remove(&row).unwrap_or_else(|| RowSet::empty(part.labels.len() as u16))).collect();
                Instance { row, reading }
            })
            .collect()))
    }

    /// The order by content of two readings of the assembly: part by part,
    /// in the order of the parts, each part's rows in the order of
    /// [`crate::terms::set_order`].
    fn reading_order(&self, a: &[RowSet], b: &[RowSet], table: &crate::terms::InternTable) -> Ordering {
        for ((part, a), b) in self.parts.iter().zip(a).zip(b) {
            let order = crate::terms::set_order(&part.types, a.rows(), b.rows(), table);
            if order.is_ne() {
                return order;
            }
        }
        Ordering::Equal
    }

    /// Whether some column of some part holds the assembly's own Idents.
    fn has_own_idents(&self) -> bool {
        self.parts.iter().any(|part| part.own.contains(&true))
    }

    /// Whether the element `g` takes `frame`, the rows of each part in the
    /// order of the parts, onto `observed` at every part at once: the image
    /// of the frame under `g` is `observed`, up to one one-to-one renaming
    /// of the assembly's own Idents, the same at every part.
    fn takes_onto(&self, geometry: &Geometry, g: D4Element, frame: &[RowSet], observed: &[RowSet]) -> bool {
        if !self.has_own_idents() {
            return self.parts.iter().zip(frame).zip(observed).all(|((part, frame), observed)| {
                let images: StableHashSet<Row> = frame.rows().map(|values| image(geometry, g, values, &part.types).collect()).collect();
                images.len() == observed.len() && observed.rows().all(|values| images.contains(values))
            });
        }
        let mut images: IdentRowsBuilder<u32, TermId> = IdentRowsBuilder::default();
        let mut readings: IdentRowsBuilder<u32, TermId> = IdentRowsBuilder::default();
        for (index, part) in self.parts.iter().enumerate() {
            let split = |values: &[TermId], builder: &mut IdentRowsBuilder<u32, TermId>| {
                let leaves = values.iter().zip(&part.own).map(|(&value, &own)| (!own).then_some(value.encoding())).collect();
                let idents = values.iter().zip(&part.own).filter(|(_, own)| **own).map(|(&value, _)| value);
                builder.push(index, leaves, idents);
            };
            for values in frame[index].rows() {
                let moved: Vec<TermId> = image(geometry, g, values, &part.types).collect();
                split(&moved, &mut images);
            }
            for values in observed[index].rows() {
                split(values, &mut readings);
            }
        }
        renaming_between(&images.finish(), &readings.finish())
    }

    /// The assembly's frames and poses: at each key, the reading of the
    /// instance at that key whose reading is least by
    /// [`Assembly::reading_order`], and for each instance, the D4 elements
    /// that take its key's frame onto its reading at every part at once,
    /// as [`Assembly::takes_onto`] gives; or `undefined`, where some instance has no such element, or the
    /// value of a body of the form that is `undefined` or stopped, or of a
    /// stop.
    fn solve(&self, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<Solution, RelationValue>> {
        let instances = match self.readings(bodies, example)? {
            Ok(instances) => instances,
            Err(value) => return Ok(Err(value)),
        };
        let mut frames: StableHashMap<Row, Vec<RowSet>> = StableHashMap::default();
        {
            let table = self.evaluation.session.intern.read().expect("an intern table that no panic poisoned");
            let mut least: StableHashMap<&[TermId], &Instance> = StableHashMap::default();
            for instance in &instances {
                let key = &instance.row[..self.key_labels.len()];
                let frame = least.entry(key).or_insert(instance);
                if self.reading_order(&instance.reading, &frame.reading, &table).is_lt() {
                    *frame = instance;
                }
            }
            frames.extend(least.into_iter().map(|(key, instance)| (key.into(), instance.reading.clone())));
        }
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let mut poses = Vec::with_capacity(instances.len());
        for instance in instances {
            if let Err(bound) = budget.charge_work(elements.len() as u64) {
                return Ok(Err(self.stopped(bound)));
            }
            let frame = &frames[&instance.row[..self.key_labels.len()]];
            let mut found = Vec::new();
            for &element in elements {
                if self.has_own_idents() {
                    let searched = frame.iter().chain(&instance.reading).map(|rows| rows.len() as u64).sum();
                    if let Err(bound) = budget.charge_work(searched) {
                        return Ok(Err(self.stopped(bound)));
                    }
                }
                if self.takes_onto(geometry, geometry.element(element), frame, &instance.reading) {
                    found.push(element);
                }
            }
            if found.is_empty() {
                return Ok(Err(RelationValue::Undefined));
            }
            poses.push((instance.row, found));
        }
        Ok(Ok(Solution { frames, poses }))
    }

    /// The rows of `&marker.<part>`: at each key, at each D4 element, the
    /// image under it of the key's frame at the part, or the value of
    /// [`Assembly::solve`] where it gives no solution.
    fn placements(&self, part: usize, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<RowSet, RelationValue>> {
        let solution = match self.solve(bodies, example, budget)? {
            Ok(solution) => solution,
            Err(value) => return Ok(Err(value)),
        };
        let part_types = &self.parts[part].types;
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let mut rows = RowSet::empty((self.key_width() + 1 + part_types.len()) as u16);
        for (key, frame) in &solution.frames {
            let reading = &frame[part];
            if let Err(bound) = budget.charge_rows((elements.len() * reading.len()) as u64) {
                return Ok(Err(self.stopped(bound)));
            }
            for &element in elements {
                let g = geometry.element(element);
                for values in reading.rows() {
                    let mut row = key.to_vec();
                    row.push(element);
                    row.extend(image(geometry, g, values, part_types));
                    rows.insert(row.into());
                }
            }
        }
        Ok(Ok(rows))
    }

    /// The rows of `&marker.pose`: for each instance, each D4 element that
    /// takes its key's frame onto the instance's reading at every part at
    /// once, as [`Assembly::takes_onto`] gives, or the value of [`Assembly::solve`] where it gives no
    /// solution.
    fn poses(&self, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<RowSet, RelationValue>> {
        let solution = match self.solve(bodies, example, budget)? {
            Ok(solution) => solution,
            Err(value) => return Ok(Err(value)),
        };
        let mut rows = RowSet::empty((self.key_width() + self.instance_labels.len() + 1) as u16);
        for (instance, elements) in &solution.poses {
            let (key, at) = instance.split_at(self.key_labels.len());
            for &element in elements {
                let mut row = key.to_vec();
                row.extend_from_slice(at);
                row.push(element);
                rows.insert(row.into());
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
        let clause = ir::compile_safe(self.evaluation.program, self.form, conjuncts, columns)
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
pub fn image<'v>(geometry: &'v Geometry, g: D4Element, values: &'v [TermId], types: &'v [ValueType]) -> impl Iterator<Item = TermId> + 'v {
    values.iter().zip(types).map(move |(&value, ty)| match ty {
        ValueType::Record(_) => unreachable!("a label's type is no record"),
        ValueType::Box => Term::Box(apply(g, Term::decode_box(value))).encode().expect("a Box's margins, moved among its edges, each fit a signed byte"),
        _ if ty.moved_by_d4() => geometry.under(g, value),
        _ => value,
    })
}
