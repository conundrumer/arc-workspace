//! Refinements: what a relation's type holds of its values beside its column types, as the
//! specification's section on entailed terms gives it. Each operator has an abstract transformer from
//! its inputs' refinements to its output's. An application that the refinements prove changes nothing,
//! gives no rows, or whose value follows from a smaller term has no derivation.
//!
//! A term's refinements are its derived postcondition: they come from column types, the lib's
//! declarations and fragments' bodies, and no rule reads a table's rows.

use crate::expression::Op;

/// A set of a relation's columns, by place.
pub type Mask = u64;

const MOST_KEYS: usize = 8;

pub fn bit(column: u16) -> Mask {
    1 << column
}

pub fn mask_of(columns: &[u16]) -> Mask {
    columns.iter().fold(0, |mask, column| mask | bit(*column))
}

/// The columns `columns` of a relation hold, as tuples, only what the columns `at` of the term `of` hold.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Within {
    pub columns: Box<[u16]>,
    pub of: u32,
    pub at: Box<[u16]>,
}

/// What a relation's type holds of its values.
#[derive(Clone, Debug, Default)]
pub struct Refined {
    /// Sets of columns at which it has at most one row per value. The empty set says at most one row.
    pub keys: Vec<Mask>,
    /// The least and the greatest value of each column, where known.
    pub low: Vec<Option<i32>>,
    pub high: Vec<Option<i32>>,
    pub within: Vec<Within>,
    /// As `within`, for tuples that hold nothing of what those columns hold.
    pub outside: Vec<Within>,
    /// The columns that hold every value of their orientation type.
    pub complete: Mask,
    /// Whether the count of its rows follows from a smaller term's.
    pub count_follows: bool,
}

/// What a term with no derivation is claimed to be, for the check of a rule against evaluation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Claim {
    /// It has no rows.
    Empty,
    /// Its rows are its first relation's, over its columns.
    SameRows,
    /// Its count of rows is its first relation's.
    SameCount,
    /// It is another term that the family holds.
    Other,
    /// Its value follows from its first relation's rows in a way that no comparison here states.
    Follows,
}

/// Why an application has no derivation: the rule that rejects it, and what the rule claims.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rejected {
    pub rule: &'static str,
    pub claim: Claim,
}

pub type Outcome = Result<Refined, Rejected>;

fn rejected(rule: &'static str, claim: Claim) -> Outcome {
    Err(Rejected { rule, claim })
}

impl Refined {
    pub fn with_arity(arity: usize) -> Refined {
        Refined { keys: Vec::new(), low: vec![None; arity], high: vec![None; arity], within: Vec::new(), outside: Vec::new(), complete: 0, count_follows: false }
    }

    pub fn arity(&self) -> usize {
        self.low.len()
    }

    pub fn all_columns(&self) -> Mask {
        if self.arity() >= Mask::BITS as usize { Mask::MAX } else { (1 << self.arity()) - 1 }
    }

    /// Whether `mask` holds a key.
    pub fn is_key(&self, mask: Mask) -> bool {
        self.keys.iter().any(|key| key & !mask == 0)
    }

    pub fn one_row(&self) -> bool {
        self.is_key(0)
    }

    pub fn add_key(&mut self, key: Mask) {
        if self.is_key(key) {
            return;
        }
        self.keys.retain(|held| held & !key != 0);
        if self.keys.len() < MOST_KEYS {
            self.keys.push(key);
        }
    }

    fn sorted_keys(mut self) -> Refined {
        self.keys.sort_unstable();
        self
    }
}

/// Whether the columns `columns` of `of_relation` stand within the columns `at` of the term `of`, by what
/// `of_relation` holds, or by what a term that it stands within holds.
pub fn is_within(terms: &[Refined], of_relation: &Refined, columns: &[u16], of: u32, at: &[u16], depth: u8) -> bool {
    for held in &of_relation.within {
        let mapped: Option<Vec<u16>> = columns.iter().map(|column| held.columns.iter().position(|own| own == column).map(|place| held.at[place])).collect();
        let Some(mapped) = mapped else { continue };
        if held.of == of && mapped.as_slice() == at {
            return true;
        }
        if depth > 0 && held.of != u32::MAX {
            if let Some(next) = terms.get(held.of as usize) {
                if is_within(terms, next, &mapped, of, at, depth - 1) {
                    return true;
                }
            }
        }
    }
    false
}

/// Whether the columns `columns` hold nothing of what the columns `at` of the term `of` hold.
pub fn is_outside(relation: &Refined, columns: &[u16], of: u32, at: &[u16]) -> bool {
    relation.outside.iter().any(|held| {
        // No match on a part of a tuple is no match on the tuple.
        held.of == of && held.columns.iter().zip(held.at.iter()).all(|(own, other)| columns.iter().zip(at).any(|(column, target)| column == own && target == other))
    })
}

/// `project`.
pub fn project(a: &Refined, columns: &[u16]) -> Outcome {
    let mask = mask_of(columns);
    if columns.len() < a.arity() && a.is_key(mask) {
        return rejected("project-keeps-key", Claim::SameCount);
    }
    let place = |column: u16| columns.iter().position(|own| *own == column).map(|at| at as u16);
    let mut out = Refined::with_arity(columns.len());
    for key in &a.keys {
        if key & !mask == 0 {
            out.keys.push((0..a.arity() as u16).filter(|column| key & bit(*column) != 0).filter_map(place).fold(0, |held, column| held | bit(column)));
        }
    }
    out.add_key(out.all_columns());
    for (at, column) in columns.iter().enumerate() {
        out.low[at] = a.low[usize::from(*column)];
        out.high[at] = a.high[usize::from(*column)];
        if a.complete & bit(*column) != 0 {
            out.complete |= bit(at as u16);
        }
    }
    for held in &a.within {
        let kept: Vec<(u16, u16)> = held.columns.iter().zip(held.at.iter()).filter_map(|(own, other)| place(*own).map(|own| (own, *other))).collect();
        if !kept.is_empty() {
            out.within.push(Within { columns: kept.iter().map(|pair| pair.0).collect(), of: held.of, at: kept.iter().map(|pair| pair.1).collect() });
        }
    }
    for held in &a.outside {
        let kept: Option<Vec<u16>> = held.columns.iter().map(|own| place(*own)).collect();
        if let Some(kept) = kept {
            out.outside.push(Within { columns: kept.into_boxed_slice(), of: held.of, at: held.at.clone() });
        }
    }
    out.count_follows = a.one_row();
    Ok(out.sorted_keys())
}

const LESS: u8 = 1;
const SAME: u8 = 2;
const MORE: u8 = 4;

fn op_outcomes(op: Op) -> u8 {
    match op {
        Op::Eq => SAME,
        Op::Ne => LESS | MORE,
        Op::Lt => LESS,
        Op::Le => LESS | SAME,
        Op::Gt => MORE,
        Op::Ge => SAME | MORE,
    }
}

/// The op among those that the same outcomes state that a family generates.
fn canonical_op(outcomes: u8, possible: u8) -> Option<Op> {
    Op::ALL.into_iter().find(|op| op_outcomes(*op) & possible == outcomes)
}

/// The op a family generates for the outcomes of `op` against `0`.
pub fn canonical_zero_op(a: &Refined, at: u16, op: Op) -> Option<Op> {
    let (low, high) = (a.low[usize::from(at)], a.high[usize::from(at)]);
    let mut possible = 0;
    if low.is_none_or(|low| low < 0) {
        possible |= LESS;
    }
    if low.is_none_or(|low| low <= 0) && high.is_none_or(|high| high >= 0) {
        possible |= SAME;
    }
    if high.is_none_or(|high| high > 0) {
        possible |= MORE;
    }
    canonical_op(op_outcomes(op) & possible, possible)
}

/// The refinements after a column is dropped: `dropped` leaves, as a place in the relation before.
fn without_column(a: &Refined, dropped: Option<u16>, same_as: Option<u16>) -> Refined {
    let Some(dropped) = dropped else { return a.clone() };
    let after = |column: u16| if column > dropped { column - 1 } else { column };
    let remap = |mask: Mask| -> Mask {
        let mut out = 0;
        for column in 0..a.arity() as u16 {
            if mask & bit(column) != 0 {
                if column == dropped {
                    if let Some(other) = same_as {
                        out |= bit(after(other));
                    }
                } else {
                    out |= bit(after(column));
                }
            }
        }
        out
    };
    let mut out = Refined::with_arity(a.arity() - 1);
    for key in &a.keys {
        out.add_key(remap(*key));
    }
    for column in 0..a.arity() as u16 {
        if column != dropped {
            out.low[usize::from(after(column))] = a.low[usize::from(column)];
            out.high[usize::from(after(column))] = a.high[usize::from(column)];
        }
    }
    let tuples = |held: &Within| -> Within {
        let kept: Vec<(u16, u16)> = held.columns.iter().zip(held.at.iter()).filter_map(|(own, other)| {
            if *own == dropped { same_as.map(|same| (after(same), *other)) } else { Some((after(*own), *other)) }
        }).collect();
        Within { columns: kept.iter().map(|pair| pair.0).collect(), of: held.of, at: kept.iter().map(|pair| pair.1).collect() }
    };
    out.within = a.within.iter().map(tuples).filter(|held| !held.columns.is_empty()).collect();
    out.outside = a.outside.iter().filter(|held| !held.columns.contains(&dropped)).map(tuples).collect();
    out
}

/// `select` of a column against `0`. `has_order` holds of a column whose values have the order of numbers.
pub fn select_zero(a: &Refined, at: u16, op: Op, drop: bool, has_order: bool) -> Outcome {
    let (low, high) = (a.low[usize::from(at)], a.high[usize::from(at)]);
    let mut possible = 0;
    if low.is_none_or(|low| low < 0) {
        possible |= LESS;
    }
    if low.is_none_or(|low| low <= 0) && high.is_none_or(|high| high >= 0) {
        possible |= SAME;
    }
    if high.is_none_or(|high| high > 0) {
        possible |= MORE;
    }
    let outcomes = op_outcomes(op) & possible;
    if outcomes == 0 {
        return rejected("select-zero-empty", Claim::Empty);
    }
    if outcomes == possible {
        return rejected("select-zero-no-op", Claim::SameRows);
    }
    if has_order && canonical_op(outcomes, possible) != Some(op) {
        return rejected("select-zero-same-op", Claim::Other);
    }
    let mut out = a.clone();
    out.complete = 0;
    let place = usize::from(at);
    match outcomes {
        LESS => out.high[place] = Some(high.map_or(-1, |high| high.min(-1))),
        SAME => {
            out.low[place] = Some(0);
            out.high[place] = Some(0);
        }
        MORE => out.low[place] = Some(low.map_or(1, |low| low.max(1))),
        _ if outcomes == LESS | SAME => out.high[place] = Some(high.map_or(0, |high| high.min(0))),
        _ if outcomes == SAME | MORE => out.low[place] = Some(low.map_or(0, |low| low.max(0))),
        _ => {}
    }
    out.count_follows = false;
    Ok(if drop { without_column(&out, Some(at), None).sorted_keys() } else { out.sorted_keys() })
}

/// `select` of a column against another.
pub fn select_pair(a: &Refined, at: u16, other: u16, op: Op, drop: Option<u16>) -> Outcome {
    let (one, two) = (usize::from(at), usize::from(other));
    let mut possible = LESS | SAME | MORE;
    if let (Some(low), Some(high)) = (a.low[one], a.high[two]) {
        if low > high {
            possible &= !(LESS | SAME);
        } else if low == high {
            possible &= !LESS;
        }
    }
    if let (Some(high), Some(low)) = (a.high[one], a.low[two]) {
        if high < low {
            possible &= !(MORE | SAME);
        } else if high == low {
            possible &= !MORE;
        }
    }
    let outcomes = op_outcomes(op) & possible;
    if outcomes == 0 {
        return rejected("select-pair-empty", Claim::Empty);
    }
    if outcomes == possible {
        return rejected("select-pair-no-op", Claim::SameRows);
    }
    let mut out = a.clone();
    out.complete = 0;
    out.count_follows = false;
    if op == Op::Eq {
        let low = a.low[one].into_iter().chain(a.low[two]).max();
        let high = a.high[one].into_iter().chain(a.high[two]).min();
        out.low[one] = low;
        out.low[two] = low;
        out.high[one] = high;
        out.high[two] = high;
    }
    Ok(without_column(&out, drop, Some(at)).sorted_keys())
}

/// `semijoin`. `complete` holds where each of the right columns is complete over the left column's type.
pub fn semijoin(terms: &[Refined], a: &Refined, b: &Refined, b_id: u32, left: &[u16], right: &[u16], complete: bool) -> Outcome {
    if complete || is_within(terms, a, left, b_id, right, 2) {
        return rejected("semijoin-within", Claim::SameRows);
    }
    if is_outside(a, left, b_id, right) {
        return rejected("semijoin-outside", Claim::Empty);
    }
    let mut out = a.clone();
    out.complete = 0;
    out.count_follows = false;
    out.within.push(Within { columns: left.into(), of: b_id, at: right.into() });
    for (own, other) in left.iter().zip(right) {
        let (own, other) = (usize::from(*own), usize::from(*other));
        out.low[own] = out.low[own].into_iter().chain(b.low[other]).max();
        out.high[own] = out.high[own].into_iter().chain(b.high[other]).min();
    }
    // A complete column that is a key of its relation holds one row per value of the other side.
    if let [one] = left {
        if a.complete & bit(*one) != 0 && a.is_key(bit(*one)) {
            out.count_follows = true;
        }
    }
    Ok(out)
}

/// `antijoin`.
pub fn antijoin(terms: &[Refined], a: &Refined, b_id: u32, left: &[u16], right: &[u16], complete: bool) -> Outcome {
    if complete || is_within(terms, a, left, b_id, right, 2) {
        return rejected("antijoin-within", Claim::Empty);
    }
    if is_outside(a, left, b_id, right) {
        return rejected("antijoin-outside", Claim::SameRows);
    }
    let mut out = a.clone();
    out.complete = 0;
    out.count_follows = false;
    out.outside.push(Within { columns: left.into(), of: b_id, at: right.into() });
    Ok(out)
}

/// `join`.
pub fn join(terms: &[Refined], a: &Refined, b: &Refined, b_id: u32, left: &[u16], right: &[u16], kept: &[u16]) -> Outcome {
    if is_outside(a, left, b_id, right) {
        return rejected("join-outside", Claim::Empty);
    }
    if kept.is_empty() {
        return rejected("join-no-new-column", Claim::Other);
    }
    let left_arity = a.arity() as u16;
    let map_right = |column: u16| -> u16 {
        match right.iter().position(|own| *own == column) {
            Some(at) => left[at],
            None => left_arity + kept.iter().position(|own| *own == column).unwrap_or(0) as u16,
        }
    };
    let mut out = Refined::with_arity(a.arity() + kept.len());
    let right_mask = mask_of(right);
    let left_mask = mask_of(left);
    let right_keyed = b.is_key(right_mask);
    let left_keyed = a.is_key(left_mask);
    let mapped_key = |key: Mask| -> Mask { (0..b.arity() as u16).filter(|column| key & bit(*column) != 0).fold(0, |held, column| held | bit(map_right(column))) };
    for key in &a.keys {
        if right_keyed {
            out.add_key(*key);
        }
        for other in &b.keys {
            out.add_key(*key | mapped_key(*other));
        }
    }
    if left_keyed {
        for other in &b.keys {
            out.add_key(mapped_key(*other));
        }
    }
    for column in 0..a.arity() {
        out.low[column] = a.low[column];
        out.high[column] = a.high[column];
    }
    for (own, other) in left.iter().zip(right) {
        let (own, other) = (usize::from(*own), usize::from(*other));
        out.low[own] = a.low[own].into_iter().chain(b.low[other]).max();
        out.high[own] = a.high[own].into_iter().chain(b.high[other]).min();
    }
    for (at, column) in kept.iter().enumerate() {
        out.low[usize::from(left_arity) + at] = b.low[usize::from(*column)];
        out.high[usize::from(left_arity) + at] = b.high[usize::from(*column)];
    }
    out.within = a.within.clone();
    let mut columns: Vec<u16> = left.to_vec();
    columns.extend((0..kept.len() as u16).map(|at| left_arity + at));
    let mut at: Vec<u16> = right.to_vec();
    at.extend_from_slice(kept);
    out.within.push(Within { columns: columns.into_boxed_slice(), of: b_id, at: at.into_boxed_slice() });
    out.outside = a.outside.clone();
    let _ = terms;
    // Each left row has at most one match, so the count is the `semijoin`'s.
    out.count_follows = right_keyed;
    Ok(out.sorted_keys())
}

/// `all`, with `outer` the columns it keeps.
pub fn all(terms: &[Refined], a: &Refined, b_id: u32, left: &[u16], right: &[u16], outer: &[u16], complete: bool) -> Outcome {
    if complete || is_within(terms, a, left, b_id, right, 2) {
        return rejected("all-within", Claim::Follows);
    }
    if is_outside(a, left, b_id, right) {
        return rejected("all-outside", Claim::Empty);
    }
    if !outer.is_empty() && a.is_key(mask_of(outer)) {
        return rejected("all-outer-key", Claim::Follows);
    }
    let mut out = Refined::with_arity(outer.len());
    out.add_key(out.all_columns());
    for (at, column) in outer.iter().enumerate() {
        out.low[at] = a.low[usize::from(*column)];
        out.high[at] = a.high[usize::from(*column)];
    }
    for held in &a.within {
        let kept: Vec<(u16, u16)> = held.columns.iter().zip(held.at.iter()).filter_map(|(own, other)| outer.iter().position(|column| column == own).map(|at| (at as u16, *other))).collect();
        if !kept.is_empty() {
            out.within.push(Within { columns: kept.iter().map(|pair| pair.0).collect(), of: held.of, at: kept.iter().map(|pair| pair.1).collect() });
        }
    }
    Ok(out)
}
