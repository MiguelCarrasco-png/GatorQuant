"""Common-baseline geometry: Kepler propagation, light time, solar exclusion.

Units: positions in AU, time in hours since epoch (t=0 = 2026-09-22 00:00 TDB).
"""
import json
import math
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
LIGHT_MIN_PER_AU = 8.317
LIGHT_H_PER_AU = LIGHT_MIN_PER_AU / 60.0
EXCLUSION_AU = 0.10

SETTLEMENTS = ["Mercury", "Venus", "Earth", "Mars", "Ceres",
               "Jupiter", "Saturn", "Uranus", "Neptune"]
RELAYS = ["Relay A", "Relay B"]
NODE_ID = {n: i + 1 for i, n in enumerate(SETTLEMENTS + RELAYS)}


def _load():
    els = {b["name"]: b for b in json.loads((DATA / "orbital_elements.json").read_text())["bodies"]}
    for r in json.loads((DATA / "network_model.json").read_text())["relays"]:
        els[r["name"]] = r
    return els


ELEMENTS = _load()


def _kepler_E(M, e, tol=1e-14):
    E = M if e < 0.8 else np.full_like(M, math.pi)
    for _ in range(50):
        dE = (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
        E = E - dE
        if np.max(np.abs(dE)) < tol:
            break
    return E


def position(body, t_hours):
    """Heliocentric J2000-ecliptic position (AU) of `body` at t_hours (scalar or array)."""
    el = ELEMENTS[body]
    t = np.asarray(t_hours, dtype=float)
    days = t / 24.0
    M = np.radians((el["mean_anomaly_deg"] + el["mean_motion_deg_day"] * days) % 360.0)
    e, a = el["e"], el["a_au"]
    E = _kepler_E(M, e)
    xp = a * (np.cos(E) - e)
    yp = a * math.sqrt(1 - e * e) * np.sin(E)
    w, i, O = (math.radians(el[k]) for k in ("arg_peri_deg", "i_deg", "node_deg"))
    cw, sw, ci, si, cO, sO = math.cos(w), math.sin(w), math.cos(i), math.sin(i), math.cos(O), math.sin(O)
    x = (cO * cw - sO * sw * ci) * xp + (-cO * sw - sO * cw * ci) * yp
    y = (sO * cw + cO * sw * ci) * xp + (-sO * sw + cO * cw * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return np.stack([x, y, z], axis=-1)


def light_time(sender, receiver, t_e, tol_h=1e-3 / 3600):
    """Arrival time t_a (h) for a photon emitted at t_e (h): t_a - t_e = d(r_rx(t_a), r_tx(t_e)) * 8.317 min/AU.
    Returns (t_a, d_AU, blocked)."""
    t_e = np.asarray(t_e, dtype=float)
    rs = position(sender, t_e)
    t_a = t_e + np.linalg.norm(position(receiver, t_e) - rs, axis=-1) * LIGHT_H_PER_AU
    for _ in range(30):
        rr = position(receiver, t_a)
        d = np.linalg.norm(rr - rs, axis=-1)
        new = t_e + d * LIGHT_H_PER_AU
        if np.max(np.abs(new - t_a)) < tol_h:
            t_a = new
            break
        t_a = new
    rr = position(receiver, t_a)
    d = np.linalg.norm(rr - rs, axis=-1)
    return t_a, d, segment_blocked(rs, rr)


def segment_blocked(p, q, radius=EXCLUSION_AU):
    """True if the straight segment p->q passes within `radius` of the origin."""
    v = q - p
    vv = np.sum(v * v, axis=-1)
    s = np.clip(-np.sum(p * v, axis=-1) / vv, 0.0, 1.0)
    closest = p + s[..., None] * v
    return np.linalg.norm(closest, axis=-1) < radius


CHECK = {
    "Mercury": (-0.213426, -0.410281, -0.013955), "Venus": (0.679067, -0.257950, -0.042725),
    "Earth": (1.003581, -0.023693, -0.000003), "Mars": (0.247476, 1.526869, 0.025929),
    "Ceres": (0.375786, 2.653941, 0.014791), "Jupiter": (-3.438179, 4.038309, 0.060149),
    "Saturn": (9.271221, 1.717485, -0.398962), "Uranus": (8.962475, 17.253919, -0.052129),
    "Neptune": (29.839098, 1.351785, -0.715470), "Relay A": (2.0, 2.0, 0.0), "Relay B": (-2.0, 2.0, 0.0),
}

if __name__ == "__main__":
    worst = 0
    for b, ref in CHECK.items():
        p = position(b, 0.0)
        err = np.max(np.abs(p - np.array(ref)))
        worst = max(worst, err)
        print(f"{b:8s} {p[0]:+.6f} {p[1]:+.6f} {p[2]:+.6f}  max|err|={err:.2e}")
    print("worst epoch error", worst)
