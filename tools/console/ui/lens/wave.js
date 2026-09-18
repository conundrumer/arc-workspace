/* The wave lens: the items whose stage landed without what it owes first,
   then every item by how recently it was worked on, cut to the first rows
   until the user asks for the rest. A review that has gone cold with
   nothing new on it is past the cut too, so the list holds the items the
   user can still steer warm; "show all" and the search reach the rest. */
import { html, useState, useEffect, useCallback } from "/vendor/htm-preact-standalone.module.js";
import { useClocked } from "/ui/clock.js";
import { cacheInfo, lastTurn } from "/ui/item.js";
import { ItemRow } from "/ui/rail.js";
import { snap as snapNow, tasks, post, ensureTask, ensureItem } from "/ui/server.js";
import { useSession } from "/ui/session.js";

const RAIL_SHOWN = 40;   // wave rows listed until the user asks for the rest

export const wave = {
  id: "wave",
  use({snap, selId, setSelId, pins, cli, filter}){
    const items=snap.items;
    const [railAll,setRailAll]=useState(false);   // every wave row, on the user's ask
    /* past the default cut: a review gone cold with nothing new on it. An
       owed item stays, as the user must bring its turn by hand. */
    const old = it => it.state==="needs-review" && !it.updated && !it.owes && cacheInfo(it).cls==="cold";

    /* a stage that landed without its report, callouts, or handoff leads,
       for the user to bring it by hand; then the most recently worked on
       first: a turn running now, then the latest landing, and an item whose
       phase has not landed yet last */
    const railOrder=useClocked(()=>
      [...items].sort((a,b)=>(b.owes?1:0)-(a.owes?1:0)
          || (b.active?1:0)-(a.active?1:0)
          || lastTurn(b)-lastTurn(a)
          || (a.id<b.id?-1:1))
        .map(it=>it.id),
      [items]);
    /* The selected one stays past the cut, so a row does not vanish from
       under the detail pane while it is being read. */
    const order=useClocked(()=>{
      if(filter) return railOrder.filter(id=>id.includes(filter));
      if(railAll) return railOrder;
      const byId=new Map(items.map(it=>[it.id, it]));
      const fresh=railOrder.filter(id=>byId.has(id) && !old(byId.get(id)));
      const shown=fresh.length<=RAIL_SHOWN ? fresh : fresh.slice(0, RAIL_SHOWN);
      return railOrder.includes(selId) && !shown.includes(selId) ? shown.concat([selId]) : shown;
    }, [railOrder, selId, railAll, filter, items]);

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
      /* before the first snapshot there is nothing to hold a selection
         against, so an id the page opened on is kept as it stands */
      pick: id => id && (!snap.seq || items.some(x=>x.id===id))
        ? id : (order[0] || railOrder[0] || null),
      settle: id => { ensureTask(id); ensureItem(id); },
      select,
      detailId: selItem ? selItem.id : null,
      sections: [{key:"wave", head:"owed first · cache ↑expiring", rows,
                  total:filter ? rows.length : railOrder.length, onMore:()=>setRailAll(true)}],
      mentions: session.mentions,
      head: session.head, body: session.body, composer: session.composer, code: session.code,
      keys: session.keys,
    };
  },
};
