#!/usr/bin/env python3
"""
Replace the OSM-derived Congress complex geometry with accurate primitives.

The Congresso Nacional consists of:
  - Main platform slab  (270 × 80 m, 9 m tall)
  - Twin towers         (2× 28m × 28m footprint, 100 m tall)
  - Senado dome         (hemisphere r=35m, crown at 35 m)
  - Camara bowl         (inverted hemisphere r=35m, rim at 15 m)

All coordinates are in CFD space (origin = UTM 193086, 8251318):
  X = east,  Y = north,  Z = up

Run:
    source ../../.venv/bin/activate
    python3 fix_congress_geometry.py
"""
import os, shutil
import numpy as np
import trimesh

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OBJ0       = os.path.join(SCRIPT_DIR, "results", "Brasilia_Congress_Buildings_0.obj")
OBJ1       = os.path.join(SCRIPT_DIR, "results", "Brasilia_Congress_Buildings_1.obj")
STL_OUT    = os.path.join(SCRIPT_DIR, "openfoam", "constant", "triSurface", "buildings.stl")

POI = np.array([193086.0, 8251318.0])

# Congress complex bbox in CFD space (metres from origin)
CONGRESS_CFD = dict(xmin=-60, xmax=200, ymin=-290, ymax=80)


def remove_congress_faces(mesh, cfd_bbox):
    """Remove faces inside congress bbox. mesh must already be in CFD space (metres)."""
    c = mesh.triangles_center
    inside = (
        (c[:, 0] > cfd_bbox["xmin"]) & (c[:, 0] < cfd_bbox["xmax"]) &
        (c[:, 1] > cfd_bbox["ymin"]) & (c[:, 1] < cfd_bbox["ymax"])
    )
    keep = np.where(~inside)[0]
    print(f"  Removed {inside.sum()} congress faces, kept {len(keep)}")
    return mesh.submesh([keep], append=True)


def make_dome(cx, cy, radius, crown_z, subdivisions=4, inverted=False):
    sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius)
    v = sphere.vertices.copy()
    faces = np.array([f for f in sphere.faces if all(v[i, 2] >= -0.01 for i in f)])
    cap = trimesh.Trimesh(vertices=v, faces=faces, process=False)
    cap = cap.submesh([list(range(len(cap.faces)))], append=True)
    if inverted:
        cap.vertices[:, 2] *= -1
        cap.apply_translation([cx, cy, crown_z])
    else:
        cap.apply_translation([cx, cy, crown_z - radius])
    return cap


# ── Load and clean OBJ meshes ─────────────────────────────────────────────────
print("Loading OBJ meshes …")
meshes = []
for path in [OBJ0, OBJ1]:
    if not os.path.exists(path):
        print(f"  Missing: {path}")
        continue
    m = trimesh.load(path, force="mesh")
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(list(m.geometry.values()))
    # OBJ is already in CFD space metres (City4CFD centres on POI)
    print(f"  {os.path.basename(path)}: {len(m.faces)} faces")
    meshes.append(remove_congress_faces(m, CONGRESS_CFD))

# ── Build Congress primitives ─────────────────────────────────────────────────
print("Building Congress primitives …")
parts = []

# Platform — full OSM bbox: 143 m E-W x 216 m N-S x 9 m tall
platform = trimesh.creation.box(extents=[143, 216, 9])
platform.apply_translation([54, -186, 4.5])
parts.append(platform)

# Twin towers — thin E-W slabs (50 m x 8 m x 100 m), 20 m apart in N-S, at east end X=129
for dy in [-10, +10]:
    tower = trimesh.creation.box(extents=[50, 8, 100])
    tower.apply_translation([129, -187 + dy, 50])
    parts.append(tower)

# Senado dome (NORTH/left in photo) — r=20 m, bottom at platform top z=9
parts.append(make_dome(cx=70, cy=-130, radius=20, crown_z=29, inverted=False))

# Camara bowl (SOUTH/right in photo) — r=20 m, wide rim at z=29, curved exterior down to z=9
parts.append(make_dome(cx=39, cy=-226, radius=20, crown_z=29, inverted=True))

print(f"  {len(parts)} congress parts built")

# ── Merge and export ──────────────────────────────────────────────────────────
print("Merging …")
combined = trimesh.util.concatenate(meshes + parts)
# clip any faces below ground (Z < 0)
keep = np.where(combined.triangles_center[:, 2] >= -0.001)[0]
combined = combined.submesh([keep], append=True)
print(f"  Total faces: {len(combined.faces)}")
print(f"  Z range: {combined.bounds[0,2]:.1f} → {combined.bounds[1,2]:.1f} m")

os.makedirs(os.path.dirname(STL_OUT), exist_ok=True)
combined.export(STL_OUT)
print(f"  Saved → {STL_OUT}")
print("Done. Re-run blockMesh + snappyHexMesh + simpleFoam to use new geometry.")
