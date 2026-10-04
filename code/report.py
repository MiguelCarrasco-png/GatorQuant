"""LaTeX tables and macros from the trace-simulator runs (called by code/scenarios.py after all 16 runs).

Writes latex/generated/:
  s1_summary.tex      per-run completion, traffic, capital measures (S1)
  s1_traces.tex       compact no-loss traces: VM, FR (interim prints collapsed), FF and FR-cap from h 288
  e2_probabilities.tex  backbone loss per launch and hop abandonment for every link used; traffic and quota table
  balance_sheet.tex   opening sheet alone (design paper)
  e3_balances.tex     opening sheet; balance changes at every ledger step for VM, FR, FF; conservation checks
  s2_stress.tex       S2 trace from h 264, maintenance comparison, Mars-hub alternative
  s3_access.tex       best route / one-way delay / 24 h availability per settlement at h 0 and h 300; VM timelines
  sim_macros.tex      numbers used in prose
"""
import itertools
import math
from pathlib import Path

import numpy as np

from orbits import RELAYS, SETTLEMENTS
from sim import SEC, Geometry

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "latex" / "generated"
B = "\\"


def sci(x, d=1):
    """Scientific notation for prose macros: 4.0e-02 -> 4.0\times10^{-2} (used inside math mode)."""
    m, e = f"{x:.{d}e}".split("e")
    return m + B + "times10^{" + str(int(e)) + "}"


def num(x, d=0):
    return f"{x:,.{d}f}".replace(",", "{,}")


def usd(x):
    return B + "$" + num(x)


def h(x, d=2):
    return f"{x:.{d}f}"


def esc(s):
    return s.replace("&", B + "&").replace("%", B + "%").replace("#", B + "#").replace("_", B + "_")


def tabx(spec, head, rows):
    """Full-width table that breaks across pages (xltabular = tabularx + longtable), header repeated."""
    L = [B + "begin{xltabular}{" + B + "linewidth}{" + spec + "}", B + "toprule", head + B + B, B + "midrule",
         B + "endhead", B + "bottomrule", B + "endlastfoot"]
    L += [r + B + B for r in rows]
    L += [B + "end{xltabular}"]
    return "\n".join(L) + "\n"


def ht(t):
    return B + "mbox{" + (f"${t:.4f}$" if t < 0 else f"{t:.4f}") + "}"


def tab(spec, head, rows, extra_head=None):
    L = [B + "par" + B + "noindent", B + "begin{tabular}{" + spec + "}", B + "toprule"] + \
        ([extra_head] if extra_head else []) + [head + B + B, B + "midrule"]
    L += [r + B + B for r in rows]
    L += [B + "bottomrule", B + "end{tabular}" + B + "par"]
    return "\n".join(L) + "\n"


def ttab(cols, rows, first="Measure"):
    """Transposed table: one column per run, one row per measure (keeps wide summaries inside the margins)."""
    return tab("l" + "r" * len(cols), first + " & " + " & ".join(cols), [lab + " & " + " & ".join(v) for lab, v in rows])


# ------------------------------------------------------------------ traces

# Time+actor and packet+arrival share a cell each, so the text columns are wide enough to stay short at 10 pt.
TRACE_SPEC = (">{\\raggedright\\arraybackslash}p{1.75cm}"
              ">{\\raggedright\\arraybackslash\\hsize=0.8\\hsize}X>{\\raggedright\\arraybackslash\\hsize=0.8\\hsize}X"
              ">{\\raggedright\\arraybackslash\\hsize=1.15\\hsize}X>{\\raggedright\\arraybackslash\\hsize=1.25\\hsize}X")
TRACE_HEAD = ("Time (h), actor & Local knowledge & Action & Packet (BB = backbone); arrival & "
              "Financial state after")


def trace_rows(rows):
    out = []
    for r in rows:
        actor = r["actor"].replace(" Branch", " Br.")
        arr = r["arrival"]
        packet = r["packet"] + ("; " + ("arrives " + arr if arr.startswith("h ") or arr.startswith("+") else arr)
                                if arr else "")
        out.append(" & ".join([ht(r["t"]) + B + "newline " + esc(actor), esc(r["know"]), esc(r["action"]), packet,
                               r["state"]]))
    return out


def collapse_prints(rows, lo=24, hi=216):
    """Interim prints h lo..hi forwarded identically: one summary row each for the send and the hand-over."""
    keep, fw, hand = [], [], []
    for r in rows:
        if "Forwards it to Jupiter" in r["action"] and lo <= r["t"] < hi + 1:
            fw.append(r)
        elif "Hands it to Callisto" in r["action"]:   # every print; stated once in the forward rows
            hand.append(r)
        else:
            keep.append(r)
    if fw:
        arr = [float(r["arrival"].replace("h ", "")) - r["t"] for r in fw]
        keep.append(dict(t=fw[0]["t"], actor="Ceres Branch",
                         know=f"Interim prints h {lo}, {lo + 24}, \\ldots, {hi} by local access",
                         action=f"Forwards each to Jupiter ({len(fw)} packets; information only)",
                         packet="BB Ceres $\\to$ B $\\to$ Jupiter, one per print",
                         arrival=f"+{min(arr):.4f} to +{max(arr):.4f}",
                         state="unchanged; Jupiter Branch hands every print to Callisto by local access on "
                               "arrival"))
    return sorted(keep, key=lambda r: r["t"])



BOring = ("Resubmits LOCK", "Endpoint attempt", "Repeats recorded")


def compact_s2(rows):
    """Group runs of repetitive recovery rows (resubmissions, endpoint retries, repeated answers) into one summary row."""
    out, buf = [], []

    def flush():
        if not buf:
            return
        n_re = sum(r["action"].startswith("Resubmits") for r in buf)
        n_ep = sum(r["action"].startswith("Endpoint attempt") for r in buf)
        n_rp = sum(r["action"].startswith("Repeats") for r in buf)
        parts = []
        if n_re:
            parts.append(f"{n_re} LOCK resubmissions, one every 2.4 h")
        if n_ep:
            parts.append(f"{n_ep} endpoint retries")
        if n_rp:
            parts.append(f"{n_rp} repeats of the recorded SETTLE")
        out.append(dict(t=buf[0]["t"], actor="Jupiter and Ceres Br.", know="No SETTLE has reached Jupiter; "
                        f"repeats run h {buf[0]['t']:.1f}--{buf[-1]['t']:.1f}", action="; ".join(parts),
                        packet="BB; copies launched during the incident are lost", arrival="", state="unchanged"))
        buf.clear()
    for r in rows:
        if r["action"].startswith(BOring) and r["state"] == "unchanged":
            buf.append(r)
        else:
            flush()
            out.append(r)
    flush()
    return out


def s2_summary(R):
    base, ff, fr = R["FR"], R["S2"], R["S2-FR"]
    cols = [("No incident", base, "none"),
            ("S2-FF", ff, "FF: Callisto's " + B + "$17{,}500 refund; Ceres Iron paid at the print"),
            ("S2-FR", fr, "FR: Callisto's " + B + "$132{,}500 (payoff and pledge)"),
            ("S2-ST", R["S2-ST"], "FR: Callisto's " + B + "$132{,}500, three incidents")]
    rows = [("Financial service resumes (h)", [h(r.get("spendable")) for _, r, _ in cols]),
            ("Lost service vs no incident (h)", ["---"] + [h(r["spendable"] - base["spendable"], 1) for _, r, _ in cols[1:]]),
            ("Extra " + B + "$-hours locked", ["---"] + [num(r["asset_hours"]["USD"] - base["asset_hours"]["USD"]) for _, r, _ in cols[1:]]),
            ("Backbone launches (failed)", [f"{r['launches_total']} ({r['launches_failed']})" for _, r, _ in cols]),
            ("Quota packets; peak per Branch of 66", [f"{r['originated']}; {max(r['quota_peak_branch'].values())}" for _, r, _ in cols]),
            ("Who waits, for what", [c for _, _, c in cols])]
    nl = chr(10)
    t = B + "begin{tabularx}{" + B + "linewidth}{lXXXX}" + B + "toprule" + nl
    t += "Measure & " + " & ".join(n for n, _, _ in cols) + B + B + B + "midrule" + nl
    t += nl.join(lab + " & " + " & ".join(v) + B + B for lab, v in rows) + nl
    t += B + "bottomrule" + nl + B + "end{tabularx}" + nl
    return t


def trace_table(rows, caption):
    return (B + "par" + B + "noindent" + B + "textbf{" + caption + "}" + B + "par\n{" + B + "setlength{" + B +
            "tabcolsep}{3pt}\n" + tabx(TRACE_SPEC, TRACE_HEAD, trace_rows(rows)) + "}\n")


# ------------------------------------------------------------------ S3 access table

def best_route_at(geo, src, dst, t):
    cands = [[src, r, dst] for r in RELAYS] + [[src, a, b, dst] for a, b in itertools.permutations(RELAYS)]
    best = None
    for r in cands:
        cur, ok = t, True
        for k in range(len(r) - 1):
            if not geo.known_ok(r[k], r[k + 1], cur + SEC):
                ok = False
                break
            cur += SEC + geo.flight(r[k], r[k + 1], cur + SEC)[0] + (SEC if k < len(r) - 2 else 0)
        if ok and (best is None or cur - t < best[1]):
            best = (r, cur - t)
    return best


def availability(geo, route, t, step=0.05):
    ok = 0
    ts = np.arange(t, t + 24 - 1e-9, step)
    for t0 in ts:
        cur, good = float(t0), True
        for k in range(len(route) - 1):
            if not geo.known_ok(route[k], route[k + 1], cur + SEC):
                good = False
                break
            cur += SEC + geo.flight(route[k], route[k + 1], cur + SEC)[0] + SEC
        ok += good
    return ok / len(ts)


def access_table():
    """One row per settlement: best route, one-way delay (h 0, h 300) and 24 h availability (h 0, h 300) to the referee
    (Ceres) and to the counterparty's Branch (Neptune). A route is shown once when it is the same at both hours."""
    geo = Geometry(maintenance=True)
    data, rows = {}, []
    for s in SETTLEMENTS:
        cells = [s]
        for dst in ("Ceres", "Neptune"):
            if s == dst:
                cells += ["local", "0.0003", "0.0003", "100.0", "100.0"]
                for t in (0.0, 300.0):
                    data[(s, dst, t)] = None
                continue
            got = []
            for t in (0.0, 300.0):
                r, d = best_route_at(geo, s, dst, t)
                av = availability(geo, r, t)
                data[(s, dst, t)] = dict(route=r, delay=d, avail=av)
                got.append(("via " + "".join(x[-1] for x in r[1:-1]), d, av))
            rt = got[0][0] if got[0][0] == got[1][0] else got[0][0] + " / " + got[1][0][4:]
            cells += [rt, h(got[0][1]), h(got[1][1]), f"{100 * got[0][2]:.1f}", f"{100 * got[1][2]:.1f}"]
        rows.append(" & ".join(cells))
    eh = (" & " + B + "multicolumn{5}{c}{Ceres Iron future: to the referee (Ceres)} & " + B +
          "multicolumn{5}{c}{Share DvP: to the counterparty's Branch (Neptune)}" + B + B + "\n" +
          B + "cmidrule(lr){2-6}" + B + "cmidrule(lr){7-11}")
    head = "From" + " & route & h 0 & h 300 & avail.\\ h 0 & h 300" * 2
    return tab("l" + "lrrrr" * 2, head, rows, eh), data


# ------------------------------------------------------------------ E3 balance steps

def changes(snaps, owners_filter=None):
    def keyed(sn):
        return {(x["branch"], x["owner"], x["asset"], x["kind"]): x for x in sn}
    rows = []
    prev = keyed(snaps[0][1])
    for t, sn in snaps[1:]:
        cur = keyed(sn)
        diffs = []
        for k in sorted(set(prev) | set(cur)):
            a, b = prev.get(k), cur.get(k)
            ba = a["bal"] if a else 0.0
            bb = b["bal"] if b else 0.0
            ea = sum(a["enc"].values()) if a else 0.0
            eb = sum(b["enc"].values()) if b else 0.0
            tags_a = a["enc"] if a else {}
            tags_b = b["enc"] if b else {}
            if abs(ba - bb) > 1e-9 or tags_a != tags_b:
                unit = usd if k[2] == "USD" else (lambda v: num(v) + " Ares")
                tag = " (claim)" if k[3] == "claim" else ""
                enc = ", ".join(f"{unit(v)} for {esc(t)}" for t, v in tags_b.items()) or "none"
                diffs.append(f"{esc(k[1])} at {k[0]}{tag}: {unit(bb)}; encumbered: {enc}")
        rows.append((t, diffs))
        prev = cur
    return rows


# ------------------------------------------------------------------ main writer

def write_all(R):
    GEN.mkdir(parents=True, exist_ok=True)
    M = {}

    # ---------- S1 summary (one column per run)
    runs = ["VM", "FR", "FF", "FR-cap", "S2-FR", "S2-ST"]
    G = [R[x] for x in runs]
    rows = [
        ("Completion / spendable h", [h(r.get("complete", r.get("spendable"))) for r in G]),
        ("Backbone packets (all launches)", [str(r["launches_total"]) for r in G]),
        ("of which quota (originated)", [str(r["originated"]) for r in G]),
        ("Peak encumbered " + B + "$", [num(r["peak_usd"]) for r in G]),
        ("Peak encumbered Ares", [num(r["peak_ares"]) for r in G]),
        (B + "$-hours", [num(r["asset_hours"]["USD"]) for r in G]),
        ("Ares-hours", [num(r["asset_hours"]["ARES"]) for r in G]),
        ("Capital utilization " + B + "%", [f"{100 * r['utilization']:.0f}" for r in G]),
        ("Value settled " + B + "$", [num(r["value_settled"]) for r in G]),
        ("Capital efficiency", [f"{r['capital_eff']:.2f}" for r in G]),
    ]
    (GEN / "s1_summary.tex").write_text(ttab(runs, rows))

    # ---------- S1 traces
    out = []
    out.append(trace_table(R["VM"]["trace"], "VM: Terra Capital (Earth) buys 200 Ares from Triton Fund (Neptune)"))
    out.append(trace_table(collapse_prints(R["FR"]["trace"]), "FR: Ceres Iron future, rising path (settles 123)"))
    ff = [x for x in R["FF"]["trace"] if x["t"] >= 287]
    cap = [x for x in R["FR-cap"]["trace"] if x["t"] >= 287]
    out.append(trace_table(ff + cap, "FF (falling path, settles 77; first two rows) and FR-cap (settling print 140, "
                                     "clipped to 130: the cap binds; last two rows), from h 288. Before h 288 both "
                                     "are identical to FR except the interim print values"))
    (GEN / "s1_traces.tex").write_text("\n\\medskip\n".join(out))

    # ---------- E2
    links = {}
    for run in ["VM", "FR", "FF", "FR-cap", "S2", "S2-FR", "S2-ST", "VM@Ceres", "VM@Venus", "VM@Uranus"]:
        for x in R[run]["hops"]:
            links.setdefault(x["link"], []).append(x["d"])
    pairs = {}   # both directions of a link share one row (their distances differ by < 0.005 AU)
    for lk, ds in links.items():
        pairs.setdefault((" $" + B + "leftrightarrow$ ").join(sorted(lk.split("->"), key=lambda n: n.startswith("Relay"))),
                         []).extend(ds)
    rows = []
    worst_p = 0
    for lk in sorted(pairs):
        d = np.array(pairs[lk])
        pmax = 1 - math.exp(-0.02 * d.max())
        worst_p = max(worst_p, pmax)
        rows.append(" & ".join([lk, str(len(d)), f"{d.min():.3f}", f"{d.max():.3f}",
                                f"{100 * (1 - math.exp(-0.02 * d.min())):.2f}", f"{100 * pmax:.2f}",
                                f"{pmax ** 4:.2e}"]))
    t1 = tab("lrrrrrr", "Link (both directions) & launches & $d$ min AU & $d$ max AU & $p$ min \\% & $p$ max \\% & "
             "$P$(abandon) $" + B + "le p_{" + B + "max}^4$", rows)
    runs = ["VM", "FR", "FF", "FR-cap", "S2-FR", "S2-ST", "VM@Ceres", "VM@Venus", "VM@Uranus"]
    G = [R[x] for x in runs]
    rows = [(lab, [str(r["launches_by_kind"][k]) for r in G]) for lab, k in
            [("SYN", "SYN"), ("SYN-ACK", "SYNACK"), ("ACK", "ACK"), ("data", "DATA"), ("data ACK", "DACK"),
             ("hop receipts", "RCPT")]]
    rows += [("Backbone total", [str(r["launches_total"]) for r in G]),
             ("failed (incident)", [str(r["launches_failed"]) for r in G]),
             ("Quota packets", [str(r["originated"]) for r in G]),
             ("Peak 24 h, system / 600", [str(r["quota_peak_system"]) for r in G]),
             ("Peak 24 h, one Branch / 66", [str(max(r["quota_peak_branch"].values())) for r in G]),
             ("Peak link queue / 10{,}000", [str(r["queue_peak"]) for r in G]),
             ("Peak unACKed / 64", [str(r["max_unacked"]) for r in G]),
             ("Longest known wait h", [h(r["max_wait"]) for r in G])]
    t2 = ttab([x.replace("VM@", "@") for x in runs], rows, "Packets")
    # endpoint level: one attempt is lost if any hop is abandoned (hops independent; bound uses p_max per link);
    # four attempts are spaced R_e > 24 h apart, so with no incident they share no closure or window: independent.
    pab = {lk: (1 - math.exp(-0.02 * max(d))) ** 4 for lk, d in links.items()}
    rows, worst_route = [], (0, None)
    seen = set()
    for run in ["VM", "VM@Ceres", "VM@Venus", "VM@Uranus", "FR"]:
        for ss in R[run]["sessions"]:
            rt = ss["route"]
            if tuple(rt) in seen or tuple(reversed(rt)) in seen:
                continue
            seen.add(tuple(rt))
            q = 0.0   # the worse of the two directions
            for r_ in (rt, list(reversed(rt))):
                hops = [f"{r_[k]}->{r_[k + 1]}" for k in range(len(r_) - 1)]
                q = max(q, 1 - np.prod([1 - pab[x] for x in hops]))
            worst_route = max(worst_route, (q, tuple(rt)))
            rows.append(" & ".join([(" $" + B + "leftrightarrow$ ").join(x.replace("Relay ", "") for x in rt),
                                    f"{q:.2e}", f"{q ** 4:.2e}"]))
    t15 = tab("lrr", "Pinned route (worse direction) & $P$(attempt lost) & $P$(4 lost: unknown)", rows)
    M["SimWorstAttemptLoss"] = sci(worst_route[0])
    M["SimWorstUnknown"] = sci(worst_route[0] ** 4)
    (GEN / "e2_probabilities.tex").write_text(t1 + "\n" + B + "medskip\n" + t15 + "\n" + B + "medskip\n" + t2)
    M["SimWorstLaunchLossPct"] = f"{100 * worst_p:.2f}"
    M["SimWorstHopAbandon"] = sci(worst_p ** 4)

    # ---------- E3
    op = R["VM"]["opening"]
    rows = [" & ".join([esc(o), s, usd(u), num(a)]) for o, s, u, a in op]
    rows.append(B + "midrule Total & " + str(len({x[1] for x in op})) + " settlements & " + usd(sum(x[2] for x in op)) + " & " + num(sum(x[3] for x in op)))
    t0 = tab("llrr", "Account & Settlement & NeoDollars & Ares shares", rows)
    (GEN / "balance_sheet.tex").write_text(t0)
    parts = [t0]
    rows = []
    for run in ["VM", "FR", "FF"]:  # S2 differs from FF only in the time of its last line (stated in the text)
        rows.append(B + "multicolumn{2}{l}{" + B + "textbf{" + run + "}}")
        for t, diffs in changes(R[run]["snaps"]):
            rows.append(ht(t) + " & " + "; ".join(diffs))
    parts.append(tabx("rX", "Time (h) & Lines changed (balance after, amount encumbered)",
                                              rows) + B + "normalsize\n")
    (GEN / "e3_balances.tex").write_text(("\n" + B + "medskip\n").join(parts))
    M["SimChecks"] = str(sum(R[r]["checks"] for r in R))
    M["SimRuns"] = str(len(R))

    # ---------- S2
    s2 = compact_s2([x for x in R["S2-FR"]["trace"] if x["t"] >= 287])
    st = compact_s2([x for x in R["S2-ST"]["trace"] if x["t"] >= 287])
    parts = [s2_summary(R),
             trace_table(s2, "S2-FR: the FR run plus a 72 h isolation of Ceres, h 286--358 (from h 288)"),
             trace_table(st, "S2-ST: the stacked incident (isolation of Ceres h 286--358, Ceres endpoint reset at h 358, "
                             "6 h forced loss of Jupiter's links h 358--364), from h 288")]
    bases = ["VM", "FR", "FF", "S2-FR"]
    A_, N_ = [R[x] for x in bases], [R["noMaint-" + x.replace("S2-FR", "S2")] for x in bases]

    def done(r):
        return r.get("complete", r.get("spendable"))
    rows = [("Done h, with / without maintenance", [f"{h(done(a))} / {h(done(b))}" for a, b in zip(A_, N_)]),
            ("Backbone packets, with / without", [f"{a['launches_total']} / {b['launches_total']}" for a, b in zip(A_, N_)]),
            ("Longest known wait h, with / without", [f"{h(a['max_wait'])} / {h(b['max_wait'])}" for a, b in zip(A_, N_)]),
            (B + "$-hours, with = without", [num(a["asset_hours"]["USD"]) if a["asset_hours"]["USD"] ==
                                            b["asset_hours"]["USD"] else "differ" for a, b in zip(A_, N_)])]
    vms = ["VM", "VM@Ceres", "VM@Venus", "VM@Uranus"]
    A_, H_ = [R[x] for x in vms], [R["Hub-" + x] for x in vms]
    rows = [("Complete h, home ledgers", [h(r["complete"]) for r in A_]),
            ("Complete h, Mars hub", [h(r["complete"]) for r in H_]),
            ("Backbone packets", [f"{a['launches_total']} / {b['launches_total']}" for a, b in zip(A_, H_)]),
            ("Quota packets", [f"{a['originated']} / {b['originated']}" for a, b in zip(A_, H_)]),
            ("Sessions to pre-open", [f"{len(a['sessions'])} / {len(b['sessions'])}" for a, b in zip(A_, H_)]),
            (B + "$-hours, home ledgers", [num(a["asset_hours"]["USD"]) for a in A_]),
            (B + "$-hours, Mars hub", [num(b["asset_hours"]["USD"]) for b in H_]),
            ("Ares-hours", [f"{num(a['asset_hours']['ARES'])} / {num(b['asset_hours']['ARES'])}"
                            for a, b in zip(A_, H_)])]
    parts.append(B + "par" + B + "noindent" + B + "textbf{Alternative: Mars hub ledger vs home ledgers (same funding "
                 "and guarantees; pairs are home / hub)}" + B + "par\n{" + B + "setlength{" + B + "tabcolsep}{3pt}\n" +
                 ttab(["Earth", "Ceres", "Venus", "Uranus"], rows, "Terra at") + "}\n")
    (GEN / "s2_stress.tex").write_text(("\n" + B + "medskip\n").join(parts))

    # ---------- S3
    acc, data = access_table()
    rows = []
    for v in ["VM@Ceres", "VM", "VM@Venus", "VM@Uranus"]:
        r = R[v]
        tr = r["trace"]
        lock = next(x for x in tr if "sends LOCK" in x["action"])
        com = next(x for x in tr if x["action"].startswith("Commits"))
        rel = next(x for x in tr if x["action"] == "Releases the lock")
        where = v.split("@")[1] if "@" in v else "Earth"
        rows.append(" & ".join([where, "via " + "".join(x[-1] for x in r["sessions"][0]["route"][1:-1]),
                                h(lock["t"], 4), lock["arrival"].replace("h ", ""), h(rel["t"], 4),
                                h(r["complete"] - lock["t"], 4), str(r["launches_total"]),
                                num(r["asset_hours"]["USD"])]))
    t3 = tab("llrrrrrr", "Terra at & route & LOCK sent & commit at Neptune & complete & duration & packets & " +
             B + "$-hours", rows)
    (GEN / "s3_access.tex").write_text(acc + "\n" + B + "medskip\n" + B + "par" + B + "noindent" + B +
                                       "textbf{VM re-run from reset with Terra and its " + B + "$150{,}000 at the best "
                                       "(Ceres), median (Venus) and worst (Uranus) settlement; Earth for reference}" +
                                       B + "par\n" + t3)

    # ---------- macros
    vm, fr, ff, s2r, cap = R["VM"], R["FR"], R["FF"], R["S2"], R["FR-cap"]
    M.update({
        "SimVMComplete": h(vm["complete"]), "SimVMCommit": h(vm["marks"]["commit"]),
        "SimVMPackets": str(vm["launches_total"]), "SimVMQuota": str(vm["originated"]),
        "SimFutOpen": h(fr["open"]), "SimFutSpendable": h(fr["spendable"]), "SimFutDischarge": h(fr["discharge"], 4),
        "SimFutPackets": str(fr["launches_total"]), "SimFutQuota": str(fr["originated"]),
        "SimFutDollarHours": num(fr["asset_hours"]["USD"]), "SimFutPeak": usd(fr["peak_usd"]),
        "SimFutUtil": f"{100 * fr['utilization']:.0f}",
        "SimPrintTwoFortyArrives": h(float(next(x for x in fr["trace"] if x["action"].startswith("Forwards")
                                                and abs(x["t"] - 240) < 1)["arrival"].replace("h ", "")), 4),
        "SimSTwoSpendable": h(s2r["spendable"]), "SimSTwoLost": h(s2r["spendable"] - ff["spendable"], 1),
        "SimSTwoExtraDollarHours": num(s2r["asset_hours"]["USD"] - ff["asset_hours"]["USD"]),
        "SimSTwoPackets": str(s2r["launches_total"]), "SimSTwoFailed": str(s2r["launches_failed"]),
        "SimSTwoQuota": str(s2r["originated"]),
        "SimSTwoFRSpendable": h(R["S2-FR"]["spendable"]), "SimSTwoFRLost": h(R["S2-FR"]["spendable"] - fr["spendable"], 1),
        "SimSTwoFRExtraDollarHours": num(R["S2-FR"]["asset_hours"]["USD"] - fr["asset_hours"]["USD"]),
        "SimSTwoFRPackets": str(R["S2-FR"]["launches_total"]), "SimSTwoFRFailed": str(R["S2-FR"]["launches_failed"]),
        "SimSTwoFRQuota": str(R["S2-FR"]["originated"]),
        "SimLiteLaunches": str(R["FR-lite"]["launches_total"]), "SimLiteQuota": str(R["FR-lite"]["originated"]),
        "SimLiteSaved": str(fr["launches_total"] - R["FR-lite"]["launches_total"]),
        "SimVoidSpendable": h(R["VOID"]["spendable"]), "SimVoidExtraDollarHours": num(R["VOID"]["asset_hours"]["USD"] - fr["asset_hours"]["USD"]),
        "SimSTwoFRSpendableAfter": h(R["S2-FR"]["spendable"] - 358.0, 1),
        "SimStackAfter": h(R["S2-ST"]["spendable"] - 364.0, 1),
        "SimSTwoPeakBranch": str(max(R["S2-FR"]["quota_peak_branch"].values())),
        "SimStackSpendable": h(R["S2-ST"]["spendable"]), "SimStackLost": h(R["S2-ST"]["spendable"] - fr["spendable"], 1),
        "SimStackExtraDollarHours": num(R["S2-ST"]["asset_hours"]["USD"] - fr["asset_hours"]["USD"]),
        "SimStackPackets": str(R["S2-ST"]["launches_total"]), "SimStackFailed": str(R["S2-ST"]["launches_failed"]),
        "SimStackQuota": str(R["S2-ST"]["originated"]),
        "SimStackPeakBranch": str(max(R["S2-ST"]["quota_peak_branch"].values())),
        "SimCapPayoff": usd(cap["payoff"]["to_long"]),
        "SimUranusComplete": h(R["VM@Uranus"]["complete"]), "SimCeresComplete": h(R["VM@Ceres"]["complete"]),
        "SimVenusComplete": h(R["VM@Venus"]["complete"]),
        "SimHubVMComplete": h(R["Hub-VM"]["complete"]), "SimHubVMPackets": str(R["Hub-VM"]["launches_total"]),
        "SimDirectPackets": "0",
    })
    (GEN / "sim_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    return data
