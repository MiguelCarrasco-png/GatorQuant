"""Compare settlement latency: bilateral home ledgers vs central hub, using best backbone routes at h=0."""
import numpy as np
from orbits import SETTLEMENTS
from explore_hub import best_route
import io, contextlib

S = SETTLEMENTS
D = {(a, b): best_route(a, b, 0.0)[0] for a in S for b in S if a != b}
pairs = [(a, b) for i, a in enumerate(S) for b in S[i + 1:]]

def bilateral(a, b):  # lock+offer a->b, commit b->a : one round trip
    return D[(a, b)] + D[(b, a)]

def hub(a, b, H):
    din = max(D.get((a, H), 0), D.get((b, H), 0))
    dout = max(D.get((H, a), 0), D.get((H, b), 0))
    return din + dout

print("Neptune<->Earth one-way", round(D[('Neptune','Earth')],2), "h")
print(f"{'design':22s} {'Nep-Earth':>9s} {'median pair':>11s} {'worst pair':>10s} {'same-planet':>11s} {'backbone msgs/trade':>19s}")
b = [bilateral(a, c) for a, c in pairs]
print(f"{'Home ledgers (bilat.)':22s} {bilateral('Neptune','Earth'):9.2f} {np.median(b):11.2f} {max(b):10.2f} {0:11.2f} {2:19d}")
for H in ["Mars", "Ceres", "Earth"]:
    h = [hub(a, c, H) for a, c in pairs]
    same = 2 * np.median([D[(s, H)] for s in S if s != H])
    print(f"{'Central hub @'+H:22s} {hub('Neptune','Earth',H):9.2f} {np.median(h):11.2f} {max(h):10.2f} {same:11.2f} {4:19d}")
