//! The resolver lifts a task-wide form's read of a per-input relation, a
//! `&prediction` clause of a task-wide `DEMONSTRATED` form and the bodies
//! of an instance keyed on `E` included, reads such an instance's outputs
//! unlifted, and
//! writes the content of a `DEMONSTRATED` form with the names its rules
//! declare resolved.

use arclog::layout::SourceFile;
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ColumnPosition, GraphNodeIndex, MacroExpansion, ResolvedProgram, Side};

fn resolved(text: &str) -> ResolvedProgram {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    let (program, _) = read.value;
    let resolved = resolve(&program, None, &Default::default(), Registry::get(), MacroExpansion::Keep);
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
