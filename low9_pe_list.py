#!/usr/bin/env python3
"""Fetch trailing P/E + market cap for the unique tickers in occ.json -> pe.json."""
import json, sys, time, urllib.request, urllib.parse, http.cookiejar
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

def opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA)]
    return op

def crumb(op):
    for u in ("https://fc.yahoo.com", "https://finance.yahoo.com"):
        try: op.open(u, timeout=15).read()
        except Exception: pass
    for host in ("query1", "query2"):
        try:
            c = op.open(f"https://{host}.finance.yahoo.com/v1/test/getcrumb", timeout=15).read().decode()
            if c and "<" not in c: return c
        except Exception: pass
    raise RuntimeError("no crumb")

def main():
    occ = json.load(open("occ.json"))
    syms = sorted({o["sym"] for o in occ})
    print(f"{len(syms)} unique tickers", file=sys.stderr)
    op = opener(); cr = crumb(op)
    out = {}
    B = 60
    for i in range(0, len(syms), B):
        batch = syms[i:i+B]
        ys = ",".join(s.replace(".", "-") for s in batch)
        for host in ("query1", "query2"):
            url = (f"https://{host}.finance.yahoo.com/v7/finance/quote"
                   f"?symbols={urllib.parse.quote(ys)}&crumb={urllib.parse.quote(cr)}")
            try:
                j = json.loads(op.open(url, timeout=20).read())
                for q in j.get("quoteResponse", {}).get("result", []):
                    out[q.get("symbol","")] = dict(pe=q.get("trailingPE"), mktcap=q.get("marketCap"))
                break
            except Exception:
                time.sleep(0.5)
        if (i//B) % 3 == 0:
            print(f"  ...{min(i+B,len(syms))}/{len(syms)}", file=sys.stderr)
        time.sleep(0.25)
    json.dump(out, open("pe.json", "w"))
    print(f"wrote pe.json, {len(out)} filled", file=sys.stderr)

if __name__ == "__main__":
    main()
