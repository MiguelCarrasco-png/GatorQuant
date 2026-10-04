"""E5 shifted epochs (Tier 3): VM, FR and FF at offsets of 1, 10 and 100 Julian years, plus one difficult epoch.

Brief s8 (E5): a run at offset k starts at model time k x 365.25 d. Planets and relays advance from the epoch; only the
balance sheet is reset. Maintenance windows and the S2 incident are not replayed, so every run here has neither.
Scenario hours stay relative (h 0 = start of the shifted run); geometry is evaluated at offset + h.

Difficult epoch (chosen from the E4 closure list, code/out/e4_closures.csv):
  HARD_T = 816,143 h (93.10 y, 2119-10-30 23:00 TDB label). The Jupiter-Relay A link closes at h 281.8 (and Relay A ->
  Jupiter at h 284.5) for 1,242 h (51.8 d), longer than the 30-day packet lifetime. At h -72 Jupiter-Relay A-Ceres is
  the fastest route open through first use + 24 h, so the futures session is pinned on it, and the closure lands after
  the last interim print (h 264) and before the settling print (h 288). That is the worst placement for the route rule:
  the SETTLE itself is the first message to meet the closure, so it pays a fresh handshake on the other relay. Across
  all 54 Jupiter / Ceres relay-link closures in 200 y, this one stays closed longest after maturity (1,215 h).
  A no-re-route variant (queue behind the closure) is run for contrast only.

Outputs: code/out/e5/*.json, code/out/e5_summary.json, latex/generated/e5_summary.tex, latex/generated/e5_macros.tex
Run: python code/e5_epochs.py   (about 1 min)
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

import scenarios as S
from report import B, esc, h, num, tab, usd
from sim import SEC

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "code" / "out"
GEN = ROOT / "latex" / "generated"
H_YEAR = 365.25 * 24
OFFSETS_Y = [1, 10, 100]
HARD_T = 816_143.0
EPOCH = datetime(2026, 9, 22)


def world(kind, offset, reroute=True):
    w = S.World(f"{kind}", maintenance=False, offset=offset)
    w.reroute = reroute
    if kind == "VM":
        w.script_vm()
    else:
        w.script_future({"FR": S.RISING, "FF": S.FALLING}[kind])
    w.kind = "vm" if kind == "VM" else "future"
    return w


def route_txt(r):
    return "via " + "--".join(x.replace("Relay ", "") for x in r[1:-1])


def open_frac(geo, route, t0, t1, step=0.25):
    """Share of launch times in [t0, t1] at which the whole route (and its reverse) is open by geometry."""
    ts = np.arange(t0, t1 + 1e-9, step)
    ok = sum(geo.route_open(route, float(t), float(t)) for t in ts)
    return ok / len(ts)


def closed_spans(geo, route, t0, t1, step=0.25):
    spans, cur = [], None
    for t in np.arange(t0, t1 + 1e-9, step):
        o = geo.route_open(route, float(t), float(t))
        if not o and cur is None:
            cur = float(t)
        if o and cur is not None:
            spans.append((cur, float(t)))
            cur = None
    if cur is not None:
        spans.append((cur, None))
    return spans


def run_epoch(label, offset):
    out = {}
    for kind in ("VM", "FR", "FF"):
        w = world(kind, offset)
        res = S.execute(f"{label}-{kind}", w=w, out=OUT / "e5")
        geo = w.sim.geo
        a, b, route = w.sessions[0]
        end = res["complete"] if kind == "VM" else res["spendable"]
        out[kind] = dict(route=route, pair=f"{a}-{b}", T0=geo.T0(route, 0.0), T0_back=geo.T0(route[::-1], 0.0),
                         avail=open_frac(geo, route, 0.0, end), closed=closed_spans(geo, route, -72.0, end),
                         end=end, reroutes=res["marks"].get("reroutes", []),
                         sessions=[dict(a=x, b=y, route=r) for x, y, r in w.sessions],
                         launches=res["launches_total"], originated=res["originated"],
                         usd_h=res["asset_hours"]["USD"], peak=res["peak_usd"],
                         payoff=res.get("payoff"), open=res.get("open"))
        print(f"{label:6s} {kind}  route {route_txt(route):10s} T0 {out[kind]['T0']:.3f}  avail {out[kind]['avail']:.3f}"
              f"  done h {end:.4f}  launches {res['launches_total']}  re-routes {len(out[kind]['reroutes'])}", flush=True)
    return out


def naive_hard():
    """Contrast only: the same hard-epoch FR run with the route rule switched off (queue behind the closure)."""
    w = world("FR", HARD_T, reroute=False)
    w.sim.run(until=3000.0)
    return dict(spendable=w.marks["spendable"], launches=len(w.sim.launches), originated=len(w.sim.originated))


def main():
    R = {}
    for k in OFFSETS_Y:
        R[f"+{k} y"] = dict(offset=k * H_YEAR, runs=run_epoch(f"E5+{k}y", k * H_YEAR))
    R["hard"] = dict(offset=HARD_T, runs=run_epoch("E5hard", HARD_T))
    R["hard"]["naive_FR"] = naive_hard()
    pinned = R["hard"]["runs"]["FR"]["sessions"][0]["route"]
    links = {f"{a}->{b}" for a, b in zip(pinned, pinned[1:])}
    with open(OUT / "e4_closures.csv") as f:
        cl = [r for r in csv.DictReader(f) if r["link"] in links
              and float(r["start_h"]) < HARD_T + 400 and float(r["end_h"]) > HARD_T]
    c = min(cl, key=lambda r: float(r["start_h"]))
    R["hard"]["closure"] = (float(c["start_h"]) - HARD_T, float(c["end_h"]) - HARD_T, float(c["duration_h"]), c["link"])
    # nominal settlement time at the hard epoch had the pinned route stayed open: h 288 + one-way Ceres -> Jupiter
    hr = R["hard"]["runs"]["FR"]
    geo = world("FR", HARD_T).sim.geo
    R["hard"]["nominal_spendable"] = 288.0 + geo.T0(hr["route"][::-1], 288.0)
    for k, v in R.items():
        v["date"] = (EPOCH + timedelta(hours=v["offset"])).strftime("%Y-%m-%d %H:%M")
    (OUT / "e5_summary.json").write_text(json.dumps(R, indent=1, default=str))
    write_tex(R)


def write_tex(R):
    hard = R["hard"]
    fr, ff, vm = (hard["runs"][k] for k in ("FR", "FF", "VM"))
    nom = hard["nominal_spendable"]
    late = fr["end"] - nom
    naive = hard["naive_FR"]
    naive_late = naive["spendable"] - nom
    pledge = S.MARGIN
    fr_pay = fr["payoff"]["to_long"]
    ff_refund = S.MARGIN + ff["payoff"]["to_long"]                    # what Callisto gets back in FF

    rows = []
    for key, v in R.items():
        lab = key if key != "hard" else f"+{v['offset'] / H_YEAR:.2f} y (hard)"
        r = v["runs"]
        rows.append(" & ".join([
            lab, num(v["offset"]),
            route_txt(r["VM"]["route"]), h(r["VM"]["T0"]), f"{100 * r['VM']['avail']:.1f}", h(r["VM"]["end"]),
            route_txt(r["FR"]["route"]), h(r["FR"]["T0"]), f"{100 * r['FR']['avail']:.1f}", h(r["FR"]["end"])]))
    head = r"Offset & start h & route & one-way h & open \% & done h & route & one-way h & open \% & spendable h"
    extra = (r" & & \multicolumn{4}{c}{Value move, Earth--Neptune} & "
             r"\multicolumn{4}{c}{Ceres Iron future, Jupiter--Ceres (FR = FF)}\\" + "\n"
             r"\cmidrule(lr){3-6}\cmidrule(lr){7-10}")
    t1 = (r"\par\noindent\textbf{Tier 1: shifted runs, no suspension at any offset}\par" + "\n" + r"\setlength{\tabcolsep}{3pt}" + "\n"
          + tab("lrlrrrlrrr", head, rows, extra) + r"\normalsize" + "\n")

    hr = [
        ("Value move", route_txt(vm["route"]), h(vm["end"]), "0", str(vm["launches"]), num(vm["usd_h"]),
         "none: route open"),
        ("FR (harder)", r"A$\to$B", h(fr["end"]), str(len(fr["reroutes"])), str(fr["launches"]), num(fr["usd_h"]),
         f"{usd(pledge)} pledge, {usd(fr_pay)} payoff +{h(late)} h"),
        ("FF", r"A$\to$B", h(ff["end"]), str(len(ff["reroutes"])), str(ff["launches"]), num(ff["usd_h"]),
         f"short paid h 288; {usd(ff_refund)} refund +{h(late)} h"),
        ("FR, route open (derived)", "via A", h(nom), "0", "---", num(fr["usd_h"] - pledge * late),
         f"baseline: the {num(fr['usd_h'])} total minus the extra {num(pledge * late)}"),
        ("FR, no re-route", "via A", h(naive["spendable"]), "0", str(naive["launches"]), "",
         f"SETTLE held {num(naive_late)} h $>$ 30-day lifetime"),
    ]
    t2 = (r"\par\noindent\textbf{Tiers 2--3: epoch h " + num(HARD_T) + " (" + hard["date"][:10]
          + "); Jupiter--Relay A closed from run h " + h(hard["closure"][0], 1) + " for " + num(hard["closure"][2])
          + r" h}\par" + "\n" + r"\setlength{\tabcolsep}{3pt}" + "\n"
          + tab(r"llrrrr>{\raggedright\arraybackslash}X",
                r"Run & route & done h & re-routes & launches & \$-h locked & Funded consequence",
                [" & ".join(x) for x in hr]).replace(r"\begin{tabular}{", r"\begin{tabularx}{\linewidth}{")
                                             .replace(r"\end{tabular}", r"\end{tabularx}") + "\n")
    (GEN / "e5_summary.tex").write_text(t1 + "\n" + r"\medskip" + "\n" + t2)

    m = {
        "EfiveHardH": num(HARD_T), "EfiveHardY": f"{HARD_T / H_YEAR:.2f}", "EfiveHardDate": hard["date"][:10],
        "EfiveClosureStart": h(hard["closure"][0], 1), "EfiveClosureDays": h(hard["closure"][2] / 24, 1),
        "EfiveClosureH": num(hard["closure"][2]),
        "EfiveNominal": h(nom), "EfiveFRDone": h(fr["end"]), "EfiveLate": h(late), "EfiveNaiveDone": h(naive["spendable"]),
        "EfiveNaiveLate": num(naive_late), "EfiveNaiveLaunches": str(naive["launches"]),
        "EfiveRerouteAt": h(fr["reroutes"][0]), "EfiveExtraUsdH": num(pledge * late),
        "EfiveNaiveUsdH": num(pledge * naive_late),
        "EfiveTotalUsdH": num(fr["usd_h"]), "EfiveBaseUsdH": num(fr["usd_h"] - pledge * late),
    }
    for k in OFFSETS_Y:
        r = R[f"+{k} y"]["runs"]
        w = {1: "One", 10: "Ten", 100: "Hundred"}[k]
        m[f"Efive{w}VM"], m[f"Efive{w}Fut"] = h(r["VM"]["end"]), h(r["FR"]["end"])
    (GEN / "e5_macros.tex").write_text("".join(f"{B}newcommand{{{B}{k}}}{{{v}}}\n" for k, v in m.items()))


if __name__ == "__main__":
    main()
