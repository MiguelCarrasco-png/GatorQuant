# Foundations Primer — MultiPlanetary Exchange

Read this once, top to bottom (about 20 minutes). It covers the finance you need, why space breaks a normal exchange, and how our design fixes it. Exact word meanings are in [CONTEXT.md](../CONTEXT.md).

---

## Part 1 — The finance you need

### Money in this game: NeoDollars
There are exactly **$500,000** in our world, plus **5,000 shares**, and that never changes. No one can print more. Spending means moving units from one account to another. Think of Monopoly with no bank: everyone gets their starting cash, players pay each other, and the total on the table stays the same.

### Shares (equities)
A share is a slice of ownership in a company. We invented one: **Ares Habitat**, a Mars construction company. A **share trade** swaps shares for money: the seller gives shares, the buyer gives NeoDollars.

**Delivery-versus-payment (DvP)** means the shares and the money change hands together or not at all. Nobody hands over their side and then waits for the other side to maybe show up.

### Futures
A future is a deal made *today* about a price *later*.
- The **long** side wins if the price goes up.
- The **short** side wins if the price goes down.
- **Cash-settled** means no iron ever moves. At the end, the loser pays the winner the difference in money.

Brief's example: 10 contracts, multiplier 100, entry price 100, final price P.
- The long receives **10 × 100 × (P − 100)**.
- If P = 120, the long gets $20,000 and the short pays $20,000.
- If P = 80, the long pays $20,000.

Who uses this in our story:
- **Ceres Iron Works** (a miner) is *short*. It fears iron prices falling, and the future pays it if they do.
- **Callisto Foundry** (a manufacturer that buys iron) is *long*. It fears prices rising, and the future pays it if they do.

Both are **hedging**: using the future to cancel out a business risk.

### Short positions
"Short" means you profit when a price falls. In a future, the short side is simply the other side of the deal.

### Margin
Margin is the deposit you lock so the other side knows you can pay if you lose.
- **Normal exchanges** take a *small* deposit (say 10% of the possible loss). As prices move, they send **margin calls** ("top up your deposit or we close your position"). This needs fast communication.
- **Our exchange** takes the *whole* maximum possible loss up front. There are never any margin calls.

### Default
A default is someone failing to pay what they owe.
- A **funded default** means the winner still gets paid in full from money that was already locked.
- In our design every default is funded automatically, because the maximum loss was locked at the start.

### Clearing and settlement
- **Clearing** is the referee work: recording who owes whom and checking that it's covered.
- **Settlement** is actually moving the money or shares so the books show the final result.

### Limit order
A limit order says "buy, but at no more than X" (or "sell, but at no less than X"). It protects you when your price information is stale, which out here it always is.

---

## Part 2 — Why space breaks a normal exchange

| Fact from the brief | What it breaks |
|---|---|
| Light takes about 8.3 minutes per AU. Neptune is about 4 hours from everyone. | Nobody knows what is happening elsewhere *right now*. |
| Messages get lost: a backbone launch over 28 AU has about a 43% chance of being lost, and a direct packet from Neptune to Earth about 90%. | You can't assume a message arrived. You need confirmations and retries. |
| The Sun blocks paths that pass within 0.10 AU of it. Scheduled maintenance and incidents cut links. | Some routes are down for hours or days. |
| Only 600 backbone packets per day are shared by the whole system. | Every message costs scarce capacity. |

**The core danger.** Suppose Earth and Neptune each think "I'll go ahead and hope the other side agrees." Then the same money can be promised twice, or a winner can be owed money that the loser has already spent somewhere else. The judges give the most points (30) for proving this *cannot* happen.

---

## Part 3 — Our design in one page

**1. One Branch per planet, no central bank.**
- Each settlement has a Branch with its own notebook (home ledger).
- Every dollar and share is written in exactly one notebook at any moment.

**2. Moving value between planets: lock → commit → release.**
Example: Triton (Neptune) sells 500 Ares shares to Terra (Earth) for $25,000. Times assume no packets are lost.

| Time | Branch | Action |
|---|---|---|
| h 0 | Earth | **Locks** Terra's $25,000 for this deal only. Sends "locked, deal on?" |
| h 4.2 | Neptune | **Commits**: the shares now belong to Earth's Branch, and Triton's account shows $25,000 **spendable now**. Sends "done". |
| h 8.4 | Earth | **Releases**: the locked $25,000 becomes Neptune Branch's property. Terra receives the shares. |

**3. "Triton can spend money Earth hasn't sent yet?"** Yes, safely.
- Nothing physical ever travels. "Sending money" only means notebooks rewriting who owns what.
- At h 4.2, Earth's $25,000 is **locked for this deal and nothing else**, and our rule says it can never be unlocked except by Neptune's answer.
- So Neptune's Branch holds a claim that is 100% backed. It lets Triton spend against it, the way you can spend a cheque once the bank has guaranteed it.
- System-wide totals still add up. Earth's notebook shows $25,000 in "owed to Neptune Branch", Neptune's notebook shows $25,000 for Triton, and those two lines are the same dollars seen from both ends. Counted once, the total stays $500,000.
- **The cost:** if Neptune goes silent, Terra's $25,000 stays locked until Neptune answers. Terra loses the *use* of that money for the outage, but never the money itself. That's a trade-off we state openly in the paper.

**4. Price contracts: money on the table.**
- Each side locks its **maximum possible loss** at opening. That's possible because the payout is **capped** (the price used for payment is clipped to entry ± 30%).
- No margin calls, so delays and lost messages can't create an unpaid loss.

**5. The referee sits where the price is born.**
- The iron price is published at Ceres, so the **Ceres Branch** referees iron futures.
- It sees each official print the instant it's released. No price has to cross space before payment is decided.

**6. Why the 8-hour delay doesn't change what you're paid.**
- The contract pays on a **named official print**, e.g. "the Ceres print at hour 312". Everyone agrees what that number is.
- Delay only changes *when* a far-away party learns the result, never *what* they get.
- Delay *does* matter when entering a trade: you only know an old price. Limit orders protect you. Trading also freezes just before each print, so Ceres locals can't trade on a print before everyone else can react.

---

## Part 4 — The brief's worked example through our design

**Contract:** 10 contracts × multiplier 100, entry 100, cap ±30%, so the settlement price is clipped to [70, 130].

**Margin rule, stated once before any price is known:**
- Each side locks 10 × 100 × 30 = **$30,000** at opening.
- Daily prints are published for information only. Money moves once, at maturity.

This obeys every rule in the brief:
- **No future prices used:** the lock depends only on the contract terms.
- **Same in both runs:** we don't know which way prices will go, and the rule doesn't care.
- **Counted once:** interim plus final payments trivially add up to the total, because there are no interim payments.

| Run | Final print P | Long side | Short side |
|---|---|---|---|
| Rising | 125 | receives $25,000 | pays $25,000 from its locked $30,000; $5,000 unlocked |
| Falling | 75 | pays $25,000; $5,000 unlocked | receives $25,000 |
| Binding variation | 140 | receives $30,000 (**cap binds**) | loses exactly the locked $30,000 |

**Settlement timing (no packet loss):**
- Ceres knows P instantly.
- The Jupiter side learns about **0.7 h** later via Relay B.
- The brief asks for three moments, reported separately:
  - **Discharge:** Ceres records the debt as paid.
  - **Backed claim:** the winner holds a claim covered by locked money.
  - **Spendable:** the winner's own Branch credits them.

---

## Part 5 — What the judges score, and where each point comes from

| Criterion | Points | Where we earn it |
|---|---|---|
| Correctness & asset protection | 30 | One notebook per asset, irrevocable locks, full pre-funding. Every table generated by one program, so the numbers always agree. |
| Economic usefulness | 25 | All 9 planets served, times with probabilities, few packets (2 backbone messages per trade). We give up some capital efficiency. |
| Risk discovery | 20 | Our own findings: far-pair latency, lossy direct service, Ceres information edge, locks stuck during isolation, solar blackouts. Plus a stress test chosen to hurt us. |
| Quantitative evidence | 15 | E1–E5 computed from code, targeting the top tier of each. |
| Clarity | 10 | Plain tables, one row per step, assumptions labeled. |

## Part 6 — Glossary of brief terms (short)

- **AU:** the Earth–Sun distance, about 8.3 light-minutes.
- **Backbone:** the official relay network. Reliable-ish, 600 packets per day for everyone.
- **Direct service:** cheap, lossy client messaging. Can't carry official records.
- **Relay A / B:** two satellites circling the Sun at 2.83 AU that forward backbone packets.
- **Solar exclusion:** a path passing within 0.10 AU of the Sun is blocked.
- **Session / SYN / ACK:** the handshake that opens a backbone connection. We open ours before the market opens.
- **Encumbered:** locked and unusable for anything else.
- **Asset-hours:** amount locked × hours locked, a measure of how much capital we tie up.
- **Exposure:** the most a side can lose. For us, that's always exactly what it locked.
- **Conditional (no-loss) trace:** the timeline if no packet is lost. Evidence, not a promise.
- **Reset:** restarting from the opening balance sheet for a new test run.
