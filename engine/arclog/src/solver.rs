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
use crate::resolver::SolverScope;
use std::sync::Arc;

use crate::program::{
    written_inputs, Alt, Alts, AltsName, Block, Arcdata, Body, Clause, ClauseKeyword, ColumnName, DemoRule, Demonstrated, DemonstratedPart, Form, Instance,
    InstanceInput, InstanceName, KeyClause, Node, OutputOwner, OutputStep, PortName, Program, ProgramRelation, RelationRef, RigidDetName,
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
/// A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form, with the readings
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
///
/// Of a `DET_OR_RULE` or `RULE_OR_DET` line on a port of an instance,
/// `&<instance>.<port>`, a case holds what its reading of the line gives, as
/// `docs/arclog/arclog.md#the-alts-form` gives it.
#[derive(Clone, Debug)]
pub struct Case {
    pub name: CaseName,
    pub program: Node<Program>,
    /// The file and the path there of each top-level form of the program,
    /// and of each form of a `DEMO_RULE` form that an alt's form stands in,
    /// by its path. A node below such a form stands at the same path below
    /// the form's path in the file.
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
        if path.0.is_empty() {
            return (FileOwner::Solver, NodePath::default());
        }
        let deepest = (1..=path.0.len()).rev().find_map(|depth| {
            let (form, rest) = path.0.split_at(depth);
            self.origins.get(&NodePath(form.into())).map(|origin| (origin, rest))
        });
        let ((owner, form), rest) = deepest.expect("a path of the case program");
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
    /// The names of the solver's cases
    /// (`docs/arclog/arclog.md#the-alts-form`), less the `exclude` forms of
    /// the arcdata file where `exclusion` is [`Exclusion::WithoutExcluded`].
    /// A `DET_OR_RULE` or `RULE_OR_DET` line splits only the bases that read
    /// its relation, and a line on an input of an instance, `&canvas.extent`,
    /// is read by that instance's `INIT` form.
    ///
    /// Where the arcdata file has a `representative` line, the names are as
    /// `docs/arclog/arcdata.md#header` gives.
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
        for (index, form) in self.representative_claims() {
            walk.form(form, FileOwner::Representative, NodePath::top(index as u32), 0);
        }
        walk.forms(&self.program.value().forms, FileOwner::Solver, &NodePath::default(), 0);
        walk
    }

    /// The claims of the solver the `representative` line names, each with
    /// its index among the forms of that solver's file.
    fn representative_claims(&self) -> impl Iterator<Item = (usize, &Form)> {
        let forms = self.representative.iter().flat_map(|r| r.program.value().forms.iter());
        forms.enumerate().filter(|(_, form)| matches!(form, Form::Claim(_)))
    }

    /// The case of `name`, or the first `ALTS` form it reaches at which
    /// `name` takes no alt.
    fn build(&self, name: CaseName) -> Result<Case, UnknownCase> {
        let walk = self.walk(&name.0);
        if walk.unchosen.is_some() {
            return Err(UnknownCase { name });
        }
        let mut other_readings = StableHashSet::default();
        let mut placed: Vec<Option<Placed>> = walk.placed.iter().cloned().map(Some).collect();
        for (index, p) in walk.placed.iter().enumerate() {
            let Some(line) = line_of(&p.form) else { continue };
            let all = readings(line);
            let (alt, reading) = all.iter().find(|(alt, _)| name.0.contains(alt)).unwrap_or(&all[0]);
            if *alt != all[0].0 {
                other_readings.insert(p.step);
            }
            let port = port_of(line, &walk.placed);
            placed[index] = match (port, reading) {
                (Some(_), Reading::Derived(_)) if line.proposers.is_empty() => None,
                _ => Some(Placed { form: Form::Clause(Node::new(read_as(line, *reading))), ..p.clone() }),
            };
            if let (Some(Port { instance, name, input: true }), Reading::Stored) = (port, reading) {
                if let Some(Placed { form: Form::Instance(form), .. }) = &mut placed[instance] {
                    *form = Node::new(without_input(form.value(), name));
                }
            }
        }
        let placed: Vec<Placed> = placed.into_iter().flatten().collect();
        let taken = rederived(&placed);
        let mut forms = Vec::new();
        let mut origins = StableHashMap::default();
        let mut concept_determinations = Vec::new();
        for taken in taken {
            let p = taken.placed;
            let path = NodePath::top(forms.len() as u32);
            if p.depth == 0 && is_det(&p.form) && !other_readings.contains(&p.step) {
                concept_determinations.push(path.clone());
            }
            let (form, below) = taken.form();
            origins.extend(below.into_iter().map(|(at, origin)| (path.join(&at), origin)));
            origins.insert(path, (p.owner, p.path.clone()));
            forms.push(form);
        }
        Ok(Case {
            name,
            program: Node::new(Program { forms: forms.into() }),
            origins,
            concept_determinations: concept_determinations.into(),
        })
    }

    /// What every case of the solver resolves against, as
    /// [`crate::resolver::resolve`] takes it: the relations that
    /// [`Solver::derived`] gives, and the columns that
    /// [`Solver::read_columns`] gives.
    pub fn derived_relations(&self) -> SolverScope {
        SolverScope { derived: self.derived(), read_columns: self.read_columns() }
    }

    /// The relations that some block of the solver's forms, or of the
    /// claims of the solver its `representative` line names, derives at the
    /// program's name scope, which a name that no block of a case derives
    /// resolves among, as [`crate::resolver::resolve`] takes them. A name that a
    /// `DEMO_RULE` form declares is resolved within that form alone, as
    /// [`crate::program::NameScope`] gives, so the set leaves it out. An
    /// alt's form that derives such a name stands in that `DEMO_RULE` form in
    /// each case that takes the alt, so the set leaves out its name too,
    /// unless a form of the concept program outside its `DEMO_RULE` forms
    /// derives it.
    pub fn derived(&self) -> StableHashSet<ProgramRelation> {
        let mut derived = StableHashSet::default();
        let mut owners = StableHashSet::default();
        let mut outputs = Vec::new();
        let claims = self.representative_claims().map(|(_, form)| form);
        let forms: Vec<&Form> = self.program.value().forms.iter().chain(claims).collect();
        let mut concept = StableHashSet::default();
        let mut in_rules = StableHashSet::default();
        for form in &forms {
            each_form(form, false, &mut |form, in_alt| {
                if !in_alt {
                    concept.extend(derives(form));
                    in_rules.extend(rule_derives(form));
                }
            });
        }
        let in_rules_only: StableHashSet<Derives> = in_rules.difference(&concept).cloned().collect();
        for form in forms {
            each_form(form, false, &mut |form, _| match derives(form).filter(|key| !in_rules_only.contains(key)) {
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
        derived.extend(outputs.into_iter().filter(|o| owners.contains(&o.of)).map(ProgramRelation::Output));
        derived
    }

    /// The column names that the sites of the reads of each relation name,
    /// in source order, across the solver's forms and the claims of the
    /// solver its `representative` line names, through every `ALT` block,
    /// apart from the reads in an `ALT` block that derives the relation or
    /// that a block deriving it holds: a `DET` of the concept program has
    /// one determination in every case, and an alt reads it at these
    /// columns (`docs/arclog/arclog.md#the-alts-form`).
    pub fn read_columns(&self) -> StableHashMap<ProgramRelation, Vec<ColumnName>> {
        let mut named = StableHashMap::default();
        let claims = self.representative_claims().map(|(_, form)| form);
        for form in self.program.value().forms.iter().chain(claims) {
            form_reads(form, &[], &mut named);
        }
        named
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
        let chosen = self.chosen;
        match form {
            Form::Claim(_) => self.descend(Block::Form(form), owner, &path, depth, &|alt| chosen.contains(&alt.name)),
            Form::Alts(alts) => {
                let alts = alts.value();
                let Some(choice) = alt_names(alts).find(|name| chosen.contains(name)) else {
                    self.unchosen = Some(alts.name.clone());
                    return;
                };
                self.points.push((self.placed.len() + self.points.len(), choice.clone()));
                self.descend(Block::Form(form), owner, &path, depth, &|alt| alt.name == *choice);
            }
            _ => {
                let step = self.placed.len() + self.points.len();
                self.placed.push(Placed { step, form: form.clone(), owner, path, depth })
            }
        }
    }

    /// The blocks of `block`, the block at `path`, that `enter` admits, an
    /// `ALT` block one deeper than `depth`; below an `ALT` block, each nested
    /// block that the case chooses.
    fn descend(&mut self, block: Block<'a>, owner: FileOwner, path: &NodePath, depth: u32, enter: &dyn Fn(&Alt) -> bool) {
        let chosen = self.chosen;
        for (index, inner) in inner_blocks(block, enter) {
            match inner {
                Block::Form(form) => self.form(form, owner, path.child(index), depth),
                Block::Alt(_) => self.descend(inner, owner, &path.child(index), depth + 1, &|alt| chosen.contains(&alt.name)),
            }
        }
    }

    /// Whether a form of the walk other than `line` reads its relation: an
    /// atom that names it, or, for an input of an instance, the instance's
    /// `INIT` form, which holds that input.
    fn read_elsewhere(&self, line: &Placed, clause: &Clause) -> bool {
        if port_of(clause, &self.placed).is_some_and(|port| port.input) {
            return true;
        }
        let relation = relation_of(&clause.derives);
        self.placed.iter().filter(|p| !std::ptr::eq(*p, line)).any(|p| {
            let mut reads = false;
            each_read(NodeRef::from(&p.form), &mut |read| reads |= *read == relation);
            reads
        })
    }
}

/// The port of an instance that a clause derives: the index among `placed`
/// of the instance's `INIT` form, the port's name, and whether the port is
/// an input that the form writes.
#[derive(Clone, Copy, Debug)]
struct Port<'c> {
    instance: usize,
    name: &'c PortName,
    input: bool,
}

/// The port of an instance among `placed` that `clause` derives,
/// `&<instance>.<port>`, or `None` where it derives no port of an instance
/// of `placed`.
fn port_of<'c>(clause: &'c Clause, placed: &[Placed]) -> Option<Port<'c>> {
    let ProgramRelation::Output(output) = &clause.derives else { return None };
    let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return None };
    placed.iter().enumerate().find_map(|(index, p)| match &p.form {
        Form::Instance(instance) if instance.value().name == *name => {
            let instance = instance.value();
            let input = written_inputs(instance.key.as_ref(), &instance.inputs).any(|input| input.name == *port);
            Some(Port { instance: index, name: port, input })
        }
        _ => None,
    })
}

/// `instance` with its input `port` left out, of its key clause's inputs
/// or of its own.
fn without_input(instance: &Instance, port: &PortName) -> Instance {
    let kept = |inputs: &Arc<[Node<InstanceInput>]>| -> Arc<[Node<InstanceInput>]> {
        inputs.iter().filter(|input| input.value().name != *port).cloned().collect()
    };
    let key = instance.key.as_ref().map(|key| Node::new(KeyClause { inputs: kept(&key.value().inputs), ..key.value().clone() }));
    Instance { key, inputs: kept(&instance.inputs), ..instance.clone() }
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
        Form::Claim(_) => forms_bases(Block::Form(form)),
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
    forms_bases(Block::Alt(alt))
}

/// The bases of the `ALTS` forms that the forms of `block` reach, a claim
/// or an `ALT` block, its nested `ALT` blocks left out.
fn forms_bases(block: Block<'_>) -> Vec<Vec<AltsName>> {
    inner_blocks(block, &|_| false).into_iter().fold(vec![Vec::new()], |bases, (_, inner)| match inner {
        Block::Form(form) => product(bases, form_bases(form)),
        Block::Alt(_) => bases,
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

/// A line's clause in one reading: the stored reading a `DET`, and a derived
/// reading a `RULE`. Each reading keeps the line's `ONE` marks and its
/// columns. The line's body is one reading's, as
/// `docs/arclog/arclog.md#the-alts-form` gives, and the other reading holds
/// no body. The derived reading by a proposer other than the line's first
/// holds the line's first proposer, which names the relation's columns, then
/// its own, whose columns map onto them by position.
fn read_as(line: &Clause, reading: Reading) -> Clause {
    let (keyword, proposers, owns_body) = match reading {
        Reading::Stored => (ClauseKeyword::Det, line.proposers.clone(), line.keyword == ClauseKeyword::DetOrRule),
        Reading::Derived(proposer) => {
            let proposers = match proposer {
                Some(0) => Arc::from([line.proposers[0].clone()]),
                Some(index) => Arc::from([line.proposers[0].clone(), line.proposers[index].clone()]),
                None => line.proposers.clone(),
            };
            (ClauseKeyword::Rule, proposers, line.keyword == ClauseKeyword::RuleOrDet)
        }
    };
    let body = if owns_body { line.body.clone() } else { Node::new(Body { conjuncts: Arc::from([]) }) };
    Clause { keyword, proposers, body, ..line.clone() }
}

/// The relation, instance or rigid `DET` that a form derives. A case keeps,
/// of the forms that derive one such thing, those of the deepest blocks
/// (`rederived`).
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
/// several blocks determine keeps each block's `DET`. The place of a thing
/// that a `DEMO_RULE` form of the concept program derives is in each such
/// form, at its first form that derives it, as [`Taken::in_rules`] gives.
fn rederived(placed: &[Placed]) -> Vec<Taken<'_>> {
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
    let rederived_in = |rules: &StableHashSet<Derives>| -> Vec<&Placed> {
        (0..placed.len()).filter(|index| placed[*index].depth > 0 && keep[*index] && rules.contains(&keys[*index])).map(|index| &placed[index]).collect()
    };
    let mut in_rules = StableHashSet::default();
    let mut taken = Vec::new();
    let mut emitted = vec![false; placed.len()];
    let mut placed_keys = StableHashSet::default();
    for (index, p) in placed.iter().enumerate().filter(|(_, p)| p.depth == 0) {
        let key = &keys[index];
        if keep[index] {
            let rules: StableHashSet<Derives> = rule_derives(&p.form).collect();
            taken.push(Taken { placed: p, in_rules: rederived_in(&rules) });
            in_rules.extend(rules);
            emitted[index] = true;
        }
        if deepest[key].0 > 0 && placed_keys.insert(key) {
            for other in 0..placed.len() {
                if !emitted[other] && placed[other].depth > 0 && keep[other] && keys[other] == *key {
                    taken.push(Taken { placed: &placed[other], in_rules: Vec::new() });
                    emitted[other] = true;
                }
            }
        }
    }
    let rest = (0..placed.len()).filter(|index| !emitted[*index] && keep[*index] && !in_rules.contains(&keys[*index]));
    taken.extend(rest.map(|index| Taken { placed: &placed[index], in_rules: Vec::new() }));
    taken
}

/// A form of a case: a form its walk reaches, with the forms of the alts
/// that stand in its `DEMO_RULE` forms where it is a `DEMONSTRATED` form of
/// the concept program.
struct Taken<'p> {
    placed: &'p Placed,
    /// The forms of the deepest blocks that derive a thing that a
    /// `DEMO_RULE` form of the form derives, in the order of the walk. In
    /// each such `DEMO_RULE` form, they take the place of its first form that
    /// derives that thing, and its other forms that derive it are left out.
    in_rules: Vec<&'p Placed>,
}

impl Taken<'_> {
    /// The form, with the forms of `in_rules` in its `DEMO_RULE` forms, and
    /// the file and the path there of each form of each `DEMO_RULE` form that
    /// they change, by its path below the form.
    fn form(&self) -> (Form, Vec<(NodePath, (FileOwner, NodePath))>) {
        let demonstrated = match &self.placed.form {
            Form::Demonstrated(demonstrated) if !self.in_rules.is_empty() => demonstrated.value(),
            form => return (form.clone(), Vec::new()),
        };
        let mut origins = Vec::new();
        let rules = demonstrated.rules.iter().enumerate().map(|(index, rule)| {
            let step = demonstrated.position(DemonstratedPart::Rule(index));
            let mut forms: Vec<(Form, (FileOwner, NodePath))> = Vec::new();
            let mut placed_keys = StableHashSet::default();
            for (at, form) in rule.value().forms.iter().enumerate() {
                let key = derives(form);
                let alts: Vec<&Placed> = self.in_rules.iter().copied().filter(|p| key.is_some() && derives(&p.form) == key).collect();
                if alts.is_empty() {
                    forms.push((form.clone(), (self.placed.owner, self.placed.path.child(step).child(at as u32))));
                } else if placed_keys.insert(key) {
                    forms.extend(alts.into_iter().map(|p| (p.form.clone(), (p.owner, p.path.clone()))));
                }
            }
            if placed_keys.is_empty() {
                return rule.clone();
            }
            let rule_path = NodePath::default().child(step);
            origins.extend(forms.iter().enumerate().map(|(at, (_, origin))| (rule_path.child(at as u32), origin.clone())));
            let forms = forms.into_iter().map(|(form, _)| form).collect();
            Node::new(DemoRule { forms, ..rule.value().clone() })
        });
        let rules = rules.collect();
        (Form::Demonstrated(Node::new(Demonstrated { rules, ..demonstrated.clone() })), origins)
    }
}

/// The forms of the `DEMO_RULE` forms of `form`, where it is a
/// `DEMONSTRATED` form.
fn rule_forms(form: &Form) -> impl Iterator<Item = &Form> {
    let demonstrated = match form {
        Form::Demonstrated(demonstrated) => Some(demonstrated.value()),
        _ => None,
    };
    demonstrated.into_iter().flat_map(|d| d.rules.iter().flat_map(|rule| rule.value().forms.iter()))
}

/// What the forms of the `DEMO_RULE` forms of `form` derive.
fn rule_derives(form: &Form) -> impl Iterator<Item = Derives> + '_ {
    rule_forms(form).filter_map(derives)
}

/// Adds to `named` the column names that the sites of each read in `form`
/// name, as [`Solver::read_columns`] gives them, where `rederived` holds
/// the relations that the `ALT` blocks holding `form` derive.
fn form_reads(form: &Form, rederived: &[ProgramRelation], named: &mut StableHashMap<ProgramRelation, Vec<ColumnName>>) {
    if let Form::Claim(_) | Form::Alts(_) = form {
        return block_reads(Block::Form(form), rederived, named);
    }
    each_atom(NodeRef::from(form), &mut |atom| {
        let relation = match &atom.relation {
            RelationRef::Declared(name) => ProgramRelation::Declared(name.clone()),
            RelationRef::Output(output) => ProgramRelation::Output(output.clone()),
            _ => return,
        };
        if rederived.contains(&relation) {
            return;
        }
        crate::resolver::add_columns(named.entry(relation).or_default(), atom.sites.iter().map(|site| &site.column));
    });
}

/// [`form_reads`] over the blocks of `block`, an `ALT` block adding to
/// `rederived` the relations its own forms derive.
fn block_reads(block: Block<'_>, rederived: &[ProgramRelation], named: &mut StableHashMap<ProgramRelation, Vec<ColumnName>>) {
    let mut own = rederived.to_vec();
    if let Block::Alt(_) = block {
        own.extend(block_derived(block));
    }
    for (_, inner) in inner_blocks(block, &|_| true) {
        match inner {
            Block::Form(form) => form_reads(form, &own, named),
            Block::Alt(_) => block_reads(inner, &own, named),
        }
    }
}

/// The relations that the forms of `block` derive, the forms of its claims
/// included and those of its `ALT` blocks left out.
fn block_derived(block: Block<'_>) -> Vec<ProgramRelation> {
    let mut derived = Vec::new();
    for (_, inner) in inner_blocks(block, &|_| false) {
        let Block::Form(form) = inner else { continue };
        match (form, derives(form)) {
            (Form::Claim(_), _) => derived.extend(block_derived(inner)),
            (_, Some(Derives::Relation(relation))) => derived.push(relation),
            _ => {}
        }
    }
    derived
}

/// Calls `f` on each atom below `node`.
fn each_atom<'a>(node: NodeRef<'a>, f: &mut dyn FnMut(&'a crate::program::Atom)) {
    if let Some(atom) = node.atom() {
        f(atom);
    }
    for child in node.children() {
        each_atom(child, f);
    }
}

/// Calls `f` on each form below `form`, `form` included, outside the
/// `DEMO_RULE` forms, whose names are their own, with whether the form
/// stands in an `ALT` block.
fn each_form<'a>(form: &'a Form, in_alt: bool, f: &mut dyn FnMut(&'a Form, bool)) {
    f(form, in_alt);
    each_inner_form(Block::Form(form), in_alt, f);
}

/// Calls `f` on each form below `block`, through every `ALT` block, with
/// whether the form stands in an `ALT` block; `in_alt` gives whether
/// `block` stands in one.
fn each_inner_form<'a>(block: Block<'a>, in_alt: bool, f: &mut dyn FnMut(&'a Form, bool)) {
    let in_alt = in_alt || matches!(block, Block::Alt(_));
    for (_, inner) in inner_blocks(block, &|_| true) {
        match inner {
            Block::Form(form) => each_form(form, in_alt, f),
            Block::Alt(_) => each_inner_form(inner, in_alt, f),
        }
    }
}

/// The blocks that `block` holds, each by its index among the children of
/// `block` (`Claim::blocks`, `Alts::blocks`, `Alt::blocks`), each `ALT`
/// block where `enter` admits it. A form other than a claim or an `ALTS`
/// form holds none.
fn inner_blocks<'a>(block: Block<'a>, enter: &dyn Fn(&Alt) -> bool) -> Vec<(u32, Block<'a>)> {
    let blocks: Vec<Block<'a>> = match block {
        Block::Form(Form::Claim(claim)) => claim.value().blocks().collect(),
        Block::Form(Form::Alts(alts)) => alts.value().blocks().collect(),
        Block::Form(_) => Vec::new(),
        Block::Alt(alt) => alt.blocks().collect(),
    };
    (0u32..)
        .zip(blocks)
        .filter(|(_, inner)| match inner {
            Block::Form(_) => true,
            Block::Alt(alt) => enter(alt),
        })
        .collect()
}

/// Calls `f` on the relation of each atom below `node`.
fn each_read<'a>(node: NodeRef<'a>, f: &mut dyn FnMut(&'a RelationRef)) {
    if let Some(atom) = node.atom() {
        f(&atom.relation);
    }
    for child in node.children() {
        each_read(child, f);
    }
}
