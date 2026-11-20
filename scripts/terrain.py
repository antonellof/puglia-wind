#!/usr/bin/env python3
"""Cut a square terrain patch from Copernicus GLO-30 tiles, in UTM 33N.

    scripts/terrain.py --lat 41.38 --lon 15.18 --size 60000 --res 50 -o data/terrain.npz

The patch is centred on (lat, lon); --size is the side in metres. It is cut
larger than the CFD domain so the mesh script can rotate the domain and still
sample real terrain everywhere.

Sea: GLO-30 has no tiles over open water, so cells without data become 0 m.
A land mask comes from the ISTAT region outlines (scripts/locator.py downloads
them); cells outside every region are sea, set to 0 m and given the sea
roughness later.
"""
import argparse
import glob
import os
import subprocess
import tempfile

import json

import numpy as np
from matplotlib.path import Path
from osgeo import gdal, osr

gdal.UseExceptions()


def to_utm(lat, lon):
    src = osr.SpatialReference(); src.ImportFromEPSG(4326)
    dst = osr.SpatialReference(); dst.ImportFromEPSG(32633)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    x, y, _ = osr.CoordinateTransformation(src, dst).TransformPoint(lon, lat)
    return x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=41.38)
    ap.add_argument("--lon", type=float, default=15.18)
    ap.add_argument("--size", type=float, default=60000.0)
    ap.add_argument("--res", type=float, default=50.0)
    ap.add_argument("--dem", default="data/dem")
    ap.add_argument("--regions", default="data/boundaries/regions.geojson")
    ap.add_argument("-o", "--out", default="data/terrain.npz")
    a = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(a.dem, "*.tif")))
    if not tiles:
        raise SystemExit(f"no tiles in {a.dem}; run scripts/fetch_dem.sh")
    cx, cy = to_utm(a.lat, a.lon)
    h = a.size / 2
    with tempfile.TemporaryDirectory() as tmp:
        vrt = os.path.join(tmp, "dem.vrt")
        gdal.BuildVRT(vrt, tiles)
        ds = gdal.Warp("", vrt, format="MEM", dstSRS="EPSG:32633",
                       outputBounds=(cx - h, cy - h, cx + h, cy + h),
                       xRes=a.res, yRes=a.res, resampleAlg="bilinear",
                       dstNodata=-9999)
        z = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    # Row 0 of a GDAL raster is the north edge; flip so z[j, i] has y increasing with j.
    z = z[::-1, :]
    n = z.shape[0]
    x = cx - h + a.res * (np.arange(n) + 0.5)
    y = cy - h + a.res * (np.arange(n) + 0.5)
    nodata = np.isnan(z) | (z < -100)

    land = np.ones_like(z, dtype=bool)
    if os.path.exists(a.regions):
        wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
        utm = osr.SpatialReference(); utm.ImportFromEPSG(32633)
        for s in (wgs, utm):
            s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        tr = osr.CoordinateTransformation(wgs, utm)
        X, Y = np.meshgrid(x, y)
        pts = np.c_[X.ravel(), Y.ravel()]
        inside = np.zeros(len(pts), dtype=bool)
        for f in json.load(open(a.regions))["features"]:
            g = f["geometry"]
            for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
                ring = np.array(tr.TransformPoints([(lo, la) for lo, la in poly[0]]))[:, :2]
                if ring[:, 0].max() < x[0] or ring[:, 0].min() > x[-1] or ring[:, 1].max() < y[0] or ring[:, 1].min() > y[-1]:
                    continue
                inside |= Path(ring).contains_points(pts)
        land = inside.reshape(z.shape)
    elif nodata.any():
        raise SystemExit("patch has no-data cells and no region outlines for a land mask")
    z = np.where(nodata | ~land, 0.0, np.maximum(z, 0.0)).astype(np.float32)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    np.savez_compressed(a.out, z=z, land=land, x=x, y=y, cx=cx, cy=cy, lat=a.lat, lon=a.lon, res=a.res)
    print(f"{a.out}: {n}x{n} cells at {a.res:g} m, centre UTM33N ({cx:.0f}, {cy:.0f}), "
          f"elevation {z.min():.0f} to {z.max():.0f} m, land {100 * land.mean():.0f} %")


if __name__ == "__main__":
    main()
