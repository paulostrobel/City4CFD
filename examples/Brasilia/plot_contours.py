#!/usr/bin/env python3
"""
Extended CFD post-processing — multiple slice planes and scalar fields.

Panels:
  Row 1: |U| at z=1.75 m  |  |U| at z=10 m  |  |U| at z=50 m
  Row 2: p  at z=1.75 m   |  k at z=1.75 m   |  TKE at z=1.75 m (same as k but different cmap)
  Row 3: |U| XZ plane (y=0, vertical long.)  |  |U| YZ plane (x=0, vertical transv.)
  Row 4: streamlines XZ  |  streamlines YZ

Output: contours_cfd.png
"""
import numpy as np
import pyvista as pv
import matplotlib
matplotlib.rcParams['agg.path.chunksize'] = 10000
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import matplotlib.gridspec as gridspec
from mpl_toolkits.axes_grid1 import make_axes_locatable
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
STL_PATH   = os.path.join(CASE_DIR, "constant", "triSurface", "buildings.stl")

# ── load mesh ──────────────────────────────────────────────────────────────
print("Reading OpenFOAM case …")
foam_file = os.path.join(CASE_DIR, "Brasilia.foam")
if not os.path.exists(foam_file):
    open(foam_file, "w").close()

reader = pv.OpenFOAMReader(foam_file)
reader.set_active_time_value(500.0)
mesh = reader.read()

vol = mesh["internalMesh"].cell_data_to_point_data()
print(f"  {vol.n_points:,} points  |  fields: {vol.array_names}")

# precompute |U| and add to vol
U_vec = np.array(vol["U"])
vol["U_mag"] = np.linalg.norm(U_vec, axis=1)

# ── building STL for outlines ──────────────────────────────────────────────
bld_stl = pv.read(STL_PATH)
bld_pts = np.array(bld_stl.points)

# ── helper: scatter a slice onto an axis ───────────────────────────────────
def scatter_slice(ax, pts, vals, cmap, norm, s=0.4, alpha=1.0, rasterized=True):
    cols = cmap(norm(vals))
    ax.scatter(pts[:, 0], pts[:, 1], c=cols, s=s,
               linewidths=0, alpha=alpha, rasterized=rasterized)

def add_cbar(fig, ax, cmap, norm, label, horizontal=False):
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    if horizontal:
        cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                            fraction=0.04, pad=0.1, shrink=0.85)
    else:
        cbar = fig.colorbar(sm, ax=ax, orientation="vertical",
                            fraction=0.03, pad=0.02, shrink=0.9)
    cbar.set_label(label, color="white", fontsize=8)
    cbar.ax.tick_params(colors="white", labelsize=7)
    cbar.outline.set_edgecolor("#555")
    return cbar

def style_ax(ax, xlabel, ylabel, title, xlim=None, ylim=None):
    ax.set_facecolor("#0d0d1a")
    ax.tick_params(colors="white", labelsize=7)
    for sp in ax.spines.values(): sp.set_color("#444")
    ax.set_xlabel(xlabel, color="white", fontsize=8)
    ax.set_ylabel(ylabel, color="white", fontsize=8)
    ax.set_title(title,   color="white", fontsize=9)
    if xlim: ax.set_xlim(xlim)
    if ylim: ax.set_ylim(ylim)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("white")

# ── slices ─────────────────────────────────────────────────────────────────
print("Computing slices …")
sl_z175 = vol.slice(normal="z", origin=(0, 0, 1.75))
sl_z10  = vol.slice(normal="z", origin=(0, 0, 10.0))
sl_z50  = vol.slice(normal="z", origin=(0, 0, 50.0))
sl_xz   = vol.slice(normal="y", origin=(0, 0, 0))   # XZ at y=0
sl_yz   = vol.slice(normal="x", origin=(0, 0, 0))   # YZ at x=0

for sl in (sl_z175, sl_z10, sl_z50, sl_xz, sl_yz):
    sl["U_mag"] = np.linalg.norm(np.array(sl["U"]), axis=1)

# ── streamlines in XZ and YZ planes ────────────────────────────────────────
print("Computing streamlines …")
# XZ plane: seed a vertical line at inlet, y≈0
seed_xz = pv.Line((-1700, 0, 1.0), (-1700, 0, 200.0), resolution=40)
str_xz  = vol.streamlines_from_source(seed_xz, vectors="U",
                                       max_length=10000.0,
                                       integration_direction="forward",
                                       terminal_speed=1e-5)
str_xz["U_mag"] = np.linalg.norm(np.array(str_xz["U"]), axis=1)

# YZ plane: seed at inlet, varying y
seed_yz = pv.Line((-1700, -800, 1.75), (-1700, 800, 1.75), resolution=40)
for z_s in [5.0, 15.0, 40.0, 80.0]:
    seed_yz = seed_yz.merge(pv.Line((-1700, -600, z_s), (-1700, 600, z_s), resolution=20))
str_yz  = vol.streamlines_from_source(seed_yz, vectors="U",
                                       max_length=10000.0,
                                       integration_direction="forward",
                                       terminal_speed=1e-5)
str_yz["U_mag"] = np.linalg.norm(np.array(str_yz["U"]), axis=1)

print(f"  XZ streams: {str_xz.n_points:,} pts  |  YZ streams: {str_yz.n_points:,} pts")

# ── colour maps / norms ────────────────────────────────────────────────────
n_U   = mcolors.Normalize(0.0, 9.0)
n_p   = mcolors.Normalize(-4.0, 4.0)    # Pa (gauge)
n_k   = mcolors.Normalize(0.0, 3.0)     # m²/s²
n_nut = mcolors.Normalize(0.0, 0.05)    # m²/s

cmap_U   = cm.jet
cmap_p   = cm.RdBu_r
cmap_k   = cm.hot
cmap_nut = cm.plasma

# ── figure layout ──────────────────────────────────────────────────────────
fig = plt.figure(figsize=(20, 24))
fig.patch.set_facecolor("#12121f")
gs  = gridspec.GridSpec(4, 3, figure=fig, hspace=0.38, wspace=0.22,
                        left=0.06, right=0.97, top=0.95, bottom=0.03)

# ────────────────────────────────────────────────────────────────────────────
# Row 0: |U| at three heights
# ────────────────────────────────────────────────────────────────────────────
for col, (sl, z_lbl) in enumerate([(sl_z175, "z = 1.75 m"), (sl_z10, "z = 10 m"), (sl_z50, "z = 50 m")]):
    ax = fig.add_subplot(gs[0, col])
    pts = np.array(sl.points)
    scatter_slice(ax, pts[:, :2], sl["U_mag"], cmap_U, n_U, s=0.35)
    # building outlines (projected xy)
    mask = np.abs(bld_pts[:, 2]) < 30
    ax.scatter(bld_pts[mask, 0], bld_pts[mask, 1], c="white",
               s=0.04, linewidths=0, alpha=0.15, rasterized=True)
    style_ax(ax, "x (m)", "y (m)", f"|U|  {z_lbl}", (-1750, 2750), (-1780, 1750))
    ax.set_aspect("equal")
    add_cbar(fig, ax, cmap_U, n_U, "|U| (m/s)")

# ────────────────────────────────────────────────────────────────────────────
# Row 1: p / k / nut  at z=1.75 m
# ────────────────────────────────────────────────────────────────────────────
# pressure
ax = fig.add_subplot(gs[1, 0])
pts = np.array(sl_z175.points)
scatter_slice(ax, pts[:, :2], sl_z175["p"], cmap_p, n_p, s=0.35)
ax.scatter(bld_pts[mask, 0], bld_pts[mask, 1], c="k",
           s=0.04, linewidths=0, alpha=0.2, rasterized=True)
style_ax(ax, "x (m)", "y (m)", "Pressure p  (z = 1.75 m)", (-1750, 2750), (-1780, 1750))
ax.set_aspect("equal")
add_cbar(fig, ax, cmap_p, n_p, "p (Pa gauge)")

# TKE k
ax = fig.add_subplot(gs[1, 1])
scatter_slice(ax, pts[:, :2], sl_z175["k"], cmap_k, n_k, s=0.35)
ax.scatter(bld_pts[mask, 0], bld_pts[mask, 1], c="white",
           s=0.04, linewidths=0, alpha=0.12, rasterized=True)
style_ax(ax, "x (m)", "y (m)", "TKE k  (z = 1.75 m)", (-1750, 2750), (-1780, 1750))
ax.set_aspect("equal")
add_cbar(fig, ax, cmap_k, n_k, "k (m²/s²)")

# nut
ax = fig.add_subplot(gs[1, 2])
scatter_slice(ax, pts[:, :2], sl_z175["nut"], cmap_nut, n_nut, s=0.35)
ax.scatter(bld_pts[mask, 0], bld_pts[mask, 1], c="white",
           s=0.04, linewidths=0, alpha=0.12, rasterized=True)
style_ax(ax, "x (m)", "y (m)", "Turbulent viscosity νt  (z = 1.75 m)", (-1750, 2750), (-1780, 1750))
ax.set_aspect("equal")
add_cbar(fig, ax, cmap_nut, n_nut, "νt (m²/s)")

# ────────────────────────────────────────────────────────────────────────────
# Row 2: vertical slices |U|  XZ (y=0) and YZ (x=0) + zoom panel
# ────────────────────────────────────────────────────────────────────────────
ax_xz = fig.add_subplot(gs[2, :2])   # span 2 cols
pts_xz = np.array(sl_xz.points)
scatter_slice(ax_xz, np.column_stack([pts_xz[:, 0], pts_xz[:, 2]]),
              sl_xz["U_mag"], cmap_U, n_U, s=0.3)
# building cross-section at y≈0
b_mask_xz = np.abs(bld_pts[:, 1]) < 15
ax_xz.scatter(bld_pts[b_mask_xz, 0], bld_pts[b_mask_xz, 2],
              c="white", s=0.1, linewidths=0, alpha=0.25, rasterized=True)
ax_xz.axhline(1.75, color="#ffaa00", lw=0.8, ls="--", alpha=0.7, label="z=1.75 m")
style_ax(ax_xz, "x (m)", "z (m)", "|U|  XZ vertical plane  (y = 0)",
         (-1750, 2750), (0, 300))
ax_xz.legend(fontsize=7, labelcolor="white", framealpha=0.2)
add_cbar(fig, ax_xz, cmap_U, n_U, "|U| (m/s)")

ax_yz = fig.add_subplot(gs[2, 2])
pts_yz = np.array(sl_yz.points)
scatter_slice(ax_yz, np.column_stack([pts_yz[:, 1], pts_yz[:, 2]]),
              sl_yz["U_mag"], cmap_U, n_U, s=0.35)
b_mask_yz = np.abs(bld_pts[:, 0]) < 15
ax_yz.scatter(bld_pts[b_mask_yz, 1], bld_pts[b_mask_yz, 2],
              c="white", s=0.1, linewidths=0, alpha=0.25, rasterized=True)
ax_yz.axhline(1.75, color="#ffaa00", lw=0.8, ls="--", alpha=0.7)
style_ax(ax_yz, "y (m)", "z (m)", "|U|  YZ vertical plane  (x = 0)",
         (-1780, 1750), (0, 300))
add_cbar(fig, ax_yz, cmap_U, n_U, "|U| (m/s)")

# ────────────────────────────────────────────────────────────────────────────
# Row 3: streamlines in XZ and YZ planes + pedestrian zoom
# ────────────────────────────────────────────────────────────────────────────
ax_sxz = fig.add_subplot(gs[3, :2])
s_pts = np.array(str_xz.points)
scatter_slice(ax_sxz, np.column_stack([s_pts[:, 0], s_pts[:, 2]]),
              str_xz["U_mag"], cmap_U, n_U, s=0.2, alpha=0.8)
ax_sxz.scatter(bld_pts[b_mask_xz, 0], bld_pts[b_mask_xz, 2],
               c="white", s=0.1, linewidths=0, alpha=0.25, rasterized=True)
ax_sxz.axhline(1.75, color="#ffaa00", lw=0.8, ls="--", alpha=0.7, label="z=1.75 m")
style_ax(ax_sxz, "x (m)", "z (m)", "Streamlines  XZ plane  (y = 0)",
         (-1750, 2750), (0, 200))
ax_sxz.legend(fontsize=7, labelcolor="white", framealpha=0.2)
add_cbar(fig, ax_sxz, cmap_U, n_U, "|U| (m/s)")

# pedestrian zoom: |U| at z=1.75 m, ±500 m
ax_zoom = fig.add_subplot(gs[3, 2])
pts_z175 = np.array(sl_z175.points)
zmask = (np.abs(pts_z175[:, 0]) < 500) & (np.abs(pts_z175[:, 1]) < 500)
scatter_slice(ax_zoom,
              np.column_stack([pts_z175[zmask, 0], pts_z175[zmask, 1]]),
              sl_z175["U_mag"][zmask], cmap_U, n_U, s=1.5)
b_zoom = (np.abs(bld_pts[:, 0]) < 500) & (np.abs(bld_pts[:, 1]) < 500)
ax_zoom.scatter(bld_pts[b_zoom, 0], bld_pts[b_zoom, 1],
                c="white", s=0.3, linewidths=0, alpha=0.35, rasterized=True)
# wind arrow
ax_zoom.annotate("", xy=(-350, -450), xytext=(-480, -450),
                 arrowprops=dict(arrowstyle="->", color="white", lw=1.3))
ax_zoom.text(-400, -480, "wind", color="white", fontsize=7, ha="center")
style_ax(ax_zoom, "x (m)", "y (m)", "|U| pedestrian zoom  (±500 m)",
         (-500, 500), (-500, 500))
ax_zoom.set_aspect("equal")
add_cbar(fig, ax_zoom, cmap_U, n_U, "|U| (m/s)")

fig.suptitle(
    "Brasília Congress — CFD contours  |  simpleFoam kε  |  t = 500  |  Uref = 5 m/s @ 10 m",
    color="white", fontsize=13, y=0.975)

out = os.path.join(SCRIPT_DIR, "contours_cfd.png")
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")
plt.close()
