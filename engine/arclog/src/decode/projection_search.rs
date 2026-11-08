//! The completion search of a projection: whether some completion of the
//! head of an instance input that stands open in a state, or of the field of
//! a body site, passes the checks. [`Decoder::next`] admits a token whose
//! state stands in such a head only where the search finds a completion.
//!
//! The search is exact. It walks the head sites depth-first, over the tokens
//! of [`State::head_site_completions`], and refuses only where every
//! completion of the head that those tokens give is refused by the checks.
//! It refuses with no verdict only where it has spent [`PROJECTION_STEP_CAP`]
//! steps. The cap is a bound on the time of one search, which a valid program
//! is not meant to reach, and [`measures`] reports each search that does.
//!
//! A walk with no cut comes first, for [`QUICK_STEPS`] steps. A completion
//! it finds passes the checks, and where it ends with no completion it has
//! tried every token, so either verdict is exact, and it costs no more than
//! the walk cost before the cuts: most searches end here. Only a walk that
//! spends its steps is followed by the walk with the cuts, which pays for
//! reading the form once.
//!
//! Each step of the walk with the cuts is one token that passes the cuts
//! below, and the cuts remove only tokens, and states, that the checks refuse
//! in every completion, so the walk finds a completion where the walk with no
//! cut does. They apply to the input of an `INIT` form, where the checks that
//! they read run on the form alone ([`Cuts`]):
//!
//! - A head site holds no label that the body does not let its head read
//!   ([`crate::check::labels::head_readable_labels`]).
//! - A site on a column of a fixed scalar type holds no label that
//!   [`State::head_label_conflicts`] refuses.
//! - The head closes no column that must have a site with none
//!   ([`crate::check::instance_inputs::HeadNeeds::required`]).
//! - A head that must read a label of the key body, and reads none yet, has
//!   a site that can still read one ([`crate::check::instance_inputs::HeadNeeds::key_labels`]).
//!
//! The switch of [`measures`] runs the search that
//! [`Decoder::legacy_completes_projection`] holds beside this one, to count the
//! verdicts that differ.

use std::sync::OnceLock;

use super::state::{OpenProjection, ReadsExample, State};
use super::{Decoder, Refusal};
use crate::check::instance_inputs::head_needs;
use crate::check::labels::head_readable_labels;
use crate::check::prefix::{Candidate, PrefixChecks};
use crate::program::{ColumnName, LabelId};
use crate::stats::{self, Phase};
use crate::stream::{Control, Token};

/// The message of the refusal of a search that spent its steps. Readers of
/// the refusal match on it.
const SPENT: &str = "the completion search of a projection spent its budget";

/// The steps that the search of [`Decoder::legacy_completes_projection`]
/// takes.
const LEGACY_STEPS: usize = 96;

/// The steps of the walk with no cut that starts a search.
const QUICK_STEPS: usize = 8;

/// The most steps that one search takes, a step being one token tried at a
/// head site. A search that spends them is refused with [`SPENT`].
const PROJECTION_STEP_CAP: usize = 4096;

/// Whether each search runs the search of
/// [`Decoder::legacy_completes_projection`] as well, and prints one line
/// with both verdicts to the standard error: `ARCLOG_PROJECTION_MEASURE`
/// set to a value other than `0` or empty, read once. The line reads
/// `arclog-projection-measure old=<ok|none|budget> new=<ok|none|cap>
/// old_steps=<n> new_steps=<n>`, with ` MISMATCH` after it where the old
/// search completed or found no completion in its steps and the new verdict
/// differs, and `new=cap` where the new search spent its steps. It changes no
/// verdict.
fn measures() -> bool {
    static MEASURES: OnceLock<bool> = OnceLock::new();
    *MEASURES.get_or_init(|| std::env::var("ARCLOG_PROJECTION_MEASURE").is_ok_and(|v| !v.is_empty() && v != "0"))
}

/// What a search gives.
struct Outcome {
    verdict: Result<(), Refusal>,
    /// The steps taken.
    steps: usize,
    /// Whether the search spent its steps.
    capped: bool,
}

/// What the form fixes of the head of the input whose head site stands open,
/// each read once at the start of a search. The input's body, the key clause
/// and the earlier inputs are complete and no head site changes them.
struct Cuts {
    /// By label made, whether a head site may read it.
    readable: Vec<bool>,
    /// By column of the input's port, whether the head must hold a site on it.
    required: Vec<bool>,
    /// By column, the labels a site on the column refuses, once read. Where
    /// the checks are not in mask mode none is read, as the search with no
    /// cut reads none.
    conflicts: Vec<Option<Vec<u32>>>,
    columns: Vec<ColumnName>,
    mask: bool,
    key: Option<KeyNeed>,
}

/// A head that must read a label of the key body: the input stands in the
/// key clause and its body reads none.
struct KeyNeed {
    /// By label made, whether it is a label of the key body.
    labels: Vec<bool>,
    /// By column, whether some label of the key body stands at a site on it
    /// that no check refuses on the column and the body alone.
    hosts: Vec<bool>,
    /// By column, whether a column after it is one of `hosts`.
    after: Vec<bool>,
    /// Whether some label of the key body is one a head site may read.
    any: bool,
}

const NO_SITE: Refusal = Refusal::Grammar("the head closes a column on which the input must write a site with none");
const NO_LABEL: Refusal = Refusal::Grammar("no label can stand at a site on which the input must write one");
const NO_KEY: Refusal = Refusal::Grammar("the head reads no key label, and the input's body reads none and no output of its instance, so the input is a broadcast");

impl Cuts {
    /// Whether `label` is a label of the key body, where the head must read one.
    fn is_key(&self, label: u32) -> bool {
        self.key.as_ref().is_some_and(|key| key.labels.get(label as usize) == Some(&true))
    }

    /// The refusal that holds in every completion of the head whose open site
    /// is `open`, where it holds, with `has_key` whether the head reads a label
    /// of the key body already. `open` is none where the head is closed.
    ///
    /// - A column before the open site that the head closed with no site, and
    ///   on which the input must write one, is refused in each completion:
    ///   the sites written after it are on other columns.
    /// - A head that must read a label of the key body and has read none is
    ///   refused in each completion that adds no such label. A label is added
    ///   at the open site or at a site on a later column, so it is refused in
    ///   each completion where neither can read one of those labels.
    fn dead(&self, open: Option<&OpenProjection>, has_key: bool) -> Option<Refusal> {
        if let Some(open) = open {
            if open.without_site.iter().any(|&column| self.required[column]) {
                return Some(NO_SITE);
            }
        }
        let key = self.key.as_ref().filter(|_| !has_key)?;
        let hosted = match open {
            None => false,
            Some(open) => {
                let now = if open.field_open {
                    key.any
                } else if open.record_ended {
                    false
                } else if open.args == 0 {
                    key.hosts[open.column]
                } else {
                    open.parameter && key.any
                };
                now || key.after[open.column]
            }
        };
        (!hosted).then_some(NO_KEY)
    }
}

/// One search over the tokens of the head sites of the state it starts at.
struct ProjectionSearch<'a, 'c, 'd> {
    decoder: &'a Decoder<'d>,
    checks: &'a PrefixChecks<'c>,
    reads_example: ReadsExample<'a>,
    cuts: Option<Cuts>,
    steps: usize,
    cap: usize,
    capped: bool,
    /// Whether the limit of a site shortened the tokens at some node.
    limit_shortened: bool,
    /// The work of the request that the search runs in.
    work: crate::eval::RequestWork,
}

impl<'a, 'c, 'd> ProjectionSearch<'a, 'c, 'd> {
    /// The cuts of the input whose head site stands on top of `state`, where
    /// it is the input of an `INIT` form that the checks of [`Cuts`] read.
    fn cuts_for(&self, state: &State) -> Option<Cuts> {
        let registry = self.decoder.context.registry;
        let open = state.open_projection()?;
        let (program, _) = state.partial()?;
        let form = program.value().forms.last()?;
        let needs = head_needs(registry, form)?;
        let readable = head_readable_labels(form)?;
        let columns = state.head_columns(registry);
        if needs.required.len() != columns.len() {
            return None;
        }
        let made = state.label_count();
        let readable = (0..made).map(|label| readable.contains(&LabelId(label))).collect();
        let mut cuts = Cuts { readable, required: needs.required, conflicts: vec![None; columns.len()], columns, mask: self.checks.is_mask(), key: None };
        for column in open.column..cuts.columns.len() {
            self.read_conflicts(&mut cuts, state, column);
        }
        if let Some(key_labels) = needs.key_labels {
            let mut labels = vec![false; made as usize];
            for label in key_labels {
                if let Some(slot) = labels.get_mut(label.0 as usize) {
                    *slot = true;
                }
            }
            let hosts: Vec<bool> = (0..cuts.columns.len())
                .map(|column| {
                    let conflicts = cuts.conflicts[column].as_deref().unwrap_or(&[]);
                    (0..made).any(|label| labels[label as usize] && cuts.readable[label as usize] && !conflicts.contains(&label))
                })
                .collect();
            let after = (0..hosts.len()).map(|column| hosts[column + 1..].iter().any(|host| *host)).collect();
            let any = (0..made as usize).any(|label| labels[label] && cuts.readable[label]);
            cuts.key = Some(KeyNeed { labels, hosts, after, any });
        }
        Some(cuts)
    }

    /// Reads into `cuts` the labels that a site on `column` refuses, where the
    /// checks are in mask mode and it holds none yet. They depend on the
    /// bodies of the form and on the column alone, as
    /// [`State::head_label_conflicts`] gives, so they are those at every
    /// head site of the column.
    fn read_conflicts(&self, cuts: &mut Cuts, state: &State, column: usize) {
        if !cuts.mask || cuts.conflicts[column].is_some() {
            return;
        }
        let column_type = |relation: &crate::program::RelationRef, column: &ColumnName| self.decoder.fixed_column_type(self.checks, relation, column);
        cuts.conflicts[column] = Some(state.head_label_conflicts(self.decoder.context.registry, &column_type, &cuts.columns[column]));
    }

    /// The tokens that the search tries at `state` under `limit`, in the order
    /// of [`State::head_site_completions`], less those the checks refuse in
    /// each completion, as the doc of this module gives: a label that the head
    /// may not read or that a site refuses on its column's type, and the `END`
    /// of a site that holds no argument where the input must write a site on
    /// its column. None where no head site stands on top.
    fn candidates(&self, state: &State, limit: usize) -> Option<Vec<Token>> {
        let mut tokens = state.head_site_completions(limit)?;
        let open = state.open_projection();
        match (&self.cuts, open) {
            (Some(cuts), Some(open)) => {
                let at_start = open.args == 0 && !open.field_open;
                let conflicts: &[u32] = if at_start { cuts.conflicts[open.column].as_deref().unwrap_or(&[]) } else { &[] };
                let closes_required = at_start && cuts.required[open.column];
                tokens.retain(|token| match token {
                    Token::Label(label) => cuts.readable.get(*label as usize) == Some(&true) && !conflicts.contains(label),
                    Token::Control(Control::End) => !closes_required,
                    _ => true,
                });
            }
            _ => {
                let conflicts = if self.checks.is_mask() { state.fixed_label_conflicts(self.decoder.context.registry, &|relation, column| self.decoder.fixed_column_type(self.checks, relation, column)) } else { Vec::new() };
                tokens.retain(|token| !matches!(token, Token::Label(label) if conflicts.contains(label)));
            }
        }
        Some(tokens)
    }

    /// Whether some completion of the head sites at `state` passes the checks,
    /// where `has_key` is whether the head reads a label of the key body
    /// already; or, where none does, the refusal of the last completion tried.
    fn node(&mut self, state: &State, has_key: bool, limit: usize) -> Result<(), Refusal> {
        let Some(tokens) = self.candidates(state, limit) else { return Ok(()) };
        self.limit_shortened |= state.limit_shortens(limit);
        let mut refusal = Refusal::Grammar("a projection has no completion");
        for token in tokens {
            if self.steps >= self.cap {
                self.capped = true;
                return Err(Refusal::Grammar(SPENT));
            }
            self.steps += 1;
            // A step counts as one unit of the request's work. A request past
            // its cap establishes nothing of the head: the search ends with a
            // completion, as a stop at the table work cap admits.
            if self.work.charge(1).is_err() {
                return Ok(());
            }
            stats::units(Phase::DecodeCompletes, 1);
            let next = match state.step(&self.decoder.context, &token, self.reads_example) {
                Ok((next, _, _)) => next,
                Err(unexpected) => {
                    refusal = Refusal::Grammar(unexpected);
                    continue;
                }
            };
            let next_has_key = has_key || matches!(&token, Token::Label(label) if self.cuts.as_ref().is_some_and(|cuts| cuts.is_key(*label)));
            if let Some(dead) = self.cuts.as_ref().and_then(|cuts| cuts.dead(next.open_projection().as_ref(), next_has_key)) {
                refusal = dead;
                continue;
            }
            match self.decoder.check_state(&next, Candidate::Any, self.checks).and_then(|()| self.node(&next, next_has_key, limit)) {
                Ok(()) => return Ok(()),
                Err(next) => refusal = next,
            }
        }
        Err(refusal)
    }

    /// The search from `state`, with the cuts where `cut` holds: the cuts
    /// that read the state alone, then the walk with one argument at each
    /// site, which finds a completion fast where a site holds many sets of
    /// labels and one label passes where any does, then, where some site's
    /// limit shortened its tokens and the walk found none, the walk with every
    /// token. The tokens under one argument are among those with every token,
    /// so the second walk finds a completion where any walk does.
    fn decide(mut self, state: &State, cut: bool) -> Outcome {
        self.cuts = if cut { self.cuts_for(state) } else { None };
        let verdict = match self.at_start(state) {
            Some(refusal) => Err(refusal),
            None => self.walks(state),
        };
        Outcome { verdict, steps: self.steps, capped: self.capped }
    }

    /// The refusal that the cuts give at the state that the search starts at,
    /// before any token is tried: [`Cuts::dead`], and a column from the open
    /// one on on which the input must write a site and no label can stand at
    /// a site: the labels that a head site may read, less those a site on the
    /// column refuses, are none, and a site holds a label.
    fn at_start(&self, state: &State) -> Option<Refusal> {
        let cuts = self.cuts.as_ref()?;
        let open = state.open_projection()?;
        let has_key = cuts.key.as_ref().is_some_and(|key| state.head_labels().iter().any(|label| key.labels.get(*label as usize) == Some(&true)));
        if let Some(dead) = cuts.dead(Some(&open), has_key) {
            return Some(dead);
        }
        let started = open.args > 0 || open.field_open;
        for column in open.column..cuts.columns.len() {
            if !cuts.required[column] || (started && column == open.column) {
                continue;
            }
            let conflicts = cuts.conflicts[column].as_deref().unwrap_or(&[]);
            if !(0..cuts.readable.len() as u32).any(|label| cuts.readable[label as usize] && !conflicts.contains(&label)) {
                return Some(NO_LABEL);
            }
        }
        None
    }

    fn walks(&mut self, state: &State) -> Result<(), Refusal> {
        let has_key = self.cuts.as_ref().is_some_and(|cuts| cuts.key.is_some() && state.head_labels().iter().any(|label| cuts.is_key(*label)));
        match self.node(state, has_key, 1) {
            Err(_) if self.capped => Err(Refusal::Grammar(SPENT)),
            Err(refusal) if !self.limit_shortened => Err(refusal),
            Err(_) => self.node(state, has_key, usize::MAX),
            Ok(()) => Ok(()),
        }
    }
}

impl<'d> Decoder<'d> {
    /// Whether some completion of the projection of an instance input, or of
    /// the field of a body site, that stands open in `state` passes the
    /// checks, or, where none does, the refusal of the last completion tried.
    /// The completions are the tokens of [`State::head_site_completions`] at
    /// each head site that stands open or follows, up to the state where the
    /// input is closed or the field's label stands, which is the one the
    /// checks must pass. Where the search has spent [`PROJECTION_STEP_CAP`]
    /// steps it refuses, with a refusal that says it spent its steps.
    pub(super) fn completes_projection(&self, state: &State, checks: &PrefixChecks<'_>, reads_example: ReadsExample<'_>) -> Result<(), Refusal> {
        let work = self.request_work();
        let search = |cap: usize| ProjectionSearch { decoder: self, checks, reads_example, cuts: None, steps: 0, cap, capped: false, limit_shortened: false, work: work.clone() };
        let cap = PROJECTION_STEP_CAP;
        let quick = search(QUICK_STEPS.min(cap)).decide(state, false);
        let outcome = if quick.verdict.is_ok() || !quick.capped {
            quick
        } else {
            let outcome = search(cap).decide(state, true);
            Outcome { steps: outcome.steps + quick.steps, ..outcome }
        };
        if measures() {
            self.print_measure(state, checks, reads_example, &outcome);
        }
        // The steps of the search that the bound counted, and a hit where it spent them.
        let (steps, bound) = (outcome.steps as u64, cap as u64);
        if outcome.capped {
            work.gauges().hit(crate::eval::Gauge::ProjectionSteps, steps, bound);
        } else {
            work.gauges().note(crate::eval::Gauge::ProjectionSteps, steps, bound);
        }
        outcome.verdict
    }

    /// Prints the line of [`measures`] for `outcome`, the outcome of the
    /// search from `state`.
    fn print_measure(&self, state: &State, checks: &PrefixChecks<'_>, reads_example: ReadsExample<'_>, outcome: &Outcome) {
        let mut left = LEGACY_STEPS;
        let steps = &mut left;
        let old = self.legacy_completes_projection(state, checks, reads_example, 1, steps).or_else(|_| self.legacy_completes_projection(state, checks, reads_example, usize::MAX, steps));
        let old_steps = LEGACY_STEPS - left;
        let old_kind = match &old {
            Ok(()) => "ok",
            Err(Refusal::Grammar(SPENT)) => "budget",
            Err(_) => "none",
        };
        let new_kind = match (&outcome.verdict, outcome.capped) {
            (Ok(()), _) => "ok",
            (Err(_), true) => "cap",
            (Err(_), false) => "none",
        };
        let agrees = matches!((old_kind, new_kind), ("ok", "ok") | ("none", "none") | ("budget", _));
        eprintln!("arclog-projection-measure old={old_kind} new={new_kind} old_steps={old_steps} new_steps={}{}", outcome.steps, if agrees { "" } else { " MISMATCH" });
    }

    /// The search that [`Decoder::completes_projection`] was before its cuts,
    /// kept to count against: the walk over every token of
    /// [`State::head_site_completions`] with `limit` at each head site, one
    /// step for each token tried, and a refusal where `steps` is spent.
    fn legacy_completes_projection(&self, state: &State, checks: &PrefixChecks<'_>, reads_example: ReadsExample<'_>, limit: usize, steps: &mut usize) -> Result<(), Refusal> {
        let Some(tokens) = state.head_site_completions(limit) else { return Ok(()) };
        let conflicts = if checks.is_mask() { state.fixed_label_conflicts(self.context.registry, &|relation, column| self.fixed_column_type(checks, relation, column)) } else { Vec::new() };
        let mut refusal = Refusal::Grammar("a projection has no completion");
        for token in tokens {
            if *steps == 0 {
                return Err(Refusal::Grammar(SPENT));
            }
            *steps -= 1;
            if matches!(&token, Token::Label(label) if conflicts.contains(label)) {
                continue;
            }
            let next = match state.step(&self.context, &token, reads_example) {
                Ok((next, _, _)) => next,
                Err(unexpected) => {
                    refusal = Refusal::Grammar(unexpected);
                    continue;
                }
            };
            match self.check_state(&next, Candidate::Any, checks).and_then(|()| self.legacy_completes_projection(&next, checks, reads_example, limit, steps)) {
                Ok(()) => return Ok(()),
                Err(next) => refusal = next,
            }
        }
        Err(refusal)
    }
}
