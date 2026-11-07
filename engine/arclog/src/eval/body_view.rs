//! Checked body views preserve lexical types, keys, aliases and source paths.
//! They are evaluation queries over the original program, never new public
//! clauses to be resolved or checked under a different language contract.
use super::examples::ExampleScope;
use super::ir::{self, Argument, AtomSource, ClauseIr, IrNode, IrPaths, KeyRead, NodePaths, Variable};
use super::{Outcome, RunFault};
use crate::check::CheckedProgram;
use crate::program::path::{node_at,NodePath,NodeRef};
use crate::program::{ChoosePart,Conjunct,LabelId,RigidDetPart};
use crate::resolver::Side;

const MAX_DERIVATIONS:usize=32;

#[derive(Clone)]
pub struct BodyView {
    pub union_expanded: bool,
    pub form:NodePath,
    pub clause:ClauseIr,
    pub paths:IrPaths,
    pub scope:ExampleScope,
    pub input:Option<crate::program::PortName>,
}
impl BodyView {
    /// Whether this query reads the recursive owner's state in addition to its
    /// literal clause. Both evaluation and completed-model reuse use this
    /// boundary; unknown inputs retain the native evaluation fault.
    pub fn uses_owner_context(&self, program:&CheckedProgram, registry:&crate::registry::Registry)->Outcome<bool> {
        let fault=|message:&str| RunFault {message:message.into(),form:self.form.clone()};
        let Some(port)=&self.input else {return Ok(false)};
        let Some(NodeRef::Instance(instance))=node_at(NodeRef::Program(program.program.program.value()),&self.form) else {
            return Err(fault("input query owner is not an instance"));
        };
        let component=crate::resolver::registry_columns::component(registry,&instance.component)
            .ok_or_else(||fault("body component is absent"))?;
        let declared=component.inputs.iter().find(|input|input.port.name==*port)
            .ok_or_else(||fault("body input is absent"))?;
        Ok(declared.reads_outputs)
    }
    pub fn column_of(&self,label:LabelId)->Option<usize> {
        self.clause.columns.iter().position(|v|self.paths.labels[v.0 as usize]==label)
    }
    /// Whether the INIT input at `input` declares a key column in its port. A port with none
    /// does not carry the key in its rows.
    fn port_has_key_column(program:&CheckedProgram,input:&NodePath,component:&crate::registry::LibName)->bool {
        let Some(NodeRef::InstanceInput(input))=node_at(NodeRef::Program(program.program.program.value()),input) else {return false};
        crate::resolver::registry_columns::component(crate::registry::Registry::get(),component)
            .and_then(|component|component.inputs.iter().find(|declared|declared.port.name==input.name))
            .is_some_and(|declared|declared.port.columns.iter().any(crate::registry::is_key))
    }

    /// Compile the exact body in its original checked form and key context.
    pub fn at(program:&CheckedProgram,at:&NodePath)->Outcome<Self> {
        Self::at_with(program,at,false)
    }

    /// The body as `at` compiles it, and for an INIT input outside the key
    /// whose port has a key column, joined to the key relation: the input's
    /// rows hold at every key group, so its complete tuple has the key columns.
    /// Every other body is as `at`.
    pub fn keyed_at(program:&CheckedProgram,at:&NodePath)->Outcome<Self> {
        Self::at_with(program,at,true)
    }

    fn at_with(program:&CheckedProgram,at:&NodePath,broadcast_key:bool)->Outcome<Self> {
        let root=NodeRef::Program(program.program.program.value());
        // A branch's lexical bindings include the outer body's prefix.
        // Use the same query for a whole branch and its completed prefix.
        let nested=(1..at.0.len()).any(|end|matches!(node_at(root,&NodePath(at.0[..end].into())),Some(NodeRef::Body(_))));
        let prefix=if nested {
            match node_at(root,at) {Some(NodeRef::Body(body))=>Some(body.conjuncts.len()),_=>None}
        } else {None};
        Self::compile_at(program,at,false,prefix,broadcast_key)
    }

    /// Query the full physical rows derived by an input. A broadcast input
    /// contributes its body rows at every native key group, just as
    /// init_form::grouped does. Keep the key projected so key-local witnesses
    /// do not multiply the input's derivations. Source BODY queries use at.
    pub fn derivation_at(program:&CheckedProgram,at:&NodePath)->Outcome<Self> {
        Self::compile_at(program,at,true,None,false)
    }

    /// A completed-conjunct prefix in the original checked scope. An OR
    /// branch includes the conjuncts preceding that OR in its outer bodies;
    /// sibling branches are never unioned into the observation. INIT inputs
    /// retain their projected key relation and recursive owner context.
    /// Partially written sites are not accepted by this query.
    pub fn prefix_at(program:&CheckedProgram,at:&NodePath,conjuncts:usize)->Outcome<Self> {
        Self::compile_at(program,at,false,Some(conjuncts),false)
    }

    fn compile_at(program:&CheckedProgram,at:&NodePath,physical_input:bool,prefix:Option<usize>,broadcast_key:bool)->Outcome<Self> {
        let fault=|message:String|RunFault {message:message.into(),form:at.clone()};
        let top=at.0.first().ok_or_else(||fault("body path has no form".into()))?.0;
        let form=NodePath::top(top);
        let root=NodeRef::Program(program.program.program.value());
        let Some(NodeRef::Body(body))=node_at(root,at) else {return Err(fault("path is not a body".into()))};
        let input=if prefix.is_some() {
            (1..at.0.len()).rev().find_map(|end|match node_at(root,&NodePath(at.0[..end].into())) {
                Some(NodeRef::InstanceInput(input))=>Some(input.name.clone()),_=>None,
            })
        } else {
            let parent=NodePath(at.0[..at.0.len()-1].into());
            match node_at(root,&parent) {Some(NodeRef::InstanceInput(input))=>Some(input.name.clone()),_=>None}
        };
        let selected=prefix.map(|count| {
            if count>body.conjuncts.len() {return Err(fault("prefix exceeds the BODY conjunct count".into()))}
            Ok(crate::program::Body {conjuncts:body.conjuncts[..count].into()})
        }).transpose()?;
        let body=selected.as_ref().unwrap_or(body);
        // The innermost form that holds the body: a form of a `DEMO_RULE`
        // stands in the label scope of its rule, not in the top-level one.
        let (inner,owner)=(1..at.0.len()).rev().find_map(|end| {
            let path=NodePath(at.0[..end].into());
            match node_at(root,&path)? {
                node@(NodeRef::Clause(_)|NodeRef::Instance(_)|NodeRef::Choose(_)|NodeRef::RigidDet(_)|NodeRef::Out(_)|NodeRef::Demonstrated(_))=>Some((path,node)),
                _=>None,
            }
        }).ok_or_else(||fault("body has no form".into()))?;
        let relative=NodePath(at.0[inner.0.len()..].into());
        let mut bodies=Vec::new();
        let mut key=None;
        match owner {
            NodeRef::Instance(instance)=>{
                if let Some(held)=&instance.key {
                    // The key clause is the instance's first child; an input after it is outside the key.
                    if (physical_input && input.is_some()) || (relative.0.len()>2 && relative.0[0].0==0 && relative.0[1].0>0)
                        || (broadcast_key && relative.0[0].0>0 && Self::port_has_key_column(program,&inner.child(relative.0[0].0),&instance.component)) {
                        let key_at=inner.child(0).child(0);
                        let labels=crate::read::columns::key_labels(&held.value().key.body.value());
                        let (clause,paths,_)=super::init_form::key_clause_memo(program,&inner,&(held.value().key.body.value(),key_at),&labels).map_err(|e|fault(format!("checked key body compile: {e:?}")))?;
                        key=Some((KeyRead {form:inner.clone(),clause:(*clause).clone()},(*paths).clone(),labels));
                    }
                }
            }
            NodeRef::Choose(choose)=>{
                let part=choose.parts().nth(relative.0[0].0 as usize).ok_or_else(||fault("CHOOSE body part is absent".into()))?;
                if matches!(part,ChoosePart::From) && choose.from_inside_for || matches!(part,ChoosePart::Never(_)) {
                    if let Some(rows)=&choose.rows {bodies.push((rows.body.value(),inner.child(0)));}
                }
                if matches!(part,ChoosePart::Never(_)) {bodies.push((choose.from.value(),inner.child(if choose.rows.is_some(){1}else{0})));}
            }
            NodeRef::RigidDet(rigid)=>{
                if rigid.instance.is_some() && relative.0[0].0==rigid.position(RigidDetPart::Instance) {
                    if let Some(key)=&rigid.key {bodies.push((key.body.value(),inner.child(rigid.position(RigidDetPart::Key))));}
                }
            }
            _=>{}
        }
        if prefix.is_some() {
            // Walk native paths, retaining only preceding outer conjuncts.
            // Crossing IF/ALL/NOT needs its own conditional query contract.
            for end in 1..at.0.len() {
                let parent=NodePath(at.0[..end].into());
                if let Some(NodeRef::Body(outer))=node_at(root,&parent) {
                    let index=at.0[end].0 as usize;
                    let nested=outer.conjuncts.get(index);
                    if !matches!(nested,Some(Conjunct::Or(_))) {
                        return Err(fault("prefix traversal supports OR branches; IF/ALL/NOT contexts are unavailable".into()));
                    }
                    // Keep the original body and native node paths; the
                    // selected range is applied at the shared compile boundary.
                    bodies.push((outer,parent));
                }
            }
        }
        bodies.push((body,at.clone()));
        let mut columns=Vec::new();
        if let Some((_,_,labels))=&key {columns.extend(labels.iter().copied());}
        let conjuncts=bodies.iter().flat_map(|(body,path)| {
            let count=if prefix.is_some() && path!=at && at.0.starts_with(&path.0) {
                at.0[path.0.len()].0 as usize
            } else {body.conjuncts.len()};
            body.conjuncts[..count].iter().enumerate().map(|(i,c)|(c,path.child(i as u32)))
        }).collect::<Vec<_>>();
        if prefix.is_some() {
            for (conjunct,_) in &conjuncts {
                let mut add=|label| {if !columns.contains(&label) {columns.push(label);}};
                match conjunct {
                    // A selected branch can join labels whose first spelling
                    // was in another branch. The checked scalar sites already
                    // identify those labels; freshness is not their identity.
                    Conjunct::Atom(_) | Conjunct::Constraint(_)=>
                        crate::safety::site_label_uses(conjunct,&mut |use_| {
                            if let Some(label)=crate::types::use_label(use_) {add(label);}
                        }),
                    // Keep the language's exported interface for an intact OR
                    // or IF. Its private orientation labels must not become
                    // query outputs through their finite native domains.
                    _=>for label in crate::read::columns::made_labels(&crate::program::Body {conjuncts:vec![(*conjunct).clone()].into()}) {add(label)},
                }
            }
        } else {
            for (body,_) in &bodies {for label in crate::read::columns::made_labels(body) {if !columns.contains(&label) {columns.push(label);}}}
        }
        // A label mentioned in each branch need not be bound by each branch.
        let given = key.as_ref().map(|(_,_,labels)|labels.iter().copied().collect()).unwrap_or_default();
        let outside = columns.iter().copied().collect();
        let types = ir::label_types(program,&inner);
        let bound = crate::safety::bound_labels(&conjuncts.iter().map(|(c,_)|*c).collect::<Vec<_>>(),&given,&outside,
            &|atom|ir::atom_modes(crate::registry::Registry::get(),atom),
            &|label|types.label(label).cloned());
        columns.retain(|label|bound.contains(label));
        if physical_input && prefix.is_none() && input.is_none() {
            let native = match node_at(root, &inner) {
                Some(node @ NodeRef::Clause(_)) => Some(ir::relation_columns(&program.program, &inner, node)),
                _ => None,
            };
            if let Some(native) = native {
                columns.sort_by_key(|label| native.iter().position(|at| at == label).unwrap_or(usize::MAX));
            }
        }
        let (clause,paths)=ir::compile_query(program,&inner,key.as_ref().map(|(read,paths,labels)|(read.clone(),paths.clone(),labels.as_slice())),conjuncts,&columns)
            .map_err(|e|fault(format!("checked body compile: {e:?}")))?;
        let scope=match program.program.form_side(&form) {
            Some(Side::PerInput)=>ExampleScope::PerExample,
            Some(Side::TaskWide)=>ExampleScope::TaskWide,
            None=>return Err(fault("body owner has no checked evaluation scope".into())),
        };
        Ok(Self {union_expanded:false,form,clause,paths,scope,input})
    }

    /// The body of each `&prediction` clause of the `DEMONSTRATED` form at
    /// `form`, with the labels it makes as its columns, and the label in it
    /// of each column of the form's relation, as
    /// `super::demonstrated::prediction_labels` gives them. A body takes the
    /// types of its rule's label scope and the examples of the form.
    pub fn predictions(program:&CheckedProgram,form:&NodePath)->Outcome<Vec<(Self,Vec<Option<LabelId>>)>> {
        let fault=|message:String|RunFault {message:message.into(),form:form.clone()};
        let root=NodeRef::Program(program.program.program.value());
        let Some(NodeRef::Demonstrated(demonstrated))=node_at(root,form) else {return Err(fault("prediction owner is not DEMONSTRATED".into()))};
        let scope=match program.program.form_side(form) {
            Some(Side::PerInput)=>ExampleScope::PerExample,
            Some(Side::TaskWide)=>ExampleScope::TaskWide,
            None=>return Err(fault("DEMONSTRATED owner has no checked evaluation scope".into())),
        };
        let found=super::demonstrated::prediction_labels(demonstrated,form).map_err(fault)?;
        found.into_iter().map(|(clause,labels)| {
            let Some(NodeRef::Clause(written))=node_at(root,&clause) else {return Err(fault("a prediction path is not a clause".into()))};
            let body=written.body.value();
            let at=clause.child(0);
            let conjuncts=body.conjuncts.iter().zip(0u32..).map(|(conjunct,index)|(conjunct,at.child(index))).collect();
            let columns=crate::read::columns::made_labels(body);
            let (compiled,paths)=ir::compile_query(program,&clause,None,conjuncts,&columns)
                .map_err(|e|fault(format!("checked prediction compile: {e:?}")))?;
            Ok((Self {union_expanded:false,form:form.clone(),clause:compiled,paths,scope,input:None},labels))
        }).collect()
    }

    /// The checked option relation that a CHOOSE selects rows from: its
    /// for rows with their from candidates. Never constraints and picking
    /// select a subset; they do not create the selected cells' frames.
    pub fn choose_options(program:&CheckedProgram,form:&NodePath)->Outcome<Self> {
        let fault=|message:String|RunFault {message:message.into(),form:form.clone()};
        let root=NodeRef::Program(program.program.program.value());
        let Some(NodeRef::Choose(choose))=node_at(root,form) else {
            return Err(fault("choice derivation owner is not CHOOSE".into()));
        };
        let mut bodies=Vec::new();
        if let Some(rows)=&choose.rows {bodies.push((rows.body.value(),form.child(choose.position(ChoosePart::For))));}
        bodies.push((choose.from.value(),form.child(choose.position(ChoosePart::From))));
        let columns=ir::relation_columns(&program.program,form,NodeRef::Choose(choose));
        let (clause,paths)=ir::compile_instance_pathed(program,form,&bodies,&columns)
            .map_err(|e|fault(format!("checked CHOOSE option compile: {e:?}")))?;
        let scope=match program.program.form_side(form) {
            Some(Side::PerInput)=>ExampleScope::PerExample,
            Some(Side::TaskWide)=>ExampleScope::TaskWide,
            None=>return Err(fault("CHOOSE owner has no checked evaluation scope".into())),
        };
        Ok(Self {union_expanded:false,form:form.clone(),clause,paths,scope,input:None})
    }

    /// The compiled native key queries read by this body. They retain their
    /// own projection and scope; deriving key-local evidence separately avoids
    /// joining every key witness with every input witness.
    pub fn key_views(&self)->Vec<Self> {
        self.clause.nodes.iter().zip(self.paths.nodes.iter()).filter_map(|(node,paths)| {
            let (IrNode::Atom(atom),NodePaths::Key(paths))=(node,paths) else {return None};
            let AtomSource::Key(key)=&atom.source else {return None};
            Some(Self {union_expanded:false,form:self.form.clone(),clause:key.clause.clone(),paths:(**paths).clone(),scope:self.scope,input:None})
        }).collect()
    }

    /// Derivation queries retain native projected KeyRead nodes. Key-local
    /// frame evidence is queried separately with key_views, never multiplied
    /// into the input query's witness domain.
    /// Choose union alternatives in already typed IR,
    /// expose their positive locals, and keep all original result columns.
    /// Native equality nodes bind aliases without public AST normalization.
    pub fn widened(&self)->Outcome<Vec<Self>> {
        fn expand(mut clause:ClauseIr,paths:IrPaths,out:&mut Vec<(ClauseIr,IrPaths,bool)>, expanded:bool)->bool {
            if out.len()>=MAX_DERIVATIONS {return false;}
            for i in 0..clause.nodes.len() {
                if let (IrNode::Or(union),NodePaths::Branches(branch_paths))=(&clause.nodes[i],&paths.nodes[i]) {
                    for (branch,branch_paths) in union.branches.iter().zip(branch_paths.iter()) {
                        let next=clause.splice(i,branch);let mut at=paths.clone();
                        at.nodes=paths.nodes[..i].iter().chain(branch_paths.nodes.iter()).chain(paths.nodes[i+1..].iter()).cloned().collect();
                        if !expand(next,at,out,true) {return false;}
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
            clause.columns=columns.into();out.push((clause,paths,expanded));true
        }
        let mut out=Vec::new();
        if !expand(self.clause.clone(),self.paths.clone(),&mut out,self.union_expanded) {return Err(RunFault {message:format!("the checked body widens to more than {} derivations",MAX_DERIVATIONS).into(),form:self.form.clone()});}
        Ok(out.into_iter().map(|(clause,paths,expanded)|Self {union_expanded:expanded,form:self.form.clone(),clause,paths,scope:self.scope,input:self.input.clone()}).collect())
    }
}
