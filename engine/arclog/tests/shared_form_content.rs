//! A form that two case programs share, by one node, takes in each the
//! resolved content that a resolution of that program alone gives it, so
//! the write its node keeps from one program serves the other only where
//! each name the form reads has the same content in both.

use std::sync::Arc;

use arclog::layout::SourceFile;
use arclog::program::path::NodePath;
use arclog::program::{Node, Program};
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::{resolve, ResolvedContent};

fn read(text: &str) -> Node<Program> {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    read.value.0
}

/// The resolved content of the second form of `program`.
fn second_form(program: &Node<Program>) -> ResolvedContent {
    let resolved = resolve(program, None, &Default::default(), Registry::get());
    assert!(resolved.diagnostics.is_empty(), "{:?}", resolved.diagnostics);
    resolved.value.content(&NodePath::top(1)).expect("the form has its content")
}

#[test]
fn a_shared_form_takes_the_content_of_the_names_it_reads_in_each_program() {
    let reads = "(RULE &reads (&read *Col))\n";
    let first = read(&format!("(RULE &read (input *P *Col))\n{reads}"));
    let second_alone = read(&format!("(RULE &read (input *P *Col) (= *Col 0))\n{reads}"));
    let shared = Node::new(Program { forms: Arc::from([second_alone.value().forms[0].clone(), first.value().forms[1].clone()]) });
    let in_first = second_form(&first);
    let in_shared = second_form(&shared);
    assert_ne!(in_first, in_shared);
    assert_eq!(in_shared, second_form(&second_alone));
    assert_eq!(second_form(&first), in_first);
}
