#!/usr/bin/env python3
"""News monitor for trader-news. Standard library only.

Watches headlines for the NSE stocks you watch or hold and prints only what
is new since the last check, newest first, with how far each stock has moved
today and a flag on anything that touches your tickers.

    python3 news.py                                  # watchlist + plan + portfolio tickers
    python3 news.py --tickers RELIANCE TCS M&M
    python3 news.py --tickers RELIANCE --all --hours 72  # everything in the last 3 days, seen or not
    python3 news.py --market                         # also the market: NIFTY, Sensex, RBI, SEBI, FII flows
    python3 news.py --no-moves                       # skip the price line per ticker

Your tickers, when --tickers is not given: every hit in trader/watchlist.json
(trader-scanner), the symbol in trader/plan.json (trader-exit) and the
positions in trader/portfolio.json.

Sources, one request each per ticker:
  - Google News RSS, India edition, searched by the company's name (from
    trader/universe.txt, the scanner's bundled NIFTY 50 list, or --name):
    https://news.google.com/rss/search?q=%22Reliance+Industries%22+when:2d&hl=en-IN&gl=IN&ceid=IN:en
    It carries Moneycontrol, Economic Times, Business Standard, Mint, CNBC-TV18,
    Reuters and the rest, each item with its own source.
  - The move: Yahoo Finance's chart endpoint (unofficial, can lag), the last
    price against yesterday's close:
    https://query2.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=1d&interval=5m

Exchange filings (results, board meetings, dividends, insider and bulk deals)
are on nseindia.com and bseindia.com, which do not serve scripts: open the
company's "Corporate announcements" page there, or ask your broker's
connector. Headlines usually carry the big ones within minutes.

Times print in IST. State: trader/state/news.json remembers what you have
seen (30 days), so an item shows once. Offline: --offline DIR reads
gnews-<TICKER>.xml (gnews-MARKET.xml for --market) and chart-<TICKER>.json
from DIR. The tests use it.

Headlines are leads, not facts: open the story before acting, and treat
nothing here as advice.
"""

import argparse
import datetime as _dt
import email.utils
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

GNEWS = "https://news.google.com/rss/search?q=%s&hl=en-IN&gl=IN&ceid=IN:en"
CHART = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m"
MARKET_QUERY = "(Nifty OR Sensex OR RBI OR SEBI OR FII OR \"stock market\") India"
BROWSER_UA = "Mozilla/5.0 (compatible; day-trader-skill-india/1.0; +https://github.com/msoni11/day-trader-skill)"
BUNDLED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trader-scanner", "nifty50.txt")
KEEP_DAYS = 30
MOVE_PCT = 3.0  # a stock this far from yesterday's close is flagged as moving
SUFFIX = re.compile(r"\s+(Ltd\.?|Limited|Ltd|Corporation|Corp\.?|Company|Co\.?)$", re.I)

KEYWORDS = [
    ("earnings", r"\bresults?\b|\bQ[1-4]\b|\bearnings\b|\bprofit\b|\brevenue\b|\bmargin|\bguidance\b|\bEBITDA\b"),
    ("analyst", r"\bupgrade[sd]?\b|\bdowngrade[sd]?\b|target price|price target|\bbuy rating\b|\bsell rating\b|"
                r"\boverweight\b|\bunderweight\b|\bbrokerages?\b"),
    ("legal", r"\blawsuit\b|\bprobe\b|\binvestigation\b|\bcourt\b|\bNCLT\b|\bED raid|\btax notice|\bpenalty\b"),
    ("deal", r"\bacqui(?:re|res|red|sition)\b|\bmerger\b|\bdemerger\b|\bstake\b|\btakeover\b|\bdeal\b|\border win|"
             r"\bbags? (?:an? )?order|\bcontract\b"),
    ("capital", r"\bdividend\b|\bbuyback\b|\bbonus\b|\bstock split\b|\bsplit\b|\bQIP\b|\brights issue\b|\bOFS\b|"
                r"\bIPO\b|\blisting\b|\bfund ?rais"),
    ("insider", r"\bpromoters?\b|\bpledge|\bbulk deal|\bblock deal|\binsider\b|\bstake sale|\bFII\b|\bDII\b|\bmutual funds? (?:buy|sell)"),
    ("people", r"\bCEO\b|\bCFO\b|\bMD\b|\bresign|\bsteps down\b|\bappoint"),
    ("risk", r"\bdefault\b|\bdowngrade\b by (?:CRISIL|ICRA|CARE|India Ratings)|\binsolvency\b|\bdelist|\bfraud\b|"
             r"\bhack|\bbreach\b|\bfire\b|\bshutdown\b"),
    ("circuit", r"\bupper circuit\b|\blower circuit\b|\bcircuit\b|\bF&O ban\b|\bban period\b|\bASM\b|\bGSM\b|\bsurveillance\b"),
    ("regulatory", r"\bSEBI\b|\bRBI\b|\bUSFDA\b|\bFDA\b|\bCCI\b|\bTRAI\b|\bDGCA\b|\bapproval\b|\blicen[cs]e\b"),
    ("macro", r"\brepo rate\b|\bmonetary policy\b|\bCPI\b|\binflation\b|\bGDP\b|\brupee\b|\bcrude\b|\bbudget\b|"
              r"\bGST\b|\btariffs?\b|\bFed\b|\bGIFT Nifty\b"),
]


class NewsError(Exception):
    pass


# ---------------------------------------------------------------- time

IST = _dt.timedelta(hours=5, minutes=30)   # India Standard Time, UTC+5:30, no daylight saving


def to_ist(utc):
    return utc.replace(tzinfo=None) + IST


def ist_to_utc(local):
    return local.replace(tzinfo=None) - IST


def load_json(path):
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def watch_from_files(portfolio="trader/portfolio.json", watchlist="trader/watchlist.json",
                     plan="trader/plan.json"):
    """{ticker: name or None}: the scanner's hits, the planned trade and your holdings."""
    out = {}
    wl = load_json(watchlist) or {}
    for h in wl.get("hits", []):
        sym = h.get("symbol") or h.get("ticker")
        if sym:
            out[sym.upper()] = h.get("name")
    pl = load_json(plan) or {}
    if pl.get("symbol"):
        out.setdefault(pl["symbol"].upper(), pl.get("name"))
    pf = load_json(portfolio) or {}
    for p in pf.get("positions", []):
        sym = p.get("ticker") or p.get("symbol")
        if sym:
            out[sym.upper()] = p.get("name") or out.get(sym.upper())
    return out


def names_from_lists(paths=("trader/universe.txt", BUNDLED)):
    """{SYMBOL: company name} from the scanner's universe file and its bundled NIFTY 50 list."""
    out = {}
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln and not ln.startswith("#") and "|" in ln:
                    parts = ln.split("|")
                    out.setdefault(parts[0].strip().upper(), parts[1].strip())
    return out


def search_query(ticker, name):
    """The Google News query for one stock: its company name in quotes, or the symbol and "share"."""
    if name:
        short = SUFFIX.sub("", name.strip())
        return '"%s" when:2d' % short
    return '"%s" share NSE when:2d' % ticker


# ---------------------------------------------------------------- fetching

class Fetcher(object):
    def __init__(self, offline=None, pause=0.3):
        self.offline = offline
        self.pause = pause
        self._last = 0.0

    def get(self, url, name):
        if self.offline:
            path = os.path.join(self.offline, name)
            if not os.path.isfile(path):
                raise NewsError("offline: no file %s" % path)
            with open(path, "rb") as fh:
                return fh.read()
        gap = time.time() - self._last
        if gap < self.pause:
            time.sleep(self.pause - gap)
        self._last = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return data
        except urllib.error.HTTPError as exc:
            raise NewsError("HTTP %s for %s" % (exc.code, url.split("?")[0]))
        except urllib.error.URLError as exc:
            raise NewsError("could not reach %s: %s" % (url.split("/")[2], exc.reason))


def yahoo_symbol(ticker):
    """RELIANCE -> RELIANCE.NS; .NS, .BO (BSE) and ^ indices stay as they are."""
    s = ticker.strip().upper()
    s = s if s.startswith("^") or s.endswith((".NS", ".BO")) else s + ".NS"
    return urllib.parse.quote(s, safe=".")


def safe_name(ticker):
    return re.sub(r"[^A-Z0-9.\-]", "", ticker.upper())


# ---------------------------------------------------------------- parsing

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _text(el, name):
    for c in el.iter():
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def parse_time(value):
    """RFC 822 (RSS) or ISO 8601 (Atom) -> aware UTC datetime, or None."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d.astimezone(_dt.timezone.utc)


def parse_rss(data, ticker):
    """Google News RSS -> items. Its titles end in " - <source>"; the source is kept apart."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise NewsError("RSS for %s is not valid XML: %s" % (ticker, exc))
    out = []
    for it in root.iter("item"):
        title = _text(it, "title")
        src = _text(it, "source") or "Google News"
        if src and title.endswith(" - " + src):
            title = title[:-len(src) - 3].rstrip()
        link = _text(it, "link")
        guid = _text(it, "guid") or link
        out.append({"id": "gnews:" + guid, "source": src[:28], "kind": "headline",
                    "ticker": ticker, "title": title, "summary": "",
                    "link": link, "time": parse_time(_text(it, "pubDate"))})
    return out


def parse_chart(data, ticker):
    """Yahoo chart JSON -> {"ticker", "price", "prev_close", "pct", "time"} or raise."""
    try:
        doc = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
        meta = doc["chart"]["result"][0]["meta"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise NewsError("chart for %s is not usable" % ticker)
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if not price or not prev:
        raise NewsError("chart for %s has no price" % ticker)
    when = meta.get("regularMarketTime")
    return {"ticker": ticker, "price": round(float(price), 2), "prev_close": round(float(prev), 2),
            "pct": round((float(price) / float(prev) - 1) * 100, 2),
            "time": _dt.datetime.fromtimestamp(when, _dt.timezone.utc) if when else None}


def collect_moves(fetcher, watch, errors=None):
    errors = [] if errors is None else errors
    out = []
    for t in sorted(watch):
        name = "chart-%s.json" % t
        try:
            try:
                data = fetcher.get(CHART % ("query2", yahoo_symbol(t)), "chart-%s.json" % safe_name(t))
            except NewsError as exc:
                if fetcher.offline or not re.search(r"HTTP (429|5\d\d)", str(exc)):
                    raise
                data = fetcher.get(CHART % ("query1", yahoo_symbol(t)), "chart-%s.json" % safe_name(t))
            out.append(parse_chart(data, t))
        except NewsError as exc:
            if not (fetcher.offline and "no file" in str(exc)):
                errors.append("price for %s: %s" % (t, exc))
    return out


def mention_patterns(watch):
    pats = {}
    for t, name in watch.items():
        alts = [r"\(%s\)" % re.escape(t), r"\b(?:NSE|BSE)\s*:\s*%s\b" % re.escape(t)]
        if len(t) >= 4 and t.isalpha():
            alts.append(r"\b%s\b" % re.escape(t))
        if name and len(name) >= 4:
            alts.append(r"\b%s\b" % re.escape(SUFFIX.sub("", name)).replace(r"\ ", r"[\s-]"))
        pats[t] = re.compile("|".join(alts))
    return pats


def tag(items, watch):
    """Which of your tickers each item touches, and why it matters."""
    pats = mention_patterns(watch)
    for it in items:
        hay = "%s %s" % (it["title"], it.get("summary") or "")
        touches = {it["ticker"]} if it["ticker"] in watch else set()
        for t, rx in pats.items():
            if rx.search(hay):
                touches.add(t)
        it["touches"] = sorted(touches)
        it["tags"] = [label for label, rx in KEYWORDS if re.search(rx, hay, re.I)]
    return items


def dedupe(items):
    """One item per story: same id, or same link, or same title the same day."""
    seen, out = {}, []
    for it in items:
        keys = [it["id"], it["link"],
                "%s|%s" % (re.sub(r"\W+", " ", it["title"].lower()).strip(),
                           it["time"].date() if it["time"] else "")]
        hit = next((seen[k] for k in keys if k and k in seen), None)
        if hit is not None:
            for t in it.get("touches", []):
                if t not in hit["touches"]:
                    hit["touches"].append(t)
            hit["touches"].sort()
            continue
        for k in keys:
            if k:
                seen[k] = it
        out.append(it)
    return out


def fingerprint(it):
    return hashlib.sha1(it["id"].encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- the check

def collect(fetcher, watch, market=False, errors=None):
    errors = [] if errors is None else errors
    items = []
    for t in sorted(watch):
        q = search_query(t, watch[t])
        try:
            items += parse_rss(fetcher.get(GNEWS % urllib.parse.quote_plus(q), "gnews-%s.xml" % safe_name(t)), t)
        except NewsError as exc:
            errors.append("headlines for %s: %s" % (t, exc))
    if market:
        try:
            items += parse_rss(fetcher.get(GNEWS % urllib.parse.quote_plus(MARKET_QUERY + " when:1d"),
                                           "gnews-MARKET.xml"), "MARKET")
        except NewsError as exc:
            errors.append("market headlines: %s" % exc)
    return items


def select(items, state, now, hours=48, show_all=False):
    """Items within the window; only unseen ones unless show_all."""
    seen = state.setdefault("seen", {})
    cutoff = now - _dt.timedelta(hours=hours)
    ahead = now + _dt.timedelta(minutes=10)  # a pinned --now: nothing from after it
    out = []
    for it in items:
        if it["time"] is not None and (it["time"] < cutoff or it["time"] > ahead):
            continue
        fp = fingerprint(it)
        it["new"] = fp not in seen
        if it["new"] or show_all:
            out.append(it)
    out.sort(key=lambda i: (i["time"] or now), reverse=True)
    return out


def remember(items, state, now):
    seen = state.setdefault("seen", {})
    stamp = now.isoformat()
    for it in items:
        seen.setdefault(fingerprint(it), stamp)
    cutoff = (now - _dt.timedelta(days=KEEP_DAYS)).isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= cutoff}
    state["last_check"] = stamp


def render_moves(moves, move_pct=MOVE_PCT):
    out = []
    for m in moves:
        flag = "MOVING" if abs(m["pct"]) >= move_pct else ""
        when = (" at %s IST" % to_ist(m["time"]).strftime("%H:%M")) if m.get("time") else ""
        out.append("%-10s %s %+.2f%% vs yesterday's close %s%s  %s" % (
            m["ticker"], "{:,.2f}".format(m["price"]), m["pct"], "{:,.2f}".format(m["prev_close"]),
            when, flag))
    return out


def render(items, errors, now, moves=None, move_pct=MOVE_PCT):
    out = render_moves(moves or [], move_pct)
    if out:
        out.append("")
    if not items:
        out.append("Nothing new.")
    for it in items:
        when = to_ist(it["time"]).strftime("%Y-%m-%d %H:%M IST") if it["time"] else "time unknown"
        mark = "!" if it.get("important") else " "
        who = ",".join(it["touches"]) or it["ticker"]
        out.append("%s %s  %-11s %-22s %s" % (mark, when, who, it["source"][:22], it["title"]))
        extra = []
        if it["tags"]:
            extra.append("tags: " + ", ".join(it["tags"]))
        extra.append(it["link"])
        out.append("      " + "  ".join(extra))
    for e in errors:
        out.append("note: %s" % e)
    out.append("Checked %s. Headlines are leads, not facts; open the story before acting. "
               "Not financial advice." % to_ist(now).strftime("%Y-%m-%d %H:%M IST"))
    return "\n".join(out) + "\n"


def _json_ready(items):
    out = []
    for it in items:
        d = dict(it)
        d["time"] = it["time"].isoformat() if it["time"] else None
        out.append(d)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tickers", nargs="*", help="default: watchlist + plan + portfolio")
    ap.add_argument("--portfolio", default="trader/portfolio.json")
    ap.add_argument("--watchlist", default="trader/watchlist.json")
    ap.add_argument("--plan", default="trader/plan.json")
    ap.add_argument("--state", default="trader/state/news.json")
    ap.add_argument("--hours", type=float, default=48, help="ignore items older than this")
    ap.add_argument("--all", action="store_true", help="show seen items too")
    ap.add_argument("--name", action="append", default=[], metavar="SYM=Company Name",
                    help="the name to search for a ticker, e.g. --name \"M&M=Mahindra & Mahindra\"")
    ap.add_argument("--market", action="store_true", help="also market-wide news (NIFTY, Sensex, RBI, SEBI)")
    ap.add_argument("--no-moves", action="store_true", help="skip the price line per ticker")
    ap.add_argument("--move-pct", type=float, default=MOVE_PCT, help="flag a move this big (percent)")
    ap.add_argument("--universe", default="trader/universe.txt", help="SYMBOL|Name lines for the search names")
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--now", help="ISO time, for reproducible runs")
    ap.add_argument("--dry-run", action="store_true", help="do not update the state file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.tickers:
        watch = {t.upper(): None for t in args.tickers}
        known = watch_from_files(args.portfolio, args.watchlist, args.plan)
        watch.update({t: known[t] for t in watch if known.get(t)})
    else:
        watch = watch_from_files(args.portfolio, args.watchlist, args.plan)
    names = names_from_lists((args.universe, BUNDLED))
    for t in watch:
        watch[t] = watch[t] or names.get(t)
    for pair in args.name:
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k.strip().upper() in watch:
                watch[k.strip().upper()] = v.strip()
    if not watch:
        print("news: no tickers. Pass --tickers, or run /trader-scanner first (it writes "
              "trader/watchlist.json).", file=sys.stderr)
        return 2
    now = parse_time(args.now) if args.now else _dt.datetime.now(_dt.timezone.utc)
    state = load_json(args.state) or {}
    errors = []
    fetcher = Fetcher(offline=args.offline)
    items = collect(fetcher, watch, market=args.market, errors=errors)
    items = dedupe(tag(items, watch))
    shown = select(items, state, now, hours=args.hours, show_all=args.all)
    moves = [] if args.no_moves else collect_moves(fetcher, watch, errors)
    if args.json:
        mv = [dict(m, time=m["time"].isoformat() if m.get("time") else None,
                   moving=abs(m["pct"]) >= args.move_pct) for m in moves]
        print(json.dumps({"checked": now.isoformat(), "moves": mv, "items": _json_ready(shown),
                          "notes": errors}, indent=2))
    else:
        sys.stdout.write(render(shown, errors, now, moves, args.move_pct))
    if not args.dry_run:
        remember(items, state, now)
        folder = os.path.dirname(args.state)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
    return 0 if any(i["new"] for i in shown) else 1


if __name__ == "__main__":
    sys.exit(main())
