#!/usr/bin/env python3
"""Add compact price sparkline series to a low9/high9 scan JSON."""
import sys, time, json, argparse, urllib.request
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]

def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_closes(sym, rng="6mo"):
    ysym = sym.replace(".", "-")
    last = None
    for host in HOSTS:
        url = f"https://{host}/v8/finance/chart/{ysym}?range={rng}&interval=1d"
        for attempt in range(3):
            try:
                j = json.loads(http_get(url))
                res = j["chart"]["result"][0]
                closes = res["indicators"]["quote"][0]["close"]
                return [c for c in closes if c is not None]
            except Exception as e:
                last = e
                time.sleep(0.8 * (attempt + 1))
    raise last

def downsample(vals, n=48):
    if len(vals) <= n:
        return [round(v, 2) for v in vals]
    step = (len(vals) - 1) / (n - 1)
    return [round(vals[int(round(i * step))], 2) for i in range(n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="low9_hits_pe.json")
    ap.add_argument("--out", dest="out", default="low9_hits_full.json")
    ap.add_argument("--points", type=int, default=48)
    ap.add_argument("--sleep", type=float, default=0.15)
    a = ap.parse_args()
    data = json.load(open(a.inp))
    syms = sorted({r["sym"] for rows in data["cls"].values() for r in rows})
    print(f"Fetching sparkline series for {len(syms)} hit tickers...", file=sys.stderr)
    series = {}
    errors = 0
    for i, sym in enumerate(syms):
        try:
            closes = fetch_closes(sym)
            if len(closes) >= 5:
                sp = downsample(closes, a.points)
                chg = round(100.0 * (closes[-1] - closes[0]) / closes[0], 1) if closes[0] else None
                series[sym] = dict(spark=sp, chg=chg)
        except Exception:
            errors += 1
        time.sleep(a.sleep)
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(syms)} ({errors} errors)", file=sys.stderr)
    filled = 0
    for rows in data["cls"].values():
        for r in rows:
            s = series.get(r["sym"])
            if s:
                r["spark"] = s["spark"]
                r["chg"] = s["chg"]
                filled += 1
    data["spark_filled"] = filled
    json.dump(data, open(a.out, "w"), indent=2)
    print(f"wrote {a.out} — sparklines for {filled} rows, {errors} errors", file=sys.stderr)

if __name__ == "__main__":
    main()
