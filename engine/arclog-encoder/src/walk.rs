//! The bottom-up walk over classes of relations on one task: a class is a schema
//! and the rows at each grid, and each operator extends one member of a class, so
//! the cost follows the distinct relations the task has, and not the names that
//! write them. A root's class is its vector of values over the grids.

use std::time::Instant;

use arclog::decode::corpus::corpus_session;
use arclog::eval::join::each_row;
use arclog::program::FactRelation;
use arclog::task::Task;
use arclog::terms::{Example, TermId};
use arclog::types::ValueType;

use crate::expression::Rel;
use crate::enumerate::Typed;
use crate::native::{hash_words, Cell, Evaluator, FastMap, Step, Table, Val, WORD_COUNT, WORD_NONEMPTY, WORD_SET};
use crate::optable::{rebased, Entry, LeafKind, OpTable};
use crate::run::Host;

const NONE_VALUE: u32 = 0;
const EMPTY_VALUE: u32 = 1;
const NO_CHILD: u32 = u32::MAX;
const PAYLOAD: u64 = (1 << 62) - 1;

struct Class {
    schema: u32,
    vec: u32,
    /// Whether a term of this class is a root, and the class's first size.
    root: bool,
    size: u8,
    rep: Option<Typed>,
}

/// What a run of the walk gives.
pub struct WalkResult {
    pub grids: usize,
    /// A row per class of roots, a column per grid.
    pub words: Vec<u64>,
    /// The first size of each class of roots.
    pub sizes: Vec<u8>,
    pub classes_by_size: Vec<usize>,
    pub edges: u64,
    pub evaluations: u64,
    pub component_runs: u64,
    pub seconds: f64,
    pub timed_out: bool,
    /// The operators of the top size in their walk's order, and how many ran.
    pub top_edges: u64,
    pub top_done: u64,
    /// The count of those operators in each tier.
    pub tier_edges: Vec<u64>,
    /// For each class of roots, the operator of the walk's order that first gave
    /// it; below the top size, 0.
    pub order: Vec<u32>,
    /// For each shape of component that ran: its name, its runs and its seconds.
    pub shape_time: Vec<(String, u64, f64)>,
    /// The seconds of the sizes below the top, and the operators that a count
    /// answered and that built their rows.
    pub lower_seconds: f64,
    pub counted: u64,
    pub built: u64,
}

/// What a slice of a walk starts from: what an earlier slice wrote.
#[derive(Default)]
pub struct Resume {
    pub words: Vec<u64>,
    pub sizes: Vec<u8>,
    pub order: Vec<u32>,
    pub top_done: u64,
}

/// What the comparison with the engine found.
#[derive(Default, Debug, Clone)]
pub struct CheckTally {
    pub compared: u64,
    pub equal: u64,
    pub skipped_large: u64,
    pub stopped_either: u64,
    pub different: u64,
    pub refused: u64,
    pub fault: u64,
    pub examples: Vec<String>,
}

/// A comparison of sampled operators with the engine's evaluation.
pub struct Checker<'h> {
    pub host: &'h Host,
    pub rate_per_million: u64,
    pub tally: CheckTally,
    /// How many operators of each kind stood in the sample, by the step's kind.
    pub by_kind: FastMap<u8, u64>,
}

fn step_kind(step: &Step) -> u8 {
    match step {
        Step::Project { .. } => 0,
        Step::Select { .. } => 1,
        Step::Join { .. } => 2,
        Step::Antijoin { .. } => 3,
        Step::Union { .. } => 4,
        Step::LibJoin { .. } => 5,
        Step::Component { .. } => 6,
    }
}

struct Walk<'a, 'h> {
    table: &'a OpTable,
    eval: Evaluator<'a>,
    grids: usize,
    values: Vec<Val>,
    value_index: FastMap<u128, u32>,
    vecs: Vec<Box<[u32]>>,
    vec_index: FastMap<u128, u32>,
    all_empty: u32,
    classes: Vec<Class>,
    class_index: FastMap<(u32, u32), u32>,
    by_size: Vec<Vec<u32>>,
    memo: FastMap<(u32, u32, u32, u32), u32>,
    top_memo: FastMap<(u32, u32, u32, u32), u32>,
    arena: Vec<u64>,
    word_memo: FastMap<(u32, u32), u32>,
    invariants: FastMap<u128, u32>,
    root_index: FastMap<u128, u32>,
    words: Vec<u64>,
    sizes: Vec<u8>,
    order: Vec<u32>,
    /// The place in the top size's order of the operator that runs.
    current: u32,
    edges: u64,
    evaluations: u64,
    checker: Option<Checker<'h>>,
    deadline: Option<Instant>,
    timed_out: bool,
}

fn hash_vec(values: &[u32]) -> u128 {
    hash_words(values.iter().map(|value| u64::from(*value)))
}

fn sample_hit(rate: u64, op: u32, a: u32, b: u32, c: u32) -> bool {
    let word = hash_words([u64::from(op), u64::from(a), u64::from(b), u64::from(c), 0x5eed]) as u64;
    word % 1_000_000 < rate
}

impl<'a, 'h> Walk<'a, 'h> {
    fn value_id(&mut self, value: Val) -> u32 {
        match value {
            Val::None => NONE_VALUE,
            Val::Empty => EMPTY_VALUE,
            Val::Rows(_) => {
                let hash = value.hash();
                if let Some(found) = self.value_index.get(&hash) {
                    return *found;
                }
                let at = self.values.len() as u32;
                self.values.push(value);
                self.value_index.insert(hash, at);
                at
            }
        }
    }

    fn vec_id(&mut self, values: &[u32]) -> u32 {
        let hash = hash_vec(values);
        if let Some(found) = self.vec_index.get(&hash) {
            return *found;
        }
        let at = self.vecs.len() as u32;
        self.vecs.push(values.into());
        self.vec_index.insert(hash, at);
        at
    }

    /// Adds the roots whose words the rows of `offsets` give, each `count` long.
    fn register(&mut self, offsets: &[u32], count: usize, size: u8) {
        for root in 0..count {
            let hash = hash_words(offsets.iter().map(|offset| self.arena[*offset as usize + root]));
            if !self.root_index.contains_key(&hash) {
                let at = self.sizes.len() as u32;
                self.root_index.insert(hash, at);
                for offset in offsets {
                    self.words.push(self.arena[*offset as usize + root]);
                }
                self.sizes.push(size);
                self.order.push(self.current);
            }
        }
    }

    /// The offset in the arena of the words of `value` at the columns of
    /// `invariant`.
    fn value_words(&mut self, value: u32, invariant: &[u16], names: &[bool]) -> u32 {
        let signature = hash_words(invariant.iter().map(|at| u64::from(*at)).chain(names.iter().enumerate().filter(|(_, name)| **name).map(|(at, _)| 1 << 32 | at as u64)));
        let next = self.invariants.len() as u32;
        let id = *self.invariants.entry(signature).or_insert(next);
        if let Some(found) = self.word_memo.get(&(value, id)) {
            return *found;
        }
        let at = self.arena.len() as u32;
        let held = self.values[value as usize].clone();
        self.eval.words(&held, invariant, names, &mut self.arena);
        self.word_memo.insert((value, id), at);
        at
    }

    fn register_class(&mut self, class: u32, size: u8) {
        let (schema, vec) = {
            let held = &self.classes[class as usize];
            (held.schema, held.vec)
        };
        let table = self.table;
        let held = &table.schemas[schema as usize];
        let count = crate::optable::roots_of(held.invariant.len());
        let values = self.vecs[vec as usize].clone();
        let mut offsets = Vec::with_capacity(values.len());
        for value in values.iter() {
            offsets.push(self.value_words(*value, &held.invariant, &held.names));
        }
        self.register(&offsets, count, size);
    }

    fn add_class(&mut self, schema: u32, vec: u32, size: u8, root: bool, rep: Option<Typed>) {
        match self.class_index.get(&(schema, vec)) {
            Some(found) => {
                let found = *found;
                if root && !self.classes[found as usize].root {
                    self.classes[found as usize].root = true;
                    self.register_class(found, size);
                }
            }
            None => {
                let at = self.classes.len() as u32;
                self.classes.push(Class { schema, vec, root, size, rep });
                self.class_index.insert((schema, vec), at);
                if self.by_size.len() <= usize::from(size) {
                    self.by_size.resize(usize::from(size) + 1, Vec::new());
                }
                self.by_size[usize::from(size)].push(at);
                if root {
                    self.register_class(at, size);
                }
            }
        }
    }

    /// The operator `op` on the classes `children`, at the size `size`.
    fn edge(&mut self, op: u32, children: &[u32], size: u8, top: bool) {
        let table = self.table;
        let entry: &'a Entry = &table.entries[op as usize];
        let root = children.iter().any(|child| self.classes[*child as usize].root);
        if top && !root {
            return;
        }
        self.edges += 1;
        let vecs: Vec<u32> = children.iter().map(|child| self.classes[*child as usize].vec).collect();
        let check = self.checker.as_ref().is_some_and(|checker| sample_hit(checker.rate_per_million, op, vecs[0], vecs.get(1).copied().unwrap_or(NO_CHILD), 0));
        // Emptiness: an operator that is empty on an empty relation needs no run.
        let empty = !check && (entry.step.empty_on_empty() && vecs[0] == self.all_empty || matches!(entry.step, Step::Join { .. }) && vecs.get(1) == Some(&self.all_empty));
        if empty {
            if top {
                self.register_defaults(entry.roots as usize, size);
            } else {
                let rep = self.rep_of(entry, children);
                let vec = self.all_empty;
                self.add_class(entry.result, vec, size, root, rep);
            }
            return;
        }
        let first = self.vecs[vecs[0] as usize].clone();
        let second = vecs.get(1).map(|vec| self.vecs[*vec as usize].clone());
        if top {
            let count = entry.roots as usize;
            let (invariant, names) = &table.invariants[entry.invariant as usize];
            let mut offsets: Vec<u32> = Vec::with_capacity(self.grids);
            for grid in 0..self.grids {
                let a = first[grid];
                let b = second.as_ref().map_or(NO_CHILD, |second| second[grid]);
                let key = (op, a, b, NO_CHILD);
                let offset = match self.top_memo.get(&key) {
                    Some(found) => *found,
                    None => {
                        let at = self.arena.len() as u32;
                        // A root that only counts needs no rows built.
                        let counted = if count == 2 { self.count_of(entry, a, b) } else { None };
                        match counted {
                            Some(Some(rows)) => {
                                self.arena.push(WORD_NONEMPTY | u64::from(rows > 0));
                                self.arena.push(WORD_COUNT | rows.min(PAYLOAD));
                            }
                            Some(None) => self.arena.extend_from_slice(&[0, 0]),
                            None => {
                                let value = self.apply(entry, a, b);
                                self.eval.words(&value, invariant, names, &mut self.arena);
                            }
                        }
                        self.top_memo.insert(key, at);
                        at
                    }
                };
                offsets.push(offset);
            }
            if check {
                self.compare(entry, children, &first, second.as_deref());
            }
            self.register(&offsets, count, size);
        } else {
            let mut values: Vec<u32> = Vec::with_capacity(self.grids);
            for grid in 0..self.grids {
                let a = first[grid];
                let b = second.as_ref().map_or(NO_CHILD, |second| second[grid]);
                let key = (op, a, b, NO_CHILD);
                let value = match self.memo.get(&key) {
                    Some(found) => *found,
                    None => {
                        let value = self.apply(entry, a, b);
                        let id = self.value_id(value);
                        self.memo.insert(key, id);
                        id
                    }
                };
                values.push(value);
            }
            if check {
                self.compare(entry, children, &first, second.as_deref());
            }
            let vec = self.vec_id(&values);
            let rep = self.rep_of(entry, children);
            self.add_class(entry.result, vec, size, root, rep);
        }
    }

    fn register_defaults(&mut self, count: usize, size: u8) {
        for root in 0..count {
            let word = match root {
                0 => WORD_NONEMPTY,
                1 => WORD_COUNT,
                _ => WORD_SET,
            };
            let hash = hash_words(std::iter::repeat_n(word, self.grids));
            if !self.root_index.contains_key(&hash) {
                let at = self.sizes.len() as u32;
                self.root_index.insert(hash, at);
                self.words.extend(std::iter::repeat_n(word, self.grids));
                self.sizes.push(size);
                self.order.push(self.current);
            }
            if root >= 2 {
                break;
            }
        }
    }

    /// The count of rows of `entry` on the values `a` and `b`, where it needs no rows.
    fn count_of(&mut self, entry: &Entry, a: u32, b: u32) -> Option<Option<u64>> {
        let first = self.values[a as usize].clone();
        let found = if b == NO_CHILD {
            self.eval.count(&entry.step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.count(&entry.step, &[&first, &second])
        };
        if found.is_some() {
            self.eval.counted += 1;
        }
        found
    }

    fn apply(&mut self, entry: &Entry, a: u32, b: u32) -> Val {
        self.evaluations += 1;
        self.eval.built += 1;
        let first = self.values[a as usize].clone();
        if b == NO_CHILD {
            self.eval.apply(&entry.step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.apply(&entry.step, &[&first, &second])
        }
    }

    /// A member of the class `op` gives on `children`, for a comparison.
    fn rep_of(&self, entry: &Entry, children: &[u32]) -> Option<Typed> {
        self.checker.as_ref()?;
        let reps: Vec<&Typed> = entry.meta.as_ref()?.children.iter().map(|schema| &self.table.schemas[*schema as usize].rep).collect();
        let to: Option<Vec<&Typed>> = children.iter().map(|child| self.classes[*child as usize].rep.as_ref()).collect();
        let rel = rebased(&entry.meta.as_ref()?.term, &reps, &to?);
        Some(typed_of(self.checker.as_ref()?.host, rel))
    }

    /// Compares the value of `op` on `children` with the engine's evaluation of a
    /// term that writes it.
    fn compare(&mut self, entry: &Entry, children: &[u32], first: &[u32], second: Option<&[u32]>) {
        let Some(rel) = self.rep_of(entry, children) else { return };
        let values: Vec<Val> = (0..self.grids).map(|grid| {
            let a = first[grid];
            let b = second.map_or(NO_CHILD, |second| second[grid]);
            self.apply(entry, a, b)
        }).collect();
        // The count that builds no rows, read against the rows.
        let counts: Vec<Option<Option<u64>>> = (0..self.grids).map(|grid| {
            let a = first[grid];
            let b = second.map_or(NO_CHILD, |second| second[grid]);
            self.count_of(entry, a, b)
        }).collect();
        let checker = self.checker.as_mut().expect("a comparison has a checker");
        *checker.by_kind.entry(step_kind(&entry.step)).or_default() += 1;
        let outcome = checker.host.evaluate_terms(&[&rel.rel], false).pop().expect("one term");
        let values_outcome = match outcome {
            Ok(values) => values,
            Err(message) => {
                checker.tally.refused += 1;
                if checker.tally.examples.len() < 40 {
                    checker.tally.examples.push(format!("REFUSED {}: {}", rel.rel, message.chars().take(200).collect::<String>()));
                }
                return;
            }
        };
        let meta = entry.meta.as_ref().expect("a comparison keeps its terms");
        let arity = meta.columns.len();
        let names: Vec<String> = rel.columns.iter().map(|column| column.name.clone()).collect();
        let places: Option<Vec<usize>> = names.iter().map(|name| values_outcome.row_names.iter().position(|own| *own == crate::expand::label_of(name) || own == name)).collect();
        let Some(places) = places else {
            checker.tally.fault += 1;
            if checker.tally.examples.len() < 40 {
                checker.tally.examples.push(format!("COLUMNS {}: {names:?} against {:?}", rel.rel, values_outcome.row_names));
            }
            return;
        };
        for (grid, native) in values.iter().enumerate() {
            checker.tally.compared += 1;
            let engine = &values_outcome.examples[grid];
            match (native, engine) {
                (Val::None, None) => {
                    checker.tally.equal += 1;
                }
                (Val::None, Some(_)) | (_, None) => {
                    checker.tally.stopped_either += 1;
                    if checker.tally.examples.len() < 40 && matches!(native, Val::None) != engine.is_none() && !matches!(entry.step, Step::Component { .. }) {
                        checker.tally.examples.push(format!("STOP {} at {grid}: native none {}", rel.rel, matches!(native, Val::None)));
                    }
                }
                (native, Some(engine)) => {
                    if let Some(Some(count)) = counts[grid] {
                        if count != engine.len() {
                            checker.tally.different += 1;
                            if checker.tally.examples.len() < 40 {
                                checker.tally.examples.push(format!("COUNT {} at {grid}: the count {count}, engine {}", rel.rel, engine.len()));
                            }
                            continue;
                        }
                    }
                    const LARGE: u64 = 20_000;
                    if engine.len() > LARGE {
                        checker.tally.skipped_large += 1;
                        continue;
                    }
                    let Some(rows) = native.rows(arity, LARGE as usize) else {
                        checker.tally.different += 1;
                        if checker.tally.examples.len() < 40 {
                            checker.tally.examples.push(format!("COUNT {} at {grid}: engine {}, native past the cap", rel.rel, engine.len()));
                        }
                        continue;
                    };
                    let native_rows: Vec<Vec<TermId>> = rows.iter().map(|row| row.iter().map(|cell| TermId::from_encoding(*cell)).collect()).collect();
                    let mut engine_rows: Vec<Vec<TermId>> = Vec::with_capacity(engine.len() as usize);
                    each_row(engine, &mut |row| engine_rows.push(places.iter().map(|at| row[*at]).collect()));
                    let types: Vec<ValueType> = places.iter().map(|at| values_outcome.types[*at].clone()).collect();
                    let equal = native_rows.len() == engine_rows.len() && crate::law::canonical(&native_rows, &types) == crate::law::canonical(&engine_rows, &types);
                    if equal {
                        checker.tally.equal += 1;
                    } else {
                        checker.tally.different += 1;
                        if checker.tally.examples.len() < 40 {
                            let show = |rows: &Vec<Vec<TermId>>| rows.iter().take(4).map(|row| row.iter().map(|cell| cell.encoding().to_string()).collect::<Vec<_>>().join(",")).collect::<Vec<_>>().join(" ");
                            checker.tally.examples.push(format!("ROWS {} at {grid}: native {} rows [{}], engine {} rows [{}]", rel.rel, native_rows.len(), show(&native_rows), engine_rows.len(), show(&engine_rows)));
                        }
                    }
                }
            }
        }
    }

    /// The operators of the top size, each with its children.
    fn top_edges(&self, size: usize) -> Vec<(u32, u32, u32)> {
        let table = self.table;
        let empty = Vec::new();
        let lower = |at: usize| self.by_size.get(at).unwrap_or(&empty);
        let mut edges = Vec::new();
        for class in lower(size - 1) {
            let held = &self.classes[*class as usize];
            if !held.root {
                continue;
            }
            for op in table.unary.get(&held.schema).into_iter().flatten() {
                edges.push((*op, *class, NO_CHILD));
            }
        }
        for left in 0..size {
            for a in lower(left) {
                let held = &self.classes[*a as usize];
                for b in lower(size - 1 - left) {
                    let other = &self.classes[*b as usize];
                    if !held.root && !other.root {
                        continue;
                    }
                    for op in table.binary.get(&(held.schema, other.schema)).into_iter().flatten() {
                        let entry = &table.entries[*op as usize];
                        if entry.mirrored && (a > b || (a == b && !entry.self_first)) {
                            continue;
                        }
                        edges.push((*op, *a, *b));
                    }
                }
            }
        }
        if size >= 2 {
            for left in 0..=size - 2 {
                for a in lower(left) {
                    let held = &self.classes[*a as usize];
                    for b in lower(size - 2 - left) {
                        let other = &self.classes[*b as usize];
                        if !held.root && !other.root {
                            continue;
                        }
                        for op in table.two_inputs.get(&(held.schema, other.schema)).into_iter().flatten() {
                            edges.push((*op, *a, *b));
                        }
                    }
                }
            }
        }
        edges
    }

    /// Runs the operators of the top size in a seeded order, from `start`, up to
    /// the deadline: a walk cut off holds a fair sample of its operators.
    fn walk_top(&mut self, size: usize, start: u64) -> (u64, u64, Vec<u64>) {
        let edges = self.top_edges(size);
        // Each tier in a seeded order of its own: the cheaper tiers first, and a tier
        // cut off holds a fair sample of its operators.
        let mut tiers: Vec<Vec<(u32, u32, u32)>> = vec![Vec::new(); crate::optable::TIERS];
        for edge in edges {
            tiers[usize::from(self.table.entries[edge.0 as usize].tier)].push(edge);
        }
        let mut state = 0x9e37_79b9_7f4a_7c15u64;
        for tier in &mut tiers {
            for at in (1..tier.len()).rev() {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                tier.swap(at, (state % (at as u64 + 1)) as usize);
            }
        }
        let counts: Vec<u64> = tiers.iter().map(|tier| tier.len() as u64).collect();
        let total: u64 = counts.iter().sum();
        let mut done = start.min(total);
        for (at, (op, a, b)) in tiers.iter().flatten().enumerate().skip(done as usize) {
            if let Some(deadline) = self.deadline {
                if Instant::now() >= deadline {
                    self.timed_out = true;
                    break;
                }
            }
            self.current = at as u32;
            if *b == NO_CHILD {
                self.edge(*op, &[*a], size as u8, true);
            } else {
                self.edge(*op, &[*a, *b], size as u8, true);
            }
            done += 1;
        }
        (total, done, counts)
    }

    fn walk_size(&mut self, size: usize, d: usize) {
        let top = size == d;
        let table = self.table;
        let lower = |by_size: &Vec<Vec<u32>>, at: usize| by_size.get(at).cloned().unwrap_or_default();
        let one = lower(&self.by_size, size - 1);
        for class in &one {
            if let Some(list) = table.unary.get(&self.classes[*class as usize].schema) {
                for op in list {
                    self.edge(*op, &[*class], size as u8, top);
                }
            }
        }
        for left in 0..size {
            let lefts = lower(&self.by_size, left);
            let rights = lower(&self.by_size, size - 1 - left);
            for a in &lefts {
                let schema_a = self.classes[*a as usize].schema;
                let root_a = self.classes[*a as usize].root;
                for b in &rights {
                    if top && !root_a && !self.classes[*b as usize].root {
                        continue;
                    }
                    let Some(list) = table.binary.get(&(schema_a, self.classes[*b as usize].schema)) else { continue };
                    for op in list {
                        let entry = &table.entries[*op as usize];
                        if entry.mirrored && (a > b || (a == b && !entry.self_first)) {
                            continue;
                        }
                        self.edge(*op, &[*a, *b], size as u8, top);
                    }
                }
            }
        }
        if size >= 2 {
            for left in 0..=size - 2 {
                let lefts = lower(&self.by_size, left);
                let rights = lower(&self.by_size, size - 2 - left);
                for a in &lefts {
                    let schema_a = self.classes[*a as usize].schema;
                    let root_a = self.classes[*a as usize].root;
                    for b in &rights {
                        if top && !root_a && !self.classes[*b as usize].root {
                            continue;
                        }
                        let Some(list) = table.two_inputs.get(&(schema_a, self.classes[*b as usize].schema)) else { continue };
                        for op in list {
                            self.edge(*op, &[*a, *b], size as u8, top);
                        }
                    }
                }
            }
        }
    }
}

fn typed_of(host: &Host, rel: Rel) -> Typed {
    let columns = crate::expand::columns_of(&rel, host, arclog::registry::Registry::get(), false).unwrap_or_default();
    let size = rel.size();
    Typed { rel, columns, size }
}

/// The rows of a grid fact at an example.
fn grid_value(task: &Task, fact: FactRelation, example: Example) -> Val {
    let relation = task.fact_rows(fact, Some(example));
    let mut cells: Vec<Cell> = Vec::with_capacity(relation.len() as usize * 2);
    each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
    Val::of_table(Table::new(2, cells))
}

/// The walk up to size `d` on the examples of `task`, each one grid.
pub fn walk(table: &OpTable, task: &Task, d: usize, seconds: Option<f64>, checker: Option<Checker<'_>>, resume: Resume) -> (WalkResult, Option<CheckTally>) {
    let start = Instant::now();
    let grids = task.examples().count();
    let session = corpus_session();
    let mut walk = Walk {
        table,
        eval: Evaluator::new(&table.shapes, &table.instances, &table.libs, session),
        grids,
        values: vec![Val::None, Val::Empty],
        value_index: FastMap::default(),
        vecs: Vec::new(),
        vec_index: FastMap::default(),
        all_empty: 0,
        classes: Vec::new(),
        class_index: FastMap::default(),
        by_size: Vec::new(),
        memo: FastMap::default(),
        top_memo: FastMap::default(),
        arena: Vec::new(),
        word_memo: FastMap::default(),
        invariants: FastMap::default(),
        root_index: FastMap::default(),
        words: Vec::new(),
        sizes: Vec::new(),
        order: Vec::new(),
        current: 0,
        edges: 0,
        evaluations: 0,
        checker,
        deadline: None,
        timed_out: false,
    };
    // What an earlier slice wrote stands first, so a slice only adds to it.
    if grids > 0 {
        for ((row, size), order) in resume.words.chunks_exact(grids).zip(&resume.sizes).zip(&resume.order) {
            let hash = hash_words(row.iter().copied());
            walk.root_index.insert(hash, walk.sizes.len() as u32);
            walk.words.extend_from_slice(row);
            walk.sizes.push(*size);
            walk.order.push(*order);
        }
    }
    walk.all_empty = walk.vec_id(&vec![EMPTY_VALUE; grids]);
    for leaf in &table.leaves {
        let mut values = Vec::with_capacity(grids);
        for example in task.examples() {
            let value = match leaf.kind {
                LeafKind::Input => grid_value(task, FactRelation::Input, example),
                LeafKind::Output => grid_value(task, FactRelation::Output, example),
                LeafKind::Lib(relation) => match walk.eval.lib_table(relation) {
                    Some(table) => Val::of_table(table),
                    None => Val::None,
                },
                LeafKind::Table => Val::None,
            };
            values.push(walk.value_id(value));
        }
        let vec = walk.vec_id(&values);
        let rep = walk.checker.is_some().then(|| leaf.rep.clone());
        walk.add_class(leaf.schema, vec, 0, leaf.root, rep);
    }
    for size in 1..d {
        walk.walk_size(size, d);
    }
    // Only the top size is bounded: the sizes below it are few and each slice needs them.
    let lower_seconds = start.elapsed().as_secs_f64();
    // A slice's seconds are for the top size: the sizes below it run in each slice.
    walk.deadline = seconds.map(|seconds| Instant::now() + std::time::Duration::from_secs_f64(seconds));
    let (top_edges, top_done, tier_edges) = walk.walk_top(d, resume.top_done);
    let shape_time: Vec<(String, u64, f64)> = walk.eval.shape_time.iter().map(|(shape, (runs, seconds))| (table.shapes[*shape as usize].name.clone(), *runs, *seconds)).collect();
    let classes_by_size = walk.by_size.iter().map(Vec::len).collect();
    let tally = walk.checker.take().map(|checker| checker.tally);
    let result = WalkResult {
        grids,
        words: std::mem::take(&mut walk.words),
        sizes: std::mem::take(&mut walk.sizes),
        classes_by_size,
        edges: walk.edges,
        evaluations: walk.evaluations,
        component_runs: walk.eval.runs[0],
        seconds: start.elapsed().as_secs_f64(),
        timed_out: walk.timed_out,
        top_edges,
        top_done,
        tier_edges,
        order: std::mem::take(&mut walk.order),
        shape_time,
        lower_seconds,
        counted: walk.eval.counted,
        built: walk.eval.built,
    };
    (result, tally)
}

