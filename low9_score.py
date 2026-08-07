#!/usr/bin/env python3
"""Add a 0-100 confidence score to WEEKLY LOW-9 hits using model.json (pure stdlib).
Score = model's estimated probability that the 8-week forward return is positive.
Runs after low9_fetch_pe.py (needs mktcap). Usage: low9_score.py --in X.json --out Y.json"""
import json, math, argparse

def load_model(path="model.json"):
    return json.load(open(path))

def score_one(h, M):
    depth = h.get("depth")
    vol = h.get("vol")
    above = 1.0 if h.get("above_ma") else 0.0
    mc = h.get("mktcap")
    price = h.get("price")
    sector = h.get("sector")
    depth = depth if isinstance(depth, (int, float)) else 0.0
    vol = vol if isinstance(vol, (int, float)) else M["vmed"]
    lmc = math.log(mc if isinstance(mc, (int, float)) and mc > 0 else M["mcmed"])
    lpr = math.log(max(price if isinstance(price, (int, float)) else 1.0, 0.5))
    srate = M["sector_rate"].get(sector or "?", M["global_rate"])
    x = [depth, vol, above, lmc, lpr, srate]
    z = [(x[i] - M["mean"][i]) / M["std"][i] for i in range(len(x))]
    lin = M["intercept"] + sum(z[i] * M["coef"][i] for i in range(len(z)))
    p = 1.0 / (1.0 + math.exp(-lin))
    return round(100 * p)

def tier(score):
    if score >= 78: return "High"
    if score >= 65: return "Medium"
    return "Low"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="low9_hits_pe.json")
    ap.add_argument("--out", dest="out", default="low9_hits_scored.json")
    ap.add_argument("--model", default="model.json")
    a = ap.parse_args()
    data = json.load(open(a.inp))
    try:
        M = load_model(a.model)
    except Exception as e:
        print("no model, skipping scoring:", e)
        json.dump(data, open(a.out, "w"), indent=2); return
    # score the weekly-low lists (fresh + extended + near)
    for key in ("weekly_low_9", "weekly_low_ext", "weekly_low_near"):
        for h in data["cls"].get(key, []):
            s = score_one(h, M)
            h["score"] = s
            h["tier"] = tier(s)
    # sort fresh weekly low-9 by score desc
    data["cls"]["weekly_low_9"] = sorted(data["cls"].get("weekly_low_9", []),
                                         key=lambda h: -h.get("score", 0))
    data["model_base_win"] = M.get("base_win")
    json.dump(data, open(a.out, "w"), indent=2)
    n = len(data["cls"].get("weekly_low_9", []))
    print(f"scored {n} fresh weekly low-9 hits -> {a.out}")

if __name__ == "__main__":
    main()
