/* The finalize lens: the items in a finalize pass, then every unfinalized
   solver on disk, in one of the lens orderings; a row peeks at the solver
   and its reports, and takes the ruling that ends it. */
import { html, useState, useEffect, useMemo, useCallback, useRef } from "/vendor/htm-preact-standalone.module.js";
import { useClocked } from "/ui/clock.js";
import { FINAL, SETTLED, cacheInfo } from "/ui/item.js";
import { PeekHead, PeekBody } from "/ui/panels/detail.js";
import { esc } from "/ui/prose.js";
import { ItemRow, BkRow, passLabel } from "/ui/rail.js";
import { snap as snapNow, tasks, peeks, post, ensureTask, ensureItem, ensurePeek } from "/ui/server.js";
import { useSession } from "/ui/session.js";

/* finalize lens orderings: the server's triage sort, a complexity measure, or
   the models that made the passes. One choice orders both sections; in the
   finalizing section it orders the cold sessions, behind the warm ones. */
const BK_ORDERS = {flag:"triage order",
                   passes:"grouped by the models of the passes, triage order within",
                   ts:"reference TS solver complexity",
                   dl:"solver rule-literal count"};
const BK_SHOWN = 40;   // unfinalized rows listed until the user asks for the rest
/* the chosen ordering over lens rows; the triage rank is the row's place in
   the server's list, and a task with no row goes last */
const triage = r => r.triage ?? Infinity;
const bkCmp = order => (a,b) => {
  if(order==="flag") return triage(a)-triage(b) || 0;
  if(order==="passes") return passLabel(a).localeCompare(passLabel(b)) || triage(a)-triage(b) || 0;
  const k=order+"_size", av=a[k]??-1, bv=b[k]??-1;
  return bv-av || (a.id<b.id?-1:1);
};
const sizeOf = (row, order) => ["flag","passes"].includes(order) ? null : (row[order+"_size"] ?? "—");

export const finalize = {
  id: FINAL,
  use({snap, selId, setSelId, pins, cli}){
    const items=snap.items;
    const [backlog,setBacklog]=useState([]);
    const [finRows,setFinRows]=useState({});   // id -> lens row of a finalize pass in flight
    const [bkAll,setBkAll]=useState(false);   // every unfinalized row, on the user's ask
    const [bkOrder,setBkOrderState]=useState(()=>{
      const v=localStorage.getItem("bkOrder");
      return BK_ORDERS[v] ? v : "flag";
    });
    const setBkOrder=useCallback(v=>{
      localStorage.setItem("bkOrder", v);
      setBkOrderState(v);
    },[]);

    const open=useRef(true);
    useEffect(()=>()=>{ open.current=false; },[]);
    const fetchBacklog=useCallback(async()=>{
      try {
        const r=await fetch("/api/backlog");
        const d=await r.json();
        if(!open.current) return;
        const ranked = rows => (rows||[]).map((row,i)=>({...row, triage:i}));
        setBacklog(ranked(d.items));
        setFinRows(Object.fromEntries(ranked(d.finalizing).map(row=>[row.id,row])));
      } catch(e){}
    },[]);
    /* the scan stats every solver, so it is polled only while the lens is
       open, and slowly: flags and started passes refresh it on the spot */
    useEffect(()=>{
      fetchBacklog();
      const h=setInterval(fetchBacklog, 15000);
      return ()=>clearInterval(h);
    },[fetchBacklog]);
    /* a landing writes the ledger line the backlog reads */
    useEffect(()=>{ if(snap.seq) fetchBacklog(); },[snap.seq]);

    const railOrder=useClocked(()=>
      [...items].sort((a,b)=>cacheInfo(a).sort-cacheInfo(b).sort).map(it=>it.id),
      [items]);
    /* An approved or committed item is settled, so the lens gives its row
       back; the selected one stays, so a row does not vanish from under the
       detail pane while it is being read. A session with a cache to keep
       warm leads in cache order; the cold ones follow in the chosen
       ordering, over the rows the server sent for them. */
    const itemOrder=useClocked(()=>{
      const rows=railOrder.map(id=>items.find(x=>x.id===id)).filter(it=>
        it && it.phase===FINAL && (it.id===selId || !SETTLED.includes(it.state)));
      const cmp=bkCmp(bkOrder), rowOf=it=>finRows[it.id]||{id:it.id};
      return rows.filter(it=>cacheInfo(it).cls!=="cold")
        .concat(rows.filter(it=>cacheInfo(it).cls==="cold").sort((a,b)=>cmp(rowOf(a), rowOf(b))))
        .map(it=>it.id);
    }, [railOrder, items, selId, bkOrder, finRows]);
    /* the rows arrive in triage order; the other orderings resort them here */
    const bkSorted=useMemo(()=>[...backlog].sort(bkCmp(bkOrder)), [backlog, bkOrder]);
    const bkShown=useMemo(()=>bkAll ? bkSorted : bkSorted.slice(0, BK_SHOWN), [bkSorted, bkAll]);
    /* one selection over both sections: in-pass items, then the unfinalized rows
       on show. An id that is both a live item and a row resolves to the item. */
    const order=useMemo(()=>
      itemOrder.concat(bkShown.map(b=>b.id).filter(id=>!itemOrder.includes(id))),
      [itemOrder, bkShown]);

    const selItem = items.find(it=>it.id===selId) || null;
    const selBk = !selItem ? (backlog.find(b=>b.id===selId)||null) : null;
    const detailId = selItem ? selItem.id : selBk ? selBk.id : null;

    const select=useCallback(id=>{
      if(!id) return;
      setSelId(id);
      const it=snapNow().items.find(x=>x.id===id);
      ensureTask(id);
      if(it){
        ensureItem(id, true);
        if(it.updated) post("/api/seen",{id});
      } else {
        ensurePeek(id);
      }
    },[]);
    const session=useSession(selItem, {cli, reviewOrder:railOrder, select, pins, afterRule:fetchBacklog});
    const onApprove=useCallback(async id=>{
      if(!confirm("Approve "+id+"? The draft line comes off the solver file.")) return;
      await post("/api/approve-solver",{id});
      fetchBacklog();
    },[fetchBacklog]);

    /* the rows on screen want their thumbnails */
    useEffect(()=>{ for(const id of order) ensureTask(id); },[order]);

    /* ---- the peeked solver ---- */
    const peek = selBk ? peeks[selBk.id] : null;
    const peekPane = useMemo(()=>peek?esc(peek.solver):"", [peek]);
    let head=session.head, body=session.body, code=session.code;
    if(selBk){
      head = peek ? html`<${PeekHead} d=${peek} onDismiss=${session.dismiss} onApprove=${onApprove}/>` : null;
      body = peek ? html`<${PeekBody} key="peek" d=${peek}/>`
                  : html`<div id="judge-scroll" key="peek"></div>`;
      code = peek ? {jumpKey:"peek|"+peek.id, fname:"programs/solvers/"+peek.id+".dl",
                     lines:peek.solver.split("\n").length+" lines", buttons:null, pane:peekPane}
                  : null;
    }

    const tools=html`<span class="bktog">${Object.keys(BK_ORDERS).map(k=>html`<button key=${k}
      class=${bkOrder===k?"on":""} title=${BK_ORDERS[k]}
      onClick=${()=>setBkOrder(k)}>${k==="flag"?"flag ↑":k==="passes"?"passes":k+" ↓"}</button>`)}</span>`;
    const finRowsShown=itemOrder.map(id=>html`<${ItemRow} key=${id} it=${items.find(x=>x.id===id)}
      task=${tasks[id]} metric=${sizeOf(finRows[id]||{}, bkOrder)}
      sel=${!!selItem && id===selId} onSelect=${select}/>`);
    const bkRows=bkShown.map(b=>html`<${BkRow} key=${b.id} b=${b} task=${tasks[b.id]}
      metric=${sizeOf(b, bkOrder)}
      sel=${b.id===selId && !itemOrder.includes(b.id)} onSelect=${select}/>`);
    return {
      order,
      pick: id => id && (items.some(x=>x.id===id) || backlog.some(b=>b.id===id))
        ? id : (order[0] || railOrder[0] || null),
      settle: id => { ensureTask(id); if(items.some(x=>x.id===id)) ensureItem(id); else ensurePeek(id); },
      select,
      detailId,
      sections: [
        {key:"fin", head:"finalizing · "+itemOrder.length, tools, rows:finRowsShown, total:itemOrder.length},
        {key:"bk", head:"unfinalized · "+bkSorted.length, rows:bkRows,
         total:bkSorted.length, onMore:()=>setBkAll(true)},
      ],
      head, body, composer: session.composer, code,
      keys: session.keys,
    };
  },
};
