"""E1 evidence: epoch check, period/radius checks, later positions, moving-receiver light time.

Writes latex/generated/:
  e1_epoch_check.tex  computed vs brief epoch positions, period closure and radius bounds
  e1_later.tex        positions at h 288 and h 300 (the settling print and the S3 second snapshot)
  e1_lighttime.tex    forward vs return light time on the scenario links, moving vs frozen receiver
  e1_macros.tex       numbers used in prose
"""
from pathlib import Path

import numpy as np

from orbits import CHECK, ELEMENTS, LIGHT_H_PER_AU, RELAYS, SETTLEMENTS, light_time, position

GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"
B = "\\"


def tab(spec, head, rows):
    L = [B + "par" + B + "noindent", B + "begin{tabular}{" + spec + "}", B + "toprule", head + B + B, B + "midrule"]
    L += [r + B + B for r in rows]
    L += [B + "bottomrule", B + "end{tabular}" + B + "par"]
    return "\n".join(L) + "\n"


def iterate(sender, receiver, t_e, tol_h=1e-3 / 3600):
    """Fixed-point light-time solution, returning every iterate of t_a (h) so the convergence can be shown."""
    rs = position(sender, t_e)
    t_a = t_e + np.linalg.norm(position(receiver, t_e) - rs) * LIGHT_H_PER_AU
    out = [t_a]
    for _ in range(30):
        new = t_e + np.linalg.norm(position(receiver, t_a) - rs) * LIGHT_H_PER_AU
        out.append(new)
        if abs(new - t_a) < tol_h:
            break
        t_a = new
    return out


def main():
    M = {}
    # ---------- epoch check, period closure, radius bounds
    rows, worst, worst_close, worst_rad = [], 0.0, 0.0, 0.0
    for b, ref in CHECK.items():
        p = position(b, 0.0)
        err = float(np.max(np.abs(p - np.array(ref))))
        worst = max(worst, err)
        el = ELEMENTS[b]
        P_h = el["period_days"] * 24
        close = float(np.linalg.norm(position(b, P_h) - p))
        worst_close = max(worst_close, close)
        r = np.linalg.norm(position(b, np.linspace(0, P_h, 20001)), axis=1)
        lo, hi = el["a_au"] * (1 - el["e"]), el["a_au"] * (1 + el["e"])
        worst_rad = max(worst_rad, lo - r.min(), r.max() - hi, 0.0)
        rows.append(" & ".join([b, f"{p[0]:+.6f}", f"{p[1]:+.6f}", f"{p[2]:+.6f}", f"{err:.1e}",
                                f"{el['period_days']:,.1f}".replace(",", "{,}"), f"{close:.0e}",
                                f"{r.min():.4f}--{r.max():.4f}", f"{lo:.4f}--{hi:.4f}"]))
    (GEN / "e1_epoch_check.tex").write_text(tab(
        "lrrrrrrcc", "Body & $x$ & $y$ & $z$ (AU) & $|\\Delta|_{\\max}$ & period d & $|r(P)-r(0)|$ & "
        "$|r|$ over one period & $a(1\\mp e)$", rows))
    M["EoneWorstErr"] = f"{worst:.1e}"
    M["EoneWorstClose"] = f"{worst_close:.0e}"
    M["EoneRadSlack"] = f"{worst_rad:.0e}"

    # ---------- later positions
    rows = []
    for b in CHECK:
        p, q = position(b, 288.0), position(b, 300.0)
        rows.append(" & ".join([b] + [f"{v:+.6f}" for v in p] + [f"{v:+.6f}" for v in q]))
    (GEN / "e1_later.tex").write_text(tab(
        "lrrrrrr", "Body & \\multicolumn{3}{c}{h 288 (settling print), AU} & \\multicolumn{3}{c}{h 300 (S3 snapshot), AU}",
        rows))

    # ---------- forward and return on the scenario hops, moving vs frozen receiver
    legs = [  # launch times from the VM and FR no-loss traces
        ("VM LOCK", "Earth", "Relay A", 0.0006), ("VM LOCK", "Relay A", "Neptune", 0.3138),
        ("VM COMMIT", "Neptune", "Relay A", 4.1756), ("VM COMMIT", "Relay A", "Earth", 8.0378),
        ("FR LOCK", "Jupiter", "Relay B", 0.0006), ("FR LOCK", "Relay B", "Ceres", 0.3470),
        ("FR COMMIT", "Ceres", "Relay B", 0.6891), ("FR COMMIT", "Relay B", "Jupiter", 1.0313),
    ]
    rows = []
    for lab, s, r, te in legs:
        ta, d, _ = light_time(s, r, te)
        ta, d = float(ta), float(d)
        frozen = float(np.linalg.norm(position(r, te) - position(s, te))) * LIGHT_H_PER_AU
        rows.append(" & ".join([lab, (s + " $" + B + "to$ " + r).replace("Relay ", ""), f"{te:.4f}", f"{d:.5f}",
                                f"{(ta - te) * 60:.3f}", f"{((ta - te) - frozen) * 3600:+.2f}", f"{ta:.4f}"]))
    (GEN / "e1_lighttime.tex").write_text(tab(
        "llrrrrr", "Message & hop & $t_e$ (h) & $d$ (AU) & flight (min) & receiver motion (s) & $t_a$ (h)", rows))

    # ---------- worked example: scan every ordered pair, h 0..2000 hourly, for the largest receiver-motion effect,
    # then solve that leg (forward) and the reverse leg emitted at the same instant (return) step by step.
    names, ts, best = SETTLEMENTS + RELAYS, np.arange(0, 2000, 1.0), (0.0, None)
    for s_ in names:
        for r_ in names:
            if s_ == r_:
                continue
            ta_, _, _ = light_time(s_, r_, ts)
            fr_ = np.linalg.norm(position(r_, ts) - position(s_, ts), axis=1) * LIGHT_H_PER_AU
            sh = np.abs((ta_ - ts) - fr_) * 3600
            i = int(np.argmax(sh))
            best = max(best, (float(sh[i]), (s_, r_, float(ts[i]))))
    s_, r_, te = best[1]
    fw, rv = iterate(s_, r_, te), iterate(r_, s_, te)
    frozen = float(np.linalg.norm(position(r_, te) - position(s_, te))) * LIGHT_H_PER_AU
    vrx = (position(r_, te + 1 / 3600) - position(r_, te)) * 3600  # AU/h
    los = (position(r_, te) - position(s_, te)) / np.linalg.norm(position(r_, te) - position(s_, te))
    M.update({
        "EoneExSender": s_, "EoneExReceiver": r_, "EoneExTe": f"{te:,.0f}".replace(",", "{,}"),
        "EoneFrozenMin": f"{frozen * 60:.4f}",
        "EoneFwdMin": f"{(fw[-1] - te) * 60:.4f}", "EoneRevMin": f"{(rv[-1] - te) * 60:.4f}",
        "EoneFwdShiftS": f"{((fw[-1] - te) - frozen) * 3600:+.2f}",
        "EoneRevShiftS": f"{((rv[-1] - te) - frozen) * 3600:+.2f}",
        "EoneAsymS": f"{abs(fw[-1] - rv[-1]) * 3600:.2f}",
        "EoneRxRadialKms": f"{float(np.dot(vrx, los)) * 149597870.7 / 3600:+.1f}",
        "EoneFwdIters": str(len(fw)), "EoneRevIters": str(len(rv)),
    })
    for k, x in enumerate(fw[:4]):
        M["EoneIt" + "ABCD"[k]] = f"{(x - te) * 60:.5f}"
    (GEN / "e1_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    for k, v in M.items():
        print(k, v)


if __name__ == "__main__":
    main()
