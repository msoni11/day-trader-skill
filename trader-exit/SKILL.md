---
name: trader-exit
description: >-
  Exit Planner for NSE intraday trades. Sets your stop and your target
  before you enter, so you know when to get out. Reads the entry from
  trader-entry (or a price you give), puts the stop at the opening-range
  midpoint by default (or the range low, your price, a percent, or a
  multiple of the ATR), rounds it down to NSE's tick size for that price
  (Rs 0.01 under Rs 250, 0.05, 0.10, 0.50, 1, 5 above), sets the target at
  2R (or 1R, or your price), and a flat-by time (15:10 IST) ahead of your
  broker's MIS auto square-off. Refuses a stop at or above the entry, a target
  at or below it, or a stop too tight to survive the spread, and says why.
  Writes trader/plan.json. Long side only. Use when the user says "where's my
  stop", "set my stop and target", "plan the exit", "when do I get out",
  "stop loss", "what's my R", "risk reward", or right after /trader-entry
  triggers, before /trader-timemachine.
argument-hint: "[--stop or-mid|or-low|price:X|pct:X|atr:K] [--target 2R|1R|price:X]"
---

# trader-exit

Decide the way out before the way in. The Exit Planner writes down where the
trade is wrong (the stop), where it is right enough (the target), and when it
ends either way (flat by 15:10, before the broker squares you off).

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --write                    # from trader/entry.json: or-mid stop, 2R
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --target 1R --write
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --symbol RELIANCE --entry 1174.30 --or-high 1170.50 --or-low 1156.20
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --stop atr:1.5 --offline RELIANCE.json
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --symbol TATASTEEL --entry 162.37 --setup level --stop pct:1
python3 "${CLAUDE_SKILL_DIR}/exit.py" show
```

Other flags: `--flat-by HH:MM`, `--tick 0.05` (when the broker shows a
different tick than the price table), `--from FILE`, `--now`, `--json`.

## Ticks and square-off

- NSE prices sit on a tick grid set by the price (circulars of 2024 and
  2025): under Rs 250: Rs 0.01; Rs 250 to 1,000: Rs 0.05; Rs 1,000 to 5,000:
  Rs 0.10; Rs 5,000 to 10,000: Rs 0.50; Rs 10,000 to 20,000: Rs 1; above:
  Rs 5. NSE resets each stock's tick monthly from its last close, so
  `tick_size` in the config overrides the table. A stop rounds DOWN to the
  tick, a target to the nearest tick.
- Most brokers square off open MIS positions from about 15:15 to 15:25 and
  charge for it (often Rs 50 + GST). The default flat-by, 15:10, is before that.

## Steps

1. Run it right after `/trader-entry` triggers (or `--entry PRICE` to plan ahead).
2. Default stop for an opening-range breakout unless the user names another.
   A level setup needs one: ask.
3. `exit.py plan --write`. Read back entry, stop and its rule, target, risk a
   share, reward:risk and flat by.
4. If it refuses, say the reason and the fix. Never loosen anything yourself.
5. Hand off to `/trader-timemachine`, then `/trader-budget`. Offer `/trader-alerts`.

## Example: the reel

RELIANCE, Thursday 29 October 2026. Entry 1,174.30 at 9:40 AM, range 1,156.20 to 1,170.50:

```
Exit plan: RELIANCE long, Thu 2026-10-29, opening-range breakout on 5-minute bars
  Entry         Rs 1,174.30 at 9:40 AM (bar 4)
  Stop          Rs 1,163.30  opening-range midpoint: (Rs 1,170.50 + Rs 1,156.20) / 2 = Rs 1163.35, rounded down to the Rs 0.10 tick
  Target        Rs 1,185.30  1R (one times the risk)
  Risk a share  Rs 11.00 (0.94% of the entry)
  Reward:risk   1.0
  Flat by       15:10 IST, win or lose: no overnight hold
```

## Rules

- A stop is a plan, not a guarantee: a gap, a circuit or a fast market can
  fill past it. An SL-M order at the broker is what makes it real.
- Never move a stop further away after the entry.
- Long side only.

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
