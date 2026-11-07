//! Counts of the evaluations that a bound stopped, per bound and per term head.
//!
//! The counts run only where the environment variable `GENERATE_COUNT_BOUNDS` is set to a
//! value other than empty or `0`. With it unset, each call here returns at once and no list changes.
//!
//! A walker calls [`begin`] before an evaluation and [`end`] after it. A bound that stops the
//! evaluation calls [`mark`] in between, and the evaluation then counts once for that bound, however
//! many times the bound is met inside it. A walk calls [`flush`] when it ends, which adds the counts
//! of the thread to the totals that [`summary`] prints.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

/// A bound that makes an evaluation give no value.
#[derive(Clone, Copy)]
pub enum Bound {
    /// `inside-boxes` and `boxes-holding`: the rows of the left side times the boxes of the right side pass 4,000,000.
    BoxesGuard,
    /// A side of a `join`, as a product of parts, passes `CELL_CAP` cells. No step marks it: a `join` reads the parts of a side in place, or joins them one at a time.
    JoinSide,
    /// The rows of a `join` that an operator reads, written out or as the tuples at the columns it names, pass `CELL_CAP` cells.
    JoinOutput,
    /// The product of the parts of an `antijoin`'s left that hold its paired columns passes `CELL_CAP` cells. One part is read in place at any size.
    AntijoinSide,
    /// The pairs of rows that a `select` keeps from two parts, where it compares a column of one with a column of the other, pass `CELL_CAP` cells.
    SelectSide,
    /// A side or the output of a `union` passes `CELL_CAP` cells.
    Union,
    /// The groups that a count over a `join` stands for pass `CELL_CAP` cells, or the work of counting the distinct tuples of its rows passes its bound.
    CountOutput,
    /// A product of parts that `flat` writes passes 2^18 rows.
    Flat,
    /// A walk has passed 100,000,000 cells of values.
    Walk,
    /// The rows of `inside` that an operator reads, written out or as the tuples at the columns it names, pass `CELL_CAP` cells.
    InsideCells,
    /// `complement` reads a box of more than 4096 cells.
    ComplementArea,
    /// A lib join passes `CELL_CAP` cells, on a side or as its output.
    LibJoin,
    /// The rows that a component takes as input pass `CELL_CAP` cells.
    Projected,
    /// The rows that a component gives pass `CELL_CAP` cells.
    ComponentOutput,
}

/// The name of each bound, in the order of [`Bound`].
const NAMES: [&str; 14] = [
    "boxes-guard", "cap-join-side", "cap-join-output", "cap-antijoin-side", "cap-select-side", "cap-union", "cap-count-output", "flat", "walk", "inside-cells", "complement-area", "cap-lib-join", "cap-projected", "cap-component-output",
];

/// The slot of the evaluations in a head's counts, and of those whose input already had no value.
const EVALUATIONS: usize = NAMES.len();
const INHERITED: usize = NAMES.len() + 1;
const SLOTS: usize = NAMES.len() + 2;

type Counts = [u64; SLOTS];

/// The heads by number, and the counts of each head.
#[derive(Default)]
struct Totals {
    names: Vec<String>,
    index: HashMap<String, u32>,
    counts: Vec<Counts>,
}

static TOTALS: OnceLock<Mutex<Totals>> = OnceLock::new();

fn totals() -> &'static Mutex<Totals> {
    TOTALS.get_or_init(|| Mutex::new(Totals { names: vec!["(no head)".to_string()], index: HashMap::new(), counts: vec![[0; SLOTS]] }))
}

thread_local! {
    /// The bounds that stopped the evaluation in progress, one bit each.
    static MARKS: Cell<u32> = const { Cell::new(0) };
    /// The head of the term in progress.
    static HEAD: Cell<u32> = const { Cell::new(0) };
    /// This thread's counts by head, not yet added to the totals.
    static LOCAL: RefCell<Vec<Counts>> = const { RefCell::new(Vec::new()) };
}

/// Whether the counts run.
pub fn enabled() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var("GENERATE_COUNT_BOUNDS").is_ok_and(|value| !value.is_empty() && value != "0"))
}

/// The number of a term head, from the text of a term: its first word without the opening parentheses.
pub fn head_of(text: &str) -> u32 {
    let head = text.trim_start_matches('(').split(' ').next().unwrap_or("").trim_end_matches(')');
    let mut held = totals().lock().unwrap();
    if let Some(found) = held.index.get(head) {
        return *found;
    }
    let at = held.names.len() as u32;
    held.names.push(head.to_string());
    held.counts.push([0; SLOTS]);
    held.index.insert(head.to_string(), at);
    at
}

/// The name of a head number.
pub fn name_of(head: u32) -> String {
    totals().lock().unwrap().names[head as usize].clone()
}

/// The head of the terms that evaluate from now on.
pub fn set_head(head: u32) {
    if enabled() {
        HEAD.with(|held| held.set(head));
    }
}

fn add(slot: usize, by: u64) {
    let head = HEAD.with(Cell::get) as usize;
    LOCAL.with(|local| {
        let mut local = local.borrow_mut();
        if local.len() <= head {
            local.resize(head + 1, [0; SLOTS]);
        }
        local[head][slot] += by;
    });
}

/// Starts an evaluation.
pub fn begin() {
    if enabled() {
        MARKS.with(|marks| marks.set(0));
    }
}

/// A bound stopped the evaluation in progress.
pub fn mark(bound: Bound) {
    if enabled() {
        MARKS.with(|marks| marks.set(marks.get() | 1 << bound as u32));
    }
}

/// Ends an evaluation, and counts it, and each bound that stopped it. `inherited` says that an input had no value.
pub fn end(inherited: bool) {
    if !enabled() {
        return;
    }
    add(EVALUATIONS, 1);
    if inherited {
        add(INHERITED, 1);
    }
    let marks = MARKS.with(Cell::get);
    for slot in 0..NAMES.len() {
        if marks & 1 << slot != 0 {
            add(slot, 1);
        }
    }
}

/// `count` evaluations of the term in progress that a walk did not run, as a bound stopped it.
pub fn skipped(bound: Bound, count: u64) {
    if enabled() && count > 0 {
        add(bound as usize, count);
        add(EVALUATIONS, count);
    }
}

/// Counts of a walk by group and by label, for the checks of a change.
static TALLIES: OnceLock<Mutex<HashMap<(&'static str, String), u64>>> = OnceLock::new();

/// `count` more under a label of a group.
pub fn tally(group: &'static str, label: String, count: u64) {
    if enabled() && count > 0 {
        *TALLIES.get_or_init(Default::default).lock().unwrap().entry((group, label)).or_insert(0) += count;
    }
}

/// Adds this thread's counts to the totals.
pub fn flush() {
    if !enabled() {
        return;
    }
    let local = LOCAL.with(|local| std::mem::take(&mut *local.borrow_mut()));
    let mut held = totals().lock().unwrap();
    for (head, counts) in local.iter().enumerate() {
        for (slot, count) in counts.iter().enumerate() {
            held.counts[head][slot] += count;
        }
    }
}

/// The totals as text: for each bound, the heads it stopped and the evaluations it stopped, then each head's evaluations and those whose input had no value.
pub fn summary() -> String {
    flush();
    let held = totals().lock().unwrap();
    let mut out = String::from("bounds\tbound\thead\tstopped evaluations\n");
    for (slot, name) in NAMES.iter().enumerate() {
        let mut heads: Vec<(&str, u64)> = held.names.iter().zip(&held.counts).filter(|(_, counts)| counts[slot] > 0).map(|(head, counts)| (head.as_str(), counts[slot])).collect();
        heads.sort_by_key(|(head, count)| (std::cmp::Reverse(*count), *head));
        let whole: u64 = heads.iter().map(|(_, count)| count).sum();
        out.push_str(&format!("bounds\t{name}\t(all heads)\t{whole}\n"));
        for (head, count) in heads {
            out.push_str(&format!("bounds\t{name}\t{head}\t{count}\n"));
        }
    }
    out.push_str("bounds\ttally\tgroup\tlabel\tcount\n");
    if let Some(tallies) = TALLIES.get() {
        let mut rows: Vec<_> = tallies.lock().unwrap().iter().map(|((group, label), count)| (*group, label.clone(), *count)).collect();
        rows.sort();
        for (group, label, count) in rows {
            out.push_str(&format!("bounds\ttally\t{group}\t{label}\t{count}\n"));
        }
    }
    out.push_str("bounds\thead\tevaluations\tinput had no value\n");
    let mut heads: Vec<(&str, u64, u64)> = held.names.iter().zip(&held.counts).filter(|(_, counts)| counts[EVALUATIONS] > 0).map(|(head, counts)| (head.as_str(), counts[EVALUATIONS], counts[INHERITED])).collect();
    heads.sort_by_key(|(head, count, _)| (std::cmp::Reverse(*count), *head));
    for (head, evaluations, inherited) in heads {
        out.push_str(&format!("bounds\thead\t{head}\t{evaluations}\t{inherited}\n"));
    }
    out
}
