---
name: trader-alerts
description: >-
  Price Alerts and the NSE clock. Rings when a price, a stop, a target, a
  percent move or the opening bell hits. Turns the trade plan into three
  alerts in one go (the stop, the target and the flat-by time), plus above /
  below / stop / target levels, percent moves from the previous close (NIFTY
  ^NSEI, Bank NIFTY ^NSEBANK, Sensex ^BSESN too), any time of day, and the
  9:15 opening bell, each ringing once. Knows NSE hours (pre-open 9:00 to
  9:15, session 9:15 to 15:30 IST), the 2026 holidays and the Muhurat
  session, fetches free delayed quotes (Yahoo .NS) and writes
  trader/prices.json for sizing and the risk check. Use when the user says
  "alert me when", "tell me if RELIANCE hits", "watch my stop", "watch my
  trade", "remind me to close by 3:10", "is the market open", "is today a
  holiday", "get me a price", or right after /trader-exit writes a plan.
argument-hint: "[clock|quote|add|check|list|reset]"
---

# trader-alerts

Alerts so the user does not have to stare at the screen, and the clock that
knows when NSE is open.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/alerts.py" clock                       # is NSE open? next open
python3 "${CLAUDE_SKILL_DIR}/alerts.py" quote RELIANCE --write      # -> trader/prices.json
python3 "${CLAUDE_SKILL_DIR}/alerts.py" add --from-plan             # stop, target, flat-by
python3 "${CLAUDE_SKILL_DIR}/alerts.py" add --symbol ^NSEI --pct 1  # NIFTY 50 moved 1 %
python3 "${CLAUDE_SKILL_DIR}/alerts.py" add --opening-bell
python3 "${CLAUDE_SKILL_DIR}/alerts.py" check                       # rings what hit, once
python3 "${CLAUDE_SKILL_DIR}/alerts.py" list
```

## Steps

1. After `/trader-exit`: `alerts.py add --from-plan`.
2. While the trade is open, run `alerts.py check` on a `/loop` every minute or
   two (or a scheduled task during market hours). Say what rang, plainly.
3. On the stop or target ringing: the matching exit order should have filled
   at the broker; remind the user to cancel the other one.
4. On the flat-by ringing: hand off to `/trader-broker flatten`.

Quotes are free and delayed; for alerts only, never for timing an order. A
quote from the broker's connector (Kite `get_ltp`, Groww `get_ltp`) can be
written to `trader/prices.json` instead.

## Example

```
IST 2026-10-29 09:05 (Thursday): NSE closed, pre-open call auction (orders until 9:08, matching to 9:15).
Today's session: 09:15 to 15:30.
IST 2026-11-08 14:30 (Sunday): NSE OPEN, Muhurat trading (Diwali).
IST 2026-11-10 10:00 (Tuesday): NSE closed, NSE holiday: Diwali Balipratipada.
```

## Rules

- Each alert rings once (unless `rearm`). An alert is information, not an order.
- The holiday list covers 2026. Add 2027 when NSE publishes it in December.

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
