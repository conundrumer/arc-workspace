//! Order, BoundingBox, Cardinality, Excess, Singleton and Inclusion:
//! counts, sorts and minima.

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::relations::RowSet;
use arclog::terms::{Margins, Number, Term, TermId};

/// An empty set for each output of the component, of the arity its rows
/// take.
fn empty_outputs(arities: &[usize]) -> Vec<RowSet> {
    arities.iter().map(|&arity| RowSet::empty(arity as u16)).collect()
}

/// The outputs, once `work` bindings and the outputs' rows are counted
/// against the budget.
fn charged(outputs: Vec<RowSet>, work: usize, context: &mut ConstructionContext<'_, '_>) -> Result<GroupOutputs, ReachedBound> {
    let rows: usize = outputs.iter().map(RowSet::len).sum();
    context.budget.charge_work((work + rows) as u64)?;
    context.budget.charge_rows(rows as u64)?;
    Ok(GroupOutputs { outputs: outputs.into() })
}

/// The rows of every input of the group, the work of reading them.
fn input_rows(group: &GroupInputs<'_>) -> usize {
    group.inputs.iter().map(RowSet::len).sum()
}

/// A member or a probe of an Order: its columns of `T`.
type Element<'r> = &'r [TermId];

/// What an Order gives before its outputs are rows: each ranked element
/// with its rank and dual rank, the minimal and maximal members, and each
/// pair of a member and its immediate successor.
struct Ranking<'r> {
    ranks: Vec<(Element<'r>, usize, usize)>,
    minimal: Vec<Element<'r>>,
    maximal: Vec<Element<'r>>,
    successors: Vec<(Element<'r>, Element<'r>)>,
    work: usize,
}

/// The ranking under the `before` rows whose endpoints are members, or,
/// for a probe, whose other endpoint is a member.
fn before_ranking<'r>(members: &StableHashSet<Element<'r>>, probes: &[Element<'r>], before: &'r RowSet, width: usize) -> Ranking<'r> {
    let mut predecessors: StableHashMap<Element<'r>, Vec<Element<'r>>> = StableHashMap::default();
    let mut successors: StableHashMap<Element<'r>, StableHashSet<Element<'r>>> = StableHashMap::default();
    let mut edges = Vec::new();
    for row in before.rows() {
        let (a, b) = row.split_at(width);
        if members.contains(a) {
            predecessors.entry(b).or_default().push(a);
        }
        if members.contains(b) {
            successors.entry(a).or_default().insert(b);
        }
        if members.contains(a) && members.contains(b) {
            edges.push((a, b));
        }
    }
    let ranked = members.iter().copied().chain(probes.iter().copied());
    let ranks: Vec<_> = ranked
        .map(|t| (t, predecessors.get(t).map_or(0, Vec::len), successors.get(t).map_or(0, StableHashSet::len)))
        .collect();
    let minimal = members.iter().copied().filter(|t| !predecessors.contains_key(t)).collect();
    let maximal = members.iter().copied().filter(|t| !successors.contains_key(t)).collect();
    let mut work = 0;
    let immediate = edges
        .into_iter()
        .filter(|&(a, b)| {
            let between = &predecessors[b];
            work += between.len();
            !between.iter().any(|x| successors[a].contains(x))
        })
        .collect();
    Ranking { ranks, minimal, maximal, successors: immediate, work }
}

/// The ranking under the preorder that `score` induces: a member or a probe
/// precedes another when its score is less, tied members share a rank, and
/// a member with no score is related to no other.
///
/// Panics where an element has several scores, which the preorder of
/// `docs/lib-spec.md#the-constructions` does not cover.
fn score_ranking<'r>(members: &StableHashSet<Element<'r>>, probes: &[Element<'r>], score: &'r RowSet, width: usize) -> Ranking<'r> {
    let mut scores: StableHashMap<Element<'r>, Number> = StableHashMap::default();
    for row in score.rows() {
        let (t, s) = row.split_at(width);
        if scores.insert(t, Number(Term::decode_number(s[0]))).is_some() {
            panic!("an Order whose `score` gives one element several scores");
        }
    }
    let mut levels: StableHashMap<Number, Vec<Element<'r>>> = StableHashMap::default();
    let mut unscored = Vec::new();
    for &t in members {
        match scores.get(t) {
            Some(&s) => levels.entry(s).or_default().push(t),
            None => unscored.push(t),
        }
    }
    let mut sorted: Vec<Number> = members.iter().filter_map(|t| scores.get(t).copied()).collect();
    sorted.sort_unstable();
    let ranks = members
        .iter()
        .copied()
        .chain(probes.iter().copied())
        .map(|t| match scores.get(t) {
            Some(&s) => (t, sorted.partition_point(|&x| x < s), sorted.len() - sorted.partition_point(|&x| x <= s)),
            None => (t, 0, 0),
        })
        .collect();
    let mut distinct: Vec<Number> = levels.keys().copied().collect();
    distinct.sort_unstable();
    let level = |s: Option<&Number>| s.map_or(&[][..], |s| levels[s].as_slice());
    let minimal = level(distinct.first()).iter().chain(&unscored).copied().collect();
    let maximal = level(distinct.last()).iter().chain(&unscored).copied().collect();
    let successors = distinct
        .windows(2)
        .flat_map(|pair| levels[&pair[0]].iter().flat_map(|&a| levels[&pair[1]].iter().map(move |&b| (a, b))))
        .collect();
    Ranking { ranks, minimal, maximal, successors, work: sorted.len() }
}

/// Rank, dual rank, the minimal and maximal members and the successors of
/// the group's members under `before` or `score`, tied members sharing a
/// rank and each tied member minimal or maximal.
///
/// Panics where a group gives both `before` and `score` rows, which
/// `docs/lib-spec.md#the-constructions` does not cover.
#[derive(Clone, Copy, Debug, Default)]
pub struct Order;

impl Construction for Order {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [member, before, score, probe] = group.inputs else { panic!("Order's four inputs") };
        let width = usize::from(member.arity());
        let members: StableHashSet<Element<'_>> = member.rows().collect();
        let probes: Vec<Element<'_>> = probe.rows().filter(|t| !members.contains(t)).collect();
        let ranking = match (before.is_empty(), score.is_empty()) {
            (_, true) => before_ranking(&members, &probes, before, width),
            (true, false) => score_ranking(&members, &probes, score, width),
            (false, false) => panic!("an Order group with both `before` and `score` rows"),
        };
        context.budget.charge_work((ranking.successors.len() + ranking.maximal.len() * ranking.minimal.len()) as u64)?;
        let [mut rank, mut dual_rank, mut minimal, mut maximal, mut successor, mut cyclic_successor]: [RowSet; 6] =
            empty_outputs(&[width + 1, width + 1, width, width, 2 * width, 2 * width])
                .try_into()
                .expect("six outputs");
        for &(t, r, d) in &ranking.ranks {
            rank.insert(t.iter().copied().chain([Term::encode_number(i32::try_from(r).expect("a count of rows within an i32"))]).collect());
            dual_rank.insert(t.iter().copied().chain([Term::encode_number(i32::try_from(d).expect("a count of rows within an i32"))]).collect());
        }
        for &t in &ranking.minimal {
            minimal.insert(t.into());
        }
        for &t in &ranking.maximal {
            maximal.insert(t.into());
        }
        let pair = |a: Element<'_>, b: Element<'_>| a.iter().chain(b).copied().collect();
        for &(a, b) in &ranking.successors {
            successor.insert(pair(a, b));
            cyclic_successor.insert(pair(a, b));
        }
        for &last in &ranking.maximal {
            for &first in &ranking.minimal {
                cyclic_successor.insert(pair(last, first));
            }
        }
        let outputs = vec![rank, dual_rank, minimal, maximal, successor, cyclic_successor];
        charged(outputs, input_rows(group) + ranking.work, context)
    }
}

/// The least box that holds the group's cells, a minimum over margins.
#[derive(Clone, Copy, Debug, Default)]
pub struct BoundingBox;

impl Construction for BoundingBox {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell] = group.inputs else { panic!("BoundingBox's one input") };
        let mut outputs = empty_outputs(&[1]);
        let margins = cell.rows().map(|row| Term::decode_box(row[0]));
        let least = margins.reduce(|a, b| Margins {
            top: a.top.min(b.top),
            bottom: a.bottom.min(b.bottom),
            left: a.left.min(b.left),
            right: a.right.min(b.right),
        });
        if let Some(least) = least {
            outputs[0].insert([Term::Box(least).encode().map_err(ReachedBound::Margin)?].into());
        }
        charged(outputs, input_rows(group), context)
    }
}

/// The count of the group's members, 0 for a key of the domain with none.
#[derive(Clone, Copy, Debug, Default)]
pub struct Cardinality;

impl Construction for Cardinality {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [member, domain] = group.inputs else { panic!("Cardinality's two inputs") };
        let mut outputs = empty_outputs(&[1]);
        if !member.is_empty() || !domain.is_empty() {
            outputs[0].insert([Term::encode_number(i32::try_from(member.len()).expect("a count of rows within an i32"))].into());
        }
        charged(outputs, input_rows(group), context)
    }
}

/// The amount by which the group's plus set outnumbers its minus set.
#[derive(Clone, Copy, Debug, Default)]
pub struct Excess;

impl Construction for Excess {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [plus, minus] = group.inputs else { panic!("Excess's two inputs") };
        let mut outputs = empty_outputs(&[1]);
        if plus.len() > minus.len() {
            outputs[0].insert([Term::encode_number(i32::try_from(plus.len() - minus.len()).expect("a count of rows within an i32"))].into());
        }
        charged(outputs, input_rows(group), context)
    }
}

/// The one value of the group's members, and the keys whose members
/// disagree.
#[derive(Clone, Copy, Debug, Default)]
pub struct Singleton;

impl Construction for Singleton {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [member] = group.inputs else { panic!("Singleton's one input") };
        let mut outputs = empty_outputs(&[usize::from(member.arity()), 0]);
        match member.len() {
            0 => {}
            1 => {
                let value = member.rows().next().expect("one row");
                outputs[0].insert(value.into());
            }
            _ => {
                outputs[1].insert([].into());
            }
        }
        charged(outputs, input_rows(group), context)
    }
}

/// Each observed set against the patterns, by counts over the pairs that
/// share a member.
#[derive(Clone, Copy, Debug, Default)]
pub struct Inclusion;

impl Construction for Inclusion {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        _group: &GroupInputs<'_>,
        _context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        todo!()
    }
}
