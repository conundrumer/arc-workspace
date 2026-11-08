//! A `RIGID_DET` assembly: its outputs `&marker.<part>` and
//! `&marker.pose`, as `docs/arclog/rigid.md#semantics` gives, computed from
//! its instances' readings by the method of
//! `docs/engine/rigid.md#implementation`.
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
//! Where a key column holds the assembly's own Idents, the renaming also
//! takes the frame's key onto the instance's key, and the instances whose
//! readings and keys are images of one another form one class, which
//! takes the place of a key: its frame is the reading of its instance
//! least by content, its key is that instance's key, and each output
//! holds the class's key. Where two classes hold instances at one key, the
//! assembly has no value.
//!
//! A part's site that holds a bare label of the `instance` clause selects
//! the part's rows at an instance and gives the part no column, so an
//! instance's reading of the part is the part's rows at that instance's
//! row, without those columns.
//!
//! In a form with an `instance` clause, a part with no such site is a frame
//! part. No instance's reading holds it: the elements of each instance are
//! those that take the frame onto the instance's reading of the other parts.
//! The frame holds the frame part's rows. They are the rows of the part's
//! `DET`, other than at the stored records where the part's `DET` has no
//! record, no `assign` and no clause of its own. There they are the image of
//! the record of `&<assembly>.<part>` under the elements that take the
//! records of the other parts onto the frame, which must agree on the image;
//! where none does or they differ, the assembly has no value. In a form with
//! no `instance` clause, a part is a frame part only at those stored records.

pub mod renaming;

use std::cmp::Ordering;
use std::sync::Arc;

use self::renaming::{renaming_between, IdentRowsBuilder};
use super::join::{self, Budget};
use super::ir::{ClauseIr, IrPaths};
use super::{ir, Evaluation, FormBodies, Outcome, RelationValue, RunFault, Stop};
use crate::algebra::boxes::apply;
use crate::algebra::geometry::{D4Element, Geometry};
use crate::check::{AssemblyClause, CheckedProgram};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Atom, Body, Conjunct, LabelId, Node, OutputName, OutputOwner, OutputStep, ParamValue, ProgramRelation, RigidDet, RigidDetName};
use crate::relations::{Row, RowSet};
use crate::resolver::form_columns;
use crate::terms::{Example, Term, TermId};
use crate::types::{FormTypes, ValueType};

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
    let assembly = Assembly::of(evaluation.program, form, rigid)?.with_recorded_parts(bodies);
    let rows = match output {
        OutputStep::Pose => assembly.poses(bodies, example, budget)?,
        step => {
            let part = assembly.part(step)?;
            match assembly.assigned_placements(part, bodies)? {
                Some(rows) => Ok(rows),
                None => assembly.placements(part, bodies, example, budget)?,
            }
        }
    };
    // The content of the assembly: the rows of the table it writes.
    if let Ok(found) = &rows
        && let Err(bound) = budget.charge_content(found.len() as u64)
    {
        return Ok(RelationValue::Stopped(super::Stop { bound, form: form.clone() }));
    }
    Ok(rows.map_or_else(|value| value, |rows| RelationValue::Rows(Arc::new(join::one_part(rows)))))
}

/// The index, among the part's columns in the output at `path` of the form
/// `rigid`, of each column at a label of the `key` clause: the output holds
/// that key column again there.
pub fn part_key_columns(rigid: &RigidDet, path: &[OutputStep]) -> Vec<usize> {
    let Some(key) = &rigid.key else { return Vec::new() };
    let part = rigid.parts.iter().find(|part| form_columns::part_steps(&part.value().relation).is_some_and(|steps| steps.first() == path.first()));
    let labels = part.map_or_else(Vec::new, |part| form_columns::part_labels(rigid, part.value()));
    labels.iter().enumerate().filter(|(_, label)| key.columns.iter().any(|column| column.label == **label)).map(|(at, _)| at).collect()
}

/// The clause that the evaluation joins for the output `step` of the
/// `RIGID_DET` form `rigid` at `form`, with the paths of its nodes: the key
/// and instance bodies, and the atom of the part that `step` begins the path
/// of, or none for [`OutputStep::Pose`]. The error is the fault of the
/// form or of the compile.
pub(crate) fn output_clause(program: &CheckedProgram, form: &NodePath, rigid: &RigidDet, step: &OutputStep) -> Result<(ClauseIr, IrPaths), String> {
    let assembly = Assembly::of(program, form, rigid).map_err(|fault| fault.message.to_string())?;
    let part = match step {
        OutputStep::Pose => None,
        step => Some(&assembly.parts[assembly.part(step).map_err(|fault| fault.message.to_string())?]),
    };
    let (clause, paths) = assembly.clause(part).map_err(|compile| format!("a body of the form does not compile: {compile:?}"))?;
    Ok(((*clause).clone(), (*paths).clone()))
}

/// One part of an assembly: its atom with its path, the labels of its
/// sites that give it a column, in the order of its columns, their types,
/// whether each column holds the assembly's own Idents, and whether it is a
/// frame part.
pub(crate) struct Part<'p> {
    atom: &'p Node<Atom>,
    path: NodePath,
    labels: Vec<LabelId>,
    types: Vec<ValueType>,
    own: Vec<bool>,
    frame: bool,
}

impl Part<'_> {
    /// The part's rows where it has none.
    fn no_rows(&self) -> RowSet {
        RowSet::empty(self.labels.len() as u16)
    }
}

/// An instance of an assembly: its row of the key and instance clauses,
/// and its reading, its rows of each part in the order of the parts, none
/// for a frame part.
struct Instance {
    row: Row,
    reading: Vec<RowSet>,
}

impl Instance {
    /// The instance's key, the first `key_width` columns of its row, and
    /// its reading.
    fn view(&self, key_width: usize) -> View<'_> {
        View { key: &self.row[..key_width], parts: &self.reading }
    }
}

/// What [`Assembly::classes`] gives: the key of each instance's class, in
/// the order of the instances, and each class's frame at its key.
struct Classes {
    keys: Vec<Row>,
    frames: StableHashMap<Row, Vec<RowSet>>,
}

/// A key and a reading, the rows of each part in the order of the parts.
struct View<'v> {
    key: &'v [TermId],
    parts: &'v [RowSet],
}

/// What [`Assembly::solve`] gives: each class's frame, a reading in the
/// order of the parts, at the class's key, and, for each instance, its row
/// at its class's key, with its D4 elements.
struct Solution {
    frames: StableHashMap<Row, Vec<RowSet>>,
    poses: Vec<(Row, Vec<TermId>)>,
}

/// What a `RIGID_DET` form gives the evaluation of its assembly: its key
/// and instance clauses with their paths and labels, and its parts.
struct Assembly<'e, 'p> {
    program: &'e CheckedProgram,
    form: &'e NodePath,
    name: &'p RigidDetName,
    key: Option<(&'p Body, NodePath)>,
    key_labels: Vec<LabelId>,
    key_types: Vec<ValueType>,
    key_own: Vec<bool>,
    instance: Option<(&'p Body, NodePath)>,
    instance_labels: Vec<LabelId>,
    parts: Vec<Part<'p>>,
}

impl<'e, 'p> Assembly<'e, 'p> {
    /// The assembly of `rigid`, the `RIGID_DET` form at `form`.
    pub(crate) fn of(program: &'e CheckedProgram, form: &'e NodePath, rigid: &'p RigidDet) -> Outcome<Self> {
        let fault = |message: String| fault(form, message);
        let types_of = ir::label_types(program, form);
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
        let key_types = typed(&key_labels)?;
        let key_own = own_flags(types_of, &key_labels, &key_types);
        let mut parts = Vec::with_capacity(rigid.parts.len());
        for (atom, index) in rigid.parts.iter().zip(clauses..) {
            let labels = form_columns::part_labels(rigid, atom.value());
            if labels.iter().any(|label| instance_labels.contains(label)) {
                return Err(fault("a part's site holds a label of the `instance` clause inside a term of other labels, whose column `docs/arclog/rigid.md#semantics` gives no value in the part's output".into()));
            }
            let types = typed(&labels)?;
            let own = own_flags(types_of, &labels, &types);
            let frame = form_columns::is_frame_part(rigid, atom.value());
            parts.push(Part { atom, path: form.child(index), labels, types, own, frame });
        }
        Ok(Assembly { program, form, name: &rigid.name, key, key_labels, key_types, key_own, instance, instance_labels, parts })
    }

    /// The assembly, where its form has no `instance` clause, with each part
    /// that [`Assembly::frame_record`] gives a record as a frame part.
    fn with_recorded_parts(mut self, bodies: &FormBodies<'_>) -> Self {
        if self.instance.is_none() {
            let recorded: Vec<bool> = self.parts.iter().map(|part| self.frame_record(part, bodies).is_some()).collect();
            for (part, recorded) in self.parts.iter_mut().zip(recorded) {
                part.frame = recorded;
            }
        }
        self
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
    /// begins with `step`. A part that has no output matches no step.
    fn part(&self, step: &OutputStep) -> Outcome<usize> {
        let mut found = self.parts.iter().enumerate().filter(|(_, part)| self.steps(part).is_some_and(|steps| steps.first() == Some(step))).map(|(index, _)| index);
        match (found.next(), found.next()) {
            (Some(part), None) => Ok(part),
            (Some(_), Some(_)) => Err(self.fault(format!("more than one part's output begins with the step {step:?}"))),
            (None, _) => panic!("an output step of a part of the assembly"),
        }
    }

    /// The path after the form's name of `part`'s output, or `None` for a
    /// part that reads a fact or a lib relation, which has no output.
    fn steps(&self, part: &Part<'_>) -> Option<Vec<OutputStep>> {
        form_columns::part_steps(&part.atom.value().relation)
    }

    /// The instances of the assembly, each with its reading of each part,
    /// in the order of the parts, or the value of a body of the form that
    /// is `undefined` or stopped.
    fn readings(&self, bodies: &FormBodies<'_>, example: Option<Example>) -> Outcome<Result<Vec<Instance>, RelationValue>> {
        let prefix = self.columns(None);
        let rows = match self.key.is_none() && self.instance.is_none() {
            true => vec![Row::default()],
            false => match self.rows(bodies, None, example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            },
        };
        let mut by_part: Vec<StableHashMap<Row, RowSet>> = Vec::with_capacity(self.parts.len());
        for part in &self.parts {
            if part.frame {
                by_part.push(StableHashMap::default());
                continue;
            }
            let rows = match self.rows(bodies, Some(part), example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            };
            by_part.push(group_by_key(rows, prefix.len(), part.labels.len()));
        }
        Ok(Ok(rows
            .into_iter()
            .map(|row| {
                let reading = self.parts.iter().zip(&mut by_part).map(|(part, by_instance)| by_instance.remove(&row).unwrap_or_else(|| part.no_rows())).collect();
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

    /// Whether some column of some part that an instance reads, or of the
    /// key, holds the assembly's own Idents.
    fn has_own_idents(&self) -> bool {
        self.key_has_own_idents() || self.parts.iter().any(|part| !part.frame && part.own.contains(&true))
    }

    /// Whether some column of the key holds the assembly's own Idents.
    fn key_has_own_idents(&self) -> bool {
        self.key_own.contains(&true)
    }

    /// Whether the element `g` takes `frame` onto `observed` at every part
    /// at once: the image of the frame's rows of each part under `g` is
    /// `observed`'s, up to one one-to-one renaming of the assembly's own
    /// Idents, the same at every part and at the key, which `g` leaves as
    /// it is.
    fn takes_onto(&self, geometry: &Geometry, g: D4Element, frame: &View<'_>, observed: &View<'_>) -> bool {
        if !self.has_own_idents() {
            return self.parts.iter().zip(frame.parts).zip(observed.parts).all(|((part, frame), observed)| {
                let images: StableHashSet<Row> = frame.rows().filter_map(|values| image(geometry, g, values, &part.types)).collect();
                images.len() == observed.len() && observed.rows().all(|values| images.contains(values))
            });
        }
        let mut images: IdentRowsBuilder<u32, TermId> = IdentRowsBuilder::default();
        let mut readings: IdentRowsBuilder<u32, TermId> = IdentRowsBuilder::default();
        for (index, part) in self.parts.iter().enumerate() {
            for values in frame.parts[index].rows() {
                let Some(moved) = image(geometry, g, values, &part.types) else { continue };
                push_row(&mut images, index, &moved, &part.own);
            }
            for values in observed.parts[index].rows() {
                push_row(&mut readings, index, values, &part.own);
            }
        }
        push_row(&mut images, self.parts.len(), frame.key, &self.key_own);
        push_row(&mut readings, self.parts.len(), observed.key, &self.key_own);
        renaming_between(&images.finish(), &readings.finish())
    }

    /// The classes of the assembly's instances: for each instance, in the
    /// order of `instances`, the key of its class, and for each class key,
    /// the class's frame, the reading of the class's instance least by
    /// [`Assembly::reading_order`], and then by the content of its key.
    ///
    /// Where the key holds no own Idents, a class is the instances at one
    /// key. Where it does, a class is the instances whose key and reading
    /// some D4 element and one renaming take onto those of one instance, as
    /// [`Assembly::takes_onto`] gives; or `undefined`, where two classes
    /// hold instances at one key, or the value of a stop.
    fn classes(&self, instances: &[Instance], bodies: &FormBodies<'_>, budget: &mut Budget<'_>) -> Outcome<Result<Classes, RelationValue>> {
        let key_width = self.key_labels.len();
        let table = bodies.driver.evaluation.session.intern.read().expect("an intern table that no panic poisoned");
        let mut representatives: Vec<&Instance> = Vec::new();
        let mut class_of = vec![0; instances.len()];
        if self.key_has_own_idents() {
            let by_content = |a: &Instance, b: &Instance| {
                self.reading_order(&a.reading, &b.reading, &table).then_with(|| crate::terms::content_order(&self.key_types, &a.row[..key_width], &b.row[..key_width], &table))
            };
            let mut order: Vec<usize> = (0..instances.len()).collect();
            order.sort_by(|&a, &b| by_content(&instances[a], &instances[b]));
            let geometry = Geometry::get();
            let elements = geometry.domain(&ValueType::D4);
            for at in order {
                let instance = &instances[at];
                let observed = instance.view(key_width);
                let mut found = None;
                for (class, representative) in representatives.iter().enumerate() {
                    let frame = representative.view(key_width);
                    if let Err(bound) = self.charge_search(budget, &frame, &observed, elements.len()) {
                        return Ok(Err(self.stopped(bound)));
                    }
                    if elements.iter().any(|&element| self.takes_onto(geometry, geometry.element(element), &frame, &observed)) {
                        found = Some(class);
                        break;
                    }
                }
                class_of[at] = found.unwrap_or_else(|| {
                    representatives.push(instance);
                    representatives.len() - 1
                });
            }
            let mut at_key: StableHashMap<&[TermId], usize> = StableHashMap::default();
            for (instance, &class) in instances.iter().zip(&class_of) {
                if *at_key.entry(&instance.row[..key_width]).or_insert(class) != class {
                    return Ok(Err(RelationValue::Undefined));
                }
            }
        } else {
            let mut class_at: StableHashMap<&[TermId], usize> = StableHashMap::default();
            for (at, instance) in instances.iter().enumerate() {
                let class = *class_at.entry(&instance.row[..key_width]).or_insert_with(|| {
                    representatives.push(instance);
                    representatives.len() - 1
                });
                if self.reading_order(&instance.reading, &representatives[class].reading, &table).is_lt() {
                    representatives[class] = instance;
                }
                class_of[at] = class;
            }
        }
        let keys = class_of.iter().map(|&class| representatives[class].row[..key_width].into()).collect();
        let frames = representatives.iter().map(|representative| (representative.row[..key_width].into(), representative.reading.clone())).collect();
        Ok(Ok(Classes { keys, frames }))
    }

    /// Charges `budget` for the search of the D4 elements that take
    /// `frame` onto `observed`, where `elements` is their count.
    fn charge_search(&self, budget: &mut Budget<'_>, frame: &View<'_>, observed: &View<'_>, elements: usize) -> Result<(), super::ReachedBound> {
        budget.charge_work(elements as u64)?;
        if self.has_own_idents() {
            let searched: u64 = frame.parts.iter().chain(observed.parts).map(|rows| rows.len() as u64).sum();
            budget.charge_work(searched * elements as u64)?;
        }
        Ok(())
    }

    /// The assembly's frames and poses: the frame of each class of
    /// instances, as [`Assembly::classes`] gives them, and for each
    /// instance, the D4 elements that take its class's frame onto its
    /// reading at every part at once, as [`Assembly::takes_onto`] gives; or
    /// `undefined`, where some instance has no such element, or the
    /// value of a body of the form that is `undefined` or stopped, or of a
    /// stop.
    fn solve(&self, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<Solution, RelationValue>> {
        let instances = match self.readings(bodies, example)? {
            Ok(instances) => instances,
            Err(value) => return Ok(Err(value)),
        };
        let Classes { keys, mut frames } = match self.classes(&instances, bodies, budget)? {
            Ok(classes) => classes,
            Err(value) => return Ok(Err(value)),
        };
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let key_width = self.key_labels.len();
        let mut poses = Vec::with_capacity(instances.len());
        for (instance, key) in instances.into_iter().zip(keys) {
            let frame = &frames[&key];
            let (frame, observed) = (View { key: &key, parts: frame }, instance.view(key_width));
            if let Err(bound) = self.charge_search(budget, &frame, &observed, elements.len()) {
                return Ok(Err(self.stopped(bound)));
            }
            let found: Vec<TermId> = elements.iter().copied().filter(|&element| self.takes_onto(geometry, geometry.element(element), &frame, &observed)).collect();
            if found.is_empty() {
                return Ok(Err(RelationValue::Undefined));
            }
            let mut row = key.to_vec();
            row.extend_from_slice(&instance.row[key_width..]);
            poses.push((row.into(), found));
        }
        if let Err(value) = self.place_frame_parts(&mut frames, bodies, example, budget)? {
            return Ok(Err(value));
        }
        Ok(Ok(Solution { frames, poses }))
    }

    /// Sets the rows of each frame part in `frames`, the frame of each class
    /// of instances, which hold none yet: at the class's key, the rows of the
    /// part's `DET`, or, where [`Assembly::frame_record`] gives a record, as
    /// [`Assembly::image_records`] gives them; or the value of a body of the
    /// form that is `undefined` or stopped, or of a stop.
    fn place_frame_parts(&self, frames: &mut StableHashMap<Row, Vec<RowSet>>, bodies: &FormBodies<'_>, example: Option<Example>, budget: &mut Budget<'_>) -> Outcome<Result<(), RelationValue>> {
        let key_width = self.key_width();
        let mut recorded = Vec::new();
        for (index, part) in self.parts.iter().enumerate().filter(|(_, part)| part.frame) {
            if self.frame_record(part, bodies).is_some() {
                recorded.push(index);
                continue;
            }
            let rows = match self.rows(bodies, Some(part), example)? {
                Ok(rows) => rows,
                Err(value) => return Ok(Err(value)),
            };
            let mut by_key = group_by_key(rows, key_width, part.labels.len());
            for (key, frame) in frames.iter_mut() {
                frame[index] = by_key.remove(key).unwrap_or_else(|| part.no_rows());
            }
        }
        if recorded.is_empty() { Ok(Ok(())) } else { self.image_records(&recorded, frames, bodies, budget) }
    }

    /// Sets the rows of the frame parts at `recorded` in `frames`: at each
    /// class's key, the image of the part's record under the D4 elements that
    /// take the records of the parts that an instance reads onto the class's
    /// frame, as [`Assembly::takes_onto`] gives them; or `undefined`, where
    /// some class has no such element, or the elements give a record
    /// different images, or the value of a stop.
    fn image_records(&self, recorded: &[usize], frames: &mut StableHashMap<Row, Vec<RowSet>>, bodies: &FormBodies<'_>, budget: &mut Budget<'_>) -> Outcome<Result<(), RelationValue>> {
        let key_width = self.key_width();
        let evaluation = bodies.driver.evaluation;
        let mut records: Vec<StableHashMap<Row, RowSet>> = Vec::with_capacity(self.parts.len());
        for (index, part) in self.parts.iter().enumerate() {
            if part.frame && !recorded.contains(&index) {
                records.push(StableHashMap::default());
                continue;
            }
            let Some(record) = self.record_of(part, bodies) else {
                return Err(self.fault(format!("the stored records hold no record of the part {:?}, which the record of a frame part is imaged by", part.atom.value().relation)));
            };
            let types: Vec<ValueType> = self.key_types.iter().chain(&part.types).cloned().collect();
            let rows = {
                let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
                crate::terms::encode_param_value(record, &types, evaluation.registry, &mut table)
                    .map_err(|error| self.fault(format!("the record of a part does not read at the key and the part's columns: {error:?}")))?
            };
            records.push(group_by_key(rows, key_width, part.labels.len()));
        }
        let geometry = Geometry::get();
        let elements = geometry.domain(&ValueType::D4);
        let mut undefined = false;
        for (key, frame) in frames.iter_mut() {
            let others: Vec<RowSet> = self.parts.iter().zip(&records).map(|(part, rows)| rows.get(key).filter(|_| !part.frame).cloned().unwrap_or_else(|| part.no_rows())).collect();
            let (from, onto) = (View { key, parts: &others }, View { key, parts: frame });
            if let Err(bound) = self.charge_search(budget, &from, &onto, elements.len()) {
                return Ok(Err(self.stopped(bound)));
            }
            let found: Vec<D4Element> = elements.iter().map(|&element| geometry.element(element)).filter(|&g| self.takes_onto(geometry, g, &from, &onto)).collect();
            undefined |= found.is_empty();
            for &index in recorded {
                let part = &self.parts[index];
                let mut agreed: Option<StableHashSet<Row>> = None;
                for &g in &found {
                    let images: StableHashSet<Row> = records[index].get(key).into_iter().flat_map(RowSet::rows).filter_map(|values| image(geometry, g, values, &part.types)).collect();
                    undefined |= agreed.get_or_insert_with(|| images.clone()) != &images;
                }
                let mut rows = part.no_rows();
                for row in agreed.unwrap_or_default() {
                    rows.insert(row);
                }
                frame[index] = rows;
            }
        }
        Ok(if undefined { Err(RelationValue::Undefined) } else { Ok(()) })
    }

    /// The stored record of `&<assembly>.<part>` that gives the frame part
    /// `part` its rows: the record, where the stored records leave the part's
    /// `DET` no rows of its own, as `Driver::lacks_stored_rows` gives, and
    /// hold the record. At values determined from the evidence, none.
    fn frame_record<'b>(&self, part: &Part<'_>, bodies: &'b FormBodies<'_>) -> Option<&'b ParamValue> {
        if bodies.driver.lacks_stored_rows(&part.atom.value().relation) { self.record_of(part, bodies) } else { None }
    }

    /// The stored record of `&<assembly>.<part>`, or `None` where the
    /// records hold none, or the part has no output.
    fn record_of<'b>(&self, part: &Part<'_>, bodies: &'b FormBodies<'_>) -> Option<&'b ParamValue> {
        let name = OutputName { of: OutputOwner::RigidDet(self.name.clone()), path: self.steps(part)?.into() };
        bodies.driver.evaluation.parameters.recorded(&ProgramRelation::Output(name))
    }

    /// The rows of `&marker.<part>` that a witness's `assign` of that output
    /// gives: the rows as the output holds them, the key's columns, the pose
    /// and the part's columns. `None` where the witness gives none. The
    /// instances take no part in them.
    fn assigned_placements(&self, part: usize, bodies: &FormBodies<'_>) -> Outcome<Option<RowSet>> {
        let part = &self.parts[part];
        let Some(steps) = self.steps(part) else { return Ok(None) };
        let name = OutputName { of: OutputOwner::RigidDet(self.name.clone()), path: steps.into() };
        let evaluation = bodies.driver.evaluation;
        let Some(assigned) = evaluation.parameters.assigned(&ProgramRelation::Output(name)) else { return Ok(None) };
        let types: Vec<ValueType> = self.key_types.iter().cloned().chain(std::iter::once(ValueType::D4)).chain(part.types.iter().cloned()).collect();
        let rows = {
            let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
            crate::terms::encode_param_value(assigned, &types, evaluation.registry, &mut table)
                .map_err(|error| self.fault(format!("the `assign` of a part does not read at the key, the pose and the part's columns: {error:?}")))?
        };
        let mut set = RowSet::empty(types.len() as u16);
        for row in rows {
            set.insert(row);
        }
        Ok(Some(set))
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
            if let Err(bound) = budget.charge_rows_of((elements.len() * reading.len()) as u64, usize::from(rows.arity())) {
                return Ok(Err(self.stopped(bound)));
            }
            for &element in elements {
                let g = geometry.element(element);
                for values in reading.rows() {
                    let Some(moved) = image(geometry, g, values, part_types) else { continue };
                    let mut row = key.to_vec();
                    row.push(element);
                    row.extend_from_slice(&moved);
                    rows.insert(row.into());
                }
            }
        }
        Ok(Ok(rows))
    }

    /// The rows of `&marker.pose`: for each instance, at its class's key,
    /// each D4 element that takes its class's frame onto the instance's reading at every part at
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

    /// The columns of the clause that joins the key and instance bodies with
    /// the atom of `part` where it is given: the key's labels, the
    /// instance's, and the part's. A frame part's clause leaves out the
    /// instance body and its labels.
    fn columns(&self, part: Option<&Part<'_>>) -> Vec<LabelId> {
        let instance: &[LabelId] = if part.is_some_and(|part| part.frame) { &[] } else { &self.instance_labels };
        self.key_labels.iter().chain(instance).chain(part.into_iter().flat_map(|part| &part.labels)).copied().collect()
    }

    /// The clause that joins the key and instance bodies with the atom of
    /// `part` where it is given, at [`Self::columns`], with the paths of its
    /// nodes: what the form's output reads, and its column flows read. The
    /// program compiles it on the first ask for the form and the part, and
    /// keeps the result, a compile fault included.
    pub(crate) fn clause(&self, part: Option<&Part<'_>>) -> Result<AssemblyClause, ir::CompileFault> {
        self.program.assembly_clause(self.form, part.map(|part| &part.path), || self.compile_clause(part))
    }

    /// What [`Self::clause`] keeps: the compile of the clause of `part`.
    fn compile_clause(&self, part: Option<&Part<'_>>) -> Result<(ClauseIr, IrPaths), ir::CompileFault> {
        let atom = part.map(|part| (Conjunct::Atom(part.atom.clone()), part.path.clone()));
        let conjuncts = self
            .key
            .iter()
            .chain(self.instance.iter().filter(|_| !part.is_some_and(|part| part.frame)))
            .flat_map(|(body, path)| body.conjuncts.iter().zip(0u32..).map(move |(conjunct, index)| (conjunct, path.child(index))))
            .chain(atom.iter().map(|(conjunct, path)| (conjunct, path.clone())))
            .collect();
        ir::compile_safe(self.program, self.form, conjuncts, &self.columns(part))
    }

    /// The rows of [`Self::clause`] of `part`, or the value of the join
    /// where it is `undefined` or stopped.
    fn rows(&self, bodies: &FormBodies<'_>, part: Option<&Part<'_>>, example: Option<Example>) -> Outcome<Result<Vec<Row>, RelationValue>> {
        let columns = self.columns(part);
        let (clause, _) = self.clause(part).map_err(|compile| self.fault(format!("a body of the form does not compile: {compile:?}")))?;
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

/// `rows` grouped by their first `key_width` columns: for each key, the
/// rest of the rows that begin with it, which have `arity` columns.
fn group_by_key(rows: impl IntoIterator<Item = Row>, key_width: usize, arity: usize) -> StableHashMap<Row, RowSet> {
    let mut groups: StableHashMap<Row, RowSet> = StableHashMap::default();
    for row in rows {
        let (key, values) = row.split_at(key_width);
        groups.entry(key.into()).or_insert_with(|| RowSet::empty(arity as u16)).insert(values.into());
    }
    groups
}

/// The fault `message` at the form at `form`.
fn fault(form: &NodePath, message: String) -> RunFault {
    RunFault { message: message.into(), form: form.clone() }
}

/// Adds to `builder` the row `values` of the relation at `relation`: its
/// leaves, with each own Ident's place left empty, and its own Idents.
fn push_row(builder: &mut IdentRowsBuilder<u32, TermId>, relation: usize, values: &[TermId], own: &[bool]) {
    let leaves = values.iter().zip(own).map(|(&value, &own)| (!own).then_some(value.encoding())).collect();
    builder.push(relation, leaves, values.iter().zip(own).filter(|(_, own)| **own).map(|(&value, _)| value));
}

/// Whether each of `labels`, whose types are `types`, is a column of the
/// assembly's own Idents.
fn own_flags(types_of: &FormTypes, labels: &[LabelId], types: &[ValueType]) -> Vec<bool> {
    labels.iter().zip(types).map(|(&label, ty)| matches!(ty, ValueType::Ident(_)) && types_of.is_own_ident(label)).collect()
}

/// The type of `label`, or the fault of a label with none.
fn label_type(types: &FormTypes, label: LabelId) -> Result<ValueType, String> {
    types.label(label).cloned().ok_or_else(|| format!("the label {label:?} has no type"))
}

/// The image under `g` of `values`, whose columns take `types`, each value
/// acted on by its type, as `docs/arclog/rigid.md#semantics` gives, or `None`
/// where a value of an orientation type has no image, and so the row has none.
pub fn image(geometry: &Geometry, g: D4Element, values: &[TermId], types: &[ValueType]) -> Option<Row> {
    values.iter().zip(types).map(|(&value, ty)| match ty {
        ValueType::Record(_) => unreachable!("a label's type is no record"),
        ty if ty.is_box() => Some(Term::Box(apply(g, Term::decode_box(value))).encode().expect("a Box's margins, moved among its edges, each fit a signed byte")),
        _ if ty.moved_by_d4() => geometry.try_under(g, value),
        _ => Some(value),
    }).collect()
}
