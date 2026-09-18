/* The page's place: the lens in view and the row selected in it. It lives
   in the URL, so the browser keeps the history and the back button returns
   the user to where they were.

   A move the user made pushes an entry. A move the page made for them — the
   selection settling on a row that exists, after the one they picked went —
   replaces the current entry, so back does not walk through fallbacks. */

export function readNav(){
  const q = new URLSearchParams(location.search);
  return {view: q.get("lens") || "", sel: q.get("sel") || null};
}

/* Moves closer together than this are one move: j/k held down walks the
   rail row by row, and each row is no place to come back to. The browsers
   also cap how often a page may push. */
const COALESCE = 700;   // ms
let lastPush = 0;

export function writeNav(nav, replace){
  const q = new URLSearchParams(location.search);
  if(nav.view) q.set("lens", nav.view); else q.delete("lens");
  if(nav.sel) q.set("sel", nav.sel); else q.delete("sel");
  const s = q.toString();
  const now = Date.now();
  const push = !replace && now-lastPush > COALESCE;
  if(push) lastPush = now;
  history[push?"pushState":"replaceState"](nav, "", location.pathname+(s?"?"+s:""));
}

/* An entry from an earlier page load carries no state of ours, so the URL
   stands in for it. */
export function onPop(cb){
  const h = e => cb(e.state && e.state.view ? e.state : readNav());
  addEventListener("popstate", h);
  return ()=>removeEventListener("popstate", h);
}
