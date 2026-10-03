---
title: Cross-planet value-move protocol — messages, states, loss handling
type: grilling
status: open
assignee:
blocked_by: []
---

## Question

Pin down the exact lock → commit → release procedure between two Branches: message types and fields (fit in 960-byte payloads, batchable), ledger states for every asset (free / locked / owed-to-Branch / released), what each actor knows/does/owes when a message is lost, delayed, duplicated or contradicted, idempotent resubmission rules after transport gives "status unknown", and when a counterparty Branch may decline. Also: how the Ceres referee pulls the Jupiter long's margin (pledge-at-home vs move-to-Ceres).
