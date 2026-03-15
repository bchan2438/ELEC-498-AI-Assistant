import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Database_Code.ingest_data import connection, run_schema, insert_data

def main():
    conn = connection()
    try:
        run_schema(conn)
        insert_data(conn, "test")
        print("Database refresh complete.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()