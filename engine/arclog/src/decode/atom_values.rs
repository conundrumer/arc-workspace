//! The rows of each of many atoms joined to the body in progress at a state of
//! a decode, with no program made for any of them.
//!
//! An atom that reads one part of the body's rows reads it through the columns
//! at its sites alone. The rows of the part with equal values at those columns
//! form a group, and what the atom gives at a group holds for each row of it.
//! So the atom costs one read of its relation for each group, and no row of its
//! table is made until a caller asks for the rows of a table it has not seen.
//! A table's hash comes from the groups: it needs no rows.

use std::cell::OnceCell;
use std::rc::Rc;
use std::sync::Arc;

use super::interface::{relation_dets, SubBody};
use super::{Assigned, Decoder};
use crate::eval::ir::{Argument, Arguments, AtomSource, ClauseIr, Filter, IrNode, LibAtom, RelationAtom, Variable, VariableInfo};
use crate::eval::join::{self, Budget, JoinInputs, NodeInput};
use crate::eval::{examples, plan};
use crate::eval::{Evaluation, Limits, Outcome, ParameterValues, ReachedBound, RelationValue, TableWork};
use crate::hash::{StableHash, StableHashMap};
use crate::program::{FactRelation, ProgramRelation, RelationRef};
use crate::relations::{hash_plus, hash_times, row_hash_at, rows_hash_of, value_hash, ColumnIndex, ColumnOrder, Index, IndexNode, Relation, RelationPart, RowSet};
use crate::resolver::DependencyKind;
use crate::stream::{Control, Token};
use crate::terms::{Example, TermId};
use crate::types::{GraphRelation, ValueType};

/// The body's rows at each assignment of each example, each part of them held
/// as a relation of its own, so that its indexes serve each atom.
pub struct BaseRows {
    /// The labels of the body's columns, in order, and their types.
    pub columns: Vec<(crate::program::LabelId, ValueType)>,
    /// The `DET`s of the body's assignments.
    dets: Vec<ProgramRelation>,
    /// For each example, at each assignment: the assignment and the body's value.
    examples: Vec<(Option<Example>, Outcome<Assigned<HeldBase>>)>,
    /// Whether the body is evaluated once for the task.
    task_wide: bool,
    /// The labels that stand in the body at no column, such as in a `NOT`.
    other_labels: Vec<u32>,
}

/// The value of a body at one assignment of one example.
struct HeldBase {
    value: RelationValue,
    /// One relation for each part of the value's rows.
    parts: Vec<Arc<Relation>>,
}

/// One candidate atom as the join reads it.
struct AtomPlan {
    negated: bool,
    /// The token that opens the atom.
    relation: u32,
    source: PlanSource,
    /// The column of the relation and what stands at it, for each site.
    sites: Vec<(ColumnIndex, PlanArgument)>,
    /// The type of each label the atom makes.
    made: Vec<ValueType>,
    /// The type of each column of the body after the atom, in order.
    types: Vec<ValueType>,
    /// The variables of a clause of the body's columns and the labels the atom makes.
    variables: Box<[VariableInfo]>,
}

#[derive(Clone)]
enum PlanSource {
    Lib(crate::registry::LibName),
    Fact(FactRelation),
    Relation(GraphRelation, u32),
}

#[derive(Clone, Copy)]
enum PlanArgument {
    Column(u16),
    Made(u16),
    Zero,
}

/// The most labels that an atom makes where the join reads it one group at a time.
const MADE_LABELS: usize = 32;

/// The most bytes of rows of lib relations that the atoms of one call share.
const READ_BYTES: usize = 1 << 29;

/// What is known of a relation that an atom opens.
#[derive(Clone)]
struct OpenedRelation {
    reference: RelationRef,
    columns: Arc<[crate::program::ColumnName]>,
    source: PlanSource,
    /// The place among the relation's rows of each column of `columns`, where
    /// it is not the column's own place.
    places: Option<Vec<u16>>,
}

/// What the join gives for one atom.
pub enum AtomRows {
    /// The table of the atom.
    Rows(JoinedAtom),
    /// The body with the atom is no body that a program holds, so it has no table.
    NoTable,
    /// The atom's work passed the cap.
    OverCap,
    /// The join does not read the atom. A program made for it does.
    ByProgram,
}

/// The table of one atom: the types of its columns, and for each example, at
/// each assignment, its value, whose rows are made on a call of [`JoinedAtom::table`].
pub struct JoinedAtom {
    types: Vec<ValueType>,
    examples: Vec<(Option<Example>, Outcome<Assigned<HeldValue>>)>,
}

/// The value of an atom's table at one assignment of one example.
enum HeldValue {
    Whole(RelationValue),
    Grouped(GroupedValue),
}

/// The rows of a body with the rows of one part kept or extended by what an
/// atom gives at each group of them.
struct GroupedValue {
    rows: Arc<Relation>,
    part: usize,
    groups: Rc<Groups>,
    result: GroupResult,
    /// Whether the atom is negated, so that a row stays where the atom does not hold.
    negated: bool,
    /// The hashes and the order of the rows of the part.
    hashes: Rc<PartHashes>,
    /// The columns of the value.
    arity: u16,
    /// The value's rows hash ([`Relation::rows_hash`]).
    hash: StableHash,
}

/// What an atom gives at each group.
enum GroupResult {
    /// Whether the atom holds.
    Holds(Rc<Bits>),
    /// The values of the labels that the atom makes.
    Makes(Made),
}

/// For each group, the rows of the values of the labels an atom makes.
struct Made {
    /// The labels the atom makes.
    width: usize,
    /// The first row of each group, and the end of the last.
    starts: Vec<u32>,
    values: Vec<TermId>,
}

impl Made {
    fn at(&self, group: usize) -> &[TermId] {
        &self.values[self.starts[group] as usize * self.width..self.starts[group + 1] as usize * self.width]
    }
}

/// A set of bits.
struct Bits(Box<[u64]>);

impl Bits {
    fn new(count: usize) -> Self {
        Bits(vec![0; count.div_ceil(64)].into())
    }

    fn set(&mut self, at: usize) {
        self.0[at / 64] |= 1 << (at % 64);
    }

    fn get(&self, at: usize) -> bool {
        self.0[at / 64] & (1 << (at % 64)) != 0
    }
}

/// The rows of a part of a body's rows, grouped by their values at some of its columns.
struct Groups {
    /// The places of those columns in the part's rows, ascending.
    places: Box<[u16]>,
    /// The values of each group at those places, group after group.
    values: Vec<TermId>,
    /// The group of each list of values.
    of_values: StableHashMap<Box<[TermId]>, u32>,
    /// The count of rows of each group.
    rows: Vec<u32>,
    /// The sum of the hashes of the rows of each group.
    sums: Vec<u64>,
    /// The group of each row of the part, made on the first read.
    of_row: OnceCell<Vec<u32>>,
}

impl Groups {
    fn of(part: &RelationPart, hashes: &[u64], places: Box<[u16]>) -> Self {
        let mut groups = Groups { values: Vec::new(), of_values: StableHashMap::default(), rows: Vec::new(), sums: Vec::new(), of_row: OnceCell::new(), places };
        let mut key: Vec<TermId> = Vec::with_capacity(groups.places.len());
        for (row, &hash) in part.rows.rows().zip(hashes) {
            key.clear();
            key.extend(groups.places.iter().map(|&place| row[usize::from(place)]));
            let group = match groups.of_values.get(&key[..]) {
                Some(&group) => group as usize,
                None => {
                    let group = groups.rows.len();
                    groups.of_values.insert(key.as_slice().into(), group as u32);
                    groups.values.extend_from_slice(&key);
                    groups.rows.push(0);
                    groups.sums.push(0);
                    group
                }
            };
            groups.rows[group] += 1;
            groups.sums[group] = hash_plus(groups.sums[group], hash);
        }
        groups
    }

    fn count(&self) -> usize {
        self.rows.len()
    }

    fn values_at(&self, group: usize) -> &[TermId] {
        let width = self.places.len();
        &self.values[group * width..(group + 1) * width]
    }

    /// The group of each row of `part`.
    fn of_row(&self, part: &RelationPart) -> &[u32] {
        self.of_row.get_or_init(|| {
            let mut key = Vec::with_capacity(self.places.len());
            part.rows.rows().map(|row| {
                key.clear();
                key.extend(self.places.iter().map(|&place| row[usize::from(place)]));
                self.of_values[&key[..]]
            }).collect()
        })
    }
}

/// The hash of each row of a part of a body's rows, and their sum.
struct PartHashes {
    rows: Vec<u64>,
    sum: u64,
    /// The rows' numbers in the order of their values, made on the first read.
    order: OnceCell<Vec<u32>>,
}

impl PartHashes {
    /// The numbers of the rows of `part` in the order of the cells of a table,
    /// whose columns have the types `types`. A reader that sorts the rows finds
    /// them sorted, and the rows that an atom keeps stay in this order.
    fn order(&self, part: &RelationPart, types: &[ValueType]) -> &[u32] {
        self.order.get_or_init(|| {
            let mut places: Vec<usize> = (0..part.columns.len()).collect();
            places.sort_unstable_by_key(|&place| part.columns[place].0);
            let boxes: Vec<bool> = places.iter().map(|&place| types[usize::from(part.columns[place].0)].is_box()).collect();
            let mut order: Vec<u32> = (0..part.rows.len() as u32).collect();
            order.sort_unstable_by(|&a, &b| {
                let values = |number: u32| {
                    let row = part.rows.row(number as usize);
                    places.iter().zip(&boxes).map(move |(&place, &is_box)| cell_key(row[place], is_box))
                };
                values(a).cmp(values(b))
            });
            order
        })
    }
}

/// A key that orders the values of a column as a table's cells order them: by
/// its margins, in the order of the cells, for a column of Boxes, and by its bits
/// as a signed number for any other.
fn cell_key(value: TermId, is_box: bool) -> i64 {
    if is_box {
        let margins = crate::terms::Term::decode_box(value);
        [margins.top, margins.bottom, margins.left, margins.right].into_iter().fold(0i64, |key, margin| (key << 8) | i64::from(margin + 128))
    } else {
        i64::from(value.encoding() as i32)
    }
}

/// Adds to `made` the rows of `found`, each `width` values, in the order of the
/// cells of a table, each once, and ends the group's rows.
fn end_group(made: &mut Made, found: &[TermId], boxes: &[bool]) {
    let width = made.width;
    let mut rows: Vec<&[TermId]> = found.chunks_exact(width).collect();
    rows.sort_unstable_by(|a, b| a.iter().zip(boxes).map(|(&value, &is_box)| cell_key(value, is_box)).cmp(b.iter().zip(boxes).map(|(&value, &is_box)| cell_key(value, is_box))));
    rows.dedup();
    rows.iter().for_each(|row| made.values.extend_from_slice(row));
    made.starts.push((made.values.len() / width) as u32);
}

/// An atom over the groups that it reads: its relation, the column of each site
/// that no label of the atom's own fills, with the place among a group's values of
/// what stands there, the example, the assignment, the part and the places of the
/// groups.
type HoldsKey = (u32, Box<[(u16, u16)]>, usize, usize, usize, Box<[u16]>);

/// What the atoms of one call share.
#[derive(Default)]
struct BatchMemo {
    /// The rows of a relation that atoms read, by the token that opens it, at each assignment of each example.
    read: StableHashMap<(u32, usize, usize), Option<Arc<Relation>>>,
    /// The hashes of each part of the base, by example, assignment and part.
    hashes: StableHashMap<(usize, usize, usize), Rc<PartHashes>>,
    /// The groups of each part, by the places they read.
    groups: StableHashMap<(usize, usize, usize, Box<[u16]>), Rc<Groups>>,
    /// Whether an atom with no label of its own holds at each group, for an atom and the `NOT` of it.
    holds: StableHashMap<HoldsKey, Rc<Bits>>,
    /// The rows of a lib relation at each group, by the sites that the groups fill, which the atoms that differ in the sites of their own labels share.
    reads: StableHashMap<HoldsKey, Rc<LibRead>>,
    /// The bytes that `reads` holds.
    read_bytes: usize,
}

/// The rows of a lib relation at each group of a part, each row its value at each column of the relation.
struct LibRead {
    width: usize,
    /// The first row of each group, and the end of the last.
    starts: Vec<u32>,
    values: Vec<TermId>,
}

impl LibRead {
    fn at(&self, group: usize) -> &[TermId] {
        &self.values[self.starts[group] as usize * self.width..self.starts[group + 1] as usize * self.width]
    }
}

/// What stands at a level of an index that an atom walks.
#[derive(Clone, Copy)]
enum Level {
    /// A value that the group holds at this place of its values.
    Group(u16),
    Term(TermId),
    Made(u16),
}

impl JoinedAtom {
    /// A hash of the types of the table's columns and of its value at each
    /// assignment of each example, which reads no row.
    pub fn key(&self) -> u128 {
        use std::hash::{Hash, Hasher};
        let mut hasher = crate::hash::StableHasher::new();
        self.types.hash(&mut hasher);
        for (example, value) in &self.examples {
            example.hash(&mut hasher);
            match value {
                Err(fault) => fault.message.hash(&mut hasher),
                Ok(assigned) => {
                    assigned.stop.as_ref().map(|stop| format!("{:?}", stop.bound)).hash(&mut hasher);
                    for (_, value) in &assigned.at {
                        hasher.write_usize(1);
                        match value {
                            HeldValue::Grouped(grouped) => hasher.write_u128(grouped.hash.0),
                            HeldValue::Whole(RelationValue::Rows(rows)) => hasher.write_u128(rows.rows_hash().0),
                            HeldValue::Whole(RelationValue::Undefined) => hasher.write_u8(1),
                            HeldValue::Whole(RelationValue::Stopped(stop)) => format!("{:?}", stop.bound).hash(&mut hasher),
                        }
                    }
                }
            }
        }
        hasher.finish128().0
    }

    /// The types of the table's columns, and for each example, at each
    /// assignment, the value.
    pub fn table(self) -> (Vec<ValueType>, Vec<(Option<Example>, Outcome<Assigned<Vec<RelationValue>>>)>) {
        let types = self.types;
        let examples = self.examples.into_iter().map(|(example, value)| {
            (example, value.map(|assigned| Assigned {
                at: assigned.at.into_iter().map(|(values, value)| (values, vec![match value {
                    HeldValue::Whole(value) => value,
                    HeldValue::Grouped(grouped) => grouped.value(&types),
                }])).collect(),
                stop: assigned.stop,
            }))
        }).collect();
        (types, examples)
    }
}

impl GroupedValue {
    /// The value, with its rows, whose columns have the types `types`.
    fn value(&self, types: &[ValueType]) -> RelationValue {
        let part = &self.rows.parts()[self.part];
        let mut parts: Vec<RelationPart> = self.rows.parts().iter().enumerate().filter(|(at, _)| *at != self.part).map(|(_, part)| part.clone()).collect();
        let arity = usize::from(part.rows.arity());
        match &self.result {
            GroupResult::Holds(holds) => {
                let stays = |group: usize| holds.get(group) != self.negated;
                if (0..self.groups.count()).all(stays) {
                    return RelationValue::Rows(Arc::clone(&self.rows));
                }
                let mut values = Vec::new();
                if (0..self.groups.count()).any(stays) {
                    let of_row = self.groups.of_row(part);
                    for &number in self.hashes.order(part, types) {
                        if stays(of_row[number as usize] as usize) {
                            values.extend_from_slice(part.rows.row(number as usize));
                        }
                    }
                }
                parts.push(RelationPart { columns: part.columns.clone(), rows: RowSet::of_distinct(arity as u16, values) });
            }
            GroupResult::Makes(made) => {
                let first = self.arity - made.width as u16;
                let columns = part.columns.iter().copied().chain((0..made.width as u16).map(|index| ColumnIndex(first + index))).collect();
                let of_row = self.groups.of_row(part);
                let mut values = Vec::new();
                for &number in self.hashes.order(part, types) {
                    let row = part.rows.row(number as usize);
                    for added in made.at(of_row[number as usize] as usize).chunks_exact(made.width) {
                        values.extend_from_slice(row);
                        values.extend_from_slice(added);
                    }
                }
                parts.push(RelationPart { columns, rows: RowSet::of_distinct((arity + made.width) as u16, values) });
            }
        }
        RelationValue::Rows(Arc::new(Relation::from_parts_hashed(self.arity, parts.into(), self.hash)))
    }
}

impl<'a> Decoder<'a> {
    /// The rows of the body `sub`, none for a body of no conjunct, at each
    /// assignment of each example.
    pub fn base_rows(&self, sub: Option<&SubBody>, columns: Vec<(crate::program::LabelId, ValueType)>, dets: Vec<ProgramRelation>, work: &TableWork) -> BaseRows {
        let Some(sub) = sub else {
            let unit = |example: Option<Example>| (example, Ok(Assigned { at: vec![(Vec::new(), HeldBase { value: RelationValue::Rows(Arc::new(Relation::from_parts(0, Box::new([])))), parts: Vec::new() })], stop: None }));
            let task_wide = self.body_is_task_wide();
            let scope = if task_wide { examples::ExampleScope::TaskWide } else { examples::ExampleScope::PerExample };
            return BaseRows { columns, dets, examples: self.examples_of(scope).into_iter().map(unit).collect(), task_wide, other_labels: Vec::new() };
        };
        let examples = self.examples_of(sub.scope).into_iter().zip(self.values_of(sub, Some(work)).into_vec()).map(|(example, value)| {
            let held = value.map(|assigned| Assigned {
                at: assigned.at.into_iter().map(|(values, value)| {
                    let value = value.0;
                    let parts = match &value {
                        RelationValue::Rows(rows) => rows.parts().iter().map(|part| Arc::new(join::one_part(part.rows.clone()))).collect(),
                        _ => Vec::new(),
                    };
                    (values, HeldBase { value, parts })
                }).collect(),
                stop: assigned.stop,
            });
            (example, held)
        }).collect();
        let mut other_labels = Vec::new();
        if let Some(crate::program::Form::Clause(clause)) = sub.program.program.program.value().forms.last() {
            for conjunct in clause.value().body.value().conjuncts.iter() {
                other_labels.extend(crate::safety::conjunct_label_set(conjunct).into_iter().map(|label| label.0).filter(|label| !columns.iter().any(|(held, _)| held.0 == *label)));
            }
        }
        BaseRows { columns, dets, examples, task_wide: sub.scope == examples::ExampleScope::TaskWide, other_labels }
    }

    /// What is known of the relation that the token `id` opens, none for a
    /// token that opens no atom of a relation the join reads.
    fn opened_relation(&self, sub: Option<&SubBody>, base: &BaseRows, id: u32) -> Option<OpenedRelation> {
        let token = self.vocabulary().token(id)?;
        let opened = self.next_state(token).ok()?.0;
        let (columns, no_site) = opened.open_atom_columns()?;
        if !no_site {
            return None;
        }
        let reference = opened.open_relation()?;
        // A read of a relation can give an `INIT` form a side of its own, and a body of another side has other rows.
        if matches!(token, Token::Fact(_) | Token::Relation(_)) && !self.keeps_side(&opened, base.task_wide) {
            return None;
        }
        let mut places = None;
        let source = match token {
            Token::Lib(name) => {
                // A rule that reads whether two labels stand in one grid reads what only a program tells.
                if self.context.registry.algebra_relation(name)?.rules.iter().any(|rule| !rule.same_frame.is_empty()) {
                    return None;
                }
                PlanSource::Lib(name.clone())
            }
            Token::Fact(fact) => {
                // A body evaluated once for the task reads no fact of one example, and a body of one example no `ex_` fact.
                if (base.task_wide && fact.per_example()) || (!base.task_wide && matches!(fact, FactRelation::ExInput | FactRelation::ExOutput)) {
                    return None;
                }
                PlanSource::Fact(*fact)
            }
            Token::Relation(slot) => {
                let program = &sub?.program;
                let node = program.program.program_read(&reference)?;
                let output = match (&reference, &program.program.graph.nodes[node.0 as usize].kind) {
                    (RelationRef::Output(name), DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_)) => Some(name.path.clone()),
                    _ => None,
                };
                let relation = GraphRelation { node, output };
                if base.task_wide && examples::scope_of(program, &relation) == examples::ExampleScope::PerExample {
                    return None;
                }
                if !program.program.example_columns(relation.node, relation.output.as_deref()).is_empty() {
                    return None;
                }
                if !relation_dets(program, node).iter().all(|det| base.dets.contains(&det.relation)) {
                    return None;
                }
                if relation.output.is_some() {
                    return None;
                }
                let rows = program.program.read_row_paths(node)?;
                places = Some(columns.iter().map(|name| rows.iter().position(|path| matches!(&path[..], [one] if one == name)).and_then(|at| u16::try_from(at).ok())).collect::<Option<Vec<u16>>>()?);
                PlanSource::Relation(relation, *slot)
            }
            _ => return None,
        };
        Some(OpenedRelation { reference, columns, source, places })
    }

    /// How the join reads the atom `tokens`, or what stands in place of it.
    /// `labels` is the count of labels at this state.
    #[allow(clippy::too_many_arguments)]
    fn atom_plan(&self, opened: &OpenedRelation, base: &BaseRows, labels: u32, relation: u32, negated: bool, sites: &[u32], column_type: &dyn Fn(&RelationRef, &crate::program::ColumnName) -> Option<ValueType>) -> Result<AtomPlan, AtomRows> {
        let vocabulary = self.vocabulary();
        let token = |id: &u32| vocabulary.token(*id).expect("an id of the vocabulary");
        let mut types: Vec<ValueType> = base.columns.iter().map(|(_, ty)| ty.clone()).collect();
        let mut made: Vec<ValueType> = Vec::new();
        let mut plan: Vec<(ColumnIndex, PlanArgument)> = Vec::new();
        // The place in `made` of each label that a `*` of this atom makes, and of each label that another part of the form makes.
        let mut fresh: Vec<u16> = Vec::new();
        let mut outside: Vec<(u32, u16)> = Vec::new();
        let mut at = sites.iter();
        while let Some(column) = at.next() {
            let Token::Column(position) = token(column) else { return Err(AtomRows::ByProgram) };
            let name = opened.columns.get(*position as usize).ok_or(AtomRows::ByProgram)?;
            let ty = column_type(&opened.reference, name).ok_or(AtomRows::ByProgram)?;
            let column = match &opened.places {
                Some(places) => ColumnIndex(*places.get(*position as usize).ok_or(AtomRows::ByProgram)?),
                None => ColumnIndex(u16::try_from(*position).map_err(|_| AtomRows::ByProgram)?),
            };
            match token(at.next().ok_or(AtomRows::ByProgram)?) {
                Token::Label(label) if *label >= labels => {
                    let index = *fresh.get((*label - labels) as usize).ok_or(AtomRows::ByProgram)?;
                    let held = &mut made[usize::from(index)];
                    match held.meet(&ty) {
                        crate::types::Meet::Type(met) => *held = met,
                        crate::types::Meet::Empty => return Err(AtomRows::ByProgram),
                    }
                    plan.push((column, PlanArgument::Made(index)));
                }
                Token::Label(label) => {
                    match base.columns.iter().position(|(held, _)| held.0 == *label) {
                        Some(place) => {
                            match types[place].meet(&ty) {
                                crate::types::Meet::Type(met) if !negated => types[place] = met,
                                crate::types::Meet::Type(_) => {}
                                crate::types::Meet::Empty => return Err(AtomRows::ByProgram),
                            }
                            plan.push((column, PlanArgument::Column(place as u16)));
                        }
                        // A label that no conjunct of this body holds: the atom makes it, as a `*` does.
                        None => {
                            if negated || base.other_labels.contains(label) {
                                return Err(AtomRows::ByProgram);
                            }
                            let index = match outside.iter().find(|(held, _)| held == label) {
                                Some(&(_, index)) => {
                                    let held = &mut made[usize::from(index)];
                                    match held.meet(&ty) {
                                        crate::types::Meet::Type(met) => *held = met,
                                        crate::types::Meet::Empty => return Err(AtomRows::ByProgram),
                                    }
                                    index
                                }
                                None => {
                                    let index = made.len() as u16;
                                    outside.push((*label, index));
                                    made.push(ty);
                                    index
                                }
                            };
                            plan.push((column, PlanArgument::Made(index)));
                        }
                    }
                }
                // In a body that a clause reads, a label that a key marks is a label that the body makes.
                Token::Control(Control::Fresh | Control::Key) => {
                    // No check passes a `NOT` atom one of whose sites makes a label.
                    if negated {
                        return Err(AtomRows::NoTable);
                    }
                    fresh.push(made.len() as u16);
                    plan.push((column, PlanArgument::Made(made.len() as u16)));
                    made.push(ty);
                }
                Token::Control(Control::Zero) => plan.push((column, PlanArgument::Zero)),
                _ => return Err(AtomRows::ByProgram),
            }
        }
        self.apply_rules(opened, &plan, &mut types, &mut made, negated).ok_or(AtomRows::ByProgram)?;
        let width = base.columns.len();
        let variables = types[..width].iter().cloned().chain(made.iter().cloned()).map(|ty| VariableInfo { ty }).collect();
        if !negated {
            types.extend(made.iter().cloned());
        }
        Ok(AtomPlan { negated, relation, source: opened.source.clone(), sites: plan, made, types, variables })
    }

    /// Meets the type of each label at a site of a lib relation with what a
    /// type rule of the relation gives its column there; none where the types
    /// have no meet.
    fn apply_rules(&self, opened: &OpenedRelation, sites: &[(ColumnIndex, PlanArgument)], types: &mut [ValueType], made: &mut [ValueType], negated: bool) -> Option<()> {
        let PlanSource::Lib(name) = &opened.source else { return Some(()) };
        let rules = &self.context.registry.algebra_relation(name)?.rules;
        if rules.is_empty() {
            return Some(());
        }
        let argument_at = |column: &crate::program::ColumnName| {
            let position = opened.columns.iter().position(|name| name == column)? as u16;
            sites.iter().find(|(at, _)| at.0 == position).map(|&(_, argument)| argument)
        };
        // A rule reads the types of the labels that the others leave: two rounds reach what one rule gives another.
        for _ in 0..2 {
            for rule in rules.iter() {
                let held = rule.holds(&|column: &crate::program::ColumnName| match argument_at(column)? {
                    PlanArgument::Column(place) => Some(types[usize::from(place)].clone()),
                    PlanArgument::Made(index) => Some(made[usize::from(index)].clone()),
                    PlanArgument::Zero => None,
                }, &|_, _| false);
                if !held {
                    continue;
                }
                for (column, ty) in rule.gives.iter() {
                    let slot = match argument_at(column) {
                        Some(PlanArgument::Column(place)) if !negated => &mut types[usize::from(place)],
                        Some(PlanArgument::Made(index)) => &mut made[usize::from(index)],
                        _ => continue,
                    };
                    match slot.meet(ty) {
                        crate::types::Meet::Type(met) => *slot = met,
                        crate::types::Meet::Empty => return None,
                    }
                }
            }
        }
        Some(())
    }

    /// Calls `visit` with the place of each atom of `atoms`, each its token
    /// ids, and what the join gives for it, in the order of the list. `labels`
    /// is the count of labels at this state, and each atom's work counts under
    /// `cap`.
    pub fn each_atom_rows(&self, sub: Option<&SubBody>, base: &BaseRows, labels: u32, atoms: &[Box<[u32]>], cap: u64, visit: &mut dyn FnMut(usize, AtomRows)) {
        // A `NOT` that stands before the atoms reads them in a way that the tokens of an atom do not show, and a body in a form of a body adds its atoms to that form.
        if self.state.negation_pending() || self.state.in_other_form() {
            (0..atoms.len()).for_each(|at| visit(at, AtomRows::ByProgram));
            return;
        }
        let limits = self.limits();
        let mut opened: StableHashMap<u32, Option<OpenedRelation>> = StableHashMap::default();
        let not = self.vocabulary().id(&Token::Control(Control::Not));
        let plans: Vec<Result<AtomPlan, AtomRows>> = self.with_checks_at_state(|checks| {
            let column_type = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
            atoms.iter().map(|atom| {
                let negated = atom.first().copied() == not;
                let rest = if negated { &atom[1..] } else { &atom[..] };
                let (relation, sites) = rest.split_first().ok_or(AtomRows::ByProgram)?;
                let held = opened.entry(*relation).or_insert_with(|| self.opened_relation(sub, base, *relation));
                let held = held.as_ref().ok_or(AtomRows::ByProgram)?;
                self.atom_plan(held, base, labels, *relation, negated, sites, &column_type)
            }).collect()
        });
        let mut memo = BatchMemo::default();
        for (at, plan) in plans.into_iter().enumerate() {
            let rows = match plan {
                Ok(plan) => self.atom_table(sub, base, plan, cap, &limits, &mut memo),
                Err(other) => other,
            };
            visit(at, rows);
        }
    }

    /// The table of the atom of `plan`.
    fn atom_table(&self, sub: Option<&SubBody>, base: &BaseRows, plan: AtomPlan, cap: u64, limits: &Limits, memo: &mut BatchMemo) -> AtomRows {
        let work = TableWork::new(cap);
        let limits = limits.clone().counted_in(work);
        let mut found = Vec::with_capacity(base.examples.len());
        for (at_example, (example, held)) in base.examples.iter().enumerate() {
            let value = match held {
                Err(fault) => Err(fault.clone()),
                Ok(assigned) => {
                    let mut at = Vec::with_capacity(assigned.at.len());
                    for (at_assignment, (values, held)) in assigned.at.iter().enumerate() {
                        let value = match &held.value {
                            RelationValue::Rows(rows) => {
                                let input = match &plan.source {
                                    PlanSource::Relation(relation, slot) => {
                                        let rows = memo.read.entry((*slot, at_example, at_assignment)).or_insert_with(|| {
                                            let program = &sub.expect("a body where an atom reads a relation of the program").program;
                                            let (task, session, constructions) = self.evaluation_inputs();
                                            let parameters = ParameterValues::determined(values.clone());
                                            let evaluation = Evaluation { program, concept: None, task, session, constructions, registry: self.context.registry, parameters: &parameters, limits: &limits };
                                            let on = (examples::scope_of(program, relation) == examples::ExampleScope::PerExample).then_some(*example).flatten();
                                            match evaluation.relation(relation, on) {
                                                Ok(RelationValue::Rows(rows)) => Some(rows),
                                                _ => None,
                                            }
                                        });
                                        match rows {
                                            Some(rows) => NodeInput::Relation(Arc::clone(rows)),
                                            None => return AtomRows::ByProgram,
                                        }
                                    }
                                    PlanSource::Fact(fact) => {
                                        let on = fact.per_example().then_some(*example).flatten();
                                        NodeInput::Relation(self.session.fact_relation(self.task, *fact, on))
                                    }
                                    PlanSource::Lib(_) => NodeInput::Unread,
                                };
                                let mut budget = Budget::new(&limits, self.session);
                                let part = self.part_it_reads(rows, &plan);
                                let value = match part {
                                    Some(part) => self.grouped(rows, part, &plan, &input, base.columns.len(), (at_example, at_assignment), memo, &mut budget).map(HeldValue::Grouped),
                                    None => self.joined(rows, &held.parts, &plan, input, base.columns.len(), &limits).map(HeldValue::Whole),
                                };
                                match value {
                                    Ok(value) => value,
                                    Err(ReachedBound::TableWork { .. }) => return AtomRows::OverCap,
                                    Err(_) => return AtomRows::ByProgram,
                                }
                            }
                            other => HeldValue::Whole(other.clone()),
                        };
                        at.push((values.clone(), value));
                    }
                    Ok(Assigned { at, stop: assigned.stop.clone() })
                }
            };
            found.push((*example, value));
        }
        AtomRows::Rows(JoinedAtom { types: plan.types, examples: found })
    }

    /// The place of the one part of `rows` that the atom of `plan` reads, where
    /// the atom's values come from its relation at the values of that part.
    fn part_it_reads(&self, rows: &Relation, plan: &AtomPlan) -> Option<usize> {
        let holds = |part: &RelationPart| plan.sites.iter().any(|&(_, argument)| matches!(argument, PlanArgument::Column(column) if part.columns.contains(&ColumnIndex(column))));
        let mut reads = rows.parts().iter().enumerate().filter(|(_, part)| holds(part)).map(|(at, _)| at);
        let part = reads.next()?;
        if reads.next().is_some() || plan.made.len() > MADE_LABELS {
            return None;
        }
        if let PlanSource::Lib(name) = &plan.source {
            let relation = self.context.registry.algebra_relation(name)?;
            if !relation.modes.is_empty() {
                let mut bound = vec![false; relation.columns.len()];
                for &(column, argument) in &plan.sites {
                    bound[usize::from(column.0)] = !matches!(argument, PlanArgument::Made(_));
                }
                crate::algebra::satisfied_mode(relation, &bound)?;
            }
        }
        Some(part)
    }

    /// The value of the atom of `plan` over the part at `part` of `rows`, read one group at a time.
    #[allow(clippy::too_many_arguments)]
    fn grouped(&self, rows: &Arc<Relation>, part: usize, plan: &AtomPlan, input: &NodeInput, width: usize, at: (usize, usize), memo: &mut BatchMemo, budget: &mut Budget<'_>) -> Result<GroupedValue, ReachedBound> {
        let held = &rows.parts()[part];
        let place_of = |column: u16| held.columns.iter().position(|held| held.0 == column).expect("a column of the part") as u16;
        let mut places: Vec<u16> = plan.sites.iter().filter_map(|&(_, argument)| match argument { PlanArgument::Column(column) => Some(place_of(column)), _ => None }).collect();
        places.sort_unstable();
        places.dedup();
        let hashes = |memo: &mut BatchMemo, part: usize| {
            Rc::clone(memo.hashes.entry((at.0, at.1, part)).or_insert_with(|| {
                let held = &rows.parts()[part];
                let hashes: Vec<u64> = held.rows.rows().map(|row| row_hash_at(&held.columns, row)).collect();
                let sum = hashes.iter().fold(0, |sum, hash| hash_plus(sum, *hash));
                Rc::new(PartHashes { rows: hashes, sum, order: OnceCell::new() })
            }))
        };
        let own = hashes(memo, part);
        let groups = Rc::clone(memo.groups.entry((at.0, at.1, part, places.as_slice().into())).or_insert_with(|| Rc::new(Groups::of(held, &own.rows, places.as_slice().into()))));
        // The groups of the part's rows that the atom reads are content, and the candidate values of each are tried as effort.
        budget.charge_content(groups.count() as u64)?;
        budget.charge_work(groups.count() as u64)?;
        // Where each site's value stands among the values of a group.
        let group_place = |column: u16| places.iter().position(|place| *place == place_of(column)).expect("a place of the groups") as u16;
        let sites: Box<[(u16, u16)]> = plan.sites.iter().filter(|(_, argument)| !matches!(argument, PlanArgument::Made(_))).map(|&(column, argument)| (column.0, match argument {
            PlanArgument::Column(held) => group_place(held),
            _ => u16::MAX,
        })).collect();
        let key: HoldsKey = (plan.relation, sites, at.0, at.1, part, places.as_slice().into());
        let result = if plan.made.is_empty() {
            match memo.holds.get(&key) {
                Some(holds) => GroupResult::Holds(Rc::clone(holds)),
                None => {
                    let holds = Rc::new(self.holds_at(plan, input, &groups, &group_place, &key, memo)?);
                    memo.holds.insert(key, Rc::clone(&holds));
                    GroupResult::Holds(holds)
                }
            }
        } else {
            GroupResult::Makes(self.makes_at(plan, input, &groups, &group_place, &key, memo)?)
        };
        // The hash of a row with what the atom adds is the row's hash times the hash of what it adds.
        let others = (0..rows.parts().len()).filter(|other| *other != part).fold(1u64, |product, other| hash_times(product, hashes(memo, other).sum));
        let (sum, count) = match &result {
            GroupResult::Holds(holds) => (0..groups.count()).filter(|&group| holds.get(group) != plan.negated).fold((0u64, 0u64), |(sum, count), group| (hash_plus(sum, groups.sums[group]), count + u64::from(groups.rows[group]))),
            GroupResult::Makes(made) => (0..groups.count()).fold((0u64, 0u64), |(sum, count), group| {
                let values = made.at(group);
                let adds = values.chunks_exact(made.width).fold(0u64, |adds, row| hash_plus(adds, row.iter().enumerate().fold(1u64, |hash, (index, value)| hash_times(hash, value_hash((width + index) as u16, value.encoding())))));
                (hash_plus(sum, hash_times(groups.sums[group], adds)), count + u64::from(groups.rows[group]) * (values.len() / made.width) as u64)
            }),
        };
        budget.charge_rows(count)?;
        // A program counts the rows of a product as content, and stops at their cap.
        if rows.parts().len() >= 2 {
            let product = (0..rows.parts().len()).filter(|other| *other != part).fold(count, |product, other| product.saturating_mul(rows.parts()[other].rows.len() as u64));
            budget.charge_content(product)?;
            budget.charge_work(0)?;
        }
        let arity = (width + plan.made.len()) as u16;
        Ok(GroupedValue { rows: Arc::clone(rows), part, groups, result, negated: plan.negated, hashes: own, arity, hash: rows_hash_of(arity, hash_times(others, sum)) })
    }

    /// The rows of the lib relation `name` at each group, which the atom of `plan` reads.
    fn lib_read(&self, name: &crate::registry::LibName, plan: &AtomPlan, groups: &Groups, group_place: &dyn Fn(u16) -> u16, key: &HoldsKey, memo: &mut BatchMemo) -> Result<Rc<LibRead>, ReachedBound> {
        if let Some(read) = memo.reads.get(key) {
            return Ok(Rc::clone(read));
        }
        let (algebra, mut bound, sites) = self.lib_reading(name, plan, group_place);
        let mut read = LibRead { width: bound.len(), starts: Vec::with_capacity(groups.count() + 1), values: Vec::new() };
        read.starts.push(0);
        for group in 0..groups.count() {
            let values = groups.values_at(group);
            for &(column, place) in &sites {
                bound[column] = Some(values[usize::from(place)]);
            }
            algebra.evaluate(&bound, self.context.registry, &mut |row| {
                if bound.iter().zip(row).all(|(held, value)| held.is_none_or(|held| held == *value)) {
                    read.values.extend_from_slice(row);
                }
            }).map_err(ReachedBound::Margin)?;
            read.starts.push((read.values.len() / read.width.max(1)) as u32);
        }
        let read = Rc::new(read);
        let bytes = read.values.len() * 4;
        if memo.read_bytes + bytes <= READ_BYTES {
            memo.read_bytes += bytes;
            memo.reads.insert(key.clone(), Rc::clone(&read));
        }
        Ok(read)
    }

    /// Whether the atom of `plan`, which makes no label, holds at each group.
    fn holds_at(&self, plan: &AtomPlan, input: &NodeInput, groups: &Groups, group_place: &dyn Fn(u16) -> u16, key: &HoldsKey, memo: &mut BatchMemo) -> Result<Bits, ReachedBound> {
        let mut holds = Bits::new(groups.count());
        match (&plan.source, input) {
            (PlanSource::Lib(name), _) => {
                let read = self.lib_read(name, plan, groups, group_place, key, memo)?;
                for group in 0..groups.count() {
                    if read.starts[group] != read.starts[group + 1] {
                        holds.set(group);
                    }
                }
            }
            (_, NodeInput::Relation(relation)) => {
                let (index, levels) = trie_reading(relation, plan, group_place);
                for group in 0..groups.count() {
                    if walk_group(index.root(), &levels, groups.values_at(group)).is_some() {
                        holds.set(group);
                    }
                }
            }
            _ => unreachable!("an atom of a program or fact relation reads its rows"),
        }
        Ok(holds)
    }

    /// The values of the labels that the atom of `plan` makes, at each group.
    fn makes_at(&self, plan: &AtomPlan, input: &NodeInput, groups: &Groups, group_place: &dyn Fn(u16) -> u16, key: &HoldsKey, memo: &mut BatchMemo) -> Result<Made, ReachedBound> {
        let width = plan.made.len();
        let mut made = Made { width, starts: Vec::with_capacity(groups.count() + 1), values: Vec::new() };
        made.starts.push(0);
        match (&plan.source, input) {
            (PlanSource::Lib(name), _) => {
                let read = self.lib_read(name, plan, groups, group_place, key, memo)?;
                let made_sites: Vec<(usize, usize)> = plan.sites.iter().filter_map(|&(column, argument)| match argument {
                    PlanArgument::Made(index) => Some((usize::from(column.0), usize::from(index))),
                    _ => None,
                }).collect();
                let boxes: Vec<bool> = plan.made.iter().map(ValueType::is_box).collect();
                let mut found: Vec<TermId> = Vec::new();
                let mut row_values = vec![TermId::from_encoding(0); width];
                for group in 0..groups.count() {
                    found.clear();
                    'rows: for row in read.at(group).chunks_exact(read.width) {
                        let mut seen = [false; MADE_LABELS];
                        for &(column, index) in &made_sites {
                            if std::mem::replace(&mut seen[index], true) {
                                if row_values[index] != row[column] {
                                    continue 'rows;
                                }
                            } else {
                                row_values[index] = row[column];
                            }
                        }
                        found.extend_from_slice(&row_values);
                    }
                    // A column with no site repeats a row of the columns at sites.
                    end_group(&mut made, &found, &boxes);
                }
            }
            (_, NodeInput::Relation(relation)) => {
                let (index, levels) = trie_reading(relation, plan, group_place);
                let bound = levels.iter().take_while(|level| !matches!(level, Level::Made(_))).count();
                let boxes: Vec<bool> = plan.made.iter().map(ValueType::is_box).collect();
                let mut row_values = vec![None; width];
                let mut found: Vec<TermId> = Vec::new();
                for group in 0..groups.count() {
                    let values = groups.values_at(group);
                    found.clear();
                    if let Some(node) = walk_group(index.root(), &levels[..bound], values) {
                        walk_made(node, &levels[bound..], &mut row_values, &mut found);
                    }
                    end_group(&mut made, &found, &boxes);
                }
            }
            _ => unreachable!("an atom of a program or fact relation reads its rows"),
        }
        Ok(made)
    }

    /// How an atom of the lib relation `name` reads a group: the relation, its
    /// columns with the values that no group changes, and for each column that
    /// a group gives, the place of its value among the group's values.
    #[allow(clippy::type_complexity)]
    fn lib_reading(&self, name: &crate::registry::LibName, plan: &AtomPlan, group_place: &dyn Fn(u16) -> u16) -> (&'static dyn crate::algebra::Algebra, Vec<Option<TermId>>, Vec<(usize, u16)>) {
        let algebra = crate::algebra::algebra(name).expect("a native form of each algebra relation");
        let columns = self.context.registry.algebra_relation(name).expect("the declaration of an algebra relation").columns.len();
        let mut bound = vec![None; columns];
        let mut sites = Vec::new();
        for &(column, argument) in &plan.sites {
            match argument {
                PlanArgument::Column(held) => sites.push((usize::from(column.0), group_place(held))),
                PlanArgument::Zero => bound[usize::from(column.0)] = Some(TermId::from_encoding(0)),
                PlanArgument::Made(_) => {}
            }
        }
        (algebra, bound, sites)
    }

    /// The value of the atom of `plan`, reading `input`, joined to the body's rows `rows`.
    fn joined(&self, rows: &Relation, parts: &[Arc<Relation>], plan: &AtomPlan, input: NodeInput, width: usize, limits: &Limits) -> Result<RelationValue, ReachedBound> {
        // The variable of a column of the body is its place, and that of a made label follows them.
        let variable_of = |argument: PlanArgument| match argument {
            PlanArgument::Column(column) => Argument::Variable(Variable(column)),
            PlanArgument::Made(index) => Argument::Variable(Variable(width as u16 + index)),
            PlanArgument::Zero => Argument::Term(TermId::from_encoding(0)),
        };
        let arguments = Arguments(plan.sites.iter().map(|&(column, argument)| (column, variable_of(argument))).collect());
        let joins = |column: u16| plan.sites.iter().any(|&(_, argument)| matches!(argument, PlanArgument::Column(held) if held == column));
        let mut nodes: Vec<IrNode> = Vec::new();
        let mut inputs: Vec<NodeInput> = Vec::new();
        let mut kept: Vec<RelationPart> = Vec::new();
        let mut joined_columns: Vec<Variable> = Vec::new();
        for (part, held) in rows.parts().iter().zip(parts) {
            if part.columns.iter().any(|column| joins(column.0)) {
                let arguments = part.columns.iter().enumerate().map(|(at, column)| (ColumnIndex(at as u16), Argument::Variable(Variable(column.0)))).collect();
                nodes.push(IrNode::Atom(RelationAtom { source: AtomSource::Fact(FactRelation::Input), train_only: false, arguments: Arguments(arguments) }));
                inputs.push(NodeInput::Relation(Arc::clone(held)));
                joined_columns.extend(part.columns.iter().map(|column| Variable(column.0)));
            } else {
                kept.push(part.clone());
            }
        }
        let node = match &plan.source {
            PlanSource::Lib(name) => IrNode::Lib(LibAtom { relation: name.clone(), arguments }),
            PlanSource::Fact(fact) => IrNode::Atom(RelationAtom { source: AtomSource::Fact(*fact), train_only: false, arguments }),
            PlanSource::Relation(relation, _) => IrNode::Atom(RelationAtom { source: AtomSource::Relation(relation.clone()), train_only: false, arguments }),
        };
        if plan.negated {
            let mut outer: Vec<Variable> = plan.sites.iter().filter_map(|&(_, argument)| match argument { PlanArgument::Column(column) => Some(Variable(column)), _ => None }).collect();
            outer.sort_by_key(|variable| variable.0);
            outer.dedup();
            let body = ClauseIr::new(plan.variables.clone(), Box::new([node]), Box::new([]));
            nodes.push(IrNode::Not(Filter { outer: outer.into(), body: Box::new(body) }));
            inputs.push(NodeInput::Clauses(Box::new([JoinInputs(Box::new([input]))])));
        } else {
            joined_columns.extend((0..plan.made.len()).map(|index| Variable(width as u16 + index as u16)));
            nodes.push(node);
            inputs.push(input);
        }
        let clause = ClauseIr::new(plan.variables.clone(), nodes.into(), joined_columns.into());
        let inputs = JoinInputs(inputs.into());
        let order = plan::variable_order(&clause, &join::sizes(&clause, &inputs), &[]);
        let all: Vec<usize> = (0..clause.nodes.len()).collect();
        let mut budget = Budget::new(limits, self.session);
        for part in join::parts(&clause, &all, &|node| node) {
            let columns = part.columns(&clause);
            let found = join::search_part(&clause, &part.nodes, part.order(&order, &[]), &inputs, self.context.registry, &columns, &mut budget)?;
            kept.extend(found.parts().iter().map(|found| RelationPart {
                columns: found.columns.iter().map(|column| ColumnIndex(clause.columns[usize::from(columns[usize::from(column.0)].0)].0)).collect(),
                rows: found.rows.clone(),
            }));
        }
        let arity = if plan.negated { width } else { width + plan.made.len() };
        let kept: Vec<RelationPart> = kept.into_iter().filter(|part| !part.columns.is_empty() || part.rows.is_empty()).collect();
        let relation = Relation::from_parts(arity as u16, kept.into());
        // A program counts the rows of a product as the bindings of its walk, and stops at their cap.
        budget.charge_product(&relation)?;
        Ok(RelationValue::Rows(Arc::new(relation)))
    }
}

/// The index of `relation` in the order of the sites of `plan` whose values no
/// walk of the index makes, and then the others, with what stands at each level.
fn trie_reading(relation: &Relation, plan: &AtomPlan, group_place: &dyn Fn(u16) -> u16) -> (Arc<Index>, Vec<Level>) {
    let mut sites: Vec<(ColumnIndex, Level)> = plan.sites.iter().filter(|(_, argument)| !matches!(argument, PlanArgument::Made(_))).map(|&(column, argument)| (column, match argument {
        PlanArgument::Column(held) => Level::Group(group_place(held)),
        PlanArgument::Zero => Level::Term(TermId::from_encoding(0)),
        PlanArgument::Made(_) => unreachable!("a site that the filter leaves out"),
    })).collect();
    sites.extend(plan.sites.iter().filter_map(|&(column, argument)| match argument {
        PlanArgument::Made(index) => Some((column, Level::Made(index))),
        _ => None,
    }));
    let order = ColumnOrder(sites.iter().map(|(column, _)| *column).collect());
    // No budget stands here, so the rows of a build wait for the next charge of the request.
    // They count at each use, whether or not the relation held the index.
    let (index, _) = relation.index_built(&order);
    crate::eval::RequestWork::note_unbilled(index.walked());
    (index, sites.into_iter().map(|(_, level)| level).collect())
}

/// The node of an index at the values that `levels`, none of them a made label, give at `values`.
fn walk_group<'i>(root: IndexNode<'i>, levels: &[Level], values: &[TermId]) -> Option<IndexNode<'i>> {
    let mut at = root;
    for level in levels {
        at = at.child(match level {
            Level::Group(place) => values[usize::from(*place)],
            Level::Term(term) => *term,
            Level::Made(_) => unreachable!("levels that hold no made label"),
        })?;
    }
    Some(at)
}

/// Adds to `found` the values of the made labels at each path below `node`.
fn walk_made(node: IndexNode<'_>, levels: &[Level], row: &mut Vec<Option<TermId>>, found: &mut Vec<TermId>) {
    let Some((level, rest)) = levels.split_first() else {
        found.extend(row.iter().map(|value| value.expect("a value of each made label")));
        return;
    };
    let Level::Made(index) = *level else { unreachable!("levels that hold made labels alone") };
    let index = usize::from(index);
    match row[index] {
        Some(value) => {
            if let Some(child) = node.child(value) {
                walk_made(child, rest, row, found);
            }
        }
        None => {
            for (value, child) in node.entries() {
                row[index] = Some(value);
                walk_made(child, rest, row, found);
            }
            row[index] = None;
        }
    }
}
