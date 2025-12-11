import sqlite3
import os

DB_PATH = "maui.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]

        if "status" in columns:
            print("Column 'status' already exists in 'user' table.")
        else:
            print("Adding 'status' column to 'user' table...")
            # Default value matches UserStatus.PENDING ("PENDING")
            cursor.execute("ALTER TABLE user ADD COLUMN status VARCHAR(255) DEFAULT 'PENDING'")
            conn.commit()
            print("Migration successful.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
