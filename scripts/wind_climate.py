#!/usr/bin/env python3
"""Wind climate at the site from ERA5 (via the Open-Meteo archive API).

    scripts/wind_climate.py --lat 41.38 --lon 15.18 --start 2015-01-01 --end 2024-12-31

Downloads hourly 100 m wind speed and direction once (cached in data/), bins
them into 12 sectors of 30 degrees and writes data/wind_climate.json with the
frequency, mean speed and Weibull fit of each sector. The sector centres are
the directions the CFD sweep runs.
"""
import argparse
import json
import math
import os
import urllib.parse
import urllib.request

import numpy as np

API = "https://archive-api.open-meteo.com/v1/archive"


def weibull_fit(u):
    """Weibull k and A from the mean and standard deviation (Justus' approximation)."""
    u = u[u > 0.1]
    k = (np.std(u) / np.mean(u)) ** -1.086
    a = np.mean(u) / math.gamma(1 + 1 / k)
    return float(k), float(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=41.38)
    ap.add_argument("--lon", type=float, default=15.18)
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--sectors", type=int, default=12)
    ap.add_argument("-o", "--out", default="data/wind_climate.json")
    a = ap.parse_args()

    cache = f"data/era5_{a.lat}_{a.lon}_{a.start}_{a.end}.json"
    if not os.path.exists(cache):
        q = urllib.parse.urlencode(dict(latitude=a.lat, longitude=a.lon, start_date=a.start,
                                        end_date=a.end, models="era5",
                                        hourly="wind_speed_100m,wind_direction_100m",
                                        wind_speed_unit="ms", timezone="UTC"))
        os.makedirs("data", exist_ok=True)
        with urllib.request.urlopen(f"{API}?{q}", timeout=300) as r:
            open(cache, "wb").write(r.read())
    d = json.load(open(cache))
    u = np.array(d["hourly"]["wind_speed_100m"], dtype=float)
    th = np.array(d["hourly"]["wind_direction_100m"], dtype=float)
    ok = ~(np.isnan(u) | np.isnan(th))
    u, th = u[ok], th[ok]

    width = 360 / a.sectors
    idx = np.floor(((th + width / 2) % 360) / width).astype(int)
    sectors = []
    for s in range(a.sectors):
        m = idx == s
        k, A = weibull_fit(u[m])
        sectors.append(dict(dir=s * width, freq=float(m.mean()), mean=float(u[m].mean()),
                            k=k, A=A, hours=int(m.sum())))
    k, A = weibull_fit(u)
    out = dict(source="ERA5 via Open-Meteo archive API", lat=d["latitude"], lon=d["longitude"],
               elevation=d.get("elevation"), start=a.start, end=a.end, height_m=100,
               hours=int(u.size), mean=float(u.mean()), k=k, A=A, sectors=sectors)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{a.out}: {u.size} hours, mean {u.mean():.2f} m/s at 100 m, Weibull k {k:.2f} A {A:.2f}")
    for s in sorted(sectors, key=lambda s: -s["freq"])[:5]:
        print(f"  {s['dir']:5.0f} deg  {100 * s['freq']:4.1f} %  mean {s['mean']:.1f} m/s")


if __name__ == "__main__":
    main()
