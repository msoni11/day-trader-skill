---
name: trader-entry
description: >-
  Entry Timer for NSE. Watches a setup bar by bar and tells you the moment to
  get in. Reads free Yahoo 1-minute or 5-minute bars (.NS), builds the opening
  range (9:15 to 9:30 IST by default) and calls the entry on the first
  completed bar that CLOSES above the range high, or above a level you give
  it (like a 20-day high from the scanner), with an optional volume check.
  Also reads candles saved from any broker (Kite, Groww, Upstox, Dhan...).
  Says waiting and how far, triggered with the time and the price, expired,
  or not open yet, and writes trader/entry.json for /trader-exit. Long side
  only. It never places an order. Use when the user says "tell me when to get
  in", "watch RELIANCE", "has it broken out", "did it break the opening
  range", "entry signal", "time my entry", "check my watchlist", or after
  /trader-scanner and /trader-news, before /trader-exit.
argument-hint: "[TICKER] [--setup orb|level] [--interval 5m|1m]"
---

# trader-entry

The Entry Timer turns a setup into one moment: the bar that confirms it. A
price that pokes above the high in the middle of a bar is not an entry. A
bar that CLOSES above it is. Then it says the time and the price, writes them
down for the Exit Planner, and stops. It never buys anything.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/entry.py" check RELIANCE                # 15-minute opening range, 5-minute bars
python3 "${CLAUDE_SKILL_DIR}/entry.py" check RELIANCE --write        # also save trader/entry.json
python3 "${CLAUDE_SKILL_DIR}/entry.py" check TCS --setup level --level 3050
python3 "${CLAUDE_SKILL_DIR}/entry.py" check INFY --interval 1m --min-volume-x 1.5
python3 "${CLAUDE_SKILL_DIR}/entry.py" watch RELIANCE --until 14:45  # one line per closed bar
python3 "${CLAUDE_SKILL_DIR}/entry.py" watchlist                     # every hit in trader/watchlist.json
```

Other flags: `--or-minutes N` (15), `--json`, `--offline FILE` (a saved Yahoo
chart, or broker candles, `.json` or `.json.gz`, or a folder of `<TICKER>.json`),
`--now "2026-10-29 09:40"` (IST) to replay a day.

## Data from your broker

Yahoo is free and can lag. When the user has a broker connector (Zerodha
Kite `get_historical_data`, Groww `fetch_historical_candle_data`, Upstox,
Dhan, Angel One...), Claude can fetch today's 5-minute candles there, save
them as

```json
{"symbol": "RELIANCE", "interval": "5m", "candles": [["2026-10-29T09:15:00+05:30", 1159.2, 1162.2, 1156.2, 1161.1, 501032]]}
```

and run `entry.py check RELIANCE --offline that.json`. Times can be Unix
seconds, milliseconds or ISO with an offset (no offset = IST).

## The rule

- **Opening range (orb):** the high and low of 9:15 to 9:30 (three 5-minute
  bars). The 9:15 bar follows the 9:00 to 9:15 pre-open call auction.
- **Level:** a price the user gives, like a 20-day high.
- **The trigger** is the first completed bar after the range that CLOSES above
  the level. A close exactly at the level is not above it.
- **The time** is that bar's close time (the 9:35 bar closes at 9:40 AM).
- **Time limits:** no entries before 9:30 or after 14:45 (config), well before
  brokers square off intraday (MIS) positions around 15:15 to 15:25. On a
  special session (Muhurat trading, 14:20 to 15:30 on 8 November 2026) both
  times move with its open.
- **Market closed:** weekends and NSE holidays (2026 list built in).

## Steps

1. Get the symbol, or run `entry.py watchlist` after `/trader-scanner`.
2. Run `entry.py check SYMBOL`. Say the status in one line.
3. To wait for it, run `entry.py watch SYMBOL --until 14:45` in the
   background, or `check --write` on a `/loop` every 5 minutes.
4. When it triggers, say the time and the price, and that nothing was
   placed. If it is more than a bar old, say a late entry is a different trade.
5. Hand off to `/trader-exit` to set the stop and target BEFORE anything is bought.

## Example: the reel

RELIANCE, Thursday 29 October 2026, real 5-minute bars:

```
RELIANCE  Thu 2026-10-29 09:40 IST  opening-range breakout (15-minute range) on 5-minute bars (Yahoo, free, can lag)
Opening range 9:15-9:30: high Rs 1170.50, low Rs 1156.20 (3 of 3 bars).
TRIGGERED 9:40 AM at Rs 1174.30: the 9:35 bar (bar 4) closed above the range high Rs 1170.50 (+0.32%).
This is the moment to get in, if you take the trade. Nothing was placed.
```

At 9:36 it said WAITING: the 9:30 bar closed at 1,169.50, Rs 1.00 under the high.

## Rules

- Bar by bar, closed bars only. Never call an entry early because a bar looks
  like it will close above.
- Long side only.
- One trigger per setup per day: the first close above.
- It never runs `/trader-broker` from a background watch: nobody is there to say yes.

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
