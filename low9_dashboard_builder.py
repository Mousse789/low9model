#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from a low9/high9 scan JSON.

Layout, top to bottom, all open on load:
    tiles -> one-line performance headline -> ⭐ double-9 lists (low then high)
    -> LOW 9: fresh weekly + fresh daily -> HIGH 9: fresh weekly + fresh daily.
Only three things are folded: each side's "already extended" list, the full backtest
table, and the how-to-read note — each with its count or win rate on the summary line.

Extended setups older than EXT_MAX_WEEKLY weeks / EXT_MAX_DAILY days past their 9 are
dropped from the page as stale; the fold's summary reports how many were dropped.

Colour means one thing: GREEN = low side (expecting up), RED = high side (expecting
down), VIOLET = daily+weekly confluence. Solid badge = fresh 9, outline = extended.

Daily+weekly confluence ("double 9"): the same side signalling on BOTH timeframes.
A 1-2 bar discrepancy is allowed — one timeframe must have completed its 9, the other
must be at 7 or better. Tier "both" = both completed (the true double 9).

Optional P/E enrichment: if hit rows carry a "pe" field, a P/E column and interactive
sliders are rendered — low-9 tables keep value names (P/E <= threshold), high-9 tables
keep expensive names (P/E >= threshold). Names with no trailing earnings are always
shown and flagged.
"""
import json, sys, html

CONF_NEAR = 7
CONF_H = [5, 10, 20, 60]

# An "extended" setup is one whose 9 completed N bars ago and still hasn't reversed.
# Past these limits the signal is stale and is dropped from the page entirely
# (the count of what was dropped is still shown, so nothing disappears silently).
EXT_MAX_DAILY = 10    # trading days past the 9
EXT_MAX_WEEKLY = 4    # weeks past the 9

def prune_stale(rows, field):
    """Returns (kept, n_dropped) for an extended list."""
    lim = 9 + (EXT_MAX_WEEKLY if field.startswith("weekly") else EXT_MAX_DAILY)
    kept = [h for h in rows if h.get(field, 0) <= lim]
    return kept, len(rows) - len(kept)

# ---------- confluence ----------
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

def _cnum(v):
    return f"9+{v - 9}" if v > 9 else str(v)

def conf_chip(h, side):
    t = conf_tier(h, side)
    if not t:
        return ""
    d, w = h[f"daily_{side}"], h[f"weekly_{side}"]
    title = (f"{side}-9 on both timeframes — daily {d}, weekly {w}"
             + (" (both completed)" if t == "both" else " (one within 1-2 bars)"))
    return (f'<span class="cchip{" solid" if t == "both" else ""}" title="{title}">'
            f'D{_cnum(d)}·W{_cnum(w)}</span>')

# ---------- table rows ----------
def count_label(field, v):
    unit = "w" if field.startswith("weekly") else "d"
    if v > 9:
        return f'9&thinsp;<span class="plus">+{v - 9}{unit}</span>'
    return str(v)

def _pe_cell(h):
    pe, fwd = h.get("pe"), h.get("fwd_pe")
    if isinstance(pe, (int, float)):
        return f'<td class="pe" data-has="1">{pe:g}</td>'
    hint = f'<span class="fwd">fwd {fwd:g}</span>' if isinstance(fwd, (int, float)) else ""
    return (f'<td class="pe" data-has="0"><span class="na" title="no trailing (TTM) earnings">n/a</span>'
            f'<span class="flag">no earnings</span>{hint}</td>')

def _sort_conf_first(rows, side, field):
    """Confluence first, then the model score where low9_score.py supplied one,
    then raw setup count."""
    rank = {"both": 0, "near": 1, None: 2}
    return sorted(rows, key=lambda h: (rank[conf_tier(h, side)],
                                       -(h.get("score") or 0),
                                       -h.get(field, 0)))

def has_scores(rows):
    return any(isinstance(h.get("score"), (int, float)) for h in rows)

def _score_cell(h, scored):
    """0-100 model confidence from low9_score.py (weekly low-9 rows only)."""
    if not scored:
        return ""
    s = h.get("score")
    if not isinstance(s, (int, float)):
        return '<td class="cf"><span class="dash">–</span></td>'
    t = (h.get("tier") or "").lower()
    facts = ", ".join(h.get("factors") or [])
    title = f"model confidence {s}/100 ({h.get('tier') or '?'})" + (f" · {facts}" if facts else "")
    return f'<td class="cf"><span class="spill {t}" title="{html.escape(title)}">{s}</span></td>'

def _row_open(h, side):
    t = conf_tier(h, side)
    pe = h.get("pe")
    pe_attr = f"{pe:g}" if isinstance(pe, (int, float)) else ""
    noearn = "0" if isinstance(pe, (int, float)) else "1"
    rcls = f" {'conf2' if t == 'both' else 'conf'}" if t else ""
    return f'<tr class="row {side}{rcls}" data-pe="{pe_attr}" data-noearn="{noearn}">'

def _tail(rows, mx, cols=6):
    out = []
    if len(rows) > mx:
        out.append(f'<tr class="more"><td colspan="{cols}" class="empty">… +{len(rows)-mx} more</td></tr>')
    out.append(f'<tr class="emptyrow" style="display:none"><td colspan="{cols}" class="empty">'
               f'No names match the P/E filter</td></tr>')
    return out

def rows_html(rows, field, side, kind, mx=25):
    if not rows:
        return '<tr><td colspan="6" class="empty">None today</td></tr>'
    scored = has_scores(rows)
    cols = 7 if scored else 6
    rows = _sort_conf_first(rows, side, field)
    bcls = f"badge {side}" + ("" if kind == "fresh" else " out")
    out = []
    for h in rows[:mx]:
        out.append(
            _row_open(h, side)
            + _score_cell(h, scored)
            + f'<td class="tk">{html.escape(h["sym"])}{conf_chip(h, side)}</td>'
            f'<td class="nm">{html.escape(h["name"])}</td>'
            f'<td class="sc">{html.escape(h["sector"])}</td>'
            f'<td class="pr">${h["price"]:,.2f}</td>'
            f'{_pe_cell(h)}'
            f'<td class="ct"><span class="{bcls}">{count_label(field, h[field])}</span></td></tr>')
    return "\n".join(out + _tail(rows, mx, cols))

def conf_rows_html(rows, side, mx=30):
    """Rows for the ⭐ double-9 list — badge carries both counts."""
    if not rows:
        return '<tr><td colspan="6" class="empty">None today</td></tr>'
    scored = has_scores(rows)
    cols = 7 if scored else 6
    rows = _sort_conf_first(rows, side, f"weekly_{side}")
    out = []
    for h in rows[:mx]:
        t = conf_tier(h, side)
        if not t:
            continue
        d, w = h[f"daily_{side}"], h[f"weekly_{side}"]
        # the ⭐ list is the headline: never let the P/E slider empty it
        out.append(
            _row_open(h, side).replace('<tr class="row', '<tr data-nofilter="1" class="row')
            + _score_cell(h, scored)
            + f'<td class="tk">{html.escape(h["sym"])}</td>'
            f'<td class="nm">{html.escape(h["name"])}</td>'
            f'<td class="sc">{html.escape(h["sector"])}</td>'
            f'<td class="pr">${h["price"]:,.2f}</td>'
            f'{_pe_cell(h)}'
            f'<td class="ct"><span class="badge vio{"" if t == "both" else " out"}">'
            f'D{_cnum(d)}·W{_cnum(w)}</span></td></tr>')
    return "\n".join(out + _tail(rows, mx, cols))

# ---------- blocks ----------
def section(title, sub, rows, field, side, kind, cnt=None):
    c = f'<span class="cc {side}">{len(rows) if cnt is None else cnt}</span>'
    return (f'<section><div class="shd"><span class="dot {side}"></span>{title}{c}'
            f'<small>{sub}</small></div><table>{rows_html(rows, field, side, kind)}</table></section>')

def conf_section(title, sub, rows, side):
    both = sum(1 for h in rows if conf_tier(h, side) == "both")
    cnt = f'<span class="cc vio">{len(rows)}{f" · {both} true double 9" if both else ""}</span>'
    return (f'<section class="confsec"><div class="shd"><span class="dot vio"></span>{title}{cnt}'
            f'<small>{sub}</small></div><table>{conf_rows_html(rows, side)}</table></section>')

def fold(summary_html, body, cls=""):
    return (f'<details class="fold {cls}"><summary>{summary_html}</summary>'
            f'<div class="foldbody">{body}</div></details>')

# ---------- performance (one table, low and high colour-separated) ----------
def perf_table(P):
    """Merged backtest: confluence tiers + single-timeframe baselines, per side.

    Columns are trading-day horizons. Weekly-setup rows use the nearest weekly
    horizon (4w under 1 month, 12w under 3 months) and are blank at 1-2 weeks,
    which weekly bars simply don't resolve.
    """
    def cell(key):
        s = P.get(key)
        if not s:
            return '<td class="pv"><span class="dash">–</span></td>'
        wr = s["win_rate"]
        cls = "gp" if wr >= 55 else ("gn" if wr < 45 else "gm")
        med = f' · median {s["med_ret"]:+}%' if "med_ret" in s else ""
        return (f'<td class="pv {cls}" title="{s["n"]} past signals{med}">{wr}%'
                f'<span class="pn">{s["avg_ret"]:+}% avg · n={s["n"]:,}</span></td>')
    def drow(label, prefix, cls=""):
        return f'<tr class="{cls}"><td class="pl">{label}</td>' + "".join(cell(f"{prefix}_{h}") for h in CONF_H) + "</tr>"
    def wrow(label, prefix, cls=""):
        cells = ['<td class="pv"><span class="dash">–</span></td>'] * 2
        cells.append(cell(f"{prefix}_4"))
        cells.append(cell(f"{prefix}_12"))
        return f'<tr class="{cls}"><td class="pl">{label}</td>' + "".join(cells) + "</tr>"
    head = ('<tr><td class="pl"></td><td class="ph">1 week<br><i>5d</i></td><td class="ph">2 weeks<br><i>10d</i></td>'
            '<td class="ph">1 month<br><i>20d</i></td><td class="ph">3 months<br><i>60d</i></td></tr>')
    low = ('<tr class="grp low"><td class="pl" colspan="5">🟢 LOW 9 — did price go UP?</td></tr>'
           + drow("★★ Double 9 — daily 9 + weekly 9", "conf_buy_both", "vv")
           + drow("★ 9 + near — other timeframe 7–8", "conf_buy_near", "vv")
           + wrow("Weekly 9 alone", "weekly_buy", "base")
           + drow("Daily 9 alone", "daily_buy", "base"))
    high = ('<tr class="grp high"><td class="pl" colspan="5">🔴 HIGH 9 — did price go DOWN?</td></tr>'
            + drow("★★ Double 9 — daily 9 + weekly 9", "conf_sell_both", "vv")
            + drow("★ 9 + near — other timeframe 7–8", "conf_sell_near", "vv")
            + wrow("Weekly 9 alone", "weekly_sell", "base")
            + drow("Daily 9 alone", "daily_sell", "base"))
    note = ('<div class="pnote">Win rate = how often price moved the expected way. The number under it is the '
            '<i>raw</i> average price move, so on the high-9 half a negative average is the favourable one. '
            'Hover any cell for the median. Backtest covers ~2y of history across this universe; confluence rows '
            'count each episode once, from the day it first appeared.</div>')
    return f'<table class="perf">{head}{low}{high}</table>{note}'

def perf_headline(P):
    """One line that survives the fold. Shows every low-side baseline, not just the
    flattering one — on some universes weekly-9-alone beats the double 9."""
    b, w, d = P.get("conf_buy_both_60"), P.get("weekly_buy_12"), P.get("daily_buy_60")
    parts = []
    if b: parts.append(f'double 9: {b["win_rate"]}%')
    if w: parts.append(f'weekly alone: {w["win_rate"]}%')
    if d: parts.append(f'daily alone: {d["win_rate"]}%')
    if not parts:
        return '<b class="hl">Backtest</b>'
    return (f'<b class="hl">Low 9 over 3 months</b> <span class="hl2">— '
            + " · ".join(parts) + " went up</span>")

def high_caveat(P):
    """Shown beside the high-9 heading — the side is fully visible, but the backtest
    result travels with it rather than being buried in the note."""
    s = P.get("conf_sell_both_60") or P.get("daily_sell_60")
    if s:
        return f'<span class="h2n">backtest: {s["win_rate"]}% at 3 months — weakest side</span>'
    return ""

# ---------- controls ----------
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
      if(tr.dataset.nofilter==='1'){tr.style.display=''; return;}   // ⭐ double-9 list always shows
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
    matchinfo.innerHTML=vis+' of '+rows.length+' rows pass the P/E filter'+
      (cf?' · <span class="cfx">★ '+cf+' double 9</span>':'');
  }
  lowr.addEventListener('input',apply); highr.addEventListener('input',apply);
  showall.addEventListener('change',apply); apply();
})();
</script>"""

# ---------- page ----------
def build(data, path):
    C = data["cls"]; P = data.get("perf", {})
    asof = data["asof"][:10]
    has_pe = any("pe" in r for rows in C.values() for r in rows)
    n = lambda k: len(C.get(k, []))

    def conf_rows(side):
        """One row per confluent ticker. The same name appears in several buckets as
        separate copies and only the weekly-low copies carry a score — prefer those."""
        best = {}
        for rows in C.values():
            for r in rows:
                if not conf_tier(r, side):
                    continue
                cur = best.get(r["sym"])
                if cur is None or (isinstance(r.get("score"), (int, float))
                                   and not isinstance(cur.get("score"), (int, float))):
                    best[r["sym"]] = r
        return list(best.values())
    low_conf, high_conf = conf_rows("low"), conf_rows("high")

    tiles = [
        ("★ Low double 9", len(low_conf), "vio"),
        ("Fresh weekly low-9", n("weekly_low_9"), "low"),
        ("Fresh daily low-9", n("daily_low_9"), "low"),
        ("★ High double 9", len(high_conf), "high"),
    ]
    tile_html = "\n".join(
        f'<div class="tile {c}"><div class="tval">{v}</div><div class="tlab">{l}</div></div>'
        for l, v, c in tiles)

    # --- ⭐ double 9, both sides, at the very top ---
    hero = ""
    if low_conf or high_conf:
        hero = '<h2>⭐ Daily + weekly — the same 9 on both timeframes</h2>'
        if low_conf:
            hero += conf_section("🟢 Low 9 on daily AND weekly",
                                 "strongest bottom confirmation — always shown, the P/E slider does not apply here",
                                 low_conf, "low")
        if high_conf:
            hero += conf_section("🔴 High 9 on daily AND weekly",
                                 "strongest top confirmation — always shown, the P/E slider does not apply here",
                                 high_conf, "high")

    # --- fresh signals: open, both sides ---
    def side_block(side, wk_title, dy_title, wk_sub, dy_sub, ext_label):
        fresh = (section(wk_title, wk_sub, C[f"weekly_{side}_9"], f"weekly_{side}", side, "fresh")
                 + section(dy_title, dy_sub, C[f"daily_{side}_9"], f"daily_{side}", side, "fresh"))
        wk_ext, wk_drop = prune_stale(C[f"weekly_{side}_ext"], f"weekly_{side}")
        dy_ext, dy_drop = prune_stale(C[f"daily_{side}_ext"], f"daily_{side}")
        dropped = wk_drop + dy_drop
        stale = (f'<span class="stale">{dropped} dropped as stale</span>' if dropped else "")
        ext = fold(
            f'<span class="dot {side}"></span>{ext_label}'
            f'<span class="cc {side}">{len(wk_ext) + len(dy_ext)}</span>{stale}'
            f'<small>the 9 completed and price kept going — hidden past '
            f'{EXT_MAX_WEEKLY}w / {EXT_MAX_DAILY}d</small>',
            section("Weekly extended", "badge shows weeks since the 9", wk_ext, f"weekly_{side}", side, "ext")
            + section("Daily extended", "badge shows days since the 9", dy_ext, f"daily_{side}", side, "ext"))
        return fresh + ext

    low_block = side_block("low",
                           "Fresh weekly low-9", "Fresh daily low-9",
                           "9 weekly closes below the close 4 weeks earlier",
                           "9 daily closes below the close 4 days earlier",
                           "Low 9 already extended")
    high_block = side_block("high",
                            "Fresh weekly high-9", "Fresh daily high-9",
                            "9 weekly closes above the close 4 weeks earlier",
                            "9 daily closes above the close 4 days earlier",
                            "High 9 already extended")

    perf_fold = fold(f'<span class="dot vio"></span>{perf_headline(P)}'
                     f'<small>tap for the full backtest — both sides, all horizons</small>',
                     perf_table(P), cls="perffold")

    any_scored = any(isinstance(r.get("score"), (int, float)) for rows in C.values() for r in rows)
    base = data.get("model_base_win")
    score_note = ("<b>Confidence score (weekly low-9 only):</b> the coloured 0–100 pill on the left of each row is the "
                  "model's estimate of the chance this name's price is higher 8 weeks out, learned from ~2y of history "
                  "(it rewards a deeper drop, bigger cap, calmer stock, stronger sector). "
                  '<span class="spill high">≥78</span> high · <span class="spill medium">65–77</span> medium · '
                  '<span class="spill low">&lt;65</span> low. '
                  + (f"Baseline for all weekly low-9s ≈ {base}%. " if base else "")
                  + "Hover a pill for the factors behind it. Rows without a score (daily-only signals) show "
                    "<span class='na'>–</span> — the model only scores weekly low-9s.<br><br>") if any_scored else ""
    pe_note = ("<b>P/E filter:</b> the sliders keep only reasonably-valued names in the low-9 lists and only "
               "richly-valued names in the high-9 lists. P/E is trailing (TTM). Names with no trailing earnings "
               "show <span class='na'>n/a</span> and are always displayed and flagged — never hidden. ") if has_pe else ""
    note_fold = fold(
        '<span class="dot mut"></span>How to read this<small>definitions, badges, caveats</small>',
        f'<div class="note">{score_note}{pe_note}A <b>low 9</b> completes after 9 straight bars each closing <b>below</b> the '
        'close 4 bars earlier (TD Buy Setup) — downtrend exhaustion, a possible bottom. A <b>high 9</b> completes '
        'after 9 straight bars each closing <b>above</b> the close 4 bars earlier (TD Sell Setup) — uptrend '
        'exhaustion, a possible top. Weekly signals are stronger and slower than daily.<br><br>'
        '<b>Colour:</b> <span class="k low">green</span> = low side, expecting up · '
        '<span class="k high">red</span> = high side, expecting down · '
        '<span class="k vio">violet</span> = the same 9 on both timeframes. A solid badge is a fresh 9; an outlined '
        'badge means the 9 completed N bars ago and price kept going (<b>9 +N</b>).<br><br>'
        '<b>★ Double 9:</b> the chip reads <b>D<i>daily</i>·W<i>weekly</i></b> (e.g. <span class="k vio">D9·W8</span>). '
        'A 1–2 bar discrepancy is allowed: one timeframe has completed its 9, the other is at 7 or better. '
        'Solid chip = both completed. These names are tinted violet and sorted to the top of every table.<br><br>'
        f'Scanned {data["scanned"]:,} names, {data["errors"]} fetch errors. '
        f'Approaching 7–8: low {n("daily_low_near")}d/{n("weekly_low_near")}w, '
        f'high {n("daily_high_near")}d/{n("weekly_high_near")}w.<br><br>'
        'Technical screen for research only — <b>not financial advice</b>. Signals fail often; do your own analysis.'
        '</div>')

    high_caveat_html = high_caveat(P)
    controls = CONTROLS if has_pe else ""
    filter_js = FILTER_JS if has_pe else ""

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Low-9 / High-9 Monitor</title><style>
:root{{--bg:#0f1420;--card:#182031;--ink:#e8edf7;--mut:#8a97b0;--line:#26304a;--mutc:#5a6683;
--low:#37d39b;--high:#ff5470;--vio:#9085e9;--warm:#ffa23a;
--conf1:rgba(144,133,233,.10);--conf2:rgba(144,133,233,.20);}}
@media(prefers-color-scheme:light){{:root{{--bg:#f4f6fb;--card:#fff;--ink:#141b2d;--mut:#5b6478;--line:#e2e7f1;--mutc:#9aa4bd;
--low:#0f9d6b;--high:#e0294c;--vio:#4a3aa7;--conf1:rgba(74,58,167,.07);--conf2:rgba(74,58,167,.15);}}}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:var(--bg);color:var(--ink);padding:26px 16px 60px}}
.wrap{{max-width:1000px;margin:0 auto}}h1{{font-size:22px;margin:0 0 2px;letter-spacing:-.3px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:11px;margin-bottom:20px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px}}
.tval{{font-size:29px;font-weight:700;line-height:1}}
.tlab{{color:var(--mut);font-size:11px;margin-top:6px;text-transform:uppercase;letter-spacing:.5px}}
.tile.low .tval{{color:var(--low)}}.tile.high .tval{{color:var(--high)}}.tile.vio .tval{{color:var(--vio)}}
.tile.vio{{border-color:var(--vio);background:linear-gradient(180deg,var(--conf1),transparent)}}
.ctl{{position:sticky;top:0;z-index:5;background:var(--card);border:1px solid var(--line);border-radius:13px;
padding:15px 16px;margin-bottom:18px;display:grid;grid-template-columns:1fr 1fr;gap:14px 22px;align-items:center;
box-shadow:0 4px 18px rgba(0,0,0,.18)}}
.ctl .cg{{min-width:0}}.ctl .cl{{font-size:13px;margin-bottom:8px}}.ctl .cl b{{font-variant-numeric:tabular-nums}}
.ctl input[type=range]{{width:100%;accent-color:var(--vio)}}
.ctl .tg{{font-size:13px;color:var(--mut);display:flex;align-items:center;gap:6px}}
.ctl .mi{{font-size:12px;color:var(--mut);text-align:right;font-variant-numeric:tabular-nums}}
.ctl .cfx{{color:var(--vio);font-weight:600}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);margin:24px 0 10px;
border-bottom:1px solid var(--line);padding-bottom:6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:13px;margin-bottom:14px;overflow:hidden}}
section.confsec{{border-color:var(--vio);box-shadow:0 0 0 1px var(--conf1)}}
.shd,summary{{padding:13px 16px;font-weight:650;font-size:14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.shd{{border-bottom:1px solid var(--line)}}
.shd small,summary small{{color:var(--mut);font-weight:400;margin-left:auto;font-size:12px}}
.dot{{width:9px;height:9px;border-radius:50%;flex:none}}
.dot.low{{background:var(--low)}}.dot.high{{background:var(--high)}}.dot.vio{{background:var(--vio)}}.dot.mut{{background:var(--mutc)}}
.cc{{font-weight:700;font-size:11.5px;border-radius:6px;padding:1px 7px;border:1px solid currentColor}}
.cc.low{{color:var(--low)}}.cc.high{{color:var(--high)}}.cc.vio{{color:var(--vio)}}
.fold{{background:var(--card);border:1px solid var(--line);border-radius:13px;margin-bottom:14px;overflow:hidden}}
.fold summary{{cursor:pointer;list-style:none;user-select:none}}
.fold summary::-webkit-details-marker{{display:none}}
.fold summary::after{{content:'▸';margin-left:8px;color:var(--mut);font-size:12px;order:9}}
.fold[open] summary::after{{content:'▾'}}
.fold[open] summary{{border-bottom:1px solid var(--line)}}
.fold summary:hover{{background:rgba(127,127,127,.06)}}
.foldbody{{padding:14px 16px 4px}}
.foldbody section{{background:transparent;border-color:var(--line)}}
.perffold summary .hl{{font-weight:700}}.perffold summary .hl2{{color:var(--mut);font-weight:400;font-size:13px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
td{{padding:9px 14px;border-top:1px solid var(--line)}}tr:first-child td{{border-top:none}}
.tk{{font-weight:700}}.nm{{color:var(--mut)}}.sc{{color:var(--mut);font-size:12px}}
.pr{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.ct{{text-align:right}}
.pe{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink)}}
.pe .na{{color:var(--mutc)}}
.pe .flag{{display:inline-block;margin-left:5px;font-size:10px;color:var(--warm);border:1px solid var(--warm);
border-radius:5px;padding:0 4px;vertical-align:middle;opacity:.85}}
.pe .fwd{{display:block;font-size:10px;color:var(--mut)}}
tr.conf td{{background:var(--conf1)}}tr.conf2 td{{background:var(--conf2)}}
tr.conf td.tk,tr.conf2 td.tk{{box-shadow:inset 3px 0 0 var(--vio)}}
.cchip{{display:inline-block;margin-left:6px;font-size:9.5px;font-weight:700;color:var(--vio);
border:1px solid var(--vio);border-radius:5px;padding:0 4px;vertical-align:middle;white-space:nowrap;
font-variant-numeric:tabular-nums}}
.cchip.solid{{background:var(--vio);color:#fff}}
.badge{{display:inline-block;min-width:26px;text-align:center;padding:2px 9px;border-radius:20px;
font-weight:700;font-size:13px;color:#fff;font-variant-numeric:tabular-nums}}
.badge.low{{background:var(--low)}}.badge.high{{background:var(--high)}}.badge.vio{{background:var(--vio)}}
.badge.out{{background:transparent;border:1px solid currentColor}}
.badge.low.out{{color:var(--low)}}.badge.high.out{{color:var(--high)}}.badge.vio.out{{color:var(--vio)}}
.badge .plus{{font-weight:400;font-size:11px;opacity:.85}}
h2 .h2n{{float:right;text-transform:none;letter-spacing:0;font-size:11.5px;color:var(--high);opacity:.85}}
.stale{{font-size:11px;color:var(--mutc);border:1px dashed var(--mutc);border-radius:6px;padding:1px 6px}}
.cf{{width:56px;text-align:center}}
.spill{{display:inline-block;min-width:34px;text-align:center;padding:3px 7px;border-radius:8px;
font-weight:700;font-size:13px;font-variant-numeric:tabular-nums;color:#fff}}
.spill.high{{background:var(--low)}}.spill.medium{{background:var(--warm)}}.spill.low{{background:var(--mutc)}}
.cf .dash{{color:var(--mutc)}}
.empty{{color:var(--mutc);text-align:center;padding:16px}}
.perf td{{text-align:center;font-variant-numeric:tabular-nums;padding:9px 10px}}
.perf .pl{{text-align:left;color:var(--ink);font-weight:500}}
.perf .ph{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}}
.perf .ph i{{font-style:normal;opacity:.6;font-size:10px}}
.perf .grp td{{font-size:11.5px;text-transform:uppercase;letter-spacing:.8px;font-weight:700;
padding-top:14px;border-top:2px solid var(--line)}}
.perf .grp.low td{{color:var(--low)}}.perf .grp.high td{{color:var(--high)}}
.perf .vv .pl{{color:var(--vio);font-weight:650}}
.perf .base td{{color:var(--mut)}}.perf .base .pv{{font-weight:600}}
.pv{{font-weight:700}}.pv .pn{{display:block;font-weight:400;font-size:11px;color:var(--mut)}}
.pv.gp{{color:var(--low)}}.pv.gn{{color:var(--high)}}.pv.gm{{color:var(--warm)}}
.pv .dash{{color:var(--mutc)}}
.pnote{{color:var(--mut);font-size:11.5px;line-height:1.6;padding:12px 10px 14px}}
.note{{color:var(--mut);font-size:12px;line-height:1.65;padding-bottom:12px}}
.note .na{{color:var(--mutc)}}
.note .k{{display:inline-block;font-size:10px;font-weight:700;border:1px solid currentColor;border-radius:5px;
padding:0 5px;vertical-align:middle}}
.note .k.low{{color:var(--low)}}.note .k.high{{color:var(--high)}}.note .k.vio{{color:var(--vio)}}
@media(max-width:640px){{.nm,.sc{{display:none}}.ctl{{grid-template-columns:1fr}}.ctl .mi{{text-align:left}}
.shd small,summary small{{margin-left:0;width:100%}}}}
</style></head><body><div class="wrap">
<h1>📉📈 Low-9 / High-9 Monitor</h1>
<div class="sub">TD Sequential setups (九转序列) · {html.escape(data['universe'])} · daily &amp; weekly · data as of {asof}</div>
<div class="tiles">{tile_html}</div>
{controls}
{perf_fold}
{hero}
<h2>🟢 Low 9 — potential bottoms (bounce up)</h2>
{low_block}
<h2>🔴 High 9 — potential tops (reverse / drop){high_caveat_html}</h2>
{high_block}
{note_fold}
</div>{filter_js}</body></html>"""
    with open(path, "w") as f:
        f.write(doc)
    print("wrote", path, len(doc), "bytes")

if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2])
