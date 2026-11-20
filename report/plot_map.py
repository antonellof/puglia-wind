#!/usr/bin/env python3
"""Maps over a hillshade, in km east/north of the domain centre.

    report/plot_map.py case/runs/mesh-200-d300/hub_100m.npz -o report/figures/speedup_d300.png
    report/plot_map.py case/runs/mesh-200-climate.npz --field mean -o report/figures/mean_wind.png

--field speedup (one direction, diverging around 1.0), mean (long-term mean
speed, sequential) or power (wind power density, sequential).
"""
import argparse
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, Normalize

INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
DIVERGING = LinearSegmentedColormap.from_list("speedup", ["#2a78d6", "#d9d8d3", "#eb6834"])
SEQUENTIAL = LinearSegmentedColormap.from_list("seq", ["#f3efe6", "#f2b48c", "#eb6834", "#a8351a", "#5a1a0b"])

LABELS = {
    "speedup": "speed 100 m above ground / inflow speed",
    "mean": "mean wind speed 100 m above ground [m/s]",
    "power": "wind power density 100 m above ground [W/m²]",
}


def hillshade(z, dx, az=315, alt=40):
    gy, gx = np.gradient(z, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, e = math.radians(az), math.radians(alt)
    return np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--field", default="speedup", choices=list(LABELS))
    ap.add_argument("--turbines", default="data/turbines.json")
    ap.add_argument("--title", default=None)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    d = np.load(a.npz)
    E, N = d["east"] / 1000, d["north"] / 1000
    v, zg = d[a.field], d["ground"]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
                         "axes.edgecolor": GRID})
    fig, ax = plt.subplots(figsize=(7.2, 6.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.pcolormesh(E, N, hillshade(zg, float(d["dx"])), shading="auto", cmap="gray", vmin=-0.3, vmax=1.15,
                  rasterized=True, edgecolors="none", antialiased=False)
    if a.field == "speedup":
        norm = TwoSlopeNorm(vcenter=1.0, vmin=min(float(v.min()), 0.99), vmax=max(float(v.max()), 1.01))
        cmap = DIVERGING
    else:
        norm, cmap = Normalize(vmin=float(np.percentile(v, 1)), vmax=float(np.percentile(v, 99.5))), SEQUENTIAL
    im = ax.pcolormesh(E, N, v, shading="auto", cmap=cmap, norm=norm, alpha=0.7, rasterized=True,
                       edgecolors="none", antialiased=False)
    cs = ax.contour(E, N, zg, levels=np.arange(200, 1201, 200), colors=INK_2, linewidths=0.4, alpha=0.55)
    ax.clabel(cs, fmt="%d m", fontsize=6.5, colors=INK_2)

    if os.path.exists(a.turbines):
        t = json.load(open(a.turbines))
        if t:
            ax.scatter([p["x"] / 1000 for p in t], [p["y"] / 1000 for p in t], s=7, marker="^",
                       facecolor=INK, edgecolor=SURFACE, linewidth=0.4, zorder=3,
                       label=f"wind turbines mapped in OpenStreetMap ({len(t)})")
            ax.legend(loc="upper left", bbox_to_anchor=(0, -0.09), frameon=False, fontsize=8)

    if "dir" in d.files:
        th = math.radians(float(d["dir"]))
        ux, uy = -math.sin(th), -math.cos(th)
        x0, y0 = float(E.max()) - 3.5, float(N.max()) - 3.0
        ax.annotate("", xy=(x0 + 1.8 * ux, y0 + 1.8 * uy), xytext=(x0 - 1.8 * ux, y0 - 1.8 * uy),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4), zorder=4)
        ax.text(x0, y0 - 2.9, f"wind from {float(d['dir']):.0f}°", ha="center", fontsize=8, zorder=4)

    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cb.set_label(LABELS[a.field], color=INK_2)
    cb.outline.set_visible(False)
    ax.set_xlabel("km east of domain centre")
    ax.set_ylabel("km north of domain centre")
    ax.set_title(a.title or "Monti Dauni", loc="left", fontsize=11)
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(False)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    print(a.out)


if __name__ == "__main__":
    main()
