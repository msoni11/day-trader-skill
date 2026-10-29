---
name: trader-scanner
description: >-
  Chart Scanner for NSE. Scans NIFTY 50, NIFTY 500 or any NSE list for
  setups: opening-range breakouts, 20-day breakouts, bull flags, oversold
  bounces. Builds the list from a bundled NIFTY 50 file or a CSV downloaded
  from NSE, runs a pre-market scan of daily closes (20-day closing-high
  breakout, bull flag, reclaimed the 20-day average, oversold, oversold
  bounce) and an intraday opening-range breakout scan on 5-minute bars from
  9:15 IST, then writes trader/watchlist.json for trader-news and
  trader-entry. Free Yahoo data (.NS symbols), bar by bar. Use when the user
  says "scan the market", "scan NIFTY", "find me setups", "what is breaking
  out", "opening range breakouts", "scan for bull flags", "oversold stocks",
  "pre-market scan", "build my watchlist", "what should I look at today", or
  at the start of a trading day before /trader-news.
argument-hint: "[universe|daily|orb] [--symbols RELIANCE,TCS]"
---

# trader-scanner

The Chart Scanner looks at many NSE charts so the user does not have to,
and returns the few that match a rule. A hit is a chart worth a look, not a
stock to buy.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/scan.py" universe                         # bundled NIFTY 50 -> trader/universe.txt
python3 "${CLAUDE_SKILL_DIR}/scan.py" universe --file ind_nifty500list.csv   # a list saved from NSE
python3 "${CLAUDE_SKILL_DIR}/scan.py" daily                            # before 9:15: daily setups
python3 "${CLAUDE_SKILL_DIR}/scan.py" daily --symbols RELIANCE,TCS,M&M
python3 "${CLAUDE_SKILL_DIR}/scan.py" orb                              # after 9:35 IST: opening-range breakouts
python3 "${CLAUDE_SKILL_DIR}/scan.py" orb --at 09:40                   # cut the clock at 9:40
```

Other flags: `--watchlist FILE`, `--limit N`, `--min-price` (Rs 50), `--min-volume`
(100,000 shares for `daily`), `--or-minutes` (15), `--max-confirm` (200),
`--until HH:MM`, `--offline PATH`, `--now "2026-10-29 09:40"` (IST), `--json`.

## The universe

NSE's website does not serve scripts, so the list comes from a file:

- **Bundled:** `nifty50.txt` next to `scan.py`, the NIFTY 50 as of 8 December
  2025. NSE Indices reviews it every March and September, so it drifts.
- **Yours:** download `ind_nifty500list.csv` (or NIFTY 100, NIFTY Midcap 150,
  any index) from niftyindices.com > Indices > Index Constituents, or
  `EQUITY_L.csv` (every listed stock) from nseindia.com > Market Data >
  Securities available for trading, in a browser, and run
  `scan.py universe --file <that file>`. It keeps series EQ (`--series EQ,BE`
  for more). Claude can open these pages in its browser for the user and
  save the file when the user asks.

Symbols are NSE's own (RELIANCE, M&M, BAJAJ-AUTO). Yahoo gets them with
`.NS`; a BSE-only stock keeps `.BO`.

## The setups

`daily` (closes only, today's bar dropped until the close): 20-day closing-high
breakout, bull flag (up more than 10 % over 10 sessions, then 5 closes inside
5 %), reclaimed the 20-day average, oversold (RSI 14 under 30), oversold bounce.

`orb`: the 15-minute opening range is 9:15 to 9:30. A hit is the first
completed 5-minute bar after it that CLOSES above the range high (real highs,
from each candidate's own chart). A chart with a missing bar (a halt, a
circuit, no trades) is left out.

## Steps

1. Once a month, or after an index review: `scan.py universe` (or `--file`).
2. Before the open (pre-open is 9:00 to 9:15): `scan.py daily`. Tell the user
   the counts and the top few by setup.
3. After 9:35 IST: `scan.py orb`. Say how many charts broke their range and
   when; a later hit is closer to the price now.
4. The user picks one chart. Hand it on: `/trader-news TICKER`, then
   `/trader-entry TICKER`. Never pick for them.

## Example: the reel

Thursday 29 October 2026, NIFTY 50, scan at 9:40 AM on real Yahoo charts
(`tests/fixtures/nse/wall5m-2026-10-29.json.gz`):

```
Opening-range breakout scan, Thu 2026-10-29 9:40 AM IST: 15-minute range (9:15 to 9:30 AM), 5-minute bars, Yahoo.
Fetched 50 of 50 charts; 50 usable; 29 candidates, 29 confirmed with real highs and lows.
12 of 50 charts closed above their opening-range high by 9:40 AM:
   9:35 AM  ADANIENT   Rs 2,505.70  range 2,474.80 to 2,505.20  +0.02% over
  ...
   9:40 AM  RELIANCE   Rs 1,174.30  range 1,156.20 to 1,170.50  +0.32% over
```

RELIANCE's range is 1,156.20 to 1,170.50; its 9:35 bar closed at 1,174.30,
0.32 % over the high, at 9:40 AM. The user picks RELIANCE and Claude hands it
to `/trader-news RELIANCE`, then `/trader-entry RELIANCE`.

## Rules

- Free Yahoo data: unofficial, delayed a little, can lag. A polite pause
  between requests. Partial results are said to be partial.
- A scan is a list of charts that match a rule, not a list of stocks to buy.
- Stocks in F&O ban, under ASM / GSM surveillance or stuck at a circuit can
  match a rule and still be untradeable intraday: check before planning.

## Safety

- Education and tooling, not financial advice. This pack is not a SEBI-registered investment
  adviser or research analyst, and a PASS is a rules check, not a recommendation.
- SEBI's own studies: about 7 in 10 individual intraday traders in the equity cash segment lost
  money in FY23, and 9 in 10 individual F&O traders lost money over FY22 to FY24. Say so when it matters.
- Practice by default (`"paper": true`): nothing goes to a broker. Indian brokers have no paper
  accounts; going live is the user's own decision, in their own config.
- Nothing in this pack places an order except trader-broker, and only when all three hold:
  trader-risk passed that exact order today, the user typed an explicit yes for that one order in
  the chat, and, with a broker connector that can place orders, the user clicked Allow once on
  Claude's own card for each call (tool permission "Needs approval", never "Always allow").
  Without a connector the user places the order in their broker's app themselves.
- No F&O, MTF / margin, short selling or leverage unless the config allows it and the user confirms.
- Broker logins, API keys, access tokens, PINs and TOTPs never go in the chat.
