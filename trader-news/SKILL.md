---
name: trader-news
description: >-
  News Monitor for NSE stocks. Tracks breaking news on every stock you watch
  and flags what moves it: Indian business headlines per company from Google
  News India (Economic Times, Moneycontrol, Mint, Business Standard,
  CNBC-TV18, Reuters...), market-wide news (NIFTY, Sensex, RBI, SEBI, FII
  flows) with --market, and how far each stock is from yesterday's close.
  Shows only what is new since the last check, newest first, in IST, tags each
  item (results, analyst, deal, capital, insider, circuit, regulatory,
  macro...) and never repeats one. Use when the user says "any news on
  RELIANCE", "why is this moving", "what's the news on my watchlist",
  "morning briefing", "pre-market news", "monitor the news", "did anything
  break", or after /trader-scanner finds setups.
argument-hint: "[--tickers RELIANCE TCS] [--market]"
---

# trader-news

Headlines first, then the user decides. The News Monitor finds what is new
on the stocks the user watches and says why it might matter. A headline is a
lead, not a fact: open the story before acting on it.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/news.py"                               # watchlist + plan + portfolio
python3 "${CLAUDE_SKILL_DIR}/news.py" --tickers RELIANCE TCS M&M
python3 "${CLAUDE_SKILL_DIR}/news.py" --market                      # also NIFTY, Sensex, RBI, SEBI, FIIs
python3 "${CLAUDE_SKILL_DIR}/news.py" --tickers INFY --all --hours 72
python3 "${CLAUDE_SKILL_DIR}/news.py" --name "M&M=Mahindra & Mahindra" --tickers M&M
```

Other flags: `--no-moves`, `--move-pct 3`, `--json`, `--dry-run`, `--offline DIR`,
`--now ISO`. State: `trader/state/news.json` (30 days), so an item shows once.

## Where it looks

- **Headlines:** Google News RSS, India edition, searched by the company's name
  (from `trader/universe.txt` or the scanner's bundled NIFTY 50 list; give
  `--name SYM=Name` for anything else). Each item keeps its own source.
- **The move:** the last price against yesterday's close (Yahoo, `.NS`).
  3 % or more is flagged MOVING.
- **Exchange filings** (results, board meetings, dividends, bonus and split
  record dates, SAST and insider disclosures) are on nseindia.com and
  bseindia.com under Corporate Filings; those sites do not serve scripts.
  If the user wants them, open the company's announcements page in a browser
  for them, or use `/trader-insider` for insider and bulk / block deals.

## Steps

1. Run `news.py` (or with `--tickers`). Add `--market` before the open.
2. Lead with any ticker flagged MOVING and any item that touches the user's
   holdings. Then the rest, newest first, one line each: time IST, source, title, tags.
3. If a stock reports results this week, say so: a day trade is out by the
   close, so it is not exposed to an after-hours result, but the next
   morning's gap is.
4. Hand off: `/trader-entry TICKER` for a stock the user wants to watch.

## Example: the reel

RELIANCE, Thursday 29 October 2026 (real Google News items, `tests/fixtures/trader-news-india`):

```
RELIANCE   1,167.40 +0.81% vs yesterday's close 1,158.00 at 15:29 IST
  2026-10-29 04:40 IST  RELIANCE    The Times of India     On debut, Jio 2nd most valuable company, behind only parent Reliance Industries
  2026-10-29 03:22 IST  RELIANCE    The Economic Times     Jio Platforms lists on NSE as 3,138th company, making Ambani family proud with a 21.36% surge
  ...
```

A headline that day also said the Q2 results were due on October 30: a
reason to be flat by the close.

## Rules

- Headlines are leads, not facts. Never trade on a headline alone.
- Never present a rumour, a "target price" or a tip as news the user should act on.
- WhatsApp / Telegram "tips" and finfluencer calls are not sources. SEBI has
  acted against unregistered tip providers; say so if the user brings one.

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
