---
title: Destination & opening decisions
type: grilling
status: closed
assignee: claude
blocked_by: []
---

## Question

What are we delivering, and what is the core shape of the design?

## Resolution (2026-10-03)

- **Deliverables:** design paper ≤12 pp + evidence appendix ≤12 pp, LaTeX/Overleaf. Map carries execution through to PDFs. Spec lock Sat ~10:00 ET. Claude computes and drafts; team decides and reviews.

### Q3
**Money on the table.** Every obligation is fully pre-funded at opening: each side of a price contract locks its maximum possible loss. No margin calls, no unsecured credit across light-lag. Cost accepted: higher encumbered capital (part of the 5-pt capital-efficiency score).

### Q7
**Home ledgers, no hub, no central bank.** Each settlement has one Branch keeping the authoritative ledger for assets held there. Cross-planet value moves: initiator Branch locks → counterparty Branch commits (its client spendable on commit, backed by the irrevocable lock) → initiator Branch releases on receipt of commit. Locks are never released unilaterally on timeout. Each price contract is refereed (cleared) by the Branch where its price source publishes.

Evidence (h=0, no-loss, best ≤3-link backbone route): bilateral vs Mars hub — Neptune↔Earth 8.4 h vs 8.2 h; median pair 2.7 vs 2.5 h; worst pair 12.4 h (Uranus↔Neptune) vs 8.2 h; same-planet 0 vs 1.4 h; 2 vs 4 backbone messages per trade. Script: `code/compare_arch.py`.

### Q9
1. **Ares Habitat shares** — equity trade with cross-planet delivery-vs-payment (covers "equities" and requirement 1, value move).
2. **Ceres Iron capped future** — cash-settled on a named official Ceres print, payoff capped ±30% of entry, both sides lock max loss at open (covers "futures", requirement 2 if open ≥240 h, requirement 3 rising/falling).

### Q10
| Account | Settlement | NeoDollars | Ares shares |
|---|---|---|---|
| Terra Capital | Earth | 200,000 | 0 |
| Ares Habitat Treasury | Mars | 40,000 | 3,000 |
| Ceres Iron Works | Ceres | 60,000 | 0 |
| Callisto Foundry | Jupiter | 60,000 | 0 |
| Triton Fund | Neptune | 100,000 | 1,000 |
| Helios Traders | Mercury | 40,000 | 1,000 |
| **Total** | 6 settlements | **500,000** | **5,000** |
