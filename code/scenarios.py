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

from sim import SEC, Incident, Sim

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
VM_SHARES, VM_PRICE, VM_OFFER_EXPIRY = 200, 125, 24.0
VM_CASH = VM_SHARES * VM_PRICE

# Ceres Iron capped future
ENTRY, MULT, CONTRACTS, CAP = 100.0, 100, 25, 0.30
MARGIN = CAP * ENTRY * MULT * CONTRACTS                  # 75,000 per side
PRINT_HOURS = [24 * k for k in range(13)]                # 0 .. 288
SETTLE_H, FREEZE_H, FUT_OFFER_EXPIRY = 288.0, 264.0, 24.0
RISING = [100, 103, 107, 111, 115, 118, 121, 124, 126, 125, 124, 124, 123]
FALLING = [100, 97, 93, 89, 85, 82, 79, 76, 74, 75, 76, 76, 77]
CAPPED = RISING[:-1] + [140]
KEEPALIVE_IDLE = 120.0


def money(x):
    return f"\\${x:,.0f}".replace(",", "{,}")


# ======================================================================== applications

class Branch:
    """One Branch's application: home-ledger actions and record handling (protocol sections 3, 4, 6)."""

    def __init__(self, w, name):
        self.w, self.name = w, name
        self.decisions = {}     # deal -> recorded answer record (deciding / referee side)
        self.locks = {}         # deal -> dict (initiator / pledge-holder side)
        self.offers = {}        # offer id -> dict

    @property
    def me(self):
        return f"{self.name} Branch"

    # ---------------- records arriving
    def on_records(self, sim, t, s, pkt):
        for r in pkt.records:
            getattr(self, "rx_" + r["type"])(sim, t, s.peer(self.name), r, pkt)

    def on_unknown(self, sim, t, s, pkt):
        """Endpoint attempts ran out with status unknown. Only a lock holder acts: it resubmits the LOCK unchanged
        (RESUBMISSION flag, recovery reserve; no cap on tries). Deciding and referee Branches only answer."""
        self.w.sim.ev(t, self.name, "status unknown", label=pkt.label)
        lock = next((r for r in pkt.records if r["type"] == "LOCK"), None)
        if lock is None or self.locks.get(lock["deal"], {}).get("state") not in ("locked", "pledged"):
            return
        self.w.send(t, self.name, s.peer(self.name), [dict(lock, flags="RESUBMISSION")], f"LOCK {lock['deal']} (resub)",
                    know=f"{pkt.label}: 4 endpoint attempts, status unknown; still holds the lock",
                    action="Resubmits LOCK unchanged (recovery reserve)", state="unchanged", resub=True)

    # ---------------- deciding Branch (share offer) and referee (future)
    def rx_LOCK(self, sim, t, peer, r, pkt):
        w, deal = self.w, r["deal"]
        if deal in self.decisions:                       # duplicate / resubmission / pull: repeat the recorded answer
            ans = self.decisions[deal]
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
        if lk is None or lk["state"] != "locked":
            return                                       # duplicate after close: ignored
        if r["product"] == "future":
            lk["state"] = "pledged"
            w.row(t, self.me, "COMMIT arrived: position recorded at Ceres", "Keeps the lock as a pledge; "
                  "only a SETTLE ends it", "", "", f"{r['buyer']} {money(MARGIN)} pledged to Ceres (unchanged)")
            return
        lk["state"] = "released"
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
        if lk is None or lk["state"] != "locked":
            return
        lk["state"] = "free"
        self.w.sim.book(t, lambda L: L.unencumber(self.name, r["buyer"], "USD", r["deal"]))
        self.w.row(t, self.me, "DECLINE arrived", "Unlocks", "", "", f"{r['buyer']} {money(r['cash'])} free again")

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
        lk["state"] = "settled"
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
        w.row(t, self.me, f"SETTLE arrived: settling print {r['price']:g}, clipped {r['clipped']:g}",
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
    def __init__(self, name, maintenance=True, incident=None, relocate=None):
        self.name = name
        self.opening = [(o, relocate if (relocate and o == "Terra Capital") else s, u, a) for o, s, u, a in OPENING]
        self.sim = Sim(maintenance=maintenance, incident=incident, opening=[(o, s, u, a) for o, s, u, a in self.opening],
                       branches=BRANCHES)
        self.apps = {}
        self.marks = {}
        self.position = None
        self.deal_ctr = {}
        self.sessions = []

    def branch_of(self, owner):
        return next(s for o, s, _, _ in self.opening if o == owner)

    def row(self, t, actor, know, action, packet="", arrival="", state=""):
        self.sim.row(t, actor, know, action, packet, arrival, state)

    def send(self, t, frm, to, records, label, know="", action="", state="", resub=False):
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
            ok = self.sim.book(t, lambda L: L.encumber(buyer_at, "Terra Capital", "USD", VM_CASH, deal))
            assert ok
            B.locks[deal] = dict(state="locked", t=t)
            self.marks["lock"] = t
            rec = dict(type="LOCK", product="hub-offer" if hub else "share", side="buy", deal=deal, offer="O-1",
                       shares=VM_SHARES, price=VM_PRICE, cash=VM_CASH, buyer="Terra Capital", seller_branch=seller_at)
            self.send(t, buyer_at, "Mars" if hub else seller_at, [rec], f"LOCK {deal}",
                      know="Terra's acceptance of O-1 (terms as advertised); free balance covers it; knows nothing "
                           "of Neptune's state", action=f"Locks {money(VM_CASH)}; sends LOCK {deal}",
                      state=f"Terra {money(VM_CASH)} locked for {deal}")

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
            assert self.sim.book(t, lambda L: L.encumber(J, "Callisto Foundry", "USD", MARGIN, deal))
            self.apps[J].locks[deal] = dict(state="locked", t=t)
            self.marks["lock"] = t
            self.send(t, J, C, [dict(type="LOCK", product="future", deal=deal, offer="O-F", contracts=CONTRACTS,
                                     margin=MARGIN, buyer="Callisto Foundry")], f"LOCK {deal}",
                      know="Callisto's order (long 25, entry = h 0 print); free balance covers the max loss",
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
            else:
                self.sim.at(tb, lambda t2: settle(t2, p))

        def settle(t, p):
            pos = self.position
            clipped = min(max(p, ENTRY * (1 - CAP)), ENTRY * (1 + CAP))
            y = CONTRACTS * MULT * (clipped - ENTRY)        # to the long
            Y = abs(y)
            if y < 0:   # short wins Y: credited now, backed by the Jupiter pledge
                rel, credit = Y, 0.0

                def book(L):
                    L.unencumber(C, pos["short"], "USD", f"{pos['deal']}/short")
                    L.issue_claim(C, pos["short"], "USD", Y)
                    L.add_pending(pos["deal"], C, "USD", Y, J)
                st = (f"Payoff {money(Y)} to Ceres Iron Works: credited now, spendable (claim backed by Callisto's "
                      f"pledge at Jupiter); its own {money(MARGIN)} margin released")
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
            # pull rule at the pledge holder: print + R_e, then every R_e while the lock is held
            sch = self.sim.sessions[(J, C)]
            R = 2 * self.sim.geo.T0(sch.path(J), SETTLE_H) + 24.0
            self.sim.at(SETTLE_H + R, pull, R)

        def pull(t, R):
            lk = self.apps[J].locks[deal]
            if lk["state"] != "pledged":
                return
            self.marks.setdefault("pulls", []).append(t)
            self.send(t, J, C, [dict(type="LOCK", product="future", deal=deal, offer="O-F", contracts=CONTRACTS,
                                     margin=MARGIN, buyer="Callisto Foundry", flags="RESUBMISSION")],
                      f"LOCK {deal} (pull)", know="Still holds the pledge at print + R\\textsubscript{e}",
                      action="Resubmits LOCK (pull rule; recovery reserve)", state="unchanged", resub=True)
            # one pull; if it also ends with status unknown, on_unknown resubmits again

        def keepalive(t):
            s = self.sim.sessions[(J, C)]
            last = s.last_rx[J] if s.last_rx[J] is not None else OPEN_SESSIONS_H
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

def make(run):
    base = run.replace("noMaint-", "").replace("Hub-", "")
    maint = not run.startswith("noMaint-")
    inc = Incident("isolation", "Ceres", 286.0, 72.0) if base == "S2" else None
    reloc = base.split("@")[1] if "@" in base else None
    w = World(run, maintenance=maint, incident=inc, relocate=reloc)
    if base.startswith("VM"):
        w.script_vm(hub=run.startswith("Hub-"))
    else:
        w.script_future({"FR": RISING, "FF": FALLING, "FR-cap": CAPPED, "S2": FALLING}[base])
    w.kind = "vm" if base.startswith("VM") else "future"
    return w


RUNS = ["VM", "FR", "FF", "FR-cap", "S2", "VM@Ceres", "VM@Venus", "VM@Uranus",
        "noMaint-VM", "noMaint-FR", "noMaint-FF", "noMaint-S2",
        "Hub-VM", "Hub-VM@Ceres", "Hub-VM@Venus", "Hub-VM@Uranus"]


def execute(run):
    w = make(run)
    sim = w.sim
    sim.run(until=1000.0)
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
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{run}_events.csv", "w", newline="") as f:
        keys = ["t", "actor", "what", "kind", "link", "pid", "n", "flight", "d", "p_loss", "arrival", "failed",
                "attempt", "seq", "label"]
        wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        wr.writeheader()
        for e in sorted(sim.log, key=lambda e: e["t"]):
            wr.writerow(e)
    res["trace"] = sorted(sim.trace, key=lambda r: r["t"])
    (OUT / f"{run}.json").write_text(json.dumps(res, indent=1, default=str))
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
