#!/usr/bin/env python3
"""Enrich a low9/high9 scan JSON with trailing/forward P/E and market cap."""
import sys, json, time, argparse, urllib.request, urllib.parse, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

def make_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA)]
    return op

def get_crumb(op):
    for u in ("https://fc.yahoo.com", "https://finance.yahoo.com"):
        try:
            op.open(u, timeout=15).read()
        except Exception:
            pass
    for host in ("query1", "query2"):
        try:
            c = op.open(f"https://{host}.finance.yahoo.com/v1/test/getcrumb", timeout=15).read().decode()
            if c and "<" not in c:
                return c
        except Exception:
            pass
    raise RuntimeError("could not obtain crumb")

def fetch_quotes(op, crumb, syms):
    out = {}
    B = 50
    for i in range(0, len(syms), B):
        batch = syms[i:i+B]
        ysyms = ",".join(s.replace(".", "-") for s in batch)
        got = False
        for host in ("query1", "query2"):
            url = (f"https://{host}.finance.yahoo.com/v7/finance/quote"
                   f"?symbols={urllib.parse.quote(ysyms)}&crumb={urllib.parse.quote(crumb)}")
            for attempt in range(3):
                try:
                    j = json.loads(op.open(url, timeout=20).read())
                    for q in j.get("quoteResponse", {}).get("result", []):
                        sym = q.get("symbol", "")
                        out[sym] = dict(
                            pe=q.get("trailingPE"),
                            fwd_pe=q.get("forwardPE"),
                            mktcap=q.get("marketCap"),
                            eps=q.get("epsTrailingTwelveMonths"),
                        )
                    got = True
                    break
                except Exception as e:
                    time.sleep(1.0 * (attempt + 1))
                    last = e
            if got:
                break
        print(f"  ...{min(i+B,len(syms))}/{len(syms)} quoted ({len(out)} filled)", file=sys.stderr)
        time.sleep(0.4)
    return out

def apply(data, quotes):
    def norm(sym):
        return quotes.get(sym) or quotes.get(sym.replace(".", "-"))
    filled = 0
    for k, rows in data["cls"].items():
        for r in rows:
            q = norm(r["sym"]) or {}
            pe = q.get("pe")
            fwd = q.get("fwd_pe")
            r["pe"] = round(pe, 1) if isinstance(pe, (int, float)) else None
            r["fwd_pe"] = round(fwd, 1) if isinstance(fwd, (int, float)) else None
            mc = q.get("mktcap")
            r["mktcap"] = mc if isinstance(mc, (int, float)) else None
            if r["pe"] is not None:
                filled += 1
    data["pe_filled"] = filled
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="low9_hits.json")
    ap.add_argument("--out", dest="out", default="low9_hits_pe.json")
    a = ap.parse_args()
    data = json.load(open(a.inp))
    syms = sorted({r["sym"] for rows in data["cls"].values() for r in rows})
    print(f"Fetching P/E for {len(syms)} tickers...", file=sys.stderr)
    op = make_opener()
    crumb = get_crumb(op)
    print("crumb ok", file=sys.stderr)
    quotes = fetch_quotes(op, crumb, syms)
    data = apply(data, quotes)
    json.dump(data, open(a.out, "w"), indent=2)
    print(f"wrote {a.out} — P/E filled for {data['pe_filled']} rows", file=sys.stderr)

if __name__ == "__main__":
    main()
