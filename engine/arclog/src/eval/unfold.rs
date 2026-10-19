//! `Unfold`: its states, its rounds, the forks of a tied `score`, and the
//! distinct outputs of its walks.
//!
//! A state is the cursor `t` with its `taken`, `untaken` and `excluded`
//! sets. Each round evaluates the instance's `step`, `skip` and `take`
//! bodies against the current states, a `NOT` in them reading the current
//! state. A state already reached is not expanded again, and the states are
//! finite, so the rounds end. Where a `score` ties, the walk forks: each
//! walk is one tiebreak resolution, as
//! `docs/handbook/solver-file.md#alt-outputs` gives, and walks that reach
//! states of equal content share that state.
//!
//! A step from a state moves the items of its take as `Take` of
//! `programs/lib/orders.dl` does at one cursor: the take joins `taken`, an
//! untaken item that differs from an item of the take stays `untaken`, or
//! leaves it as `excluded` where that item is in conflict with it.

use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::ir::{self, ClauseIr};
use super::join::{self, Budget};
use super::{Evaluation, FormBodies, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::check::instance_inputs::inputs_at;
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, InstanceInput, LabelId, OutputStep, PortName};
use crate::registry::{Column, Component, LibEntry};
use crate::relations::{Row, RowSet};
use crate::terms::{Constant, Example, Term, TermId};
use crate::types::{each_site_label, use_label, GraphRelation, ValueType};

/// A state of an `Unfold` walk, on one key: its cursor and its three sets
/// of items, each sorted, so that states of equal content are equal.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct UnfoldState {
    pub cursor: TermId,
    pub taken: Box<[TermId]>,
    pub untaken: Box<[TermId]>,
    pub excluded: Box<[TermId]>,
}

/// The index of a state in a [`StateGraph`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct StateIndex(pub u32);

/// One way a round continues from a state: the items it takes, and the
/// states its `step` and `skip` rows reach.
#[derive(Clone, Debug)]
pub struct Branch {
    pub take: Box<[TermId]>,
    pub next: Box<[StateIndex]>,
}

/// The states an `Unfold` instance reaches on one key, and the edges of its
/// rounds between them.
#[derive(Clone, Debug, Default)]
pub struct StateGraph {
    pub states: Vec<UnfoldState>,
    /// The states of the `start` rows.
    pub starts: Vec<StateIndex>,
    /// For each state, its branches: one per item of least `score` where
    /// several tie, and otherwise one. A walk takes one branch of each
    /// state it reaches.
    pub branches: Vec<Box<[Branch]>>,
}

/// An output of `Unfold`, each of key, cursor and item.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum UnfoldOutput {
    Taken,
    Untaken,
    Excluded,
    Take,
}

impl UnfoldOutput {
    const ALL: [UnfoldOutput; 4] = [UnfoldOutput::Taken, UnfoldOutput::Untaken, UnfoldOutput::Excluded, UnfoldOutput::Take];

    fn port(self) -> PortName {
        let name = match self {
            UnfoldOutput::Taken => "taken",
            UnfoldOutput::Untaken => "untaken",
            UnfoldOutput::Excluded => "excluded",
            UnfoldOutput::Take => "take",
        };
        PortName(name.into())
    }

    /// Adds to `rows` the rows of this output at `state` on `branch`, the
    /// branch a walk takes there, each `key`, the cursor, then the item.
    fn add_rows(self, key: &[TermId], state: &UnfoldState, branch: &Branch, rows: &mut RowSet) {
        let items: &[TermId] = match self {
            UnfoldOutput::Taken => &state.taken,
            UnfoldOutput::Untaken => &state.untaken,
            UnfoldOutput::Excluded => &state.excluded,
            UnfoldOutput::Take => &branch.take,
        };
        for &item in items {
            rows.insert(key.iter().copied().chain([state.cursor, item]).collect());
        }
    }
}

/// An input of `Unfold`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum UnfoldInput {
    Start,
    InitialTaken,
    InitialUntaken,
    Conflict,
    Score,
    Step,
    Skip,
    Take,
}

impl UnfoldInput {
    fn port(self) -> PortName {
        let name = match self {
            UnfoldInput::Start => "start",
            UnfoldInput::InitialTaken => "initial_taken",
            UnfoldInput::InitialUntaken => "initial_untaken",
            UnfoldInput::Conflict => "conflict",
            UnfoldInput::Score => "score",
            UnfoldInput::Step => "step",
            UnfoldInput::Skip => "skip",
            UnfoldInput::Take => "take",
        };
        PortName(name.into())
    }
}

/// The state graph of the `Unfold` instance whose `INIT` form stands at
/// `form`, on each of its keys, with the key's labels of the key clause, or
/// no label where it has none; `output` is an output of the instance. The
/// value of a body that is `undefined` or stopped is given in place of the
/// graphs.
pub fn unfold<'a>(
    evaluation: &Evaluation<'a>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &GraphRelation,
    example: Option<Example>,
    budget: &mut Budget<'a>,
) -> Outcome<Result<Vec<(Row, StateGraph)>, RelationValue>> {
    let shape = UnfoldForm::of(evaluation, form)?;
    let run = Run { evaluation, bodies, shape: &shape, example, own: own_outputs(evaluation, output, example) };
    run.graphs(budget)
}

/// The distinct values of `output` over the walks of `graph`, each the rows
/// of the states along one walk, each state's once, with `key` before the
/// cursor and the item of each row, and at most `limit` of them: the
/// collection stops at the `limit`-th distinct value. Which values a stop
/// leaves out follows the order of the term ids of the tied items.
pub fn distinct_outputs(
    graph: &StateGraph,
    output: UnfoldOutput,
    key: &[TermId],
    limit: usize,
    budget: &mut Budget<'_>,
) -> Result<Vec<RowSet>, ReachedBound> {
    let arity = (key.len() + 2) as u16;
    let mut seen: StableHashSet<Vec<Row>> = StableHashSet::default();
    let mut values = Vec::new();
    let mut visit = |chosen: &[Option<u32>]| {
        let mut rows = RowSet::empty(arity);
        for ((state, branches), branch) in graph.states.iter().zip(&graph.branches).zip(chosen) {
            let Some(branch) = branch else { continue };
            output.add_rows(key, state, &branches[*branch as usize], &mut rows);
        }
        let mut sorted: Vec<Row> = rows.rows().map(Row::from).collect();
        sorted.sort_by(|a, b| a.iter().map(|id| id.encoding()).cmp(b.iter().map(|id| id.encoding())));
        if seen.insert(sorted) {
            values.push(rows);
        }
        values.len() < limit
    };
    let reached = initial_reach(graph);
    extend(graph, vec![None; graph.states.len()], reached.0, reached.1, budget, &mut visit)?;
    Ok(values)
}

/// The values of `output`, an output of the `Unfold` instance at `form`:
/// one per distinct value over its walks, at most `limit`, so one value
/// where no `score` ties, on `example`, or task-wide where it is `None`,
/// with the instance's bodies evaluated through `bodies`. The walks of
/// several keys combine, each value one walk on each key.
pub fn evaluate_unfold<'a>(
    evaluation: &Evaluation<'a>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    output: &GraphRelation,
    example: Option<Example>,
    limit: usize,
    budget: &mut Budget<'a>,
) -> Outcome<Vec<RelationValue>> {
    let Some([OutputStep::Port(port)]) = output.output.as_deref() else { panic!("an instance output read by its port") };
    let which = UnfoldOutput::ALL.into_iter().find(|candidate| candidate.port() == *port).expect("an output `Unfold` declares");
    let graphs = match unfold(evaluation, bodies, form, output, example, budget)? {
        Ok(graphs) => graphs,
        Err(value) => return Ok(vec![value]),
    };
    let types = evaluation.program.types.columns(output);
    let arity = types.ok_or_else(|| RunFault { message: "the output's columns have no types".into(), form: form.clone() })?.len() as u16;
    let mut values = vec![RowSet::empty(arity)];
    for (key, graph) in &graphs {
        let key = output_key(key);
        let walks = match distinct_outputs(graph, which, &key, limit, budget) {
            Ok(walks) => walks,
            Err(bound) => return Ok(vec![RelationValue::Stopped(Stop { bound, form: form.clone() })]),
        };
        let mut combined = Vec::new();
        'combine: for value in &values {
            for walk in &walks {
                let mut rows = value.clone();
                for row in walk.rows() {
                    rows.insert(row.into());
                }
                combined.push(rows);
                if combined.len() == limit {
                    break 'combine;
                }
            }
        }
        values = combined;
    }
    Ok(values.into_iter().map(|rows| RelationValue::Rows(Arc::new(join::one_part(rows)))).collect())
}

/// The positions of an output's `key` column for the key `key`: its
/// labels, or one `Unit` for the one key of a form with no key clause.
fn output_key(key: &[TermId]) -> Row {
    if key.is_empty() { Box::from([Term::Constant(Constant::Unit).encode().expect("a Unit has a term id")]) } else { key.into() }
}

/// The states a walk reaches before it takes a branch: the starts, each
/// marked reached and pending.
fn initial_reach(graph: &StateGraph) -> (Vec<bool>, Vec<StateIndex>) {
    let mut reached = vec![false; graph.states.len()];
    let mut pending = Vec::new();
    for &start in &graph.starts {
        if !std::mem::replace(&mut reached[start.0 as usize], true) {
            pending.push(start);
        }
    }
    (reached, pending)
}

/// Extends a walk, whose branch at each state is `chosen`, by the states
/// `pending` that it reached and has not yet left, forking at each state
/// of several branches, and gives each complete walk to `visit` until it
/// gives `false`. Gives whether to go on.
fn extend(
    graph: &StateGraph,
    mut chosen: Vec<Option<u32>>,
    mut reached: Vec<bool>,
    mut pending: Vec<StateIndex>,
    budget: &mut Budget<'_>,
    visit: &mut dyn FnMut(&[Option<u32>]) -> bool,
) -> Result<bool, ReachedBound> {
    while let Some(state) = pending.pop() {
        budget.charge_work(1)?;
        let branches = &graph.branches[state.0 as usize];
        let take = |chosen: &mut Vec<Option<u32>>, reached: &mut Vec<bool>, pending: &mut Vec<StateIndex>, index: usize| {
            chosen[state.0 as usize] = Some(index as u32);
            for &next in branches[index].next.iter() {
                if !std::mem::replace(&mut reached[next.0 as usize], true) {
                    pending.push(next);
                }
            }
        };
        if branches.len() == 1 {
            take(&mut chosen, &mut reached, &mut pending, 0);
            continue;
        }
        for index in 0..branches.len() {
            let (mut chosen, mut reached, mut pending) = (chosen.clone(), reached.clone(), pending.clone());
            take(&mut chosen, &mut reached, &mut pending, index);
            if !extend(graph, chosen, reached, pending, budget, visit)? {
                return Ok(false);
            }
        }
        return Ok(true);
    }
    Ok(visit(&chosen))
}

/// What the `INIT` form of an `Unfold` instance gives its evaluation: its
/// key body and key labels, and the inputs it writes with their paths and
/// whether each stands in the key clause.
struct UnfoldForm<'p> {
    form: &'p NodePath,
    component: &'p Component,
    key_body: Option<(&'p Body, NodePath)>,
    key_labels: Vec<LabelId>,
    written: Vec<(NodePath, bool, &'p InstanceInput)>,
}

impl<'p> UnfoldForm<'p> {
    fn of(evaluation: &Evaluation<'p>, form: &'p NodePath) -> Outcome<Self> {
        let root = NodeRef::Program(evaluation.program.program.program.value());
        let Some(NodeRef::Instance(instance)) = node_at(root, form) else { panic!("an `INIT` form at the form of a recursive instance") };
        let Some(LibEntry::Component(component)) = evaluation.registry.entry(&instance.component) else {
            return Err(RunFault { message: format!("the engine does not evaluate the component `{}`", instance.component.0).into(), form: form.clone() });
        };
        let key = instance.key.as_ref().map(|key| key.value());
        let key_body = key.map(|key| (key.key.body.value(), form.child(0).child(0)));
        let key_labels = key.map_or_else(Vec::new, |key| key.key.columns.iter().map(|column| column.label).collect());
        let written = inputs_at(instance).into_iter().map(|(path, keyed, input)| (form.join(&path), keyed, input)).collect();
        Ok(UnfoldForm { form, component, key_body, key_labels, written })
    }

    fn fault(&self, message: String) -> RunFault {
        RunFault { message: message.into(), form: self.form.clone() }
    }

    /// The clause of `input` where the form writes it, whose columns are
    /// the key's labels where the input stands in the key clause, then the
    /// label of each head site in the order of the port's columns, with
    /// whether it holds the key's labels.
    fn compile(&self, evaluation: &Evaluation<'_>, input: UnfoldInput) -> Outcome<Option<(ClauseIr, bool)>> {
        let port = input.port();
        let declared = self.component.inputs.iter().find(|declared| declared.port.name == port);
        let declared = declared.ok_or_else(|| self.fault(format!("the component declares no input `{}`", port.0)))?;
        let Some((path, keyed, written)) = self.written.iter().find(|(_, _, written)| written.name == port) else { return Ok(None) };
        let head = head_labels(written, &declared.port.columns).map_err(|message| self.fault(message))?;
        let body = (written.body.value(), path.child(written.head.len() as u32));
        let (parts, prefix): (Vec<(&Body, NodePath)>, &[LabelId]) = match (&self.key_body, keyed) {
            (Some(key_body), true) => (vec![key_body.clone(), body], &self.key_labels),
            _ => (vec![body], &[]),
        };
        let columns: Vec<LabelId> = prefix.iter().chain(&head).copied().collect();
        let clause = ir::compile_instance_body(evaluation.program, self.form, &parts, &columns)
            .map_err(|compile| self.fault(format!("input `{}` does not compile: {compile:?}", port.0)))?;
        Ok(Some((clause, !prefix.is_empty())))
    }
}

/// The label of each head site of `input` at the columns of `columns`
/// other than `key`, each site one label.
fn head_labels(input: &InstanceInput, columns: &[Column]) -> Result<Vec<LabelId>, String> {
    let key = crate::resolver::columns::key();
    let mut labels = Vec::new();
    for column in columns.iter().filter(|column| column.name != key) {
        let site = input.head.iter().find(|site| site.column == column.name);
        let site = site.ok_or_else(|| format!("input `{}` writes no head site on column {:?}", input.name.0, column.name))?;
        let mut at_site = Vec::new();
        each_site_label(site, &mut Vec::new(), &mut |use_, _| at_site.extend(use_label(use_)));
        match at_site[..] {
            [label] => labels.push(label),
            _ => return Err(format!("head site {:?} of input `{}` of `Unfold` holds other than one label", column.name, input.name.0)),
        }
    }
    Ok(labels)
}

/// Each output of the instance, as its bodies read it, with the example of
/// the driver's entry of that read.
fn own_outputs(evaluation: &Evaluation<'_>, output: &GraphRelation, example: Option<Example>) -> Vec<(UnfoldOutput, (GraphRelation, Option<Example>))> {
    UnfoldOutput::ALL
        .into_iter()
        .map(|which| {
            let relation = GraphRelation { node: output.node, output: Some(Arc::from([OutputStep::Port(which.port())])) };
            let on = match examples::scope_of(evaluation.program, &relation) {
                ExampleScope::PerExample => example,
                ExampleScope::TaskWide => None,
            };
            (which, (relation, on))
        })
        .collect()
}

/// A compiled input with the rows it gives where it reads no output, each
/// with the key's labels first where it holds them.
struct InputRows {
    keyed: bool,
    rows: Vec<Row>,
}

impl InputRows {
    /// The rows at `key`, with the key's labels left out.
    fn at<'r>(&'r self, key: &'r [TermId]) -> impl Iterator<Item = &'r [TermId]> + 'r {
        let width = if self.keyed { key.len() } else { 0 };
        self.rows.iter().filter(move |row| row[..width] == key[..width]).map(move |row| &row[width..])
    }
}

/// The rows of one key of the inputs that read no output.
struct Group {
    key: Row,
    start: Vec<TermId>,
    taken: Box<[TermId]>,
    untaken: Box<[TermId]>,
    conflict: StableHashSet<(TermId, TermId)>,
    /// The score of each cursor and item, where the form writes `score`.
    score: Option<StableHashMap<(TermId, TermId), i32>>,
}

/// One evaluation of an `Unfold` instance.
struct Run<'r, 'a> {
    evaluation: &'r Evaluation<'a>,
    bodies: &'r FormBodies<'r>,
    shape: &'r UnfoldForm<'r>,
    example: Option<Example>,
    own: Vec<(UnfoldOutput, (GraphRelation, Option<Example>))>,
}

/// The bodies that read the outputs, each where the form writes it.
struct Recursive {
    step: Option<(ClauseIr, bool)>,
    skip: Option<(ClauseIr, bool)>,
    take: Option<(ClauseIr, bool)>,
}

impl<'r, 'a> Run<'r, 'a> {
    fn graphs(&self, budget: &mut Budget<'a>) -> Outcome<Result<Vec<(Row, StateGraph)>, RelationValue>> {
        let groups = match self.groups()? {
            Ok(groups) => groups,
            Err(value) => return Ok(Err(value)),
        };
        let compile = |input| self.shape.compile(self.evaluation, input);
        let recursive = Recursive { step: compile(UnfoldInput::Step)?, skip: compile(UnfoldInput::Skip)?, take: compile(UnfoldInput::Take)? };
        let mut graphs = Vec::with_capacity(groups.len());
        for group in &groups {
            match self.graph(group, &recursive, budget)? {
                Ok(graph) => graphs.push((group.key.clone(), graph)),
                Err(value) => return Ok(Err(value)),
            }
        }
        Ok(Ok(graphs))
    }

    /// The rows of `clause` through the driver, or the value where it holds
    /// no rows.
    fn rows(&self, clause: &ClauseIr) -> Outcome<Result<Vec<Row>, RelationValue>> {
        let relation = match self.bodies.relation(self.shape.form, clause, self.example)? {
            RelationValue::Rows(relation) => relation,
            other => return Ok(Err(other)),
        };
        let mut rows = Vec::new();
        join::each_row(&relation, &mut |row| rows.push(row.into()));
        Ok(Ok(rows))
    }

    /// The rows of the written input `input`, or none where the form does
    /// not write it.
    fn input_rows(&self, input: UnfoldInput) -> Outcome<Result<InputRows, RelationValue>> {
        let Some((clause, keyed)) = self.shape.compile(self.evaluation, input)? else { return Ok(Ok(InputRows { keyed: false, rows: Vec::new() })) };
        Ok(self.rows(&clause)?.map(|rows| InputRows { keyed, rows }))
    }

    /// The key groups, each with its rows of the inputs that read no output.
    fn groups(&self) -> Outcome<Result<Vec<Group>, RelationValue>> {
        let keys: Vec<Row> = match &self.shape.key_body {
            Some(key_body) => {
                let clause = ir::compile_instance_body(self.evaluation.program, self.shape.form, &[key_body.clone()], &self.shape.key_labels)
                    .map_err(|compile| self.shape.fault(format!("the key body does not compile: {compile:?}")))?;
                match self.rows(&clause)? {
                    Ok(rows) => rows,
                    Err(value) => return Ok(Err(value)),
                }
            }
            None => vec![Row::default()],
        };
        let read = |input| self.input_rows(input);
        let (start, taken, untaken, conflict) =
            match (read(UnfoldInput::Start)?, read(UnfoldInput::InitialTaken)?, read(UnfoldInput::InitialUntaken)?, read(UnfoldInput::Conflict)?) {
                (Ok(start), Ok(taken), Ok(untaken), Ok(conflict)) => (start, taken, untaken, conflict),
                (Err(value), ..) | (_, Err(value), ..) | (_, _, Err(value), _) | (.., Err(value)) => return Ok(Err(value)),
            };
        let score_written = self.shape.written.iter().any(|(_, _, written)| written.name == UnfoldInput::Score.port());
        let score = match read(UnfoldInput::Score)? {
            Ok(score) => score,
            Err(value) => return Ok(Err(value)),
        };
        let items = |rows: &InputRows, key: &[TermId]| -> Box<[TermId]> { sorted(rows.at(key).map(|row| row[0])) };
        let groups = keys
            .into_iter()
            .map(|key| Group {
                start: items(&start, &key).into_vec(),
                taken: items(&taken, &key),
                untaken: items(&untaken, &key),
                conflict: conflict.at(&key).map(|row| (row[0], row[1])).collect(),
                score: score_written.then(|| {
                    score.at(&key).map(|row| ((row[0], row[1]), number(row[2]))).collect()
                }),
                key,
            })
            .collect();
        Ok(Ok(groups))
    }

    /// The states of `group` and their branches, round by round from the
    /// states of its starts.
    fn graph(&self, group: &Group, recursive: &Recursive, budget: &mut Budget<'a>) -> Outcome<Result<StateGraph, RelationValue>> {
        let mut graph = StateGraph::default();
        let mut index: StableHashMap<UnfoldState, StateIndex> = StableHashMap::default();
        let mut queue = Vec::new();
        let mut reach = |state: UnfoldState, graph: &mut StateGraph, queue: &mut Vec<StateIndex>, budget: &mut Budget<'a>| -> Result<StateIndex, ReachedBound> {
            if let Some(&at) = index.get(&state) {
                return Ok(at);
            }
            budget.charge_rows(1)?;
            let at = StateIndex(graph.states.len() as u32);
            index.insert(state.clone(), at);
            graph.states.push(state);
            graph.branches.push(Box::default());
            queue.push(at);
            Ok(at)
        };
        let stopped = |bound| RelationValue::Stopped(Stop { bound, form: self.shape.form.clone() });
        for &cursor in &group.start {
            let state = UnfoldState { cursor, taken: group.taken.clone(), untaken: group.untaken.clone(), excluded: Box::default() };
            let at = reach(state, &mut graph, &mut queue, budget).map_err(stopped);
            match at {
                Ok(at) => graph.starts.push(at),
                Err(value) => return Ok(Err(value)),
            }
        }
        while let Some(at) = queue.pop() {
            if let Err(bound) = budget.charge_work(1) {
                return Ok(Err(stopped(bound)));
            }
            let state = graph.states[at.0 as usize].clone();
            let rounds = match self.round(group, recursive, &state)? {
                Ok(rounds) => rounds,
                Err(value) => return Ok(Err(value)),
            };
            let mut branches = Vec::with_capacity(rounds.len());
            for (take, successors) in rounds {
                let mut next = Vec::with_capacity(successors.len());
                for successor in successors {
                    match reach(successor, &mut graph, &mut queue, budget) {
                        Ok(state) => next.push(state),
                        Err(bound) => return Ok(Err(stopped(bound))),
                    }
                }
                branches.push(Branch { take, next: next.into() });
            }
            graph.branches[at.0 as usize] = branches.into();
        }
        Ok(Ok(graph))
    }

    /// One round from `state`: for each of its takes, one per item of least
    /// score where several tie, the states its `step` and `skip` rows reach.
    fn round(&self, group: &Group, recursive: &Recursive, state: &UnfoldState) -> Outcome<Result<Vec<(Box<[TermId]>, Vec<UnfoldState>)>, RelationValue>> {
        let written_take = match &recursive.take {
            Some(take) => match self.at_cursor(group, state, &[], take)? {
                Ok(items) => items,
                Err(value) => return Ok(Err(value)),
            },
            None => Vec::new(),
        };
        let least = group.score.as_ref().map_or_else(Vec::new, |score| least_scored(score, state));
        let takes: Vec<Box<[TermId]>> = match least.len() {
            0 | 1 => vec![sorted(written_take.iter().chain(&least).copied())],
            _ => least.iter().map(|&item| sorted(written_take.iter().copied().chain([item]))).collect(),
        };
        let mut rounds = Vec::with_capacity(takes.len());
        for take in takes {
            let mut successors = Vec::new();
            for (body, stepped) in [(&recursive.step, true), (&recursive.skip, false)] {
                let Some(body) = body else { continue };
                let cursors = match self.at_cursor(group, state, &take, body)? {
                    Ok(cursors) => cursors,
                    Err(value) => return Ok(Err(value)),
                };
                for cursor in cursors {
                    successors.push(if stepped { step(state, &take, &group.conflict, cursor) } else { UnfoldState { cursor, ..state.clone() } });
                }
            }
            rounds.push((take, successors));
        }
        Ok(Ok(rounds))
    }

    /// The second column of the rows that `body` gives at the key of
    /// `group` and the cursor of `state`, with the outputs read at `state`
    /// and `take`.
    fn at_cursor(&self, group: &Group, state: &UnfoldState, take: &[TermId], body: &(ClauseIr, bool)) -> Outcome<Result<Vec<TermId>, RelationValue>> {
        let (clause, keyed) = body;
        let rows = self.with_state(group, state, take, || self.rows(clause))?;
        let rows = match rows {
            Ok(rows) => InputRows { keyed: *keyed, rows },
            Err(value) => return Ok(Err(value)),
        };
        Ok(Ok(rows.at(&group.key).filter(|row| row[0] == state.cursor).map(|row| row[1]).collect()))
    }

    /// The value of `evaluate`, with each read of the instance's outputs
    /// reading the rows of `state` and `take` at the key of `group`.
    fn with_state<T>(&self, group: &Group, state: &UnfoldState, take: &[TermId], evaluate: impl FnOnce() -> T) -> T {
        let key = output_key(&group.key);
        let branch = Branch { take: take.into(), next: Box::default() };
        let values = &self.bodies.driver.values;
        for (which, entry) in &self.own {
            let mut rows = RowSet::empty((key.len() + 2) as u16);
            which.add_rows(&key, state, &branch, &mut rows);
            values.borrow_mut().insert(entry.clone(), RelationValue::Rows(Arc::new(join::one_part(rows))));
        }
        let value = evaluate();
        for (_, entry) in &self.own {
            values.borrow_mut().remove(entry);
        }
        value
    }
}

/// The untaken items of `state` of least score at its cursor.
fn least_scored(score: &StableHashMap<(TermId, TermId), i32>, state: &UnfoldState) -> Vec<TermId> {
    let scored: Vec<(TermId, i32)> =
        state.untaken.iter().filter_map(|&item| score.get(&(state.cursor, item)).map(|&value| (item, value))).collect();
    let Some(least) = scored.iter().map(|(_, value)| *value).min() else { return Vec::new() };
    scored.into_iter().filter(|(_, value)| *value == least).map(|(item, _)| item).collect()
}

/// The state a `step` from `state` to `cursor` reaches with `take`.
fn step(state: &UnfoldState, take: &[TermId], conflict: &StableHashSet<(TermId, TermId)>, cursor: TermId) -> UnfoldState {
    let differs = |item: TermId, in_conflict: bool| take.iter().any(|&taken| taken != item && conflict.contains(&(taken, item)) == in_conflict);
    UnfoldState {
        cursor,
        taken: sorted(state.taken.iter().chain(take).copied()),
        untaken: sorted(state.untaken.iter().copied().filter(|&item| differs(item, false))),
        excluded: sorted(state.excluded.iter().copied().chain(state.untaken.iter().copied().filter(|&item| differs(item, true)))),
    }
}

/// `items` sorted, each once.
fn sorted(items: impl IntoIterator<Item = TermId>) -> Box<[TermId]> {
    let mut items: Vec<TermId> = items.into_iter().collect();
    items.sort_by_key(|id| id.encoding());
    items.dedup();
    items.into()
}

/// The number of a score's term id.
fn number(id: TermId) -> i32 {
    match Term::decode(id, &ValueType::Number) {
        Term::Number(number) => number.0,
        other => panic!("a score of type number, not {other:?}"),
    }
}
