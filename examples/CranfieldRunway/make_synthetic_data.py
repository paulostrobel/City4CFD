#!/usr/bin/env python3
"""
Generate a synthetic offline stand-in for the OSM data that
fetch_osm_cranfield.py downloads, for testing the pipeline without network
access (the geometry/stl/mesh stages run unchanged on this data).

Layout mimics Cranfield Airport in EPSG:27700: runway 03/21 (1799 m × 45 m,
33.6° true) through the point_of_interest, a parallel taxiway, a hangar
line on the apron, a campus block south-east of the airfield with a mix of
height-tagged, levels-tagged and untagged buildings, plus grass and a lake.

Usage:  python3 make_synthetic_data.py [outdir]   (default: data)
"""
import json
import math
import sys

import numpy as np

POI = np.array([494916.0, 242440.0])   # runway midpoint, BNG
AZ = math.radians(33.6)                # runway 03 true bearing
AXIS = np.array([math.sin(AZ), math.cos(AZ)])    # along runway, towards NE
PERP = np.array([math.cos(AZ), -math.sin(AZ)])   # across runway, towards SE


def rect(centre, along, across, props):
    """Runway-frame axis-aligned rectangle feature."""
    c = POI + centre[0] * AXIS + centre[1] * PERP
    pts = [c + s * along / 2 * AXIS + t * across / 2 * PERP
           for s, t in [(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]]
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon",
                         "coordinates": [[list(map(float, p)) for p in pts]]}}


def collection(feats):
    return {"type": "FeatureCollection", "features": feats}


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"

    runway = [
        rect((0, 0), 1799, 45, {"aeroway": "runway", "ref": "03/21"}),
        rect((0, 150), 1600, 15, {"aeroway": "taxiway"}),
        rect((-300, 320), 500, 200, {"aeroway": "apron"}),
    ]

    buildings = []
    # hangar line on the apron edge (height-tagged, the tallest obstacles)
    for i in range(4):
        buildings.append(rect((-550 + i * 220, 450), 90, 60,
                              {"building": "hangar", "height": "18"}))
    # control tower
    buildings.append(rect((150, 400), 15, 15,
                          {"building": "tower", "height": "22"}))
    # campus block SE of the airfield: levels-tagged offices/labs
    rng = np.random.default_rng(42)
    for i in range(6):
        for j in range(4):
            buildings.append(rect(
                (200 + i * 120 + rng.uniform(-20, 20),
                 700 + j * 100 + rng.uniform(-15, 15)),
                60, 35, {"building": "university",
                         "building:levels": str(int(rng.integers(2, 6)))}))
    # a few untagged sheds → exercise reconstruct_failed / min_height
    for i in range(3):
        buildings.append(rect((-800 + i * 150, 600), 25, 15,
                              {"building": "shed"}))

    vegetation = [
        rect((0, -400), 2200, 500, {"landuse": "grass"}),     # airfield grass
        rect((900, 800), 400, 300, {"landuse": "forest"}),
    ]
    water = [rect((-1000, 900), 150, 100, {"natural": "water"})]

    import os
    os.makedirs(outdir, exist_ok=True)
    for name, feats in [("buildings", buildings), ("runway", runway),
                        ("vegetation", vegetation), ("water", water)]:
        path = f"{outdir}/cranfield_{name}.geojson"
        gj = collection(feats)
        gj["crs"] = {"type": "name",
                     "properties": {"name": "urn:ogc:def:crs:EPSG::27700"}}
        json.dump(gj, open(path, "w"))
        print(f"wrote {len(feats):3d} features → {path}")


if __name__ == "__main__":
    main()
