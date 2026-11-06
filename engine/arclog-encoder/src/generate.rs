//! Generated features: the shapes over a table up to a size, enumerated over parts, and evaluated
//! natively in one pass per table. The size of a term counts its operators and its parts, each
//! once. Nothing here is written for one feature.
//!
//! A walk gives each root's numbers at each instance of a table: an example, or a model at an
//! example where the example has several. What the numbers are is the specification's section on
//! vectors, and `table_vector` combines the instances into a table's vector.

use std::collections::HashSet;
use std::sync::{Arc, Mutex};

use arclog::types::ValueType;

use crate::expression::Op;
use crate::gen_constants::{constant_parts, constant_tables, number_of};
use crate::gen_parts::{clear_views, flat, PartStep};
use crate::native::{hash_words, Evaluator, FastMap, Step, Table, Val, WORD_COUNT, WORD_NONEMPTY, WORD_SET};
use crate::stored::{mix_word, shape_text};

pub const READS_INPUT: u8 = 1;
pub const READS_OUTPUT: u8 = 2;
pub const READS_TABLE: u8 = 4;
const NO_TERM: u32 = u32::MAX;
const MAX_PROJECTED: usize = 3;
const MAX_COLUMNS: usize = 8;
const PAYLOAD: u64 = (1 << 62) - 1;
/// The leaves that stand first among a family's terms.
const LEAF_TABLE: u32 = 0;
const LEAF_OUTPUT: u32 = 1;
const LEAF_INPUT: u32 = 2;
/// A leaf of the two grids of an example, for the parts that read both.
const LEAF_GRIDS: u32 = 3;
const FIRST_CONSTANT: u32 = 4;

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
    /// `nonempty`, on a relation of no columns.
    Holds,
    /// `cardinality`.
    Rows,
    /// `cardinality`, and the `ratio` of its rows over its first relation's.
    Share,
    /// `cardinality`, and the `value-set` of its one number column.
    Number,
    /// The `ratio` of its first relation over its second, and the other way.
    Against,
}

/// What a root reads of a term at an instance.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum RootOf {
    Nonempty,
    Cardinality,
    /// The term's rows over its first relation's.
    Share,
    ValueSet,
    /// The first relation's rows over the second's.
    Over,
    /// The second relation's rows over the first's.
    Under,
}

impl RootOf {
    /// Whether the root's two numbers are the greatest and the least, as a fraction's are.
    pub fn is_ratio(self) -> bool {
        matches!(self, RootOf::Share | RootOf::Over | RootOf::Under)
    }
}

pub struct Term {
    step: Option<Step>,
    a: u32,
    b: u32,
    columns: Vec<Column>,
    flags: u8,
    size: u8,
    root: RootKind,
    roots: Vec<(u128, RootOf)>,
    text: String,
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

impl Generated {
    /// The family over a table of the column types `types`, up to size `d` in parts. Two Ident
    /// columns of one source can meet, and an Ident column whose source is open meets no other.
    pub fn of(types: &[ValueType], d: usize, names: &NameStore) -> Generated {
        let columns: Vec<String> = (0..types.len()).map(|at| format!("T{at}")).collect();
        Generated::with_column_names(types, &columns, d, names)
    }

    /// As [`Generated::of`], with the columns under the names a program gives them, so a term's text
    /// reads that program's table. A shape's name reads the names of [`Generated::of`].
    pub fn with_column_names(types: &[ValueType], column_names: &[String], d: usize, names: &NameStore) -> Generated {
        let mut family = Generated { terms: Vec::new(), first_term: 0, by_size: Vec::new(), roots: 0 };
        let source_of = |at: usize| -> u16 {
            let first = types.iter().position(|other| *other == types[at] && *other != ValueType::OPEN_IDENT).unwrap_or(at);
            100 + first as u16
        };
        let table_columns: Vec<Column> = types.iter().enumerate().map(|(at, ty)| Column { name: column_names[at].clone(), ty: ty.clone(), source: source_of(at) }).collect();
        let grid = |source: u16| vec![Column { name: "P".to_string(), ty: ValueType::Position, source }, Column { name: "Col".to_string(), ty: ValueType::Color, source }];
        family.push_leaf("T", table_columns, READS_TABLE, 0);
        family.push_leaf("output", grid(0), READS_OUTPUT, 0);
        family.push_leaf("input", grid(0), READS_INPUT, 0);
        family.push_leaf("grids", Vec::new(), READS_INPUT | READS_OUTPUT, 0);
        let parts = constant_parts();
        for part in &parts {
            let columns = part.columns.iter().map(|(name, ty)| Column { name: (*name).to_string(), ty: ty.clone(), source: ident_source(&part.name) }).collect();
            let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
            family.push_leaf(&part.name, columns, flags, 1);
        }
        family.first_term = family.terms.len();
        let constants: Vec<u32> = (FIRST_CONSTANT..family.first_term as u32).filter(|at| parts[(*at - FIRST_CONSTANT) as usize].meets_table).collect();
        // Size 1: over the leaves. The table's own rows give its own count.
        let own_columns = family.terms[LEAF_TABLE as usize].columns.clone();
        family.push(Step::Part(Box::new(PartStep::Same)), LEAF_TABLE, NO_TERM, own_columns, 0, "T".to_string(), RootKind::Rows);
        let own_rows = family.terms.len() as u32 - 1;
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
            let below: Vec<u32> = constants.iter().copied().chain((family.first_term as u32..family.by_size[0] as u32).filter(|at| family.terms[*at as usize].size > 0)).collect();
            for at in below {
                family.extend_term(at, 2, true);
            }
        }
        // A number of a term of size 1 over the table alone against each number a grid gives. Each
        // has three parts by the count, and they stand here in full, since a table's number equal
        // to one of the output's is a rule that hand walks use. A table's counts meet a grid's
        // through `ratio`, which is 1 where they are equal.
        if d == 2 {
            let numbers: Vec<u32> = constants.iter().copied().filter(|at| {
                let term = &family.terms[*at as usize];
                term.flags & (READS_INPUT | READS_OUTPUT) != 0 && term.columns.iter().any(|column| is_number(&column.ty))
            }).collect();
            let terms: Vec<u32> = (family.first_term as u32..family.by_size[0] as u32).filter(|at| {
                let term = &family.terms[*at as usize];
                term.flags == READS_TABLE && term.size > 0 && term.columns.len() <= MAX_PROJECTED && term.columns.iter().any(|column| is_number(&column.ty))
            }).collect();
            for at in terms {
                for number in &numbers {
                    family.number_meets(at, *number, 3);
                }
            }
            let bases: Vec<u32> = [LEAF_OUTPUT, LEAF_INPUT].into_iter().chain(constants.iter().copied().filter(|at| {
                let term = &family.terms[*at as usize];
                term.flags & (READS_INPUT | READS_OUTPUT) != 0 && !term.columns.is_empty()
            })).collect();
            let tops: Vec<u32> = (family.first_term as u32..family.by_size[0] as u32).filter(|at| {
                let term = &family.terms[*at as usize];
                *at == own_rows || (term.flags == READS_TABLE && matches!(term.step, Some(Step::Project { .. })) && term.columns.len() == 1)
            }).collect();
            for top in tops {
                for base in &bases {
                    let text = format!("{} {}", family.terms[top as usize].text, family.terms[*base as usize].text);
                    family.push(Step::Part(Box::new(PartStep::Same)), top, *base, Vec::new(), 2, text, RootKind::Against);
                }
            }
        }
        family.by_size.push(family.terms.len());
        // The name of each root.
        let mut held = names.begin();
        let mut roots = 0;
        let texts_of_first: Vec<String> = family.terms.iter().map(|term| term.text.clone()).collect();
        for term in family.terms.iter_mut().skip(family.first_term) {
            if term.flags & READS_TABLE == 0 {
                continue;
            }
            let number_column = term.columns.first().map_or(String::new(), |column| column.name.clone());
            let left_text = texts_of_first[term.a as usize].clone();
            let texts: Vec<(String, RootOf)> = match term.root {
                RootKind::Holds => vec![(format!("(nonempty {})", term.text), RootOf::Nonempty)],
                RootKind::Rows => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality)],
                RootKind::Share => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality), (format!("(ratio {} {left_text})", term.text), RootOf::Share)],
                RootKind::Number => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality), (format!("(value-set {} {number_column})", term.text), RootOf::ValueSet)],
                RootKind::Against => {
                    let right_text = texts_of_first[term.b as usize].clone();
                    vec![(format!("(ratio {left_text} {right_text})"), RootOf::Over), (format!("(ratio {right_text} {left_text})"), RootOf::Under)]
                }
            };
            term.roots = texts.into_iter().map(|(text, of)| {
                let shape = shape_text(&text, "T", types);
                let hash = hash_words(shape.bytes().map(u64::from));
                held.add(hash, shape, term.flags, term.size);
                (hash, of)
            }).collect();
            roots += term.roots.len();
        }
        family.roots = roots;
        // A walk reads the steps and the roots.
        if std::env::var_os("GENERATE_KEEP_TEXT").is_none() {
            for term in &mut family.terms {
                term.text = String::new();
                term.columns = Vec::new();
            }
        }
        family
    }

    /// Each operator and part over a term, with what stays within the size.
    fn extend_term(&mut self, at: u32, size: u8, with_grids_alone: bool) {
        let flags = self.terms[at as usize].flags;
        let _ = with_grids_alone;
        if flags & READS_TABLE != 0 {
            self.unary_operators(at, size);
            self.parts_of(at, size);
            self.binary(at, LEAF_OUTPUT, size, true);
            self.binary(LEAF_OUTPUT, at, size, false);
            self.binary(at, LEAF_INPUT, size, true);
            self.binary(LEAF_INPUT, at, size, false);
        } else {
            self.binary(LEAF_TABLE, at, size, true);
            self.binary(at, LEAF_TABLE, size, false);
        }
    }

    /// `semijoin` and `all` of a term on one number column of it and one of a part.
    fn number_meets(&mut self, l: u32, r: u32, size: u8) {
        let (left, right) = (self.terms[l as usize].columns.clone(), self.terms[r as usize].columns.clone());
        let (left_text, right_text) = (self.terms[l as usize].text.clone(), self.terms[r as usize].text.clone());
        for (a, x) in left.iter().enumerate() {
            for (b, y) in right.iter().enumerate() {
                if !is_number(&x.ty) || !is_number(&y.ty) {
                    continue;
                }
                let pair_text = format!("({} {})", x.name, y.name);
                let (left_at, right_at): (Box<[u16]>, Box<[u16]>) = (vec![a as u16].into_boxed_slice(), vec![b as u16].into_boxed_slice());
                self.push(Step::Semijoin { left: left_at.clone(), right: right_at.clone() }, l, r, left.clone(), size, format!("(semijoin {left_text} {right_text} {pair_text})"), RootKind::Share);
                self.push(Step::All { left: left_at, right: right_at, outer: Box::new([]) }, l, r, Vec::new(), size, format!("(all {left_text} {right_text} () {pair_text})"), RootKind::Holds);
            }
        }
    }

    fn push_leaf(&mut self, text: &str, columns: Vec<Column>, flags: u8, size: u8) {
        self.terms.push(Term { step: None, a: NO_TERM, b: NO_TERM, columns, flags, size, root: RootKind::Rows, roots: Vec::new(), text: text.to_string(), used: true });
    }

    #[allow(clippy::too_many_arguments)]
    fn push(&mut self, step: Step, a: u32, b: u32, mut columns: Vec<Column>, size: u8, text: String, root: RootKind) {
        if columns.len() > MAX_COLUMNS {
            return;
        }
        // A derived relation's columns are its labels, each with its first letter in upper case.
        for column in &mut columns {
            if column.name.starts_with(|first: char| first.is_lowercase()) {
                column.name = crate::expand::label_of(&column.name);
            }
        }
        let flags = self.terms[a as usize].flags | if b == NO_TERM { 0 } else { self.terms[b as usize].flags };
        let root = if root == RootKind::Against {
            RootKind::Against
        } else if columns.is_empty() {
            RootKind::Holds
        } else if root == RootKind::Rows && columns.len() == 1 && is_number(&columns[0].ty) {
            RootKind::Number
        } else {
            root
        };
        self.terms[a as usize].used = true;
        if b != NO_TERM {
            self.terms[b as usize].used = true;
        }
        self.terms.push(Term { step: Some(step), a, b, columns, flags, size, root, roots: Vec::new(), text, used: false });
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
                        // One label at the two columns has the narrower type.
                        let kept: Vec<Column> = columns.iter().enumerate().filter(|(place, _)| Some(*place) != dropped).map(|(place, column)| {
                            let mut column = column.clone();
                            if op == Op::Eq && place == a && columns[b].ty.is_below(&column.ty) {
                                column.ty = columns[b].ty.clone();
                            }
                            column
                        }).collect();
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
            let names: Vec<&str> = group.iter().map(|at| columns[usize::from(*at)].name.as_str()).collect();
            out.push((group.into_boxed_slice(), format!("(T*:{})", names.join(","))));
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
        let fresh = |name: &str, ty: ValueType, source: u16| Column { name: unique(name, &columns), ty, source };
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
                    add(PartStep::NeighborhoodClass { p }, grid, vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)], format!("(neighborhood-class {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::NeighborColorClass { p }, grid, vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)], format!("(neighbor-color-class {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::SameColorNeighbors { p }, grid, vec![column.clone(), fresh("Col", ValueType::Color, 0), fresh("N", ValueType::Nat, 0)], format!("(same-color-neighbors {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::Distance { p }, grid, vec![one("P", ValueType::Position, 0), one("K", ValueType::Nat, 0)], format!("(distance {text} {name} {label})"), RootKind::Rows);
                }
                add(PartStep::FrameExtent { p }, NO_TERM, vec![one("A", ValueType::Axis, 0), one("N", ValueType::Int, 0)], format!("(frame-extent {text} {name})"), RootKind::Rows);
                for (other, second) in columns.iter().enumerate() {
                    if other != place && second.ty == ValueType::Position {
                        add(PartStep::Displacement { a: p, b: other as u16 }, NO_TERM, with(&[("V", ValueType::Offset, 0)]), format!("(displacement {text} {name} {})", second.name), RootKind::Rows);
                    }
                }
                add(PartStep::Around { p }, NO_TERM, vec![fresh("Q", ValueType::Position, 0)], format!("(around {text} {name})"), RootKind::Rows);
                add(PartStep::Neighbors { p }, NO_TERM, with(&[("D", ValueType::Dir8, 0), ("Q", ValueType::Position, 0)]), format!("(neighbors {text} {name})"), RootKind::Rows);
                add(PartStep::Split { p }, NO_TERM, with(&[("A", ValueType::Axis, 0), ("Along", ValueType::Box, 0)]), format!("(split {text} {name})"), RootKind::Rows);
                add(PartStep::Margin { p }, NO_TERM, with(&[("D", ValueType::Dir, 0), ("K", ValueType::Int, 0)]), format!("(margin {text} {name})"), RootKind::Rows);
                add(PartStep::CornerDist { p }, NO_TERM, with(&[("Diag", ValueType::DiagDir, 0), ("K", ValueType::Int, 0)]), format!("(corner-dist {text} {name})"), RootKind::Rows);
                add(PartStep::Parity { p }, NO_TERM, with(&[("Diag", ValueType::DiagDir, 0), ("K", ValueType::Nat, 0)]), format!("(parity {text} {name})"), RootKind::Rows);
                add(PartStep::BorderDistance { p }, NO_TERM, with(&[("K", ValueType::Int, 0)]), format!("(border-distance {text} {name})"), RootKind::Rows);
                for (keys, key_text) in Self::key_options(&columns, &[place]) {
                    let heads = key_columns(&keys);
                    let extended = |extra: Vec<Column>| -> Vec<Column> { heads.iter().cloned().chain(extra).collect() };
                    add(PartStep::Pieces { keys: keys.clone(), p, four: false }, NO_TERM, extended(vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Pieces { keys: keys.clone(), p, four: true }, NO_TERM, extended(vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces4 {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::FullLines { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("Along", ValueType::Box, 0)]), format!("(full-lines {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::BoxOf { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("B", ValueType::Box, 0)]), format!("(box-of {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::RelBox { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("X_rel", ValueType::Box, 0)]), format!("(cells-in-box {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::ShapeClass { keys: keys.clone(), p, turned: false }, NO_TERM, extended(vec![fresh("Id", ValueType::OPEN_IDENT, 900)]), format!("(shape-class {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::ShapeClass { keys: keys.clone(), p, turned: true }, NO_TERM, extended(vec![fresh("Id", ValueType::OPEN_IDENT, 901)]), format!("(shape-class-d4 {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Holes { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(holes {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Symmetry { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(symmetry {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::TouchesEdge { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(touches-edge {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::FillsBox { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(fills-box {text} {key_text} {name})"), RootKind::Rows);
                    for (v, value) in columns.iter().enumerate() {
                        if value.ty == ValueType::Color && v != place && !keys.contains(&(v as u16)) {
                            for (turned, label) in [(false, "occurs"), (true, "occurs-d4")] {
                                for (grid, grid_label) in [(LEAF_OUTPUT, "output"), (LEAF_INPUT, "input")] {
                                    add(PartStep::Occurs { keys: keys.clone(), p, v: v as u16, turned }, grid, extended(vec![fresh("V", ValueType::Box, 0)]), format!("({label} {text} {key_text} {name} {} {grid_label})", value.name), RootKind::Rows);
                                }
                            }
                        }
                    }
                }
            }
            if column.ty == ValueType::Box {
                for (grid, label) in [(LEAF_OUTPUT, "output"), (LEAF_INPUT, "input")] {
                    add(PartStep::Inside { b: p }, grid, with(&[("P", ValueType::Position, 0), ("Col", ValueType::Color, 0)]), format!("(inside {text} {name} {label})"), RootKind::Rows);
                    add(PartStep::BoxExtent { b: p }, grid, with(&[("A", ValueType::Axis, 0), ("N", ValueType::Int, 0)]), format!("(box-extent {text} {name} {label})"), RootKind::Rows);
                }
                let place_of = |label: &str| fresh(label, ValueType::Position, 0);
                let colors = |two: bool| -> Vec<Column> { if two { vec![one("Col", ValueType::Color, 0), one("Col_2", ValueType::Color, 0)] } else { vec![one("Col", ValueType::Color, 0)] } };
                for (kept, label) in [(true, "kept"), (false, "changed")] {
                    let columns_read: Vec<Column> = [column.clone(), place_of("P"), place_of("X_rel")].into_iter().chain(colors(!kept)).collect();
                    add(PartStep::BoxRead { b: p, kept }, LEAF_GRIDS, columns_read, format!("(box-{label} {text} {name})"), RootKind::Rows);
                    for (x, cell) in columns.iter().enumerate() {
                        if cell.ty == ValueType::Position {
                            let read: Vec<Column> = [column.clone(), cell.clone(), place_of("P")].into_iter().chain(colors(!kept)).collect();
                            add(PartStep::BoxFrameRead { b: p, x: x as u16, kept }, LEAF_GRIDS, read, format!("(box-frame-{label} {text} {name} {})", cell.name), RootKind::Rows);
                            let read: Vec<Column> = [column.clone(), cell.clone(), place_of("X_rel")].into_iter().chain(colors(!kept)).collect();
                            add(PartStep::BoxCellRead { b: p, x: x as u16, kept }, LEAF_GRIDS, read, format!("(box-cell-{label} {text} {name} {})", cell.name), RootKind::Rows);
                        }
                    }
                }
            }
            if matches!(column.ty, ValueType::Box | ValueType::Offset) {
                add(PartStep::BoxMargin { b: p }, NO_TERM, with(&[("D", ValueType::Dir, 0), ("K", ValueType::Int, 0)]), format!("(box-margin {text} {name})"), RootKind::Rows);
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
            let with_n: Vec<Column> = heads.iter().cloned().chain([fresh("N", ValueType::Nat, 0)]).collect();
            if !keys.is_empty() {
                add(PartStep::Count { keys: keys.clone() }, NO_TERM, with_n, format!("(count {text} {key_text})"), RootKind::Rows);
            }
            if !keys.is_empty() && keys.len() < columns.len() {
                let with_id: Vec<Column> = heads.iter().cloned().chain([fresh("Id", ValueType::OPEN_IDENT, 902)]).collect();
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
            // A label at a column and a narrower one has the narrower type.
            let mut narrowed = left.clone();
            for (a, b) in &pairs {
                let (own, other) = (&mut narrowed[usize::from(*a)], &right[usize::from(*b)]);
                if own.ty != other.ty && other.ty.is_below(&own.ty) {
                    own.ty = other.ty.clone();
                }
            }
            if joins {
                let kept: Box<[u16]> = (0..right.len() as u16).filter(|at| !right_at.contains(at)).collect();
                let mut columns = narrowed.clone();
                for at in kept.iter() {
                    let column = &right[usize::from(*at)];
                    let name = unique(&column.name, &columns);
                    columns.push(Column { name, ty: column.ty.clone(), source: column.source });
                }
                self.push(Step::Join { left: left_at.clone(), right: right_at.clone(), kept, left_arity: left.len() as u16 }, l, r, columns, size, format!("(join {left_text} {right_text} {pair_text})"), RootKind::Rows);
            }
            self.push(Step::Semijoin { left: left_at.clone(), right: right_at.clone() }, l, r, narrowed.clone(), size, format!("(semijoin {left_text} {right_text} {pair_text})"), RootKind::Share);
            self.push(Step::Antijoin { left: left_at.clone(), right: right_at.clone() }, l, r, left.clone(), size, format!("(antijoin {left_text} {right_text} {pair_text})"), RootKind::Rows);
            self.push(Step::All { left: left_at.clone(), right: right_at.clone(), outer: Box::new([]) }, l, r, Vec::new(), size, format!("(all {left_text} {right_text} () {pair_text})"), RootKind::Holds);
            for (at, column) in left.iter().enumerate() {
                if !left_at.contains(&(at as u16)) {
                    self.push(Step::All { left: left_at.clone(), right: right_at.clone(), outer: vec![at as u16].into_boxed_slice() }, l, r, vec![column.clone()], size, format!("(all {left_text} {right_text} ({}) {pair_text})", column.name), RootKind::Rows);
                }
            }
            if let [(a, b)] = pairs[..] {
                let (a_name, b_name) = (&left[usize::from(a)].name, &right[usize::from(b)].name);
                // A key that determines whether a row has a match.
                if left.len() >= 2 {
                    for (at, column) in left.iter().enumerate() {
                        if at != usize::from(a) {
                            self.push(Step::Part(Box::new(PartStep::DeterminesFlag { keys: vec![at as u16].into_boxed_slice(), a, b })), l, r, Vec::new(), size, format!("(determines-flag {left_text} {right_text} ({}) {a_name} {b_name})", column.name), RootKind::Holds);
                        }
                    }
                }
                if left[usize::from(a)].ty == ValueType::Position && right[usize::from(b)].ty == ValueType::Position {
                    self.push(Step::Part(Box::new(PartStep::SharedLine { a, b })), l, r, left.clone(), size, format!("(shared-line {left_text} {right_text} {a_name} {b_name})"), RootKind::Share);
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
        "changed-components" | "changed-component-boxes" => 5,
        _ => 0,
    }
}

/// A number: an integer, or a fraction in lowest terms.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Number {
    pub top: i32,
    pub bottom: u32,
}

impl Number {
    pub fn whole(value: i64) -> Number {
        Number { top: value.clamp(i64::from(i32::MIN), i64::from(i32::MAX)) as i32, bottom: 1 }
    }

    pub fn fraction(top: u64, bottom: u64) -> Number {
        let shared = gcd(top, bottom).max(1);
        Number { top: (top / shared).min(i32::MAX as u64) as i32, bottom: (bottom / shared).min(u64::from(u32::MAX)) as u32 }
    }

    pub fn float(self) -> f64 {
        f64::from(self.top) / f64::from(self.bottom.max(1))
    }

    fn above(self, other: Number) -> bool {
        i64::from(self.top) * i64::from(other.bottom.max(1)) > i64::from(other.top) * i64::from(self.bottom.max(1))
    }

    fn plus(self, other: Number) -> Number {
        if self.bottom <= 1 && other.bottom <= 1 {
            return Number::whole(i64::from(self.top) + i64::from(other.top));
        }
        let (a, b) = (u64::from(self.bottom.max(1)), u64::from(other.bottom.max(1)));
        let top = i64::from(self.top) * b as i64 + i64::from(other.top) * a as i64;
        if top < 0 {
            return Number::whole(top / (a * b) as i64);
        }
        Number::fraction(top as u64, a * b)
    }
}

/// A root's numbers at one instance. A root with no slot, or with `state` 0, is at its default.
#[derive(Clone, Copy, Debug, Default)]
pub struct Slot {
    /// The greatest of its ground expressions' values.
    pub greatest: Number,
    /// Their sum, or for a ratio their least.
    pub second: Number,
    /// A commutative hash of the multiset of those values other than the default.
    pub digest: u64,
    /// 0 where every value is the default, 1 where one is not, 2 where a bound stopped one.
    pub state: u8,
}

pub const SLOT_DEFAULT: u8 = 0;
pub const SLOT_VALUE: u8 = 1;
pub const SLOT_NO_VALUE: u8 = 2;

/// Each root's numbers at each instance of a table.
#[derive(Default)]
pub struct RootTable {
    pub index: FastMap<u128, u32>,
    pub slots: Vec<Slot>,
    pub stride: usize,
    /// What each root reads, its size, and which kind of root it is.
    pub meta: Vec<(u8, u8, RootOf)>,
}

impl RootTable {
    fn slots_of(&mut self, hash: u128, flags: u8, size: u8, of: RootOf) -> usize {
        let next = self.meta.len() as u32;
        let stride = self.stride;
        let at = *self.index.entry(hash).or_insert(next);
        if at == next {
            self.meta.push((flags, size, of));
            self.slots.resize(self.slots.len() + stride, Slot::default());
        }
        at as usize * stride
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
/// A count past this stands for "no value": a bound stopped the term.
const NO_COUNT: u32 = u32::MAX;

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

fn count_of(value: &Val) -> u32 {
    rows_of(value).map_or(NO_COUNT, |count| count.min(u64::from(NO_COUNT - 1)) as u32)
}

fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}

/// The value of a root at an instance: no value, or a number and the word that hashes it.
fn root_value(of: RootOf, rows: u32, left: u32, other: u32, number: u32) -> Option<(Number, u64)> {
    let share = |top: u32, bottom: u32| -> Option<(Number, u64)> {
        // A ratio with no rows in its second relation is left out, and stands at its default.
        if top == NO_COUNT || bottom == NO_COUNT {
            return None;
        }
        if bottom == 0 || top == 0 {
            return Some((Number::whole(0), 0));
        }
        let held = Number::fraction(u64::from(top), u64::from(bottom));
        Some((held, WORD_SET | (hash_words([u64::from(held.top as u32), u64::from(held.bottom)]) as u64 & PAYLOAD)))
    };
    match of {
        RootOf::Nonempty => (rows != NO_COUNT).then(|| (Number::whole(i64::from(rows > 0)), if rows > 0 { WORD_NONEMPTY | 1 } else { 0 })),
        RootOf::Cardinality => (rows != NO_COUNT).then(|| (Number::whole(i64::from(rows)), if rows > 0 { WORD_COUNT | u64::from(rows) } else { 0 })),
        RootOf::Share => share(rows, left),
        RootOf::Over => share(rows, other),
        RootOf::Under => share(other, rows),
        RootOf::ValueSet => {
            if rows == NO_COUNT {
                return None;
            }
            // One member gives a number, and any other set gives no value, which here is the
            // default of a set with no member.
            (number > 0).then(|| (Number::whole(i64::from(number) - 1), WORD_SET | u64::from(number))).or(Some((Number::whole(0), 0)))
        }
    }
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
            // The tables those values held are gone, so an address they had can hold another.
            clear_views();
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

    /// Each root's numbers at each instance of `leaves`. The first `train` instances have an
    /// output: a root that reads the output has a value at those alone, and any other root at
    /// every instance. With `only_output`, only the roots that read the output enter.
    pub fn walk(&mut self, leaves: &[Vec<Val>], train: usize, only_output: bool) -> RootTable {
        self.keep_within_budget();
        let family = self.family;
        let instances = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut table = RootTable { stride: instances, ..RootTable::default() };
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let at = at as u32;
            let first = std::mem::take(&mut ids[term.a as usize]);
            let second = if term.b == NO_TERM { Vec::new() } else { std::mem::take(&mut ids[term.b as usize]) };
            let step = term.step.as_ref().expect("a term has a step");
            let reads_output = term.flags & READS_OUTPUT != 0;
            let scope = if reads_output { train.min(instances) } else { instances };
            let wanted = term.flags & READS_TABLE != 0 && (reads_output || !only_output);
            let extended = term.used;
            let mut own = Vec::new();
            let idle = first[..scope].iter().all(|id| *id == 1) || first[..scope].iter().all(|id| *id == 0) || (matches!(step, Step::Join { .. } | Step::Semijoin { .. }) && second[..scope].iter().all(|id| *id == 1));
            if extended {
                own.reserve(instances);
                for pair in 0..scope {
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
                own.resize(instances, 0);
            }
            if wanted && !idle && !term.roots.is_empty() {
                for pair in 0..scope {
                    let (id, b) = (first[pair], if term.b == NO_TERM { NO_TERM } else { second[pair] });
                    let (rows, number) = if extended {
                        let value = &self.values[own[pair] as usize];
                        (count_of(value), if term.root == RootKind::Number { number_word(value) } else { 0 })
                    } else {
                        let key = (at, id, b);
                        match self.counts.get(&key) {
                            Some(found) => *found,
                            None => {
                                let value = self.apply(step, id, b);
                                let found = (count_of(&value), if term.root == RootKind::Number { number_word(&value) } else { 0 });
                                self.counts.insert(key, found);
                                found
                            }
                        }
                    };
                    let left = count_of(&self.values[id as usize]);
                    let other = if term.b == NO_TERM { NO_COUNT } else { count_of(&self.values[b as usize]) };
                    for (hash, of) in &term.roots {
                        let value = root_value(*of, rows, left, other, number);
                        // Nothing to add at a default value, which is a slot's own state.
                        if matches!(value, Some((_, 0))) {
                            continue;
                        }
                        let base = table.slots_of(*hash, term.flags, term.size, *of);
                        let slot = &mut table.slots[base + pair];
                        match value {
                            None => slot.state = SLOT_NO_VALUE,
                            Some((held, word)) => {
                                if slot.state == SLOT_DEFAULT {
                                    slot.state = SLOT_VALUE;
                                    slot.greatest = held;
                                    slot.second = held;
                                } else {
                                    if held.above(slot.greatest) {
                                        slot.greatest = held;
                                    }
                                    slot.second = if of.is_ratio() {
                                        if slot.second.above(held) { held } else { slot.second }
                                    } else {
                                        slot.second.plus(held)
                                    };
                                }
                                slot.digest = slot.digest.wrapping_add(mix_word(word));
                            }
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
        table
    }

    /// The count of rows at each instance of each term whose text holds `pattern`, leaves
    /// included, for a check against the expression that a term stands for.
    pub fn term_counts(&mut self, leaves: &[Vec<Val>], train: usize, pattern: &str) -> Vec<(String, Vec<Option<u64>>)> {
        let family = self.family;
        let pairs = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut out = Vec::new();
        for (at, term) in family.terms.iter().enumerate() {
            if at >= family.first_term {
                let step = term.step.as_ref().expect("a term has a step");
                let scope = if term.flags & READS_OUTPUT != 0 { train } else { pairs };
                let mut own = Vec::with_capacity(pairs);
                for pair in 0..scope {
                    let a = ids[term.a as usize][pair];
                    let b = if term.b == NO_TERM { NO_TERM } else { ids[term.b as usize][pair] };
                    let value = if term.text.contains(pattern) || term.used { self.apply(step, a, b) } else { Val::None };
                    own.push(self.value_id(value));
                }
                own.resize(pairs, 0);
                ids.push(own);
            }
            if term.text.contains(pattern) {
                out.push((term.text.clone(), ids[at].iter().map(|id| rows_of(&self.values[*id as usize])).collect()));
            }
        }
        out
    }
}

impl Generated {
    /// The count of terms, and of the leaves that stand before them.
    pub fn counts(&self) -> (usize, usize) {
        (self.terms.len(), self.first_term)
    }

    /// The count of a term's roots.
    pub fn term_roots(&self, at: usize) -> usize {
        self.terms[at].roots.len()
    }

    /// Whether a term stands for two relations, whose ratios are its roots.
    pub fn is_pair_term(&self, at: usize) -> bool {
        self.terms[at].root == RootKind::Against
    }

    /// A term's text, the names of its columns and types, what it reads, and whether it has roots,
    /// where the family keeps them.
    pub fn term_info(&self, at: usize) -> (&str, Vec<(String, ValueType)>, u8) {
        let term = &self.terms[at];
        (&term.text, term.columns.iter().map(|column| (column.name.clone(), column.ty.clone())).collect(), term.flags)
    }
}

impl Walker<'_> {
    /// The rows at each instance of each term that `chosen` picks, with what they read computed on
    /// the way, for a check against the expression a term stands for.
    pub fn term_values(&mut self, leaves: &[Vec<Val>], train: usize, chosen: &dyn Fn(usize) -> bool) -> Vec<(usize, Vec<Val>)> {
        let family = self.family;
        let pairs = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut out = Vec::new();
        for (at, held) in ids.iter().enumerate().skip(FIRST_CONSTANT as usize) {
            if chosen(at) {
                out.push((at, held.iter().map(|id| self.values[*id as usize].clone()).collect()));
            }
        }
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let picked = chosen(at);
            let step = term.step.as_ref().expect("a term has a step");
            let scope = if term.flags & READS_OUTPUT != 0 { train } else { pairs };
            let mut own = Vec::with_capacity(pairs);
            for pair in 0..scope {
                let id = if picked || term.used {
                    let a = ids[term.a as usize][pair];
                    let b = if term.b == NO_TERM { NO_TERM } else { ids[term.b as usize][pair] };
                    let value = self.apply(step, a, b);
                    self.value_id(value)
                } else {
                    0
                };
                own.push(id);
            }
            own.resize(pairs, 0);
            if picked {
                out.push((at, own.iter().map(|id| self.values[*id as usize].clone()).collect()));
            }
            ids.push(own);
        }
        out
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

/// The leaves of a walk: the table's rows, the grids, and the constant parts at each instance, where
/// `example_of` gives the example of each instance. An example with no output has no value at the
/// leaves that read it.
pub fn leaves_at(rows: &[Option<Arc<Table>>], example_of: &[usize], inputs: &[Arc<Table>], outputs: &[Arc<Table>], constants: &[Vec<Option<Arc<Table>>>]) -> Vec<Vec<Val>> {
    let output_at = |example: usize| outputs.get(example);
    let mut out = vec![
        rows.iter().map(|table| table.clone().map_or(Val::None, Val::of_table)).collect::<Vec<_>>(),
        example_of.iter().map(|at| output_at(*at).map_or(Val::None, |table| Val::of_table(table.clone()))).collect(),
        example_of.iter().map(|at| Val::of_table(inputs[*at].clone())).collect(),
        example_of.iter().map(|at| output_at(*at).map_or(Val::None, |table| Val::of_pair(inputs[*at].clone(), table.clone()))).collect(),
    ];
    let count = constants.first().map_or(0, Vec::len);
    for part in 0..count {
        out.push(example_of.iter().map(|at| constants[*at][part].clone().map_or(Val::None, Val::of_table)).collect());
    }
    out
}

/// Each constant part's rows at each train pair, and at each test input those that read no output.
pub fn constants_of(facts: &[crate::catalog_facts::PairFacts], tests: &[crate::catalog_facts::GridFacts]) -> Vec<Vec<Option<Arc<Table>>>> {
    clear_views();
    let mut out: Vec<Vec<Option<Arc<Table>>>> = facts.iter().map(|fact| constant_tables(fact).into_iter().map(Some).collect()).collect();
    out.extend(tests.iter().map(crate::gen_constants::input_only_tables));
    out
}

/// Where the names of roots go: a map in memory, or a file that each name reaches once.
#[derive(Default)]
pub struct NameStore {
    names: Mutex<FastMap<u128, String>>,
    file: Option<Mutex<(HashSet<u64>, Box<dyn std::io::Write + Send>)>>,
}

pub enum NameWriter<'a> {
    Map(std::sync::MutexGuard<'a, FastMap<u128, String>>),
    File(std::sync::MutexGuard<'a, (HashSet<u64>, Box<dyn std::io::Write + Send>)>),
}

impl NameWriter<'_> {
    fn add(&mut self, hash: u128, shape: String, flags: u8, size: u8) {
        match self {
            NameWriter::Map(map) => {
                map.entry(hash).or_insert(shape);
            }
            NameWriter::File(file) => {
                let held = &mut **file;
                if held.0.insert(hash as u64) {
                    let _ = std::io::Write::write_all(&mut held.1, format!("{:016x}\t{shape}\t{flags}\t{size}\n", hash as u64).as_bytes());
                }
            }
        }
    }
}

impl NameStore {
    pub fn to_file(path: &str) -> Result<NameStore, String> {
        let file = crate::zio::writer(path, true)?;
        Ok(NameStore { names: Mutex::default(), file: Some(Mutex::new((HashSet::new(), file))) })
    }

    /// Writes the name of a root that no family holds.
    pub fn add_root(&self, hash: u128, shape: String, flags: u8) {
        self.begin().add(hash, shape, flags, 1);
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

    /// Each root's name that the store holds in memory.
    pub fn all(&self) -> Vec<(u128, String)> {
        self.names.lock().expect("no panic").iter().map(|(hash, name)| (*hash, name.clone())).collect()
    }
}

/// The terms that the cache of families holds at most; past it, the oldest families leave.
const CACHED_TERMS: usize = 12_000_000;

/// The families of each schema, kept in a bounded cache, and the name of each root.
#[derive(Default)]
pub struct Generators {
    held: Mutex<(FastMap<u128, (Arc<Generated>, u64)>, u64)>,
    pub names: NameStore,
}

impl Generators {
    pub fn get(&self, stored: &crate::stored::Stored, d: usize) -> Arc<Generated> {
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
        let family = Arc::new(Generated::of(&stored.types, d, &self.names));
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

