---
name: trader-risk
description: >-
  Risk Manager for Indian trades. Checks every order against your limits and
  stops anything over them before it can reach the broker. For an intraday
  (MIS) trade: a stop is required, the loss at the stop plus charges must fit
  your max loss per trade, reward:risk must meet your minimum, the day's risk
  must fit your daily loss limit, no more than your trades per day, no new
  entries outside your window or when NSE is closed, and a flat-by before
  your broker's MIS square-off. Also: whole shares only, MIS / CNC, NSE / BSE
  symbols, F&O off unless allowed, blocked tickers, size, position cap, cash
  buffer, short sales and duplicates. Getting out is never blocked by a day
  limit. Prints PASS or BLOCK with the reason. Use when the user says "check
  my order", "is this safe", "risk check", "can I take this trade", "how much
  have I risked today", or before /trader-broker, always.
argument-hint: "[--orders trader/orders.json] [--now HH:MM]"
---

# trader-risk

The Risk Manager is the brake. It reads the proposed orders and the user's
own rules and says PASS or BLOCK for each, with the reason. trader-broker
only shows an order as ready if THIS exact order passed today.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/check.py"                          # writes trader/state/risk.json
python3 "${CLAUDE_SKILL_DIR}/check.py" --now "2026-10-29 09:41"
python3 "${CLAUDE_SKILL_DIR}/check.py" --json --no-write
```

Reads `trader/orders.json`, `trader/config.json`, `trader/portfolio.json`,
`trader/prices.json` and `trader/state/broker.json`.

## What blocks

| check | blocks |
| --- | --- |
| format | no whole-share qty (no fractions, no rupee amounts), bad type, product not MIS / CNC / NRML, a bracket missing a leg |
| asset | F&O contracts (NIFTY26NOV24500CE, ...FUT) unless `allow_options`; anything not an NSE / BSE symbol |
| short | selling more than you hold, unless `allow_short` |
| blocked | a ticker on your `blocked` list |
| size / position / cash | under `min_order_inr`, over `max_order_inr`, over `max_position_pct`, into the cash buffer |
| stop | no stop (with `require_stop`), or a stop on the wrong side |
| loss | qty x (entry - stop) + charges over `max_loss_per_trade_inr` |
| reward:risk | under `min_reward_risk` |
| daily loss / trades | over `max_daily_loss_inr`, or `max_trades_per_day` reached |
| window | before `no_entries_before`, after `no_entries_after`, or NSE closed |
| square-off | an MIS entry with a flat-by at or after `square_off_by` (15:15) |

An exit (a sell that only reduces what you hold) is checked for format,
asset and short sales only. Getting out must always be possible.

## Steps

1. Refresh the price if it may have moved (`alerts.py quote RELIANCE --write`).
2. Run `check.py`. 3. Say each verdict in plain words; for a BLOCK the reason
   and the fix. Never change a limit yourself.
4. If the order changes in any way, check it again.

## Example: the reel

The RELIANCE order from trader-budget at 9:41 AM, 29 October 2026:

```
PASS  #1 buy RELIANCE 63 shares, entry
          entry 1174.30 (the plan's entry), stop 1163.30, target 1185.30: risk 11.00 a share
          max loss Rs 766.07 (limit Rs 1,000), reward:risk 1.00 (min 1)
          today before this: 0 of 3 trades, Rs 0 of Rs 3,000 daily loss
```

The same order at 14:50: `BLOCK ... window: no new entries after 14:45 IST (it is 14:50)`.

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
