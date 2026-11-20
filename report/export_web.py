#!/usr/bin/env python3
"""Pack terrain, solved fields and turbines for the 3D viewer in docs/.

    report/export_web.py case/runs/mesh-200 --terrain data/terrain.npz --res 50

Everything is in the mesh frame (UTM rotated by mesh.json "rotate"), in
metres from the domain centre; the viewer rotates the scene back so north
is up. Files:
  docs/data/meta.json     sizes, scales, directions, sector climate, turbines
  docs/data/terrain.bin   uint16 elevation [m], (nt x nt), display resolution
  docs/data/fields.bin    uint8 per field (nf x nf): for each direction
                          speed-up*100, then ux and uy as int8 (m/s * 6);
                          then the long-term mean speed * 30
"""
import argparse
import json
import os

import numpy as np
from scipy.ndimage import map_coordinates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("--terrain", default="data/terrain.npz")
    ap.add_argument("--climate", default="data/wind_climate.json")
    ap.add_argument("--turbines", default="data/turbines.json")
    ap.add_argument("--res", type=float, default=50.0, help="display terrain resolution [m]")
    ap.add_argument("-o", "--out", default="docs/data")
    a = ap.parse_args()

    name = os.path.basename(os.path.normpath(a.mesh))
    mesh = json.load(open(os.path.join(a.mesh, "mesh.json")))
    clim = json.load(open(a.climate))
    rot = np.radians(mesh["rotate"])
    ca, sa = np.cos(rot), np.sin(rot)
    h = mesh["size"] / 2
    os.makedirs(a.out, exist_ok=True)

    # Display terrain: the real DEM (no edge blending), sampled in the mesh frame.
    t = np.load(a.terrain)
    nt = int(round(mesh["size"] / a.res)) + 1
    s = np.linspace(-h, h, nt)
    X, Y = np.meshgrid(s, s)
    E, N = X * ca - Y * sa, X * sa + Y * ca
    fi = (E + float(t["cx"]) - t["x"][0]) / float(t["res"])
    fj = (N + float(t["cy"]) - t["y"][0]) / float(t["res"])
    z = map_coordinates(t["z"], [fj, fi], order=1)
    np.clip(z, 0, 65535).astype("<u2").tofile(os.path.join(a.out, "terrain.bin"))

    # Fields: one block of three bytes-per-cell arrays per direction, then the mean.
    blocks, dirs = [], []
    for sec in clim["sectors"]:
        d = np.load(f"case/runs/{name}-d{sec['dir']:g}/hub_100m.npz")
        ux = d["ue"] * ca + d["un"] * sa      # back into the mesh frame
        uy = -d["ue"] * sa + d["un"] * ca
        blocks += [np.clip(np.round(d["speedup"] * 100), 0, 255).astype(np.uint8),
                   np.clip(np.round(ux * 6), -127, 127).astype(np.int8).view(np.uint8),
                   np.clip(np.round(uy * 6), -127, 127).astype(np.int8).view(np.uint8)]
        dirs.append(dict(dir=sec["dir"], freq=sec["freq"], mean=sec["mean"]))
    m = np.load(f"case/runs/{name}-climate.npz")
    blocks.append(np.clip(np.round(m["mean"] * 30), 0, 255).astype(np.uint8))
    np.concatenate([b.ravel() for b in blocks]).tofile(os.path.join(a.out, "fields.bin"))

    tur = []
    if os.path.exists(a.turbines):
        for p in json.load(open(a.turbines)):
            x = p["x"] * ca + p["y"] * sa
            y = -p["x"] * sa + p["y"] * ca
            if abs(x) < h and abs(y) < h:
                tur.append([round(x), round(y)])

    meta = dict(size=mesh["size"], rotate=mesh["rotate"], nt=nt, nf=mesh["n"], dx=mesh["dx"],
                cells=mesh["cells"], lat=mesh["lat"], lon=mesh["lon"], zmin=float(z.min()),
                zmax=float(z.max()), uref=10.0, agl=100, dirs=dirs, turbines=tur,
                mean_range=[float(np.percentile(m["mean"], 1)), float(np.percentile(m["mean"], 99.5))],
                era5_mean=clim["mean"], years=f"{clim['start'][:4]} to {clim['end'][:4]}")
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(a.out, f)) for f in ("meta.json", "terrain.bin", "fields.bin"))
    print(f"{a.out}: terrain {nt}x{nt}, fields {mesh['n']}x{mesh['n']} x {len(dirs)} directions, "
          f"{len(tur)} turbines, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
