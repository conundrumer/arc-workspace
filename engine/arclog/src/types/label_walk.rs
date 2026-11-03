//! The type of a label over its scope: the meet of the types of its sites
//! other than those of `NOT` atoms, or, where those give no type, of the
//! sites of `NOT` atoms, the join over the branches of an `OR` or an `IF`
//! that exports it, and the fault where a meet is empty or a join does not
//! exist.

use super::body_walks::{each_conjunct, each_site_label, each_site_use, use_label};
use super::{Meet, ValueType};

/// A fault of the type of one label in a body.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum LabelFault {
    /// Two sites give the label types with an empty meet.
    EmptyMeet(ValueType, ValueType),
    /// Two branches give the label types with no join.
    NoJoin(ValueType, ValueType),
}

/// The text of `fault` of a label, for a diagnostic that names the label
/// before it.
pub(crate) fn label_fault_message(fault: LabelFault) -> String {
    match fault {
        LabelFault::EmptyMeet(a, b) => format!("stands at sites of the types {a:?} and {b:?}, whose meet is empty"),
        LabelFault::NoJoin(a, b) => format!("takes the types {a:?} and {b:?} from two branches, which have no join"),
    }
}

/// The type that `body` gives `label`, `None` where it gives none, or the
/// fault of that type. `body` is the list of the label's scope, as
/// `scope_lists` gives it.
///
/// The type is the meet, as [`ValueType::meet`] gives it, of the types of
/// every site of the label, at any depth, and a join, as [`ValueType::join`]
/// gives it, comes only between alternatives. A site of a `NOT` atom gives a
/// type only where no site of a positive atom does, since a `NOT` atom tests
/// whether a row with the label's value stands and binds no value; a `NOT`
/// site whose type has an empty meet with the type of any other site is the
/// fault `EmptyMeet`. A constraint over two labels gives each the sites of
/// the other in the list that holds the constraint and in the lists nested
/// in it, and, for a constraint in an `IF`'s test or in an `ALL`'s domain,
/// in that form's then or body as well; `0` gives no type. A `NOT` of a form
/// gives what that form gives. An `OR` gives the join of the types its
/// branches give, and an `ALL` the meet of its domain's and its body's types.
/// An `IF` gives the meet of its test's type with the join of its then and
/// else lists' types, or, where the label is fresh in the test, the meet of
/// its test's and its then's types (`docs/arclog/arclog.md#conditional`).
/// Where a branch of an `OR` makes the label fresh, a branch that holds no
/// label equal to the label takes no part in the `OR`'s join. Where no branch
/// does, a branch that holds no such label lets each value of the label
/// through and gives the join no type, so the label keeps the meet of its
/// other sites' types. A branch that gives the label no type gives that join
/// none. A then or an else list that gives the label no
/// type gives the `IF`'s join none. Where the label is fresh in no part of an
/// `OR` or an `IF`, the type of each branch that takes part, each `OR`
/// branch and the then and the else of an `IF`, has a meet with the type
/// that the label's sites outside the form give it, in the other conjuncts of
/// each list that holds the form, and an empty meet is a fault of that branch,
/// whatever the other branches give. In a list nested in `body`, a label
/// that the list's constraints make equal to the label, and that the
/// constraints of the lists around the list do not, gives the label in the
/// list as well the type that its own sites in the lists around the list
/// give it, outside the conjunct that holds the list.
///
/// A site is one label at an atom's site, at any depth of the site: a bare
/// label at the site's column, a bare label at a column of a type
/// parameter, which names its field, or a label at a site on a record's
/// field, `*A1` of `(:key (:C C) (:A *A1))`. The site has the type that
/// `site_type` gives the atom and the site's column path: the site's column,
/// then the field of each nested site, then, for a bare label at a column
/// of a type parameter, the name it holds.
pub fn label_type(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
) -> Result<Option<ValueType>, LabelFault> {
    label_type_keyed(body, label, site_type, None)
}

/// [`label_type`] for a label of an `INIT` form's input, where `key` is the
/// body of the form's key clause. The key clause is a list around the
/// input's body: a label that a constraint makes equal to a label of the
/// key clause takes the type that the key clause's sites give that label
/// (`docs/arclog/arclog.md#instance`).
pub fn label_type_keyed(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
    key: Option<&crate::program::Body>,
) -> Result<Option<ValueType>, LabelFault> {
    label_type_cached(body, label, site_type, key, &WalkCache::default())
}

/// [`label_type_keyed`] with the facts of the walk that do not depend on
/// the label asked taken from `cache`, which holds them for the walks of
/// every label of one inference that `site_type` types. The walk over every
/// site gives the faults and the type; where a `NOT` atom stands in `body`
/// or in `key`, a walk over the sites of positive atoms gives the type, and
/// the first walk gives it only where the second gives none.
pub(crate) fn label_type_cached(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
    key: Option<&crate::program::Body>,
    cache: &WalkCache,
) -> Result<Option<ValueType>, LabelFault> {
    label_type_mode(body,label,site_type,key,cache,false)
}

/// Storage type of a branch-local binding. A branch producing no value of
/// the label contributes no value type, rather than erasing the types of
/// values produced by other branches. This pass does not infer a domain
/// restriction for a label that passes through an unconstrained branch.
pub(crate) fn label_binding_type_cached(body:&crate::program::Body,label:crate::program::LabelId,site_type:&dyn Fn(&crate::program::Atom,&[crate::program::ColumnName])->Option<ValueType>,key:Option<&crate::program::Body>,cache:&WalkCache)->Result<Option<ValueType>,LabelFault> {
    label_type_mode(body,label,site_type,key,cache,true)
}

fn label_type_mode(body:&crate::program::Body,label:crate::program::LabelId,site_type:&dyn Fn(&crate::program::Atom,&[crate::program::ColumnName])->Option<ValueType>,key:Option<&crate::program::Body>,cache:&WalkCache,binding_types:bool)->Result<Option<ValueType>,LabelFault> {
    let walk = |sites| LabelWalk { label, site_type, asked: vec![label], key, cache, sites, binding_types };
    let all = walk(Sites::All).body_type(body, &[], None, &Outside::Sites(None))?;
    if !cache.holds_negated_atom(body) && !key.is_some_and(|key| cache.holds_negated_atom(key)) {
        return Ok(all);
    }
    Ok(walk(Sites::Positive).body_type(body, &[], None, &Outside::Unchecked)?.or(all))
}

/// The result of [`label_type`] for every label of a body of positive atoms
/// alone, at once, from the type each site of the body gives its label
/// (`None` where a site gives none): the meet of a label's site types, or
/// `None` where one meet is empty, whose fault [`label_type`] gives. A
/// label with no site type has the entry `None`.
pub(crate) fn flat_label_types(sites: impl IntoIterator<Item = (crate::program::LabelId, Option<ValueType>)>) -> Option<crate::hash::StableHashMap<crate::program::LabelId, Option<ValueType>>> {
    let mut types = crate::hash::StableHashMap::<crate::program::LabelId, Option<ValueType>>::default();
    for (label, site) in sites {
        let held = types.entry(label).or_default();
        *held = meet(held.take(), site).ok()?;
    }
    Some(types)
}

/// The type of each label of a scope, or its fault, in the order of the
/// scope's labels.
pub(crate) type TypedLabels = Vec<(crate::program::LabelId, Result<Option<ValueType>, LabelFault>)>;

/// The type `types` gives `label`, where it gives one.
pub(crate) fn typed(types: &[(crate::program::LabelId, Result<Option<ValueType>, LabelFault>)], label: crate::program::LabelId) -> Option<ValueType> {
    match types.iter().find(|(found, _)| *found == label)? {
        (_, Ok(ty)) => ty.clone(),
        (_, Err(_)) => None,
    }
}

/// The types of a scope's labels once a run gives the types of the run
/// before it. `types` are the types `run` gives with no earlier types, and
/// `run` gives the types under the earlier types it is given. `narrows` tells
/// whether a site, read under the types it is given as the earlier types,
/// gives its label a type that the label's type is not under; where none
/// does, a run gives the same types, and is not made. A fault ends the runs.
/// The types of a label only narrow from run to run, so the runs end.
pub(crate) fn settle_label_types(
    mut types: TypedLabels,
    narrows: impl Fn(&TypedLabels) -> bool,
    run: impl Fn(&TypedLabels) -> TypedLabels,
) -> TypedLabels {
    while types.iter().all(|(_, ty)| ty.is_ok()) && narrows(&types) {
        let next = run(&types);
        if next == types {
            break;
        }
        types = next;
    }
    types
}

/// What the walks of the labels of one inference read of a part of the
/// program, which does not depend on the label asked: the type that the
/// sites of an atom give a class of labels, and, for a body, the labels
/// that stand in it, the labels fresh in it, and what it makes by zero.
/// A part is identified by its address. It holds as well the type that a
/// walk of [`LabelWalk::key_type`] or [`LabelWalk::around_type`] gives,
/// under the [`AroundKey`] of all that the walk reads.
#[derive(Default)]
pub(crate) struct WalkCache {
    atoms: std::cell::RefCell<crate::hash::StableHashMap<(usize, Vec<crate::program::LabelId>), Result<Option<ValueType>, LabelFault>>>,
    held: std::cell::RefCell<crate::hash::StableHashMap<usize, std::rc::Rc<crate::hash::StableHashSet<crate::program::LabelId>>>>,
    fresh: std::cell::RefCell<crate::hash::StableHashMap<usize, std::rc::Rc<crate::hash::StableHashSet<crate::program::LabelId>>>>,
    zero_made: std::cell::RefCell<crate::hash::StableHashMap<usize, std::rc::Rc<ZeroMade>>>,
    negated: std::cell::RefCell<crate::hash::StableHashMap<usize, bool>>,
    around: std::cell::RefCell<crate::hash::StableHashMap<AroundKey, Result<Option<ValueType>, LabelFault>>>,
}

/// What a walk of another label, [`LabelWalk::key_type`] or
/// [`LabelWalk::around_type`], reads beyond the walk cache and `site_type`:
/// the label, the labels asked as a set, the sites read, the mode of
/// branches without the label, the key clause's body, and, for a walk
/// around a list, each list around it, innermost first, with its pairs and
/// the index of its conjunct that holds the inner list. A body is
/// identified by its address.
#[derive(PartialEq, Eq, Hash)]
struct AroundKey {
    label: crate::program::LabelId,
    asked: Vec<crate::program::LabelId>,
    positive: bool,
    binding_types: bool,
    key: Option<usize>,
    frames: Option<Vec<(usize, Vec<LabelPair>, usize)>>,
}

impl WalkCache {
    fn held(&self, body: &crate::program::Body) -> std::rc::Rc<crate::hash::StableHashSet<crate::program::LabelId>> {
        let at = body as *const crate::program::Body as usize;
        std::rc::Rc::clone(self.held.borrow_mut().entry(at).or_insert_with(|| std::rc::Rc::new(crate::safety::body_labels(body))))
    }

    fn fresh(&self, body: &crate::program::Body) -> std::rc::Rc<crate::hash::StableHashSet<crate::program::LabelId>> {
        let at = body as *const crate::program::Body as usize;
        std::rc::Rc::clone(self.fresh.borrow_mut().entry(at).or_insert_with(|| std::rc::Rc::new(fresh_labels(body))))
    }

    /// Whether an atom under a `NOT` stands in `body`, at any depth.
    fn holds_negated_atom(&self, body: &crate::program::Body) -> bool {
        let at = body as *const crate::program::Body as usize;
        *self.negated.borrow_mut().entry(at).or_insert_with(|| {
            let mut found = false;
            each_conjunct(body, &mut |conjunct| found |= matches!(conjunct, crate::program::Conjunct::Not(crate::program::Negated::Atom(_))));
            found
        })
    }

    fn zero_made(&self, body: &crate::program::Body) -> std::rc::Rc<ZeroMade> {
        let at = body as *const crate::program::Body as usize;
        std::rc::Rc::clone(self.zero_made.borrow_mut().entry(at).or_insert_with(|| std::rc::Rc::new(ZeroMade::of(body))))
    }

    /// The type of the walk of `key`, which `walk` gives where none is held.
    fn walk(&self, key: AroundKey, walk: impl FnOnce() -> Result<Option<ValueType>, LabelFault>) -> Result<Option<ValueType>, LabelFault> {
        if let Some(found) = self.around.borrow().get(&key) {
            return found.clone();
        }
        let found = walk();
        self.around.borrow_mut().insert(key, found.clone());
        found
    }
}

/// The labels that `list`'s own constraints make equal to `label`, `label`
/// included.
pub(crate) fn list_class(list: &crate::program::Body, label: crate::program::LabelId) -> Vec<crate::program::LabelId> {
    equal_labels(&with_constraints(&[], list), label)
}

/// The list of the scope of a label of `list` that is no head
/// label: the innermost list that holds each of its sites, or, where that
/// list is an `IF`'s test or a list of an `ALL`, or where its sites stand in
/// both the test and the then of an `IF`, the list that holds that form,
/// since a label fresh there is local to the form.
/// For each of `labels`, in their order, the list of its scope. The labels of each
/// conjunct of a list are taken once, and a part of a form is entered once
/// for all the labels that stand in it alone.
pub(crate) fn scope_lists<'a>(list: &'a crate::program::Body, labels: &[crate::program::LabelId]) -> Vec<&'a crate::program::Body> {
    use crate::program::{Body, Conjunct, Negated};
    // The parts of a form, with whether a label that stands only in it takes
    // it as its scope, and the labels each part holds.
    struct Parts<'a> {
        own: Vec<crate::program::LabelId>,
        parts: Vec<(&'a Body, bool, crate::hash::StableHashSet<crate::program::LabelId>)>,
    }
    let held: Vec<crate::hash::StableHashSet<crate::program::LabelId>> = list
        .conjuncts
        .iter()
        .map(|conjunct| {
            let mut labels = crate::hash::StableHashSet::default();
            crate::safety::conjunct_labels(conjunct, &mut labels);
            labels
        })
        .collect();
    let mut parts_of: Vec<Option<Parts<'a>>> = list.conjuncts.iter().map(|_| None).collect();
    let mut result = vec![list; labels.len()];
    // For each conjunct and part, the positions of the labels that it takes.
    let mut groups: Vec<((usize, usize), Vec<usize>)> = Vec::new();
    for (at, label) in labels.iter().enumerate() {
        let mut holders = held.iter().enumerate().filter(|(_, labels)| labels.contains(label)).map(|(i, _)| i);
        let (Some(i), None) = (holders.next(), holders.next()) else { continue };
        let conjunct = &list.conjuncts[i];
        let parts = parts_of[i].get_or_insert_with(|| {
            let mut own = Vec::new();
            crate::safety::own_labels(conjunct, &mut own);
            let mut form = conjunct;
            while let Conjunct::Not(Negated::Form(inner)) = form {
                form = inner;
            }
            let parts: Vec<(&Body, bool)> = match form {
                Conjunct::Or(branches) => branches.iter().map(|branch| (branch.value(), true)).collect(),
                Conjunct::If { test, then, otherwise } => vec![(test.value(), false), (then.value(), true), (otherwise.value(), true)],
                Conjunct::All { domain, body } => vec![(domain.value(), false), (body.value(), false)],
                Conjunct::Atom(_) | Conjunct::Not(_) | Conjunct::Constraint(_) => Vec::new(),
            };
            Parts { own, parts: parts.into_iter().map(|(part, takes)| (part, takes, crate::safety::body_labels(part))).collect() }
        });
        if parts.own.contains(label) {
            continue;
        }
        let mut holding = parts.parts.iter().enumerate().filter(|(_, (_, _, held))| held.contains(label));
        let (Some((k, (_, true, _))), None) = (holding.next(), holding.next()) else { continue };
        match groups.iter_mut().find(|(key, _)| *key == (i, k)) {
            Some((_, members)) => members.push(at),
            None => groups.push(((i, k), vec![at])),
        }
    }
    for ((i, k), members) in groups {
        let part = parts_of[i].as_ref().expect("a conjunct with a group").parts[k].0;
        let inner: Vec<_> = members.iter().map(|&at| labels[at]).collect();
        for (&at, scope) in members.iter().zip(scope_lists(part, &inner)) {
            result[at] = scope;
        }
    }
    result
}

/// The walk of [`label_type`] for `label`, the label asked. `asked` holds
/// `label` and each label whose walk holds this one, whose types the walk
/// does not take from the lists around a list.
struct LabelWalk<'a> {
    label: crate::program::LabelId,
    site_type: &'a dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
    asked: Vec<crate::program::LabelId>,
    /// The body of the key clause of the `INIT` form, a list around every
    /// input's body.
    key: Option<&'a crate::program::Body>,
    cache: &'a WalkCache,
    sites: Sites,
    binding_types:bool,
}

/// The sites of atoms that a walk reads.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Sites {
    /// Every site of an atom, a `NOT` atom's included.
    All,
    /// The sites of the atoms that no `NOT` holds.
    Positive,
}

/// A list around the list a walk is in: the list, the pairs of labels that
/// its constraints and those around it make equal there, the index of its
/// conjunct that holds the inner list, and the list around it.
struct Around<'b> {
    list: &'b crate::program::Body,
    pairs: &'b [LabelPair],
    holder: usize,
    outer: Option<&'b Around<'b>>,
}

/// What a walk of a list checks of the branches of the forms in it.
#[derive(Clone)]
enum Outside {
    /// The walk checks no branch.
    Unchecked,
    /// The walk meets the type of each branch of a form with this type: the
    /// type that the label's sites outside the form give it, `None` where
    /// they give it none.
    Sites(Option<ValueType>),
}

impl Outside {
    /// The outside of the parts of a form, where the label is `fresh` in one
    /// of them, so that the form exports it and the sites outside the form
    /// do not bound its branches.
    fn of_parts(&self, fresh: bool) -> Outside {
        match self {
            Outside::Sites(_) if fresh => Outside::Sites(None),
            outside => outside.clone(),
        }
    }

    /// The fault of a branch of type `branch` whose meet with this type is
    /// empty.
    fn admit(&self, branch: &Option<ValueType>) -> Result<(), LabelFault> {
        match self {
            Outside::Unchecked => Ok(()),
            Outside::Sites(sites) => meet(branch.clone(), sites.clone()).map(|_| ()),
        }
    }
}

impl LabelWalk<'_> {
    /// The type of `body`, where `outer` holds the pairs of labels that the
    /// constraints of the lists around `body` make equal there, and
    /// `around` the list around `body`, none for the list of the label's
    /// scope. `outside` is what the walk checks of the forms in `body`.
    fn body_type(
        &self,
        body: &crate::program::Body,
        outer: &[LabelPair],
        around: Option<&Around<'_>>,
        outside: &Outside,
    ) -> Result<Option<ValueType>, LabelFault> {
        let before = equal_labels(outer, self.label);
        if !self.holds(body, &before) {
            return Ok(None);
        }
        let pairs = with_constraints(outer, body);
        let class = equal_labels(&pairs, self.label);
        let mut ty = self.list_type(body, &pairs, &class, around, None, outside)?;
        for &other in class.iter().filter(|label| !before.contains(label) && !self.asked.contains(label)) {
            if let Some(around) = around {
                ty = meet(ty, self.around_type(other, around)?)?;
            }
            ty = meet(ty, self.key_type(other)?)?;
        }
        Ok(ty)
    }

    /// The type that the sites of `other` give it in the key clause.
    fn key_type(&self, other: crate::program::LabelId) -> Result<Option<ValueType>, LabelFault> {
        let Some(key) = self.key else { return Ok(None) };
        let asked: Vec<_> = self.asked.iter().copied().chain(std::iter::once(other)).collect();
        let memo = self.around_key(other, &asked, Some(key), None);
        self.cache.walk(memo, || {
            let walk = LabelWalk { label: other, site_type: self.site_type, asked, key: None, cache: self.cache, sites: self.sites,binding_types:self.binding_types };
            walk.list_type(key, &[], &[other], None, None, &Outside::Unchecked)
        })
    }

    /// The type that the sites of `other` give it in `around` and the lists
    /// around it, outside the conjunct of each that holds the inner list.
    fn around_type(&self, other: crate::program::LabelId, around: &Around<'_>) -> Result<Option<ValueType>, LabelFault> {
        let asked: Vec<_> = self.asked.iter().copied().chain(std::iter::once(other)).collect();
        let mut frames = Vec::new();
        let mut frame = Some(around);
        while let Some(list) = frame {
            frames.push((list.list as *const crate::program::Body as usize, list.pairs.to_vec(), list.holder));
            frame = list.outer;
        }
        let memo = self.around_key(other, &asked, self.key, Some(frames));
        self.cache.walk(memo, || {
            let walk = LabelWalk { label: other, site_type: self.site_type, asked, key: self.key, cache: self.cache, sites: self.sites,binding_types:self.binding_types };
            let mut ty = None;
            let mut frame = Some(around);
            while let Some(list) = frame {
                let class = equal_labels(list.pairs, other);
                ty = meet(ty, walk.list_type(list.list, list.pairs, &class, list.outer, Some(list.holder), &Outside::Unchecked)?)?;
                frame = list.outer;
            }
            Ok(ty)
        })
    }

    /// The [`AroundKey`] of a walk of `other` with the labels `asked`, over
    /// the key clause's body `key`, and around `frames`, where it is given.
    fn around_key(&self, other: crate::program::LabelId, asked: &[crate::program::LabelId], key: Option<&crate::program::Body>, frames: Option<Vec<(usize, Vec<LabelPair>, usize)>>) -> AroundKey {
        let mut asked = asked.to_vec();
        asked.sort_unstable_by_key(|label| label.0);
        asked.dedup();
        AroundKey {
            label: other,
            asked,
            positive: self.sites == Sites::Positive,
            binding_types: self.binding_types,
            key: key.map(|key| key as *const crate::program::Body as usize),
            frames,
        }
    }

    /// The meet of the types of the conjuncts of `list`, other than the one
    /// at `skip`, where `pairs` and `class` are as [`LabelWalk::conjunct_type`]
    /// takes them, and `outer` is the list around `list`. Where `outside` is
    /// [`Outside::Sites`], the walk reads each conjunct that holds a form a
    /// second time, with the meet of the other conjuncts' types and the
    /// outside of `list` as the outside of that form's branches.
    fn list_type(
        &self,
        list: &crate::program::Body,
        pairs: &[LabelPair],
        class: &[crate::program::LabelId],
        outer: Option<&Around<'_>>,
        skip: Option<usize>,
        outside: &Outside,
    ) -> Result<Option<ValueType>, LabelFault> {
        if !self.holds(list, class) {
            return Ok(None);
        }
        let mut ty = None;
        let mut types = Vec::new();
        for (holder, conjunct) in list.conjuncts.iter().enumerate().filter(|(index, _)| Some(*index) != skip) {
            if !self.conjunct_holds(conjunct, class) {
                continue;
            }
            let here = Around { list, pairs, holder, outer };
            let conjunct_type = self.conjunct_type(conjunct, pairs, class, &here, &Outside::Unchecked)?;
            ty = meet(ty, conjunct_type.clone())?;
            types.push((holder, conjunct_type));
        }
        if let Outside::Sites(sites) = outside {
            for &(holder, _) in types.iter().filter(|(holder, _)| holds_form(&list.conjuncts[*holder])) {
                let rest = types.iter().filter(|(other, _)| *other != holder).try_fold(sites.clone(), |rest, (_, other)| meet(rest, other.clone()))?;
                let here = Around { list, pairs, holder, outer };
                self.conjunct_type(&list.conjuncts[holder], pairs, class, &here, &Outside::Sites(rest))?;
            }
        }
        Ok(ty)
    }

    /// The type of `conjunct`, a conjunct of a list whose constraints and
    /// those around it give `pairs`, and the class of the label asked there.
    /// `here` is that list, with `conjunct` as the holder of the lists
    /// nested in it. `outside` is what the walk checks of the forms in
    /// `conjunct`, and, where it is [`Outside::Sites`], the type that the
    /// label's sites outside `conjunct` give it.
    fn conjunct_type(
        &self,
        conjunct: &crate::program::Conjunct,
        pairs: &[LabelPair],
        class: &[crate::program::LabelId],
        here: &Around<'_>,
        outside: &Outside,
    ) -> Result<Option<ValueType>, LabelFault> {
        use crate::program::{Conjunct, Negated};
        match conjunct {
            Conjunct::Not(Negated::Atom(_)) if self.sites == Sites::Positive => Ok(None),
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                let atom = atom.value();
                let mut held = class.to_vec();
                held.sort_unstable_by_key(|label| label.0);
                self.cache.atoms.borrow_mut().entry((atom as *const crate::program::Atom as usize, held)).or_insert_with(|| self.atom_type(atom, class)).clone()
            }
            Conjunct::Not(Negated::Form(form)) => self.conjunct_type(form, pairs, class, here, outside),
            Conjunct::Or(branches) => {
                let holds = |branch: &crate::program::Body| {
                    let labels = self.cache.held(branch);
                    class.iter().any(|label| labels.contains(label))
                };
                let made_here = branches.iter().any(|branch| self.fresh_in(branch.value()));
                let taking = branches
                    .iter()
                    .filter(|branch| (!made_here || holds(branch.value())) && !self.makes_only_by_zero(branch.value(), class));
                let inside = outside.of_parts(made_here);
                join_branches(taking.map(|branch| self.branch_type(branch.value(), pairs, here, &inside)).collect::<Result<Vec<_>, _>>()?,self.binding_types)
            }
            Conjunct::If { test, then, otherwise } => {
                let inside = outside.of_parts(self.fresh_in_any(&[test.value(), then.value(), otherwise.value()]));
                let test_type = self.body_type(test.value(), pairs, Some(here), &inside)?;
                let then_type = self.branch_type(then.value(), &with_constraints(pairs, test.value()), here, &inside)?;
                if self.fresh_in(test.value()) {
                    return meet(test_type, then_type);
                }
                let otherwise_type = (!self.makes_only_by_zero(otherwise.value(), class)).then(|| self.branch_type(otherwise.value(), pairs, here, &inside)).transpose()?;
                meet(test_type, join_branches([then_type].into_iter().chain(otherwise_type),self.binding_types)?)
            }
            Conjunct::All { domain, body } => {
                let inside = outside.of_parts(self.fresh_in_any(&[domain.value(), body.value()]));
                let domain_type = self.body_type(domain.value(), pairs, Some(here), &inside)?;
                meet(domain_type, self.body_type(body.value(), &with_constraints(pairs, domain.value()), Some(here), &inside)?)
            }
            Conjunct::Constraint(_) => Ok(None),
        }
    }

    /// The type of `branch`, a branch of the form that `here` holds, whose
    /// meet with `outside` is not empty.
    fn branch_type(
        &self,
        branch: &crate::program::Body,
        pairs: &[LabelPair],
        here: &Around<'_>,
        outside: &Outside,
    ) -> Result<Option<ValueType>, LabelFault> {
        let ty = self.body_type(branch, pairs, Some(here), outside)?;
        outside.admit(&ty)?;
        Ok(ty)
    }

    /// The meet of the types that the sites of `atom` give the labels of `class`.
    fn atom_type(&self, atom: &crate::program::Atom, class: &[crate::program::LabelId]) -> Result<Option<ValueType>, LabelFault> {
        let mut ty = None;
        for site in atom.sites.iter() {
            if !site_holds_class(site, class) {
                continue;
            }
            let mut path = Vec::new();
            let mut fault = None;
            each_site_label(site, &mut path, &mut |use_, path| {
                if fault.is_some() || !use_label(use_).is_some_and(|l| class.contains(&l)) {
                    return;
                }
                match meet(ty.take(), (self.site_type)(atom, path)) {
                    Ok(met) => ty = met,
                    Err(err) => fault = Some(err),
                }
            });
            if let Some(err) = fault {
                return Err(err);
            }
        }
        Ok(ty)
    }

    /// Whether a label of `class` stands in `body`, at any depth.
    ///
    /// A body where none stands gives the label asked no type and no fault,
    /// whatever its outside: no site there is of a label of `class`, and no
    /// constraint there makes a label equal to one of `class`, so the class
    /// in each list nested in it is `class`, and each of its conjuncts gives
    /// no type.
    fn holds(&self, body: &crate::program::Body, class: &[crate::program::LabelId]) -> bool {
        let labels = self.cache.held(body);
        class.iter().any(|label| labels.contains(label))
    }

    /// Whether a label of `class` stands in `conjunct`, at any depth. A
    /// conjunct where none stands gives no type and no fault, as
    /// [`LabelWalk::holds`] gives for a body.
    fn conjunct_holds(&self, conjunct: &crate::program::Conjunct, class: &[crate::program::LabelId]) -> bool {
        use crate::program::{Conjunct, Negated};
        match conjunct {
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => atom.value().sites.iter().any(|site| site_holds_class(site, class)),
            Conjunct::Not(Negated::Form(form)) => self.conjunct_holds(form, class),
            Conjunct::Or(branches) => branches.iter().any(|branch| self.holds(branch.value(), class)),
            Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().any(|part| self.holds(part.value(), class)),
            Conjunct::All { domain, body } => [domain, body].into_iter().any(|part| self.holds(part.value(), class)),
            Conjunct::Constraint(_) => false,
        }
    }

    /// Whether the label asked is fresh at a site or a constraint of
    /// `body`, at any depth.
    fn fresh_in(&self, body: &crate::program::Body) -> bool {
        self.cache.fresh(body).contains(&self.label)
    }

    /// Whether the label asked is fresh in any of `parts`.
    fn fresh_in_any(&self, parts: &[&crate::program::Body]) -> bool {
        parts.iter().any(|part| self.fresh_in(part))
    }

    /// Whether `branch` makes the label of `class` only by a `(= X 0)`, with
    /// the label at no site of an atom in `branch`: such a branch adds no
    /// type to the label, as a clause whose head label only `(= *X 0)` gives a
    /// type adds none.
    fn makes_only_by_zero(&self, branch: &crate::program::Body, class: &[crate::program::LabelId]) -> bool {
        let ZeroMade { zeroed, at_sites } = &*self.cache.zero_made(branch);
        zeroed.iter().any(|(label, _)| class.contains(label)) && !at_sites.iter().any(|label| class.contains(label))
    }
}

/// Whether `conjunct` is a form, or a `NOT` of one.
fn holds_form(conjunct: &crate::program::Conjunct) -> bool {
    use crate::program::{Conjunct, Negated};
    !matches!(conjunct, Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_))
}

/// The labels that are fresh at a site or a constraint of `body`, at any depth.
fn fresh_labels(body: &crate::program::Body) -> crate::hash::StableHashSet<crate::program::LabelId> {
    use crate::program::{Conjunct, LabelUse, Operand};
    let mut fresh = crate::hash::StableHashSet::default();
    each_conjunct(body, &mut |conjunct| match conjunct {
        Conjunct::Constraint(c) => {
            let second = match c.second {
                Operand::Label(label) => Some(label),
                Operand::Zero => None,
            };
            fresh.extend(std::iter::once(c.first).chain(second).filter(|used| used.fresh).map(|used| used.label));
        }
        _ => {
            if let Some(atom) = conjunct.atom() {
                for site in atom.value().sites.iter() {
                    each_site_use(site, &mut |use_| {
                        if let LabelUse::Fresh(label) = use_ {
                            fresh.insert(label);
                        }
                    });
                }
            }
        }
    });
    fresh
}

/// Whether `label` is fresh inside an `OR`, an `IF` or an `ALL` nested in
/// `list`, at any depth. Where it is not, and the form has no key clause,
/// the walk of `list` for `label` reads the label only through its class,
/// so every label of the class takes the one type.
pub(crate) fn fresh_in_nested_form(list: &crate::program::Body, label: crate::program::LabelId, cache: &WalkCache) -> bool {
    use crate::program::{Conjunct, Negated};
    list.conjuncts.iter().any(|conjunct| {
        let mut form = conjunct;
        while let Conjunct::Not(Negated::Form(inner)) = form {
            form = inner;
        }
        match form {
            Conjunct::Or(branches) => branches.iter().any(|branch| cache.fresh(branch.value()).contains(&label)),
            Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().any(|part| cache.fresh(part.value()).contains(&label)),
            Conjunct::All { domain, body } => [domain, body].into_iter().any(|part| cache.fresh(part.value()).contains(&label)),
            Conjunct::Atom(_) | Conjunct::Not(_) | Conjunct::Constraint(_) => false,
        }
    })
}

/// Whether a label use at `site`, at any depth, is of a label of `class`.
fn site_holds_class(site: &crate::program::Site, class: &[crate::program::LabelId]) -> bool {
    let mut holds = false;
    each_site_use(site, &mut |use_| holds |= use_label(use_).is_some_and(|l| class.contains(&l)));
    holds
}


/// The meet of two types of one label, either of which may be absent.
pub(crate) fn meet(a: Option<ValueType>, b: Option<ValueType>) -> Result<Option<ValueType>, LabelFault> {
    match (a, b) {
        (Some(a), Some(b)) => match a.meet(&b) {
            Meet::Type(ty) => Ok(Some(ty)),
            Meet::Empty => Err(LabelFault::EmptyMeet(a, b)),
        },
        (a, b) => Ok(a.or(b)),
    }
}

/// The labels that a body makes by `(= X 0)`, each with whether the
/// constraint makes it fresh, and the labels that stand at a site of an
/// atom of the body, at any depth.
pub(crate) struct ZeroMade {
    pub zeroed: Vec<(crate::program::LabelId, bool)>,
    pub at_sites: Vec<crate::program::LabelId>,
}

impl ZeroMade {
    pub(crate) fn of(body: &crate::program::Body) -> Self {
        use crate::program::{Conjunct, Constraint, ConstraintOp, Operand};
        let mut made = ZeroMade { zeroed: Vec::new(), at_sites: Vec::new() };
        each_conjunct(body, &mut |conjunct| match conjunct {
            Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) => made.zeroed.push((first.label, first.fresh)),
            _ => {
                if let Some(atom) = conjunct.atom() {
                    for site in atom.value().sites.iter() {
                        each_site_use(site, &mut |use_| made.at_sites.extend(use_label(use_)));
                    }
                }
            }
        });
        made
    }
}

/// The join of the types that branches give one label, or `None` where a
/// branch gives it none.
fn join_branches(branches: impl IntoIterator<Item = Option<ValueType>>,binding_types:bool) -> Result<Option<ValueType>, LabelFault> {
    let mut joined: Option<ValueType> = None;
    for branch in branches {
        let Some(ty) = branch else { if binding_types {continue;} else {return Ok(None);} };
        joined = Some(match joined {
            None => ty,
            Some(prev) => prev.join(&ty).ok_or_else(|| LabelFault::NoJoin(prev.clone(), ty.clone()))?,
        });
    }
    Ok(joined)
}

/// Two labels that a constraint makes equal.
type LabelPair = (crate::program::LabelId, crate::program::LabelId);

/// `outer` and the pairs of labels of each constraint of `list` itself, a
/// constraint under a `NOT` included, and no constraint of a list nested in
/// `list`.
fn with_constraints(outer: &[LabelPair], list: &crate::program::Body) -> Vec<LabelPair> {
    use crate::program::{constraint_second, Conjunct, Negated};
    let mut pairs = outer.to_vec();
    for conjunct in list.conjuncts.iter() {
        let mut conjunct = conjunct;
        while let Conjunct::Not(Negated::Form(inner)) = conjunct {
            conjunct = inner;
        }
        if let Conjunct::Constraint(k) = conjunct {
            if let Some(second) = constraint_second(k) {
                pairs.push((k.first.label, second.label));
            }
        }
    }
    pairs
}

/// `label` and each label that `pairs` make equal to it, directly or
/// through other labels.
fn equal_labels(pairs: &[LabelPair], label: crate::program::LabelId) -> Vec<crate::program::LabelId> {
    let mut class = vec![label];
    let mut grown = true;
    while grown {
        grown = false;
        for &(a, b) in pairs {
            match (class.contains(&a), class.contains(&b)) {
                (true, false) => class.push(b),
                (false, true) => class.push(a),
                _ => continue,
            }
            grown = true;
        }
    }
    class
}
