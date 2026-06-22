#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Brasília Congress CFD Setup ==="

# Check Python dependencies
python3 -c "import osmnx, geopandas, pyproj, geopy" 2>/dev/null || {
    echo "Installing required Python packages..."
    pip install osmnx geopandas pyproj geopy shapely
}

# Print exact UTM 23S coordinates for the point_of_interest
echo ""
echo "=== Verifying UTM coordinates for point_of_interest ==="
python3 - <<'EOF'
from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
lon, lat = -47.8647, -15.7980
easting, northing = transformer.transform(lon, lat)
print(f"National Congress UTM 23S (EPSG:31983):")
print(f"  Easting:  {easting:.0f} m")
print(f"  Northing: {northing:.0f} m")
print()
print("Update 'point_of_interest' in config_bpg.json if these differ significantly from [193838, 8243590]")
EOF

# Download building footprints, vegetation and water from OpenStreetMap
echo ""
echo "=== Downloading OSM data ==="
python3 ../../tools/fetch_polygons/fetch_osm.py

# Create output directory
mkdir -p results

echo ""
echo "=== Setup complete ==="
echo "Build City4CFD if not already done:"
echo "  cd /home/user/City4CFD && mkdir -p build && cd build && cmake .. && make -j\$(nproc)"
echo ""
echo "Then run the simulation from examples/Brasilia/:"
echo "  ../../build/city4cfd config_bpg.json --output_dir results"
