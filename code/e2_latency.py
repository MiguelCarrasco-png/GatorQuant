"""E2 evidence: completion-time distribution under random backbone loss (no incident), by Monte Carlo.

Model, per data packet on a pinned route (geometry frozen at the traced launch times, which moves T0 by < 1 s):
  hop k launches until one arrives, at most 4; each failed launch adds R_h = 2 x flight + 60 min (brief s.5);
  4 failures abandon the endpoint attempt. Endpoint attempt j (j = 0..3) is enqueued at j x R_e, R_e = 2 T0 + 24 h;
  the packet is delivered at the earliest arrival over attempts (later copies are duplicates). Every launch is an
  independent trial with p = 1 - exp(-0.02 d) (no incident shares a window). Hop receipts that are lost cause extra
  launches but never delay the first delivery, so they are left out. Serialization and relay processing are in T0.
Deal logic: VM commits on the LOCK's first arrival if it is before the offer expiry (h 96), else declines (R7);
the trade completes when the COMMIT arrives. Futures: open when COMMIT reaches Jupiter; settlement spendable at
Jupiter when SETTLE arrives (from the h 288 print). If all 4 attempts of a reply fail, the pull rule (R8) resends
at print/expected reply + R_e; we count those cases in the tail bucket.

Writes latex/generated/e2_latency.tex and e2_latency_macros.tex.
"""
from pathlib import Path

import numpy as np

from orbits import light_time

GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"
B = "\\"
N = 1_000_000
SEC = 1 / 3600
rng = np.random.default_rng(20261003)


def hops(route, t0):
    """(flight h, loss p, R_h h) per hop at the traced launch time, chaining arrival times along the route."""
    out, t = [], t0 + SEC
    for a, b in zip(route[:-1], route[1:]):
        ta, d, _ = light_time(a, b, t)
        f = float(ta) - t
        out.append((f, 1 - np.exp(-0.02 * float(d)), 2 * f + 1.0))
        t = float(ta) + 2 * SEC
    return out


def deliver(route, t0):
    """Delivery delay (h) after enqueue at t0, or inf if all 4 endpoint attempts fail; plus the no-loss delay."""
    H = hops(route, t0)
    T0 = sum(f for f, _, _ in H) + SEC * (2 * len(H))
    Re = 2 * T0 + 24.0
    best = np.full(N, np.inf)
    for j in range(4):
        t = np.full(N, j * Re + T0)
        ok = np.ones(N, bool)
        for f, p, Rh in H:
            fails = rng.geometric(1 - p, N) - 1        # failed launches before the first success
            ok &= fails < 4
            t += np.minimum(fails, 3) * Rh
        best = np.minimum(best, np.where(ok, t, np.inf))
    return best, T0


def min_life(route, t):
    """R5: shortest remote-offer life an initiator may accept, R_e + T0 + 3 sum(R_h), at time t."""
    H = hops(route, t)
    T0 = sum(f for f, _, _ in H) + SEC * (2 * len(H))
    return 2 * T0 + 24.0 + T0 + 3 * sum(rh for _, _, rh in H)


def row(name, t, nominal, marks):
    cells = [name, f"{nominal:.2f}"] + [f"{100 * np.mean(t <= m):.1f}" for m in marks]
    fin = t[np.isfinite(t)]
    cells += [f"{np.median(fin):.2f}", f"{np.quantile(t, 0.99):.1f}" if np.isfinite(np.quantile(t, 0.99)) else "---"]
    return " & ".join(cells)


def main():
    M, rows = {}, []
    marks_label = ["no-loss", "+6 h", "+24 h", "+48 h"]
    # value moves: Branch X -> A -> Neptune and back; offer expiry h 48
    for name, frm, lock_t in [("VM Earth", "Earth", 0.0003), ("VM@Uranus", "Uranus", 0.0003)]:
        L, T0f = deliver([frm, "Relay A", "Neptune"], lock_t)
        arrive = lock_t + L
        commit_ok = arrive < 96.0
        C, T0r = deliver(["Neptune", "Relay A", frm], 4.2)
        done = np.where(commit_ok, arrive + C, np.inf)
        nominal = lock_t + T0f + T0r
        marks = [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]
        rows.append(row(name + " trade complete", done, nominal, marks))
        key = "Earth" if frm == "Earth" else "Uranus"
        M[f"EtwoVM{key}NoLoss"] = f"{100 * np.mean(done <= nominal + 1e-6):.1f}"
        M[f"EtwoVM{key}Decline"] = f"{100 * np.mean(~commit_ok):.2f}"
        # sensitivity: the same LOCK deliveries against shorter offer lives (24 h, 48 h) than R5 allows
        for life, word in ((24.0, "TwentyFour"), (48.0, "FortyEight")):
            M[f"EtwoVM{key}Decline{word}"] = f"{100 * np.mean(arrive >= life):.2f}"
        M[f"EtwoVM{key}Day"] = f"{100 * np.mean(done <= nominal + 24):.2f}"
    # future: open (LOCK Jupiter -> B -> Ceres, COMMIT back), settlement (SETTLE Ceres -> B -> Jupiter after h 288)
    L, T0f = deliver(["Jupiter", "Relay B", "Ceres"], 0.0003)
    C, T0r = deliver(["Ceres", "Relay B", "Jupiter"], 0.69)
    opened = 0.0003 + L + C
    nominal = 0.0003 + T0f + T0r
    rows.append(row("Future: open known at Jupiter", opened, nominal,
                    [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]))
    S, T0s = deliver(["Ceres", "Relay B", "Jupiter"], 288.0003)
    settled = 288.0003 + S
    nominal = 288.0003 + T0s
    rows.append(row("Future: settlement spendable", settled, nominal,
                    [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]))
    M["EtwoSettleNoLoss"] = f"{100 * np.mean(settled <= nominal + 1e-6):.1f}"
    M["EtwoSettleSixH"] = f"{100 * np.mean(settled <= nominal + 6):.2f}"
    # R5 minimum offer life at h 0 from every settlement, to the referee (Ceres) and to Neptune (VM counterparty)
    from orbits import SETTLEMENTS
    for frm in SETTLEMENTS:
        if frm != "Ceres":
            relay = "Relay B" if frm == "Jupiter" else "Relay A"
            life = min_life([frm, relay, "Ceres"], 0.0)
            M["EtwoLife" + frm + "Ceres"] = f"{life:.0f}"
            M["EtwoLatest" + frm] = f"{264 - life:.0f}"
        if frm != "Neptune":
            M["EtwoLife" + frm + "Neptune"] = f"{min_life([frm, 'Relay A', 'Neptune'], 0.0):.0f}"
    head = (" & & " + B + "multicolumn{4}{c}{" + B + "% complete by} & & " + B + B + "\n" + B + "cmidrule(lr){3-6}\n" +
            "Event & no-loss h & no-loss & +6 h & +24 h & +48 h & median h & 99th pct h")
    L_ = [B + "par" + B + "noindent", B + "begin{tabular}{lrrrrrrr}", B + "toprule", head + B + B, B + "midrule"]
    L_ += [r + B + B for r in rows] + [B + "bottomrule", B + "end{tabular}" + B + "par"]
    (GEN / "e2_latency.tex").write_text("\n".join(L_) + "\n")
    (GEN / "e2_latency_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    print("\n".join(rows))
    for k, v in M.items():
        print(k, v)


if __name__ == "__main__":
    main()
