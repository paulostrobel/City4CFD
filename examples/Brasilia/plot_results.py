#!/usr/bin/env python3
"""
Post-processing: pedestrian-level velocity slice, building surface mesh,
and streamlines from the t=500 simpleFoam solution.

Output: results_cfd.png
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
import os

# ── paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
STL_PATH   = os.path.join(CASE_DIR, "constant", "triSurface", "buildings.stl")
TIME_DIR   = os.path.join(CASE_DIR, "500")

# ── load OpenFOAM fields from t=500 using pyvista ──────────────────────────
print("Reading OpenFOAM case …")
foam_file = os.path.join(CASE_DIR, "Brasilia.foam")
if not os.path.exists(foam_file):
    open(foam_file, "w").close()

reader = pv.OpenFOAMReader(foam_file)
reader.set_active_time_value(500.0)
mesh = reader.read()

# internalMesh block
vol = mesh["internalMesh"]
vol = vol.cell_data_to_point_data()          # interpolate to nodes for slicing

print(f"  Volume mesh: {vol.n_points:,} points, {vol.n_cells:,} cells")
print(f"  Fields: {vol.array_names}")

# ── 1. pedestrian-level slice at z = 1.75 m ────────────────────────────────
print("Slicing at z=1.75 m …")
slice_z = vol.slice(normal="z", origin=(0, 0, 1.75))
U_vec = slice_z["U"]                         # (N,3) velocity vectors
U_mag = np.linalg.norm(U_vec, axis=1)
slice_z["U_mag"] = U_mag

# ── 2. building walls from boundary patches ────────────────────────────────
print("Extracting building walls …")
boundaries = mesh["boundary"]

buildings_surf = None
ground_surf    = None
for i in range(boundaries.n_blocks):
    block = boundaries[i]
    name  = boundaries.get_block_name(i) or ""
    if block is None:
        continue
    if "building" in name.lower():
        buildings_surf = block
    elif "ground" in name.lower():
        ground_surf = block

# ── 3. streamlines seeded at inlet ────────────────────────────────────────
print("Computing streamlines …")
# seed line along the inlet face at z=1.75 m and several heights
seed = pv.Line((-1700, -800, 1.75), (-1700, 800, 1.75), resolution=30)
# add a few height levels
for z_s in [5.0, 15.0, 40.0]:
    extra = pv.Line((-1700, -800, z_s), (-1700, 800, z_s), resolution=15)
    seed  = seed.merge(extra)

streams = vol.streamlines_from_source(
    seed,
    vectors="U",
    max_length=15000.0,
    integration_direction="forward",
    terminal_speed=1e-5,
)
print(f"  Streamlines: {streams.n_points:,} points")

# ── plotting with matplotlib ───────────────────────────────────────────────
print("Rendering …")

# colour map
cmap_vel  = cm.jet
cmap_norm = mcolors.Normalize(vmin=0.0, vmax=8.0)   # m/s

fig = plt.figure(figsize=(18, 10))
fig.patch.set_facecolor("#1a1a2e")

# ── panel A: plan view (xy slice at z=1.75 m) ─────────────────────────────
ax1 = fig.add_axes([0.03, 0.08, 0.55, 0.88])
ax1.set_facecolor("#0a0a1a")

# velocity slice — scatter coloured by |U|
pts  = np.array(slice_z.points)
cols = cmap_vel(cmap_norm(slice_z["U_mag"]))
ax1.scatter(pts[:, 0], pts[:, 1], c=cols, s=0.3, linewidths=0, rasterized=True)

# building footprints from STL
if buildings_surf is not None:
    bpts = np.array(buildings_surf.points)
    ax1.scatter(bpts[:, 0], bpts[:, 1], c="white", s=0.05,
                linewidths=0, alpha=0.25, rasterized=True)

# streamlines projected to xy
if streams.n_points > 0:
    s_pts = np.array(streams.points)
    # colour by speed
    s_U  = streams.point_data["U"] if "U" in streams.point_data.keys() else None
    if s_U is not None:
        s_spd = np.linalg.norm(s_U, axis=1)
        s_col = cmap_vel(cmap_norm(s_spd))
        ax1.scatter(s_pts[:, 0], s_pts[:, 1], c=s_col,
                    s=0.15, linewidths=0, alpha=0.5, rasterized=True)

# domain box
ax1.set_xlim(-1750, 2750)
ax1.set_ylim(-1780, 1750)
ax1.set_aspect("equal")
ax1.tick_params(colors="white"); ax1.spines[:].set_color("#444")
for lbl in ax1.get_xticklabels() + ax1.get_yticklabels():
    lbl.set_color("white")
ax1.set_xlabel("x  (m)", color="white", fontsize=9)
ax1.set_ylabel("y  (m)", color="white", fontsize=9)
ax1.set_title("Velocity magnitude — pedestrian level  z = 1.75 m", color="white", fontsize=11)

# flow direction arrow
ax1.annotate("", xy=(-1500, -1600), xytext=(-1700, -1600),
             arrowprops=dict(arrowstyle="->", color="white", lw=1.5))
ax1.text(-1550, -1650, "wind", color="white", fontsize=8, ha="center")

# colour bar
sm = cm.ScalarMappable(norm=cmap_norm, cmap=cmap_vel)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax1, orientation="horizontal",
                    fraction=0.025, pad=0.06, shrink=0.6)
cbar.set_label("|U|  (m/s)", color="white", fontsize=9)
cbar.ax.xaxis.set_tick_params(color="white")
plt.setp(cbar.ax.xaxis.get_ticklabels(), color="white")
cbar.outline.set_edgecolor("#444")

# ── panel B: vertical profile at centreline ──────────────────────────────
ax2 = fig.add_axes([0.65, 0.55, 0.31, 0.38])
ax2.set_facecolor("#0a0a1a")

# sample U along a vertical line at the Congress building location
line3d = pv.Line((0, 0, 0.1), (0, 0, 300), resolution=200)
sampled = vol.sample(line3d)
z_prof  = np.array(sampled.points)[:, 2]
U_prof  = np.linalg.norm(np.array(sampled["U"]), axis=1)

ax2.plot(U_prof, z_prof, color="#00aaff", lw=1.5)
ax2.axhline(1.75, color="#ffaa00", lw=1, ls="--", label="z = 1.75 m")
ax2.set_xlabel("|U|  (m/s)", color="white", fontsize=9)
ax2.set_ylabel("z  (m)",     color="white", fontsize=9)
ax2.set_title("Vertical profile\n(x=0, y=0)", color="white", fontsize=9)
ax2.tick_params(colors="white"); ax2.spines[:].set_color("#444")
for lbl in ax2.get_xticklabels() + ax2.get_yticklabels():
    lbl.set_color("white")
ax2.legend(fontsize=8, labelcolor="white", framealpha=0.3)

# ── panel C: streamlines + buildings 3-D isometric ─────────────────────
ax3 = fig.add_axes([0.65, 0.08, 0.31, 0.38], projection="3d")
ax3.set_facecolor("#0a0a1a")
ax3.patch.set_alpha(0.0)

# buildings STL
bld_stl = pv.read(STL_PATH)
bpts    = np.array(bld_stl.points)
# crop to zoom region ±700 m
mask = (np.abs(bpts[:, 0]) < 700) & (np.abs(bpts[:, 1]) < 700)
ax3.scatter(bpts[mask, 0], bpts[mask, 1], bpts[mask, 2],
            c="lightgray", s=0.02, linewidths=0, alpha=0.3, rasterized=True)

# streamlines 3D
if streams.n_points > 0:
    s_pts = np.array(streams.points)
    s_mask = (np.abs(s_pts[:, 0]) < 700) & (np.abs(s_pts[:, 1]) < 700)
    s_U2  = streams.point_data["U"] if "U" in streams.point_data.keys() else None
    if s_U2 is not None:
        s_spd2 = np.linalg.norm(s_U2[s_mask], axis=1)
        ax3.scatter(s_pts[s_mask, 0], s_pts[s_mask, 1], s_pts[s_mask, 2],
                    c=cmap_vel(cmap_norm(s_spd2)),
                    s=0.15, linewidths=0, alpha=0.6, rasterized=True)

ax3.set_xlim(-700, 700); ax3.set_ylim(-700, 700); ax3.set_zlim(0, 300)
ax3.set_xlabel("x", color="white", fontsize=7, labelpad=2)
ax3.set_ylabel("y", color="white", fontsize=7, labelpad=2)
ax3.set_zlabel("z", color="white", fontsize=7, labelpad=2)
ax3.set_title("Streamlines (±700 m)", color="white", fontsize=9, pad=4)
ax3.tick_params(colors="white", labelsize=6)
ax3.xaxis.pane.fill = False
ax3.yaxis.pane.fill = False
ax3.zaxis.pane.fill = False
ax3.view_init(elev=30, azim=-60)

fig.suptitle("Brasília Congress — Microclimate CFD  |  simpleFoam kε  |  t = 500",
             color="white", fontsize=13, y=0.99)

out = os.path.join(SCRIPT_DIR, "results_cfd.png")
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")
plt.close()
