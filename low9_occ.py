#!/usr/bin/env python3
"""Record every historical low-9 / high-9 occurrence with per-signal features,
so we can analyze what distinguishes winners from losers. Saves occ.json."""
import sys, json, argparse, statistics
from datetime import datetime, timezone
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import low9_scanner as S

def to_weekly_ts(rows):
    wk = OrderedDict()
    for t, c in rows:
        key = datetime.fromtimestamp(t, tz=timezone.utc).isocalendar()[:2]
        wk[key] = (t, c)
    return list(wk.values())  # [(ts, close), ...] one per ISO week

def annualized_vol(closes):
    rets = [(closes[i]-closes[i-1])/closes[i-1] for i in range(1, len(closes)) if closes[i-1] > 0]
    if len(rets) < 20:
        return None
    return statistics.pstdev(rets) * (252 ** 0.5)

def analyze_ticker(item):
    sym, name, sector = item
    rows = S.fetch_daily(sym)
    if len(rows) < 60:
        return None
    dtimes = [t for t, _ in rows]
    dcloses = [c for _, c in rows]
    wk = to_weekly_ts(rows)
    wtimes = [t for t, _ in wk]
    wcloses = [c for _, c in wk]
    vol = annualized_vol(dcloses)
    occ = []
    # weekly low-9 and high-9
    for side, tf, closes, times, horizons in [
        ("buy", "weekly", wcloses, wtimes, S.WEEKLY_H),
        ("sell", "weekly", wcloses, wtimes, S.WEEKLY_H),
        ("buy", "daily", dcloses, dtimes, S.DAILY_H),
        ("sell", "daily", dcloses, dtimes, S.DAILY_H),
    ]:
        cnt = S.setup_count(closes, side)
        n = len(closes)
        for i, ct in enumerate(cnt):
            if ct == 9 and i >= 9 and closes[i] > 0:
                # setup depth = pct move over the 9 setup bars (negative for low-9)
                base = closes[i-9] if closes[i-9] > 0 else closes[i]
                depth = (closes[i] - base) / base if base else 0.0
                # trend: price vs long moving average (40 wk / 200 day)
                win = 40 if tf == "weekly" else 200
                lo = max(0, i - win)
                ma = sum(closes[lo:i+1]) / (i+1-lo)
                above_ma = closes[i] > ma
                date = datetime.fromtimestamp(times[i], tz=timezone.utc).strftime("%Y-%m-%d")
                rec = dict(sym=sym, sector=sector, side=side, tf=tf, date=date,
                           price=round(closes[i], 2), depth=round(depth, 4),
                           vol=round(vol, 4) if vol else None, above_ma=above_ma)
                for h in horizons:
                    rec[f"r{h}"] = round((closes[i+h]-closes[i])/closes[i], 4) if i+h < n else None
                occ.append(rec)
    return occ

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topn", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=40)
    ap.add_argument("--out", default="occ.json")
    a = ap.parse_args()
    syms = S.get_liquid_universe(a.topn)
    print(f"Fetching {len(syms)} tickers...", file=sys.stderr)
    all_occ = []
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(analyze_ticker, it): it for it in syms}
        for fut in as_completed(futs):
            done += 1
            try:
                r = fut.result()
                if r:
                    all_occ.extend(r)
            except Exception:
                pass
            if done % 200 == 0:
                print(f"  ...{done}/{len(syms)}, {len(all_occ)} occurrences", file=sys.stderr)
    json.dump(all_occ, open(a.out, "w"))
    # quick counts
    from collections import Counter
    c = Counter((o["tf"], o["side"]) for o in all_occ)
    print("occurrences by (tf, side):", dict(c), file=sys.stderr)
    print(f"wrote {a.out} with {len(all_occ)} occurrences", file=sys.stderr)

if __name__ == "__main__":
    main()
