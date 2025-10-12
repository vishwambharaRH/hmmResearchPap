import pyproj
import re
import utils
import pandas as pd
from shapely import wkt
from sqlalchemy import create_engine, event
import os

# --- NEW, MORE ROBUST PATHING & SPATIALITE SETUP ---
script_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(script_dir, 'socal_roads.sqlite')

# --- ACTION REQUIRED: Set the path to your SpatiaLite library ---
# This path MUST match the one you used in create_index.py
# Common paths on macOS (using Homebrew):
# - For Apple Silicon (M1/M2/M3): '/opt/homebrew/lib/mod_spatialite.dylib'
# - For Intel Macs: '/usr/local/lib/mod_spatialite.dylib'
SPATIALITE_PATH = '/opt/homebrew/lib/mod_spatialite.dylib' # <-- UPDATE THIS PATH IF NEEDED

LINE_TABLE = 'lines'
SEARCH_RADIUS_METERS = 50

# This function loads the SpatiaLite extension. It's needed for ANY spatial query.
def load_spatialite(dbapi_conn, connection_record):
    dbapi_conn.enable_load_extension(True)
    dbapi_conn.load_extension(SPATIALITE_PATH)

wgs84_to_mercator = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

try:
    engine = create_engine(f'sqlite:///{DB_FILE}')
    # We MUST listen for the connect event here too, so that every time
    # a query is made, the spatial functions are available.
    event.listen(engine, 'connect', load_spatialite)
    print(f"Successfully configured database connection for: {DB_FILE}")
except Exception as e:
    print(f"Unable to connect to database file {DB_FILE}")
    print(f"Error: {e}")
    raise

def query_ways_within_radius(lat, lon, radius=SEARCH_RADIUS_METERS):
    """
    Query the SpatiaLite database for ways (roads) that are within 'radius' meters
    from the point defined by 'lat' and 'lon'.
    """
    merc_x, merc_y = wgs84_to_mercator.transform(lon, lat)
    min_x, max_x = merc_x - radius, merc_x + radius
    min_y, max_y = merc_y - radius, merc_y + radius
    
    qstring = f"""
        SELECT
            osm_id,
            oneway,
            AsText(geometry) as wkt_geometry
        FROM {LINE_TABLE}
        WHERE ROWID IN (
            SELECT id
            FROM rtree_{LINE_TABLE}_geometry
            WHERE minX <= {max_x} AND maxX >= {min_x} AND
                  minY <= {max_y} AND maxY >= {min_y}
        )
    """
    df = pd.read_sql_query(qstring, engine)

    if df.empty:
        return None, None

    point_in_merc = (merc_x, merc_y)
    ways = []
    for _, row in df.iterrows():
        osm_id = int(row['osm_id'])
        if osm_id < 0:
            continue
        oneway = True if str(row['oneway']).lower() in ['yes', '1', 'true'] else False
        line = wkt.loads(row['wkt_geometry'])
        projected_coords = [wgs84_to_mercator.transform(px, py) for px, py in line.coords]
        way = {'osm_id': osm_id, 'points': projected_coords, 'oneway': oneway}
        ways.append(way)
    return point_in_merc, ways

def get_node_id(way_id, index):
    """DEPRECATED: This function is not compatible with the new data structure."""
    print("WARNING: get_node_id is deprecated and is not functional.")
    return None

def get_node_gps_point(way_id, index):
    """
    Gets the original lat/lon coordinates for a specific node in a way.
    """
    qstring = f"""
        SELECT AsText(geometry) as wkt_geometry
        FROM {LINE_TABLE}
        WHERE osm_id = '{way_id}'
    """
    df = pd.read_sql_query(qstring, engine)
    if df.empty:
        return (None, None)
    line = wkt.loads(df.iloc[0]['wkt_geometry'])
    points = list(line.coords)
    return points[index] if len(points) > index else (None, None)

