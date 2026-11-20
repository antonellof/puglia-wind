#!/usr/bin/env python3
"""Combine the direction sweep with the ERA5 climate into long-term maps.

    scripts/wind_map.py case/runs/mesh-200 --climate data/wind_climate.json

For each sector s the solved speed-up S_s(x, y) at hub height scales the
ERA5 Weibull distribution of that sector (A_s -> S_s * A_s, same k_s). Then

    mean speed     U(x, y) = sum_s f_s * S_s * A_s * Gamma(1 + 1/k_s)
    power density  P(x, y) = sum_s f_s * 0.5 * rho * (S_s * A_s)^3 * Gamma(1 + 3/k_s)

This treats the ERA5 point as the undisturbed inflow, which is the main
simplification: ERA5 already sees a smoothed version of the same hills.
Writes <mesh>-climate.npz next to the runs.
"""
import argparse
import glob
import json
import math
import os

import numpy as np

RHO = 1.20  # kg/m3, about 400 m above sea level


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("--climate", default="data/wind_climate.json")
    ap.add_argument("--agl", type=float, default=100.0)
    a = ap.parse_args()
    clim = json.load(open(a.climate))
    name = os.path.basename(os.path.normpath(a.mesh))

    U = P = None
    used = []
    for s in clim["sectors"]:
        f = f"case/runs/{name}-d{s['dir']:g}/hub_{a.agl:g}m.npz"
        if not os.path.exists(f):
            raise SystemExit(f"missing {f}; run scripts/run_sweep.sh {a.mesh}")
        d = np.load(f)
        S, k, A = d["speedup"], s["k"], s["A"]
        u = s["freq"] * S * A * math.gamma(1 + 1 / k)
        p = s["freq"] * 0.5 * RHO * (S * A) ** 3 * math.gamma(1 + 3 / k)
        U = u if U is None else U + u
        P = p if P is None else P + p
        used.append(s["dir"])
        east, north, zg, dx = d["east"], d["north"], d["ground"], d["dx"]
    ref_u = sum(s["freq"] * s["A"] * math.gamma(1 + 1 / s["k"]) for s in clim["sectors"])
    out = f"case/runs/{name}-climate.npz"
    np.savez_compressed(out, mean=U, power=P, east=east, north=north, dx=dx, ground=zg, ref_mean=ref_u, sectors=used)
    print(f"{out}: mean speed {U.min():.2f} to {U.max():.2f} m/s (ERA5 point {ref_u:.2f}), "
          f"power density {P.min():.0f} to {P.max():.0f} W/m2")


if __name__ == "__main__":
    main()
