#!/usr/bin/env python3
"""Where do the built turbines sit in the modelled wind field?

    scripts/turbine_check.py case/runs/mesh-200-climate.npz

Samples the long-term mean speed at each OSM turbine (nearest column) and
compares it with the whole domain, outside the flat edge ring.
"""
import argparse
import json

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("climate")
ap.add_argument("--turbines", default="data/turbines.json")
ap.add_argument("--ring", type=float, default=3000.0, help="edge ring to exclude [m]")
ap.add_argument("-o", "--out", default="report/turbine_check.json")
a = ap.parse_args()
d = np.load(a.climate)
E, N, U, Z = d["east"], d["north"], d["mean"], d["ground"]
t = json.load(open(a.turbines))

n = E.shape[0]
inner = np.zeros_like(U, dtype=bool)
k = int(round(a.ring / float(d["dx"])))
inner[k:n - k, k:n - k] = True

pts = np.c_[E.ravel(), N.ravel()]
ut, zt = [], []
for p in t:
    i = np.argmin((pts[:, 0] - p["x"]) ** 2 + (pts[:, 1] - p["y"]) ** 2)
    if inner.ravel()[i]:
        ut.append(U.ravel()[i])
        zt.append(Z.ravel()[i])
ut, ud, zt, zd = np.array(ut), U[inner], np.array(zt), Z[inner]
pct = np.array([(ud < u).mean() * 100 for u in ut])
# Elevation alone as the competing explanation: ridges are both high and windy.
zpct = np.array([(zd < z).mean() * 100 for z in zt])
# Among the cells as high as the turbines, are the turbines on the windier ones?
cond = []
for u, z in zip(ut, zt):
    band = np.abs(zd - z) < 25.0
    cond.append((ud[band] < u).mean() * 100)
res = dict(turbines=int(ut.size), turbine_mean=float(ut.mean()), domain_mean=float(ud.mean()),
           turbine_median_percentile=float(np.median(pct)),
           share_in_top_quarter=float((pct >= 75).mean()),
           share_in_bottom_quarter=float((pct < 25).mean()),
           turbine_median_elevation_percentile=float(np.median(zpct)),
           median_percentile_among_same_elevation=float(np.median(cond)))
json.dump(res, open(a.out, "w"), indent=1)
print(f"{ut.size} turbines inside the ring: mean {ut.mean():.2f} m/s vs domain {ud.mean():.2f} m/s; "
      f"median turbine sits at percentile {np.median(pct):.0f}; "
      f"{100 * (pct >= 75).mean():.0f} % in the windiest quarter, {100 * (pct < 25).mean():.0f} % in the calmest")
print(f"elevation alone: median turbine at percentile {np.median(zpct):.0f}; among cells within 25 m "
      f"of the same elevation, the median turbine is at percentile {np.median(cond):.0f} of wind")
