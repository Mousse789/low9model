#!/usr/bin/env python3
"""Low-9 / High-9 scanner (TD Sequential setups, 九转序列) for US stocks — daily + weekly.

LOW 9  (TD Buy Setup):  9 consecutive bars each close BELOW the close 4 bars earlier.
                        Downtrend exhaustion -> potential BOTTOM / bounce up.
HIGH 9 (TD Sell Setup): 9 consecutive bars each close ABOVE the close 4 bars earlier.
                        Uptrend exhaustion  -> potential TOP / drop.

DAILY + WEEKLY CONFLUENCE ("double 9"): the same side signalling on both timeframes
at once. A 1-2 bar discrepancy is allowed — at least one timeframe has completed its
9 (count >= 9) and the other is at 7 or better. Two tiers:
    both  — daily >= 9 AND weekly >= 9   (the true double 9)
    near  — one >= 9, the other at 7-8
Confluence events are backtested separately: for every historical day a confluence
first appeared, the forward return over 5/10/20/60 trading days is logged, so the
dashboard can show whether stacking the timeframes actually beats a single-timeframe 9.

Data: Yahoo chart API (daily bars); weekly bars resampled locally. Standard library only.
"""
import sys, time, json, csv, io, re, argparse, urllib.request, statistics
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]

DAILY_H = [5, 10, 20, 60]   # forward horizons (trading days) for the daily backtest
WEEKLY_H = [4, 8, 12]       # forward horizons (weeks) for the weekly backtest
CONF_H = [5, 10, 20, 60]    # forward horizons (trading days) for the confluence backtest

CONF_NEAR = 7               # tolerance: the lagging timeframe must be at 7 or better

def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# ---------- universe ----------
def get_sp500():
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    rows = list(csv.DictReader(io.StringIO(http_get(url).decode())))
    return [(r["Symbol"].strip(), r["Security"].strip(), r["GICS Sector"].strip()) for r in rows]

NASDAQ_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nasdaq/nasdaq_full_tickers.json"
NYSE_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nyse/nyse_full_tickers.json"

def _clean_name(nm):
    for suf in (" Common Stock", " Class A Common Stock", " Class B Common Stock",
                " Ordinary Shares", " Common Shares", " Class A Ordinary Shares",
                " American Depositary Shares", " Class A common stock", " Inc.", ", Inc."):
        if nm.endswith(suf):
            nm = nm[: -len(suf)]
    return nm.strip() or nm

def get_liquid_universe(topn=1000):
    """Most liquid US common stocks (NYSE+Nasdaq) by dollar volume, unioned with the S&P 500."""
    syms = {}
    for url in (NASDAQ_URL, NYSE_URL):
        try:
            data = json.loads(http_get(url))
        except Exception:
            continue
        for r in data:
            sym = (r.get("symbol") or "").strip()
            if not re.fullmatch(r"[A-Z]{1,5}", sym):
                continue
            try:
                price = float((r.get("lastsale") or "").replace("$", "").replace(",", ""))
                vol = float(r.get("volume") or 0)
            except ValueError:
                continue
            if price <= 0 or vol <= 0:
                continue
            dv = price * vol
            if dv > syms.get(sym, (0,))[0]:
                syms[sym] = (dv, _clean_name((r.get("name") or "").strip()),
                             (r.get("sector") or "").strip() or "—")
    ranked = sorted(syms.items(), key=lambda kv: -kv[1][0])[:topn]
    universe = [(s, v[1], v[2]) for s, v in ranked]
    have = {s for s, _, _ in universe}
    try:
        for s, nm, sc in get_sp500():
            if s not in have:
                universe.append((s, nm, sc)); have.add(s)
    except Exception:
        pass
    return universe

# ---------- data ----------
def fetch_daily(sym, rng="2y"):
    ysym = sym.replace(".", "-")
    last_err = None
    for host in HOSTS:
        url = f"https://{host}/v8/finance/chart/{ysym}?range={rng}&interval=1d"
        for attempt in range(3):
            try:
                j = json.loads(http_get(url))
                res = j["chart"]["result"][0]
                ts = res["timestamp"]
                closes = res["indicators"]["quote"][0]["close"]
                return [(t, c) for t, c in zip(ts, closes) if c is not None]
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
    raise last_err

def _wkey(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).isocalendar()[:2]

def to_weekly(rows):
    wk = OrderedDict()
    for t, c in rows:
        wk[_wkey(t)] = c
    return list(wk.values())

# ---------- TD setup counts ----------
def setup_count(closes, side):
    """side='buy' -> low setup (close<close[-4]); 'sell' -> high setup (close>close[-4]). Returns running count."""
    cnt = 0; res = []
    for i, c in enumerate(closes):
        if i >= 4 and ((c < closes[i - 4]) if side == "buy" else (c > closes[i - 4])):
            cnt += 1
        else:
            cnt = 0
        res.append(cnt)
    return res

def weekly_asof_counts(rows, side):
    """Weekly setup count as it stood on EACH daily bar.

    Mirrors the live scan: the current (partial) week's close is that day's close,
    completed weeks are frozen. Returned list is aligned 1:1 with `rows`.
    """
    fin, fcnt = [], []          # closes / counts of completed weeks
    out = []
    curkey = None
    prev_close = prev_cnt = None
    for t, c in rows:
        key = _wkey(t)
        if curkey is None:
            curkey = key
        elif key != curkey:
            fin.append(prev_close); fcnt.append(prev_cnt)   # freeze the week that just ended
            curkey = key
        m = len(fin)
        if m >= 4:
            cond = (c < fin[m - 4]) if side == "buy" else (c > fin[m - 4])
            cnt = (fcnt[-1] + 1) if cond else 0
        else:
            cnt = 0
        prev_close, prev_cnt = c, cnt
        out.append(cnt)
    return out

def conf_tier(d, w):
    """'both' = double 9 (both timeframes completed); 'near' = one completed, other 7-8; else None."""
    if d is None or w is None:
        return None
    if d >= 9 and w >= 9:
        return "both"
    if min(d, w) >= CONF_NEAR and max(d, w) >= 9:
        return "near"
    return None

def hit_features(dcloses, wcloses):
    """Model features consumed by low9_score.py — DO NOT REMOVE.

    vol      annualised stdev of daily returns
    depth    10-week price change (how deep the drop into the setup was)
    above_ma weekly close above its own 40-week average
    Dropping these does not break scoring loudly: score_one() silently substitutes
    depth=0.0 and vol=median, which are the model's two strongest coefficients. Every
    score then lands ~12 points low (a 0 depth reads as "never dropped"), the High/Medium
    tiers become unreachable, and the ranking loses its two best features. Measured on a
    2026-08-20 sample: with features 46-62, without 34-50 for the same names.
    """
    rets = [(dcloses[i] - dcloses[i - 1]) / dcloses[i - 1] for i in range(1, len(dcloses)) if dcloses[i - 1] > 0]
    vol = round(statistics.pstdev(rets) * (252 ** 0.5), 4) if len(rets) >= 20 else None
    depth = round((wcloses[-1] - wcloses[-10]) / wcloses[-10], 4) if len(wcloses) >= 11 and wcloses[-10] > 0 else None
    ma = sum(wcloses[-40:]) / len(wcloses[-40:]) if wcloses else None
    above = bool(wcloses[-1] > ma) if ma else None
    return vol, depth, above

def record_backtest(closes, tf, side, horizons, bt):
    """For every bar where the setup first completes (count==9), log the forward return over each horizon."""
    cnt = setup_count(closes, side)
    n = len(closes)
    for i, ct in enumerate(cnt):
        if ct == 9:
            for h in horizons:
                if i + h < n and closes[i] > 0:
                    bt[(tf, side, h)].append((closes[i + h] - closes[i]) / closes[i])

def record_conf_backtest(rows, side, cbt):
    """Log forward returns from the FIRST day of each daily+weekly confluence episode.

    Only episode starts are recorded (and near -> both upgrades), so a confluence that
    persists for two weeks counts once, not ten times.
    """
    dcloses = [c for _, c in rows]
    dcnt = setup_count(dcloses, side)
    wcnt = weekly_asof_counts(rows, side)
    n = len(dcloses)
    prev = None
    for i in range(n):
        tier = conf_tier(dcnt[i], wcnt[i])
        if tier:
            fresh = []
            if prev is None:
                fresh = [tier, "any"]              # new episode
            elif tier == "both" and prev == "near":
                fresh = ["both"]                   # upgraded to a true double 9
            for t in fresh:
                for h in CONF_H:
                    if i + h < n and dcloses[i] > 0:
                        cbt[(side, t, h)].append((dcloses[i + h] - dcloses[i]) / dcloses[i])
        prev = tier

# ---------- scan ----------
def scan(symbols, sleep=0.25):
    hits = []
    errors = 0
    bt = defaultdict(list)
    cbt = defaultdict(list)
    for i, (sym, name, sector) in enumerate(symbols):
        try:
            rows = fetch_daily(sym)
            if len(rows) < 40:
                continue
            dcloses = [c for _, c in rows]
            wcloses = to_weekly(rows)
            # backtest accumulation
            record_backtest(dcloses, "daily", "buy", DAILY_H, bt)
            record_backtest(dcloses, "daily", "sell", DAILY_H, bt)
            record_backtest(wcloses, "weekly", "buy", WEEKLY_H, bt)
            record_backtest(wcloses, "weekly", "sell", WEEKLY_H, bt)
            record_conf_backtest(rows, "buy", cbt)
            record_conf_backtest(rows, "sell", cbt)
            # current counts
            cur = dict(
                daily_low=setup_count(dcloses, "buy")[-1],
                daily_high=setup_count(dcloses, "sell")[-1],
                weekly_low=setup_count(wcloses, "buy")[-1],
                weekly_high=setup_count(wcloses, "sell")[-1],
            )
            if max(cur.values()) >= 7:
                vol, depth, above_ma = hit_features(dcloses, wcloses)
                h = dict(sym=sym, name=name, sector=sector,
                         price=round(dcloses[-1], 2),
                         vol=vol, depth=depth, above_ma=above_ma, **cur)
                h["conf_low"] = conf_tier(cur["daily_low"], cur["weekly_low"])
                h["conf_high"] = conf_tier(cur["daily_high"], cur["weekly_high"])
                hits.append(h)
        except Exception:
            errors += 1
        time.sleep(sleep)
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(symbols)} scanned, {len(hits)} hits, {errors} errors", file=sys.stderr)
    return hits, errors, bt, cbt

# ---------- classify ----------
def _grp(hits, field, pred, sortdesc=True):
    rows = [h for h in hits if pred(h[field])]
    return sorted(rows, key=lambda x: -x[field] if sortdesc else x[field])

def classify(hits):
    out = {}
    for side, field in [("low", "low"), ("high", "high")]:
        for tf in ["daily", "weekly"]:
            f = f"{tf}_{side}"
            out[f"{tf}_{side}_9"] = _grp(hits, f, lambda v: v == 9)
            out[f"{tf}_{side}_ext"] = _grp(hits, f, lambda v: v > 9)
            out[f"{tf}_{side}_near"] = _grp(hits, f, lambda v: v in (7, 8))
    # daily + weekly confluence buckets (true double 9s first)
    for side in ("low", "high"):
        rows = [h for h in hits if h.get(f"conf_{side}")]
        rows.sort(key=lambda h: (0 if h[f"conf_{side}"] == "both" else 1,
                                 -(h[f"daily_{side}"] + h[f"weekly_{side}"])))
        out[f"{side}_conf"] = rows
    return out

def summarize_backtest(bt):
    """For each (tf, side, horizon): count, win-rate in expected direction, avg forward return %."""
    res = {}
    for (tf, side, h), rets in bt.items():
        if not rets:
            continue
        res[f"{tf}_{side}_{h}"] = _stats(rets, side, dict(tf=tf, side=side, horizon=h))
    return res

def summarize_conf(cbt):
    """For each (side, tier, horizon): same stats for daily+weekly confluence events."""
    res = {}
    for (side, tier, h), rets in cbt.items():
        if not rets:
            continue
        res[f"conf_{side}_{tier}_{h}"] = _stats(rets, side, dict(side=side, tier=tier, horizon=h, conf=True))
    return res

def _stats(rets, side, meta):
    n = len(rets)
    if side == "buy":       # expect price UP after a low-9
        wins = sum(1 for r in rets if r > 0)
    else:                   # expect price DOWN after a high-9
        wins = sum(1 for r in rets if r < 0)
    srt = sorted(rets)
    med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    out = dict(meta)
    out.update(n=n,
               win_rate=round(100.0 * wins / n, 1),
               avg_ret=round(100.0 * sum(rets) / n, 2),
               med_ret=round(100.0 * med, 2))
    return out

# ---------- text report ----------
def _count_label(field, v):
    """Show extended counts as '9 +Nd/Nw since' instead of the raw streak length."""
    unit = "w" if field.startswith("weekly") else "d"
    if v > 9:
        return f"9 +{v - 9}{unit}"
    return str(v)

def _fmt(rows, field, mx=12):
    if not rows:
        return "   (none)"
    out = []
    for h in rows[:mx]:
        lab = _count_label(field, h[field])
        star = ""
        side = "low" if "low" in field else "high"
        if h.get(f"conf_{side}") == "both":
            star = " **"
        elif h.get(f"conf_{side}"):
            star = " *"
        out.append(f"   • {h['sym']:<6} ${h['price']:<9} {h['sector'][:18]:<18} {field.split('_')[0]}={lab:<7} {h['name'][:26]}{star}")
    if len(rows) > mx:
        out.append(f"   … +{len(rows)-mx} more")
    return "\n".join(out)

def _fmt_conf(rows, side, mx=20):
    if not rows:
        return "   (none)"
    out = []
    for h in rows[:mx]:
        d, w = h[f"daily_{side}"], h[f"weekly_{side}"]
        tier = "double 9" if h[f"conf_{side}"] == "both" else "9 + near"
        out.append(f"   • {h['sym']:<6} ${h['price']:<9} {h['sector'][:16]:<16} "
                   f"D={_count_label('daily_x', d):<7} W={_count_label('weekly_x', w):<7} [{tier}] {h['name'][:24]}")
    if len(rows) > mx:
        out.append(f"   … +{len(rows)-mx} more")
    return "\n".join(out)

def build_report(out):
    C = out["cls"]; bt = out["perf"]; dt = out["asof"][:10]
    L = [f"📉📈 Low-9 / High-9 Monitor — {out['universe']} — {dt}"]
    fresh = (len(C["weekly_low_9"]) + len(C["daily_low_9"]) +
             len(C["weekly_high_9"]) + len(C["daily_high_9"]))
    L.append(f"{fresh} fresh 9-completions today "
             f"({len(C['weekly_low_9'])+len(C['daily_low_9'])} low / "
             f"{len(C['weekly_high_9'])+len(C['daily_high_9'])} high).")

    L.append("\n=== ⭐ DAILY + WEEKLY CONFLUENCE (strongest) ===")
    for side, lab in (("low", "LOW"), ("high", "HIGH")):
        rows = C.get(f"{side}_conf", [])
        both = sum(1 for h in rows if h[f"conf_{side}"] == "both")
        L.append(f"{lab} 9 on both timeframes — {len(rows)} ({both} true double 9)")
        L.append(_fmt_conf(rows, side))

    L.append("\n=== 🟢 LOW 9 — potential BOTTOMS (bounce up) ===")
    L.append(f"🔴 Fresh WEEKLY low-9 (strongest) — {len(C['weekly_low_9'])}")
    L.append(_fmt(C["weekly_low_9"], "weekly_low"))
    L.append(f"\n🟠 Fresh DAILY low-9 — {len(C['daily_low_9'])}")
    L.append(_fmt(C["daily_low_9"], "daily_low"))
    if C["weekly_low_ext"]:
        L.append(f"\nWeekly low extended >9 (still falling) — {len(C['weekly_low_ext'])}")
        L.append(_fmt(C["weekly_low_ext"], "weekly_low"))
    if C["daily_low_ext"]:
        L.append(f"\nDaily low extended >9 — {len(C['daily_low_ext'])}")
        L.append(_fmt(C["daily_low_ext"], "daily_low"))

    L.append("\n=== 🔴 HIGH 9 — potential TOPS (reverse / drop) ===")
    L.append(f"🔴 Fresh WEEKLY high-9 (strongest) — {len(C['weekly_high_9'])}")
    L.append(_fmt(C["weekly_high_9"], "weekly_high"))
    L.append(f"\n🟠 Fresh DAILY high-9 — {len(C['daily_high_9'])}")
    L.append(_fmt(C["daily_high_9"], "daily_high"))
    if C["weekly_high_ext"]:
        L.append(f"\nWeekly high extended >9 (still rising) — {len(C['weekly_high_ext'])}")
        L.append(_fmt(C["weekly_high_ext"], "weekly_high"))
    if C["daily_high_ext"]:
        L.append(f"\nDaily high extended >9 — {len(C['daily_high_ext'])}")
        L.append(_fmt(C["daily_high_ext"], "daily_high"))

    L.append("\n=== 📊 SIGNAL PERFORMANCE (backtest, ~2y history, this universe) ===")
    def line(tf, side, hs, label, unit):
        parts = []
        for h in hs:
            s = bt.get(f"{tf}_{side}_{h}")
            if s:
                parts.append(f"{h}{unit}: {s['win_rate']}% ({s['avg_ret']:+}% avg, n={s['n']})")
        if parts:
            L.append(f"{label}: " + " | ".join(parts))
    line("daily", "buy", DAILY_H, "Low-9 daily → bounced UP within", "d")
    line("weekly", "buy", WEEKLY_H, "Low-9 weekly → bounced UP within", "w")
    line("daily", "sell", DAILY_H, "High-9 daily → dropped DOWN within", "d")
    line("weekly", "sell", WEEKLY_H, "High-9 weekly → dropped DOWN within", "w")

    L.append("\n--- ⭐ daily + weekly confluence (forward returns from day 1 of the signal) ---")
    def cline(side, tier, label):
        parts = []
        for h in CONF_H:
            s = bt.get(f"conf_{side}_{tier}_{h}")
            if s:
                parts.append(f"{h}d: {s['win_rate']}% ({s['avg_ret']:+}% avg, {s['med_ret']:+}% med, n={s['n']})")
        if parts:
            L.append(f"{label}: " + " | ".join(parts))
    cline("buy", "both", "Low double 9 (D9+W9) → UP within")
    cline("buy", "near", "Low 9 + near (7-8) → UP within")
    cline("sell", "both", "High double 9 (D9+W9) → DOWN within")
    cline("sell", "near", "High 9 + near (7-8) → DOWN within")

    L.append(f"\napproaching 7–8: low {len(C['daily_low_near'])}d/{len(C['weekly_low_near'])}w, "
             f"high {len(C['daily_high_near'])}d/{len(C['weekly_high_near'])}w · "
             f"scanned {out['scanned']}, {out['errors']} errors")
    L.append("Low/High 9 = 9 bars closing below/above the close 4 bars earlier (TD Buy/Sell Setup, 九转序列). "
             "** = same signal completed on daily AND weekly (double 9); * = one completed, the other 1-2 bars away. "
             "Win-rate = % of past completions that moved the expected way. Research only — not financial advice.")
    return "\n".join(L)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--json", default="/tmp/low9_hits.json")
    ap.add_argument("--universe", choices=["liquid", "sp500"], default="liquid")
    ap.add_argument("--topn", type=int, default=1000)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.universe == "sp500":
        syms = get_sp500(); uname = "S&P 500"
    else:
        syms = get_liquid_universe(a.topn); uname = f"top-{a.topn} liquid US + S&P 500"
    if a.limit:
        syms = syms[:a.limit]
    print(f"Scanning {len(syms)} tickers ({uname}) for low-9 & high-9 (daily + weekly)...", file=sys.stderr)
    hits, errors, bt, cbt = scan(syms, a.sleep)
    cls = classify(hits)
    perf = summarize_backtest(bt)
    perf.update(summarize_conf(cbt))
    out = dict(asof=datetime.now(timezone.utc).isoformat(), universe=uname,
               scanned=len(syms), errors=errors, cls=cls, perf=perf)
    with open(a.json, "w") as f:
        json.dump(out, f, indent=2)
    if a.report:
        print(build_report(out))
    else:
        print(json.dumps({k: len(v) for k, v in cls.items()}, indent=2))

if __name__ == "__main__":
    main()
