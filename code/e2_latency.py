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


def deliver(route, t0, m=1.0, ke=1.0):
    """Delivery delay (h) after enqueue at t0, or inf if all 4 endpoint attempts fail; plus the no-loss delay."""
    H = hops(route, t0)
    T0 = sum(f for f, _, _ in H) + SEC * (2 * len(H))
    Re = ke * (2 * T0 + 24.0)
    best = np.full(N, np.inf)
    for j in range(4):
        t = np.full(N, j * Re + T0)
        ok = np.ones(N, bool)
        for f, p, Rh in H:
            fails = rng.geometric((1 - p) ** m, N) - 1        # failed launches before the first success
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


PCT = lambda x: ">99.99" if x > 0.99995 else f"{100 * x:.1f}" if x < 0.9995 else f"{100 * x:.2f}"
RELAY = lambda frm: "Relay B" if frm == "Jupiter" else "Relay A"
ORDER = ["Mercury", "Venus", "Earth", "Mars", "Ceres", "Jupiter", "Saturn", "Uranus", "Neptune"]
CI95 = 1.96 * 0.5 / N ** 0.5 * 100            # worst-case 95% half-width in percentage points


def dvp(frm, to, m=1.0, ke=1.0, expiry=96.0):
    """Share DvP initiated at `frm` against a firm offer at `to`: (trade-complete times, no-loss time, decline mask)."""
    L, T0f = deliver([frm, "Relay A", to], 0.0003, m, ke)
    arrive = 0.0003 + L
    ok = arrive < expiry
    C, T0r = deliver([to, "Relay A", frm], 4.2, m, ke)
    return np.where(ok, arrive + C, np.inf), 0.0003 + T0f + T0r, ~ok


def future(frm, m=1.0, ke=1.0):
    S, T0s = deliver(["Ceres", RELAY(frm), frm], 288.0003, m, ke)
    return 288.0003 + S, 288.0003 + T0s


def table(head, rows, cols):
    L_ = [B + "par" + B + "noindent", B + "begin{tabular}{" + cols + "}", B + "toprule", head + B + B, B + "midrule"]
    return "\n".join(L_ + [r + B + B for r in rows] + [B + "bottomrule", B + "end{tabular}" + B + "par"]) + "\n"


def main():
    M, rows = {}, []
    # ---- nine settlements: share DvP with Neptune (Neptune itself trades with Earth) and the Ceres Iron future
    for frm in ORDER:
        cells = [frm]
        if frm == "Ceres":
            cells += ["local"] * 4
        else:
            to = "Earth" if frm == "Neptune" else "Neptune"
            done, nominal, dec = dvp(frm, to)
            cells += [f"{nominal:.2f}", PCT(np.mean(done <= nominal + 1e-6)), PCT(np.mean(done <= nominal + 24)),
                      PCT(np.mean(done <= nominal + 48))]
            M["EtwoDvP" + frm + "NoLoss"] = PCT(np.mean(done <= nominal + 1e-6))
            M["EtwoDvP" + frm + "Day"] = PCT(np.mean(done <= nominal + 24))
            M["EtwoDvP" + frm + "Decline"] = f"{100 * np.mean(dec):.2f}"
        if frm == "Ceres":
            cells += ["local"] * 3
        else:
            settled, nominal = future(frm)
            cells += [PCT(np.mean(settled <= nominal + 1e-6)), PCT(np.mean(settled <= nominal + 6)),
                      PCT(np.mean(settled <= nominal + 24))]
            M["EtwoFut" + frm + "NoLoss"] = PCT(np.mean(settled <= nominal + 1e-6))
            M["EtwoFut" + frm + "Day"] = PCT(np.mean(settled <= nominal + 24))
        rows.append(" & ".join(cells))
    head = (" & " + B + "multicolumn{4}{c}{Share DvP, " + B + "% complete by} & " + B + "multicolumn{3}{c}{Ceres Iron future, "
            + B + "% spendable by} " + B + B + "\n" + B + "cmidrule(lr){2-5}" + B + "cmidrule(lr){6-8}\n"
            "Settlement & no-loss h & no-loss & +24 h & +48 h & no-loss & +6 h & +24 h")
    (GEN / "e2_latency.tex").write_text(table(head, rows, "lrrrrrrr"))

    # ---- the traced Earth / Uranus value moves in full (median, 99th percentile)
    full = []
    for name, frm in [("VM Earth", "Earth"), ("VM@Uranus", "Uranus")]:
        done, nominal, dec = dvp(frm, "Neptune")
        marks = [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]
        full.append(row(name + " trade complete", done, nominal, marks))
        key = "Earth" if frm == "Earth" else "Uranus"
        M[f"EtwoVM{key}NoLoss"] = f"{100 * np.mean(done <= nominal + 1e-6):.1f}"
        M[f"EtwoVM{key}Decline"] = f"{100 * np.mean(dec):.2f}"
        L, _ = deliver([frm, "Relay A", "Neptune"], 0.0003)
        arrive = 0.0003 + L
        for life, word in ((24.0, "TwentyFour"), (48.0, "FortyEight")):
            M[f"EtwoVM{key}Decline{word}"] = f"{100 * np.mean(arrive >= life):.2f}"
        M[f"EtwoVM{key}Day"] = f"{100 * np.mean(done <= nominal + 24):.2f}"
    L, T0f = deliver(["Jupiter", "Relay B", "Ceres"], 0.0003)
    C, T0r = deliver(["Ceres", "Relay B", "Jupiter"], 0.69)
    opened, nominal = 0.0003 + L + C, 0.0003 + T0f + T0r
    full.append(row("Future: open known at Jupiter", opened, nominal,
                    [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]))
    settled, nominal = future("Jupiter")
    full.append(row("Future: settlement spendable", settled, nominal,
                    [nominal + 1e-6, nominal + 6, nominal + 24, nominal + 48]))
    M["EtwoSettleNoLoss"] = f"{100 * np.mean(settled <= nominal + 1e-6):.1f}"
    M["EtwoSettleSixH"] = f"{100 * np.mean(settled <= nominal + 6):.2f}"
    head2 = (" & & " + B + "multicolumn{4}{c}{" + B + "% complete by} & & " + B + B + "\n" + B + "cmidrule(lr){3-6}\n" +
             "Event & no-loss h & no-loss & +6 h & +24 h & +48 h & median h & 99th pct h")
    (GEN / "e2_latency_detail.tex").write_text(table(head2, full, "lrrrrrrr"))

    # ---- sensitivity: loss multiplier m (loss law 1 - exp(-0.02 m d) on every launch) and R_e factor
    sw = []
    for label, m, ke in [(f"loss {B}times{m}", m, 1.0) for m in (0.5, 1.0, 2.0, 4.0)] + \
                        [(f"$R_e$ {B}times{ke}", 1.0, ke) for ke in (0.5, 2.0)]:
        label = label.replace(B + "times", "$" + B + "times$ ").replace("$$", "$")
        e, ne, de = dvp("Earth", "Neptune", m=m, ke=ke)
        u, nu, du = dvp("Uranus", "Neptune", m=m, ke=ke)
        st, ns = future("Uranus", m=m, ke=ke)
        sw.append(" & ".join([label, PCT(np.mean(e <= ne + 1e-6)), PCT(np.mean(e <= ne + 24)),
                              f"{100 * np.mean(de):.2f}", PCT(np.mean(u <= nu + 24)), f"{100 * np.mean(du):.2f}",
                              PCT(np.mean(st <= ns + 6)), PCT(np.mean(st <= ns + 24))]))
        if ke == 1.0:
            k = {0.5: "Half", 1.0: "One", 2.0: "Two", 4.0: "Four"}[m]
            M[f"EtwoSweepLoss{k}Day"] = PCT(np.mean(e <= ne + 24))
            M[f"EtwoSweepLoss{k}Decline"] = f"{100 * np.mean(de):.2f}"
            M[f"EtwoSweepLoss{k}UranusDecline"] = f"{100 * np.mean(du):.2f}"
            M[f"EtwoSweepLoss{k}FutDay"] = PCT(np.mean(st <= ns + 24))
    head3 = (" & " + B + "multicolumn{3}{c}{Earth DvP, " + B + "%} & " + B + "multicolumn{2}{c}{Uranus DvP, " + B + "%} & "
             + B + "multicolumn{2}{c}{Uranus future, " + B + "%} " + B + B + "\n" + B + "cmidrule(lr){2-4}" + B +
             "cmidrule(lr){5-6}" + B + "cmidrule(lr){7-8}\n"
             "Change & no-loss & $" + B + "le$ +24 h & declined & $" + B + "le$ +24 h & declined & $" + B +
             "le$ +6 h & $" + B + "le$ +24 h")
    (GEN / "e2_sweep.tex").write_text(table(head3, sw, "lrrrrrrr"))
    M["EtwoN"] = "1{,}000{,}000"
    M["EtwoSeed"] = "20261003"
    M["EtwoCI"] = f"{CI95:.2f}"
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
    (GEN / "e2_latency_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    print("\n".join(rows))
    print()
    print("\n".join(full))
    print()
    print("\n".join(sw))
    for k, v in M.items():
        if "Life" not in k and "Latest" not in k:
            print(k, v)


if __name__ == "__main__":
    main()
