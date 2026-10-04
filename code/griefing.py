"""Griefing bound (S2 extension): a seller posts a firm offer and withdraws it after a buyer's LOCK is on its way.
The decider declines (reason 1); the buyer's cash stays locked until the DECLINE arrives. Measured on the VM run:
the offer holder withdraws locally at h 0.5 (after the LOCK leaves, before it arrives). Also the same from Uranus, and
for the Ceres Iron future (the long side's margin). Output: code/out/griefing.json, latex/generated/griefing_macros.tex"""
import json
from pathlib import Path

import scenarios as sc

OUT = Path(__file__).resolve().parent / "out"
GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"


def run(name, withdraw_at):
    w = sc.make(name)
    sim = w.sim
    decider = "Neptune" if name.startswith("VM") else "Ceres"
    oid, owner, asset = ("O-1", "Triton Fund", "ARES") if name.startswith("VM") else ("O-F", "Ceres Iron Works", "USD")

    def withdraw(t):
        off = w.apps[decider].offers[oid]
        off["state"] = "withdrawn"
        sim.book(t, lambda L: L.unencumber(decider, owner, asset, off["tag"]))
    sim.at(withdraw_at, withdraw)
    sim.run(until=500.0)
    L = sim.ledger
    holder = next(a for n, a in w.apps.items() if n != decider)
    lk = next(iter(holder.locks.values()))
    unlock = max(e["t"] for e in sim.log if e["what"] == "deliver" and "DECLINE" in str(e.get("label", "")))
    return dict(run=name, withdrawn_at=withdraw_at, state=lk["state"], unlocked_h=unlock,
                usd_hours=L.asset_hours["USD"], locked=(sc.VM_CASH if name.startswith("VM") else sc.MARGIN))


if __name__ == "__main__":
    rows = [run("VM", 0.5), run("VM@Uranus", 0.5), run("FR", 0.5)]
    for r in rows:
        print(r)
    (OUT / "griefing.json").write_text(json.dumps(rows, indent=1))
    M = {"GriefVMHours": f"{rows[0]['unlocked_h']:.1f}", "GriefVMDollarHours": f"{rows[0]['usd_hours']:,.0f}".replace(",", "{,}"),
         "GriefUranusHours": f"{rows[1]['unlocked_h']:.1f}", "GriefUranusDollarHours": f"{rows[1]['usd_hours']:,.0f}".replace(",", "{,}"),
         "GriefFutHours": f"{rows[2]['unlocked_h']:.1f}", "GriefFutDollarHours": f"{rows[2]['usd_hours']:,.0f}".replace(",", "{,}"),
         "GriefCap": "3"}
    bs = chr(92)
    (GEN / "griefing_macros.tex").write_text("".join(bs + "newcommand{" + bs + k + "}{" + v + "}" + chr(10) for k, v in M.items()))
