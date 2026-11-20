#!/usr/bin/env python3
"""Map of the hub-height speed-up for one run, over a hillshade.

    report/plot_map.py case/runs/d300/hub_100m.npz -o report/figures/speedup_d300.png
"""
import argparse
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SLOW, FAST = "#2a78d6", "#eb6834"
CMAP = LinearSegmentedColormap.from_list("speedup", [SLOW, "#d9d8d3", FAST])


def hillshade(z, dx, az=315, alt=40):
    gy, gx = np.gradient(z, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, e = math.radians(az), math.radians(alt)
    return np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hub")
    ap.add_argument("--turbines", default="data/turbines.json")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    d = np.load(a.hub)
    x, y = d["x"] / 1000, d["y"] / 1000
    su, zg = d["speedup"], d["ground"]
    dx = float(x[1] - x[0]) * 1000

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
                         "axes.edgecolor": GRID})
    fig, ax = plt.subplots(figsize=(7.2, 6.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ext = (x[0], x[-1], y[0], y[-1])
    ax.imshow(hillshade(zg, dx), origin="lower", extent=ext, cmap="gray", vmin=-0.2, vmax=1.1)
    lo, hi = float(su.min()), float(su.max())
    norm = TwoSlopeNorm(vcenter=1.0, vmin=min(lo, 0.99), vmax=max(hi, 1.01))
    im = ax.imshow(su, origin="lower", extent=ext, cmap=CMAP, norm=norm, alpha=0.72)
    cs = ax.contour(x, y, zg, levels=np.arange(200, 1201, 200), colors=INK_2, linewidths=0.4, alpha=0.6)
    ax.clabel(cs, fmt="%d m", fontsize=6.5, colors=INK_2)

    if os.path.exists(a.turbines):
        t = json.load(open(a.turbines))
        if t:
            ax.scatter([p["x"] / 1000 for p in t], [p["y"] / 1000 for p in t], s=9, marker="^",
                       facecolor=INK, edgecolor=SURFACE, linewidth=0.5, label=f"Wind turbines in OSM ({len(t)})")
            ax.legend(loc="lower left", frameon=False, fontsize=8)

    # Arrow showing where the wind blows towards.
    th = math.radians(float(d["dir"]))
    ux, uy = -math.sin(th), -math.cos(th)
    x0, y0 = x[-1] - 0.14 * (x[-1] - x[0]), y[-1] - 0.12 * (y[-1] - y[0])
    ax.annotate("", xy=(x0 + 2 * ux, y0 + 2 * uy), xytext=(x0 - 2 * ux, y0 - 2 * uy),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4))
    ax.text(x0, y0 - 3.2, f"wind from {float(d['dir']):.0f}°", ha="center", fontsize=8, color=INK)

    cb = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    cb.set_label(f"speed at 100 m above ground / inflow speed", color=INK_2)
    cb.outline.set_visible(False)
    ax.set_xlabel("km east of domain centre")
    ax.set_ylabel("km north of domain centre")
    ax.set_title("Monti Dauni, wind speed-up 100 m above ground", loc="left", fontsize=11, color=INK)
    ax.set_aspect("equal")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    print(a.out)


if __name__ == "__main__":
    main()
