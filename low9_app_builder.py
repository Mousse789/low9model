#!/usr/bin/env python3
"""Build the vivid, interactive Low-9 / High-9 web app (single self-contained HTML)."""
import json, sys, datetime

TEMPLATE = r"""<!DOCTYPE html><html lang="en" data-theme="dark"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Low-9 / High-9 Monitor</title>
<style>
:root{
  --blue:#3987e5; --orange:#d95926; --aqua:#199e70; --yellow:#c98500;
  --magenta:#d55181; --violet:#9085e9; --red:#e66767;
  --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;
}
html[data-theme="dark"]{
  --page:#0d0d0d; --surface:#1a1a19; --surface2:#232320; --ink:#ffffff;
  --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --line:#383835;
  --up:#0ca30c; --down:#e66767; --ring:rgba(255,255,255,0.10);
}
html[data-theme="light"]{
  --page:#f9f9f7; --surface:#fcfcfb; --surface2:#f2f1ec; --ink:#0b0b0b;
  --ink2:#52514e; --muted:#898781; --grid:#e1e0d9; --line:#c3c2b7;
  --up:#006300; --down:#d03b3b; --ring:rgba(11,11,11,0.10);
  --blue:#2a78d6; --orange:#eb6834; --aqua:#1baf7a; --yellow:#eda100;
  --magenta:#e87ba4; --violet:#4a3aa7; --red:#e34948;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  padding:22px 16px 70px}
.wrap{max-width:1160px;margin:0 auto}
.top{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:6px}
h1{font-size:23px;margin:0;letter-spacing:-.3px;font-weight:750}
.sub{color:var(--ink2);font-size:13px;margin:2px 0 20px}
.spacer{flex:1}
.tbtn{background:var(--surface);border:1px solid var(--line);color:var(--ink2);
  border-radius:9px;padding:7px 12px;font-size:13px;cursor:pointer;white-space:nowrap}
.tbtn:hover{color:var(--ink);border-color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin-bottom:22px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:15px 16px}
.tval{font-size:30px;font-weight:750;line-height:1;font-variant-numeric:tabular-nums}
.tlab{color:var(--muted);font-size:10.5px;margin-top:7px;text-transform:uppercase;letter-spacing:.6px}
.tile.hot .tval{color:var(--red)}.tile.warm .tval{color:var(--orange)}
.tile.grn .tval{color:var(--aqua)}.tile.teal .tval{color:var(--blue)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.chd{padding:13px 16px 4px;font-weight:650;font-size:14px}
.chd small{color:var(--muted);font-weight:400;font-size:12px;display:block;margin-top:2px}
.cbody{padding:10px 16px 16px}
.legend{display:flex;gap:14px;font-size:12px;color:var(--ink2);padding:0 16px 10px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.barrow{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12.5px}
.barrow .bl{width:120px;flex:none;color:var(--ink2);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bartrack{flex:1;display:flex;gap:3px;align-items:center}
.bar{height:14px;border-radius:0 4px 4px 0;min-width:2px}
.barrow .bv{width:74px;flex:none;color:var(--muted);font-variant-numeric:tabular-nums;font-size:11.5px}
.ctl{position:sticky;top:0;z-index:20;background:var(--surface);border:1px solid var(--line);
  border-radius:14px;padding:13px 16px;margin:18px 0 20px;box-shadow:0 6px 22px rgba(0,0,0,.28)}
.ctl-row{display:flex;gap:14px 18px;flex-wrap:wrap;align-items:center}
.ctl input[type=search],.ctl select{background:var(--surface2);border:1px solid var(--line);
  color:var(--ink);border-radius:9px;padding:7px 10px;font-size:13px;font-family:inherit}
.ctl input[type=search]{min-width:180px}
.cg{display:flex;flex-direction:column;gap:5px;min-width:150px}
.cg .cl{font-size:11.5px;color:var(--ink2)}.cg .cl b{color:var(--ink);font-variant-numeric:tabular-nums}
.cg input[type=range]{width:100%;accent-color:var(--blue)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:var(--surface2);border:0;color:var(--ink2);padding:7px 12px;font-size:12.5px;cursor:pointer}
.seg button.on{background:var(--blue);color:#fff}
.tg{font-size:12.5px;color:var(--ink2);display:flex;align-items:center;gap:6px;cursor:pointer}
.mi{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;margin-left:auto}
h2{font-size:12.5px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);
  margin:26px 0 12px;border-bottom:1px solid var(--line);padding-bottom:7px}
section{background:var(--surface);border:1px solid var(--line);border-radius:14px;margin-bottom:14px;overflow:hidden}
.shd{padding:13px 16px;font-weight:650;font-size:14px;border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.shd small{color:var(--muted);font-weight:400;margin-left:auto;font-size:12px}
.shd .cnt{color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:14px}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);
  text-align:left;padding:8px 14px;border-bottom:1px solid var(--line);cursor:pointer;user-select:none;white-space:nowrap}
th.num{text-align:right}th:hover{color:var(--ink2)}th .ar{opacity:.5;font-size:9px}
td{padding:9px 14px;border-top:1px solid var(--grid)}
tbody tr:first-child td{border-top:none}
.tk{font-weight:700}.nm{color:var(--ink2);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc{color:var(--muted);font-size:12px;white-space:nowrap}
.pr,.pe,.ct,.chg{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chg.up{color:var(--up)}.chg.down{color:var(--down)}
.pe .na{color:var(--muted)}.pe .flag{display:inline-block;margin-left:5px;font-size:9.5px;color:var(--warn);
  border:1px solid var(--warn);border-radius:5px;padding:0 4px;opacity:.85;vertical-align:middle}
.spark{display:block}
.badge{display:inline-block;min-width:24px;text-align:center;padding:2px 9px;border-radius:20px;
  font-weight:700;font-size:12.5px;color:#fff}
.badge .plus{font-weight:400;font-size:10.5px;opacity:.9}
.empty{color:var(--muted);text-align:center;padding:16px}
.note{color:var(--ink2);font-size:12px;line-height:1.65;margin-top:22px;border-top:1px solid var(--line);padding-top:14px}
.note b{color:var(--ink)}.note .na{color:var(--muted)}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
@media(max-width:640px){.nm,.sc,th.h-nm,th.h-sc{display:none}.mi{width:100%;margin:4px 0 0}}
</style></head>
<body><div class="wrap">
<div class="top">
  <div>
    <h1>📉📈 Low-9 / High-9 Monitor</h1>
  </div>
  <div class="spacer"></div>
  <button class="tbtn" id="themebtn">◐ Theme</button>
</div>
<div class="sub" id="subline"></div>

<div class="tiles" id="tiles"></div>

<div class="grid2">
  <div class="card">
    <div class="chd">Signals by sector<small>count of fresh + extended 9-signals in each sector</small></div>
    <div class="legend"><span><i style="background:var(--blue)"></i>Low-9 (bottoms)</span><span><i style="background:var(--orange)"></i>High-9 (tops)</span></div>
    <div class="cbody" id="sectorchart"></div>
  </div>
  <div class="card">
    <div class="chd">Backtest win-rate<small>% of past completions that moved the expected way (~2y history, this universe)</small></div>
    <div class="cbody" id="perfchart"></div>
  </div>
</div>

<div class="ctl">
  <div class="ctl-row">
    <input type="search" id="q" placeholder="Search ticker or company…" autocomplete="off">
    <select id="sector"><option value="">All sectors</option></select>
    <select id="cap">
      <option value="">All sizes</option>
      <option value="mega">Mega ≥ $200B</option>
      <option value="large">Large $10–200B</option>
      <option value="mid">Mid $2–10B</option>
      <option value="small">Small &lt; $2B</option>
    </select>
    <div class="seg" id="tfseg">
      <button data-tf="all" class="on">All</button>
      <button data-tf="daily">Daily</button>
      <button data-tf="weekly">Weekly</button>
    </div>
    <span class="mi" id="matchinfo"></span>
  </div>
  <div class="ctl-row" id="perow" style="margin-top:12px">
    <div class="cg">
      <div class="cl">🟢 Low-9 — keep value names, P/E ≤ <b id="lowv">25</b></div>
      <input type="range" id="lowr" min="0" max="80" step="1" value="25">
    </div>
    <div class="cg">
      <div class="cl">🔴 High-9 — keep pricey names, P/E ≥ <b id="highv">40</b></div>
      <input type="range" id="highr" min="0" max="120" step="1" value="40">
    </div>
    <label class="tg"><input type="checkbox" id="showall"> Ignore P/E filter</label>
  </div>
</div>

<h2>🟢 Low 9 — potential bottoms (bounce up)</h2>
<div id="lowsections"></div>
<h2>🔴 High 9 — potential tops (reverse / drop)</h2>
<div id="highsections"></div>

<div class="note" id="note"></div>
</div>

<script>
const DATA = __DATA__;
const ASOF = "__ASOF__", UNIVERSE = "__UNIVERSE__", GENAT = "__GENAT__";

const C = DATA.cls, P = DATA.perf || {};
const fmtInt = n => n.toLocaleString('en-US');
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

const SECTIONS = [
  {key:'weekly_low_9',  side:'low', tf:'weekly', field:'weekly_low', color:'red',    title:'Fresh weekly low-9', sub:'strongest bottom — 9 weekly closes below the close 4 weeks earlier'},
  {key:'daily_low_9',   side:'low', tf:'daily',  field:'daily_low',  color:'orange', title:'Fresh daily low-9',  sub:'9 daily closes below the close 4 days earlier'},
  {key:'weekly_low_ext',side:'low', tf:'weekly', field:'weekly_low', color:'blue',   title:'Weekly low extended',sub:'9 completed, still falling — badge shows weeks since'},
  {key:'daily_low_ext', side:'low', tf:'daily',  field:'daily_low',  color:'blue',   title:'Daily low extended', sub:'9 completed, still falling — badge shows days since'},
  {key:'weekly_high_9', side:'high',tf:'weekly', field:'weekly_high',color:'aqua',   title:'Fresh weekly high-9',sub:'strongest top — 9 weekly closes above the close 4 weeks earlier'},
  {key:'daily_high_9',  side:'high',tf:'daily',  field:'daily_high', color:'blue',   title:'Fresh daily high-9', sub:'9 daily closes above the close 4 days earlier'},
  {key:'weekly_high_ext',side:'high',tf:'weekly',field:'weekly_high',color:'aqua',   title:'Weekly high extended',sub:'9 completed, still rising — badge shows weeks since'},
  {key:'daily_high_ext',side:'high',tf:'daily',  field:'daily_high', color:'blue',   title:'Daily high extended',sub:'9 completed, still rising — badge shows days since'},
];
const DOTCOL = {red:'var(--red)',orange:'var(--orange)',blue:'var(--blue)',aqua:'var(--aqua)'};

const state = {q:'', sector:'', cap:'', tf:'all', low:25, high:40, showall:false, sort:{}};

function capBucket(mc){ if(mc==null) return null;
  if(mc>=200e9)return'mega'; if(mc>=10e9)return'large'; if(mc>=2e9)return'mid'; return'small';}
function countLabel(field,v){ const u=field.startsWith('weekly')?'w':'d';
  return v>9 ? `9&thinsp;<span class="plus">+${v-9}${u}</span>` : String(v);}
function sparkSVG(spark, up){ if(!spark||spark.length<2) return '';
  const w=88,h=26,pad=2; const mn=Math.min(...spark),mx=Math.max(...spark),rng=(mx-mn)||1;
  const dx=(w-2*pad)/(spark.length-1);
  const pts=spark.map((v,i)=>`${(pad+i*dx).toFixed(1)},${(pad+(h-2*pad)*(1-(v-mn)/rng)).toFixed(1)}`).join(' ');
  const col=up?'var(--up)':'var(--down)';
  const last=pts.split(' ').pop().split(',');
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" fill="none">
    <polyline points="${pts}" stroke="${col}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="2.1" fill="${col}"/></svg>`;}

function rowVisible(r, sec){
  if(state.tf!=='all' && sec.tf!==state.tf) return false;
  if(state.q){ const q=state.q.toLowerCase();
    if(!(r.sym.toLowerCase().includes(q) || (r.name||'').toLowerCase().includes(q))) return false;}
  if(state.sector && r.sector!==state.sector) return false;
  if(state.cap && capBucket(r.mktcap)!==state.cap) return false;
  if(!state.showall && r.pe!=null && !isNaN(r.pe)){
    if(sec.side==='low' && r.pe>state.low) return false;
    if(sec.side==='high' && r.pe<state.high) return false;
  }
  return true;
}

function renderTiles(){
  const n=k=>(C[k]||[]).length;
  const tiles=[
    ['Fresh weekly low-9', n('weekly_low_9'),'hot'],
    ['Fresh daily low-9', n('daily_low_9'),'warm'],
    ['Fresh weekly high-9', n('weekly_high_9'),'grn'],
    ['Fresh daily high-9', n('daily_high_9'),'teal'],
    ['Low approaching 7–8', n('daily_low_near')+n('weekly_low_near'),''],
    ['Scanned', DATA.scanned,''],
  ];
  document.getElementById('tiles').innerHTML = tiles.map(([l,v,c])=>
    `<div class="tile ${c}"><div class="tval">${fmtInt(v)}</div><div class="tlab">${l}</div></div>`).join('');
}

function renderSectorChart(){
  const agg={};
  for(const sec of SECTIONS){ for(const r of (C[sec.key]||[])){
    const s=r.sector||'—'; agg[s]=agg[s]||{low:0,high:0}; agg[s][sec.side]++; }}
  const rows=Object.entries(agg).map(([s,v])=>[s,v.low,v.high,v.low+v.high])
    .sort((a,b)=>b[3]-a[3]).slice(0,10);
  const mx=Math.max(1,...rows.map(r=>r[3]));
  document.getElementById('sectorchart').innerHTML = rows.map(([s,lo,hi])=>
    `<div class="barrow"><div class="bl" title="${esc(s)}">${esc(s)}</div><div class="bartrack">
      ${lo?`<div class="bar" style="width:${lo/mx*100}%;background:var(--blue)"></div>`:''}
      ${hi?`<div class="bar" style="width:${hi/mx*100}%;background:var(--orange)"></div>`:''}
    </div><div class="bv">${lo} / ${hi}</div></div>`).join('') || '<div class="empty">No signals</div>';
}

function renderPerfChart(){
  const groups=[
    ['Low-9 daily','daily','buy',[5,10,20],'d'],
    ['Low-9 weekly','weekly','buy',[4,8,12],'w'],
    ['High-9 daily','daily','sell',[5,10,20],'d'],
    ['High-9 weekly','weekly','sell',[4,8,12],'w'],
  ];
  let html='';
  for(const [lab,tf,side,hs,u] of groups){
    for(const h of hs){ const s=P[`${tf}_${side}_${h}`];
      const wr=s?s.win_rate:null;
      const col=wr==null?'var(--muted)':(wr>=55?'var(--good)':(wr<45?'var(--crit)':'var(--warn)'));
      const w=wr==null?0:wr;
      html+=`<div class="barrow"><div class="bl">${h==hs[0]?lab:''} <span style="color:var(--muted)">${h}${u}</span></div>
        <div class="bartrack"><div class="bar" style="width:${w}%;background:${col};border-radius:0 4px 4px 0"></div></div>
        <div class="bv">${wr==null?'–':wr+'%'}${s?` · ${s.avg_ret>0?'+':''}${s.avg_ret}%`:''}</div></div>`;
    }
  }
  document.getElementById('perfchart').innerHTML = html;
}

function sortRows(rows, sec){
  const sk=state.sort[sec.key];
  if(!sk) return rows;
  const {col,dir}=sk, m=dir==='asc'?1:-1;
  const val=r=>{
    if(col==='sym')return r.sym;
    if(col==='price')return r.price??-Infinity;
    if(col==='chg')return r.chg??-Infinity;
    if(col==='pe')return r.pe??Infinity;
    if(col==='ct')return r[sec.field]??0;
    return 0;
  };
  return rows.slice().sort((a,b)=>{const x=val(a),y=val(b);
    return x<y?-1*m:x>y?1*m:0;});
}
function peCell(r){
  if(r.pe!=null && !isNaN(r.pe)) return `<td class="pe">${r.pe}</td>`;
  const fwd=(r.fwd_pe!=null&&!isNaN(r.fwd_pe))?`<span class="na"> fwd ${r.fwd_pe}</span>`:'';
  return `<td class="pe"><span class="na">n/a</span><span class="flag">no earn</span>${fwd}</td>`;
}
function tableHTML(sec){
  let rows=(C[sec.key]||[]).filter(r=>rowVisible(r,sec));
  rows=sortRows(rows,sec);
  const ar=col=>{const sk=state.sort[sec.key];return sk&&sk.col===col?`<span class="ar">${sk.dir==='asc'?'▲':'▼'}</span>`:'';};
  const head=`<thead><tr>
    <th data-c="sym">Ticker ${ar('sym')}</th>
    <th class="h-nm">Company</th>
    <th class="h-sc">Sector</th>
    <th class="num" data-c="price">Price ${ar('price')}</th>
    <th class="num" data-c="chg">6mo ${ar('chg')}</th>
    <th>Trend</th>
    <th class="num" data-c="pe">P/E ${ar('pe')}</th>
    <th class="num" data-c="ct">Signal ${ar('ct')}</th></tr></thead>`;
  let body;
  if(!rows.length){ body=`<tr><td colspan="8" class="empty">None match</td></tr>`; }
  else body=rows.map(r=>{
    const up=(r.chg??0)>=0;
    return `<tr>
      <td class="tk">${esc(r.sym)}</td>
      <td class="nm">${esc(r.name||'')}</td>
      <td class="sc">${esc(r.sector||'')}</td>
      <td class="pr">$${(r.price??0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
      <td class="chg ${up?'up':'down'}">${r.chg==null?'':(up?'+':'')+r.chg+'%'}</td>
      <td>${sparkSVG(r.spark,up)}</td>
      ${peCell(r)}
      <td class="ct"><span class="badge" style="background:${DOTCOL[sec.color]}">${countLabel(sec.field,r[sec.field])}</span></td>
    </tr>`;}).join('');
  const total=(C[sec.key]||[]).length;
  return `<section data-key="${sec.key}" data-tf="${sec.tf}">
    <div class="shd"><span class="dot" style="background:${DOTCOL[sec.color]}"></span>${sec.title}
      <span class="cnt">${rows.length}${rows.length!==total?` / ${total}`:''}</span>
      <small>${sec.sub}</small></div>
    <table>${head}<tbody>${body}</tbody></table></section>`;
}
function renderTables(){
  const low=SECTIONS.filter(s=>s.side==='low'&&(C[s.key]||[]).length);
  const high=SECTIONS.filter(s=>s.side==='high'&&(C[s.key]||[]).length);
  const vis=s=>state.tf==='all'||s.tf===state.tf;
  document.getElementById('lowsections').innerHTML =
    low.filter(vis).map(tableHTML).join('') || '<section><div class="empty">No low-9 signals for this filter</div></section>';
  document.getElementById('highsections').innerHTML =
    high.filter(vis).map(tableHTML).join('') || '<section><div class="empty">No high-9 signals for this filter</div></section>';
  bindSortHeaders();
  updateMatch();
}
function bindSortHeaders(){
  document.querySelectorAll('section table th[data-c]').forEach(th=>{
    th.onclick=()=>{ const key=th.closest('section').dataset.key, col=th.dataset.c;
      const cur=state.sort[key];
      state.sort[key]=(cur&&cur.col===col)?{col,dir:cur.dir==='asc'?'desc':'asc'}:{col,dir:col==='sym'?'asc':'desc'};
      renderTables();
    };
  });
}
function updateMatch(){
  let shown=0,total=0;
  for(const sec of SECTIONS){ const all=C[sec.key]||[]; total+=all.length;
    if(state.tf==='all'||sec.tf===state.tf) shown+=all.filter(r=>rowVisible(r,sec)).length;}
  document.getElementById('matchinfo').textContent=`${shown} of ${total} signals shown`;
}

function initControls(){
  const secs=new Set(); for(const sec of SECTIONS) for(const r of (C[sec.key]||[])) if(r.sector) secs.add(r.sector);
  const sel=document.getElementById('sector');
  [...secs].sort().forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;sel.appendChild(o);});
  sel.onchange=e=>{state.sector=e.target.value;renderTables();};
  document.getElementById('cap').onchange=e=>{state.cap=e.target.value;renderTables();};
  document.getElementById('q').oninput=e=>{state.q=e.target.value.trim();renderTables();};
  const lowr=document.getElementById('lowr'),highr=document.getElementById('highr');
  lowr.oninput=e=>{state.low=+e.target.value;document.getElementById('lowv').textContent=state.low;renderTables();};
  highr.oninput=e=>{state.high=+e.target.value;document.getElementById('highv').textContent=state.high;renderTables();};
  document.getElementById('showall').onchange=e=>{state.showall=e.target.checked;
    document.getElementById('perow').style.opacity=e.target.checked?.45:1;renderTables();};
  document.querySelectorAll('#tfseg button').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#tfseg button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');state.tf=b.dataset.tf;renderTables();});
  const hasPE=SECTIONS.some(sec=>(C[sec.key]||[]).some(r=>'pe' in r));
  if(!hasPE) document.getElementById('perow').style.display='none';
  document.getElementById('themebtn').onclick=()=>{
    const h=document.documentElement; h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';};
}

function renderStatic(){
  document.getElementById('subline').innerHTML =
    `TD Sequential setups (九转序列) · ${esc(UNIVERSE)} · daily &amp; weekly · data as of <b>${esc(ASOF)}</b> · ${fmtInt(DATA.scanned)} scanned, ${DATA.errors} fetch errors`;
  document.getElementById('note').innerHTML =
    `<b>How to read this:</b> A <b>low 9</b> completes after 9 straight bars each closing <b>below</b> the close 4 bars earlier (TD Buy Setup) — downtrend exhaustion, a possible bottom. A <b>high 9</b> completes after 9 straight bars each closing <b>above</b> the close 4 bars earlier (TD Sell Setup) — uptrend exhaustion, a possible top. Weekly signals are stronger and slower than daily. In the "extended" rows the badge reads <b>9 +N</b>: the 9 completed and the trend has continued N more bars since (days on daily, weeks on weekly). <b>Trend</b> is the ~6-month price path; <b>6mo</b> is its total change. <b>P/E</b> is trailing (TTM); names with no trailing earnings show <span class="na">n/a</span> and are always shown. The <b>backtest win-rate</b> is how often each completed 9 moved the expected way over ~2y of history (avg forward return beside it). In strong uptrends high-9 "sell" signals often keep rising — the win-rates make that visible. Generated ${esc(GENAT)}.<br><br>Technical screen for research only — <b>not financial advice</b>. Signals fail often; do your own analysis.`;
}

renderStatic(); renderTiles(); renderSectorChart(); renderPerfChart(); initControls(); renderTables();
</script>
</body></html>"""

def build(scan_path, out_path):
    data = json.load(open(scan_path))
    asof = data.get("asof", "")[:10]
    universe = data.get("universe", "")
    genat = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__ASOF__", asof)
            .replace("__UNIVERSE__", universe.replace('"', "'"))
            .replace("__GENAT__", genat))
    with open(out_path, "w") as f:
        f.write(html)
    print(f"wrote {out_path} — {len(html):,} bytes")

if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
