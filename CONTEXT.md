# MultiPlanetary Exchange — Context

The vocabulary of our exchange design. Terms from the brief keep the brief's meaning; this file adds the terms our design introduces.

## Language

**Branch**:
The one institution at a settlement that keeps the authoritative ledger for every asset held at that settlement. An operator in the brief's sense.
_Avoid_: bank, exchange node, hub

**Home ledger**:
A Branch's book of record. Every NeoDollar and share sits on exactly one home ledger at every moment.
_Avoid_: database, chain

**Lock**:
A ledger state in which an asset is reserved for one named deal and cannot be spent or locked again. Only the deal's commit or decline ends it, never a timer.
_Avoid_: hold, freeze (in the paper)

**Commit**:
The counterparty Branch's decision that a cross-planet deal is final. Its client may spend the proceeds from this moment, because they are backed by the initiator's lock.

**Release**:
The initiator Branch turning a locked asset into the counterparty Branch's property when the commit arrives.

**Inter-Branch account**:
A balance one Branch holds on another Branch's ledger. It is a claim, not new money: it nets to zero across the system.
_Avoid_: nostro (in the paper)

**Referee Branch**:
The Branch that clears a price contract: it records the position, holds or controls both sides' locked maximum loss, and pays out. It is always the Branch where the contract's price source publishes.
_Avoid_: clearinghouse, CCP

**Official print**:
One signed price observation released by a price source, locally, at its single settlement, at a scheduled hour. A contract names which prints count.

**Settling print**:
The single official print a contract names as the one that fixes its payoff. Its publication is the contract's **maturity**.
_Avoid_: final mark, closing price

**Interim print**:
Any official print before the settling print. Information only: it creates no ledger entry and moves no money.
_Avoid_: mark (implies a payment)

**Capped future**:
A cash-settled future whose settlement price is clipped to entry ± a cap, so each side's maximum loss is known and fully locked at opening. Positions are held to maturity; there is no early close-out.

**Clip**:
Forcing the settling print into the band entry ± cap before computing the payoff.

**Freeze**:
The period before a settling print in which the referee Branch accepts no new positions. Existing positions are unaffected.
_Avoid_: halt, suspension (those mean stopping existing service)

## Relationships

- Each **Settlement** has exactly one **Branch**; each **Branch** keeps one **Home ledger**.
- A cross-planet deal touches exactly two **Home ledgers**: **Lock** at the initiator, **Commit** at the counterparty, **Release** at the initiator.
- Each price contract has exactly one **Referee Branch**, located where its **Official print** is published.

## Flagged ambiguities

- "Two ledgers" was used to mean two-Branch deals, not a system with two ledgers in total. Resolved: one **Home ledger** per settlement; a single deal touches at most two.
- "Spend NeoDollars" means moving existing units between accounts. No one can create them; the system total is constant.
