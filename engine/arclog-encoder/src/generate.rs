//! Generated features: shapes enumerated over parts, with `all`, `ratio` and `semijoin`, and
//! evaluated natively in one pass per table. The size of a term counts its operators and its
//! parts, each once. Nothing here is written for one feature.

use std::collections::HashSet;
use std::sync::{Arc, Mutex};

use arclog::types::ValueType;

use crate::expression::Op;
use crate::gen_constants::{constant_parts, constant_tables, number_bits, number_of};
use crate::gen_parts::{clear_views, flat, PartStep};
use crate::native::{hash_words, Evaluator, FastMap, Step, Table, Val, WORD_COUNT, WORD_NONEMPTY, WORD_SET};
use crate::tablewalk::{mix_word, shape_text, Entry2, ShapeMap};

const READS_INPUT: u8 = 1;
const READS_OUTPUT: u8 = 2;
const READS_TABLE: u8 = 4;
const REQUIRED: u8 = READS_TABLE | READS_OUTPUT;
const NO_TERM: u32 = u32::MAX;
const MAX_PROJECTED: usize = 3;
const MAX_COLUMNS: usize = 8;
const PAYLOAD: u64 = (1 << 62) - 1;
/// The leaves that stand first among a family's terms.
const LEAF_TABLE: u32 = 0;
const LEAF_OUTPUT: u32 = 1;
const LEAF_INPUT: u32 = 2;

/// A column of a term: its name, its type, and for an Ident the source it joins within.
#[derive(Clone, Debug)]
struct Column {
    name: String,
    ty: ValueType,
    source: u16,
}

/// Which roots a term has.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum RootKind {
    /// `nonempty` alone, on a relation of no columns.
    Holds,
    /// `nonempty` and `cardinality`.
    Rows,
    /// Those, and the `ratio` of its rows over its first relation's.
    Share,
    /// Those of `Rows`, and the one value of its one number column.
    Number,
}

pub struct Term {
    step: Option<Step>,
    a: u32,
    b: u32,
    columns: Vec<Column>,
    flags: u8,
    size: u8,
    root: RootKind,
    roots: Vec<u128>,
    text: String,
    types: u64,
    /// Whether another term reads this one.
    used: bool,
}

/// The terms over a table of one schema.
pub struct Generated {
    terms: Vec<Term>,
    pub first_term: usize,
    pub by_size: Vec<usize>,
    pub roots: usize,
}

fn is_number(ty: &ValueType) -> bool {
    matches!(ty, ValueType::Int | ValueType::Nat)
}

fn unique(name: &str, taken: &[Column]) -> String {
    if !taken.iter().any(|column| column.name == name) {
        return name.to_string();
    }
    let mut suffix = 2;
    loop {
        let held = format!("{name}_{suffix}");
        if !taken.iter().any(|column| column.name == held) {
            return held;
        }
        suffix += 1;
    }
}

fn meets(a: &Column, b: &Column) -> bool {
    if matches!(a.ty, ValueType::Ident(_)) || matches!(b.ty, ValueType::Ident(_)) {
        return a.source == b.source && a.ty.meets(&b.ty);
    }
    a.ty.meets(&b.ty)
}

/// The pair sets of a binary operator: one or two pairs of columns that can meet.
fn pair_sets(left: &[Column], right: &[Column]) -> Vec<Vec<(u16, u16)>> {
    let mut pairs: Vec<(u16, u16)> = Vec::new();
    for (l, a) in left.iter().enumerate() {
        for (r, b) in right.iter().enumerate() {
            if meets(a, b) {
                pairs.push((l as u16, r as u16));
            }
        }
    }
    let mut out: Vec<Vec<(u16, u16)>> = pairs.iter().map(|pair| vec![*pair]).collect();
    for (at, a) in pairs.iter().enumerate() {
        for b in &pairs[at + 1..] {
            if a.0 != b.0 && a.1 != b.1 {
                out.push(vec![*a, *b]);
            }
        }
    }
    out
}

fn types_hash(columns: &[Column]) -> u64 {
    hash_words(columns.iter().flat_map(|column| format!("{:?}", column.ty).into_bytes().into_iter().map(u64::from).chain([u64::from(column.source)]))) as u64
}

impl Generated {
    /// The family over a table of the column types `types`, up to size `d` in parts. At size 3,
    /// it extends only the terms that `extend` names: one per class of observed values.
    pub fn of(types: &[ValueType], d: usize, names: &NameStore, extend: Option<&[u32]>) -> Generated {
        let mut family = Generated { terms: Vec::new(), first_term: 0, by_size: Vec::new(), roots: 0 };
        let table_columns: Vec<Column> = types.iter().enumerate().map(|(at, ty)| Column { name: format!("T{at}"), ty: ty.clone(), source: 100 + at as u16 }).collect();
        let grid = |source: u16| vec![Column { name: "P".to_string(), ty: ValueType::Position, source }, Column { name: "Col".to_string(), ty: ValueType::Color, source }];
        family.push_leaf("T", table_columns, READS_TABLE, 0);
        family.push_leaf("output", grid(0), READS_OUTPUT, 0);
        family.push_leaf("input", grid(0), READS_INPUT, 0);
        let parts = constant_parts();
        for part in &parts {
            let columns = part.columns.iter().map(|(name, ty)| Column { name: (*name).to_string(), ty: ty.clone(), source: ident_source(&part.name) }).collect();
            let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
            family.push_leaf(&part.name, columns, flags, 1);
        }
        family.first_term = family.terms.len();
        let constants: Vec<u32> = (3..family.first_term as u32).collect();
        // Size 1: over the leaves.
        family.unary_operators(LEAF_TABLE, 1);
        family.parts_of(LEAF_TABLE, 1);
        family.unary_operators(LEAF_OUTPUT, 1);
        family.unary_operators(LEAF_INPUT, 1);
        family.binary(LEAF_TABLE, LEAF_OUTPUT, 1, true);
        family.binary(LEAF_OUTPUT, LEAF_TABLE, 1, false);
        family.binary(LEAF_TABLE, LEAF_INPUT, 1, true);
        family.binary(LEAF_INPUT, LEAF_TABLE, 1, false);
        family.binary(LEAF_OUTPUT, LEAF_INPUT, 1, true);
        family.binary(LEAF_INPUT, LEAF_OUTPUT, 1, false);
        family.by_size.push(family.terms.len());
        // Size 2: over each term of size 1, the constants among them.
        if d >= 2 {
            let below: Vec<u32> = constants.iter().copied().chain(family.first_term as u32..family.by_size[0] as u32).collect();
            for at in below {
                family.extend_term(at, 2, true);
            }
        }
        // Size 3: over the terms of size 2 that stand for a class, and each term of size 1 of a
        // class with each constant.
        if d >= 3 {
            family.by_size.push(family.terms.len());
            let chosen = extend.unwrap_or(&[]);
            for at in chosen {
                if u32::try_from(family.by_size[1]).is_ok_and(|end| *at < end) && family.terms[*at as usize].size == 2 {
                    family.extend_term(*at, 3, false);
                }
            }
            for at in chosen {
                if family.terms[*at as usize].size == 1 && (*at as usize) >= family.first_term && family.terms[*at as usize].flags & READS_TABLE != 0 {
                    for constant in &constants {
                        if family.terms[*constant as usize].flags & READS_OUTPUT != 0 {
                            family.binary(*at, *constant, 3, true);
                            family.binary(*constant, *at, 3, false);
                        }
                    }
                }
            }
        }
        family.by_size.push(family.terms.len());
        // The name of each root.
        let mut held = names.begin();
        let mut roots = 0;
        for term in family.terms.iter_mut().skip(family.first_term) {
            if term.flags & REQUIRED != REQUIRED {
                continue;
            }
            let texts: Vec<String> = match term.root {
                RootKind::Holds => vec![format!("(nonempty {})", term.text)],
                RootKind::Rows => vec![format!("(nonempty {})", term.text), format!("(cardinality {})", term.text)],
                RootKind::Share => vec![format!("(nonempty {})", term.text), format!("(cardinality {})", term.text), format!("(ratio {})", term.text)],
                RootKind::Number => vec![format!("(nonempty {})", term.text), format!("(cardinality {})", term.text), format!("(value {})", term.text)],
            };
            term.roots = texts.iter().map(|text| {
                let shape = shape_text(text, "T", types);
                let hash = hash_words(shape.bytes().map(u64::from));
                held.add(hash, shape);
                hash
            }).collect();
            roots += term.roots.len();
        }
        family.roots = roots;
        // A walk reads the steps and the roots.
        for term in &mut family.terms {
            term.text = String::new();
            term.columns = Vec::new();
        }
        family
    }

    /// Each operator and part over a term, with what stays within the size.
    fn extend_term(&mut self, at: u32, size: u8, with_grids_alone: bool) {
        let flags = self.terms[at as usize].flags;
        let table_reader = flags & READS_TABLE != 0;
        let output_reader = flags & READS_OUTPUT != 0;
        let _ = with_grids_alone;
        if table_reader {
            self.unary_operators(at, size);
            self.parts_of(at, size);
            self.binary(at, LEAF_OUTPUT, size, true);
            self.binary(LEAF_OUTPUT, at, size, false);
            if output_reader {
                self.binary(at, LEAF_INPUT, size, true);
                self.binary(LEAF_INPUT, at, size, false);
            }
        } else if output_reader {
            self.binary(LEAF_TABLE, at, size, true);
            self.binary(at, LEAF_TABLE, size, false);
        }
    }

    fn push_leaf(&mut self, text: &str, columns: Vec<Column>, flags: u8, size: u8) {
        let types = types_hash(&columns);
        self.terms.push(Term { step: None, a: NO_TERM, b: NO_TERM, columns, flags, size, root: RootKind::Rows, roots: Vec::new(), text: text.to_string(), types, used: true });
    }

    #[allow(clippy::too_many_arguments)]
    fn push(&mut self, step: Step, a: u32, b: u32, columns: Vec<Column>, size: u8, text: String, root: RootKind) {
        if columns.len() > MAX_COLUMNS {
            return;
        }
        let flags = self.terms[a as usize].flags | if b == NO_TERM { 0 } else { self.terms[b as usize].flags };
        let root = if columns.is_empty() {
            RootKind::Holds
        } else if root == RootKind::Rows && columns.len() == 1 && is_number(&columns[0].ty) {
            RootKind::Number
        } else {
            root
        };
        let types = types_hash(&columns);
        self.terms[a as usize].used = true;
        if b != NO_TERM {
            self.terms[b as usize].used = true;
        }
        self.terms.push(Term { step: Some(step), a, b, columns, flags, size, root, roots: Vec::new(), text, types, used: false });
    }

    /// `project` and `select` over a term.
    fn unary_operators(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        let count = columns.len();
        if count >= 2 && count <= 10 {
            for mask in 1u32..(1 << count) - 1 {
                if mask.count_ones() as usize > MAX_PROJECTED {
                    continue;
                }
                let places: Vec<u16> = (0..count as u16).filter(|place| mask & (1 << place) != 0).collect();
                let kept: Vec<Column> = places.iter().map(|place| columns[usize::from(*place)].clone()).collect();
                let names: Vec<&str> = kept.iter().map(|column| column.name.as_str()).collect();
                let line = format!("(project {text} {})", names.join(" "));
                self.push(Step::Project { columns: places.into_boxed_slice() }, at, NO_TERM, kept, size, line, RootKind::Rows);
            }
        }
        for a in 0..count {
            for b in a + 1..count {
                if !meets(&columns[a], &columns[b]) {
                    continue;
                }
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || (is_number(&columns[a].ty) && is_number(&columns[b].ty)) {
                        let dropped = (op == Op::Eq).then_some(b);
                        let kept: Vec<Column> = columns.iter().enumerate().filter(|(place, _)| Some(*place) != dropped).map(|(_, column)| column.clone()).collect();
                        let line = format!("(select {text} {} {} {})", columns[a].name, op.text(), columns[b].name);
                        self.push(Step::Select { at: a as u16, op, other: Some(b as u16), drop: dropped.map(|at| at as u16) }, at, NO_TERM, kept, size, line, RootKind::Rows);
                    }
                }
            }
            if columns[a].ty.has_zero() {
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || is_number(&columns[a].ty) {
                        let dropped = (op == Op::Eq).then_some(a);
                        let kept: Vec<Column> = columns.iter().enumerate().filter(|(place, _)| Some(*place) != dropped).map(|(_, column)| column.clone()).collect();
                        let line = format!("(select {text} {} {} 0)", columns[a].name, op.text());
                        self.push(Step::Select { at: a as u16, op, other: None, drop: dropped.map(|at| at as u16) }, at, NO_TERM, kept, size, line, RootKind::Rows);
                    }
                }
            }
        }
    }

    /// The ways to key a part: no key, each column, and every group column as one hole.
    fn key_options(columns: &[Column], not: &[usize]) -> Vec<(Box<[u16]>, String)> {
        let mut out: Vec<(Box<[u16]>, String)> = vec![(Box::new([]), "()".to_string())];
        for (at, column) in columns.iter().enumerate() {
            if !not.contains(&at) {
                out.push((vec![at as u16].into_boxed_slice(), format!("({})", column.name)));
            }
        }
        let group: Vec<u16> = columns.iter().enumerate().filter(|(at, column)| !not.contains(at) && matches!(column.ty, ValueType::Color | ValueType::Ident(_))).map(|(at, _)| at as u16).collect();
        if group.len() >= 2 {
            out.push((group.into_boxed_slice(), "(T*)".to_string()));
        }
        out
    }

    /// The parts with holes over a term.
    fn parts_of(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        if columns.is_empty() {
            return;
        }
        let one = |name: &str, ty: ValueType, source: u16| Column { name: name.to_string(), ty, source };
        let key_columns = |keys: &[u16]| -> Vec<Column> { keys.iter().map(|key| columns[usize::from(*key)].clone()).collect() };
        let with = |extra: &[(&str, ValueType, u16)]| -> Vec<Column> {
            let mut out = columns.clone();
            for (name, ty, source) in extra {
                let name = unique(name, &out);
                out.push(one(&name, ty.clone(), *source));
            }
            out
        };
        let id_source = 1000 + (self.terms.len() % 60000) as u16;
        let mut pushes: Vec<(Step, u32, Vec<Column>, String, RootKind)> = Vec::new();
        let mut add = |part: PartStep, b: u32, kept: Vec<Column>, line: String, root: RootKind| pushes.push((Step::Part(Box::new(part)), b, kept, line, root));
        for (place, column) in columns.iter().enumerate() {
            let p = place as u16;
            let name = &column.name;
            if column.ty == ValueType::Position {
                for (grid, label) in [(LEAF_OUTPUT, "output"), (LEAF_INPUT, "input")] {
                    add(PartStep::CellsOn { p }, grid, vec![column.clone()], format!("(cells-on {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::ColorsUnder { p }, grid, vec![one("Col", ValueType::Color, 0)], format!("(colors-under {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::NeighborhoodClass { p }, grid, vec![column.clone(), one("Id", ValueType::OPEN_IDENT, id_source)], format!("(neighborhood-class {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::NeighborColorClass { p }, grid, vec![column.clone(), one("Id", ValueType::OPEN_IDENT, id_source)], format!("(neighbor-color-class {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::SameColorNeighbors { p }, grid, vec![column.clone(), one("Col", ValueType::Color, 0), one("N", ValueType::Nat, 0)], format!("(same-color-neighbors {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::Distance { p }, grid, vec![one("P", ValueType::Position, 0), one("K", ValueType::Nat, 0)], format!("(distance {text} {name} {label})"), RootKind::Rows);
                }
                add(PartStep::Around { p }, NO_TERM, vec![one("Q", ValueType::Position, 0)], format!("(around {text} {name})"), RootKind::Rows);
                add(PartStep::Neighbors { p }, NO_TERM, with(&[("D", ValueType::Dir8, 0), ("Q", ValueType::Position, 0)]), format!("(neighbors {text} {name})"), RootKind::Rows);
                add(PartStep::Split { p }, NO_TERM, with(&[("A", ValueType::Axis, 0), ("Along", ValueType::Box, 0)]), format!("(split {text} {name})"), RootKind::Rows);
                add(PartStep::Margin { p }, NO_TERM, with(&[("D", ValueType::Dir, 0), ("K", ValueType::Nat, 0)]), format!("(margin {text} {name})"), RootKind::Rows);
                add(PartStep::CornerDist { p }, NO_TERM, with(&[("Diag", ValueType::DiagDir, 0), ("K", ValueType::Nat, 0)]), format!("(corner-dist {text} {name})"), RootKind::Rows);
                add(PartStep::Parity { p }, NO_TERM, with(&[("K", ValueType::Nat, 0)]), format!("(parity {text} {name})"), RootKind::Rows);
                add(PartStep::BorderDistance { p }, NO_TERM, with(&[("K", ValueType::Nat, 0)]), format!("(border-distance {text} {name})"), RootKind::Rows);
                for (keys, key_text) in Self::key_options(&columns, &[place]) {
                    let heads = key_columns(&keys);
                    let extended = |extra: Vec<Column>| -> Vec<Column> { heads.iter().cloned().chain(extra).collect() };
                    add(PartStep::Pieces { keys: keys.clone(), p }, NO_TERM, extended(vec![column.clone(), one("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::BoxOf { keys: keys.clone(), p }, NO_TERM, extended(vec![one("B", ValueType::Box, 0)]), format!("(box-of {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::RelBox { keys: keys.clone(), p }, NO_TERM, extended(vec![one("X_rel", ValueType::Offset, 0)]), format!("(cells-in-box {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::ShapeClass { keys: keys.clone(), p, turned: false }, NO_TERM, extended(vec![one("Id", ValueType::OPEN_IDENT, 900)]), format!("(shape-class {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::ShapeClass { keys: keys.clone(), p, turned: true }, NO_TERM, extended(vec![one("Id", ValueType::OPEN_IDENT, 901)]), format!("(shape-class-d4 {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Holes { keys: keys.clone(), p }, NO_TERM, extended(vec![one("N", ValueType::Nat, 0)]), format!("(holes {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Symmetry { keys: keys.clone(), p }, NO_TERM, extended(vec![one("N", ValueType::Nat, 0)]), format!("(symmetry {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::TouchesEdge { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(touches-edge {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::FillsBox { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(fills-box {text} {key_text} {name})"), RootKind::Rows);
                    for (v, value) in columns.iter().enumerate() {
                        if value.ty == ValueType::Color && v != place && !keys.contains(&(v as u16)) {
                            for (turned, label) in [(false, "occurs"), (true, "occurs-d4")] {
                                add(PartStep::Occurs { keys: keys.clone(), p, v: v as u16, turned }, LEAF_OUTPUT, extended(vec![one("V", ValueType::Offset, 0)]), format!("({label} {text} {key_text} {name} {})", value.name), RootKind::Rows);
                            }
                        }
                    }
                }
            }
            if column.ty == ValueType::Box {
                for (grid, label) in [(LEAF_OUTPUT, "output"), (LEAF_INPUT, "input")] {
                    add(PartStep::Inside { b: p }, grid, with(&[("P", ValueType::Position, 0), ("Col", ValueType::Color, 0)]), format!("(inside {text} {name} {label})"), RootKind::Rows);
                }
            }
            if is_number(&column.ty) {
                for (greatest, label) in [(true, "greatest"), (false, "least")] {
                    add(PartStep::NumberExtreme { n: p, greatest }, NO_TERM, vec![column.clone()], format!("({label} {text} {name})"), RootKind::Rows);
                    if columns.len() >= 2 {
                        for (other, value) in columns.iter().enumerate() {
                            if other != place {
                                for (keys, key_text) in Self::key_options(&columns, &[place, other]) {
                                    let kept: Vec<Column> = key_columns(&keys).into_iter().chain([value.clone()]).collect();
                                    add(PartStep::Extreme { keys, t: other as u16, score: p, greatest }, NO_TERM, kept, format!("({label}-by {text} {key_text} {} {name})", value.name), RootKind::Rows);
                                }
                            }
                        }
                    }
                }
            }
        }
        for (keys, key_text) in Self::key_options(&columns, &[]) {
            let heads = key_columns(&keys);
            let with_n: Vec<Column> = heads.iter().cloned().chain([one("N", ValueType::Nat, 0)]).collect();
            add(PartStep::Count { keys: keys.clone() }, NO_TERM, with_n, format!("(count {text} {key_text})"), RootKind::Rows);
            if !keys.is_empty() && keys.len() < columns.len() {
                let with_id: Vec<Column> = heads.iter().cloned().chain([one("Id", ValueType::OPEN_IDENT, 902)]).collect();
                add(PartStep::ClassOf { keys: keys.clone() }, NO_TERM, with_id, format!("(class-of {text} {key_text})"), RootKind::Rows);
            }
            for (f, field) in columns.iter().enumerate() {
                if keys.contains(&(f as u16)) {
                    continue;
                }
                let kept: Vec<Column> = heads.iter().cloned().chain([field.clone()]).collect();
                add(PartStep::OneValue { keys: keys.clone(), f: f as u16 }, NO_TERM, kept, format!("(one-value {text} {key_text} {})", field.name), RootKind::Rows);
                add(PartStep::Several { keys: keys.clone(), f: f as u16 }, NO_TERM, heads.clone(), format!("(several {text} {key_text} {})", field.name), RootKind::Rows);
                if !keys.is_empty() {
                    add(PartStep::Determines { keys: keys.clone(), f: f as u16 }, NO_TERM, Vec::new(), format!("(determines {text} {key_text} {})", field.name), RootKind::Holds);
                    add(PartStep::MostFrequentRows { keys: keys.clone(), v: f as u16 }, NO_TERM, columns.clone(), format!("(most-frequent-rows {text} {key_text} {})", field.name), RootKind::Share);
                }
            }
        }
        for (step, b, kept, line, root) in pushes {
            self.push(step, at, b, kept, size, line, root);
        }
    }

    /// `join`, `semijoin`, `antijoin` and `all`, with a pair set of one or two pairs.
    fn binary(&mut self, l: u32, r: u32, size: u8, joins: bool) {
        let (left, right) = (self.terms[l as usize].columns.clone(), self.terms[r as usize].columns.clone());
        let (left_text, right_text) = (self.terms[l as usize].text.clone(), self.terms[r as usize].text.clone());
        for pairs in pair_sets(&left, &right) {
            let pair_text: Vec<String> = pairs.iter().map(|(a, b)| format!("({} {})", left[usize::from(*a)].name, right[usize::from(*b)].name)).collect();
            let pair_text = pair_text.join(" ");
            let left_at: Box<[u16]> = pairs.iter().map(|(a, _)| *a).collect();
            let right_at: Box<[u16]> = pairs.iter().map(|(_, b)| *b).collect();
            if joins {
                let kept: Box<[u16]> = (0..right.len() as u16).filter(|at| !right_at.contains(at)).collect();
                let mut columns = left.clone();
                for at in kept.iter() {
                    let column = &right[usize::from(*at)];
                    let name = unique(&column.name, &columns);
                    columns.push(Column { name, ty: column.ty.clone(), source: column.source });
                }
                self.push(Step::Join { left: left_at.clone(), right: right_at.clone(), kept, left_arity: left.len() as u16 }, l, r, columns, size, format!("(join {left_text} {right_text} {pair_text})"), RootKind::Rows);
            }
            self.push(Step::Semijoin { left: left_at.clone(), right: right_at.clone() }, l, r, left.clone(), size, format!("(semijoin {left_text} {right_text} {pair_text})"), RootKind::Share);
            self.push(Step::Antijoin { left: left_at.clone(), right: right_at.clone() }, l, r, left.clone(), size, format!("(antijoin {left_text} {right_text} {pair_text})"), RootKind::Rows);
            self.push(Step::All { left: left_at.clone(), right: right_at.clone(), outer: Box::new([]) }, l, r, Vec::new(), size, format!("(all {left_text} {right_text} () {pair_text})"), RootKind::Holds);
            for (at, column) in left.iter().enumerate() {
                if !left_at.contains(&(at as u16)) {
                    self.push(Step::All { left: left_at.clone(), right: right_at.clone(), outer: vec![at as u16].into_boxed_slice() }, l, r, vec![column.clone()], size, format!("(all {left_text} {right_text} ({}) {pair_text})", column.name), RootKind::Rows);
                }
            }
            // A key that determines whether a row has a match.
            if left.len() >= 2 {
                for (at, column) in left.iter().enumerate() {
                    if !left_at.contains(&(at as u16)) {
                        self.push(Step::Part(Box::new(PartStep::DeterminesFlag { keys: vec![at as u16].into_boxed_slice(), left: left_at.clone(), right: right_at.clone() })), l, r, Vec::new(), size, format!("(determines-flag {left_text} {right_text} ({}) {pair_text})", column.name), RootKind::Holds);
                    }
                }
            }
            if let [(a, b)] = pairs[..] {
                if left[usize::from(a)].ty == ValueType::Position && right[usize::from(b)].ty == ValueType::Position {
                    self.push(Step::Part(Box::new(PartStep::SharedLine { a, b })), l, r, left.clone(), size, format!("(shared-line {left_text} {right_text} ({} {}))", left[usize::from(a)].name, right[usize::from(b)].name), RootKind::Share);
                }
            }
        }
    }
}

/// The source of an Ident column of a constant part: a grid's components share one.
fn ident_source(name: &str) -> u16 {
    match name {
        "input-components" | "input-component-boxes" => 1,
        "output-components" | "output-component-boxes" => 2,
        "input-foreground-components" => 3,
        "output-foreground-components" => 4,
        "changed-components" => 5,
        _ => 0,
    }
}

/// One family's evaluation on one task.
pub struct Walker<'a> {
    family: &'a Generated,
    eval: Evaluator<'a>,
    values: Vec<Val>,
    value_index: FastMap<u128, u32>,
    memo: FastMap<(u32, u32, u32), u32>,
    counts: FastMap<(u32, u32, u32), (u32, u32)>,
    /// The cells that `values` holds.
    held_cells: usize,
}

/// What a walker holds at most between walks.
const HELD_CELLS: usize = 3_000_000;
const HELD_MEMO: usize = 250_000;

static NO_SHAPES: [crate::native::CompShape; 0] = [];
static NO_INSTANCES: [crate::native::CompInstance; 0] = [];
static NO_LIBS: [crate::native::LibRelation; 0] = [];

fn rows_of(value: &Val) -> Option<u64> {
    match value {
        Val::None => None,
        Val::Empty => Some(0),
        Val::Rows(parts) => Some(parts.iter().fold(1u64, |count, part| count.saturating_mul(part.table.len as u64))),
    }
}

fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}

impl<'a> Walker<'a> {
    pub fn new(family: &'a Generated) -> Self {
        Walker { family, eval: Evaluator::new(&NO_SHAPES, &NO_INSTANCES, &NO_LIBS, arclog::decode::corpus::corpus_session()), values: vec![Val::None, Val::Empty], value_index: FastMap::default(), memo: FastMap::default(), counts: FastMap::default(), held_cells: 0 }
    }

    /// Drops the values and the memos where they pass the budget. A later walk computes again
    /// what it needs.
    fn keep_within_budget(&mut self) {
        if self.held_cells > HELD_CELLS || self.memo.len() + self.counts.len() > HELD_MEMO {
            self.values = vec![Val::None, Val::Empty];
            self.value_index = FastMap::default();
            self.memo = FastMap::default();
            self.counts = FastMap::default();
            self.held_cells = 0;
        }
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
                if let Val::Rows(parts) = &value {
                    self.held_cells += parts.iter().map(|part| part.table.cells.len()).sum::<usize>();
                }
                self.values.push(value);
                self.value_index.insert(hash, at);
                at
            }
        }
    }

    fn apply(&mut self, step: &Step, a: u32, b: u32) -> Val {
        let first = self.values[a as usize].clone();
        if b == NO_TERM {
            self.eval.apply(step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.apply(step, &[&first, &second])
        }
    }

    /// Adds each term's values on one table to its signature, and says which terms have a row.
    pub fn observe(&mut self, leaves: &[Vec<Val>], salt: u128, signature: &mut [u128], some: &mut [bool]) {
        let family = self.family;
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let pairs = leaves[0].len();
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let step = term.step.as_ref().expect("a term has a step");
            let mut own = Vec::with_capacity(pairs);
            for pair in 0..pairs {
                let a = ids[term.a as usize][pair];
                let b = if term.b == NO_TERM { NO_TERM } else { ids[term.b as usize][pair] };
                let key = (at as u32, a, b);
                let id = match self.memo.get(&key) {
                    Some(found) => *found,
                    None => {
                        let value = self.apply(step, a, b);
                        let id = self.value_id(value);
                        self.memo.insert(key, id);
                        id
                    }
                };
                own.push(id);
                let hash = self.values[id as usize].hash();
                some[at] |= id > 1;
                signature[at] = signature[at].wrapping_add(hash_words([salt as u64, (salt >> 64) as u64, pair as u64, hash as u64, (hash >> 64) as u64, term.types]));
            }
            ids.push(own);
        }
    }

    /// One table's sparse map from a root's shape to its value at each pair. Each leaf's rows
    /// stand at each pair.
    pub fn walk(&mut self, leaves: &[Vec<Val>], top: u8, allow: Option<&HashSet<u128>>) -> ShapeMap {
        self.keep_within_budget();
        let family = self.family;
        let pairs = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut map: ShapeMap = FastMap::default();
        let empty = vec![1u32; pairs];
        let none = vec![0u32; pairs];
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let at = at as u32;
            let first = std::mem::take(&mut ids[term.a as usize]);
            let second = if term.b == NO_TERM { Vec::new() } else { std::mem::take(&mut ids[term.b as usize]) };
            let step = term.step.as_ref().expect("a term has a step");
            let required = term.flags & REQUIRED == REQUIRED;
            let wanted = required && allow.is_none_or(|allow| term.roots.iter().any(|hash| allow.contains(hash)));
            let extended = term.used;
            let _ = top;
            let mut own = Vec::new();
            let idle = first == empty || first == none || (matches!(step, Step::Join { .. } | Step::Semijoin { .. }) && second == empty);
            if extended {
                own.reserve(pairs);
                for pair in 0..pairs {
                    let b = if term.b == NO_TERM { NO_TERM } else { second[pair] };
                    let key = (at, first[pair], b);
                    let id = match self.memo.get(&key) {
                        Some(found) => *found,
                        None => {
                            let value = self.apply(step, first[pair], b);
                            let id = self.value_id(value);
                            self.memo.insert(key, id);
                            id
                        }
                    };
                    own.push(id);
                }
            }
            if wanted && !idle {
                let mut words: [[u64; 3]; 12] = [[0; 3]; 12];
                for pair in 0..pairs.min(12) {
                    let (id, b) = (first[pair], if term.b == NO_TERM { NO_TERM } else { second[pair] });
                    let (rows, left) = if extended {
                        let value = &self.values[own[pair] as usize];
                        let left = rows_of(&self.values[id as usize]);
                        (rows_of(value).map_or(u32::MAX, |n| n.min(u64::from(u32::MAX - 1)) as u32), left.map_or(u32::MAX, |n| n.min(u64::from(u32::MAX - 1)) as u32))
                    } else {
                        let key = (at, id, b);
                        match self.counts.get(&key) {
                            Some(found) => *found,
                            None => {
                                let value = self.apply(step, id, b);
                                let found = (rows_of(&value).map_or(u32::MAX, |n| n.min(u64::from(u32::MAX - 1)) as u32), rows_of(&self.values[id as usize]).map_or(u32::MAX, |n| n.min(u64::from(u32::MAX - 1)) as u32));
                                let found = if term.root == RootKind::Number { (found.0, number_word(&value)) } else { found };
                                self.counts.insert(key, found);
                                found
                            }
                        }
                    };
                    let left = if term.root == RootKind::Number && extended { number_word(&self.values[own[pair] as usize]) } else { left };
                    if rows == u32::MAX {
                        continue;
                    }
                    words[pair][0] = WORD_NONEMPTY | u64::from(rows > 0);
                    words[pair][1] = WORD_COUNT | u64::from(rows);
                    words[pair][2] = match term.root {
                        RootKind::Share if left != u32::MAX && left > 0 => {
                            let shared = gcd(u64::from(rows), u64::from(left)).max(1);
                            WORD_SET | (hash_words([u64::from(rows) / shared, u64::from(left) / shared]) as u64 & PAYLOAD) * u64::from(rows > 0)
                        }
                        RootKind::Number => WORD_SET | u64::from(left),
                        _ => 0,
                    };
                }
                for (root, hash) in term.roots.iter().enumerate() {
                    if allow.is_some_and(|allow| !allow.contains(hash)) {
                        continue;
                    }
                    if !(0..pairs.min(12)).any(|pair| words[pair][root] == 0 || words[pair][root] & PAYLOAD != 0) {
                        continue;
                    }
                    let entry = map.entry(*hash).or_insert(Entry2 { sums: [0; 12], none: 0, size: term.size });
                    for pair in 0..pairs.min(12) {
                        let word = words[pair][root];
                        if word == 0 {
                            entry.none |= 1 << pair;
                        } else if word & PAYLOAD != 0 {
                            entry.sums[pair] = entry.sums[pair].wrapping_add(mix_word(word));
                        }
                    }
                }
            }
            ids[term.a as usize] = first;
            if term.b != NO_TERM {
                ids[term.b as usize] = second;
            }
            ids.push(own);
        }
        map
    }
}

/// The word of a relation's one number, where it has one row.
fn number_word(value: &Val) -> u32 {
    let Some(table) = flat(value) else { return 0 };
    if table.len == 1 && table.arity == 1 {
        (number_of(table.cells[0]) + 1).clamp(0, i64::from(u32::MAX - 1)) as u32
    } else {
        0
    }
}

/// The leaves of a walk: the table's rows, the grids, and the constant parts at each pair.
pub fn leaves_of(rows: &[Option<Arc<Table>>], inputs: &[Arc<Table>], outputs: &[Arc<Table>], constants: &[Vec<Arc<Table>>]) -> Vec<Vec<Val>> {
    let mut out = vec![
        rows.iter().map(|table| table.clone().map_or(Val::None, Val::of_table)).collect::<Vec<_>>(),
        outputs.iter().map(|table| Val::of_table(table.clone())).collect(),
        inputs.iter().map(|table| Val::of_table(table.clone())).collect(),
    ];
    let count = constants.first().map_or(0, Vec::len);
    for part in 0..count {
        out.push(constants.iter().map(|tables| Val::of_table(tables[part].clone())).collect());
    }
    out
}

pub fn constants_of(facts: &[crate::catalog_facts::PairFacts]) -> Vec<Vec<Arc<Table>>> {
    clear_views();
    facts.iter().map(constant_tables).collect()
}

/// Keeps `number_bits` in use by callers of this module's numbers.
pub fn encoded_number(n: i64) -> u32 {
    number_bits(n)
}

/// Where the names of roots go: a map in memory, or a file that each name reaches once.
#[derive(Default)]
pub struct NameStore {
    names: Mutex<FastMap<u128, String>>,
    file: Option<Mutex<(HashSet<u64>, std::io::BufWriter<std::fs::File>)>>,
}

pub enum NameWriter<'a> {
    Map(std::sync::MutexGuard<'a, FastMap<u128, String>>),
    File(std::sync::MutexGuard<'a, (HashSet<u64>, std::io::BufWriter<std::fs::File>)>),
}

impl NameWriter<'_> {
    fn add(&mut self, hash: u128, shape: String) {
        match self {
            NameWriter::Map(map) => {
                map.entry(hash).or_insert(shape);
            }
            NameWriter::File(file) => {
                let held = &mut **file;
                if held.0.insert(hash as u64) {
                    let _ = std::io::Write::write_all(&mut held.1, format!("{:016x}\t{shape}\n", hash as u64).as_bytes());
                }
            }
        }
    }
}

impl NameStore {
    pub fn to_file(path: &str) -> Result<NameStore, String> {
        let file = std::fs::OpenOptions::new().create(true).append(true).open(path).map_err(|error| error.to_string())?;
        Ok(NameStore { names: Mutex::default(), file: Some(Mutex::new((HashSet::new(), std::io::BufWriter::new(file)))) })
    }

    fn begin(&self) -> NameWriter<'_> {
        match &self.file {
            Some(file) => NameWriter::File(file.lock().expect("no panic")),
            None => NameWriter::Map(self.names.lock().expect("no panic")),
        }
    }

    pub fn flush(&self) {
        if let Some(file) = &self.file {
            let _ = std::io::Write::flush(&mut file.lock().expect("no panic").1);
        }
    }

    pub fn get(&self, hash: &u128) -> Option<String> {
        self.names.lock().expect("no panic").get(hash).cloned()
    }
}

/// The terms that the cache of families holds at most; past it, the oldest families leave.
const CACHED_TERMS: usize = 6_000_000;

/// The families of each schema, kept in a bounded cache, and the name of each root.
#[derive(Default)]
pub struct Generators {
    held: Mutex<(FastMap<u128, (Arc<Generated>, u64)>, u64)>,
    pub names: NameStore,
    /// Per schema, the terms that stand for their class.
    pub extend: std::collections::HashMap<String, Vec<u32>>,
}

impl Generators {
    fn get(&self, stored: &crate::tablewalk::Stored, d: usize) -> Arc<Generated> {
        let hash = hash_words(stored.key.bytes().map(u64::from));
        {
            let mut held = self.held.lock().expect("no panic");
            let (cache, clock) = &mut *held;
            *clock += 1;
            if let Some(found) = cache.get_mut(&hash) {
                found.1 = *clock;
                return found.0.clone();
            }
        }
        let family = Arc::new(Generated::of(&stored.types, d, &self.names, self.extend.get(&stored.key).map(Vec::as_slice)));
        let mut held = self.held.lock().expect("no panic");
        let (cache, clock) = &mut *held;
        *clock += 1;
        cache.insert(hash, (family.clone(), *clock));
        let mut total: usize = cache.values().map(|found| found.0.terms.len()).sum();
        while total > CACHED_TERMS && cache.len() > 1 {
            let Some(oldest) = cache.iter().filter(|(key, _)| **key != hash).min_by_key(|(_, found)| found.1).map(|(key, _)| *key) else { break };
            if let Some(gone) = cache.remove(&oldest) {
                total -= gone.0.terms.len();
            }
        }
        family
    }
}

/// A task's Candidate result on the generated shapes: per size, the AUC and the null over every
/// comparison and over those whose mutant has rows, each shape's tally, and the seconds of its
/// walks.
#[allow(clippy::too_many_arguments)]
pub fn generate_task(path: &str, task_dir: &std::path::Path, families: &Generators, d: usize, nulls: usize, allow: Option<&HashSet<u128>>, max_table_columns: usize) -> Result<serde_json::Value, String> {
    use crate::family::{auc_of, scores, Held, Tally};
    use crate::tablewalk::{stored_of, StableRule, Stored};
    let rule = StableRule::Active;
    let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let task_path = task_dir.join(format!("{task_name}.json"));
    let task = arclog::task::read_task(&task_path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let task_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&task_path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let grid = |fact: arclog::program::FactRelation, at: usize| {
        let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
        let mut cells = Vec::new();
        arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
        Table::new(2, cells)
    };
    let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
    let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
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
    struct Parsed {
        query: String,
        reads: Vec<Stored>,
        gold: Stored,
        mutants: Vec<Stored>,
    }
    let mut parsed: Vec<Parsed> = Vec::new();
    let mut left_out: Vec<String> = Vec::new();
    let usable = |stored: &Stored| stored.types.len() <= max_table_columns && stored.rows.iter().all(|rows| rows.as_ref().is_none_or(|table| table.len <= 5000));
    for item in data["items"].as_array().ok_or("a file's items")? {
        let query = item["query"].as_str().unwrap_or("").to_string();
        let gold = stored_of(&item["gold"], train);
        let reads: Option<Vec<Stored>> = item["reads"].as_object().map_or(Some(Vec::new()), |reads| reads.values().map(|table| stored_of(table, train)).collect());
        let mutants: Option<Vec<Stored>> = item["mutants"].as_array().and_then(|mutants| mutants.iter().map(|mutant| stored_of(&mutant["table"], train)).collect());
        match (gold, reads, mutants) {
            (Some(gold), Some(reads), Some(mutants)) if usable(&gold) && reads.iter().all(&usable) && mutants.iter().all(&usable) => parsed.push(Parsed { query, reads, gold, mutants }),
            _ => left_out.push(query),
        }
    }
    let everywhere = |stored: &Stored| stored.rows.iter().all(|rows| rows.as_ref().is_some_and(|table| table.len > 0));
    let mut tables: Vec<&Stored> = vec![&input_table];
    for item in &parsed {
        tables.extend(item.reads.iter());
        tables.push(&item.gold);
        tables.extend(item.mutants.iter());
    }
    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    for table in &tables {
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), families.get(table, d)));
        }
    }
    let mut walkers: Vec<(String, Walker<'_>)> = held.iter().map(|(key, family)| (key.clone(), Walker::new(family))).collect();
    let mut tallies: FastMap<u128, Tally> = FastMap::default();
    let mut walks = 0u64;
    let mut walk_seconds = 0f64;
    let is_last = |at: usize| parsed[at].query == last_query;
    let mutant_rows: Vec<Vec<bool>> = parsed.iter().map(|item| item.mutants.iter().map(&everywhere).collect()).collect();
    type Scores = (usize, f64, Vec<f64>, usize);
    let mut run = |order: Option<&[usize]>, null: bool, tallies: &mut FastMap<u128, Tally>| -> Vec<Vec<Scores>> {
        let facts = crate::catalog_run::pairs_of_task(&task_json, order);
        let constants = constants_of(&facts);
        let moved: Vec<Arc<Table>> = (0..train).map(|at| outputs[order.map_or(at, |order| order[at])].clone()).collect();
        let mut done: FastMap<u128, Arc<ShapeMap>> = FastMap::default();
        let mut map_of = |stored: &Stored| -> Arc<ShapeMap> {
            let content = hash_words(stored.key.bytes().map(u64::from).chain(stored.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |table| [table.hash as u64, (table.hash >> 64) as u64]))));
            if let Some(found) = done.get(&content) {
                return found.clone();
            }
            let walker = &mut walkers.iter_mut().find(|(key, _)| *key == stored.key).expect("a schema's walker").1;
            let started = std::time::Instant::now();
            let leaves = leaves_of(&stored.rows, &inputs, &moved, &constants);
            let map = Arc::new(walker.walk(&leaves, d as u8, allow));
            walks += 1;
            walk_seconds += started.elapsed().as_secs_f64();
            done.insert(content, map.clone());
            map
        };
        let input_map = map_of(&input_table);
        parsed.iter().enumerate().map(|(at, item)| {
            let reads: Vec<(Arc<ShapeMap>, bool)> = item.reads.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let gold_map = map_of(&item.gold);
            let mutants: Vec<(Arc<ShapeMap>, bool)> = item.mutants.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let mut bases: Vec<Held<'_>> = vec![(&input_map, true)];
            bases.extend(reads.iter().map(|(map, rows)| (map.as_ref(), *rows)));
            let mutant_refs: Vec<Held<'_>> = mutants.iter().map(|(map, rows)| (map.as_ref(), *rows)).collect();
            let gold = (gold_map.as_ref(), everywhere(&item.gold));
            let last = is_last(at);
            (1..=d).map(|size| {
                let tally = (size == d && !last).then_some((&mut *tallies, null));
                scores(rule, &bases, gold, &mutant_refs, train, size as u8, tally)
            }).collect()
        }).collect()
    };
    let started = std::time::Instant::now();
    let results = run(None, false, &mut tallies);
    let per_size = |results: &[Vec<Scores>], size: usize, rows_only: bool| -> Vec<(usize, f64, Vec<f64>)> {
        results.iter().enumerate().filter(|(at, _)| !is_last(*at)).map(|(at, item)| {
            let found = &item[size];
            let kept = if rows_only { found.2.iter().zip(&mutant_rows[at]).filter(|(_, rows)| **rows).map(|(score, _)| *score).collect() } else { found.2.clone() };
            (found.0, found.1, kept)
        }).collect()
    };
    let distinct_outputs = outputs.iter().map(|table| table.hash).collect::<std::collections::BTreeSet<_>>().len() > 1;
    let mut null_every: Vec<Vec<f64>> = vec![Vec::new(); d];
    let mut null_rows: Vec<Vec<f64>> = vec![Vec::new(); d];
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
            let found = run(Some(&order), true, &mut tallies);
            for size in 0..d {
                if let Some(auc) = auc_of(&per_size(&found, size, false)) {
                    null_every[size].push(auc);
                }
                if let Some(auc) = auc_of(&per_size(&found, size, true)) {
                    null_rows[size].push(auc);
                }
            }
        }
    }
    let mean = |values: &[f64]| (!values.is_empty()).then(|| values.iter().sum::<f64>() / values.len() as f64);
    let sizes: Vec<serde_json::Value> = (0..d).map(|size| {
        let every = per_size(&results, size, false);
        let rows = per_size(&results, size, true);
        serde_json::json!({
            "d": size + 1,
            "auc": auc_of(&every),
            "null": mean(&null_every[size]),
            "auc_rows": auc_of(&rows),
            "null_rows": mean(&null_rows[size]),
            "contingent": mean(&every.iter().map(|found| found.0 as f64).collect::<Vec<_>>()),
            "items": every.iter().map(|found| found.2.len()).sum::<usize>(),
        })
    }).collect();
    let terms: Vec<serde_json::Value> = held.iter().map(|(key, family)| serde_json::json!({"schema": key, "by_size": family.by_size, "roots": family.roots})).collect();
    let mut shapes: Vec<serde_json::Value> = Vec::new();
    for (hash, tally) in &tallies {
        if tally.gold_only + tally.mutant_only + tally.null_gold_only + tally.null_mutant_only == 0 {
            continue;
        }
        shapes.push(serde_json::json!([families.names.get(hash).unwrap_or_default(), tally.gold_only, tally.mutant_only, tally.compared, tally.null_gold_only, tally.null_mutant_only, tally.null_compared]));
    }
    Ok(serde_json::json!({
        "task": task_name, "sizes": sizes, "left_out": left_out, "shapes": shapes, "terms": terms,
        "walks": walks, "walk_seconds": walk_seconds, "seconds": started.elapsed().as_secs_f64(),
    }))
}

/// Which written kinds the generated shapes reach, by value: a kind is reached where a generated
/// root equals it at every sampled table and pair where the kind has a value.
pub fn reach(files: &[String], task_dir: &std::path::Path, d: usize, per_task: usize, sink: &mut impl std::io::Write) -> Result<(), String> {
    use crate::catalog::{pass, Kind, Record, Value};
    use crate::catalog_run::{pairs_of_task, parse_table};
    use crate::catalog_vector::shape_name;
    use crate::tablewalk::stored_of;
    let families = Generators::default();
    // Per written shape, its sums by point, and per generated root the same.
    let mut written: FastMap<String, Vec<(u32, u64, u64, u64)>> = FastMap::default();
    let mut generated: FastMap<u128, Vec<(u32, u64)>> = FastMap::default();
    let mut points = 0u32;
    for path in files {
        let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
        let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
        let train = data["train"].as_u64().ok_or("a file's train")? as usize;
        let task_path = task_dir.join(format!("{task_name}.json"));
        let task = arclog::task::read_task(&task_path).map_err(|error| format!("the task does not read: {error:?}"))?;
        let task_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&task_path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
        let grid = |fact: arclog::program::FactRelation, at: usize| {
            let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
            let mut cells = Vec::new();
            arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
            Table::new(2, cells)
        };
        let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
        let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
        let facts = pairs_of_task(&task_json, None);
        let constants = constants_of(&facts);
        let mut seen: Vec<String> = Vec::new();
        let mut taken = 0;
        let empty = Vec::new();
        for item in data["items"].as_array().unwrap_or(&empty) {
            for table in std::iter::once(&item["gold"]).chain(item["mutants"].as_array().unwrap_or(&empty).iter().take(1).map(|mutant| &mutant["table"])) {
                let Some(stored) = stored_of(table, train) else { continue };
                if taken >= per_task || seen.contains(&stored.key) || stored.types.len() > 8 || stored.rows.iter().any(|rows| rows.as_ref().is_none_or(|t| t.len == 0 || t.len > 2000)) {
                    continue;
                }
                seen.push(stored.key.clone());
                taken += 1;
                let family = families.get(&stored, d);
                let mut walker = Walker::new(&family);
                let leaves = leaves_of(&stored.rows, &inputs, &outputs, &constants);
                let map = walker.walk(&leaves, d as u8, None);
                let parsed = parse_table(table, train);
                let mut sums: FastMap<String, Vec<[u64; 3]>> = FastMap::default();
                let mut records: Vec<Record> = Vec::with_capacity(256);
                for (pair, fact) in facts.iter().enumerate().take(12) {
                    let Some(Some((rows, cells))) = parsed.rows.get(pair) else { continue };
                    records.clear();
                    pass(&crate::catalog::TableAt { kinds: &parsed.kinds, keys: &parsed.keys, rows: *rows, cells }, fact, &mut records);
                    for record in &records {
                        let word = match record.value {
                            Value::Bool(flag) => [WORD_NONEMPTY | u64::from(flag), 0, 0],
                            Value::Num(n) => [WORD_COUNT | n.max(0) as u64, WORD_SET | (n + 1).max(0) as u64, 0],
                            Value::Share(hits, of) if of > 0 => {
                                let shared = gcd(u64::from(hits), u64::from(of)).max(1);
                                [WORD_SET | (hash_words([u64::from(hits) / shared, u64::from(of) / shared]) as u64 & PAYLOAD) * u64::from(hits > 0), WORD_NONEMPTY | u64::from(hits == of), 0]
                            }
                            _ => continue,
                        };
                        let held = sums.entry(shape_name(record, &parsed.kinds)).or_insert_with(|| vec![[u64::MAX; 3]; train.min(12)]);
                        let at = &mut held[pair];
                        for (slot, value) in at.iter_mut().zip(word) {
                            if *slot == u64::MAX {
                                *slot = 0;
                            }
                            if value & PAYLOAD != 0 {
                                *slot = slot.wrapping_add(mix_word(value));
                            }
                        }
                    }
                }
                let _ = Kind::Other;
                for pair in 0..train.min(12) {
                    let point = points + pair as u32;
                    for (name, held) in &sums {
                        if held[pair][0] != u64::MAX {
                            written.entry(name.clone()).or_default().push((point, held[pair][0], held[pair][1], held[pair][2]));
                        }
                    }
                    for (hash, entry) in map.iter() {
                        if entry.sums[pair] != 0 {
                            generated.entry(*hash).or_default().push((point, entry.sums[pair]));
                        }
                    }
                }
                points += train.min(12) as u32;
            }
        }
    }
    // A generated root by its value at each point; a written shape's matches.
    let lookup: Vec<(u128, FastMap<u32, u64>)> = generated.iter().map(|(hash, list)| (*hash, list.iter().copied().collect())).collect();
    for (name, list) in &written {
        let mut found: [Vec<String>; 3] = [Vec::new(), Vec::new(), Vec::new()];
        for (reading, held) in found.iter_mut().enumerate() {
            let value_of = |item: &(u32, u64, u64, u64)| match reading {
                0 => item.1,
                1 => item.2,
                _ => item.3,
            };
            if reading == 2 || !list.iter().any(|item| value_of(item) != 0) {
                continue;
            }
            for (hash, values) in &lookup {
                if list.iter().all(|item| values.get(&item.0).copied().unwrap_or(0) == value_of(item)) {
                    held.push(families.names.get(hash).unwrap_or_default());
                    if held.len() >= 200 {
                        break;
                    }
                }
            }
            held.sort_by_key(String::len);
            held.truncate(3);
        }
        let nonzero = list.iter().filter(|item| item.1 != 0).count();
        let distinct: std::collections::BTreeSet<u64> = list.iter().map(|item| item.1).collect();
        let line = serde_json::json!({"shape": name, "points": list.len(), "nonzero": nonzero, "values": distinct.len(), "value": found[0], "second": found[1]});
        writeln!(sink, "{line}").map_err(|error| error.to_string())?;
    }
    Ok(())
}


/// Per schema, one term per class of observed values among the terms up to size 2: the terms to
/// extend. A term that is empty on every sampled table has no class, and a term equal to one
/// that stands before it has none of its own.
pub fn classes(files: &[String], task_dir: &std::path::Path, per_schema: usize) -> Result<std::collections::HashMap<String, Vec<u32>>, String> {
    use crate::tablewalk::stored_of;
    struct Held {
        family: Arc<Generated>,
        signature: Vec<u128>,
        some: Vec<bool>,
        tables: usize,
        seen: HashSet<u128>,
    }
    let families = Generators::default();
    let mut by_schema: std::collections::HashMap<String, Held> = std::collections::HashMap::new();
    for path in files {
        let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
        let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
        let train = data["train"].as_u64().ok_or("a file's train")? as usize;
        let task_path = task_dir.join(format!("{task_name}.json"));
        let task = arclog::task::read_task(&task_path).map_err(|error| format!("the task does not read: {error:?}"))?;
        let task_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&task_path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
        let grid = |fact: arclog::program::FactRelation, at: usize| {
            let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
            let mut cells = Vec::new();
            arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
            Table::new(2, cells)
        };
        let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
        let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
        let facts = crate::catalog_run::pairs_of_task(&task_json, None);
        let constants = constants_of(&facts);
        let empty = Vec::new();
        let mut walkers: FastMap<u128, (Arc<Generated>, usize)> = FastMap::default();
        let _ = &mut walkers;
        for item in data["items"].as_array().unwrap_or(&empty) {
            for table in std::iter::once(&item["gold"]).chain(item["mutants"].as_array().unwrap_or(&empty).iter().map(|mutant| &mutant["table"])) {
                let Some(stored) = stored_of(table, train) else { continue };
                if stored.types.len() > 8 || stored.rows.iter().any(|rows| rows.as_ref().is_some_and(|t| t.len > 2000)) {
                    continue;
                }
                let held = by_schema.entry(stored.key.clone()).or_insert_with(|| {
                    let family = families.get(&stored, 2);
                    let count = family.terms.len();
                    Held { family, signature: vec![0; count], some: vec![false; count], tables: 0, seen: HashSet::new() }
                });
                let content = hash_words(stored.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |t| [t.hash as u64, (t.hash >> 64) as u64])));
                if held.tables >= per_schema || !held.seen.insert(content) {
                    continue;
                }
                held.tables += 1;
                let family = held.family.clone();
                let mut walker = Walker::new(&family);
                let leaves = leaves_of(&stored.rows, &inputs, &outputs, &constants);
                walker.observe(&leaves, hash_words([content as u64, (content >> 64) as u64, task_name.len() as u64]), &mut held.signature, &mut held.some);
            }
        }
    }
    let mut out = std::collections::HashMap::new();
    for (key, held) in by_schema {
        let family = &held.family;
        let mut seen: HashSet<u128> = HashSet::new();
        let mut chosen = Vec::new();
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            if !held.some[at] {
                continue;
            }
            if seen.insert(held.signature[at]) {
                chosen.push(at as u32);
            }
            let _ = term;
        }
        out.insert(key, chosen);
    }
    Ok(out)
}


/// The hex id of a shape in a dump.
fn shape_id(hash: u128) -> String {
    format!("{:016x}", hash as u64)
}

/// One task's stable generated shapes per item, in the form the scoring reads, one result for
/// each size up to `d`. A table lists the shapes it holds that are contingent on the item's
/// base tables and that not every one of the item's tables holds, since those alone can tell
/// two tables apart. An item with a table this path leaves out has no sides.
pub fn dump_task(path: &str, task_dir: &std::path::Path, families: &Generators, derangements: &std::collections::BTreeMap<String, Option<Vec<usize>>>, d: usize) -> Result<(String, Vec<serde_json::Value>, u64, f64), String> {
    use crate::tablewalk::{active_entry, stored_of, Stored};
    let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let task_path = task_dir.join(format!("{task_name}.json"));
    let task = arclog::task::read_task(&task_path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let task_json: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&task_path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let grid = |fact: arclog::program::FactRelation, at: usize| {
        let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
        let mut cells = Vec::new();
        arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
        Table::new(2, cells)
    };
    let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
    let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
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
    struct Parsed {
        query: String,
        reads: Vec<Stored>,
        gold: Option<Stored>,
        mutants: Vec<Stored>,
    }
    let good = |stored: &Stored| stored.types.len() <= 8 && stored.rows.iter().all(|rows| rows.as_ref().is_none_or(|table| table.len <= 2000));
    let mut parsed: Vec<Parsed> = Vec::new();
    for item in data["items"].as_array().ok_or("a file's items")? {
        let query = item["query"].as_str().unwrap_or("").to_string();
        let gold = stored_of(&item["gold"], train);
        let reads: Option<Vec<Stored>> = item["reads"].as_object().map_or(Some(Vec::new()), |reads| reads.values().map(|table| stored_of(table, train)).collect());
        let mutants: Option<Vec<Stored>> = item["mutants"].as_array().and_then(|mutants| mutants.iter().map(|mutant| stored_of(&mutant["table"], train)).collect());
        match (gold, reads, mutants) {
            (Some(gold), Some(reads), Some(mutants)) if good(&gold) && reads.iter().all(&good) && mutants.iter().all(&good) => parsed.push(Parsed { query, reads, gold: Some(gold), mutants }),
            _ => parsed.push(Parsed { query, reads: Vec::new(), gold: None, mutants: Vec::new() }),
        }
    }
    // The parsed file is far larger than its tables, so it leaves here.
    drop(data);
    let mut tables: Vec<&Stored> = vec![&input_table];
    for item in parsed.iter().filter(|item| item.gold.is_some()) {
        tables.extend(item.reads.iter());
        tables.extend(item.gold.iter());
        tables.extend(item.mutants.iter());
    }
    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    for table in &tables {
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), families.get(table, d)));
        }
    }
    let mut walkers: Vec<(String, Walker<'_>)> = held.iter().map(|(key, family)| (key.clone(), Walker::new(family))).collect();
    let mut walks = 0u64;
    let mut walk_seconds = 0f64;
    let mut sides = |order: Option<&[usize]>| -> Vec<Vec<serde_json::Value>> {
        let facts = crate::catalog_run::pairs_of_task(&task_json, order);
        let constants = constants_of(&facts);
        let moved: Vec<Arc<Table>> = (0..train).map(|at| outputs[order.map_or(at, |order| order[at])].clone()).collect();
        let mut done: FastMap<u128, Arc<FastMap<u128, u8>>> = FastMap::default();
        let mut map_of = |stored: &Stored| -> Arc<FastMap<u128, u8>> {
            let content = hash_words(stored.key.bytes().map(u64::from).chain(stored.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |table| [table.hash as u64, (table.hash >> 64) as u64]))));
            if let Some(found) = done.get(&content) {
                return found.clone();
            }
            let walker = &mut walkers.iter_mut().find(|(key, _)| *key == stored.key).expect("a schema's walker").1;
            let started = std::time::Instant::now();
            let leaves = leaves_of(&stored.rows, &inputs, &moved, &constants);
            let full = walker.walk(&leaves, d as u8, None);
            let map: Arc<FastMap<u128, u8>> = Arc::new(full.iter().filter(|(_, entry)| active_entry(Some(*entry), train)).map(|(name, entry)| (*name, entry.size)).collect());
            walks += 1;
            walk_seconds += started.elapsed().as_secs_f64();
            done.insert(content, map.clone());
            map
        };
        let input_map = map_of(&input_table);
        parsed.iter().map(|item| {
            let Some(gold) = &item.gold else { return vec![serde_json::Value::Null; d] };
            let bases: Vec<Arc<FastMap<u128, u8>>> = std::iter::once(input_map.clone()).chain(item.reads.iter().map(&mut map_of)).collect();
            let mut own: Vec<Arc<FastMap<u128, u8>>> = vec![map_of(gold)];
            own.extend(item.mutants.iter().map(&mut map_of));
            (1..=d).map(|size| {
                let holds_at = |map: &FastMap<u128, u8>, name: &u128| map.get(name).is_some_and(|held| usize::from(*held) <= size);
                let mut lists: Vec<Vec<String>> = vec![Vec::new(); own.len()];
                let mut seen: HashSet<u128> = HashSet::new();
                for map in &own {
                    for name in map.keys() {
                        if !seen.insert(*name) || !own.iter().any(|table| holds_at(table, name)) {
                            continue;
                        }
                        if bases.iter().all(|base| holds_at(base, name)) || own.iter().all(|table| holds_at(table, name)) {
                            continue;
                        }
                        for (list, table) in lists.iter_mut().zip(&own) {
                            if holds_at(table, name) {
                                list.push(shape_id(*name));
                            }
                        }
                    }
                }
                for list in &mut lists {
                    list.sort_unstable();
                }
                serde_json::json!({"tables": lists, "contexts": [[]]})
            }).collect()
        }).collect()
    };
    let truth = sides(None);
    let order = derangements.get(&task_name).and_then(Option::as_ref);
    let deranged = order.map(|order| sides(Some(order)));
    let results = (0..d).map(|size| {
        let items: Vec<serde_json::Value> = parsed.iter().enumerate().map(|(at, item)| {
            let null_side = deranged.as_ref().map_or(serde_json::Value::Null, |found| found[at][size].clone());
            serde_json::json!({"query": item.query, "last": item.query == last_query, "true": truth[at][size], "null": null_side})
        }).collect();
        serde_json::json!({"task": task_name, "items": items})
    }).collect();
    Ok((task_name, results, walks, walk_seconds))
}
