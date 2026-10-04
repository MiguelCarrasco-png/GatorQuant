"""Stacked-incident scan (S2): isolation of Ceres + endpoint reset + optional 6 h forced loss, over a small grid.
Picks the combination with the latest financial-service resumption. Output: code/out/stack_scan.json"""
import itertools, json
from pathlib import Path
import scenarios as sc

OUT = Path(__file__).resolve().parent / "out"
rows = []
for iso, rn, ra, fo in itertools.product((272.5, 280.0, 286.0), ("Ceres", "Jupiter"), (0.0, 2.0, 5.0),
                                         (None, ("Jupiter", 344.0), ("Jupiter", 358.0))):
    sc.STACK.update(iso_start=iso, reset_node=rn, reset_after=ra,
                    forced_node=fo[0] if fo else None, forced_start=fo[1] if fo else 0.0)
    r = sc.execute("S2-ST", sc.make("S2-ST"), out=OUT / "stack_tmp")
    rows.append(dict(iso=iso, reset_node=rn, reset_after=ra, forced=fo, spendable=r["spendable"],
                     usd_h=r["asset_hours"]["USD"], launches=r["launches_total"], failed=r["launches_failed"],
                     originated=r["originated"]))
    print(rows[-1], flush=True)
rows.sort(key=lambda x: -x["spendable"])
(OUT / "stack_scan.json").write_text(json.dumps(rows, indent=1))
print("WORST", rows[0])
