"""The ticket dashboard's page around its sections (`ticket_dashboard`):
its CSS, in one column with a light and a dark scheme, the sheet of a
ticket, and the script that asks the server for the search's hits and for a ticket's
sheet, shows in each set of tabs the tab the user last chose in it, keeps each
fold open or shut as the user left it, sends the Clear of Updates, and updates the page on an event of the stream while the page is shown; with
the routes that script requests."""

EVENTS = "/events"
"""The route of the Server-Sent Events stream."""

SEARCH_ROUTE = "/search"
"""The route of the search's hits."""

TICKET_ROUTE = "/ticket"
"""The route of a ticket's sheet."""

CLEAR_ROUTE = "/clear"
"""The route that takes the time of the newest event Updates showed, as
the body of a POST."""

QUEUED_TAB = "queueTab"
"""The key under which `localStorage` holds the session of the tab of
Queued the user last chose."""

FOLD = "fold:"
"""The prefix of the keys under which `localStorage` holds whether a fold
of the page is open; a key ends in the fold's section and place in it."""

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ops</title><style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1c1c1c;--mute:#6b6b6b;--line:#e3e3df;--acc:#2f6fdf;--warn:#b5462b;--ok:#2d7a4b;--now:#2f6fdf}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--card:#1e1e1e;--ink:#ececec;--mute:#9a9a9a;--line:#2e2e2e;--acc:#7aa7ff;--warn:#ff8a6b;--ok:#6fcf97;--now:#7aa7ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 -apple-system,system-ui,sans-serif}
main{max-width:560px;margin:0 auto;padding:0 16px 40px}
.strip{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.strip .r1{font-weight:600}
.ub{display:flex;align-items:center;gap:8px;margin-top:6px}.ul{width:38px;flex-shrink:0;font-size:12px;color:var(--mute)}
.uv{width:34px;text-align:right;font-size:12px;font-variant-numeric:tabular-nums}
.bar{flex:1;min-width:20px;height:6px;background:var(--line);border-radius:3px;position:relative}
.bar i.hot{background:var(--warn)}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--acc)}
.bar b{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:22px 0 8px}
.card,.alert{display:block;width:100%;text-align:left;font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 8px;overflow-wrap:anywhere}
.alert{border-color:var(--warn);color:var(--warn)}.ok{color:var(--ok);padding:4px 0}
.num{color:var(--mute);font-variant-numeric:tabular-nums}.sh{font-weight:600}.star{color:#d9a200;margin-right:4px}
.meta{color:var(--mute);font-size:13px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin-bottom:8px}
summary{cursor:pointer;font-weight:600}details .row{padding:6px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}
.row.tk,.card.tk{cursor:pointer}
.kv{display:flex;justify-content:space-between;gap:12px;padding:3px 0}.kv span:last-child{font-variant-numeric:tabular-nums;text-align:right}
.days{display:flex;gap:6px;align-items:flex-end;height:60px;margin-top:8px}.days div{flex:1;display:flex;gap:1px;align-items:flex-end;height:100%}
.days i{flex:1;background:var(--acc);border-radius:2px 2px 0 0}.days i.c{background:var(--ok)}
.dl{display:flex;gap:6px;font-size:10px;color:var(--mute)}.dl span{flex:1;text-align:center}
input{width:100%;font:inherit;font-size:16px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
#res{margin-top:8px}#res .card{padding:8px 12px}
.sheet{position:fixed;inset:auto 0 0 0;max-height:75vh;overflow:auto;background:var(--card);border-top:1px solid var(--line);border-radius:14px 14px 0 0;padding:16px;box-shadow:0 -8px 30px rgba(0,0,0,.2);transform:translateY(100%);transition:transform .2s;z-index:5;visibility:hidden;overflow-wrap:anywhere}
.sheet.on{transform:none;visibility:visible}.sheet .p{font-weight:600;margin:6px 0 10px}.sheet .lg{font-size:13px;color:var(--mute);border-top:1px solid var(--line);padding:6px 0}.lg .more{color:var(--acc);font-style:normal;cursor:pointer}
.x{float:right;border:0;background:none;font-size:20px;color:var(--mute)}
.wl{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:10px}
.wr{display:grid;grid-template-columns:auto 1fr auto;gap:0 8px;align-items:baseline;padding:4px 12px 8px 9px;border-top:1px solid var(--line);border-left:3px solid transparent;cursor:pointer}
.wr:first-child{border-top:0}.wr.me{border-left-color:var(--acc)}
.wn{color:var(--mute);font-variant-numeric:tabular-nums;font-size:13px}.wn small{display:block;font-size:11px;opacity:.75}
.members{margin-top:4px;grid-column:1/-1;display:flex;flex-direction:column;gap:6px;min-width:0}.related{white-space:normal;overflow-wrap:anywhere;font-size:13px}.wp{min-width:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.members details a{display:block;margin-top:6px}.wl .members summary{padding:0;border:0}
.ws{color:var(--mute);font-size:13px;white-space:nowrap;text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:4px}
@media (max-width:540px){.wr{grid-template-columns:auto minmax(0,1fr)}.wr .ws{grid-column:1/-1;white-space:normal;text-align:left;align-items:flex-start;overflow-wrap:anywhere;min-width:0}}
.ws a{color:var(--acc);text-decoration:none}
.wt{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) 18ch;align-items:center;gap:8px;min-width:0;color:var(--mute);font-size:13px;line-height:13px;margin-bottom:-1px}
.wt>span:not(.mb){grid-column:2;min-width:0;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wt a{color:var(--acc);text-decoration:none}
.mb{display:flex;gap:2px;min-width:0}.mb b,.mb i{flex:1 1 0;min-width:0}.mb i{display:flex;gap:2px}.mb b{height:4px;border-radius:2px;background:var(--line)}
.mb b.d{background:var(--mute);opacity:.55}.mb b.n{background:var(--now)}.mb b.x{background:none;box-shadow:inset 0 0 0 1.5px #d9a200}
.tabs{display:flex;gap:6px;overflow-x:auto;margin:0 0 10px;padding-bottom:2px}
.tab{flex:0 0 auto;font:inherit;font-size:13px;padding:6px 10px;border-radius:16px;border:1px solid var(--line);background:var(--card);color:var(--ink);white-space:nowrap}
.tab.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}.tab small{opacity:.7}
.pane{display:none}.pane.on{display:block}
.sh2{font-size:13px;color:var(--mute);margin:0 0 8px}
.gh{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin:12px 0 6px}
.wl details{border:0;border-radius:0;margin:0;padding:0;background:none}
.wl summary{padding:6px 12px;border-top:1px solid var(--line);color:var(--mute);font-weight:400;font-size:13px}
details.grp{background:none;border:0;padding:0;margin:0}
details.grp>summary{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin:12px 0 6px;font-weight:400}
.wn i{font-style:normal}.wn .m{color:var(--ok)}.wn .x{color:var(--mute)}.wn .b{color:var(--warn)}
.w{color:var(--warn);font-weight:600}.scrim{position:fixed;inset:0;background:rgba(0,0,0,.3);display:none;z-index:4}.scrim.on{display:block}
</style></head><body>
<div id="live">@BODY@</div>
<div class="scrim" id="scrim"></div><div class="sheet" id="sheet"><button class="x" id="x">&times;</button><div id="sc"></div></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const sheet=$('sheet'),scrim=$('scrim'),sc=$('sc');let shown=null;
async function open(n){shown=n;sc.innerHTML='<div class="meta">Loading '+esc(n)+'</div>';sheet.classList.add('on');scrim.classList.add('on');
let h;try{const r=await fetch('@TICKET@?n='+encodeURIComponent(n),{cache:'no-store'});h=await r.text();if(!r.ok)h='<div class="meta">'+esc(r.status+' '+h)+'</div>'}
catch(e){h='<div class="meta">'+esc('load failed: '+e)+'</div>'}
if(shown===n)sc.innerHTML=h}
function shut(){shown=null;sheet.classList.remove('on');scrim.classList.remove('on')}
scrim.onclick=shut;$('x').onclick=shut;
function tab(){document.querySelectorAll('.tset').forEach(set=>{let k=null;try{k=localStorage.getItem(set.dataset.key)}catch(e){}
const tabs=set.querySelectorAll('.tab');if(!tabs.length)return;
if(!k||!set.querySelector('.tab[data-s="'+k+'"]'))k=tabs[0].dataset.s;
tabs.forEach(t=>t.classList.toggle('on',t.dataset.s===k));
set.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.dataset.s===k))})}
function fkey(d){return d.dataset.k||d.dataset.fk}
function folds(){let sec='top',seen={};document.querySelectorAll('#live h2,#live details').forEach(el=>{
if(el.tagName==='H2'){sec=el.id;return}
if(!el.dataset.k){const p=el.closest('.pane'),sm=[...el.children].find(c=>c.tagName==='SUMMARY');
let k=sec+':'+(p?p.dataset.s:'')+':'+((sm?sm.textContent:'').match(/[A-Za-z][A-Za-z' ]*/)||[''])[0].trim();
seen[k]=(seen[k]||0)+1;el.dataset.fk=seen[k]>1?k+'#'+seen[k]:k}
let s=null;try{s=localStorage.getItem('@FOLD@'+fkey(el))}catch(e){}
if(s==='1'||s==='0')el.open=s==='1';else if(el.dataset.k==='since')el.open=false;
if(el.dataset.k){sec=el.dataset.k}})}
function fold(d){setTimeout(()=>{try{localStorage.setItem('@FOLD@'+fkey(d),d.open?'1':'0')}catch(e){}},0)}
document.addEventListener('click',e=>{const sm=e.target.closest('#live summary');if(sm&&sm.parentElement.tagName==='DETAILS')fold(sm.parentElement);const cl=e.target.closest('#clear');if(cl){clear(cl.dataset.t);return}const b=e.target.closest('.tab');if(b){try{localStorage.setItem(b.closest('.tset').dataset.key,b.dataset.s)}catch(x){}tab();return}const g=e.target.closest('.lg'),m=g&&g.querySelector('.more');if(m){const s=g.querySelectorAll('span');s.forEach(x=>x.hidden=!x.hidden);m.textContent=s[1].hidden?'more':'less';return}if(e.target.closest('.members summary'))return;const t=e.target.closest('.tk');if(t){e.preventDefault();open(t.dataset.n)}});
async function clear(t){$('since').innerHTML='<div class="meta">Nothing new.</div>';$('sl').textContent='Updates';
let ok=false;try{ok=(await fetch('@CLEAR@',{method:'POST',body:t})).ok}catch(e){}
if(!ok)update()}
let asked=0,timer=null;
async function search(){const q=$('q').value.trim(),n=++asked,res=$('res');if(!q){res.innerHTML='';return}
let h;try{const r=await fetch('@SEARCH@?q='+encodeURIComponent(q),{cache:'no-store'});h=await r.text();if(!r.ok)h='<div class="meta">'+esc('search failed: '+r.status)+'</div>'}
catch(e){h='<div class="meta">'+esc('search failed: '+e)+'</div>'}
if(n===asked)res.innerHTML=h}
document.addEventListener('input',e=>{if(e.target.id==='q'){clearTimeout(timer);timer=setTimeout(search,250)}});
tab();folds();
let busy=false,again=false;
async function update(){if(busy){again=true;return}busy=true;
try{const r=await fetch('/',{cache:'no-store'});if(r.ok){const d=new DOMParser().parseFromString(await r.text(),'text/html');
const q=$('q')?.value,x=window.scrollX,y=window.scrollY;
$('live').replaceWith(d.getElementById('live'));
if(q!==undefined&&$('q'))$('q').value=q;tab();folds();if(q&&$('q'))search();window.scrollTo(x,y)}}
catch(e){}
busy=false;if(again){again=false;update()}}
let ev=null;
function connect(){ev=new EventSource('@EVENTS@');ev.onmessage=()=>update()}
document.addEventListener('visibilitychange',()=>{if(document.hidden){if(ev){ev.close();ev=null}}
else if(!ev){connect();update()}});
if(!document.hidden)connect();
</script></body></html>"""
