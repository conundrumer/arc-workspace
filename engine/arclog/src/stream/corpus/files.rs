//! The files of the cases of a solver: each case program read alone, written
//! as the `.arclog` and `.arcdata` texts of a solver of its own, and the
//! read of those files from the `cases/` directory of a corpus.
//!
//! A case's files are `cases/<task id>/<file>.arclog` and
//! `cases/<task id>/<file>.arcdata`, with `<file>` as [`case_file_name`]
//! gives it.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;

use crate::check::CheckCache;
use crate::harness::{panic_message, read_solver_texts};
use crate::layout::{Layout, NodeLayout, SourceFile, SourcePlace};
use crate::program::path::{node_at, NodePath, NodeRef, PathNode};
use crate::program::{constraint_second, Arcdata, ClauseKeyword, ColumnName, Conjunct, Constraint, Form, LabelId, LabelUse, Node, OutputOwner, Param, ProgramRelation, RelationColumn, RigidDetName, Site, SiteArg};
use crate::solver::{Case, CaseName, Exclusion, FileOwner, Solver};
use crate::trace::label_names::label_name;
use crate::write::{elide_out_sites, write_arcdata, write_arclog};

use super::{case_spelled, check_alone};

/// The texts of the two files of a case.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CaseTexts {
    pub arclog: String,
    pub arcdata: String,
}

/// The files of one case of a solver, or the fault that gives none.
#[derive(Clone, Debug)]
pub struct CaseFiles {
    /// The case as [`case_spelled`] writes its name.
    pub case: String,
    /// The case's file name, as [`case_file_name`] gives it.
    pub file: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// The texts, or the fault that the case's program has none.
    pub texts: Result<CaseTexts, String>,
}

/// The name of the files of the case `name`, without their extensions:
/// `concept` for the concept case, and otherwise its alts, each without its
/// `$`, joined by `+`.
pub fn case_file_name(name: &CaseName) -> String {
    if name.0.is_empty() {
        return "concept".to_owned();
    }
    name.0.iter().map(|alt| alt.0.replace('$', "")).collect::<Vec<_>>().join("+")
}

/// The files of each case of the solver `task_id` given by the texts
/// `arclog` and `arcdata`, every combination of alts, the excluded ones
/// included, in the order of the cases. `corpus` is the directory that holds
/// the files of the solvers the `arcdata` text names.
///
/// A case's `.arclog` text is its program read alone
/// ([`Case::program_alone`]), and its `.arcdata` text holds each `param`
/// record of the solver whose relation a `DET` of that program derives, and no
/// `exclude` record. The two texts read as a solver with no alts whose
/// concept case is that program. A case gets a fault in place of its texts
/// where its program read alone has no stream: a `DET` it takes from the
/// concept program reads a relation that a block other than the concept
/// program derives, or its reading of a line gives no program, as
/// [`super::case_stream`] gives.
///
/// `Err` where the solver's texts do not read, or two cases get one file
/// name.
pub fn case_files(task_id: &str, arclog: &str, arcdata: &str, corpus: &Path) -> Result<Vec<CaseFiles>, String> {
    let solver = read_solver_texts(corpus, task_id, arclog, arcdata).map_err(|e| format!("the solver's files do not read: {e}"))?;
    let concept = solver.concept_case().name;
    let mut files: Vec<CaseFiles> = Vec::new();
    let mut cache = CheckCache::default();
    for case in solver.cases(Exclusion::WithExcluded) {
        let file = case_file_name(&case.name);
        if let Some(taken) = files.iter().find(|held| held.file == file) {
            return Err(format!("the cases {} and {} get the file name {file}", taken.case, case_spelled(&case.name)));
        }
        let texts = catch_unwind(AssertUnwindSafe(|| case_texts(&solver, &case, &mut cache))).unwrap_or_else(|payload| {
            Err(format!("the writer panicked: {}", panic_message(&*payload).unwrap_or("a payload that is not a message")))
        });
        files.push(CaseFiles { case: case_spelled(&case.name), file, concept: case.name == concept, texts });
    }
    Ok(files)
}

/// The texts of the files of the case `name` in `corpus`, or `None` where it
/// has none, or the fault that the files stand in part or do not read.
pub(super) fn read_case_files(corpus: &Path, task_id: &str, name: &CaseName) -> Result<Option<CaseTexts>, String> {
    let directory = corpus.join("cases").join(task_id);
    let file = case_file_name(name);
    let read = |extension: &str| {
        let path = directory.join(format!("{file}.{extension}"));
        match std::fs::read_to_string(&path) {
            Ok(text) => Ok(Some(text)),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(format!("{}: {error}", path.display())),
        }
    };
    match (read("arclog")?, read("arcdata")?) {
        (Some(arclog), Some(arcdata)) => Ok(Some(CaseTexts { arclog, arcdata })),
        (None, None) => Ok(None),
        _ => Err(format!("{} holds only one of {file}.arclog and {file}.arcdata", directory.display())),
    }
}

/// The texts of the case `case` of `solver`, or the fault that it has none:
/// the fault that [`super::case_stream`] gives for the same case, where the
/// case's reading of a line gives no program
/// ([`crate::solver::Case::reading_fault`]), or the program read alone has
/// no stream or the checker refuses it.
fn case_texts(solver: &Solver, case: &Case, cache: &mut CheckCache) -> Result<CaseTexts, String> {
    if let Some(fault) = case.reading_fault() {
        return Err(format!("the case's reading of a line gives no program: {fault}"));
    }
    if !case.reads_alone_as_it_stands() {
        check_alone(case, cache).map_err(|fault| format!("the case program read alone has no files: {fault}"))?;
    }
    let program = case.program_alone();
    let mut layout = case_layout(solver, case);
    let arcdata = case_arcdata(solver, case, &mut layout);
    Ok(CaseTexts { arclog: write_arclog(program, &layout), arcdata: write_arcdata(&arcdata, &layout) })
}

/// The layout of the `.arclog` text of the case `case` of `solver`, the text
/// of its program read alone ([`Case::program_alone`]): the places of the
/// tokens and the names of the labels, as [`Placing::place`] gives them.
pub(super) fn case_layout(solver: &Solver, case: &Case) -> Layout {
    let mut layout = Layout::default();
    let mut line = 1;
    for (index, form) in case.program_alone().value().forms.iter().enumerate() {
        line = Placing { solver, case, index, form }.place(&mut layout, line);
    }
    layout
}

/// The name that `layout` gives the label `label` at `path` of the arclog
/// text: the one in the innermost node at or above `path` whose label names
/// hold `label`, since a label is made by the form that is its scope. `None`
/// where no node does.
pub(super) fn label_name_at<'a>(layout: &'a Layout, path: &NodePath, label: LabelId) -> Option<&'a str> {
    innermost_label_name(path, label, |at| layout.node(SourceFile::Arclog, at))
}

/// The name of `label` in the innermost node at or above `path` that
/// `node_at` gives and whose label names hold `label`.
fn innermost_label_name<'a>(path: &NodePath, label: LabelId, node_at: impl Fn(&NodePath) -> Option<&'a NodeLayout>) -> Option<&'a str> {
    (0..=path.0.len()).rev().find_map(|depth| {
        let node = node_at(&NodePath(path.0[..depth].into()))?;
        node.label_names.iter().find(|(id, _)| *id == label).map(|(_, name)| &**name)
    })
}

/// The solver whose file holds a node of a case program.
fn owner_solver(solver: &Solver, owner: FileOwner) -> &Solver {
    match owner {
        FileOwner::Solver => solver,
        FileOwner::Representative => solver.representative.as_deref().expect("a case program with a node of the representative's file has a representative"),
    }
}

/// Whether two nodes are the one node: a case program shares the nodes of the
/// solver's tree that it takes as they stand.
fn same_node(a: NodeRef, b: NodeRef) -> bool {
    std::mem::discriminant(&a) == std::mem::discriminant(&b) && a.address() == b.address()
}

/// The place at the start of line `line`.
fn line_start(file: SourceFile, line: u32) -> SourcePlace {
    SourcePlace { file, start: 0, end: 0, line, column: 1 }
}

/// `place` moved by `shift`.
fn moved(place: SourcePlace, shift: Shift) -> SourcePlace {
    let line = u32::try_from(i64::from(place.line) + shift.lines).expect("a place moved to a line from 1");
    SourcePlace { line, column: place.column.saturating_sub(shift.columns).max(1), ..place }
}

/// How far the places of a form move: down by `lines`, and left by `columns`.
#[derive(Clone, Copy)]
struct Shift {
    lines: i64,
    columns: u32,
}

impl Shift {
    /// The shift that takes the place `from` to the start of line `line`.
    fn to_line_start(from: SourcePlace, line: u32) -> Shift {
        Shift { lines: i64::from(line) - i64::from(from.line), columns: from.column - 1 }
    }
}

/// The calls of `visit` on `node` at `path` and on each node below it.
fn each_node<'a>(node: NodeRef<'a>, path: &NodePath, visit: &mut impl FnMut(&NodePath, NodeRef<'a>)) {
    visit(path, node);
    for (index, child) in node.children().into_iter().enumerate() {
        each_node(child, &path.child(index as u32), visit);
    }
}

/// One top-level form of a case program, to be placed in the layout of the
/// case's files.
struct Placing<'c> {
    solver: &'c Solver,
    case: &'c Case,
    index: usize,
    form: &'c Form,
}

impl Placing<'_> {
    /// Adds to `layout` the layout of the form, from the line `line`, and
    /// gives the line where the next form starts.
    ///
    /// A form of the case program that stands as its file writes it keeps
    /// the places of its tokens, moved to `line`, and the names of its labels.
    /// One that the zero-column lowering rewrote ([`Case::program_alone`])
    /// keeps the names of its labels, which the lowering leaves, and its
    /// tokens stand one space after the other. One that the case program
    /// rewrites or builds ([`Case::program`]) takes the names that
    /// [`fallback_names`] gives, and its tokens stand one space after the
    /// other.
    ///
    /// A node whose tokens are the file's keeps the file's elided sites. Each
    /// other atom, and each head of an instance's input, elides the sites
    /// that hold one label whose name in its scope is the site's column's
    /// name, as `docs/arclog/arclog.md#sites` gives.
    fn place(&self, layout: &mut Layout, line: u32) -> u32 {
        let top = NodePath::top(self.index as u32);
        let (owner, origin) = self.case.file_path(&top);
        let source = owner_solver(self.solver, owner);
        let taken = NodeRef::from(&self.case.program.value().forms[self.index]);
        let labels_stand = node_at(NodeRef::Program(source.program.value()), &origin).is_some_and(|written| same_node(written, taken));
        let tokens_stand = labels_stand && same_node(NodeRef::from(self.form), taken);
        let first_token = source.layout.node(SourceFile::Arclog, &origin).and_then(|node| node.tokens.first());
        let shift = match (tokens_stand, first_token) {
            (true, Some(first)) => Some(Shift::to_line_start(*first, line)),
            _ => None,
        };
        let mut last = line;
        let mut nodes: Vec<(NodePath, NodeLayout)> = Vec::new();
        // Whether the node took its tokens and its elided sites from the file.
        let mut copied: Vec<bool> = Vec::new();
        each_node(NodeRef::from(self.form), &top, &mut |path, _| {
            let below = NodePath(path.0[1..].into());
            let written = labels_stand.then(|| source.layout.node(SourceFile::Arclog, &origin.join(&below))).flatten();
            let mut node = NodeLayout::default();
            if let Some(written) = written {
                node.label_names = written.label_names.clone();
                if let Some(shift) = shift {
                    node.place = written.place.map(|place| moved(place, shift));
                    node.tokens = written.tokens.iter().map(|place| moved(*place, shift)).collect();
                    node.elided_sites = written.elided_sites.clone();
                }
            }
            if path == &top && shift.is_none() {
                node.tokens = Box::new([line_start(SourceFile::Arclog, line)]);
            }
            last = node.tokens.iter().map(|place| place.line).fold(last, u32::max);
            copied.push(written.is_some() && shift.is_some());
            nodes.push((path.clone(), node));
        });
        if !labels_stand {
            for (path, names) in fallback_names(self.form, &top) {
                let node = nodes.iter_mut().find(|(at, _)| *at == path).map(|(_, node)| node).expect("a scope of the form is a node of it");
                node.label_names = names.into();
            }
        }
        // The other nodes elide each site of one label that the layout names as the site's column.
        let mut elided: Vec<Box<[u32]>> = Vec::new();
        each_node(NodeRef::from(self.form), &top, &mut |path, node| {
            let sites = match node {
                NodeRef::Conjunct(conjunct) => conjunct.atom().map(|atom| &atom.value().sites[..]),
                NodeRef::InstanceInput(input) => Some(&input.head[..]),
                _ => None,
            };
            let name_of = |label: LabelId| innermost_label_name(path, label, |at| nodes.iter().find(|(held, _)| held == at).map(|(_, node)| node));
            let is_bare = |site: &Site| match (&site.column, &site.value.args[..]) {
                (ColumnName::Written(column), [SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label))]) => name_of(*label).is_some_and(|name| name == &**column),
                _ => false,
            };
            elided.push(sites.map_or_else(|| Box::new([]) as Box<[u32]>, |sites| sites.iter().enumerate().filter(|(_, site)| is_bare(site)).map(|(index, _)| index as u32).collect()));
        });
        for (((_, node), copied), elided) in nodes.iter_mut().zip(&copied).zip(elided) {
            if !copied {
                node.elided_sites = elided;
            }
        }
        layout.nodes.extend(nodes.into_iter().map(|(path, node)| ((SourceFile::Arclog, path), node)));
        if let Form::Out(out) = self.form {
            elide_out_sites(out.value(), &top, layout);
        }
        last + 2
    }
}

/// The label names of each scope of `form`, at `top`, the path of the form,
/// for a form whose label ids no layout names: the form's own scope, each
/// `DEMO_RULE` form of a `DEMONSTRATED` form, at the rule's path, and each
/// form that an `ALT` gave to a `DEMO_RULE` form, at the form's path.
///
/// The labels of a scope take, in this order: the name of the column that
/// the label gives a relation, the name of the field that a site of a column
/// of a type parameter reads, which labels of different bodies may share, and
/// the name of the column of the site that makes the label, PascalCase, with
/// the least digit suffix that gives a name that no other label of the scope
/// holds.
fn fallback_names(form: &Form, top: &NodePath) -> Vec<(NodePath, Vec<(LabelId, Box<str>)>)> {
    let mut scopes: Vec<(NodePath, Uses)> = vec![(top.clone(), Uses::default())];
    each_node(NodeRef::from(form), top, &mut |path, node| {
        if let NodeRef::DemoRule(rule) = node {
            scopes.push((path.clone(), Uses::default()));
            let given = (0..rule.forms.len()).filter(|index| rule.forms.from_alt(*index));
            scopes.extend(given.map(|index| (path.child(index as u32), Uses::default())));
        }
        // The innermost scope that holds `path`: the last one it starts with.
        let scope = scopes.iter_mut().rev().find(|(at, _)| path.0.starts_with(&at.0)).map(|(_, uses)| uses).expect("the form's own scope holds each node of it");
        scope.node(node);
    });
    scopes.into_iter().map(|(path, uses)| (path, uses.names())).collect()
}

/// The base of the name of a label that no site of a named column makes.
const UNMADE_BASE: &str = "V";

/// The labels of one scope, collected in any order.
#[derive(Default)]
struct Uses {
    /// The labels that a site of a column of a type parameter reads as a
    /// field, with that field's name.
    reserved: Vec<(LabelId, Box<str>)>,
    /// The labels that give a relation a column, with the column's name.
    columns: Vec<(LabelId, Box<str>)>,
    /// Each label with the column of the site that makes it.
    made: Vec<(LabelId, String)>,
    /// Each label the scope uses.
    used: Vec<LabelId>,
}

impl Uses {
    fn node(&mut self, node: NodeRef) {
        match node {
            NodeRef::Clause(clause) => {
                self.columns(&clause.columns);
                self.used.extend(clause.ones.iter().flat_map(|mark| mark.key.iter().copied()));
            }
            NodeRef::KeyClause(key) => self.columns(&key.key.columns),
            NodeRef::Choose(choose) => {
                if let Some(rows) = &choose.rows {
                    self.columns(&rows.columns);
                }
                self.columns(&choose.candidate_columns);
            }
            NodeRef::RigidDet(rigid) => {
                for key in [&rigid.key, &rigid.instance].into_iter().flatten() {
                    self.columns(&key.columns);
                }
            }
            NodeRef::DemoRule(rule) => self.columns(&rule.fields),
            NodeRef::Site(site) => self.site(site),
            NodeRef::Conjunct(Conjunct::Constraint(constraint)) => self.constraint(constraint),
            _ => {}
        }
    }

    fn columns(&mut self, columns: &[RelationColumn]) {
        for column in columns {
            self.used.push(column.label);
            if let ColumnName::Written(name) = &column.name {
                self.columns.push((column.label, name.clone()));
            }
        }
    }

    fn constraint(&mut self, constraint: &Constraint) {
        let operands = [Some(constraint.first), constraint_second(constraint)];
        for operand in operands.into_iter().flatten() {
            self.used.push(operand.label);
            if operand.fresh {
                self.made.push((operand.label, UNMADE_BASE.to_owned()));
            }
        }
    }

    fn site(&mut self, site: &Site) {
        let column = match &site.column {
            ColumnName::Written(text) => text.to_string(),
            ColumnName::Slot(_) => UNMADE_BASE.to_owned(),
        };
        for arg in site.value.args.iter() {
            let label = match arg {
                SiteArg::Label(label) => *label,
                SiteArg::NamedLabel { name, label } => {
                    if let (ColumnName::Written(name), LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) = (name, label) {
                        self.reserved.push((*id, name.clone()));
                    }
                    *label
                }
                SiteArg::Field(_) => continue,
            };
            match label {
                LabelUse::Fresh(id) | LabelUse::Key(id) => {
                    self.used.push(id);
                    self.made.push((id, column.clone()));
                }
                LabelUse::Join(id) => self.used.push(id),
                LabelUse::Zero => {}
            }
        }
    }

    /// The name of each label of the scope.
    fn names(&self) -> Vec<(LabelId, Box<str>)> {
        let mut names: Vec<(LabelId, Box<str>)> = Vec::new();
        for (id, name) in &self.columns {
            if !names.iter().any(|(named, held)| named == id || held == name) {
                names.push((*id, name.clone()));
            }
        }
        // Labels of different bodies of one scope may read one field, so they may share its name.
        for (id, name) in &self.reserved {
            if !names.iter().any(|(named, _)| named == id) {
                names.push((*id, name.clone()));
            }
        }
        let mut rest: Vec<(LabelId, &str)> = self.used.iter().map(|id| (*id, UNMADE_BASE)).collect();
        for (id, column) in &self.made {
            if let Some(entry) = rest.iter_mut().find(|(rest_id, _)| rest_id == id) {
                entry.1 = column;
            }
        }
        rest.sort_by_key(|(id, _)| id.0);
        rest.dedup_by_key(|(id, _)| *id);
        for (id, base) in rest {
            if names.iter().any(|(named, _)| *named == id) {
                continue;
            }
            let taken = |name: &str| names.iter().any(|(_, held)| &**held == name);
            let name = label_name(base, taken);
            names.push((id, name.into()));
        }
        names
    }
}

/// The arcdata of the case `case` of `solver`: each `param` record of the
/// solver whose relation a `DET` of the case program derives, or whose
/// `RIGID_DET` form the case program holds, and no other record. The
/// layout of each record, from the solver's, is added to `layout`.
fn case_arcdata(solver: &Solver, case: &Case, layout: &mut Layout) -> Node<Arcdata> {
    let forms = &case.program_alone().value().forms;
    let determined: Vec<&ProgramRelation> = forms
        .iter()
        .filter_map(|form| match form {
            Form::Clause(clause) if clause.value().keyword == ClauseKeyword::Det => Some(&clause.value().derives),
            _ => None,
        })
        .collect();
    let rigid: Vec<&RigidDetName> = forms.iter().filter_map(|form| if let Form::RigidDet(rigid) = form { Some(&rigid.value().name) } else { None }).collect();
    let read = |param: &Param| {
        determined.contains(&&param.name) || matches!(&param.name, ProgramRelation::Output(output) if matches!(&output.of, OutputOwner::RigidDet(name) if rigid.contains(&name)))
    };
    let arcdata = solver.arcdata.value();
    let first = u32::from(arcdata.representative.is_some());
    let mut kept: Vec<Node<Param>> = Vec::new();
    let mut line = 1;
    for (index, param) in arcdata.params.iter().enumerate().filter(|(_, param)| read(param.value())) {
        let written = solver.layout.node(SourceFile::Arcdata, &NodePath::top(first + index as u32));
        let new = NodePath::top(kept.len() as u32);
        let mut node = NodeLayout::default();
        if let Some(written) = written {
            let shift = written.tokens.first().map(|start| Shift::to_line_start(*start, line));
            let at = |place: &SourcePlace| shift.map_or(*place, |shift| moved(*place, shift));
            node.place = written.place.as_ref().map(at);
            node.tokens = written.tokens.iter().map(at).collect();
            line = node.tokens.iter().map(|place| place.line).fold(line, u32::max) + 1;
        }
        layout.nodes.insert((SourceFile::Arcdata, new), node);
        kept.push(param.clone());
    }
    Node::new(Arcdata { representative: None, params: kept.into(), excludes: Default::default(), witness_records: Default::default() })
}
