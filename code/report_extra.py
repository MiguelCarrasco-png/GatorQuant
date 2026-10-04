"""Tables and macros from the hardening runs: fuzz.json, faulty.json, stack_scan.json, griefing.json, probe_sweep.json.
Writes latex/generated/fuzz_summary.tex, faulty_table.tex, stack_scan.tex, extra_macros.tex.
Run after: fuzz.py, faulty.py, stack_scan.py, griefing.py, probe_sweep.py, quota_test.py. Run: python code/report_extra.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
GEN = Path(__file__).resolve().parent.parent / "latex" / "generated"
B = chr(92)
NL = chr(10)


def num(x):
    return f"{x:,.0f}".replace(",", "{,}")


def tab(spec, head, rows):
    return NL.join([B + "begin{tabular}{" + spec + "}", B + "toprule", head + B + B, B + "midrule"]
                   + [r + B + B for r in rows] + [B + "bottomrule", B + "end{tabular}"]) + NL


def main():
    M = {}
    # ---- fuzz
    fz = json.loads((OUT / "fuzz.json").read_text())
    S = fz["summary"]
    names = {"VM": "Value move (VM)", "FR": "Future, rising (FR)", "FF": "Future, falling (FF)"}
    rows = []
    for k in ("VM", "FR", "FF"):
        s = S[k]
        rows.append(" & ".join([names[k], num(s["runs"]), num(s["ledger_steps"]), num(s["launches"]), num(s["loss"]),
                                num(s["dup"]), num(s["reorder"]), num(s["contradiction"]), num(s["reset"]),
                                num(s["crash"]), num(s.get("withdraw", 0)), f"{s['committed']}/{s['declined']}",
                                str(s["failures"])]))
    tot = lambda key: sum(S[k].get(key, 0) for k in S)
    rows.append(B + "midrule Total & " + " & ".join(num(tot(k)) for k in
                ("runs", "ledger_steps", "launches", "loss", "dup", "reorder", "contradiction", "reset", "crash", "withdraw"))
                + f" & {tot('committed')}/{tot('declined')} & {tot('failures')}")
    head = "Product & runs & ledger steps & launches & lost & dup. & reord. & contra. & resets & crashes & withdr. & commit/decl. & failed"
    (GEN / "fuzz_summary.tex").write_text(tab("lrrrrrrrrrrrr", head, rows))
    M.update(FuzzRuns=num(tot("runs")), FuzzSteps=num(tot("ledger_steps")), FuzzFailures=str(tot("failures")),
             FuzzLaunches=num(tot("launches")), FuzzPerProduct=num(S["VM"]["runs"]))
    # ---- faulty Branch
    fa = json.loads((OUT / "faulty.json").read_text())
    by = {(r["fault"], r["audit"]): r for r in fa}

    def eff(r):
        if r["fault"] == "F4":
            return "decision never sent; lock stays open, no loss, no detection (liveness fault only)"
        if r["invariants"] != "hold":
            d = r.get("client_delta") or {}
            if d:
                o, v = next(iter(d.items()))
                return f"forged amount applied: {o} {v['USD']:+,.0f} NeoDollars; {r['invariants'][:40]}".replace("$", B + "$")
            return "invariant check fails: " + r["invariants"].split(":", 1)[-1].strip()[:70]
        return "no effect on any balance" + ("; flagged: " + r["detected"][0] if r.get("detected") else "; not noticed")
    what = {"F1": "commits, then sends DECLINE for the same deal",
            "F2": "sends SETTLE for " + B + "$70{,}000 when its own print pays " + B + "$57{,}500",
            "F3": "sends COMMIT echoing " + B + "$24{,}000, not the LOCK's " + B + "$25{,}000",
            "F4": "records its decision and never sends it"}
    rows = []
    for f in ("F1", "F2", "F3", "F4"):
        rows.append(" & ".join([f, what[f], eff(by[(f, True)]), eff(by[(f, False)])]))
    t = NL.join([B + "begin{tabularx}{" + B + "linewidth}{l>{" + B + "raggedright" + B + "arraybackslash}p{3.7cm}XX}", B + "toprule",
                 "& Faulty Branch & With R22 (echo check, recompute) & Without" + B + B, B + "midrule"]
                + [r + B + B for r in rows] + [B + "bottomrule", B + "end{tabularx}"]) + NL
    (GEN / "faulty_table.tex").write_text(t)
    # ---- stacked scan
    sc = json.loads((OUT / "stack_scan.json").read_text())
    M["StackCombos"] = str(len(sc))
    M["StackWorstH"] = f"{sc[0]['spendable']:.1f}"
    M["StackMedianH"] = f"{sorted(x['spendable'] for x in sc)[len(sc) // 2]:.1f}"
    rows = []
    for x in sc[:4]:
        fo = f"Jupiter links {x['forced'][1]:g}--{x['forced'][1] + 6:g}" if x["forced"] else "none"
        rows.append(" & ".join([f"{x['iso']:g}--{x['iso'] + 72:g}", f"{x['reset_node']} at h {x['iso'] + 72 + x['reset_after']:g}", fo,
                                f"{x['spendable']:.1f}", f"{x['spendable'] - 288.6895:.1f}"]))
    head = "Ceres isolated (h) & endpoint reset & 6 h forced loss & service resumes (h) & lost (h)"
    (GEN / "stack_scan.tex").write_text(tab("lllrr", head, rows))
    # ---- griefing, quota
    gr = json.loads((OUT / "griefing.json").read_text())
    q = json.loads((OUT / "quota_test.json").read_text())
    M["QuotaS"] = str(min(r["S"] for r in q))
    (GEN / "extra_macros.tex").write_text("".join(B + "newcommand{" + B + k + "}{" + v + "}" + NL for k, v in M.items()))
    print(M)


if __name__ == "__main__":
    main()
