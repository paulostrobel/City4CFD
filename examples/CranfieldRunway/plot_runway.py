#!/usr/bin/env python3
"""
Post-processing for the Cranfield runway microclimate case.

Panels:
  A — velocity magnitude at z = 1.75 m (pedestrian / apron level)
  B — wind speed along the runway centreline at z = 10 m (anemometer height)
  C — vertical ABL profiles above the runway midpoint and threshold

The frame is runway-aligned: x runs along runway 03/21 (03 threshold at
x ≈ -900 m, 21 threshold at x ≈ +900 m), wind from 214° enters at x-min.

Output: results_cfd.png
"""
import os

import numpy as np
import pyvista as pv
import matplotlib
matplotlib.rcParams["agg.path.chunksize"] = 10000
matplotlib.rcParams["path.simplify"] = True
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
STL_PATH   = os.path.join(CASE_DIR, "constant", "triSurface", "buildings.stl")
TIME       = 500.0
RWY_HALF   = 900.0     # runway half-length [m]

# ── load OpenFOAM solution ──────────────────────────────────────────────────
print("Reading OpenFOAM case …")
foam_file = os.path.join(CASE_DIR, "Cranfield.foam")
if not os.path.exists(foam_file):
    open(foam_file, "w").close()

reader = pv.OpenFOAMReader(foam_file)
reader.set_active_time_value(TIME)
mesh = reader.read()
vol  = mesh["internalMesh"].cell_data_to_point_data()
print(f"  Volume mesh: {vol.n_points:,} points, {vol.n_cells:,} cells")

# ── figure ──────────────────────────────────────────────────────────────────
cmap_vel  = cm.jet
cmap_norm = mcolors.Normalize(vmin=0.0, vmax=8.0)

fig = plt.figure(figsize=(18, 10))
fig.patch.set_facecolor("#1a1a2e")

# ── panel A: plan view at z = 1.75 m ───────────────────────────────────────
print("Slicing at z=1.75 m …")
slice_z = vol.slice(normal="z", origin=(0, 0, 1.75))
slice_z["U_mag"] = np.linalg.norm(slice_z["U"], axis=1)

ax1 = fig.add_axes([0.03, 0.08, 0.55, 0.88])
ax1.set_facecolor("#0a0a1a")
pts = np.array(slice_z.points)
ax1.scatter(pts[:, 0], pts[:, 1], c=cmap_vel(cmap_norm(slice_z["U_mag"])),
            s=0.3, linewidths=0, rasterized=True)

# building footprints
bld = pv.read(STL_PATH)
bpts = np.array(bld.points)
ax1.scatter(bpts[:, 0], bpts[:, 1], c="white", s=0.05,
            linewidths=0, alpha=0.25, rasterized=True)

# runway outline (03 threshold → 21 threshold, 45 m wide)
ax1.plot([-RWY_HALF, RWY_HALF, RWY_HALF, -RWY_HALF, -RWY_HALF],
         [-22.5, -22.5, 22.5, 22.5, -22.5],
         color="cyan", lw=1.0, ls="--")
ax1.text(-RWY_HALF, 60, "RWY 03", color="cyan", fontsize=8)
ax1.text(RWY_HALF - 150, 60, "RWY 21", color="cyan", fontsize=8)

ax1.set_xlim(-1850, 2350)
ax1.set_ylim(-1650, 1650)
ax1.set_aspect("equal")
ax1.tick_params(colors="white"); ax1.spines[:].set_color("#444")
for lbl in ax1.get_xticklabels() + ax1.get_yticklabels():
    lbl.set_color("white")
ax1.set_xlabel("x — runway axis  (m)", color="white", fontsize=9)
ax1.set_ylabel("y  (m)", color="white", fontsize=9)
ax1.set_title("Velocity magnitude — z = 1.75 m  (wind from 214°, along runway)",
              color="white", fontsize=11)
ax1.annotate("", xy=(-1500, -1500), xytext=(-1750, -1500),
             arrowprops=dict(arrowstyle="->", color="white", lw=1.5))
ax1.text(-1620, -1560, "wind 214°", color="white", fontsize=8, ha="center")

sm = cm.ScalarMappable(norm=cmap_norm, cmap=cmap_vel)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax1, orientation="horizontal",
                    fraction=0.025, pad=0.06, shrink=0.6)
cbar.set_label("|U|  (m/s)", color="white", fontsize=9)
cbar.ax.xaxis.set_tick_params(color="white")
plt.setp(cbar.ax.xaxis.get_ticklabels(), color="white")
cbar.outline.set_edgecolor("#444")

# ── panel B: centreline wind at z = 10 m (anemometer height) ───────────────
print("Sampling runway centreline …")
ax2 = fig.add_axes([0.65, 0.55, 0.31, 0.38])
ax2.set_facecolor("#0a0a1a")

line = pv.Line((-RWY_HALF, 0, 10.0), (RWY_HALF, 0, 10.0), resolution=400)
s = vol.sample(line)
x_cl = np.array(s.points)[:, 0]
U_cl = np.array(s["U"])
ax2.plot(x_cl, np.linalg.norm(U_cl, axis=1), color="#00aaff", lw=1.5,
         label="|U|")
ax2.plot(x_cl, U_cl[:, 0], color="#ffaa00", lw=1.0, ls="--",
         label="headwind $U_x$")
ax2.plot(x_cl, U_cl[:, 1], color="#ff5555", lw=1.0, ls=":",
         label="crosswind $U_y$")
ax2.set_xlabel("distance along runway  (m)", color="white", fontsize=9)
ax2.set_ylabel("wind speed  (m/s)", color="white", fontsize=9)
ax2.set_title("Runway centreline — z = 10 m", color="white", fontsize=9)
ax2.tick_params(colors="white"); ax2.spines[:].set_color("#444")
for lbl in ax2.get_xticklabels() + ax2.get_yticklabels():
    lbl.set_color("white")
ax2.legend(fontsize=8, labelcolor="white", framealpha=0.3)

# ── panel C: vertical profiles ─────────────────────────────────────────────
print("Sampling vertical profiles …")
ax3 = fig.add_axes([0.65, 0.08, 0.31, 0.38])
ax3.set_facecolor("#0a0a1a")

for x_p, colour, label in [(-RWY_HALF, "#00ff88", "RWY 03 threshold"),
                           (0.0,       "#00aaff", "midfield"),
                           (RWY_HALF,  "#ffaa00", "RWY 21 threshold")]:
    line3d = pv.Line((x_p, 0, 0.1), (x_p, 0, 300), resolution=200)
    sampled = vol.sample(line3d)
    z_prof = np.array(sampled.points)[:, 2]
    U_prof = np.linalg.norm(np.array(sampled["U"]), axis=1)
    ax3.plot(U_prof, z_prof, color=colour, lw=1.5, label=label)

ax3.axhline(10, color="#888", lw=0.8, ls="--", label="z = 10 m")
ax3.set_xlabel("|U|  (m/s)", color="white", fontsize=9)
ax3.set_ylabel("z  (m)", color="white", fontsize=9)
ax3.set_title("Vertical profiles on centreline", color="white", fontsize=9)
ax3.tick_params(colors="white"); ax3.spines[:].set_color("#444")
for lbl in ax3.get_xticklabels() + ax3.get_yticklabels():
    lbl.set_color("white")
ax3.legend(fontsize=8, labelcolor="white", framealpha=0.3)

fig.suptitle("Cranfield University runway — Microclimate CFD  |  "
             f"simpleFoam kε  |  t = {TIME:.0f}",
             color="white", fontsize=13, y=0.99)

out = os.path.join(SCRIPT_DIR, "results_cfd.png")
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")
plt.close()
