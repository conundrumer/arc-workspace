//! Checked body views preserve lexical types, keys, aliases and source paths.
//! They are evaluation queries over the original program, never new public
//! clauses to be resolved or checked under a different language contract.
use super::examples::ExampleScope;
use super::ir::{self, Argument, AtomSource, ClauseIr, IrNode, IrPaths, KeyRead, NodePaths, Variable};
use super::{Outcome, RunFault};
use crate::check::CheckedProgram;
use crate::program::path::{node_at,NodePath,NodeRef};
use crate::program::{ChoosePart,Form,LabelId,RigidDetPart};
use crate::resolver::Side;

const MAX_DERIVATIONS:usize=32;

#[derive(Clone)]
pub struct BodyView {
    pub form:NodePath,
    pub clause:ClauseIr,
    pub paths:IrPaths,
    pub scope:ExampleScope,
    pub input:Option<crate::program::PortName>,
}
impl BodyView {
    pub fn column_of(&self,label:LabelId)->Option<usize> {
        self.clause.columns.iter().position(|v|self.paths.labels[v.0 as usize]==label)
    }
    /// Compile the exact body in its original checked form and key context.
    pub fn at(program:&CheckedProgram,at:&NodePath)->Outcome<Self> {
        let fault=|message:String|RunFault {message:message.into(),form:at.clone()};
        let top=at.0.first().ok_or_else(||fault("body path has no form".into()))?.0;
        let form=NodePath::top(top);
        let root=NodeRef::Program(program.program.program.value());
        let Some(NodeRef::Body(body))=node_at(root,at) else {return Err(fault("path is not a body".into()))};
        let owner=&program.program.program.value().forms[top as usize];
        let relative=NodePath(at.0[1..].into());
        let mut bodies=Vec::new();
        let mut key=None;
        match owner {
            Form::Instance(instance)=>{
                if let Some(held)=&instance.value().key {
                    if relative.0.len()>2 && relative.0[0].0==0 && relative.0[1].0>0 {
                        let key_at=form.child(0).child(0);
                        let labels=crate::read::columns::key_labels(&held.value().key.body.value());
                        let (clause,paths)=ir::compile_instance_pathed(program,&form,&[(held.value().key.body.value(),key_at)],&labels).map_err(|e|fault(format!("checked key body compile: {e:?}")))?;
                        key=Some((KeyRead {form:form.clone(),clause},paths,labels));
                    }
                }
            }
            Form::Choose(choose)=>{
                let choose=choose.value();
                let part=choose.parts().nth(relative.0[0].0 as usize).ok_or_else(||fault("CHOOSE body part is absent".into()))?;
                if matches!(part,ChoosePart::From) && choose.from_inside_for || matches!(part,ChoosePart::Never(_)) {
                    if let Some(rows)=&choose.rows {bodies.push((rows.body.value(),form.child(0)));}
                }
                if matches!(part,ChoosePart::Never(_)) {bodies.push((choose.from.value(),form.child(if choose.rows.is_some(){1}else{0})));}
            }
            Form::RigidDet(rigid)=>{
                if rigid.value().instance.is_some() && relative.0[0].0==rigid.value().position(RigidDetPart::Instance) {
                    if let Some(key)=&rigid.value().key {bodies.push((key.body.value(),form.child(rigid.value().position(RigidDetPart::Key))));}
                }
            }
            _=>{}
        }
        bodies.push((body,at.clone()));
        let mut columns=Vec::new();
        if let Some((_,_,labels))=&key {columns.extend(labels.iter().copied());}
        for (body,_) in &bodies {for label in crate::read::columns::made_labels(body) {if !columns.contains(&label) {columns.push(label);}}}
        // A label mentioned in each branch need not be bound by each branch.
        // Query columns are outer requirements, never branch-local witnesses.
        let conjuncts = bodies.iter().flat_map(|(body,_)|body.conjuncts.iter()).collect::<Vec<_>>();
        let given = key.as_ref().map(|(_,_,labels)|labels.iter().copied().collect()).unwrap_or_default();
        let outside = columns.iter().copied().collect();
        let types = ir::label_types(program,&form);
        let bound = crate::safety::bound_labels(&conjuncts,&given,&outside,
            &|atom|ir::atom_modes(crate::registry::Registry::get(),atom),
            &|label|types.label(label).cloned());
        columns.retain(|label|bound.contains(label));
        let (clause,paths)=if let Some((read,paths,labels))=key {
            ir::compile_keyed_body(program,&form,(read,paths,&labels),(body,at.clone()),&columns)
        } else {
            let conjuncts=bodies.iter().flat_map(|(body,path)|body.conjuncts.iter().enumerate().map(|(i,c)|(c,path.child(i as u32)))).collect();
            ir::compile_safe(program,&form,conjuncts,&columns)
        }.map_err(|e|fault(format!("checked body compile: {e:?}")))?;
        let scope=match program.program.form_side(&form) {
            Some(Side::PerInput)=>ExampleScope::PerExample,
            Some(Side::TaskWide)=>ExampleScope::TaskWide,
            None=>return Err(fault("body owner has no checked evaluation scope".into())),
        };
        let parent=NodePath(at.0[..at.0.len()-1].into());
        let input=match node_at(root,&parent) {Some(NodeRef::InstanceInput(input))=>Some(input.name.clone()),_=>None};
        Ok(Self {form,clause,paths,scope,input})
    }

    /// Derivation queries: choose union alternatives in already typed IR,
    /// expose their positive locals, and keep all original result columns.
    /// Native equality nodes bind aliases without public AST normalization.
    pub fn widened(&self)->Outcome<Vec<Self>> {
        fn expand(mut clause:ClauseIr,mut paths:IrPaths,out:&mut Vec<(ClauseIr,IrPaths)>)->bool {
            if out.len()>=MAX_DERIVATIONS {return false;}
            for i in 0..clause.nodes.len() {
                if let (IrNode::Atom(atom),NodePaths::Key(key_paths))=(&clause.nodes[i],&paths.nodes[i]) {
                    if let AtomSource::Key(read)=&atom.source {
                        // Both compiles use the same checked form's canonical
                        // variable scope. Keep the key's positive witnesses.
                        let nodes=clause.nodes[..i].iter().chain(read.clause.nodes.iter()).chain(clause.nodes[i+1..].iter()).cloned().collect();
                        let nodes_at=paths.nodes[..i].iter().chain(key_paths.nodes.iter()).chain(paths.nodes[i+1..].iter()).cloned().collect();
                        clause.nodes=nodes;paths.nodes=nodes_at;
                        return expand(clause,paths,out);
                    }
                }
                if let (IrNode::Or(union),NodePaths::Branches(branch_paths))=(&clause.nodes[i],&paths.nodes[i]) {
                    for (branch,branch_paths) in union.branches.iter().zip(branch_paths.iter()) {
                        let mut next=clause.clone();let mut at=paths.clone();
                        next.nodes=clause.nodes[..i].iter().chain(branch.nodes.iter()).chain(clause.nodes[i+1..].iter()).cloned().collect();
                        at.nodes=paths.nodes[..i].iter().chain(branch_paths.nodes.iter()).chain(paths.nodes[i+1..].iter()).cloned().collect();
                        if !expand(next,at,out) {return false;}
                    }
                    return true;
                }
            }
            let mut columns=clause.columns.to_vec();
            let mut add=|v:Variable|{if !columns.contains(&v) {columns.push(v);}};
            for node in clause.nodes.iter() {match node {
                IrNode::Atom(atom)=>for (_,a) in atom.arguments.0.iter() {if let Argument::Variable(v)=a {add(*v)}},
                IrNode::Lib(atom)=>for (_,a) in atom.arguments.0.iter() {if let Argument::Variable(v)=a {add(*v)}},
                IrNode::Comparison(c) if c.op==crate::program::ConstraintOp::Eq=>{add(c.first);if let ir::Operand::Variable(v)=c.second {add(v)}},
                _=>{}
            }}
            clause.columns=columns.into();out.push((clause,paths));true
        }
        let mut out=Vec::new();
        if !expand(self.clause.clone(),self.paths.clone(),&mut out) {return Err(RunFault {message:format!("the checked body widens to more than {} derivations",MAX_DERIVATIONS).into(),form:self.form.clone()});}
        Ok(out.into_iter().map(|(clause,paths)|Self {form:self.form.clone(),clause,paths,scope:self.scope,input:self.input.clone()}).collect())
    }
}
