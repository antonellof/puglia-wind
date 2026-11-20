#!/usr/bin/env python3
"""Horizontal wind speed at a fixed height above ground, for one solved run.

    scripts/hub_height.py RUN [--agl 100]

Needs the reconstructed latest time and the cell centres
(postProcess -func writeCellCentres -latestTime). Because the mesh is a
single structured block, cell (i, j, k) is number i + n*(j + n*k), so every
column is interpolated to the requested height directly.

Writes RUN/hub_<agl>m.npz with the speed, the speed-up against the inflow at
the same height, and the ground height of each column.
"""
import argparse
import json
import os
import re

import numpy as np


def latest_time(run):
    times = [d for d in os.listdir(run) if re.fullmatch(r"[0-9.eE+-]+", d) and d != "0"]
    if not times:
        raise SystemExit(f"{run}: no solved time directory; run reconstructPar")
    return max(times, key=float)


def read_field(path, ncomp):
    txt = open(path).read()
    m = re.search(r"internalField\s+nonuniform\s+List<\w+>\s*\n?(\d+)\s*\n?\(", txt)
    if not m:
        raise SystemExit(f"{path}: expected an ascii nonuniform internalField")
    n = int(m.group(1))
    end = txt.index("\n)\n", m.end())
    a = np.array(txt[m.end():end].replace("(", " ").replace(")", " ").split(), dtype=float)
    if a.size != n * ncomp:
        raise SystemExit(f"{path}: expected {n} values, parsed {a.size // ncomp}")
    return a.reshape(n, ncomp) if ncomp > 1 else a


def read_points(path):
    txt = open(path).read()
    m = re.search(r"\n(\d+)\s*\n\(", txt)
    n = int(m.group(1))
    a = np.array(txt[m.end():txt.rindex(")")].replace("(", " ").replace(")", " ").split(), dtype=float)
    return a.reshape(n, 3)


def column_interp(z, v, zt):
    """Linear interpolation of v at height zt for every column (axis 0 is k)."""
    k = np.clip((z < zt).sum(axis=0), 1, z.shape[0] - 1)
    jj, ii = np.indices(zt.shape)
    z0, z1 = z[k - 1, jj, ii], z[k, jj, ii]
    v0, v1 = v[k - 1, jj, ii], v[k, jj, ii]
    w = np.clip((zt - z0) / (z1 - z0), 0, 1)
    return v0 + w * (v1 - v0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--agl", type=float, default=100.0)
    a = ap.parse_args()

    mesh = json.load(open(os.path.join(a.run, "mesh.json")))
    wind = json.load(open(os.path.join(a.run, "wind.json")))
    n, nz = mesh["n"], mesh["nz"]
    t = latest_time(a.run)
    U = read_field(os.path.join(a.run, t, "U"), 3).reshape(nz, n, n, 3)
    C = read_field(os.path.join(a.run, t, "C"), 3).reshape(nz, n, n, 3)
    P = read_points(os.path.join(a.run, "constant", "polyMesh", "points")).reshape(nz + 1, n + 1, n + 1, 3)

    zg = 0.25 * (P[0, :-1, :-1, 2] + P[0, 1:, :-1, 2] + P[0, :-1, 1:, 2] + P[0, 1:, 1:, 2])
    speed = np.hypot(U[..., 0], U[..., 1])
    s = column_interp(C[..., 2], speed, zg + a.agl)
    ux = column_interp(C[..., 2], U[..., 0], zg + a.agl)
    uy = column_interp(C[..., 2], U[..., 1], zg + a.agl)

    # Inflow reference: the log profile the ABL inlet imposes, at the same height.
    kappa, cmu = 0.4, 0.09
    ustar = kappa * wind["uref"] / np.log((wind["zref"] + wind["z0"]) / wind["z0"])
    uin = ustar / kappa * np.log((a.agl + wind["z0"]) / wind["z0"])

    rot = np.radians(mesh.get("rotate", 0.0))
    xl, yl = C[0, ..., 0], C[0, ..., 1]
    east = xl * np.cos(rot) - yl * np.sin(rot)
    north = xl * np.sin(rot) + yl * np.cos(rot)
    ue = ux * np.cos(rot) - uy * np.sin(rot)
    un = ux * np.sin(rot) + uy * np.cos(rot)
    out = os.path.join(a.run, f"hub_{a.agl:g}m.npz")
    np.savez_compressed(out, speed=s, speedup=s / uin, ground=zg, east=east, north=north, ue=ue, un=un, dx=mesh["dx"],
                        time=float(t), uin=uin, **{k: v for k, v in wind.items()})
    print(f"{out}: time {t}, inflow {uin:.2f} m/s at {a.agl:g} m, speed {s.min():.2f} to "
          f"{s.max():.2f} m/s, speed-up {s.min() / uin:.2f} to {s.max() / uin:.2f}")


if __name__ == "__main__":
    main()
