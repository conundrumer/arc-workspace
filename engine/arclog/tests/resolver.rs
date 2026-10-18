//! The resolver lifts a task-wide form's read of a per-input relation, a
//! `&prediction` clause of a task-wide `DEMONSTRATED` form and the bodies
//! of an instance keyed on an Example label included, reads such an
//! instance's outputs unlifted, gives a keyed instance the task-wide side
//! where its key holds an Example label, by what the label holds, and
//! writes the content of a `DEMONSTRATED` form with the names its rules
//! declare resolved.

use arclog::layout::SourceFile;
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ColumnPosition, ConceptReads, GraphNodeIndex, ResolvedProgram, Side};

fn resolved(text: &str) -> ResolvedProgram {
    resolved_with(text, None)
}

fn resolved_with(text: &str, concept: Option<ConceptReads<'_>>) -> ResolvedProgram {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    let (program, _) = read.value;
    let resolved = resolve(&program, concept, &Default::default(), Registry::get());
    assert!(resolved.diagnostics.is_empty(), "{:?}", resolved.diagnostics);
    resolved.value
}

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().copied().map(PathStep).collect())
}

/// The position of the site of the first atom of the clause at `form`.
fn first_site(program: &ResolvedProgram, form: u32) -> ColumnPosition {
    program.column_position(&path(&[form, 0, 0, 0])).expect("the site has a position")
}

#[test]
fn a_det_reads_a_rule_relation_lifted_with_no_site_on_e() {
    let program = resolved(
        "(RULE &cell (input *P *Col))\n\
         (RULE &rule_reads (&cell *Col))\n\
         (DET &det_reads (&cell *Col))\n",
    );
    let in_rule = first_site(&program, 1);
    assert_eq!(first_site(&program, 2), ColumnPosition(in_rule.0 + 1));
}

fn demonstrated(local: &str) -> String {
    format!(
        "(RULE &stage (input *P *Col))\n\
         (DEMONSTRATED &catalog\n\
           (value ((:o P) (:v Col))\n\
             (&stage *P *Col))\n\
           (demonstration ((:o P) (:o2 P2))\n\
             (&stage *P *Col)\n\
             (&stage *P2 Col))\n\
           (DEMO_RULE $Same\n\
             (RULE {local} (&stage *P *Col))\n\
             (RULE &prediction ({local} *P *Col))))\n"
    )
}

#[test]
fn demonstrated_forms_whose_rules_name_a_local_relation_apart_have_equal_content() {
    let contents: Vec<_> = ["&local", "&other"]
        .iter()
        .map(|local| resolved(&demonstrated(local)).content(&path(&[1])).expect("the form has content"))
        .collect();
    assert_eq!(contents[0], contents[1]);
}

#[test]
fn the_prediction_of_a_task_wide_demonstrated_form_reads_lifted() {
    let program = resolved(
        "(RULE &stage (input *P *Col))\n\
         (DEMONSTRATED &catalog\n\
           (key ((&stage ^E))\n\
             (value ((:o P) (:v Col))\n\
               (&stage E *P *Col))\n\
             (demonstration ((:o P) (:o2 P2))\n\
               (&stage E *P *Col)\n\
               (&stage E *P2 Col)))\n\
           (DEMO_RULE $Same\n\
             (RULE &prediction (&stage *E *P *Col))))\n",
    );
    let prediction = path(&[1, 1, 0]);
    let node = (0..program.graph.nodes.len() as u32)
        .map(GraphNodeIndex)
        .find(|node| *program.form_of(*node) == prediction)
        .expect("a node of the `&prediction` clause");
    assert_eq!(program.side(node), Side::TaskWide);
    let positions: Vec<_> = (0..3).map(|site| program.column_position(&path(&[1, 1, 0, 0, 0, site]))).collect();
    assert_eq!(positions, [0, 1, 2].map(|position| Some(ColumnPosition(position))));
}

#[test]
fn an_instance_keyed_on_e_is_task_wide_and_a_det_reads_its_outputs_unlifted() {
    let program = resolved(
        "(RULE &bg (input *P *Col))\n\
         (DET &cells (ex_input *E *P *Col))\n\
         (INIT &obj Connectivity\n\
           (key ((&cells ^E *P))\n\
             (node (P)\n\
               (&cells E *P)\n\
               (&bg *Col))))\n\
         (DET &reads (&obj.component (:key *E) *P *Id))\n",
    );
    let obj = path(&[2]);
    let nodes: Vec<_> = (0..program.graph.nodes.len() as u32)
        .map(GraphNodeIndex)
        .filter(|node| program.form_of(*node).0.starts_with(&obj.0))
        .collect();
    assert!(!nodes.is_empty());
    assert!(nodes.iter().all(|node| program.side(*node) == Side::TaskWide));
    let positions: Vec<_> = (1..3).map(|site| program.column_position(&path(&[3, 0, 0, site]))).collect();
    assert_eq!(positions, [1, 2].map(|position| Some(ColumnPosition(position))));
    assert_eq!(program.column_position(&path(&[3, 0, 0, 0, 0])), Some(ColumnPosition(0)));
    assert_eq!(program.column_position(&path(&[2, 0, 1, 1, 1, 0])), Some(ColumnPosition(2)));
}

/// The side of each node of the form at `form`.
fn form_sides(program: &ResolvedProgram, form: u32) -> Vec<Side> {
    let form = path(&[form]);
    let sides: Vec<Side> = (0..program.graph.nodes.len() as u32)
        .map(GraphNodeIndex)
        .filter(|node| program.form_of(*node).0.starts_with(&form.0))
        .map(|node| program.side(node))
        .collect();
    assert!(!sides.is_empty());
    sides
}

const PER_INPUT_BACKGROUND: &str = "(RULE &bg (input *P *Col))\n";

#[test]
fn an_instance_keyed_on_an_example_label_of_another_name_is_task_wide() {
    let program = resolved(&format!(
        "{PER_INPUT_BACKGROUND}\
         (DET &cells (ex_input *E *P *Col))\n\
         (INIT &obj Connectivity\n\
           (key ((&cells (:E ^K) *P))\n\
             (node (P)\n\
               (&cells (:E K) *P)\n\
               (&bg *P *Col))))\n\
         (INIT &next Connectivity\n\
           (key ((&obj.component (:key (:K ^K2)) *P *Id))\n\
             (node (P)\n\
               (&obj.component (:key (:K K2)) *P *Id)\n\
               (&bg *P *Col))))\n",
    ));
    assert!(form_sides(&program, 2).iter().all(|side| *side == Side::TaskWide));
    assert!(form_sides(&program, 3).iter().all(|side| *side == Side::TaskWide));
}

#[test]
fn an_instance_keyed_on_a_det_column_bound_at_an_example_site_is_task_wide() {
    let program = resolved(&format!(
        "{PER_INPUT_BACKGROUND}\
         (DET &top (ex_input (:E *Ky) *P *Col))\n\
         (INIT &obj Connectivity\n\
           (key ((&top ^Ky *P))\n\
             (node (P)\n\
               (&top Ky *P)\n\
               (&bg *P *Col))))\n",
    ));
    assert!(form_sides(&program, 2).iter().all(|side| *side == Side::TaskWide));
}

#[test]
fn an_instance_keyed_on_a_field_named_e_that_holds_no_example_takes_its_side_by_its_reads() {
    let program = resolved(
        "(RULE &piece (input (:P *Id) *Col))\n\
         (INIT &obj Connectivity\n\
           (key ((&piece (:Id ^E)))\n\
             (node (P)\n\
               (&piece (:Id E) (:Col *P)))))\n",
    );
    assert!(form_sides(&program, 1).iter().all(|side| *side == Side::PerInput));
}

#[test]
fn an_instance_keyed_on_a_demonstrated_key_field_that_holds_an_example_is_task_wide() {
    let program = resolved(&format!(
        "{PER_INPUT_BACKGROUND}\
         (DET &cells (ex_input (:E *K) *P *Col))\n\
         (DEMONSTRATED &catalog\n\
           (key ((&cells ^K *P))\n\
             (value ((:o P) (:v Col))\n\
               (&cells K *P)\n\
               (&bg *P *Col))\n\
             (demonstration ((:o P) (:o2 P2))\n\
               (&bg *P *Col)\n\
               (&bg *P2 Col)))\n\
           (DEMO_RULE $Same\n\
             (RULE &prediction (&bg *P *Col))))\n\
         (INIT &obj Connectivity\n\
           (key ((&catalog (:key (:K ^K2)) (:o *P)))\n\
             (node (P)\n\
               (&catalog (:key (:K K2)) (:o *P))\n\
               (&bg *P *Col))))\n",
    ));
    assert!(form_sides(&program, 3).iter().all(|side| *side == Side::TaskWide));
}

#[test]
fn an_instance_keyed_on_an_example_column_of_a_concept_det_is_task_wide() {
    let det = "(DET &d (ex_input (:E *Ky) *P *Col))\n";
    let concept = resolved(det);
    let determinations = [path(&[0])];
    let program = resolved_with(
        &format!(
            "{det}{PER_INPUT_BACKGROUND}\
             (INIT &obj Connectivity\n\
               (key ((&d ^Ky *P))\n\
                 (node (P)\n\
                   (&d Ky *P)\n\
                   (&bg *P *Col))))\n",
        ),
        Some(ConceptReads { concept: &concept, determinations: &determinations }),
    );
    assert!(form_sides(&program, 2).iter().all(|side| *side == Side::TaskWide));
}

#[test]
fn an_instance_keyed_on_a_chosen_column_that_holds_an_example_is_task_wide() {
    let program = resolved(&format!(
        "{PER_INPUT_BACKGROUND}\
         (CHOOSE &pick\n\
           (from (ex_input (:E *Ky) *P *Col)))\n\
         (INIT &obj Connectivity\n\
           (key ((&pick ^Ky *P))\n\
             (node (P)\n\
               (&pick Ky *P)\n\
               (&bg *P *Col))))\n",
    ));
    assert!(form_sides(&program, 2).iter().all(|side| *side == Side::TaskWide));
}

#[test]
fn an_instance_keyed_on_a_column_whose_binding_head_projects_an_example_label_is_task_wide() {
    let programs = [
        "(INIT &classes Quotient\n\
           (edge ((:a E P) (:b E (:P Q)))\n\
             (ex_input *E *P *Col)\n\
             (ex_input E (:P *Q) Col)))\n\
         (INIT &obj Connectivity\n\
           (key ((&classes.class (:a (:E ^K) *P)))\n\
             (node (P)\n\
               (&classes.class (:a (:E K) *P))\n\
               (&bg *P *Col))))\n",
        "(INIT &ord Order\n\
           (member ((:t E))\n\
             (ex_input *E *P *Col)))\n\
         (INIT &obj Connectivity\n\
           (key ((&ord.rank (:t ^K) *R))\n\
             (node (P)\n\
               (&ord.rank (:t K) *R)\n\
               (&bg *P *Col))))\n",
        "(DEMONSTRATED &catalog\n\
           (value ((:o E P) (:v Col))\n\
             (ex_input *E *P *Col))\n\
           (demonstration ((:o E P) (:o2 E P2))\n\
             (ex_input *E *P *Col)\n\
             (ex_input E *P2 Col))\n\
           (DEMO_RULE $Same\n\
             (RULE &prediction (&bg *P *Col))))\n\
         (INIT &obj Connectivity\n\
           (key ((&catalog (:o (:E ^K) *P)))\n\
             (node (P)\n\
               (&catalog (:o (:E K) *P))\n\
               (&bg *P *Col))))\n",
    ];
    for forms in programs {
        let program = resolved(&format!("{PER_INPUT_BACKGROUND}{forms}"));
        assert!(form_sides(&program, 2).iter().all(|side| *side == Side::TaskWide), "{forms}");
    }
}
