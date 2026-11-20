#!/usr/bin/env python3
"""Wind turbine positions in the domain from OpenStreetMap (Overpass API).

    scripts/turbines.py --mesh case/runs/mesh-200/mesh.json

Writes data/turbines.json with lon, lat and local x, y (UTM 33N minus the
domain centre). OSM coverage is volunteered; treat it as indicative.
"""
import argparse
import json
import urllib.parse
import urllib.request

import time

from osgeo import osr

osr.UseExceptions()
SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]

ap = argparse.ArgumentParser()
ap.add_argument("--mesh", required=True)
ap.add_argument("-o", "--out", default="data/turbines.json")
a = ap.parse_args()
m = json.load(open(a.mesh))
h = m["size"] / 2

wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
utm = osr.SpatialReference(); utm.ImportFromEPSG(32633)
for s in (wgs, utm):
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
inv = osr.CoordinateTransformation(utm, wgs)
fwd = osr.CoordinateTransformation(wgs, utm)
corners = [inv.TransformPoint(m["cx"] + sx * h, m["cy"] + sy * h)[:2] for sx in (-1, 1) for sy in (-1, 1)]
lons, lats = zip(*corners)
bbox = f"{min(lats)},{min(lons)},{max(lats)},{max(lons)}"
q = f'[out:json][timeout:120];node["power"="generator"]["generator:source"="wind"]({bbox});out;'
els = None
for url in SERVERS:
    req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "puglia-wind-study"})
    try:
        els = json.load(urllib.request.urlopen(req, timeout=180))["elements"]
        break
    except Exception as e:  # busy servers answer 429/502/504; try the next one
        print(f"{url}: {e}")
        time.sleep(5)
if els is None:
    raise SystemExit("all Overpass servers failed; retry later")
out = []
for e in els:
    x, y, _ = fwd.TransformPoint(e["lon"], e["lat"])
    x, y = x - m["cx"], y - m["cy"]
    if abs(x) < h and abs(y) < h:
        out.append(dict(lon=e["lon"], lat=e["lat"], x=x, y=y,
                        hub=e.get("tags", {}).get("height:hub") or e.get("tags", {}).get("height")))
json.dump(out, open(a.out, "w"), indent=1)
print(f"{a.out}: {len(out)} turbines in the domain (bbox {bbox})")
