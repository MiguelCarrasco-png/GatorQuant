"""S2 incident ranking (ticket: S2 incident - which kind, node and start time hurts most).

Question: in the S2 run (FF = falling path, settles h 288) which single brief-Section-5 incident does the most damage?
Damage is measured on the one financial step an incident can delay: the SETTLE that releases Callisto's pledged
$75,000 at Jupiter after the h 288 settling print at Ceres (docs/spec/value-move-protocol.md section 6), plus, for an
isolation at the very start, the delay in opening the position.

Model (conditional no-loss trace; geometry, maintenance, timers, retries and incidents all apply):
  * One pinned Ceres<->Jupiter session. Route = fastest simple route open at the time (Relay B; checked below).
  * Hop rules (brief s5): launch emission t_e = ready + 1 s; relay adds 1 s; R_h = 2*flight + 60 min; <= 4 launches per hop,
    a hop attempt is used only when the packet actually launches. A sender WAITS for known closures (geometry or
    maintenance overlap) but cannot know about an incident, so a launch emitted inside an incident window fails and still
    uses an attempt.
  * Endpoint rules: R_e = 2*T0 + 24 h with T0 = empty-queue one-way route delay at enqueue; <= 4 endpoint attempts per data
    packet; an attempt that is abandoned by the hop layer simply ends.
  * Application rule from the locked spec: the referee sends SETTLE once, at the print; the pledge holder, if it still holds
    the lock after print + R_e, resubmits its LOCK (we repeat every R_e: "no cap on tries") and the referee answers with
    the recorded SETTLE.
  * Incident = launch-time predicate: fails if t_e in [s, s+D) and the named node is an endpoint of the link. Packets already
    in flight are unaffected (brief). Endpoint reset: durable records survive, sessions die, one SYN per new session.

Outputs: code/out/s2_incident.json (+ latex/generated/s2_incident.tex)
Run: python code/s2_incident.py
"""
import json
from pathlib import Path

import numpy as np

from orbits import light_time

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "code" / "out"
GEN = ROOT / "latex" / "generated"

SEC = 1 / 3600
MAINT = {frozenset(("Relay B", "Neptune")): (2.0, 26.0), frozenset(("Relay B", "Ceres")): (240.0, 264.0)}
PROBE_H = 2.4             # R8': resubmission pace (24 h / recovery reserve of 10)
SETTLE_H = 288.0           # settling print
OPEN_H = 0.0               # both orders at h 0
SHORT_WINS = 57_500.0      # FF: Ceres Iron Works (short) wins Y = 25*100*(100-77)
LOCK = 75_000.0
REFUND = LOCK - SHORT_WINS  # 17,500 back to Callisto


class Incident:
    def __init__(self, kind, node, start, dur=None):
        self.kind, self.node, self.s = kind, node, start
        self.dur = dur if dur is not None else {"isolation": 72.0, "forced": 6.0, "reset": 0.0}[kind]

    def kills(self, a, b, te):
        return self.kind != "reset" and self.node in (a, b) and self.s <= te < self.s + self.dur

    def __repr__(self):
        return f"{self.kind}@{self.node} s={self.s:.2f} D={self.dur:g}"


def flight(a, b, te):
    ta, _, blk = light_time(a, b, te)
    return float(ta - te), bool(blk)


def known_ok(a, b, te):
    f, blk = flight(a, b, te)
    if blk:
        return False
    w = MAINT.get(frozenset((a, b)))
    return not (w and te < w[1] and te + f > w[0])


def first_valid(a, b, ready):
    """Earliest emission >= ready+1 s that the sender knows is usable (waits out geometry and maintenance)."""
    te = ready + SEC
    steps = 0
    while not known_ok(a, b, te):
        te += 0.01
        steps += 1
        if steps > 200_000:
            return None
    return te


def hop(a, b, ready, inc):
    """Move one packet across hop a->b. Returns (arrival, launches_used) or (None, launches_used) if abandoned."""
    used = 0
    t = ready
    while used < 4:
        te = first_valid(a, b, t)
        if te is None:
            return None, used
        f, _ = flight(a, b, te)
        used += 1
        if not (inc and inc.kills(a, b, te)):
            return te + f, used
        t = te + 2 * f + 1.0  # R_h expires, next copy ready
    return None, used


def deliver(route, ready, inc):
    """One endpoint attempt along a route. Returns arrival at destination or None."""
    t = ready
    for k in range(len(route) - 1):
        arr, _ = hop(route[k], route[k + 1], t, inc)
        if arr is None:
            return None
        t = arr + (1 * SEC if k < len(route) - 2 else 0.0)  # relay processing
    return t


def T0(route, t):
    tot = 0.0
    for k in range(len(route) - 1):
        te = t + SEC
        f, _ = flight(route[k], route[k + 1], te)
        tot += SEC + f + (SEC if k < len(route) - 2 else 0)
        t = te + f
    return tot


def endpoint_send(route, enq, inc, max_att=4):
    """Data packet with endpoint retries. Returns (arrival, attempt_index, [attempt enqueue times])."""
    e, times = enq, []
    for i in range(max_att):
        times.append(e)
        arr = deliver(route, e, inc)
        if arr is not None:
            return arr, i, times
        e += 2 * T0(route, e) + 24.0
    return None, None, times


def pick_route(a, b, t):
    cands = [[a, "Relay A", b], [a, "Relay B", b], [a, "Relay A", "Relay B", b], [a, "Relay B", "Relay A", b]]
    best = min(cands, key=lambda r: deliver(r, t, None) or 1e18)
    return best


def release_time(inc, start=SETTLE_H, ref="Ceres", holder="Jupiter", route=None, probes=True, failover=None):
    """Hour at which the pledge holder first holds SETTLE (financial service resumed for the loser). Returns (t, how)."""
    route = route or pick_route(ref, holder, start)
    back = list(reversed(route))
    best, how = None, None
    if inc and inc.kind == "reset" and inc.node == ref and inc.s <= start:
        # referee lost its sessions; it knows, handshakes anew (SYN, SYN-ACK, then data right after the SYN-ACK)
        t_ready = max(start, inc.s + 2 * T0(route, inc.s))
        arr = deliver(route, t_ready, None)
        return arr, "referee re-handshake"
    if inc and inc.kind == "reset" and inc.node == holder:
        a0 = deliver(route, start, None)
        if inc.s <= a0:  # reset before the first copy lands: it is ignored; dead session
            # holder re-handshakes and pulls with LOCK; referee answers
            t_hs = inc.s + 2 * T0(back, inc.s)
            lock_arr = deliver(back, t_hs, None)
            arr = deliver(route, lock_arr, None)
            return arr, "holder re-handshake + pull"
        return a0, "unaffected"
    if inc and inc.kind == "reset":
        return deliver(route, start, None), "unaffected"
    arr, i, _ = endpoint_send(route, start, inc)
    if arr is not None:
        best, how = arr, f"referee SETTLE attempt {i + 1}"
    if failover:  # extra pre-opened session on the other relay, used when the hop layer abandons
        alt = failover
        # referee learns its own hop was abandoned only after 4 hop launches; model: all 4 hop timers expire
        t_giveup = start
        for _ in range(4):
            te = first_valid(route[0], route[1], t_giveup)
            f, _ = flight(route[0], route[1], te)
            t_giveup = te + 2 * f + 1.0
        a2 = deliver(alt, t_giveup, inc)
        if a2 is not None and (best is None or a2 < best):
            best, how = a2, "failover on second session"
    if probes:
        # R8': after print + R_e the holder resubmits every PROBE_H (the pace its recovery reserve affords), each
        # resubmission being a fresh data packet with its own four endpoint attempts.
        p = start + 2 * T0(back, start) + 24.0  # print + R_e
        k = 0
        while k < 60 and (best is None or p < best):
            la, _, _ = endpoint_send(back, p, inc)
            if la is not None:
                ra, _, _ = endpoint_send(route, la, inc)
                if ra is not None and (best is None or ra < best):
                    best, how = ra, f"holder resubmission #{k + 1}"
            p += PROBE_H
            k += 1
    return best, how


def open_time(inc, holder="Jupiter", ref="Ceres", route=None):
    """Hour at which the referee records the position (COMMIT at the referee). LOCK from the holder, resubmitted on R_e."""
    route = route or pick_route(holder, ref, OPEN_H)
    base, _, _ = endpoint_send(route, OPEN_H + SEC, None)
    arr, _, _ = endpoint_send(route, OPEN_H + SEC, inc)
    p = OPEN_H + SEC + 2 * T0(route, OPEN_H + SEC) + 24.0
    k = 0
    while k < 60 and (arr is None or p < arr):   # R8': the holder resubmits every PROBE_H after one R_e
        a, _, _ = endpoint_send(route, p, inc)
        if a is not None and (arr is None or a < arr):
            arr = a
        p += PROBE_H
        k += 1
    return base, arr


def scan(kind, node, starts, dur=None, **kw):
    out = []
    for s in starts:
        inc = Incident(kind, node, float(s), dur)
        t, how = release_time(inc, **kw)
        out.append((float(s), t, how))
    return out


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    route = pick_route("Ceres", "Jupiter", SETTLE_H)
    base_t = release_time(None)[0]
    t0 = T0(route, SETTLE_H)
    print("route", route, "base release", base_t, "T0", t0, "R_e", 2 * t0 + 24)
    res = {"route": route, "baseline_release_h": base_t, "T0_h": t0, "R_e_h": 2 * t0 + 24, "scans": {}}

    grid = np.arange(240.0, 300.01, 0.5)
    cases = [("isolation", "Ceres"), ("isolation", "Jupiter"), ("isolation", "Relay B"),
             ("forced", "Relay B"), ("forced", "Relay A"), ("forced", "Ceres"), ("forced", "Jupiter"),
             ("reset", "Ceres"), ("reset", "Jupiter")]
    for kind, node in cases:
        if kind == "isolation" and node.startswith("Relay"):
            continue
        g = grid if kind != "reset" else np.arange(280.0, 296.01, 0.05)
        rows = scan(kind, node, g)
        worst = max(rows, key=lambda r: (r[1] if r[1] is not None else 1e9))
        plateau = [r[0] for r in rows if r[1] is not None and abs(r[1] - worst[1]) < 0.05]
        res["scans"][f"{kind}@{node}"] = dict(worst_start=worst[0], worst_release=worst[1], how=worst[2],
                                              delay_h=worst[1] - base_t, plateau=[min(plateau), max(plateau)])
        print(f"{kind:9s} {node:8s} worst s={worst[0]:7.2f} release={worst[1]:8.3f}  delay={worst[1] - base_t:7.3f}  "
              f"plateau [{min(plateau):.2f},{max(plateau):.2f}]  via {worst[2]}")

    # ---- ranking table: lost-service hours and extra NeoDollar-hours encumbered versus the FF run with no incident
    alt = ["Ceres", "Relay A", "Jupiter"]
    sc = res["scans"]
    open_base, open_iso = open_time(Incident("isolation", "Ceres", 0.0))
    _, open_forced = open_time(Incident("forced", "Relay B", 0.0))
    rows = []

    def add(name, hours, locked, note):
        rows.append(dict(name=name, lost_h=hours, extra_dollar_h=hours * locked, locked=locked, note=note))

    d = sc["isolation@Ceres"]["delay_h"]
    add("72 h isolation, Ceres or Jupiter, over the h 288 print", d, LOCK, "pledge $75,000 held after outcome known")
    add("72 h isolation, Ceres or Jupiter, from h 0 (opening)", open_iso - open_base, 2 * LOCK,
        "both margins idle, no position yet")
    add("6 h forced loss, pinned relay or either gateway, at the print", sc["forced@Relay B"]["delay_h"], LOCK,
        "all 4 hop launches die; next endpoint attempt")
    add("Endpoint reset, Jupiter, as SETTLE lands", sc["reset@Jupiter"]["delay_h"], LOCK, "re-handshake and pull")
    add("Endpoint reset, Ceres, as SETTLE is queued", sc["reset@Ceres"]["delay_h"], LOCK, "re-handshake, then send")
    res["ranking"] = rows
    chosen = Incident("isolation", "Ceres", 286.0)
    t_rel, how = release_time(chosen)
    res["chosen"] = dict(kind="isolation", node="Ceres", start_h=286.0, end_h=358.0, release_h=t_rel, how=how,
                         baseline_release_h=base_t, lost_service_h=t_rel - base_t,
                         asset_hours_extra=LOCK * (t_rel - base_t), refund_stuck=REFUND,
                         endpoint_attempts_h=endpoint_send(route, SETTLE_H, chosen)[2],
                         with_second_session=release_time(chosen, failover=alt)[0],
                         relayB_forced_with_second_session=release_time(Incident("forced", "Relay B", 287.5), failover=alt)[0])
    print("chosen", res["chosen"])
    json.dump(res, open(OUT / "s2_incident.json", "w"), indent=2)
    GEN.mkdir(parents=True, exist_ok=True)
    B = "\\"
    L = [B + "begin{tabular}{p{7.3cm} rr}", B + "toprule",
         "Incident & lost-service h & extra " + B + "$-hours locked" + B + B, B + "midrule"]
    for r in sorted(rows, key=lambda r: -r["lost_h"]):
        L.append(f"{r['name']} & {r['lost_h']:.1f} & " + f"{r['extra_dollar_h']:,.0f}".replace(",", "{,}") + B + B)
    L += [B + "bottomrule", B + "end{tabular}"]
    (GEN / "s2_incident.tex").write_text(chr(10).join(L) + chr(10))
