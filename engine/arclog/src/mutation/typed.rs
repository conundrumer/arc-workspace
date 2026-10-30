//! Additional native interface proposals. All are certified by CompletionDomain.
use super::*;
use crate::resolver::DependencyKind;

pub(super) fn additions(program: &StudyProgram, at: &NodePath, registry: &Registry,
    stats: &mut DrawStats) -> Result<Vec<(Option<Conjunct>, &'static str)>, String> {
    let Some(NodeRef::Conjunct(old)) = node_at(NodeRef::Program(program.program().value()), at) else { return Ok(vec![]) };
    let Some(atom) = old.atom() else { return Ok(vec![]) };
    let Some(types) = scope_types(program, at) else { return Ok(vec![]) };
    let mut arguments = Vec::new();
    let native=program.typed_sites(registry)?;
    fn source_site(site:&Site,path:&NodePath,types:&FormTypes,
        native:&crate::check::render_sites::TypedSiteExport,out:&mut Vec<(LabelUse,ValueType)>) -> Result<(),String> {
        for (index,arg) in site.value.args.iter().enumerate() {
            let at=path.child(index as u32);
            match arg {
                SiteArg::Field(field)=>source_site(field,&at,types,native,out)?,
                SiteArg::Label(label)|SiteArg::NamedLabel{label,..}=> {
                    let ty=use_label(*label).and_then(|l|types.label(l)).cloned()
                        .or_else(||native.columns.get(&at).and_then(|s|s.ty.clone()))
                        .ok_or_else(||format!("typed source argument unavailable at {at:?}"))?;
                    out.push((*label,ty));
                }
            }
        }
        Ok(())
    }
    for (index,site) in atom.value().sites.iter().enumerate() {
        source_site(site,&at.child(index as u32),types,&native,&mut arguments)?;
    }
    let mut bound = available(program, at, registry).into_iter().collect::<Vec<_>>();
    bound.sort_by_key(|l| l.0);
    let mandatory = arguments.iter().enumerate().filter_map(|(i,(l,_))|
        matches!(l,LabelUse::Fresh(_) | LabelUse::Key(_)).then_some(i)).collect::<Vec<_>>();
    let mut out = Vec::new();
    // Equality can replace a functional orientation relation without depending
    // on a coincidentally equal library column spelling (perp A *A2 -> = *A2 A).
    for (left, ty) in &arguments {
        let Ok(first) = ConstraintLabel::try_from(*left) else {continue};
        for right in &bound {
            if use_label(*left)==Some(*right) || !types.label(*right).is_some_and(|r|r.meets(ty)) {continue}
            if !mandatory.iter().all(|i|arguments[*i].0==*left) {continue}
            out.push((Some(Conjunct::Constraint(Constraint {op:ConstraintOp::Eq, first,
                second:Operand::Label(ConstraintLabel{label:*right,fresh:false})})),"typed_equality"));
        }
        if ty.has_zero() && mandatory.iter().all(|i|arguments[*i].0==*left) {
            out.push((Some(Conjunct::Constraint(Constraint{op:ConstraintOp::Eq,first,second:Operand::Zero})),"typed_equality"));
        }
    }
    let mut catalog = Vec::new();
    let mut names = registry.names().collect::<Vec<_>>();names.sort_by(|a,b|a.0.cmp(&b.0));
    for name in names {
        if registry.algebra_relation(name).is_none() {continue}
        let relation=RelationRef::Lib(name.clone());
        let Some(columns)=typed_columns(registry,&relation) else {continue};
        if columns.iter().any(|c|c.ty.fixed().is_none()) {stats.count("typed_unavailable:nonfixed_library_interface");continue}
        catalog.push((relation,columns.iter().map(|c|TargetColumn{path:vec![c.name.clone()],ty:c.ty.fixed().unwrap().clone()}).collect::<Vec<_>>()));
    }
    // Canonical resolved relation inventory, including unused component ports.
    // Read eligibility is independent of whether an earlier atom used the port.
    let resolved=&program.checked().program;
    let target_nodes=resolved.nodes_of(&NodePath(at.0[..1].into()));
    for (graph, tys) in program.checked().types.relations() {
        let node=graph.node;
        if graph.output.is_some() {stats.count("typed_unavailable:compound_output_schema");continue}
        if resolved.graph.nodes[node.0 as usize].scope!=NameScope::Program {continue}
        let forms=resolved.forms_of(node);
        if forms.is_empty() || forms.iter().any(|p|p.0.first().is_none_or(|s|s.0>=at.0[0].0)) {continue}
        let reached=resolved.graph.reached(node);
        if target_nodes.iter().any(|n|reached[n.0 as usize]) {continue}
        let relation=match &resolved.graph.nodes[node.0 as usize].kind {
            DependencyKind::Clause(r)|DependencyKind::Parameter(r)=> match r {
                ProgramRelation::Declared(r)=>RelationRef::Declared(r.clone()),
                ProgramRelation::Output(r)=>RelationRef::Output(r.clone())},
            DependencyKind::Chosen(r)|DependencyKind::Demonstrated(r)=>RelationRef::Declared(r.clone()),
            DependencyKind::InstanceInput{instance,input}=>RelationRef::Output(OutputName{of:OutputOwner::Instance(instance.clone()),path:Arc::from([OutputStep::Port(input.clone())])}),
            DependencyKind::InstanceOutput{instance,output}=>RelationRef::Output(OutputName{of:OutputOwner::Instance(instance.clone()),path:Arc::from([OutputStep::Port(output.clone())])}),
            _=>continue,
        };
        // Use the resolver's declared physical paths and native inferred types.
        let Some(paths)=resolved.read_row_paths(node).or_else(||resolved.row_paths(node)) else {stats.count("typed_unavailable:program_schema");continue};
        if paths.len()!=tys.len() || paths.iter().any(|p|p.is_empty()) {stats.count("typed_unavailable:program_row_path_type_alignment");continue}
        let columns=paths.iter().zip(tys).map(|(p,t)|TargetColumn{path:p.to_vec(),ty:t.clone()}).collect();
        catalog.push((relation,columns));
    }
    for (relation, columns) in catalog {
        let mut walk=Mapping {arguments:&arguments,mandatory:&mandatory,bound:&bound,types,
            columns:&columns,relation:&relation,old,sites:vec![],used:vec![false;arguments.len()],
            results:vec![],visits:0,stopped:false};
        walk.visit(0);
        if walk.stopped {stats.count("domain_proposal_stopped:typed_mapping_budget");}
        out.extend(walk.results.into_iter().map(|c|(Some(c),"typed_interface")));
    }
    // Eliminate baseline primitives without recertifying them. The old run's
    // selected/rejected alternatives are never visited by this added-only draw.
    let baseline=alternatives(program,at,"substitute",registry,true)?.into_iter()
        .map(|(c,_)|c.map(|c|conjunct_json(&c)).unwrap_or(Value::Null).to_string()).collect::<BTreeSet<_>>();
    out.retain(|(c,_)|c.as_ref().is_some_and(|c|!baseline.contains(&conjunct_json(c).to_string()) && conjunct_json(c)!=conjunct_json(old)));
    Ok(out)
}

struct TargetColumn {path:Vec<ColumnName>,ty:ValueType}

fn add_site(sites:&mut Vec<Site>,path:&[ColumnName],label:LabelUse) {
    if path.len()==1 {sites.push(Site{column:path[0].clone(),value:SiteValue{args:Arc::from([SiteArg::Label(label)])}});return}
    let index=match sites.iter().position(|s|s.column==path[0]) {Some(i)=>i,None=> {sites.push(Site{column:path[0].clone(),value:SiteValue{args:Arc::from([])}});sites.len()-1}};
    let mut fields=sites[index].value.args.iter().filter_map(|a|match a {SiteArg::Field(s)=>Some(s.clone()),_=>None}).collect::<Vec<_>>();
    add_site(&mut fields,&path[1..],label);
    sites[index].value.args=fields.into_iter().map(SiteArg::Field).collect::<Vec<_>>().into();
}

struct Mapping<'a> {
    arguments:&'a [(LabelUse,ValueType)],mandatory:&'a [usize],bound:&'a [LabelId],types:&'a FormTypes,
    columns:&'a [TargetColumn],relation:&'a RelationRef,old:&'a Conjunct,
    sites:Vec<Site>,used:Vec<bool>,results:Vec<Conjunct>,visits:usize,stopped:bool,
}
impl Mapping<'_> {
    fn visit(&mut self,index:usize) {
        if self.results.len()>=8 || self.visits>=512 {self.stopped=true;return}
        self.visits+=1;
        if index==self.columns.len() {
            if !self.sites.is_empty() && self.mandatory.iter().all(|i|self.used[*i]) {
                self.results.push(with_atom(self.old,Atom{relation:self.relation.clone(),sites:self.sites.clone().into()}));
            }
            return
        }
        let column=&self.columns[index];let ty=&column.ty;
        let mut choices=Vec::new();
        for (i,(label,actual)) in self.arguments.iter().enumerate() {
            if !self.used[i] && actual.meets(ty) {choices.push((Some(i),*label));}
        }
        choices.sort_by_key(|(source,_)|source.is_none_or(|i|!self.mandatory.contains(&i)));
        for label in self.bound {
            if self.types.label(*label).is_some_and(|t|t.meets(ty)) {choices.push((None,LabelUse::Join(*label)));}
        }
        if ty.has_zero() {choices.push((None,LabelUse::Zero));}
        for (source,label) in choices {
            if let Some(i)=source {self.used[i]=true;}
            let previous=self.sites.clone();
            add_site(&mut self.sites,&column.path,label);
            self.visit(index+1);self.sites=previous;
            if let Some(i)=source {self.used[i]=false;}
            if self.stopped {return}
        }
        // Omitted unused relation columns are existential in the native grammar;
        // the ordinary checker decides each mode and frame, not this enumerator.
        self.visit(index+1);
    }
}
