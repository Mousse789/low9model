#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from a low9/high9 scan JSON.

Supports optional P/E enrichment: if hit rows carry a "pe" field, a P/E column
and interactive P/E sliders are rendered — low-9 (bottom/buy) tables keep value
names (P/E <= threshold), high-9 (top/sell) tables keep expensive names
(P/E >= threshold). Names with no trailing earnings are always shown and flagged.
"""
import json, sys, html

def count_label(field, v):
    unit = "w" if field.startswith("weekly") else "d"
    if v > 9:
        return f'9&thinsp;<span class="plus">+{v - 9}{unit}</span>'
    return str(v)

def _pe_cell(h):
    pe = h.get("pe")
    fwd = h.get("fwd_pe")
    if isinstance(pe, (int, float)):
        return f'<td class="pe" data-has="1">{pe:g}</td>'
    hint = f'<span class="fwd">fwd {fwd:g}</span>' if isinstance(fwd, (int, float)) else ""
    return (f'<td class="pe" data-has="0"><span class="na" title="no trailing (TTM) earnings">n/a</span>'
            f'<span class="flag">no earnings</span>{hint}</td>')

def rows_html(rows, field, badge, mx=25):
    side = "low" if "low" in field else "high"
    if not rows:
        return '<tr><td colspan="6" class="empty">None today</td></tr>'
    out = []
    for h in rows[:mx]:
        pe = h.get("pe")
        pe_attr = f'{pe:g}' if isinstance(pe, (int, float)) else ""
        noearn = "0" if isinstance(pe, (int, float)) else "1"
        out.append(
            f'<tr class="row {side}" data-pe="{pe_attr}" data-noearn="{noearn}">'
            f'<td class="tk">{html.escape(h["sym"])}</td>'
            f'<td class="nm">{html.escape(h["name"])}</td>'
            f'<td class="sc">{html.escape(h["sector"])}</td>'
            f'<td class="pr">${h["price"]:,.2f}</td>'
            f'{_pe_cell(h)}'
            f'<td class="ct"><span class="badge {badge}">{count_label(field, h[field])}</span></td></tr>'
        )
    if len(rows) > mx:
        out.append(f'<tr class="more"><td colspan="6" class="empty">… +{len(rows)-mx} more</td></tr>')
    out.append('<tr class="emptyrow" style="display:none"><td colspan="6" class="empty">No names match the P/E filter</td></tr>')
    return "\n".join(out)

def section(title, sub, dot, rows, field, badge):
    return (f'<section><div class="shd"><span class="dot {dot}"></span>{title}'
            f'<small>{sub}</small></div><table>{rows_html(rows, field, badge)}</table></section>')

def perf_panel(perf):
    def cell(key, good_hi=True):
        s = perf.get(key)
        if not s:
            return '<td class="pv">–</td>'
        wr = s["win_rate"]
        cls = "gp" if (wr >= 55) else ("gn" if wr < 45 else "gm")
        return f'<td class="pv {cls}">{wr}%<span class="pn">{s["avg_ret"]:+}% · n={s["n"]}</span></td>'
    def row(label, tf, side, hs):
        cells = "".join(cell(f"{tf}_{side}_{h}") for h in hs)
        return f'<tr><td class="pl">{label}</td>{cells}</tr>'
    return f"""<section><div class="shd"><span class="dot gp"></span>Signal performance
<small>backtest over ~2y history · % that moved the expected way (avg forward return · sample size)</small></div>
<table class="perf">
<tr><td class="pl"></td><td class="ph">near</td><td class="ph">mid</td><td class="ph">far</td></tr>
{row("Low-9 daily → up (5/10/20d)","daily","buy",[5,10,20])}
{row("Low-9 weekly → up (4/8/12w)","weekly","buy",[4,8,12])}
{row("High-9 daily → down (5/10/20d)","daily","sell",[5,10,20])}
{row("High-9 weekly → down (4/8/12w)","weekly","sell",[4,8,12])}
</table></section>"""

CONTROLS = """<div class="ctl">
<div class="cg">
  <div class="cl">🟢 Low-9 (bottoms) — keep value names, P/E ≤ <b id="lowv">25</b></div>
  <input type="range" id="lowr" min="0" max="80" step="1" value="25">
</div>
<div class="cg">
  <div class="cl">🔴 High-9 (tops) — keep expensive names, P/E ≥ <b id="highv">40</b></div>
  <input type="range" id="highr" min="0" max="120" step="1" value="40">
</div>
<label class="tg"><input type="checkbox" id="showall"> Show all (ignore P/E)</label>
<span id="matchinfo" class="mi"></span>
</div>"""

FILTER_JS = """<script>
(function(){
  var lowr=document.getElementById('lowr'), highr=document.getElementById('highr'),
      lowv=document.getElementById('lowv'), highv=document.getElementById('highv'),
      showall=document.getElementById('showall'), matchinfo=document.getElementById('matchinfo');
  var rows=Array.prototype.slice.call(document.querySelectorAll('tr.row'));
  function apply(){
    var lo=+lowr.value, hi=+highr.value, all=showall.checked;
    lowv.textContent=lo; highv.textContent=hi;
    rows.forEach(function(tr){
      var noearn=tr.dataset.noearn==='1';
      var pe=tr.dataset.pe===''?null:parseFloat(tr.dataset.pe);
      var isLow=tr.classList.contains('low');
      var vis;
      if(all) vis=true;
      else if(noearn||pe===null||isNaN(pe)) vis=true;
      else if(isLow) vis=pe<=lo;
      else vis=pe>=hi;
      tr.style.display=vis?'':'none';
    });
    document.querySelectorAll('table').forEach(function(t){
      var trs=t.querySelectorAll('tr.row');
      if(!trs.length) return;
      var shown=Array.prototype.filter.call(trs,function(r){return r.style.display!=='none';}).length;
      var emp=t.querySelector('tr.emptyrow');
      if(emp) emp.style.display=(shown===0)?'':'none';
    });
    var vis=rows.filter(function(r){return r.style.display!=='none';}).length;
    matchinfo.textContent=vis+' of '+rows.length+' signal rows shown';
  }
  lowr.addEventListener('input',apply); highr.addEventListener('input',apply);
  showall.addEventListener('change',apply); apply();
})();
</script>"""

def build(data, path):
    C = data["cls"]; P = data["perf"]
    asof = data["asof"][:10]
    has_pe = any(isinstance(r.get("pe"), (int, float)) or r.get("pe") is None and "pe" in r
                 for rows in C.values() for r in rows) and any("pe" in r for rows in C.values() for r in rows)
    n = lambda k: len(C[k])
    tiles = [
        ("Fresh weekly low-9", n("weekly_low_9"), "hot"),
        ("Fresh daily low-9", n("daily_low_9"), "warm"),
        ("Fresh weekly high-9", n("weekly_high_9"), "grn"),
        ("Fresh daily high-9", n("daily_high_9"), "teal"),
        ("Low approaching 7–8", n("daily_low_near") + n("weekly_low_near"), "mut"),
        ("Scanned", data["scanned"], "mut"),
    ]
    tile_html = "\n".join(
        f'<div class="tile {c}"><div class="tval">{v}</div><div class="tlab">{l}</div></div>'
        for l, v, c in tiles)

    low = (section("Fresh weekly low-9", "strongest bottom signal — 9 weekly closes below the close 4 weeks earlier", "hot", C["weekly_low_9"], "weekly_low", "hot")
           + section("Fresh daily low-9", "9 daily closes below the close 4 days earlier", "warm", C["daily_low_9"], "daily_low", "warm")
           + section("Weekly low extended", "9 completed, still falling — badge shows weeks since the 9", "cool", C["weekly_low_ext"], "weekly_low", "cool")
           + section("Daily low extended", "9 completed, still falling — badge shows days since the 9", "cool", C["daily_low_ext"], "daily_low", "cool"))
    high = (section("Fresh weekly high-9", "strongest top signal — 9 weekly closes above the close 4 weeks earlier", "grn", C["weekly_high_9"], "weekly_high", "grn")
            + section("Fresh daily high-9", "9 daily closes above the close 4 days earlier", "teal", C["daily_high_9"], "daily_high", "teal")
            + section("Weekly high extended", "9 completed, still rising — badge shows weeks since the 9", "teal", C["weekly_high_ext"], "weekly_high", "teal")
            + section("Daily high extended", "9 completed, still rising — badge shows days since the 9", "teal", C["daily_high_ext"], "daily_high", "teal"))

    controls = CONTROLS if has_pe else ""
    filter_js = FILTER_JS if has_pe else ""
    pe_note = ("<b>P/E filter:</b> use the sliders to keep only reasonably-valued names in the low-9 (bottom/buy) "
               "lists and only richly-valued names in the high-9 (top/sell) lists. P/E is trailing (TTM). Names with "
               "no trailing earnings show <span class='na'>n/a</span> and are always displayed and flagged — never hidden by the filter. ") if has_pe else ""

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Low-9 / High-9 Monitor</title><style>
:root{{--bg:#0f1420;--card:#182031;--ink:#e8edf7;--mut:#8a97b0;--line:#26304a;
--hot:#ff5470;--warm:#ffa23a;--cool:#3aa0ff;--grn:#37d39b;--teal:#22b8cf;--mutc:#5a6683;}}
@media(prefers-color-scheme:light){{:root{{--bg:#f4f6fb;--card:#fff;--ink:#141b2d;--mut:#5b6478;--line:#e2e7f1;--mutc:#9aa4bd;}}}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--ink);padding:26px 16px 60px}}
.wrap{{max-width:1000px;margin:0 auto}}h1{{font-size:22px;margin:0 0 2px;letter-spacing:-.3px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin-bottom:24px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px}}
.tval{{font-size:29px;font-weight:700;line-height:1}}.tlab{{color:var(--mut);font-size:11px;margin-top:6px;text-transform:uppercase;letter-spacing:.5px}}
.tile.hot .tval{{color:var(--hot)}}.tile.warm .tval{{color:var(--warm)}}.tile.grn .tval{{color:var(--grn)}}.tile.teal .tval{{color:var(--teal)}}
.ctl{{position:sticky;top:0;z-index:5;background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px 16px;margin-bottom:22px;display:grid;grid-template-columns:1fr 1fr;gap:16px 22px;align-items:center;box-shadow:0 4px 18px rgba(0,0,0,.18)}}
.ctl .cg{{min-width:0}}.ctl .cl{{font-size:13px;margin-bottom:8px}}.ctl .cl b{{font-variant-numeric:tabular-nums}}
.ctl input[type=range]{{width:100%;accent-color:var(--cool)}}
.ctl .tg{{font-size:13px;color:var(--mut);display:flex;align-items:center;gap:6px}}
.ctl .mi{{font-size:12px;color:var(--mut);text-align:right;font-variant-numeric:tabular-nums}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);margin:26px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:13px;margin-bottom:16px;overflow:hidden}}
.shd{{padding:13px 16px;font-weight:650;font-size:14px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.dot{{width:9px;height:9px;border-radius:50%;flex:none}}
.dot.hot{{background:var(--hot)}}.dot.warm{{background:var(--warm)}}.dot.cool{{background:var(--cool)}}.dot.grn{{background:var(--grn)}}.dot.teal{{background:var(--teal)}}.dot.gp{{background:var(--grn)}}
.shd small{{color:var(--mut);font-weight:400;margin-left:auto;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td{{padding:9px 14px;border-top:1px solid var(--line)}}
tr:first-child td{{border-top:none}}.tk{{font-weight:700}}.nm{{color:var(--mut)}}.sc{{color:var(--mut);font-size:12px}}
.pr{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.ct{{text-align:right}}
.pe{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink)}}
.pe .na{{color:var(--mutc)}}.pe .flag{{display:inline-block;margin-left:5px;font-size:10px;color:var(--warm);border:1px solid var(--warm);border-radius:5px;padding:0 4px;vertical-align:middle;opacity:.85}}
.pe .fwd{{display:block;font-size:10px;color:var(--mut)}}
.badge{{display:inline-block;min-width:26px;text-align:center;padding:2px 8px;border-radius:20px;font-weight:700;font-size:13px;color:#fff}}
.badge.hot{{background:var(--hot)}}.badge.warm{{background:var(--warm)}}.badge.cool{{background:var(--cool)}}.badge.grn{{background:var(--grn)}}.badge.teal{{background:var(--teal)}}
.badge .plus{{font-weight:400;font-size:11px;opacity:.85}}
.empty{{color:var(--mutc);text-align:center;padding:16px}}
.perf td{{text-align:center;font-variant-numeric:tabular-nums}}.perf .pl{{text-align:left;color:var(--ink);font-weight:500}}
.ph{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
.pv{{font-weight:700}}.pv .pn{{display:block;font-weight:400;font-size:11px;color:var(--mut)}}
.pv.gp{{color:var(--grn)}}.pv.gn{{color:var(--hot)}}.pv.gm{{color:var(--warm)}}
.note{{color:var(--mut);font-size:12px;line-height:1.6;margin-top:20px;border-top:1px solid var(--line);padding-top:14px}}
.note .na{{color:var(--mutc)}}
@media(max-width:640px){{.nm,.sc{{display:none}}.ctl{{grid-template-columns:1fr}}.ctl .mi{{text-align:left}}}}
</style></head><body><div class="wrap">
<h1>📉📈 Low-9 / High-9 Monitor</h1>
<div class="sub">TD Sequential setups (九转序列) · {html.escape(data['universe'])} · daily &amp; weekly · data as of {asof}</div>
<div class="tiles">{tile_html}</div>
{controls}
{perf_panel(P)}
<h2>🟢 Low 9 — potential bottoms (bounce up)</h2>
{low}
<h2>🔴 High 9 — potential tops (reverse / drop)</h2>
{high}
<div class="note">{pe_note}<b>How to read this:</b> A <b>low 9</b> completes after 9 straight bars each closing <b>below</b> the close 4 bars earlier (TD Buy Setup) — downtrend exhaustion, a possible bottom. A <b>high 9</b> completes after 9 straight bars each closing <b>above</b> the close 4 bars earlier (TD Sell Setup) — uptrend exhaustion, a possible top. Weekly signals are stronger and slower than daily. In the "extended" sections the badge reads <b>9 +N</b>: the setup completed its 9, and the trend has continued for N more bars since (days on daily, weeks on weekly) — i.e. the expected reversal hasn't happened yet. <b>Signal performance</b> backtests every completed 9 over the available history: the % is how often price moved the expected way (up after a low-9, down after a high-9), with average forward return and sample size. Note that in strong uptrends high-9 "sell" signals often keep rising, which the win-rates make visible. Scanned {data['scanned']} names, {data['errors']} fetch errors.<br><br>
Technical screen for research only — <b>not financial advice</b>. Signals fail often; do your own analysis.</div>
</div>{filter_js}</body></html>"""
    with open(path, "w") as f:
        f.write(doc)
    print("wrote", path, len(doc), "bytes")

if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2])
