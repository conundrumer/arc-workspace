/* The wave lens: the items whose stage landed without what it owes first,
   then every item in cache-expiry order, cut to the first rows until the
   user asks for the rest. */
import { html, useState, useEffect, useCallback } from "/vendor/htm-preact-standalone.module.js";
import { useClocked } from "/ui/clock.js";
import { cacheInfo } from "/ui/item.js";
import { ItemRow } from "/ui/rail.js";
import { snap as snapNow, tasks, post, ensureTask, ensureItem } from "/ui/server.js";
import { useSession } from "/ui/session.js";

const RAIL_SHOWN = 40;   // wave rows listed until the user asks for the rest

export const wave = {
  id: "wave",
  use({snap, selId, setSelId, pins, cli}){
    const items=snap.items;
    const [railAll,setRailAll]=useState(false);   // every wave row, on the user's ask

    /* a stage that landed without its report, callouts, or handoff leads,
       for the user to bring it by hand; then soonest-expiring cache first: a
       phase with no session yet, or a turn that never landed, leads with "—";
       running turns follow; cold ones close by state */
    const railOrder=useClocked(()=>
      [...items].sort((a,b)=>(b.owes?1:0)-(a.owes?1:0) || cacheInfo(a).sort-cacheInfo(b).sort)
        .map(it=>it.id),
      [items]);
    /* The selected one stays past the cut, so a row does not vanish from
       under the detail pane while it is being read. */
    const order=useClocked(()=>{
      if(railAll || railOrder.length<=RAIL_SHOWN) return railOrder;
      const shown=railOrder.slice(0, RAIL_SHOWN);
      return railOrder.includes(selId) && !shown.includes(selId) ? shown.concat([selId]) : shown;
    }, [railOrder, selId, railAll]);

    const selItem = items.find(it=>it.id===selId) || null;
    const select=useCallback(id=>{
      if(!id) return;
      setSelId(id);
      const it=snapNow().items.find(x=>x.id===id);
      ensureTask(id);
      if(it){
        ensureItem(id, true);
        if(it.updated) post("/api/seen",{id});
      }
    },[]);
    const session=useSession(selItem, {cli, reviewOrder:railOrder, select, pins});

    /* the rows on screen want their thumbnails */
    useEffect(()=>{ for(const id of order) ensureTask(id); },[order]);

    const rows=order.map(id=>html`<${ItemRow} key=${id} it=${items.find(x=>x.id===id)}
      task=${tasks[id]} metric=${null} sel=${id===selId} onSelect=${select}/>`);
    return {
      order,
      pick: id => id && items.some(x=>x.id===id) ? id : (order[0] || railOrder[0] || null),
      settle: id => { ensureTask(id); ensureItem(id); },
      select,
      detailId: selItem ? selItem.id : null,
      sections: [{key:"wave", head:"owed first · cache ↑expiring", rows,
                  total:railOrder.length, onMore:()=>setRailAll(true)}],
      head: session.head, body: session.body, composer: session.composer, code: session.code,
      keys: session.keys,
    };
  },
};
