"""Quick look: link delays at h=0 and h=300, and best-route delay from every settlement to each candidate hub."""
import itertools
import numpy as np
from orbits import SETTLEMENTS, RELAYS, light_time

SER = 1 / 3600  # 1 s serialization, h
PROC = 1 / 3600  # relay processing


def hop(a, b, t):
    ta, d, blk = light_time(a, b, t + SER)
    return float(ta), float(d), bool(blk)


def best_route(src, dst, t):
    """Search simple routes of <=3 backbone links (gateway-relay-gateway, gateway-relay-relay-gateway)."""
    best = None
    paths = [[src, r, dst] for r in RELAYS] + [[src, r1, r2, dst] for r1, r2 in itertools.permutations(RELAYS)]
    for p in paths:
        tt, ok, ds = t, True, []
        for i in range(len(p) - 1):
            ta, d, blk = hop(p[i], p[i + 1], tt)
            if blk:
                ok = False
                break
            ds.append(d)
            tt = ta + (PROC if i < len(p) - 2 else 0)
        if ok and (best is None or tt - t < best[0]):
            best = (tt - t, p, ds)
    return best


for t in (0, 300):
    print(f"\n=== links at h={t} (one-way hours, AU, blocked) ===")
    for s in SETTLEMENTS:
        row = []
        for r in RELAYS:
            ta, d, blk = hop(s, r, t)
            row.append(f"{r[-1]}: {ta - t:6.2f}h {d:6.2f}AU {'BLK' if blk else '   '}")
        print(f"{s:8s} " + " | ".join(row))
    ta, d, blk = hop("Relay A", "Relay B", t)
    print(f"A<->B {ta - t:.2f}h {d:.2f}AU blk={blk}")

    print(f"\n=== hub ranking at h={t}: max / median one-way delay from other settlements ===")
    for hub in SETTLEMENTS:
        ds = []
        for s in SETTLEMENTS:
            if s == hub:
                continue
            b = best_route(s, hub, t)
            ds.append(b[0] if b else float("inf"))
        print(f"{hub:8s} max {max(ds):6.2f}h  median {np.median(ds):6.2f}h  mean {np.mean(ds):6.2f}h")
