#!/usr/bin/env python3
"""Copy the case template for one wind direction, reusing a built mesh.

    scripts/setup_case.py RUN --mesh MESHCASE --dir 300 [--uref 10 --zref 100 --z0 0.1]

--dir is the meteorological direction the wind blows from, in degrees
(0 north, 90 east). The mesh frame is UTM rotated by mesh.json "rotate"
degrees, so flowDir is rotated back into it.
"""
import argparse
import json
import math
import os
import shutil

here = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(here, "..", "case", "template")

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--mesh", required=True, help="case directory holding constant/polyMesh")
ap.add_argument("--dir", type=float, required=True)
ap.add_argument("--uref", type=float, default=10.0)
ap.add_argument("--zref", type=float, default=100.0)
ap.add_argument("--z0", type=float, default=0.1)
ap.add_argument("--procs", type=int, default=4)
a = ap.parse_args()

if os.path.exists(a.run):
    shutil.rmtree(a.run)
shutil.copytree(TEMPLATE, a.run)
shutil.copytree(os.path.join(a.mesh, "constant", "polyMesh"),
                os.path.join(a.run, "constant", "polyMesh"))
shutil.copy(os.path.join(a.mesh, "mesh.json"), a.run)

rot = math.radians(json.load(open(os.path.join(a.mesh, "mesh.json"))).get("rotate", 0.0))
th = math.radians(a.dir)
ex, ny = -math.sin(th), -math.cos(th)  # direction the wind blows towards, east/north
fx = ex * math.cos(rot) + ny * math.sin(rot)
fy = -ex * math.sin(rot) + ny * math.cos(rot)
abl = os.path.join(a.run, "0", "include", "ABLConditions")
txt = open(abl).read()
for key, val in [("Uref", f"{a.uref:g}"), ("Zref", f"{a.zref:g}"),
                 ("z0", f"uniform {a.z0:g}"), ("flowDir", f"({fx:.6f} {fy:.6f} 0)")]:
    lines = [l for l in txt.splitlines() if not l.startswith(key + " ")]
    txt = "\n".join(lines) + f"\n{key:<12}{val};\n"
open(abl, "w").write(txt)

# The internal field starts as a uniform flow in the wind direction.
u = os.path.join(a.run, "0", "U")
s = open(u).read().replace("uniform (0 0 0)", f"uniform ({a.uref * fx:.4f} {a.uref * fy:.4f} 0)", 1)
open(u, "w").write(s)

dec = os.path.join(a.run, "system", "decomposeParDict")
s = open(dec).read().replace("numberOfSubdomains 4;", f"numberOfSubdomains {a.procs};")
open(dec, "w").write(s)

json.dump(dict(dir=a.dir, uref=a.uref, zref=a.zref, z0=a.z0, procs=a.procs),
          open(os.path.join(a.run, "wind.json"), "w"), indent=1)
print(f"{a.run}: wind from {a.dir:g} deg, flowDir ({fx:.3f} {fy:.3f} 0), Uref {a.uref:g} m/s at {a.zref:g} m")
