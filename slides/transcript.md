# Presentation transcript

Target: about 5 minutes spoken (about 700 words at a calm pace), leaving buffer inside the 7-minute slot. Click cues match the deck. Slide numbers are the footer numbers.

Suggested split: **Speaker A** takes slides 1 to 5, **Speaker B** takes slides 6 to 9. Swap the labels if you prefer.

---

## Slide 1: Title (0:15) — A

Hi everyone, we're Tony and Miguel. Our design for the MultiPlanetary Exchange fits in one sentence: **a lost packet can delay a deal, but it can never change who owns what.** Everything else follows from that.

## Slide 2: The problem (0:30) — A

*(Point at Earth, then Neptune as the ring expands.)*

Light takes about four hours to get from Earth to Neptune. So a message can be late, lost, duplicated, or contradicted, and nobody can just ask a neighbor what happened. A normal exchange assumes it can. Here we have nine settlements, no shared clock, and no central hub. The question is: what can you promise when you can't confirm anything?

## Slide 3: Our answer (0:45) — A

Our answer is that **nothing is owed across the lag unless it is locked first.** Three ideas.

One: nine Branches, one per settlement. Each keeps the only ledger for the assets held there. No hub, no central bank.

Two: locks, not timers. An asset is reserved for one named deal, and only that deal's recorded outcome releases it, never a clock running out.

Three: one decider. The Branch holding the offer decides exactly once and repeats that same answer to every copy of the request.

Because of this, our first three guarantees hold whatever the network does.

## Slide 4: Share trade (0:50) — A

*(Click through: lock, packet crosses, decide, commit crosses back, release.)*

Here's a share trade. Earth buys a share from Neptune, and a full round trip takes 8.35 hours.

Earth locks the buyer's money first. The request crosses to Neptune. Neptune decides once and commits. The commit travels back, and Earth releases the money.

The key point: the seller can spend the proceeds at hour 4.2, before Earth has even heard back, because those proceeds are backed by the buyer's lock. And if a packet is lost, the lock holder just resends. The money stays put.

## Slide 5: Price contract (0:45) — A

Now a harder case: a price contract. This is a capped Ceres Iron future over 288 hours.

Both sides lock their worst case **before** the position opens. We force the settling price into a band around the entry price, so the maximum loss is known up front. That means the winner is paid in full either way, from locked assets. No margin calls, no defaults.

The price of that guarantee is 30% of all cash locked. And the remote winner can spend 0.69 hours after maturity.

*(Handoff to B.)*

## Slide 6: Guarantees (0:30) — B

We state four guarantees. G1: funding is conserved and no asset serves two uses. G2: every cross-planet deal is all or nothing. G3: every price contract pays in full. Those three rest on the rules alone.

G4, that every lock eventually ends, also depends on our orbit model: it holds if the two Branches can eventually exchange a packet. We say that openly, because we'd rather be precise than overclaim.

## Slide 7: Evidence (0:40) — B

Then we tried to break it, and it held. 75 conservation and single-use checks over 16 simulated runs, none failed. A 200-year orbit scan, certified to one millisecond, showed no settlement is ever cut off, and every pair is at most three links apart. And route availability is 100% in every 24-hour window.

One honest note: with random packet loss, no unconditional deadline exists. Earth to Neptune finishes at its no-loss time 30% of the time, and within 24 hours of it 79% of the time. It only delays, and the lock stays in place the whole time.

## Slide 8: Limits (0:25) — B

And the limits. Capital sits locked, and a far client can't pull it back early during an outage. Neptune clients see prices later, 8.2 to 12.4 hours per deal. Losses are bounded, and we left out real-world effects like solar conjunction. Those can delay a deal, but none can unfund one.

## Slide 9: Summary (0:20) — B

So, three rules. **Lock first. Decide once. Resend until it lands.** A lost packet costs time, never money.

Thank you. We're happy to take questions, and the appendix has the backup for any number.

---

## Timing

| Slides | Time |
| --- | --- |
| 1 to 5 | about 3:05 |
| 6 to 9 | about 1:55 |
| **Total** | **about 5:00 spoken** |

That leaves about 2 minutes of buffer for clicks and transitions. If you run long, cut slide 8 down to one sentence ("Capital stays locked, far clients see prices later, and effects we left out can only delay a deal") and trim slide 7 to the three numbers.

## Likely questions

- **Why 30% locked?** That is the cost of paying the winner in full without margin calls. Appendix covers the sizing.
- **Why is G4 conditional?** Termination needs the two Branches to eventually exchange a packet, which is a fact about the orbits, not the rules.
- **What if the lock holder never comes back?** The lock only ends on a recorded outcome, so the asset stays reserved. It never double-spends. That's the trade-off on slide 8.
