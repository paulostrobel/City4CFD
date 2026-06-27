#!/usr/bin/env python3
"""
Mesh refinement study — comparison plots.

Reads archived solutions from study/coarse/, study/medium/, study/fine/
and produces:
  - Vertical U profiles at three locations (upstream, at Congress, wake)
  - Horizontal |U| line transect at z=1.75 m along y=0
  - Summary table of cell counts and max residuals

Output: study/refinement_comparison.png
"""
import os
import sys
import numpy as np
import pyvista as pv
import matplotlib
matplotlib.rcParams['agg.path.chunksize'] = 10000
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
STUDY_DIR  = os.path.join(SCRIPT_DIR, "study")
FOAM_FILE  = os.path.join(CASE_DIR, "Brasilia.foam")

LEVELS = ["coarse", "medium", "fine"]
COLORS = {"coarse": "#4e9af1", "medium": "#f1a14e", "fine": "#4ef191"}
LABELS = {"coarse": "Coarse (20 m, ~7 M)", "medium": "Medium (15 m, ~15 M)", "fine": "Fine (10 m, ~50 M)"}

# probe locations (x, y) — vertical profiles extracted here
PROBES_XY = {
    "Upstream\n(x=−500)":   (-500,   0),
    "Congress\n(x=0)":      (   0,   0),
    "Wake\n(x=+500)":       ( 500,   0),
}

# ── helpers ────────────────────────────────────────────────────────────────
def load_level(level):
    """Load archived solution for a given refinement level."""
    sol_dir = os.path.join(STUDY_DIR, level, "solution")
    mesh_dir = os.path.join(STUDY_DIR, level, "polyMesh")

    if not os.path.isdir(sol_dir):
        print(f"  [{level}] no solution archived — skipping")
        return None

    # temporarily swap polyMesh to load this level's mesh + fields
    orig_mesh = os.path.join(CASE_DIR, "constant", "polyMesh")
    orig_bak  = orig_mesh + ".bak"

    try:
        # backup current mesh
        if os.path.isdir(orig_mesh):
            os.rename(orig_mesh, orig_bak)
        os.symlink(mesh_dir, orig_mesh)

        # find time value
        t = max(
            float(d) for d in os.listdir(sol_dir)
            if d.replace(".", "").isdigit()
        )
        t_str = str(int(t)) if t == int(t) else str(t)
        t_dir = os.path.join(CASE_DIR, t_str)

        # symlink solution time dir into case
        if not os.path.exists(t_dir):
            os.symlink(os.path.join(sol_dir, t_str), t_dir)
            created_tdir = t_dir
        else:
            created_tdir = None

        if not os.path.exists(FOAM_FILE):
            open(FOAM_FILE, "w").close()

        reader = pv.OpenFOAMReader(FOAM_FILE)
        reader.set_active_time_value(t)
        mesh = reader.read()
        vol  = mesh["internalMesh"].cell_data_to_point_data()
        vol["U_mag"] = np.linalg.norm(np.array(vol["U"]), axis=1)
        print(f"  [{level}] loaded t={t}  {vol.n_cells:,} cells")

        # count cells from checkMesh log
        n_cells = None
        log_path = os.path.join(STUDY_DIR, level, "log.checkMesh")
        if os.path.exists(log_path):
            for line in open(log_path):
                if "cells:" in line and "Total" not in line:
                    try:
                        n_cells = int(line.strip().split()[-1])
                    except ValueError:
                        pass

        return {"vol": vol, "t": t, "n_cells": n_cells, "level": level}

    finally:
        # restore mesh symlinks
        if os.path.islink(orig_mesh):
            os.unlink(orig_mesh)
        if os.path.isdir(orig_bak):
            os.rename(orig_bak, orig_mesh)
        if created_tdir and os.path.islink(created_tdir):
            os.unlink(created_tdir)


def sample_vertical(vol, x, y, z_max=300, n=200):
    """Sample |U| along a vertical line at (x,y)."""
    line = pv.Line((x, y, 0.1), (x, y, z_max), resolution=n)
    s = vol.sample(line)
    z = np.array(s.points)[:, 2]
    U = np.linalg.norm(np.array(s["U"]), axis=1)
    return z, U


def sample_horizontal(vol, z=1.75, x0=-1700, x1=2700, n=500):
    """Sample |U| along a streamwise line at z=1.75, y=0."""
    line = pv.Line((x0, 0, z), (x1, 0, z), resolution=n)
    s = vol.sample(line)
    x = np.array(s.points)[:, 0]
    U = np.linalg.norm(np.array(s["U"]), axis=1)
    return x, U


# ── load available levels ──────────────────────────────────────────────────
print("Loading archived solutions …")
data = {}
for lvl in LEVELS:
    d = load_level(lvl)
    if d is not None:
        data[lvl] = d

if not data:
    sys.exit("No archived solutions found. Run refinement_study.sh first.")

available = [l for l in LEVELS if l in data]
print(f"Available levels: {available}")

# ── figure layout ──────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 14))
fig.patch.set_facecolor("#12121f")
gs  = gridspec.GridSpec(3, 3, figure=fig, hspace=0.42, wspace=0.32,
                        left=0.07, right=0.97, top=0.93, bottom=0.07)

def style(ax, xlabel, ylabel, title):
    ax.set_facecolor("#0d0d1a")
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values(): sp.set_color("#444")
    ax.set_xlabel(xlabel, color="white", fontsize=9)
    ax.set_ylabel(ylabel, color="white", fontsize=9)
    ax.set_title(title,   color="white", fontsize=10)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("white")
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.2,
              facecolor="#1a1a2e", edgecolor="#444")

# ── Row 0: vertical U profiles at three probe locations ────────────────────
for col, (probe_name, (px, py)) in enumerate(PROBES_XY.items()):
    ax = fig.add_subplot(gs[0, col])
    for lvl in available:
        vol = data[lvl]["vol"]
        z, U = sample_vertical(vol, px, py)
        ax.plot(U, z, color=COLORS[lvl], lw=1.8, label=LABELS[lvl])
    ax.axhline(1.75, color="#ffaa00", lw=1.0, ls="--", alpha=0.8, label="z=1.75 m")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 150)
    style(ax, "|U| (m/s)", "z (m)", f"Vertical profile — {probe_name}")

# ── Row 1: streamwise |U| at z=1.75 m along centreline ────────────────────
ax_line = fig.add_subplot(gs[1, :])
for lvl in available:
    vol = data[lvl]["vol"]
    x, U = sample_horizontal(vol, z=1.75)
    ax_line.plot(x, U, color=COLORS[lvl], lw=1.8, label=LABELS[lvl])
ax_line.axhline(5.0, color="white", lw=0.8, ls=":", alpha=0.5, label="Uref=5 m/s")
ax_line.set_xlim(-1700, 2700)
ax_line.set_ylim(bottom=0)
style(ax_line, "x (m)", "|U| (m/s)", "|U| along centreline (y=0, z=1.75 m) — refinement comparison")

# mark Congress building cluster
ax_line.axvspan(-200, 200, alpha=0.08, color="white", label="Congress (~x=0)")

# ── Row 2: GCI-style convergence at probe points ───────────────────────────
# For each probe extract the scalar U at z=1.75 m and plot vs 1/cell_size
if len(available) >= 2:
    ax_conv = fig.add_subplot(gs[2, :2])
    cell_sizes = {"coarse": 20.0, "medium": 15.0, "fine": 10.0}

    for probe_name, (px, py) in PROBES_XY.items():
        xs, ys = [], []
        for lvl in available:
            vol = data[lvl]["vol"]
            z, U = sample_vertical(vol, px, py)
            # value at z=1.75 m (nearest index)
            idx = np.argmin(np.abs(z - 1.75))
            xs.append(cell_sizes[lvl])
            ys.append(U[idx])
        if xs:
            ax_conv.plot(xs, ys, "o-", lw=1.5, ms=6, label=probe_name.replace("\n", " "))

    ax_conv.invert_xaxis()  # finer mesh on right
    style(ax_conv, "Base cell size (m)  ←  finer", "|U| at z=1.75 m (m/s)",
          "Convergence at probe points")
    ax_conv.set_xticks([10, 15, 20])
    ax_conv.set_xticklabels(["10\n(fine)", "15\n(medium)", "20\n(coarse)"])
    for lbl in ax_conv.get_xticklabels(): lbl.set_color("white")

# ── Row 2 col 2: cell count and solve-time table ───────────────────────────
ax_tbl = fig.add_subplot(gs[2, 2])
ax_tbl.set_facecolor("#0d0d1a")
ax_tbl.axis("off")

rows = [["Level", "Cells", "Finest cell", "Solve time"]]
approx_times = {"coarse": "~11 h", "medium": "~25 h", "fine": "~65 h"}
finest_cell  = {"coarse": "2.5 m", "medium": "1.875 m", "fine": "0.75 m"}
for lvl in LEVELS:
    nc = f"{data[lvl]['n_cells']:,}" if lvl in data and data[lvl]["n_cells"] else "—"
    rows.append([lvl.capitalize(), nc, finest_cell[lvl], approx_times[lvl]])

tbl = ax_tbl.table(cellText=rows[1:], colLabels=rows[0],
                   cellLoc="center", loc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(9)
for (r, c), cell in tbl.get_celld().items():
    cell.set_facecolor("#1a1a2e" if r == 0 else "#0d0d1a")
    cell.set_text_props(color="white")
    cell.set_edgecolor("#444")
ax_tbl.set_title("Study summary", color="white", fontsize=10)

fig.suptitle(
    "Brasília Congress — Mesh Refinement Study  |  simpleFoam kε  |  Uref=5 m/s",
    color="white", fontsize=13, y=0.97)

out = os.path.join(STUDY_DIR, "refinement_comparison.png")
os.makedirs(STUDY_DIR, exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"\nSaved → {out}")
plt.close()
