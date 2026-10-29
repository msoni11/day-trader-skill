# The Day Trader skill, India edition

11 Claude skills for intraday trading on NSE: scan NIFTY charts, track Indian market news, time every entry and exit in IST, count every rupee of charges, and replay every outcome before you risk a rupee.

Free, MIT, no signup, no API key. The tools are plain Python that read free
public data: Yahoo Finance's NSE charts (`.NS`), Yahoo's quarterly
fundamentals and Google News India. They read files you save from
nseindia.com, and candles from any broker's connector: Zerodha Kite, Groww,
Upstox, Dhan, Angel One.

Built for the Indian market:

- **NSE hours and calendar.** Pre-open 9:00 to 9:15, session 9:15 to 15:30
  IST, the 2026 NSE trading holidays, and the Muhurat trading session.
- **NSE tick sizes.** Rs 0.01 below Rs 250, then 0.05, 0.10, 0.50, 1 and 5 as
  the price rises. Stops and targets snap to the grid.
- **Intraday (MIS) rules.** A flat-by time (15:10) ahead of your broker's
  auto square-off, and an entry window that ends at 14:45.
- **Real costs.** Brokerage, STT, NSE transaction charges, SEBI fee, stamp
  duty and GST are counted inside your max loss.
- **Indian brokers.** Order tickets you can type into any broker's app, leg
  by leg (entry, SL-M stop, target), or `place_order` calls for Zerodha's
  Kite MCP server.
- **Promoter, insider and big-money trades.** Bulk deals, block deals and
  SEBI insider-trading (PIT) disclosures.

No trade goes through until you say yes. Practice mode is the default:
nothing goes to a broker.

> This is a fork of [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
> (US markets), ported to NSE / BSE. The method is the same; the market, the
> clock, the money and the rules are India's.

## Install

Paste this into Claude:

```
https://github.com/msoni11/day-trader-skill

install skill
```

Or as a plugin, in Claude Code:

```
/plugin marketplace add msoni11/day-trader-skill
/plugin install day-trader-skill-india@day-trader-skill-india
```

As a plugin, the skills show up as `/day-trader-skill-india:trader-scanner` and
so on. Copy the folders instead if you want plain `/trader-scanner`:

```bash
git clone https://github.com/msoni11/day-trader-skill.git
cp -r day-trader-skill/trader-* ~/.claude/skills/
```

The tools need Python 3.8 or newer, with nothing to pip install. Copy
`trader-budget/config.example.json` to `trader/config.json` in your project
and set your own budget and limits.

**Behind a corporate proxy, Cloudflare WARP or Zscaler?** If Python reports
`CERTIFICATE_VERIFY_FAILED`, point it at your system's certificates. On a Mac:

```bash
security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > ~/.trader-ca.pem
export SSL_CERT_FILE=~/.trader-ca.pem
```

## The eleven

| command | job | what it does |
| --- | --- | --- |
| `/trader-scanner` | Chart Scanner | Scans NIFTY 50, NIFTY 500 or any NSE list for opening-range breakouts, 20-day breakouts, flags and oversold bounces. |
| `/trader-news` | News Monitor | Indian business headlines on every stock you watch, plus market news (NIFTY, Sensex, RBI, SEBI), and each stock's move. |
| `/trader-entry` | Entry Timer | Watches a setup bar by bar from 9:15 IST and tells you the moment to get in. |
| `/trader-exit` | Exit Planner | Sets your stop and target on NSE's tick grid, and a flat-by before MIS square-off. |
| `/trader-timemachine` | Time Machine | Replays the rest of the session 10,000 times from the stock's own last 60 days, plus every past day the setup fired. |
| `/trader-risk` | Risk Manager | Checks every order against your limits, the NSE window, square-off and the basics. PASS or BLOCK. |
| `/trader-budget` | Budget Manager | Sizes every position to your budget and max loss in rupees, charges included. |
| `/trader-broker` | Order Executor | Turns an approved order into a ticket for any Indian broker, or Kite `place_order` calls. Practice by default, never without your yes. |
| `/trader-alerts` | Price Alerts | Rings on a price, a stop, a target, a NIFTY move, the opening bell or your flat-by. Knows NSE holidays. |
| `/trader-analyst` | Earnings Analyst | Quarterly results in Rs crore, on Indian fiscal quarters, with what changed YoY and QoQ. |
| `/trader-insider` | Promoter & Big-Money Tracker | Bulk deals, block deals and SEBI insider-trading disclosures, new since the last check, your stocks flagged. |

## How to use it

Everything lands in a `trader/` folder in your project, and each skill reads
what the last one wrote:

```
scanner -> news -> entry -> exit -> timemachine -> budget -> risk -> broker   (one trade)
alerts: stop, target, flat by 15:10                                           (while it is open)
news / analyst / insider                                                       (on a schedule)
```

Here is the example trade, on real data: RELIANCE on Thursday, 29 October 2026.

1. **`/trader-scanner`** at 9:40 AM IST: 12 of the 50 NIFTY charts have
   closed above their 15-minute opening range. RELIANCE is one. Its range is
   1,156.20 to 1,170.50, and the 9:35 candle closed at 1,174.30, 0.32 % over
   the top.
2. **`/trader-news`**: the morning's RELIANCE headlines (Jio Platforms' NSE
   listing the day before). They also say Q2 results are due on October 30.
   A day trade is out before the close, so it is not exposed to the
   results, but the next morning's gap is.
3. **`/trader-entry`** watched RELIANCE bar by bar. At 9:36 it said waiting:
   the 9:30 bar closed Rs 1.00 under the high. At 9:40 it said triggered: the
   first 5-minute close above the range, Rs 1,174.30.
4. **`/trader-exit`** set the plan before the entry: stop at the range
   midpoint, rounded down to the Rs 0.10 tick (Rs 1,163.30, so Rs 11.00 a
   share at risk), target 1R at Rs 1,185.30, flat by 15:10 either way.
5. **`/trader-timemachine`** replayed the rest of the day 10,000 times from
   RELIANCE's own last 52 full sessions (seed 19), up to 15:10: target first
   23.2 %, stop first 32.8 %, still open 44.0 %. On those 52 real sessions
   the same rule fired 24 times: 12 targets, 9 stops, 3 neither. Its
   verdict: leans toward the stop. That is the point of looking before you
   risk a rupee.
6. **`/trader-budget`** with a Rs 1,00,000 account and a Rs 1,000 max loss:
   63 shares (the 75 % position cap binds), Rs 73,980.90. If the stop fills,
   the loss is Rs 693, plus about Rs 73 in brokerage, STT, exchange charges,
   GST and stamp duty: Rs 766 all in.
7. **`/trader-risk`** checks it against your limits: the max loss with
   charges, the daily loss limit, trades per day, reward to risk, the
   9:30-14:45 entry window, square-off, position size and cash. PASS or
   BLOCK, with the reason.
8. **`/trader-broker`** shows the ticket in plain words: BUY 63 RELIANCE on
   NSE, MIS, market. Once it fills, an SL-M sell with the trigger at 1,163.30
   and a limit sell at 1,185.30, then cancel whichever exit does not fill.
   You type yes for that one order, then place it in your broker's app.
   With a self-hosted Kite MCP server, Claude's "Allow once / Deny" card asks
   again for each `place_order` call.
9. **`/trader-alerts`** rings on the stop, the target and at 15:10 to close
   whatever is still open, before the broker's square-off.

## The tools

All standard-library Python.

```bash
python3 trader-scanner/scan.py universe                                # bundled NIFTY 50 (or --file an NSE CSV)
python3 trader-scanner/scan.py daily                                   # pre-market setups
python3 trader-scanner/scan.py orb --at 09:40                          # opening-range breakouts so far
python3 trader-news/news.py --tickers RELIANCE --market                # headlines, market news, today's move
python3 trader-entry/entry.py check RELIANCE                           # waiting / triggered / expired
python3 trader-entry/entry.py watch RELIANCE --until 14:45             # bar by bar until it triggers
python3 trader-exit/exit.py plan --stop or-mid --target 1R --write     # -> trader/plan.json
python3 trader-timemachine/timemachine.py run --until 15:10 --write    # 10,000 replays + the history
python3 trader-budget/size.py --write                                  # -> trader/orders.json, with charges
python3 trader-risk/check.py                                           # PASS / BLOCK per order
python3 trader-broker/ticket.py show                                   # the tickets, READY or not
python3 trader-alerts/alerts.py clock                                  # is NSE open today?
python3 trader-alerts/alerts.py add --from-plan                        # stop, target, flat-by
python3 trader-analyst/facts.py RELIANCE                               # quarters, growth, EPS in Rs crore
python3 trader-insider/deals.py check trader/bulk.csv trader/insider.csv   # new deals and filings
```

```bash
python3 -m unittest discover -s tests -v
```

The tests run offline, on fixtures saved from real data:

- **RELIANCE:** 5-minute bars for 29 October 2026, and the 60 sessions before it.
- **NIFTY 50:** the whole index's 5-minute charts and 3 months of daily closes.
- **News:** Google News India's RELIANCE headlines.
- **Results:** Yahoo's RELIANCE quarterly results.
- **Deals and filings:** NSE bulk-deal rows and insider-trading filings.

## Where the data comes from, and what it cannot do

- **Yahoo Finance** (charts, quotes, fundamentals): free and unofficial. It
  can lag, change or rate-limit you. Its NSE feed usually leaves the last ten
  minutes (15:20 to 15:30) empty.
- **NSE's website** blocks scripts, and this pack does not try to get around
  that. Index lists, bulk / block deals and insider-trading files come from
  your browser: you download the CSV, or Claude opens the page in its own
  browser for you. Exchange announcements (results dates, board meetings,
  dividends) are on the company's NSE / BSE page.
- **Your broker's connector** is the best source of live prices and candles
  when you have one. Every tool that reads bars takes broker candles saved
  as `{"symbol", "interval", "candles": [[time, o, h, l, c, v], ...]}`.

## Fine print

**Not financial advice.** This is software that reads public data and does
arithmetic. It is not a SEBI-registered investment adviser or research
analyst. It does not know your situation and it cannot see the future.
SEBI's own studies found that about 7 in 10 individual intraday traders in
the equity cash segment lost money in FY23, and 9 in 10 individual F&O
traders lost money over FY22 to FY24. You can lose money. Decide for
yourself, and talk to a SEBI-registered adviser if you need advice.

**No trade goes through until you say yes.** Only `/trader-broker` can lead
to an order. It does so only after `/trader-risk` passes that exact order
and you type yes for it in the chat, and then you place it yourself. With a
broker connector that can place orders, set those tools to "Needs approval",
never "Always allow", so Claude's own "Allow once / Deny" card is a second
check. F&O, margin (MTF), short selling and leverage stay off unless you
turn them on.

**Practice first.** `"paper": true` is the default. Indian brokers have no
paper accounts, so practice means nothing is sent anywhere and you record
pretend fills. Logins, API keys, access tokens, PINs and TOTPs never go in
the chat.

**MIS square-off.** Brokers close open intraday positions themselves from
about 15:15 to 15:25 and charge for it. The default flat-by, 15:10, keeps you
ahead of that.

**The Time Machine is a simulation, not a prediction.** It is built from the
stock's own last 60 days of 5-minute bars. The future can do things those
days never did: results, a circuit, an F&O ban, a headline.

**A stop is a plan, not a guarantee.** In a fast market, across a gap or at a
circuit, a stop can fill well past its price, or not at all. Stops and
targets are rounded to NSE's tick table; your broker may show a different
tick for a stock, so set `tick_size` when it does.

**Charges change.** The charge rates in `config.example.json` are 2026
rates for intraday equity on NSE. Check them against your contract note.

**Taxes.** In India, intraday equity profit is speculative business income,
taxed at your slab rate, and it has its own rules for offsetting losses.
Nothing here is tax advice.

**The holiday list covers 2026.** NSE publishes the next year's list in
December. Add it to `NSE_HOLIDAYS` in the scripts, or the tools will say the
date is outside the known calendar.

## Files

```
trader-scanner/     SKILL.md, scan.py, nifty50.txt
trader-news/        SKILL.md, news.py
trader-entry/       SKILL.md, entry.py
trader-exit/        SKILL.md, exit.py
trader-timemachine/ SKILL.md, timemachine.py
trader-risk/        SKILL.md, check.py
trader-budget/      SKILL.md, size.py, config.example.json, targets.example.json
trader-broker/      SKILL.md, ticket.py, claude_desktop_config.example.json (Kite MCP)
trader-alerts/      SKILL.md, alerts.py, alerts.example.json
trader-analyst/     SKILL.md, facts.py, metrics.example.json
trader-insider/     SKILL.md, deals.py
tests/              unittest suite + offline fixtures
```

MIT. Original US pack by [Jake Schincariol](https://opusjake.ai); Indian market port by [msoni11](https://github.com/msoni11).
