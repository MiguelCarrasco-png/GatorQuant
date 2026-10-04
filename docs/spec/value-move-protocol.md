# Cross-planet value-move protocol

Status: locked 2026-10-03. Resolves [Cross-planet value-move protocol — messages, states, loss handling](https://github.com/MiguelCarrasco-png/GatorQuant/issues/4).
Vocabulary: [CONTEXT.md](../../CONTEXT.md). All times are TDB, in milliseconds from t = 0.

## 1. Roles and the one rule

A cross-planet deal always accepts a **firm offer**.

- **Deciding Branch** is the Branch holding the offer. It decides **once**, on the first arrival of the LOCK, and records that decision durably before it sends any reply.
- **Initiator Branch** is the Branch of the client accepting the offer. It locks its client's side and is the **only** party that ever resends.

The deciding Branch never resends on its own. It answers every LOCK copy it receives with the decision it already recorded. The one exception is SETTLE (§6), which the referee sends once without being asked.

A lock ends only on COMMIT, DECLINE or SETTLE. A timer never ends a lock.

Deals between two clients at the same settlement never use this protocol. They are one atomic posting on one ledger.

## 2. Messages

Payload ≤ 960 B, fixed-width, no compression. One packet carries a 16 B batch header plus up to **14 records of 64 B** each (912 B).

**Batch header (16 B)**

| Field | Bytes |
|---|---|
| sender Branch (node ID 1–9) | 1 |
| receiver Branch | 1 |
| record count | 1 |
| reserved | 5 |
| low-water mark: all of the sender's deals with this receiver numbered below this are closed | 8 |

**Record (64 B)**, the same layout for every type

| Field | Bytes | Notes |
|---|---|---|
| type | 1 | 1 LOCK, 2 COMMIT, 3 DECLINE, 4 SETTLE |
| flags | 1 | bit 0 ABORT, bit 1 RESUBMISSION |
| deal ID | 9 | initiator Branch (1) + initiator's deal counter (8); never reused |
| offer / contract ID | 8 | assigned by the deciding Branch when the offer is posted |
| initiator account | 2 | |
| offer-holder account | 2 | |
| leg A: asset code, quantity | 2 + 8 | what the initiator's client gives (cash in cents, shares in units) |
| leg B: asset code, quantity | 2 + 8 | what the initiator's client gets |
| time | 8 | LOCK: creation time. Reply: decision time |
| reason / amount | 9 | DECLINE: reason code (1). SETTLE: release-to-referee amount (8) |
| reserved | 4 | |

Every reply echoes the full terms of the LOCK. That lets a mismatch be detected rather than silently accepted.

**Batching:** a record goes out as soon as it is created. Records already waiting for the same peer at the same moment share a packet. Capacity is ≈14 deals per packet, so the 600/day shared quota carries about 8,400 deal records a day.

## 3. Ledger states

**Initiator ledger (e.g. Earth, Terra buying 200 Ares from Triton for $25,000)**

| State of Terra's $25,000 | Entered when | Left when |
|---|---|---|
| Free | — | Terra instructs acceptance and free balance ≥ amount (otherwise refused locally and nothing is sent) |
| Locked (deal D) | LOCK created | COMMIT or DECLINE recorded for D |
| Released | COMMIT arrives: debit Terra $25,000, credit Neptune Branch's inter-Branch account at Earth $25,000. Credit Terra 200 Ares as a claim on Earth Branch, backed by Earth Branch's inter-Branch holding at Neptune (created by Neptune at commit) | final |
| Free again | DECLINE arrives | final |

**Deciding ledger (Neptune)**

| State of Triton's 200 Ares | Entered when | Left when |
|---|---|---|
| Free | — | Triton posts a firm offer |
| Reserved (offer O, expiry hour X) | offer posted | fills, is withdrawn locally, or passes X → Free |
| Transferred | COMMIT recorded: shares move to Earth Branch's inter-Branch account at Neptune. Triton is credited $25,000 as a claim on Neptune Branch, backed by Terra's lock at Earth (Neptune Branch's *pending release*) | final |

Neptune Branch treats the pending release as settled once Earth's low-water mark passes D. Until then it may not instruct any use of that Earth balance.

**Spendable moments:** Triton at COMMIT on Neptune, Terra at release on Earth. The trade is complete at the later of the two, normally the release.

**Double-spend:** a Locked or Reserved asset is not free balance, so any other instruction against it is refused locally. Clients cannot unlock anything. Only the Branch records above change state.

## 4. Decision rule at the deciding Branch

Decline on first arrival, for one of these closed reasons only:

1. Offer filled, withdrawn, or past its expiry hour at the LOCK's arrival time. An offer on a price contract expires no later than the start of the contract's freeze.
2. The terms in the LOCK differ from the offer: asset, quantity or price.
3. The LOCK carries ABORT and D is still undecided.
4. Malformed record or unknown account.

If none of these applies, commit. Either way, record the decision durably first, then reply.

## 5. Loss, delay, duplication, contradiction, faults

| Event | What happens | Who owes what |
|---|---|---|
| LOCK lost (transport returns status unknown) | Initiator resubmits LOCK D unchanged (RESUBMISSION flag), on the current session or a fresh one, on the next usable route chosen by foresight pinning. No cap on tries; 1 quota packet each. | Terra's $25,000 stays locked. Terra loses the use of it, never the money. |
| COMMIT / DECLINE lost | Initiator's next LOCK copy triggers the recorded answer again. | Triton is already spendable; Earth owes the release on arrival. |
| LOCK delayed past the offer expiry | Decline reason 1. | Lock returns to Terra when the DECLINE arrives. |
| Duplicate LOCK | Recorded answer resent. No second decision. | — |
| Duplicate COMMIT / DECLINE after D is closed | Ignored. | — |
| Contradiction: same deal ID, different terms | Deciding Branch replies with the recorded decision and the original terms; the new terms are ignored. Initiator logs a protocol error. | — |
| ABORT | A flag on a LOCK copy. Decline if D is undecided; otherwise the recorded COMMIT is resent and the deal stands. | — |
| 72 h isolation of either Branch | Locks stay locked; local trading at the isolated settlement continues. Resubmissions resume on reconnection. | Locked capital × hours is reported as the cost. |
| Endpoint reset | Sessions are gone; durable ledgers, deal counter, decisions and packet IDs survive. On restart the Branch handshakes new sessions (1 SYN quota each) and resubmits a LOCK for every deal it holds Locked. | — |
| Forced-loss 6 h | Covered by transport and endpoint retries; any deal ending in status unknown follows row 1. | — |

**Route and timing rules** (from the E4 scan and the deployment research):
- Every deadline, offer expiry and decision time is in TDB, the one shared timescale.
- **Offer life** (added 2026-10-03 while drafting the paper, rule R5): the initiator accepts a remote firm offer only if its remaining life is at least R_e + T0 + 3·ΣR_h on the pinned route (T0, R_e = 2·T0 + 24 h and each hop's R_h = 2 × flight + 1 h, all at enqueue). That is the latest a second endpoint attempt can arrive without being abandoned, so a decline needs two abandoned attempts. Otherwise the initiator refuses locally and locks nothing. At h 0: 68 h Earth→Neptune, 86 h Uranus→Neptune, 36 h Jupiter→Ceres. The traced offers use 96 h (VM) and 48 h (future). Monte Carlo (`code/e2_latency.py`): a 24 h offer would be declined 7.8% of the time from Earth, a 48 h offer 0.6%, and under this rule 0.00%.
- Pin a session's route by foresight: choose a route that is open for the next 24 h, not simply the fastest one now.
- Never launch on a link whose reverse direction closes within one R_h.
- Closures at Mars, Jupiter, Saturn and Ceres can outlast the 30-day packet lifetime. Nothing waits in a queue behind such a closure. The initiator re-routes or resubmits on a fresh session.
  - **Threshold:** before each send, a Branch checks its pinned route (both directions). If a known *geometric* closure would hold the packet more than 24 h at any hop, it opens a fresh session on the route pinned by foresight for the next 24 h (1 SYN quota) and sends there. Records wait for the SYN-ACK. Scheduled maintenance (one-time, 24 h) is waited out, never re-routed around.
  - Cost at the E5 difficult epoch (h 816,143): one extra handshake. SETTLE arrives 3.15 h later than an open route would allow. Queueing behind the closure instead would hold it 1,238 h (see *E5 shifted epochs*, issue 10).

A solar blackout never delays a settlement *decision*. The referee is at the print's settlement and sees the settling print locally. A blackout only delays SETTLE reaching the remote side, and the pull rule (§6.3) covers that.

**Optional echo:** when it has spare room, a deciding Branch adds its decisions above the receiver's low-water mark to any batch already going to that initiator. This only speeds recovery. Correctness rests on the pull rule.

**Bounded storage:** the deciding Branch may delete the decision record for D once the initiator's low-water mark for this pair passes D. Deal counters are 8 B and never wrap in the modeled lifetime.

## 6. Price contracts: pledge at home (Ceres Iron capped future)

Callisto Foundry (Jupiter, long) accepts a firm offer from Ceres Iron Works (Ceres, short).

1. **Open.** Jupiter Branch locks Callisto's maximum loss ($75,000) on the Jupiter ledger and sends LOCK (contract ID, legs = margin and number of contracts). Ceres, the referee and deciding Branch, applies §4. Ceres Iron's margin is already reserved by its offer. On commit, Ceres records the position. **Position open** = the COMMIT record at Ceres, because both margins are then encumbered. Jupiter learns of it when COMMIT arrives, but the Jupiter lock is **not** released: from now on, only a SETTLE ends it.
2. **Settle.** At the settling print, Ceres computes the clipped payoff Y and records it.
   - **Short wins Y.** Ceres credits Ceres Iron Y at once, as a claim backed by the Jupiter lock, so it is spendable at the print instant. Ceres also returns Ceres Iron's own margin. SETTLE tells Jupiter: release Y to Ceres Branch's inter-Branch account at Jupiter, return $75,000 − Y to Callisto.
   - **Long wins Y.** Ceres moves Y from Ceres Iron's margin to Jupiter Branch's inter-Branch account at Ceres and returns the rest of Ceres Iron's margin. SETTLE tells Jupiter: return $75,000 to Callisto and credit Callisto Y as a claim on Jupiter Branch. Callisto can spend it when SETTLE arrives.
3. **Loss.** Ceres sends SETTLE once. If Jupiter still holds the lock after the settling print plus R_e, Jupiter resubmits its LOCK, and Ceres answers with the recorded SETTLE. This is the same pull rule as §1.

## 7. What this does not decide

- Sessions per Branch pair, the quota budget and interim-print forwarding → *Institutions chartered and backbone quota budget* (issue 5, resolved: per-Branch 66/24 h slices with 10 for recovery; each run opens its trade pair at h −72 on a foresight-pinned route; keep-alive at 120 h idle; Ceres Branch forwards interim prints to Jupiter over the backbone).
- Contract size, cap, print schedule → *Ceres Iron future — exact terms, margin rule, price paths*.
- Using an inter-Branch balance in a later deal (e.g. Triton paying someone at Earth) is a new deal under this same protocol. Fees and replenishment are still unmapped (fog).

## 8. Amendments of 2026-10-04 (hardening round; issue 16)

These supersede the matching text above.

- **R8 (recovery).** Only the lock holder resends. After one `R_e` with no recorded answer (for a pledge: after the settling print plus `R_e`) it resubmits its LOCK, batched with every other probed lock to the same peer (14 records per packet), then every `P = 24/10 = 2.4 h` per packet (stretched to `P x ceil(n/14)` for `n` open locks), at once on any packet from the peer (at most hourly), and from a fresh session if none is up (after one handshake round trip). A newer copy replaces older ones; a closed deal drops its copies. The decider repeats a recorded answer at most once an hour per deal. The referee's SETTLE is one application message; transport retries it at `R_e`.
- **R22 (extension, tested).** The lock holder applies COMMIT/DECLINE only if the echoed terms equal its LOCK, applies SETTLE only if the amount equals the payoff recomputed from the settling print carried in the record (value in 4 reserved bytes), logs a second different outcome for a closed deal. Detection, not enforcement.
- **R23 (extension, tested).** No settling print 24 h after maturity: the referee voids the contract and every margin returns.
- **R24 (extension, analysed).** Griefing cap: refuse a (client, offer holder) pair for 7 days after 3 reason-1 declines in 24 h.
- **Offers expire:** an offer still open at its expiry hour frees its reservation (R4).
