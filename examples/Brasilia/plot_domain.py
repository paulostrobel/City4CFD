"""
Visualise Brasília Congress City4CFD surfaces and CFD domain.
Produces a two-panel PNG:
  Left  – plan view (XY): buildings + terrain + domain box + flow arrow
  Right – isometric 3-D view of buildings inside the domain wireframe
"""

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d import Axes3D

RESULTS = "/home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/results"
OUT     = "/home/paulo/mydropbox/homelab/City4CFD/examples/Brasilia/domain_preview.png"

# ── domain extents (from blockMeshDict) ──────────────────────────────────────
XMIN, XMAX = -1700, 2700
YMIN, YMAX = -1730, 1700
ZMIN, ZMAX =     0,  600

# ── load meshes ──────────────────────────────────────────────────────────────
print("Loading buildings…")
b0 = trimesh.load(f"{RESULTS}/Brasilia_Congress_Buildings_0.obj", force="mesh")
b1 = trimesh.load(f"{RESULTS}/Brasilia_Congress_Buildings_1.obj", force="mesh")
buildings = trimesh.util.concatenate([b0, b1])

print("Loading terrain…")
terrain = trimesh.load(f"{RESULTS}/Brasilia_Congress_Terrain.obj", force="mesh")

print("Loading water + vegetation…")
water = trimesh.load(f"{RESULTS}/Brasilia_Congress_Water.obj", force="mesh")
veg   = trimesh.load(f"{RESULTS}/Brasilia_Congress_Vegetation.obj", force="mesh")

# ── helpers ──────────────────────────────────────────────────────────────────
def domain_rect():
    """Matplotlib Rectangle for the plan-view domain box."""
    return mpatches.FancyArrowPatch(
        posA=(XMIN, YMIN), posB=(XMAX, YMAX), arrowstyle="-",
        linewidth=0, fill=False)

def domain_lines_2d(ax):
    xs = [XMIN, XMAX, XMAX, XMIN, XMIN]
    ys = [YMIN, YMIN, YMAX, YMAX, YMIN]
    ax.plot(xs, ys, color="#E63946", lw=1.5, zorder=5, label="CFD domain")

def domain_wireframe_3d(ax):
    corners = np.array([
        [XMIN, YMIN, ZMIN], [XMAX, YMIN, ZMIN],
        [XMAX, YMAX, ZMIN], [XMIN, YMAX, ZMIN],
        [XMIN, YMIN, ZMAX], [XMAX, YMIN, ZMAX],
        [XMAX, YMAX, ZMAX], [XMIN, YMAX, ZMAX],
    ])
    edges = [
        (0,1),(1,2),(2,3),(3,0),   # bottom
        (4,5),(5,6),(6,7),(7,4),   # top
        (0,4),(1,5),(2,6),(3,7),   # verticals
    ]
    for a, b in edges:
        ax.plot3D(*zip(corners[a], corners[b]), color="#E63946",
                  lw=0.9, alpha=0.8)

# ── sample triangles for 3-D scatter (subsample for speed) ───────────────────
def face_centroids(mesh, n=4000):
    idx = np.random.choice(len(mesh.faces), min(n, len(mesh.faces)), replace=False)
    tris = mesh.vertices[mesh.faces[idx]]
    return tris.mean(axis=1)

rng = np.random.default_rng(0)

# ── figure ───────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 8), facecolor="#1A1A2E")
fig.patch.set_facecolor("#1A1A2E")

# ─────────────── LEFT: plan view ────────────────────────────────────────────
ax1 = fig.add_subplot(121, facecolor="#16213E")

# terrain extent as filled polygon
tx, ty = terrain.vertices[:, 0], terrain.vertices[:, 1]
ax1.fill([XMIN, XMAX, XMAX, XMIN], [YMIN, YMIN, YMAX, YMAX],
         color="#2C3E50", zorder=0)

# water
if len(water.vertices):
    wc = face_centroids(water, 8000)
    ax1.scatter(wc[:, 0], wc[:, 1], s=1, c="#457B9D", alpha=0.6, zorder=2, lw=0)

# vegetation
if len(veg.vertices):
    vc = face_centroids(veg, 8000)
    ax1.scatter(vc[:, 0], vc[:, 1], s=1, c="#2D6A4F", alpha=0.6, zorder=2, lw=0)

# building footprints (project to XY)
bc = face_centroids(buildings, 40000)
ax1.scatter(bc[:, 0], bc[:, 1], s=1, c="#F1FAEE", alpha=0.9, zorder=3, lw=0)

# domain rectangle
domain_lines_2d(ax1)

# flow arrow
arrow_y = YMIN + (YMAX - YMIN) * 0.12
ax1.annotate("", xy=(XMIN + 400, arrow_y), xytext=(XMIN + 50, arrow_y),
             arrowprops=dict(arrowstyle="-|>", color="#FFB703", lw=2, mutation_scale=18))
ax1.text(XMIN + 220, arrow_y + 80, "Wind\n5 m/s", color="#FFB703",
         fontsize=8, ha="center", va="bottom")

# POI marker (National Congress)
ax1.plot(0, 0, "o", color="#E63946", ms=6, zorder=6, label="National Congress")

# scale bar – 500 m
sb_x, sb_y = XMAX - 800, YMIN + 120
ax1.plot([sb_x, sb_x + 500], [sb_y, sb_y], color="white", lw=2)
ax1.text(sb_x + 250, sb_y + 60, "500 m", color="white", fontsize=8, ha="center")

ax1.set_xlim(XMIN - 100, XMAX + 100)
ax1.set_ylim(YMIN - 100, YMAX + 100)
ax1.set_aspect("equal")
ax1.set_xlabel("Easting offset (m)", color="white", fontsize=9)
ax1.set_ylabel("Northing offset (m)", color="white", fontsize=9)
ax1.set_title("Plan view — Esplanada dos Ministérios", color="white", fontsize=11, pad=10)
ax1.tick_params(colors="white", labelsize=8)
for sp in ax1.spines.values():
    sp.set_color("#444")

legend_handles = [
    mpatches.Patch(color="#F1FAEE", label="Buildings (543)"),
    mpatches.Patch(color="#457B9D", label="Water"),
    mpatches.Patch(color="#2D6A4F", label="Vegetation"),
    mpatches.Patch(color="#E63946", label="CFD domain"),
]
ax1.legend(handles=legend_handles, loc="upper right",
           facecolor="#0F3460", edgecolor="#444", labelcolor="white", fontsize=8)

# ─────────────── RIGHT: 3-D isometric ───────────────────────────────────────
ax2 = fig.add_subplot(122, projection="3d", facecolor="#16213E")
ax2.set_facecolor("#16213E")

# sub-sample buildings for 3-D scatter coloured by height
bc3 = face_centroids(buildings, 60000)
sc = ax2.scatter(bc3[:, 0], bc3[:, 1], bc3[:, 2],
                 c=bc3[:, 2], cmap="plasma", s=0.5, alpha=0.8,
                 vmin=0, vmax=80)
cbar = plt.colorbar(sc, ax=ax2, shrink=0.45, pad=0.0, label="Height (m)")
cbar.ax.yaxis.set_tick_params(color="white")
cbar.ax.yaxis.label.set_color("white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
cbar.outline.set_edgecolor("#444")

# domain wireframe
domain_wireframe_3d(ax2)

ax2.set_xlim(XMIN, XMAX)
ax2.set_ylim(YMIN, YMAX)
ax2.set_zlim(ZMIN, ZMAX)
ax2.set_xlabel("X (m)", color="white", fontsize=8, labelpad=6)
ax2.set_ylabel("Y (m)", color="white", fontsize=8, labelpad=6)
ax2.set_zlabel("Z (m)", color="white", fontsize=8, labelpad=6)
ax2.set_title("3-D view — buildings & CFD domain", color="white", fontsize=11, pad=10)
ax2.tick_params(colors="white", labelsize=7)
ax2.xaxis.pane.fill = False
ax2.yaxis.pane.fill = False
ax2.zaxis.pane.fill = False
ax2.xaxis.pane.set_edgecolor("#333")
ax2.yaxis.pane.set_edgecolor("#333")
ax2.zaxis.pane.set_edgecolor("#333")
ax2.view_init(elev=28, azim=-50)

# ── title + save ─────────────────────────────────────────────────────────────
fig.suptitle("Congresso Nacional, Brasília — City4CFD Microclimate Setup",
             color="white", fontsize=13, fontweight="bold", y=0.97)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(OUT, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {OUT}")
