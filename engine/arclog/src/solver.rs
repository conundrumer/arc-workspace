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
use crate::program::zero_columns;
use crate::program::canonical::relation_of;
use crate::write::relation_ref;
use crate::resolver::SolverScope;
use std::sync::Arc;

use crate::program::{
    written_inputs, Alt, Alts, AltsName, Block, Arcdata, Body, Clause, ClauseKeyword, ColumnName, DeclaredName, DemoRule, Demonstrated, DemonstratedPart, Form, Instance,
    InstanceInput, InstanceName, KeyBody, KeyClause, LabelId, LabelUse, Atom, Choose, Conjunct, FactRelation, Negated, Node, OutputOwner, OutputStep, PortName, Program, ProgramRelation, RelationColumn, RelationName, RelationRef, RigidDet, RigidDetName, RuleForms, Site, SiteArg, SiteValue,
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
    rederived: Box<[NodePath]>,
    /// The program as [`Case::program_alone`] gives it, where it differs from
    /// `program`.
    alone: Option<Node<Program>>,
}

impl Case {
    /// The paths in the case program of the `DET` forms it takes from the
    /// concept program, which resolve in the concept program, as
    /// [`crate::resolver::ConceptReads`] gives, so each reads the concept
    /// program's derivation in every case.
    pub fn concept_determinations(&self) -> &[NodePath] {
        &self.concept_determinations
    }

    /// The paths in the case program of the forms that a block other than the
    /// concept program gives: an alt's form that replaces or adds a thing,
    /// and a `DEMONSTRATED` form of the concept program that holds such a
    /// form in a `DEMO_RULE` form.
    pub fn rederived_forms(&self) -> &[NodePath] {
        &self.rederived
    }

    /// The case program as it reads when it stands alone, with no concept
    /// program to take a `DET` from, and with each column that is `0` in
    /// every clause of its relation dropped:
    ///
    /// - A `DET` of the concept program that reads the relation of a
    ///   `RULE_OR_DET` line at its stored reading reads the derivation of the
    ///   line's body, the line's helper, as the concept program reads it.
    /// - The columns that the zero-column lowering drops, as
    ///   `docs/arclog/arclog.md#negation-and-constraints` gives, each with the
    ///   `(= *X 0)` that made it. A form that the drop rewrites keeps its
    ///   place, so [`Case::file_path`] names its form of the file.
    ///
    /// It is the case program where neither applies.
    pub fn program_alone(&self) -> &Node<Program> {
        self.alone.as_ref().unwrap_or(&self.program)
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

    /// The names of `case_names(exclusion)` that take, at each
    /// `DET_OR_RULE` and `RULE_OR_DET` line they reach, the line's first
    /// reading, the concept case's: one name per base, the cases whose train
    /// pairs filter the values of a `DET`, as
    /// `docs/engine/determination.md#det` gives.
    pub fn base_case_names(&self, exclusion: Exclusion) -> Vec<CaseName> {
        let takes_first = |name: &CaseName| {
            let walk = self.walk(&name.0);
            walk.placed.iter().filter_map(|placed| line_of(&placed.form)).all(|line| !readings(line)[1..].iter().any(|(alt, _)| name.0.contains(alt)))
        };
        self.case_names(exclusion).into_iter().filter(takes_first).collect()
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
        let mut placed: Vec<Vec<Placed>> = walk.placed.iter().cloned().map(|p| vec![p]).collect();
        let mut stored = Vec::new();
        for (index, p) in walk.placed.iter().enumerate() {
            let Some(line) = line_of(&p.form) else { continue };
            let all = readings(line);
            let (alt, reading) = all.iter().find(|(alt, _)| name.0.contains(alt)).unwrap_or(&all[0]);
            if *alt != all[0].0 {
                other_readings.insert(p.step);
            }
            let port = port_of(line, &walk.placed);
            placed[index] = match (port, reading) {
                (Some(_), Reading::Derived(_)) if line.proposers.is_empty() => Vec::new(),
                _ => vec![Placed { form: Form::Clause(Node::new(read_as(line, *reading))), ..p.clone() }],
            };
            if line.keyword == ClauseKeyword::RuleOrDet && *reading == Reading::Stored {
                stored.push((index, line, port));
            } else if let (Some(Port { instance, name, input: true }), Reading::Stored) = (port, reading) {
                if let Some(Placed { form: Form::Instance(form), .. }) = placed[instance].first_mut() {
                    *form = Node::new(without_input(form.value(), name));
                }
            }
        }
        let concept_determination = |p: &Placed| p.depth == 0 && is_det(&p.form) && !other_readings.contains(&p.step);
        let mut helpers = Vec::new();
        if !stored.is_empty() {
            let mut used = self.declared_names();
            let read_columns = self.columns_read_in_any_block();
            for (index, line, port) in stored {
                let original = walk.placed[index].clone();
                // The instance's `INIT` form as it stood before `without_input`.
                let instance = port.and_then(|port| match &walk.placed[port.instance].form {
                    Form::Instance(instance) => Some(instance.value()),
                    _ => None,
                });
                let others: Vec<&Placed> = placed.iter().flatten().filter(|p| !concept_determination(p)).collect();
                let reading = stored_reading(line, port, instance, &others, read_columns.get(&line.derives).map_or(&[], |columns| columns), &mut used);
                let Some(reading) = reading else {
                    if let Some(Port { instance, name, input: true }) = port {
                        if let Some(Placed { form: Form::Instance(form), .. }) = placed[instance].first_mut() {
                            *form = Node::new(without_input(form.value(), name));
                        }
                    }
                    continue;
                };
                if let (Some(Port { instance, name, .. }), Some(body)) = (port, &reading.input) {
                    if let Some(Placed { form: Form::Instance(form), .. }) = placed[instance].first_mut() {
                        *form = Node::new(with_input_body(form.value(), name, body));
                    }
                }
                if let Some(rename) = &reading.rename {
                    for forms in placed.iter_mut() {
                        for p in forms.iter_mut() {
                            if !concept_determination(p) {
                                if let Some(form) = map_atoms(&p.form, &|atom| rename.of(atom)) {
                                    p.form = form;
                                }
                            }
                        }
                    }
                }
                if let Some(helper) = reading.helper {
                    helpers.push(helper);
                }
                placed[index] = reading.forms.into_iter().map(|form| Placed { form, ..original.clone() }).collect();
            }
        }
        let placed: Vec<Placed> = placed.into_iter().flatten().collect();
        let taken = rederived(&placed);
        let mut forms = Vec::new();
        let mut origins = StableHashMap::default();
        let mut concept_determinations = Vec::new();
        let mut rederived = Vec::new();
        for taken in taken {
            let p = taken.placed;
            let path = NodePath::top(forms.len() as u32);
            if p.depth > 0 || !taken.in_rules.is_empty() {
                rederived.push(path.clone());
            }
            if concept_determination(p) {
                concept_determinations.push(path.clone());
            }
            let (form, below) = taken.form();
            origins.extend(below.into_iter().map(|(at, origin)| (path.join(&at), origin)));
            origins.insert(path, (p.owner, p.path.clone()));
            forms.push(form);
        }
        let mut alone = forms.clone();
        let mut changed = false;
        for path in &concept_determinations {
            let at = path.0[0].0 as usize;
            for helper in &helpers {
                if let Some(form) = map_atoms(&alone[at], &|atom| helper.of(atom)) {
                    alone[at] = form;
                    changed = true;
                }
            }
        }
        if let Some(lowered) = zero_columns::lower(&alone, crate::registry::Registry::get()) {
            alone = lowered;
            changed = true;
        }
        let alone = changed.then(|| Node::new(Program { forms: alone.into() }));
        Ok(Case {
            name,
            program: Node::new(Program { forms: forms.into() }),
            origins,
            concept_determinations: concept_determinations.into(),
            rederived: rederived.into(),
            alone,
        })
    }

    /// The names of the relations that any form of the solver declares or
    /// reads, which a name made fresh avoids.
    fn declared_names(&self) -> StableHashSet<Box<str>> {
        let mut names = StableHashSet::default();
        let claims = self.representative_claims().map(|(_, form)| form);
        for form in self.program.value().forms.iter().chain(claims) {
            each_form(form, false, &mut |form, _| {
                if let Some(Derives::Relation(ProgramRelation::Declared(RelationName(DeclaredName::Written(name))))) = derives(form) {
                    names.insert(name);
                }
                each_read(NodeRef::from(form), &mut |read| {
                    if let RelationRef::Declared(RelationName(DeclaredName::Written(name))) = read {
                        names.insert(name.clone());
                    }
                });
            });
        }
        names
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

    /// The column names that the sites of the reads of each relation name,
    /// across the solver's forms and the claims of the solver its
    /// `representative` line names, through every `ALT` block, an `ALT` block
    /// that derives the relation included. A stored reading of a `RULE_OR_DET`
    /// line has a column for each one of these that the line holds, since each
    /// read in any case names columns of the `DET`.
    fn columns_read_in_any_block(&self) -> StableHashMap<ProgramRelation, Vec<ColumnName>> {
        let mut named = StableHashMap::default();
        let claims = self.representative_claims().map(|(_, form)| form);
        for form in self.program.value().forms.iter().chain(claims) {
            each_form(form, false, &mut |form, _| {
                each_atom(NodeRef::from(form), &mut |atom| {
                    let relation = match &atom.relation {
                        RelationRef::Declared(name) => ProgramRelation::Declared(name.clone()),
                        RelationRef::Output(output) => ProgramRelation::Output(output.clone()),
                        _ => return,
                    };
                    crate::resolver::add_columns(named.entry(relation).or_default(), atom.sites.iter().map(|site| &site.column));
                });
            });
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

    /// The alts that a case takes without departing from the concept case:
    /// each alt of the concept case's name, and the first reading of each
    /// `DET_OR_RULE` and `RULE_OR_DET` line that some base reads, the
    /// concept case's reading of that line, including a line that the
    /// concept case's own base does not reach.
    pub fn concept_alts(&self) -> Vec<AltsName> {
        let mut alts = self.all_case_names().swap_remove(0).0.into_vec();
        for base in alts_product(&self.program.value().forms) {
            for placed in &self.walk(&base).placed {
                if let Some(line) = line_of(&placed.form) {
                    let first = readings(line).swap_remove(0).0;
                    if !alts.contains(&first) {
                        alts.push(first);
                    }
                }
            }
        }
        alts
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

    /// Whether a form of the case other than `line` reads its relation: an
    /// atom that names it, or, for an input of an instance, the instance's
    /// `INIT` form, which holds that input. A form that a deeper block
    /// derives again (`rederived`) is not a form of the case, and a form
    /// that no read leads from to `&output` (`reaching_output`) reads
    /// nothing the case needs.
    fn read_elsewhere(&self, line: &Placed, clause: &Clause) -> bool {
        if port_of(clause, &self.placed).is_some_and(|port| port.input) {
            return true;
        }
        let relation = relation_of(&clause.derives);
        let kept: Vec<&Placed> = rederived(&self.placed).into_iter().map(|taken| taken.placed).collect();
        let reaching = reaching_output(&kept);
        kept.iter().zip(reaching).filter(|(p, reaches)| *reaches && !std::ptr::eq(**p, line)).any(|(p, _)| {
            let mut reads = false;
            each_read(NodeRef::from(&p.form), &mut |read| reads |= *read == relation);
            reads
        })
    }
}

/// For each of `forms`, whether the thing it derives reaches `&output`: it
/// is `&output`, or an instance or a rigid determination, or a form that
/// reaches `&output` reads it.
fn reaching_output(forms: &[&Placed]) -> Vec<bool> {
    let output = relation_of(&ProgramRelation::Declared(RelationName(DeclaredName::Written("&output".into()))));
    let derived: Vec<Option<RelationRef>> = forms
        .iter()
        .map(|p| match derives(&p.form) {
            Some(Derives::Relation(relation)) => Some(relation_of(&relation)),
            _ => None,
        })
        .collect();
    let mut reaching: Vec<bool> = derived.iter().map(|relation| relation.as_ref().is_none_or(|relation| *relation == output)).collect();
    loop {
        let mut changed = false;
        for reader in 0..forms.len() {
            if !reaching[reader] {
                continue;
            }
            each_read(NodeRef::from(&forms[reader].form), &mut |read| {
                for (index, relation) in derived.iter().enumerate() {
                    if !reaching[index] && relation.as_ref() == Some(read) {
                        reaching[index] = true;
                        changed = true;
                    }
                }
            });
        }
        if !changed {
            return reaching;
        }
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

/// `instance` with the body of its input `port` replaced by `body`, of its
/// key clause's inputs or of its own.
fn with_input_body(instance: &Instance, port: &PortName, body: &Node<Body>) -> Instance {
    let replaced = |inputs: &Arc<[Node<InstanceInput>]>| -> Arc<[Node<InstanceInput>]> {
        inputs
            .iter()
            .map(|input| if input.value().name == *port { Node::new(InstanceInput { body: body.clone(), ..input.value().clone() }) } else { input.clone() })
            .collect()
    };
    let key = instance.key.as_ref().map(|key| Node::new(KeyClause { inputs: replaced(&key.value().inputs), ..key.value().clone() }));
    Instance { key, inputs: replaced(&instance.inputs), ..instance.clone() }
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
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Reading {
    Stored,
    Derived(Option<usize>),
}

/// The readings of a line, each with its name, the concept case's first, as
/// `docs/arclog/arclog.md#the-alts-form` gives.
fn readings(line: &Clause) -> Vec<(AltsName, Reading)> {
    let relation = relation_ref(&relation_of(&line.derives), crate::write::declared);
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
/// columns; the stored reading alone keeps its `SET` mark. The line's body is one reading's, as
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
    // A reading with no body has no labels for the body's columns: its
    // proposer declares the columns.
    let columns = if body.value().conjuncts.is_empty() && !proposers.is_empty() { Arc::from([]) } else { line.columns.clone() };
    Clause { keyword, proposers, body, columns, set: line.set && reading == Reading::Stored, ..line.clone() }
}

/// A read of one relation that a form reads as another, with its sites as
/// they stand.
struct Rename {
    from: RelationRef,
    to: RelationRef,
    /// Whether an atom with a site on the Example column keeps reading
    /// `from`.
    keep_lifted: bool,
    /// The flat column that each field of a record column takes in `to`:
    /// the record column, the field, and the column of `to`.
    flat: Vec<(ColumnName, ColumnName, ColumnName)>,
}

/// Whether the read `atom` has a site on the Example column.
fn lifted(atom: &Atom) -> bool {
    atom.sites.iter().any(|site| site.column == crate::resolver::columns::example())
}

impl Rename {
    /// The atom read as `to`, or `None` where `atom` reads other than `from`
    /// or is kept.
    fn of(&self, atom: &Atom) -> Option<Atom> {
        (atom.relation == self.from && !(self.keep_lifted && lifted(atom))).then(|| Atom { relation: self.to.clone(), sites: self.sites(&atom.sites) })
    }

    /// The sites of a read of `from` as sites of a read of `to`: a site on a
    /// record column of `flat` is one site on the flat column of each
    /// field it names.
    fn sites(&self, sites: &[Site]) -> Arc<[Site]> {
        let flat = |record: &ColumnName, field: &ColumnName| self.flat.iter().find(|(r, f, _)| r == record && f == field).map(|(_, _, flat)| flat.clone());
        sites
            .iter()
            .flat_map(|site| match record_fields(site) {
                Some(fields) if self.flat.iter().any(|(record, _, _)| *record == site.column) => fields
                    .into_iter()
                    .map(|(field, label)| match flat(&site.column, &field) {
                        Some(column) => Site { column, value: SiteValue { args: Arc::new([SiteArg::Label(label)]) } },
                        None => site.clone(),
                    })
                    .collect::<Vec<_>>(),
                _ => vec![site.clone()],
            })
            .collect()
    }
}

/// The stored reading of a `RULE_OR_DET` line: its forms in place of the
/// line's one clause, as `docs/arclog/arclog.md#the-alts-form` gives.
struct StoredReading {
    /// The helper `RULE` where the reading has one, then the `DET`.
    forms: Vec<Form>,
    /// The reads of the line's port, which the forms of the case other than
    /// the concept determinations read as the `DET`.
    rename: Option<Rename>,
    /// The reads of the line's relation, which a concept determination reads
    /// as the helper when the case program stands alone.
    helper: Option<Rename>,
    /// On an input port, the body that replaces the input's clause in the
    /// instance: a read of the `DET`.
    input: Option<Node<Body>>,
}

/// One column of the relation a stored reading's `DET` determines: its name,
/// and the argument that stands at a site on it, whose label the site takes.
struct StoredColumn {
    name: ColumnName,
    arg: SiteArg,
    /// Where the column is the field of a record column of the line's port,
    /// the record column and the field.
    record: Option<(ColumnName, ColumnName)>,
}

/// The fields a site on a record column names, each with its label: a bare
/// label whose name is the field's, or a field site of one bare label.
fn record_fields(site: &Site) -> Option<Vec<(ColumnName, LabelUse)>> {
    site.value
        .args
        .iter()
        .map(|arg| match arg {
            SiteArg::NamedLabel { name, label } => Some((name.clone(), *label)),
            SiteArg::Field(field) => match &field.value.args[..] {
                [SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }] => Some((field.column.clone(), *label)),
                _ => None,
            },
            SiteArg::Label(_) => None,
        })
        .collect()
}

impl StoredColumn {
    /// The site on the port: the field site of a record column, where the
    /// column is a field.
    fn port_site(&self, label: LabelUse) -> Site {
        match &self.record {
            Some((record, field)) => {
                let field = Site { column: field.clone(), value: SiteValue { args: Arc::new([SiteArg::Label(label)]) } };
                Site { column: record.clone(), value: SiteValue { args: Arc::new([SiteArg::Field(field)]) } }
            }
            None => self.site(label),
        }
    }

    fn site(&self, label: LabelUse) -> Site {
        let arg = match &self.arg {
            SiteArg::NamedLabel { name, .. } => SiteArg::NamedLabel { name: name.clone(), label },
            _ => SiteArg::Label(label),
        };
        Site { column: self.name.clone(), value: SiteValue { args: Arc::new([arg]) } }
    }
}

/// The argument of a site that is one bare label, a fresh or joined one.
fn single_label(site: &Site) -> Option<(&SiteArg, LabelId)> {
    match &site.value.args[..] {
        [arg @ (SiteArg::Label(LabelUse::Fresh(id) | LabelUse::Join(id)) | SiteArg::NamedLabel { label: LabelUse::Fresh(id) | LabelUse::Join(id), .. })] => Some((arg, *id)),
        _ => None,
    }
}

/// The stored reading of the `RULE_OR_DET` line `line`, which stands on
/// `port` of `instance` where it has a port, or `None` where it holds no
/// body and stands on no port, or where its derivation cannot stand by
/// itself. `others` are the forms of the case that read the line's port. With
/// `D` the derivation, a relation read with a site on each of its columns:
///
/// ```text
/// (DET &r
///   (ex_output (:E *Ex))
///   (D (:E Ex) (:c *c) ...)
///   (ALL ((ex_output (:E *Ex2)))
///        ((D (:E Ex2) (:c c) ...))))
/// ```
///
/// A line with a body has the helper `RULE` as `D`; a line on an input has a
/// helper over the `INIT` form's clause of that input; a line on an output has
/// the port as `D`, and the `DET` takes a name of its own. The `DET` of a line
/// with a body has the columns of the line that a read of its relation names,
/// `read`, the Example column left out (`docs/arclog/arclog.md#sites`); the
/// helper has all of the line's.
///
/// A line on an output port of an instance with a key clause states its value
/// columns by [`value_columns`]: the `DET` determines those columns alone, each
/// field of a record column as a column of its own (`(:key D)` as `KeyD`),
/// reading the port with the others existential, and a `RULE` joins its rows
/// with the rows of the other columns that a read names, which the port gives
/// on the input. A read of the port in the case reads that `RULE`, a record
/// site expanded to one site on each field's column.
fn stored_reading(
    line: &Clause,
    port: Option<Port<'_>>,
    instance: Option<&Instance>,
    others: &[&Placed],
    read: &[ColumnName],
    used: &mut StableHashSet<Box<str>>,
) -> Option<StoredReading> {
    let relation = relation_of(&line.derives);
    let text = relation_ref(&relation, crate::write::declared);
    let fresh = |suffix: &str, used: &mut StableHashSet<Box<str>>| {
        let base = format!("{}{suffix}", text.replace('.', "_"));
        let mut name = base.clone();
        let mut count = 1;
        while used.contains(name.as_str()) {
            count += 1;
            name = format!("{base}{count}");
        }
        used.insert(name.as_str().into());
        RelationName(DeclaredName::Written(name.into()))
    };
    let helper = |name: &RelationName, body: Node<Body>, columns: Arc<[RelationColumn]>| {
        Form::Clause(Node::new(Clause {
            keyword: ClauseKeyword::Rule,
            derives: ProgramRelation::Declared(name.clone()),
            gloss: None,
            proposers: Arc::from([]),
            body,
            ones: Arc::from([]),
            set: false,
            columns,
        }))
    };
    if !line.body.value().conjuncts.is_empty() {
        let name = fresh("_derived", used);
        let named = line.columns.iter().filter(|column| column.name != crate::resolver::columns::example() && read.contains(&column.name));
        let columns = named.map(|column| StoredColumn { name: column.name.clone(), arg: SiteArg::Label(LabelUse::Zero), record: None }).collect::<Vec<_>>();
        let derivation = RelationRef::Declared(name.clone());
        let forms = vec![helper(&name, line.body.clone(), line.columns.clone()), Form::Clause(Node::new(determination(line, &derivation, &columns, false)))];
        return Some(StoredReading { forms, rename: None, helper: Some(Rename { from: relation, to: derivation, keep_lifted: false, flat: Vec::new() }), input: None });
    }
    let port = port?;
    if port.input {
        let instance = instance?;
        let input = written_inputs(instance.key.as_ref(), &instance.inputs).find(|input| input.name == *port.name)?;
        let mut heads = Vec::new();
        for site in input.head.iter() {
            let (arg, label) = single_label(site)?;
            heads.push((label, StoredColumn { name: site.column.clone(), arg: arg.clone(), record: None }));
        }
        // The helper's columns are the labels its body makes, in order, and
        // the `DET` reads the ones the head names, in that order.
        let mut columns = Vec::new();
        let mut labels = Vec::new();
        let mut made = Vec::new();
        let input_body = input.body.clone();
        for (position, label) in crate::read::columns::made_labels(input.body.value()).into_iter().enumerate() {
            match heads.iter().position(|(head, _)| *head == label) {
                Some(at) => {
                    let (_, column) = heads.remove(at);
                    made.push(RelationColumn { name: column.name.clone(), label });
                    columns.push(column);
                    labels.push(label);
                }
                None => made.push(RelationColumn { name: ColumnName::Slot(position as u32), label }),
            }
        }
        if !heads.is_empty() {
            return None;
        }
        let name = fresh("_derived", used);
        let derivation = RelationRef::Declared(name.clone());
        let mut det = determination(line, &derivation, &columns, false);
        let stored = fresh("_stored", used);
        det.derives = ProgramRelation::Declared(stored.clone());
        // The input then holds the rows of the `DET`: its clause reads it at
        // the labels its head names.
        let read = Atom {
            relation: RelationRef::Declared(stored),
            sites: columns.iter().zip(&labels).map(|(column, label)| column.site(LabelUse::Fresh(*label))).collect(),
        };
        let input = Node::new(Body { conjuncts: Arc::from([Conjunct::Atom(Node::new(read))]) });
        let forms = vec![helper(&name, input_body, made.into()), Form::Clause(Node::new(det))];
        return Some(StoredReading { forms, rename: None, helper: None, input: Some(input) });
    }
    let ProgramRelation::Output(_) = &line.derives else { return None };
    let keyed = instance.and_then(|instance| instance.key.as_ref());
    let key_column = crate::resolver::columns::key();
    let records: Vec<&ColumnName> = keyed.iter().map(|_| &key_column).collect();
    let mut plain: Vec<ColumnName> = Vec::new();
    let mut flat: Vec<(ColumnName, ColumnName, ColumnName)> = Vec::new();
    for placed in others {
        each_atom(NodeRef::from(&placed.form), &mut |atom| {
            if atom.relation == relation {
                plain.extend(atom.sites.iter().filter(|site| !records.contains(&&site.column)).map(|site| site.column.clone()));
            }
        });
    }
    // The flat column of a field of a record column: the column's name and
    // the field's, joined, and made fresh against the columns that are read.
    let mut flat_column = |record: &ColumnName, field: &ColumnName| {
        if let Some((_, _, column)) = flat.iter().find(|(r, f, _)| r == record && f == field) {
            return column.clone();
        }
        let ColumnName::Written(record_text) = record else { return field.clone() };
        let ColumnName::Written(field_text) = field else { return field.clone() };
        let mut chars = record_text.chars();
        let head: String = chars.next().into_iter().flat_map(char::to_uppercase).chain(chars).collect();
        let base = format!("{head}{field_text}");
        let mut name = ColumnName::Written(base.as_str().into());
        let mut count = 1;
        while plain.contains(&name) || flat.iter().any(|(_, _, taken)| *taken == name) {
            count += 1;
            name = ColumnName::Written(format!("{base}{count}").into());
        }
        flat.push((record.clone(), field.clone(), name.clone()));
        name
    };
    let mut columns: Vec<StoredColumn> = Vec::new();
    for placed in others {
        let mut shapes_ok = true;
        each_atom(NodeRef::from(&placed.form), &mut |atom| {
            if atom.relation != relation || lifted(atom) {
                return;
            }
            // A column new to `columns` stands after the column that precedes it
            // in this read, so the columns keep the order of the port's.
            let mut after: Option<ColumnName> = None;
            for site in atom.sites.iter() {
                let read: Option<Vec<StoredColumn>> = if records.contains(&&site.column) {
                    record_fields(site).map(|fields| {
                        fields
                            .into_iter()
                            .map(|(field, _)| StoredColumn { name: flat_column(&site.column, &field), arg: SiteArg::Label(LabelUse::Zero), record: Some((site.column.clone(), field)) })
                            .collect()
                    })
                } else {
                    single_label(site).map(|(arg, _)| vec![StoredColumn { name: site.column.clone(), arg: arg.clone(), record: None }])
                };
                let Some(read) = read else {
                    shapes_ok = false;
                    continue;
                };
                for column in read {
                    if !columns.iter().any(|known| known.name == column.name) {
                        let at = after.as_ref().and_then(|previous| columns.iter().position(|known| known.name == *previous)).map_or(0, |at| at + 1);
                        after = Some(column.name.clone());
                        columns.insert(at, column);
                    } else {
                        after = Some(column.name.clone());
                    }
                }
            }
        });
        if !shapes_ok {
            return None;
        }
    }
    let value_sites = keyed.map_or_else(Vec::new, |key| value_columns(key.value(), &key_column, &columns, others, &relation));
    if value_sites.is_empty() {
        let name = fresh("_stored", used);
        let det = RelationRef::Declared(name.clone());
        let mut clause = determination(line, &relation, &columns, false);
        clause.derives = ProgramRelation::Declared(name);
        return Some(StoredReading { forms: vec![Form::Clause(Node::new(clause))], rename: Some(Rename { from: relation, to: det, keep_lifted: true, flat: Vec::new() }), helper: None, input: None });
    }
    // The value columns, then the other columns read.
    let mut values = Vec::new();
    for (column, field) in &value_sites {
        let at = columns.iter().position(|known| match field {
            None => known.record.is_none() && known.name == *column,
            Some(field) => known.record.as_ref() == Some(&(column.clone(), field.clone())),
        });
        values.push(match at {
            Some(at) => columns.remove(at),
            None => match field {
                None => StoredColumn { name: column.clone(), arg: SiteArg::Label(LabelUse::Zero), record: None },
                Some(field) => StoredColumn { name: flat_column(column, field), arg: SiteArg::Label(LabelUse::Zero), record: Some((column.clone(), field.clone())) },
            },
        });
    }
    let value = fresh("_value", used);
    let stored = fresh("_stored", used);
    let value_ref = RelationRef::Declared(value.clone());
    let mut det = determination(line, &relation, &values, true);
    det.derives = ProgramRelation::Declared(value);
    // The `RULE` joins the value rows with the rows of the other columns
    // that the port gives on the input.
    let all: Vec<&StoredColumn> = values.iter().chain(&columns).collect();
    let atom = |relation: RelationRef, from: usize, taken: &[StoredColumn], port: bool| {
        let sites = taken.iter().zip(from as u32..).map(|(column, id)| if port { column.port_site(LabelUse::Fresh(LabelId(id))) } else { column.site(LabelUse::Fresh(LabelId(id))) });
        Conjunct::Atom(Node::new(Atom { relation, sites: sites.collect() }))
    };
    let mut conjuncts = vec![atom(value_ref, 0, &values, false)];
    if !columns.is_empty() {
        conjuncts.push(atom(relation.clone(), values.len(), &columns, true));
    }
    let rule_columns: Arc<[RelationColumn]> = all.iter().zip(0u32..).map(|(column, id)| RelationColumn { name: column.name.clone(), label: LabelId(id) }).collect();
    let rule = helper(&stored, Node::new(Body { conjuncts: conjuncts.into() }), rule_columns);
    let to = RelationRef::Declared(stored);
    let forms = vec![Form::Clause(Node::new(det)), rule];
    Some(StoredReading { forms, rename: Some(Rename { from: relation, to, keep_lifted: true, flat }), helper: None, input: None })
}

/// The value columns of the stored reading of a line on an output port of an
/// instance with the key clause `key`, each as the port's column and, for a
/// field of the key record `key_column`, the field: the key's fields, then
/// each of `columns` that every read of `relation` among `others` names with
/// the label that the same read gives a field of the key.
fn value_columns(key: &KeyClause, key_column: &ColumnName, columns: &[StoredColumn], others: &[&Placed], relation: &RelationRef) -> Vec<(ColumnName, Option<ColumnName>)> {
    let mut joined: Vec<&ColumnName> = columns.iter().filter(|column| column.record.is_none()).map(|column| &column.name).collect();
    for placed in others {
        each_atom(NodeRef::from(&placed.form), &mut |atom| {
            if atom.relation == *relation && !lifted(atom) {
                joined.retain(|column| names_key_field(atom, key_column, column));
            }
        });
    }
    let fields = key.key.columns.iter().map(|field| (key_column.clone(), Some(field.name.clone())));
    fields.chain(joined.into_iter().map(|column| (column.clone(), None))).collect()
}

/// Whether the read `atom` names `column` with the label that it gives a
/// field of its site on `key_column`.
fn names_key_field(atom: &Atom, key_column: &ColumnName, column: &ColumnName) -> bool {
    let site_on = |name: &ColumnName| atom.sites.iter().find(|site| site.column == *name);
    let (Some(key), Some(site)) = (site_on(key_column), site_on(column)) else { return false };
    let (Some(fields), Some((_, label))) = (record_fields(key), single_label(site)) else { return false };
    fields.iter().any(|(_, field)| matches!(field, LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id) if *id == label))
}

/// The `DET` of the line `line` that derives `line.derives` from the train
/// examples' rows of `derivation`, read with a site on each of `columns`:
/// the rows that `derivation` gives at every train example.
fn determination(line: &Clause, derivation: &RelationRef, columns: &[StoredColumn], at_port: bool) -> Clause {
    let count = columns.len() as u32;
    let (ex, ex2) = (LabelId(count), LabelId(count + 1));
    let example = |label: LabelUse| Site { column: crate::resolver::columns::example(), value: SiteValue { args: Arc::new([SiteArg::Label(label)]) } };
    let ex_output = |label: LabelUse| Conjunct::Atom(Node::new(Atom { relation: RelationRef::Fact(FactRelation::ExOutput), sites: Arc::from([example(label)]) }));
    let derivation_of = |at: LabelUse, make: &dyn Fn(u32) -> LabelUse| {
        let sites = std::iter::once(example(at)).chain(columns.iter().zip(0u32..).map(|(column, index)| if at_port { column.port_site(make(index)) } else { column.site(make(index)) }));
        Conjunct::Atom(Node::new(Atom { relation: derivation.clone(), sites: sites.collect() }))
    };
    let body = |conjuncts: Vec<Conjunct>| Node::new(Body { conjuncts: conjuncts.into() });
    let conjuncts = vec![
        ex_output(LabelUse::Fresh(ex)),
        derivation_of(LabelUse::Join(ex), &|index| LabelUse::Fresh(LabelId(index))),
        Conjunct::All {
            domain: body(vec![ex_output(LabelUse::Fresh(ex2))]),
            body: body(vec![derivation_of(LabelUse::Join(ex2), &|index| LabelUse::Join(LabelId(index)))]),
        },
    ];
    // The labels the body makes at its top level, in order, as the reader
    // takes them: the Example label first. The columns a read names are the
    // relation's; each other is existential.
    let own = std::iter::once(RelationColumn { name: ColumnName::Written("Ex".into()), label: ex });
    let made = own.chain(columns.iter().zip(0u32..).map(|(column, index)| RelationColumn { name: column.name.clone(), label: LabelId(index) }));
    Clause {
        keyword: ClauseKeyword::Det,
        derives: line.derives.clone(),
        gloss: line.gloss.clone(),
        proposers: Arc::from([]),
        body: body(conjuncts),
        ones: Arc::from([]),
        set: false,
        columns: made.collect(),
    }
}

/// `form` with each atom below it that `map` gives another atom for read as
/// that atom, or `None` where `map` changes none. The columns of each clause
/// and form stay as they are.
fn map_atoms(form: &Form, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Form> {
    fn atom(node: &Node<Atom>, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Node<Atom>> {
        map(node.value()).map(Node::new)
    }
    fn conjunct(c: &Conjunct, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Conjunct> {
        match c {
            Conjunct::Atom(a) => atom(a, map).map(Conjunct::Atom),
            Conjunct::Not(Negated::Atom(a)) => atom(a, map).map(|a| Conjunct::Not(Negated::Atom(a))),
            Conjunct::Not(Negated::Form(inner)) => conjunct(inner, map).map(|inner| Conjunct::Not(Negated::Form(Arc::new(inner)))),
            Conjunct::Constraint(_) => None,
            Conjunct::Or(branches) => bodies(branches, map).map(Conjunct::Or),
            Conjunct::If { test, then, otherwise } => {
                let parts = bodies(&[test.clone(), then.clone(), otherwise.clone()], map)?;
                Some(Conjunct::If { test: parts[0].clone(), then: parts[1].clone(), otherwise: parts[2].clone() })
            }
            Conjunct::All { domain, body: inner } => {
                let parts = bodies(&[domain.clone(), inner.clone()], map)?;
                Some(Conjunct::All { domain: parts[0].clone(), body: parts[1].clone() })
            }
        }
    }
    fn body(node: &Node<Body>, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Node<Body>> {
        let changed: Vec<Option<Conjunct>> = node.value().conjuncts.iter().map(|c| conjunct(c, map)).collect();
        if changed.iter().all(Option::is_none) {
            return None;
        }
        let conjuncts = node.value().conjuncts.iter().zip(changed).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect();
        Some(Node::new(Body { conjuncts }))
    }
    /// Each of `nodes`, the changed ones as changed, or `None` where none is.
    fn bodies(nodes: &[Node<Body>], map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Arc<[Node<Body>]>> {
        let changed: Vec<Option<Node<Body>>> = nodes.iter().map(|n| body(n, map)).collect();
        if changed.iter().all(Option::is_none) {
            return None;
        }
        Some(nodes.iter().zip(changed).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect())
    }
    fn key_body(key: &KeyBody, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<KeyBody> {
        body(&key.body, map).map(|b| KeyBody { body: b, columns: key.columns.clone() })
    }
    fn input(node: &Node<InstanceInput>, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Node<InstanceInput>> {
        body(&node.value().body, map).map(|b| Node::new(InstanceInput { body: b, ..node.value().clone() }))
    }
    fn inputs(nodes: &Arc<[Node<InstanceInput>]>, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Arc<[Node<InstanceInput>]>> {
        let changed: Vec<Option<Node<InstanceInput>>> = nodes.iter().map(|n| input(n, map)).collect();
        if changed.iter().all(Option::is_none) {
            return None;
        }
        Some(nodes.iter().zip(changed).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect())
    }
    fn key_clause(key: &Option<Node<KeyClause>>, map: &dyn Fn(&Atom) -> Option<Atom>) -> Option<Option<Node<KeyClause>>> {
        let node = key.as_ref()?;
        let changed_body = key_body(&node.value().key, map);
        let changed_inputs = inputs(&node.value().inputs, map);
        if changed_body.is_none() && changed_inputs.is_none() {
            return None;
        }
        Some(Some(Node::new(KeyClause {
            key: changed_body.unwrap_or_else(|| node.value().key.clone()),
            inputs: changed_inputs.unwrap_or_else(|| node.value().inputs.clone()),
        })))
    }
    match form {
        Form::Clause(clause) => body(&clause.value().body, map).map(|b| Form::Clause(Node::new(Clause { body: b, ..clause.value().clone() }))),
        Form::Instance(instance) => {
            let instance = instance.value();
            let key = key_clause(&instance.key, map);
            let own = inputs(&instance.inputs, map);
            if key.is_none() && own.is_none() {
                return None;
            }
            Some(Form::Instance(Node::new(Instance {
                key: key.unwrap_or_else(|| instance.key.clone()),
                inputs: own.unwrap_or_else(|| instance.inputs.clone()),
                ..instance.clone()
            })))
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let rows = choose.rows.as_ref().and_then(|rows| key_body(rows, map));
            let from = body(&choose.from, map);
            let never = bodies(&choose.never, map);
            if rows.is_none() && from.is_none() && never.is_none() {
                return None;
            }
            Some(Form::Choose(Node::new(Choose {
                rows: rows.or_else(|| choose.rows.clone()),
                from: from.unwrap_or_else(|| choose.from.clone()),
                never: never.unwrap_or_else(|| choose.never.clone()),
                ..choose.clone()
            })))
        }
        Form::RigidDet(rigid) => {
            let rigid = rigid.value();
            let key = rigid.key.as_ref().and_then(|key| key_body(key, map));
            let instance = rigid.instance.as_ref().and_then(|instance| key_body(instance, map));
            let changed: Vec<Option<Node<Atom>>> = rigid.parts.iter().map(|part| atom(part, map)).collect();
            if key.is_none() && instance.is_none() && changed.iter().all(Option::is_none) {
                return None;
            }
            let parts = rigid.parts.iter().zip(changed).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect();
            Some(Form::RigidDet(Node::new(RigidDet {
                name: rigid.name.clone(),
                key: key.or_else(|| rigid.key.clone()),
                instance: instance.or_else(|| rigid.instance.clone()),
                parts,
            })))
        }
        Form::Demonstrated(demonstrated) => {
            let demonstrated = demonstrated.value();
            let key = key_clause(&demonstrated.key, map);
            let own = inputs(&demonstrated.inputs, map);
            let rules: Vec<Option<Node<DemoRule>>> = demonstrated
                .rules
                .iter()
                .map(|rule| {
                    let rule = rule.value();
                    let forms: Vec<Option<Form>> = rule.forms.iter().map(|form| map_atoms(form, map)).collect();
                    if forms.iter().all(Option::is_none) {
                        return None;
                    }
                    let forms: RuleForms = rule.forms.iter().zip(forms).enumerate().map(|(index, (old, new))| (new.unwrap_or_else(|| old.clone()), rule.forms.from_alt(index))).collect();
                    Some(Node::new(DemoRule { forms, ..rule.clone() }))
                })
                .collect();
            if key.is_none() && own.is_none() && rules.iter().all(Option::is_none) {
                return None;
            }
            Some(Form::Demonstrated(Node::new(Demonstrated {
                name: demonstrated.name.clone(),
                key: key.unwrap_or_else(|| demonstrated.key.clone()),
                inputs: own.unwrap_or_else(|| demonstrated.inputs.clone()),
                rules: demonstrated.rules.iter().zip(rules).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect(),
            })))
        }
        Form::Claim(_) | Form::Alts(_) => None,
    }
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

/// Whether two forms are of one variant and have equal nodes.
fn equal_forms(left: &Form, right: &Form) -> bool {
    match (left, right) {
        (Form::Claim(a), Form::Claim(b)) => a == b,
        (Form::Clause(a), Form::Clause(b)) => a == b,
        (Form::Instance(a), Form::Instance(b)) => a == b,
        (Form::Choose(a), Form::Choose(b)) => a == b,
        (Form::RigidDet(a), Form::RigidDet(b)) => a == b,
        (Form::Demonstrated(a), Form::Demonstrated(b)) => a == b,
        (Form::Alts(a), Form::Alts(b)) => a == b,
        _ => false,
    }
}

fn is_det(form: &Form) -> bool {
    matches!(form, Form::Clause(clause) if clause.value().keyword == ClauseKeyword::Det)
}

/// The forms of a case, from the forms its walk reaches: for each thing
/// derived, the forms of the deepest blocks that derive it, at the place of
/// the concept program's first form that derives it. The place of a thing
/// that a `DEMO_RULE` form of the concept program derives is in each such
/// form, at its first form that derives it, as [`Taken::in_rules`] gives.
/// Of the kept forms of one thing that are equal, the first in the walk's
/// order stands: forms that derive one thing equally derive it once, so their
/// combination needs no nested `ALT`, and a relation is derived by one clause.
fn rederived(placed: &[Placed]) -> Vec<Taken<'_>> {
    let keys: Vec<Derives> = placed.iter().map(|p| derives(&p.form).expect("a reached form derives")).collect();
    let mut deepest: StableHashMap<&Derives, u32> = StableHashMap::default();
    for (p, key) in placed.iter().zip(&keys) {
        let depth = deepest.entry(key).or_insert(p.depth);
        *depth = (*depth).max(p.depth);
    }
    let mut keep: Vec<bool> = placed.iter().zip(&keys).map(|(p, key)| p.depth == deepest[key]).collect();
    for index in 0..placed.len() {
        if keep[index] && (0..index).any(|earlier| keep[earlier] && keys[earlier] == keys[index] && equal_forms(&placed[earlier].form, &placed[index].form)) {
            keep[index] = false;
        }
    }
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
        if deepest[key] > 0 && placed_keys.insert(key) {
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
    /// Each keeps the label ids of its `ALT`, and is a label scope of its
    /// own in the rule.
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
            let mut forms: Vec<(Form, bool, (FileOwner, NodePath))> = Vec::new();
            let mut placed_keys = StableHashSet::default();
            for (at, form) in rule.value().forms.iter().enumerate() {
                let key = derives(form);
                let alts: Vec<&Placed> = self.in_rules.iter().copied().filter(|p| key.is_some() && derives(&p.form) == key).collect();
                if alts.is_empty() {
                    forms.push((form.clone(), false, (self.placed.owner, self.placed.path.child(step).child(at as u32))));
                } else if placed_keys.insert(key) {
                    forms.extend(alts.into_iter().map(|p| (p.form.clone(), true, (p.owner, p.path.clone()))));
                }
            }
            if placed_keys.is_empty() {
                return rule.clone();
            }
            let rule_path = NodePath::default().child(step);
            origins.extend(forms.iter().enumerate().map(|(at, (_, _, origin))| (rule_path.child(at as u32), origin.clone())));
            let forms = forms.into_iter().map(|(form, from_alt, _)| (form, from_alt)).collect();
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
