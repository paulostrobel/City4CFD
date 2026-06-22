"""
Detailed zoomed view of Brasília Congress buildings.
Three panels:
  Left   – plan view zoomed on the Esplanada, buildings as solid polygons
  Centre – 3-D close-up of the Congress / ministerial strip (solid faces)
  Right  – 3-D close-up from a pedestrian-level angle
"""

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.collections as mc
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

RESULTS = "/home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/results"
OUT     = "/home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/zoom_buildings.png"

# ── load ─────────────────────────────────────────────────────────────────────
print("Loading meshes…")
b0 = trimesh.load(f"{RESULTS}/Brasilia_Congress_Buildings_0.obj", force="mesh")
b1 = trimesh.load(f"{RESULTS}/Brasilia_Congress_Buildings_1.obj", force="mesh")
buildings = trimesh.util.concatenate([b0, b1])

water = trimesh.load(f"{RESULTS}/Brasilia_Congress_Water.obj", force="mesh")
veg   = trimesh.load(f"{RESULTS}/Brasilia_Congress_Vegetation.obj", force="mesh")

verts = buildings.vertices          # (N,3)
faces = buildings.faces             # (F,3)

# ── compute per-face height (mean Z of triangle) ─────────────────────────────
face_z = verts[faces][:, :, 2].mean(axis=1)
zmax   = np.percentile(face_z, 99)   # cap colour at 99th pct to avoid outliers

# ── zoom region ──────────────────────────────────────────────────────────────
ZOOM = 700          # ± metres around National Congress (origin)

def in_zoom(v, pad=0):
    return (np.abs(v[:, 0]) < ZOOM + pad) & (np.abs(v[:, 1]) < ZOOM + pad)

# mask faces where all 3 vertices are in zoom
in_z = in_zoom(verts)
face_mask = in_z[faces[:, 0]] & in_z[faces[:, 1]] & in_z[faces[:, 2]]
fz = faces[face_mask]
fz_z = face_z[face_mask]

print(f"  {face_mask.sum():,} / {len(faces):,} faces in zoom region")

# ── colour map helper ─────────────────────────────────────────────────────────
cmap = plt.cm.plasma
norm = plt.Normalize(vmin=0, vmax=zmax)

def face_colours(z_vals, alpha=1.0):
    rgba = cmap(norm(z_vals))
    rgba[:, 3] = alpha
    return rgba

# ── water scatter inside zoom ─────────────────────────────────────────────────
def centroids_in_zoom(mesh, pad=0):
    if len(mesh.faces) == 0:
        return np.empty((0, 3))
    c = mesh.vertices[mesh.faces].mean(axis=1)
    m = (np.abs(c[:, 0]) < ZOOM + pad) & (np.abs(c[:, 1]) < ZOOM + pad)
    return c[m]

wc = centroids_in_zoom(water, pad=200)
vc = centroids_in_zoom(veg,   pad=200)

# ── figure ───────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(21, 8), facecolor="#1A1A2E")
fig.patch.set_facecolor("#1A1A2E")

BG = "#0D1B2A"

# ══════════════════════════════════════════════════════════════════════════════
# Panel 1 – Plan view (XY projection, per-face colour)
# ══════════════════════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(131, facecolor=BG)

# ground
ax1.add_patch(mpatches.Rectangle((-ZOOM, -ZOOM), 2*ZOOM, 2*ZOOM,
              color="#1C2B3A", zorder=0))

# water
if len(wc):
    ax1.scatter(wc[:, 0], wc[:, 1], s=1.2, c="#457B9D", alpha=0.7, lw=0, zorder=1)

# vegetation
if len(vc):
    ax1.scatter(vc[:, 0], vc[:, 1], s=1.2, c="#2D6A4F", alpha=0.7, lw=0, zorder=1)

# building footprints as filled triangles coloured by height
tris_2d = verts[fz][:, :, :2]           # (F,3,2)
colours  = face_colours(fz_z, alpha=0.92)

coll = mc.PolyCollection(tris_2d, facecolors=colours, edgecolors="none", zorder=3)
ax1.add_collection(coll)

# National Congress marker
ax1.plot(0, 0, "*", color="#FFB703", ms=10, zorder=6, label="National Congress")

# compass rose
cr_x, cr_y = ZOOM - 80, -ZOOM + 80
ax1.annotate("", xy=(cr_x, cr_y + 60), xytext=(cr_x, cr_y),
             arrowprops=dict(arrowstyle="-|>", color="white", lw=1.5, mutation_scale=12))
ax1.text(cr_x, cr_y + 70, "N", color="white", ha="center", va="bottom", fontsize=9, fontweight="bold")

# scale bar – 200 m
sb_x, sb_y = -ZOOM + 50, -ZOOM + 50
ax1.plot([sb_x, sb_x + 200], [sb_y, sb_y], color="white", lw=2)
ax1.text(sb_x + 100, sb_y + 25, "200 m", color="white", fontsize=8, ha="center")

ax1.set_xlim(-ZOOM, ZOOM)
ax1.set_ylim(-ZOOM, ZOOM)
ax1.set_aspect("equal")
ax1.set_xlabel("Easting offset (m)", color="white", fontsize=9)
ax1.set_ylabel("Northing offset (m)", color="white", fontsize=9)
ax1.set_title("Plan view — building footprints\n(coloured by height)", color="white", fontsize=10, pad=8)
ax1.tick_params(colors="white", labelsize=8)
for sp in ax1.spines.values():
    sp.set_color("#333")

sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cb1 = plt.colorbar(sm, ax=ax1, shrink=0.6, pad=0.02, label="Height (m)")
cb1.ax.yaxis.label.set_color("white")
cb1.ax.tick_params(colors="white", labelsize=7)
cb1.outline.set_edgecolor("#444")

# ══════════════════════════════════════════════════════════════════════════════
# Panel 2 – 3-D aerial view (solid polygons)
# ══════════════════════════════════════════════════════════════════════════════
ax2 = fig.add_subplot(132, projection="3d", facecolor=BG)
ax2.set_facecolor(BG)

tris_3d  = verts[fz]          # (F,3,3)
colours3 = face_colours(fz_z, alpha=0.95)

# split into chunks to avoid memory spike with huge PolyCollection
CHUNK = 5000
for i in range(0, len(tris_3d), CHUNK):
    sl = slice(i, i + CHUNK)
    poly = Poly3DCollection(tris_3d[sl], facecolors=colours3[sl], edgecolors="none")
    ax2.add_collection3d(poly)

ax2.set_xlim(-ZOOM, ZOOM)
ax2.set_ylim(-ZOOM, ZOOM)
ax2.set_zlim(0, zmax * 1.2)
ax2.set_xlabel("X (m)", color="white", fontsize=8, labelpad=4)
ax2.set_ylabel("Y (m)", color="white", fontsize=8, labelpad=4)
ax2.set_zlabel("Z (m)", color="white", fontsize=8, labelpad=4)
ax2.set_title("3-D aerial view\n(solid building geometry)", color="white", fontsize=10, pad=8)
ax2.tick_params(colors="white", labelsize=7)
ax2.xaxis.pane.fill = False
ax2.yaxis.pane.fill = False
ax2.zaxis.pane.fill = False
ax2.xaxis.pane.set_edgecolor("#333")
ax2.yaxis.pane.set_edgecolor("#333")
ax2.zaxis.pane.set_edgecolor("#333")
ax2.view_init(elev=40, azim=-55)

# ══════════════════════════════════════════════════════════════════════════════
# Panel 3 – 3-D pedestrian-level oblique
# ══════════════════════════════════════════════════════════════════════════════
ax3 = fig.add_subplot(133, projection="3d", facecolor=BG)
ax3.set_facecolor(BG)

# tighter sub-zoom for the Congress + ministerial strip
TIGHT = 350
in_tight = (np.abs(verts[:, 0]) < TIGHT) & (np.abs(verts[:, 1]) < TIGHT)
fm_tight  = in_tight[fz[:, 0]] & in_tight[fz[:, 1]] & in_tight[fz[:, 2]]
tris_t    = tris_3d[fm_tight]
col_t     = colours3[fm_tight]

print(f"  Tight zoom: {fm_tight.sum():,} faces")

for i in range(0, len(tris_t), CHUNK):
    sl = slice(i, i + CHUNK)
    poly = Poly3DCollection(tris_t[sl], facecolors=col_t[sl],
                            edgecolors="#ffffff18", linewidths=0.15)
    ax3.add_collection3d(poly)

# flat ground plane
gx = np.array([-TIGHT, TIGHT, TIGHT, -TIGHT])
gy = np.array([-TIGHT, -TIGHT, TIGHT, TIGHT])
gz = np.zeros(4)
ax3.plot_surface(gx.reshape(2, 2), gy.reshape(2, 2), gz.reshape(2, 2),
                 color="#1C2B3A", alpha=0.6, zorder=0)

ax3.set_xlim(-TIGHT, TIGHT)
ax3.set_ylim(-TIGHT, TIGHT)
ax3.set_zlim(0, zmax * 1.1)
ax3.set_xlabel("X (m)", color="white", fontsize=8, labelpad=4)
ax3.set_ylabel("Y (m)", color="white", fontsize=8, labelpad=4)
ax3.set_zlabel("Z (m)", color="white", fontsize=8, labelpad=4)
ax3.set_title(f"Close-up — National Congress\n(±{TIGHT} m, pedestrian angle)", color="white", fontsize=10, pad=8)
ax3.tick_params(colors="white", labelsize=7)
ax3.xaxis.pane.fill = False
ax3.yaxis.pane.fill = False
ax3.zaxis.pane.fill = False
ax3.xaxis.pane.set_edgecolor("#333")
ax3.yaxis.pane.set_edgecolor("#333")
ax3.zaxis.pane.set_edgecolor("#333")
ax3.view_init(elev=18, azim=-40)

sm2 = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm2.set_array([])
cb2 = plt.colorbar(sm2, ax=ax3, shrink=0.55, pad=0.0, label="Height (m)")
cb2.ax.yaxis.label.set_color("white")
cb2.ax.tick_params(colors="white", labelsize=7)
cb2.outline.set_edgecolor("#444")

# ── global title + save ───────────────────────────────────────────────────────
fig.suptitle(
    "Congresso Nacional, Brasília — Detailed Building Geometry (City4CFD LOD 1.2)",
    color="white", fontsize=13, fontweight="bold", y=0.99)

plt.tight_layout(rect=[0, 0, 1, 0.97])
plt.savefig(OUT, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {OUT}")
