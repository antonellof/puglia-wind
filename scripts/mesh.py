#!/usr/bin/env python3
"""Build a terrain-following hex mesh for one case directory.

    scripts/mesh.py CASE --terrain data/terrain.npz --size 24000 --dx 200 --nz 40

Steps:
  1. write system/blockMeshDict for a flat unit-height block (patches: ground,
     top, sides) with geometric grading towards the ground, and run blockMesh;
  2. move every point column onto the terrain: z = h + s * (ztop - h), where s
     is the graded height from step 1;
  3. the block is rotated by --rotate degrees (anticlockwise) against UTM, so
     no sector direction (multiples of 30) runs parallel to a side. With a
     side parallel to the wind the face flux is near zero, the inlet/outlet
     switch flickers every iteration, and the cross-stream residual stalls
     around 1e-2;
  4. near the edges, blend the terrain to a flat ring at the mean edge height,
     so the ABL inflow on the sides sees level ground. All four sides use the
     same inlet/outlet condition, and one mesh serves every wind direction.

Writes case/mesh.json with what the solver and post-processing need.
"""
import argparse
import json
import os
import re
import subprocess

import numpy as np
from scipy.ndimage import map_coordinates

BLOCKMESH = """FoamFile {{ version 2.0; format ascii; class dictionary; object blockMeshDict; }}
scale 1;
vertices
(
    ({x0} {y0} 0) ({x1} {y0} 0) ({x1} {y1} 0) ({x0} {y1} 0)
    ({x0} {y0} 1) ({x1} {y0} 1) ({x1} {y1} 1) ({x0} {y1} 1)
);
blocks ( hex (0 1 2 3 4 5 6 7) ({n} {n} {nz}) simpleGrading (1 1 {grading}) );
boundary
(
    ground {{ type wall;  faces ((0 3 2 1)); }}
    top    {{ type patch; faces ((4 5 6 7)); }}
    sides  {{ type patch; faces ((0 1 5 4) (1 2 6 5) (2 3 7 6) (3 0 4 7)); }}
);
"""


def read_points(path):
    txt = open(path).read()
    m =re.search(r"\n(\d+)\s*\n\(", txt)
    if not m:
        raise SystemExit(f"cannot parse {path} (needs writeFormat ascii)")
    n = int(m.group(1))
    start = m.end()
    end = txt.rindex(")")
    arr = np.array(txt[start:end].replace("(", " ").replace(")", " ").split(), dtype=float)
    if arr.size != 3 * n:
        raise SystemExit(f"{path}: expected {n} points, parsed {arr.size // 3}")
    return txt[:m.start()], arr.reshape(n, 3)


def write_points(path, header, p):
    with open(path, "w") as f:
        f.write(header)
        f.write(f"\n{len(p)}\n(\n")
        np.savetxt(f, p, fmt="(%.3f %.3f %.3f)")
        f.write(")\n")


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--terrain", default="data/terrain.npz")
    ap.add_argument("--size", type=float, default=24000.0, help="domain side [m]")
    ap.add_argument("--dx", type=float, default=200.0, help="horizontal cell size [m]")
    ap.add_argument("--nz", type=int, default=40)
    ap.add_argument("--grading", type=float, default=60.0, help="top/bottom cell height ratio")
    ap.add_argument("--blend", type=float, default=3000.0, help="width of the flat edge ring [m]")
    ap.add_argument("--rotate", type=float, default=15.0, help="mesh rotation against UTM [deg]")
    ap.add_argument("--headroom", type=float, default=3000.0, help="top above highest terrain [m]")
    a = ap.parse_args()

    t = np.load(a.terrain)
    zgrid, xg, yg, res = t["z"], t["x"], t["y"], float(t["res"])
    cx, cy = float(t["cx"]), float(t["cy"])
    n = int(round(a.size / a.dx))
    h = a.size / 2
    if a.size * 1.42 + 2 * a.dx > xg[-1] - xg[0]:
        raise SystemExit("terrain patch is smaller than the domain; cut a larger one")

    sysdir = os.path.join(a.case, "system")
    with open(os.path.join(sysdir, "blockMeshDict"), "w") as f:
        f.write(BLOCKMESH.format(x0=-h, x1=h, y0=-h, y1=h, n=n, nz=a.nz, grading=a.grading))
    subprocess.run(["blockMesh", "-case", a.case], check=True,
                   stdout=open(os.path.join(a.case, "log.blockMesh"), "w"))

    ppath = os.path.join(a.case, "constant", "polyMesh", "points")
    header, p = read_points(ppath)

    # Terrain height at every point, local coordinates relative to the centre.
    ca, sa = np.cos(np.radians(a.rotate)), np.sin(np.radians(a.rotate))
    east = p[:, 0] * ca - p[:, 1] * sa
    north = p[:, 0] * sa + p[:, 1] * ca
    fi = (east + cx - xg[0]) / res
    fj = (north + cy - yg[0]) / res
    ht = map_coordinates(zgrid, [fj, fi], order=1, mode="nearest")

    # Distance to the nearest edge decides the blend weight.
    edge = h - np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1]))
    w = smoothstep(edge / a.blend)
    ring = np.isclose(edge, 0.0, atol=1e-3) & np.isclose(p[:, 2], 0.0)
    h0 = float(ht[ring].mean())
    hb = w * ht + (1 - w) * h0

    ztop = float(zgrid.max() + a.headroom)
    p[:, 2] = hb + p[:, 2] * (ztop - hb)
    write_points(ppath, header, p)
    subprocess.run(["checkMesh", "-case", a.case], check=True,
                   stdout=open(os.path.join(a.case, "log.checkMesh"), "w"))

    q = a.grading ** (1.0 / (a.nz - 1))
    s1 = (q - 1) / (q ** a.nz - 1)
    info = dict(size=a.size, dx=a.dx, n=n, nz=a.nz, cells=n * n * a.nz, grading=a.grading,
                blend=a.blend, rotate=a.rotate, h0=h0, ztop=ztop, cx=cx, cy=cy, lat=float(t["lat"]),
                lon=float(t["lon"]), first_cell_min=s1 * (ztop - hb.max()),
                first_cell_max=s1 * (ztop - hb.min()), terrain_min=float(hb.min()),
                terrain_max=float(hb.max()))
    json.dump(info, open(os.path.join(a.case, "mesh.json"), "w"), indent=1)
    print(f"{a.case}: {info['cells']} cells ({n}x{n}x{a.nz}), terrain {hb.min():.0f} to "
          f"{hb.max():.0f} m, edge ring {h0:.0f} m, top {ztop:.0f} m, first cell "
          f"{info['first_cell_min']:.1f} to {info['first_cell_max']:.1f} m")


if __name__ == "__main__":
    main()
