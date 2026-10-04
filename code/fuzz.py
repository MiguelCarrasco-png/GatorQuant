"""Fault-injection fuzzer for the invariants (appendix S1, 'Invariant fuzzing').

Each run is one of the three products (VM, FR, FF) driven through the real simulator and Branch rules
(scenarios.py), with these injected, all seeded:
  * random launch loss (p in [0, 0.35], every launch incl. receipts)
  * duplicate delivery of a record batch (p up to 0.5, replayed up to 30 h later)
  * reordering: delivery of a batch to the application held back up to 30 h
  * a contradictory LOCK (same deal ID, altered terms) sent to the deciding Branch after it decided
  * 0-2 endpoint resets of either Branch at random hours
  * a crash right after ledger step k: the reply that follows the durable record is never sent and that Branch resets
    (k enumerated over every ledger step of the product in turn, plus random runs without a crash)
Checked after EVERY ledger step by the omniscient ledger (sim.Ledger.check): conservation, no unit in two uses, every
claim backed. Checked at the end of every run: every lock closed; exactly one decision per deal ID; the lock holder's
outcome agrees with the recorded decision; every Branch's claims equal its backing; nothing left encumbered.
A failing run prints its seed. Run: python code/fuzz.py [runs_per_product]  ->  code/out/fuzz.json
"""
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import scenarios as sc

OUT = Path(__file__).resolve().parent / "out"
PRODUCTS = ("VM", "FR", "FF")
HORIZON = 6000.0


class P:
    """A record batch handed straight to a Branch (injected copies)."""

    def __init__(self, records, label="injected"):
        self.records, self.label, self.row = records, label, None


def run_one(args):
    product, seed, crash_k = args
    rng = random.Random(f"{product}-{seed}")
    w = sc.make(product)
    sim = w.sim
    cnt = dict(loss=0, dup=0, reorder=0, contradiction=0, reset=0, crash=0, launches=0, withdraw=0)
    p_loss = rng.uniform(0.0, 0.35)
    p_dup, p_reo = rng.uniform(0.0, 0.5), rng.uniform(0.0, 0.5)

    def loss(a, b, te):
        cnt["launches"] += 1
        if rng.random() < p_loss:
            cnt["loss"] += 1
            return True
        return False
    sim.loss = loss
    for node, app in w.apps.items():
        orig = app.on_records

        def on_records(sim_, t, s, pkt, orig=orig):
            if rng.random() < p_reo:
                cnt["reorder"] += 1
                sim_.at(t + rng.uniform(0.01, 30.0), lambda t2: orig(sim_, t2, s, pkt))
                return
            orig(sim_, t, s, pkt)
            if rng.random() < p_dup:
                cnt["dup"] += 1
                sim_.at(t + rng.uniform(0.001, 30.0), lambda t2: orig(sim_, t2, s, pkt))
        app.on_records = on_records
    nodes = ("Earth", "Neptune") if product == "VM" else ("Jupiter", "Ceres")
    end = w.end
    for _ in range(rng.choice((0, 0, 1, 2))):
        node, t = rng.choice(nodes), rng.uniform(0.0, end)
        cnt["reset"] += 1
        sim.at(t, lambda t_, n=node: w.reset(t_, n))
    decider = nodes[1]
    # the offer holder withdraws locally at a random hour (exercises DECLINE and the return of the lock)
    if rng.random() < 0.3:
        oid, own, asset = ("O-1", "Triton Fund", "ARES") if product == "VM" else ("O-F", "Ceres Iron Works", "USD")

        def withdraw(t):
            off = w.apps[decider].offers.get(oid)
            if off and off["state"] == "open":
                off["state"] = "withdrawn"
                sim.book(t, lambda L: L.unencumber(decider, own, asset, off["tag"]))
                cnt["withdraw"] += 1
        sim.at(rng.uniform(0.01, 12.0), withdraw)

    def contradict(t, tries=0):
        app = w.apps[decider]
        dealid = next(iter(app.decisions), None)
        if dealid is None:
            if tries < 40:
                sim.at(t + 3.0, contradict, tries + 1)
            return
        bad = dict(w.apps[nodes[0]].locks[dealid]["rec"], type="LOCK")
        for k in ("shares", "contracts"):
            if k in bad:
                bad[k] = bad[k] + 1
        key = "margin" if "margin" in bad else "cash"
        bad[key] = bad[key] + 1
        bad["flags"] = "RESUBMISSION"
        cnt["contradiction"] += 1
        s = sim.sessions[(nodes[0], decider)]
        app.on_records(sim, t, s, P([bad]))
    for _ in range(rng.choice((0, 1, 2))):
        sim.at(rng.uniform(0.5, end), contradict)
    if crash_k is not None:
        state = dict(n=0, pending=False)
        ob = sim.book

        def book(t, fn):
            r = ob(t, fn)
            state["n"] += 1
            if state["n"] == crash_k:
                state["pending"] = True
            return r
        sim.book = book
        osend = w.send

        def send(t, frm, to, records, label, **kw):
            if state["pending"] and records and records[0]["type"] in ("COMMIT", "DECLINE", "SETTLE"):
                state["pending"] = False
                cnt["crash"] += 1
                w.reset(t, frm)
                return None
            return osend(t, frm, to, records, label, **kw)
        w.send = send
    fail = None
    try:
        sim.run(until=HORIZON)
        L = sim.ledger
        for name, app in w.apps.items():
            for d, lk in app.locks.items():
                assert lk["state"] in ("released", "free", "settled"), f"lock {d} still {lk['state']}"
            for d, n in app.decided_n.items():
                assert n == 1, f"{name}: {n} decisions recorded for {d}"
        for name, app in w.apps.items():
            for d, lk in app.locks.items():
                dec = w.apps[decider].decisions[d]["type"]
                want = {"released": ("COMMIT",), "free": ("DECLINE",), "settled": ("COMMIT", "SETTLE")}[lk["state"]]
                assert dec in want, f"outcome {lk['state']} disagrees with recorded {dec}"
        for x in sc.BRANCHES:
            for a in ("USD", "ARES"):
                claims = sum(ln["bal"] for (o, aa, k), ln in L.lines[x].items() if k == "claim" and aa == a)
                held = sum(ln["bal"] for y, lines in L.lines.items() if y != x
                           for (o, aa, k), ln in lines.items() if o == f"{x} Branch" and aa == a and k == "own")
                assert abs(claims - held) < 1e-6, f"equity {x} {a}"
        assert not L.pending, "pending release left"
        assert all(v < 1e-9 for v in L.encumbered().values()), "still encumbered"
    except AssertionError as e:
        fail = str(e)
    except Exception as e:                                   # a crash of the simulator is also a finding
        fail = f"{type(e).__name__}: {e}"
    outcome = None
    for app in w.apps.values():
        for lk in app.locks.values():
            outcome = lk["state"]
    return dict(product=product, seed=seed, crash_k=crash_k, fail=fail, steps=sim.ledger.checks, outcome=outcome, **cnt)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    Ks = {"VM": 4, "FR": 5, "FF": 5}
    jobs = []
    for p in PRODUCTS:
        for i in range(n):
            ck = (i % (Ks[p] + 1)) or None                   # k = 1..K in turn, every (K+1)th run without a crash
            jobs.append((p, i, ck))
    res = []
    with Pool(8) as pool:
        for k, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            res.append(r)
            if r["fail"]:
                print("FAIL", r, flush=True)
            if k % 200 == 0:
                print(k, flush=True)
    summ = {}
    for p in PRODUCTS:
        rr = [r for r in res if r["product"] == p]
        summ[p] = dict(runs=len(rr), failures=sum(1 for r in rr if r["fail"]), ledger_steps=sum(r["steps"] for r in rr),
                       committed=sum(1 for r in rr if r["outcome"] in ("released", "settled")),
                       declined=sum(1 for r in rr if r["outcome"] == "free"),
                       **{k: sum(r[k] for r in rr) for k in ("launches", "loss", "dup", "reorder", "contradiction", "reset", "crash", "withdraw")})
    (OUT / "fuzz.json").write_text(json.dumps(dict(summary=summ, failures=[r for r in res if r["fail"]]), indent=1))
    print(json.dumps(summ, indent=1))
