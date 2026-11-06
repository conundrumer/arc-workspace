//! A table's closed roots, keyed by shape: a shape is a ground expression with the
//! table and each of its columns as typed holes, numbered by first appearance, so
//! its name carries over to any table. A shape's value at an example is the multiset
//! of its ground expressions' values there. A shape with no binding, or whose every
//! value is the default, has no entry.
//!
//! The walk is a plain function of the operators of a table's schema, which the
//! engine's checker gives once, and of the rows of the table and the grids.

use std::sync::Arc;

use arclog::decode::corpus::corpus_session;
use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::enumerate::Typed;
use crate::expand::columns_of;
use crate::native::{hash_words, Evaluator, FastMap, Step, Table, Val};
use crate::optable::{rebased, Entry, LeafKind, Mode, OpTable};
use crate::run::Host;

const NO_LEAF: u32 = u32::MAX;
const PAYLOAD: u64 = (1 << 62) - 1;

/// A ground term of size 1 of a schema.
pub struct SmallTerm {
    pub entry: u32,
    pub a: u32,
    pub b: u32,
    pub flags: u8,
    pub schema: u32,
    /// A hash of its shape.
    pub shape: u64,
    /// For each of its columns: the table's column it holds, with the number of
    /// its hole where the term's text names it, or a code of its fixed name.
    pub symbols: Vec<Symbol>,
}

#[derive(Clone, Copy, Debug)]
pub enum Symbol {
    /// A column of the table, and which reading of it: `T0`, or `T0_2`.
    Hole { column: u16, reading: u16 },
    Fixed(u64),
}

/// The operators of a table's schema.
pub struct TableOps {
    pub table: OpTable,
    pub types: Vec<ValueType>,
    pub small: Vec<SmallTerm>,
}

fn type_code(ty: &ValueType) -> u64 {
    hash_words(format!("{:?}", ty.without_source()).bytes().map(u64::from)) as u64
}

fn symbol_of(name: &str) -> Symbol {
    if let Some(rest) = name.strip_prefix('T') {
        let (base, reading) = rest.split_once('_').unwrap_or((rest, "1"));
        if let (Ok(column), Ok(reading)) = (base.parse::<u16>(), reading.parse::<u16>()) {
            return Symbol::Hole { column, reading };
        }
    }
    Symbol::Fixed(hash_words(name.bytes().map(u64::from)) as u64)
}

/// The text of a term with the table `T` and its columns as holes.
pub fn shape_text(text: &str, table: &str, types: &[ValueType]) -> String {
    let mut out = String::with_capacity(text.len());
    let mut numbers: Vec<u16> = Vec::new();
    let mut token = String::new();
    let mut flush = |token: &mut String, out: &mut String| {
        if token.is_empty() {
            return;
        }
        if token == table {
            out.push('T');
        } else if let Symbol::Hole { column, reading } = symbol_of(token) {
            let number = match numbers.iter().position(|held| *held == column) {
                Some(at) => at + 1,
                None => {
                    numbers.push(column);
                    numbers.len()
                }
            };
            let ty = types.get(usize::from(column)).map_or_else(String::new, |ty| format!("{:?}", ty.without_source()));
            out.push_str(&format!("?{number}:{ty}"));
            if reading > 1 {
                out.push_str(&format!("#{reading}"));
            }
        } else {
            out.push_str(token);
        }
        token.clear();
    };
    for ch in text.chars() {
        if ch == ' ' || ch == '(' || ch == ')' {
            flush(&mut token, &mut out);
            out.push(ch);
        } else {
            token.push(ch);
        }
    }
    flush(&mut token, &mut out);
    out
}

/// The operators of the schema `types`, whose table is `table` in `host`, with the
/// small terms over the leaves.
pub fn table_ops(host: &Host, table: &str, types: &[ValueType], d: usize, max_columns: Option<usize>, top_components: bool, answers: FastMap<u128, bool>) -> Result<(TableOps, FastMap<u128, bool>), String> {
    // The small terms read their operators' terms, which the top size keeps only when asked.
    let (held, answers) = crate::optable::build_with(host, Mode::Table(table.to_string()), d, d == 1, max_columns, top_components, answers)?;
    let mut small = Vec::new();
    let registry = Registry::get();
    let mut add = |entry: u32, a: u32, b: u32, flags: u8| {
        let record: &Entry = &held.entries[entry as usize];
        let Some(meta) = &record.meta else { return };
        let reps: Vec<&Typed> = meta.children.iter().map(|schema| &held.schemas[*schema as usize].rep).collect();
        let mut to: Vec<&Typed> = vec![&held.leaves[a as usize].rep];
        if b != NO_LEAF {
            to.push(&held.leaves[b as usize].rep);
        }
        let rel = rebased(&meta.term, &reps, &to);
        let columns = columns_of(&rel, host, registry, false).unwrap_or_default();
        let shape = hash_words(shape_text(&rel.to_string(), table, types).bytes().map(u64::from)) as u64;
        let symbols = columns.iter().map(|column| symbol_of(&column.name)).collect();
        small.push(SmallTerm { entry, a, b, flags, schema: record.result, shape, symbols });
    };
    for (at, leaf) in held.leaves.iter().enumerate() {
        for entry in held.unary.get(&leaf.schema).into_iter().flatten() {
            if leaf.flags != 0 {
                add(*entry, at as u32, NO_LEAF, leaf.flags);
            }
        }
    }
    for (at, leaf) in held.leaves.iter().enumerate() {
        for (other_at, other) in held.leaves.iter().enumerate() {
            if leaf.flags | other.flags == 0 {
                continue;
            }
            for entry in held.binary.get(&(leaf.schema, other.schema)).into_iter().flatten() {
                add(*entry, at as u32, other_at as u32, leaf.flags | other.flags);
            }
        }
    }
    Ok((TableOps { table: held, types: types.to_vec(), small }, answers))
}

/// The value of a shape's root at each pair: a commutative hash of the multiset of
/// its values other than the default, and which pairs hold no value.
#[derive(Clone, Debug)]
pub struct Entry2 {
    pub sums: [u64; 12],
    pub none: u16,
    pub size: u8,
}

pub type ShapeMap = FastMap<u128, Entry2>;

pub fn mix_word(word: u64) -> u64 {
    let mut x = word;
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    x = x.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    x ^ (x >> 33)
}

/// The evaluation of one schema's operators on one task.
pub struct TableEval<'a> {
    ops: &'a TableOps,
    eval: Evaluator<'a>,
    values: Vec<Val>,
    value_index: FastMap<u128, u32>,
    memo: FastMap<(u32, u32, u32), u32>,
    top_memo: FastMap<(u32, u32, u32), u32>,
    arena: Vec<u64>,
    pub evaluations: u64,
}

impl<'a> TableEval<'a> {
    pub fn new(ops: &'a TableOps) -> Self {
        let table = &ops.table;
        TableEval { ops, eval: Evaluator::new(&table.shapes, &table.instances, &table.libs, corpus_session()), values: vec![Val::None, Val::Empty], value_index: FastMap::default(), memo: FastMap::default(), top_memo: FastMap::default(), arena: Vec::new(), evaluations: 0 }
    }

    fn value_id(&mut self, value: Val) -> u32 {
        match value {
            Val::None => 0,
            Val::Empty => 1,
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

    fn apply(&mut self, entry: &Entry, a: u32, b: u32) -> Val {
        self.evaluations += 1;
        let first = self.values[a as usize].clone();
        if b == NO_LEAF {
            self.eval.apply(&entry.step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.apply(&entry.step, &[&first, &second])
        }
    }

    fn values_of(&mut self, op: u32, a: &[u32], b: Option<&[u32]>) -> Vec<u32> {
        let entry = &self.ops.table.entries[op as usize];
        (0..a.len()).map(|pair| {
            let second = b.map_or(NO_LEAF, |b| b[pair]);
            let key = (op, a[pair], second);
            match self.memo.get(&key) {
                Some(found) => *found,
                None => {
                    let value = self.apply(entry, a[pair], second);
                    let id = self.value_id(value);
                    self.memo.insert(key, id);
                    id
                }
            }
        }).collect()
    }

    /// The offset of the words of each pair's value of `op`.
    fn top_words(&mut self, op: u32, a: &[u32], b: Option<&[u32]>) -> Vec<u32> {
        let entry = &self.ops.table.entries[op as usize];
        let (invariant, names) = &self.ops.table.invariants[entry.invariant as usize];
        (0..a.len()).map(|pair| {
            let second = b.map_or(NO_LEAF, |b| b[pair]);
            let key = (op, a[pair], second);
            match self.top_memo.get(&key) {
                Some(found) => *found,
                None => {
                    let value = self.apply(entry, a[pair], second);
                    let at = self.arena.len() as u32;
                    self.eval.words(&value, invariant, names, &mut self.arena);
                    self.top_memo.insert(key, at);
                    at
                }
            }
        }).collect()
    }

    fn accumulate(&self, map: &mut ShapeMap, shape: u64, offsets: &[u32], roots: usize, size: u8) {
        for root in 0..roots {
            let mut active = false;
            for offset in offsets {
                let word = self.arena[*offset as usize + root];
                active |= word == 0 || word & PAYLOAD != 0;
            }
            if !active {
                continue;
            }
            let key = (u128::from(shape) << 16) | root as u128;
            let entry = map.entry(key).or_insert(Entry2 { sums: [0; 12], none: 0, size });
            for (pair, offset) in offsets.iter().enumerate().take(12) {
                let word = self.arena[*offset as usize + root];
                if word == 0 {
                    entry.none |= 1 << pair;
                } else if word & PAYLOAD != 0 {
                    entry.sums[pair] = entry.sums[pair].wrapping_add(mix_word(word));
                }
            }
        }
    }

    /// The sparse map of the table whose rows at each pair are `rows`, with `inputs`
    /// and `outputs` at each pair; operators of the top size only where a shape falls
    /// in the sample of `rate` in a million.
    pub fn walk(&mut self, rows: &[Option<Arc<Table>>], inputs: &[Arc<Table>], outputs: &[Arc<Table>], d: usize, rate: u64) -> ShapeMap {
        let ops = self.ops;
        let table = &ops.table;
        let pairs = rows.len();
        let required = Mode::Table(String::new()).required();
        let mut leaf_values: Vec<Vec<u32>> = Vec::with_capacity(table.leaves.len());
        for leaf in &table.leaves {
            let mut values = Vec::with_capacity(pairs);
            for pair in 0..pairs {
                let value = match leaf.kind {
                    LeafKind::Input => Val::of_table(inputs[pair].clone()),
                    LeafKind::Output => Val::of_table(outputs[pair].clone()),
                    LeafKind::Table => rows[pair].clone().map_or(Val::None, Val::of_table),
                    LeafKind::Lib(relation) => self.eval.lib_table(relation).map_or(Val::None, Val::of_table),
                };
                values.push(self.value_id(value));
            }
            leaf_values.push(values);
        }
        let mut map: ShapeMap = FastMap::default();
        let empty = vec![1u32; pairs];
        let mut small_values: Vec<Vec<u32>> = Vec::with_capacity(ops.small.len());
        for term in &ops.small {
            let values = self.values_of(term.entry, &leaf_values[term.a as usize], (term.b != NO_LEAF).then(|| &leaf_values[term.b as usize][..]));
            if term.flags & required == required {
                let entry = &table.entries[term.entry as usize];
                let (invariant, names) = &table.invariants[entry.invariant as usize];
                let mut offsets = Vec::with_capacity(pairs);
                for value in &values {
                    let at = self.arena.len() as u32;
                    let held = self.values[*value as usize].clone();
                    self.eval.words(&held, invariant, names, &mut self.arena);
                    offsets.push(at);
                }
                self.accumulate(&mut map, term.shape, &offsets, entry.roots as usize, 1);
            }
            small_values.push(values);
        }
        if d < 2 {
            return map;
        }
        let in_sample = |shape: u64| shape % 1_000_000 < rate;
        // Each operator of size 2 over a small term, and over two leaves.
        for (at, term) in ops.small.iter().enumerate() {
            let values = &small_values[at];
            let is_empty = *values == empty;
            if term.flags & required == required {
                for op in table.unary.get(&term.schema).into_iter().flatten() {
                    let entry = &table.entries[*op as usize];
                    if is_empty && entry.step.empty_on_empty() {
                        continue;
                    }
                    let shape = unary_shape(table, entry, term, &ops.types);
                    if in_sample(shape) {
                        let offsets = self.top_words(*op, values, None);
                        self.accumulate(&mut map, shape, &offsets, entry.roots as usize, 2);
                    }
                }
            }
            for (leaf_at, leaf) in table.leaves.iter().enumerate() {
                if (term.flags | leaf.flags) & required != required {
                    continue;
                }
                let leaf_vals = &leaf_values[leaf_at];
                for op in table.binary.get(&(term.schema, leaf.schema)).into_iter().flatten() {
                    let entry = &table.entries[*op as usize];
                    if is_empty && entry.step.empty_on_empty() {
                        continue;
                    }
                    let shape = binary_shape(table, entry, Some(term), None, leaf_at as u32, &ops.types);
                    if in_sample(shape) {
                        let offsets = self.top_words(*op, values, Some(leaf_vals));
                        self.accumulate(&mut map, shape, &offsets, entry.roots as usize, 2);
                    }
                }
                for op in table.binary.get(&(leaf.schema, term.schema)).into_iter().flatten() {
                    let entry = &table.entries[*op as usize];
                    if is_empty && matches!(entry.step, Step::Join { .. }) {
                        continue;
                    }
                    let shape = binary_shape(table, entry, None, Some(term), leaf_at as u32, &ops.types);
                    if in_sample(shape) {
                        let offsets = self.top_words(*op, leaf_vals, Some(values));
                        self.accumulate(&mut map, shape, &offsets, entry.roots as usize, 2);
                    }
                }
            }
        }
        for (a_at, a) in table.leaves.iter().enumerate() {
            for (b_at, b) in table.leaves.iter().enumerate() {
                if (a.flags | b.flags) & required != required {
                    continue;
                }
                for op in table.two_inputs.get(&(a.schema, b.schema)).into_iter().flatten() {
                    let entry = &table.entries[*op as usize];
                    let shape = leaves_shape(table, entry, a_at as u32, b_at as u32, &ops.types);
                    if in_sample(shape) {
                        let offsets = self.top_words(*op, &leaf_values[a_at], Some(&leaf_values[b_at]));
                        self.accumulate(&mut map, shape, &offsets, entry.roots as usize, 2);
                    }
                }
            }
        }
        map
    }
}

/// The holes that a shape's text has named so far, in order.
#[derive(Default)]
struct Numbers(Vec<u16>);

impl Numbers {
    fn code(&mut self, symbol: Symbol, types: &[ValueType]) -> u64 {
        match symbol {
            Symbol::Fixed(code) => code,
            Symbol::Hole { column, reading } => {
                let number = match self.0.iter().position(|held| *held == column) {
                    Some(at) => at + 1,
                    None => {
                        self.0.push(column);
                        self.0.len()
                    }
                };
                (1 << 63) | ((number as u64) << 32) | (u64::from(reading) << 16) ^ type_code(&types[usize::from(column)]) >> 20
            }
        }
    }
}

/// The holes that a small term's text names, in the order of its symbols' first
/// mention: its shape's hash stands for them, so a later hole takes the next number.
fn numbers_of(term: &SmallTerm) -> Numbers {
    let mut numbers = Numbers::default();
    for symbol in &term.symbols {
        if let Symbol::Hole { column, .. } = symbol {
            if !numbers.0.contains(column) {
                numbers.0.push(*column);
            }
        }
    }
    numbers
}

fn step_code(table: &OpTable, step: &Step) -> u64 {
    match step {
        Step::Project { .. } => 11,
        Step::Select { op, other, .. } => 13 + 2 * (*op as u64) + 64 * u64::from(other.is_none()),
        Step::Join { .. } => 17,
        Step::Antijoin { .. } => 19,
        Step::Semijoin { .. } | Step::All { .. } | Step::Part(_) => 19,
        Step::Union { map } => hash_words(map.iter().map(|at| u64::from(at.is_none()))) as u64 ^ 23,
        Step::LibJoin { relation, bound, .. } => table.libs[*relation as usize].code ^ hash_words(bound.iter().map(|at| u64::from(at.is_some()))) as u64,
        Step::Component { instance, port } => {
            let held = &table.instances[*instance as usize];
            table.shapes[held.shape as usize].code ^ (u64::from(*port) << 48)
        }
    }
}

fn unary_shape(table: &OpTable, entry: &Entry, term: &SmallTerm, types: &[ValueType]) -> u64 {
    let mut numbers = numbers_of(term);
    let mut words = vec![term.shape, step_code(table, &entry.step)];
    let mut sym = |at: u16, numbers: &mut Numbers| numbers.code(term.symbols[usize::from(at)], types);
    match &entry.step {
        Step::Project { columns } => {
            for at in columns.iter() {
                words.push(sym(*at, &mut numbers));
            }
        }
        Step::Select { at, other, .. } => {
            words.push(sym(*at, &mut numbers));
            if let Some(other) = other {
                words.push(sym(*other, &mut numbers));
            }
        }
        Step::LibJoin { bound, .. } => {
            for at in bound.iter().flatten() {
                words.push(sym(*at, &mut numbers));
            }
        }
        Step::Component { instance, .. } => {
            for bound in table.instances[*instance as usize].bound.iter() {
                words.push(u64::from(bound.input) + 1000);
                for at in bound.positions.iter() {
                    words.push(at.map_or(7, |at| sym(at, &mut numbers)));
                }
            }
        }
        _ => {}
    }
    hash_words(words) as u64
}

fn leaf_symbols(table: &OpTable, leaf: u32) -> Vec<Symbol> {
    let leaf = &table.leaves[leaf as usize];
    leaf.rep.columns.iter().map(|column| {
        if leaf.kind == LeafKind::Table {
            symbol_of(&column.name)
        } else {
            Symbol::Fixed(hash_words(format!("{}.{}", leaf.rep.rel, column.name).bytes().map(u64::from)) as u64)
        }
    }).collect()
}

fn binary_shape(table: &OpTable, entry: &Entry, left: Option<&SmallTerm>, right: Option<&SmallTerm>, leaf: u32, types: &[ValueType]) -> u64 {
    let leaf_syms = leaf_symbols(table, leaf);
    let leaf_shape = hash_words([u64::from(table.leaves[leaf as usize].flags), hash_words(table.leaves[leaf as usize].rep.rel.to_string().bytes().map(u64::from)) as u64 & if table.leaves[leaf as usize].kind == LeafKind::Table { 0 } else { u64::MAX }]) as u64;
    let (left_syms, right_syms, shapes): (&[Symbol], &[Symbol], [u64; 2]) = match (left, right) {
        (Some(term), _) => (&term.symbols, &leaf_syms, [term.shape, leaf_shape]),
        (_, Some(term)) => (&leaf_syms, &term.symbols, [leaf_shape, term.shape]),
        _ => unreachable!("one child is a small term"),
    };
    let mut numbers = left.or(right).map_or_else(Numbers::default, numbers_of);
    let mut words = vec![shapes[0], shapes[1], step_code(table, &entry.step)];
    match &entry.step {
        Step::Join { left: l, right: r, .. } | Step::Antijoin { left: l, right: r } => {
            for (a, b) in l.iter().zip(r.iter()) {
                words.push(numbers.code(left_syms[usize::from(*a)], types));
                words.push(numbers.code(right_syms[usize::from(*b)], types));
            }
        }
        Step::Union { map } => {
            for (a, b) in map.iter().enumerate() {
                words.push(numbers.code(left_syms[a], types));
                words.push(b.map_or(7, |b| numbers.code(right_syms[usize::from(b)], types)));
            }
        }
        _ => {}
    }
    hash_words(words) as u64
}

fn leaves_shape(table: &OpTable, entry: &Entry, a: u32, b: u32, types: &[ValueType]) -> u64 {
    let syms = [leaf_symbols(table, a), leaf_symbols(table, b)];
    let shape_of = |leaf: u32| hash_words(table.leaves[leaf as usize].rep.rel.to_string().bytes().map(u64::from)) as u64 & if table.leaves[leaf as usize].kind == LeafKind::Table { 0 } else { u64::MAX };
    let mut numbers = Numbers::default();
    let mut words = vec![shape_of(a), shape_of(b), step_code(table, &entry.step)];
    if let Step::Component { instance, .. } = &entry.step {
        for bound in table.instances[*instance as usize].bound.iter() {
            words.push(u64::from(bound.input) + 1000);
            for at in bound.positions.iter() {
                words.push(at.map_or(7, |at| numbers.code(syms[usize::from(bound.child)][usize::from(at)], types)));
            }
        }
    }
    hash_words(words) as u64
}


// ---- Candidate recognition over stored tables. ----

/// A table of a candidate file: its columns ordered by type, named `T0`, `T1`, so no
/// name of it stands in a shape, and its rows at each train pair.
pub struct Stored {
    pub key: String,
    pub types: Vec<ValueType>,
    pub rows: Vec<Option<Arc<Table>>>,
}

pub fn cell_bits(value: &serde_json::Value, ty: &ValueType) -> Option<u32> {
    use arclog::terms::{Color, Constant, Margins, Term, TermId};
    let term = match ty {
        ty if ty.is_box() => {
            let cells = value.as_array()?;
            let margin = |at: usize| cells.get(at).and_then(serde_json::Value::as_i64).map(|margin| margin as i32);
            Term::Box(Margins { top: margin(0)?, bottom: margin(1)?, left: margin(2)?, right: margin(3)? })
        }
        ValueType::Color => Term::Constant(Constant::Color(Color::from_digit(value.as_u64()? as u8)?)),
        ValueType::Int | ValueType::Nat => return Some(Term::encode_number(value.as_i64()? as i32).encoding()),
        ValueType::Ident(_) => {
            let bits = match value {
                serde_json::Value::String(text) => hash_words(text.bytes().map(u64::from)) as u32,
                other => other.as_i64()? as u32,
            };
            return Some(bits);
        }
        _ => Term::Constant(Constant::Orientation(Registry::get().orientation_constant(value.as_str()?)?)),
    };
    term.encode().ok().map(TermId::encoding)
}

/// The table of a candidate file's `value`.
pub fn stored_of(value: &serde_json::Value, train: usize) -> Option<Stored> {
    let names = value["types"].as_array()?;
    let types: Vec<ValueType> = names.iter().map(|name| crate::schema::type_of_name(name.as_str()?)).collect::<Option<_>>()?;
    let mut order: Vec<usize> = (0..types.len()).collect();
    order.sort_by_key(|at| format!("{:?}", types[*at]));
    let sorted: Vec<ValueType> = order.iter().map(|at| types[*at].clone()).collect();
    let mut rows = Vec::with_capacity(train);
    for pair in 0..train {
        let Some(held) = value["rows"].get(format!("train/{pair}")).and_then(serde_json::Value::as_array) else {
            rows.push(None);
            continue;
        };
        let mut cells = Vec::with_capacity(held.len() * order.len());
        for row in held {
            let row = row.as_array()?;
            for at in &order {
                cells.push(cell_bits(row.get(*at)?, &types[*at])?);
            }
        }
        rows.push(Some(if order.is_empty() { Table::unit(!held.is_empty()) } else { Table::distinct(order.len(), cells) }));
    }
    Some(Stored { key: format!("{sorted:?}"), types: sorted, rows })
}

/// The operators of each schema, built on first use, and the checker's answers.
pub struct OpsCache {
    pub d: usize,
    pub max_columns: Option<usize>,
    /// Whether the top size holds components.
    pub top_components: bool,
    ops: std::sync::Mutex<FastMap<u128, (Arc<TableOps>, u64)>>,
    answers: std::sync::Mutex<FastMap<u128, bool>>,
    uses: std::sync::atomic::AtomicU64,
}

impl OpsCache {
    pub fn new(d: usize, max_columns: Option<usize>, top_components: bool) -> Self {
        OpsCache { d, max_columns, top_components, ops: Default::default(), answers: Default::default(), uses: Default::default() }
    }

    /// The operators of the schema of `types`.
    pub fn get(&self, key: &str, types: &[ValueType]) -> Result<Arc<TableOps>, String> {
        let hash = hash_words(key.bytes().map(u64::from));
        let tick = self.uses.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        if let Some(found) = self.ops.lock().expect("no panic").get_mut(&hash) {
            found.1 = tick;
            return Ok(found.0.clone());
        }
        let columns: Vec<crate::schema::TableColumn> = types.iter().enumerate().map(|(at, ty)| crate::schema::TableColumn { name: format!("T{at}"), path: vec![format!("T{at}")], ty: Some(ty.clone()) }).collect();
        let stored = crate::run::StoredRows {
            table: "&t".to_string(),
            stored_name: format!("candidate/{hash:032x}"),
            columns,
            types: types.to_vec(),
            per_input: true,
            has_example: false,
            rows: vec![(Some(arclog::terms::Example::at(0)), Vec::new())],
        };
        let task = crate::closed::task_of_inputs(&[vec![vec![0u8]]])?;
        let host = Host::stored(task, &stored)?;
        let answers = self.answers.lock().expect("no panic").clone();
        let (ops, answers) = table_ops(&host, "&t", types, self.d, self.max_columns, self.top_components, answers)?;
        self.answers.lock().expect("no panic").extend(answers);
        let ops = Arc::new(ops);
        let mut held = self.ops.lock().expect("no panic");
        held.insert(hash, (ops.clone(), tick));
        // The operators of a schema are large, so the cache keeps those used last.
        let total: usize = held.values().map(|(ops, _)| ops.table.entries.len()).sum();
        if total > 3_000_000 {
            let mut order: Vec<(u64, u128)> = held.iter().filter(|(_, (ops, _))| Arc::strong_count(ops) == 1).map(|(key, (_, tick))| (*tick, *key)).collect();
            order.sort_unstable();
            let mut left = total;
            for (_, key) in order {
                if left <= 1_500_000 {
                    break;
                }
                if let Some((ops, _)) = held.remove(&key) {
                    left -= ops.table.entries.len();
                }
            }
        }
        Ok(ops)
    }
}

/// Whether a root has one value at every pair that is not its default.
pub fn active_entry(entry: Option<&Entry2>, pairs: usize) -> bool {
    active(entry, pairs)
}

/// Whether a root has one value at every pair that is not its default: an entry
/// with no pair of no value, and one nonzero hash of its multiset.
fn active(entry: Option<&Entry2>, pairs: usize) -> bool {
    match entry {
        None => false,
        Some(entry) => entry.none == 0 && entry.sums[0] != 0 && entry.sums[..pairs].iter().all(|sum| *sum == entry.sums[0]),
    }
}

/// Which roots a table has as stable.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StableRule {
    /// One value at every pair that is not the root's default.
    Active,
    /// One value at every pair, not no value, on a table with rows at every pair: a
    /// default counts, so an empty table meets nothing vacuously.
    NonVacuous,
}

/// A table's map, and whether it has rows at every pair.
#[derive(Clone, Copy)]
struct Held<'m> {
    map: &'m ShapeMap,
    rows_everywhere: bool,
}

fn holds(rule: StableRule, held: Held<'_>, name: &u128, pairs: usize) -> bool {
    let entry = held.map.get(name);
    match rule {
        StableRule::Active => active(entry, pairs),
        StableRule::NonVacuous => {
            held.rows_everywhere
                && match entry {
                    None => true,
                    Some(entry) => entry.none == 0 && entry.sums[..pairs].iter().all(|sum| *sum == entry.sums[0]),
                }
        }
    }
}

/// An item's scores at size `d`: the count of contingent classes, gold's score, and
/// each mutant's. A contingent root is one that `input` or a table the query reads
/// does not have as stable, and a score is the share of contingent classes stable on
/// the table.
fn item_scores(rule: StableRule, bases: &[Held<'_>], gold: Held<'_>, mutants: &[Held<'_>], pairs: usize, d: u8) -> (usize, f64, Vec<f64>) {
    let every: Vec<Held<'_>> = bases.iter().copied().chain(std::iter::once(gold)).chain(mutants.iter().copied()).collect();
    let mut names: FastMap<u128, ()> = FastMap::default();
    for held in &every {
        for (name, entry) in held.map.iter() {
            if entry.size <= d && !names.contains_key(name) && !bases.iter().all(|base| holds(rule, *base, name, pairs)) {
                names.insert(*name, ());
            }
        }
    }
    let mut classes: FastMap<u128, u128> = FastMap::default();
    for name in names.keys() {
        let mut words: Vec<u64> = Vec::with_capacity(every.len() * (pairs + 2));
        for held in &every {
            match held.map.get(name) {
                Some(entry) => {
                    words.extend_from_slice(&entry.sums[..pairs]);
                    words.push(u64::from(entry.none));
                }
                None => words.extend(std::iter::repeat_n(0, pairs + 1)),
            }
            words.push(u64::from(held.rows_everywhere));
        }
        classes.entry(hash_words(words)).or_insert(*name);
    }
    let contingent: Vec<u128> = classes.values().copied().collect();
    if contingent.is_empty() {
        return (0, 0.0, vec![0.0; mutants.len()]);
    }
    let score = |held: Held<'_>| contingent.iter().filter(|name| holds(rule, held, name, pairs)).count() as f64 / contingent.len() as f64;
    (contingent.len(), score(gold), mutants.iter().map(|held| score(*held)).collect())
}

/// The AUC of `scores`: gold against each mutant, over a task's items.
fn auc_of(scores: &[(usize, f64, Vec<f64>)]) -> Option<f64> {
    let mut sum = 0.0;
    let mut count = 0usize;
    for (_, gold, mutants) in scores {
        for mutant in mutants {
            sum += if gold > mutant { 1.0 } else if gold == mutant { 0.5 } else { 0.0 };
            count += 1;
        }
    }
    (count > 0).then(|| sum / count as f64)
}

/// A file's result: per size, each item's scores, and the null's AUC per draw.
pub fn candidate_task(path: &str, task_dir: &std::path::Path, cache: &OpsCache, rate: u64, nulls: usize, max_table_columns: usize, rule: StableRule) -> Result<serde_json::Value, String> {
    let data: serde_json::Value = serde_json::from_str(&crate::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let task = arclog::task::read_task(&task_dir.join(format!("{task_name}.json"))).map_err(|error| format!("the task does not read: {error:?}"))?;
    let grid = |fact: arclog::program::FactRelation, at: usize| {
        let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
        let mut cells = Vec::new();
        arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
        Table::new(2, cells)
    };
    let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
    let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
    // `input` as a table: its columns in the order of their types.
    let input_table = {
        let rows: Vec<Option<Arc<Table>>> = inputs.iter().map(|table| {
            let mut cells = Vec::with_capacity(table.cells.len());
            for row in table.rows() {
                cells.push(row[1]);
                cells.push(row[0]);
            }
            Some(Table::new(2, cells))
        }).collect();
        let types = vec![ValueType::Color, ValueType::Position];
        Stored { key: format!("{types:?}"), types, rows }
    };
    let items = data["items"].as_array().ok_or("a file's items")?;
    let mut left_out: Vec<String> = Vec::new();
    // Every table of the file, each once.
    struct Parsed {
        query: String,
        reads: Vec<Stored>,
        gold: Stored,
        mutants: Vec<Stored>,
    }
    let mut parsed: Vec<Parsed> = Vec::new();
    for item in items {
        let query = item["query"].as_str().unwrap_or("").to_string();
        let gold = stored_of(&item["gold"], train);
        let reads: Option<Vec<Stored>> = item["reads"].as_object().map_or(Some(Vec::new()), |reads| reads.values().map(|table| stored_of(table, train)).collect());
        let mutants: Option<Vec<Stored>> = item["mutants"].as_array().and_then(|mutants| mutants.iter().map(|mutant| stored_of(&mutant["table"], train)).collect());
        match (gold, reads, mutants) {
            (Some(gold), Some(reads), Some(mutants)) if gold.types.len() <= max_table_columns && reads.iter().all(|table| table.types.len() <= max_table_columns) && mutants.iter().all(|table| table.types.len() <= max_table_columns) => parsed.push(Parsed { query, reads, gold, mutants }),
            _ => left_out.push(query),
        }
    }
    let d = cache.d;
    let mut evals: Vec<(String, Arc<TableOps>)> = Vec::new();
    let mut schema_of = |stored: &Stored| -> Result<Arc<TableOps>, String> {
        if let Some((_, ops)) = evals.iter().find(|(key, _)| *key == stored.key) {
            return Ok(ops.clone());
        }
        let ops = cache.get(&stored.key, &stored.types)?;
        evals.push((stored.key.clone(), ops.clone()));
        Ok(ops)
    };
    // The schemas' operators stay for the task, and each schema's evaluation shares
    // its rows across the tables of that schema.
    let mut tables: Vec<&Stored> = vec![&input_table];
    for item in &parsed {
        tables.extend(item.reads.iter());
        tables.push(&item.gold);
        tables.extend(item.mutants.iter());
    }
    let mut held: Vec<(String, Arc<TableOps>)> = Vec::new();
    for table in &tables {
        let ops = schema_of(table)?;
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), ops));
        }
    }
    let mut run = |moved: &[Arc<Table>]| -> Vec<Vec<(usize, f64, Vec<f64>)>> {
        let mut evaluations: Vec<(String, TableEval<'_>)> = held.iter().map(|(key, ops)| (key.clone(), TableEval::new(ops))).collect();
        let mut done: FastMap<u128, Arc<ShapeMap>> = FastMap::default();
        let mut map_of = |stored: &Stored| -> Arc<ShapeMap> {
            let content = hash_words(stored.key.bytes().map(u64::from).chain(stored.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |table| [table.hash as u64, (table.hash >> 64) as u64]))));
            if let Some(found) = done.get(&content) {
                return found.clone();
            }
            let eval = &mut evaluations.iter_mut().find(|(key, _)| *key == stored.key).expect("a schema's evaluation").1;
            let map = Arc::new(eval.walk(&stored.rows, &inputs, moved, d, rate));
            done.insert(content, map.clone());
            map
        };
        let everywhere = |stored: &Stored| stored.rows.iter().all(|rows| rows.as_ref().is_some_and(|table| table.len > 0));
        let input_map = map_of(&input_table);
        parsed.iter().map(|item| {
            let reads: Vec<(Arc<ShapeMap>, bool)> = item.reads.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let gold_map = map_of(&item.gold);
            let mutants: Vec<(Arc<ShapeMap>, bool)> = item.mutants.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let mut bases: Vec<Held<'_>> = vec![Held { map: &input_map, rows_everywhere: everywhere(&input_table) }];
            bases.extend(reads.iter().map(|(map, rows_everywhere)| Held { map: map.as_ref(), rows_everywhere: *rows_everywhere }));
            let mutant_refs: Vec<Held<'_>> = mutants.iter().map(|(map, rows_everywhere)| Held { map: map.as_ref(), rows_everywhere: *rows_everywhere }).collect();
            let gold = Held { map: &gold_map, rows_everywhere: everywhere(&item.gold) };
            (1..=d).map(|size| item_scores(rule, &bases, gold, &mutant_refs, train, size as u8)).collect()
        }).collect()
    };
    let started = std::time::Instant::now();
    let results = run(&outputs);
    let primary_seconds = started.elapsed().as_secs_f64();
    let is_last = |at: usize| parsed[at].query == last_query;
    let per_size = |results: &[Vec<(usize, f64, Vec<f64>)>], size: usize, last: bool| -> Vec<(usize, f64, Vec<f64>)> {
        results.iter().enumerate().filter(|(at, _)| is_last(*at) == last).map(|(_, item)| item[size].clone()).collect()
    };
    // The null: the outputs deranged across the pairs, in a seeded order.
    let distinct_outputs = outputs.iter().map(|table| table.hash).collect::<std::collections::BTreeSet<_>>().len() > 1;
    let mut null_aucs: Vec<Vec<f64>> = vec![Vec::new(); d];
    if distinct_outputs && train > 1 {
        let mut state = 0x2545_f491_4f6c_dd1du64 ^ hash_words(task_name.bytes().map(u64::from)) as u64;
        for _ in 0..nulls {
            let mut order: Vec<usize> = (0..train).collect();
            loop {
                for at in (1..train).rev() {
                    state ^= state << 13;
                    state ^= state >> 7;
                    state ^= state << 17;
                    order.swap(at, (state % (at as u64 + 1)) as usize);
                }
                if order.iter().enumerate().all(|(at, own)| at != *own) {
                    break;
                }
            }
            let moved: Vec<Arc<Table>> = order.iter().map(|at| outputs[*at].clone()).collect();
            let found = run(&moved);
            for size in 0..d {
                if let Some(auc) = auc_of(&per_size(&found, size, false)) {
                    null_aucs[size].push(auc);
                }
            }
        }
    }
    let sizes: Vec<serde_json::Value> = (0..d).map(|size| {
        let rest = per_size(&results, size, false);
        let last = per_size(&results, size, true);
        let mean = |values: &[f64]| (!values.is_empty()).then(|| values.iter().sum::<f64>() / values.len() as f64);
        serde_json::json!({
            "d": size + 1,
            "auc": auc_of(&rest),
            "auc_last": auc_of(&last),
            "null": mean(&null_aucs[size]),
            "contingent": mean(&rest.iter().map(|found| found.0 as f64).collect::<Vec<_>>()),
            "items": rest.iter().map(|found| found.2.len()).sum::<usize>(),
        })
    }).collect();
    let shapes: usize = evals.len();
    Ok(serde_json::json!({ "task": task_name, "rule": format!("{rule:?}"), "rate": rate, "max_columns": cache.max_columns, "top_components": cache.top_components, "bounded": rate < 1_000_000 || cache.max_columns.is_some(), "sizes": sizes, "left_out": left_out, "schemas": shapes, "primary_seconds": primary_seconds, "seconds": started.elapsed().as_secs_f64() }))
}
