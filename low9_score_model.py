#!/usr/bin/env python3
"""Fit + validate a confidence model for WEEKLY LOW-9 longs (target: 8-week return > 0).
Honest test: train on the earlier signals, test on the most recent ~30% (time split).
Exports model.json (coeffs + preprocessing) for a pure-Python live scorer."""
import json, math, statistics
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_score

occ = json.load(open("occ.json"))
pe = json.load(open("pe.json"))
def getpe(s):
    q = pe.get(s) or pe.get(s.replace(".", "-")) or {}
    return q.get("pe"), q.get("mktcap")

rows = [o for o in occ if o["side"] == "buy" and o["tf"] == "weekly" and o.get("r8") is not None and o.get("date")]
for o in rows:
    p, mc = getpe(o["sym"]); o["_mc"] = mc if isinstance(mc, (int, float)) else None
rows.sort(key=lambda o: o["date"])
print(f"weekly low-9 samples with r8: {len(rows)}  ({rows[0]['date']} .. {rows[-1]['date']})")

# medians for imputation
vols = [o["vol"] for o in rows if o.get("vol") is not None]; VMED = statistics.median(vols)
mcs = [o["_mc"] for o in rows if o.get("_mc")]; MCMED = statistics.median(mcs)

# time split
cut = int(len(rows) * 0.70)
train, test = rows[:cut], rows[cut:]
print(f"train {len(train)} (<= {train[-1]['date']}), test {len(test)} (>= {test[0]['date']})")

# sector target-encoding (smoothed) from TRAIN only
glob = sum(1 for o in train if o["r8"] > 0) / len(train)
sec_w, sec_n = {}, {}
for o in train:
    s = o["sector"] or "?"; sec_n[s] = sec_n.get(s, 0) + 1; sec_w[s] = sec_w.get(s, 0) + (1 if o["r8"] > 0 else 0)
A = 15.0
sec_rate = {s: (sec_w[s] + A*glob)/(sec_n[s] + A) for s in sec_n}
def srate(s): return sec_rate.get(s or "?", glob)

def feats(o):
    depth = o.get("depth") or 0.0
    vol = o.get("vol") if o.get("vol") is not None else VMED
    above = 1.0 if o.get("above_ma") else 0.0
    lmc = math.log(o.get("_mc") or MCMED)
    lpr = math.log(max(o.get("price") or 1.0, 0.5))
    return [depth, vol, above, lmc, lpr, srate(o["sector"])]

Xtr = np.array([feats(o) for o in train]); ytr = np.array([1 if o["r8"] > 0 else 0 for o in train])
Xte = np.array([feats(o) for o in test]);  yte = np.array([1 if o["r8"] > 0 else 0 for o in test])
mu = Xtr.mean(0); sd = Xtr.std(0); sd[sd == 0] = 1
Xtrs = (Xtr - mu)/sd; Xtes = (Xte - mu)/sd

clf = LogisticRegression(C=0.5, max_iter=1000)
clf.fit(Xtrs, ytr)

# cross-val AUC on train (robustness) + honest holdout AUC
cv = cross_val_score(clf, Xtrs, ytr, cv=5, scoring="roc_auc")
ptr = clf.predict_proba(Xtrs)[:, 1]; pte = clf.predict_proba(Xtes)[:, 1]
print(f"\nAUC  train={roc_auc_score(ytr,ptr):.3f}  5foldCV={cv.mean():.3f}±{cv.std():.3f}  HOLDOUT={roc_auc_score(yte,pte):.3f}")
print("(0.5=coinflip; >0.55 = real signal on unseen data)")

names = ["depth", "vol", "above_ma", "log_mktcap", "log_price", "sector_rate"]
print("\nstandardized coefficients (sign/size = influence on win prob):")
for nme, c in sorted(zip(names, clf.coef_[0]), key=lambda x: -abs(x[1])):
    print(f"   {nme:<12} {c:+.3f}")

# calibration on HOLDOUT: bucket by predicted score, show real win rate + avg r8
def report(split, p, label):
    order = np.argsort(p)
    q = [order[i*len(order)//4:(i+1)*len(order)//4] for i in range(4)]
    print(f"\n{label}: actual outcome by predicted-confidence quartile")
    print("   quartile   score-range   win%   avg r8%   n")
    for i, idx in enumerate(q):
        ps = p[idx]; ys = np.array([1 if split[j]["r8"] > 0 else 0 for j in idx])
        r8 = np.array([split[j]["r8"] for j in idx])
        print(f"   Q{i+1}        {ps.min()*100:4.0f}-{ps.max()*100:3.0f}     {100*ys.mean():4.0f}   {100*r8.mean():+5.1f}    {len(idx)}")
report(test, pte, "HOLDOUT (unseen recent signals)")

# refit on ALL data for the shipped model
Xall = np.array([feats(o) for o in rows]); yall = np.array([1 if o["r8"] > 0 else 0 for o in rows])
mu = Xall.mean(0); sd = Xall.std(0); sd[sd == 0] = 1
clf.fit((Xall-mu)/sd, yall)
# recompute sector rates on ALL for shipping
sec_w, sec_n = {}, {}
for o in rows:
    s = o["sector"] or "?"; sec_n[s] = sec_n.get(s, 0)+1; sec_w[s] = sec_w.get(s, 0)+(1 if o["r8"]>0 else 0)
glob_all = sum(yall)/len(yall)
sec_rate_all = {s: (sec_w[s] + A*glob_all)/(sec_n[s] + A) for s in sec_n}

model = dict(features=names, mean=mu.tolist(), std=sd.tolist(),
             coef=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0]),
             vmed=VMED, mcmed=MCMED, sector_rate=sec_rate_all, global_rate=glob_all,
             base_win=round(100*glob_all, 1))
json.dump(model, open("model.json", "w"), indent=2)
print("\nwrote model.json  (base win rate all weekly low-9 =", model["base_win"], "%)")
