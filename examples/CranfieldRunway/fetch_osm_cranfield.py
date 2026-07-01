#!/usr/bin/env python3
"""
Download OpenStreetMap data for the Cranfield Airport / Cranfield University
runway microclimate case.

Compared to the generic tools/fetch_polygons/fetch_osm.py this script also
downloads aeroway features (runway, taxiways, aprons) so the runway can be
used as a distinct SurfaceLayer, and it buffers LineString features (runway
centrelines, waterways) into polygons, since City4CFD consumes polygons only.

Output (EPSG:27700, British National Grid):
    data/cranfield_buildings.geojson
    data/cranfield_runway.geojson
    data/cranfield_vegetation.geojson
    data/cranfield_water.geojson
"""
import os

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

# ── user parameters ─────────────────────────────────────────────────────────
LAT, LON = 52.0722, -0.6166   # Cranfield Airport (EGTC) midfield / ARP
CRS      = "EPSG:27700"       # British National Grid (metres)
OUTDIR   = "data"

HMAX        = 20              # tallest obstacles: hangars ~20 m
R_BUILDINGS = 1500            # radius for building footprints [m]
R_POLYGONS  = 15 * HMAX + 2 * R_BUILDINGS   # COST-732 rule → 3300 m

# Default half-widths used to buffer LineString features into polygons [m]
LINE_WIDTHS = {"runway": 45.0, "taxiway": 15.0, "waterway": 5.0}

TAGS = {
    "buildings": {
        "building": True,
        "height": True,
        "building:levels": True,
    },
    "runway": {
        "aeroway": ["runway", "taxiway", "apron", "helipad"],
    },
    "vegetation": {
        "landuse": ["forest", "grass", "meadow", "orchard"],
        "leisure": ["park", "nature_reserve", "garden", "dog_park"],
        "natural": ["grassland", "wood"],
    },
    "water": {
        "natural": ["water"],
        "waterway": True,
    },
}

RADII = {
    "buildings": R_BUILDINGS,
    "runway": 2500,           # full 1799 m runway + taxiway loops
    "vegetation": R_POLYGONS,
    "water": R_POLYGONS,
}


def line_to_polygon(row):
    """Buffer LineString features to their mapped or default width."""
    geom = row.geometry
    if geom.geom_type not in ("LineString", "MultiLineString"):
        return geom
    width = None
    w = row.get("width")
    if w is not None and not pd.isna(w):
        try:
            width = float(str(w).replace("m", "").strip())
        except ValueError:
            width = None
    if width is None:
        aeroway = row.get("aeroway")
        if aeroway in LINE_WIDTHS:
            width = LINE_WIDTHS[aeroway]
        elif row.get("waterway") is not None and not pd.isna(row.get("waterway")):
            width = LINE_WIDTHS["waterway"]
        else:
            width = 10.0
    return geom.buffer(width / 2.0, cap_style="flat")


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    centre = gpd.GeoDataFrame(geometry=[Point(LON, LAT)], crs="EPSG:4326").to_crs(CRS)
    print(f"Cranfield Airport in {CRS}: "
          f"E {centre.geometry.x.iloc[0]:.0f}, N {centre.geometry.y.iloc[0]:.0f}")

    for category, tags in TAGS.items():
        radius = RADII[category]
        print(f"\nDownloading {category} within {radius} m …")
        try:
            gdf = ox.features_from_point((LAT, LON), tags=tags, dist=radius)
        except Exception as e:
            print(f"  Error downloading {category}: {e}")
            continue
        if gdf.empty:
            print(f"  No {category} data found.")
            continue

        gdf = gdf.to_crs(CRS)

        # buffer lines into polygons, drop points
        gdf["geometry"] = gdf.apply(line_to_polygon, axis=1)
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]
        if gdf.empty:
            print(f"  No polygonal {category} features after filtering.")
            continue

        clip = centre.buffer(radius)
        gdf = gpd.clip(gdf, clip)

        out = f"{OUTDIR}/cranfield_{category}.geojson"
        gdf.to_file(out, driver="GeoJSON")
        b = gdf.total_bounds
        print(f"  Saved {len(gdf)} features → {out}")
        print(f"  Bounds (+10 m offset): "
              f"{b[0]-10:.0f} {b[1]-10:.0f} {b[2]+10:.0f} {b[3]+10:.0f}")


if __name__ == "__main__":
    main()
