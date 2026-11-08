//! Thin, GIL-releasing entry points for native study filters. JSON carries
//! typed full rows and AST-addressed inventory, never rewritten identities.
use arclog_bindings::{Names, PyMutationPoint, PyStudyProgram};
use arclog_tables::study_filters::{self as filters, Work};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::Value;

fn read(s: &str) -> PyResult<Value> {
    serde_json::from_str(s)
        .map_err(|e| PyValueError::new_err(format!("invalid filter input JSON: {e}")))
}
fn budget(max_work: u64) -> Work {
    Work::new(max_work)
}

/// One fixed equality selection/projection, comparison restriction, or
/// available-table semijoin/antijoin, witnessed at all train inputs.
/// Proven pairs are code-labeled and never sent to a judge. final_output
/// is required; study_final_output derives it from the checked gold AST.
#[pyfunction]
#[pyo3(signature=(gold,mutant,*,n_train,final_output,available="[]",type_domains="{}",restrictions=true,max_work=10_000_000))]
fn study_recovery(
    py: Python<'_>,
    gold: &str,
    mutant: &str,
    n_train: usize,
    final_output: bool,
    available: &str,
    type_domains: &str,
    restrictions: bool,
    max_work: u64,
) -> PyResult<String> {
    let (gold, mutant, available, mut domains) = (
        read(gold)?,
        read(mutant)?,
        read(available)?,
        read(type_domains)?,
    );
    let object = domains
        .as_object_mut()
        .ok_or_else(|| PyValueError::new_err("type_domains must be an object"))?;
    for (ty, values) in arclog_tables::columns::orientation_types(arclog::registry::Registry::get())
    {
        object.entry(ty).or_insert(serde_json::json!(values));
    }
    let mut work = budget(max_work);
    Ok(py
        .detach(|| {
            if restrictions {
                filters::recovery_ext::evaluate(
                    &gold,
                    &mutant,
                    n_train,
                    &domains,
                    &available,
                    final_output,
                    &mut work,
                )
            } else {
                let result =
                    filters::recovery::evaluate(&gold, &mutant, n_train, &domains, &mut work);
                filters::recovery_ext::finish(result, final_output, &work)
            }
        })
        .to_string())
}

#[pyfunction]
#[pyo3(signature=(table,*,earlier="[]",max_work=10_000_000))]
fn study_normalize(
    py: Python<'_>,
    table: &str,
    earlier: &str,
    max_work: u64,
) -> PyResult<String> {
    let (table, earlier) = (read(table)?, read(earlier)?);
    let mut work = budget(max_work);
    Ok(py
        .detach(|| filters::normal::evaluate(&table, &earlier, &mut work))
        .to_string())
}

/// nf4f at a search point: the caller supplies only X and preceding tables.
/// Whole-program used/siblings metadata is never consulted by this route.
#[pyfunction]
#[pyo3(signature=(table,*,earlier="[]",max_work=10_000_000))]
fn study_feature_normalize(py:Python<'_>,table:&str,earlier:&str,max_work:u64)->PyResult<String> {
    let (table,earlier)=(read(table)?,read(earlier)?);
    let mut work=budget(max_work);
    Ok(py.detach(||filters::normal::evaluate_prefix(&table,&earlier,&mut work)).to_string())
}

#[pyfunction]
#[pyo3(signature=(mutant,candidates,*,earlier="[]",max_work=10_000_000))]
fn study_table_equal(
    py: Python<'_>,
    mutant: &str,
    candidates: &str,
    earlier: &str,
    max_work: u64,
) -> PyResult<String> {
    let (mutant, candidates, earlier) = (read(mutant)?, read(candidates)?, read(earlier)?);
    let mut work = budget(max_work);
    Ok(py
        .detach(|| filters::equality::evaluate(&mutant, &candidates, &earlier, &mut work))
        .to_string())
}

/// Whether this gold form defines a relation read directly by OUT. AST
/// relation identity is used throughout; no final token/slot convention.
#[pyfunction]
fn study_final_output(gold: &PyStudyProgram, point: &PyMutationPoint) -> PyResult<bool> {
    use arclog::program::path::{NodePath, NodeRef, node_at};
    use arclog::program::*;
    let top = point
        .inner
        .body
        .0
        .first()
        .ok_or_else(|| PyValueError::new_err("point has no gold form"))?
        .0;
    let form = gold
        .program
        .program()
        .value()
        .forms
        .get(top as usize)
        .ok_or_else(|| PyValueError::new_err("point is outside gold"))?;
    fn belongs(relation: &RelationRef, form: &Form) -> bool {
        match (relation, form) {
            (RelationRef::Declared(name), Form::Clause(c)) => {
                c.value().derives == arclog::program::ProgramRelation::Declared(name.clone())
            }
            (RelationRef::Declared(name), Form::Choose(c)) => name == &c.value().name,
            (
                RelationRef::Output(OutputName {
                    of: OutputOwner::Instance(name),
                    ..
                }),
                Form::Instance(i),
            ) => name == &i.value().name,
            (
                RelationRef::Output(OutputName {
                    of: OutputOwner::RigidDet(name),
                    ..
                }),
                Form::RigidDet(r),
            ) => name == &r.value().name,
            _ => false,
        }
    }
    fn reads(node: NodeRef<'_>, form: &Form) -> bool {
        node.atom().is_some_and(|a| belongs(&a.relation, form))
            || node.children().into_iter().any(|n| reads(n, form))
    }
    let program = gold.program.program().value();
    Ok(program.forms.iter().enumerate().any(|(i, f)| {
        matches!(f, Form::Out(_))
            && node_at(NodeRef::Program(program), &NodePath::top(i as u32))
                .is_some_and(|n| reads(n, form))
    }))
}

pub(crate) fn register(names: &Names<'_, '_>) -> PyResult<()> {
    names.function(wrap_pyfunction!(study_filter_policy, names.module())?)?;
    names.function(wrap_pyfunction!(study_recovery, names.module())?)?;
    names.function(wrap_pyfunction!(study_normalize, names.module())?)?;
    names.function(wrap_pyfunction!(study_feature_normalize, names.module())?)?;
    names.function(wrap_pyfunction!(study_table_equal, names.module())?)?;
    names.function(wrap_pyfunction!(study_final_output, names.module())?)
}

#[pyfunction]
fn study_filter_policy() -> &'static str {
    "native-filters-v1"
}
