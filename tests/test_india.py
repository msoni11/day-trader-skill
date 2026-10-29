"""The NSE calendar in every script, and the data skills (alerts, news, analyst, insider), plus repo checks."""

import contextlib
import datetime
import io
import json
import os
import re
import shutil
import tempfile
import unittest

from _load import FIX, ROOT, load

SKILLS = ["trader-scanner", "trader-news", "trader-entry", "trader-exit", "trader-timemachine",
          "trader-risk", "trader-budget", "trader-broker", "trader-alerts", "trader-analyst", "trader-insider"]
CALENDAR_SCRIPTS = [("trader-entry", "entry"), ("trader-exit", "exit"), ("trader-scanner", "scan"),
                    ("trader-risk", "check"), ("trader-alerts", "alerts")]
D = datetime.date


def quiet(fn, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = fn(list(argv))
    return code, out.getvalue()


class Calendar(unittest.TestCase):
    def test_every_script_knows_the_same_nse_days(self):
        for folder, name in CALENDAR_SCRIPTS:
            m = load(folder, name)
            self.assertEqual(m.trading_day(D(2026, 10, 29)), (True, ""), name)
            self.assertFalse(m.trading_day(D(2026, 10, 20))[0], name)             # Dussehra
            self.assertFalse(m.trading_day(D(2026, 1, 15))[0], name)              # Maharashtra civic polls
            self.assertFalse(m.trading_day(D(2026, 11, 10))[0], name)             # Balipratipada
            self.assertEqual(m.trading_day(D(2026, 10, 31)), (False, "weekend"), name)
            self.assertTrue(m.trading_day(D(2026, 11, 8))[0], name)               # Muhurat, a Sunday
            if hasattr(m, "session"):
                self.assertEqual(m.session(D(2026, 10, 29)), (datetime.time(9, 15), datetime.time(15, 30)), name)
                self.assertEqual(m.session(D(2026, 11, 8)), (datetime.time(14, 20), datetime.time(15, 30)), name)
            self.assertEqual(m.NSE_HOLIDAYS, load("trader-entry", "entry").NSE_HOLIDAYS, name)

    def test_ist_has_no_daylight_saving(self):
        for folder, name in CALENDAR_SCRIPTS + [("trader-budget", "size"), ("trader-broker", "ticket"),
                                                ("trader-timemachine", "timemachine")]:
            m = load(folder, name)
            for when in ("2026-01-10 09:15", "2026-07-10 09:15"):
                utc = m.parse_now(when)
                self.assertEqual(m.to_ist(utc).strftime("%Y-%m-%d %H:%M"), when, name)
                self.assertEqual(utc.strftime("%H:%M"), "03:45", name)

    def test_real_bars_skip_the_holidays(self):
        """Yahoo's 60 days of RELIANCE bars have no session on the listed weekday holidays."""
        import gzip
        tm = load("trader-timemachine", "timemachine")
        with gzip.open(os.path.join(FIX, "nse", "RELIANCE-60d5m.json.gz"), "rt") as fh:
            res = tm.chart_result(fh.read(), "RELIANCE")
        days = {tm.to_ist(tm.utc_of(t)).date().isoformat() for t in res["timestamp"]}
        entry = load("trader-entry", "entry")
        for h in entry.NSE_HOLIDAYS:
            if min(days) <= h <= max(days):
                self.assertNotIn(h, days, h)


class Alerts(unittest.TestCase):
    alerts = load("trader-alerts", "alerts")

    def status(self, when):
        return self.alerts.market_status(self.alerts.parse_now(when))

    def test_clock(self):
        self.assertIn("pre-open", self.status("2026-10-29 09:05")["reason"])
        self.assertTrue(self.status("2026-10-29 11:00")["open"])
        self.assertFalse(self.status("2026-10-29 15:30")["open"])
        mu = self.status("2026-11-08 14:30")
        self.assertTrue(mu["open"])
        self.assertEqual(mu["special_session"], "Muhurat trading (Diwali)")
        self.assertEqual(self.status("2026-11-10 10:00")["next_open"], "2026-11-11 09:15")

    def test_flat_by_stays_inside_muhurat(self):
        st = self.status("2026-11-08 14:30")
        self.assertEqual(self.alerts.ring_time({"at": "15:40", "before_close": True}, st), datetime.time(15, 10))
        self.assertEqual(self.alerts.ring_time({"at": "15:10", "before_close": True}, self.status("2026-10-29 11:00")),
                         datetime.time(15, 10))

    def test_quote_from_a_saved_chart(self):
        with open(os.path.join(FIX, "nse", "RELIANCE-2026-10-29-5m.json"), encoding="utf-8") as fh:
            q = self.alerts.parse_yahoo(fh.read(), "RELIANCE")
        self.assertEqual((q["currency"], q["prev_close"]), ("INR", 1158.0))
        self.assertIn("RELIANCE.NS", self.alerts.yahoo_url("RELIANCE"))


class News(unittest.TestCase):
    news = load("trader-news", "news")
    DIR = os.path.join(FIX, "trader-news")

    def test_google_news_items(self):
        with open(os.path.join(self.DIR, "gnews-RELIANCE.xml"), "rb") as fh:
            items = self.news.parse_rss(fh.read(), "RELIANCE")
        self.assertEqual(len(items), 100)
        self.assertTrue(all(not i["title"].endswith(" - " + i["source"]) for i in items))
        self.assertIn("Reuters", {i["source"] for i in items})

    def test_tags_and_query(self):
        items = [{"id": "x", "ticker": "RELIANCE", "kind": "headline", "summary": "", "link": "", "time": None,
                  "title": "Reliance Industries Q2 results: net profit rises; board approves bonus issue"}]
        self.news.tag(items, {"RELIANCE": "Reliance Industries Ltd"})
        self.assertEqual(items[0]["tags"], ["earnings", "capital"])
        self.assertEqual(self.news.search_query("RELIANCE", "Reliance Industries Ltd"), '"Reliance Industries" when:2d')

    def test_offline_run(self):
        code, out = quiet(self.news.main, "--tickers", "RELIANCE", "--offline", self.DIR,
                          "--now", "2026-10-29T14:20:00Z", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("RELIANCE   1,167.40 +0.81% vs yesterday's close 1,158.00", out)


class Analyst(unittest.TestCase):
    facts = load("trader-analyst", "facts")

    def test_indian_fiscal_quarters(self):
        f = self.facts.fy_label
        self.assertEqual([f("2026-06-30"), f("2026-09-30"), f("2026-12-31"), f("2027-03-31")],
                         ["Q1 FY27", "Q2 FY27", "Q3 FY27", "Q4 FY27"])

    def test_reliance(self):
        with open(os.path.join(FIX, "trader-analyst", "timeseries-RELIANCE.json"), encoding="utf-8") as fh:
            q, cur = self.facts.parse(fh.read(), "RELIANCE")
        r = self.facts.analyse(q)
        top = r["quarters"][0]
        self.assertEqual((cur, top["label"], top["revenue_yoy"], top["net_income_yoy"]), ("INR", "Q1 FY27", 27.0, -22.4))
        self.assertEqual(round(top["revenue"] / self.facts.CRORE), 309468)
        self.assertEqual(r["missing"], ["Q2 FY26"])
        self.assertIsNone(r["ttm"])        # Q2 FY26 is missing, so no four quarters in a row


class Insider(unittest.TestCase):
    deals = load("trader-insider", "deals")
    DIR = os.path.join(FIX, "trader-insider")

    def test_indian_numbers(self):
        self.assertEqual(self.deals.number("66,44,519"), 6644519.0)
        self.assertEqual(self.deals.indian(6644519), "66,44,519")
        self.assertEqual(self.deals.parse_date("22-OCT-2026"), "2026-10-22")
        self.assertEqual(self.deals.parse_date("29-Oct-2026 15:40:56"), "2026-10-29")

    def test_files_and_summary(self):
        items, notes = self.deals.read_files([os.path.join(self.DIR, "bulk-2026-10-22.csv"),
                                              os.path.join(self.DIR, "pit-2026-10-29.json")])
        self.assertEqual(notes, [])
        self.assertEqual(sum(1 for i in items if i["kind"] == "insider"), 3)
        lt = [i for i in items if i["who"] == "LARSEN & TOUBRO LIMITED"][0]
        self.assertEqual((lt["side"], lt["qty"], round(lt["value"] / 1e7, 2)), ("BUY", 6644519.0, 50.23))
        net = {(r["symbol"], r["who"]): r["net"] for r in self.deals.summary(items)}
        self.assertEqual(net[("DCMSRIND", "ALPHAGREP SECURITIES PRIVATE LIMITED")], 0)

    def test_new_since_last_check(self):
        d = tempfile.mkdtemp()
        try:
            state = os.path.join(d, "s.json")
            f = os.path.join(self.DIR, "bulk-2026-10-22.csv")
            self.assertEqual(quiet(self.deals.main, "check", f, "--state", state, "--today", "2026-10-29")[0], 0)
            self.assertEqual(quiet(self.deals.main, "check", f, "--state", state, "--today", "2026-10-29")[0], 1)
        finally:
            shutil.rmtree(d)


class Repo(unittest.TestCase):
    def test_eleven_skill_folders(self):
        found = sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "SKILL.md")))
        self.assertEqual(found, sorted(SKILLS))

    def test_frontmatter_and_safety(self):
        for s in SKILLS:
            with open(os.path.join(ROOT, s, "SKILL.md"), encoding="utf-8") as fh:
                text = fh.read()
            m = re.match(r"^---\nname: (.*?)\ndescription: >-\n(.*?)\n---\n", text, re.S)
            self.assertTrue(m, s)
            self.assertEqual(m.group(1), s)
            self.assertLessEqual(len(" ".join(m.group(2).split())), 1024, s)
            self.assertIn("not financial advice", text.lower(), s)

    def test_nothing_american_left_in_the_skills(self):
        us = re.compile(r"\b(TSLA|NYSE|Alpaca|alpaca|New York|EDGAR|Nasdaq Trader|pdt_guard|_usd)\b|\$\d")
        for s in SKILLS:
            for f in os.listdir(os.path.join(ROOT, s)):
                if f.endswith((".py", ".md", ".json", ".txt")):
                    with open(os.path.join(ROOT, s, f), encoding="utf-8") as fh:
                        for n, line in enumerate(fh, 1):
                            self.assertIsNone(us.search(line), "%s/%s:%d %s" % (s, f, n, line.strip()))

    def test_manifests(self):
        for f in ("plugin.json", "marketplace.json"):
            with open(os.path.join(ROOT, ".claude-plugin", f), encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertIn("india", json.dumps(doc).lower(), f)


if __name__ == "__main__":
    unittest.main()
