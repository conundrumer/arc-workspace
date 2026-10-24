//! At the `END` of a `RULE` clause, a decode reports whether the relation,
//! read as `&output`, solves the train pairs, keeps the assignments of a
//! `DET` under which it does, and ends at a consistent relation; a prefix
//! past the row cap reports the stop and the cap; and a batch of decodes
//! gives the results of each decode stepped alone.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::{step_batch, Consistency, Decoder, Point, Points, Refusal, Projections, TableRelation};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::Pool;
use arclog::eval::{Caps, ReachedBound, RelationValue};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::program::ProgramRelation;
use arclog::relations::Relation;
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::{Color, Example};

type Assignment = (ProgramRelation, Arc<Relation>);

/// The input of the one train pair: one row of two cells.
const INPUT: &[u8] = &[1, 2];

const COPIES: &str = "(RULE &output (input *P *Col))\n";

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

/// The checked concept program of `arclog`.
fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("decode", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

/// What a decode runs on: a task of one train pair whose output is
/// `output`, under `caps`.
struct Inputs {
    task: Task,
    judged: JudgedTask,
    session: TaskSession,
    constructions: Constructions,
    settings: DecodeSettings,
}

fn inputs(output: &[u8], caps: Caps) -> Inputs {
    let task = Task { train: Box::new([TrainPair { input: grid(INPUT), output: grid(output) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, caps);
    Inputs { task, judged, session, constructions, settings: DecodeSettings { caps, ..DecodeSettings::default() } }
}

fn decoder(inputs: &Inputs) -> Decoder<'_> {
    let train: Arc<[PairCandidates<'_>]> = inputs.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, &inputs.settings).judging(train)
}

/// The tokens of the language model in the stream of `arclog`.
fn model_tokens(arclog: &str) -> Vec<Token> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&checked(arclog), &vocabulary).expect("the program has a stream");
    stream.into_iter().filter(|(_, emitter)| *emitter == Emitter::Model).map(|(token, _)| token).collect()
}

/// Steps `decoder` through `tokens`, and gives the last consistency a step
/// gave.
fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) -> Option<Consistency> {
    let mut last = None;
    for token in tokens {
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        last = step.consistency.or(last);
    }
    last
}

#[test]
fn a_relation_that_solves_the_pairs_is_consistent_and_ends_the_decode() {
    let inputs = inputs(INPUT, Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES);
    assert!(matches!(walk(&mut decoder, &tokens), Some(Consistency::Consistent { .. })));
    assert!(decoder.output().is_some());
    assert!(matches!(decoder.step(Token::Control(Control::Rule)), Err(Refusal::Grammar(_))), "the decode has ended");
}

#[test]
fn a_relation_that_does_not_solve_the_pairs_is_not_consistent() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    assert!(matches!(walk(&mut decoder, &model_tokens(COPIES)), Some(Consistency::NotConsistent)));
    assert!(decoder.output().is_none());
}

#[test]
fn a_det_of_two_values_keeps_the_assignment_that_solves_the_pairs() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let program = "(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n";
    let Some(Consistency::Consistent { assignments }) = walk(&mut decoder, &model_tokens(program)) else { panic!("a consistent relation") };
    assert_eq!(assignments.len(), 1, "one value of `&c` paints the output: {assignments:?}");
}

#[test]
fn a_prefix_past_the_row_cap_is_stopped_at_the_cap() {
    let caps = Caps { rows: 1, ..Caps::CORPUS };
    let inputs = inputs(INPUT, caps);
    let mut decoder = decoder(&inputs);
    let tokens = model_tokens(COPIES);
    let (end, prefix) = tokens.split_last().expect("a stream");
    assert_eq!(*end, Token::Control(Control::End));
    walk(&mut decoder, prefix);
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    let [(_, value)] = &rows.at[..] else { panic!("one entry: {rows:?}") };
    let RelationValue::Stopped(stop) = &value.0 else { panic!("a stop: {value:?}") };
    assert_eq!(stop.bound, ReachedBound::Rows { cap: 1 });
}

#[test]
fn a_batch_of_decodes_gives_the_results_of_each_decode_alone() {
    let consistent = inputs(INPUT, Caps::CORPUS);
    let inconsistent = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let alone: Vec<String> = [&consistent, &inconsistent]
        .iter()
        .map(|inputs| {
            let mut decoder = decoder(inputs);
            tokens.iter().map(|token| format!("{:?}", decoder.step(token.clone()))).collect::<Vec<_>>().join("\n")
        })
        .collect();
    let pool = Pool::new(Some(2));
    let mut decoders = [decoder(&consistent), decoder(&inconsistent)];
    let mut batched = vec![Vec::new(); 2];
    for token in &tokens {
        let results = step_batch(&pool, &mut decoders, &[token.clone(), token.clone()]);
        for (seen, result) in batched.iter_mut().zip(results.iter()) {
            seen.push(format!("{result:?}"));
        }
    }
    let batched: Vec<String> = batched.into_iter().map(|steps| steps.join("\n")).collect();
    assert_eq!(batched, alone);
}

/// The counts of the sub-body of the clause in progress after `tokens`, at
/// each assignment, with the assignments.
fn counts_after(inputs: &Inputs, tokens: &[Token]) -> Vec<(Vec<Assignment>, Option<u64>)> {
    let mut decoder = decoder(inputs);
    walk(&mut decoder, tokens);
    let counts = decoder.counts().expect("a clause in progress");
    let [counted] = &*counts else { panic!("one example: {counts:?}") };
    let counted = counted.as_ref().expect("the sub-body checks");
    assert!(counted.stop.is_none());
    counted.at.clone()
}

const BG: &str = "(RULE &bg (input (:Col *C)))\n";
const FG: &str = "(RULE &fg (input *P *Col) (&bg (:C *V)) (!= Col V))\n";

#[test]
fn a_prefix_that_reads_a_det_of_two_values_gives_its_rows_at_each_value() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let tokens = model_tokens("(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n");
    let (_, prefix) = tokens.split_last().expect("a stream");
    let counted = counts_after(&inputs, prefix);
    let values: Vec<_> = counted.iter().map(|(assigned, _)| assigned.clone()).collect();
    assert_eq!(values.len(), 2, "one entry for each value of `&c`: {counted:?}");
    assert!(values.iter().all(|assigned| assigned.len() == 1));
    assert!(format!("{:?}", values[0][0].1) != format!("{:?}", values[1][0].1), "the two entries hold two values of `&c`");
    assert!(counted.iter().all(|(_, count)| count.is_some()));
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, prefix);
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    assert_eq!(rows.at.len(), 2);
}

#[test]
fn a_prefix_that_reads_no_det_of_several_values_gives_one_entry() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let (_, prefix) = tokens.split_last().expect("a stream");
    let counted = counts_after(&inputs, prefix);
    assert!(matches!(&counted[..], [(assigned, _)] if assigned.is_empty()), "{counted:?}");
}

#[test]
fn a_prefix_past_the_assignment_cap_gives_the_stop() {
    let caps = Caps { assignments: 1, ..Caps::CORPUS };
    let inputs = inputs(&[3, 3], caps);
    let tokens = model_tokens("(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n");
    let (_, prefix) = tokens.split_last().expect("a stream");
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, prefix);
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    assert_eq!(rows.at.len(), 1);
    assert_eq!(rows.stop.expect("a stop").bound, ReachedBound::Assignments { cap: 1 });
}

#[test]
fn a_choose_form_with_its_from_clause_open_gives_the_rows_of_that_clause() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let pick = "(CHOOSE &pick (from (&fg *P *Col)) (never (&fg *P *Col) (&fg (:P *P2) Col) (!= P P2) (&bg (:C Col))))\n";
    let tokens = model_tokens(&format!("{BG}{FG}{pick}"));
    let at = tokens.iter().position(|token| *token == Token::Control(Control::Choose)).expect("a `CHOOSE` form");
    let written = counts_after(&inputs, &tokens[..at + 7]);
    let rule = model_tokens(&format!("{BG}{FG}(RULE &copy (&fg *P *Col))\n"));
    let (_, plain) = rule.split_last().expect("a stream");
    let expected = counts_after(&inputs, plain);
    let counts = |counted: &[(Vec<Assignment>, Option<u64>)]| counted.iter().map(|(_, count)| *count).collect::<Vec<_>>();
    assert_eq!(counts(&written), counts(&expected));
    assert!(written[0].1.is_some_and(|count| count > 0), "{written:?}");
}

#[test]
fn a_prefix_inside_an_algebra_atom_without_the_sites_of_a_mode_gives_the_rows_of_the_conjuncts_before_it() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens("(RULE &output (input *P *Col) (axis_elem *A) (split P A (:Along *Q)))\n");
    let at = tokens.iter().position(|token| *token == Token::Lib(LibName("split".into()))).expect("a `split` atom");
    let rows_after = |prefix: &[Token]| {
        let mut decoder = decoder(&inputs);
        walk(&mut decoder, prefix);
        decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks")
    };
    let before = rows_after(&tokens[..at]);
    let inside = rows_after(&tokens[..=at]);
    assert_eq!(format!("{:?}", inside.at), format!("{:?}", before.at));
}

#[test]
fn a_det_clause_in_progress_gives_the_rows_of_its_kept_conjuncts() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens("(DET &cells (ex_input *E *P *Col))\n(RULE &output (input (:P *Q)) (&cells (:Col *Col)))\n");
    let at = tokens.iter().position(|token| *token == Token::Control(Control::Det)).expect("a `DET` form");
    let after = |count: usize| {
        let mut decoder = decoder(&inputs);
        walk(&mut decoder, &tokens[..count]);
        let counts = decoder.counts().expect("a clause in progress");
        let [counted] = &*counts else { panic!("a task-wide clause gives one entry: {counts:?}") };
        let counted = counted.as_ref().expect("the sub-body checks").at.clone();
        let rows = decoder.rows(None).expect("a clause in progress").expect("the sub-body checks");
        assert_eq!(rows.at.len(), 1, "the clause's own `DET` is not assigned");
        (counted, rows)
    };
    after(at + 1);
    let (counted, _) = after(at + 4);
    assert!(counted[0].1.is_some_and(|count| count > 0), "{counted:?}");
}

#[test]
fn a_body_under_the_projection_cap_is_its_one_projection_with_the_rows_of_the_body() {
    let inputs = inputs(&[3, 3], Caps::CORPUS);
    let tokens = model_tokens(COPIES);
    let (_, prefix) = tokens.split_last().expect("a stream");
    let mut decoder = decoder(&inputs);
    walk(&mut decoder, prefix);
    let Some(Ok(Projections::Found(found))) = decoder.projections() else { panic!("the projections of a clause in progress") };
    let [projection] = &found[..] else { panic!("one projection: {found:?}") };
    let rows = decoder.rows(Some(Example::at(0))).expect("a clause in progress").expect("the sub-body checks");
    let [(_, body)] = &rows.at[..] else { panic!("one entry: {rows:?}") };
    let RelationValue::Rows(body) = &body.0 else { panic!("rows: {body:?}") };
    assert_eq!(projection.columns.len(), usize::from(body.arity()));
    let [projected_example] = &projection.rows[..] else { panic!("one example: {projection:?}") };
    let [(_, Some(projected))] = &projected_example.at[..] else { panic!("one projection: {projected_example:?}") };
    assert_eq!((projected.arity(), projected.len()), (body.arity(), body.len()));
    assert!(self::decoder(&inputs).projections().is_none(), "no clause is in progress before the first token");
}

#[test]
fn the_table_of_a_det_at_the_end_of_its_form_gives_its_rows_at_each_value() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let tokens = model_tokens("(DET &c ColorDomain)\n(RULE &output (input *P) (&c (:C *Col)))\n");
    let mut decoder = decoder(&inputs);
    let mut found = None;
    for token in &tokens {
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        let tables = decoder.tables(Points::All);
        if tables.iter().any(|table| table.point == Point::Relation) {
            found = Some(tables);
            break;
        }
    }
    let tables = found.expect("the DET form ends");
    let [table] = &tables[..] else { panic!("one relation: {tables:?}") };
    let contents = table.contents.as_ref().expect("the table has contents");
    assert_eq!(contents.dets.len(), 1, "the DET's own table gives that DET");
    let [example] = &*contents.examples else { panic!("one example: {contents:?}") };
    let rows = example.rows.as_ref().expect("the example gives no fault");
    assert!(rows.stop.is_none());
    assert!(rows.at.len() > 1, "one entry for each value of `&c`: {rows:?}");
    assert!(rows.at.iter().all(|(assigned, models)| assigned.len() == 1 && !models.is_empty()));
}

#[test]
fn the_tables_of_a_connectivity_form_give_component_and_adjacent_and_no_connected() {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let tokens = model_tokens("(RULE &fg (input *P *Col))\n(INIT &comps Connectivity (node ((:P P)) (&fg *P)))\n(RULE &output (&comps.component *P *Id))\n");
    let mut decoder = decoder(&inputs);
    let mut relation_batches = Vec::new();
    for token in &tokens {
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        let tables: Vec<_> = decoder.tables(Points::Relations).into_iter().filter(|table| table.point == Point::Relation).collect();
        if !tables.is_empty() {
            relation_batches.push(tables);
        }
    }
    let [_, comps, _] = &relation_batches[..] else { panic!("one batch each for `&fg`, the INIT form and `&output`: {}", relation_batches.len()) };
    let slots: Vec<_> = comps.iter().map(|table| match &table.contents.as_ref().expect("the table has contents").relation {
        TableRelation::Slot(slot) => *slot,
        TableRelation::Fact(fact) => panic!("a fact relation {fact:?}"),
    }).collect();
    // The slots of the form, in order: `component` 1, `connected` 2, `adjacent` 3, and the input `node` 4. The slots of `connected` and of `node`, whose body is one atom of a declared relation, give no table.
    assert_eq!(slots, [1, 3]);
    assert!(comps.iter().all(|table| table.contents.is_ok()));
}

/// The slots of the tables of the last form that `arclog` finishes, in order.
fn slots_of_last_form(arclog: &str) -> Vec<u32> {
    let inputs = inputs(&[2, 2], Caps::CORPUS);
    let mut decoder = decoder(&inputs);
    let mut last = Vec::new();
    for token in &model_tokens(arclog) {
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        let tables: Vec<_> = decoder.tables(Points::Relations).into_iter().filter(|table| table.point == Point::Relation).collect();
        if !tables.is_empty() {
            last = tables;
        }
    }
    last.iter().map(|table| match &table.contents.as_ref().expect("the table has contents").relation {
        TableRelation::Slot(slot) => *slot,
        TableRelation::Fact(fact) => panic!("a fact relation {fact:?}"),
    }).collect()
}

#[test]
fn an_input_of_one_atom_of_a_fact_or_declared_relation_gives_no_table() {
    // `source` reads a declared relation, `node` a fact relation, and `dir` a lib relation.
    let slots = slots_of_last_form("(RULE &fg (input *P *Col))\n(INIT &rays Ray (source (P) (&fg *P)) (node (P) (input *P *Col)) (dir (D) (dir8_elem *D)))\n");
    assert_eq!(slots, [1, 2, 5], "`ray`, `end` and `dir`; `source` and `node` give none");
}

#[test]
fn an_input_of_two_conjuncts_gives_its_table() {
    let slots = slots_of_last_form("(RULE &fg (input *P *Col))\n(INIT &comps Connectivity (node (P) (&fg *P) (input *P *Col)))\n");
    assert_eq!(slots, [1, 3, 4], "`component`, `adjacent` and `node`");
}

#[test]
fn an_input_of_one_atom_in_a_key_clause_gives_no_table() {
    let slots = slots_of_last_form("(RULE &fg (input *P *Col))\n(INIT &rays Ray (key ((&fg *P ^Col)) (source (P) (&fg *P Col))) (node (P) (input *P *Col)) (dir (D) (dir8_elem *D)))\n");
    assert_eq!(slots, [1, 2, 5], "`source` in the key clause and `node` give none");
}
