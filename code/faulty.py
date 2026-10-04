"""Faulty-Branch test (S2 extension, rule R20). The brief assumes Branches follow the rules; a Branch that breaks them is an
optional extension. We inject four faults as records that arrive at the lock holder, and run each with R20 (echo check +
SETTLE recompute) on and off, so the table shows what the rule detects and what it prevents.

  F1  double decision    the deciding Branch committed, then sends a DECLINE for the same deal
  F2  forged SETTLE      the referee sends a SETTLE whose amount differs from the payoff of its own settling print
  F3  unmatched COMMIT   a COMMIT whose echoed terms differ from the LOCK (cash $24,000 not $25,000)
  F4  withheld decision  the deciding Branch records its decision and never sends it (and never answers a resubmission)

Output: code/out/faulty.json. Run: python code/faulty.py
"""
import json
from pathlib import Path

import scenarios as sc
from fuzz import P

OUT = Path(__file__).resolve().parent / "out"
OWNERS = ("Terra Capital", "Triton Fund", "Callisto Foundry", "Ceres Iron Works")


def totals(L):
    out = {}
    for o in OWNERS:
        out[o] = {a: sum(ln["bal"] for b in L.lines.values() for (ow, aa, k), ln in b.items() if ow == o and aa == a)
                  for a in ("USD", "ARES")}
    return out


def run(fault, audit):
    sc.AUDIT_ON = audit
    prod = "VM" if fault in ("F1", "F3") else "FF"
    w = sc.make(prod)
    sim = w.sim
    holder, decider = ("Earth", "Neptune") if prod == "VM" else ("Jupiter", "Ceres")
    deal = None

    def inject(t, rec):
        s = sim.sessions[(decider, holder)]
        w.apps[holder].on_records(sim, t, s, P([rec]))
    if fault == "F1":
        def go(t):
            lk = w.apps[holder].locks
            d = next(iter(lk))
            if lk[d]["state"] == "released":
                inject(t, dict(w.apps[decider].decisions[d], type="DECLINE", reason=1))
            else:
                sim.at(t + 1.0, go)
        sim.at(1.0, go)
    elif fault == "F2":
        def go(t):
            d = next(iter(w.apps[holder].locks))
            if w.apps[holder].locks[d]["state"] == "pledged":
                true = w.apps[decider].decisions.get(d)
                if true and true["type"] == "SETTLE":
                    inject(t, dict(true, release=70_000.0, credit=0.0))
                    return
            if w.apps[holder].locks[d]["state"] == "pledged":
                sim.at(t + 0.05, go)
        sim.at(288.01, go)
    elif fault == "F3":
        def go(t):
            d = next(iter(w.apps[holder].locks))
            lk = w.apps[holder].locks[d]
            if lk["state"] == "locked":
                inject(t, dict(lk["rec"], type="COMMIT", cash=24_000, time=t))
        sim.at(1.5, go)
    elif fault == "F4":
        osend = w.send

        def send(t, frm, to, records, label, **kw):
            if frm == decider and records and records[0]["type"] in ("COMMIT", "DECLINE", "SETTLE"):
                return None
            return osend(t, frm, to, records, label, **kw)
        w.send = send
    base = None
    res = dict(fault=fault, audit=audit, product=prod)
    horizon = 2000.0 if fault == "F4" else 800.0
    try:
        sim.run(until=horizon)
        L = sim.ledger
        errs = [e for a in w.apps.values() for e in a.errors]
        res["detected"] = [e[2] for e in errs]
        res["locks"] = {d: lk["state"] for a in w.apps.values() for d, lk in a.locks.items()}
        res["totals"] = totals(L)
        res["invariants"] = "hold"
        for x in sc.BRANCHES:
            for a in ("USD", "ARES"):
                claims = sum(ln["bal"] for (o, aa, k), ln in L.lines[x].items() if k == "claim" and aa == a)
                held = sum(ln["bal"] for y, lines in L.lines.items() if y != x
                           for (o, aa, k), ln in lines.items() if o == f"{x} Branch" and aa == a and k == "own")
                pend = sum(p["amount"] for p in L.pending.values() if p["creditor"] == x and p["asset"] == a)
                if abs(claims - held - pend) > 1e-6:
                    res["invariants"] = f"BROKEN: {x} {a} claims {claims:,.0f} vs backing {held:,.0f}"
        enc = L.encumbered()
        res["still_encumbered"] = enc
        res["locked_usd_hours"] = L.asset_hours["USD"] if (L.advance(horizon) or True) else 0
    except AssertionError as e:
        res["invariants"] = "BROKEN (check failed): " + str(e)[:120]
        res["detected"] = [e2[2] for a in w.apps.values() for e2 in a.errors]
    return res


if __name__ == "__main__":
    honest = {}
    for prod in ("VM", "FF"):
        sc.AUDIT_ON = True
        w = sc.make(prod)
        w.sim.run(until=800.0)
        honest[prod] = totals(w.sim.ledger)
    rows = []
    for f in ("F1", "F2", "F3", "F4"):
        for audit in (True, False):
            r = run(f, audit)
            ref = honest[r["product"]]
            if "totals" in r:
                r["client_delta"] = {o: {a: r["totals"][o][a] - ref[o][a] for a in ("USD", "ARES")} for o in OWNERS
                                     if any(abs(r["totals"][o][a] - ref[o][a]) > 1e-6 for a in ("USD", "ARES"))}
            rows.append(r)
            print(f, "R20 on " if audit else "R20 off", r["invariants"], "| detected:", r.get("detected"),
                  "| client delta vs honest:", r.get("client_delta"), "| locks:", r.get("locks"), flush=True)
    sc.AUDIT_ON = True
    (OUT / "faulty.json").write_text(json.dumps(rows, indent=1, default=str))
