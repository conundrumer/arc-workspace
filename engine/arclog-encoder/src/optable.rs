//! The operators that can extend a relation, per schema: what the checker
//! accepts on a relation depends on its schema alone, so each operator is checked
//! once per schema and written by the positions of its columns. A schema is the
//! type of each column, which columns share an Ident source, and which columns the
//! checker takes as standing in one frame.

use std::collections::BTreeSet;
use std::ops::ControlFlow;

use arclog::algebra::algebra;
use arclog::program::ColumnName;
use arclog::registry::{is_key, key_fill, ColumnType, LibName, Registry};
use arclog::resolver::registry_columns::component;
use arclog::types::ValueType;

use crate::enumerate::{Space, Typed};
use crate::expand::{input_fields, label_of, spelled, ZERO_FIELD};
use crate::expression::{Binding, Field, Leaf, Op, Operand, Rel};
use crate::native::{BoundInput, CompInstance, CompShape, FastMap, InputFill, InputShape, LibRelation, Step};
use crate::run::{Host, TermCheck};

/// The result of an operator whose schema nothing reads.
pub const NO_SCHEMA: u32 = u32::MAX;

/// What a term of a run reads: `input`, `output`, a table.
pub const READS_INPUT: u8 = 1;
pub const READS_OUTPUT: u8 = 2;
pub const READS_TABLE: u8 = 4;

/// Which roots a run reads.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Roots that read `input`.
    Scene,
    /// Roots that read `output`.
    Rule,
    /// Roots that read the table of this name and `output`.
    Table(String),
}

impl Mode {
    /// What a root must read.
    pub fn required(&self) -> u8 {
        match self {
            Mode::Scene => READS_INPUT,
            Mode::Rule => READS_OUTPUT,
            Mode::Table(_) => READS_TABLE | READS_OUTPUT,
        }
    }
}

/// A schema, with a relation that has it.
pub struct Schema {
    pub rep: Typed,
    pub types: Vec<ValueType>,
    pub invariant: Vec<u16>,
    pub names: Vec<bool>,
    /// Which pairs of `Position` columns stand in one frame, in the order of the
    /// pairs, each column with itself and those after it.
    pub frames: Vec<bool>,
    /// Whether the relation is a leaf, which an atom reads directly.
    pub leaf: bool,
    /// Whether it reads `d4_elem`, whose column takes its type from a later site.
    pub open_d4: bool,
}

impl Schema {
    /// The text of what the checker reads of the columns `columns`: each type,
    /// which of them are one column, which share a source, and which share a frame.
    fn touched(&self, columns: &[usize]) -> String {
        let positions: Vec<usize> = self.types.iter().enumerate().filter(|(_, ty)| **ty == ValueType::Position).map(|(at, _)| at).collect();
        let frame = |a: usize, b: usize| -> bool {
            let (a, b) = if a <= b { (a, b) } else { (b, a) };
            let mut at = 0;
            for (place, first) in positions.iter().enumerate() {
                for second in &positions[place..] {
                    if *first == a && *second == b {
                        return self.frames.get(at).copied().unwrap_or(false);
                    }
                    at += 1;
                }
            }
            false
        };
        let mut text = String::new();
        for (place, column) in columns.iter().enumerate() {
            let same = columns.iter().position(|other| other == column).unwrap_or(place);
            let ty = &self.types[*column];
            let source = columns.iter().position(|other| self.types[*other] == *ty).unwrap_or(place);
            text.push_str(&format!("{:?}#{same}#{source}", ty.without_source()));
            if *ty == ValueType::Position {
                for other in &columns[..=place] {
                    if self.types[*other] == ValueType::Position {
                        text.push(if frame(*column, *other) { 'f' } else { 'g' });
                    }
                }
            }
            text.push(';');
        }
        text
    }
}

/// What a run that compares operators with the engine, or that reads their
/// shapes, keeps of an operator.
pub struct EntryMeta {
    /// The term with its children's places left as `input`, and the names of its
    /// children's relations.
    pub term: Rel,
    pub children: Vec<u32>,
    /// The names of the value's columns.
    pub columns: Vec<String>,
    /// The types of those columns.
    pub types: Vec<ValueType>,
}

/// An operator over relations of given schemas.
pub struct Entry {
    pub step: Step,
    pub result: u32,
    /// The columns its roots read: an index in `OpTable::invariants`.
    pub invariant: u32,
    pub roots: u32,
    pub meta: Option<Box<EntryMeta>>,
    /// Whether the operator with its children swapped gives the same rows, in
    /// another order of columns.
    pub mirrored: bool,
    /// Which of a pair of mirrored operators on one relation counts.
    pub self_first: bool,
    /// The tier of the operator: the cheaper operators stand in the lower ones.
    pub tier: u8,
}

/// The number of tiers of the top size's operators.
pub const TIERS: usize = 4;

/// The names of the tiers.
pub const TIER_NAMES: [&str; TIERS] = ["relational", "counting", "structure", "closures"];

/// The tier of a component by its cost: counting a key's rows, then structure over
/// a group's rows, then orders and closures over their graph.
fn component_tier(name: &str) -> u8 {
    match name {
        "Cardinality" | "Singleton" | "Excess" | "BoundingBox" | "Inclusion" => 1,
        "Boundary" | "Frame" | "Division" | "Tiling" | "Agreement" | "Periods" | "Outlines" | "Occurrences" | "ExtentDivisions" | "Ray" | "Walk" => 2,
        _ => 3,
    }
}

/// The number of roots over a relation with `invariant` invariant columns.
pub fn roots_of(invariant: usize) -> usize {
    2 + ((1usize << invariant.min(12)) - 1)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeafKind {
    Input,
    Output,
    Lib(u32),
    Table,
}

pub struct LeafEntry {
    pub kind: LeafKind,
    pub schema: u32,
    /// The leaf as a relation: two leaves can share a schema.
    pub rep: Typed,
    /// Whether a root over this leaf counts: it reads what the test's roots read.
    pub root: bool,
    /// What the leaf reads.
    pub flags: u8,
}

/// The operators of a run, by the schemas of their children.
#[derive(Default)]
pub struct OpTable {
    /// The invariant columns of an operator's value, with which positions hold a
    /// lib name, each list once.
    pub invariants: Vec<(Vec<u16>, Vec<bool>)>,
    invariant_index: std::collections::HashMap<(Vec<u16>, Vec<bool>), u32>,
    pub schemas: Vec<Schema>,
    index: FastMap<u128, u32>,
    pub entries: Vec<Entry>,
    pub leaves: Vec<LeafEntry>,
    pub unary: FastMap<u32, Vec<u32>>,
    pub binary: FastMap<(u32, u32), Vec<u32>>,
    pub two_inputs: FastMap<(u32, u32), Vec<u32>>,
    pub shapes: Vec<CompShape>,
    shape_index: FastMap<u128, u32>,
    pub instances: Vec<CompInstance>,
    instance_index: std::collections::HashMap<CompInstance, u32>,
    pub libs: Vec<LibRelation>,
    lib_index: std::collections::HashMap<String, u32>,
    /// The terms that the checker refused, and those with no native form.
    pub refused: u64,
    pub no_native: Vec<String>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Family {
    Unary(u32),
    Binary(u32, u32),
    TwoInputs(u32, u32),
}

struct Pending {
    term: Typed,
    family: Family,
}

fn invariant_type(ty: &ValueType) -> bool {
    matches!(ty, ValueType::Int | ValueType::Nat | ValueType::Unit | ValueType::Example | ValueType::LibName)
}

/// The types of `columns` from what the checker gives, by their names.
fn aligned(columns: &[String], check: &TermCheck) -> Option<Vec<ValueType>> {
    columns.iter().map(|name| check.row_names.iter().position(|own| *own == label_of(name) || own == name).and_then(|at| check.types.get(at).cloned())).collect()
}

/// A key of what the checker reads of a relation's columns: their types, which
/// share a source, and the pairs of columns in one frame.
fn schema_key(types: &[ValueType], frames: &[bool], open_d4: bool) -> u128 {
    let mut text = String::new();
    if open_d4 {
        text.push('o');
    }
    for (at, ty) in types.iter().enumerate() {
        let first = types.iter().position(|other| other == ty).unwrap_or(at);
        text.push_str(&format!("{:?}#{first};", ty.without_source()));
    }
    for frame in frames {
        text.push(if *frame { '1' } else { '0' });
    }
    crate::native::hash_words(text.bytes().map(u64::from))
}

struct Builder<'a> {
    host: &'a Host,
    /// The space of the terms, which a walk over it holds.
    space: Option<Space<'a>>,
    table: OpTable,
    pending: Vec<Pending>,
    done: BTreeSet<(u8, u32, u32)>,
    top: bool,
    mode: Mode,
    log_every: std::time::Instant,
    /// What the checker said of an operator, by what it reads of its children's
    /// columns: the columns it does not read have labels of their own, so they
    /// take no part. A key maps to whether the checker accepts it.
    answers: FastMap<u128, bool>,
    /// The terms the checker read, and those a key answered.
    pub checked: u64,
    pub answered: u64,
    keep_terms: bool,
}

const BATCH: usize = 256;

impl Builder<'_> {
    fn lib(&mut self, name: &str) -> Result<u32, String> {
        if let Some(found) = self.table.lib_index.get(name) {
            return Ok(*found);
        }
        let lib_name = LibName(name.into());
        let held = algebra(&lib_name).ok_or_else(|| format!("`{name}` has no native form"))?;
        let arity = Registry::get().algebra_relation(&lib_name).map(|relation| relation.columns.len()).or_else(|| match Registry::get().entry(&lib_name) {
            Some(arclog::registry::LibEntry::Relation(relation) | arclog::registry::LibEntry::Macro(arclog::registry::Macro::Relation { relation, .. })) => Some(relation.columns.len()),
            _ => None,
        }).ok_or_else(|| format!("`{name}` has no columns"))?;
        let at = self.table.libs.len() as u32;
        self.table.libs.push(LibRelation { code: crate::native::hash_words(name.bytes().map(u64::from)) as u64, algebra: held, arity });
        self.table.lib_index.insert(name.to_string(), at);
        Ok(at)
    }

    /// The pairs of `Position` columns of `columns` that the checker takes as one
    /// frame, in the order of the pairs: `relative` reads that alone.
    fn frames_of(&self, terms: &[(&Rel, &[String], &[ValueType])]) -> Vec<Vec<bool>> {
        let mut probes: Vec<Rel> = Vec::new();
        let mut places: Vec<Vec<usize>> = Vec::new();
        for (rel, columns, types) in terms {
            let positions: Vec<usize> = types.iter().enumerate().filter(|(_, ty)| **ty == ValueType::Position).map(|(at, _)| at).collect();
            let mut own = Vec::new();
            for (place, a) in positions.iter().enumerate() {
                for b in &positions[place..] {
                    own.push(probes.len());
                    probes.push(Rel::LibJoin(Box::new((*rel).clone()), "relative".to_string(), vec![("Base".to_string(), columns[*a].clone()), ("X".to_string(), columns[*b].clone())]));
                }
            }
            places.push(own);
        }
        let refs: Vec<&Rel> = probes.iter().collect();
        let mut answers: Vec<bool> = Vec::with_capacity(refs.len());
        for batch in refs.chunks(BATCH) {
            for check in self.host.check_terms(batch) {
                answers.push(check.is_ok_and(|check| check.row_names.iter().position(|name| name == "X_rel").and_then(|at| check.types.get(at).cloned()) == Some(ValueType::Offset)));
            }
        }
        places.into_iter().map(|own| own.into_iter().map(|at| answers[at]).collect()).collect()
    }

    fn schema_of(&mut self, term: &Typed, types: Vec<ValueType>, frames: &[bool]) -> u32 {
        let open_d4 = term.rel.to_string().contains("d4_elem");
        let key = schema_key(&types, frames, open_d4);
        if let Some(found) = self.table.index.get(&key) {
            return *found;
        }
        let invariant: Vec<u16> = types.iter().enumerate().filter(|(_, ty)| invariant_type(ty)).map(|(at, _)| at as u16).collect();
        let names: Vec<bool> = types.iter().map(|ty| *ty == ValueType::LibName).collect();
        let at = self.table.schemas.len() as u32;
        let leaf = matches!(term.rel, Rel::Leaf(_));
        // A later operator's bindings read the rep's types, so it holds the narrowed ones.
        let mut rep = term.clone();
        if rep.columns.len() == types.len() {
            for (column, ty) in rep.columns.iter_mut().zip(&types) {
                column.ty = Some(ty.clone());
            }
        }
        self.table.schemas.push(Schema { rep, types, invariant, names, frames: frames.to_vec(), leaf, open_d4 });
        self.table.index.insert(key, at);
        at
    }

    fn add_leaves(&mut self) -> Result<Vec<(u32, u8)>, String> {
        let leaves = self.space.as_ref().expect("the space between two walks").leaves();
        let refs: Vec<&Rel> = leaves.iter().map(|leaf| &leaf.rel).collect();
        let checks = self.host.check_terms(&refs);
        let mut typed: Vec<(usize, Vec<String>, Vec<ValueType>)> = Vec::new();
        for (at, (leaf, check)) in leaves.iter().zip(checks).enumerate() {
            let check = check.map_err(|message| format!("the leaf {} is refused: {message}", leaf.rel))?;
            let columns: Vec<String> = leaf.columns.iter().map(|column| column.name.clone()).collect();
            let types = aligned(&columns, &check).ok_or_else(|| format!("the leaf {} has unknown columns", leaf.rel))?;
            typed.push((at, columns, types));
        }
        let probes: Vec<(&Rel, &[String], &[ValueType])> = typed.iter().map(|(at, columns, types)| (&leaves[*at].rel, &columns[..], &types[..])).collect();
        let frames = self.frames_of(&probes);
        let mut members = Vec::new();
        for ((at, _, types), frames) in typed.iter().zip(&frames) {
            let leaf = &leaves[*at];
            let kind = match &leaf.rel {
                Rel::Leaf(Leaf::Input) => LeafKind::Input,
                Rel::Leaf(Leaf::Output) => LeafKind::Output,
                Rel::Leaf(Leaf::Lib(name)) => LeafKind::Lib(self.lib(name)?),
                Rel::Leaf(Leaf::Table(_)) => LeafKind::Table,
                other => return Err(format!("the leaf {other} is no grid, table or lib relation")),
            };
            let schema = self.schema_of(leaf, types.clone(), frames);
            let flags = match kind {
                LeafKind::Input => READS_INPUT,
                LeafKind::Output => READS_OUTPUT,
                LeafKind::Table => READS_TABLE,
                LeafKind::Lib(_) => 0,
            };
            let required = self.mode.required();
            self.table.leaves.push(LeafEntry { kind, schema, rep: leaf.clone(), root: flags & required == required, flags });
            members.push((schema, flags));
        }
        Ok(members)
    }

    fn visit(&mut self, family: Family, term: Typed) {
        self.pending.push(Pending { term, family });
        if self.pending.len() >= BATCH {
            self.flush();
        }
    }

    /// The key of what the checker reads of `rel` on the schemas `children`, for an
    /// operator whose answer does not depend on the columns it does not read.
    fn answer_key(&self, rel: &Rel, children: &[u32]) -> Option<u128> {
        let schema = |at: usize| &self.table.schemas[children[at] as usize];
        let place = |at: usize, name: &str| -> Option<usize> { schema(at).rep.columns.iter().position(|column| column.name == name) };
        let leafs = |text: &mut String| {
            for at in 0..children.len() {
                text.push(if schema(at).leaf { 'l' } else { 'd' });
                text.push(if schema(at).open_d4 { 'o' } else { 'c' });
            }
        };
        let mut text = String::new();
        leafs(&mut text);
        match rel {
            // A `project` reads each column under a label of its own, whatever its type.
            Rel::Project(..) => text.push('P'),
            Rel::Select(_, column, op, operand) => {
                let mut places = vec![place(0, column)?];
                if let Operand::Column(other) = operand {
                    places.push(place(0, other)?);
                }
                text.push_str(&format!("S|{}|{}|{}", op.text(), matches!(operand, Operand::Zero), schema(0).touched(&places)));
            }
            Rel::Join(_, _, pairs) | Rel::Antijoin(_, _, pairs) => {
                let lefts: Option<Vec<usize>> = pairs.iter().map(|(l, _)| place(0, l)).collect();
                let rights: Option<Vec<usize>> = pairs.iter().map(|(_, r)| place(1, r)).collect();
                text.push_str(if matches!(rel, Rel::Join(..)) { "J|" } else { "A|" });
                text.push_str(&schema(0).touched(&lefts?));
                text.push('|');
                text.push_str(&schema(1).touched(&rights?));
            }
            Rel::Union(_, _, pairs) => {
                let lefts: Option<Vec<usize>> = pairs.iter().map(|(l, _)| place(0, l)).collect();
                let mut rights = Vec::new();
                let mut shape = String::new();
                for (_, operand) in pairs {
                    match operand {
                        Operand::Column(r) => {
                            rights.push(place(1, r)?);
                            shape.push('c');
                        }
                        Operand::Zero => shape.push('0'),
                    }
                }
                text.push_str(&format!("U|{shape}|{}|{}", schema(0).touched(&lefts?), schema(1).touched(&rights)));
            }
            Rel::LibJoin(_, name, bindings) => {
                let places: Option<Vec<usize>> = bindings.iter().map(|(_, column)| place(0, column)).collect();
                let libs: Vec<&str> = bindings.iter().map(|(lib, _)| lib.as_str()).collect();
                text.push_str(&format!("L|{name}|{libs:?}|{}", schema(0).touched(&places?)));
            }
            // With one binding, a column of an unbounded type parameter takes any
            // type, and so does the key, so only the number of its fields counts.
            Rel::Component(name, bindings, port) if bindings.len() == 1 && !schema(0).open_d4 => {
                let binding = &bindings[0];
                let held = component(Registry::get(), &LibName(name.as_str().into()))?;
                let input = held.inputs.iter().find(|input| input.port.name.0.as_ref() == binding.input)?;
                let mut kept = Vec::new();
                let mut shape = format!("k{}", binding.key.len());
                let columns = input_fields(input, binding).ok()?;
                // Two columns of one parameter in an input take types that meet.
                let once = |name: &str| columns.iter().filter(|(column, _)| matches!(&column.ty, ColumnType::Parameter(parameter) if &*parameter.name == name)).count() == 1;
                for (column, fields) in &columns {
                    match &column.ty {
                        ColumnType::Parameter(parameter) if parameter.bound.is_none() && once(&parameter.name) => shape.push_str(&format!("g{}", fields.len())),
                        _ => {
                            shape.push('f');
                            for field in fields {
                                if field == ZERO_FIELD {
                                    shape.push('0');
                                } else {
                                    shape.push('c');
                                    kept.push(place(0, field)?);
                                }
                            }
                        }
                    }
                }
                text.push_str(&format!("C1|{name}|{port}|{}|{shape}|{}", binding.input, schema(0).touched(&kept)));
            }
            Rel::Component(name, bindings, port) => {
                text.push_str(&format!("C|{name}|{port}"));
                for (at, binding) in bindings.iter().enumerate() {
                    let keys: Option<Vec<usize>> = binding.key.iter().map(|column| place(at, column)).collect();
                    let mut fields = Vec::new();
                    let mut shape = String::new();
                    for field in &binding.fields {
                        match field {
                            Field::One(column) => {
                                fields.push(place(at, column)?);
                                shape.push('o');
                            }
                            Field::Record(columns) => {
                                shape.push_str(&format!("r{}", columns.len()));
                                for column in columns {
                                    fields.push(place(at, column)?);
                                }
                            }
                            Field::Zero => shape.push('0'),
                        }
                    }
                    let keys = keys?;
                    let width = keys.len();
                    let mut all = keys;
                    all.extend(fields);
                    text.push_str(&format!("|{}|{width}|{shape}|{}", binding.input, schema(at).touched(&all)));
                }
            }
            _ => return None,
        }
        Some(crate::native::hash_words(text.bytes().map(u64::from)))
    }

    fn children_of(family: Family) -> Vec<u32> {
        match family {
            Family::Unary(a) => vec![a],
            Family::Binary(a, b) | Family::TwoInputs(a, b) => vec![a, b],
        }
    }

    fn flush(&mut self) {
        let batch = std::mem::take(&mut self.pending);
        if batch.is_empty() {
            return;
        }
        // At the top size an operator takes its answer from its key, and no result
        // reads its schema; the checker reads one term per key.
        let mut keys: Vec<Option<u128>> = Vec::with_capacity(batch.len());
        for pending in &batch {
            keys.push(self.answer_key(&pending.term.rel, &Builder::children_of(pending.family)));
        }
        let mut ask: Vec<usize> = Vec::new();
        let mut asked: BTreeSet<u128> = BTreeSet::new();
        for (at, key) in keys.iter().enumerate() {
            match key {
                Some(key) if self.answers.contains_key(key) => self.answered += 1,
                Some(key) => {
                    if asked.insert(*key) {
                        ask.push(at);
                    } else {
                        self.answered += 1;
                    }
                }
                None => ask.push(at),
            }
        }
        let refs: Vec<&Rel> = ask.iter().map(|at| &batch[*at].term.rel).collect();
        self.checked += refs.len() as u64;
        if self.checked % (BATCH as u64 * 16) < refs.len() as u64 {
            self.host.clear_check_cache();
        }
        let checks = if refs.is_empty() { Vec::new() } else { self.host.check_terms(&refs) };
        let mut held: FastMap<usize, TermCheck> = FastMap::default();
        for (at, check) in ask.iter().zip(checks) {
            let accepted = check.is_ok();
            if let Some(key) = keys[*at] {
                self.answers.insert(key, accepted);
            }
            if let Ok(check) = check {
                held.insert(*at, check);
            }
        }
        // The columns of each term, its types, and at a lower size its frames.
        let mut compiled: Vec<(Pending, Vec<String>, Vec<ValueType>)> = Vec::new();
        for (at, pending) in batch.into_iter().enumerate() {
            let keyed = keys[at].is_some();
            let check = match held.remove(&at) {
                Some(check) if !keyed => check,
                found => {
                    let accepted = found.is_some() || keys[at].and_then(|key| self.answers.get(&key).copied()).unwrap_or(false);
                    if !accepted {
                        self.table.refused += 1;
                        continue;
                    }
                    // The types the expansion gives: an answer has no types of its own.
                    let columns: Vec<String> = pending.term.columns.iter().map(|column| column.name.clone()).collect();
                    let types: Option<Vec<ValueType>> = pending.term.columns.iter().map(|column| column.ty.clone()).collect();
                    match types {
                        Some(types) => compiled.push((pending, columns, types)),
                        None => self.table.no_native.push(format!("{}: a column with no type", pending.term.rel)),
                    }
                    continue;
                }
            };
            let columns: Vec<String> = pending.term.columns.iter().map(|column| column.name.clone()).collect();
            match aligned(&columns, &check) {
                Some(types) => compiled.push((pending, columns, types)),
                None => self.table.no_native.push(format!("{}: columns {columns:?} against {:?}", pending.term.rel, check.row_names)),
            }
        }
        let frames: Vec<Vec<bool>> = if self.top {
            vec![Vec::new(); compiled.len()]
        } else {
            let probes: Vec<(&Rel, &[String], &[ValueType])> = compiled.iter().map(|(pending, columns, types)| (&pending.term.rel, &columns[..], &types[..])).collect();
            self.frames_of(&probes)
        };
        for ((pending, columns, types), frames) in compiled.into_iter().zip(frames) {
            let (children, mirrored, self_first) = match pending.family {
                Family::Unary(a) => (vec![a], false, true),
                Family::Binary(a, b) => {
                    let (mirrored, self_first) = mirror_of(&pending.term.rel);
                    (vec![a, b], mirrored, self_first)
                }
                Family::TwoInputs(a, b) => (vec![a, b], false, true),
            };
            let reps: Vec<Typed> = children.iter().map(|child| self.table.schemas[*child as usize].rep.clone()).collect();
            let rep_types: Vec<Vec<ValueType>> = children.iter().map(|child| self.table.schemas[*child as usize].types.clone()).collect();
            let rep_refs: Vec<&Typed> = reps.iter().collect();
            let type_refs: Vec<&[ValueType]> = rep_types.iter().map(|types| &types[..]).collect();
            let step = match self.compile(&pending.term.rel, &rep_refs, &type_refs) {
                Ok(step) => step,
                Err(message) => {
                    self.table.no_native.push(format!("{}: {message}", pending.term.rel));
                    continue;
                }
            };
            let types = if self.top { types } else { narrowed(&step, &rep_types, types, &pending.term.rel) };
            let result = if self.top { NO_SCHEMA } else { self.schema_of(&pending.term, types.clone(), &frames) };
            let invariant: Vec<u16> = types.iter().enumerate().filter(|(_, ty)| invariant_type(ty)).map(|(at, _)| at as u16).collect();
            let names: Vec<bool> = if types.contains(&ValueType::LibName) { types.iter().map(|ty| *ty == ValueType::LibName).collect() } else { Vec::new() };
            let roots = roots_of(invariant.len()) as u32;
            let key = (invariant, names);
            let invariant = match self.table.invariant_index.get(&key) {
                Some(found) => *found,
                None => {
                    let held = self.table.invariants.len() as u32;
                    self.table.invariants.push(key.clone());
                    self.table.invariant_index.insert(key, held);
                    held
                }
            };
            let at = self.table.entries.len() as u32;
            let meta = (!self.top || self.keep_terms).then(|| Box::new(EntryMeta { term: stripped(pending.term.rel), children, columns, types }));
            let tier = match &step {
                Step::Component { instance, .. } => component_tier(&self.table.shapes[self.table.instances[*instance as usize].shape as usize].name),
                _ => 0,
            };
            self.table.entries.push(Entry { step, result, invariant, roots, meta, mirrored, self_first, tier });
            match pending.family {
                Family::Unary(a) => self.table.unary.entry(a).or_default().push(at),
                Family::Binary(a, b) => self.table.binary.entry((a, b)).or_default().push(at),
                Family::TwoInputs(a, b) => self.table.two_inputs.entry((a, b)).or_default().push(at),
            }
        }
        if self.log_every.elapsed().as_secs() >= 30 {
            self.log_every = std::time::Instant::now();
            eprintln!("op table: {} entries, {} schemas, {} refused, {} with no native form, {} read by the checker, {} answered by a key", self.table.entries.len(), self.table.schemas.len(), self.table.refused, self.table.no_native.len(), self.checked, self.answered);
        }
    }

    /// The position of the column `name` of `child`.
    fn position(child: &Typed, name: &str) -> Result<u16, String> {
        child.columns.iter().position(|column| column.name == name).map(|at| at as u16).ok_or_else(|| format!("no column `{name}`"))
    }

    fn compile(&mut self, rel: &Rel, children: &[&Typed], types: &[&[ValueType]]) -> Result<Step, String> {
        let at = |child: usize, name: &str| Builder::position(children[child], name);
        match rel {
            Rel::Project(_, columns) => {
                let columns: Result<Box<[u16]>, String> = columns.iter().map(|name| at(0, name)).collect();
                Ok(Step::Project { columns: columns? })
            }
            Rel::Select(_, column, op, operand) => {
                let first = at(0, column)?;
                match (op, operand) {
                    (Op::Eq, Operand::Column(other)) => {
                        let second = at(0, other)?;
                        Ok(Step::Select { at: first, op: *op, other: Some(second), drop: (second != first).then_some(second) })
                    }
                    (Op::Eq, Operand::Zero) => Ok(Step::Select { at: first, op: *op, other: None, drop: Some(first) }),
                    (_, Operand::Column(other)) => Ok(Step::Select { at: first, op: *op, other: Some(at(0, other)?), drop: None }),
                    (_, Operand::Zero) => Ok(Step::Select { at: first, op: *op, other: None, drop: None }),
                }
            }
            Rel::Join(_, _, pairs) => {
                let (left, right) = pair_positions(pairs, &at)?;
                let kept: Box<[u16]> = (0..children[1].columns.len() as u16).filter(|column| !right.contains(column)).collect();
                Ok(Step::Join { left, right, kept, left_arity: children[0].columns.len() as u16 })
            }
            Rel::Antijoin(_, _, pairs) => {
                let (left, right) = pair_positions(pairs, &at)?;
                Ok(Step::Antijoin { left, right })
            }
            Rel::Union(_, _, pairs) => {
                let mut map: Vec<Option<u16>> = vec![None; children[0].columns.len()];
                for (l, operand) in pairs {
                    let place = at(0, l)?;
                    map[usize::from(place)] = match operand {
                        Operand::Column(r) => Some(at(1, r)?),
                        Operand::Zero => None,
                    };
                }
                Ok(Step::Union { map: map.into_boxed_slice() })
            }
            Rel::LibJoin(_, name, bindings) => {
                let relation = self.lib(name)?;
                let lib_name = LibName(name.as_str().into());
                let columns = match Registry::get().entry(&lib_name) {
                    Some(arclog::registry::LibEntry::Relation(relation) | arclog::registry::LibEntry::Macro(arclog::registry::Macro::Relation { relation, .. })) => &relation.columns,
                    _ => return Err(format!("`{name}` is no lib relation")),
                };
                let mut bound: Vec<Option<u16>> = Vec::with_capacity(columns.len());
                for column in columns.iter() {
                    let own = spelled(&column.name);
                    bound.push(match bindings.iter().find(|(lib, _)| *lib == own) {
                        Some((_, name)) => Some(at(0, name)?),
                        None => None,
                    });
                }
                Ok(Step::LibJoin { relation, bound: bound.into_boxed_slice(), left_arity: children[0].columns.len() as u16 })
            }
            Rel::Component(name, bindings, port) => self.compile_component(name, bindings, port, children, types),
            other => Err(format!("{other} has no native form")),
        }
    }

    fn compile_component(&mut self, name: &str, bindings: &[Binding], port: &str, children: &[&Typed], types: &[&[ValueType]]) -> Result<Step, String> {
        let registry = Registry::get();
        let held = component(registry, &LibName(name.into())).ok_or_else(|| format!("`{name}` is no component"))?;
        let construction = arclog_constructions::shared()?.get(&LibName(name.into())).ok_or_else(|| format!("`{name}` has no construction"))?;
        let port_at = held.outputs.iter().position(|output| output.name.0.as_ref() == port).ok_or_else(|| format!("`{name}` has no output `{port}`"))?;
        // What each binding reads, in the order of the component's inputs.
        let mut parameters: Vec<(String, Vec<(String, ValueType)>)> = Vec::new();
        let mut key_types: Vec<ValueType> = Vec::new();
        let mut bound: Vec<(usize, BoundInput)> = Vec::new();
        for (child, binding) in bindings.iter().enumerate() {
            let input_at = held.inputs.iter().position(|input| input.port.name.0.as_ref() == binding.input).ok_or_else(|| format!("`{name}` has no input `{}`", binding.input))?;
            let input = &held.inputs[input_at];
            let mut positions: Vec<Option<u16>> = Vec::new();
            for column in &binding.key {
                let place = Builder::position(children[child], column)?;
                positions.push(Some(place));
            }
            if key_types.is_empty() {
                key_types = positions.iter().flatten().map(|place| types[child][usize::from(*place)].clone()).collect();
            }
            for (column, fields) in input_fields(input, binding)? {
                let mut labels: Vec<(String, ValueType)> = Vec::new();
                for field in &fields {
                    if field == ZERO_FIELD {
                        positions.push(None);
                        let ty = match &column.ty {
                            ColumnType::Parameter(parameter) => parameter.bound.clone(),
                            other => other.fixed().cloned(),
                        }.ok_or("a field `0` at a column with no type")?;
                        labels.push(("Z".to_string(), ty));
                    } else {
                        let place = Builder::position(children[child], field)?;
                        positions.push(Some(place));
                        labels.push((label_of(field), types[child][usize::from(place)].clone()));
                    }
                }
                if let ColumnType::Parameter(parameter) = &column.ty {
                    if !parameters.iter().any(|(held, _)| **held == *parameter.name) {
                        parameters.push((parameter.name.to_string(), labels));
                    }
                }
            }
            bound.push((input_at, BoundInput { input: input_at as u8, child: child as u8, positions: positions.into_boxed_slice() }));
        }
        bound.sort_by_key(|(input_at, _)| *input_at);
        let key_width = bindings.iter().map(|binding| binding.key.len()).max().unwrap_or(0);
        let column_types = |column: &arclog::registry::Column| -> Result<(Vec<ValueType>, ValueType), String> {
            match &column.ty {
                ColumnType::Parameter(parameter) => match parameters.iter().find(|(held, _)| **held == *parameter.name) {
                    Some((_, fields)) => {
                        let types: Vec<ValueType> = fields.iter().map(|(_, ty)| ty.clone()).collect();
                        let whole = match &fields[..] {
                            [(_, one)] => one.clone(),
                            fields => ValueType::Record(fields.iter().map(|(name, ty)| (ColumnName::Written(name.as_str().into()), ty.clone())).collect()),
                        };
                        Ok((types, whole))
                    }
                    None => match &parameter.bound {
                        Some(bound) => Ok((vec![bound.clone()], bound.clone())),
                        None => Ok((Vec::new(), ValueType::Record(Box::new([])))),
                    },
                },
                other => {
                    let ty = other.fixed().cloned().ok_or("a column with no type of its own")?;
                    Ok((vec![ty.clone()], ty))
                }
            }
        };
        let mut inputs: Vec<InputShape> = Vec::with_capacity(held.inputs.len());
        let session = arclog::decode::corpus::corpus_session();
        for (input_at, input) in held.inputs.iter().enumerate() {
            let mut flat = Vec::new();
            let mut whole = Vec::new();
            let mut per_column: Vec<Vec<ValueType>> = Vec::new();
            for column in input.port.columns.iter().filter(|column| !is_key(column)) {
                let (own, one) = column_types(column)?;
                flat.extend(own.iter().cloned());
                per_column.push(own);
                whole.push(one);
            }
            let binding = bound.iter().find(|(at, _)| *at == input_at);
            let fill = if binding.is_some() {
                InputFill::Bound { keyed: !bindings.iter().find(|own| own.input == input.port.name.0.as_ref()).is_none_or(|own| own.key.is_empty()) }
            } else if let Some(default) = &input.default {
                let mut intern = session.intern.write().expect("an intern table that no panic poisoned");
                let rows = default.rows(&flat, registry, &mut intern).map_err(|error| format!("the default rows of `{}` do not read: {error:?}", input.port.name.0))?;
                let mut rows: Vec<Box<[arclog::terms::TermId]>> = rows.into_iter().collect();
                rows.sort_by_key(|row| row.iter().map(|cell| cell.encoding()).collect::<Vec<_>>());
                InputFill::Rows(rows)
            } else if input.from_key && input.port.columns.iter().any(is_key) && key_width > 0 {
                match key_fill(&key_types, per_column.iter().map(Vec::as_slice)) {
                    Some(places) => InputFill::FromKey(places),
                    None => InputFill::Rows(Vec::new()),
                }
            } else {
                InputFill::Rows(Vec::new())
            };
            inputs.push(InputShape { fill, types: flat.into_boxed_slice(), columns: whole.into_boxed_slice() });
        }
        let mut outputs: Vec<(usize, bool)> = Vec::with_capacity(held.outputs.len());
        for output in held.outputs.iter() {
            let mut width = 0;
            for column in output.columns.iter().filter(|column| !is_key(column)) {
                width += column_types(column)?.0.len();
            }
            outputs.push((width, output.columns.iter().any(is_key)));
        }
        // Two instances with equal shapes on equal rows give equal rows.
        let mut text = format!("{name}|{key_width}|");
        for input in &inputs {
            text.push_str(&format!("{:?};{:?};", input.fill, input.types.iter().map(ValueType::without_source).collect::<Vec<_>>()));
        }
        let key = crate::native::hash_words(text.bytes().map(u64::from));
        let shape = match self.table.shape_index.get(&key) {
            Some(found) => *found,
            None => {
                let at = self.table.shapes.len() as u32;
                self.table.shapes.push(CompShape { code: key as u64, name: name.to_string(), construction, inputs, key_width, outputs });
                self.table.shape_index.insert(key, at);
                at
            }
        };
        let instance = CompInstance { shape, bound: bound.into_iter().map(|(_, bound)| bound).collect() };
        let at = match self.table.instance_index.get(&instance) {
            Some(found) => *found,
            None => {
                let at = self.table.instances.len() as u32;
                self.table.instances.push(instance.clone());
                self.table.instance_index.insert(instance, at);
                at
            }
        };
        Ok(Step::Component { instance: at, port: port_at as u16 })
    }

    fn unary_of(&mut self, schema: u32) {
        if !self.done.insert((0, schema, 0)) {
            return;
        }
        let rep = self.table.schemas[schema as usize].rep.clone();
        let space = self.space.take().expect("the space between two walks");
        let _ = space.unary_of(&rep, &mut |term| {
            self.visit(Family::Unary(schema), term);
            ControlFlow::Continue(())
        });
        let _ = space.components_of(&[&rep], &mut |term| {
            self.visit(Family::Unary(schema), term);
            ControlFlow::Continue(())
        });
        self.space = Some(space);
        self.table.unary.entry(schema).or_default();
    }

    fn binary_of(&mut self, a: u32, b: u32) {
        if !self.done.insert((2, a, b)) {
            return;
        }
        let left = self.table.schemas[a as usize].rep.clone();
        let right = self.table.schemas[b as usize].rep.clone();
        let space = self.space.take().expect("the space between two walks");
        let _ = space.binary_of(&left, &right, &mut |term| {
            self.visit(Family::Binary(a, b), term);
            ControlFlow::Continue(())
        });
        self.space = Some(space);
        self.table.binary.entry((a, b)).or_default();
    }

    fn two_inputs_of(&mut self, a: u32, b: u32) {
        if !self.done.insert((3, a, b)) {
            return;
        }
        let left = self.table.schemas[a as usize].rep.clone();
        let right = self.table.schemas[b as usize].rep.clone();
        let space = self.space.take().expect("the space between two walks");
        let _ = space.components_of(&[&left, &right], &mut |term| {
            self.visit(Family::TwoInputs(a, b), term);
            ControlFlow::Continue(())
        });
        self.space = Some(space);
        self.table.two_inputs.entry((a, b)).or_default();
    }
}

/// The lower of two types, where one stands under the other.
fn lower_of(a: &ValueType, b: &ValueType) -> Option<ValueType> {
    if a.is_below(b) {
        Some(a.clone())
    } else if b.is_below(a) {
        Some(b.clone())
    } else {
        None
    }
}

/// `types`, the types of `step`'s columns as the expansion writes them, with each
/// label at the lowest type of its sites, as the checker gives it: a `lib-join`'s bound
/// column, and a pair's or a `select`'s two columns. `rel` names the lib relation.
fn narrowed(step: &Step, children: &[Vec<ValueType>], mut types: Vec<ValueType>, rel: &Rel) -> Vec<ValueType> {
    match (step, rel) {
        (Step::LibJoin { bound, .. }, Rel::LibJoin(_, name, _)) => {
            if let Some(arclog::registry::LibEntry::Relation(relation) | arclog::registry::LibEntry::Macro(arclog::registry::Macro::Relation { relation, .. })) = Registry::get().entry(&LibName(name.as_str().into())) {
                for (column, at) in relation.columns.iter().zip(bound.iter()) {
                    if let (Some(at), Some(ty)) = (at, column.ty.fixed()) {
                        if let Some(lower) = types.get(usize::from(*at)).and_then(|held| lower_of(held, ty)) {
                            types[usize::from(*at)] = lower;
                        }
                    }
                }
            }
        }
        (Step::Join { left, right, .. }, _) => {
            for (l, r) in left.iter().zip(right.iter()) {
                if let Some(ty) = children.get(1).and_then(|own| own.get(usize::from(*r))) {
                    if let Some(lower) = types.get(usize::from(*l)).and_then(|held| lower_of(held, ty)) {
                        types[usize::from(*l)] = lower;
                    }
                }
            }
        }
        (Step::Select { at, other: Some(other), drop: Some(_), .. }, _) => {
            if let (Some(a), Some(b)) = (children[0].get(usize::from(*at)), children[0].get(usize::from(*other))) {
                if let Some(lower) = lower_of(a, b) {
                    if let Some(held) = types.get_mut(usize::from(*at)) {
                        *held = lower;
                    }
                }
            }
        }
        _ => {}
    }
    types
}

type ColumnAt<'c> = dyn Fn(usize, &str) -> Result<u16, String> + 'c;

fn pair_positions(pairs: &[(String, String)], at: &ColumnAt<'_>) -> Result<(Box<[u16]>, Box<[u16]>), String> {
    let mut left = Vec::with_capacity(pairs.len());
    let mut right: Vec<u16> = Vec::with_capacity(pairs.len());
    for (l, r) in pairs {
        left.push(at(0, l)?);
        let place = at(1, r)?;
        if right.contains(&place) {
            return Err(format!("the right column `{r}` stands in two pairs"));
        }
        right.push(place);
    }
    Ok((left.into_boxed_slice(), right.into_boxed_slice()))
}

/// Whether `rel`, a `join` or a `union`, gives the same rows with its children
/// swapped, and whether its pairs come first of the two where its children are
/// one relation. A `join` that pairs a left column twice has no such form.
fn mirror_of(rel: &Rel) -> (bool, bool) {
    match rel {
        Rel::Join(_, _, pairs) => {
            let lefts: BTreeSet<&String> = pairs.iter().map(|(l, _)| l).collect();
            if lefts.len() != pairs.len() {
                return (false, true);
            }
            let mut own: Vec<(&String, &String)> = pairs.iter().map(|(l, r)| (l, r)).collect();
            let mut other: Vec<(&String, &String)> = pairs.iter().map(|(l, r)| (r, l)).collect();
            own.sort();
            other.sort();
            (true, own <= other)
        }
        Rel::Union(_, _, pairs) => {
            if pairs.iter().any(|(_, operand)| matches!(operand, Operand::Zero)) {
                return (false, true);
            }
            let mut own: Vec<(String, String)> = pairs.iter().filter_map(|(l, r)| match r {
                Operand::Column(r) => Some((l.clone(), r.clone())),
                Operand::Zero => None,
            }).collect();
            let mut other: Vec<(String, String)> = own.iter().map(|(l, r)| (r.clone(), l.clone())).collect();
            own.sort();
            other.sort();
            (true, own <= other)
        }
        _ => (false, true),
    }
}

/// The op table up to size `d`. At the top size it holds only operators with
/// children that together read what a root reads, since any other term is no root.
pub fn build(host: &Host, mode: Mode, d: usize, keep_terms: bool, max_columns: Option<usize>) -> Result<OpTable, String> {
    build_with(host, mode, d, keep_terms, max_columns, FastMap::default()).map(|(table, _)| table)
}

/// [`build`], starting from the answers `answers` that earlier builds gave, which
/// hold for any schema. It gives the answers it holds at its end.
pub fn build_with(host: &Host, mode: Mode, d: usize, keep_terms: bool, max_columns: Option<usize>, answers: FastMap<u128, bool>) -> Result<(OpTable, FastMap<u128, bool>), String> {
    let registry = Registry::get();
    let table_names = match &mode {
        Mode::Table(name) => vec![name.clone()],
        _ => Vec::new(),
    };
    let no_output = mode == Mode::Scene;
    let required = mode.required();
    let table_mode = matches!(mode, Mode::Table(_));
    let space = Space { registry, tables: host, task_wide: false, table_names, program_relations: false, max_inputs: None, thin: None, no_output, quick: false, max_bound_columns: None };
    let mut builder = Builder { host, space: Some(space), table: OpTable::default(), pending: Vec::new(), done: BTreeSet::new(), top: false, mode, log_every: std::time::Instant::now(), answers, checked: 0, answered: 0, keep_terms };
    let mut members: Vec<BTreeSet<(u32, u8)>> = vec![builder.add_leaves()?.into_iter().collect()];
    for size in 1..=d {
        builder.top = size == d;
        let top = builder.top;
        // No later term reads the names of a term of the top size.
        if let Some(space) = builder.space.as_mut() {
            space.quick = top;
            space.max_bound_columns = if top || table_mode { max_columns } else { None };
        }
        // Below the top size, a table's run needs only terms that read something.
        let keep = |flags: u8| if top { flags & required == required } else { !table_mode || flags != 0 };
        for (schema, flags) in members[size - 1].clone() {
            if keep(flags) {
                builder.unary_of(schema);
            }
        }
        for left in 0..size {
            let right = size - 1 - left;
            for (a, flags_a) in members[left].clone() {
                for (b, flags_b) in members[right].clone() {
                    if keep(flags_a | flags_b) {
                        builder.binary_of(a, b);
                    }
                }
            }
        }
        if size >= 2 {
            for left in 0..=size - 2 {
                let right = size - 2 - left;
                for (a, flags_a) in members[left].clone() {
                    for (b, flags_b) in members[right].clone() {
                        if keep(flags_a | flags_b) {
                            builder.two_inputs_of(a, b);
                        }
                    }
                }
            }
        }
        builder.flush();
        // The schemas of this size, with what a term of each reads.
        if !top {
            let mut next: BTreeSet<(u32, u8)> = BTreeSet::new();
            let table = &builder.table;
            let mut add = |list: Option<&Vec<u32>>, flags: u8| {
                for entry in list.into_iter().flatten() {
                    next.insert((table.entries[*entry as usize].result, flags));
                }
            };
            for (schema, flags) in &members[size - 1] {
                if keep(*flags) {
                    add(table.unary.get(schema), *flags);
                }
            }
            for left in 0..size {
                let right = size - 1 - left;
                for (a, flags_a) in &members[left] {
                    for (b, flags_b) in &members[right] {
                        if keep(*flags_a | *flags_b) {
                            add(table.binary.get(&(*a, *b)), *flags_a | *flags_b);
                        }
                    }
                }
            }
            if size >= 2 {
                for left in 0..=size - 2 {
                    let right = size - 2 - left;
                    for (a, flags_a) in &members[left] {
                        for (b, flags_b) in &members[right] {
                            if keep(*flags_a | *flags_b) {
                                add(table.two_inputs.get(&(*a, *b)), *flags_a | *flags_b);
                            }
                        }
                    }
                }
            }
            members.push(next);
        }
    }
    eprintln!("op table: {} read by the checker, {} answered by a key", builder.checked, builder.answered);
    Ok((builder.table, builder.answers))
}

/// `term` with each child left as `input`: what a child is comes from its schema.
fn stripped(term: Rel) -> Rel {
    let leaf = || Box::new(Rel::Leaf(Leaf::Input));
    match term {
        Rel::Project(_, columns) => Rel::Project(leaf(), columns),
        Rel::Select(_, column, op, operand) => Rel::Select(leaf(), column, op, operand),
        Rel::Join(_, _, pairs) => Rel::Join(leaf(), leaf(), pairs),
        Rel::Antijoin(_, _, pairs) => Rel::Antijoin(leaf(), leaf(), pairs),
        Rel::Union(_, _, pairs) => Rel::Union(leaf(), leaf(), pairs),
        Rel::LibJoin(_, name, bindings) => Rel::LibJoin(leaf(), name, bindings),
        Rel::Component(name, bindings, port) => Rel::Component(name, bindings.into_iter().map(|binding| Binding { relation: Rel::Leaf(Leaf::Input), ..binding }).collect(), port),
        other => other,
    }
}

/// `term`, over `rep`'s relation, with the relation `to` in its place and each of
/// `rep`'s columns under the name of `to`'s column at its place.
pub fn rebased(term: &Rel, reps: &[&Typed], to: &[&Typed]) -> Rel {
    let name_in = |child: usize, name: &String| -> String {
        reps[child].columns.iter().position(|column| column.name == *name).and_then(|at| to[child].columns.get(at)).map_or_else(|| name.clone(), |column| column.name.clone())
    };
    let child = |at: usize| Box::new(to[at].rel.clone());
    match term {
        Rel::Leaf(_) | Rel::Call(..) => term.clone(),
        Rel::Project(_, columns) => Rel::Project(child(0), columns.iter().map(|name| name_in(0, name)).collect()),
        Rel::Select(_, column, op, operand) => Rel::Select(child(0), name_in(0, column), *op, match operand {
            Operand::Column(other) => Operand::Column(name_in(0, other)),
            Operand::Zero => Operand::Zero,
        }),
        Rel::Join(_, _, pairs) => Rel::Join(child(0), child(1), pairs.iter().map(|(l, r)| (name_in(0, l), name_in(1, r))).collect()),
        Rel::Antijoin(_, _, pairs) => Rel::Antijoin(child(0), child(1), pairs.iter().map(|(l, r)| (name_in(0, l), name_in(1, r))).collect()),
        Rel::Union(_, _, pairs) => Rel::Union(child(0), child(1), pairs.iter().map(|(l, operand)| (name_in(0, l), match operand {
            Operand::Column(r) => Operand::Column(name_in(1, r)),
            Operand::Zero => Operand::Zero,
        })).collect()),
        Rel::LibJoin(_, name, bindings) => Rel::LibJoin(child(0), name.clone(), bindings.iter().map(|(lib, column)| (lib.clone(), name_in(0, column))).collect()),
        Rel::Component(name, bindings, port) => Rel::Component(name.clone(), bindings.iter().enumerate().map(|(at, binding)| Binding {
            input: binding.input.clone(),
            relation: to[at].rel.clone(),
            key: binding.key.iter().map(|column| name_in(at, column)).collect(),
            fields: binding.fields.iter().map(|field| match field {
                Field::One(own) => Field::One(name_in(at, own)),
                Field::Record(own) => Field::Record(own.iter().map(|column| name_in(at, column)).collect()),
                Field::Zero => Field::Zero,
            }).collect(),
        }).collect(), port.clone()),
    }
}
