"""E4 long-horizon scan (Tier 3): every closure of all 38 directed backbone links over 200 Julian years,
certified by a Lipschitz bound, one refined boundary, and per-settlement availability / route-delay ranges.

Method (stated in the appendix):
  * m(t) = distance from the Sun to the photon segment sender(t_e) -> receiver(t_a), t_e = t. Link closed iff m < 0.10 AU.
  * m is Lipschitz in t_e with constant L = max endpoint speed (each segment point is a convex combination of the
    endpoints, so moving both endpoints by <= eps moves the segment by <= eps). L is computed per link from the
    perihelion speed of each body, times (1+v_tx/c)/(1-v_rx/c) for the arrival-time stretch.
  * On [a,b] with values ma, mb:  (ma+mb-L(b-a))/2 <= m <= (ma+mb+L(b-a))/2.  If the lower bound is >= R the link is
    certified open on all of [a,b]; if the upper bound is < R it is certified closed. Otherwise bisect, down to 1 ms.
  * So the base step (1 h) only sets cost: no closure or opening longer than 1 ms can be missed.

Outputs: code/out/e4_closures.csv, code/out/e4_summary.json, latex/generated/e4_*.tex
Run: python code/e4_scan.py   (about 5-10 min)
"""
import json
import math
from pathlib import Path

import numpy as np

from orbits import ELEMENTS, SETTLEMENTS, RELAYS, LIGHT_H_PER_AU, EXCLUSION_AU, position

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "code" / "out"
GEN = ROOT / "latex" / "generated"

YEARS = float(__import__("os").environ.get("E4_YEARS", 200))
H_YEAR = 365.25 * 24
H_END = YEARS * H_YEAR             # 1,753,200 h
STEP = 1.0                         # base grid, h
TOL = 1e-3 / 3600                  # boundary tolerance: 1 ms, h
DELAY_STRIDE = 6                   # keep hop delays every 6 h for route sampling (interp error < 0.1 s)
CHUNK = 200_000
R = EXCLUSION_AU
SEC = 1 / 3600
C_AU_H = 1 / LIGHT_H_PER_AU
A, B = RELAYS


def directed_links():
    links = []
    for s in SETTLEMENTS:
        for r in RELAYS:
            links += [(s, r), (r, s)]
    return links + [(A, B), (B, A)]


def vmax(body):
    """Perihelion speed in AU/h (upper bound on speed anywhere on the orbit)."""
    el = ELEMENTS[body]
    n = math.radians(el["mean_motion_deg_day"]) / 24
    return n * el["a_au"] * math.sqrt((1 + el["e"]) / (1 - el["e"]))


def lipschitz(tx, rx):
    vt, vr = vmax(tx), vmax(rx)
    return max(vt, vr * (1 + vt / C_AU_H) / (1 - vr / C_AU_H))


def miss(tx, rx, te):
    """Miss distance of the photon segment (AU) and flight time (h) for emission times te."""
    te = np.atleast_1d(np.asarray(te, dtype=float))
    rs = position(tx, te)
    ta = te + np.linalg.norm(position(rx, te) - rs, axis=-1) * LIGHT_H_PER_AU
    for _ in range(20):
        new = te + np.linalg.norm(position(rx, ta) - rs, axis=-1) * LIGHT_H_PER_AU
        done = np.max(np.abs(new - ta)) < 1e-9
        ta = new
        if done:
            break
    v = position(rx, ta) - rs
    s = np.clip(-np.sum(rs * v, axis=-1) / np.sum(v * v, axis=-1), 0.0, 1.0)
    return np.linalg.norm(rs + s[:, None] * v, axis=-1), ta - te


def scan_link(tx, rx):
    """Return (closures [(start,end,min_m,censored)], stats, coarse delay array, refinement log)."""
    L = lipschitz(tx, rx)
    t = np.arange(0.0, H_END + STEP / 2, STEP)
    m = np.empty_like(t)
    d = np.empty_like(t)
    for i in range(0, len(t), CHUNK):
        m[i:i + CHUNK], d[i:i + CHUNK] = miss(tx, rx, t[i:i + CHUNK])

    # level-wise certification of every grid interval
    a, b, ma, mb = t[:-1], t[1:], m[:-1], m[1:]
    crossings, slivers, evals, depth = [], 0, len(t), 0
    while len(a):
        h = b - a
        lo = (ma + mb - L * h) / 2
        hi = (ma + mb + L * h) / 2
        keep = (lo < R) & (hi >= R)
        a, b, ma, mb, h = a[keep], b[keep], ma[keep], mb[keep], h[keep]
        fine = h <= TOL
        flips = fine & ((ma < R) != (mb < R))
        crossings += list(zip((a[flips] + b[flips]) / 2, mb[flips] < R))  # (time, True = closing)
        slivers += int(np.sum(fine & ~flips))
        a, b, ma, mb = a[~fine], b[~fine], ma[~fine], mb[~fine]
        if not len(a):
            break
        mid = (a + b) / 2
        mm, _ = miss(tx, rx, mid)
        evals += len(mid)
        depth += 1
        a, b, ma, mb = np.concatenate([a, mid]), np.concatenate([mid, b]), np.concatenate([ma, mm]), np.concatenate([mm, mb])

    crossings.sort()
    closures, start = [], (0.0 if m[0] < R else None)
    for tc, closing in crossings:
        if closing:
            start = tc
        else:
            closures.append([start, tc])
            start = None
    if start is not None:
        closures.append([start, H_END])
    out = []
    for s0, e0 in closures:
        inside = m[(t >= s0) & (t <= e0)]
        mn = float(inside.min()) if len(inside) else float(miss(tx, rx, (s0 + e0) / 2)[0][0])
        out.append((s0, e0, mn, s0 == 0.0 or e0 == H_END))
    stats = dict(L_au_per_h=L, grid_margin_au=L * STEP / 2, evals=evals, depth=depth, slivers=slivers,
                 min_m=float(m.min()), max_m=float(m.max()))
    return out, stats, d[::DELAY_STRIDE]


def refined_boundary(tx, rx, closure):
    """Re-derive one closure start from its 1 h bracket by plain bisection, logging the bracket and tolerance."""
    s0 = closure[0]
    lo = math.floor(s0 / STEP) * STEP
    hi = lo + STEP
    mlo, mhi = miss(tx, rx, lo)[0][0], miss(tx, rx, hi)[0][0]
    a, b, it = lo, hi, 0
    while b - a > TOL:
        mid = (a + b) / 2
        if miss(tx, rx, mid)[0][0] < R:
            b = mid
        else:
            a = mid
        it += 1
    return dict(link=f"{tx} -> {rx}", bracket=[lo, hi], m_bracket=[float(mlo), float(mhi)], iterations=it,
                t_close=(a + b) / 2, width_s=(b - a) * 3600, m_at=[float(miss(tx, rx, a)[0][0]), float(miss(tx, rx, b)[0][0])])


# ---------------------------------------------------------------- routes (Tier 3)

def is_closed(cl, t):
    """cl: (starts, ends) sorted arrays. Vectorized membership."""
    s, e = cl
    i = np.searchsorted(s, t, side="right") - 1
    ok = i >= 0
    out = np.zeros(t.shape, bool)
    out[ok] = t[ok] < e[i[ok]]
    return out


def clipped(cl, lo, hi):
    """Up to two closure intervals of link overlapping [lo,hi) per row, clipped; returns (n,2) starts/ends."""
    s, e = cl
    n = len(lo)
    S, E = np.repeat(lo[:, None], 2, 1), np.repeat(lo[:, None], 2, 1)
    if not len(s):
        return S, E
    i = np.searchsorted(e, lo, side="right")  # first closure ending after lo
    for k in range(2):
        j = i + k
        ok = j < len(s)
        jj = np.minimum(j, len(s) - 1)
        cs, ce = np.maximum(s[jj], lo), np.minimum(e[jj], hi)
        good = ok & (ce > cs)
        S[good, k], E[good, k] = cs[good], ce[good]
    return S, E


def union_measure(S, E):
    o = np.argsort(S, axis=1)
    S, E = np.take_along_axis(S, o, 1), np.take_along_axis(E, o, 1)
    tot = np.zeros(len(S))
    reach = S[:, 0].copy()
    for j in range(S.shape[1]):
        tot += np.maximum(0, E[:, j] - np.maximum(S[:, j], reach))
        reach = np.maximum(reach, E[:, j])
    return tot


def routes(src, dst):
    return [[src, A, dst], [src, B, dst], [src, A, B, dst], [src, B, A, dst]]


def route_eval(path, h, CL, DL, tgrid):
    """Hop emission offsets, total empty-queue delay and open-at-start flag for route starting (ready) at h."""
    t = h + SEC  # serialization
    offs, open_ = [], np.ones(h.shape, bool)
    for k in range(len(path) - 1):
        link = (path[k], path[k + 1])
        offs.append(t - h)
        open_ &= ~is_closed(CL[link], t)
        t = t + np.interp(t, tgrid, DL[link])
        if k < len(path) - 2:
            t = t + 2 * SEC  # relay processing + next serialization
    return offs, t - h, open_


def route_availability(path, h, offs, CL):
    S, E = [], []
    for k in range(len(path) - 1):
        s, e = clipped(CL[(path[k], path[k + 1])], h + offs[k], h + offs[k] + 24)
        S.append(s - offs[k][:, None])
        E.append(e - offs[k][:, None])
    return 1 - union_measure(np.hstack(S), np.hstack(E)) / 24


# ---------------------------------------------------------------- main

def fmt_h(x):
    return f"{x:.2f}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)
    CL, DL, link_rows, rows = {}, {}, {}, []
    tgrid = np.arange(0.0, H_END + STEP / 2, STEP)[::DELAY_STRIDE]
    for tx, rx in directed_links():
        cl, st, dl = scan_link(tx, rx)
        CL[(tx, rx)] = (np.array([c[0] for c in cl]), np.array([c[1] for c in cl]))
        DL[(tx, rx)] = dl
        dur = np.array([c[1] - c[0] for c in cl if not c[3]])
        open_gaps = CL[(tx, rx)][0][1:] - CL[(tx, rx)][1][:-1]
        link_rows[(tx, rx)] = dict(
            n=len(cl), closed_frac=float(sum(c[1] - c[0] for c in cl) / H_END),
            dur_min=float(dur.min()) if len(dur) else None, dur_med=float(np.median(dur)) if len(dur) else None,
            dur_max=float(dur.max()) if len(dur) else None, min_gap=float(open_gaps.min()) if len(open_gaps) else None,
            shallowest=float(max(c[2] for c in cl)) if cl else None,
            delay_min=float(dl.min()), delay_max=float(dl.max()), **st)
        rows += [(f"{tx}->{rx}", *c) for c in cl]
        print(f"{tx:8s}->{rx:8s} closures {len(cl):4d}  closed {100 * link_rows[(tx, rx)]['closed_frac']:5.2f}%"
              f"  dur min/med/max {link_rows[(tx, rx)]['dur_min']} / {link_rows[(tx, rx)]['dur_med']} / {link_rows[(tx, rx)]['dur_max']}"
              f"  slivers {st['slivers']}  evals {st['evals']}", flush=True)
        assert link_rows[(tx, rx)]["min_gap"] is None or link_rows[(tx, rx)]["min_gap"] > 48, "two closures in one window"

    with open(OUT / "e4_closures.csv", "w") as f:
        f.write("link,start_h,end_h,duration_h,min_miss_au,censored\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]:.7f},{r[2]:.7f},{r[2] - r[1]:.7f},{r[3]:.6f},{int(r[4])}\n")

    # both relays closed at once for any settlement? (exact interval intersection)
    both = {}
    for s in SETTLEMENTS:
        worst = 0.0
        for d1, d2 in [((s, A), (s, B)), ((A, s), (B, s))]:
            s1, e1 = CL[d1]
            s2, e2 = CL[d2]
            for x0, x1 in zip(s1, e1):
                ov = np.maximum(0, np.minimum(x1, e2) - np.maximum(x0, s2))
                worst = max(worst, float(ov.max()) if len(ov) else 0.0)
        both[s] = worst

    # Tier 2: refine the first closure on an Earth link (Earth hosts Terra Capital)
    earth = sorted(((CL[l][0][i], l) for l in CL if "Earth" in l for i in range(len(CL[l][0])) if CL[l][0][i] > 0))
    t0, (tx, rx) = earth[0]
    i0 = int(np.where(CL[(tx, rx)][0] == t0)[0][0])
    bnd = refined_boundary(tx, rx, (t0, CL[(tx, rx)][1][i0]))
    bnd["closure_end"] = float(CL[(tx, rx)][1][i0])
    bnd["closure_days"] = (bnd["closure_end"] - bnd["t_close"]) / 24
    # last packet through: emitted just before t_close, its arrival and the reverse-link status for its hop receipt
    te = bnd["t_close"] - TOL
    m_last, fl = miss(tx, rx, te)
    t_arr = te + fl[0]
    receipt_emit = t_arr + 2 * SEC  # store + queue receipt, 1 s serialization (receipt queued at once)
    rev = (rx, tx)
    rev_closed = bool(is_closed(CL[rev], np.array([receipt_emit]))[0])
    j = np.searchsorted(CL[rev][1], receipt_emit)
    rev_s, rev_e = float(CL[rev][0][j]), float(CL[rev][1][j])
    bnd.update(last_emit=te, last_flight_h=float(fl[0]), last_arrival=float(t_arr), last_miss=float(m_last[0]),
               reverse_link=f"{rx} -> {tx}", reverse_closure=[rev_s, rev_e], receipt_emit=float(receipt_emit),
               receipt_blocked=rev_closed, R_h=float(2 * fl[0] + 1.0),
               offset_fwd_rev_h=rev_s - bnd["t_close"])

    # Tier 3: route delay and 24 h availability for every ordered settlement pair, windows every hour
    H = np.arange(0.0, H_END - 24 + 1e-9, 1.0)
    pair = {}
    for src in SETTLEMENTS:
        for dst in SETTLEMENTS:
            if src == dst:
                continue
            R4 = [route_eval(p, H, CL, DL, tgrid) for p in routes(src, dst)]
            delay = np.stack([r[1] for r in R4])
            opn = np.stack([r[2] for r in R4])
            avail = np.stack([route_availability(p, H, r[0], CL) for p, r in zip(routes(src, dst), R4)])
            dmask = np.where(opn, delay, np.inf)
            best = np.argmin(dmask, axis=0)
            any_open = opn.any(axis=0)
            bdelay = dmask[best, np.arange(len(H))]
            naive = avail[best, np.arange(len(H))]
            fore = avail.max(axis=0)
            pair[(src, dst)] = dict(
                never_cut=bool(any_open.all()), d_min=float(bdelay[any_open].min()), d_max=float(bdelay[any_open].max()),
                t_dmax=float(H[np.argmax(np.where(any_open, bdelay, -1))]),
                naive_min=float(naive.min()), t_naive=float(H[np.argmin(naive)]),
                fore_min=float(fore.min()), t_fore=float(H[np.argmin(fore)]),
                three_hop_share=float(np.mean(best >= 2)))
            print(f"{src:8s}->{dst:8s} delay {pair[(src, dst)]['d_min']:.2f}-{pair[(src, dst)]['d_max']:.2f} h"
                  f"  naive min {100 * pair[(src, dst)]['naive_min']:.1f}%  foresight min {100 * pair[(src, dst)]['fore_min']:.1f}%", flush=True)

    summary = dict(years=YEARS, step_h=STEP, tol_s=TOL * 3600, links={f"{a}->{b}": v for (a, b), v in link_rows.items()},
                   both_relays_closed_max_h=both, boundary=bnd,
                   pairs={f"{a}->{b}": v for (a, b), v in pair.items()})
    (OUT / "e4_summary.json").write_text(json.dumps(summary, indent=1))
    write_tex(summary)


# ---------------------------------------------------------------- LaTeX

def write_tex(S):
    L = S["links"]
    # link table: one row per settlement, both relays, both directions summarized (worse direction)
    lines = [r"\begin{tabular}{l rrrr rrrr}", r"\toprule",
             r" & \multicolumn{4}{c}{Gateway $\leftrightarrow$ Relay A} & \multicolumn{4}{c}{Gateway $\leftrightarrow$ Relay B}\\",
             r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
             r"Settlement & closures & open \% & median d & max d & closures & open \% & median d & max d\\", r"\midrule"]
    for s in SETTLEMENTS:
        cells = []
        for r in RELAYS:
            x, y = L[f"{s}->{r}"], L[f"{r}->{s}"]
            n = max(x["n"], y["n"])
            op = 100 * (1 - max(x["closed_frac"], y["closed_frac"]))
            med = max(x["dur_med"] or 0, y["dur_med"] or 0) / 24
            mx = max(x["dur_max"] or 0, y["dur_max"] or 0) / 24
            cells += [f"{n}", f"{op:.2f}", f"{med:.1f}", f"{mx:.1f}"]
        lines.append(f"{s} & " + " & ".join(cells) + r"\\")
    ab = L[f"{A}->{B}"]
    lines += [r"\midrule", f"Relay A $\\leftrightarrow$ B & \\multicolumn{{8}}{{l}}{{{ab['n']} closures; miss distance never below {ab['min_m']:.2f} AU}}\\\\",
              r"\bottomrule", r"\end{tabular}"]
    (GEN / "e4_links.tex").write_text("\n".join(lines) + "\n")

    P = S["pairs"]
    lines = [r"\begin{tabular}{l rr rr rr}", r"\toprule",
             r" & \multicolumn{2}{c}{To Ceres (referee), h} & \multicolumn{2}{c}{Any counterpart, h} & \multicolumn{2}{c}{Worst 24 h avail.\ \%}\\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
             r"From & min & max & min & max & naive pin & foresight pin\\", r"\midrule"]
    for s in SETTLEMENTS:
        out = [v for k, v in P.items() if k.startswith(s + "->")]
        c = P.get(f"{s}->Ceres")
        cer = [fmt_h(c["d_min"]), fmt_h(c["d_max"])] if c else ["local", "local"]
        lines.append(f"{s} & {cer[0]} & {cer[1]} & {fmt_h(min(v['d_min'] for v in out))} & {fmt_h(max(v['d_max'] for v in out))}"
                     f" & {100 * min(v['naive_min'] for v in out):.1f} & {100 * min(v['fore_min'] for v in out):.1f}\\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (GEN / "e4_settlements.tex").write_text("\n".join(lines) + "\n")

    b = S["boundary"]
    worst_d = max(P.items(), key=lambda kv: kv[1]["d_max"])
    worst_f = min(P.items(), key=lambda kv: kv[1]["fore_min"])
    worst_n = min(P.items(), key=lambda kv: kv[1]["naive_min"])
    allL = [v for k, v in L.items()]
    shortest = min((v["dur_min"], k) for k, v in L.items() if v["dur_min"] is not None)
    longest = max((v["dur_max"], k) for k, v in L.items() if v["dur_max"] is not None)
    mac = {
        "EfourYears": f"{S['years']:g}", "EfourStep": f"{S['step_h']:g}", "EfourTolMs": f"{S['tol_s'] * 1000:g}",
        "EfourLmax": f"{max(v['L_au_per_h'] for v in allL):.5f}", "EfourMargin": f"{max(v['grid_margin_au'] for v in allL):.5f}",
        "EfourSlivers": sum(v["slivers"] for v in allL), "EfourClosures": sum(v["n"] for v in allL),
        "EfourEvals": f"{sum(v['evals'] for v in allL):,}".replace(",", "{,}"),
        "EfourShortestH": f"{shortest[0]:.1f}", "EfourShortestLink": shortest[1].replace("->", r" $\to$ "),
        "EfourLongestD": f"{longest[0] / 24:.1f}", "EfourLongestLink": longest[1].replace("->", r" $\to$ "),
        "EfourBothClosedMaxH": f"{max(S['both_relays_closed_max_h'].values()):.2f}",
        "EfourBndLink": b["link"].replace("->", r"$\to$"), "EfourBndLo": f"{b['bracket'][0]:.0f}", "EfourBndHi": f"{b['bracket'][1]:.0f}",
        "EfourBndMlo": f"{b['m_bracket'][0]:.5f}", "EfourBndMhi": f"{b['m_bracket'][1]:.5f}",
        "EfourBndIter": b["iterations"], "EfourBndT": f"{b['t_close']:.7f}", "EfourBndWidthMs": f"{b['width_s'] * 1000:.2f}",
        "EfourBndDays": f"{b['closure_days']:.2f}", "EfourBndFlight": f"{b['last_flight_h'] * 60:.2f}",
        "EfourBndRevLink": b["reverse_link"].replace("->", r"$\to$"),
        "EfourBndRevStart": f"{b['reverse_closure'][0]:.4f}", "EfourBndRevEnd": f"{b['reverse_closure'][1]:.4f}",
        "EfourBndOffsetMin": f"{b['offset_fwd_rev_h'] * 60:.2f}", "EfourBndReceiptBlocked": "yes" if b["receipt_blocked"] else "no",
        "EfourBndRh": f"{b['R_h'] * 60:.1f}",
        "EfourWorstDelayPair": worst_d[0].replace("->", r" $\to$ "), "EfourWorstDelay": fmt_h(worst_d[1]["d_max"]),
        "EfourWorstDelayAt": f"{worst_d[1]['t_dmax']:,.0f} = year {worst_d[1]['t_dmax'] / H_YEAR:.1f}".replace(",", "{,}"),
        "EfourWorstForePair": worst_f[0].replace("->", r" $\to$ "), "EfourWorstFore": f"{100 * worst_f[1]['fore_min']:.1f}",
        "EfourWorstNaivePair": worst_n[0].replace("->", r" $\to$ "), "EfourWorstNaive": f"{100 * worst_n[1]['naive_min']:.1f}",
        "EfourWorstNaiveAt": f"{worst_n[1]['t_naive']:,.0f} = year {worst_n[1]['t_naive'] / H_YEAR:.1f}".replace(",", "{,}"),
        "EfourNeverCut": "yes" if all(v["never_cut"] for v in P.values()) else "no",
    }
    (GEN / "e4_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in mac.items()))


if __name__ == "__main__":
    main()
