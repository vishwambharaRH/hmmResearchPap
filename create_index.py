import os
from sqlalchemy import create_engine, text, event

# --- CONFIGURATION ---
DB_FILENAME = 'socal_roads.sqlite'
TABLE_NAME = 'lines'
GEOMETRY_COLUMN = 'geometry'
# SRID 4326 is the standard for GPS (lat/lon) coordinates.
SRID = 4326 
GEOMETRY_TYPE = 'LINESTRING'

# --- ACTION REQUIRED: Set the path to your SpatiaLite library ---
# find / -name "mod_spatialite.dylib" 2>/dev/null
SPATIALITE_PATH = '/opt/homebrew/lib/mod_spatialite.dylib' # <-- UPDATE THIS PATH IF NEEDED

# --- SCRIPT LOGIC ---

def load_spatialite(dbapi_conn, connection_record):
    """Loads the SpatiaLite extension into the database connection."""
    dbapi_conn.enable_load_extension(True)
    dbapi_conn.load_extension(SPATIALITE_PATH)

def run():
    """Connects to the DB and performs setup tasks."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_file_path = os.path.join(script_dir, DB_FILENAME)

    if not os.path.exists(db_file_path):
        print(f"❌ ERROR: Database file not found at '{db_file_path}'")
        return
    if not os.path.exists(SPATIALITE_PATH):
        print(f"❌ ERROR: SpatiaLite library not found at '{SPATIALITE_PATH}'")
        return
        
    print(f"Connecting to database: {db_file_path}")
    engine = create_engine(f'sqlite:///{db_file_path}')
    event.listen(engine, 'connect', load_spatialite)

    with engine.connect() as connection:
        try:
            # STEP 1: Register the geometry column. This fixes the root cause.
            recover_sql = f"SELECT RecoverGeometryColumn('{TABLE_NAME}', '{GEOMETRY_COLUMN}', {SRID}, '{GEOMETRY_TYPE}');"
            print(f"STEP 1/2: Registering geometry column...")
            print(f"  > Executing: {recover_sql}")
            connection.execute(text(recover_sql))
            connection.commit()
            print("  > Geometry column registered successfully.")

            # STEP 2: Create the spatial index.
            index_sql = f"SELECT CreateSpatialIndex('{TABLE_NAME}', '{GEOMETRY_COLUMN}');"
            print(f"STEP 2/2: Creating spatial index...")
            print(f"  > Executing: {index_sql}")
            connection.execute(text(index_sql))
            connection.commit()
            
            print("\n" + "="*40)
            print("✅ SUCCESS!")
            print("Database is now correctly configured.")
            print("You can run viterbi.py")
            print("="*40)

        except Exception as e:
            # Provide more specific feedback on errors
            error_message = str(e).lower()
            if "already has a spatial index" in error_message:
                print("\n" + "="*40)
                print("✅ Looks like everything is already set up!")
                print("The spatial index already exists.")
                print("You can run viterbi.py")
                print("="*40)
            else:
                print(f"\n❌ An error occurred: {e}")
                print("Please check the error message above.")

if __name__ == "__main__":
    run()

