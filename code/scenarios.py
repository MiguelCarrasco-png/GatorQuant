"""The 16 declared runs of the Scenario plan, driven through the trace simulator (code/sim.py).

Runs (each a declared reset of the opening balance sheet; orbital phase never reset):
  VM, FR, FF, FR-cap, S2, VM@Ceres, VM@Venus, VM@Uranus, noMaint-{VM,FR,FF,S2}, Hub-{VM,VM@Ceres,VM@Venus,VM@Uranus}
Application rules: docs/spec/value-move-protocol.md; terms: Ceres Iron future ticket; sessions/quota: Institutions ticket.

Outputs: code/out/sim/<run>.json + <run>_events.csv, code/out/sim/summary.json, latex/generated/sim_*.tex
Run: python code/scenarios.py
"""
import csv
import json
import sys
from pathlib import Path

from sim import SEC, Incident, Sim, Stack

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "code" / "out" / "sim"
GEN = ROOT / "latex" / "generated"

BRANCHES = ["Mercury", "Venus", "Earth", "Mars", "Ceres", "Jupiter", "Saturn", "Uranus", "Neptune"]
OPENING = [  # owner, settlement, NeoDollars, Ares shares
    ("Terra Capital", "Earth", 150_000, 0),
    ("Ares Habitat Treasury", "Mars", 40_000, 3_000),
    ("Ceres Iron Works", "Ceres", 85_000, 0),
    ("Callisto Foundry", "Jupiter", 85_000, 0),
    ("Triton Fund", "Neptune", 100_000, 1_000),
    ("Helios Traders", "Mercury", 40_000, 1_000),
]
OPEN_SESSIONS_H = -72.0

# Value move: Terra buys 200 Ares from Triton's firm offer at $125 (delivery vs payment)
VM_SHARES, VM_PRICE, VM_OFFER_EXPIRY = 200, 125, 96.0
VM_CASH = VM_SHARES * VM_PRICE

# Ceres Iron capped future
ENTRY, MULT, CONTRACTS, CAP = 100.0, 100, 25, 0.30
MARGIN = CAP * ENTRY * MULT * CONTRACTS                  # 75,000 per side
PRINT_HOURS = [24 * k for k in range(13)]                # 0 .. 288
SETTLE_H, FREEZE_H, FUT_OFFER_EXPIRY = 288.0, 264.0, 48.0
RISING = [100, 103, 107, 111, 115, 118, 121, 124, 126, 125, 124, 124, 123]
FALLING = [100, 97, 93, 89, 85, 82, 79, 76, 74, 75, 76, 76, 77]
CAPPED = RISING[:-1] + [140]
KEEPALIVE_IDLE = 120.0
RESERVE_PER_DAY = 10                                     # recovery reserve of one Branch slice (packets / 24 h)
PROBE_H = 24.0 / RESERVE_PER_DAY                         # R8': resubmission pace once status is unknown, 2.4 h
VOID_GRACE_H = 24.0                                      # R21 [EXTENSION]: referee voids a contract 24 h after a missing settling print
REPLY_GAP_H = 1.0                                        # R8': a decided answer is repeated at most once an hour
CONTACT_GAP_H = 1.0                                      # R8': resubmit on contact at most once per hour
AUDIT_ON = True                                          # R20 [EXTENSION]: echo check and SETTLE recompute
PROBE_ON = True                                          # False reproduces the superseded timer-only rule


def money(x):
    return f"\\${x:,.0f}".replace(",", "{,}")



TERM_KEYS = ("deal", "offer", "product", "shares", "price", "cash", "contracts", "margin", "buyer")


def echo_ok(lock_rec, r):
    """R20: a reply must echo the LOCK's terms exactly (spec section 2)."""
    return all(r.get(k) == lock_rec.get(k) for k in TERM_KEYS if k in lock_rec and k != "price") and (
        lock_rec.get("product") != "share" or r.get("price") == lock_rec.get("price"))


def payoff_of(print_value):
    clipped = min(max(print_value, ENTRY * (1 - CAP)), ENTRY * (1 + CAP))
    y = CONTRACTS * MULT * (clipped - ENTRY)
    return clipped, y


def settle_ok(r):
    """R20 audit: the lock holder recomputes the payoff from the signed settling print in the SETTLE record."""
    if r.get("void"):                                    # R21: no settling print; every margin returns in full
        return r["release"] == 0 and r["credit"] == 0
    clipped, y = payoff_of(r["price"])
    Y = abs(y)
    rel, credit = (Y, 0.0) if y < 0 else (0.0, Y)
    return abs(r["release"] - rel) < 1e-6 and abs(r["credit"] - credit) < 1e-6 and abs(r["clipped"] - clipped) < 1e-9

# ======================================================================== applications

class Branch:
    """One Branch's application: home-ledger actions and record handling (protocol sections 3, 4, 6)."""

    def __init__(self, w, name):
        self.w, self.name = w, name
        self.decisions = {}     # deal -> recorded answer record (deciding / referee side)
        self.locks = {}         # deal -> dict (initiator / pledge-holder side)
        self.offers = {}        # offer id -> dict
        self.last_reply = {}    # deal -> hour the recorded answer was last sent
        self.errors = []        # detected protocol errors: (t, deal, what)
        self.decided_n = {}     # deal -> number of decisions recorded (must stay 1)

    @property
    def me(self):
        return f"{self.name} Branch"

    # ---------------- records arriving
    def on_records(self, sim, t, s, pkt):
        """Handle every record of one arriving packet; the replies it provokes to the same peer share packets
        (up to 14 records each), as the batching rule says."""
        w = self.w
        outer = w._batch
        w._batch = {}
        for r in pkt.records:
            getattr(self, "rx_" + r["type"])(sim, t, s.peer(self.name), r, pkt)
        pending, w._batch = w._batch, outer
        for (frm, to), items in pending.items():
            for k in range(0, len(items), 14):
                chunk = items[k:k + 14]
                first = chunk[0]
                w.send(t, frm, to, [c[0] for c in chunk], first[1], **first[2])

    def on_unknown(self, sim, t, s, pkt):
        """Endpoint attempts ran out with status unknown. Recovery is the lock holder's probe loop (arm / _probe), so
        this only logs. Deciding and referee Branches never resend on their own."""
        self.w.sim.ev(t, self.name, "status unknown", label=pkt.label)
        if not PROBE_ON:
            lock = next((r for r in pkt.records if r["type"] == "LOCK"), None)
            if lock is None or self.locks.get(lock["deal"], {}).get("state") not in ("locked", "pledged"):
                return
            self.w.send(t, self.name, s.peer(self.name), [dict(lock, flags="RESUBMISSION")],
                        f"LOCK {lock['deal']} (resub)",
                        know=f"{pkt.label}: 4 endpoint attempts, status unknown; still holds the lock",
                        action="Resubmits LOCK unchanged (recovery reserve)", state="unchanged", resub=True)

    # ---------------- lock holder's recovery (R8 and R8')
    def arm(self, t, deal, peer, rec):
        """Called when a lock is created. After one endpoint timer R_e with no recorded answer the holder starts to
        resubmit, every PROBE_H (the pace the recovery reserve affords) until the deal ends, and also at once on any
        packet from the peer (at most one per CONTACT_GAP_H). While a future's lock is pledged and the position is
        open, nothing is due until the settling print plus R_e."""
        lk = self.locks[deal]
        lk.update(peer=peer, rec=rec, probing=False, last_sub=t)
        s = self.w.sim.sessions[(self.name, peer)]
        lk["due"] = t + 2 * self.w.sim.geo.T0(s.path(self.name), t) + 24.0
        self.w.sim.at(lk["due"], self._probe, deal)

    def _resub(self, t, deal, why):
        """Resubmit LOCK for `deal` and, in the same packet (up to 14 records), for every other lock to the same peer
        that is already being probed. One packet per peer per probe, however many locks are open."""
        lk = self.locks[deal]
        peer = lk["peer"]
        iv = self._interval(peer)
        batch = [deal] + [d for d, o in self.locks.items() if d != deal and o.get("peer") == peer
                          and o["state"] in ("locked", "pledged")
                          and ((not o.get("probing") and o.get("due", 1e18) <= t + 1e-9)
                               or (o.get("probing") and t - o["last_sub"] >= iv - 1e-6))
                          and not (o["rec"].get("product") == "future" and o["state"] == "pledged" and t < SETTLE_H)]
        batch = batch[:14]
        for d in batch:
            self.locks[d]["probing"] = True
            self.locks[d]["last_sub"] = t
            self.w.sim.cancel_deal(self.name, d)          # this copy supersedes every earlier copy still being retried
        self.w.marks.setdefault("resubs", []).append(t)
        recs = [dict(self.locks[d]["rec"], flags="RESUBMISSION") for d in batch]
        self.w.send(t, self.name, peer, recs, f"LOCK {deal} (resub)",
                    know=f"Still holds the lock; {why}", action="Resubmits LOCK unchanged (recovery reserve)",
                    state="unchanged", resub=True)

    def _interval(self, peer):
        """Probe pace: PROBE_H per packet, stretched so that all open locks to this peer (14 per packet) still fit in the
        recovery reserve: 24 h x packets needed / reserve."""
        n = sum(1 for o in self.locks.values() if o.get("peer") == peer and o["state"] in ("locked", "pledged"))
        return PROBE_H * max(1, -(-n // 14))

    def _probe(self, t, deal):
        lk = self.locks[deal]
        if lk["state"] not in ("locked", "pledged"):
            return
        if lk["state"] == "pledged" and lk["rec"].get("product") == "future":
            s = self.w.sim.sessions[(self.name, lk["peer"])]
            due = SETTLE_H + 2 * self.w.sim.geo.T0(s.path(self.name), SETTLE_H) + 24.0
            if t < due - 1e-9:
                self.w.sim.at(due, self._probe, deal)
                return
        iv = self._interval(lk["peer"])
        if lk.get("probing") and t - lk["last_sub"] < iv - 1e-6:
            self.w.sim.at(lk["last_sub"] + iv, self._probe, deal)           # a batch already carried this lock
            return
        lk["probing"] = True
        sess = self.w.sim.sessions[(self.name, lk["peer"])]
        if sess.state[self.name] != "established" and t - sess.opened >= self._interval(lk["peer"]) - 1e-6:
            # R8': the session is not up (a reset peer's handshake is stuck): the holder opens its own fresh one, 1 SYN
            route = self.w.sim.geo.pin_route(self.name, lk["peer"], t, t + 24.0)
            self.w.sessions.append((self.name, lk["peer"], route))
            self.w.sim.open_session(t, self.name, lk["peer"], route,
                                    know=f"No established session to {lk['peer']}; lock still open",
                                    state="unchanged (fresh session)")
        self._resub(t, deal, "no recorded answer one endpoint timer on" if lk["last_sub"] < t else "still unanswered")
        self.w.sim.at(t + self._interval(lk["peer"]), self._probe, deal)

    def on_contact(self, sim, t, s, pkt):
        """R8': any packet from the peer while a lock is open and being probed triggers an immediate resubmission."""
        if not PROBE_ON:
            return
        for deal, lk in self.locks.items():
            if (lk.get("probing") and lk["state"] in ("locked", "pledged") and lk["peer"] == s.peer(self.name)
                    and t - lk["last_sub"] >= CONTACT_GAP_H):
                self._resub(t, deal, f"a packet from {lk['peer']} arrived")

    # ---------------- deciding Branch (share offer) and referee (future)
    def rx_LOCK(self, sim, t, peer, r, pkt):
        w, deal = self.w, r["deal"]
        if deal in self.decisions:                       # duplicate / resubmission / pull: repeat the recorded answer
            ans = self.decisions[deal]
            if t - self.last_reply.get(deal, -1e9) < REPLY_GAP_H:
                return                                   # the same answer is already on its way (R8')
            self.last_reply[deal] = t
            w.send(t, self.name, peer, [ans], f"{ans['type']} {deal} (recorded answer)",
                   know=f"{deal} already decided: {ans['type']}", action=f"Repeats recorded {ans['type']}",
                   state="unchanged")
            return
        if r["product"] == "share":
            self._decide_share(t, peer, r)
        elif r["product"] == "future":
            self._decide_future(t, peer, r)
        elif r["product"] == "hub-offer":
            w.hub_offer(t, self.name, peer, r)

    def _decide_share(self, t, peer, r):
        w, deal, off = self.w, r["deal"], self.offers.get(r["offer"])
        reason = None
        if off is None or off["state"] != "open" or t >= off["expiry"]:
            reason = 1
        elif (off["shares"], off["price"]) != (r["shares"], r["price"]):
            reason = 2
        if reason:
            ans = dict(r, type="DECLINE", reason=reason, time=t)
            self.decisions[deal] = ans
            self.decided_n[deal] = self.decided_n.get(deal, 0) + 1
            w.send(t, self.name, peer, [ans], f"DECLINE {deal}", know="LOCK fails the offer check",
                   action=f"Declines (reason {reason})", state="offer unchanged")
            return
        off["state"] = "filled"
        lock_at = w.branch_of(r["buyer"])

        def book(L):
            L.move(self.name, off["owner"], f"{lock_at} Branch", "ARES", r["shares"], tag=off["tag"])
            L.issue_claim(self.name, off["owner"], "USD", r["cash"])
            if L.lines[lock_at].get((r["buyer"], "USD", "own"), {"enc": {}})["enc"].get(deal):
                L.add_pending(deal, self.name, "USD", r["cash"], lock_at)
        w.sim.book(t, book)
        ans = dict(r, type="COMMIT", time=t)
        self.decisions[deal] = ans
        self.decided_n[deal] = self.decided_n.get(deal, 0) + 1
        w.marks.setdefault("commit", t)
        w.send(t, self.name, peer, [ans], f"COMMIT {deal}",
               know=f"Holds {off['owner']}'s firm offer {r['offer']}; LOCK terms match; before expiry h {off['expiry']:g}",
               action=f"Commits {deal}; records it durably, then replies",
               state=f"{r['shares']} Ares $\\to$ {lock_at} Branch's account here. {off['owner']} credited "
                     f"{money(r['cash'])}, spendable now (claim on {self.name} Branch backed by the lock at {lock_at})")

    def _decide_future(self, t, peer, r):
        w, deal, off = self.w, r["deal"], self.offers.get(r["offer"])
        reason = None
        if t >= FREEZE_H or off is None or off["state"] != "open" or t >= off["expiry"]:
            reason = 1
        elif (off["contracts"], off["margin"]) != (r["contracts"], r["margin"]):
            reason = 2
        if reason:
            ans = dict(r, type="DECLINE", reason=reason, time=t)
            self.decisions[deal] = ans
            self.decided_n[deal] = self.decided_n.get(deal, 0) + 1
            w.send(t, self.name, peer, [ans], f"DECLINE {deal}", know="LOCK fails the offer check",
                   action=f"Declines (reason {reason})", state="offer unchanged")
            return
        off["state"] = "filled"

        def book(L):
            L.unencumber(self.name, off["owner"], "USD", off["tag"])
            L.encumber(self.name, off["owner"], "USD", MARGIN, f"{deal}/short")
        w.sim.book(t, book)
        ans = dict(r, type="COMMIT", time=t)
        self.decisions[deal] = ans
        self.decided_n[deal] = self.decided_n.get(deal, 0) + 1
        w.position = dict(deal=deal, long=r["buyer"], short=off["owner"], holder=peer, opened=t)
        w.marks["open"] = t
        w.send(t, self.name, peer, [ans], f"COMMIT {deal}",
               know=f"Holds Ceres Iron Works' offer (short {CONTRACTS} at entry {ENTRY:g}); LOCK matches; before freeze",
               action="Records the position; replies COMMIT",
               state=f"Position open: long {CONTRACTS} {r['buyer']} / short {off['owner']}. Margins locked: "
                     f"{money(MARGIN)} at {peer} (pledged to Ceres) + {money(MARGIN)} here = {money(2 * MARGIN)}")

    def rx_COMMIT(self, sim, t, peer, r, pkt):
        w, deal = self.w, r["deal"]
        lk = self.locks.get(deal)
        if lk is None:
            return
        if AUDIT_ON and lk["state"] != "locked":
            if lk.get("outcome") not in (None, "COMMIT"):
                self.errors.append((t, deal, "conflicting decision: COMMIT after " + lk["outcome"]))
            return                                       # duplicate after close: ignored
        if lk["state"] != "locked":
            return
        if AUDIT_ON and not echo_ok(lk["rec"], r):
            self.errors.append((t, deal, "COMMIT echoes terms that differ from the LOCK"))
            return                                       # not applied; the lock stays and probing continues
        lk["outcome"] = "COMMIT"
        if r["product"] == "future":
            lk["state"] = "pledged"
            self.w.sim.cancel_deal(self.name, deal)
            w.row(t, self.me, "COMMIT arrived: position recorded at Ceres", "Keeps the lock as a pledge; "
                  "only a SETTLE ends it", "", "", f"{r['buyer']} {money(MARGIN)} pledged to Ceres (unchanged)")
            return
        lk["state"] = "released"
        self.w.sim.cancel_deal(self.name, deal)
        seller_at = r["seller_branch"]

        def book(L):
            L.move(self.name, r["buyer"], f"{seller_at} Branch", "USD", r["cash"], tag=deal)
            if deal in L.pending:
                L.settle_pending(deal)
            L.issue_claim(self.name, r["buyer"], "ARES", r["shares"])
        w.sim.book(t, book)
        w.marks["release"] = t
        w.row(t, self.me, f"COMMIT {deal} arrived", "Releases the lock",
              "", "", f"{money(r['cash'])} $\\to$ {seller_at} Branch's account here. {r['buyer']} credited "
                      f"{r['shares']} Ares, spendable now (claim on {self.name} Branch backed by its holding at "
                      f"{seller_at}). Trade complete.")

    def rx_DECLINE(self, sim, t, peer, r, pkt):
        lk = self.locks.get(r["deal"])
        if lk is None:
            return
        if AUDIT_ON and lk["state"] != "locked":
            if lk.get("outcome") not in (None, "DECLINE"):
                self.errors.append((t, r["deal"], "conflicting decision: DECLINE after " + lk["outcome"]))
            return
        if lk["state"] != "locked":
            return
        if AUDIT_ON and not echo_ok(lk["rec"], r):
            self.errors.append((t, r["deal"], "DECLINE echoes terms that differ from the LOCK"))
            return
        lk["outcome"] = "DECLINE"
        lk["state"] = "free"
        self.w.sim.cancel_deal(self.name, r["deal"])
        self.w.sim.book(t, lambda L: L.unencumber(self.name, r["buyer"], "USD", r["deal"]))
        self.w.row(t, self.me, "DECLINE arrived", "Unlocks", "", "", f"{r['buyer']} {money(r.get('cash', r.get('margin', 0)))} free again")

    # ---------------- pledge holder (Jupiter)
    def rx_PRINT(self, sim, t, peer, r, pkt):
        self.w.row(t, self.me, f"Interim print h {r['h']:g} = {r['price']:g} (information only)",
                   "Hands it to Callisto by local access", "", "", "unchanged")

    def rx_KEEPALIVE(self, sim, t, peer, r, pkt):
        pass

    def rx_SETTLE(self, sim, t, peer, r, pkt):
        w, deal = self.w, r["deal"]
        lk = self.locks.get(deal)
        if lk is None or lk["state"] != "pledged":
            return                                       # duplicate SETTLE: ignored
        if AUDIT_ON and not settle_ok(r):
            self.errors.append((t, deal, "SETTLE amount differs from the payoff recomputed from the settling print"))
            return                                       # not applied; the lock stays and probing continues
        lk["outcome"] = "SETTLE"
        lk["state"] = "settled"
        self.w.sim.cancel_deal(self.name, deal)
        to_ref, back, credit = r["release"], MARGIN - r["release"], r["credit"]

        def book(L):
            if to_ref:
                L.move(self.name, r["buyer"], f"{peer} Branch", "USD", to_ref, tag=deal)
                L.settle_pending(deal)
            L.unencumber(self.name, r["buyer"], "USD", deal)
            if credit:
                L.issue_claim(self.name, r["buyer"], "USD", credit)
        w.sim.book(t, book)
        w.marks["spendable"] = t
        if to_ref:
            st = (f"{money(to_ref)} of the pledge $\\to$ Ceres Branch's account here; {money(back)} back to "
                  f"{r['buyer']}, spendable. Pledge ended.")
        else:
            st = (f"{money(MARGIN)} pledge returned to {r['buyer']}; plus {money(credit)} credited (claim on "
                  f"Jupiter Branch backed by its holding at Ceres). All spendable. Pledge ended.")
        w.row(t, self.me, ("SETTLE arrived: contract voided, no settling print" if r.get("void") else
                           f"SETTLE arrived: settling print {r['price']:g}, clipped {r['clipped']:g}"),
              "Applies SETTLE", "", "", st)


class Hub(Branch):
    """Alternative design: a Mars hub ledger records every cross-planet trade (matching both legs)."""

    def __init__(self, w, name):
        super().__init__(w, name)
        self.book_ = {}

    def rx_LOCK(self, sim, t, peer, r, pkt):
        deal = r["deal"]
        if deal in self.decisions:
            ans = self.decisions[deal]
            self.w.send(t, self.name, peer, [ans], f"COMMIT {deal} (recorded)", know="already matched",
                        action="Repeats", state="unchanged")
            return
        e = self.book_.setdefault(deal, {})
        e[r["side"]] = (peer, r)
        if len(e) == 2:
            ans = dict(e["buy"][1], type="COMMIT", time=t, seller_branch=e["sell"][0])
            self.decisions[deal] = ans
            self.w.marks["hub_match"] = t
            buyer_at, seller_at, r0 = e["buy"][0], e["sell"][0], e["buy"][1]

            def book(L):  # the hub's record makes each locked leg owed to the other side's Branch
                L.add_pending(deal, seller_at, "USD", r0["cash"], buyer_at)
                L.add_pending(r0["offer"], buyer_at, "ARES", r0["shares"], seller_at)
            self.w.sim.book(t, book)
            for side in ("sell", "buy"):
                p = e[side][0]
                self.w.send(t, self.name, p, [dict(ans, side=side)], f"COMMIT {deal} $\\to$ {p}",
                            know="Holds both legs: buyer's lock and seller's reserved offer", action=f"Records the trade; "
                            f"sends COMMIT to {p}", state="Trade recorded on the hub ledger (no assets at Mars)")
        else:
            self.w.row(t, f"{self.name} hub", f"Has the {r['side']} leg of {deal} only", "Waits for the other leg",
                       "", "", "unchanged")


class HubMember(Branch):
    def rx_COMMIT(self, sim, t, peer, r, pkt):
        w, deal = self.w, r["deal"]
        if r["side"] == "buy":
            return super().rx_COMMIT(sim, t, r["seller_branch"], r, pkt)
        off = self.offers[r["offer"]]
        if off["state"] != "open":
            return
        off["state"] = "filled"
        lock_at = w.branch_of(r["buyer"])

        def book(L):
            L.move(self.name, off["owner"], f"{lock_at} Branch", "ARES", r["shares"], tag=off["tag"])
            L.settle_pending(off["tag"])
            L.issue_claim(self.name, off["owner"], "USD", r["cash"])
        w.sim.book(t, book)
        w.marks["commit"] = t
        w.row(t, self.me, f"Hub COMMIT for {deal} arrived", "Transfers the reserved shares",
              "", "", f"{r['shares']} Ares $\\to$ {lock_at} Branch's account here. {off['owner']} credited "
                      f"{money(r['cash'])}, spendable (claim on {self.name} Branch backed by the lock at {lock_at})")


# ======================================================================== the world (one run)

class World:
    def __init__(self, name, maintenance=True, incident=None, relocate=None, offset=0.0):
        self.name = name
        self.opening = [(o, relocate if (relocate and o == "Terra Capital") else s, u, a) for o, s, u, a in OPENING]
        self.sim = Sim(maintenance=maintenance, incident=incident, opening=[(o, s, u, a) for o, s, u, a in self.opening],
                       branches=BRANCHES, offset=offset)
        self.apps = {}
        self.marks = {}
        self.position = None
        self.deal_ctr = {}
        self.sessions = []
        self.reroute = True
        self._batch = None
        self.void = False

    def offer_life_ok(self, frm, to, t, expiry):
        """Offer-life rule R5: the initiator accepts a remote offer only if a second endpoint attempt, if it is not
        abandoned, is sure to arrive before expiry: expiry - t >= R_e + T0 + 3 * sum(R_h) on its pinned route, with
        R_e = 2 T0 + 24 h and R_h = 2 x hop flight + 1 h (all at enqueue). Otherwise refused locally, nothing locked."""
        path = self.sim.sessions[(frm, to)].path(frm)
        T0 = self.sim.geo.T0(path, t)
        rh = sum(2 * self.sim.geo.flight(a, b, t)[0] + 1.0 for a, b in zip(path[:-1], path[1:]))
        return expiry - t >= (2 * T0 + 24.0) + T0 + 3 * rh

    def reset(self, t, node):
        """R19 (spec section 5, endpoint reset): sessions are gone; the node handshakes a new one with each peer
        (1 SYN quota each) and resubmits a LOCK for every deal it holds Locked."""
        peers = self.sim.reset_node(t, node)
        app = self.apps.get(node)
        for p in peers:
            route = self.sim.geo.pin_route(node, p, t, t + 24.0)
            self.sessions.append((node, p, route))
            self.sim.open_session(t, node, p, route, know=f"{node} Branch restarted: sessions lost; durable ledger, "
                                  "deal counter and decisions survive", state="unchanged (reset)")
        self.marks.setdefault("resets", []).append(t)
        if app is not None:
            for deal, lk in app.locks.items():
                if lk["state"] in ("locked", "pledged") and lk.get("peer") in peers:
                    app._resub(t, deal, "restarted")

    def branch_of(self, owner):
        return next(s for o, s, _, _ in self.opening if o == owner)

    def row(self, t, actor, know, action, packet="", arrival="", state=""):
        self.sim.row(t, actor, know, action, packet, arrival, state)

    def send(self, t, frm, to, records, label, know="", action="", state="", resub=False):
        if self._batch is not None and not resub and len(records) == 1:
            self._batch.setdefault((frm, to), []).append(
                (records[0], label, dict(know=know, action=action, state=state, resub=resub)))
            return None
        s = self.sim.sessions[(frm, to)]
        if self.reroute and self.sim.geo.route_stalled(s.path(frm), t):
            # Protocol route rule: never queue behind a known closure longer than 24 h; re-pin by foresight and
            # handshake a fresh session (1 SYN quota). Records wait for SYN-ACK in the new session's outbox.
            route = self.sim.geo.pin_route(frm, to, t, t + 24.0)
            self.sessions.append((frm, to, route))
            self.marks.setdefault("reroutes", []).append(t)
            self.sim.open_session(t, frm, to, route,
                                  know=f"Pinned route {self.sim._route_txt(s.path(frm))} is closed by geometry for "
                                       f"more than 24 h (known in advance)", state="unchanged (re-route)")
        r = dict(t=t, actor=f"{frm} Branch" if frm != "Mars" or not isinstance(self.apps.get("Mars"), Hub) else "Mars hub",
                 know=know, action=action, packet="", arrival="", state=state)
        pkt = self.sim.send_data(t, frm, to, records, label)
        route = self.sim.sessions[(frm, to)].path(frm)
        r["packet"] = "BB " + self.sim._route_txt(route) + (", resubmission" if resub else "")
        self.sim.trace.append(r)
        if pkt is not None:
            pkt.row = r
        return pkt

    def open(self, a, b, cover_until):
        route = self.sim.geo.pin_route(a, b, OPEN_SESSIONS_H, cover_until)
        self.sessions.append((a, b, route))
        return self.sim.open_session(OPEN_SESSIONS_H, a, b, route)

    def next_deal(self, branch):
        self.deal_ctr[branch] = self.deal_ctr.get(branch, 0) + 1
        return f"{branch[:3].upper()}-{self.deal_ctr[branch]}"

    # ---------------- value move
    def script_vm(self, hub=False):
        buyer_at = self.branch_of("Terra Capital")
        seller_at = "Neptune"
        if hub:
            self.apps = {"Mars": Hub(self, "Mars"), buyer_at: HubMember(self, buyer_at), seller_at: HubMember(self, seller_at)}
            self.open(buyer_at, "Mars", 24.0)
            self.open(seller_at, "Mars", 24.0)
        else:
            self.apps = {buyer_at: Branch(self, buyer_at), seller_at: Branch(self, seller_at)}
            self.open(buyer_at, seller_at, 24.0)
        self.sim.apps = self.apps
        S, B = self.apps[seller_at], self.apps[buyer_at]
        deal = self.next_deal(buyer_at)

        def post_offer(t):
            ok = self.sim.book(t, lambda L: L.encumber(seller_at, "Triton Fund", "ARES", VM_SHARES, "O-1"))
            assert ok
            S.offers["O-1"] = dict(owner="Triton Fund", shares=VM_SHARES, price=VM_PRICE, expiry=VM_OFFER_EXPIRY,
                                   state="open", tag="O-1")
            self.row(t, f"{seller_at} Branch", "Triton's offer arrives by local access (1 s)",
                     f"Posts firm offer O-1: sell {VM_SHARES} Ares at {money(VM_PRICE)}, expiry h {VM_OFFER_EXPIRY:g}",
                     "local", "", f"Triton {VM_SHARES} Ares reserved for O-1")
            if hub:
                self.send(t, seller_at, "Mars", [dict(type="LOCK", product="hub-offer", side="sell", deal=deal,
                          offer="O-1", shares=VM_SHARES, price=VM_PRICE, cash=VM_CASH, buyer="Terra Capital")],
                          f"OFFER {deal}", know="Offer reserved here", action="Sends the sell leg to the hub",
                          state="unchanged")

        def accept(t):
            assert hub or self.offer_life_ok(buyer_at, seller_at, t, VM_OFFER_EXPIRY)
            ok = self.sim.book(t, lambda L: L.encumber(buyer_at, "Terra Capital", "USD", VM_CASH, deal))
            assert ok
            B.locks[deal] = dict(state="locked", t=t)
            self.marks["lock"] = t
            rec = dict(type="LOCK", product="hub-offer" if hub else "share", side="buy", deal=deal, offer="O-1",
                       shares=VM_SHARES, price=VM_PRICE, cash=VM_CASH, buyer="Terra Capital", seller_branch=seller_at)
            self.send(t, buyer_at, "Mars" if hub else seller_at, [rec], f"LOCK {deal}",
                      know="Terra's acceptance of O-1 (terms as advertised); free balance covers it; offer life "
                           "covers a second attempt (R5); knows nothing of Neptune's state", action=f"Locks {money(VM_CASH)}; sends LOCK {deal}",
                      state=f"Terra {money(VM_CASH)} locked for {deal}")
            B.arm(t, deal, "Mars" if hub else seller_at, rec)

        self.sim.at(SEC, lambda t: post_offer(t))
        self.sim.at(SEC, lambda t: accept(t))
        self.end = 48.0

    # ---------------- future
    def script_future(self, path):
        self.path = path
        J, C = "Jupiter", "Ceres"
        self.apps = {J: Branch(self, J), C: Branch(self, C)}
        self.sim.apps = self.apps
        sess = self.open(J, C, 24.0)
        deal = self.next_deal(J)
        self.deal = deal

        def offer(t):
            assert self.sim.book(t, lambda L: L.encumber(C, "Ceres Iron Works", "USD", MARGIN, "O-F"))
            self.apps[C].offers["O-F"] = dict(owner="Ceres Iron Works", contracts=CONTRACTS, margin=MARGIN,
                                              expiry=FUT_OFFER_EXPIRY, state="open", tag="O-F")
            self.row(t, "Ceres Branch", "Ceres Iron Works' order by local access; h 0 print = 100 = entry",
                     f"Posts firm offer O-F: short {CONTRACTS} at {ENTRY:g}, expiry h {FUT_OFFER_EXPIRY:g}",
                     "local", "", f"Ceres Iron Works {money(MARGIN)} reserved (max loss)")

        def accept(t):
            assert self.offer_life_ok(J, C, t, FUT_OFFER_EXPIRY)
            assert self.sim.book(t, lambda L: L.encumber(J, "Callisto Foundry", "USD", MARGIN, deal))
            self.apps[J].locks[deal] = dict(state="locked", t=t)
            self.marks["lock"] = t
            lock_rec = dict(type="LOCK", product="future", deal=deal, offer="O-F", contracts=CONTRACTS,
                            margin=MARGIN, buyer="Callisto Foundry")
            self.apps[J].arm(t, deal, C, lock_rec)
            self.send(t, J, C, [lock_rec], f"LOCK {deal}",
                      know="Callisto's order (long 25, entry = h 0 print); free balance covers the max loss; offer life "
                           "covers a second attempt (R5)",
                      action=f"Locks {money(MARGIN)} at home; sends LOCK {deal}",
                      state=f"Callisto {money(MARGIN)} locked (pledge at home)")

        def print_(t, k):
            h, p = PRINT_HOURS[k], path[k]
            if k == 0:
                self.row(t, "Ceres Iron Price Board", "Ceres Iron price", f"Releases print h 0 = {p:g} locally",
                         "local", "", "entry price fixed at 100")
                return
            tb = t + SEC                                   # local access to Ceres Branch
            if h < SETTLE_H:
                self.sim.at(tb, lambda t2: self.send(t2, C, J, [dict(type="PRINT", h=h, price=p)], f"PRINT h{h}",
                            know=f"Interim print h {h} = {p:g} by local access", action="Forwards it to Jupiter "
                            "(information only)", state="unchanged"))
            elif self.void:
                self.sim.at(SETTLE_H + VOID_GRACE_H, void_settle)
            else:
                self.sim.at(tb, lambda t2: settle(t2, p))

        def void_settle(t):
            pos = self.position
            if pos is None:
                return

            def book(L):
                L.unencumber(C, pos["short"], "USD", f"{pos['deal']}/short")
            self.sim.book(t, book)
            self.marks["discharge"] = self.marks["backed"] = t
            ans = dict(type="SETTLE", product="future", deal=pos["deal"], price=None, clipped=None, release=0.0,
                       credit=0.0, buyer=pos["long"], void=True)
            self.apps[C].decisions[pos["deal"]] = ans
            self.payoff = dict(price=None, clipped=None, to_long=0.0)
            self.send(t, C, J, [ans], f"SETTLE {pos['deal']} (void)",
                      know=f"No settling print by h {SETTLE_H + VOID_GRACE_H:g} (Price Board silent for {VOID_GRACE_H:g} h)",
                      action="Voids the contract; returns Ceres Iron's margin; sends SETTLE (void)",
                      state=f"Ceres Iron Works' {money(MARGIN)} margin free; no payoff")

        def settle(t, p):
            pos = self.position
            if pos is None:
                return                                   # offer withdrawn or declined: no position, nothing to settle
            clipped = min(max(p, ENTRY * (1 - CAP)), ENTRY * (1 + CAP))
            y = CONTRACTS * MULT * (clipped - ENTRY)        # to the long
            Y = abs(y)
            if y < 0:   # short wins Y: credited now, backed by the Jupiter pledge
                rel, credit = Y, 0.0

                def book(L):
                    L.unencumber(C, pos["short"], "USD", f"{pos['deal']}/short")
                    L.issue_claim(C, pos["short"], "USD", Y)
                    L.add_pending(pos["deal"], C, "USD", Y, J)
                st = (f"Payoff {money(Y)} to Ceres Iron Works: backed claim now (backed by Callisto's pledge at "
                      f"Jupiter), usable at Ceres; its own {money(MARGIN)} margin released")
            else:       # long wins Y: paid from the short margin into Jupiter Branch's account here
                rel, credit = 0.0, Y

                def book(L):
                    if Y:
                        L.move(C, pos["short"], "Jupiter Branch", "USD", Y, tag=f"{pos['deal']}/short")
                    L.unencumber(C, pos["short"], "USD", f"{pos['deal']}/short")
                st = (f"{money(Y)} of Ceres Iron Works' margin $\\to$ Jupiter Branch's account here; "
                      f"{money(MARGIN - Y)} released to Ceres Iron Works")
            self.sim.book(t, book)
            self.marks["discharge"] = self.marks["backed"] = t
            ans = dict(type="SETTLE", product="future", deal=pos["deal"], price=p, clipped=clipped, release=rel,
                       credit=credit, buyer=pos["long"])
            self.apps[C].decisions[pos["deal"]] = ans
            self.payoff = dict(price=p, clipped=clipped, to_long=y)
            self.send(t, C, J, [ans], f"SETTLE {pos['deal']}",
                      know=f"Settling print h 288 = {p:g} by local access; clipped to {clipped:g}",
                      action="Records the payoff (discharge); sends SETTLE once", state=st)

        def keepalive(t):
            s = self.sim.sessions[(J, C)]
            last = s.last_rx[J] if s.last_rx[J] is not None else s.opened
            if self.apps[J].locks.get(deal, {}).get("state") in ("locked", "pledged") and t - last >= KEEPALIVE_IDLE:
                self.send(t, J, C, [dict(type="KEEPALIVE")], "KEEPALIVE", know="Session idle 120 h",
                          action="Sends keep-alive", state="unchanged")
            if t < 400:
                self.sim.at(t + 1.0, keepalive)

        self.sim.at(SEC, offer)
        self.sim.at(SEC, accept)
        for k, h in enumerate(PRINT_HOURS):
            self.sim.at(float(h), print_, k)
        self.sim.at(0.0, keepalive)
        self.end = 312.0


# ======================================================================== runs and reporting

STACK = dict(iso_start=286.0, reset_node="Ceres", reset_after=0.0, forced_node="Jupiter", forced_start=358.0)  # worst of code/stack_scan.py


def make(run):
    base = run.replace("noMaint-", "").replace("Hub-", "")
    maint = not run.startswith("noMaint-")
    inc, resets = None, []
    iso = Incident("isolation", "Ceres", 286.0, 72.0)
    if base in ("S2", "S2-FR"):
        inc = iso
    elif base == "S2-ST":                                   # stacked: isolation + endpoint reset + forced loss
        k = STACK
        iso = Incident("isolation", "Ceres", k["iso_start"], 72.0)
        inc = Stack(iso, Incident("forced", k["forced_node"], k["forced_start"], 6.0)) if k["forced_node"] else iso
        resets = [(k["iso_start"] + 72.0 + k["reset_after"], k["reset_node"])]
    reloc = base.split("@")[1] if "@" in base else None
    w = World(run, maintenance=maint, incident=inc, relocate=reloc)
    w.void = base == "VOID"
    if base.startswith("VM"):
        w.script_vm(hub=run.startswith("Hub-"))
    else:
        w.script_future({"FR": RISING, "FF": FALLING, "FR-cap": CAPPED, "S2": FALLING, "S2-FR": RISING,
                         "S2-ST": RISING, "VOID": RISING}[base])
        for t, node in resets:
            w.sim.at(t, lambda t_, n=node: w.reset(t_, n))
    w.kind = "vm" if base.startswith("VM") else "future"
    return w


RUNS = ["VM", "FR", "FF", "FR-cap", "S2", "S2-FR", "S2-ST", "VOID", "VM@Ceres", "VM@Venus", "VM@Uranus",
        "noMaint-VM", "noMaint-FR", "noMaint-FF", "noMaint-S2",
        "Hub-VM", "Hub-VM@Ceres", "Hub-VM@Venus", "Hub-VM@Uranus"]


def execute(run, w=None, out=OUT):
    """One run: w defaults to make(run); E5 passes a pre-built shifted-epoch World and its own output folder."""
    w = w or make(run)
    sim = w.sim
    sim.run(until=w.end + 1000.0)
    end = max(w.end, max(w.marks.get("spendable", 0), w.marks.get("release", 0), w.marks.get("commit", 0)))
    end = float(int(end) + 1) if end > w.end else w.end
    sim.ledger.advance(end)
    L = sim.ledger
    # final-state checks: every Branch's claims exactly backed; nothing left encumbered
    for x in BRANCHES:
        for a in ("USD", "ARES"):
            claims = sum(ln["bal"] for (o, aa, k), ln in L.lines[x].items() if k == "claim" and aa == a)
            held = sum(ln["bal"] for y, lines in L.lines.items() if y != x
                       for (o, aa, k), ln in lines.items() if o == f"{x} Branch" and aa == a and k == "own")
            assert abs(claims - held) < 1e-6 and not L.pending, f"{run}: Branch equity not zero at end ({x} {a})"
    assert all(v < 1e-9 for v in L.encumbered().values()), f"{run}: still encumbered at end"

    launches = sim.launches                              # every launch in the run, including trailing ACKs
    last_packet = max(x["arrival"] or x["t"] for x in launches)
    peak_sys, peak_br = sim.quota_peaks()
    assert peak_sys <= 600 and all(v <= 66 for v in peak_br.values()), f"{run}: quota slice exceeded"
    # session expiry: no endpoint may go 168 h without a session packet while the run needs the session
    need_until = max(v for v in w.marks.values() if isinstance(v, float))
    gaps = {}
    for s in set(sim.sessions.values()):
        for x in (s.a, s.b):
            ts = [t for t in s.rx_times[x] if t <= need_until] + [need_until]
            gaps[f"{x} on {s.a}-{s.b}"] = max(b - a for a, b in zip(ts, ts[1:])) if len(ts) > 1 else None
    assert all(g is None or g < 168 for g in gaps.values()), f"{run}: a session would expire: {gaps}"
    m = w.marks
    res = dict(run=run, end=end, marks=m, sessions=[dict(a=a, b=b, route=r) for a, b, r in w.sessions],
               launches_total=len(launches), launches_failed=sum(x["failed"] for x in launches),
               launches_by_kind={k: sum(1 for x in launches if x["kind"] == k)
                                 for k in ("SYN", "SYNACK", "ACK", "DATA", "DACK", "RCPT")},
               originated=len(sim.originated), originated_list=sim.originated, quota_peak_system=peak_sys,
               quota_peak_branch=peak_br, queue_peak=sim.queue_peak(),
               max_unacked=max(s.max_unacked for s in set(sim.sessions.values())),
               peak_usd=L.peak["USD"][0], peak_usd_at=L.peak["USD"][1], peak_ares=L.peak["ARES"][0],
               asset_hours=L.asset_hours, checks=L.checks, final=L.snapshot(),
               hops=[dict(link=x["link"], d=x["d"], p=x["p_loss"]) for x in launches if not x["failed"]],
               max_wait=max((x["wait"] for x in launches), default=0.0), last_packet=last_packet, rx_gaps=gaps,
               snaps=sim.snaps, opening=w.opening)
    if w.kind == "vm":
        res["complete"] = max(m["commit"], m["release"])
        res["value_settled"] = VM_CASH
        res["completed_tx"] = 1
        res["exposure"] = "none beyond the locked price: DvP, each side's asset is locked until the other is committed"
    else:
        res.update(open=m["open"], discharge=m["discharge"], backed=m["backed"], spendable=m["spendable"],
                   payoff=w.payoff, value_settled=CONTRACTS * MULT * ENTRY, completed_tx=1,
                   exposure=f"{MARGIN:.0f} per side (cap x entry x multiplier x contracts)")
    res["capital_eff"] = res["peak_usd"] / res["value_settled"]
    res["comm_eff"] = res["launches_total"] / res["completed_tx"]
    res["utilization"] = res["peak_usd"] / 500_000
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{run}_events.csv", "w", newline="") as f:
        keys = ["t", "actor", "what", "kind", "link", "pid", "n", "flight", "d", "p_loss", "arrival", "failed",
                "attempt", "seq", "label"]
        wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        wr.writeheader()
        for e in sorted(sim.log, key=lambda e: e["t"]):
            wr.writerow(e)
    res["trace"] = sorted(sim.trace, key=lambda r: r["t"])
    (out / f"{run}.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    runs = sys.argv[1:] or RUNS
    allres = {}
    for r in runs:
        res = execute(r)
        allres[r] = res
        key = res.get("complete", res.get("spendable"))
        print(f"{r:16s} done h {key:9.4f}  launches {res['launches_total']:4d} (failed {res['launches_failed']:3d})"
              f"  originated {res['originated']:3d}  quota peak {res['quota_peak_system']:3d}  peak $ {res['peak_usd']:9,.0f}"
              f"  $-h {res['asset_hours']['USD']:12,.0f}  checks {res['checks']}", flush=True)
    if not sys.argv[1:]:
        import report
        report.write_all(allres)
