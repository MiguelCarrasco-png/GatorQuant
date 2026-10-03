"""Trace simulator: packet-level conditional (no-loss) timeline plus the home-ledger balance book.

Every number in the S1-S3 / E2 / E3 evidence comes from here (runs are scripted in code/scenarios.py).

Transport (brief s4-5), implemented exactly as stated there:
  * Directed backbone links, FIFO, 1 packet/s: a packet ready at t is emitted at t_e = max(t, link free) + 1 s,
    then later still if the sender KNOWS the launch would fail (blocked photon path, or flight [t_e, t_a] overlapping a
    scheduled maintenance window). Incidents are not known: a launch emitted inside one simply fails.
  * Relay processing 1 s. Light time to the moving receiver (orbits.light_time, 1 ms).
  * Hop layer: the receiver stores the packet, queues a hop receipt on the reverse link at once and forwards the first
    copy; duplicates get a receipt but are not forwarded. R_h = 2 x flight + 60 min from t_e; at most 4 launches;
    a receipt cancels unlaunched retries only; after the 4th timeout the hop is abandoned.
  * Sessions: SYN / SYN-ACK / ACK along the pinned route and its reverse; data after SYN-ACK; the receiver releases data
    only after the final ACK. Endpoints acknowledge data (DACK). Endpoint timer R_e = 2 T0 + 24 h with T0 the
    empty-queue route delay at enqueue; at most 4 attempts for SYN, SYN-ACK and each data packet; a retry gets a new
    packet ID and discards an unlaunched earlier copy. Duplicate data is never delivered twice in one session.
  * Quota: SYN, every new data packet and every application resubmission count against the sender Branch's slice and
    the shared 600 (rolling 24 h). Receipts, SYN-ACK, ACK, DACK and automatic retries do not, but every launch is
    counted in the communication totals.
  * Random loss is removed (conditional trace). Each launch records its path length d so p = 1 - exp(-0.02 d) is
    reported next to it.

Ledger (docs/spec/value-move-protocol.md): one home ledger per Branch. A balance line is
  (owner, asset, kind) with kind 'own' (real units held on this ledger) or 'claim' (a client balance owed by this
  Branch, backed by the Branch's holding or a pending release elsewhere). Units can be free, locked (deal), reserved
  (offer) or pledged (price-contract margin). After every ledger step the omniscient check asserts:
    1. real units of each asset are conserved (sum of 'own' lines = opening totals);
    2. every claim a Branch has issued is backed by that Branch's 'own' holdings elsewhere plus releases owed to it by
       committed remote locks (pending releases); at the end of a run claims equal backing exactly (Branch equity 0);
    3. no unit serves two uses: encumbrances never exceed the line, and each lock backs at most one pending release.
"""
import heapq
import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from orbits import NODE_ID, RELAYS, light_time

SEC = 1 / 3600.0
TOL = 1e-3 / 3600.0
DEFAULT_MAINT = {frozenset(("Relay B", "Neptune")): (2.0, 26.0), frozenset(("Relay B", "Ceres")): (240.0, 264.0)}
ASSETS = ("USD", "ARES")


def fmt_h(t):
    return f"{t:.4f}"


# ======================================================================== geometry with cache

class Geometry:
    def __init__(self, maintenance=True, offset=0.0):
        self.maint = DEFAULT_MAINT if maintenance else {}
        self.offset = offset                 # E5: scenario hour h is model time offset + h (orbital phase never reset)
        self._c = {}

    def flight(self, a, b, te):
        key = (a, b, round(te, 9))
        r = self._c.get(key)
        if r is None:
            ta, d, blk = light_time(a, b, te + self.offset)
            r = (float(ta - (te + self.offset)), float(d), bool(blk))
            self._c[key] = r
        return r

    def maint_overlap(self, a, b, te, f):
        w = self.maint.get(frozenset((a, b)))
        return w if (w and te < w[1] and te + f > w[0]) else None

    def known_ok(self, a, b, te):
        f, _, blk = self.flight(a, b, te)
        return not blk and self.maint_overlap(a, b, te, f) is None

    def first_valid(self, a, b, t):
        """Earliest emission >= t the sender knows is usable. Waits out maintenance exactly and geometric closures
        to 1 ms (step 0.25 h, then bisection)."""
        te = t
        for _ in range(100_000):
            f, _, blk = self.flight(a, b, te)
            if not blk:
                w = self.maint_overlap(a, b, te, f)
                if w is None:
                    return te
                te = w[1]
                continue
            lo, hi = te, te + 0.25
            while self.flight(a, b, hi)[2]:
                lo, hi = hi, hi + 0.25
            while hi - lo > TOL:
                mid = (lo + hi) / 2
                if self.flight(a, b, mid)[2]:
                    lo = mid
                else:
                    hi = mid
            te = hi
        raise RuntimeError(f"no valid launch {a}->{b} after {t}")

    def T0(self, route, t):
        """Brief s5: flight + serialization + relay processing at enqueue geometry, empty queues, no waiting for closures."""
        tot, cur = 0.0, t
        for k in range(len(route) - 1):
            te = cur + SEC
            f, _, _ = self.flight(route[k], route[k + 1], te)
            step = SEC + f + (SEC if k < len(route) - 2 else 0.0)
            tot += step
            cur += step
        return tot

    def route_stalled(self, route, t, limit=24.0, step=0.25):
        """True if a geometric closure would hold a packet on route or its reverse more than `limit` hours at some
        hop, launching at t. Spec: nothing waits in a queue behind such a closure. Maintenance (one-time, 24 h) is
        waited out, never re-routed around."""
        for path in (route, list(reversed(route))):
            cur = t
            for k in range(len(path) - 1):
                a, b = path[k], path[k + 1]
                te = cur + SEC
                while self.flight(a, b, te)[2]:
                    te += step
                    if te - cur > limit:
                        return True
                cur = te + self.flight(a, b, te)[0] + SEC
        return False

    def route_open(self, route, t0, t1, step=0.25):
        """True if every hop of route (and its reverse) can launch throughout [t0, t1] (geometry and maintenance)."""
        for t in np.arange(t0, t1 + 1e-9, step):
            cur = float(t)
            for k in range(len(route) - 1):
                a, b = route[k], route[k + 1]
                if not self.known_ok(a, b, cur + SEC) or not self.known_ok(b, a, cur + SEC):
                    return False
                cur += SEC + self.flight(a, b, cur + SEC)[0] + SEC
        return True

    def pin_route(self, src, dst, t_open, t_cover):
        """Foresight pinning (Institutions ticket): fastest simple route (<= 3 links) that stays open in both directions
        from t_open through t_cover."""
        cands = [[src, r, dst] for r in RELAYS] + [[src, r1, r2, dst] for r1, r2 in itertools.permutations(RELAYS)]
        cands.sort(key=lambda r: self.T0(r, t_cover if t_cover < t_open + 1 else t_open))
        cands.sort(key=lambda r: self.T0(r, t_open))
        for r in cands:
            if self.route_open(r, t_open, t_cover):
                return r
        return cands[0]


# ======================================================================== incidents

@dataclass
class Incident:
    kind: str          # 'isolation' | 'forced'
    node: str
    start: float
    dur: float

    def kills(self, a, b, te):
        return self.node in (a, b) and self.start <= te < self.start + self.dur

    def label(self):
        return f"{self.dur:g} h {'isolation' if self.kind == 'isolation' else 'forced loss'} of {self.node}, h {self.start:g}-{self.start + self.dur:g}"


# ======================================================================== ledger

class Ledger:
    """All nine home ledgers, plus the omniscient conservation checker and asset-hour integrator."""

    def __init__(self, opening, branches):
        # lines[branch][(owner, asset, kind)] = {'bal': x, 'enc': {tag: amount}}
        self.lines = {b: {} for b in branches}
        self.pending = {}          # lock tag -> dict(creditor_branch, asset, amount, at_branch)
        self.opening = {a: 0.0 for a in ASSETS}
        for owner, branch, usd, ares in opening:
            if usd:
                self._line(branch, owner, "USD", "own")["bal"] += usd
            if ares:
                self._line(branch, owner, "ARES", "own")["bal"] += ares
            self.opening["USD"] += usd
            self.opening["ARES"] += ares
        self.t_last = None
        self.asset_hours = {a: 0.0 for a in ASSETS}
        self.peak = {a: (0.0, None) for a in ASSETS}
        self.enc_series = []
        self.checks = 0

    def _line(self, branch, owner, asset, kind):
        return self.lines[branch].setdefault((owner, asset, kind), {"bal": 0.0, "enc": {}})

    # ---- queries
    def free(self, branch, owner, asset, kind=None):
        tot = 0.0
        for (o, a, k), ln in self.lines[branch].items():
            if o == owner and a == asset and (kind is None or k == kind):
                tot += ln["bal"] - sum(ln["enc"].values())
        return tot

    def encumbered(self):
        out = {a: 0.0 for a in ASSETS}
        for b in self.lines.values():
            for (o, a, k), ln in b.items():
                if k == "own":
                    out[a] += sum(ln["enc"].values())
        return out

    # ---- time integration (call before each change)
    def advance(self, t):
        if self.t_last is not None and t > self.t_last:
            enc = self.encumbered()
            for a in ASSETS:
                self.asset_hours[a] += enc[a] * (t - self.t_last)
        if self.t_last is None or t >= self.t_last:
            self.t_last = t

    # ---- primitive operations
    def encumber(self, branch, owner, asset, amount, tag, kind="own"):
        ln = self._line(branch, owner, asset, kind)
        if ln["bal"] - sum(ln["enc"].values()) < amount - 1e-9:
            return False
        ln["enc"][tag] = ln["enc"].get(tag, 0.0) + amount
        return True

    def unencumber(self, branch, owner, asset, tag, kind="own"):
        ln = self._line(branch, owner, asset, kind)
        return ln["enc"].pop(tag, 0.0)

    def move(self, branch, frm, to, asset, amount, kind_from="own", kind_to="own", tag=None):
        """Move units on one ledger; if tag given, the units come out of that encumbrance."""
        a = self._line(branch, frm, asset, kind_from)
        if tag is not None:
            a["enc"][tag] = a["enc"][tag] - amount
            assert a["enc"][tag] > -1e-9
            if abs(a["enc"][tag]) < 1e-9:
                del a["enc"][tag]
        assert a["bal"] - sum(a["enc"].values()) >= amount - 1e-9 or tag is not None
        a["bal"] -= amount
        self._line(branch, to, asset, kind_to)["bal"] += amount

    def issue_claim(self, branch, owner, asset, amount):
        self._line(branch, owner, asset, "claim")["bal"] += amount

    def add_pending(self, tag, creditor, asset, amount, at_branch):
        assert tag not in self.pending, "a lock may back only one pending release"
        self.pending[tag] = dict(creditor=creditor, asset=asset, amount=amount, at=at_branch)

    def settle_pending(self, tag, amount=None):
        p = self.pending[tag]
        if amount is None or abs(amount - p["amount"]) < 1e-9:
            del self.pending[tag]
        else:
            p["amount"] -= amount

    # ---- the check
    def check(self):
        self.checks += 1
        own = {a: 0.0 for a in ASSETS}
        for b, lines in self.lines.items():
            for (o, a, k), ln in lines.items():
                enc = sum(ln["enc"].values())
                assert ln["bal"] >= -1e-6, (b, o, a, k, ln)
                assert enc <= ln["bal"] + 1e-6, f"over-encumbered {b} {o} {a}: {ln}"
                if k == "own":
                    own[a] += ln["bal"]
        for a in ASSETS:
            assert abs(own[a] - self.opening[a]) < 1e-6, f"{a} not conserved: {own[a]} vs {self.opening[a]}"
        # claims issued by Branch X = X's own holdings on other ledgers + pending releases owed to X
        for x in self.lines:
            bx = f"{x} Branch"
            for a in ASSETS:
                claims = sum(ln["bal"] for (o, aa, k), ln in self.lines[x].items() if k == "claim" and aa == a)
                held = sum(ln["bal"] for y, lines in self.lines.items() if y != x
                           for (o, aa, k), ln in lines.items() if o == bx and aa == a and k == "own")
                pend = sum(p["amount"] for p in self.pending.values() if p["creditor"] == x and p["asset"] == a)
                # no unbacked claim; a positive gap is a holding whose owner's claim is still in flight (COMMIT/SETTLE
                # not yet arrived). Branches start with nothing, so the gap must be zero again by the end of a run.
                assert claims <= held + pend + 1e-6, f"unbacked claims on {bx} {a}: {claims} > held {held} + pending {pend}"
        # every pending release is backed by a live encumbrance of at least its amount
        for tag, p in self.pending.items():
            enc = sum(ln["enc"].get(tag, 0.0) for ln in self.lines[p["at"]].values())
            assert enc >= p["amount"] - 1e-6, f"pending {tag} not backed: {enc} < {p['amount']}"
        enc = self.encumbered()
        for a in ASSETS:
            if enc[a] > self.peak[a][0] + 1e-9:
                self.peak[a] = (enc[a], self.t_last)
        self.enc_series.append((self.t_last, enc["USD"], enc["ARES"]))

    def snapshot(self):
        """Non-zero lines, for the E3 tables."""
        out = []
        for b, lines in self.lines.items():
            for (o, a, k), ln in lines.items():
                if abs(ln["bal"]) > 1e-9:
                    out.append(dict(branch=b, owner=o, asset=a, kind=k, bal=ln["bal"],
                                    enc={t: v for t, v in ln["enc"].items() if v > 1e-9}))
        return out


# ======================================================================== transport

_ids = itertools.count(1)


@dataclass
class Packet:
    kind: str                  # SYN SYNACK ACK DATA DACK
    session: "Session"
    src: str                   # endpoint node
    dst: str
    route: list
    seq: int = 0               # session data sequence (DATA / DACK)
    records: list = field(default_factory=list)
    attempt: int = 1
    created: float = 0.0
    pid: int = field(default_factory=lambda: next(_ids))
    discarded: bool = False
    first_launched: bool = False
    label: str = ""
    row: dict = None


class Session:
    _sid = itertools.count(1)

    def __init__(self, sim, a, b, route):
        self.sim, self.a, self.b = sim, a, b          # a = initiator of the handshake
        self.route = route                             # a -> b
        self.sid = next(Session._sid)
        self.state = {a: "closed", b: "closed"}
        self.next_seq = {a: 0, b: 0}
        self.delivered = {a: set(), b: set()}
        self.unacked = {a: {}, b: {}}                 # seq -> packet (latest attempt)
        self.buffer = {a: [], b: []}                  # data received before final ACK
        self.outbox = {a: [], b: []}                  # app records waiting for establishment
        self.last_rx = {a: None, b: None}
        self.rx_times = {a: [], b: []}
        self.max_unacked = 0
        self.established_at = None
        self.retired = None                            # time a replacement session took over this pair

    def path(self, frm):
        return self.route if frm == self.a else list(reversed(self.route))

    def peer(self, x):
        return self.b if x == self.a else self.a


class Sim:
    def __init__(self, maintenance=True, incident=None, opening=(), branches=(), offset=0.0):
        self.geo = Geometry(maintenance, offset)
        self.incident = incident
        self.q = []
        self.ctr = itertools.count()
        self.link_free = {}
        self.link_busy = {}            # link -> list of (ready, te)
        self.hops = {}                 # (pid, a, b) -> state
        self.stored = {}               # (pid, node) seen
        self.log = []                  # every event row
        self.launches = []             # every launch
        self.originated = []           # (t, branch, what)
        self.ledger = Ledger(opening, branches)
        self.sessions = {}
        self.apps = {}                 # node -> callable(sim, t, session, records)
        self.trace = []                # compact trace rows
        self.snaps = [(0.0, self.ledger.snapshot())]
        self.now = -1e9

    # ---- event loop
    def at(self, t, fn, *args, order=99):
        heapq.heappush(self.q, (t, order, next(self.ctr), fn, args))

    def run(self, until=1e9):
        while self.q and self.q[0][0] <= until:
            t, _, _, fn, args = heapq.heappop(self.q)
            self.now = t
            fn(t, *args)

    # ---- logging
    def ev(self, t, actor, what, **kw):
        self.log.append(dict(t=t, actor=actor, what=what, **kw))

    def row(self, t, actor, know, action, packet="", arrival="", state=""):
        self.trace.append(dict(t=t, actor=actor, know=know, action=action, packet=packet, arrival=arrival, state=state))

    def originate(self, t, branch, what):
        self.originated.append((t, branch, what))

    # ---- ledger step wrapper
    def book(self, t, fn):
        self.ledger.advance(t)
        r = fn(self.ledger)
        self.ledger.check()
        self.snaps.append((t, self.ledger.snapshot()))
        return r

    # ---- hop layer
    def hop_send(self, t_ready, pkt, k):
        """Forward pkt from route[k] to route[k+1]; ready at t_ready."""
        a, b = pkt.route[k], pkt.route[k + 1]
        st = self.hops.setdefault((pkt.pid, a, b), dict(launches=0, receipt=False, abandoned=False, k=k))
        self._launch(t_ready, pkt, a, b, st)

    def _launch(self, t_ready, pkt, a, b, st):
        link = (a, b)
        start = max(t_ready, self.link_free.get(link, -1e9))
        te = self.geo.first_valid(a, b, start + SEC)
        self.link_free[link] = te
        self.link_busy.setdefault(link, []).append((t_ready, te))
        self.at(te, self._emit, pkt, a, b, st, t_ready, order=NODE_ID[a])

    def _emit(self, te, pkt, a, b, st, t_ready):
        if st["receipt"]:
            return                                       # late receipt cancelled this unlaunched retry
        if pkt.discarded and a == pkt.src and not pkt.first_launched:
            self.ev(te, a, "discard", pid=pkt.pid, kind=pkt.kind, link=f"{a}->{b}")
            return
        if a == pkt.src:
            pkt.first_launched = True
        f, d, _ = self.geo.flight(a, b, te)
        st["launches"] += 1
        failed = bool(self.incident and self.incident.kills(a, b, te))
        rec = dict(t=te, link=f"{a}->{b}", kind=pkt.kind, pid=pkt.pid, n=st["launches"], flight=f, d=d,
                   p_loss=1 - math.exp(-0.02 * d), arrival=None if failed else te + f, failed=failed,
                   session=pkt.session.sid, wait=te - t_ready - SEC, label=pkt.label)
        self.launches.append(rec)
        st.setdefault("launch_log", []).append(rec)
        self.ev(te, a, "launch", **{k: v for k, v in rec.items() if k != "t"})
        if not failed:
            self.at(te + f, self._arrive, pkt, a, b, order=NODE_ID[a])
        R_h = 2 * f + 1.0
        self.at(te + R_h, self._hop_timer, pkt, a, b, st)

    def _hop_timer(self, t, pkt, a, b, st):
        if st["receipt"] or st["abandoned"]:
            return
        if st["launches"] >= 4:
            st["abandoned"] = True
            self.ev(t, a, "hop abandoned", pid=pkt.pid, kind=pkt.kind, link=f"{a}->{b}")
            return
        self._launch(t, pkt, a, b, st)

    def _arrive(self, t, pkt, a, b):
        self.ev(t, b, "arrive", pid=pkt.pid, kind=pkt.kind, link=f"{a}->{b}")
        # hop receipt on the reverse link, at once (one-shot, no receipt of its own)
        self._send_receipt(t, pkt, b, a)
        key = (pkt.pid, b)
        if key in self.stored:
            return
        self.stored[key] = t
        k = pkt.route.index(b)
        if b == pkt.dst:
            self.endpoint_rx(t, pkt)
        else:
            self.hop_send(t + SEC, pkt, k)              # relay processing 1 s

    def _send_receipt(self, t_ready, pkt, frm, to):
        link = (frm, to)
        start = max(t_ready, self.link_free.get(link, -1e9))
        te = self.geo.first_valid(frm, to, start + SEC)
        self.link_free[link] = te
        self.link_busy.setdefault(link, []).append((t_ready, te))

        def emit(te_):
            f, d, _ = self.geo.flight(frm, to, te_)
            failed = bool(self.incident and self.incident.kills(frm, to, te_))
            rec = dict(t=te_, link=f"{frm}->{to}", kind="RCPT", pid=pkt.pid, n=1, flight=f, d=d,
                       p_loss=1 - math.exp(-0.02 * d), arrival=None if failed else te_ + f, failed=failed,
                       session=pkt.session.sid, wait=te_ - t_ready - SEC, label=f"receipt {pkt.label}")
            self.launches.append(rec)
            self.ev(te_, frm, "launch", **{k: v for k, v in rec.items() if k != "t"})
            if not failed:
                st = self.hops.get((pkt.pid, to, frm))
                self.at(te_ + f, self._receipt_in, st, pkt, to, frm, order=NODE_ID[frm])

        self.at(te, emit, order=NODE_ID[frm])

    def _receipt_in(self, t, st, pkt, to, frm):
        if st is not None and not st["receipt"]:
            st["receipt"] = True
            st["receipt_at"] = t
        self.ev(t, to, "receipt", pid=pkt.pid, link=f"{frm}->{to}")

    # ---- endpoint layer
    def open_session(self, t, a, b, route, know=None, state="No financial state (h < 0)"):
        old = self.sessions.get((a, b))
        if old is not None:
            old.retired = t
        s = Session(self, a, b, route)
        self.sessions[(a, b)] = self.sessions[(b, a)] = s
        s.opened = t
        s.state[a] = "syn-sent"
        self._ep_send(t, s, a, "SYN", attempt=1, quota=True, label=f"SYN {a}-{b}")
        self.row(t, f"{a} Branch", know or f"Plans to trade with {b}; knows geometry and maintenance",
                 f"Sends SYN toward {b}", self._route_txt(route), "", state)
        return s

    def _route_txt(self, route):
        return " $\\to$ ".join(r.replace("Relay ", "") for r in route)

    def _ep_send(self, t, s, frm, kind, attempt=1, quota=False, seq=0, records=None, label="", prev=None):
        to = s.peer(frm)
        route = s.path(frm)
        pkt = Packet(kind, s, frm, to, route, seq=seq, records=records or [], attempt=attempt, created=t, label=label)
        if prev is not None:
            prev.discarded = True
            pkt.created = prev.created
            pkt.row = prev.row
        if quota:
            self.originate(t, frm, label)
        self.ev(t, frm, "enqueue", pid=pkt.pid, kind=kind, attempt=attempt, label=label)
        self.hop_send(t, pkt, 0)
        if kind in ("SYN", "SYNACK", "DATA"):
            R_e = 2 * self.geo.T0(route, t) + 24.0
            pkt.R_e = R_e
            self.at(t + R_e, self._ep_timer, s, frm, pkt)
            if kind == "DATA":
                s.unacked[frm][seq] = pkt
                s.max_unacked = max(s.max_unacked, len(s.unacked[frm]))
                assert len(s.unacked[frm]) <= 64
        return pkt

    def _ep_timer(self, t, s, frm, pkt):
        done = {"SYN": s.state[frm] != "syn-sent",
                "SYNACK": s.state[frm] == "established",
                "DATA": pkt.seq not in s.unacked[frm] or s.unacked[frm][pkt.seq] is not pkt}[pkt.kind]
        if done:
            return
        if pkt.attempt >= 4:
            self.ev(t, frm, "endpoint attempts exhausted: status unknown", kind=pkt.kind, seq=pkt.seq, label=pkt.label)
            if pkt.kind == "DATA":
                del s.unacked[frm][pkt.seq]
            app = self.apps.get(frm)
            if app and hasattr(app, "on_unknown"):
                app.on_unknown(self, t, s, pkt)
            return
        self.ev(t, frm, "endpoint retry", kind=pkt.kind, attempt=pkt.attempt + 1, label=pkt.label)
        if pkt.kind == "DATA" and pkt.row is not None:
            self.row(t, f"{frm} Branch", f"No data ACK for {pkt.label} within R\\textsubscript{{e}}",
                     f"Endpoint attempt {pkt.attempt + 1} of {pkt.label}",
                     f"attempt {pkt.attempt}: " + (self._hops_txt(pkt) or "not yet launched"), "lost", "unchanged")
        return self._ep_send(t, s, frm, pkt.kind, attempt=pkt.attempt + 1, seq=pkt.seq, records=pkt.records,
                      label=pkt.label, prev=pkt)

    def send_data(self, t, branch, peer, records, label, resubmission=False):
        """Application hands records to the transport; one packet (<= 14 records). Counts against the quota."""
        s = self.sessions[(branch, peer)]
        assert len(records) <= 14
        if s.state[branch] != "established":
            s.outbox[branch].append((records, label))
            return None
        seq = s.next_seq[branch]
        s.next_seq[branch] += 1
        return self._ep_send(t, s, branch, "DATA", quota=True, seq=seq, records=records, label=label)

    def endpoint_rx(self, t, pkt):
        s, me = pkt.session, pkt.dst
        s.last_rx[me] = t
        s.rx_times[me].append(t)
        k = pkt.kind
        if k == "SYN":
            if s.state[me] == "closed":
                s.state[me] = "synack-sent"
                s._synack = self._ep_send(t, s, me, "SYNACK", label=f"SYN-ACK {me}-{pkt.src}")
            elif s.state[me] == "synack-sent" and s._synack.attempt < 4:
                s._synack = self._ep_send(t, s, me, "SYNACK", attempt=s._synack.attempt + 1, label=s._synack.label,
                                          prev=s._synack)
        elif k == "SYNACK":
            if s.state[me] in ("syn-sent", "data-ok", "established"):
                if s.state[me] == "syn-sent":
                    s.state[me] = "established"
                self._ep_send(t, s, me, "ACK", label=f"ACK {me}-{pkt.src}")
                self._flush(t, s, me)
        elif k == "ACK":
            if s.state[me] != "established":
                s.state[me] = "established"
                s.established_at = t
                for p in s.buffer[me]:
                    self._deliver(t, p)
                s.buffer[me] = []
                self._flush(t, s, me)
        elif k == "DATA":
            if s.state[me] != "established":
                s.buffer[me].append(pkt)
            else:
                self._deliver(t, pkt)
            self._ep_send(t, s, me, "DACK", seq=pkt.seq, label=f"DACK {pkt.label}")
        elif k == "DACK":
            cur = s.unacked[me].get(pkt.seq)
            if cur is not None:
                del s.unacked[me][pkt.seq]
                self.ev(t, me, "data acknowledged", seq=pkt.seq, label=cur.label)

    def _flush(self, t, s, me):
        box, s.outbox[me] = s.outbox[me], []
        for records, label in box:
            self.send_data(t, me, s.peer(me), records, label)

    def _deliver(self, t, pkt):
        s, me = pkt.session, pkt.dst
        if pkt.seq in s.delivered[me]:
            return
        s.delivered[me].add(pkt.seq)
        self.ev(t, me, "deliver", seq=pkt.seq, label=pkt.label)
        if pkt.row is not None and not pkt.row["arrival"]:
            pkt.row["arrival"] = f"h {t:.4f}"
            pkt.row["packet"] += "; " + self._hops_txt(pkt)
        app = self.apps.get(me)
        if app:
            app.on_records(self, t, s, pkt)

    def _hops_txt(self, pkt):
        parts = []
        for k in range(len(pkt.route) - 1):
            a, b = pkt.route[k], pkt.route[k + 1]
            st = self.hops.get((pkt.pid, a, b))
            if not st or "launch_log" not in st:
                continue
            ts = ", ".join(f"{L['t']:.4f}" + (" lost" if L["failed"] else "") for L in st["launch_log"])
            parts.append(a.replace("Relay ", "") + r"$\to$" + b.replace("Relay ", "") + f" h {ts}")
        return "; ".join(parts)

    # ---- summaries
    def hop_summary(self, pid_label):
        """Launch / receipt detail for one endpoint message, for the compact trace."""
        out = []
        for (pid, a, b), st in self.hops.items():
            if pid in pid_label:
                out.append((pid, a, b, st))
        return out

    def quota_peaks(self):
        """Peak originated packets in any rolling 24 h window: system-wide and per Branch."""
        ts = sorted(self.originated)

        def peak(times):
            times = sorted(times)
            best, j = 0, 0
            for i in range(len(times)):
                while times[i] - times[j] >= 24.0:
                    j += 1
                best = max(best, i - j + 1)
            return best
        per = {}
        for t, b, _ in ts:
            per.setdefault(b, []).append(t)
        return peak([t for t, _, _ in ts]), {b: peak(v) for b, v in per.items()}

    def queue_peak(self):
        best = 0
        for link, iv in self.link_busy.items():
            evs = sorted([(r, 1) for r, _ in iv] + [(e, -1) for _, e in iv], key=lambda x: (x[0], x[1]))
            cur = 0
            for _, d in evs:
                cur += d
                best = max(best, cur)
        return best
