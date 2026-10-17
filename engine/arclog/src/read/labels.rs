//! The labels of one scope, as [`crate::program::LabelId`] gives a scope.
//!
//! Each site that makes a label, `*X` or `^X`, makes its own id. A join `X`
//! takes the id of the site that makes `X` nearest to it in the tree of
//! lists: the one whose least list in common with the join is deepest, then
//! the one least deep below that list, then the first. So an input's head
//! joins the label its own body makes over one its key body makes, a later
//! branch of an `OR` joins what the first branch makes, and an `IF`'s then
//! joins what its test makes.

use std::cell::RefCell;

use crate::layout::SourcePlace;
use crate::program::LabelId;

use super::spelling::{FRESH_MARK, KEY_MARK};
use super::{LabelNames, SExpr};

/// A site of the scope that makes a label.
struct Made {
    name: Box<str>,
    start: u32,
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
                    self.made.push(Made { name: name.into(), start: place.start, depth });
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
            .binary_search_by_key(&place.start, |m| m.start)
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
                let common = self.common_depth(at, m.start);
                (u32::MAX - common, m.depth - common, *index)
            })
            .map(|(index, _)| LabelId(index as u32))?;
        self.joins.borrow_mut().push((at, best));
        Some(best)
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

    /// The names of the labels the scope's sites have read, in the order
    /// they first stand.
    pub(super) fn names_in_order(&self) -> LabelNames {
        let mut uses: Vec<(u32, LabelId)> = self.joins.borrow().clone();
        uses.extend(self.made.iter().enumerate().map(|(index, m)| (m.start, LabelId(index as u32))));
        uses.sort_by_key(|(start, _)| *start);
        let mut seen = std::collections::BTreeSet::new();
        uses.into_iter()
            .filter(|(_, id)| seen.insert(id.0))
            .map(|(_, id)| (self.name(id).into(), id))
            .collect()
    }
}
