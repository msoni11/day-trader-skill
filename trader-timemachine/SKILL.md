---
name: trader-timemachine
description: >-
  Time Machine for NSE trades. Replays every possible outcome of a trade
  before you risk a rupee: 10,000 simulated sessions plus every past time the
  setup fired. Takes the plan from trader-exit (entry, stop, target), rebuilds
  the rest of the day 10,000 times from the stock's own 5-minute bars over the
  last 60 days (9:15 to 15:20 IST), and re-runs the same rule on every past
  session. Prints the odds of target first, stop first, or neither by your
  flat-by time, where the price sits then, the average R, the history, and one
  honest verdict, then hands off to /trader-budget. Use when the user says
  "run the time machine", "replay this trade", "what are the odds", "simulate
  this trade", "monte carlo", "backtest this setup", "how often does this hit
  the target", "is this a coin flip", or after /trader-exit writes a plan.
argument-hint: "[run|chart] [--until 15:10] [--seed 19]"
---

# trader-timemachine

Before a rupee is at risk, look at how this exact plan would have played out
on this stock's own recent days. The answer is often "close to a coin flip".
That is the point.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --until 15:10 --write   # replays to your flat-by
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --seed 7 --replays 20000 --json
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --symbol RELIANCE --date 2026-10-29 --entry 1174.30 \
    --stop 1163.30 --target 1185.30 --entry-time "9:40 AM"
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" chart
```

`--offline FILE` reads a saved 60-day 5-minute chart (Yahoo, or broker candles
in the same shape trader-entry reads). `--now` pins the clock (IST).

## How it works

- 60 days of 5-minute bars, one request. FULL sessions only: 73 bars, 9:15 to
  15:20. Yahoo's NSE feed leaves the 15:20 and 15:25 bars empty on most days,
  so a replay ends at 15:20 at the latest; a day trade is out by then anyway.
- Each replay walks the rest of the day bar by bar, each bar drawn from the
  stock's own bars at the same time of day (plus or minus 2 bars), scaled to
  the current price. A bar that touches both the stop and the target counts
  as the stop.
- History: the same rule on every past session: first close above the same
  opening range = entry, same stop rule, same R.
- The verdict compares target-first with the break-even share at the plan's R
  (50 % at 1R, 33 % at 2R). Under 5 points: "Close to a coin flip".
- A Muhurat session is refused: there is no history like it.

## Steps

1. Make sure `trader/plan.json` is today's plan. 2. Run `run --until <flat-by> --write`.
3. Tell the user the four odds, the price at the end, average R, history,
   then the verdict and the lines under it exactly as printed. Say the seed.
4. Coin flip or worse: say so plainly. 5. Say once it is not a prediction.
6. If the user still wants it, hand off to `/trader-budget`.

## Example: the reel

RELIANCE, Thursday 29 October 2026: entry 1,174.30 at 9:40 AM, stop 1,163.30, target 1,185.30 (1R):

```
10,000 replays of the rest of the session, 9:40 AM to 3:10 PM (66 five-minute bars), seed 19.
  target first   23.2 %
  stop first     32.8 %
  neither        44.0 %   still open at 3:10 PM
History: the same rule on each of those 52 real sessions fired 24 times: 12 target, 9 stop, 3 neither. Average R +0.062.
Leans toward the stop: target first 23.2 % vs stop first 32.8 %.
```

The replays lean toward the stop while the real history was slightly
positive: say both, and that 24 trades is a small sample.

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
