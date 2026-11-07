//! Each check's prefix form refuses a prefix of a form at the first prefix
//! of [`prefixes`] that no completion passes, and at no prefix before it.

use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{check_program, CheckCache, CheckId, PrefixResult, SolverClauses};
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::eval::values::Caps;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, DecodeSettings, Emitter, Vocabulary};
use arclog::task::Task;
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{Node, Program};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases};

/// The end of the first prefix of the last form of `arclog` that `check`
/// refuses, with the paths of its refusals.
fn first_refused(arclog: &str, check: CheckId) -> Option<(NodePath, Vec<NodePath>)> {
    let solver = read_solver("prefix", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let scope = solver.derived_relations();
    let forms = cases.concept().resolved.value.program.value().forms.clone();
    let (last, complete) = forms.split_last().expect("the file holds a form");
    for prefix in prefixes(last) {
        let held: Vec<_> = complete.iter().cloned().chain([prefix.partial.clone()]).collect();
        let program = resolve(&Node::new(Program { forms: held.into() }), None, &scope, registry).value;
        for (id, result) in check_prefix(&program, &clauses, registry, prefix.open().as_ref()) {
            if let (true, PrefixResult::Refuse(refusals)) = (id == check, result) {
                return Some((prefix.end, refusals.iter().map(|refusal| refusal.at.clone()).collect()));
            }
        }
    }
    None
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|step| PathStep(*step)).collect())
}

#[test]
fn a_read_of_a_name_that_resolves_to_nothing_is_refused_once_the_atom_stands() {
    let found = first_refused("(RULE &x (&nothing *A) (input *P (:Col *C)))", CheckId::Scope);
    assert_eq!(found, Some((path(&[0, 0, 0, 0]), vec![path(&[0, 0])])));
}

#[test]
fn a_site_on_a_column_its_relation_lacks_is_refused_once_the_site_stands() {
    let found = first_refused("(RULE &x (input *P (:Nope *C)))", CheckId::SiteColumns);
    assert_eq!(found, Some((path(&[0, 0, 1, 0]), vec![path(&[0, 0, 1])])));
}

#[test]
fn an_empty_meet_is_refused_at_the_site_that_empties_it() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (dir_elem (:D C)))", CheckId::Types);
    assert_eq!(found, Some((path(&[0, 1, 0, 0]), vec![path(&[0, 0, 1, 0])])));
}

#[test]
fn an_order_on_a_color_is_refused_at_its_constraint() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (input *Q (:Col *E)) (< C E))", CheckId::Types);
    assert_eq!(found, Some((path(&[0, 2]), vec![path(&[0, 2]), path(&[0, 2])])));
}

#[test]
fn a_label_no_mode_binds_is_refused_at_its_site() {
    let found = first_refused("(RULE &x (input *P (:Col *C)) (compose *A *B *Q) (input Q (:Col C)))", CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 1, 0, 0]), vec![path(&[0, 1, 0, 0])])));
}

/// An `OR` whose branches bind `X` and `Y` only from each other, written
/// before the conjunct that binds `X`, leaves `X` and `Y` unbound at the
/// prefix that ends the `OR`, where a conjunct written after the `OR` binds
/// `X` for the whole clause, so a completion passes.
#[test]
fn a_label_an_or_binds_from_a_label_a_later_conjunct_binds_is_refused_at_no_prefix() {
    let arclog = "(RULE &x (OR ((input *P (:Col *X)) (input P (:Col *Y))) ((= X Y))) (input *Q (:Col X)))";
    assert_eq!(first_refused(arclog, CheckId::Safety), None);
}

/// A site of `frame_extent` whose label no mode binds from the conjuncts
/// before the atom is refused only if no later site of the atom binds the
/// column that a mode needs: the mode of `frame_extent` needs its `P`
/// column, which the site written after `*N` gives.
#[test]
fn a_site_whose_atom_takes_a_later_site_that_a_mode_needs_is_refused_at_no_prefix() {
    assert_eq!(first_refused("(RULE &x (input *P) (frame_extent *N P))", CheckId::Safety), None);
}

/// The mode of `compose` needs its `A` and `B` columns bound. With `A` at
/// the bound `P`, the atom can still take a bound label at `B`, so the site
/// `(:A P)` stands unrefused; the site `(:B *U)` makes `U` unbound, and no
/// site written after it binds it.
#[test]
fn a_site_whose_atom_has_no_mode_that_a_later_site_completes_is_refused_at_the_site() {
    let found = first_refused("(RULE &x (input *P) (compose (:A P) (:B *U) (:C *W)))", CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 1, 1, 0]), vec![path(&[0, 1, 1, 0])])));
}

#[test]
fn a_per_input_read_of_ex_input_is_refused_once_its_atom_opens() {
    let found = first_refused("(RULE &x (ex_input *E *P (:Col *C)))", CheckId::PooledAndLiftedReads);
    assert_eq!(found, Some((path(&[0, 0, 0, 0]), vec![path(&[0, 0])])));
}

#[test]
fn an_input_its_component_does_not_declare_is_refused_at_the_input() {
    let found = first_refused("(DET &arr_dim ScaleRatio)\n(INIT &f Frame (nope (A) (axis_elem *A)))", CheckId::InstanceInputs);
    assert_eq!(found, Some((path(&[0]), vec![path(&[0])])));
}

#[test]
fn an_algebra_atom_that_leaves_out_an_input_no_mode_leaves_out_is_refused_once_the_atom_stands() {
    let arclog = "(RULE &x (input *P (:Col *C)) (dir_elem *D) (axis_inset D (:K1 C) (:B P)))";
    let found = first_refused(arclog, CheckId::Safety);
    assert_eq!(found, Some((path(&[0, 2]), vec![path(&[0, 2])])));
}

/// At each state along the stream of a clause whose `OR` holds a label local
/// to its branches, after the label of an orientation type, the mask admits
/// the tokens that a step of a decode with no mask in front of it admits: the
/// bindings that the mask keeps across its candidates are those each
/// candidate's own check finds.
#[test]
fn the_mask_admits_the_tokens_a_step_admits_along_a_clause_with_an_or_and_an_orientation_label() {
    let source = "(RULE &x (input *P *Col) (dir_elem *D) (OR ((input P (:Col *E)) (!= E Col)) ((input P (:Col *F)) (!= F Col))) (input (:P *Q) (:Col Col)))\n";
    let solver = read_solver("prefix", source, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let concept = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let checked = check_program(concept, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let stream = token_stream(&checked, &vocabulary).expect("the program has a stream");
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let task = Task { train: Box::new([]), test: Box::new([]) };
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let mut decoder = Decoder::new(&task, &session, registry, &constructions, &DecodeSettings::default());
    let mut compared = 0;
    for (token, emitter) in &stream {
        if matches!(emitter, Emitter::Engine) {
            continue;
        }
        let mask = decoder.admissible();
        for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
            let stepped = decoder.fork().step(vocabulary.token(id).expect("an id of the vocabulary").clone()).is_ok();
            assert_eq!(mask.contains(id), stepped, "{:?} before {token:?}", vocabulary.token(id));
            compared += 1;
        }
        decoder.step(token.clone()).expect("a token of the stream");
    }
    assert!(compared > 0);
}
