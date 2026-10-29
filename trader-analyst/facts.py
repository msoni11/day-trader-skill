#!/usr/bin/env python3
"""Earnings reader for trader-analyst. Standard library only.

Pulls an NSE company's reported quarterly numbers and lays out what changed,
quarter by quarter: revenue, gross, operating and net margins, net profit,
diluted EPS, growth against the same quarter a year earlier (YoY) and the
quarter before (QoQ), and the trailing twelve months when four quarters in a
row are there. Amounts are in Rs crore (1 crore = 10 million), the way Indian
results are read.

    python3 facts.py RELIANCE
    python3 facts.py RELIANCE TCS --quarters 8
    python3 facts.py INFY --json
    python3 facts.py HDFCBANK ICICIBANK INFY --metrics trader/metrics.json

Source: Yahoo Finance's fundamentals time series (free, unofficial, can lag
the exchange filing by a few days; consolidated numbers as Yahoo maps them):
  https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/RELIANCE.NS
      ?type=quarterlyTotalRevenue,quarterlyGrossProfit,...&period1=...&period2=...

How the quarters are read:
  - Indian companies file results every quarter, including the fourth (the
    Q4 results come with the full year), so no quarter is derived.
  - Indian fiscal years run April to March: the quarter ending 30 June is Q1,
    30 September Q2, 31 December Q3, 31 March Q4. FY27 is April 2026 to March 2027.
  - A quarter Yahoo does not have is left out and said so; growth that needs
    it is blank, never guessed. TTM needs four quarters in a row.
  - Banks and NBFCs report "total income" and interest, not revenue and cost
    of goods; gross margin is blank for them and revenue is Yahoo's total
    revenue line.

The official numbers are in the company's results filing on nseindia.com /
bseindia.com (Corporate filings, Financial results) and its investor
presentation: check them there before you lean on a number. Offline:
--offline DIR reads timeseries-<TICKER>.json from DIR. The tests use it.

Numbers only: this tool never says whether a stock is a buy.
"""

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; day-trader-skill-india/1.0; +https://github.com/msoni11/day-trader-skill)"
URL = ("https://%s.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/%s"
       "?type=%s&period1=%d&period2=%d")
HOSTS = ("query2", "query1")
CONCEPTS = {
    "revenue": "TotalRevenue",
    "cost_of_revenue": "CostOfRevenue",
    "gross_profit": "GrossProfit",
    "operating_income": "OperatingIncome",
    "net_income": "NetIncome",
    "eps_diluted": "DilutedEPS",
}
CRORE = 1e7
YEARS_BACK = 3
PAUSE = 0.5


class FactsError(Exception):
    pass


# ---------------------------------------------------------------- fetching

def yahoo_symbol(sym):
    s = sym.strip().upper()
    return s if s.startswith("^") or s.endswith((".NS", ".BO")) else s + ".NS"


def fetch(sym, now=None, timeout=30):
    """The quarterly series for one ticker, as Yahoo's JSON text."""
    now = now or int(time.time())
    types = ",".join("quarterly" + v for v in CONCEPTS.values())
    last = None
    for host in HOSTS:
        url = URL % (host, urllib.parse.quote(yahoo_symbol(sym), safe="."), types,
                     now - YEARS_BACK * 366 * 86400, now)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code != 429 and e.code < 500:
                break
            time.sleep(PAUSE * 4)
        except urllib.error.URLError as e:
            raise FactsError("could not reach Yahoo: %s" % e.reason)
    raise FactsError("Yahoo answered %s for %s" % (last, sym))


def read_offline(folder, sym):
    path = os.path.join(folder, "timeseries-%s.json" % sym.upper().replace("&", ""))
    if not os.path.exists(path):
        raise FactsError("offline: no file %s" % path)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------- the numbers

def parse(text, sym):
    """Yahoo time series JSON -> ({quarter end "YYYY-MM-DD": {key: value}}, currency)."""
    try:
        doc = json.loads(text)
        results = doc["timeseries"]["result"]
    except (ValueError, KeyError, TypeError):
        raise FactsError("Yahoo returned something unexpected for %s" % sym)
    back = {"quarterly" + v: k for k, v in CONCEPTS.items()}
    quarters, currency = {}, None
    for r in results or []:
        t = ((r.get("meta") or {}).get("type") or [None])[0]
        key = back.get(t)
        if not key:
            continue
        for x in r.get(t) or []:
            if not x or not x.get("asOfDate") or not isinstance(x.get("reportedValue"), dict):
                continue
            if x.get("periodType") not in (None, "3M"):
                continue
            quarters.setdefault(x["asOfDate"], {})[key] = float(x["reportedValue"]["raw"])
            currency = currency or x.get("currencyCode")
    if not quarters:
        raise FactsError("Yahoo has no quarterly results for %s (check the symbol)" % sym)
    return quarters, currency


def fy_label(end):
    """2026-06-30 -> "Q1 FY27": April to March fiscal years."""
    d = _dt.date.fromisoformat(end)
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(d.month)
    fy = d.year + 1 if d.month >= 4 else d.year
    return ("Q%d FY%02d" % (q, fy % 100)) if q else end


def month_end(end, months):
    """The last day of the month `months` away from the quarter end `end`."""
    d = _dt.date.fromisoformat(end)
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    first_next = _dt.date(y + (1 if m == 12 else 0), m % 12 + 1, 1)
    return (first_next - _dt.timedelta(days=1)).isoformat()


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1) * 100 * (1 if b > 0 else -1), 1)


def margin(part, whole):
    if part is None or not whole:
        return None
    return round(part / whole * 100, 1)


def analyse(quarters, n=6):
    """The newest n quarters, newest first, each with margins and growth."""
    ends = sorted(quarters, reverse=True)
    rows = []
    for end in ends[:n]:
        q = dict(quarters[end])
        if q.get("gross_profit") is None and q.get("revenue") is not None and q.get("cost_of_revenue") is not None:
            q["gross_profit"] = q["revenue"] - q["cost_of_revenue"]
        yoy = quarters.get(month_end(end, -12)) or {}
        qoq = quarters.get(month_end(end, -3)) or {}
        rows.append({
            "end": end, "label": fy_label(end), "revenue": q.get("revenue"), "net_income": q.get("net_income"),
            "operating_income": q.get("operating_income"), "eps_diluted": q.get("eps_diluted"),
            "gross_margin": margin(q.get("gross_profit"), q.get("revenue")),
            "operating_margin": margin(q.get("operating_income"), q.get("revenue")),
            "net_margin": margin(q.get("net_income"), q.get("revenue")),
            "revenue_yoy": pct(q.get("revenue"), yoy.get("revenue")),
            "net_income_yoy": pct(q.get("net_income"), yoy.get("net_income")),
            "eps_yoy": pct(q.get("eps_diluted"), yoy.get("eps_diluted")),
            "revenue_qoq": pct(q.get("revenue"), qoq.get("revenue")),
            "net_income_qoq": pct(q.get("net_income"), qoq.get("net_income")),
        })
    missing = []
    e = ends[0]
    while True:
        e = month_end(e, -3)
        if e < ends[-1]:
            break
        if e not in quarters:
            missing.append(fy_label(e))
    ttm = None
    last4 = [month_end(ends[0], -3 * k) for k in range(4)]
    if all(k in quarters for k in last4):
        four = [quarters[k] for k in last4]

        def total(key):
            vals = [x.get(key) for x in four]
            return None if any(v is None for v in vals) else sum(vals)
        ttm = {"through": ends[0], "revenue": total("revenue"), "net_income": total("net_income"),
               "eps_diluted": total("eps_diluted")}
    return {"quarters": rows, "missing": missing, "ttm": ttm}


def changes(result):
    """Plain sentences on what moved in the newest quarter."""
    out = []
    rows = result["quarters"]
    if not rows:
        return out
    q = rows[0]
    if q["revenue_yoy"] is not None:
        out.append("Revenue %s %.1f%% from %s a year earlier." % (
            "up" if q["revenue_yoy"] >= 0 else "down", abs(q["revenue_yoy"]), fy_label(month_end(q["end"], -12))))
    if q["net_income_yoy"] is not None:
        out.append("Net profit %s %.1f%% YoY." % ("up" if q["net_income_yoy"] >= 0 else "down",
                                                  abs(q["net_income_yoy"])))
    if len(rows) > 1 and q["operating_margin"] is not None and rows[1]["operating_margin"] is not None:
        d = q["operating_margin"] - rows[1]["operating_margin"]
        if abs(d) >= 0.5:
            out.append("Operating margin %s %.1f points on %s (%.1f%% vs %.1f%%)." % (
                "widened" if d > 0 else "narrowed", abs(d), rows[1]["label"], q["operating_margin"],
                rows[1]["operating_margin"]))
        else:
            out.append("Operating margin about flat on %s (%.1f%%)." % (rows[1]["label"], q["operating_margin"]))
    if q["eps_yoy"] is not None:
        out.append("Diluted EPS Rs %.2f, %s %.1f%% YoY." % (q["eps_diluted"], "up" if q["eps_yoy"] >= 0 else "down",
                                                             abs(q["eps_yoy"])))
    if result["missing"]:
        out.append("Yahoo has no numbers for %s: growth that needs them is blank." % ", ".join(result["missing"]))
    return out


# ---------------------------------------------------------------- output

def _cr(v):
    return "-" if v is None else "{:,.0f}".format(v / CRORE)


def _p(v):
    return "-" if v is None else "%.1f%%" % v


def _pm(v):
    return "-" if v is None else "%+.1f%%" % v


def render(ticker, result, currency):
    head = "%s: quarterly results (Yahoo Finance; amounts in Rs crore)" % ticker
    if currency and currency != "INR":
        head += ", reported in %s" % currency
    out = [head, "  %-9s %-10s %10s %8s %8s %10s %8s %7s %7s %8s" % (
        "quarter", "ended", "revenue", "YoY", "QoQ", "profit", "YoY", "op mgn", "net mgn", "EPS")]
    for q in result["quarters"]:
        out.append("  %-9s %-10s %10s %8s %8s %10s %8s %7s %7s %8s" % (
            q["label"], q["end"], _cr(q["revenue"]), _pm(q["revenue_yoy"]), _pm(q["revenue_qoq"]),
            _cr(q["net_income"]), _pm(q["net_income_yoy"]), _p(q["operating_margin"]), _p(q["net_margin"]),
            "-" if q["eps_diluted"] is None else "%.2f" % q["eps_diluted"]))
    t = result["ttm"]
    if t:
        out.append("  TTM through %s: revenue Rs %s crore, net profit Rs %s crore, EPS %s." % (
            fy_label(t["through"]), _cr(t["revenue"]), _cr(t["net_income"]),
            "-" if t["eps_diluted"] is None else "Rs %.2f" % t["eps_diluted"]))
    for line in changes(result):
        out.append("  " + line)
    out.append("  Check the filing on nseindia.com before relying on a number. Numbers only, not advice.")
    return "\n".join(out)


def metrics_row(ticker, result):
    q = result["quarters"][0] if result["quarters"] else {}
    t = result["ttm"] or {}
    cr = lambda v: None if v is None else round(v / CRORE, 2)
    return {"ticker": ticker, "quarter": q.get("label"), "quarter_end": q.get("end"),
            "revenue_cr": cr(q.get("revenue")), "net_profit_cr": cr(q.get("net_income")),
            "revenue_yoy_pct": q.get("revenue_yoy"), "net_profit_yoy_pct": q.get("net_income_yoy"),
            "operating_margin_pct": q.get("operating_margin"), "net_margin_pct": q.get("net_margin"),
            "eps_diluted": q.get("eps_diluted"), "ttm_revenue_cr": cr(t.get("revenue")),
            "ttm_eps": t.get("eps_diluted")}


def write_metrics(path, results):
    doc = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except ValueError:
            doc = {}
    rows = {r["ticker"]: r for r in doc.get("rows", [])}
    for t, (res, _) in results.items():
        rows[t] = metrics_row(t, res)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"source": "Yahoo Finance fundamentals", "unit": "Rs crore",
                   "rows": [rows[k] for k in sorted(rows)]}, fh, indent=2)
        fh.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Quarterly results for NSE stocks (trader-analyst).")
    ap.add_argument("tickers", nargs="+", help="NSE symbols: RELIANCE TCS M&M")
    ap.add_argument("--quarters", type=int, default=6)
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--metrics", metavar="FILE", help="merge one row per ticker into this JSON file")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results, failed = {}, {}
    for i, t in enumerate(a.tickers):
        t = t.upper()
        try:
            if a.offline:
                text = read_offline(a.offline, t)
            else:
                if i:
                    time.sleep(PAUSE)
                text = fetch(t)
            quarters, currency = parse(text, t)
            results[t] = (analyse(quarters, a.quarters), currency)
        except FactsError as e:
            failed[t] = str(e)
    if a.metrics and results:
        write_metrics(a.metrics, results)
    if a.json:
        doc = {t: dict(res, currency=c) for t, (res, c) in results.items()}
        doc["errors"] = failed
        print(json.dumps(doc, indent=2))
    else:
        for t, (res, c) in results.items():
            print(render(t, res, c))
            print()
        for t, e in failed.items():
            print("%s: %s" % (t, e), file=sys.stderr)
        if a.metrics and results:
            print("Merged %d row(s) into %s." % (len(results), a.metrics))
    return 0 if results and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
