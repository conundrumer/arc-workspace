//! Whole-block row selectors. Native scope/export/check rules remain authoritative.
use super::*;
use crate::hash::StableHashMap;

pub(super) fn is_block(c:&Conjunct)->bool {
    matches!(c,Conjunct::Or(_) | Conjunct::If{..} | Conjunct::All{..} | Conjunct::Not(Negated::Form(_)))
}
pub(super) fn is_site(program:&StudyProgram,point:&MutationPoint,at:&NodePath)->bool {
    at.0.len()==point.body.0.len()+1 && at.0.starts_with(&point.body.0)
        && matches!(node_at(NodeRef::Program(program.program().value()),at),Some(NodeRef::Conjunct(c)) if is_block(c))
}
fn body(cs:Vec<Conjunct>)->Node<Body> {Node::new(Body{conjuncts:cs.into()})}
fn together(a:&Node<Body>,b:&Node<Body>)->Node<Body> {
    body(a.value().conjuncts.iter().chain(b.value().conjuncts.iter()).cloned().collect())
}
fn negated(b:&Node<Body>)->Conjunct {
    Conjunct::Not(Negated::Form(Arc::new(Conjunct::Or(Arc::from([b.clone()])))))
}

/// Change label uses at their exact native AST sites, including constraints.
/// No names, ordinal pairing or independently inferred label scopes are used.
fn map_body(old:&Node<Body>,change:&mut dyn FnMut(LabelUse,bool)->LabelUse)->Node<Body> {
    map_body_with(old,change,true)
}
fn map_body_with(old:&Node<Body>,change:&mut dyn FnMut(LabelUse,bool)->LabelUse,positive:bool)->Node<Body> {
    body(old.value().conjuncts.iter().map(|c|map_conjunct(c,change,positive)).collect())
}
fn map_site(old:&Site,change:&mut dyn FnMut(LabelUse,bool)->LabelUse,positive:bool)->Site {
    Site{column:old.column.clone(),value:SiteValue{args:old.value.args.iter().map(|a|match a {
        SiteArg::Label(l)=>SiteArg::Label(change(*l,positive)),
        SiteArg::NamedLabel{name,label}=>SiteArg::NamedLabel{name:name.clone(),label:change(*label,positive)},
        SiteArg::Field(s)=>SiteArg::Field(map_site(s,change,positive)),
    }).collect::<Vec<_>>().into()}}
}
fn map_conjunct(old:&Conjunct,change:&mut dyn FnMut(LabelUse,bool)->LabelUse,positive:bool)->Conjunct {
    let atom=|a:&Node<Atom>,change:&mut dyn FnMut(LabelUse,bool)->LabelUse,positive|Node::new(Atom{
        relation:a.value().relation.clone(),sites:a.value().sites.iter().map(|s|map_site(s,change,positive)).collect::<Vec<_>>().into()});
    match old {
        Conjunct::Atom(a)=>Conjunct::Atom(atom(a,change,positive)),
        Conjunct::Not(Negated::Atom(a))=>Conjunct::Not(Negated::Atom(atom(a,change,false))),
        Conjunct::Constraint(c)=> {
            let mut c=*c;
            c.first=ConstraintLabel::try_from(change(c.first.into(),positive && c.op==ConstraintOp::Eq)).expect("constraint label kind preserved");
            if let Operand::Label(l)=c.second {c.second=Operand::Label(ConstraintLabel::try_from(change(l.into(),false)).expect("constraint label kind preserved"));}
            Conjunct::Constraint(c)
        },
        Conjunct::Not(Negated::Form(c))=>Conjunct::Not(Negated::Form(Arc::new(map_conjunct(c,change,false)))),
        Conjunct::Or(bs)=>Conjunct::Or(bs.iter().map(|b|body(b.value().conjuncts.iter().map(|c|map_conjunct(c,change,positive)).collect())).collect()),
        Conjunct::If{test,then,otherwise}=>Conjunct::If{test:map_body_with(test,change,positive),then:map_body_with(then,change,positive),otherwise:map_body_with(otherwise,change,positive)},
        Conjunct::All{domain,body:b}=>Conjunct::All{domain:map_body_with(domain,change,positive),body:map_body_with(b,change,positive)},
    }
}

/// A selected path must expose exactly the original block's native exports.
/// Two alpha-distinct copies preserve existential local variables: the native
/// OR export intersection keeps shared output IDs, not private branch IDs.
/// This is a syntactic projection constructor, never a second evaluator.
fn project(selected:&Node<Body>,exports:&[LabelId],outside:&StableHashSet<LabelId>,next:u32)->Result<Conjunct,String> {
    let made=crate::read::columns::made_labels(selected.value());
    let mut missing=exports.iter().copied().filter(|l|!made.contains(l)).collect::<StableHashSet<_>>();
    let first=map_body(selected,&mut |used,positive| {
        if let LabelUse::Join(id)=used {
            if positive && missing.remove(&id) {return LabelUse::Fresh(id)}
        }
        used
    });
    let mut locals=crate::safety::body_labels(first.value()).into_iter()
        .filter(|id|!exports.contains(id) && !outside.contains(id)).collect::<Vec<_>>();
    locals.sort_by_key(|id|id.0);
    let mut renamed=StableHashMap::default();
    for (index,id) in locals.into_iter().enumerate() {
        let fresh=next.checked_add(u32::try_from(index).map_err(|_|"too many private labels")?).ok_or("private label id overflow")?;
        renamed.insert(id,LabelId(fresh));
    }
    let second=map_body(&first,&mut |used,_| match used {
        LabelUse::Fresh(id) if exports.contains(&id)=>LabelUse::Join(id),
        LabelUse::Fresh(id)=>LabelUse::Fresh(*renamed.get(&id).unwrap_or(&id)),
        LabelUse::Join(id)=>LabelUse::Join(*renamed.get(&id).unwrap_or(&id)),
        LabelUse::Key(id)=>LabelUse::Key(*renamed.get(&id).unwrap_or(&id)),
        LabelUse::Zero=>LabelUse::Zero,
    });
    Ok(Conjunct::Or(Arc::from([first,second])))
}

pub(super) fn alternatives(program:&StudyProgram,at:&NodePath,registry:&Registry,stats:&mut DrawStats)
    ->Result<Vec<(Option<Conjunct>,&'static str)>,String> {
    let Some(NodeRef::Conjunct(old))=node_at(NodeRef::Program(program.program().value()),at) else{return Ok(vec![])};
    let exports=crate::read::columns::made_labels(&Body{conjuncts:Arc::from([old.clone()])});
    let outside=available(program,at,registry);
    let mut highest=0;
    let form=&program.program().value().forms[at.0[0].0 as usize];
    crate::safety::each_label_use_at(NodeRef::from(form),&NodePath::top(at.0[0].0),&mut |_,used| {
        if let Some(id)=use_label(used) {highest=highest.max(id.0);}
    });
    let next=highest.checked_add(1).ok_or("private label id overflow")?;
    let mut out=Vec::new();
    match old {
        Conjunct::Or(branches)=> {
            for (index,branch) in branches.iter().enumerate() {
                if index>=64 {stats.count("domain_proposal_stopped:block_branch_budget");break}
                out.push((Some(project(branch,&exports,&outside,next)?),"block_or_select"));
                if branches.len()>2 {
                    let kept=branches.iter().enumerate().filter(|(i,_)|*i!=index).map(|(_,b)|b.clone()).collect::<Vec<_>>();
                    out.push((Some(project(&body(vec![Conjunct::Or(kept.into())]),&exports,&outside,next)?),"block_or_omit"));
                }
            }
        },
        Conjunct::If{test,then,otherwise}=> {
            out.push((Some(project(&together(test,then),&exports,&outside,next)?),"block_if_then"));
            let mut else_path=vec![negated(test)];else_path.extend(otherwise.value().conjuncts.iter().cloned());
            out.push((Some(project(&body(else_path),&exports,&outside,next)?),"block_if_else"));
            out.push((Some(Conjunct::If{test:test.clone(),then:otherwise.clone(),otherwise:then.clone()}),"block_if_swap"));
            let union=body(vec![Conjunct::Or(Arc::from([together(test,then),otherwise.clone()]))]);
            out.push((Some(project(&union,&exports,&outside,next)?),"block_if_union"));
        },
        Conjunct::All{domain,body:b}=> {
            out.push((Some(Conjunct::Not(Negated::Form(Arc::new(old.clone())))),"block_all_complement"));
            let existential=project(&together(domain,b),&exports,&outside,next)?;
            out.push((Some(existential.clone()),"block_all_exists"));
            out.push((Some(Conjunct::Not(Negated::Form(Arc::new(existential)))),"block_all_none"));
            out.push((Some(Conjunct::All{domain:domain.clone(),body:body(vec![negated(b)])}),"block_all_negate_body"));
        },
        Conjunct::Not(Negated::Form(inner))=>out.push((Some((**inner).clone()),"block_not_remove")),
        _=>{},
    }
    out.retain(|(c,_)|c.as_ref().is_some_and(|c|conjunct_json(c)!=conjunct_json(old)));
    Ok(out)
}
