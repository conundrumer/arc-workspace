"""The ticket dashboard's page around its sections (`ticket_dashboard`):
its CSS, the search form, and the script that asks the server for the
search's results, filters the rows of Bugs and cost savings, and updates
the page on an event of the stream while the page is shown; with the
routes that script requests."""

EVENTS = "/events"
"""The route of the Server-Sent Events stream."""

SEARCH_ROUTE = "/search"
"""The route of the search's results."""

SEARCH = """<div class="filters">
<input id="q" type="search" placeholder="number, title, kind or log words" size="40">
<select id="fkind"><option value="">any kind</option>@KINDS@</select>
<select id="fstatus"><option value="">any status</option><option value="open">open</option>@STATUSES@</select>
<input id="fsession" type="text" placeholder="session" size="6">
<label>est. cost below $<input id="fbelow" type="number" min="0" step="1" style="width:5em"></label>
<label><input id="fpriced" type="checkbox"> gain priced only</label>
</div><div id="results"></div>"""

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tickets</title><style>
body{font:14px/1.4 -apple-system,Helvetica,Arial,sans-serif;margin:0 16px 40px;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:6px 0;z-index:2}
h1{font-size:18px;margin:0 12px 0 0;display:inline}h2{font-size:16px;margin:22px 0 6px;border-bottom:2px solid #ddd}
a.nav{margin-right:10px;white-space:nowrap}.box{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;margin:4px 0}
th,td{border:1px solid #ddd;padding:3px 6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:#f3f3f3}tr:nth-child(even) td{background:#fafafa}
.warn{color:#b00020;font-weight:600}.ok{color:#1b7f2a}.hint{color:#666;font-size:12px;margin:2px 0}
.bar{display:inline-block;height:10px;background:#4a78c2;max-width:100%}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.filters input,.filters select{font-size:16px;max-width:100%}
.res{border:1px solid #ddd;margin:4px 0;padding:4px 8px;overflow-wrap:anywhere}.res summary{cursor:pointer}
.log{font:12px/1.35 Menlo,monospace;white-space:pre-wrap;margin:4px 0}.path{font:12px Menlo,monospace;color:#555}
.notes{color:#666;font-size:12px;overflow-wrap:anywhere}
@media (min-width:701px){td:nth-child(-n+3){white-space:nowrap;overflow-wrap:normal}}
#live-state{font-size:12px}
@media (max-width:700px){body{margin:0 8px 40px;font-size:13px}
header{position:static}h2{font-size:15px}
.box table,.box tbody,.box tr,.box td{display:block;width:auto}.box thead{display:none}
.box tr{border:1px solid #ddd;margin:0 0 6px;padding:2px 0}.box td{border:0;padding:1px 6px;overflow-wrap:anywhere}
.box td:empty{display:none}.box td::before{content:attr(data-l) ": ";color:#666;font-size:12px}
.box tr:nth-child(even) td{background:none}
#q{width:100%}}
</style></head><body>
<header><h1>Tickets</h1><span class="hint">rendered <span id="rendered">@RENDERED@</span> UTC;
<span id="live-state">connecting</span></span><br>@NAV@</header>
<div id="live">@NOTES@
@BODY@</div>
<script>
const ids=['q','fkind','fstatus','fsession','fbelow','fpriced'];
const params={q:'q',fkind:'kind',fstatus:'status',fsession:'session',fbelow:'below',fpriced:'priced'};
const OPEN=s=>@OPEN@.includes(s);
function val(id){const e=document.getElementById(id);return e.type==='checkbox'?(e.checked?'1':''):e.value}
function setv(id,v){const e=document.getElementById(id);if(e.type==='checkbox')e.checked=!!v;else e.value=v||''}
function snapshot(){const s={open:[...document.querySelectorAll('details.res[open]')].map(d=>d.dataset.n)};
ids.forEach(i=>s[i]=val(i));return s}
function fromHash(){const h=new URLSearchParams(location.hash.slice(1));const s={};
let any=false;for(const[i,k]of Object.entries(params))if(h.has(k)){s[i]=h.get(k);any=true}return any?s:null}
function keep(t){const k=val('fkind'),st=val('fstatus'),se=val('fsession'),b=val('fbelow'),p=val('fpriced');
if(k&&t.k!==k)return false;if(st&&(st==='open'?!OPEN(t.s):t.s!==st))return false;
if(se&&String(t.se)!==se)return false;if(b!==''&&t.e!==null&&t.e>=+b)return false;if(p&&!t.g)return false;return true}
function rows(){document.querySelectorAll('tr.worth').forEach(r=>{const t={k:r.dataset.kind,s:r.dataset.status,se:r.dataset.session,
e:r.dataset.est===''?null:+r.dataset.est,g:+r.dataset.priced};r.style.display=keep(t)?'':'none'})}
let asked=0,timer=null;
async function search(openSet){rows();const n=++asked;const u=new URLSearchParams();
for(const i of ids){const v=val(i);if(v!=='')u.set(params[i],v)}
let h;try{const r=await fetch('@SEARCH@?'+u,{cache:'no-store'});h=await r.text();if(!r.ok)h='search failed: '+r.status+' '+h}
catch(e){h='search failed: '+e}
if(n!==asked)return;const res=document.getElementById('results');res.innerHTML=h;const q=val('q').trim();
res.querySelectorAll('details.res').forEach(d=>{if(openSet.has(d.dataset.n)||d.dataset.n===q)d.open=true})}
function later(){clearTimeout(timer);timer=setTimeout(()=>search(new Set()),250)}
function restore(s){clearTimeout(timer);if(s)ids.forEach(i=>setv(i,s[i]));return search(new Set(s&&s.open||[]))}
function openTicket(n){clearTimeout(timer);document.getElementById('q').value=n;search(new Set([n]));document.getElementById('search').scrollIntoView()}
document.addEventListener('click',e=>{const a=e.target.closest('a.tk');if(a){e.preventDefault();openTicket(a.dataset.n)}});
document.addEventListener('input',e=>{if(ids.includes(e.target.id))later()});
window.addEventListener('hashchange',()=>{const h=fromHash();if(h)restore(h)});
restore(fromHash());
let busy=false,again=false;
async function update(){if(busy){again=true;return}busy=true;
try{const r=await fetch('/',{cache:'no-store'});const d=new DOMParser().parseFromString(await r.text(),'text/html');
const s=snapshot(),x=window.scrollX,y=window.scrollY;
document.getElementById('live').replaceWith(d.getElementById('live'));
document.getElementById('rendered').textContent=d.getElementById('rendered').textContent;
await restore(s);window.scrollTo(x,y)}
catch(e){document.getElementById('live-state').textContent='update failed: '+e}
busy=false;if(again){again=false;update()}}
const st=document.getElementById('live-state');let ev=null;
function connect(){ev=new EventSource('@EVENTS@');
ev.onopen=()=>{st.textContent='live: updates as tickets change'};
ev.onerror=()=>{st.textContent='disconnected; retrying'};
ev.onmessage=()=>update()}
document.addEventListener('visibilitychange',()=>{if(document.hidden){if(ev){ev.close();ev=null}
st.textContent='paused while hidden'}else if(!ev){connect();update()}});
if(!document.hidden)connect();
</script></body></html>"""
