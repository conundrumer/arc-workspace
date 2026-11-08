//! The atoms that may come next at a state of a decode.

use std::hash::Hasher;
use std::sync::Arc;

use super::state::{AtomPlace, State};
use super::Decoder;
use crate::hash::{StableHash, StableHashMap, StableHasher};
use crate::program::RelationRef;
use crate::stream::{Control, Token};

/// What [`Decoder::candidate_atoms`] gives.
#[derive(Debug, Default)]
pub struct CandidateAtoms {
    /// The tokens of each atom, by vocabulary id, from the token that opens
    /// it through its last site, a `NOT` first where one stands before it.
    pub atoms: Vec<Box<[u32]>>,
    /// The states whose candidates the walk checked.
    pub states: usize,
    /// Whether the walk stopped at its limit, with atoms left to find.
    pub truncated: bool,
}

/// The ids of the tokens of a kind, in ascending order, for one walk.
struct Tokens {
    /// The tokens that open an atom.
    opening: Vec<u32>,
    not: Option<u32>,
    /// The column tokens, by position.
    columns: Vec<u32>,
    /// The labels, `*`, `^` and `0`.
    values: Vec<u32>,
    /// Each token that is no column and no value, and so closes an atom: the
    /// tokens that open one first, whose check reads the least.
    closing: Vec<u32>,
    end: Option<u32>,
    /// What may stand after a site's column, in ascending order of id.
    ascending_after_site: Vec<u32>,
    /// The settings of the decode that give the ids of the tokens or that a check reads.
    settings: String,
}

/// The most verdicts that the process holds for the lib's relations and the
/// fact relations.
const SHARED_VERDICTS: usize = 1 << 22;

/// A hash of the engine's sources and its lib, in 16 digits.
const SOURCES_HASH: &str = env!("ARCLOG_SOURCES_HASH");

/// The verdicts of the atoms of the lib's relations and of the fact relations,
/// which read no program and no task: the sessions of the process share them.
/// A verdict that may read a task's rows stands apart ([`Decoder::atom_place_walk`]).
fn shared_verdicts() -> &'static std::sync::Mutex<crate::hash::StableHashMap<u128, HeldVerdict>> {
    static HELD: std::sync::OnceLock<std::sync::Mutex<crate::hash::StableHashMap<u128, HeldVerdict>>> = std::sync::OnceLock::new();
    HELD.get_or_init(Default::default)
}

/// The verdicts that the process holds for the lib's relations and the fact
/// relations, as bytes for [`add_atom_verdicts`] in a process of the same build
/// of the engine, which the bytes name.
pub fn atom_verdicts() -> Vec<u8> {
    let held = shared_verdicts().lock().expect("the atom verdicts are not poisoned");
    let mut bytes = Vec::with_capacity(16 + held.len() * 26);
    bytes.extend_from_slice(SOURCES_HASH.as_bytes());
    for (key, verdict) in held.iter() {
        bytes.extend_from_slice(&key.to_le_bytes());
        match verdict {
            HeldVerdict::Value { admitted, effort } => {
                bytes.push(u8::from(*admitted));
                bytes.extend_from_slice(&effort.to_le_bytes());
            }
            HeldVerdict::Place(verdict) => {
                bytes.push(2 + u8::from(verdict.place == AtomPlace::Value) + 2 * u8::from(verdict.closes));
                bytes.extend_from_slice(&verdict.effort.to_le_bytes());
                bytes.extend_from_slice(&(verdict.next.len() as u32).to_le_bytes());
                verdict.next.iter().for_each(|id| bytes.extend_from_slice(&id.to_le_bytes()));
            }
        }
    }
    bytes
}

/// Adds the verdicts that [`atom_verdicts`] gave in this build of the engine, and
/// gives the count of them. `None` where the bytes are not whole or another
/// build gave them, since a verdict holds for the checks that gave it.
pub fn add_atom_verdicts(bytes: &[u8]) -> Option<usize> {
    if bytes.get(..SOURCES_HASH.len())? != SOURCES_HASH.as_bytes() {
        return None;
    }
    let mut held = shared_verdicts().lock().expect("the atom verdicts are not poisoned");
    let mut at = SOURCES_HASH.len();
    let mut count = 0;
    let take = |at: &mut usize, len: usize| -> Option<&[u8]> {
        let found = bytes.get(*at..*at + len)?;
        *at += len;
        Some(found)
    };
    while at < bytes.len() {
        let key = u128::from_le_bytes(take(&mut at, 16)?.try_into().ok()?);
        let tag = take(&mut at, 1)?[0];
        let verdict = match tag {
            0 | 1 => HeldVerdict::Value { admitted: tag == 1, effort: u64::from_le_bytes(take(&mut at, 8)?.try_into().ok()?) },
            2..=5 => {
                let effort = u64::from_le_bytes(take(&mut at, 8)?.try_into().ok()?);
                let len = u32::from_le_bytes(take(&mut at, 4)?.try_into().ok()?) as usize;
                let next = take(&mut at, len * 4)?.chunks_exact(4).map(|id| u32::from_le_bytes(id.try_into().expect("four bytes"))).collect();
                let place = if (tag - 2) % 2 == 1 { AtomPlace::Value } else { AtomPlace::Sites };
                HeldVerdict::Place(Arc::new(AtomVerdict { place, closes: tag >= 4, next, effort }))
            }
            _ => return None,
        };
        held.insert(key, verdict);
        count += 1;
    }
    Some(count)
}

/// What the checks give at a place in an atom, which an atom of the same shape shares.
#[derive(Debug)]
pub(crate) struct AtomVerdict {
    place: AtomPlace,
    /// Whether a token closes the atom here.
    closes: bool,
    /// The ids of the column tokens and the `END` that may come next here.
    next: Box<[u32]>,
    /// The effort that the checks charged to the request to give this verdict,
    /// which a read of the verdict charges again.
    effort: u64,
}

/// A verdict that the walk keeps for a key.
#[derive(Clone, Debug)]
pub(crate) enum HeldVerdict {
    /// The verdict at a place.
    Place(Arc<AtomVerdict>),
    /// Whether a value of a shape may come next at a place, and the effort
    /// that the checks charged to the request to give that verdict, which a
    /// read of the verdict charges again.
    Value { admitted: bool, effort: u64 },
}

/// The shape of each value token at a state where an atom opens: what the
/// checks read of a token, so that two tokens of one shape, at one place of
/// atoms of one shape, share a verdict.
struct Shapes {
    /// The count of the labels that stand before the atom.
    labels: u32,
    /// The shape of each of those labels, by its id.
    kinds: Vec<u64>,
}

const COLUMN_SHAPE: u64 = 1 << 62;
const HELD_SHAPE: u64 = 1 << 58;
const AGAIN_SHAPE: u64 = 1 << 61;
const FRESH_SHAPE: u64 = 1;
const KEY_SHAPE: u64 = 2;

impl Shapes {
    fn of(&self, token: &Token) -> u64 {
        match token {
            Token::Column(column) => COLUMN_SHAPE | u64::from(*column),
            Token::Label(label) if *label < self.labels => self.kinds[*label as usize],
            Token::Label(label) => AGAIN_SHAPE | u64::from(*label - self.labels),
            Token::Control(Control::Fresh) => FRESH_SHAPE,
            Token::Control(Control::Key) => KEY_SHAPE,
            Token::Control(Control::Zero) => 3,
            Token::Control(Control::End) => 4,
            _ => 5,
        }
    }
}

/// One walk of the atoms of one relation.
struct AtomWalk<'t> {
    tokens: &'t Tokens,
    shapes: &'t Shapes,
    /// What the verdicts of the walk's atoms read beyond their tokens.
    context: StableHash,
    /// The tokens of the atom so far, which `base` of them precede its first site.
    path: Vec<u32>,
    /// The shape of each token after the relation's.
    shape: Vec<u64>,
    /// A state at each length of `shape`, where the walk holds one.
    states: Vec<Option<State>>,
    limit: usize,
    /// The atoms of the relation that the body holds: whether each is negated,
    /// and its sites. A check reads whether an atom repeats a conjunct.
    priors: Vec<(bool, Vec<(u32, u32)>)>,
    /// The column and the label of each site of the atom so far.
    sites: Vec<(u32, u32)>,
    /// Whether the walk's atom is negated.
    negated: bool,
    /// The last field written of the record at the site in progress.
    field: Option<u32>,
}

impl AtomWalk<'_> {
    /// The shape of `token` at this place of the atom. A check reads whether a
    /// site holds the label of an earlier site, so a label that the atom holds
    /// already has a shape of that place.
    fn shape_of(&self, token: &Token) -> u64 {
        let shape = self.shapes.of(token);
        let Token::Label(label) = token else { return shape };
        match self.sites.iter().position(|(_, held)| held == label) {
            Some(at) => {
                let mut hasher = StableHasher::new();
                hasher.write_u64(shape);
                hasher.write_usize(at);
                hasher.finish() | HELD_SHAPE
            }
            None => shape,
        }
    }

    /// How the atom so far stands to the atoms of its relation in the body:
    /// for each sign, the same sign and the other, whether one holds each of
    /// its sites, in any order, and whether one holds those sites alone.
    fn repeats(&self) -> u8 {
        let mut flags = 0;
        for (negated, sites) in &self.priors {
            let bit = if *negated == self.negated { 0 } else { 2 };
            if self.sites.iter().all(|site| sites.contains(site)) {
                flags |= 1 << bit;
                if sites.len() == self.sites.len() {
                    flags |= 2 << bit;
                }
            }
        }
        flags
    }
}

impl Decoder<'_> {
    /// The atoms that may come next at this state: each atom that a walk of
    /// the masks writes from here, as a relation with one value at each site
    /// and its sites in ascending order of their columns, where the mask after
    /// its last site admits a token that closes it. The atoms come in the order
    /// of a walk that takes the tokens of a mask in ascending order of their
    /// ids, an atom before the atoms that add sites to it.
    ///
    /// The checks of one atom read what its tokens spell, and of the labels
    /// before it their types and whether they are bound, so the walk asks them
    /// once for each shape of an atom ([`Shapes`]), and each later atom of that
    /// shape takes the verdict. The walk asks at most `limit` times.
    pub fn candidate_atoms(&self, limit: usize) -> CandidateAtoms {
        let _request = self.begin_request();
        let mut found = CandidateAtoms::default();
        let vocabulary = self.vocabulary();
        let mut tokens = Tokens { opening: Vec::new(), not: None, columns: Vec::new(), values: Vec::new(), closing: Vec::new(), end: None, ascending_after_site: Vec::new(), settings: { let settings = &self.context.settings; format!("{:?}", (&settings.vocabulary, &settings.caps, settings.check_copies, settings.rule_tests)) } };
        for id in 0..vocabulary.len() as u32 {
            match vocabulary.token(id).expect("an id of the vocabulary") {
                Token::Relation(_) | Token::Fact(_) | Token::Lib(_) => tokens.opening.push(id),
                Token::Column(_) => tokens.columns.push(id),
                Token::Label(_) | Token::Control(Control::Fresh | Control::Key | Control::Zero) => tokens.values.push(id),
                Token::Control(Control::Not) => tokens.not = Some(id),
                Token::Control(Control::End) => tokens.end = Some(id),
                _ => {}
            }
        }
        tokens.closing = tokens.opening.iter().copied().chain((0..vocabulary.len() as u32).filter(|id| !tokens.opening.contains(id) && !tokens.columns.contains(id) && !tokens.values.contains(id))).collect();
        tokens.ascending_after_site = tokens.values.iter().chain(&tokens.columns).chain(&tokens.end).copied().collect();
        tokens.ascending_after_site.sort_unstable();
        let mut walker = self.clone();
        walker.held = Default::default();
        walker.before = None;
        let mut opening = tokens.opening.clone();
        opening.extend(tokens.not);
        opening.sort_unstable();
        let start = walker.mask_over(opening.iter().copied());
        found.states += 1;
        for &id in &opening {
            let Some((next, _)) = start.steps.get(&id) else { continue };
            if Some(id) == tokens.not {
                walker.at(next.clone(), |walker| {
                    let inner = walker.mask_over(tokens.opening.iter().copied());
                    found.states += 1;
                    for &relation in &tokens.opening {
                        let Some((atom, _)) = inner.steps.get(&relation) else { continue };
                        walker.relation_atoms(&tokens, &[id, relation], atom.clone(), limit, &mut found);
                    }
                });
            } else {
                walker.relation_atoms(&tokens, &[id], next.clone(), limit, &mut found);
            }
        }
        let gauges = self.request_work();
        let (gauges, states, limit) = (gauges.gauges(), found.states as u64, limit as u64);
        if found.truncated {
            gauges.hit(crate::eval::Gauge::AtomStates, states, limit);
        } else {
            gauges.note(crate::eval::Gauge::AtomStates, states, limit);
        }
        found
    }

    /// What identifies this state to a reader of its candidate atoms: at one
    /// task session, equal keys give equal atoms and equal tables. `None` where a
    /// form takes no key.
    pub fn state_key(&self) -> Option<u128> {
        let (program, open) = self.state.partial()?;
        let mut hasher = StableHasher::new();
        if let Some((last, finished)) = program.value().forms.split_last() {
            for form in finished {
                hasher.write(&super::prefix_key::key(form, None)?);
            }
            hasher.write(&super::prefix_key::key(last, open.as_ref())?);
        }
        self.state.atom_context(true, &mut hasher);
        hasher.write_u32(self.state.label_count());
        Some(hasher.finish128().0)
    }

    /// Runs `body` with the decode at `state`, and puts the state back.
    fn at(&mut self, state: State, body: impl FnOnce(&mut Self)) {
        let held = std::mem::replace(&mut self.state, state);
        // The decode's path is not the path of `state`, so no mask of its context stands for it.
        let path = self.path.take();
        body(self);
        self.state = held;
        self.path = path;
    }

    /// The atoms of the relation that the tokens `opening` open, which leave the decode at `state`.
    fn relation_atoms(&mut self, tokens: &Tokens, opening: &[u32], state: State, limit: usize, found: &mut CandidateAtoms) {
        if state.atom_place().is_none() {
            return;
        }
        let (shapes, each) = self.with_state_shapes(&state);
        let mut hasher = StableHasher::new();
        // A read of a program's relation can read an output of the form in progress, whose checks read the rest of the form.
        let reads_program = opening.last().is_some_and(|id| matches!(self.vocabulary().token(*id), Some(Token::Relation(_))));
        state.atom_context(reads_program, &mut hasher);
        hasher.write(tokens.settings.as_bytes());
        // A rule that reads whether two labels stand in one grid reads what no shape holds.
        let reads_grids = opening.last().and_then(|id| match self.vocabulary().token(*id) {
            Some(Token::Lib(name)) => self.context.registry.algebra_relation(name),
            _ => None,
        }).is_some_and(|relation| relation.rules.iter().any(|rule| !rule.same_frame.is_empty()));
        if !each || reads_grids {
            // A label with its id for its shape means what this form makes it mean.
            if let Some((program, _)) = state.partial() {
                if let Some(form) = program.value().forms.last() {
                    hasher.write(format!("{form:?}").as_bytes());
                }
            }
        }
        for &id in opening {
            hasher.write_u32(id);
        }
        let priors = state.prior_atoms();
        let negated = opening.len() > 1;
        let mut walk = AtomWalk { tokens, shapes: &shapes, context: hasher.finish128(), path: opening.to_vec(), shape: Vec::new(), states: vec![Some(state)], limit, priors, sites: Vec::new(), negated, field: None };
        self.atom_place_walk(&mut walk, None, found);
    }

    /// The shapes of the labels at `state`, which an atom just opened, and whether each has more than its id.
    fn with_state_shapes(&mut self, state: &State) -> (Shapes, bool) {
        let mut kinds = None;
        let opened = state.clone();
        self.at(opened, |walker| {
            kinds = Some(walker.with_checks_at_state(|checks| {
                let column_type = |relation: &RelationRef, column: &crate::program::ColumnName| walker.fixed_column_type(checks, relation, column);
                walker.state.label_shapes(walker.context.registry, &column_type)
            }));
        });
        let (kinds, each) = kinds.expect("the body ran");
        (Shapes { labels: kinds.len() as u32, kinds }, each)
    }

    /// A state at the place that `walk` stands at, made from the nearest that it
    /// holds; none where a check refuses a token that an atom of its shape passed.
    fn state_of_walk(&mut self, walk: &mut AtomWalk<'_>) -> Option<State> {
        // The effort of a step was charged where the verdict of the place before it was given, or is held in that verdict, so making the state again charges none.
        crate::eval::unmetered_effort(|| {
            let mut from = walk.states.len() - 1;
            while walk.states[from].is_none() {
                from -= 1;
            }
            let first = walk.path.len() - walk.shape.len();
            for at in from..walk.shape.len() {
                let token = self.vocabulary().token(walk.path[first + at]).expect("an id of the vocabulary").clone();
                let state = walk.states[at].clone().expect("the state before it");
                let mut next = None;
                self.at(state, |walker| next = Some(walker.next_state(&token)));
                walk.states[at + 1] = Some(next.expect("the body ran").ok()?.0);
            }
            walk.states[walk.shape.len()].clone()
        })
    }

    /// The atoms that hold the tokens of `walk`, at the place it stands at. A site's column stands above `floor`.
    fn atom_place_walk(&mut self, walk: &mut AtomWalk<'_>, floor: Option<u32>, found: &mut CandidateAtoms) {
        if found.states >= walk.limit {
            found.truncated = true;
            return;
        }
        let mut hasher = StableHasher::new();
        hasher.write_u128(walk.context.0);
        for &shape in &walk.shape {
            hasher.write_u64(shape);
        }
        hasher.write_u8(walk.repeats());
        let node = hasher.finish128().0;
        let relation = walk.path[walk.path.len() - walk.shape.len() - 1];
        let shared = !matches!(self.vocabulary().token(relation), Some(Token::Relation(_)));
        let tokens = walk.tokens;
        let mut steps: StableHashMap<u32, State> = StableHashMap::default();
        let work = self.request_work();
        // A read of a verdict charges the effort that its checks charged, as a hit in a cache does; where that would pass the effort guard, the checks run again and stop where they stop with no verdict held.
        let held = self.atom_verdict_held(shared, node).filter(|held| match held {
            HeldVerdict::Place(verdict) => work.fits_effort(verdict.effort),
            HeldVerdict::Value { .. } => false,
        });
        let verdict = match held {
            Some(HeldVerdict::Place(verdict)) => {
                let _ = work.charge_effort(verdict.effort);
                verdict
            }
            _ => {
                found.states += 1;
                let Some(here) = self.state_of_walk(walk) else { return };
                let place = here.atom_place().expect("a place in an open atom");
                let mut made = None;
                let ((), effort) = work.effort_of(|| self.at(here, |walker| {
                    made = Some(if place == AtomPlace::Sites {
                        // The token that opens an atom reads no task. A token that closes a `DET` reads the rows of its task.
                        let by_atom = walker.mask_first(tokens.opening.iter().copied());
                        let closes = by_atom || walker.mask_first(tokens.closing.iter().copied());
                        let reads_task = !by_atom && walker.state.closes_a_det() && (closes || [Control::End, Control::Set, Control::One].into_iter().any(|control| matches!(walker.next_state(&Token::Control(control)), Err(super::Refusal::DetAdmission(_)))));
                        let above = floor.map_or(0, |floor| floor as usize + 1);
                        (closes, !reads_task, walker.mask_over(tokens.columns[above.min(tokens.columns.len())..].iter().copied()))
                    } else {
                        (false, true, walker.mask_over(tokens.columns.iter().chain(&tokens.end).copied()))
                    });
                }));
                let (closes, reads_no_task, mask) = made.expect("the body ran");
                let mut next: Vec<u32> = mask.steps.keys().copied().collect();
                next.sort_unstable();
                steps.extend(mask.steps.into_iter().map(|(id, (state, _))| (id, state)));
                let verdict = Arc::new(AtomVerdict { place, closes, next: next.into(), effort });
                // A verdict that a stop at the effort guard cut short is the verdict of no place.
                if (reads_no_task || !shared) && !work.is_effort_exhausted() {
                    self.atom_verdict_keep(shared, node, HeldVerdict::Place(Arc::clone(&verdict)));
                }
                verdict
            }
        };
        if verdict.closes {
            found.atoms.push(walk.path.clone().into_boxed_slice());
        }
        // The values that may come next, by the shape of each, from the checks where no atom of its shape has asked.
        let mut values: Vec<(u32, u64, u128)> = Vec::new();
        if verdict.place == AtomPlace::Value {
            let limit = walk.shapes.labels + walk.shape.iter().filter(|&&shape| shape == FRESH_SHAPE || shape == KEY_SHAPE).count() as u32;
            let mut missing: Vec<(u32, u128)> = Vec::new();
            // A key is read once, whatever count of tokens share it.
            let mut read: Vec<u128> = Vec::new();
            for &id in &tokens.values {
                let token = self.vocabulary().token(id).expect("an id of the vocabulary");
                if matches!(token, Token::Label(label) if *label >= limit) {
                    continue;
                }
                let shape = walk.shape_of(token);
                let mut hasher = StableHasher::new();
                hasher.write_u128(node);
                hasher.write_u64(shape);
                let key = hasher.finish128().0;
                let held = self.atom_verdict_held(shared, key).filter(|held| match held {
                    HeldVerdict::Value { effort, .. } => read.contains(&key) || work.fits_effort(*effort),
                    HeldVerdict::Place(_) => false,
                });
                match held {
                    Some(HeldVerdict::Value { admitted, effort }) => {
                        if !read.contains(&key) {
                            read.push(key);
                            let _ = work.charge_effort(effort);
                        }
                        if admitted {
                            values.push((id, shape, key));
                        }
                    }
                    _ => {
                        if !missing.iter().any(|(_, held)| *held == key) {
                            missing.push((id, key));
                        }
                        values.push((id, shape, key));
                    }
                }
            }
            if !missing.is_empty() {
                found.states += 1;
                let Some(here) = self.state_of_walk(walk) else { return };
                // Each key is checked on its own, so the effort it records is that of the key alone, whichever keys are missing with it.
                for (id, key) in &missing {
                    let (mask, effort) = work.effort_of(|| {
                        let mut mask = None;
                        self.at(here.clone(), |walker| mask = Some(walker.mask_over(std::iter::once(*id))));
                        mask.expect("the body ran")
                    });
                    if !work.is_effort_exhausted() {
                        self.atom_verdict_keep(shared, *key, HeldVerdict::Value { admitted: mask.steps.contains_key(id), effort });
                    }
                    steps.extend(mask.steps.into_iter().map(|(id, (state, _))| (id, state)));
                }
                values.retain(|(_, _, key)| !missing.iter().any(|(id, held)| held == key && !steps.contains_key(id)));
            }
        }
        // The tokens in ascending order of their ids: the values and the column tokens and `END` of the verdict.
        let mut next: Vec<(u32, u64)> = values.iter().map(|&(id, shape, _)| (id, shape)).collect();
        next.extend(verdict.next.iter().map(|&id| (id, walk.shapes.of(self.vocabulary().token(id).expect("an id of the vocabulary")))));
        next.sort_unstable();
        for (id, shape) in next {
            let token = self.vocabulary().token(id).expect("an id of the vocabulary");
            let column = match token {
                Token::Column(column) if verdict.place == AtomPlace::Sites => Some(*column),
                _ => floor,
            };
            // The fields of a record stand in ascending order, as the columns of an atom do.
            let held_field = walk.field;
            match token {
                Token::Column(_) if verdict.place == AtomPlace::Sites => walk.field = None,
                Token::Column(field) => {
                    if walk.field.is_some_and(|last| *field <= last) {
                        continue;
                    }
                    walk.field = Some(*field);
                }
                _ => {}
            }
            // The site this token gives, where it is a site's value.
            let site = (verdict.place == AtomPlace::Value && !matches!(token, Token::Column(_) | Token::Control(Control::End))).then(|| {
                let label = match token {
                    Token::Label(label) => *label,
                    _ => u32::MAX,
                };
                (floor.unwrap_or(u32::MAX), label)
            });
            walk.sites.extend(site);
            walk.path.push(id);
            walk.shape.push(shape);
            walk.states.push(steps.get(&id).cloned());
            self.atom_place_walk(walk, column, found);
            walk.states.pop();
            walk.shape.pop();
            walk.path.pop();
            if site.is_some() {
                walk.sites.pop();
            }
            walk.field = held_field;
        }
    }

    fn atom_verdict_held(&self, shared: bool, key: u128) -> Option<HeldVerdict> {
        if shared { shared_verdicts().lock().expect("the atom verdicts are not poisoned").get(&key).cloned() } else { self.state.atom_verdict(key) }
    }

    fn atom_verdict_keep(&self, shared: bool, key: u128, verdict: HeldVerdict) {
        if shared {
            let mut held = shared_verdicts().lock().expect("the atom verdicts are not poisoned");
            if held.len() >= SHARED_VERDICTS {
                held.clear();
            }
            held.insert(key, verdict);
        } else {
            self.state.keep_atom_verdict(key, verdict);
        }
    }
}

impl Decoder<'_> {
    /// The list of [`Decoder::candidate_atoms`] from a whole mask at each token
    /// of each atom, for a check of that walk.
    pub fn candidate_atoms_reference(&self, limit: usize) -> CandidateAtoms {
        let _request = self.begin_request();
        let mut found = CandidateAtoms::default();
        let mut path = Vec::new();
        let mask = self.admissible();
        found.states += 1;
        let vocabulary = self.vocabulary();
        for id in (0..vocabulary.len() as u32).filter(|&id| mask.contains(id)) {
            let token = vocabulary.token(id).expect("an id of the vocabulary");
            let opens = matches!(token, Token::Relation(_) | Token::Fact(_) | Token::Lib(_));
            if !opens && !matches!(token, Token::Control(Control::Not)) {
                continue;
            }
            let Ok(next) = self.successor(token.clone()) else { continue };
            path.push(id);
            if opens {
                if next.state.atom_place().is_some() {
                    next.reference_atom(&mut path, None, limit, &mut found);
                }
            } else {
                let mask = next.admissible();
                found.states += 1;
                for inner in (0..vocabulary.len() as u32).filter(|&id| mask.contains(id)) {
                    let token = vocabulary.token(inner).expect("an id of the vocabulary");
                    if !matches!(token, Token::Relation(_) | Token::Fact(_) | Token::Lib(_)) {
                        continue;
                    }
                    let Ok(after) = next.successor(token.clone()) else { continue };
                    if after.state.atom_place().is_some() {
                        path.push(inner);
                        after.reference_atom(&mut path, None, limit, &mut found);
                        path.pop();
                    }
                }
            }
            path.pop();
        }
        found
    }

    fn reference_atom(&self, path: &mut Vec<u32>, floor: Option<u32>, limit: usize, found: &mut CandidateAtoms) {
        if found.states >= limit {
            found.truncated = true;
            return;
        }
        let Some(place) = self.state.atom_place() else { return };
        let mask = self.admissible();
        found.states += 1;
        let vocabulary = self.vocabulary();
        let admitted = (0..vocabulary.len() as u32).filter(|&id| mask.contains(id));
        if place == AtomPlace::Sites {
            let mut columns = Vec::new();
            let mut closes = false;
            for id in admitted {
                match vocabulary.token(id).expect("an id of the vocabulary") {
                    Token::Column(column) => columns.push((id, *column)),
                    Token::Label(_) | Token::Control(Control::Fresh | Control::Key | Control::Zero) => {}
                    _ => closes = true,
                }
            }
            if closes {
                found.atoms.push(path.clone().into_boxed_slice());
            }
            for (id, column) in columns {
                if floor.is_some_and(|floor| column <= floor) {
                    continue;
                }
                let Ok(next) = self.successor(Token::Column(column)) else { continue };
                path.push(id);
                next.reference_atom(path, Some(column), limit, found);
                path.pop();
            }
        } else {
            let ids: Vec<u32> = admitted.collect();
            for id in ids {
                let token = vocabulary.token(id).expect("an id of the vocabulary");
                let Ok(next) = self.successor(token.clone()) else { continue };
                path.push(id);
                next.reference_atom(path, floor, limit, found);
                path.pop();
            }
        }
    }
}
