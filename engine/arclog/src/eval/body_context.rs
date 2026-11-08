//! State-local body queries of recursive instances. The selected model
//! retains its reached states, so a NOT reads one state rather than the
//! union of unrelated states along the walk.
use super::{driver::Driver,body_view::BodyView,init_form::{key_group_rows,key_relation,InstanceShape},models,unfold::UnfoldOutput,Outcome,RelationValue,RunFault};
use crate::program::path::{node_at,NodeRef};
use crate::program::{OutputStep,PortName};
use crate::resolver::{registry_columns,DependencyKind};
use crate::terms::Example;
use crate::types::GraphRelation;
use std::sync::Arc;

pub(super) fn value(driver:&Driver<'_, '_>,view:&BodyView,example:Option<Example>)->Outcome<RelationValue> {
    let evaluation=driver.evaluation;
    let fault=|message:String|RunFault {message:message.into(),form:view.form.clone()};
    let plain=||driver.bodies().relation(&view.form,&view.clause,example);
    if !view.uses_owner_context(evaluation.program,evaluation.registry)? {return plain();}
    let Some(port)=&view.input else {unreachable!("an owner-context query has an input")};
    let Some(NodeRef::Instance(instance))=node_at(NodeRef::Program(evaluation.program.program.program.value()),&view.form) else {return Err(fault("input query owner is not an instance".into()))};
    let component=registry_columns::component(evaluation.registry,&instance.component).ok_or_else(||fault("body component is absent".into()))?;
    let declared=component.inputs.iter().find(|i|i.port.name==*port).ok_or_else(||fault("body input is absent".into()))?;
    let node=evaluation.program.program.nodes_of(&view.form).iter().copied().find(|n|matches!(&evaluation.program.program.graph.nodes[n.0 as usize].kind,DependencyKind::RecursiveInstance(_))).ok_or_else(||fault("recursive body has no recursive owner".into()))?;
    let shape=InstanceShape::of(evaluation.program,&view.form,instance,component);
    let input=shape.input_clause(evaluation.program,&view.form,declared).map_err(fault)?.ok_or_else(||fault("recursive body is not written".into()))?;
    let contexts=match models::walk_contexts(driver,node,example)? {Ok(contexts)=>contexts,Err(value)=>return Ok(value)};
    let mut rows=crate::relations::RowSet::empty(view.clause.columns.len() as u16);
    let layout=super::unfold::OutputLayout::at(evaluation,&view.form)?;
    // A body that reads the outputs at a key it names reads the other keys' rows of this model.
    let mut reached=Vec::new();
    if shape.reads_outputs_at_keys(&instance.name,component) {
        for which in UnfoldOutput::ALL {
            let mut held=crate::relations::RowSet::empty(contexts.first().map_or(0,|context|context.key.len()+layout.width()) as u16);
            for context in &contexts {
                let branch=super::unfold::Branch {take:context.take.clone(),next:Box::default()};
                which.add_rows(layout,&context.records,&context.key,&context.state,&branch,&mut held);
            }
            reached.push(held);
        }
    }
    for context in contexts {
        let Some(bound)=input.at_state(&context.key,context.state.cursor,&context.records).map_err(fault)? else {continue};
        let take=if port.0.as_ref()=="take" {&[][..]} else {&context.take};
        let mut saved=Vec::new();
        for (at,which) in UnfoldOutput::ALL.into_iter().enumerate() {
            let relation=GraphRelation {node,output:Some(Arc::from([OutputStep::Port(which.port())]))};
            let mut local=crate::relations::RowSet::empty((context.key.len()+layout.width()) as u16);
            let branch=super::unfold::Branch {take:take.into(),next:Box::default()};
            which.add_rows(layout,&context.records,&context.key,&context.state,&branch,&mut local);
            if let Some(reached)=reached.get(at) {super::unfold::add_other_keys(reached,&context.key,&mut local);}
            let entry=(relation,example);
            let old=driver.values.borrow_mut().insert(entry.clone(),RelationValue::Rows(Arc::new(super::join::one_part(local))));
            saved.push((entry,old));
        }
        let result=driver.bodies().bound_relation(&view.form,&view.clause,example,&bound);
        for (entry,old) in saved {let mut held=driver.values.borrow_mut();match old {Some(old)=>{held.insert(entry,old);},None=>{held.remove(&entry);}}}
        match result? {
            RelationValue::Rows(found)=>{
                if let Err(stop)=super::join::charge_walk(evaluation,&found,&view.form) {return Ok(RelationValue::Stopped(stop));}
                super::join::each_row(&found,&mut |row|{rows.insert(row.into());});
            }
            other=>return Ok(other),
        }
    }
    Ok(RelationValue::Rows(Arc::new(super::join::one_part(rows))))
}

/// A declared recursive input has its own typed relation on the shared
/// node. Ordinary inputs run once; recursive inputs use the model's states.
pub(super) fn input_value(driver:&Driver<'_, '_>,relation:&GraphRelation,port:&PortName,example:Option<Example>)->Outcome<RelationValue> {
    let evaluation=driver.evaluation;
    let form=evaluation.program.program.form_of(relation.node);
    let fault=|message:String|RunFault {message:message.into(),form:form.clone()};
    let Some(NodeRef::Instance(instance))=node_at(NodeRef::Program(evaluation.program.program.program.value()),form) else {return Err(fault("recursive input owner is not an instance".into()))};
    let component=registry_columns::component(evaluation.registry,&instance.component).ok_or_else(||fault("recursive component is absent".into()))?;
    let declared=component.inputs.iter().find(|i|i.port.name==*port).ok_or_else(||fault(format!("recursive instance declares no relation port {}",port.0)))?;
    let shape=InstanceShape::of(evaluation.program,form,instance,component);
    let input=shape.input_clause(evaluation.program,form,declared).map_err(fault)?.ok_or_else(||fault("recursive input is not written".into()))?;
    // A broadcast input's clause holds no key columns, and its port does.
    let key=if !input.keyed()&&shape.key_width()>0 {
        match key_relation(evaluation,&driver.bodies(),form,&shape.key_body,&shape.key_labels(),example)? {Ok(key)=>key,Err(value)=>return Ok(value)}
    } else {None};
    let scope=super::examples::scope_of(evaluation.program,relation);
    let view=BodyView {union_expanded:false,form:form.clone(),clause:(*input.clause).clone(),paths:(*input.paths).clone(),scope,input:Some(port.clone())};
    match value(driver,&view,example)? {
        RelationValue::Rows(rows)=>{
            if let Err(stop)=super::join::charge_walk(evaluation,&rows,form) {return Ok(RelationValue::Stopped(stop));}
            if let Some(key)=key {
                let count=key.len().saturating_mul(rows.len());
                let mut budget=super::join::Budget::new(evaluation.limits,evaluation.session);
                let width=usize::from(rows.arity()).saturating_add(shape.key_width());
                if let Err(bound)=budget.charge_rows_of(count,width).and_then(|()|budget.charge_work(0)) {return Ok(RelationValue::Stopped(super::Stop {bound,form:form.clone()}));}
                return Ok(RelationValue::Rows(Arc::new(super::join::one_part(input.broadcast_rows(shape.key_width(),&key_group_rows(Some(&key)),&rows)))));
            }
            Ok(RelationValue::Rows(Arc::new(super::join::one_part(input.expanded_rows(&rows)))))
        }
        other=>Ok(other),
    }
}
