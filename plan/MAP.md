---
label: wayfinder:map
title: MultiPlanetary Exchange — GQH 2026 submission
---

# Map: MultiPlanetary Exchange — GQH 2026 submission

## Destination

Two submitted PDFs built in LaTeX/Overleaf by **Sun 2026-10-04 09:00 ET** (hard deadline 10:00): a **design paper (≤12 pp)** and an **evidence appendix (≤12 pp, S1–S3 + E1–E5, claiming Tier 3 on E4 and E5)**, every number in both generated from one codebase so balances agree everywhere.

## Notes

- **Execution is in scope** (override of plan-only default): tickets may produce code, tables and LaTeX, not just decisions. Design spec must be locked by **Sat 2026-10-03 ~10:00 ET**; after that only compute + write.
- Team: 2 people, rudimentary finance. Claude does all computation and drafts; the team decides and reviews. Explain finance in plain terms before asking for a decision. Primer: [docs/primer.md](../docs/primer.md). Glossary: [CONTEXT.md](../CONTEXT.md).
- Scoring to optimise: correctness/asset protection 30, economic usefulness 25, risk 20, quant evidence 15 (3 per E-item), clarity 10. Polish and code volume earn 0.
- Skills: grilling + domain-modeling for decision tickets; research for research tickets.
- Source of truth for rules: `MultiPlanetary_Exchange_System_Participant_Brief.pdf`; check for posted numbered clarifications before locking anything.
- Code lives in `code/` (Python + numpy). `code/orbits.py` matches every epoch check position to < 5e-7 AU.
- Tracker: local markdown. Tickets in `plan/tickets/`, frontmatter carries `type`, `status` (open/closed), `assignee` (the claim), `blocked_by`.

## Decisions so far

- [Destination & deliverables](tickets/00-destination.md): both documents, full execution inside the map, LaTeX/Overleaf, Claude computes and drafts.
- [Settlement philosophy](tickets/00-destination.md#q3): "money on the table" — every obligation fully pre-funded at opening; no margin calls, no credit across light-lag.
- [Ledger architecture](tickets/00-destination.md#q7): one home ledger (Branch) per settlement, no central hub or bank; cross-planet moves by lock → commit → release; each price contract refereed by the Branch where its price is published.
- [Products](tickets/00-destination.md#q9): Ares Habitat share trade with cross-planet delivery-vs-payment (equities) + capped cash-settled Ceres Iron future (futures).
- [Foundations primer for the team](tickets/10-primer.md): primer + glossary written for the team.
- [Deployment assessment — numeric size of real-world effects](tickets/09-deployment-research.md): five sourced effects, none threatens solvency; conjunction and clock drift need protocol rules (print fallback, single TDB timescale).
- [Opening balance sheet](tickets/00-destination.md#q10): six accounts, $500,000 and 5,000 shares, at Earth/Mars/Ceres/Jupiter/Neptune/Mercury.

## Not yet specified

- **Long-term operation (brief §9):** identifier sizing and lifetime, bounded storage, accepted demand rate and what happens above it, capital replenishment via fees. Shape depends on the message protocol and fee decisions.
- **Fee model:** whether Branches charge fees to fund themselves (they start with nothing) and how that interacts with "no free endowment".
- **Service table (paper):** product × settlement offer/conditions/restrictions — falls out once the access table (S3) and the far-pair risk treatment are known.
- **Risk register ranking:** candidates so far: Neptune/Uranus far-pair latency (12.4 h), lossy direct service beyond ~10 AU, Ceres-local information advantage before each print, blocking two-phase lock under isolation, Mercury solar-conjunction blackouts. Ranking waits on S2 and E4 results.
- **Protocol rules surfaced by deployment research:** fallback when the settling Ceres print falls inside a solar blackout of the referee or a counterparty; all deadlines in TDB. Likely lands inside the future-terms and protocol tickets.
- **Labeled extensions:** routing far pairs via an intermediate Branch; malicious-operator handling.

## Out of scope

- Malicious or colluding operators beyond a labeled-extension paragraph (brief marks it optional).
- Higher-fidelity gravity / relativistic ephemeris (allowed only as labeled extension; not worth the clock).
