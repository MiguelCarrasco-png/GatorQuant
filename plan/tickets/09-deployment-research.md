---
title: Deployment assessment — numeric size of real-world effects
type: research
status: closed
assignee: claude
blocked_by: []
---

## Question

Find sourced numeric estimates for at least two real effects the baseline omits (candidates: planetary rotation / ground-station visibility at Mars, relativistic clock drift between Earth and outer planets, Doppler shift on deep-space links, planetary shadow, local relay handoff) and say whether each would change a pre-funded settlement guarantee.

## Resolution (2026-10-03)

Findings: [docs/research/deployment-effects.md](../../docs/research/deployment-effects.md). None of the five effects threatens solvency (all obligations fully locked before commit). Two need protocol rules, not collateral: (1) solar conjunction — real NASA Mars blackout ~2 weeks vs ~41 days under the baseline 0.10 AU sphere (baseline is conservative); needs a fallback for the Ceres print and for locks during blackout; (2) clock drift — Mars clocks gain ~477.6 µs/day vs Earth (Ashby & Patla 2025), ~174 ms/yr unsynced; all deadlines must be stated in one reference timescale (TDB). Rotation (~12.3 h/sol hidden for a single Mars station), Doppler (v/c ~1e-4) and Shapiro delay (~124 µs) are timing-only. Several magnitudes are derived (marked in the file).
