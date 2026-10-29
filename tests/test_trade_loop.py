"""The example trade end to end on real data: RELIANCE, NSE, Thursday 29 October 2026.
scanner -> entry -> exit -> timemachine -> budget -> risk -> broker, every number the README quotes."""

import contextlib
import datetime
import gzip
import io
import json
import os
import shutil
import tempfile
import unittest

from _load import FIX, ROOT, load

scan = load("trader-scanner", "scan")
entry = load("trader-entry", "entry")
exitp = load("trader-exit", "exit")
tm = load("trader-timemachine", "timemachine")
size = load("trader-budget", "size")
check = load("trader-risk", "check")
ticket = load("trader-broker", "ticket")

NSE = os.path.join(FIX, "nse")
DAY = os.path.join(NSE, "RELIANCE-2026-10-29-5m.json")
SIXTY = os.path.join(NSE, "RELIANCE-60d5m.json.gz")
WALL = os.path.join(NSE, "wall5m-2026-10-29.json.gz")
DAILY = os.path.join(NSE, "daily-spark-2026-10-29.json.gz")
CONFIG = os.path.join(ROOT, "trader-budget", "config.example.json")


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def quiet(fn, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = fn(list(argv))
    return code, out.getvalue()


class InTemp(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)
        os.makedirs("trader")
        shutil.copy(CONFIG, "trader/config.json")

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)


class Scanner(unittest.TestCase):
    def test_orb_at_940_finds_twelve_including_reliance(self):
        data, _ = scan.load_offline(WALL)
        syms = sorted(data)
        self.assertEqual(len(syms), 50)
        day = datetime.date(2026, 10, 29)
        hits, counts, _ = scan.scan_orb(data, syms, day, datetime.datetime(2026, 10, 29, 9, 40), 15, 50.0, 0)
        self.assertEqual(len(hits), 12)
        rel = [h for h in hits if h["symbol"] == "RELIANCE"][0]
        self.assertEqual((rel["price"], rel["or_high"], rel["or_low"], rel["at"]), (1174.3, 1170.5, 1156.2, "9:40 AM"))

    def test_orb_by_ten_finds_twenty_two(self):
        data, _ = scan.load_offline(WALL)
        hits, _, _ = scan.scan_orb(data, sorted(data), datetime.date(2026, 10, 29),
                                   datetime.datetime(2026, 10, 29, 10, 0), 15, 50.0, 0)
        self.assertEqual(len(hits), 22)

    def test_daily_scan_on_real_closes(self):
        data, _ = scan.load_offline(DAILY)
        hits, counts, last = scan.scan_daily(data, sorted(data), scan.parse_now("2026-10-29 08:45"), 50.0, 100000)
        self.assertEqual(counts["fetched"], 50)
        self.assertEqual(len(hits), 14)
        self.assertIn("M&M", [h["symbol"] for h in hits])

    def test_yahoo_symbols(self):
        self.assertEqual(scan.to_yahoo("RELIANCE"), "RELIANCE.NS")
        self.assertEqual(scan.to_yahoo("500325.BO"), "500325.BO")
        self.assertEqual(scan.to_yahoo("^NSEI"), "^NSEI")
        self.assertEqual(scan.from_yahoo("M&M.NS"), "M&M")
        self.assertIn("M%26M.NS", scan.spark_path(["M&M"], "1d", "5m"))


class Entry(unittest.TestCase):
    def chart(self):
        return entry.get_chart("RELIANCE", "5m", offline=DAY)

    def test_waiting_at_936(self):
        r = entry.evaluate(self.chart(), entry.parse_now("2026-10-29 09:36"))
        self.assertEqual(r["status"], "waiting")
        self.assertEqual(r["opening_range"]["high"], 1170.5)

    def test_triggered_at_940(self):
        r = entry.evaluate(self.chart(), entry.parse_now("2026-10-29 09:40"))
        self.assertEqual(r["status"], "triggered")
        self.assertEqual((r["trigger"]["time"], r["trigger"]["price"], r["trigger"]["bar_index"]), ("9:40 AM", 1174.3, 4))

    def test_broker_candles_read_the_same_as_yahoo(self):
        ch = self.chart()
        doc = {"symbol": "RELIANCE", "interval": "5m",
               "candles": [[(entry.EPOCH + datetime.timedelta(seconds=b["t"], hours=5, minutes=30)).strftime(
                   "%Y-%m-%dT%H:%M:%S+0530"), b["o"], b["h"], b["l"], b["c"], b["v"]] for b in ch["bars"]]}
        other = entry.parse_chart(json.dumps(doc), "RELIANCE")
        self.assertEqual([b["t"] for b in other["bars"]], [b["t"] for b in ch["bars"]])
        r = entry.evaluate(other, entry.parse_now("2026-10-29 09:40"))
        self.assertEqual(r["trigger"]["price"], 1174.3)

    def test_symbol_with_an_ampersand(self):
        ch = entry.get_chart("M&M", "5m", offline=os.path.join(NSE, "MM-2026-10-29-5m.json"))
        self.assertEqual(ch["symbol"], "M&M")
        self.assertEqual(entry.chart_path("M&M", "1d", "5m"), "/v8/finance/chart/M%26M.NS?range=1d&interval=5m")


class Exit(unittest.TestCase):
    def test_ticks(self):
        D = exitp.Decimal
        self.assertEqual([exitp.tick_for(p) for p in (162.37, 250, 999.95, 1174.3, 7294, 12000, 25000)],
                         [D("0.01"), D("0.05"), D("0.05"), D("0.10"), D("0.50"), D("1.00"), D("5.00")])

    def test_the_reel_plan(self):
        c = exitp.compute(1174.30, "or_mid", None, "r", exitp.D("1"), 1170.50, 1156.20)
        self.assertEqual((str(c["stop"]), str(c["target"]), str(c["risk"])), ("1163.30", "1185.30", "11.00"))

    def test_small_stock_uses_the_paisa_tick(self):
        c = exitp.compute(162.37, "pct", exitp.D("1"), "r", exitp.D("2"))
        self.assertEqual((str(c["stop"]), str(c["target"])), ("160.74", "165.63"))

    def test_flat_by_default_and_muhurat(self):
        self.assertEqual(exitp.resolve_flat_by(datetime.date(2026, 10, 29), None, {}, None)[0], "15:10")
        t, note = exitp.resolve_flat_by(datetime.date(2026, 11, 8), None, {"flat_by": "15:40"}, None)
        self.assertEqual(t, "15:10")
        self.assertIn("Muhurat", note)


class TimeMachine(unittest.TestCase):
    PLAN = {"symbol": "RELIANCE", "side": "buy", "date": "2026-10-29", "setup": "orb", "entry": 1174.30,
            "entry_time": "9:40 AM", "stop": 1163.30, "target": 1185.30, "stop_rule": "or_mid",
            "opening_range": {"high": 1170.5, "low": 1156.2, "minutes": 15}}

    def run_tm(self, until):
        with gzip.open(SIXTY, "rt") as fh:
            text = fh.read()
        return tm.time_machine(text, tm.normalize_plan(dict(self.PLAN)), tm.parse_now("2026-10-29 10:50"),
                               until=until)

    def test_the_reel_odds_to_1510(self):
        doc = self.run_tm("15:10")
        mc, h = doc["mc"], doc["history"]
        self.assertEqual((round(mc["p_target"] * 100, 1), round(mc["p_stop"] * 100, 1),
                          round(mc["p_neither"] * 100, 1)), (23.2, 32.8, 44.0))
        self.assertEqual(mc["pool_sessions"], 52)
        self.assertEqual(h["triggered"], 24)
        self.assertTrue(doc["verdict"].startswith("Leans toward the stop"))

    def test_muhurat_is_refused(self):
        with self.assertRaises(tm.TMError):
            with gzip.open(SIXTY, "rt") as fh:
                tm.time_machine(fh.read(), tm.normalize_plan(dict(self.PLAN, date="2026-11-08", entry_time="2:40 PM")),
                                tm.parse_now("2026-11-08 14:50"))


class Money(InTemp):
    def plan(self):
        quiet(entry.main, "check", "RELIANCE", "--now", "2026-10-29 09:40", "--offline", DAY, "--write")
        code, _ = quiet(exitp.main, "plan", "--target", "1R", "--write", "--now", "2026-10-29 09:41")
        self.assertEqual(code, 0)

    def test_charges_by_hand(self):
        c = size.charges(63, 1174.30, 1163.30)
        self.assertEqual(c, {"brokerage": 40.0, "stt": 18.32, "exchange": 4.37, "sebi": 0.15, "stamp": 2.22,
                             "gst": 8.01, "total": 73.07})

    def test_the_reel_size_and_risk_pass(self):
        self.plan()
        code, out = quiet(size.main, "--now", "2026-10-29 09:41", "--write")
        self.assertEqual(code, 0, out)
        self.assertIn("63 shares of RELIANCE", out)
        self.assertIn("All in at the stop: Rs 766.07", out)
        order = read_json("trader/orders.json")["orders"][0]
        self.assertEqual((order["exchange"], order["product"], order["qty"]), ("NSE", "MIS", "63"))
        code, out = quiet(check.main, "--now", "2026-10-29 09:41")
        self.assertEqual(code, 0, out)
        self.assertIn("max loss Rs 766.07 (limit Rs 1,000)", out)

    def test_charges_trim_the_size_to_the_max_loss(self):
        self.plan()
        cfg = read_json("trader/config.json")
        cfg.update(max_loss_per_trade_inr=700, max_position_pct=100, max_order_inr=200000)
        write_json("trader/config.json", cfg)
        code, out = quiet(size.main, "--now", "2026-10-29 09:41", "--json")
        s = json.loads(out)["sizing"]
        self.assertEqual(s["bound_by"], "max loss")
        self.assertLessEqual(s["max_loss_with_charges"], 700)
        self.assertGreater(s["qty"] * 11.0 + size.charges(s["qty"] + 1, 1174.3, 1163.3)["total"] + 11.0, 700)

    def test_window_and_square_off_block(self):
        self.plan()
        quiet(size.main, "--now", "2026-10-29 09:41", "--write")
        code, out = quiet(check.main, "--now", "2026-10-29 14:50", "--no-write")
        self.assertEqual(code, 1)
        self.assertIn("no new entries after 14:45", out)
        cfg = read_json("trader/config.json")
        cfg["square_off_by"] = "15:05"
        write_json("trader/config.json", cfg)
        code, out = quiet(check.main, "--now", "2026-10-29 09:41", "--no-write")
        self.assertIn("square-off", out)

    def test_broker_ticket_and_yes(self):
        self.plan()
        quiet(size.main, "--now", "2026-10-29 09:41", "--write")
        quiet(check.main, "--now", "2026-10-29 09:41")
        order = read_json("trader/orders.json")["orders"][0]
        self.assertEqual(ticket.fingerprint(order), check.fingerprint(order))
        code, out = quiet(ticket.main, "show", "--now", "2026-10-29 09:42")
        self.assertIn("SL-M (stop-loss market), trigger 1163.30", out)
        self.assertIn("READY", out)
        code, out = quiet(ticket.main, "approve", "--index", "1", "--reply", "sure", "--now", "2026-10-29 09:42")
        self.assertIn("Not recorded", out)
        code, out = quiet(ticket.main, "approve", "--index", "1", "--reply", "yes", "--now", "2026-10-29 09:42")
        self.assertEqual(code, 0, out)
        legs = ticket.kite_calls(order)
        self.assertEqual([l["args"]["order_type"] for l in legs], ["MARKET", "SL-M", "LIMIT"])
        self.assertEqual(legs[1]["args"]["trigger_price"], 1163.3)
        self.assertEqual(legs[0]["args"]["tradingsymbol"], "RELIANCE")


class RiskBasics(unittest.TestCase):
    def verdict(self, order, **cfg):
        c = read_json(CONFIG)
        c.update(cfg)
        res = check.check([order], c, portfolio={"cash": 100000, "positions": []}, prices={},
                          now=check.parse_now("2026-10-29 11:00"))
        return res["results"][0]

    def test_fno_and_notional_are_blocked(self):
        r = self.verdict({"symbol": "NIFTY26NOV24500CE", "side": "buy", "qty": "75", "type": "market"})
        self.assertEqual(r["verdict"], "BLOCK")
        self.assertTrue(any("F&O" in x for x in r["reasons"]))
        r = self.verdict({"symbol": "RELIANCE", "side": "buy", "notional": "5000", "type": "market"})
        self.assertTrue(any("whole-share" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main()
