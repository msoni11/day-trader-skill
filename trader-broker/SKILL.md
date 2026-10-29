---
name: trader-broker
description: >-
  Order Executor for Indian brokers. Turns an approved order into a ticket
  for any broker (Zerodha, Groww, Upstox, Dhan, Angel One, ICICI Direct,
  Fyers, Kotak, HDFC Sky...), leg by leg: the MIS entry, then an SL-M
  stop-loss and a limit target once it fills, and a reminder to cancel the
  other exit when one fills. Practice mode by default: nothing goes to a
  broker. Records your yes word for word, and with Zerodha's Kite MCP server
  (order tools on, each set to Needs approval) shows the exact place_order
  calls, so Claude's own Allow once / Deny card asks again for each one.
  Builds the sell ticket that closes a day trade by your flat-by time, records
  fills, and logs each trade's max loss so trader-risk can hold the daily
  limit. Use when the user says "place the order", "buy it", "execute",
  "send it to Zerodha", "close my position", "flatten", "get me out",
  "connect Kite", or after /trader-risk passes.
argument-hint: "[order number]"
---

# trader-broker

The only skill in this pack that can lead to a real order, so it is the
strictest. An order goes anywhere only after three separate gates, every time:

1. **trader-risk passed this exact order today** (matched by fingerprint).
2. **The user typed an explicit yes for this one order** in the chat.
3. **The user places it** in their broker's app, or, with a Kite MCP server
   whose order tools are set to Needs approval, **clicks Allow once** on
   Claude's card for each call.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show
python3 "${CLAUDE_SKILL_DIR}/ticket.py" approve --index 1 --reply "yes"
python3 "${CLAUDE_SKILL_DIR}/ticket.py" result --index 1 --status placed --broker-id 261029000123456 --filled-qty 63 --filled-price 1174.40
python3 "${CLAUDE_SKILL_DIR}/ticket.py" fill --symbol RELIANCE --side sell --qty 63 --price 1185.30
python3 "${CLAUDE_SKILL_DIR}/ticket.py" flatten --symbol RELIANCE --qty 63
python3 "${CLAUDE_SKILL_DIR}/ticket.py" log
```

`ticket.py` never talks to a broker. It renders tickets, checks that a reply
is a real yes for that order, builds the flatten ticket, and keeps the log in
`trader/state/broker.json`.

## Brackets in India

Most Indian brokers stopped offering one-click bracket orders for stocks.
So a bracket is three legs: the entry (MIS, market or limit); then, once it
fills, a stop-loss (SELL, SL-M, trigger at the stop) and a target (SELL,
LIMIT at the target). When one exit fills, cancel the other at once, or the
next fill makes you short. Some brokers can tie the two exits together (GTT
OCO, or an OCO / cover order): use it where the user has it.

## Brokers

- **`"broker": "manual"`** (default) or a broker's name (`zerodha`, `groww`,
  `upstox`, `dhan`, `angel`, `icici`, `fyers`, `kotak`, `hdfc`): the ticket
  says exactly what to enter in that broker's app. The user places it and
  tells Claude what happened (`result`, `fill`).
- **`"broker": "kite"`**: Zerodha's Kite MCP server (github.com/zerodha/kite-mcp-server).
  Its hosted endpoint, `https://mcp.kite.trade/mcp`, is for reading: quotes,
  holdings, positions, orders, historical candles. Placing orders needs a
  self-hosted server with `place_order` enabled. Set `place_order`,
  `modify_order`, `cancel_order` and the GTT tools to **Needs approval**, never
  Always allow. The user logs in to Kite in their browser through the
  server's `login` flow, never in the chat. The ticket shows each `place_order`
  call (variety, exchange, tradingsymbol, transaction_type, quantity, product,
  order_type, price / trigger_price, validity).
- **Groww's connector**, where the user has it, reads holdings, positions,
  margins, quotes and candles; the orders still go in the Groww app.
- **`"paper": true`** (default) is practice: Indian brokers have no paper
  accounts, so nothing goes anywhere; record pretend fills with `fill`.
  `"paper": false` is real money, and only the user sets it.

## Steps: the entry

1. `ticket.py show`. Only READY tickets go to the user.
2. Show ONE ticket and ask: "Place this order? Reply yes or no." Never "yes to all".
3. `ticket.py approve --index N --reply "<the user's reply, word for word>"`.
   "Not recorded" means it was not a clear yes for this order: ask again.
4. Manual: the user places the legs in their app. Kite: call `place_order`
   for the entry with exactly the printed arguments; after it fills
   (`get_orders` / `get_positions`), the two exits.
5. Record what happened: `ticket.py result ...` (placed with the order id and
   fill, denied, or failed). A failed order is not retried without a new check and a new yes.

## Steps: out by the flat-by

- By `flat_by` (15:10), anything still open gets closed: `ticket.py flatten
  --symbol RELIANCE --qty 63`, then `/trader-risk`, then the user's yes.
- **Cancel the open stop-loss and target first**, then sell. If the user misses
  it, the broker squares off MIS itself around 15:15 to 15:25 and charges for it.

## Example: the reel

```
ORDER 1 of 1, PRACTICE (paper: nothing goes to a broker), your broker's app
  BUY 63 RELIANCE on NSE, market, MIS, good for today
  stop-loss 1163.30
  take-profit 1185.30
  max loss about Rs 766.07 with charges if the stop fills at 1163.30 (it can fill worse in a fast market)
  READY: trader-risk PASS, waiting for your yes
  Practice: what you would enter:
    1. BUY 63 RELIANCE on NSE, MIS (intraday), MARKET, validity DAY
    2. once it fills: SELL 63 RELIANCE, MIS, SL-M (stop-loss market), trigger 1163.30
    3. and: SELL 63 RELIANCE, MIS, LIMIT at 1185.30 (the target)
    4. when one of those two fills, cancel the other at once (or use your broker's GTT OCO)
```

## What it never does

- Never places an order without all three gates, never two orders on one yes.
- Never places orders from a scheduled or background task.
- Never asks for, reads, stores or repeats passwords, PINs, TOTPs, API keys or access tokens.
- Never switches `"paper"` to false. The user does that.
- Never calls F&O, cancel-all or exit-all tools on its own.

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
