---
name: trader-budget
description: >-
  Budget Manager for Indian intraday trades. Sizes every position to your
  budget and your max loss per trade in rupees, counting the real costs of an
  NSE round trip (brokerage, STT, exchange charges, SEBI fee, stamp duty,
  GST). Reads the plan from trader-exit, finds the whole shares that fit
  inside your limits (max loss with charges, position cap, max order, cash
  after your buffer, optional MIS leverage), says which limit decided it, and
  writes ONE order (entry, stop-loss, take-profit, product MIS, exchange NSE)
  to trader/orders.json for any Indian broker. A stop too far away for your max
  loss is a plain refusal, not a smaller order. Nothing is placed. Use when
  the user says "how many shares", "size this trade", "how much should I
  buy", "I have 1 lakh", "I only want to risk 1,000 a trade", "what are the
  charges", "set my rules", or after /trader-exit writes a plan.
argument-hint: "[--budget 100000] [--limit PRICE] [--write]"
---

# trader-budget

Size from the loss, not from the conviction. The Budget Manager starts from
what the user is willing to lose if the stop fills, takes off the charges,
and works out the shares from there.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/size.py"                       # trader/plan.json + trader/config.json
python3 "${CLAUDE_SKILL_DIR}/size.py" --budget 100000 --write
python3 "${CLAUDE_SKILL_DIR}/size.py" --limit --write       # a limit order at the plan's entry
python3 "${CLAUDE_SKILL_DIR}/size.py" --json
```

Start the config from `config.example.json` here: copy it to
`trader/config.json` and change the numbers with the user.

## The rules (trader/config.json)

- **budget** (Rs 1,00,000 in the example), **cash_buffer_pct** (10).
- **max_loss_per_trade_inr** (1,000): the most one trade may lose at the stop,
  charges included when **count_charges** is on (the default).
- **max_position_pct** (75), **max_order_inr** (80,000), **min_order_inr** (100).
- **intraday_leverage** (1 = none): MIS margin lets an order be up to that many
  times the cash; SEBI caps intraday equity margin at 20 % (5x at most) and the
  broker may allow less. It moves the cash limit only, never the max loss.
- **charges**: brokerage_per_order (Rs 20) and brokerage_pct (0.03 %, the lower
  wins, each side), stt_sell_pct (0.025 %), exchange_pct (0.00297 %),
  sebi_per_crore (Rs 10), stamp_buy_pct (0.003 %), gst_pct (18 % on brokerage,
  exchange and SEBI fees). Set brokerage to 0 for a zero-brokerage broker. Check
  them against the user's contract note.
- Day limits trader-risk enforces: max_daily_loss_inr (3,000), max_trades_per_day (3),
  no_entries_before / after (09:30 / 14:45), flat_by (15:10), square_off_by (15:15).

## Steps

1. Make sure the plan is today's (`/trader-exit`) and the price is fresh
   (`/trader-alerts quote --write`).
2. Run `size.py --write`. Say: shares, cost, max loss at the stop, charges,
   all-in loss, net at the target, and which limit decided it.
3. A refusal is final for that plan: say why and the fix (closer stop, skip).
4. Hand off to `/trader-risk`, then `/trader-broker`.

## Example: the reel

RELIANCE, 29 October 2026, entry 1,174.30, stop 1,163.30, target 1,185.30, budget Rs 1,00,000:

```
Limits (whole shares; the smallest one wins):
  max loss      Rs 1,000 max loss / 11.00 risk a share                      90 shares
  position cap  75% of Rs 100,000 = Rs 75,000 / 1174.30                     63 shares  <- binds
  max order     Rs 80,000 / 1174.30                                         68 shares
  cash          budget Rs 100,000 minus the Rs 10,000 cash buffer = Rs 90,000 / 1174.30  76 shares

Size: 63 shares of RELIANCE = Rs 73,980.90 at 1174.30. Max loss at the stop: 63 x 11.00 = Rs 693.
Charges for the round trip: about Rs 73.07 at the stop (brokerage Rs 40, STT Rs 18.32, exchange Rs 4.37, GST Rs 8.01, stamp Rs 2.22, SEBI Rs 0.15), Rs 73.48 at the target.
All in at the stop: Rs 766.07. Net at the target: Rs 619.52.
  BUY 63 RELIANCE on NSE, market, MIS (intraday), take-profit 1185.30, stop-loss 1163.30
```

Charges take more than a tenth of a 1R win here. Say that: small targets get eaten by costs.

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
