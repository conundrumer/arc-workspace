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
use crate::refine::{self, bit, Claim, Refined, Rejected, Within};
use crate::refine_parts::{self, PartPlan, RelationInput};
use crate::stored::{mix_word, shape_text};

pub const READS_INPUT: u8 = 1;
pub const READS_OUTPUT: u8 = 2;
pub const READS_TABLE: u8 = 4;
pub const READS_SECOND: u8 = 8;
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
    /// The term's rows over the count of examples.
    OverExamples,
}

impl RootOf {
    /// Whether the root's two numbers are the greatest and the least, as a fraction's are.
    pub fn is_ratio(self) -> bool {
        matches!(self, RootOf::Share | RootOf::Over | RootOf::Under | RootOf::OverExamples)
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
    /// What its fragment gives, for a part.
    plan: Option<Arc<PartPlan>>,
}

/// What a term's text stands in for, where a normal form leaves out one of two orders.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
enum FormKind {
    #[default]
    Base,
    Project,
    Filter,
    Extension,
}

/// How a term is built, for the normal forms. It holds names, since a filter that drops a column moves places.
#[derive(Clone, Debug, Default)]
struct Form {
    kind: FormKind,
    /// The order of the last filter over its base.
    last_filter: u64,
    /// The columns the filters read.
    filter_reads: Vec<String>,
    /// Each `semijoin` among the filters.
    semijoins: Vec<u64>,
    /// Each pair of columns, or a column and `0`, that a `select` compares.
    selects: Vec<(String, String)>,
    /// For an extension: its relation's columns, those it reads, and whether every row of its relation stands in it.
    own: Vec<String>,
    reads: Vec<String>,
    total: bool,
    /// The order of an extension among those over one relation.
    order: u64,
}

/// A term that no derivation reaches, kept for the check of its rule.
pub struct RejectedTerm {
    pub rule: &'static str,
    pub claim: Claim,
    pub step: Step,
    pub a: u32,
    pub b: u32,
    pub text: String,
    pub columns: Vec<String>,
    /// The term it is, where it is one of the family's.
    pub other: Option<String>,
}

/// Where a rejected term's text says what it stands for.
enum Partner {
    None,
    /// The same operator over the term's first relation's first relation.
    OverBase,
    /// The two operators in the other order.
    Swap,
    Text(String),
}

const MARK: &str = "\u{1}";

/// The terms over a table of one schema.
pub struct Generated {
    terms: Vec<Term>,
    pub first_term: usize,
    pub by_size: Vec<usize>,
    pub roots: usize,
    refined: Vec<Refined>,
    forms: Vec<Form>,
    /// The terms each rule rejected.
    pub rejected_by_rule: std::collections::BTreeMap<&'static str, u64>,
    pub rejected: Vec<RejectedTerm>,
    keep_text: bool,
    /// Where the family is built with no rule, for a count of what the rules remove.
    no_rules: bool,
    /// Whether its terms read a table in its lifted form.
    task_wide: bool,
    /// Whether the next term stands whatever a rule says of it: a named feature, whose parts read more than a count.
    force_next: bool,
    /// The terms that a part of the base tables names.
    diff_terms: Vec<u32>,
    /// Whether the family's roots read the base tables and no other table.
    over_grids: bool,
    /// Whether each of the family's roots reads two tables.
    two_tables: bool,
}

pub fn is_number(ty: &ValueType) -> bool {
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

const MAX_PAIRINGS: usize = 24;

/// Each way to pair every column of `from` with its own column of `to`, or none where there are more than `MAX_PAIRINGS`, so that no value depends on the
/// columns' order.
fn pairings(from: &[Column], to: &[Column]) -> Vec<Vec<(u16, u16)>> {
    fn extend(from: &[Column], to: &[Column], held: &mut Vec<(u16, u16)>, out: &mut Vec<Vec<(u16, u16)>>) -> bool {
        let Some(column) = from.get(held.len()) else {
            out.push(held.clone());
            return out.len() <= MAX_PAIRINGS;
        };
        for (at, other) in to.iter().enumerate() {
            if meets(column, other) && !held.iter().any(|pair| usize::from(pair.1) == at) {
                held.push((held.len() as u16, at as u16));
                let room = extend(from, to, held, out);
                held.pop();
                if !room {
                    return false;
                }
            }
        }
        true
    }
    let mut out = Vec::new();
    if !from.is_empty() && !extend(from, to, &mut Vec::new(), &mut out) {
        out.clear();
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
        let mut family = Generated::empty();
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
        family.leaf_refinements(types, &parts);
        let constants: Vec<u32> = (FIRST_CONSTANT..family.first_term as u32).filter(|at| parts[(*at - FIRST_CONSTANT) as usize].meets_table).collect();
        // Size 1: over the leaves. The table's own rows give its own count.
        let own_columns = family.terms[LEAF_TABLE as usize].columns.clone();
        family.push(Step::Part(Box::new(PartStep::Same)), LEAF_TABLE, NO_TERM, own_columns, 0, "T".to_string(), RootKind::Rows);
        let own_rows = family.terms.len() as u32 - 1;
        family.unary_operators(LEAF_TABLE, 1);
        family.product();
        family.parts_of(LEAF_TABLE, 1);
        family.unary_operators(LEAF_OUTPUT, 1);
        family.unary_operators(LEAF_INPUT, 1);
        family.binary(LEAF_TABLE, LEAF_OUTPUT, 1, true);
        family.binary(LEAF_OUTPUT, LEAF_TABLE, 1, false);
        family.binary(LEAF_TABLE, LEAF_INPUT, 1, true);
        family.binary(LEAF_INPUT, LEAF_TABLE, 1, false);
        family.same_rows(LEAF_OUTPUT);
        family.same_rows(LEAF_INPUT);
        family.binary(LEAF_OUTPUT, LEAF_INPUT, 1, true);
        family.binary(LEAF_INPUT, LEAF_OUTPUT, 1, false);
        family.by_size.push(family.terms.len());
        family.diff_is_named();
        // Size 2: over each term of size 1, the constants among them.
        if d >= 2 {
            let below: Vec<u32> = constants.iter().copied().chain((family.first_term as u32..family.by_size[0] as u32).filter(|at| family.terms[*at as usize].size > 0 && !family.diff_terms.contains(at))).collect();
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
            // A ratio with a relation of at most one row follows from the other relation's count.
            let bases: Vec<u32> = [LEAF_OUTPUT, LEAF_INPUT].into_iter().chain(constants.iter().copied().filter(|at| {
                let term = &family.terms[*at as usize];
                term.flags & (READS_INPUT | READS_OUTPUT) != 0 && !term.columns.is_empty() && (family.no_rules || !family.refined[*at as usize].one_row())
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
        family.name_roots(types, names);
        family
    }

    /// The family of two tables of a state, T and U: how the rows, values and cells of one stand to the
    /// other's, and what the two say together of the output.
    pub fn of_two_tables(t_types: &[ValueType], u_types: &[ValueType], names: &NameStore) -> Generated {
        let t_names: Vec<String> = (0..t_types.len()).map(|at| format!("T{at}")).collect();
        let u_names: Vec<String> = (0..u_types.len()).map(|at| format!("T{}", t_types.len() + at)).collect();
        Generated::two_tables_with_names(t_types, &t_names, u_types, &u_names, "U", names)
    }

    /// As [`Generated::of_two_tables`], with the columns under the names a program gives them, and U's text.
    pub fn two_tables_with_names(t_types: &[ValueType], t_names: &[String], u_types: &[ValueType], u_names: &[String], u_text: &str, names: &NameStore) -> Generated {
        let mut family = Generated::empty();
        family.two_tables = true;
        let all: Vec<ValueType> = t_types.iter().chain(u_types).cloned().collect();
        let source_of = |at: usize| -> u16 {
            let first = all.iter().position(|other| *other == all[at] && *other != ValueType::OPEN_IDENT).unwrap_or(at);
            100 + first as u16
        };
        let t_columns: Vec<Column> = t_types.iter().enumerate().map(|(at, ty)| Column { name: t_names[at].clone(), ty: ty.clone(), source: source_of(at) }).collect();
        let u_columns: Vec<Column> = u_types.iter().enumerate().map(|(at, ty)| Column { name: u_names[at].clone(), ty: ty.clone(), source: source_of(t_types.len() + at) }).collect();
        let grid = || vec![Column { name: "P".to_string(), ty: ValueType::Position, source: 0 }, Column { name: "Col".to_string(), ty: ValueType::Color, source: 0 }];
        family.push_leaf("T", t_columns.clone(), READS_TABLE, 0);
        family.push_leaf("output", grid(), READS_OUTPUT, 0);
        family.push_leaf("input", grid(), READS_INPUT, 0);
        family.push_leaf("grids", Vec::new(), READS_INPUT | READS_OUTPUT, 0);
        let parts = constant_parts();
        for part in &parts {
            let columns = part.columns.iter().map(|(name, ty)| Column { name: (*name).to_string(), ty: ty.clone(), source: ident_source(&part.name) }).collect();
            let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
            family.push_leaf(&part.name, columns, flags, 1);
        }
        let u_leaf = family.terms.len() as u32;
        family.push_leaf(u_text, u_columns.clone(), READS_SECOND, 0);
        family.first_term = family.terms.len();
        family.leaf_refinements(t_types, &parts);
        let mut second = Refined::with_arity(u_types.len());
        second.add_key(second.all_columns());
        for (at, ty) in u_types.iter().enumerate() {
            if *ty == ValueType::Nat {
                second.low[at] = Some(0);
            }
        }
        second.within.push(Within { columns: (0..u_types.len() as u16).collect(), of: u_leaf, at: (0..u_types.len() as u16).collect() });
        family.refined.push(second);
        // The rows of each kept by the other.
        family.binary(LEAF_TABLE, u_leaf, 1, true);
        family.binary(u_leaf, LEAF_TABLE, 1, false);
        family.same_rows(u_leaf);
        family.by_size.push(family.terms.len());
        let places = |columns: &[Column], kinds: &[ValueType]| -> Vec<u16> { (0..columns.len() as u16).filter(|at| kinds.contains(&columns[usize::from(*at)].ty)).collect() };
        // The value sets of a column of each.
        let mut own_projects: FastMap<(u32, u16), u32> = FastMap::default();
        for (a, x) in t_columns.iter().enumerate() {
            for (b, y) in u_columns.iter().enumerate() {
                if !meets(x, y) {
                    continue;
                }
                let (a, b) = (a as u16, b as u16);
                family.push(Step::Part(Box::new(PartStep::SameValues { a, b })), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("(same-values T {u_text} {} {})", x.name, y.name), RootKind::Holds);
                // A column's values are its `project` at every width, so a shape's name does not depend on a table's width.
                let mut project_of = |family: &mut Generated, leaf: u32, place: u16| -> u32 {
                    *own_projects.entry((leaf, place)).or_insert_with(|| {
                        let column = family.terms[leaf as usize].columns[usize::from(place)].clone();
                        let text = format!("(project {} {})", family.terms[leaf as usize].text, column.name);
                        family.force_next = true;
                        family.push(Step::Project { columns: vec![place].into_boxed_slice() }, leaf, NO_TERM, vec![column], 1, text, RootKind::Rows);
                        family.terms.len() as u32 - 1
                    })
                };
                let (t_values, u_values) = (project_of(&mut family, LEAF_TABLE, a), project_of(&mut family, u_leaf, b));
                if t_values != LEAF_TABLE || u_values != u_leaf {
                    let (t_text, u_values_text) = (family.terms[t_values as usize].text.clone(), family.terms[u_values as usize].text.clone());
                    let (a_at, b_at) = (if t_values == LEAF_TABLE { a } else { 0 }, if u_values == u_leaf { b } else { 0 });
                    let (left, right): (Box<[u16]>, Box<[u16]>) = (vec![a_at].into_boxed_slice(), vec![b_at].into_boxed_slice());
                    let t_own = family.terms[t_values as usize].columns.clone();
                    let u_own = family.terms[u_values as usize].columns.clone();
                    let pair = format!("({} {})", x.name, y.name);
                    let back = format!("({} {})", y.name, x.name);
                    family.push(Step::Semijoin { left: left.clone(), right: right.clone() }, t_values, u_values, t_own, 2, format!("(semijoin {t_text} {u_values_text} {pair})"), RootKind::Share);
                    family.push(Step::Semijoin { left: right.clone(), right: left.clone() }, u_values, t_values, u_own, 2, format!("(semijoin {u_values_text} {t_text} {back})"), RootKind::Share);
                    family.push(Step::All { left: left.clone(), right: right.clone(), outer: Box::new([]) }, t_values, u_values, Vec::new(), 2, format!("(all {t_text} {u_values_text} () {pair})"), RootKind::Holds);
                    family.push(Step::All { left: right, right: left, outer: Box::new([]) }, u_values, t_values, Vec::new(), 2, format!("(all {u_values_text} {t_text} () {back})"), RootKind::Holds);
                }
            }
        }
        let cells = [ValueType::Position];
        let boxes = [ValueType::Box];
        // A table's cells inside the other's boxes, and the boxes that hold them.
        for (cell_leaf, box_leaf) in [(LEAF_TABLE, u_leaf), (u_leaf, LEAF_TABLE)] {
            let (cell_columns, box_columns) = (family.terms[cell_leaf as usize].columns.clone(), family.terms[box_leaf as usize].columns.clone());
            let (cell_text, box_text) = (family.terms[cell_leaf as usize].text.clone(), family.terms[box_leaf as usize].text.clone());
            for a in places(&cell_columns, &cells) {
                for b in places(&box_columns, &boxes) {
                    let (cell_name, box_name) = (&cell_columns[usize::from(a)].name, &box_columns[usize::from(b)].name);
                    family.push(Step::Part(Box::new(PartStep::InsideBoxes { a, b })), cell_leaf, box_leaf, cell_columns.clone(), 1, format!("(inside-boxes {cell_text} {box_text} {cell_name} {box_name})"), RootKind::Share);
                    family.push(Step::Part(Box::new(PartStep::BoxesHolding { a: b, b: a })), box_leaf, cell_leaf, box_columns.clone(), 1, format!("(boxes-holding {box_text} {cell_text} {box_name} {cell_name})"), RootKind::Share);
                }
            }
        }
        // The cells of each key of one that are those of a key of the other.
        for (first, other) in [(LEAF_TABLE, u_leaf), (u_leaf, LEAF_TABLE)] {
            let (own, theirs) = (family.terms[first as usize].columns.clone(), family.terms[other as usize].columns.clone());
            let (own_text, their_text) = (family.terms[first as usize].text.clone(), family.terms[other as usize].text.clone());
            for a in places(&own, &cells) {
                for b in places(&theirs, &cells) {
                    for (keys, key_text) in Self::key_options(&own, &[usize::from(a)]) {
                        for (others, other_text) in Self::key_options(&theirs, &[usize::from(b)]) {
                            let heads: Vec<Column> = keys.iter().map(|at| own[usize::from(*at)].clone()).collect();
                            let (a_name, b_name) = (&own[usize::from(a)].name, &theirs[usize::from(b)].name);
                            for (turned, word) in [(false, "same-shape"), (true, "same-shape-d4")] {
                                family.push(Step::Part(Box::new(PartStep::SameShape { keys: keys.clone(), a, others: others.clone(), b, turned })), first, other, heads.clone(), 1, format!("({word} {own_text} {their_text} {key_text} {a_name} {other_text} {b_name})"), RootKind::Rows);
                            }
                        }
                    }
                }
            }
        }
        // What the two say together of the output color.
        for a in places(&t_columns, &cells) {
            for b in places(&u_columns, &cells) {
                let join_text = format!("(join T {u_text} ({} {}))", t_columns[usize::from(a)].name, u_columns[usize::from(b)].name);
                let Some(join) = family.terms.iter().position(|term| term.text == join_text) else { continue };
                let columns = family.terms[join].columns.clone();
                let free = |column: &Column| !matches!(column.ty, ValueType::Position | ValueType::Box | ValueType::Offset);
                for v in (0..t_columns.len()).filter(|at| *at != usize::from(a) && free(&columns[*at])) {
                    for w in (t_columns.len()..columns.len()).filter(|at| free(&columns[*at])) {
                        let text = format!("(determines-jointly {join_text} {} {} {})", columns[usize::from(a)].name, columns[v].name, columns[w].name);
                        family.push(Step::Part(Box::new(PartStep::DeterminesJointly { p: a, v: v as u16, w: w as u16 })), join as u32, LEAF_GRIDS, Vec::new(), 2, text, RootKind::Holds);
                    }
                }
            }
        }
        // The output's cells and the changed cells that T holds, with or without U.
        let changed = FIRST_CONSTANT + parts.iter().position(|part| part.name == "output-diff").expect("the part of the output's changed cells") as u32;
        let colors = [ValueType::Color];
        for covered in [LEAF_OUTPUT, changed] {
            let (covered_columns, covered_text) = (family.terms[covered as usize].columns.clone(), family.terms[covered as usize].text.clone());
            for a in places(&t_columns, &cells) {
                let mut own_sets: Vec<(Vec<u16>, Vec<u16>)> = vec![(vec![0], vec![a])];
                own_sets.extend(places(&t_columns, &colors).into_iter().map(|c| (vec![0, 1], vec![a, c])));
                for (left, right) in own_sets {
                    let pairs: Vec<String> = left.iter().zip(&right).map(|(l, r)| format!("({} {})", covered_columns[usize::from(*l)].name, t_columns[usize::from(*r)].name)).collect();
                    let before = family.terms.len();
                    let t_text = format!("(semijoin {covered_text} T {})", pairs.join(" "));
                    family.push(Step::Semijoin { left: left.clone().into_boxed_slice(), right: right.into_boxed_slice() }, covered, LEAF_TABLE, covered_columns.clone(), 2, t_text.clone(), RootKind::Share);
                    if family.terms.len() == before {
                        continue;
                    }
                    let held = before as u32;
                    for b in places(&u_columns, &cells) {
                        let mut their_sets: Vec<(Vec<u16>, Vec<u16>)> = vec![(vec![0], vec![b])];
                        their_sets.extend(places(&u_columns, &colors).into_iter().map(|c| (vec![0, 1], vec![b, c])));
                        for (l, r) in their_sets {
                            let pairs: Vec<String> = l.iter().zip(&r).map(|(l, r)| format!("({} {})", covered_columns[usize::from(*l)].name, u_columns[usize::from(*r)].name)).collect();
                            let pairs = pairs.join(" ");
                            family.push(Step::Semijoin { left: l.clone().into_boxed_slice(), right: r.clone().into_boxed_slice() }, held, u_leaf, covered_columns.clone(), 3, format!("(semijoin {t_text} {u_text} {pairs})"), RootKind::Share);
                            family.push(Step::Antijoin { left: l.into_boxed_slice(), right: r.into_boxed_slice() }, held, u_leaf, covered_columns.clone(), 3, format!("(antijoin {t_text} {u_text} {pairs})"), RootKind::Share);
                        }
                    }
                }
            }
        }
        family.by_size.push(family.terms.len());
        family.name_roots(&all, names);
        family
    }

    /// The family of a pair's own numbers: each part that reads a grid, and what stands over it, with no table.
    pub fn of_grids(d: usize, names: &NameStore) -> Generated {
        let mut family = Generated::empty();
        family.over_grids = true;
        let grid = || vec![Column { name: "P".to_string(), ty: ValueType::Position, source: 0 }, Column { name: "Col".to_string(), ty: ValueType::Color, source: 0 }];
        family.push_leaf("T", Vec::new(), READS_TABLE, 0);
        family.push_leaf("output", grid(), READS_OUTPUT, 0);
        family.push_leaf("input", grid(), READS_INPUT, 0);
        family.push_leaf("grids", Vec::new(), READS_INPUT | READS_OUTPUT, 0);
        let parts = constant_parts();
        for part in &parts {
            let columns = part.columns.iter().map(|(name, ty)| Column { name: (*name).to_string(), ty: ty.clone(), source: ident_source(&part.name) }).collect();
            let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
            family.push_leaf(&part.name, columns, flags, 1);
        }
        family.first_term = family.terms.len();
        family.leaf_refinements(&[], &parts);
        let reading: Vec<u32> = (FIRST_CONSTANT..family.first_term as u32).filter(|at| family.terms[*at as usize].flags != 0 && !family.terms[*at as usize].columns.is_empty()).collect();
        for at in &reading {
            let (columns, text) = (family.terms[*at as usize].columns.clone(), family.terms[*at as usize].text.clone());
            family.force_next = true;
            family.push(Step::Part(Box::new(PartStep::Same)), *at, NO_TERM, columns, 1, text, RootKind::Rows);
            // The count of a relation of at most one row follows from its value.
            let mut refined = family.refined[*at as usize].clone();
            refined.count_follows = refined.one_row() && family.terms[*at as usize].columns.len() == 1 && is_number(&family.terms[*at as usize].columns[0].ty);
            *family.refined.last_mut().expect("the term just pushed") = refined;
        }
        family.by_size.push(family.terms.len());
        if d >= 2 {
            for at in &reading {
                family.unary_operators(*at, 2);
                family.parts_of(*at, 2);
            }
        }
        family.by_size.push(family.terms.len());
        family.name_roots(&[], names);
        family
    }

    /// The name of each root, and what a walk does not read dropped from the terms.
    fn name_roots(&mut self, types: &[ValueType], names: &NameStore) {
        let family = self;
        let task_wide = family.task_wide;
        let over_grids = family.over_grids;
        let two_tables = family.two_tables;
        let mut held = names.begin();
        let mut roots = 0;
        let texts_of_first: Vec<String> = family.terms.iter().map(|term| term.text.clone()).collect();
        let first_term = family.first_term;
        let follows: Vec<bool> = family.refined.iter().map(|refined| refined.count_follows).collect();
        for (at, term) in family.terms.iter_mut().enumerate().skip(first_term) {
            if (term.flags & READS_TABLE == 0 && !over_grids) || (two_tables && term.flags & READS_SECOND == 0) {
                continue;
            }
            let count_follows = follows[at];
            let number_column = term.columns.first().map_or(String::new(), |column| column.name.clone());
            let left_text = texts_of_first[term.a as usize].clone();
            let mut texts: Vec<(String, RootOf)> = match term.root {
                RootKind::Holds => vec![(format!("(nonempty {})", term.text), RootOf::Nonempty)],
                // A count that follows from a smaller term's has no root.
                RootKind::Rows if count_follows => Vec::new(),
                RootKind::Rows => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality)],
                RootKind::Share if count_follows => Vec::new(),
                RootKind::Share => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality), (format!("(ratio {} {left_text})", term.text), RootOf::Share)],
                RootKind::Number if count_follows => vec![(format!("(value-set {} {number_column})", term.text), RootOf::ValueSet)],
                RootKind::Number => vec![(format!("(cardinality {})", term.text), RootOf::Cardinality), (format!("(value-set {} {number_column})", term.text), RootOf::ValueSet)],
                RootKind::Against => {
                    let right_text = texts_of_first[term.b as usize].clone();
                    vec![(format!("(ratio {left_text} {right_text})"), RootOf::Over), (format!("(ratio {right_text} {left_text})"), RootOf::Under)]
                }
            };
            // A task-wide count over the rows of every example depends on how many examples there are.
            if task_wide && !count_follows && matches!(term.root, RootKind::Rows | RootKind::Share | RootKind::Number) && term.columns.iter().any(|column| column.ty == ValueType::Example) {
                texts.push((format!("(ratio {} (project ex_input E))", term.text), RootOf::OverExamples));
            }
            term.roots = texts.into_iter().map(|(text, of)| {
                let shape = shape_text(&text, "T", types);
                let shape = if task_wide { format!("task {shape}") } else { shape };
                let hash = hash_words(shape.bytes().map(u64::from));
                held.add(hash, shape, term.flags, term.size);
                (hash, of)
            }).collect();
            roots += term.roots.len();
        }
        family.roots = roots;
        // A walk reads the steps and the roots, and the leaves' refinements.
        if !family.keep_text {
            for term in &mut family.terms {
                term.text = String::new();
                term.columns = Vec::new();
                term.plan = None;
            }
            family.refined.truncate(family.first_term);
            family.forms = Vec::new();
        }
    }

    /// The family of a table's task-wide terms, as the specification's section on them gives: the
    /// table in its lifted form, with `E` as a column like any other, and the grids with theirs. A
    /// pair of operators reads `E` only where its pairs list it, so one example meets another.
    pub fn task_wide(types: &[ValueType], d: usize, names: &NameStore) -> Generated {
        let mut family = Generated::empty();
        family.task_wide = true;
        let source_of = |at: usize| -> u16 {
            let first = types.iter().position(|other| *other == types[at] && *other != ValueType::OPEN_IDENT).unwrap_or(at);
            100 + first as u16
        };
        let example = || Column { name: "E".to_string(), ty: ValueType::Example, source: 0 };
        let table_columns: Vec<Column> = std::iter::once(example()).chain(types.iter().enumerate().map(|(at, ty)| Column { name: format!("T{at}"), ty: ty.clone(), source: source_of(at) })).collect();
        let grid = || vec![example(), Column { name: "P".to_string(), ty: ValueType::Position, source: 0 }, Column { name: "Col".to_string(), ty: ValueType::Color, source: 0 }];
        family.push_leaf("T", table_columns, READS_TABLE, 0);
        family.push_leaf("ex_output", grid(), READS_OUTPUT, 0);
        family.push_leaf("ex_input", grid(), READS_INPUT, 0);
        family.push_leaf("grids", Vec::new(), READS_INPUT | READS_OUTPUT, 0);
        family.first_term = family.terms.len();
        let lifted: Vec<ValueType> = std::iter::once(ValueType::Example).chain(types.iter().cloned()).collect();
        family.lifted_refinements(&lifted);
        let own_columns = family.terms[LEAF_TABLE as usize].columns.clone();
        family.push(Step::Part(Box::new(PartStep::Same)), LEAF_TABLE, NO_TERM, own_columns, 0, "T".to_string(), RootKind::Rows);
        let own_rows = family.terms.len() as u32 - 1;
        family.unary_operators(LEAF_TABLE, 1);
        family.lifted_parts(LEAF_TABLE, 1);
        family.binary(LEAF_TABLE, LEAF_OUTPUT, 1, true);
        family.binary(LEAF_OUTPUT, LEAF_TABLE, 1, false);
        family.binary(LEAF_TABLE, LEAF_INPUT, 1, true);
        family.binary(LEAF_INPUT, LEAF_TABLE, 1, false);
        family.across_examples(LEAF_TABLE, 1);
        family.by_size.push(family.terms.len());
        if d >= 2 {
            let below: Vec<u32> = (family.first_term as u32..family.by_size[0] as u32).filter(|at| family.terms[*at as usize].size > 0).collect();
            for at in below {
                family.unary_operators(at, 2);
                family.lifted_parts(at, 2);
                family.binary(at, LEAF_OUTPUT, 2, true);
                family.binary(LEAF_OUTPUT, at, 2, false);
                family.binary(at, LEAF_INPUT, 2, true);
                family.binary(LEAF_INPUT, at, 2, false);
            }
        }
        family.common_values(own_rows);
        family.groupings(own_rows);
        family.by_size.push(family.terms.len());
        family.name_roots(types, names);
        family
    }

    /// What each leaf of a task-wide family holds.
    fn lifted_refinements(&mut self, types: &[ValueType]) {
        let mut table = Refined::with_arity(types.len());
        table.add_key(table.all_columns());
        for (at, ty) in types.iter().enumerate() {
            if *ty == ValueType::Nat {
                table.low[at] = Some(0);
            }
        }
        self.refined.push(table);
        for _ in 0..2 {
            let mut grid = Refined::with_arity(3);
            grid.add_key(bit(0) | bit(1));
            self.refined.push(grid);
        }
        self.refined.push(Refined::with_arity(0));
        self.forms = vec![Form::default(); self.first_term];
    }

    /// One example against another: each value of a column at two examples.
    fn across_examples(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        for (place, column) in columns.iter().enumerate() {
            if column.ty == ValueType::Example || columns.iter().filter(|other| other.ty != ValueType::Example).count() == 0 {
                continue;
            }
            let kept: Box<[u16]> = (0..columns.len() as u16).filter(|other| usize::from(*other) != place).collect();
            let mut out = columns.clone();
            for other in kept.iter() {
                let held = &columns[usize::from(*other)];
                let name = unique(&held.name, &out);
                out.push(Column { name, ty: held.ty.clone(), source: held.source });
            }
            let pair = [place as u16];
            self.push(Step::Join { left: pair.into(), right: pair.into(), kept, left_arity: columns.len() as u16 }, at, at, out, size, format!("(join {text} {text} ({0} {0}))", column.name), RootKind::Rows);
        }
    }

    /// The parts with keys over a term of a task-wide family.
    fn lifted_parts(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        let Some(e) = columns.iter().position(|column| column.ty == ValueType::Example).map(|place| place as u16) else { return };
        let fresh = |name: &str, ty: ValueType, source: u16| Column { name: unique(name, &columns), ty, source };
        let id_source = 1000 + (self.terms.len() % 60000) as u16;
        let group: Vec<u16> = columns.iter().enumerate().filter(|(place, column)| *place != usize::from(e) && matches!(column.ty, ValueType::Color | ValueType::Ident(_))).map(|(place, _)| place as u16).collect();
        let e_name = columns[usize::from(e)].name.clone();
        let mut keyed: Vec<(Box<[u16]>, String)> = vec![(vec![e].into_boxed_slice(), format!("({e_name})"))];
        for (place, column) in columns.iter().enumerate() {
            if place != usize::from(e) {
                keyed.push((vec![place as u16].into_boxed_slice(), format!("({})", column.name)));
                keyed.push((vec![e, place as u16].into_boxed_slice(), format!("({e_name} {})", column.name)));
            }
        }
        if group.len() >= 2 {
            let names: Vec<&str> = group.iter().map(|place| columns[usize::from(*place)].name.as_str()).collect();
            keyed.push((group.clone().into_boxed_slice(), format!("(T*:{})", names.join(","))));
            let with_e: Vec<u16> = std::iter::once(e).chain(group.iter().copied()).collect();
            keyed.push((with_e.into_boxed_slice(), format!("({e_name} T*:{})", names.join(","))));
        }
        let mut pushes: Vec<(PartStep, Vec<Column>, String, RootKind)> = Vec::new();
        for (keys, key_text) in &keyed {
            let heads: Vec<Column> = keys.iter().map(|key| columns[usize::from(*key)].clone()).collect();
            let with = |extra: Vec<Column>| -> Vec<Column> { heads.iter().cloned().chain(extra).collect() };
            pushes.push((PartStep::Count { keys: keys.clone() }, with(vec![fresh("N", ValueType::Nat, 0)]), format!("(count {text} {key_text})"), RootKind::Rows));
            if keys.len() < columns.len() {
                pushes.push((PartStep::ClassOf { keys: keys.clone() }, with(vec![fresh("Id", ValueType::OPEN_IDENT, 902)]), format!("(class-of {text} {key_text})"), RootKind::Rows));
            }
            for (f, field) in columns.iter().enumerate() {
                if keys.contains(&(f as u16)) || f == usize::from(e) {
                    continue;
                }
                pushes.push((PartStep::OneValue { keys: keys.clone(), f: f as u16 }, with(vec![field.clone()]), format!("(one-value {text} {key_text} {})", field.name), RootKind::Rows));
                pushes.push((PartStep::Several { keys: keys.clone(), f: f as u16 }, heads.clone(), format!("(several {text} {key_text} {})", field.name), RootKind::Rows));
                pushes.push((PartStep::Determines { keys: keys.clone(), f: f as u16 }, Vec::new(), format!("(determines {text} {key_text} {})", field.name), RootKind::Holds));
            }
            // A part that reads a cell's place reads the cells of one example.
            if !keys.contains(&e) {
                continue;
            }
            for (place, column) in columns.iter().enumerate() {
                if column.ty != ValueType::Position || keys.contains(&(place as u16)) {
                    continue;
                }
                let p = place as u16;
                let name = &column.name;
                pushes.push((PartStep::Pieces { keys: keys.clone(), p, four: false }, with(vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::BoxOf { keys: keys.clone(), p }, with(vec![fresh("B", ValueType::Box, 0)]), format!("(box-of {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::RelBox { keys: keys.clone(), p }, with(vec![fresh("X_rel", ValueType::Box, 0)]), format!("(cells-in-box {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::ShapeClass { keys: keys.clone(), p, turned: false }, with(vec![fresh("Id", ValueType::OPEN_IDENT, 900)]), format!("(shape-class {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::ShapeClass { keys: keys.clone(), p, turned: true }, with(vec![fresh("Id", ValueType::OPEN_IDENT, 901)]), format!("(shape-class-d4 {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::Holes { keys: keys.clone(), p }, with(vec![fresh("N", ValueType::Nat, 0)]), format!("(holes {text} {key_text} {name})"), RootKind::Rows));
                pushes.push((PartStep::Symmetry { keys: keys.clone(), p }, with(vec![fresh("N", ValueType::Nat, 0)]), format!("(symmetry {text} {key_text} {name})"), RootKind::Rows));
            }
        }
        for (part, kept, line, root) in pushes {
            self.push(Step::Part(Box::new(part)), at, NO_TERM, kept, size, line, root);
        }
    }

    /// Each column's values at every example, and their share of its values, as a named feature.
    fn common_values(&mut self, table: u32) {
        let columns = self.terms[table as usize].columns.clone();
        let text = self.terms[table as usize].text.clone();
        let Some(e) = columns.iter().position(|column| column.ty == ValueType::Example) else { return };
        for (n, column) in columns.iter().enumerate() {
            if n == e || matches!(column.ty, ValueType::Ident(_)) {
                continue;
            }
            let values_text = format!("(project {text} {})", column.name);
            let values = self.terms.iter().rposition(|term| term.text == values_text).map(|at| at as u32);
            for (grid, label) in [(LEAF_INPUT, "ex_input"), (LEAF_OUTPUT, "ex_output")] {
                let line = format!("(all (join (project {text} {0}) (project {label} E)) {text} ({0}) ({0} {0}) (E E))", column.name);
                let before = self.terms.len();
                self.push(Step::Part(Box::new(PartStep::CommonValues { e: e as u16, n: n as u16 })), table, grid, vec![column.clone()], 3, line.clone(), RootKind::Rows);
                if let (Some(values), true) = (values, self.terms.len() > before) {
                    let common = before as u32;
                    self.push(Step::Part(Box::new(PartStep::Same)), common, values, Vec::new(), 3, format!("{line} {values_text}"), RootKind::Against);
                }
            }
        }
    }

    /// The share of the classes of examples by a table's rows that one value of the outputs meets at
    /// each example, and the other way: 1 both ways where the table's rows group the pairs as the value does.
    fn groupings(&mut self, table: u32) {
        let id = |name: &str, source: u16| Column { name: name.to_string(), ty: ValueType::OPEN_IDENT, source };
        let e = || Column { name: "E".to_string(), ty: ValueType::Example, source: 0 };
        // What a table gives at each example.
        let has_ident = |term: &Term| term.columns.iter().any(|column| matches!(column.ty, ValueType::Ident(_)));
        let mut own: Vec<u32> = Vec::new();
        for at in self.first_term as u32..self.terms.len() as u32 {
            let term = &self.terms[at as usize];
            let lifted = term.columns.first().is_some_and(|column| column.ty == ValueType::Example) && term.columns.len() >= 2;
            if !lifted || has_ident(term) || term.a != LEAF_TABLE {
                continue;
            }
            if at == table || matches!(term.step, Some(Step::Project { .. })) || term.text == format!("(count {} (E))", self.terms[table as usize].text) {
                own.push(at);
            }
        }
        // What the outputs give at each example, whatever a rule says of its count.
        let output = self.terms[LEAF_OUTPUT as usize].text.clone();
        let input = self.terms[LEAF_INPUT as usize].text.clone();
        let (p, col, n) = (|| Column { name: "P".to_string(), ty: ValueType::Position, source: 0 }, |name: &str| Column { name: name.to_string(), ty: ValueType::Color, source: 0 }, Column { name: "N".to_string(), ty: ValueType::Nat, source: 0 });
        let mut values: Vec<u32> = vec![LEAF_OUTPUT];
        let mut add = |family: &mut Generated, step: Step, a: u32, b: u32, columns: Vec<Column>, text: String| -> u32 {
            family.force_next = true;
            family.push(step, a, b, columns, 1, text, RootKind::Rows);
            let at = family.terms.len() as u32 - 1;
            values.push(at);
            at
        };
        add(self, Step::Project { columns: Box::new([0, 2]) }, LEAF_OUTPUT, NO_TERM, vec![e(), col("Col")], format!("(project {output} E Col)"));
        add(self, Step::Project { columns: Box::new([0, 1]) }, LEAF_OUTPUT, NO_TERM, vec![e(), p()], format!("(project {output} E P)"));
        add(self, Step::Part(Box::new(PartStep::Count { keys: Box::new([0]) })), LEAF_OUTPUT, NO_TERM, vec![e(), n.clone()], format!("(count {output} (E))"));
        let by_color = add(self, Step::Part(Box::new(PartStep::Count { keys: Box::new([0, 2]) })), LEAF_OUTPUT, NO_TERM, vec![e(), col("Col"), n.clone()], format!("(count {output} (E Col))"));
        add(self, Step::Part(Box::new(PartStep::Extreme { keys: Box::new([0]), t: 1, score: 2, greatest: true })), by_color, NO_TERM, vec![e(), col("Col")], format!("(greatest-by (count {output} (E Col)) (E) Col N)"));
        let new_cells = add(self, Step::Antijoin { left: Box::new([0, 2]), right: Box::new([0, 2]) }, LEAF_OUTPUT, LEAF_INPUT, vec![e(), p(), col("Col")], format!("(antijoin {output} {input} (E E) (Col Col))"));
        add(self, Step::Project { columns: Box::new([0, 2]) }, new_cells, NO_TERM, vec![e(), col("Col")], format!("(project (antijoin {output} {input} (E E) (Col Col)) E Col)"));
        let both_text = format!("(join {input} {output} (E E) (P P))");
        let both = add(self, Step::Join { left: Box::new([0, 1]), right: Box::new([0, 1]), kept: Box::new([2]), left_arity: 3 }, LEAF_INPUT, LEAF_OUTPUT, vec![e(), p(), col("Col"), col("Col_2")], both_text.clone());
        let changed_text = format!("(select {both_text} Col != Col_2)");
        let changed = add(self, Step::Select { at: 2, op: Op::Ne, other: Some(3), drop: None }, both, NO_TERM, vec![e(), p(), col("Col"), col("Col_2")], changed_text.clone());
        add(self, Step::Project { columns: Box::new([0, 2, 3]) }, changed, NO_TERM, vec![e(), col("Col"), col("Col_2")], format!("(project {changed_text} E Col Col_2)"));
        add(self, Step::Project { columns: Box::new([0, 3]) }, changed, NO_TERM, vec![e(), col("Col_2")], format!("(project {changed_text} E Col_2)"));
        add(self, Step::Project { columns: Box::new([0, 1]) }, changed, NO_TERM, vec![e(), p()], format!("(project {changed_text} E P)"));
        // The class of each example under each of those.
        let classes_text = |text: &str, columns: &[Column]| -> String {
            let fields: Vec<&str> = columns.iter().skip(1).map(|column| column.name.as_str()).collect();
            let fields = if let [one] = fields[..] { one.to_string() } else { format!("({})", fields.join(" ")) };
            format!("(component Quotient (equivalent (component Inclusion (pattern {text} () (E {fields})) (observed {text} () (E {fields})) equal) () (E E_2)) class)")
        };
        let class_of = |family: &mut Generated, at: u32, source: u16| -> u32 {
            let (text, columns) = (family.terms[at as usize].text.clone(), family.terms[at as usize].columns.clone());
            family.force_next = true;
            family.push(Step::Part(Box::new(PartStep::ExampleClasses { e: 0 })), at, NO_TERM, vec![e(), id("Id", source)], 1, classes_text(&text, &columns), RootKind::Rows);
            family.terms.len() as u32 - 1
        };
        let value_classes: Vec<u32> = values.iter().map(|at| class_of(self, *at, 3000)).collect();
        for at in own {
            let mine = class_of(self, at, 3000);
            for theirs in &value_classes {
                let (one, two) = (self.terms[mine as usize].text.clone(), self.terms[*theirs as usize].text.clone());
                let joined_text = format!("(join {one} {two} (E E))");
                self.force_next = true;
                self.push(Step::Join { left: Box::new([0]), right: Box::new([0]), kept: Box::new([1]), left_arity: 2 }, mine, *theirs, vec![e(), id("Id", 3000), id("Id_2", 3000)], 3, joined_text.clone(), RootKind::Rows);
                let joined = self.terms.len() as u32 - 1;
                for (from, to, from_name, to_name) in [(1u16, 2u16, "Id", "Id_2"), (2, 1, "Id_2", "Id")] {
                    let classes = format!("(project {joined_text} {from_name})");
                    self.force_next = true;
                    self.push(Step::Project { columns: Box::new([from]) }, joined, NO_TERM, vec![id(from_name, 3000)], 3, classes.clone(), RootKind::Rows);
                    let domain = self.terms.len() as u32 - 1;
                    let one_text = format!("(one-value {joined_text} ({from_name}) {to_name})");
                    self.force_next = true;
                    self.push(Step::Part(Box::new(PartStep::OneValue { keys: Box::new([from]), f: to })), joined, NO_TERM, vec![id(from_name, 3000), id(to_name, 3000)], 3, one_text.clone(), RootKind::Rows);
                    let single = self.terms.len() as u32 - 1;
                    self.force_next = true;
                    self.push(Step::Semijoin { left: Box::new([0]), right: Box::new([0]) }, domain, single, vec![id(from_name, 3000)], 3, format!("(semijoin {classes} {one_text} ({from_name} {from_name}))"), RootKind::Share);
                }
            }
        }
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

    fn empty() -> Generated {
        Generated { terms: Vec::new(), first_term: 0, by_size: Vec::new(), roots: 0, refined: Vec::new(), forms: Vec::new(), rejected_by_rule: Default::default(), rejected: Vec::new(), keep_text: std::env::var_os("GENERATE_KEEP_TEXT").is_some(), no_rules: std::env::var_os("GENERATE_NO_RULES").is_some(), task_wide: false, force_next: false, diff_terms: Vec::new(), over_grids: false, two_tables: false }
    }

    fn push_leaf(&mut self, text: &str, columns: Vec<Column>, flags: u8, size: u8) {
        self.terms.push(Term { step: None, a: NO_TERM, b: NO_TERM, columns, flags, size, root: RootKind::Rows, roots: Vec::new(), text: text.to_string(), used: true, plan: None });
    }

    /// The `antijoin` of the two grids on all their columns has a part's name, so no term stands over it.
    fn diff_is_named(&mut self) {
        for at in self.first_term..self.terms.len() {
            let text = &self.terms[at].text;
            if text == "(antijoin output input (P P) (Col Col))" || text == "(antijoin input output (P P) (Col Col))" {
                self.diff_terms.push(at as u32);
            }
        }
    }

    /// What each leaf's type holds: the table by its column types, the grids and the parts by the
    /// declarations of the lib and their fragments.
    fn leaf_refinements(&mut self, types: &[ValueType], parts: &[crate::gen_constants::ConstantPart]) {
        let mut table = Refined::with_arity(types.len());
        table.add_key(table.all_columns());
        for (at, ty) in types.iter().enumerate() {
            if *ty == ValueType::Nat {
                table.low[at] = Some(0);
            }
        }
        table.within.push(Within { columns: (0..types.len() as u16).collect(), of: LEAF_TABLE, at: (0..types.len() as u16).collect() });
        self.refined.push(table);
        for grid in ["output", "input"] {
            self.refined.push(refine_parts::grid_refined(grid));
        }
        self.refined.push(Refined::with_arity(0));
        self.forms = vec![Form::default(); self.first_term];
        for (place, part) in parts.iter().enumerate() {
            self.refined.push(base_refinements(place, part));
        }
    }

    /// Whether a term's column stands under each of the right columns' types, for a complete relation.
    fn is_complete(&self, a: u32, b: u32, left: &[u16], right: &[u16]) -> bool {
        let ([one], [other]) = (left, right) else { return false };
        if self.refined[b as usize].complete & bit(*other) == 0 {
            return false;
        }
        let (own, target) = (&self.terms[a as usize].columns[usize::from(*one)], &self.terms[b as usize].columns[usize::from(*other)]);
        own.ty.is_below(&target.ty)
    }

    fn names_of(&self, at: u32, places: &[u16]) -> Vec<String> {
        places.iter().map(|place| self.terms[at as usize].columns[usize::from(*place)].name.clone()).collect()
    }

    /// The call of a native part over a relation of the columns `C0..`, with the relation's own name for each.
    fn part_plan(&self, part: &PartStep, a: u32, b: u32, columns: &[Column]) -> Option<Arc<PartPlan>> {
        let left = &self.terms[a as usize].columns;
        let right: Option<&Term> = (b != NO_TERM).then(|| &self.terms[b as usize]);
        let s_columns: Vec<String> = if part.reads_second_relation() { right.map_or_else(Vec::new, |term| term.columns.iter().map(|column| crate::expand::label_of(&column.name)).collect()) } else { Vec::new() };
        let grid = right.and_then(|term| matches!(term.text.as_str(), "input" | "output").then(|| term.text.clone())).unwrap_or_default();
        let call = part.call_text(&grid, &|place| s_columns.get(usize::from(place)).cloned().unwrap_or_default())?;
        let native: Vec<(String, String)> = columns.iter().map(|column| {
            let own = left.iter().position(|held| crate::expand::label_of(&held.name) == column.name);
            let literal = match column.name.rfind('_') {
                Some(at) if column.name[at + 1..].parse::<u32>().is_ok() => column.name[..at].to_string(),
                _ => column.name.clone(),
            };
            (own.map_or_else(|| literal.clone(), |at| format!("C{at}")), literal)
        }).collect();
        refine_parts::plan(&call, left.len(), &s_columns, &native)
    }

    /// Whether an application has a derivation, and its output's type where it has one.
    fn judge(&self, step: &Step, a: u32, b: u32, columns: &[Column]) -> Result<(Refined, Form, Option<Arc<PartPlan>>), (Rejected, Partner)> {
        let first = &self.refined[a as usize];
        let form = &self.forms[a as usize];
        let no_partner = |rejected: Rejected| (rejected, Partner::None);
        let other = |rule: &'static str, partner: Partner| (Rejected { rule, claim: Claim::Other }, partner);
        match step {
            Step::Project { columns: places } => {
                let kept = self.names_of(a, places);
                let holds_all = |names: &[String]| names.iter().all(|name| kept.contains(name));
                match form.kind {
                    FormKind::Project => return Err(other("project-over-project", Partner::OverBase)),
                    FormKind::Filter if holds_all(&form.filter_reads) => return Err(other("project-over-filter", Partner::Swap)),
                    FormKind::Extension => {
                        let added: Vec<String> = self.terms[a as usize].columns.iter().map(|column| column.name.clone()).filter(|name| !form.own.contains(name)).collect();
                        if holds_all(&form.reads) && holds_all(&added) {
                            return Err(other("project-over-extension", Partner::Swap));
                        }
                        if kept.iter().all(|name| form.own.contains(name)) && form.total {
                            return Err(other("project-below-extension", Partner::OverBase));
                        }
                    }
                    _ => {}
                }
                let refined = refine::project(first, places).map_err(no_partner)?;
                Ok((refined, Form { kind: FormKind::Project, ..Form::default() }, None))
            }
            Step::Select { at, op, other: second, drop } => {
                let name = self.terms[a as usize].columns[usize::from(*at)].name.clone();
                let pair = (name.clone(), second.map_or_else(|| "0".to_string(), |second| self.terms[a as usize].columns[usize::from(second)].name.clone()));
                if form.selects.contains(&pair) {
                    return Err((Rejected { rule: "select-twice", claim: Claim::Follows }, Partner::None));
                }
                let mut reads = vec![name];
                if second.is_some() {
                    reads.push(pair.1.clone());
                }
                let dropped = drop.map(|place| self.terms[a as usize].columns[usize::from(place)].name.clone());
                let order = hash_words(format!("0 {} {} {}", pair.0, op.text(), pair.1).bytes().map(u64::from)) as u64 >> 2;
                self.commutes(a, order, &reads, dropped.as_deref())?;
                let refined = match second {
                    None => {
                        let has_order = is_number(&self.terms[a as usize].columns[usize::from(*at)].ty);
                        refine::select_zero(first, *at, *op, drop.is_some(), has_order).map_err(|rejected| {
                            let partner = if rejected.claim == Claim::Other {
                                refine::canonical_zero_op(first, *at, *op).map_or(Partner::None, |canonical| Partner::Text(format!("(select {} {} {} 0)", self.terms[a as usize].text, pair.0, canonical.text())))
                            } else {
                                Partner::None
                            };
                            (rejected, partner)
                        })?
                    }
                    Some(second) => refine::select_pair(first, *at, *second, *op, *drop).map_err(no_partner)?,
                };
                let mut next = self.filter_form(a, order, &reads);
                next.selects.push(pair);
                Ok((refined, next, None))
            }
            Step::Semijoin { left, right } | Step::Antijoin { left, right } => {
                self.second_relation_form(b, right)?;
                let is_semi = matches!(step, Step::Semijoin { .. });
                let reads = self.names_of(a, left);
                let key = self.semijoin_key(a, b, left, right);
                let order = hash_words([u64::from(is_semi), key]) as u64 >> 2 | 1 << 62;
                self.commutes(a, order, &reads, None)?;
                let complete = self.is_complete(a, b, left, right);
                let second = &self.refined[b as usize];
                let refined = if is_semi { refine::semijoin(&self.refined, first, second, b, left, right, complete) } else { refine::antijoin(&self.refined, first, b, left, right, complete) }.map_err(no_partner)?;
                let mut next = self.filter_form(a, order, &reads);
                if is_semi {
                    next.semijoins.push(key);
                }
                Ok((refined, next, None))
            }
            Step::Join { left, right, kept, .. } => {
                let key = self.semijoin_key(a, b, left, right);
                if form.kind == FormKind::Filter && form.semijoins.contains(&key) {
                    return Err(other("join-over-its-semijoin", Partner::OverBase));
                }
                let second = &self.refined[b as usize];
                let refined = refine::join(&self.refined, first, second, b, left, right, kept).map_err(|rejected| {
                    (rejected, if rejected.claim == Claim::Other { Partner::Text(format!("(semijoin {} {} {})", self.terms[a as usize].text, self.terms[b as usize].text, self.pair_text(a, b, left, right))) } else { Partner::None })
                })?;
                let own = self.terms[a as usize].columns.iter().map(|column| column.name.clone()).collect();
                let order = hash_words(format!("join {b} {key}").bytes().map(u64::from)) as u64;
                Ok((refined, Form { kind: FormKind::Extension, own, reads: self.names_of(a, left), total: false, order, ..Form::default() }, None))
            }
            Step::All { left, right, outer } => {
                self.second_relation_form(b, right)?;
                // The rows of a domain over the columns that the form reads are all it reads of them.
                if form.kind == FormKind::Project {
                    return Err(other("all-over-project", Partner::OverBase));
                }
                if form.kind == FormKind::Extension && form.total {
                    let names = self.names_of(a, left);
                    let kept = self.names_of(a, outer);
                    if names.iter().chain(&kept).all(|name| form.own.contains(name)) {
                        return Err(other("all-below-extension", Partner::OverBase));
                    }
                }
                let complete = self.is_complete(a, b, left, right);
                let refined = refine::all(&self.refined, first, b, left, right, outer, complete).map_err(no_partner)?;
                Ok((refined, Form::default(), None))
            }
            Step::Part(part) => self.judge_part(part, a, b, columns),
            _ => {
                let mut refined = Refined::with_arity(columns.len());
                refined.add_key(refined.all_columns());
                Ok((refined, Form::default(), None))
            }
        }
    }

    /// Whether the second relation of an operator that reads only whether a row has a match stands in
    /// its normal form: a `project` of a relation, over the columns the pairs read, has its matches.
    fn second_relation_form(&self, b: u32, right: &[u16]) -> Result<(), (Rejected, Partner)> {
        let form = &self.forms[b as usize];
        let rejected = |rule: &'static str| Err((Rejected { rule, claim: Claim::Other }, Partner::None));
        match form.kind {
            FormKind::Project => rejected("match-in-project"),
            FormKind::Extension if form.total && self.names_of(b, right).iter().all(|name| form.own.contains(name)) => rejected("match-in-extension"),
            _ => Ok(()),
        }
    }

    fn pair_text(&self, a: u32, b: u32, left: &[u16], right: &[u16]) -> String {
        let (l, r) = (self.names_of(a, left), self.names_of(b, right));
        l.iter().zip(&r).map(|(one, two)| format!("({one} {two})")).collect::<Vec<_>>().join(" ")
    }

    fn semijoin_key(&self, a: u32, b: u32, left: &[u16], right: &[u16]) -> u64 {
        let names = self.names_of(a, left);
        let mut words: Vec<u64> = vec![u64::from(b)];
        for (name, place) in names.iter().zip(right) {
            words.extend(name.bytes().map(u64::from));
            words.push(1000 + u64::from(*place));
        }
        hash_words(words) as u64
    }

    /// The form of a filter over `a`.
    fn filter_form(&self, a: u32, order: u64, reads: &[String]) -> Form {
        let form = &self.forms[a as usize];
        let mut next = if form.kind == FormKind::Filter { form.clone() } else { Form { kind: FormKind::Filter, ..Form::default() } };
        next.last_filter = order;
        next.filter_reads.extend(reads.iter().cloned());
        next
    }

    /// Whether a filter over `a` that reads `reads` stands in its normal form: filters in one order,
    /// and each below an extension over its columns. Dropping a column the filter below reads leaves
    /// no other order.
    fn commutes(&self, a: u32, order: u64, reads: &[String], dropped: Option<&str>) -> Result<(), (Rejected, Partner)> {
        let form = &self.forms[a as usize];
        match form.kind {
            FormKind::Filter if order < form.last_filter && dropped.is_none_or(|name| !form.filter_reads.iter().any(|read| read == name)) => {
                Err((Rejected { rule: "filter-order", claim: Claim::Other }, Partner::Swap))
            }
            FormKind::Extension if reads.iter().all(|read| form.own.contains(read)) && dropped.is_none_or(|name| !form.reads.iter().any(|read| read == name)) => {
                Err((Rejected { rule: "filter-below-extension", claim: Claim::Other }, Partner::Swap))
            }
            _ => Ok(()),
        }
    }

    fn relation_input(refined: &Refined, of: Option<u32>) -> RelationInput {
        let columns: Vec<String> = (0..refined.arity()).map(|at| format!("C{at}")).collect();
        let mut within = Vec::new();
        if of.is_some() {
            for held in &refined.within {
                let source = match held.of {
                    LEAF_INPUT => "input",
                    LEAF_OUTPUT => "output",
                    _ => continue,
                };
                for (own, target) in held.columns.iter().zip(held.at.iter()) {
                    within.push((columns[usize::from(*own)].clone(), source.to_string(), if *target == 0 { "P".to_string() } else { "Col".to_string() }));
                }
            }
        }
        RelationInput { columns, keys: refined.keys.clone(), low: refined.low.clone(), high: refined.high.clone(), within }
    }

    fn judge_part(&self, part: &PartStep, a: u32, b: u32, columns: &[Column]) -> Result<(Refined, Form, Option<Arc<PartPlan>>), (Rejected, Partner)> {
        let first = &self.refined[a as usize];
        if matches!(part, PartStep::Same) {
            return Ok((first.clone(), Form::default(), None));
        }
        let form = &self.forms[a as usize];
        // A flag over a key has one row at each group, and one with no other side's rows is constant.
        if let PartStep::DeterminesFlag { keys, a: left, b: right } = part {
            if first.is_key(refine::mask_of(keys)) {
                return Err((Rejected { rule: "flag-over-key", claim: Claim::Follows }, Partner::None));
            }
            if refine::is_within(&self.refined, first, &[*left], b, &[*right], 2) || refine::is_outside(first, &[*left], b, &[*right]) || self.is_complete(a, b, &[*left], &[*right]) {
                return Err((Rejected { rule: "flag-within", claim: Claim::Follows }, Partner::None));
            }
        }
        let Some(plan) = self.part_plan(part, a, b, columns) else {
            let mut refined = Refined::with_arity(columns.len());
            refined.add_key(refined.all_columns());
            for (at, column) in columns.iter().enumerate() {
                if column.ty == ValueType::Nat {
                    refined.low[at] = Some(0);
                }
            }
            return Ok((refined, Form::default(), None));
        };
        let holes = part.hole_columns();
        let hole_names = self.names_of(a, &holes);
        if plan.reads_only_holes {
            if form.kind == FormKind::Project {
                return Err((Rejected { rule: "part-over-project", claim: Claim::Other }, Partner::OverBase));
            }
            if form.kind == FormKind::Extension && form.total && hole_names.iter().all(|name| form.own.contains(name)) {
                return Err((Rejected { rule: "part-below-extension", claim: Claim::Other }, Partner::OverBase));
            }
        }
        let second = (b != NO_TERM && part.reads_second_relation()).then(|| Self::relation_input(&self.refined[b as usize], None));
        let result = plan.result(&Self::relation_input(first, Some(a)), second.as_ref());
        if let Some(rejected) = result.verdict {
            return Err((rejected, Partner::None));
        }
        let mut refined = result.refined.clone();
        for (held, source, at) in &result.within {
            let of = match source.as_str() {
                "input" => LEAF_INPUT,
                "output" => LEAF_OUTPUT,
                "&r" => a,
                "&s" if b != NO_TERM => b,
                _ => continue,
            };
            let places: Option<Vec<u16>> = at.iter().map(|name| {
                if let Some(place) = name.strip_prefix('C').and_then(|place| place.parse::<u16>().ok()) {
                    if source == "&r" {
                        return Some(place);
                    }
                }
                self.terms[of as usize].columns.iter().position(|column| crate::expand::label_of(&column.name) == *name).map(|place| place as u16)
            }).collect();
            if let Some(places) = places {
                refined.within.push(Within { columns: held.clone().into_boxed_slice(), of, at: places.into_boxed_slice() });
            }
        }
        // A part's own order among the extensions and the filters over one relation.
        let text = format!("{part:?} {b}");
        let order = hash_words(text.bytes().map(u64::from)) as u64;
        let next = if result.row_wise && !result.adds_columns {
            let row_order = order >> 2 | 2 << 62;
            self.commutes(a, row_order, &hole_names, None)?;
            self.filter_form(a, row_order, &hole_names)
        } else if result.row_wise {
            if form.kind == FormKind::Extension && hole_names.iter().all(|name| form.own.contains(name)) && order < form.order {
                return Err((Rejected { rule: "extension-order", claim: Claim::Other }, Partner::Swap));
            }
            let own = self.terms[a as usize].columns.iter().map(|column| column.name.clone()).collect();
            Form { kind: FormKind::Extension, own, reads: hole_names, total: result.total, order, ..Form::default() }
        } else {
            Form::default()
        };
        Ok((refined, next, Some(plan)))
    }

    fn partner_text(&self, a: u32, text: &str, partner: &Partner) -> Option<String> {
        let parent = &self.terms[a as usize];
        match partner {
            Partner::None => None,
            Partner::Text(held) => Some(held.clone()),
            Partner::OverBase | Partner::Swap => {
                if parent.a == NO_TERM {
                    return None;
                }
                let base = self.terms[parent.a as usize].text.as_str();
                let outer = text.replacen(parent.text.as_str(), MARK, 1);
                if matches!(partner, Partner::OverBase) {
                    return Some(outer.replace(MARK, base));
                }
                let inner = parent.text.replacen(base, MARK, 1);
                Some(inner.replace(MARK, &outer.replace(MARK, base)))
            }
        }
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
        let is_pair = root == RootKind::Against;
        let force = std::mem::take(&mut self.force_next);
        let judged = if force {
            let mut refined = Refined::with_arity(columns.len());
            refined.add_key(refined.all_columns());
            Ok((refined, Form::default(), None))
        } else if is_pair { Ok((Refined::with_arity(0), Form::default(), None)) } else if self.no_rules { let mut refined = Refined::with_arity(columns.len()); refined.add_key(refined.all_columns()); Ok((refined, Form::default(), None)) } else { self.judge(&step, a, b, &columns) };
        let (refined, form, plan) = match judged {
            Ok(held) => held,
            Err((rejected, partner)) => {
                *self.rejected_by_rule.entry(rejected.rule).or_insert(0) += 1;
                if self.keep_text {
                    let other = self.partner_text(a, &text, &partner);
                    self.rejected.push(RejectedTerm { rule: rejected.rule, claim: rejected.claim, step, a, b, text, columns: columns.iter().map(|column| column.name.clone()).collect(), other });
                }
                return;
            }
        };
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
        self.refined.push(refined);
        self.forms.push(form);
        self.terms.push(Term { step: Some(step), a, b, columns, flags, size, root, roots: Vec::new(), text, used: false, plan });
    }

    /// Whether the table's rows are those of another relation under a pairing of all the narrower one's columns. The pairing stands in no shape's name, so
    /// one shape reads every type and width. A pair of relations with more pairings than `MAX_PAIRINGS` has none of these terms.
    fn same_rows(&mut self, other: u32) {
        let (own, theirs) = (self.terms[LEAF_TABLE as usize].columns.clone(), self.terms[other as usize].columns.clone());
        let other_text = self.terms[other as usize].text.clone();
        let narrow_own = own.len() <= theirs.len();
        let (from, to) = if narrow_own { (&own, &theirs) } else { (&theirs, &own) };
        let word = if own.len() == theirs.len() { "rows-equal" } else if narrow_own { "rows-project" } else { "rows-extend" };
        for pairing in pairings(from, to) {
            let (left, right): (Vec<u16>, Vec<u16>) = if narrow_own { pairing.iter().copied().unzip() } else { pairing.iter().map(|at| (at.1, at.0)).unzip() };
            let pairs: Vec<String> = left.iter().zip(right.iter()).map(|(a, b)| format!("{}={}", own[usize::from(*a)].name, theirs[usize::from(*b)].name)).collect();
            let free: Vec<&str> = own.iter().enumerate().filter(|(at, _)| !left.contains(&(*at as u16))).map(|(_, column)| column.name.as_str()).collect();
            let free_text = if free.is_empty() { String::new() } else { format!(" T*:{}", free.join(",")) };
            let key = !free.is_empty();
            self.force_next = true;
            self.push(Step::Part(Box::new(PartStep::SameRows { left: left.into_boxed_slice(), right: right.into_boxed_slice(), key })), LEAF_TABLE, other, Vec::new(), 1, format!("({word} T {other_text} T*:{}{free_text})", pairs.join(",")), RootKind::Holds);
        }
    }

    /// `project` and `select` over a term.
    fn unary_operators(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        let count = columns.len();
        // A shape's name does not depend on a table's width, so a table's own `project` of all its columns stands as a term.
        let every = at == LEAF_TABLE;
        if (count >= 2 || (every && count == 1)) && count <= 10 {
            for mask in 1u32..(1 << count) - u32::from(!every) {
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

    /// Whether the table is a product of two groups of its columns, for each way to split them. The split stands in no shape's name.
    fn product(&mut self) {
        let columns = self.terms[LEAF_TABLE as usize].columns.clone();
        if columns.len() < 2 || columns.len() > 8 {
            return;
        }
        // Each split once: the group that holds the first column is the key.
        let whole = (1u32 << columns.len()) - 1;
        for mask in (1..whole).step_by(2) {
            let keys: Box<[u16]> = (0..columns.len() as u16).filter(|at| mask >> at & 1 == 1).collect();
            let names: Vec<&str> = keys.iter().map(|at| columns[usize::from(*at)].name.as_str()).collect();
            self.force_next = true;
            self.push(Step::Part(Box::new(PartStep::Product { keys })), LEAF_TABLE, NO_TERM, Vec::new(), 1, format!("(product T (T*:{}))", names.join(",")), RootKind::Holds);
        }
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
                for (output, grid_name) in [(true, "output"), (false, "input")] {
                    for (on, word) in [(true, "on"), (false, "off")] {
                        add(PartStep::DiffRows { p, output, on }, LEAF_GRIDS, columns.clone(), format!("({word}-{grid_name}-diff {text} {name})"), RootKind::Share);
                        add(PartStep::DiffCells { p, output, on }, LEAF_GRIDS, vec![one("P", ValueType::Position, 0), one("Col", ValueType::Color, 0)], format!("({grid_name}-diff-{word} {text} {name})"), RootKind::Rows);
                    }
                }
                add(PartStep::FrameExtent { p }, NO_TERM, vec![one("A", ValueType::Axis, 0), one("N", ValueType::Int, 0)], format!("(frame-extent {text} {name})"), RootKind::Rows);
                add(PartStep::Complement { p }, NO_TERM, vec![fresh("P", ValueType::Position, 0)], format!("(complement {text} {name})"), RootKind::Rows);
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
                    if !keys.is_empty() {
                        for (output, grid_name) in [(true, "output"), (false, "input")] {
                            add(PartStep::DiffGroupsOff { keys: keys.clone(), p, output }, LEAF_GRIDS, heads.clone(), format!("(groups-off-{grid_name}-diff {text} {key_text} {name})"), RootKind::Rows);
                        }
                    }
                    add(PartStep::TouchesEdge { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(touches-edge {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::FillsBox { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(fills-box {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Straight { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(straight {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::BoxSides { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("N", ValueType::Int, 0)]), format!("(box-sides {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::BoxMargins { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("D", ValueType::Dir, 0), fresh("K", ValueType::Int, 0)]), format!("(box-margins {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::LineCounts { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("Along", ValueType::Box, 0), fresh("N", ValueType::Nat, 0)]), format!("(line-counts {text} {key_text} {name})"), RootKind::Rows);
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
                for column in &mut columns {
                    column.name = crate::expand::label_of(&column.name);
                }
                for at in kept.iter() {
                    let column = &right[usize::from(*at)];
                    let name = unique(&crate::expand::label_of(&column.name), &columns);
                    columns.push(Column { name, ty: column.ty.clone(), source: column.source });
                }
                self.push(Step::Join { left: left_at.clone(), right: right_at.clone(), kept, left_arity: left.len() as u16 }, l, r, columns, size, format!("(join {left_text} {right_text} {pair_text})"), RootKind::Rows);
            }
            // A `semijoin` or an `antijoin` with a grid's diff on one cell is a part's call, which is smaller.
            let named = pairs.len() == 1 && (matches!(left_text.as_str(), "output-diff" | "input-diff") || matches!(right_text.as_str(), "output-diff" | "input-diff"));
            if !named {
                self.push(Step::Semijoin { left: left_at.clone(), right: right_at.clone() }, l, r, narrowed.clone(), size, format!("(semijoin {left_text} {right_text} {pair_text})"), RootKind::Share);
                self.push(Step::Antijoin { left: left_at.clone(), right: right_at.clone() }, l, r, left.clone(), size, format!("(antijoin {left_text} {right_text} {pair_text})"), RootKind::Rows);
            }
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

/// What a part of the base tables' type holds: a lib relation's by its declaration, and a fragment's by its body.
fn base_refinements(place: usize, part: &crate::gen_constants::ConstantPart) -> Refined {
    static HELD: std::sync::OnceLock<Mutex<FastMap<usize, Refined>>> = std::sync::OnceLock::new();
    let held = HELD.get_or_init(Default::default);
    if let Some(found) = held.lock().expect("no panic").get(&place) {
        return found.clone();
    }
    let names: Vec<String> = part.columns.iter().map(|(name, _)| (*name).to_string()).collect();
    let call = crate::gen_constants::part_call(&part.name);
    let found = if call.starts_with('(') {
        let native: Vec<(String, String)> = names.iter().map(|name| (name.clone(), name.clone())).collect();
        refine_parts::base_part(&call, &native).map(|result| {
            let mut refined = result.refined;
            for (columns, source, at) in &result.within {
                let of = match source.as_str() {
                    "input" => LEAF_INPUT,
                    "output" => LEAF_OUTPUT,
                    _ => continue,
                };
                let places: Vec<u16> = at.iter().map(|name| u16::from(name != "P")).collect();
                refined.within.push(Within { columns: columns.clone().into_boxed_slice(), of, at: places.into_boxed_slice() });
            }
            refined.count_follows = false;
            refined
        })
    } else {
        refine_parts::lib_leaf(&call, &names)
    };
    let found = found.unwrap_or_else(|| {
        let mut refined = Refined::with_arity(names.len());
        refined.add_key(refined.all_columns());
        refined
    });
    held.lock().expect("no panic").insert(place, found.clone());
    found
}

/// The source of an Ident column of a constant part: a grid's components share one.
fn ident_source(name: &str) -> u16 {
    match name {
        "input-components" | "input-component-boxes" => 1,
        "output-components" | "output-component-boxes" => 2,
        "input-foreground-components" => 3,
        "output-foreground-components" => 4,
        "changed-components" | "changed-component-boxes" => 5,
        "input-component-shapes" => 6,
        "output-component-shapes" => 7,
        "input-component-shapes-d4" => 8,
        "output-component-shapes-d4" => 9,
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
    /// The count of examples of a task-wide walk.
    pub examples: u32,
}

/// What a walker holds at most between walks.
const HELD_CELLS: usize = 3_000_000;
const HELD_MEMO: usize = 250_000;
/// The cells that the terms one walk extends can give, counted at each instance.
const WALK_CELLS: usize = 100_000_000;
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
        RootOf::OverExamples => share(rows, other),
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
        Walker { family, eval: Evaluator::new(&NO_SHAPES, &NO_INSTANCES, &NO_LIBS, arclog::decode::corpus::corpus_session()), values: vec![Val::None, Val::Empty], value_index: FastMap::default(), memo: FastMap::default(), counts: FastMap::default(), held_cells: 0, examples: 0 }
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
        let mut walk_cells = 0usize;
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let at = at as u32;
            let first = std::mem::take(&mut ids[term.a as usize]);
            let second = if term.b == NO_TERM { Vec::new() } else if term.b == term.a { first.clone() } else { std::mem::take(&mut ids[term.b as usize]) };
            let step = term.step.as_ref().expect("a term has a step");
            let reads_output = term.flags & READS_OUTPUT != 0;
            let scope = if reads_output { train.min(instances) } else { instances };
            let wanted = (term.flags & READS_TABLE != 0 || family.over_grids) && (reads_output || !only_output);
            let extended = term.used;
            let mut own = Vec::new();
            let on_no_rows = matches!(step, Step::Part(part) if part.gives_rows_on_no_rows());
            let idle = (!on_no_rows && first[..scope].iter().all(|id| *id == 1)) || first[..scope].iter().all(|id| *id == 0) || (matches!(step, Step::Join { .. } | Step::Semijoin { .. }) && second[..scope].iter().all(|id| *id == 1));
            if extended {
                own.reserve(instances);
                // Past the bound, what a term gives has no value, so a walk's memory stays bounded.
                for pair in 0..if walk_cells > WALK_CELLS { 0 } else { scope } {
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
                    if let Val::Rows(parts) = &self.values[id as usize] {
                        walk_cells += parts.iter().map(|part| part.table.cells.len()).sum::<usize>();
                    }
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
                        let value = root_value(*of, rows, left, if *of == RootOf::OverExamples { self.examples } else { other }, number);
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
        // A task keeps a walker per schema, so one large walk leaves nothing behind.
        self.keep_within_budget();
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

    /// A term's type, where the family keeps it.
    pub fn term_refined(&self, at: usize) -> Option<&Refined> {
        self.refined.get(at)
    }

    /// The values of a rejected term over the values of its relations.
    pub fn rejected_value(walker: &mut Walker<'_>, term: &RejectedTerm, first: &Val, second: Option<&Val>) -> Val {
        match second {
            Some(second) => walker.eval.apply(&term.step, &[first, second]),
            None => walker.eval.apply(&term.step, &[first]),
        }
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

/// The rows of a table with an Example column first: at each example, its rows with that example's
/// cell. A table with several TableRows at an example has no task-wide value.
pub fn lifted_rows(tables: &[Vec<Arc<Table>>]) -> Option<Arc<Table>> {
    let arity = tables.iter().find_map(|models| models.first()).map(|table| table.arity)?;
    let mut cells = Vec::new();
    for (example, models) in tables.iter().enumerate() {
        let one = match models.as_slice() {
            [one] => one,
            [] => continue,
            _ => return None,
        };
        let bits = example_bits(example);
        if one.arity == 0 {
            if one.len > 0 {
                cells.push(bits);
            }
            continue;
        }
        for row in one.rows() {
            cells.push(bits);
            cells.extend_from_slice(row);
        }
    }
    Some(Table::distinct(arity + 1, cells))
}

/// An example's cell.
pub fn example_bits(example: usize) -> u32 {
    arclog::terms::Term::Constant(arclog::terms::Constant::Example(arclog::terms::Example::at(example as u16))).encode().expect("an example has bits").encoding()
}

/// The terms that the cache of families holds at most; past it, the oldest families leave.
const CACHED_TERMS: usize = 3_000_000;

/// The families of each schema, kept in a bounded cache, and the name of each root.
#[derive(Default)]
pub struct Generators {
    held: Mutex<(FastMap<u128, (Arc<Generated>, u64)>, u64)>,
    pub names: NameStore,
    /// The terms that the cache holds at most, where it is not 0, in place of [`CACHED_TERMS`].
    pub term_limit: usize,
}

impl Generators {
    /// The family under `hash`, built where the cache does not hold it. Past the bound, the oldest families leave.
    fn family_of(&self, hash: u128, build: impl FnOnce() -> Generated) -> Arc<Generated> {
        {
            let mut held = self.held.lock().expect("no panic");
            let (cache, clock) = &mut *held;
            *clock += 1;
            if let Some(found) = cache.get_mut(&hash) {
                found.1 = *clock;
                return found.0.clone();
            }
        }
        let family = Arc::new(build());
        let limit = if self.term_limit == 0 { CACHED_TERMS } else { self.term_limit };
        let mut held = self.held.lock().expect("no panic");
        let (cache, clock) = &mut *held;
        *clock += 1;
        cache.insert(hash, (family.clone(), *clock));
        let mut total: usize = cache.values().map(|found| found.0.terms.len()).sum();
        while total > limit && cache.len() > 1 {
            let Some(oldest) = cache.iter().filter(|(key, _)| **key != hash).min_by_key(|(_, found)| found.1).map(|(key, _)| *key) else { break };
            if let Some(gone) = cache.remove(&oldest) {
                total -= gone.0.terms.len();
            }
        }
        family
    }

    /// The task-wide family of a table's schema.
    pub fn get_task_wide(&self, stored: &crate::stored::Stored, d: usize) -> Arc<Generated> {
        let hash = hash_words(format!("task-wide {d} {}", stored.key).bytes().map(u64::from));
        self.family_of(hash, || Generated::task_wide(&stored.types, d, &self.names))
    }

    /// The family of two tables of a state.
    pub fn get_two_tables(&self, t: &crate::stored::Stored, u: &crate::stored::Stored) -> Arc<Generated> {
        let all: Vec<ValueType> = t.types.iter().chain(&u.types).cloned().collect();
        let hash = hash_words(format!("two {} {}", t.types.len(), crate::stored::schema_key(&all)).bytes().map(u64::from));
        self.family_of(hash, || Generated::of_two_tables(&t.types, &u.types, &self.names))
    }

    /// The family of a pair's own numbers.
    pub fn get_grids(&self, d: usize) -> Arc<Generated> {
        let hash = hash_words(format!("grids {d}").bytes().map(u64::from));
        self.family_of(hash, || Generated::of_grids(d, &self.names))
    }

    pub fn get(&self, stored: &crate::stored::Stored, d: usize) -> Arc<Generated> {
        let hash = hash_words(stored.key.bytes().map(u64::from));
        self.family_of(hash, || Generated::of(&stored.types, d, &self.names))
    }
}

