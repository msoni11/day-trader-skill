---
name: trader-analyst
description: >-
  Earnings Analyst for NSE companies. Reads a company's quarterly results
  (Yahoo Finance's fundamentals for .NS symbols) and sums up what changed:
  revenue, gross, operating and net margins, net profit and diluted EPS in
  Rs crore, quarter by quarter on Indian fiscal quarters (Q1 = April to June),
  each against the same quarter a year earlier (YoY) and the quarter before
  (QoQ), with the trailing twelve months. Reads a results press release,
  investor presentation or earnings call transcript when you paste one. Use
  when the user says "how did Reliance's results look", "analyze the
  results", "what changed this quarter", "Q2 results", "is revenue growing",
  "compare margins", "sum up the concall", "does it report this week", or
  before trading a stock around its results.
argument-hint: "[TICKER ...] [--quarters 8]"
---

# trader-analyst

Numbers first, story second. The Earnings Analyst lays out the reported
numbers and what moved, and never says whether a stock is a buy.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/facts.py" RELIANCE
python3 "${CLAUDE_SKILL_DIR}/facts.py" TCS INFY --quarters 8
python3 "${CLAUDE_SKILL_DIR}/facts.py" HDFCBANK --json
python3 "${CLAUDE_SKILL_DIR}/facts.py" RELIANCE TCS --metrics trader/metrics.json
```

## What to know

- Source: Yahoo's fundamentals time series. Free and unofficial; it can lag
  the exchange filing by days and sometimes misses a quarter (the tool says
  which). The official numbers are in the results filing on nseindia.com /
  bseindia.com and the investor presentation: say so, and check there before
  leaning on a number.
- Indian fiscal year: April to March. 30 June is Q1, 30 September Q2,
  31 December Q3, 31 March Q4 (with the full year). FY27 = April 2026 to March 2027.
- Consolidated vs standalone: Indian companies report both. Yahoo's line is
  usually consolidated. Say which when it matters.
- Banks and NBFCs: no gross margin; look at NII, NIM, GNPA / NNPA and credit
  costs in the press release instead.
- One-offs (an exceptional item, a stake sale) can swing net profit: read the
  notes before calling a quarter strong or weak.

## Steps

1. Run `facts.py TICKER`. Lead with the newest quarter: revenue and profit
   YoY, margin change, EPS. Then the trend.
2. If the user pastes a press release, presentation or concall transcript,
   summarise: guidance, segment numbers, management's own words on demand and
   margins, and what changed from last quarter. Quote sparingly.
3. Before a day trade: if results are due (check `/trader-news`), say the
   stock can gap on them.

## Example: the reel

```
RELIANCE: quarterly results (Yahoo Finance; amounts in Rs crore)
  quarter   ended         revenue      YoY      QoQ     profit      YoY  op mgn net mgn      EPS
  Q1 FY27   2026-06-30    309,468   +27.0%    +5.2%     20,946   -22.4%   10.5%    6.8%    15.48
  Q4 FY26   2026-03-31    294,059   +12.5%   +11.0%     16,971   -12.6%   10.0%    5.8%    12.54
  ...
  Yahoo has no numbers for Q2 FY26: growth that needs them is blank.
```

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
