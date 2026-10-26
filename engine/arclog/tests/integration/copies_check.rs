//! The check of the rows that an output declares it copies reports an output
//! row whose mapped values are no row of the input, and nothing otherwise.

use arclog::eval::copies::broken_rows;
use arclog::eval::instance::{GroupInputs, GroupOutputs};
use arclog::registry::{is_key, LibEntry, LibName, Registry};
use arclog::relations::RowSet;
use arclog::terms::Term;
use arclog::types::ValueType;

fn rows(arity: u16, rows: &[&[i32]]) -> RowSet {
    let mut set = RowSet::empty(arity);
    for row in rows {
        set.insert(row.iter().map(|&n| Term::encode_number(n)).collect());
    }
    set
}

/// The six outputs of an Order over members 1 and 2, with `minimal` holding `minimal`.
fn broken(minimal: &[&[i32]]) -> Vec<(usize, usize, usize)> {
    let registry = Registry::get();
    let Some(LibEntry::Component(order)) = registry.entry(&LibName("Order".into())) else { panic!("Order is a component") };
    let inputs = [rows(1, &[&[1], &[2]]), rows(2, &[]), rows(2, &[]), rows(2, &[]), rows(1, &[])];
    let numbers: Box<[ValueType]> = Box::new([ValueType::Number]);
    let pair: Box<[ValueType]> = Box::new([ValueType::Number, ValueType::Number]);
    let types = [numbers.clone(), pair.clone(), pair.clone(), pair.clone(), numbers.clone()];
    let columns = [numbers.clone(), pair.clone(), pair.clone(), pair, numbers];
    let wanted = [true; 6];
    let group = GroupInputs { inputs: &inputs, types: &types, columns: &columns, wanted: &wanted };
    let outputs = GroupOutputs { outputs: Box::new([rows(2, &[&[1, 0]]), rows(2, &[&[1, 0]]), rows(1, minimal), rows(1, &[&[2]]), rows(2, &[&[1, 2]]), rows(2, &[&[1, 2], &[2, 1]])]) };
    let widths: Vec<Vec<Option<usize>>> = order.outputs.iter().map(|output| output.columns.iter().map(|column| if is_key(column) { None } else { Some(1) }).collect()).collect();
    broken_rows(order, &group, &outputs, &widths)
}

#[test]
fn an_output_row_that_is_no_row_of_its_input_gives_one_violation() {
    assert_eq!(broken(&[&[1]]), [], "a minimal member");
    assert_eq!(broken(&[&[1], &[9]]), [(2, 0, 1)], "`minimal` holds 9, which is no member");
}
