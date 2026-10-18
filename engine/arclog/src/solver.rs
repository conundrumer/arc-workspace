//! The `Solver` tree, and `cases()`, which gives its case programs on demand.
//!
//! The reader reads a solver's `.arclog` and `.arcdata` files into one
//! `Solver` tree: the claims, the tree of alts, the arcdata records, and
//! `cases()`.
//!
//! A case program is built from the nodes of the solver's tree, so two
//! cases that take one form share its node and its canonical hash.

use crate::hash::{StableHashMap, StableHashSet};
use crate::layout::Layout;
use crate::program::path::{NodePath, NodeRef};
use crate::program::canonical::relation_of;
use crate::write::relation_ref;
use std::sync::Arc;

use crate::program::{
    Alt, AltItem, Alts, AltsName, Arcdata, Body, Clause, ClauseKeyword, Conjunct, Form, InstanceName, Negated, Node,
    OutputOwner, Program, ProgramRelation, RelationRef, RigidDetName,
};

/// A solver read from its two files: the claims, the tree of alts, the
/// arcdata records, and `cases()`.
#[derive(Clone, Debug)]
pub struct Solver {
    /// The task id the files are named by.
    pub task_id: Box<str>,
    /// The arclog file: the claims, the concept program's forms and the tree
    /// of alts.
    pub program: Node<Program>,
    /// The arcdata file.
    pub arcdata: Node<Arcdata>,
    /// The layout of the two files.
    pub layout: Layout,
    /// The solver that the arcdata file's `representative` line names, whose
    /// claims this solver's forms are read under, as
    /// `docs/arclog/arcdata.md#header` gives.
    pub representative: Option<Arc<Solver>>,
}

/// The name of one case: the alt it takes at each `ALTS` form it reaches,
/// the concept case's name included, in the order of the forms in the file.
/// A case reaches an `ALTS` form that its branch holds, as the nesting of
/// the blocks gives, and a `DET_OR_RULE` or `RULE_OR_DET` line that its base
/// reads, as [`Solver::case_names`] gives.
///
/// A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form whose readings
/// are `&background=$Stored` and `&background=$Derived`, or, on a line with
/// several proposers, the stored reading and one derived reading per
/// proposer, `&tile_size=ConstInDim`, as
/// `docs/arclog/arclog.md#the-alts-form` gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct CaseName(pub Box<[AltsName]>);

/// Whether `cases()` gives the cases the `exclude` forms leave, or every
/// case.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Exclusion {
    /// The cases the arcdata file's `exclude` forms leave.
    WithoutExcluded,
    /// Every case, the excluded ones included.
    WithExcluded,
}

/// One case of a solver: its name and its program.
///
/// The program holds no claim. It holds
/// the forms each alt of the case rederives in the place of the concept
/// program's, and the forms of each claim the alt adds, and a combination
/// of alts takes the forms of its nested `ALT`,
/// [`crate::program::AltItem::Alt`]. A `DET` of the concept program is
/// evaluated in the concept program, and the case program reads its
/// parameter as one node, never its body:
/// [`crate::resolver::DependencyKind::Parameter`], or
/// [`crate::resolver::DependencyKind::Chosen`] for a `DET` that ends in
/// `(ONE)`.
#[derive(Clone, Debug)]
pub struct Case {
    pub name: CaseName,
    pub program: Node<Program>,
    /// The file and the path there of each top-level form of the program,
    /// by its path. A node below a form stands at the same path below the
    /// form's path in the file.
    origins: StableHashMap<NodePath, (FileOwner, NodePath)>,
    concept_determinations: Box<[NodePath]>,
}

impl Case {
    /// The paths in the case program of the `DET` forms it takes from the
    /// concept program, which resolve in the concept program, as
    /// [`crate::resolver::ConceptReads`] gives, so each reads the concept
    /// program's derivation in every case.
    pub fn concept_determinations(&self) -> &[NodePath] {
        &self.concept_determinations
    }

    /// The arclog file that holds the node at `path` of the case program,
    /// and its path there, so that a diagnostic on a case program reports
    /// its place in the file. Both paths walk as
    /// [`crate::program::path::node_at`] gives.
    ///
    /// Panics where `path` names no node of the case program.
    pub fn file_path(&self, path: &NodePath) -> (FileOwner, NodePath) {
        let Some((first, rest)) = path.0.split_first() else {
            return (FileOwner::Solver, NodePath::default());
        };
        let (owner, form) = self.origins.get(&NodePath(Box::new([*first]))).expect("a path of the case program");
        (*owner, form.join(&NodePath(rest.into())))
    }
}

/// The solver whose arclog file holds a node of a case program: the solver
/// itself, or the solver its `representative` line names, whose claims its
/// forms are read under, and whose file holds those claims
/// (`docs/arclog/arcdata.md#header`).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum FileOwner {
    Solver,
    Representative,
}

/// A combination of alts that names no case of the solver.
#[derive(Clone, Debug)]
pub struct UnknownCase {
    pub name: CaseName,
}

impl Solver {
    /// The names of the solver's cases: the product of its `ALTS` forms,
    /// restricted by the nesting of the blocks, less the `exclude` forms of
    /// the arcdata file where `exclusion` is [`Exclusion::WithoutExcluded`].
    /// A `DET_OR_RULE` or `RULE_OR_DET` line splits only the bases that read
    /// its relation.
    ///
    /// Where the arcdata file has a `representative` line that gives a case's
    /// name, the one name is that case's (`docs/arclog/arcdata.md#header`).
    pub fn case_names(&self, exclusion: Exclusion) -> Vec<CaseName> {
        let names = self.all_case_names();
        if let Some(given) = self.arcdata.value().representative.as_ref().and_then(|line| line.case.as_ref()) {
            let named: Vec<CaseName> = names.into_iter().filter(|name| given.iter().all(|alt| name.0.contains(alt))).collect();
            assert!(named.len() == 1, "a `representative` line names one case of the solver's alts");
            return named;
        }
        match exclusion {
            Exclusion::WithExcluded => names,
            Exclusion::WithoutExcluded => {
                let excludes = &self.arcdata.value().excludes;
                let excluded = |name: &CaseName| excludes.iter().any(|e| e.combination.iter().all(|alt| name.0.contains(alt)));
                names.into_iter().filter(|name| !excluded(name)).collect()
            }
        }
    }

    /// Every name of the product, the concept case's first: for each base,
    /// the product of the readings of each line that the base reads, each
    /// name in the order of the forms in the file.
    fn all_case_names(&self) -> Vec<CaseName> {
        let mut names = Vec::new();
        for base in alts_product(&self.program.value().forms) {
            let walk = self.walk(&base);
            let lines: Vec<&Placed> = walk.placed.iter().filter(|p| line_of(&p.form).is_some_and(|line| walk.read_elsewhere(p, line))).collect();
            let mut picks: Vec<Vec<(usize, AltsName)>> = vec![walk.points.clone()];
            for line in lines {
                let clause = line_of(&line.form).expect("a line");
                picks = picks
                    .into_iter()
                    .flat_map(|pick| {
                        readings(clause).into_iter().map(move |(name, _)| {
                            let mut pick = pick.clone();
                            pick.push((line.step, name));
                            pick
                        })
                    })
                    .collect();
            }
            for mut pick in picks {
                pick.sort_by_key(|(step, _)| *step);
                names.push(CaseName(pick.into_iter().map(|(_, name)| name).collect()));
            }
        }
        names
    }

    /// The forms that the case of the alts `chosen` reaches, each where it
    /// stands, with each `ALTS` form it reaches and its alt.
    fn walk<'a>(&'a self, chosen: &'a [AltsName]) -> Walk<'a> {
        let mut walk = Walk { chosen, placed: Vec::new(), points: Vec::new(), unchosen: None };
        if let Some(representative) = &self.representative {
            for (index, form) in representative.program.value().forms.iter().enumerate() {
                if let Form::Claim(_) = form {
                    walk.form(form, FileOwner::Representative, NodePath(Box::new([PathStep(index as u32)])), 0);
                }
            }
        }
        walk.forms(&self.program.value().forms, FileOwner::Solver, &NodePath::default(), 0);
        walk
    }

    /// The case of `name`, or the first `ALTS` form it reaches at which
    /// `name` takes no alt.
    fn build(&self, name: CaseName) -> Result<Case, UnknownCase> {
        let walk = self.walk(&name.0);
        if walk.unchosen.is_some() {
            return Err(UnknownCase { name });
        }
        let placed: Vec<Placed> = walk
            .placed
            .iter()
            .map(|p| match line_of(&p.form) {
                Some(line) => {
                    let all = readings(line);
                    let reading = all.iter().find(|(alt, _)| name.0.contains(alt)).unwrap_or(&all[0]).1;
                    Placed { form: Form::Clause(Node::new(read_as(line, reading))), ..p.clone() }
                }
                None => p.clone(),
            })
            .collect();
        let taken = rederived(&placed);
        let mut forms = Vec::new();
        let mut origins = StableHashMap::default();
        let mut concept_determinations = Vec::new();
        for p in taken {
            let path = NodePath(Box::new([PathStep(forms.len() as u32)]));
            if p.depth == 0 && matches!(&p.form, Form::Clause(c) if c.value().keyword == ClauseKeyword::Det) {
                concept_determinations.push(path.clone());
            }
            origins.insert(path, (p.owner, p.path.clone()));
            forms.push(p.form.clone());
        }
        Ok(Case {
            name,
            program: Node::new(Program { forms: forms.into() }),
            origins,
            concept_determinations: concept_determinations.into(),
        })
    }

    /// The relations that some block of the solver derives at the program's
    /// name scope, which a name that no block of a case derives resolves
    /// among, as [`crate::resolver::resolve`] takes them. A name that a
    /// `DEMO_RULE` form declares is resolved within that form alone, as
    /// [`crate::program::NameScope`] gives, so the set leaves it out.
    pub fn derived_relations(&self) -> StableHashSet<ProgramRelation> {
        let mut derived = StableHashSet::default();
        let mut owners = StableHashSet::default();
        let mut outputs = Vec::new();
        let mut programs = vec![&self.program];
        programs.extend(self.representative.as_ref().map(|r| &r.program));
        for program in programs {
            for form in program.value().forms.iter() {
                each_form(form, &mut |form| match derives(form) {
                    Some(Derives::Relation(relation)) => {
                        derived.insert(relation);
                    }
                    Some(Derives::Instance(name)) => {
                        owners.insert(OutputOwner::Instance(name));
                    }
                    Some(Derives::RigidDet(name)) => {
                        owners.insert(OutputOwner::RigidDet(name));
                    }
                    None => {}
                });
                each_read(NodeRef::from(form), &mut |relation| {
                    if let RelationRef::Output(output) = relation {
                        outputs.push(output.clone());
                    }
                });
            }
        }
        derived.extend(outputs.into_iter().filter(|o| owners.contains(&o.of)).map(ProgramRelation::Output));
        derived
    }

    /// The concept case: the concept case's name at each `ALTS` form, whose
    /// resolution the other cases' [`crate::resolver::ConceptReads`] take, so
    /// a `DET` of the concept program is evaluated once, in it.
    pub fn concept_case(&self) -> Case {
        let name = self.all_case_names().swap_remove(0);
        self.build(name).expect("the concept case takes an alt at each `ALTS` form it reaches")
    }

    /// The cases of `case_names(exclusion)`, each built when the iterator
    /// reaches it, so a run builds only the cases it runs.
    pub fn cases(&self, exclusion: Exclusion) -> Cases<'_> {
        Cases { solver: self, names: self.case_names(exclusion).into_iter() }
    }

    /// The case `name`, excluded or not.
    pub fn case(&self, name: &CaseName) -> Result<Case, UnknownCase> {
        if !self.case_names(Exclusion::WithExcluded).contains(name) {
            return Err(UnknownCase { name: name.clone() });
        }
        self.build(name.clone())
    }
}

/// The iterator of [`Solver::cases`]: it builds each case program when it
/// reaches it.
#[derive(Debug)]
pub struct Cases<'a> {
    solver: &'a Solver,
    names: std::vec::IntoIter<CaseName>,
}

impl Iterator for Cases<'_> {
    type Item = Case;

    fn next(&mut self) -> Option<Case> {
        let name = self.names.next()?;
        Some(self.solver.build(name).expect("a name of `case_names` takes an alt at each `ALTS` form it reaches"))
    }
}

use crate::program::path::PathStep;

/// A form a case reaches: the form, its file and its path there, and the
/// number of `ALT` blocks it stands in, so the form of a combination's
/// nested `ALT` stands deeper than each alt's. `step` counts the walk's
/// steps before it, so it gives the order of the forms in the files.
#[derive(Clone, Debug)]
struct Placed {
    step: usize,
    form: Form,
    owner: FileOwner,
    path: NodePath,
    depth: u32,
}

/// The walk of a case's blocks: the forms it reaches, and the alt of each
/// `ALTS` form it reaches.
struct Walk<'a> {
    chosen: &'a [AltsName],
    placed: Vec<Placed>,
    /// Each `ALTS` form reached, by the walk's step at it, and its alt.
    points: Vec<(usize, AltsName)>,
    /// An `ALTS` form at which `chosen` takes no alt.
    unchosen: Option<AltsName>,
}

impl<'a> Walk<'a> {
    fn forms(&mut self, forms: &'a [Form], owner: FileOwner, base: &NodePath, depth: u32) {
        for (index, form) in forms.iter().enumerate() {
            self.form(form, owner, base.child(index as u32), depth);
        }
    }

    fn form(&mut self, form: &'a Form, owner: FileOwner, path: NodePath, depth: u32) {
        match form {
            Form::Claim(claim) => self.forms(&claim.value().forms, owner, &path, depth),
            Form::Alts(alts) => {
                let alts = alts.value();
                let Some(choice) = alt_names(alts).find(|name| self.chosen.contains(name)) else {
                    self.unchosen = Some(alts.name.clone());
                    return;
                };
                self.points.push((self.placed.len() + self.points.len(), choice.clone()));
                if let Some((index, alt)) = alts.alts.iter().enumerate().find(|(_, alt)| alt.value().name == *choice) {
                    self.alt(alt.value(), owner, path.child(index as u32), depth + 1);
                }
            }
            _ => {
                let step = self.placed.len() + self.points.len();
                self.placed.push(Placed { step, form: form.clone(), owner, path, depth })
            }
        }
    }

    fn alt(&mut self, alt: &'a Alt, owner: FileOwner, path: NodePath, depth: u32) {
        for (index, item) in alt.items.iter().enumerate() {
            match item {
                AltItem::Form(form) => self.form(form, owner, path.child(index as u32), depth),
                AltItem::Alt(nested) if self.chosen.contains(&nested.value().name) => {
                    self.alt(nested.value(), owner, path.child(index as u32), depth + 1)
                }
                AltItem::Alt(_) => {}
            }
        }
    }

    /// Whether a form of the walk other than `line` reads its relation.
    fn read_elsewhere(&self, line: &Placed, clause: &Clause) -> bool {
        let relation = relation_of(&clause.derives);
        self.placed.iter().filter(|p| !std::ptr::eq(*p, line)).any(|p| {
            let mut reads = false;
            each_read(NodeRef::from(&p.form), &mut |read| reads |= *read == relation);
            reads
        })
    }
}

/// The alt names of an `ALTS` form: the concept case's, then each alt's
/// that is another.
fn alt_names(alts: &Alts) -> impl Iterator<Item = &AltsName> {
    std::iter::once(&alts.concept).chain(alts.alts.iter().map(|alt| &alt.value().name).filter(move |name| **name != alts.concept))
}

/// The alts each base of `forms` takes at the `ALTS` forms it reaches, in
/// the order of the forms, the concept case's base first.
fn alts_product(forms: &[Form]) -> Vec<Vec<AltsName>> {
    forms.iter().fold(vec![Vec::new()], |bases, form| product(bases, form_bases(form)))
}

fn form_bases(form: &Form) -> Vec<Vec<AltsName>> {
    match form {
        Form::Claim(claim) => alts_product(&claim.value().forms),
        Form::Alts(alts) => {
            let alts = alts.value();
            alt_names(alts)
                .flat_map(|name| {
                    let block = alts.alts.iter().find(|alt| alt.value().name == *name);
                    let below = block.map_or_else(|| vec![Vec::new()], |alt| alt_bases(alt.value()));
                    below.into_iter().map(move |rest| std::iter::once(name.clone()).chain(rest).collect())
                })
                .collect()
        }
        _ => vec![Vec::new()],
    }
}

/// The bases of the `ALTS` forms an `ALT` block holds. A nested `ALT`
/// block holds a combination's forms, and no `ALTS` form of its own.
fn alt_bases(alt: &Alt) -> Vec<Vec<AltsName>> {
    alt.items.iter().fold(vec![Vec::new()], |bases, item| match item {
        AltItem::Form(form) => product(bases, form_bases(form)),
        AltItem::Alt(_) => bases,
    })
}

fn product(left: Vec<Vec<AltsName>>, right: Vec<Vec<AltsName>>) -> Vec<Vec<AltsName>> {
    left.iter().flat_map(|l| right.iter().map(move |r| l.iter().chain(r).cloned().collect())).collect()
}

/// The clause of a `DET_OR_RULE` or `RULE_OR_DET` line.
fn line_of(form: &Form) -> Option<&Clause> {
    match form {
        Form::Clause(clause) if matches!(clause.value().keyword, ClauseKeyword::DetOrRule | ClauseKeyword::RuleOrDet) => {
            Some(clause.value())
        }
        _ => None,
    }
}

/// A reading of a `DET_OR_RULE` or `RULE_OR_DET` line: the stored
/// parameter, or the derivation, by the proposer at an index on a line
/// with several.
#[derive(Clone, Copy, Debug)]
enum Reading {
    Stored,
    Derived(Option<usize>),
}

/// The readings of a line, each with its name, the concept case's first, as
/// `docs/arclog/arclog.md#the-alts-form` gives.
fn readings(line: &Clause) -> Vec<(AltsName, Reading)> {
    let relation = relation_ref(&relation_of(&line.derives));
    let named = |reading: &str| AltsName(format!("{relation}={reading}").into());
    let stored = (named("$Stored"), Reading::Stored);
    let derived: Vec<(AltsName, Reading)> = if line.proposers.len() > 1 {
        line.proposers.iter().enumerate().map(|(index, proposer)| (named(&proposer.0), Reading::Derived(Some(index)))).collect()
    } else {
        vec![(named("$Derived"), Reading::Derived(None))]
    };
    match line.keyword {
        ClauseKeyword::RuleOrDet => derived.into_iter().chain([stored]).collect(),
        _ => std::iter::once(stored).chain(derived).collect(),
    }
}

/// A line's clause in one reading: the stored reading a `DET`, and a
/// derived reading a `RULE`. The body of a `DET_OR_RULE` line with
/// proposers is the stored reading's, so a derived reading of it reads its
/// proposer alone.
fn read_as(line: &Clause, reading: Reading) -> Clause {
    match reading {
        Reading::Stored => Clause { keyword: ClauseKeyword::Det, ..line.clone() },
        Reading::Derived(proposer) => {
            let proposers = match proposer {
                Some(index) => Arc::from([line.proposers[index].clone()]),
                None => line.proposers.clone(),
            };
            if line.keyword == ClauseKeyword::DetOrRule && !line.proposers.is_empty() {
                Clause {
                    keyword: ClauseKeyword::Rule,
                    proposers,
                    body: Node::new(Body { conjuncts: Arc::from([]) }),
                    ones: Arc::from([]),
                    columns: Arc::from([]),
                    ..line.clone()
                }
            } else {
                Clause { keyword: ClauseKeyword::Rule, proposers, ..line.clone() }
            }
        }
    }
}

/// What a form derives, by which a form of an alt takes the place of the
/// concept program's.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum Derives {
    Relation(ProgramRelation),
    Instance(InstanceName),
    RigidDet(RigidDetName),
}

fn derives(form: &Form) -> Option<Derives> {
    match form {
        Form::Clause(clause) => Some(Derives::Relation(clause.value().derives.clone())),
        Form::Instance(instance) => Some(Derives::Instance(instance.value().name.clone())),
        Form::Choose(choose) => Some(Derives::Relation(ProgramRelation::Declared(choose.value().name.clone()))),
        Form::RigidDet(rigid) => Some(Derives::RigidDet(rigid.value().name.clone())),
        Form::Demonstrated(demonstrated) => {
            Some(Derives::Relation(ProgramRelation::Declared(demonstrated.value().name.clone())))
        }
        Form::Claim(_) | Form::Alts(_) => None,
    }
}

fn is_det(form: &Form) -> bool {
    matches!(form, Form::Clause(clause) if clause.value().keyword == ClauseKeyword::Det)
}

/// The forms of a case, from the forms its walk reaches: for each thing
/// derived, the forms of the deepest blocks that derive it, at the place of
/// the concept program's first form that derives it. A parameter that
/// several blocks determine keeps each block's `DET`.
fn rederived(placed: &[Placed]) -> Vec<&Placed> {
    let keys: Vec<Derives> = placed.iter().map(|p| derives(&p.form).expect("a reached form derives")).collect();
    let mut deepest: StableHashMap<&Derives, (u32, bool)> = StableHashMap::default();
    for (p, key) in placed.iter().zip(&keys) {
        let entry = deepest.entry(key).or_insert((p.depth, true));
        if p.depth > entry.0 {
            *entry = (p.depth, is_det(&p.form));
        } else if p.depth == entry.0 {
            entry.1 &= is_det(&p.form);
        }
    }
    let keep: Vec<bool> = placed
        .iter()
        .zip(&keys)
        .map(|(p, key)| {
            let (depth, all_det) = deepest[key];
            p.depth == depth || (all_det && is_det(&p.form))
        })
        .collect();
    let mut taken = Vec::new();
    let mut emitted = vec![false; placed.len()];
    let mut placed_keys = StableHashSet::default();
    for (index, p) in placed.iter().enumerate().filter(|(_, p)| p.depth == 0) {
        let key = &keys[index];
        if keep[index] {
            taken.push(p);
            emitted[index] = true;
        }
        if deepest[key].0 > 0 && placed_keys.insert(key) {
            for other in 0..placed.len() {
                if !emitted[other] && placed[other].depth > 0 && keep[other] && keys[other] == *key {
                    taken.push(&placed[other]);
                    emitted[other] = true;
                }
            }
        }
    }
    taken.extend((0..placed.len()).filter(|index| !emitted[*index] && keep[*index]).map(|index| &placed[index]));
    taken
}

/// Calls `f` on each form below `form`, `form` included, outside the
/// `DEMO_RULE` forms, whose names are their own.
fn each_form<'a>(form: &'a Form, f: &mut dyn FnMut(&'a Form)) {
    f(form);
    match form {
        Form::Claim(claim) => claim.value().forms.iter().for_each(|form| each_form(form, f)),
        Form::Alts(alts) => alts.value().alts.iter().for_each(|alt| each_alt_form(alt.value(), f)),
        _ => {}
    }
}

fn each_alt_form<'a>(alt: &'a Alt, f: &mut dyn FnMut(&'a Form)) {
    for item in alt.items.iter() {
        match item {
            AltItem::Form(form) => each_form(form, f),
            AltItem::Alt(nested) => each_alt_form(nested.value(), f),
        }
    }
}

/// Calls `f` on the relation of each atom below `node`.
fn each_read<'a>(node: NodeRef<'a>, f: &mut dyn FnMut(&'a RelationRef)) {
    match node {
        NodeRef::Conjunct(Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) => f(&atom.value().relation),
        NodeRef::Atom(atom) => f(&atom.relation),
        _ => {}
    }
    for child in node.children() {
        each_read(child, f);
    }
}
