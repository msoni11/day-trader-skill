#!/usr/bin/env python3
"""Promoter, insider and big-money tracker for trader-insider. Standard library only.

Reads the trades India makes public the same day or within days:

  bulk deals    one client trading more than 0.5 % of a company's shares in a
                day; the exchange publishes the client's name, side, quantity and
                price after the close
  block deals   a single trade of at least Rs 10 crore in the block-deal
                windows (8:45-9:00 and 14:05-14:20); same details
  insider       SEBI (Prohibition of Insider Trading) Regulations, 2015 filings
  (PIT)         by promoters, directors and designated people: Regulation 7(2)
                is a trade, due within 2 trading days; 7(3) is the company
                passing it on

    python3 deals.py check bulk.csv block.csv insider.csv   # what is new since the last check
    python3 deals.py check bulk.csv --symbol RELIANCE       # one stock
    python3 deals.py check bulk.csv --min-value-cr 5        # Rs 5 crore and up
    python3 deals.py show bulk.csv --all                    # everything in the files, seen or not
    python3 deals.py summary bulk.csv block.csv             # net buy / sell by stock and client

Where the files come from: NSE's site does not serve scripts, so save them
from your browser (or ask Claude to open the page in its browser and save the
table):
  - Bulk and block deals: nseindia.com > Market Data > Bulk / Block Deals
    ("Download (.csv)"), or the JSON the page loads. Columns: DATE, SYMBOL,
    SECURITY NAME, CLIENT NAME, BUY / SELL, QUANTITY TRADED, TRADE PRICE /
    WGHT. AVG. PRICE, REMARKS.
  - Insider trading: nseindia.com > Companies > Corporate Filings > Insider
    Trading ("Download (.csv)"). Columns include SYMBOL, COMPANY, REGULATION,
    the acquirer or disposer, category (Promoter, Director ...), securities
    and value acquired or disposed, transaction type, dates and the broadcast
    time; the page's own JSON (corporates-pit) has the filing list.
  The file kind is told from its columns. Indian number formats (1,66,800) are fine.

What these are, and are not: public disclosures, published after the trade.
Reading them fast is not inside information; there is none here. A promoter
buying is a fact, not a forecast, and a bulk "buy" is often a broker or an
algo trading both sides on the same day: `summary` nets each client's buys
against its sells for that reason.

State: trader/state/insider.json remembers what was shown, so each deal or
filing alerts once. Holdings and watchlist tickers (trader/portfolio.json,
trader/watchlist.json, trader/plan.json) are flagged.
"""

import argparse
import csv
import datetime as _dt
import hashlib
import io
import json
import os
import re
import sys

CRORE = 1e7
KEEP_DAYS = 60
MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


class DealsError(Exception):
    pass


# ---------------------------------------------------------------- reading

def norm(k):
    """A header, loosely: "BUY / SELL" -> "buy/sell", "TRADE PRICE / WGHT. AVG. PRICE" -> "trade price/wght. avg. price"."""
    return re.sub(r"\s*/\s*", "/", re.sub(r"\s+", " ", str(k or "").replace("﻿", "").strip().lower()))


def pick(row, *needles):
    """The first column whose header holds every word of one of the needles."""
    for n in needles:
        words = n.split()
        for k, v in row.items():
            if all(w in k for w in words):
                return (v if v is not None else "").strip() if isinstance(v, str) else v
    return None


def number(text):
    """"1,66,800" -> 166800.0; "-" or "" -> None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    t = str(text).replace(",", "").replace("Rs", "").replace("₹", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def parse_date(text):
    """"22-OCT-2026", "22-Oct-2026 20:09:55", "2026-10-22", "22/10/2026" -> "2026-10-22" (or "" when unknown)."""
    t = str(text or "").strip()
    m = re.match(r"^(\d{1,2})[-/ ]([A-Za-z]{3})[A-Za-z]*[-/ ](\d{4})", t)
    if m and m.group(2).upper() in MONTHS:
        return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2).upper()], int(m.group(1)))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return ""


def load_rows(path):
    """A CSV or a JSON file (a list, or {"data": [...]}) -> list of dicts with loose headers."""
    if not os.path.exists(path):
        raise DealsError("no file %s: save it from nseindia.com first" % path)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    if text.lstrip().startswith(("{", "[")):
        try:
            doc = json.loads(text)
        except ValueError as e:
            raise DealsError("%s is not valid JSON: %s" % (path, e))
        rows = doc.get("data", doc) if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            raise DealsError("%s has no list of rows" % path)
    else:
        rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append({norm(k): v for k, v in r.items()})
    return out


def kind_of(rows):
    if not rows:
        return None
    keys = " | ".join(rows[0].keys())
    if "client" in keys:
        return "deal"
    if "regulation" in keys or "acquirer" in keys or "acqname" in keys or "personcategory" in keys:
        return "insider"
    return None


def fid(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def read_deals(rows, source):
    """Bulk / block deal rows -> items."""
    out = []
    block = "block" in source.lower()
    for r in rows:
        sym = (pick(r, "symbol") or "").upper()
        side = (pick(r, "buy/sell", "buysell", "buy sell") or "").upper()
        qty = number(pick(r, "quantity", "qty"))
        price = number(pick(r, "price"))
        if not sym or not side or qty is None:
            continue
        date = parse_date(pick(r, "date"))
        client = pick(r, "client") or ""
        value = qty * price if price else None
        remark = pick(r, "remark") or ""
        out.append({"id": fid("deal", date, sym, client, side, qty, price), "kind": "block deal" if block else "deal",
                    "date": date, "symbol": sym, "name": pick(r, "security name", "name") or "",
                    "who": client, "category": "", "side": "BUY" if side.startswith("B") else "SELL",
                    "qty": qty, "price": price, "value": value,
                    "note": "" if remark in ("-", "") else remark, "source": source})
    return out


def read_insider(rows, source):
    """SEBI PIT disclosure rows (NSE's CSV export or its JSON) -> items."""
    out = []
    for r in rows:
        sym = (pick(r, "symbol") or "").upper()
        if not sym:
            continue
        who = pick(r, "acquirer", "acqname", "name of the") or ""
        cat = pick(r, "category", "personcategory") or ""
        qty = number(pick(r, "no. of securities (acquired", "securities acquired", "secacq", "no. of securities"))
        value = number(pick(r, "value of security", "secval", "value"))
        txn = (pick(r, "transaction type", "tdpTransactionType".lower(), "acquisition/disposal") or "").strip()
        side = "BUY" if re.search(r"buy|acqui|purchase|allot", txn, re.I) else \
            "SELL" if re.search(r"sell|sale|dispos|pledge|revok", txn, re.I) else ""
        when = parse_date(pick(r, "broadcast", "date of allotment/acquisition from", "acqfromdt", "date"))
        reg = pick(r, "regulation") or ""
        mode = pick(r, "mode of acquisition", "acqmode") or ""
        price = (value / qty) if value and qty else None
        out.append({"id": fid("pit", sym, who, when, qty, value, reg, pick(r, "appid", "xml") or ""),
                    "kind": "insider", "date": when, "symbol": sym,
                    "name": pick(r, "company") or "", "who": who, "category": cat, "side": side,
                    "qty": qty, "price": price, "value": value,
                    "note": "; ".join(x for x in (reg, txn, mode, pick(r, "type of submission", "typeofsubmission") or "")
                                      if x and x != "-"),
                    "link": pick(r, "ixbrl", "attachment", "xmlfilename") or "", "source": source})
    return out


def read_files(paths):
    items, notes = [], []
    for p in paths:
        rows = load_rows(p)
        k = kind_of(rows)
        if k == "deal":
            items += read_deals(rows, os.path.basename(p))
        elif k == "insider":
            items += read_insider(rows, os.path.basename(p))
        elif not rows:
            notes.append("%s has no rows" % p)
        else:
            notes.append("%s: not a bulk / block deal or insider-trading file (columns %s)"
                         % (p, ", ".join(list(rows[0])[:6])))
    return items, notes


# ---------------------------------------------------------------- yours

def load_json(path):
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except ValueError:
            return None
    return None


def my_tickers(portfolio="trader/portfolio.json", watchlist="trader/watchlist.json", plan="trader/plan.json"):
    """{SYMBOL: "holding" | "watchlist" | "plan"}."""
    out = {}
    for h in (load_json(watchlist) or {}).get("hits", []):
        if h.get("symbol"):
            out[str(h["symbol"]).upper()] = "watchlist"
    pl = load_json(plan) or {}
    if pl.get("symbol"):
        out[str(pl["symbol"]).upper()] = "plan"
    for p in (load_json(portfolio) or {}).get("positions", []):
        s = p.get("ticker") or p.get("symbol")
        if s:
            out[str(s).upper()] = "holding"
    return out


# ---------------------------------------------------------------- state

def load_state(path):
    return load_json(path) or {"seen": {}, "last_check": None}


def save_state(path, state):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")


def remember(items, state, today):
    seen = state.setdefault("seen", {})
    for it in items:
        seen.setdefault(it["id"], today)
    cutoff = (_dt.date.fromisoformat(today) - _dt.timedelta(days=KEEP_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= cutoff}
    state["last_check"] = today


# ---------------------------------------------------------------- words

def cr(v):
    if v is None:
        return "-"
    if v >= CRORE:
        return "Rs %s cr" % "{:,.2f}".format(v / CRORE)
    return "Rs %s lakh" % "{:,.2f}".format(v / 1e5)


def indian(n):
    """166800 -> "1,66,800": the way the exchange writes it."""
    if n is None:
        return "-"
    s = "%d" % round(n)
    neg, s = s.startswith("-"), s.lstrip("-")
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ("-" if neg else "") + ",".join(parts + [tail]) if parts else ("-" if neg else "") + tail


def describe(it, mine):
    flag = ("  <- your %s" % mine[it["symbol"]]) if it["symbol"] in mine else ""
    who = it["who"] + (" (%s)" % it["category"] if it["category"] else "")
    what = "%s %s shares" % (it["side"] or "TRADE", indian(it["qty"])) if it["qty"] is not None else (it["side"] or "filing")
    at = (" at Rs %.2f" % it["price"]) if it["price"] else ""
    val = (" = %s" % cr(it["value"])) if it["value"] else ""
    line = "%s  %-6s %-12s %s %s%s%s%s" % (it["date"] or "date ?", "PIT" if it["kind"] == "insider" else
                                          ("BLOCK" if it["kind"] == "block deal" else "BULK"),
                                          it["symbol"], who + ":" if who else "", what, at, val, flag)
    extra = "  ".join(x for x in (it["note"], it.get("link") or "") if x)
    return [line] + (["      " + extra] if extra else [])


def summary(items):
    """Net shares and rupees by (symbol, client) over the deals: buys minus sells."""
    net = {}
    for it in items:
        if it["kind"] == "insider" or it["qty"] is None:
            continue
        k = (it["symbol"], it["who"])
        n = net.setdefault(k, {"symbol": it["symbol"], "who": it["who"], "bought": 0.0, "sold": 0.0, "value": 0.0})
        sign = 1 if it["side"] == "BUY" else -1
        n["bought" if sign > 0 else "sold"] += it["qty"]
        n["value"] += sign * (it["value"] or 0)
    rows = [dict(v, net=v["bought"] - v["sold"]) for v in net.values()]
    rows.sort(key=lambda r: -abs(r["value"]))
    return rows


# ---------------------------------------------------------------- commands

def main(argv=None):
    ap = argparse.ArgumentParser(description="Bulk, block and insider trades on NSE (trader-insider).")
    sub = ap.add_subparsers(dest="cmd")
    for name, helptext in (("check", "what is new since the last check"), ("show", "list what is in the files"),
                           ("summary", "net buy / sell by stock and client")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("files", nargs="+", help="CSV or JSON saved from nseindia.com")
        p.add_argument("--symbol", action="append", default=[], help="only this stock (repeat for more)")
        p.add_argument("--mine", action="store_true", help="only your holdings, watchlist and plan")
        p.add_argument("--min-value-cr", type=float, default=0, help="only trades worth at least this many crore")
        p.add_argument("--since", help="only trades on or after YYYY-MM-DD")
        p.add_argument("--portfolio", default="trader/portfolio.json")
        p.add_argument("--watchlist", default="trader/watchlist.json")
        p.add_argument("--plan", default="trader/plan.json")
        p.add_argument("--json", action="store_true")
        if name == "check":
            p.add_argument("--state", default="trader/state/insider.json")
            p.add_argument("--dry-run", action="store_true", help="do not update the state file")
            p.add_argument("--today", help="YYYY-MM-DD, for reproducible runs")
        if name == "show":
            p.add_argument("--all", action="store_true", help="(the default for show)")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    try:
        items, notes = read_files(a.files)
    except DealsError as e:
        print("deals.py: %s" % e, file=sys.stderr)
        return 1
    mine = my_tickers(a.portfolio, a.watchlist, a.plan)
    want = {s.upper() for s in a.symbol}
    picked = [it for it in items
              if (not want or it["symbol"] in want)
              and (not a.mine or it["symbol"] in mine)
              and (not a.min_value_cr or (it["value"] or 0) >= a.min_value_cr * CRORE)
              and (not a.since or (it["date"] or "") >= a.since)]
    picked.sort(key=lambda it: (it["date"] or "", it["symbol"] in mine, it["value"] or 0), reverse=True)

    if a.cmd == "summary":
        rows = summary(picked)
        if a.json:
            print(json.dumps(rows, indent=2))
            return 0 if rows else 1
        print("Net by stock and client (buys minus sells), biggest money first:")
        for r in rows[:40]:
            flag = ("  <- your %s" % mine[r["symbol"]]) if r["symbol"] in mine else ""
            print("  %-12s %-45s net %12s shares  %s%s" % (r["symbol"], r["who"][:45], indian(r["net"]),
                                                         ("+" if r["value"] >= 0 else "-") + cr(abs(r["value"])), flag))
        flat = sum(1 for r in rows if r["net"] == 0)
        if flat:
            print("%d client(s) bought and sold the same number of shares: intraday or market-making, "
                  "not a position." % flat)
        return 0 if rows else 1

    if a.cmd == "check":
        today = a.today or _dt.date.today().isoformat()
        state = load_state(a.state)
        seen = state.get("seen", {})
        shown = [it for it in picked if it["id"] not in seen]
    else:
        shown = picked
    if a.json:
        print(json.dumps({"items": shown, "notes": notes}, indent=2))
    else:
        hit = [it for it in shown if it["symbol"] in mine]
        print("%d %s%s." % (len(shown), "new item" if a.cmd == "check" else "item",
                            "" if len(shown) == 1 else "s") + (
            " %d in your stocks." % len(hit) if hit else ""))
        for it in shown[:200]:
            for line in describe(it, mine):
                print(line)
        if len(shown) > 200:
            print("... and %d more (use --symbol, --mine or --min-value-cr)." % (len(shown) - 200))
        for n in notes:
            print("note: " + n)
        print("Public disclosures, published after the trade. A fact, not a forecast; not advice.")
    if a.cmd == "check" and not a.dry_run:
        remember(items, state, today)
        save_state(a.state, state)
    return 0 if shown else 1


if __name__ == "__main__":
    sys.exit(main())
