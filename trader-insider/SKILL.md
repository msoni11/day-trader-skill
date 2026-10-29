---
name: trader-insider
description: >-
  Promoter, Insider and Big-Money Tracker for NSE. Reads the trades India
  makes public: bulk deals (a client trading more than 0.5 % of a company in a
  day) and block deals (Rs 10 crore and up in the block windows), with the
  client's name, side, quantity and price, and SEBI insider-trading (PIT)
  disclosures by promoters, directors and designated people under Regulation
  7. Alerts once per new deal or filing, flags trades in stocks you hold or
  watch, and nets each client's buys against its sells so an algo trading both
  sides is not mistaken for a position. Reads the CSV or JSON saved from
  nseindia.com. Use when the user says "who is buying RELIANCE", "promoter
  buying", "insider trades", "bulk deals today", "block deals", "did any
  promoter sell", "what are the big investors doing", "track an investor's
  bulk deals", or "run the insider skill".
argument-hint: "[check|show|summary] FILE..."
---

# trader-insider

Follow the money that has to show itself. In India, promoters and insiders
must disclose their trades within two trading days, and the exchange
publishes every bulk and block deal with the client's name the same evening.
This tool reads those and says what is new.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/deals.py" check bulk.csv block.csv insider.csv   # new since last check
python3 "${CLAUDE_SKILL_DIR}/deals.py" check bulk.csv --mine                  # only your stocks
python3 "${CLAUDE_SKILL_DIR}/deals.py" show bulk.csv --symbol RELIANCE
python3 "${CLAUDE_SKILL_DIR}/deals.py" summary bulk.csv block.csv --min-value-cr 5
```

## Getting the files

nseindia.com does not serve scripts, so the files come from a browser:

- **Bulk / block deals:** nseindia.com > Market Data > Bulk / Block Deals >
  "Download (.csv)". Columns: DATE, SYMBOL, SECURITY NAME, CLIENT NAME, BUY /
  SELL, QUANTITY TRADED, TRADE PRICE / WGHT. AVG. PRICE, REMARKS.
- **Insider trading:** nseindia.com > Companies > Corporate Filings > Insider
  Trading > "Download (.csv)": acquirer / disposer, category (Promoter,
  Director, KMP...), securities and value, transaction type, dates, broadcast time.
- When the user asks, Claude can open these pages in its own browser, let the
  user see them, and save the table or the page's JSON to `trader/` (ask before
  downloading a file). Never work around the site's bot protection.

## Steps

1. Get the files (above), saved under `trader/`.
2. `deals.py check <files>`. Lead with anything in the user's stocks. Then
   promoter / director buys and sells, then the biggest deals by value.
3. For bulk deals, run `summary`: a client with net 0 traded both sides
   (an algo or market maker); that is not a position.
4. Say what a disclosure is: public, after the fact, a fact not a forecast.

## Example

```
2026-10-29  PIT    INFY         filing  <- your holding
      Regulation 7 (2); Original  https://nsearchives.nseindia.com/corporate/ixbrl/IT_180_20261029_120656955_WEB.html
2026-10-22  BULK   CAPINVIT     LARSEN & TOUBRO LIMITED: BUY 66,44,519 shares at Rs 75.59 = Rs 50.23 cr
```

## Rules

- These are public disclosures. There is no inside information here.
- A promoter buying is not a reason to buy; a promoter pledging or selling is
  not a reason to sell. Say so if the user reads it that way.
- Big-investor portfolios (shareholding of 1 % or more) are in the quarterly
  shareholding pattern on NSE / BSE, not here.

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
