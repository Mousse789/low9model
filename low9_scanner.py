#!/usr/bin/env python3
"""Low-9 / High-9 scanner (TD Sequential setups, 九转序列) for US stocks — daily + weekly."""
import sys, time, json, csv, io, re, argparse, urllib.request
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]

DAILY_H = [5, 10, 20]
WEEKLY_H = [4, 8, 12]

def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

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

def to_weekly(rows):
    wk = OrderedDict()
    for t, c in rows:
        key = datetime.fromtimestamp(t, tz=timezone.utc).isocalendar()[:2]
        wk[key] = c
    return list(wk.values())

def setup_count(closes, side):
    cnt = 0; res = []
    for i, c in enumerate(closes):
        if i >= 4 and ((c < closes[i - 4]) if side == "buy" else (c > closes[i - 4])):
            cnt += 1
        else:
            cnt = 0
        res.append(cnt)
    return res

def record_backtest(closes, tf, side, horizons, bt):
    cnt = setup_count(closes, side)
    n = len(closes)
    for i, ct in enumerate(cnt):
        if ct == 9:
            for h in horizons:
                if i + h < n and closes[i] > 0:
                    bt[(tf, side, h)].append((closes[i + h] - closes[i]) / closes[i])

def scan(symbols, sleep=0.25):
    hits = []
    errors = 0
    bt = defaultdict(list)
    for i, (sym, name, sector) in enumerate(symbols):
        try:
            rows = fetch_daily(sym)
            if len(rows) < 40:
                continue
            dcloses = [c for _, c in rows]
            wcloses = to_weekly(rows)
            record_backtest(dcloses, "daily", "buy", DAILY_H, bt)
            record_backtest(dcloses, "daily", "sell", DAILY_H, bt)
            record_backtest(wcloses, "weekly", "buy", WEEKLY_H, bt)
            record_backtest(wcloses, "weekly", "sell", WEEKLY_H, bt)
            cur = dict(
                daily_low=setup_count(dcloses, "buy")[-1],
                daily_high=setup_count(dcloses, "sell")[-1],
                weekly_low=setup_count(wcloses, "buy")[-1],
                weekly_high=setup_count(wcloses, "sell")[-1],
            )
            if max(cur.values()) >= 7:
                hits.append(dict(sym=sym, name=name, sector=sector,
                                 price=round(dcloses[-1], 2), **cur))
        except Exception:
            errors += 1
        time.sleep(sleep)
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(symbols)} scanned, {len(hits)} hits, {errors} errors", file=sys.stderr)
    return hits, errors, bt

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
    return out

def summarize_backtest(bt):
    res = {}
    for (tf, side, h), rets in bt.items():
        if not rets:
            continue
        n = len(rets)
        if side == "buy":
            wins = sum(1 for r in rets if r > 0)
        else:
            wins = sum(1 for r in rets if r < 0)
        res[f"{tf}_{side}_{h}"] = dict(
            tf=tf, side=side, horizon=h, n=n,
            win_rate=round(100.0 * wins / n, 1),
            avg_ret=round(100.0 * sum(rets) / n, 2),
        )
    return res

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
    hits, errors, bt = scan(syms, a.sleep)
    cls = classify(hits)
    perf = summarize_backtest(bt)
    out = dict(asof=datetime.now().isoformat(), universe=uname,
               scanned=len(syms), errors=errors, cls=cls, perf=perf)
    with open(a.json, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: len(v) for k, v in cls.items()}, indent=2))

if __name__ == "__main__":
    main()
