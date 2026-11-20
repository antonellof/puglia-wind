#!/usr/bin/env python3
"""Region outlines and the domain square, for locator maps.

    scripts/locator.py --site dauni=case/runs/mesh-200/mesh.json --site gargano=case/runs/gargano-250/mesh.json

Reads ISTAT region boundaries (openpolis/geojson-italy, CC BY), keeps the
regions inside a southern Italy window, simplifies them and adds the corners
of the CFD domain in lon/lat.
"""
import argparse
import json
import math
import os
import sys
import urllib.request

from osgeo import osr

osr.UseExceptions()
sys.setrecursionlimit(100000)  # Douglas-Peucker recursion on long coastlines
URL = "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson"


def simplify(ring, tol):
    """Douglas-Peucker on a list of [lon, lat]."""
    if len(ring) < 3:
        return ring
    (x0, y0), (x1, y1) = ring[0], ring[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy) or 1e-12
    dmax, imax = 0.0, 0
    for i in range(1, len(ring) - 1):
        x, y = ring[i]
        d = abs(dy * x - dx * y + x1 * y0 - y1 * x0) / norm if norm > 1e-12 else math.hypot(x - x0, y - y0)
        if d > dmax:
            dmax, imax = d, i
    if dmax <= tol:
        return [ring[0], ring[-1]]
    return simplify(ring[: imax + 1], tol)[:-1] + simplify(ring[imax:], tol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", required=True, help="name=path/to/mesh.json")
    ap.add_argument("--geojson", default="data/boundaries/regions.geojson")
    ap.add_argument("--window", default="12.3,37.8,19.0,43.0", help="lon0,lat0,lon1,lat1")
    ap.add_argument("--tol", type=float, default=0.01, help="simplification tolerance [deg]")
    ap.add_argument("-o", "--out", default="docs/data/locator.json")
    a = ap.parse_args()

    if not os.path.exists(a.geojson):
        os.makedirs(os.path.dirname(a.geojson), exist_ok=True)
        urllib.request.urlretrieve(URL, a.geojson)
    lon0, lat0, lon1, lat1 = map(float, a.window.split(","))
    regions = []
    for f in json.load(open(a.geojson))["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            ring = poly[0]
            if not any(lon0 <= x <= lon1 and lat0 <= y <= lat1 for x, y in ring):
                continue
            s = simplify(ring, a.tol)
            if len(s) >= 4:
                rings.append([[round(x, 3), round(y, 3)] for x, y in s])
        if rings:
            regions.append(dict(name=f["properties"]["reg_name"], rings=rings))

    wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
    utm = osr.SpatialReference(); utm.ImportFromEPSG(32633)
    for s in (wgs, utm):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    inv = osr.CoordinateTransformation(utm, wgs)
    domains = {}
    for site in a.site:
        name, path = site.split("=", 1)
        m = json.load(open(path))
        h, r = m["size"] / 2, math.radians(m.get("rotate", 0.0))
        square = []
        for x, y in [(-h, -h), (h, -h), (h, h), (-h, h)]:
            e, n = x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)
            lon, lat, _ = inv.TransformPoint(m["cx"] + e, m["cy"] + n)
            square.append([round(lon, 4), round(lat, 4)])
        domains[name] = square

    out = dict(window=[lon0, lat0, lon1, lat1], regions=regions, domains=domains, highlight="Puglia",
               source="ISTAT region boundaries via openpolis/geojson-italy, CC BY")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    pts = sum(len(rr) for reg in regions for rr in reg["rings"])
    print(f"{a.out}: {len(regions)} regions, {pts} points, {os.path.getsize(a.out) / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
