"""Sensitivity of recovery to the resubmission pace PROBE_H (S2-FR and the stacked incident).
Output: code/out/probe_sweep.json, latex/generated/probe_sweep.tex"""
import json
from pathlib import Path

import scenarios as sc

OUT = Path(__file__).resolve().parent / "out"
GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"
rows = []
base = sc.execute("FR", out=OUT / "sweep_tmp")["spendable"]
for pace in (1.2, 2.4, 4.8, 9.6, 25.4):
    sc.PROBE_H = pace
    row = dict(pace=pace)
    for run in ("S2-FR", "S2-ST"):
        r = sc.execute(run, out=OUT / "sweep_tmp")
        row[run] = dict(spendable=r["spendable"], lost=r["spendable"] - base, launches=r["launches_total"],
                        quota=r["originated"], peak=max(r["quota_peak_branch"].values()))
    rows.append(row)
    print(row, flush=True)
(OUT / "probe_sweep.json").write_text(json.dumps(rows, indent=1))
B = chr(92)
L = [B + "begin{tabular}{rrrrrrrr}", B + "toprule",
     " & " + B + "multicolumn{4}{c}{S2-FR} & " + B + "multicolumn{3}{c}{S2-ST (stacked)}" + B + B,
     B + "cmidrule(lr){2-5}" + B + "cmidrule(lr){6-8}",
     "Pace (h) & resumes (h) & lost (h) & quota pkts & peak/Branch & resumes (h) & lost (h) & quota pkts" + B + B, B + "midrule"]
for r in rows:
    a, b = r["S2-FR"], r["S2-ST"]
    L.append(f"{r['pace']:g} & {a['spendable']:.1f} & {a['lost']:.1f} & {a['quota']} & {a['peak']} & {b['spendable']:.1f} & {b['lost']:.1f} & {b['quota']}" + B + B)
L += [B + "bottomrule", B + "end{tabular}"]
(GEN / "probe_sweep.tex").write_text(chr(10).join(L) + chr(10))
