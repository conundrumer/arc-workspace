//! `Unfold`: its states, its rounds, the forks of a tied `score`, and the
//! distinct outputs of its walks, with the rows of the inputs that read
//! the outputs from the bodies of the instance or given.
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
//! A body reads the outputs at the current state of the current key. Where
//! such a read names the `key` column, the reads of the instance also hold
//! the rows of the other keys at each state their walks reach, and the keys'
//! graphs are built again until those rows stop growing.
//!
//! A step from a state moves the items of its take as `Take` of
//! `programs/lib/orders.dl` does at one cursor: the take joins `taken`, an
//! untaken item that differs from an item of the take stays `untaken`, or
//! leaves it as `excluded` where that item is in conflict with it.

use std::cell::RefCell;
use std::sync::Arc;

use super::examples::{self, ExampleScope};
use super::init_form::{instance_at, key_groups, rows_of, InputClause, InstanceShape};
use super::ir::ClauseIr;
use super::join::{self, Budget};
use super::{Evaluation, FormBodies, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::hash::{StableHashMap, StableHashSet};
use crate::product::Product;
use crate::program::path::NodePath;
use crate::program::{OutputStep, PortName};
use crate::registry::{Component, InputPort};
use crate::relations::{Row, RowSet};
use crate::terms::{Example, Term, TermId};
use crate::types::GraphRelation;

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
    /// The cells of the states' cursors and items of several fields.
    pub records: Arc<RecordHandles>,
}

/// The cells of the cursors and items of several fields of one `Unfold`
/// run. A state stores such a value as one private handle, which equal
/// cells share. Only this table reads a handle, and no row holds one.
#[derive(Clone, Debug, Default)]
pub struct RecordHandles {
    cells: Vec<Row>,
    handles: StableHashMap<Row, TermId>,
}

impl RecordHandles {
    /// The handle of `cells`.
    pub(super) fn handle(&mut self, cells: &[TermId]) -> TermId {
        if let Some(&handle) = self.handles.get(cells) {
            return handle;
        }
        let handle = TermId::from_encoding(self.cells.len() as u32);
        self.cells.push(cells.into());
        self.handles.insert(cells.into(), handle);
        handle
    }

    /// The cells of `handle`.
    pub(super) fn cells(&self, handle: TermId) -> &[TermId] {
        &self.cells[handle.encoding() as usize]
    }
}

/// The row positions of the cursor and of the item. A zero-field value has
/// no row positions and its singleton TermId stays in states. A value of
/// several fields is a handle of [`RecordHandles`] in states.
#[derive(Clone,Copy,Debug)]
pub(super) struct OutputLayout {pub cursor:usize,pub item:usize}
impl OutputLayout {
    const SCALARS:Self=Self {cursor:1,item:1};
    pub fn width(self)->usize {self.cursor+self.item}
    pub fn at(evaluation:&Evaluation<'_>,form:&NodePath)->Outcome<Self> {
        let (instance,component)=instance_at(evaluation,form)?;
        let shape=InstanceShape::of(evaluation.program,form,instance,component);
        Self::of(&shape,component).map_err(|message|RunFault {message:message.into(),form:form.clone()})
    }
    fn of(shape:&InstanceShape<'_>,component:&Component)->Result<Self,String> {
        let widths=shape.atom_widths(&component.outputs[0].columns)?;
        Ok(Self {cursor:widths[0],item:widths[1]})
    }
}

/// The row cells of `atom`, the cursor or an item of a state, of `width`
/// row positions.
fn atom_cells<'c>(width: usize, atom: &'c TermId, records: &'c RecordHandles) -> &'c [TermId] {
    match width {
        0 => &[],
        1 => std::slice::from_ref(atom),
        _ => records.cells(*atom),
    }
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
    pub const ALL: [UnfoldOutput; 4] = [UnfoldOutput::Taken, UnfoldOutput::Untaken, UnfoldOutput::Excluded, UnfoldOutput::Take];

    pub fn port(self) -> PortName {
        let name = match self {
            UnfoldOutput::Taken => "taken",
            UnfoldOutput::Untaken => "untaken",
            UnfoldOutput::Excluded => "excluded",
            UnfoldOutput::Take => "take",
        };
        PortName(name.into())
    }

    /// The output at `port`, a port of an output of `Unfold`.
    pub fn of(port: &PortName) -> UnfoldOutput {
        UnfoldOutput::ALL.into_iter().find(|candidate| candidate.port() == *port).expect("an output `Unfold` declares")
    }

    /// Adds to `rows` the rows of this output at `state` on `branch`, the
    /// branch a walk takes there, each `key`, the cursor, then the item.
    pub(super) fn add_rows(self, layout:OutputLayout, records:&RecordHandles, key: &[TermId], state: &UnfoldState, branch: &Branch, rows: &mut RowSet) {
        let items: &[TermId] = match self {
            UnfoldOutput::Taken => &state.taken,
            UnfoldOutput::Untaken => &state.untaken,
            UnfoldOutput::Excluded => &state.excluded,
            UnfoldOutput::Take => &branch.take,
        };
        let cursor = atom_cells(layout.cursor, &state.cursor, records);
        for item in items {
            rows.insert(key.iter().chain(cursor).chain(atom_cells(layout.item, item, records)).copied().collect());
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

/// An input of `Unfold` that reads its outputs.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum RecursiveInput {
    Step,
    Skip,
    Take,
}

impl RecursiveInput {
    fn input(self) -> UnfoldInput {
        match self {
            RecursiveInput::Step => UnfoldInput::Step,
            RecursiveInput::Skip => UnfoldInput::Skip,
            RecursiveInput::Take => UnfoldInput::Take,
        }
    }
}

/// The rows of the inputs that read the outputs, at a state of a walk.
trait ReadsOutputs {
    /// What ends the evaluation of a round: a bound reached, or what the
    /// source of the rows gives in their place.
    type Halt: From<ReachedBound>;

    /// The second column of the rows of `input` at the key of `group` and
    /// the cursor of `state`, with the outputs read at `state` and `take`,
    /// or `None` where `input` has no rows to give.
    fn at_cursor(&self, group: &Group, input: RecursiveInput, state: &UnfoldState, take: &[TermId]) -> Result<Option<Vec<TermId>>, Self::Halt>;
}

/// The state graph of the `Unfold` instance whose `INIT` form stands at
/// `form`, on each of its keys, with the key columns of the instance's
/// output rows at that key; `output` is an output of the instance. The
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
    let (instance, component) = instance_at(evaluation, form)?;
    let shape = InstanceShape::of(evaluation.program, form, instance, component);
    let run = Run { instance: &instance.name, evaluation, bodies, form, shape: &shape, component, example, own: own_outputs(evaluation, output, example), records: RefCell::default(), reached: RefCell::default() };
    run.graphs(budget)
}

/// The walks of a state graph, one at a time, in the order of a depth-first
/// search that takes the branches of a state in their order. A walk is the
/// branch it takes at each state, `None` at a state it does not reach.
struct Walks<'g> {
    graph: &'g StateGraph,
    /// The walks begun and not yet complete, the next to extend last.
    partial: Vec<PartialWalk>,
}

/// A walk begun: the branch it takes at each state it has left, the states
/// it reached, and those it reached and has not yet left.
#[derive(Clone)]
struct PartialWalk {
    chosen: Vec<Option<u32>>,
    reached: Vec<bool>,
    pending: Vec<StateIndex>,
}

impl PartialWalk {
    /// Leaves `state` by its branch `index`.
    fn take(&mut self, graph: &StateGraph, state: StateIndex, index: usize) {
        self.chosen[state.0 as usize] = Some(index as u32);
        for &next in graph.branches[state.0 as usize][index].next.iter() {
            if !std::mem::replace(&mut self.reached[next.0 as usize], true) {
                self.pending.push(next);
            }
        }
    }
}

impl<'g> Walks<'g> {
    fn new(graph: &'g StateGraph) -> Self {
        let (reached, pending) = initial_reach(graph);
        Walks { graph, partial: vec![PartialWalk { chosen: vec![None; graph.states.len()], reached, pending }] }
    }

    /// The next complete walk, or `None` past the last. A walk that reaches
    /// a state with no branch is no walk.
    fn next(&mut self, budget: &mut Budget<'_>) -> Result<Option<Vec<Option<u32>>>, ReachedBound> {
        'walks: while let Some(mut walk) = self.partial.pop() {
            while let Some(state) = walk.pending.pop() {
                budget.charge_work(1)?;
                let count = self.graph.branches[state.0 as usize].len();
                if count == 0 {
                    continue 'walks;
                }
                for index in (1..count).rev() {
                    let mut fork = walk.clone();
                    fork.take(self.graph, state, index);
                    self.partial.push(fork);
                }
                walk.take(self.graph, state, 0);
            }
            // The content of a walk: the states it takes a branch at. The steps that find it, dead ends included, are effort, since which dead ends a search meets follows the order of the branches.
            budget.charge_content(walk.chosen.iter().flatten().count() as u64)?;
            return Ok(Some(walk.chosen));
        }
        Ok(None)
    }
}

/// The state-local read context of one reached round in one model.
#[derive(Clone,Debug)]
pub struct WalkContext {pub key:Row,pub state:UnfoldState,pub take:Box<[TermId]>,pub records:Arc<RecordHandles>}

/// The distinct values of some outputs over the walks of one key's state
/// graph, found as they are asked for, each the rows of each output at the
/// states along one walk, with the key before the cursor and the item.
struct DistinctWalks<'g> {
    walks: Walks<'g>,
    outputs: &'g [UnfoldOutput],
    key: Row,
    seen: StableHashSet<Vec<Vec<Row>>>,
    found: Vec<Vec<RowSet>>,
    contexts:Vec<Vec<WalkContext>>,
    layout:OutputLayout,
}

impl<'g> DistinctWalks<'g> {
    fn new(graph: &'g StateGraph, outputs: &'g [UnfoldOutput], key: Row, layout:OutputLayout) -> Self {
        DistinctWalks { walks: Walks::new(graph), outputs, key, seen: StableHashSet::default(), found: Vec::new(),contexts:Vec::new(),layout }
    }

    /// The distinct value at `index`, walking on until it is found, or
    /// `None` where the walks give fewer distinct values.
    fn get(&mut self, index: usize, budget: &mut Budget<'_>) -> Result<Option<&[RowSet]>, ReachedBound> {
        let graph = self.walks.graph;
        let arity = (self.key.len() + self.layout.width()) as u16;
        while self.found.len() <= index {
            let Some(chosen) = self.walks.next(budget)? else { break };
            let mut parts = vec![RowSet::empty(arity); self.outputs.len()];
            for ((state, branches), branch) in graph.states.iter().zip(&graph.branches).zip(&chosen) {
                let Some(branch) = branch else { continue };
                for (output, rows) in self.outputs.iter().zip(&mut parts) {
                    output.add_rows(self.layout, &graph.records, &self.key, state, &branches[*branch as usize], rows);
                }
            }
            let content = parts
                .iter()
                .map(|rows| {
                    let mut sorted: Vec<Row> = rows.rows().map(Row::from).collect();
                    sorted.sort_by(|a, b| a.iter().map(|id| id.encoding()).cmp(b.iter().map(|id| id.encoding())));
                    sorted
                })
                .collect();
            if self.seen.insert(content) {
                let contexts=graph.states.iter().zip(&graph.branches).zip(&chosen).filter_map(|((state,branches),branch)|branch.map(|b|WalkContext {key:self.key.clone(),state:state.clone(),take:branches[b as usize].take.clone(),records:graph.records.clone()})).collect();
                self.found.push(parts);self.contexts.push(contexts);
            }
        }
        Ok(self.found.get(index).map(|parts| &parts[..]))
    }
}

/// The joint walks of an `Unfold` instance, one at a time: each one
/// distinct value of the walks on each key, the first key the most
/// significant, as the rows of each of some outputs at those walks, the
/// union of the rows of each key.
pub struct JointWalks<'g> {
    keys: Product<DistinctWalks<'g>>,
    outputs: usize,
    arity: u16,
}

impl<'g> JointWalks<'g> {
    /// The joint walks over `graphs`, the state graph of each key with the
    /// key columns of the instance's output rows at that key, as [`unfold`]
    /// gives them, of each output of [`UnfoldOutput::ALL`], in that order,
    /// of `arity` columns.
    pub fn of_instance(graphs: &'g [(Row, StateGraph)], arity: u16) -> Self {
        Self::of_layout(graphs,arity,OutputLayout::SCALARS)
    }

    pub(super) fn of_layout(graphs:&'g [(Row,StateGraph)],arity:u16,layout:OutputLayout)->Self {
        Self::new(graphs.iter().map(|(key,graph)|(graph,key.clone())),&UnfoldOutput::ALL,arity,layout)
    }

    /// The joint walks over `keys`, the state graph of each key with the
    /// columns that stand before the cursor in an output's rows, of each of
    /// `outputs`, of `arity` columns.
    fn new(keys: impl IntoIterator<Item = (&'g StateGraph, Row)>, outputs: &'g [UnfoldOutput], arity: u16, layout:OutputLayout) -> Self {
        let keys = keys.into_iter().map(|(graph, key)| DistinctWalks::new(graph, outputs, key,layout)).collect();
        JointWalks { keys: Product::new(keys), outputs: outputs.len(), arity }
    }

    /// The next joint walk, or `None` past the last.
    pub fn next(&mut self, budget: &mut Budget<'_>) -> Result<Option<Vec<RowSet>>, ReachedBound> {
        self.next_with_contexts(budget).map(|found|found.map(|(rows,_)|rows))
    }

    /// The output rows and their state-local witnesses in this joint walk.
    pub fn next_with_contexts(&mut self,budget:&mut Budget<'_>)->Result<Option<(Vec<RowSet>,Vec<WalkContext>)>,ReachedBound> {
        let Some(walk) = self.keys.next(|key, index| Ok(key.get(index, budget)?.is_some()))? else {
            return Ok(None);
        };
        let mut rows = vec![RowSet::empty(self.arity); self.outputs];
        let mut contexts=Vec::new();
        for (key, position) in walk {
            contexts.extend(key.contexts[position].iter().cloned());
            for (joint, part) in rows.iter_mut().zip(&key.found[position]) {
                for row in part.rows() {
                    joint.insert_slice(row);
                }
            }
        }
        Ok(Some((rows,contexts)))
    }
}

/// The values of the outputs of an `Unfold` instance of `component` over
/// given rows: on each key of `keys`, the rows of each input of
/// `component`, in the order of its inputs, each row without its key, the
/// rows of the inputs that read the outputs fixed. One value per
/// combination of one walk on each key, at most `limit`, each the rows of
/// each output of `component`, in the order of its outputs, with the key
/// before the cursor and the item.
pub fn unfold_given(component: &Component, keys: &[(Row, Vec<RowSet>)], limit: usize, budget: &mut Budget<'_>) -> Result<Vec<Vec<RowSet>>, ReachedBound> {
    let outputs: Vec<UnfoldOutput> = component.outputs.iter().map(|output| UnfoldOutput::of(&output.name)).collect();
    let arity = keys.first().map_or(0, |(key, _)| key.len()) as u16 + 2;
    let mut graphs = Vec::with_capacity(keys.len());
    for (key, rows) in keys {
        let given = |input: UnfoldInput| -> Vec<&[TermId]> {
            let at = component.inputs.iter().position(|declared| declared.port.name == input.port());
            at.map_or_else(Vec::new, |at| rows[at].rows().collect())
        };
        let group = Group::of(key.clone(), given, true);
        let pairs = |input: RecursiveInput| given(input.input()).into_iter().map(|row| (row[0], row[1])).collect();
        let reads = GivenReads { rows: [RecursiveInput::Step, RecursiveInput::Skip, RecursiveInput::Take].map(pairs) };
        graphs.push((graph(&group, &reads, budget)?, key.clone()));
    }
    let mut walks = JointWalks::new(graphs.iter().map(|(graph, key)| (graph, key.clone())), &outputs, arity,OutputLayout::SCALARS);
    let mut values = Vec::new();
    while values.len() < limit {
        let Some(value) = walks.next(budget)? else { break };
        values.push(value);
    }
    Ok(values)
}

/// The given rows of `step`, `skip` and `take` on one key, each row its
/// cursor and its second column, in the order of [`RecursiveInput`].
struct GivenReads {
    rows: [Vec<(TermId, TermId)>; 3],
}

impl ReadsOutputs for GivenReads {
    type Halt = ReachedBound;

    fn at_cursor(&self, _: &Group, input: RecursiveInput, state: &UnfoldState, _: &[TermId]) -> Result<Option<Vec<TermId>>, ReachedBound> {
        let rows = &self.rows[input as usize];
        Ok(Some(rows.iter().filter(|(cursor, _)| *cursor == state.cursor).map(|&(_, second)| second).collect()))
    }
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

impl Group {
    /// The group of `key`, from the rows `rows` gives of each input that
    /// reads no output, at the key, each without the key's labels, with no
    /// `score` where `score_written` is false.
    fn of<'r>(key: Row, rows: impl Fn(UnfoldInput) -> Vec<&'r [TermId]>, score_written: bool) -> Group {
        let items = |input| sorted(rows(input).into_iter().map(|row| row[0]));
        Group {
            start: items(UnfoldInput::Start).into_vec(),
            taken: items(UnfoldInput::InitialTaken),
            untaken: items(UnfoldInput::InitialUntaken),
            conflict: rows(UnfoldInput::Conflict).into_iter().map(|row| (row[0], row[1])).collect(),
            score: score_written.then(|| rows(UnfoldInput::Score).into_iter().map(|row| ((row[0], row[1]), Term::decode_number(row[2]))).collect()),
            key,
        }
    }
}

/// The inputs of `Unfold` that read no output.
const GIVEN: [UnfoldInput; 5] = [UnfoldInput::Start, UnfoldInput::InitialTaken, UnfoldInput::InitialUntaken, UnfoldInput::Conflict, UnfoldInput::Score];

/// One evaluation of an `Unfold` instance.
struct Run<'r, 'a> {
    instance: &'r crate::program::InstanceName,
    evaluation: &'r Evaluation<'a>,
    bodies: &'r FormBodies<'r>,
    form: &'r NodePath,
    shape: &'r InstanceShape<'r>,
    component: &'r Component,
    example: Option<Example>,
    own: Vec<(UnfoldOutput, (GraphRelation, Option<Example>))>,
    /// The handles that the run's states hold.
    records: RefCell<RecordHandles>,
    /// The rows of each output of `own` at each state each key has reached,
    /// where a body reads the outputs at a key it names; empty otherwise.
    reached: RefCell<Vec<RowSet>>,
}

/// The bodies that read the outputs, each where the form writes it.
struct Recursive {
    step: Option<InputClause>,
    skip: Option<InputClause>,
    take: Option<InputClause>,
}

impl<'r, 'a> Run<'r, 'a> {
    fn graphs(&self, budget: &mut Budget<'a>) -> Outcome<Result<Vec<(Row, StateGraph)>, RelationValue>> {
        let groups = match self.groups(budget)? {
            Ok(groups) => groups,
            Err(value) => return Ok(Err(value)),
        };
        let compile = |input| self.compile(input);
        let recursive = Recursive { step: compile(UnfoldInput::Step)?, skip: compile(UnfoldInput::Skip)?, take: compile(UnfoldInput::Take)? };
        let reads = DriverReads { run: self, recursive: &recursive };
        let at_keys = self.shape.reads_outputs_at_keys(self.instance, self.component);
        let mut graphs: Vec<(Row, StateGraph)>;
        loop {
            graphs = Vec::with_capacity(groups.len());
            for group in &groups {
                match graph(group, &reads, budget) {
                    Ok(graph) => graphs.push((group.key.to_vec().into(), graph)),
                    Err(Halt::Fault(fault)) => return Err(fault),
                    Err(Halt::Value(value)) => return Ok(Err(value)),
                    Err(Halt::Bound(bound)) => return Ok(Err(RelationValue::Stopped(Stop { bound, form: self.form.clone() }))),
                }
            }
            if !at_keys || !self.reached_more(&graphs) {
                break;
            }
        }
        let records = Arc::new(self.records.take());
        graphs.iter_mut().for_each(|(_, graph): &mut (Row, StateGraph)| graph.records = records.clone());
        Ok(Ok(graphs))
    }

    /// Whether the states of `graphs` give a row that [`Run::reached`] lacks,
    /// each such row added to it.
    fn reached_more(&self, graphs: &[(Row, StateGraph)]) -> bool {
        let widths = self.shape.widths(&self.component.outputs[0].columns).expect("checked output widths");
        let layout = OutputLayout::of(self.shape, self.component).expect("checked output widths");
        let arity = self.shape.arity(&widths) as u16;
        let records = self.records.borrow();
        let mut held = self.reached.borrow_mut();
        held.resize_with(self.own.len(), || RowSet::empty(arity));
        let mut grew = false;
        for ((which, _), held) in self.own.iter().zip(held.iter_mut()) {
            for (key, graph) in graphs {
                let before = held.len();
                for (state, branches) in graph.states.iter().zip(&graph.branches) {
                    which.add_rows(layout, &records, key, state, &Branch { take: Box::default(), next: Box::default() }, held);
                    for branch in branches.iter() {
                        which.add_rows(layout, &records, key, state, branch, held);
                    }
                }
                grew |= held.len() != before;
            }
        }
        grew
    }

    /// A fault at the instance's form, with `message`.
    fn fault(&self, message: String) -> RunFault {
        RunFault { message: message.into(), form: self.form.clone() }
    }

    /// The input `input` as the component declares it.
    fn declared(&self, input: UnfoldInput) -> Outcome<&'r InputPort> {
        let port = input.port();
        let declared = self.component.inputs.iter().find(|declared| declared.port.name == port);
        declared.ok_or_else(|| self.fault(format!("the component declares no input `{}`", port.0)))
    }

    /// The clause of `input` where the form writes it.
    fn compile(&self, input: UnfoldInput) -> Outcome<Option<InputClause>> {
        let declared = self.declared(input)?;
        self.shape.input_clause(self.evaluation.program, self.form, declared).map_err(|message| self.fault(message))
    }

    /// The rows of `clause`, of `arity` columns, through the driver, or the
    /// value where it holds no rows.
    fn rows(&self, clause: &ClauseIr, arity: usize) -> Outcome<Result<Vec<Row>, RelationValue>> {
        rows_of(self.evaluation, self.form, self.bodies.relation(self.form, clause, self.example)?, arity).map_err(|message| self.fault(message))
    }

    /// The rows of `input`, an input that reads no output, at each of
    /// `keys`, each without the key's labels.
    fn input_rows(&self, input: UnfoldInput, keys: &[Row]) -> Outcome<Result<Vec<RowSet>, RelationValue>> {
        let declared=self.declared(input)?;
        let rows=match self.compile(input)? {
            Some(clause)=>match self.rows(&clause.clause,clause.arity())? {
                Ok(rows)=>clause.grouped(keys,rows),Err(value)=>return Ok(Err(value)),
            },
            None=>{
                let types=self.shape.port_types(&declared.port.columns).map_err(|message|self.fault(message))?;
                self.shape.unwritten(declared,&types,keys,self.evaluation).map_err(|message|self.fault(message))?
            }
        };
        let rows=rows.iter().map(|rows|self.shape.atom_rows(&declared.port.columns,rows,&mut self.records.borrow_mut()).map_err(|message|self.fault(message))).collect::<Outcome<Vec<_>>>()?;
        Ok(Ok(rows))
    }

    /// The key groups, each with its rows of the inputs that read no output.
    ///
    /// The rows read are content: the key rows and the rows of each input
    /// that reads no output, which `budget` counts.
    fn groups(&self, budget: &mut Budget<'a>) -> Outcome<Result<Vec<Group>, RelationValue>> {
        let keys = match key_groups(self.evaluation, self.bodies, self.form, self.shape, self.example)? {
            Ok(keys) => keys,
            Err(value) => return Ok(Err(value)),
        };
        let mut read = Vec::with_capacity(GIVEN.len());
        for input in GIVEN {
            match self.input_rows(input, &keys)? {
                Ok(rows) => read.push(rows),
                Err(value) => return Ok(Err(value)),
            }
        }
        let rows_read = read.iter().flatten().map(|rows| rows.len() as u64).fold(keys.len() as u64, u64::saturating_add);
        if let Err(bound) = budget.charge_content(rows_read) {
            return Ok(Err(RelationValue::Stopped(Stop { bound, form: self.form.clone() })));
        }
        let score_written = self.shape.writes(&UnfoldInput::Score.port());
        let groups = keys
            .into_iter()
            .enumerate()
            .map(|(at, key)| {
                let rows = |input| -> Vec<&[TermId]> {
                    let index = GIVEN.iter().position(|given| *given == input).expect("an input that reads no output");
                    read[index][at].rows().collect()
                };
                Group::of(key, rows, score_written)
            })
            .collect();
        Ok(Ok(groups))
    }

    /// The second column of the rows that `body` gives at the key of
    /// `group` and the cursor of `state`, with the outputs read at `state`
    /// and `take`.
    fn at_cursor(&self, group: &Group, state: &UnfoldState, take: &[TermId], body: &InputClause, input:UnfoldInput) -> Outcome<Result<Vec<TermId>, RelationValue>> {
        let rows = match self.with_state(group, state, take, || self.rows(&body.clause, body.arity()))? {
            Ok(rows) => rows,
            Err(value) => return Ok(Err(value)),
        };
        let [at_key] = &body.grouped(std::slice::from_ref(&group.key), rows)[..] else { unreachable!("the rows of one key") };
        let declared=self.declared(input)?;
        let atoms=self.shape.atom_rows(&declared.port.columns,at_key,&mut self.records.borrow_mut()).map_err(|message|self.fault(message))?;
        Ok(Ok(atoms.rows().filter(|row| row[0] == state.cursor).map(|row| row[1]).collect()))
    }

    /// The value of `evaluate`, with each read of the instance's outputs
    /// reading the rows of `state` and `take` at the key of `group`, and the
    /// rows that [`Run::reached`] holds at each other key.
    fn with_state<T>(&self, group: &Group, state: &UnfoldState, take: &[TermId], evaluate: impl FnOnce() -> T) -> T {
        let key = &group.key;
        let branch = Branch { take: take.into(), next: Box::default() };
        let values = &self.bodies.driver.values;
        let reached = self.reached.borrow();
        for (at, (which, entry)) in self.own.iter().enumerate() {
            let widths=self.shape.widths(&self.component.outputs[0].columns).expect("checked output widths");
            let layout=OutputLayout::of(self.shape,self.component).expect("checked output widths");
            let mut rows = RowSet::empty(self.shape.arity(&widths) as u16);
            which.add_rows(layout,&self.records.borrow(),key, state, &branch, &mut rows);
            if let Some(reached) = reached.get(at) {
                add_other_keys(reached, key, &mut rows);
            }
            values.borrow_mut().insert(entry.clone(), RelationValue::Rows(Arc::new(join::one_part(rows))));
        }
        let value = evaluate();
        for (_, entry) in &self.own {
            values.borrow_mut().remove(entry);
        }
        value
    }
}

/// Adds to `rows` the rows of `reached` at each key but `key`.
pub(super) fn add_other_keys(reached: &RowSet, key: &[TermId], rows: &mut RowSet) {
    for row in reached.rows().filter(|row| row[..key.len()] != *key) {
        rows.insert(row.into());
    }
}

/// What ends a round of the driver's evaluation: a fault, a value that is
/// not rows, or a bound reached.
enum Halt {
    Fault(RunFault),
    Value(RelationValue),
    Bound(ReachedBound),
}

impl From<ReachedBound> for Halt {
    fn from(bound: ReachedBound) -> Self {
        Halt::Bound(bound)
    }
}

/// The rows of the inputs that read the outputs, through the driver, from
/// the bodies the form writes.
struct DriverReads<'x, 'r, 'a> {
    run: &'x Run<'r, 'a>,
    recursive: &'x Recursive,
}

impl ReadsOutputs for DriverReads<'_, '_, '_> {
    type Halt = Halt;

    fn at_cursor(&self, group: &Group, input: RecursiveInput, state: &UnfoldState, take: &[TermId]) -> Result<Option<Vec<TermId>>, Halt> {
        let body = match input {
            RecursiveInput::Step => &self.recursive.step,
            RecursiveInput::Skip => &self.recursive.skip,
            RecursiveInput::Take => &self.recursive.take,
        };
        let Some(body) = body else { return Ok(None) };
        match self.run.at_cursor(group, state, take, body,input.input()) {
            Ok(Ok(rows)) => Ok(Some(rows)),
            Ok(Err(value)) => Err(Halt::Value(value)),
            Err(fault) => Err(Halt::Fault(fault)),
        }
    }
}

/// The states of `group` and their branches, round by round from the
/// states of its starts, with the rows of the inputs that read the
/// outputs from `reads`.
fn graph<R: ReadsOutputs>(group: &Group, reads: &R, budget: &mut Budget<'_>) -> Result<StateGraph, R::Halt> {
    let mut graph = StateGraph::default();
    let mut index: StableHashMap<UnfoldState, StateIndex> = StableHashMap::default();
    let mut queue = Vec::new();
    let mut reach = |state: UnfoldState, graph: &mut StateGraph, queue: &mut Vec<StateIndex>, budget: &mut Budget<'_>| -> Result<StateIndex, ReachedBound> {
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
    for &cursor in &group.start {
        let state = UnfoldState { cursor, taken: group.taken.clone(), untaken: group.untaken.clone(), excluded: Box::default() };
        let at = reach(state, &mut graph, &mut queue, budget)?;
        graph.starts.push(at);
    }
    while let Some(at) = queue.pop() {
        // Each state of the graph is expanded once: the states are the content, the expansion is the search's effort.
        budget.charge_content(1)?;
        budget.charge_work(1)?;
        let state = graph.states[at.0 as usize].clone();
        let rounds = round(group, reads, &state)?;
        let mut branches = Vec::with_capacity(rounds.len());
        for (take, successors) in rounds {
            let mut next = Vec::with_capacity(successors.len());
            for successor in successors {
                next.push(reach(successor, &mut graph, &mut queue, budget)?);
            }
            branches.push(Branch { take, next: next.into() });
        }
        graph.branches[at.0 as usize] = branches.into();
    }
    Ok(graph)
}

/// One round from `state`: for each of its takes, one per item of least
/// score where several tie, the states its `step` and `skip` rows reach.
fn round<R: ReadsOutputs>(group: &Group, reads: &R, state: &UnfoldState) -> Result<Vec<(Box<[TermId]>, Vec<UnfoldState>)>, R::Halt> {
    let written_take = reads.at_cursor(group, RecursiveInput::Take, state, &[])?.unwrap_or_default();
    let least = group.score.as_ref().map_or_else(Vec::new, |score| least_scored(score, state));
    let takes: Vec<Box<[TermId]>> = match least.len() {
        0 | 1 => vec![sorted(written_take.iter().chain(&least).copied())],
        _ => least.iter().map(|&item| sorted(written_take.iter().copied().chain([item]))).collect(),
    };
    let mut rounds = Vec::with_capacity(takes.len());
    for take in takes {
        let mut successors = Vec::new();
        for (input, stepped) in [(RecursiveInput::Step, true), (RecursiveInput::Skip, false)] {
            let Some(cursors) = reads.at_cursor(group, input, state, &take)? else { continue };
            for cursor in cursors {
                successors.push(if stepped { step(state, &take, &group.conflict, cursor) } else { UnfoldState { cursor, ..state.clone() } });
            }
        }
        rounds.push((take, successors));
    }
    Ok(rounds)
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

