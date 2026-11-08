//! The labels of one scope, as [`crate::program::LabelId`] gives a scope.
//!
//! Each site that makes a label, `*X` or `^X`, makes its own id. A join `X`
//! takes the id of the site that makes `X` nearest to it in the tree of
//! lists: the one whose least list in common with the join is deepest, then
//! the one least deep below that list, then the first. So an input's head
//! joins the label its own body makes over one its key body makes, a later
//! branch of an `OR` joins what the first branch makes, and an `IF`'s then
//! joins what its test makes.
//!
//! A body makes each name at one site (`docs/arclog/arclog.md#sites`):
//! [`LabelScope::repeated`] gives the sites of a body that break that.

use std::cell::RefCell;
use crate::hash::StableHashSet;

use crate::layout::SourcePlace;
use crate::program::LabelId;

use super::spelling::{FRESH_MARK, KEY_MARK};
use super::SExpr;

/// A site of the scope that makes a label.
struct Made {
    name: Box<str>,
    place: SourcePlace,
    /// The number of lists of the scope that hold the site.
    depth: u32,
}

/// The labels of one scope, read from its s-expressions before its nodes.
pub(super) struct LabelScope {
    /// The byte span of each list of the scope, in order of their starts.
    lists: Vec<(u32, u32)>,
    /// The sites that make a label, in source order; a label's id is its
    /// index here.
    made: Vec<Made>,
    /// The start of each join read so far, with its id.
    joins: RefCell<Vec<(u32, LabelId)>>,
}

impl LabelScope {
    /// The scope of `exprs`, leaving out each item of a list of `exprs` that
    /// `skip` gives, which is a scope of its own.
    pub(super) fn new(exprs: &[SExpr], skip: &dyn Fn(&SExpr) -> bool) -> Self {
        let mut scope = LabelScope { lists: Vec::new(), made: Vec::new(), joins: RefCell::new(Vec::new()) };
        for expr in exprs {
            scope.collect(expr, 0, skip);
        }
        scope
    }

    fn collect(&mut self, expr: &SExpr, depth: u32, skip: &dyn Fn(&SExpr) -> bool) {
        match expr {
            SExpr::Symbol { text, place } => {
                if let Some(name) = text.strip_prefix([FRESH_MARK, KEY_MARK]) {
                    self.made.push(Made { name: name.into(), place: *place, depth });
                }
            }
            SExpr::String { .. } => {}
            SExpr::List { items, place, .. } => {
                if depth == 1 && skip(expr) {
                    return;
                }
                self.lists.push((place.start, place.end));
                for item in items.iter() {
                    self.collect(item, depth + 1, skip);
                }
            }
        }
    }

    /// The id of the label that the site at `place`, a `*X` or `^X` of the
    /// scope, makes.
    pub(super) fn made(&self, place: SourcePlace) -> LabelId {
        let index = self
            .made
            .binary_search_by_key(&place.start, |m| m.place.start)
            .expect("each `*X` and `^X` of a scope makes a label of it");
        LabelId(index as u32)
    }

    /// The id that the join `name` at `place` takes, or `None` where no site
    /// of the scope makes `name`.
    pub(super) fn joined(&self, name: &str, place: SourcePlace) -> Option<LabelId> {
        let at = place.start;
        let best = self
            .made
            .iter()
            .enumerate()
            .filter(|(_, m)| &*m.name == name)
            .min_by_key(|(index, m)| {
                let common = self.common_depth(at, m.place.start);
                (u32::MAX - common, m.depth - common, *index)
            })
            .map(|(index, _)| LabelId(index as u32))?;
        self.joins.borrow_mut().push((at, best));
        Some(best)
    }

    /// The sites of the scope inside `exprs`, a run of adjacent items of one
    /// list.
    fn sites_in(&self, exprs: &[SExpr]) -> &[Made] {
        let (Some(first), Some(last)) = (exprs.first(), exprs.last()) else { return &[] };
        let (from, to) = (first.place().start, last.place().end);
        let low = self.made.partition_point(|m| m.place.start < from);
        let high = self.made.partition_point(|m| m.place.start < to);
        &self.made[low..high]
    }

    /// The sites inside `exprs`, a body, that make a name that an earlier site
    /// inside `exprs` makes or `held` holds, each with its name, in source
    /// order.
    pub(super) fn repeated(&self, exprs: &[SExpr], held: &[Box<str>]) -> Vec<(&str, SourcePlace)> {
        let mut seen: StableHashSet<&str> = held.iter().map(|name| &**name).collect();
        let mut repeated = Vec::new();
        for site in self.sites_in(exprs) {
            if !seen.insert(&site.name) {
                repeated.push((&*site.name, site.place));
            }
        }
        repeated
    }

    /// The number of lists of the scope that hold both `a` and `b`.
    fn common_depth(&self, a: u32, b: u32) -> u32 {
        let (low, high) = (a.min(b), a.max(b));
        self.lists.iter().filter(|(start, end)| *start <= low && high < *end).count() as u32
    }

    /// The name of each label of the scope.
    pub(super) fn names(&self) -> Box<[(LabelId, Box<str>)]> {
        self.made.iter().enumerate().map(|(index, m)| (LabelId(index as u32), m.name.clone())).collect()
    }

    /// The name of `label`.
    pub(super) fn name(&self, label: LabelId) -> &str {
        &self.made[label.0 as usize].name
    }
}
