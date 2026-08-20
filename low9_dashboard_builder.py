#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from a low9/high9 scan JSON.

Supports optional P/E enrichment: if hit rows carry a "pe" field, a P/E column
and interactive P/E sliders are rendered — low-9 (bottom/buy) tables keep value
names (P/E <= threshold), high-9 (top/sell) tables keep expensive names
(P/E >= threshold). Names with no trailing earnings are always shown and flagged.

Daily+weekly confluence ("double 9"): rows where the same side is signalling on
BOTH timeframes are tinted violet, chipped with both counts (D9·W8), and sorted to
the top of every table. A 1-2 bar discrepancy is allowed: one timeframe must have
completed its 9, the other must be at 7 or better. Dedicated ★ sections list them,
and — when the scan JSON carries conf_* backtest keys — a performance panel scores
these events against the plain single-timeframe 9.
"""
import json, sys, html

CONF_NEAR = 7

def conf_tier(h, side):
    """'both' = daily and weekly both >= 9; 'near' = one >= 9, other 7-8; else None."""
    d, w = h.get(f"daily_{side}"), h.get(f"weekly_{side}")
    if not isinstance(d, int) or not isinstance(w, int):
        return None
    if d >= 9 and w >= 9:
        return "both"
    if min(d, w) >= CONF_NEAR and max(d, w) >= 9:
        return "near"
    return None

def count_label(field, v):
    unit = "w" if field.startswith("weekly") else "d"
    if v > 9:
        return f'9&thinsp;<span class="plus">+{v - 9}{unit}</span>'
    return str(v)

def _cnum(v):
    return f"9+{v - 9}" if v > 9 else str(v)

def conf_chip(h, side):
    t = conf_tier(h, side)
    if not t:
        return ""
    d, w = h[f"daily_{side}"], h[f"weekly_{side}"]
    title = (f"{side}-9 on both timeframes — daily {d}, weekly {w}"
             + (" (both completed)" if t == "both" else " (one within 1-2 bars)"))
    cls = "cchip solid" if t == "both" else "cchip"
    return f'<span class="{cls}" title="{title}">D{_cnum(d)}·W{_cnum(w)}</span>'

def _pe_cell(h):
    pe = h.get("pe")
    fwd = h.get("fwd_pe")
    if isinstance(pe, (int, float)):
        return f'<td class="pe" data-has="1">{pe:g}</td>'
    hint = f'<span class="fwd">fwd {fwd:g}</span>' if isinstance(fwd, (int, float)) else ""
    return (f'<td class="pe" data-has="0"><span class="na" title="no trailing (TTM) earnings">n/a</span>'
            f'<span class="flag">no earnings</span>{hint}</td>')

def _sort_conf_first(rows, side, field):
    rank = {"both": 0, "near": 1, None: 2}
    return sorted(rows, key=lambda h: (rank[conf_tier(h, side)], -h.get(field, 0)))

def rows_html(rows, field, badge, mx=25):
    side = "low" if "low" in field else "high"
    if not rows:
        return '<tr><td colspan="6" class="empty">None today</td></tr>'
    rows = _sort_conf_first(rows, side, field)
    out = []
    for h in rows[:mx]:
        pe = h.get("pe")
        pe_attr = f'{pe:g}' if isinstance(pe, (int, float)) else ""
        noearn = "0" if isinstance(pe, (int, float)) else "1"
        t = conf_tier(h, side)
        rcls = f" {'conf2' if t == 'both' else 'conf'}" if t else ""
        out.append(
            f'<tr class="row {side}{rcls}" data-pe="{pe_attr}" data-noearn="{noearn}">'
            f'<td class="tk">{html.escape(h["sym"])}{conf_chip(h, side)}</td>'
            f'<td class="nm">{html.escape(h["name"])}</td>'
            f'<td class="sc">{html.escape(h["sector"])}</td>'
            f'<td class="pr">${h["price"]:,.2f}</td>'
            f'{_pe_cell(h)}'
            f'<td class="ct"><span class="badge {badge}">{count_label(field, h[field])}</span></td></tr>'
        )
    if len(rows) > mx:
        out.append(f'<tr class="more"><td colspan="6" class="empty">… +{len(rows)-mx} more</td></tr>')
    # hidden row shown by JS when the P/E filter hides every data row
    out.append('<tr class="emptyrow" style="display:none"><td colspan="6" class="empty">No names match the P/E filter</td></tr>')
    return "\n".join(out)

def conf_rows_html(rows, side, mx=30):
    """Rows for the dedicated ★ daily+weekly sections — badge carries both counts."""
    if not rows:
        return '<tr><td colspan="6" class="empty">None today</td></tr>'
    rows = _sort_conf_first(rows, side, f"weekly_{side}")
    out = []
    for h in rows[:mx]:
        t = conf_tier(h, side)
        if not t:
            continue
        pe = h.get("pe")
        pe_attr = f'{pe:g}' if isinstance(pe, (int, float)) else ""
        noearn = "0" if isinstance(pe, (int, float)) else "1"
        d, w = h[f"daily_{side}"], h[f"weekly_{side}"]
        bcls = "badge vio" if t == "both" else "badge vion"
        out.append(
            f'<tr class="row {side} {"conf2" if t == "both" else "conf"}" data-pe="{pe_attr}" data-noearn="{noearn}">'
            f'<td class="tk">{html.escape(h["sym"])}</td>'
            f'<td class="nm">{html.escape(h["name"])}</td>'
            f'<td class="sc">{html.escape(h["sector"])}</td>'
            f'<td class="pr">${h["price"]:,.2f}</td>'
            f'{_pe_cell(h)}'
            f'<td class="ct"><span class="{bcls}">D{_cnum(d)}·W{_cnum(w)}</span></td></tr>'
        )
    if len(rows) > mx:
        out.append(f'<tr class="more"><td colspan="6" class="empty">… +{len(rows)-mx} more</td></tr>')
    out.append('<tr class="emptyrow" style="display:none"><td colspan="6" class="empty">No names match the P/E filter</td></tr>')
    return "\n".join(out)

def section(title, sub, dot, rows, field, badge):
    return (f'<section><div class="shd"><span class="dot {dot}"></span>{title}'
            f'<small>{sub}</small></div><table>{rows_html(rows, field, badge)}</table></section>')

def conf_section(title, sub, rows, side):
    both = sum(1 for h in rows if conf_tier(h, side) == "both")
    cnt = (f'<span class="cc">{both} true double 9</span>' if both else "")
    return (f'<section class="confsec"><div class="shd"><span class="dot vio"></span>{title}{cnt}'
            f'<small>{sub}</small></div><table>{conf_rows_html(rows, side)}</table></section>')

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

CONF_H = [5, 10, 20, 60]

def conf_perf_panel(perf):
    """Backtest of daily+weekly confluence events. Empty string if the scan JSON predates it."""
    if not any(k.startswith("conf_") for k in perf):
        return ""
    def cell(prefix, h):
        s = perf.get(f"{prefix}_{h}")
        if not s:
            return '<td class="pv">–</td>'
        wr = s["win_rate"]
        cls = "gp" if wr >= 55 else ("gn" if wr < 45 else "gm")
        med = f' · median {s["med_ret"]:+}%' if "med_ret" in s else ""
        return (f'<td class="pv {cls}" title="{s["n"]} past signals{med}">{wr}%'
                f'<span class="pn">{s["avg_ret"]:+}% avg · n={s["n"]:,}</span></td>')
    def row(label, prefix, cls=""):
        return (f'<tr class="{cls}"><td class="pl">{label}</td>'
                + "".join(cell(prefix, h) for h in CONF_H) + "</tr>")
    return f"""<section><div class="shd"><span class="dot vio"></span>★ Daily + weekly confluence — backtested
<small>every past day a name first showed the same 9 on both timeframes, and what price did next (~2y history).
Win rate = moved the expected way; the average below it is the raw price move, so on the high-9 rows a negative average is the favourable one.</small></div>
<table class="perf conf">
<tr><td class="pl"></td><td class="ph">1 week<br>5d</td><td class="ph">2 weeks<br>10d</td><td class="ph">1 month<br>20d</td><td class="ph">3 months<br>60d</td></tr>
{row("★★ Low double 9 — daily 9 + weekly 9", "conf_buy_both", "vv")}
{row("★ Low 9 + near — other timeframe 7–8", "conf_buy_near", "vv")}
{row("Low 9 daily alone — every daily 9", "daily_buy", "base")}
{row("★★ High double 9 — daily 9 + weekly 9", "conf_sell_both", "vv gap")}
{row("★ High 9 + near — other timeframe 7–8", "conf_sell_near", "vv")}
{row("High 9 daily alone — every daily 9", "daily_sell", "base")}
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
      else if(noearn||pe===null||isNaN(pe)) vis=true; // always show flagged / missing
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
    var cf=rows.filter(function(r){return r.style.display!=='none' &&
      (r.classList.contains('conf')||r.classList.contains('conf2'));}).length;
    matchinfo.innerHTML=vis+' of '+rows.length+' signal rows shown'+
      (cf?' · <span class="cfx">★ '+cf+' daily+weekly</span>':'');
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
    n = lambda k: len(C.get(k, []))

    # confluence sets (recomputed here so older scan JSONs work too)
    def conf_rows(side):
        seen, out = set(), []
        for key, rows in C.items():
            for r in rows:
                if conf_tier(r, side) and r["sym"] not in seen:
                    seen.add(r["sym"]); out.append(r)
        return out
    low_conf, high_conf = conf_rows("low"), conf_rows("high")

    tiles = [
        ("Fresh weekly low-9", n("weekly_low_9"), "hot"),
        ("Fresh daily low-9", n("daily_low_9"), "warm"),
        ("★ Low 9 daily + weekly", len(low_conf), "vio"),
        ("Fresh weekly high-9", n("weekly_high_9"), "grn"),
        ("Fresh daily high-9", n("daily_high_9"), "teal"),
        ("★ High 9 daily + weekly", len(high_conf), "vio"),
        ("Low approaching 7–8", n("daily_low_near") + n("weekly_low_near"), "mut"),
        ("Scanned", data["scanned"], "mut"),
    ]
    tile_html = "\n".join(
        f'<div class="tile {c}"><div class="tval">{v}</div><div class="tlab">{l}</div></div>'
        for l, v, c in tiles)

    conf_html = ""
    if low_conf or high_conf:
        conf_html = ('<h2>⭐ Daily + weekly — same 9 on both timeframes</h2>'
                     + conf_section("🟢 Low 9 on daily AND weekly",
                                    "strongest bottom confirmation — badge shows both counts (daily · weekly)",
                                    low_conf, "low")
                     + conf_section("🔴 High 9 on daily AND weekly",
                                    "strongest top confirmation — badge shows both counts (daily · weekly)",
                                    high_conf, "high"))

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
--hot:#ff5470;--warm:#ffa23a;--cool:#3aa0ff;--grn:#37d39b;--teal:#22b8cf;--mutc:#5a6683;
--vio:#9085e9;--conf1:rgba(144,133,233,.10);--conf2:rgba(144,133,233,.20);}}
@media(prefers-color-scheme:light){{:root{{--bg:#f4f6fb;--card:#fff;--ink:#141b2d;--mut:#5b6478;--line:#e2e7f1;--mutc:#9aa4bd;
--vio:#4a3aa7;--conf1:rgba(74,58,167,.07);--conf2:rgba(74,58,167,.15);}}}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--ink);padding:26px 16px 60px}}
.wrap{{max-width:1000px;margin:0 auto}}h1{{font-size:22px;margin:0 0 2px;letter-spacing:-.3px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin-bottom:24px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px}}
.tval{{font-size:29px;font-weight:700;line-height:1}}.tlab{{color:var(--mut);font-size:11px;margin-top:6px;text-transform:uppercase;letter-spacing:.5px}}
.tile.hot .tval{{color:var(--hot)}}.tile.warm .tval{{color:var(--warm)}}.tile.grn .tval{{color:var(--grn)}}.tile.teal .tval{{color:var(--teal)}}
.tile.vio .tval{{color:var(--vio)}}.tile.vio{{border-color:var(--vio);background:linear-gradient(180deg,var(--conf1),transparent)}}
.ctl{{position:sticky;top:0;z-index:5;background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px 16px;margin-bottom:22px;display:grid;grid-template-columns:1fr 1fr;gap:16px 22px;align-items:center;box-shadow:0 4px 18px rgba(0,0,0,.18)}}
.ctl .cg{{min-width:0}}.ctl .cl{{font-size:13px;margin-bottom:8px}}.ctl .cl b{{font-variant-numeric:tabular-nums}}
.ctl input[type=range]{{width:100%;accent-color:var(--cool)}}
.ctl .tg{{font-size:13px;color:var(--mut);display:flex;align-items:center;gap:6px}}
.ctl .mi{{font-size:12px;color:var(--mut);text-align:right;font-variant-numeric:tabular-nums}}
.ctl .cfx{{color:var(--vio);font-weight:600}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);margin:26px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:13px;margin-bottom:16px;overflow:hidden}}
section.confsec{{border-color:var(--vio)}}
.shd{{padding:13px 16px;font-weight:650;font-size:14px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.dot{{width:9px;height:9px;border-radius:50%;flex:none}}
.dot.hot{{background:var(--hot)}}.dot.warm{{background:var(--warm)}}.dot.cool{{background:var(--cool)}}.dot.grn{{background:var(--grn)}}.dot.teal{{background:var(--teal)}}.dot.gp{{background:var(--grn)}}.dot.vio{{background:var(--vio)}}
.shd small{{color:var(--mut);font-weight:400;margin-left:auto;font-size:12px}}
.shd .cc{{color:var(--vio);font-weight:700;font-size:11.5px;border:1px solid var(--vio);border-radius:6px;padding:1px 6px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td{{padding:9px 14px;border-top:1px solid var(--line)}}
tr:first-child td{{border-top:none}}.tk{{font-weight:700}}.nm{{color:var(--mut)}}.sc{{color:var(--mut);font-size:12px}}
.pr{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.ct{{text-align:right}}
.pe{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink)}}
.pe .na{{color:var(--mutc)}}.pe .flag{{display:inline-block;margin-left:5px;font-size:10px;color:var(--warm);border:1px solid var(--warm);border-radius:5px;padding:0 4px;vertical-align:middle;opacity:.85}}
.pe .fwd{{display:block;font-size:10px;color:var(--mut)}}
tr.conf td{{background:var(--conf1)}}tr.conf2 td{{background:var(--conf2)}}
tr.conf td.tk,tr.conf2 td.tk{{box-shadow:inset 3px 0 0 var(--vio)}}
.cchip{{display:inline-block;margin-left:6px;font-size:9.5px;font-weight:700;color:var(--vio);border:1px solid var(--vio);border-radius:5px;padding:0 4px;vertical-align:middle;white-space:nowrap;font-variant-numeric:tabular-nums}}
.cchip.solid{{background:var(--vio);color:#fff}}
.badge{{display:inline-block;min-width:26px;text-align:center;padding:2px 8px;border-radius:20px;font-weight:700;font-size:13px;color:#fff}}
.badge.hot{{background:var(--hot)}}.badge.warm{{background:var(--warm)}}.badge.cool{{background:var(--cool)}}.badge.grn{{background:var(--grn)}}.badge.teal{{background:var(--teal)}}
.badge.vio{{background:var(--vio);font-variant-numeric:tabular-nums}}
.badge.vion{{background:transparent;color:var(--vio);border:1px solid var(--vio);font-variant-numeric:tabular-nums}}
.badge .plus{{font-weight:400;font-size:11px;opacity:.85}}
.empty{{color:var(--mutc);text-align:center;padding:16px}}
.perf td{{text-align:center;font-variant-numeric:tabular-nums}}.perf .pl{{text-align:left;color:var(--ink);font-weight:500}}
.ph{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
.pv{{font-weight:700}}.pv .pn{{display:block;font-weight:400;font-size:11px;color:var(--mut)}}
.pv.gp{{color:var(--grn)}}.pv.gn{{color:var(--hot)}}.pv.gm{{color:var(--warm)}}
.perf.conf .vv .pl{{color:var(--vio);font-weight:650}}
.perf.conf .base td{{color:var(--mut)}}.perf.conf .base .pv{{font-weight:500}}
.perf.conf .gap td{{border-top:2px solid var(--line)}}
.note{{color:var(--mut);font-size:12px;line-height:1.6;margin-top:20px;border-top:1px solid var(--line);padding-top:14px}}
.note .na{{color:var(--mutc)}}.note .k{{display:inline-block;font-size:9.5px;font-weight:700;color:var(--vio);border:1px solid var(--vio);border-radius:5px;padding:0 4px;vertical-align:middle}}
.note .k.solid{{background:var(--vio);color:#fff}}
@media(max-width:640px){{.nm,.sc{{display:none}}.ctl{{grid-template-columns:1fr}}.ctl .mi{{text-align:left}}}}
</style></head><body><div class="wrap">
<h1>📉📈 Low-9 / High-9 Monitor</h1>
<div class="sub">TD Sequential setups (九转序列) · {html.escape(data['universe'])} · daily &amp; weekly · data as of {asof}</div>
<div class="tiles">{tile_html}</div>
{controls}
{conf_perf_panel(P)}
{perf_panel(P)}
{conf_html}
<h2>🟢 Low 9 — potential bottoms (bounce up)</h2>
{low}
<h2>🔴 High 9 — potential tops (reverse / drop)</h2>
{high}
<div class="note">{pe_note}<b>How to read this:</b> A <b>low 9</b> completes after 9 straight bars each closing <b>below</b> the close 4 bars earlier (TD Buy Setup) — downtrend exhaustion, a possible bottom. A <b>high 9</b> completes after 9 straight bars each closing <b>above</b> the close 4 bars earlier (TD Sell Setup) — uptrend exhaustion, a possible top. Weekly signals are stronger and slower than daily. In the "extended" sections the badge reads <b>9 +N</b>: the setup completed its 9, and the trend has continued for N more bars since (days on daily, weeks on weekly) — i.e. the expected reversal hasn't happened yet. <b>Signal performance</b> backtests every completed 9 over the available history: the % is how often price moved the expected way (up after a low-9, down after a high-9), with average forward return and sample size. Note that in strong uptrends high-9 "sell" signals often keep rising, which the win-rates make visible. Scanned {data['scanned']} names, {data['errors']} fetch errors.<br><br>
<b>★ Daily + weekly (violet rows):</b> the same side is signalling on <b>both</b> timeframes — the strongest confirmation in this screen. The chip reads <b>D<i>daily</i>·W<i>weekly</i></b> (e.g. <span class="k">D9·W8</span>). A 1–2 bar discrepancy is allowed: at least one timeframe has completed its 9, the other is at 7 or better. <span class="k solid">Solid chip</span> = both timeframes completed their 9 (darkest tint); <span class="k">outlined chip</span> = one completed, the other is 1–2 bars away. These names sort to the top of every table and get their own ⭐ sections above.<br><br>
Technical screen for research only — <b>not financial advice</b>. Signals fail often; do your own analysis.</div>
</div>{filter_js}</body></html>"""
    with open(path, "w") as f:
        f.write(doc)
    print("wrote", path, len(doc), "bytes")

if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2])
