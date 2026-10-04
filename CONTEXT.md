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
A ledger state in which an asset is reserved for one named deal and cannot be spent or locked again. Only the deal's commit, decline, or settle ends it, never a timer.
_Avoid_: hold, freeze (in the paper)

**Commit**:
The counterparty Branch's decision that a cross-planet deal is final. Its client may spend the proceeds from this moment, because they are backed by the initiator's lock.

**Release**:
The initiator Branch turning a locked asset into the counterparty Branch's property when the commit arrives.

**Firm offer**:
A client's standing offer, posted at its own Branch with an expiry hour, whose assets that Branch reserves until the offer fills, is withdrawn, or expires. A cross-planet deal always accepts a firm offer.

**Initiator Branch**:
The Branch of the client who accepts a firm offer. It locks its client's side and keeps asking until the deal is decided.
_Avoid_: sender, requester

**Deciding Branch**:
The Branch holding the firm offer. It alone commits or declines, once, on the first arrival of the lock, and repeats that same answer to every later copy.
_Avoid_: counterparty (when the role matters), responder

**Decline**:
The deciding Branch's recorded refusal of a deal, for one of a closed list of reasons. It ends the initiator's lock and returns the asset to its owner.

**Abort**:
An initiator client's request to cancel a deal. It only asks; the deal ends as whatever the deciding Branch records — a decline if it was still undecided, otherwise the commit already made.

**Deal ID**:
The never-reused name of one cross-planet deal: the initiator Branch plus that Branch's running deal count.

**Settle**:
The referee Branch's instruction, sent once the settling print is known, telling the margin-holding Branch how much of a pledged lock to release to the referee and how much to return or credit to its client.

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

**Price Board**:
The institution that signs and releases a contract's official prints at its one settlement. It holds no money and never uses the backbone; a Branch forwards its prints to other Branches.
_Avoid_: oracle, feed

**Quota slice**:
A Branch's fixed share of the system-wide backbone quota, which it enforces by itself because no Branch can see the system-wide count.

**Recovery reserve**:
The part of a quota slice that only resubmissions and replacement handshakes may use, so new trade can never prevent a lock holder from resending.

**Pre-opened session**:
A backbone session handshaken before hour 0, so the first deal at hour 0 skips the handshake round trip.

**Keep-alive**:
A one-record message the lock holder sends on an idle session so it does not expire before the deal is decided or settled.

**Resubmit on contact**:
The lock holder's immediate resend of its LOCK for every deal it still holds Locked, triggered by the first packet it receives from that peer after silence, instead of waiting for its endpoint timer.
_Avoid_: reconnection retry

**Signed decision**:
A COMMIT, DECLINE or SETTLE carrying the issuing Branch's signature over the full terms it echoes, so the other Branch can detect a decision that contradicts the terms or an earlier decision. Detection only; labelled an extension because the brief assumes Branches follow the rules.

**Audit**:
The receiving Branch's recomputation of a SETTLE amount from the signed settling print and the contract terms, rejecting any instruction that does not match.

**Claim**:
A client's balance on a Branch's ledger that is backed by that Branch's inter-Branch holding or pending release at another Branch. A client never pledges a claim; only a Branch's holdings back anything.
_Avoid_: IOU, voucher

**Offer bulletin**:
An information-only announcement of a firm offer sent over the direct service. It creates no shared record; the terms are rechecked at LOCK time, so a stale or lost bulletin can only cause a decline.

**Griefing lock**:
A lock a client induces by accepting an offer its holder is about to withdraw, tying up the acceptor's cash for one round trip without a deal.

## Relationships

- Each **Settlement** has exactly one **Branch**; each **Branch** keeps one **Home ledger**.
- A cross-planet deal touches exactly two **Home ledgers**: **Lock** at the initiator, **Commit** at the counterparty, **Release** at the initiator.
- Each price contract has exactly one **Referee Branch**, located where its **Official print** is published.
- A remote side's margin is a **Lock** at that side's own Branch, controlled by the **Referee Branch**; only a **Settle** ends it.
- Only the side holding an open **Lock** ever resends; the **Deciding Branch** or **Referee Branch** only answers.

## Flagged ambiguities

- "Two ledgers" was used to mean two-Branch deals, not a system with two ledgers in total. Resolved: one **Home ledger** per settlement; a single deal touches at most two.
- "Spend NeoDollars" means moving existing units between accounts. No one can create them; the system total is constant.
