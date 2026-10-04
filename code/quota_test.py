"""Quota-exhaustion test (S2 extension; makes rule R18 and the recovery reserve R14 bind).

Setup: Earth Branch's quota slice is shrunk from 66 to S packets per rolling 24 h. 40 clients' worth of demand (40 firm
offers of 25 Ares at $125 at Neptune, all accepted by Terra at h 0 as fast as Earth Branch allows) floods the slice while
Neptune is isolated h 1--73, so every admitted lock must also resubmit.
  with the reserve   new locks may use at most S - 10 packets per 24 h; resubmissions may use all S (R14, R18)
  without the reserve  new locks and resubmissions both draw on S (the ablation: what the reserve prevents)
A new lock that cannot be sent is queued locally (nothing is locked); one whose remaining offer life falls below R5 when it
reaches the front is refused. Output: code/out/quota_test.json and latex/generated/quota_test.tex
Run: python code/quota_test.py
"""
import json
from pathlib import Path

import scenarios as sc
from sim import SEC, Incident

OUT = Path(__file__).resolve().parent / "out"
GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"
B = "\\"
N_OFFERS, SHARES, PRICE, EXPIRY, RESERVE = 40, 25, 125, 96.0, 10


def run(S, reserve):
    w = sc.World("Q", incident=Incident("isolation", "Neptune", 1.0, 72.0))
    sim = w.sim
    E, N = "Earth", "Neptune"
    w.apps = {E: sc.Branch(w, E), N: sc.Branch(w, N)}
    sim.apps = w.apps
    w.open(E, N, 24.0)
    B_, S_ = w.apps[E], w.apps[N]
    st = dict(admitted=[], refused=0, queued=0, blocked_resub=0, pk=[])

    def used(t):
        return sum(1 for (tt, br, _) in sim.originated if br == E and t - 24 < tt <= t)

    # the resubmission gate: a packet is sent only if Earth's slice has room (the reserve is what keeps room)
    orig_resub = B_._resub

    def resub(t, deal, why):
        if used(t) >= S:
            st["blocked_resub"] += 1
            return
        orig_resub(t, deal, why)
    B_._resub = resub

    def post(t, i):
        oid = f"O-{i}"
        assert sim.book(t, lambda L: L.encumber(N, "Triton Fund", "ARES", SHARES, oid))
        S_.offers[oid] = dict(owner="Triton Fund", shares=SHARES, price=PRICE, expiry=EXPIRY, state="open", tag=oid)

    queue = list(range(N_OFFERS))

    def pump(t):
        """Admit as many queued locks as the slice allows (one batched packet per 14), queue the rest."""
        budget = S - reserve if reserve else S
        recs = []
        while queue:
            new = [a for a in st["admitted"] if t - 24 < a <= t]
            n_pk = sum(1 for tt in st["pk"] if t - 24 < tt <= t) + -(-len(recs) // 14)    # packets this window
            if (len(recs) % 14 == 0 and n_pk >= budget) or (len(recs) % 14 == 0 and used(t) + -(-len(recs) // 14) >= S):
                break
            i = queue[0]
            if not w.offer_life_ok(E, N, t, EXPIRY):
                st["refused"] += 1                            # R5: not enough offer life left, nothing locked
                queue.pop(0)
                continue
            queue.pop(0)
            deal = w.next_deal(E)
            cash = SHARES * PRICE
            assert sim.book(t, lambda L: L.encumber(E, "Terra Capital", "USD", cash, deal))
            B_.locks[deal] = dict(state="locked", t=t)
            rec = dict(type="LOCK", product="share", side="buy", deal=deal, offer=f"O-{i}", shares=SHARES, price=PRICE,
                       cash=cash, buyer="Terra Capital", seller_branch=N)
            st["admitted"].append(t)
            recs.append(rec)
        for k in range(0, len(recs), 14):
            st["pk"].append(t)
            chunk = recs[k:k + 14]
            w.send(t, E, N, chunk, f"LOCK {chunk[0]['deal']}+{len(chunk) - 1}", know="flood", action="Locks and sends",
                   state="")
            for r in chunk:
                B_.arm(t, r["deal"], N, r)
        if queue:
            pk = [tt for tt in st["pk"] if t - 24 < tt <= t]
            st["queued"] = len(queue)
            sim.at(min(pk) + 24.0 + SEC if pk else t + 1.0, pump)

    for i in range(N_OFFERS):
        sim.at(SEC, post, i)
    sim.at(2 * SEC, pump)
    sim.run(until=3000.0)
    L = sim.ledger
    open_locks = sum(1 for lk in B_.locks.values() if lk["state"] in ("locked", "pledged"))
    done = [lk for lk in B_.locks.values() if lk["state"] != "locked"]
    last_close = max(sim.log_times) if hasattr(sim, "log_times") else None
    peak = sim.quota_peaks()[1].get(E, 0)
    t_end = max((e["t"] for e in sim.log if e["what"] in ("deliver",) and "COMMIT" in str(e.get("label", ""))), default=None)
    return dict(S=S, reserve=reserve, admitted=len(st["admitted"]), queued_events=st["queued"], refused_r5=st["refused"],
                blocked_resub=st["blocked_resub"], open_at_end=open_locks, peak_earth_24h=peak,
                last_commit_h=t_end, checks=L.checks)


if __name__ == "__main__":
    rows = []
    for S in (12, 11):
        for reserve in (RESERVE, 0):
            r = run(S, reserve)
            rows.append(r)
            print(r, flush=True)
    (OUT / "quota_test.json").write_text(json.dumps(rows, indent=1))
    L = [B + "begin{tabular}{rrrrrrr}", B + "toprule",
         "$S$ & reserve & admitted & refused & deferred probes & peak 24 h & last COMMIT" + B + B,
         B + "midrule"]
    for r in rows:
        L.append(f"{r['S']} & {r['reserve']} & {r['admitted']} & {N_OFFERS - r['admitted']} & {r['blocked_resub']} & "
                 f"{r['peak_earth_24h']} & {r['last_commit_h']:.1f}" + B + B if r["last_commit_h"] else
                 f"{r['S']} & {r['reserve']} & {r['admitted']} & {N_OFFERS - r['admitted']} & {r['blocked_resub']} & "
                 f"{r['peak_earth_24h']} & ---" + B + B)
    L += [B + "bottomrule", B + "end{tabular}"]
    (GEN / "quota_test.tex").write_text("\n".join(L) + "\n")
