#!/usr/bin/env python3
"""
Merge the City4CFD building OBJ files into a single STL for snappyHexMesh,
rotated so the runway 03/21 axis lies along +x.

City4CFD outputs geometry translated by -point_of_interest (runway midpoint
at the origin), so a pure rotation about the z axis is enough. The rotation
angle is derived from the actual runway polygon downloaded from OSM (longest
edge of its minimum rotated rectangle); if the polygon is unavailable the
published true bearing of runway 03 (~33.6°) is used.

With wind from 214° (prevailing SW at Cranfield), the flow in the rotated
frame is exactly (1 0 0): inlet at x-min, straight down the runway.
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np
import trimesh

FALLBACK_AZIMUTH_DEG = 33.6   # runway 03 true bearing (UK AIP, EGTC)


def runway_azimuth(geojson_path):
    """Azimuth (degrees from north, in [0, 90]) of the longest runway edge."""
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
    except ImportError:
        return None
    if not os.path.exists(geojson_path):
        return None
    with open(geojson_path) as f:
        data = json.load(f)
    runways = [shape(ft["geometry"]) for ft in data.get("features", [])
               if ft.get("properties", {}).get("aeroway") == "runway"]
    if not runways:
        return None
    rect = unary_union(runways).minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    # longest edge of the bounding rectangle = runway axis
    best, azimuth = 0.0, None
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length > best:
            best = length
            az = math.degrees(math.atan2(x1 - x0, y1 - y0)) % 180.0
            azimuth = az if az <= 90.0 else az - 180.0  # → (-90, 90]
    return abs(azimuth) if azimuth is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--runway", default="data/cranfield_runway.geojson")
    ap.add_argument("--out", default="openfoam/constant/triSurface/buildings.stl")
    ap.add_argument("--glob", default="Cranfield_Runway_Buildings_*.obj",
                    help="OBJ file pattern in the results dir to merge/rotate "
                         "(e.g. Cranfield_Runway_Runway.obj for the aeroway layer)")
    args = ap.parse_args()

    az = runway_azimuth(args.runway)
    if az is None:
        az = FALLBACK_AZIMUTH_DEG
        print(f"Runway polygon not found — using published bearing {az:.1f}°")
    else:
        print(f"Runway azimuth from OSM geometry: {az:.2f}° true")

    # runway axis (pointing NE) in (E, N); angle from +x axis is 90° - az
    phi = math.radians(90.0 - az)
    rot = trimesh.transformations.rotation_matrix(-phi, [0, 0, 1])
    print(f"Rotating scene by {-math.degrees(phi):.2f}° about z "
          f"(runway 03/21 → +x)")

    obj_files = sorted(glob.glob(os.path.join(args.results, args.glob)))
    if not obj_files:
        sys.exit(f"No OBJ files matching {args.glob} in {args.results}/ — "
                 "run the geometry stage first")

    meshes = [trimesh.load(p, force="mesh") for p in obj_files]
    combined = trimesh.util.concatenate(meshes)
    combined.apply_transform(rot)

    lo, hi = combined.bounds
    print(f"Rotated extents: x {lo[0]:.0f}..{hi[0]:.0f}  "
          f"y {lo[1]:.0f}..{hi[1]:.0f}  z {lo[2]:.1f}..{hi[2]:.1f}")
    # the domain-fit check is calibrated for the buildings; skip for other layers
    if args.glob.startswith("Cranfield_Runway_Buildings") and \
            (hi[0] > 2300 or lo[0] < -1800 or hi[1] > 1600 or lo[1] < -1600):
        print("WARNING: geometry exceeds the blockMesh box "
              "(X -1800..2300, Y -1600..1600) — enlarge system/blockMeshDict")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    combined.export(args.out)
    print(f"Exported {len(combined.faces):,} faces → {args.out}")


if __name__ == "__main__":
    main()
