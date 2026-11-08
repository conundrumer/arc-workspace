//! Generated features: the shapes over a table up to a size, enumerated over parts, and evaluated
//! natively in one pass per table. The size of a term counts its operators and its parts, each
//! once. Nothing here is written for one feature.
//!
//! A walk gives each root's numbers at each instance of a table: an example, or a model at an
//! example where the example has several. What the numbers are is the specification's section on
//! vectors, and `table_vector` combines the instances into a table's vector.

use std::sync::{Arc, Mutex};

use arclog::types::ValueType;

use crate::columns::Columns;
use crate::expression::Op;
use crate::gen_constants::{constant_parts, constant_tables, number_of};
use crate::gen_parts::{clear_views, flat, PartStep, PartTerm};
use crate::lookup::{LookupMap, LookupSet};
use crate::native::{hash_words, Evaluator, FastMap, Step, Table, Val, WORD_COUNT, WORD_NONEMPTY, WORD_SET};
use crate::refine::{self, bit, Claim, Refined, Rejected, Within};
use crate::refine_parts::{self, PartPlan, RelationInput};
use crate::stored::{mix_word, shape_text};

pub const READS_INPUT: u8 = 1;
pub const READS_OUTPUT: u8 = 2;
pub const READS_TABLE: u8 = 4;
pub const READS_SECOND: u8 = 8;
const NO_TERM: u32 = u32::MAX;
const MAX_PROJECTED: usize = 4;
pub const MAX_COLUMNS: usize = 12;
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
#[derive(Clone, Copy, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
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
#[derive(Clone, Copy, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
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

/// Each term's step as an id, so that terms with one step on equal values compute it once.
#[derive(Default)]
struct StepIds {
    /// Equal where two terms have one step and their roots read the same of its rows.
    ids: Vec<u32>,
    /// For a term whose roots read only a count of rows: the id of its step apart from its keys,
    /// and the id of its keys. A `project` has `PROJECT` as the first, since its count is the groups'.
    grouped: Vec<Option<(u32, u32)>>,
    keys: Vec<Box<[u16]>>,
}

const PROJECT: u32 = u32::MAX;

/// A built family as a file holds it: what a walk reads of each term.
#[derive(serde::Serialize, serde::Deserialize)]
struct SavedTerm(Option<Step>, u32, u32, u8, u8, RootKind, Vec<(u64, u64, RootOf)>, bool);

#[derive(serde::Serialize, serde::Deserialize)]
struct SavedFamily {
    terms: Vec<SavedTerm>,
    first_term: usize,
    by_size: Vec<usize>,
    roots: usize,
    task_wide: bool,
    over_grids: bool,
    two_tables: bool,
    /// The heads by name and the head of each term, where the counts of bounds ran.
    #[serde(default)]
    head_names: Vec<String>,
    #[serde(default)]
    term_heads: Vec<u32>,
}

/// The terms over a table of one schema.
pub struct Generated {
    /// The names of the table's key columns, while the family is built.
    key_columns: Vec<String>,
    step_ids: std::sync::OnceLock<StepIds>,
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
    /// While it holds, the parts of a table are only those keyed by its one Color or Ident column as a group.
    one_group: bool,
    /// The terms that a part of the base tables names.
    diff_terms: Vec<u32>,
    /// Whether the family's roots read the base tables and no other table.
    over_grids: bool,
    /// Whether each of the family's roots reads two tables.
    two_tables: bool,
    /// The head number of each term, where the counts of bounds run, and none otherwise.
    bound_heads: Vec<u32>,
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
        Generated::with_column_names_of(types, column_names, d, names, false)
    }

    /// The second pass's terms: a table's parts keyed by its one Color or Ident column as a group, whose shapes are those of a table with several such columns,
    /// and each of its columns of cells against the cells of a grid's parts.
    pub fn one_group(types: &[ValueType], d: usize, names: &NameStore) -> Generated {
        let columns: Vec<String> = (0..types.len()).map(|at| format!("T{at}")).collect();
        Generated::with_column_names_of(types, &columns, d, names, true)
    }

    /// As [`Generated::one_group`], with the columns under the names a program gives them.
    pub fn one_group_with_names(types: &[ValueType], column_names: &[String], d: usize, names: &NameStore) -> Generated {
        Generated::with_column_names_of(types, column_names, d, names, true)
    }

    fn with_column_names_of(types: &[ValueType], column_names: &[String], d: usize, names: &NameStore, one_group: bool) -> Generated {
        Generated::keyed_with_column_names_of(types, &[], column_names, d, names, one_group)
    }

    /// As [`Generated::of`], where `keys` says which columns are key columns, which group a table's cells beside its Ident and Color columns.
    pub fn of_keyed(types: &[ValueType], keys: &[bool], d: usize, names: &NameStore) -> Generated {
        let columns: Vec<String> = (0..types.len()).map(|at| format!("T{at}")).collect();
        Generated::keyed_with_column_names_of(types, keys, &columns, d, names, false)
    }

    /// As [`Generated::one_group`], where `keys` says which columns are key columns.
    pub fn one_group_keyed(types: &[ValueType], keys: &[bool], d: usize, names: &NameStore) -> Generated {
        let columns: Vec<String> = (0..types.len()).map(|at| format!("T{at}")).collect();
        Generated::keyed_with_column_names_of(types, keys, &columns, d, names, true)
    }

    fn keyed_with_column_names_of(types: &[ValueType], keys: &[bool], column_names: &[String], d: usize, names: &NameStore, one_group: bool) -> Generated {
        let mut family = Generated::empty();
        family.key_columns = column_names.iter().zip(keys).filter(|(_, key)| **key).map(|(name, _)| name.clone()).collect();
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
        family.push(Step::Part(PartTerm::new(PartStep::Same)), LEAF_TABLE, NO_TERM, own_columns, 0, "T".to_string(), RootKind::Rows);
        let own_rows = family.terms.len() as u32 - 1;
        if one_group {
            // The table's own count and value set are the first pass's.
            family.refined[own_rows as usize].count_follows = true;
            family.terms[own_rows as usize].root = RootKind::Rows;
            family.one_group = true;
            family.parts_of(LEAF_TABLE, 1);
            family.one_group = false;
            family.by_size.push(family.terms.len());
            if d >= 2 {
                let below: Vec<u32> = (family.first_term as u32..family.by_size[0] as u32).filter(|at| family.terms[*at as usize].size > 0).collect();
                for at in below {
                    family.extend_term(at, 2, true);
                }
            }
            for at in FIRST_CONSTANT..family.first_term as u32 {
                family.cells_against(at);
            }
            family.box_measures(true);
            family.by_size.push(family.terms.len());
            family.name_roots(types, names);
            return family;
        }
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
                    family.push(Step::Part(PartTerm::new(PartStep::Same)), top, *base, Vec::new(), 2, text, RootKind::Against);
                }
            }
        }
        family.box_measures(false);
        family.column_measures();
        family.by_size.push(family.terms.len());
        family.name_roots(types, names);
        family
    }

    /// The family of two tables of a state, T and U: how the rows, values and cells of one stand to the
    /// other's, and what the two say together of the output.
    pub fn of_two_tables(t_types: &[ValueType], u_types: &[ValueType], names: &NameStore) -> Generated {
        Generated::of_two_tables_keyed(t_types, &[], u_types, &[], names)
    }

    /// As [`Generated::of_two_tables`], where `t_keys` and `u_keys` say which columns of each table are key columns, which group its cells beside its Ident and Color columns.
    pub fn of_two_tables_keyed(t_types: &[ValueType], t_keys: &[bool], u_types: &[ValueType], u_keys: &[bool], names: &NameStore) -> Generated {
        let t_names: Vec<String> = (0..t_types.len()).map(|at| format!("T{at}")).collect();
        let u_names: Vec<String> = (0..u_types.len()).map(|at| format!("T{}", t_types.len() + at)).collect();
        Generated::two_tables_keyed_with_names(t_types, t_keys, &t_names, u_types, u_keys, &u_names, "U", names)
    }

    /// As [`Generated::of_two_tables`], with the columns under the names a program gives them, and U's text.
    pub fn two_tables_with_names(t_types: &[ValueType], t_names: &[String], u_types: &[ValueType], u_names: &[String], u_text: &str, names: &NameStore) -> Generated {
        Generated::two_tables_keyed_with_names(t_types, &[], t_names, u_types, &[], u_names, u_text, names)
    }

    #[allow(clippy::too_many_arguments)]
    fn two_tables_keyed_with_names(t_types: &[ValueType], t_keys: &[bool], t_names: &[String], u_types: &[ValueType], u_keys: &[bool], u_names: &[String], u_text: &str, names: &NameStore) -> Generated {
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
        family.derived_cells(u_leaf);
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
                family.push(Step::Part(PartTerm::new(PartStep::SameValues { a, b })), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("(same-values T {u_text} {} {})", x.name, y.name), RootKind::Holds);
                // A column's values are its `project` at every width, so a shape's name does not depend on a table's width.
                let mut project_of = |family: &mut Generated, leaf: u32, place: u16| -> u32 {
                    *own_projects.entry((leaf, place)).or_insert_with(|| {
                        let column = family.terms[leaf as usize].columns[usize::from(place)].clone();
                        let text = format!("(project {} {})", family.terms[leaf as usize].text, column.name);
                        family.force_next = true;
                        family.push(Step::Project { columns: Columns::one(place) }, leaf, NO_TERM, vec![column], 1, text, RootKind::Rows);
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
                    let step_text = format!("(semijoin {t_text} {u_values_text} {pair})");
                    family.push(Step::semijoin(&left, &right, &step_text), t_values, u_values, t_own, 2, step_text, RootKind::Share);
                    let step_text = format!("(semijoin {u_values_text} {t_text} {back})");
                    family.push(Step::semijoin(&right, &left, &step_text), u_values, t_values, u_own, 2, step_text, RootKind::Share);
                    let step_text = format!("(all {t_text} {u_values_text} () {pair})");
                    family.push(Step::all(&left, &right, &[], &step_text), t_values, u_values, Vec::new(), 2, step_text, RootKind::Holds);
                    let step_text = format!("(all {u_values_text} {t_text} () {back})");
                    family.push(Step::all(&right, &left, &[], &step_text), u_values, t_values, Vec::new(), 2, step_text, RootKind::Holds);
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
                    family.push(Step::Part(PartTerm::new(PartStep::InsideBoxes { a, b })), cell_leaf, box_leaf, cell_columns.clone(), 1, format!("(inside-boxes {cell_text} {box_text} {cell_name} {box_name})"), RootKind::Share);
                    family.push(Step::Part(PartTerm::new(PartStep::BoxesHolding { a: b, b: a })), box_leaf, cell_leaf, box_columns.clone(), 1, format!("(boxes-holding {box_text} {cell_text} {box_name} {cell_name})"), RootKind::Share);
                }
            }
        }
        // The cells of each key of one that are those of a key of the other.
        for (first, other) in [(LEAF_TABLE, u_leaf), (u_leaf, LEAF_TABLE)] {
            let (own, theirs) = (family.terms[first as usize].columns.clone(), family.terms[other as usize].columns.clone());
            let (own_text, their_text) = (family.terms[first as usize].text.clone(), family.terms[other as usize].text.clone());
            for a in places(&own, &cells) {
                for b in places(&theirs, &cells) {
                    for (keys, key_text) in family.key_options(&own, &[usize::from(a)]) {
                        for (others, other_text) in family.key_options(&theirs, &[usize::from(b)]) {
                            let heads: Vec<Column> = keys.iter().map(|at| own[usize::from(*at)].clone()).collect();
                            let (a_name, b_name) = (&own[usize::from(a)].name, &theirs[usize::from(b)].name);
                            for (turned, word) in [(false, "same-shape"), (true, "same-shape-d4")] {
                                family.push(Step::Part(PartTerm::new(PartStep::SameShape { keys: keys.clone(), a, others: others.clone(), b, turned })), first, other, heads.clone(), 1, format!("({word} {own_text} {their_text} {key_text} {a_name} {other_text} {b_name})"), RootKind::Rows);
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
                        family.push(Step::Part(PartTerm::new(PartStep::DeterminesJointly { p: a, v: v as u16, w: w as u16 })), join as u32, LEAF_GRIDS, Vec::new(), 2, text, RootKind::Holds);
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
                    let step_text = t_text.clone();
                    family.push(Step::semijoin(&left, &right, &step_text), covered, LEAF_TABLE, covered_columns.clone(), 2, step_text, RootKind::Share);
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
                            let step_text = format!("(semijoin {t_text} {u_text} {pairs})");
                            family.push(Step::semijoin(&l, &r, &step_text), held, u_leaf, covered_columns.clone(), 3, step_text, RootKind::Share);
                            let step_text = format!("(antijoin {t_text} {u_text} {pairs})");
                            family.push(Step::antijoin(&l, &r, &step_text), held, u_leaf, covered_columns.clone(), 3, step_text, RootKind::Share);
                        }
                    }
                }
            }
        }
        family.pair_words(t_keys, u_keys);
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
            family.push(Step::Part(PartTerm::new(PartStep::Same)), *at, NO_TERM, columns, 1, text, RootKind::Rows);
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
            // A relation of no column has at most one row, so its count is whether it has a row.
            let root = if term.columns.is_empty() && matches!(term.root, RootKind::Rows | RootKind::Share) { RootKind::Holds } else { term.root };
            let mut texts: Vec<(String, RootOf)> = match root {
                RootKind::Holds if count_follows && term.columns.is_empty() => Vec::new(),
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
        if crate::bounds::enabled() {
            family.bound_heads = family.terms.iter().map(|term| crate::bounds::head_of(&term.text)).collect();
        }
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
        family.push(Step::Part(PartTerm::new(PartStep::Same)), LEAF_TABLE, NO_TERM, own_columns, 0, "T".to_string(), RootKind::Rows);
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
        family.output_functions();
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
            // A key of every column has one row, so its count would be 1 everywhere; the count needs a column outside the key.
            if keys.len() < columns.len() {
                pushes.push((PartStep::Count { keys: keys.clone() }, with(vec![fresh("N", ValueType::Nat, 0)]), format!("(count {text} {key_text})"), RootKind::Rows));
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
            // The classes of a column's cells over the examples: one where its shape is one at every example.
            let classes = matches!(&part, PartStep::ShapeClass { keys, .. } if keys.as_ref() == [e]);
            let id = kept.last().cloned();
            let before = self.terms.len();
            self.push(Step::Part(PartTerm::new(part)), at, NO_TERM, kept, size, line.clone(), root);
            if let (true, Some(id), true) = (classes, id, self.terms.len() > before) {
                let place = self.terms[before].columns.len() as u16 - 1;
                self.push_forced(Step::Project { columns: Columns::one(place) }, before as u32, NO_TERM, vec![id.clone()], size, format!("(project {line} {})", id.name), RootKind::Rows);
            }
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
                self.push(Step::Part(PartTerm::new(PartStep::CommonValues { e: e as u16, n: n as u16 })), table, grid, vec![column.clone()], 3, line.clone(), RootKind::Rows);
                if let (Some(values), true) = (values, self.terms.len() > before) {
                    let common = before as u32;
                    self.push(Step::Part(PartTerm::new(PartStep::Same)), common, values, Vec::new(), 3, format!("{line} {values_text}"), RootKind::Against);
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
        let step_text = format!("(project {output} E Col)");
        add(self, Step::project(&[0, 2], &step_text), LEAF_OUTPUT, NO_TERM, vec![e(), col("Col")], step_text);
        let step_text = format!("(project {output} E P)");
        add(self, Step::project(&[0, 1], &step_text), LEAF_OUTPUT, NO_TERM, vec![e(), p()], step_text);
        add(self, Step::Part(PartTerm::new(PartStep::Count { keys: Box::new([0]) })), LEAF_OUTPUT, NO_TERM, vec![e(), n.clone()], format!("(count {output} (E))"));
        let by_color = add(self, Step::Part(PartTerm::new(PartStep::Count { keys: Box::new([0, 2]) })), LEAF_OUTPUT, NO_TERM, vec![e(), col("Col"), n.clone()], format!("(count {output} (E Col))"));
        add(self, Step::Part(PartTerm::new(PartStep::Extreme { keys: Box::new([0]), t: 1, score: 2, greatest: true })), by_color, NO_TERM, vec![e(), col("Col")], format!("(greatest-by (count {output} (E Col)) (E) Col N)"));
        let step_text = format!("(antijoin {output} {input} (E E) (Col Col))");
        let new_cells = add(self, Step::antijoin(&[0, 2], &[0, 2], &step_text), LEAF_OUTPUT, LEAF_INPUT, vec![e(), p(), col("Col")], step_text);
        let step_text = format!("(project (antijoin {output} {input} (E E) (Col Col)) E Col)");
        add(self, Step::project(&[0, 2], &step_text), new_cells, NO_TERM, vec![e(), col("Col")], step_text);
        let both_text = format!("(join {input} {output} (E E) (P P))");
        let both = add(self, Step::Join { left: Box::new([0, 1]), right: Box::new([0, 1]), kept: Box::new([2]), left_arity: 3 }, LEAF_INPUT, LEAF_OUTPUT, vec![e(), p(), col("Col"), col("Col_2")], both_text.clone());
        let changed_text = format!("(select {both_text} Col != Col_2)");
        let changed = add(self, Step::Select { at: 2, op: Op::Ne, other: Some(3), drop: None }, both, NO_TERM, vec![e(), p(), col("Col"), col("Col_2")], changed_text.clone());
        let step_text = format!("(project {changed_text} E Col Col_2)");
        add(self, Step::project(&[0, 2, 3], &step_text), changed, NO_TERM, vec![e(), col("Col"), col("Col_2")], step_text);
        let step_text = format!("(project {changed_text} E Col_2)");
        add(self, Step::project(&[0, 3], &step_text), changed, NO_TERM, vec![e(), col("Col_2")], step_text);
        let step_text = format!("(project {changed_text} E P)");
        add(self, Step::project(&[0, 1], &step_text), changed, NO_TERM, vec![e(), p()], step_text);
        // The class of each example under each of those.
        let classes_text = |text: &str, columns: &[Column]| -> String {
            let fields: Vec<&str> = columns.iter().skip(1).map(|column| column.name.as_str()).collect();
            let fields = if let [one] = fields[..] { one.to_string() } else { format!("({})", fields.join(" ")) };
            format!("(component Quotient (equivalent (component Inclusion (pattern {text} () (E {fields})) (observed {text} () (E {fields})) equal) () (E E_2)) class)")
        };
        let class_of = |family: &mut Generated, at: u32, source: u16| -> u32 {
            let (text, columns) = (family.terms[at as usize].text.clone(), family.terms[at as usize].columns.clone());
            family.force_next = true;
            family.push(Step::Part(PartTerm::new(PartStep::ExampleClasses { e: 0 })), at, NO_TERM, vec![e(), id("Id", source)], 1, classes_text(&text, &columns), RootKind::Rows);
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
                    self.push(Step::Project { columns: Columns::one(from) }, joined, NO_TERM, vec![id(from_name, 3000)], 3, classes.clone(), RootKind::Rows);
                    let domain = self.terms.len() as u32 - 1;
                    let one_text = format!("(one-value {joined_text} ({from_name}) {to_name})");
                    self.force_next = true;
                    self.push(Step::Part(PartTerm::new(PartStep::OneValue { keys: Box::new([from]), f: to })), joined, NO_TERM, vec![id(from_name, 3000), id(to_name, 3000)], 3, one_text.clone(), RootKind::Rows);
                    let single = self.terms.len() as u32 - 1;
                    self.force_next = true;
                    let step_text = format!("(semijoin {classes} {one_text} ({from_name} {from_name}))");
                    self.push(Step::semijoin(&[0], &[0], &step_text), domain, single, vec![id(from_name, 3000)], 3, step_text, RootKind::Share);
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
                let step_text = format!("(semijoin {left_text} {right_text} {pair_text})");
                self.push(Step::semijoin(&left_at, &right_at, &step_text), l, r, left.clone(), size, step_text, RootKind::Share);
                let step_text = format!("(all {left_text} {right_text} () {pair_text})");
                self.push(Step::all(&left_at, &right_at, &[], &step_text), l, r, Vec::new(), size, step_text, RootKind::Holds);
            }
        }
    }

    fn empty() -> Generated {
        Generated { key_columns: Vec::new(), step_ids: std::sync::OnceLock::new(), one_group: false, terms: Vec::new(), first_term: 0, by_size: Vec::new(), roots: 0, refined: Vec::new(), forms: Vec::new(), rejected_by_rule: Default::default(), rejected: Vec::new(), keep_text: std::env::var_os("GENERATE_KEEP_TEXT").is_some(), no_rules: std::env::var_os("GENERATE_NO_RULES").is_some(), task_wide: false, force_next: false, diff_terms: Vec::new(), over_grids: false, two_tables: false, bound_heads: Vec::new() }
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
            Step::All { reads, left_len, right } => {
                let (left, outer) = reads.split(*left_len);
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
    /// Pushes a term that no rule judges, and gives its place, or nothing where it has more columns than a term can.
    fn push_forced(&mut self, step: Step, a: u32, b: u32, columns: Vec<Column>, size: u8, text: String, root: RootKind) -> Option<u32> {
        let before = self.terms.len();
        self.force_next = true;
        self.push(step, a, b, columns, size, text, root);
        (self.terms.len() > before).then_some(before as u32)
    }

    fn push(&mut self, step: Step, a: u32, b: u32, mut columns: Vec<Column>, size: u8, text: String, root: RootKind) {
        if columns.len() > MAX_COLUMNS {
            self.force_next = false;
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
            self.push_forced(Step::Part(PartTerm::new(PartStep::SameRows { left: left.into_boxed_slice(), right: right.into_boxed_slice(), key })), LEAF_TABLE, other, Vec::new(), 1, format!("({word} T {other_text} T*:{}{free_text})", pairs.join(",")), RootKind::Holds);
        }
    }

    /// How the table and another stand to each other as words: their columns as sets, their counts, the groups of their cells, and their colors at shared cells. A column of cells is a Position column, or a Box column whose values are the cells of one frame.
    fn pair_words(&mut self, t_keys: &[bool], u_keys: &[bool]) {
        use crate::gen_parts::{AgreeRelation, SetRelation};
        let u_leaf = self.terms.iter().position(|term| term.flags & READS_SECOND != 0).expect("a second relation") as u32;
        let (own, theirs) = (self.terms[LEAF_TABLE as usize].columns.clone(), self.terms[u_leaf as usize].columns.clone());
        let u_text = self.terms[u_leaf as usize].text.clone();
        let is_number = |ty: &ValueType| matches!(ty, ValueType::Nat | ValueType::Int);
        let is_cells = |ty: &ValueType| matches!(ty, ValueType::Position | ValueType::Box);
        let of_types = |columns: &[Column], test: &dyn Fn(&ValueType) -> bool| -> Vec<(u16, String)> {
            columns.iter().enumerate().filter(|(_, column)| test(&column.ty)).map(|(at, column)| (at as u16, column.name.clone())).collect()
        };
        let (own_cells, their_cells) = (of_types(&own, &is_cells), of_types(&theirs, &is_cells));
        let (own_colors, their_colors) = (of_types(&own, &|ty| *ty == ValueType::Color), of_types(&theirs, &|ty| *ty == ValueType::Color));
        let their_boxes = of_types(&theirs, &|ty| *ty == ValueType::Box);
        let own_ways = of_types(&own, &|ty| matches!(ty, ValueType::Dir | ValueType::Dir8 | ValueType::DiagDir));
        let group = |columns: &[Column], flags: &[bool]| -> Vec<u16> {
            (0..columns.len() as u16).filter(|at| matches!(columns[usize::from(*at)].ty, ValueType::Color | ValueType::Ident(_)) || flags.get(usize::from(*at)).copied().unwrap_or(false)).collect()
        };
        let (own_group, their_group) = (group(&own, t_keys), group(&theirs, u_keys));
        let keys_text = |keys: &[u16], columns: &[Column]| -> String {
            format!("(T*:{})", keys.iter().map(|at| columns[usize::from(*at)].name.as_str()).collect::<Vec<_>>().join(","))
        };
        // Each word over a pair of columns, in each direction where the word has one.
        let words = |this: &mut Self, l: u32, l_text: &str, a: u16, x: &str, r: u32, r_text: &str, b: u16, y: &str, cells: bool| {
            let mut put = |word: SetRelation, first: (u32, &str, u16, &str), second: (u32, &str, u16, &str)| {
                let text = format!("({} {} {} {} {})", word.fragment(cells), first.1, second.1, first.3, second.3);
                this.push_forced(Step::Part(PartTerm::new(PartStep::SetWord { a: first.2, b: second.2, cells, word })), first.0, second.0, Vec::new(), 2, text, RootKind::Holds);
            };
            let (left, right) = ((l, l_text, a, x), (r, r_text, b, y));
            put(SetRelation::Subset, left, right);
            put(SetRelation::Subset, right, left);
            put(SetRelation::Overlap, left, right);
            put(SetRelation::Disjoint, left, right);
            if cells {
                put(SetRelation::Complement, left, right);
            }
        };
        for (a, x) in own.iter().enumerate() {
            for (b, y) in theirs.iter().enumerate() {
                let (a, b) = (a as u16, b as u16);
                let alike = (x.ty == y.ty && !matches!(x.ty, ValueType::Ident(_) | ValueType::Example | ValueType::Position)) || (is_number(&x.ty) && is_number(&y.ty));
                if alike {
                    words(self, LEAF_TABLE, "T", a, &x.name, u_leaf, &u_text, b, &y.name, false);
                }
                if is_cells(&x.ty) && is_cells(&y.ty) {
                    // The words over the cells of a frame need a Position column first. Over boxes, a Box column against a Box column has the words over sets.
                    let frame_cells = x.ty == ValueType::Position;
                    if frame_cells || x.ty != y.ty {
                        words(self, LEAF_TABLE, "T", a, &x.name, u_leaf, &u_text, b, &y.name, frame_cells);
                    }
                    // A Position column against a Position column already has these.
                    if x.ty == ValueType::Box || y.ty == ValueType::Box {
                        self.push_forced(Step::Part(PartTerm::new(PartStep::SameValues { a, b })), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("(same-values T {u_text} {} {})", x.name, y.name), RootKind::Holds);
                        for (turned, head) in [(false, "same-shape"), (true, "same-shape-d4")] {
                            self.push_forced(Step::Part(PartTerm::new(PartStep::SameShape { keys: Box::new([]), a, others: Box::new([]), b, turned })), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("({head} T {u_text} () {} () {})", x.name, y.name), RootKind::Rows);
                        }
                    }
                }
            }
        }
        // A column's values, as the relation that counts them.
        let values_of = |this: &mut Self, leaf: u32, text: &str, at: u16, column: &Column| -> Option<u32> {
            let own_text = format!("(project {text} {})", column.name);
            let found = this.terms.iter().rposition(|term| term.text == own_text).map(|held| held as u32);
            found.or_else(|| this.push_forced(Step::Project { columns: Columns::one(at) }, leaf, NO_TERM, vec![column.clone()], 1, own_text, RootKind::Rows))
        };
        let groups_of = |this: &mut Self, leaf: u32, text: &str, keys: &[u16], columns: &[Column], key_text: String| -> Option<u32> {
            if keys.len() >= columns.len() {
                return None;
            }
            let count_text = format!("(count {text} {key_text})");
            let found = this.terms.iter().rposition(|term| term.text == count_text).map(|held| held as u32);
            let mut held: Vec<Column> = keys.iter().map(|at| columns[usize::from(*at)].clone()).collect();
            held.push(Column { name: unique("N", columns), ty: ValueType::Nat, source: 0 });
            found.or_else(|| this.push_forced(Step::Part(PartTerm::new(PartStep::Count { keys: keys.to_vec().into_boxed_slice() })), leaf, NO_TERM, held, 1, count_text, RootKind::Rows))
        };
        let compare = |this: &mut Self, l: u32, r: u32| {
            let (l_text, r_text) = (this.terms[l as usize].text.clone(), this.terms[r as usize].text.clone());
            this.push_forced(Step::Part(PartTerm::new(PartStep::CountWord { less: true })), l, r, Vec::new(), 2, format!("(count-less {l_text} {r_text})"), RootKind::Holds);
            this.push_forced(Step::Part(PartTerm::new(PartStep::CountWord { less: true })), r, l, Vec::new(), 2, format!("(count-less {r_text} {l_text})"), RootKind::Holds);
            this.push_forced(Step::Part(PartTerm::new(PartStep::CountWord { less: false })), l, r, Vec::new(), 2, format!("(count-equal {l_text} {r_text})"), RootKind::Holds);
        };
        compare(self, LEAF_TABLE, u_leaf);
        for (a, x) in &own_cells {
            for (b, y) in &their_cells {
                if let (Some(l), Some(r)) = (values_of(self, LEAF_TABLE, "T", *a, &own[usize::from(*a)]), values_of(self, u_leaf, &u_text, *b, &theirs[usize::from(*b)])) {
                    let _ = (x, y);
                    compare(self, l, r);
                }
            }
        }
        let their_groups = if their_group.is_empty() { None } else { groups_of(self, u_leaf, &u_text, &their_group, &theirs, keys_text(&their_group, &theirs)) };
        if let (false, Some(r)) = (own_group.is_empty(), their_groups) {
            if let Some(l) = groups_of(self, LEAF_TABLE, "T", &own_group, &own, keys_text(&own_group, &own)) {
                compare(self, l, r);
            }
        }
        for (a, x) in own.iter().enumerate().filter(|(_, column)| is_number(&column.ty)) {
            for (other, other_text) in [Some((u_leaf, u_text.clone())), their_groups.map(|term| (term, self.terms[term as usize].text.clone()))].into_iter().flatten() {
                for (word, name) in [(-1i8, "less"), (0, "equal"), (1, "more")] {
                    self.push_forced(Step::Part(PartTerm::new(PartStep::GreatestCount { a: a as u16, word })), LEAF_TABLE, other, Vec::new(), 2, format!("(greatest-{name}-count T {} {other_text})", x.name), RootKind::Holds);
                }
            }
        }
        if !own_group.is_empty() && !their_group.is_empty() {
            // A group's cells are the cells of a frame, so Position columns.
            for (p, x) in own_cells.iter().filter(|(at, _)| own[usize::from(*at)].ty == ValueType::Position) {
                for (q, y) in their_cells.iter().filter(|(at, _)| theirs[usize::from(*at)].ty == ValueType::Position) {
                    let (l_keys, r_keys) = (keys_text(&own_group, &own), keys_text(&their_group, &theirs));
                    for (shapes, head) in [(false, "groups"), (true, "shapes")] {
                        let step = |word| Step::Part(PartTerm::new(PartStep::GroupsWord { p: *p, left: own_group.clone().into_boxed_slice(), q: *q, right: their_group.clone().into_boxed_slice(), shapes, word }));
                        let back = Step::Part(PartTerm::new(PartStep::GroupsWord { p: *q, left: their_group.clone().into_boxed_slice(), q: *p, right: own_group.clone().into_boxed_slice(), shapes, word: SetRelation::Subset }));
                        self.push_forced(step(SetRelation::Equal), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("({head}-equal T {u_text} {l_keys} {x} {r_keys} {y})"), RootKind::Holds);
                        self.push_forced(step(SetRelation::Subset), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("({head}-subset T {u_text} {l_keys} {x} {r_keys} {y})"), RootKind::Holds);
                        self.push_forced(back, u_leaf, LEAF_TABLE, Vec::new(), 1, format!("({head}-subset {u_text} T {r_keys} {y} {l_keys} {x})"), RootKind::Holds);
                        self.push_forced(step(SetRelation::Overlap), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("({head}-overlap T {u_text} {l_keys} {x} {r_keys} {y})"), RootKind::Holds);
                        self.push_forced(step(SetRelation::Disjoint), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("({head}-disjoint T {u_text} {l_keys} {x} {r_keys} {y})"), RootKind::Holds);
                    }
                }
            }
        }
        for (p, n) in &own_cells {
            for (x, c) in &own_colors {
                for (q, m) in &their_cells {
                    for (y, d) in &their_colors {
                        for (word, name) in [(AgreeRelation::EveryOne, "every"), (AgreeRelation::None, "none"), (AgreeRelation::Some, "some")] {
                            self.push_forced(Step::Part(PartTerm::new(PartStep::AgreeWord { p: *p, x: *x, q: *q, y: *y, word })), LEAF_TABLE, u_leaf, Vec::new(), 1, format!("(colors-agree-{name} T {u_text} {n} {c} {m} {d})"), RootKind::Holds);
                        }
                    }
                }
            }
        }
        for (a, x) in &own_cells {
            let own_text = format!("(project T {x})");
            let Some(values) = values_of(self, LEAF_TABLE, "T", *a, &own[usize::from(*a)]) else { continue };
            let own_column = self.terms[values as usize].columns.clone();
            // The project's column is named by its label.
            let label = crate::expand::label_of(x);
            for (b, y) in &their_cells {
                if own[usize::from(*a)].ty == ValueType::Position && theirs[usize::from(*b)].ty == ValueType::Position {
                    if let Some(term) = self.push_forced(Step::Part(PartTerm::new(PartStep::LeastDistance { a: *a, b: *b })), LEAF_TABLE, u_leaf, vec![Column { name: "K".to_string(), ty: ValueType::Nat, source: 0 }], 1, format!("(least-distance T {u_text} {x} {y})"), RootKind::Number) {
                        self.refined[term as usize].count_follows = true;
                    }
                }
                self.push_forced(Step::Part(PartTerm::new(PartStep::OnBoundary { b: *b })), values, u_leaf, own_column.clone(), 2, format!("(on-boundary {own_text} {u_text} {label} {y})"), RootKind::Share);
                let mut neighbor = own_column.clone();
                neighbor.push(Column { name: unique("Q", &own_column), ty: own[usize::from(*a)].ty.clone(), source: 0 });
                self.push_forced(Step::Part(PartTerm::new(PartStep::NeighborsIn { b: *b })), values, u_leaf, neighbor, 2, format!("(neighbors-in {own_text} {u_text} {label} {y})"), RootKind::Share);
            }
            for (b, y) in &their_boxes {
                self.push_forced(Step::Part(PartTerm::new(PartStep::InsideBoxes { a: 0, b: *b })), values, u_leaf, own_column.clone(), 2, format!("(inside-boxes {own_text} {u_text} {label} {y})"), RootKind::Share);
                self.push_forced(Step::Part(PartTerm::new(PartStep::OnBorder { b: *b })), values, u_leaf, own_column.clone(), 2, format!("(on-border {own_text} {u_text} {label} {y})"), RootKind::Share);
            }
            // A ray runs over the cells of a frame, so from a Position column.
            for (w, d) in own_ways.iter().filter(|_| own[usize::from(*a)].ty == ValueType::Position) {
                let pair_text = format!("(project T {x} {d})");
                let pair_columns = vec![own[usize::from(*a)].clone(), own[usize::from(*w)].clone()];
                let found = self.terms.iter().rposition(|term| term.text == pair_text).map(|at| at as u32);
                let Some(pairs) = found.or_else(|| self.push_forced(Step::project(&[*a, *w], &pair_text), LEAF_TABLE, NO_TERM, pair_columns.clone(), 1, pair_text.clone(), RootKind::Rows)) else { continue };
                for (b, y) in &their_cells {
                    self.push_forced(Step::Part(PartTerm::new(PartStep::RayMeets { b: *b })), pairs, u_leaf, pair_columns.clone(), 2, format!("(ray-meets {pair_text} {u_text} {label} {} {y})", crate::expand::label_of(d)), RootKind::Share);
                }
            }
        }
        // The cells a table derives from the other's, as sets against its own cells, and the input's colors under them, as sets against its own colors.
        for (b, y) in &their_cells {
            let name = unique("P", &theirs);
            let parts = [("box-cells", PartStep::BoxCells { p: *b, outside: false }), ("hole-cells", PartStep::HoleCells { p: *b })];
            for (word, part) in parts {
                let derived_text = format!("({word} {u_text} {y})");
                let found = self.terms.iter().rposition(|term| term.text == derived_text).map(|at| at as u32);
                let Some(derived) = found.or_else(|| self.push_forced(Step::Part(PartTerm::new(part)), u_leaf, NO_TERM, vec![Column { name: name.clone(), ty: ValueType::Position, source: 0 }], 2, derived_text.clone(), RootKind::Rows)) else { continue };
                for (a, x) in &own_cells {
                    words(self, LEAF_TABLE, "T", *a, x, derived, &derived_text, 0, &name, own[usize::from(*a)].ty == ValueType::Position);
                    self.push_forced(Step::Part(PartTerm::new(PartStep::SameValues { a: *a, b: 0 })), LEAF_TABLE, derived, Vec::new(), 2, format!("(same-values T {derived_text} {x} {name})"), RootKind::Holds);
                }
            }
            let input_leaf = self.terms.iter().position(|term| term.text == "input").expect("the input") as u32;
            let color = || vec![Column { name: "Col".to_string(), ty: ValueType::Color, source: 0 }];
            let under_text = format!("(colors-under {u_text} {y} input)");
            let found = self.terms.iter().rposition(|term| term.text == under_text).map(|at| at as u32);
            let Some(under) = found.or_else(|| self.push_forced(Step::Part(PartTerm::new(PartStep::ColorsUnder { p: *b })), u_leaf, input_leaf, color(), 2, under_text.clone(), RootKind::Rows)) else { continue };
            let top_text = format!("(most-colors-under {u_text} {y} input)");
            let Some(top) = self.push_forced(Step::Part(PartTerm::new(PartStep::TopColorsUnder { p: *b })), u_leaf, input_leaf, color(), 2, top_text.clone(), RootKind::Rows) else { continue };
            for (a, x) in &own_colors {
                words(self, LEAF_TABLE, "T", *a, x, under, &under_text, 0, "Col", false);
                self.push_forced(Step::Part(PartTerm::new(PartStep::SameValues { a: *a, b: 0 })), LEAF_TABLE, under, Vec::new(), 2, format!("(same-values T {under_text} {x} Col)"), RootKind::Holds);
                if let Some(values) = values_of(self, LEAF_TABLE, "T", *a, &own[usize::from(*a)]) {
                    let own_column = self.terms[values as usize].columns.clone();
                    let step_text = format!("(semijoin (project T {x}) {top_text} ({} Col))", crate::expand::label_of(x));
                    self.push_forced(Step::semijoin(&[0], &[0], &step_text), values, top, own_column, 2, step_text, RootKind::Share);
                }
            }
        }
    }

    /// A table's cells against the cells derived from another relation's: the rest of their frame, their box, the frame outside it, and what they enclose.
    fn derived_cells(&mut self, other: u32) {
        let (own, theirs) = (self.terms[LEAF_TABLE as usize].columns.clone(), self.terms[other as usize].columns.clone());
        let other_text = self.terms[other as usize].text.clone();
        let cells = |columns: &[Column]| -> Vec<(u16, String)> { columns.iter().enumerate().filter(|(_, column)| column.ty == ValueType::Position).map(|(at, column)| (at as u16, column.name.clone())).collect() };
        let own_cells = cells(&own);
        for (b, y) in cells(&theirs) {
            let name = unique("P", &theirs);
            let parts = [("complement", PartStep::Complement { p: b }), ("box-cells", PartStep::BoxCells { p: b, outside: false }), ("outside-box", PartStep::BoxCells { p: b, outside: true }), ("hole-cells", PartStep::HoleCells { p: b })];
            for (word, part) in parts {
                let derived_text = format!("({word} {other_text} {y})");
                let Some(derived) = self.push_forced(Step::Part(PartTerm::new(part)), other, NO_TERM, vec![Column { name: name.clone(), ty: ValueType::Position, source: 0 }], 2, derived_text.clone(), RootKind::Rows) else { continue };
                for (a, x) in &own_cells {
                    let own_text = format!("(project T {x})");
                    let found = self.terms.iter().rposition(|term| term.text == own_text).map(|at| at as u32);
                    let Some(values) = found.or_else(|| self.push_forced(Step::Project { columns: Columns::one(*a) }, LEAF_TABLE, NO_TERM, vec![own[usize::from(*a)].clone()], 1, own_text.clone(), RootKind::Rows)) else { continue };
                    let own_column = self.terms[values as usize].columns.clone();
                    let place: Box<[u16]> = Box::new([0]);
                    self.push_forced(Step::Part(PartTerm::new(PartStep::SameRows { left: place.clone(), right: place.clone(), key: false })), values, derived, Vec::new(), 2, format!("(rows-equal {own_text} {derived_text} T*:{x}={name})"), RootKind::Holds);
                    let step_text = format!("(all {own_text} {derived_text} () ({x} {name}))");
                    self.push_forced(Step::all(&place, &place, &[], &step_text), values, derived, Vec::new(), 2, step_text, RootKind::Holds);
                    let step_text = format!("(all {derived_text} {own_text} () ({name} {x}))");
                    self.push_forced(Step::all(&place, &place, &[], &step_text), derived, values, Vec::new(), 2, step_text, RootKind::Holds);
                    let step_text = format!("(semijoin {own_text} {derived_text} ({x} {name}))");
                    self.push_forced(Step::semijoin(&place, &place, &step_text), values, derived, own_column, 2, step_text, RootKind::Share);
                }
            }
        }
    }

    /// Each column of the table's cells as a set against the cells of a grid's part: whether each holds the other, whether they are one set, and the share of the column's
    /// cells that the part holds. The table's other columns do not enter, so the share counts cells and not rows.
    fn cells_against(&mut self, part: u32) {
        let (own, theirs) = (self.terms[LEAF_TABLE as usize].columns.clone(), self.terms[part as usize].columns.clone());
        let part_text = self.terms[part as usize].text.clone();
        if self.terms[part as usize].flags & (READS_INPUT | READS_OUTPUT) == 0 {
            return;
        }
        let Some(at) = theirs.iter().position(|column| column.ty == ValueType::Position) else { return };
        let name = theirs[at].name.clone();
        let there: Box<[u16]> = Box::new([at as u16]);
        let place: Box<[u16]> = Box::new([0]);
        for (a, x) in own.iter().enumerate().filter(|(_, column)| column.ty == ValueType::Position) {
            let own_text = format!("(project T {})", x.name);
            let found = self.terms.iter().rposition(|term| term.text == own_text).map(|term| term as u32);
            let Some(values) = found.or_else(|| self.push_forced(Step::Project { columns: Columns::one(a as u16) }, LEAF_TABLE, NO_TERM, vec![x.clone()], 1, own_text.clone(), RootKind::Rows)) else { continue };
            // The column's own count is the first pass's.
            self.refined[values as usize].count_follows = true;
            self.push_forced(Step::Part(PartTerm::new(PartStep::SameRows { left: place.clone(), right: there.clone(), key: false })), values, part, Vec::new(), 2, format!("(rows-equal {own_text} {part_text} T*:{}={name})", x.name), RootKind::Holds);
            let step_text = format!("(all {own_text} {part_text} () ({} {name}))", x.name);
            self.push_forced(Step::all(&place, &there, &[], &step_text), values, part, Vec::new(), 2, step_text, RootKind::Holds);
            let step_text = format!("(all {part_text} {own_text} () ({name} {}))", x.name);
            self.push_forced(Step::all(&there, &place, &[], &step_text), part, values, Vec::new(), 2, step_text, RootKind::Holds);
            let step_text = format!("(semijoin {own_text} {part_text} ({} {name}))", x.name);
            self.push_forced(Step::semijoin(&place, &there, &step_text), values, part, vec![x.clone()], 2, step_text, RootKind::Share);
        }
    }

    /// Whether a table's column and the output color at its cell determine each other over the rows of every example, and whether the column with the input
    /// color at that cell determines the output color. A task-wide family holds these whatever its size.
    fn output_functions(&mut self) {
        let own = self.terms[LEAF_TABLE as usize].columns.clone();
        for (p, place) in own.iter().enumerate().filter(|(_, column)| column.ty == ValueType::Position) {
            let text = format!("(join T ex_output (E E) ({} P))", place.name);
            let Some(join) = self.terms.iter().rposition(|term| term.text == text) else { continue };
            let columns = self.terms[join].columns.clone();
            let color = columns.len() - 1;
            let color_name = columns[color].name.clone();
            let input_name = unique("Col", &columns);
            let input_text = format!("(join {text} ex_input (E E) ({} P))", columns[p].name);
            let e = own.iter().position(|column| column.ty == ValueType::Example).unwrap_or(0);
            let mut with_input = columns.clone();
            with_input.push(Column { name: input_name.clone(), ty: ValueType::Color, source: 0 });
            let both = self.push_forced(Step::Join { left: vec![e as u16, p as u16].into_boxed_slice(), right: vec![0, 1].into_boxed_slice(), kept: vec![2].into_boxed_slice(), left_arity: columns.len() as u16 }, join as u32, LEAF_INPUT, with_input, 3, input_text.clone(), RootKind::Rows);
            for x in 0..own.len() {
                if x == p || matches!(own[x].ty, ValueType::Example | ValueType::Position | ValueType::Box | ValueType::Offset) {
                    continue;
                }
                let x_name = columns[x].name.clone();
                self.push_forced(Step::Part(PartTerm::new(PartStep::Determines { keys: vec![x as u16].into_boxed_slice(), f: color as u16 })), join as u32, NO_TERM, Vec::new(), 3, format!("(determines {text} ({x_name}) {color_name})"), RootKind::Holds);
                self.push_forced(Step::Part(PartTerm::new(PartStep::Determines { keys: vec![color as u16].into_boxed_slice(), f: x as u16 })), join as u32, NO_TERM, Vec::new(), 3, format!("(determines {text} ({color_name}) {x_name})"), RootKind::Holds);
                if let Some(both) = both {
                    self.push_forced(Step::Part(PartTerm::new(PartStep::Determines { keys: vec![x as u16, columns.len() as u16].into_boxed_slice(), f: color as u16 })), both, NO_TERM, Vec::new(), 3, format!("(determines {input_text} ({x_name} {input_name}) {color_name})"), RootKind::Holds);
                }
            }
        }
    }

    /// `project` and `select` over a term.
    fn unary_operators(&mut self, at: u32, size: u8) {
        let columns = self.terms[at as usize].columns.clone();
        let text = self.terms[at as usize].text.clone();
        let count = columns.len();
        // A shape's name does not depend on a table's width, so a table's own `project` of all its columns stands as a term.
        let every = at == LEAF_TABLE;
        if count >= 2 || (every && count == 1) {
            // Each set of at most MAX_PROJECTED columns as a mask, in the order of the masks, built from the sets of one column fewer.
            let mut masks: Vec<u64> = Vec::new();
            let mut level: Vec<u64> = vec![0];
            for _ in 0..MAX_PROJECTED.min(count) {
                let mut next: Vec<u64> = Vec::new();
                for mask in &level {
                    let first = (u64::BITS - mask.leading_zeros()) as usize;
                    next.extend((first..count).map(|place| *mask | (1u64 << place)));
                }
                masks.extend(&next);
                level = next;
            }
            masks.sort_unstable();
            for mask in masks {
                // Only a table has a projection that keeps all its columns.
                if !every && mask == (1u64 << count) - 1 {
                    continue;
                }
                let places: Vec<u16> = (0..count as u16).filter(|place| mask >> place & 1 == 1).collect();
                let kept: Vec<Column> = places.iter().map(|place| columns[usize::from(*place)].clone()).collect();
                let names: Vec<&str> = kept.iter().map(|column| column.name.as_str()).collect();
                let line = format!("(project {text} {})", names.join(" "));
                let step_text = line;
                self.push(Step::project(&places, &step_text), at, NO_TERM, kept, size, step_text, RootKind::Rows);
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
    fn key_options(&self, columns: &[Column], not: &[usize]) -> Vec<(Box<[u16]>, String)> {
        let mut out: Vec<(Box<[u16]>, String)> = vec![(Box::new([]), "()".to_string())];
        for (at, column) in columns.iter().enumerate() {
            if !not.contains(&at) {
                out.push((vec![at as u16].into_boxed_slice(), format!("({})", column.name)));
            }
        }
        let group: Vec<u16> = columns.iter().enumerate().filter(|(at, column)| !not.contains(at) && (matches!(column.ty, ValueType::Color | ValueType::Ident(_)) || self.key_columns.contains(&column.name))).map(|(at, _)| at as u16).collect();
        if group.len() >= 2 {
            let names: Vec<&str> = group.iter().map(|at| columns[usize::from(*at)].name.as_str()).collect();
            out.push((group.into_boxed_slice(), format!("(T*:{})", names.join(","))));
        }
        out
    }

    /// What one column says as a whole: its cells' frame and how they fill it, its values as a list, the rows that its two greatest numbers count, and the rows of a color column's two most frequent values.
    fn column_measures(&mut self) {
        use crate::gen_parts::ColumnMeasureKind::*;
        let columns = self.terms[LEAF_TABLE as usize].columns.clone();
        let number = || vec![Column { name: "N".to_string(), ty: ValueType::Nat, source: 0 }];
        for (place, column) in columns.iter().enumerate() {
            let (at, name) = (place as u16, column.name.clone());
            let holds = |this: &mut Self, measure, word: &str| {
                this.push_forced(Step::Part(PartTerm::new(PartStep::ColumnMeasure { a: at, measure })), LEAF_TABLE, NO_TERM, Vec::new(), 1, format!("({word} T {name})"), RootKind::Holds);
            };
            match column.ty {
                ValueType::Position => {
                    let P = |this: &Self| vec![Column { name: unique("P", &this.terms[LEAF_TABLE as usize].columns), ty: ValueType::Position, source: 0 }];
                    if let Some(term) = self.push_forced(Step::Part(PartTerm::new(PartStep::ComplementParts { p: at })), LEAF_TABLE, NO_TERM, number(), 1, format!("(complement-parts T {name})"), RootKind::Number) {
                        self.refined[term as usize].count_follows = true;
                    }
                    self.push_forced(Step::Part(PartTerm::new(PartStep::EveryPartStraight { p: at })), LEAF_TABLE, NO_TERM, Vec::new(), 1, format!("(every-part-straight T {name})"), RootKind::Holds);
                    self.push_forced(Step::Part(PartTerm::new(PartStep::OutlinesBox { p: at })), LEAF_TABLE, NO_TERM, Vec::new(), 1, format!("(outlines-box T {name})"), RootKind::Holds);
                    // How much of its frame it fills, and its bounding box fills.
                    let frame_text = format!("(frame-cells T {name})");
                    let own_text = format!("(project T {name})");
                    let cell = P(self);
                    let found = self.terms.iter().rposition(|term| term.text == own_text).map(|held| held as u32);
                    let values = found.or_else(|| self.push_forced(Step::Project { columns: Columns::one(at) }, LEAF_TABLE, NO_TERM, vec![column.clone()], 1, own_text.clone(), RootKind::Rows));
                    let box_text = format!("(box-cells T {name})");
                    let found = self.terms.iter().rposition(|term| term.text == box_text).map(|held| held as u32);
                    let in_box = found.or_else(|| self.push_forced(Step::Part(PartTerm::new(PartStep::BoxCells { p: at, outside: false })), LEAF_TABLE, NO_TERM, cell.clone(), 1, box_text.clone(), RootKind::Rows));
                    if let Some(frame) = self.push_forced(Step::Part(PartTerm::new(PartStep::FrameCells { p: at })), LEAF_TABLE, NO_TERM, cell, 1, frame_text.clone(), RootKind::Rows) {
                        if let Some(values) = values {
                            self.push_forced(Step::Part(PartTerm::new(PartStep::Same)), values, frame, Vec::new(), 2, format!("{own_text} {frame_text}"), RootKind::Against);
                        }
                        if let Some(in_box) = in_box {
                            self.push_forced(Step::Part(PartTerm::new(PartStep::Same)), in_box, frame, Vec::new(), 2, format!("{box_text} {frame_text}"), RootKind::Against);
                        }
                    }
                    if let Some(term) = self.push_forced(Step::Part(PartTerm::new(PartStep::ColumnMeasure { a: at, measure: ExtentsDistinct })), LEAF_TABLE, NO_TERM, number(), 1, format!("(extents-distinct T {name})"), RootKind::Number) {
                        self.refined[term as usize].count_follows = true;
                    }
                }
                ValueType::Color => {
                    // The rows of its most frequent value over those of its next most frequent one.
                    let text_of = |word: &str| format!("({word} T () {name})");
                    let (most_text, second_text) = (text_of("most-frequent-rows"), text_of("second-frequent-rows"));
                    let found = self.terms.iter().rposition(|term| term.text == most_text).map(|held| held as u32);
                    let most = found.or_else(|| self.push_forced(Step::Part(PartTerm::new(PartStep::MostFrequentRows { keys: Box::new([]), v: at })), LEAF_TABLE, NO_TERM, columns.clone(), 1, most_text.clone(), RootKind::Share));
                    let second = self.push_forced(Step::Part(PartTerm::new(PartStep::SecondFrequentRows { keys: Box::new([]), v: at })), LEAF_TABLE, NO_TERM, columns.clone(), 1, second_text.clone(), RootKind::Share);
                    if let (Some(most), Some(second)) = (most, second) {
                        self.push_forced(Step::Part(PartTerm::new(PartStep::Same)), most, second, Vec::new(), 2, format!("{most_text} {second_text}"), RootKind::Against);
                    }
                }
                ValueType::Nat | ValueType::Int => {
                    holds(self, Consecutive, "values-consecutive");
                    holds(self, Arithmetic, "values-arithmetic");
                }
                ValueType::Dir | ValueType::Dir8 | ValueType::DiagDir => {
                    holds(self, OnOneAxis, "directions-on-one-axis");
                    holds(self, OppositePair, "directions-opposite-pair");
                }
                ValueType::Offset => holds(self, OneLength, "offsets-one-length"),
                _ => {}
            }
        }
    }

    /// What a set of boxes says together: the bounding box of a column's cells, the bounding boxes of its groups, and a Box column's boxes in a grid's frame.
    fn box_measures(&mut self, one_group: bool) {
        use crate::gen_parts::BoxMeasureKind;
        let columns = self.terms[LEAF_TABLE as usize].columns.clone();
        let number = || vec![Column { name: "N".to_string(), ty: ValueType::Nat, source: 0 }];
        let cell = || vec![Column { name: "P".to_string(), ty: ValueType::Position, source: 0 }];
        self.one_group = one_group;
        let options: Vec<Vec<(Box<[u16]>, String)>> = (0..columns.len()).map(|place| self.keys_of(&columns, &[place])).collect();
        self.one_group = false;
        // Over a table's own Box column in a grid's frame, the least margin and the sides are what `least` and `greatest` give over `box-margin` and `box-extent`, at size 2.
        let measures = |this: &mut Self, boxes: u32, b: u16, b_name: &str, boxes_text: &str, frame: u32, f: u16, f_name: &str, frame_text: &str, in_grid: bool| {
            for measure in BoxMeasureKind::ALL {
                if in_grid && matches!(measure, BoxMeasureKind::LeastMargin | BoxMeasureKind::ShorterSideMin | BoxMeasureKind::LongerSideMax) {
                    continue;
                }
                let text = format!("({} {boxes_text} {b_name} {frame_text} {f_name})", measure.fragment());
                let step = Step::Part(PartTerm::new(PartStep::BoxMeasure { b, f, measure }));
                if measure.is_number() {
                    if let Some(term) = this.push_forced(step, boxes, frame, number(), 2, text, RootKind::Number) {
                        this.refined[term as usize].count_follows = true;
                    }
                } else {
                    this.push_forced(step, boxes, frame, Vec::new(), 2, text, RootKind::Holds);
                }
            }
            let one_text = format!("(one-box-cells {boxes_text} {b_name} {frame_text} {f_name})");
            this.push_forced(Step::Part(PartTerm::new(PartStep::OneBoxCells { b, f })), boxes, frame, cell(), 2, one_text, RootKind::Rows)
        };
        for (place, column) in columns.iter().enumerate() {
            if !matches!(column.ty, ValueType::Position | ValueType::Box) {
                continue;
            }
            let (p, name) = (place as u16, column.name.clone());
            let frame_text = format!("(frame-cells T {name})");
            for (keys, key_text) in options[place].iter().filter(|_| column.ty == ValueType::Position) {
                let grouped = key_text.starts_with("(T*");
                let one_column = grouped && !key_text.contains(',');
                if !(keys.is_empty() || grouped) || (one_group && !one_column) {
                    continue;
                }
                let box_name = unique("B", &columns);
                let boxes_text = format!("(box-of T {key_text} {name})");
                let found = self.terms.iter().rposition(|term| term.text == boxes_text).map(|held| held as u32);
                let mut own: Vec<Column> = keys.iter().map(|key| columns[usize::from(*key)].clone()).collect();
                own.push(Column { name: box_name.clone(), ty: ValueType::Box, source: 0 });
                let Some(boxes) = found.or_else(|| self.push_forced(Step::Part(PartTerm::new(PartStep::BoxOf { keys: keys.clone(), p })), LEAF_TABLE, NO_TERM, own, 1, boxes_text.clone(), RootKind::Rows)) else { continue };
                let one = measures(self, boxes, keys.len() as u16, &box_name, &boxes_text, LEAF_TABLE, p, &name, "T", false);
                let frame = self.terms.iter().rposition(|term| term.text == frame_text).map(|held| held as u32);
                let frame_columns = vec![Column { name: unique("P", &columns), ty: ValueType::Position, source: 0 }];
                let frame = frame.or_else(|| {
                    let made = self.push_forced(Step::Part(PartTerm::new(PartStep::FrameCells { p })), LEAF_TABLE, NO_TERM, frame_columns, 1, frame_text.clone(), RootKind::Rows);
                    // The first pass's family gives the frame's own count.
                    if let (true, Some(made)) = (one_group, made) {
                        self.refined[made as usize].count_follows = true;
                    }
                    made
                });
                if let (Some(one), Some(frame)) = (one, frame) {
                    let one_text = format!("(one-box-cells {boxes_text} {box_name} T {name})");
                    self.push_forced(Step::Part(PartTerm::new(PartStep::Same)), one, frame, Vec::new(), 3, format!("{one_text} {frame_text}"), RootKind::Against);
                }
            }
            if column.ty == ValueType::Box && !one_group {
                for (grid, label) in [(LEAF_INPUT, "input"), (LEAF_OUTPUT, "output")] {
                    let one = measures(self, LEAF_TABLE, p, &name, "T", grid, 0, "P", label, true);
                    if let Some(one) = one {
                        let one_text = format!("(one-box-cells T {name} {label} P)");
                        self.push_forced(Step::Part(PartTerm::new(PartStep::Same)), one, grid, Vec::new(), 3, format!("{one_text} {label}"), RootKind::Against);
                    }
                }
            }
        }
    }

    /// Whether the table is a product of two groups of its columns, for each way to split them. The split stands in no shape's name.
    fn product(&mut self) {
        let columns = self.terms[LEAF_TABLE as usize].columns.clone();
        if columns.len() < 2 {
            return;
        }
        // Each split once: the group that holds the first column is the key.
        let whole = (1u32 << columns.len()) - 1;
        for mask in (1..whole).step_by(2) {
            let keys: Box<[u16]> = (0..columns.len() as u16).filter(|at| mask >> at & 1 == 1).collect();
            let names: Vec<&str> = keys.iter().map(|at| columns[usize::from(*at)].name.as_str()).collect();
            let text = format!("(product T (T*:{}))", names.join(","));
            self.push_forced(Step::Part(PartTerm::new(PartStep::Product { keys })), LEAF_TABLE, NO_TERM, Vec::new(), 1, text, RootKind::Holds);
        }
    }

    /// The keys of a term's parts. Under `one_group`, also the one Color or Ident column as a group, which stands under the name of several such columns.
    fn keys_of(&self, columns: &[Column], not: &[usize]) -> Vec<(Box<[u16]>, String)> {
        let mut out = self.key_options(columns, not);
        if self.one_group {
            let group: Vec<u16> = columns.iter().enumerate().filter(|(at, column)| !not.contains(at) && (matches!(column.ty, ValueType::Color | ValueType::Ident(_)) || self.key_columns.contains(&column.name))).map(|(at, _)| at as u16).collect();
            // Where the table has two or more group columns, the first pass's family gives the shapes over its groups, so this pass gives none.
            let whole = columns.iter().filter(|column| matches!(column.ty, ValueType::Color | ValueType::Ident(_)) || self.key_columns.contains(&column.name)).count();
            if let ([only], true) = (&group[..], whole < 2) {
                out.push((vec![*only].into_boxed_slice(), format!("(T*:{})", columns[usize::from(*only)].name)));
            }
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
        let mut add = |part: PartStep, b: u32, kept: Vec<Column>, line: String, root: RootKind| pushes.push((Step::Part(PartTerm::new(part)), b, kept, line, root));
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
                if at == LEAF_TABLE {
                    add(PartStep::LineSpacings { p }, NO_TERM, vec![one("A", ValueType::Axis, 0), one("N", ValueType::Nat, 0)], format!("(line-spacings {text} {name})"), RootKind::Rows);
                }
            }
            if matches!(column.ty, ValueType::Position | ValueType::Box) {
                // A Box column has the parts that read its values as boxes. The others read each value as one cell of a frame.
                let cells = column.ty == ValueType::Position;
                for (keys, key_text) in self.keys_of(&columns, &[place]) {
                    let heads = key_columns(&keys);
                    let extended = |extra: Vec<Column>| -> Vec<Column> { heads.iter().cloned().chain(extra).collect() };
                    add(PartStep::Pieces { keys: keys.clone(), p, four: false }, NO_TERM, extended(vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::Pieces { keys: keys.clone(), p, four: true }, NO_TERM, extended(vec![column.clone(), fresh("Id", ValueType::OPEN_IDENT, id_source)]), format!("(pieces4 {text} {key_text} {name})"), RootKind::Rows);
                    if cells {
                        add(PartStep::FullLines { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("Along", ValueType::Box, 0)]), format!("(full-lines {text} {key_text} {name})"), RootKind::Rows);
                    }
                    add(PartStep::BoxOf { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("B", ValueType::Box, 0)]), format!("(box-of {text} {key_text} {name})"), RootKind::Rows);
                    add(PartStep::RelBox { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("X_rel", ValueType::Box, 0)]), format!("(cells-in-box {text} {key_text} {name})"), RootKind::Rows);
                    if cells {
                        add(PartStep::ShapeClass { keys: keys.clone(), p, turned: false }, NO_TERM, extended(vec![fresh("Id", ValueType::OPEN_IDENT, 900)]), format!("(shape-class {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::ShapeClass { keys: keys.clone(), p, turned: true }, NO_TERM, extended(vec![fresh("Id", ValueType::OPEN_IDENT, 901)]), format!("(shape-class-d4 {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::Holes { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(holes {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::Symmetry { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(symmetry {text} {key_text} {name})"), RootKind::Rows);
                    }
                    if !keys.is_empty() {
                        for (output, grid_name) in [(true, "output"), (false, "input")] {
                            add(PartStep::DiffGroupsOff { keys: keys.clone(), p, output }, LEAF_GRIDS, heads.clone(), format!("(groups-off-{grid_name}-diff {text} {key_text} {name})"), RootKind::Rows);
                        }
                    }
                    add(PartStep::TouchesEdge { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(touches-edge {text} {key_text} {name})"), RootKind::Rows);
                    if cells {
                        add(PartStep::FillsBox { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(fills-box {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::Straight { keys: keys.clone(), p }, NO_TERM, heads.clone(), format!("(straight {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::CellCount { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(cell-count {text} {key_text} {name})"), RootKind::Rows);
                    }
                    if self.one_group && cells {
                        add(PartStep::StraightAxis { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0)]), format!("(straight-axis {text} {key_text} {name})"), RootKind::Rows);
                    }
                    if cells {
                        add(PartStep::GroupGap { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("N", ValueType::Nat, 0)]), format!("(group-gap {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::BoxSides { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("N", ValueType::Int, 0)]), format!("(box-sides {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::BoxMargins { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("D", ValueType::Dir, 0), fresh("K", ValueType::Int, 0)]), format!("(box-margins {text} {key_text} {name})"), RootKind::Rows);
                        add(PartStep::LineCounts { keys: keys.clone(), p }, NO_TERM, extended(vec![fresh("A", ValueType::Axis, 0), fresh("Along", ValueType::Box, 0), fresh("N", ValueType::Nat, 0)]), format!("(line-counts {text} {key_text} {name})"), RootKind::Rows);
                    }
                    for (v, value) in columns.iter().enumerate() {
                        if cells && value.ty == ValueType::Color && v != place && !keys.contains(&(v as u16)) {
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
                                for (keys, key_text) in self.keys_of(&columns, &[place, other]) {
                                    let kept: Vec<Column> = key_columns(&keys).into_iter().chain([value.clone()]).collect();
                                    add(PartStep::Extreme { keys, t: other as u16, score: p, greatest }, NO_TERM, kept, format!("({label}-by {text} {key_text} {} {name})", value.name), RootKind::Rows);
                                }
                            }
                        }
                    }
                }
            }
        }
        for (keys, key_text) in self.keys_of(&columns, &[]) {
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
            // The second pass holds a key of one group column, and no shape that the first pass's family has.
            let one_column = line.find("(T*:").is_some_and(|place| !line[place..].split(')').next().unwrap_or("").contains(','));
            if !self.one_group || one_column || line.starts_with("(straight-axis ") {
                self.push(step, at, b, kept, size, line, root);
            }
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
                let step_text = format!("(semijoin {left_text} {right_text} {pair_text})");
                self.push(Step::semijoin(&left_at, &right_at, &step_text), l, r, narrowed.clone(), size, step_text, RootKind::Share);
                let step_text = format!("(antijoin {left_text} {right_text} {pair_text})");
                self.push(Step::antijoin(&left_at, &right_at, &step_text), l, r, left.clone(), size, step_text, RootKind::Rows);
            }
            let step_text = format!("(all {left_text} {right_text} () {pair_text})");
            self.push(Step::all(&left_at, &right_at, &[], &step_text), l, r, Vec::new(), size, step_text, RootKind::Holds);
            for (at, column) in left.iter().enumerate() {
                if !left_at.contains(&(at as u16)) {
                    let step_text = format!("(all {left_text} {right_text} ({}) {pair_text})", column.name);
                    self.push(Step::all(&left_at, &right_at, &vec![at as u16], &step_text), l, r, vec![column.clone()], size, step_text, RootKind::Rows);
                }
            }
            if let [(a, b)] = pairs[..] {
                let (a_name, b_name) = (&left[usize::from(a)].name, &right[usize::from(b)].name);
                // A key that determines whether a row has a match.
                if left.len() >= 2 {
                    for (at, column) in left.iter().enumerate() {
                        if at != usize::from(a) {
                            self.push(Step::Part(PartTerm::new(PartStep::DeterminesFlag { keys: vec![at as u16].into_boxed_slice(), a, b })), l, r, Vec::new(), size, format!("(determines-flag {left_text} {right_text} ({}) {a_name} {b_name})", column.name), RootKind::Holds);
                        }
                    }
                }
                if left[usize::from(a)].ty == ValueType::Position && right[usize::from(b)].ty == ValueType::Position {
                    self.push(Step::Part(PartTerm::new(PartStep::SharedLine { a, b })), l, r, left.clone(), size, format!("(shared-line {left_text} {right_text} {a_name} {b_name})"), RootKind::Share);
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
    /// The count of ground expressions that the root's definition leaves out here, as a ratio whose denominator counts 0.
    pub undefined: u32,
}

pub const SLOT_DEFAULT: u8 = 0;
pub const SLOT_VALUE: u8 = 1;
pub const SLOT_NO_VALUE: u8 = 2;

/// Each root's numbers at each instance of a table.
#[derive(Default)]
pub struct RootTable {
    /// The place of each root, by its hash.
    index: LookupMap<u128, u32>,
    /// The hash of the root at each place.
    hashes: Vec<u128>,
    pub slots: Vec<Slot>,
    pub stride: usize,
    /// What each root reads, its size, and which kind of root it is.
    pub meta: Vec<(u8, u8, RootOf)>,
    /// Per root, the count of terms that give it a value at every instance, and of those that give it one at the train instances alone.
    bindings: FastMap<u128, (u32, u32)>,
}

impl RootTable {
    fn slots_of(&mut self, hash: u128, flags: u8, size: u8, of: RootOf) -> usize {
        let next = self.meta.len() as u32;
        let stride = self.stride;
        let at = *self.index.entry(hash).or_insert(next);
        if at == next {
            self.hashes.push(hash);
            self.meta.push((flags, size, of));
            self.slots.resize(self.slots.len() + stride, Slot::default());
        }
        at as usize * stride
    }

    /// Each root's hash and place, in the order of the low 64 bits of the hash, which is how a vector names a shape, and then of the whole hash.
    pub fn sorted_roots(&self) -> Vec<(u128, usize)> {
        let mut order: Vec<(u128, usize)> = self.hashes.iter().enumerate().map(|(at, hash)| (*hash, at)).collect();
        order.sort_unstable_by_key(|(hash, _)| (*hash as u64, *hash));
        order
    }
}

/// A list of shapes, each by the low 64 bits of its hash, which is how a vector names it.
#[derive(Clone, Debug, Default)]
pub struct ShapeList {
    shapes: LookupSet<u64>,
}

impl ShapeList {
    pub fn new(shapes: impl IntoIterator<Item = u64>) -> ShapeList {
        ShapeList { shapes: shapes.into_iter().collect() }
    }

    /// The hash of a shape's text, as the vector names it.
    pub fn hash_of_text(text: &str) -> u64 {
        hash_words(text.bytes().map(u64::from)) as u64
    }

    pub fn of_texts<'t>(texts: impl IntoIterator<Item = &'t str>) -> ShapeList {
        ShapeList::new(texts.into_iter().map(ShapeList::hash_of_text))
    }

    pub fn contains(&self, shape: u64) -> bool {
        self.shapes.contains(&shape)
    }

    pub fn len(&self) -> usize {
        self.shapes.len()
    }

    pub fn is_empty(&self) -> bool {
        self.shapes.is_empty()
    }
}

/// The terms of one family that a list of shapes needs: the terms with a listed root, and every term that a term
/// of the mask reads, directly or through other terms. It is made for one family and one list.
pub struct ShapeMask {
    /// Per term, whether a walk over the mask walks it.
    needed: Vec<bool>,
    /// Per term, a bit for each of its roots that the list holds.
    listed: Vec<u8>,
}

impl ShapeMask {
    /// The count of terms that a walk over the mask walks, and the count of roots it writes.
    pub fn counts(&self) -> (usize, usize) {
        (self.needed.iter().filter(|held| **held).count(), self.listed.iter().map(|bits| bits.count_ones() as usize).sum())
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
    /// How keys group a value's rows: a hash of the grouping, and the count of groups.
    groupings: FastMap<(u32, u32), (u128, u32)>,
    /// A part's count of rows at a grouping of its first value, with its second value.
    group_counts: FastMap<(u32, u32, u128, u32), u32>,
    /// The cells that `values` holds.
    held_cells: usize,
    /// For a lazy value by id, the id of its written rows.
    written_of: FastMap<u32, u32>,
    /// The stored values that have a copy on disk, by id.
    spilled: FastMap<u32, Spilled>,
    /// The folder of those copies, once made.
    spill_dir: Option<SpillDir>,
    /// The count of copies made, which names the next.
    spill_serial: u64,
    /// What the copies on disk have cost so far.
    spill_cost: SpillCost,
    /// The count of examples of a task-wide walk.
    pub examples: u32,
    /// The cells and the memo entries it holds at most between walks.
    budget: (usize, usize),
    /// Whether the last walk stopped a term that was charged more than [`walk_cells`] cells, so that the term, and every term that reads it, have no value.
    pub over_budget: bool,
}

/// What a walker's copies on disk have cost: the values and cells written and read back, and the time of each.
#[derive(Default)]
struct SpillCost {
    written: (u64, u64),
    read: (u64, u64),
    write_nanos: u64,
    read_nanos: u64,
    compact_nanos: u64,
}

/// A stored value's copy on disk.
struct Spilled {
    path: std::path::PathBuf,
    /// The cells of the value.
    cells: usize,
    /// Whether the value is in memory. If not, its place in `values` holds no value, and a read of it must fetch it first.
    here: bool,
}

/// What a walker holds at most between walks.
const HELD_CELLS: usize = 3_000_000;
const HELD_MEMO: usize = 250_000;
/// The cells that one term can be charged in a walk, by default ([`walk_cells`]): those of each input it reads and of each output it gives, at each instance, each as rows times columns.
const WALK_CELLS: usize = 100_000_000;

/// The cells that one term can be charged in a walk: `GENERATE_WALK_CELLS` where it is set, else [`WALK_CELLS`].
fn walk_cells() -> usize {
    static LIMIT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
    *LIMIT.get_or_init(|| std::env::var("GENERATE_WALK_CELLS").ok().and_then(|text| text.parse().ok()).unwrap_or(WALK_CELLS))
}
/// The cells of movable stored values (rows of at least `spill::MIN_CELLS` cells) that a walk keeps in memory between terms, once it moves the others to disk, by default ([`resident_cells`]).
const RESIDENT_CELLS: usize = 100_000_000;

/// The cells of movable stored values that a walk keeps in memory: `GENERATE_RESIDENT_CELLS` where it is set, else [`RESIDENT_CELLS`].
fn resident_cells() -> usize {
    static LIMIT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
    *LIMIT.get_or_init(|| std::env::var("GENERATE_RESIDENT_CELLS").ok().and_then(|text| text.parse().ok()).unwrap_or(RESIDENT_CELLS))
}
/// A count past this stands for "no value": a bound stopped the term.
const NO_COUNT: u32 = u32::MAX;

static NO_SHAPES: [crate::native::CompShape; 0] = [];
static NO_INSTANCES: [crate::native::CompInstance; 0] = [];
static NO_LIBS: [crate::native::LibRelation; 0] = [];

fn rows_of(value: &Val) -> Option<u64> {
    match value {
        Val::None => None,
        Val::Empty => Some(0),
        Val::Boxes(boxes) => Some(boxes.rows()),
        Val::Joined(joined) => Some(joined.rows()),
        Val::Rows(parts) => Some(parts.iter().fold(1u64, |count, part| count.saturating_mul(part.table.len as u64))),
    }
}

/// The cells of `rows` rows of `arity` columns, as a set. No rows are no cells.
fn set_cells(rows: Option<u64>, arity: usize) -> usize {
    rows.map_or(0, |rows| usize::try_from(rows.saturating_mul(arity as u64)).unwrap_or(usize::MAX))
}

fn count_of(value: &Val) -> u32 {
    rows_of(value).map_or(NO_COUNT, |count| count.min(u64::from(NO_COUNT - 1)) as u32)
}

fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}

/// What a root is at an instance.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum RootNumber {
    /// A number, and the word that hashes it.
    Value(Number, u64),
    /// Unknown: a bound stopped the term, or it reads a relation that has no value. Its true value could change the greatest, the sum or the least of the root's values.
    Unknown,
    /// Undefined by the root's definition: a ratio whose denominator counts 0, or a set without exactly one member. It leaves the root's values, and the others stand.
    Undefined,
}

/// The cells that a stored value holds: those of its tables, or of a joined value's sides and ids.
fn held_of(value: &Val) -> usize {
    match value {
        Val::Rows(parts) => parts.iter().map(|part| part.table.cells.len()).sum::<usize>(),
        Val::Joined(joined) => joined.held_cells(),
        _ => 0,
    }
}

/// The value of a root at an instance, from the counts of rows.
fn root_value(of: RootOf, rows: u32, left: u32, other: u32, number: u32) -> RootNumber {
    let share = |top: u32, bottom: u32| -> RootNumber {
        if top == NO_COUNT || bottom == NO_COUNT {
            return RootNumber::Unknown;
        }
        // A ratio whose denominator counts 0 is undefined, 0 over 0 included. A zero numerator over a denominator that counts rows is 0.
        if bottom == 0 {
            return RootNumber::Undefined;
        }
        if top == 0 {
            return RootNumber::Value(Number::whole(0), 0);
        }
        let held = Number::fraction(u64::from(top), u64::from(bottom));
        RootNumber::Value(held, WORD_SET | (hash_words([u64::from(held.top as u32), u64::from(held.bottom)]) as u64 & PAYLOAD))
    };
    match of {
        RootOf::Nonempty if rows == NO_COUNT => RootNumber::Unknown,
        RootOf::Nonempty => RootNumber::Value(Number::whole(i64::from(rows > 0)), if rows > 0 { WORD_NONEMPTY | 1 } else { 0 }),
        RootOf::Cardinality if rows == NO_COUNT => RootNumber::Unknown,
        RootOf::Cardinality => RootNumber::Value(Number::whole(i64::from(rows)), if rows > 0 { WORD_COUNT | u64::from(rows) } else { 0 }),
        RootOf::Share => share(rows, left),
        RootOf::Over => share(rows, other),
        RootOf::Under => share(other, rows),
        RootOf::OverExamples => share(rows, other),
        RootOf::ValueSet if rows == NO_COUNT => RootNumber::Unknown,
        // One member gives a number. A set with no member, or with several, is undefined.
        RootOf::ValueSet if number > 0 => RootNumber::Value(Number::whole(number_of_word(number)), WORD_SET | u64::from(number)),
        RootOf::ValueSet => RootNumber::Undefined,
    }
}

/// The folder of a walker's copies on disk, which goes when the walker does.
struct SpillDir(std::path::PathBuf);

impl Drop for SpillDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

impl<'a> Walker<'a> {
    pub fn new(family: &'a Generated) -> Self {
        Walker { family, eval: Evaluator::new(&NO_SHAPES, &NO_INSTANCES, &NO_LIBS, arclog::decode::corpus::corpus_session()), values: vec![Val::None, Val::Empty], value_index: FastMap::default(), memo: FastMap::default(), counts: FastMap::default(), groupings: FastMap::default(), group_counts: FastMap::default(), held_cells: 0, written_of: FastMap::default(), spilled: FastMap::default(), spill_dir: None, spill_serial: 0, spill_cost: SpillCost::default(), examples: 0, budget: (HELD_CELLS, HELD_MEMO), over_budget: false }
    }

    /// A walker that holds more between walks than [`Walker::new`], for many related tables.
    pub fn with_budget(family: &'a Generated, cells: usize, entries: usize) -> Self {
        let mut walker = Walker::new(family);
        walker.budget = (cells, entries);
        walker
    }

    /// The memo entries and the cells it holds.
    pub fn held(&self) -> (usize, usize) {
        (self.memo.len() + self.counts.len() + self.groupings.len() + self.group_counts.len() + self.values.len(), self.held_cells)
    }

    /// Drops the values and the memos where they pass the budget. A later walk computes again
    /// what it needs.
    fn keep_within_budget(&mut self) {
        self.keep_within_budget_with(0);
    }

    /// [`Walker::keep_within_budget`], where `extra` cells beyond the held ones count against the budget.
    fn keep_within_budget_with(&mut self, extra: usize) {
        if self.held_cells + extra > self.budget.0 || self.memo.len() + self.counts.len() + self.groupings.len() + self.group_counts.len() > self.budget.1 || !self.spilled.is_empty() {
            self.forget_spilled();
            self.values = vec![Val::None, Val::Empty];
            self.value_index = FastMap::default();
            self.memo = FastMap::default();
            self.counts = FastMap::default();
            self.groupings = FastMap::default();
            self.group_counts = FastMap::default();
            self.written_of = FastMap::default();
            self.held_cells = 0;
            // The tables those values held are gone, so an address they had can hold another.
            clear_views();
        }
    }

    /// Drops every stored value that no list of `ids` holds, and every memo entry, so that a walk's memory stays bounded between its terms. The lists are renumbered. A later evaluation computes again what it needs, and it forces the same lazy values, so no value and no cost changes.
    fn compact(&mut self, ids: &mut [Vec<u32>]) {
        let mut hash_of: Vec<u128> = vec![0; self.values.len()];
        for (hash, at) in self.value_index.sorted_entries() {
            hash_of[*at as usize] = *hash;
        }
        let mut values = vec![Val::None, Val::Empty];
        let mut index: FastMap<u128, u32> = FastMap::default();
        let mut renumbered: FastMap<u32, u32> = FastMap::default();
        let mut held = 0usize;
        for list in ids.iter_mut() {
            for id in list.iter_mut() {
                let old = *id;
                if old > 1 {
                    *id = *renumbered.entry(old).or_insert_with(|| {
                        let value = self.values[old as usize].clone();
                        held += held_of(&value);
                        index.insert(hash_of[old as usize], values.len() as u32);
                        values.push(value);
                        values.len() as u32 - 1
                    });
                }
            }
        }
        if crate::bounds::enabled() {
            crate::bounds::tally("compact", "walks' compactions".to_string(), 1);
            crate::bounds::tally("compact", "cells dropped".to_string(), self.held_cells.saturating_sub(held) as u64);
        }
        // A copy on disk follows its value's new id, and one whose value is dropped goes.
        let mut kept: FastMap<u32, Spilled> = FastMap::default();
        for (old, copy) in std::mem::take(&mut self.spilled).into_sorted_vec() {
            match renumbered.get(&old) {
                Some(new) => {
                    kept.insert(*new, copy);
                }
                None => {
                    let _ = std::fs::remove_file(&copy.path);
                }
            }
        }
        self.spilled = kept;
        self.values = values;
        self.value_index = index;
        self.held_cells = held;
        self.memo = FastMap::default();
        self.counts = FastMap::default();
        self.groupings = FastMap::default();
        self.group_counts = FastMap::default();
        self.written_of = FastMap::default();
        // The tables those values held are gone, so an address they had can hold another.
        clear_views();
    }

    /// Forgets every copy on disk, and deletes its file.
    fn forget_spilled(&mut self) {
        for (_, copy) in std::mem::take(&mut self.spilled).into_sorted_vec() {
            let _ = std::fs::remove_file(&copy.path);
        }
    }

    /// The path of the next copy on disk, in a folder that is made on first use: `GENERATE_SPILL_DIR`, or the system's folder for temporary files.
    fn next_copy_path(&mut self) -> Option<std::path::PathBuf> {
        if self.spill_dir.is_none() {
            static FOLDERS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
            let base = std::env::var_os("GENERATE_SPILL_DIR").map(std::path::PathBuf::from).unwrap_or_else(std::env::temp_dir);
            let dir = base.join(format!("arclog-spill-{}-{}", std::process::id(), FOLDERS.fetch_add(1, std::sync::atomic::Ordering::Relaxed)));
            std::fs::create_dir_all(&dir).ok()?;
            self.spill_dir = Some(SpillDir(dir));
        }
        self.spill_serial += 1;
        Some(self.spill_dir.as_ref()?.0.join(self.spill_serial.to_string()))
    }

    /// Takes the stored value at `id` out of memory, after a copy of it is on disk. Nothing in the walk reads it until [`Walker::fetch`] brings it back, and then it is the same value. It gives false, with the value in memory, where the value is not rows or the copy cannot be written.
    fn move_to_disk(&mut self, id: u32) -> bool {
        let cells = held_of(&self.values[id as usize]);
        if !self.spilled.contains_key(&id) {
            let Val::Rows(parts) = self.values[id as usize].clone() else { return false };
            let Some(path) = self.next_copy_path() else { return false };
            let started = std::time::Instant::now();
            if crate::spill::write(&path, &parts).is_err() {
                let _ = std::fs::remove_file(&path);
                return false;
            }
            self.spill_cost.write_nanos += started.elapsed().as_nanos() as u64;
            self.spill_cost.written.0 += 1;
            self.spill_cost.written.1 += cells as u64;
            if crate::bounds::enabled() {
                crate::bounds::tally("spill", "values written to disk".to_string(), 1);
                crate::bounds::tally("spill", "cells written to disk".to_string(), cells as u64);
            }
            self.spilled.insert(id, Spilled { path, cells, here: true });
        }
        let Some(copy) = self.spilled.get_mut(&id) else { return false };
        if !copy.here {
            return false;
        }
        copy.here = false;
        self.values[id as usize] = Val::None;
        self.held_cells -= cells;
        true
    }

    /// Brings the stored value at `id` back into memory, if it is on disk only.
    fn fetch(&mut self, id: u32) {
        let Some(copy) = self.spilled.get_mut(&id) else { return };
        if copy.here {
            return;
        }
        let started = std::time::Instant::now();
        let value = crate::spill::read(&copy.path).unwrap_or_else(|error| panic!("a stored value's copy on disk, {}, cannot be read: {error}", copy.path.display()));
        self.spill_cost.read_nanos += started.elapsed().as_nanos() as u64;
        self.spill_cost.read.0 += 1;
        self.spill_cost.read.1 += copy.cells as u64;
        copy.here = true;
        self.held_cells += copy.cells;
        self.values[id as usize] = value;
        if crate::bounds::enabled() {
            crate::bounds::tally("spill", "values read back".to_string(), 1);
            crate::bounds::tally("spill", "cells read back".to_string(), copy.cells as u64);
        }
    }

    /// Brings back every stored value that a list of ids holds and that is on disk only.
    fn fetch_all(&mut self, list: &[u32]) {
        if self.spilled.is_empty() {
            return;
        }
        for id in list {
            if *id > 1 {
                self.fetch(*id);
            }
        }
    }

    /// Where the walk holds more than [`resident_cells`] cells of stored values that can move, moves to disk the values that the lists of `ids` hold and that the terms after `at` read last. `readers` has the terms that read each term, in order. The values of the leaves stay, since the caller holds them. A value is the same when it comes back, so no value of the walk changes. Run it after [`Walker::compact`], which leaves in `values` what the lists hold alone.
    fn spill(&mut self, ids: &[Vec<u32>], readers: &[Vec<usize>], at: usize) {
        let limit = resident_cells();
        if self.held_cells <= limit {
            return;
        }
        let first_term = self.family.first_term.min(ids.len());
        let mut leaf_ids: LookupSet<u32> = LookupSet::new();
        for list in &ids[..first_term] {
            for id in list {
                leaf_ids.insert(*id);
            }
        }
        // For each stored value, the first term after `at` that reads a list that holds it.
        let mut next_read: FastMap<u32, usize> = FastMap::default();
        for (term, list) in ids.iter().enumerate().skip(first_term) {
            if list.is_empty() {
                continue;
            }
            let read = readers[term].iter().copied().find(|read| *read > at).unwrap_or(usize::MAX);
            for id in list {
                if *id > 1 && !leaf_ids.contains(id) {
                    let entry = next_read.entry(*id).or_insert(usize::MAX);
                    *entry = (*entry).min(read);
                }
            }
        }
        let mut candidates: Vec<(usize, usize, u32)> = next_read
            .sorted_map(|id, read| {
                let value = &self.values[*id as usize];
                let cells = held_of(value);
                (matches!(value, Val::Rows(_)) && cells >= crate::spill::MIN_CELLS).then_some((*read, cells, *id))
            })
            .into_iter()
            .flatten()
            .collect();
        // The value read last goes first, and of those the larger. The limit holds of the values that can move: what stays in memory whatever the walk does (small values, joined values) does not count against it, so that the values the next terms read can stay.
        candidates.sort_unstable_by(|a, b| b.cmp(a));
        let mut movable: usize = candidates.iter().map(|(_, cells, _)| *cells).sum();
        let mut moved = false;
        for (_, cells, id) in candidates {
            if movable <= limit {
                break;
            }
            if self.move_to_disk(id) {
                moved = true;
                movable -= cells;
            }
        }
        if crate::bounds::enabled() {
            crate::bounds::tally_max("spill", "cells of stored values that stay in memory", (self.held_cells - movable.min(self.held_cells)) as u64);
            crate::bounds::tally_max("spill", "cells of movable stored values kept", movable as u64);
        }
        if moved {
            // The tables those values held are gone.
            clear_views();
        }
    }

    /// The sizes of what the walker and its evaluator hold, for a check of the memory of a walk.
    fn footprint(&self) {
        use crate::bounds::tally_max;
        let cost = &self.spill_cost;
        tally_max("spill", "values written, running total", cost.written.0);
        tally_max("spill", "cells written, running total", cost.written.1);
        tally_max("spill", "values read back, running total", cost.read.0);
        tally_max("spill", "cells read back, running total", cost.read.1);
        tally_max("spill", "ms writing, running total", cost.write_nanos / 1_000_000);
        tally_max("spill", "ms reading back, running total", cost.read_nanos / 1_000_000);
        tally_max("spill", "ms in compactions and moves, writing included, running total", cost.compact_nanos / 1_000_000);
        let (histogram_cells, histograms) = self.eval.histograms_held();
        tally_max("held", "cells of stored values", self.held_cells as u64);
        tally_max("held", "cells of stored joined values", self.values.iter().map(|value| if let Val::Joined(joined) = value { joined.held_cells() } else { 0 }).sum::<usize>() as u64);
        tally_max("held", "cells of stored values on disk", self.spilled.sum_of(|_, copy| if copy.here { 0 } else { copy.cells }) as u64);
        tally_max("held", "cells of written rows held by lazy values", crate::native::lazy_written_cells() as u64);
        tally_max("held", "cells of histograms", histogram_cells as u64);
        tally_max("held", "histograms", histograms as u64);
        tally_max("held", "keys of second relations", crate::gen_parts::keys_held() as u64);
        tally_max("held", "cells of groupings", crate::gen_parts::groups_held() as u64);
        tally_max("held", "stored values", self.values.len() as u64);
        tally_max("held", "memo entries", (self.memo.len() + self.counts.len() + self.groupings.len() + self.group_counts.len()) as u64);
    }

    fn value_id(&mut self, value: Val) -> u32 {
        match value {
            Val::None => 0,
            Val::Empty => 1,
            Val::Rows(_) | Val::Boxes(_) | Val::Joined(_) => {
                let hash = value.hash();
                if let Some(found) = self.value_index.get(&hash).copied() {
                    // The value stored under the hash may be on disk only: it is the value that stands.
                    if !self.spilled.is_empty() {
                        self.fetch(found);
                    }
                    return found;
                }
                let at = self.values.len() as u32;
                self.held_cells += held_of(&value);
                if let (Val::Joined(joined), true) = (&value, crate::bounds::enabled()) {
                    crate::bounds::tally("stored", "joined values".to_string(), 1);
                    crate::bounds::tally("stored", "cells of joined values, held".to_string(), joined.held_cells() as u64);
                }
                self.values.push(value);
                self.value_index.insert(hash, at);
                at
            }
        }
    }

    /// The id of the value at `id` with the rows of `inside` or of a `join` written out, unless `step` takes what it needs from the relations they come from, as its first relation or, where `first` is false, its second.
    fn written_id(&mut self, step: &Step, id: u32, first: bool) -> u32 {
        let held = &self.values[id as usize];
        if !held.is_lazy() || held.lazy_reads(step, first) {
            return id;
        }
        if let Some(&written) = self.written_of.get(&id) {
            return written;
        }
        let value = self.values[id as usize].written();
        let written = self.value_id(value);
        self.written_of.insert(id, written);
        written
    }

    /// The cells of the value at `id` as a set: its rows times the `arity` of the term that gives it, whether the rows stand written or as the relations they come from. A relation with no value has none.
    fn charge_of(&self, id: u32, arity: usize) -> usize {
        set_cells(rows_of(&self.values[id as usize]), arity)
    }

    /// Whether the value at `id` alone passes the budget of a term, so that no term reads it.
    fn cut_by_cap(&self, id: u32, arity: usize) -> bool {
        self.charge_of(id, arity) > walk_cells()
    }

    /// Whether the value at `id` gives a term no value as a relation it reads: no value, or cells that pass the budget of a term.
    fn has_no_value(&self, id: u32, arity: usize) -> bool {
        matches!(self.values[id as usize], Val::None) || self.cut_by_cap(id, arity)
    }

    /// The count of rows that an idle term gives at one instance, as the evaluation gives it: no value where the first relation has none, or the second has none. Any other idle term has no rows. A relation is given as its id and the arity of the term that gives it.
    fn idle_rows(&self, first: (u32, usize), second: Option<(u32, usize)>) -> u32 {
        if self.has_no_value(first.0, first.1) || second.is_some_and(|(id, arity)| self.has_no_value(id, arity)) {
            NO_COUNT
        } else {
            0
        }
    }

    /// The `join` or `select` of the rows of a `join` that `step` makes, kept as the tables it joins, where its form allows that.
    fn lazy_extension(&self, step: &Step, a: u32, b: u32) -> Option<Val> {
        if !crate::joined::Joined::extends(step) {
            return None;
        }
        let first = &self.values[a as usize];
        let second = (b != NO_TERM).then(|| &self.values[b as usize]);
        if !matches!(first, Val::Joined(_)) && !second.is_some_and(|second| matches!(second, Val::Joined(_))) {
            return None;
        }
        crate::joined::extend(step, first, second)
    }

    fn apply(&mut self, step: &Step, a: u32, b: u32) -> Val {
        crate::bounds::begin();
        if let Some(value) = self.lazy_extension(step, a, b) {
            crate::bounds::end(a == 0 || (b != NO_TERM && b == 0));
            return value;
        }
        let a = self.written_id(step, a, true);
        let b = if b == NO_TERM { b } else { self.written_id(step, b, false) };
        let first = self.values[a as usize].clone();
        let value = if b == NO_TERM {
            self.eval.apply(step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.apply(step, &[&first, &second])
        };
        crate::bounds::end(a == 0 || (b != NO_TERM && b == 0));
        value
    }

    /// A term's count of rows and, for a number root, its number, with what can be left unbuilt left so.
    fn count_only(&mut self, step: &Step, at: usize, id: u32, b: u32, number: bool, steps: &StepIds) -> (u32, u32) {
        if let Some(found) = self.memo.get(&(steps.ids[at], id, b)).copied() {
            crate::bounds::recall((0, steps.ids[at], id, 0, b));
            let value = &self.values[found as usize];
            return (count_of(value), if number { number_word(value) } else { 0 });
        }
        // A part that reads cells of `inside` runs on the rows written out, once per grouping. Rows of `inside` that the part takes as boxes group as the relation's rows do, where its keys are the relation's.
        let written = if steps.grouped[at].is_some() { self.written_id(step, id, true) } else { id };
        if let Some((part, keys)) = steps.grouped[at] {
            let table = match &self.values[written as usize] {
                Val::Rows(parts) => match parts.as_slice() {
                    [one] if one.columns.iter().enumerate().all(|(place, column)| usize::from(*column) == place) => Some(one.table.clone()),
                    _ => None,
                },
                Val::Boxes(boxes) => steps.keys[keys as usize].iter().all(|key| *key < boxes.width()).then(|| boxes.support()),
                _ => None,
            };
            // Keys that group the rows alike give one count, so a part runs once per grouping.
            if let Some(table) = table {
                let (grouping, groups) = *self.groupings.entry((written, keys)).or_insert_with(|| crate::gen_parts::grouping_signature(&table, &steps.keys[keys as usize]));
                if part == PROJECT {
                    return (groups, 0);
                }
                let key = (part, written, grouping, b);
                if let Some(found) = self.group_counts.get(&key).copied() {
                    crate::bounds::recall((2, key.0, key.1, key.2, key.3));
                    return (found, 0);
                }
                let bounds_before = crate::bounds::enter();
                let found = count_of(&self.apply(step, written, b));
                crate::bounds::leave((2, key.0, key.1, key.2, key.3), bounds_before);
                if !crate::native::passed_output_limit_pending() {
                    self.group_counts.insert(key, found);
                }
                return (found, 0);
            }
        }
        // The count of distinct tuples of a `join`'s rows is read from its sides, with no tuples written.
        if !number {
            let joined = match &self.values[id as usize] {
                Val::Joined(joined) => Some(joined.clone()),
                _ => None,
            };
            if let Some(joined) = joined {
                crate::bounds::begin();
                if let Some(found) = joined.count_of(step) {
                    crate::bounds::end(false);
                    return (found.map_or(NO_COUNT, |count| count.min(u64::from(NO_COUNT - 1)) as u32), 0);
                }
            }
        }
        // The count of a `join` or an `antijoin` is read from its sides' histograms, with no rows written. Their sides are written where they stand as the rows of `inside` or of a `join`.
        if !number && matches!(step, Step::Join { .. } | Step::Antijoin { .. }) {
            crate::bounds::begin();
            if let Some(value) = self.lazy_extension(step, id, b) {
                crate::bounds::end(id == 0 || b == 0);
                return (count_of(&value), 0);
            }
            let first_id = self.written_id(step, id, true);
            let second_id = self.written_id(step, b, false);
            let first = self.values[first_id as usize].clone();
            let second = self.values[second_id as usize].clone();
            if let Some(found) = self.eval.count(step, &[&first, &second]) {
                crate::bounds::end(id == 0 || b == 0);
                return (found.map_or(NO_COUNT, |count| count.min(u64::from(NO_COUNT - 1)) as u32), 0);
            }
        }
        let value = self.apply(step, id, b);
        (count_of(&value), if number { number_word(&value) } else { 0 })
    }

    /// Each root's numbers at each instance of `leaves`. The first `train` instances have an
    /// output: a root that reads the output has a value at those alone, and any other root at
    /// every instance. With `only_output`, only the roots that read the output enter.
    pub fn walk(&mut self, leaves: &[Vec<Val>], train: usize, only_output: bool) -> RootTable {
        self.walk_of(leaves, train, only_output, None)
    }

    /// [`Walker::walk`] over the terms that `mask` marks, which are those whose roots the mask's list holds and every term they read. Only the listed roots enter the table, and they hold what a full walk gives them, unless a walk's bound stops a term: this walk adds up the cells of the terms it walks alone.
    pub fn walk_shapes(&mut self, leaves: &[Vec<Val>], train: usize, only_output: bool, mask: &ShapeMask) -> RootTable {
        assert_eq!(mask.needed.len(), self.family.terms.len(), "a mask is made for the family it walks");
        self.walk_of(leaves, train, only_output, Some(mask))
    }

    fn walk_of(&mut self, leaves: &[Vec<Val>], train: usize, only_output: bool, mask: Option<&ShapeMask>) -> RootTable {
        self.keep_within_budget();
        self.over_budget = false;
        crate::native::set_output_limit(walk_cells());
        crate::native::take_passed_output_limit();
        let family = self.family;
        let steps = family.step_ids();
        let instances = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut table = RootTable { stride: instances, ..RootTable::default() };
        let mut left_out = false;
        // The last term that reads each term, among those the walk walks: its values are dropped after that, where they are the only users of stored values.
        let mut last_read: Vec<Option<usize>> = vec![None; family.terms.len()];
        // The terms that read each term, among those the walk walks, in order.
        let mut readers: Vec<Vec<usize>> = vec![Vec::new(); family.terms.len()];
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            if mask.is_none_or(|mask| mask.needed[at]) {
                last_read[term.a as usize] = Some(at);
                readers[term.a as usize].push(at);
                if term.b != NO_TERM {
                    last_read[term.b as usize] = Some(at);
                    if term.b != term.a {
                        readers[term.b as usize].push(at);
                    }
                }
            }
        }
        let mut release: Vec<Vec<usize>> = vec![Vec::new(); family.terms.len()];
        for (read, last) in last_read.iter().enumerate() {
            release[last.unwrap_or(read)].push(read);
        }
        // The cells held after the last compaction: the next one waits until the walk holds twice as many. The rows that the lazy values of the walk have written count with the held cells.
        let mut floor = 0usize;
        let lazy_base = crate::native::lazy_written_cells();
        // Per term, whether the walk's stop left it unevaluated, or it reads a term so left. Such a term has no value, and so has each root over it.
        let mut stopped: Vec<bool> = vec![false; leaves.len()];
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            // A term that no listed root reads stands as an empty value, which no term that is walked reads.
            let listed = match mask {
                Some(mask) if !mask.needed[at] => {
                    ids.push(Vec::new());
                    stopped.push(false);
                    continue;
                }
                Some(mask) => mask.listed[at],
                None => u8::MAX,
            };
            if let Some(head) = family.bound_heads.get(at) {
                crate::bounds::set_head(*head);
            }
            // A term's charge is its own: the cells of each input it reads and of each output it gives, at each instance, each as rows times columns. It depends on the term's inputs and outputs alone, so that its value or stop does not depend on the terms walked before it, or on how an operator computes it.
            let mut spent = 0usize;
            let step_id = steps.ids[at];
            crate::bounds::clear_term();
            let first = std::mem::take(&mut ids[term.a as usize]);
            let second = if term.b == NO_TERM { Vec::new() } else if term.b == term.a { first.clone() } else { std::mem::take(&mut ids[term.b as usize]) };
            // A value that the walk moved to disk comes back before the term reads it.
            self.fetch_all(&first);
            self.fetch_all(&second);
            let step = term.step.as_ref().expect("a term has a step");
            let reads_output = term.flags & READS_OUTPUT != 0;
            let scope = if reads_output { train.min(instances) } else { instances };
            let wanted = (term.flags & READS_TABLE != 0 || family.over_grids) && (reads_output || !only_output);
            let extended = term.used;
            let (arity_a, arity_b, columns) = (family.terms[term.a as usize].columns.len(), if term.b == NO_TERM { 0 } else { family.terms[term.b as usize].columns.len() }, term.columns.len());
            let mut own = Vec::new();
            let on_no_rows = matches!(step, Step::Part(part) if part.gives_rows_on_no_rows());
            // A term whose first relation is empty, or whose second relation of a `join` or a `semijoin` is, has no rows. One whose first relation has no value, or has more cells than a term's budget, has no value.
            let first_empty = !on_no_rows && first[..scope].iter().all(|id| *id == 1);
            let first_cut = first[..scope].iter().all(|id| self.has_no_value(*id, arity_a));
            let second_empty = matches!(step, Step::Join { .. } | Step::Semijoin { .. }) && second[..scope].iter().all(|id| *id == 1);
            let idle = first_empty || first_cut || second_empty;
            // A first relation with more cells than a term's budget, at an instance, leaves the term with no value there: a stop, which spreads to the terms that read it.
            let cut_by_bound = first_cut && first[..scope].iter().any(|id| self.cut_by_cap(*id, arity_a));
            // A term whose first relation has more cells than a term's budget has no value, and no evaluation counts it.
            if idle && scope > 0 && crate::bounds::enabled() {
                for id in &first[..scope] {
                    if self.cut_by_cap(*id, arity_a) {
                        crate::bounds::mark_term(crate::bounds::Bound::Walk);
                    }
                }
            }
            let inherited = stopped[term.a as usize] || (term.b != NO_TERM && stopped[term.b as usize]);
            let mut past_bound = false;
            if extended {
                own.reserve(instances);
                for pair in 0..scope {
                    let b = if term.b == NO_TERM { NO_TERM } else { second[pair] };
                    let key = (step_id, first[pair], b);
                    // The inputs are charged before the evaluation: a term whose inputs pass the budget is not evaluated, and what it gives has no value, so a walk's memory stays bounded.
                    spent = spent.saturating_add(self.charge_of(first[pair], arity_a)).saturating_add(if b == NO_TERM { 0 } else { self.charge_of(b, arity_b) });
                    if spent > walk_cells() {
                        past_bound = true;
                        self.over_budget = true;
                        crate::bounds::skipped(crate::bounds::Bound::Walk, (scope - pair) as u64);
                        break;
                    }
                    crate::native::take_passed_output_limit();
                    let id = match self.memo.get(&key).copied() {
                        Some(found) => {
                            crate::bounds::recall((0, key.0, key.1, 0, key.2));
                            found
                        }
                        None => {
                            let bounds_before = crate::bounds::enter();
                            let value = self.apply(step, first[pair], b);
                            crate::bounds::leave((0, key.0, key.1, 0, key.2), bounds_before);
                            let id = self.value_id(value);
                            if !crate::native::passed_output_limit_pending() {
                                self.memo.insert(key, id);
                            }
                            id
                        }
                    };
                    // The output is charged as it stands, written or as the relations it comes from. An operator that stopped at the budget wrote no output, and the term is over it.
                    spent = spent.saturating_add(set_cells(rows_of(&self.values[id as usize]), columns));
                    if crate::native::take_passed_output_limit() || spent > walk_cells() {
                        past_bound = true;
                        self.over_budget = true;
                        crate::bounds::skipped(crate::bounds::Bound::Walk, (scope - pair) as u64);
                        break;
                    }
                    own.push(id);
                }
                if past_bound {
                    own.clear();
                }
                own.resize(instances, 0);
            }
            let mut is_stopped = past_bound || cut_by_bound || inherited;
            let mut cut_off = false;
            if wanted && is_stopped && listed != 0 {
                // A root over a stopped term has no value at any instance, which is not its default.
                let counted = cut_by_bound && !(past_bound || inherited);
                for (place, (hash, of)) in term.roots.iter().enumerate() {
                    if listed & (1 << place) != 0 {
                        if counted {
                            crate::bounds::tally("stopped: first cut by cap", format!("{of:?}"), scope as u64);
                        }
                        let base = table.slots_of(*hash, term.flags, term.size, *of);
                        table.slots[base..base + scope].iter_mut().for_each(|slot| slot.state = SLOT_NO_VALUE);
                    }
                }
            } else if wanted && listed != 0 && !term.roots.is_empty() {
                for (place, (hash, _)) in term.roots.iter().enumerate() {
                    if listed & (1 << place) != 0 {
                        let held = table.bindings.entry(*hash).or_insert((0, 0));
                        if reads_output {
                            held.1 += 1;
                        } else {
                            held.0 += 1;
                        }
                    }
                }
                for pair in 0..scope {
                    let (id, b) = (first[pair], if term.b == NO_TERM { NO_TERM } else { second[pair] });
                    // A term that no result is kept for is charged as an extended one is: its inputs before its count, and its count as the rows of its output.
                    if !extended && !idle {
                        spent = spent.saturating_add(self.charge_of(id, arity_a)).saturating_add(if b == NO_TERM { 0 } else { self.charge_of(b, arity_b) });
                        if spent > walk_cells() {
                            cut_off = true;
                            self.over_budget = true;
                            crate::bounds::skipped(crate::bounds::Bound::Walk, (scope - pair) as u64);
                            break;
                        }
                        crate::native::take_passed_output_limit();
                    }
                    // An idle term gives what the evaluation gives, with no evaluation.
                    let (rows, number) = if idle {
                        (self.idle_rows((id, arity_a), if term.b == NO_TERM { None } else { Some((b, arity_b)) }), 0)
                    } else if extended {
                        let value = &self.values[own[pair] as usize];
                        (count_of(value), if term.root == RootKind::Number { number_word(value) } else { 0 })
                    } else {
                        let key = (step_id, id, b);
                        let counted = match self.counts.get(&key).copied() {
                            Some(found) => {
                                crate::bounds::recall((1, key.0, key.1, 0, key.2));
                                found
                            }
                            None => {
                                let bounds_before = crate::bounds::enter();
                                let found = self.count_only(step, at, id, b, term.root == RootKind::Number, steps);
                                crate::bounds::leave((1, key.0, key.1, 0, key.2), bounds_before);
                                if !crate::native::passed_output_limit_pending() {
                                    self.counts.insert(key, found);
                                }
                                found
                            }
                        };
                        spent = spent.saturating_add(set_cells((counted.0 != NO_COUNT).then_some(u64::from(counted.0)), columns));
                        if crate::native::take_passed_output_limit() || spent > walk_cells() {
                            cut_off = true;
                            self.over_budget = true;
                            crate::bounds::skipped(crate::bounds::Bound::Walk, (scope - pair) as u64);
                            break;
                        }
                        counted
                    };
                    let left = count_of(&self.values[id as usize]);
                    let other = if term.b == NO_TERM { NO_COUNT } else { count_of(&self.values[b as usize]) };
                    for (place, (hash, of)) in term.roots.iter().enumerate() {
                        if listed & (1 << place) == 0 {
                            continue;
                        }
                        let value = root_value(*of, rows, left, if *of == RootOf::OverExamples { self.examples } else { other }, number);
                        // Nothing to add at a default value, which is a slot's own state.
                        if matches!(value, RootNumber::Value(_, 0)) {
                            continue;
                        }
                        if crate::bounds::enabled() {
                            let cause = match value {
                                RootNumber::Undefined if idle => Some("left out: idle term"),
                                RootNumber::Undefined => Some("left out: full path"),
                                RootNumber::Unknown if idle && first_cut => Some("no value: idle, first has no value"),
                                RootNumber::Unknown if idle => Some("no value: idle, second has no value"),
                                _ => None,
                            };
                            if let Some(cause) = cause {
                                crate::bounds::tally(cause, format!("{of:?}"), 1);
                            }
                        }
                        let base = table.slots_of(*hash, term.flags, term.size, *of);
                        let slot = &mut table.slots[base + pair];
                        match value {
                            RootNumber::Unknown => slot.state = SLOT_NO_VALUE,
                            RootNumber::Undefined => {
                                slot.undefined += 1;
                                left_out = true;
                            }
                            RootNumber::Value(held, word) => {
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
            if cut_off {
                // The term passed its budget: it has no value at any instance, and so has each root over it.
                is_stopped = true;
                for (place, (hash, of)) in term.roots.iter().enumerate() {
                    if listed & (1 << place) != 0 {
                        let base = table.slots_of(*hash, term.flags, term.size, *of);
                        table.slots[base..base + scope].iter_mut().for_each(|slot| slot.state = SLOT_NO_VALUE);
                    }
                }
            }
            crate::bounds::note_term(at as u32);
            crate::bounds::note_cells(at as u32, spent as u64);
            if crate::bounds::enabled() && spent > 5_000_000 {
                eprintln!("term\t{}\textended {extended}\tcharged {spent}\tstopped {is_stopped}\theld {}", term.text.chars().take(160).collect::<String>(), self.held_cells);
            }
            ids[term.a as usize] = first;
            if term.b != NO_TERM {
                ids[term.b as usize] = second;
            }
            ids.push(own);
            stopped.push(is_stopped);
            for read in &release[at] {
                ids[*read] = Vec::new();
            }
            let entries = self.memo.len() + self.counts.len() + self.groupings.len() + self.group_counts.len();
            if crate::bounds::enabled() && at % 32 == 0 {
                self.footprint();
            }
            let lazy = crate::native::lazy_written_cells().saturating_sub(lazy_base);
            // The walk compacts once it holds as many cells again as it held after the last compaction, and at most half the limit of movable values more, so that the sawtooth of its memory stays within that.
            if self.held_cells + lazy > self.budget.0.max(floor + floor.min(resident_cells() / 2)) || entries > self.budget.1 {
                let started = std::time::Instant::now();
                self.compact(&mut ids);
                self.spill(&ids, &readers, at);
                self.spill_cost.compact_nanos += started.elapsed().as_nanos() as u64;
                if crate::bounds::enabled() {
                    self.footprint();
                }
                floor = self.held_cells + crate::native::lazy_written_cells().saturating_sub(lazy_base);
            }
        }
        // A root that every one of its bindings leaves out at an instance has no value there.
        let out_scope = train.min(instances);
        let RootTable { hashes, slots, bindings, stride, meta, .. } = &mut table;
        // Each root is settled on its own places and tallies, so the order of the roots changes nothing.
        for (at, hash) in hashes.iter().enumerate().filter(|_| left_out) {
            let (full, out) = bindings.get(hash).copied().unwrap_or((0, 0));
            for (pair, slot) in slots[at * *stride..at * *stride + instances].iter_mut().enumerate() {
                if slot.undefined > 0 && slot.state == SLOT_DEFAULT && slot.undefined == full + if pair < out_scope { out } else { 0 } {
                    slot.state = SLOT_NO_VALUE;
                    if crate::bounds::enabled() {
                        crate::bounds::tally("no value: every binding left out", format!("{:?}", meta[at].2), 1);
                    }
                }
            }
        }
        crate::native::set_output_limit(crate::native::CELL_CAP);
        // A task keeps a walker per schema, so one large walk leaves nothing behind.
        self.keep_within_budget_with(crate::native::lazy_written_cells().saturating_sub(lazy_base));
        crate::bounds::flush();
        table
    }

    /// The count of rows at each instance of each term whose text holds `pattern`, leaves
    /// included, for a check against the expression that a term stands for.
    pub fn term_counts(&mut self, leaves: &[Vec<Val>], train: usize, pattern: &str) -> Vec<(String, Vec<Option<u64>>)> {
        // These checks stop at no budget; they pass an evaluation's account that nothing reads.
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
    /// The terms that `list` needs, for [`Walker::walk_shapes`] over this family.
    pub fn shape_mask(&self, list: &ShapeList) -> ShapeMask {
        let count = self.terms.len();
        let mut needed = vec![false; count];
        let mut listed = vec![0u8; count];
        for (at, term) in self.terms.iter().enumerate().skip(self.first_term) {
            assert!(term.roots.len() <= 8, "a term has up to 8 roots");
            for (place, (hash, _)) in term.roots.iter().enumerate() {
                if list.contains(*hash as u64) {
                    listed[at] |= 1 << place;
                }
            }
            needed[at] = listed[at] != 0;
        }
        // A term reads terms before it, so one pass from the last term to the first marks all that a term reads.
        for at in (self.first_term..count).rev() {
            if !needed[at] {
                continue;
            }
            let term = &self.terms[at];
            for read in [term.a, term.b] {
                if read != NO_TERM {
                    needed[read as usize] = true;
                }
            }
        }
        ShapeMask { needed, listed }
    }

    fn step_ids(&self) -> &StepIds {
        self.step_ids.get_or_init(|| {
            let mut steps: FastMap<u128, u32> = FastMap::default();
            let mut rests: FastMap<u128, u32> = FastMap::default();
            let mut keys: FastMap<u128, u32> = FastMap::default();
            let mut out = StepIds::default();
            for term in &self.terms {
                let Some(step) = term.step.as_ref() else {
                    out.ids.push(0);
                    out.grouped.push(None);
                    continue;
                };
                let number = term.root == RootKind::Number;
                let text = format!("{step:?}");
                let next = steps.len() as u32;
                out.ids.push(*steps.entry(hash_words(text.bytes().map(u64::from).chain([u64::from(number)]))).or_insert(next));
                let grouping = match step {
                    _ if number || term.used => None,
                    Step::Project { columns } => Some((PROJECT, &columns[..])),
                    Step::Part(part) => part.grouping_keys().map(|held| (0, held)),
                    _ => None,
                };
                out.grouped.push(grouping.map(|(kind, held)| {
                    let next = keys.len() as u32;
                    let keys_id = *keys.entry(hash_words(held.iter().map(|column| u64::from(*column)))).or_insert_with(|| {
                        out.keys.push(held.to_vec().into_boxed_slice());
                        next
                    });
                    if kind == PROJECT {
                        return (PROJECT, keys_id);
                    }
                    // The step's text with its keys left out.
                    let start = text.find("keys: [").expect("a part with keys");
                    let end = start + text[start..].find(']').expect("the end of the keys");
                    let rest = format!("{}{}", &text[..start], &text[end + 1..]);
                    let next = rests.len() as u32;
                    (*rests.entry(hash_words(rest.bytes().map(u64::from))).or_insert(next), keys_id)
                }));
            }
            out
        })
    }

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
    /// The roots of a term, by their ids, and the terms it reads.
    pub fn term_links(&self, at: usize) -> (Vec<u128>, u32, u32) {
        let term = &self.terms[at];
        (term.roots.iter().map(|root| root.0).collect(), term.a, term.b)
    }

    /// The value that stands for no term in [`Generated::term_links`].
    pub fn no_term() -> u32 {
        NO_TERM
    }

    /// A term's shape, with the table and its columns as holes, where the family keeps the terms' text.
    pub fn term_shape(&self, at: usize, types: &[ValueType]) -> Option<String> {
        let text = &self.terms.get(at)?.text;
        (!text.is_empty()).then(|| shape_text(text, "T", types))
    }

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
    /// Each term's time in nanoseconds, its evaluations, and how many gave rows, for a study of where a walk's time goes. Where `needed` is given, only those terms run.
    pub fn timed_terms(&mut self, leaves: &[Vec<Val>], train: usize, needed: Option<&[bool]>) -> Vec<(u64, u32, u32)> {
        let family = self.family;
        let pairs = leaves[0].len();
        let mut ids: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        for leaf in leaves {
            let held: Vec<u32> = leaf.iter().map(|value| self.value_id(value.clone())).collect();
            ids.push(held);
        }
        let mut out = vec![(0, 0, 0); family.terms.len()];
        for (at, term) in family.terms.iter().enumerate().skip(family.first_term) {
            let step = term.step.as_ref().expect("a term has a step");
            let scope = if term.flags & READS_OUTPUT != 0 { train } else { pairs };
            let mut own = Vec::with_capacity(pairs);
            let run = needed.map_or(term.used || !term.roots.is_empty(), |needed| needed[at]);
            for pair in 0..scope {
                let id = if run {
                    let a = ids[term.a as usize][pair];
                    let b = if term.b == NO_TERM { NO_TERM } else { ids[term.b as usize][pair] };
                    let begun = std::time::Instant::now();
                    let value = self.apply(step, a, b);
                    let id = self.value_id(value);
                    let own_time = &mut out[at];
                    own_time.0 += begun.elapsed().as_nanos() as u64;
                    own_time.1 += 1;
                    own_time.2 += u32::from(count_of(&self.values[id as usize]) > 0);
                    id
                } else {
                    0
                };
                own.push(id);
            }
            own.resize(pairs, 0);
            ids.push(own);
        }
        out
    }

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
                out.push((at, held.iter().map(|id| self.values[*id as usize].written()).collect()));
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
                out.push((at, own.iter().map(|id| self.values[*id as usize].written()).collect()));
            }
            ids.push(own);
        }
        out
    }
}

/// The word of a relation's one number, where it has one row.
fn number_word(value: &Val) -> u32 {
    // The rows of `inside` have three columns at least, and a number stands in a relation of one column.
    if value.is_lazy() {
        return 0;
    }
    let Some(table) = flat(value) else { return 0 };
    if table.len == 1 && table.arity == 1 {
        // 0 stands for no number. A number from 0 up stands one above itself, and one below 0 in two's complement, which is the word's top half.
        let number = number_of(table.cells[0]);
        if number >= 0 {
            (number + 1).min(i64::from(i32::MAX)) as u32
        } else {
            number.max(i64::from(i32::MIN)) as i32 as u32
        }
    } else {
        0
    }
}

/// The number that a word of [`number_word`] stands for, where it stands for one.
fn number_of_word(word: u32) -> i64 {
    if word > i32::MAX as u32 {
        i64::from(word as i32)
    } else {
        i64::from(word) - 1
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
    file: Option<Mutex<(LookupSet<u64>, Box<dyn std::io::Write + Send>)>>,
}

pub enum NameWriter<'a> {
    Map(std::sync::MutexGuard<'a, FastMap<u128, String>>),
    File(std::sync::MutexGuard<'a, (LookupSet<u64>, Box<dyn std::io::Write + Send>)>),
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
        Ok(NameStore { names: Mutex::default(), file: Some(Mutex::new((LookupSet::new(), file))) })
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

    /// The name of each root of `wanted` that the store holds in memory, by the low 64 bits of its hash, which is how a vector names it.
    pub fn texts_of(&self, wanted: &LookupSet<u64>) -> LookupMap<u64, String> {
        let names = self.names.lock().expect("no panic");
        names.to_map_keeping_least(|hash, name| wanted.contains(&(*hash as u64)).then(|| (*hash as u64, name.clone())))
    }

    /// The name of each root that the store holds in memory, by the low 64 bits of its hash, which is how a vector names it.
    pub fn by_vector_hash(&self) -> LookupMap<u64, String> {
        let names = self.names.lock().expect("no panic");
        names.to_map_keeping_least(|hash, name| Some((*hash as u64, name.clone())))
    }

    /// Each root's name that the store holds in memory, in the order of the roots' hashes.
    pub fn all(&self) -> Vec<(u128, String)> {
        self.names.lock().expect("no panic").sorted_entries().into_iter().map(|(hash, name)| (*hash, name.clone())).collect()
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

/// A hash of this program's file. Saved families stand under it, so that a build reads only the families it wrote itself.
fn build_id() -> &'static str {
    static ID: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    ID.get_or_init(|| {
        // A run whose code builds the same families may name another build's folder of them.
        if let Ok(named) = std::env::var("GENERATE_FAMILIES_BUILD") {
            return named;
        }
        let program = std::env::current_exe().and_then(std::fs::read).expect("this program's file");
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        std::hash::Hash::hash(&program, &mut hasher);
        format!("{:016x}", std::hash::Hasher::finish(&hasher))
    })
}

/// The terms that the cache of families holds at most; past it, the oldest families leave.
const CACHED_TERMS: usize = 3_000_000;
const SAVED_CACHED_TERMS: usize = 400_000;

/// The families of each schema, kept in a bounded cache, and the name of each root.
#[derive(Default)]
pub struct Generators {
    held: Mutex<(FastMap<u128, (Arc<Generated>, u64)>, u64)>,
    pub names: NameStore,
    /// Where built families stand as files, so that a family the cache let go, or an earlier run built, is read and not built again. Its names stand
    /// in the names files of that folder's run, so it belongs to one run's root and one version of the code.
    pub saved: Option<std::path::PathBuf>,
    /// The terms that the cache holds at most, where it is not 0, in place of [`CACHED_TERMS`].
    pub term_limit: usize,
    /// Whether [`Generators::get`] gives [`Generated::one_group`].
    pub one_group: bool,
    /// The terms that the cache holds at most where families stand on file, where it is not 0, in place of [`SAVED_CACHED_TERMS`]. Threads share what the cache holds, and each holds its own copy of what it read after the cache let it go.
    pub saved_limit: usize,
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
        let family = Arc::new(self.read_saved(hash).unwrap_or_else(|| {
            let built = build();
            self.save(hash, &built);
            built
        }));
        // A family on file costs a read to get back, so memory holds fewer of them.
        let limit = if self.saved.is_some() { if self.saved_limit == 0 { SAVED_CACHED_TERMS } else { self.saved_limit } } else if self.term_limit == 0 { CACHED_TERMS } else { self.term_limit };
        let mut held = self.held.lock().expect("no panic");
        let (cache, clock) = &mut *held;
        *clock += 1;
        cache.insert(hash, (family.clone(), *clock));
        let mut total: usize = cache.sum_of(|_, found| found.0.terms.len());
        while total > limit && cache.len() > 1 {
            let Some(oldest) = cache.min_entry_by(|key, found| (*key == hash, found.1)).map(|(key, _)| *key) else { break };
            if let Some(gone) = cache.remove(&oldest) {
                total -= gone.0.terms.len();
            }
        }
        family
    }

    fn saved_path(&self, hash: u128) -> Option<std::path::PathBuf> {
        self.saved.as_ref().map(|folder| folder.join(build_id()).join(format!("{hash:032x}.json.zst")))
    }

    fn read_saved(&self, hash: u128) -> Option<Generated> {
        let packed = std::fs::read(self.saved_path(hash)?).ok()?;
        let held: SavedFamily = serde_json::from_slice(&zstd::stream::decode_all(&packed[..]).ok()?).ok()?;
        let mut family = Generated::empty();
        family.terms = held.terms.into_iter().map(|SavedTerm(step, a, b, flags, size, root, roots, used)| Term {
            step, a, b, columns: Vec::new(), flags, size, root,
            roots: roots.into_iter().map(|(low, high, of)| (u128::from(high) << 64 | u128::from(low), of)).collect(),
            text: String::new(), used, plan: None,
        }).collect();
        family.first_term = held.first_term;
        family.by_size = held.by_size;
        family.roots = held.roots;
        family.task_wide = held.task_wide;
        family.over_grids = held.over_grids;
        family.two_tables = held.two_tables;
        if crate::bounds::enabled() {
            // A family saved with no heads would count under none.
            if held.term_heads.len() != family.terms.len() {
                return None;
            }
            let heads: Vec<u32> = held.head_names.iter().map(|name| crate::bounds::head_of(name)).collect();
            family.bound_heads = held.term_heads.iter().map(|at| heads[*at as usize]).collect();
        }
        Some(family)
    }

    fn save(&self, hash: u128, family: &Generated) {
        let Some(path) = self.saved_path(hash) else { return };
        if family.keep_text {
            return;
        }
        // Its roots' names reach their file before the family that no later run would name them for.
        self.names.flush();
        let mut held = SavedFamily {
            terms: family.terms.iter().map(|term| SavedTerm(term.step.clone(), term.a, term.b, term.flags, term.size, term.root, term.roots.iter().map(|(hash, of)| (*hash as u64, (*hash >> 64) as u64, *of)).collect(), term.used)).collect(),
            first_term: family.first_term,
            by_size: family.by_size.clone(),
            roots: family.roots,
            task_wide: family.task_wide,
            over_grids: family.over_grids,
            two_tables: family.two_tables,
            head_names: Vec::new(),
            term_heads: Vec::new(),
        };
        let names_of: Vec<String> = family.bound_heads.iter().map(|head| crate::bounds::name_of(*head)).collect();
        held.head_names = names_of.iter().cloned().collect::<std::collections::BTreeSet<_>>().into_iter().collect();
        held.term_heads = names_of.iter().map(|name| held.head_names.binary_search(name).expect("a head's name") as u32).collect();
        let Ok(text) = serde_json::to_vec(&held) else { return };
        let Ok(packed) = zstd::stream::encode_all(&text[..], 3) else { return };
        if let Some(folder) = path.parent() {
            let _ = std::fs::create_dir_all(folder);
        }
        // Two threads can build one family, so each writes a file of its own and the rename decides.
        let mut temporary = path.as_os_str().to_os_string();
        temporary.push(format!(".{}.{:?}.tmp", std::process::id(), std::thread::current().id()));
        if std::fs::write(&temporary, packed).is_ok() {
            let _ = std::fs::rename(&temporary, &path);
        }
    }

    /// The task-wide family of a table's schema.
    pub fn get_task_wide(&self, stored: &crate::stored::Stored, d: usize) -> Arc<Generated> {
        let hash = hash_words(format!("task-wide {d} {}", stored.key).bytes().map(u64::from));
        self.family_of(hash, || Generated::task_wide(&stored.types, d, &self.names))
    }

    /// The family of two tables of a state.
    pub fn get_two_tables(&self, t: &crate::stored::Stored, u: &crate::stored::Stored) -> Arc<Generated> {
        let all: Vec<ValueType> = t.types.iter().chain(&u.types).cloned().collect();
        let hash = hash_words(format!("two {} {} {:?} {:?}", t.types.len(), crate::stored::schema_key(&all), t.keys, u.keys).bytes().map(u64::from));
        self.family_of(hash, || Generated::of_two_tables_keyed(&t.types, &t.keys, &u.types, &u.keys, &self.names))
    }

    /// The family of a pair's own numbers.
    pub fn get_grids(&self, d: usize) -> Arc<Generated> {
        let hash = hash_words(format!("grids {d}").bytes().map(u64::from));
        self.family_of(hash, || Generated::of_grids(d, &self.names))
    }

    pub fn get(&self, stored: &crate::stored::Stored, d: usize) -> Arc<Generated> {
        let hash = hash_words(format!("{} {:?}", stored.key, stored.keys).bytes().map(u64::from));
        self.family_of(hash, || if self.one_group { Generated::one_group_keyed(&stored.types, &stored.keys, d, &self.names) } else { Generated::of_keyed(&stored.types, &stored.keys, d, &self.names) })
    }
}

