import requests
import sqlite3
import os

USER_ID = 599142
BASE_URL = "http://localhost:8000/api"
DB_PATH = "maui.db" # Assumed in CWD

def check_db_count(task_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM task WHERE id = ?", (task_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def run():
    print("--- Hard Delete Verification ---")

    # 1. Create a task
    print("1. Creating task...")
    r = requests.post(f"{BASE_URL}/tasks/{USER_ID}/add", json={"content": "To Be Incinerated"})
    r.raise_for_status()
    task = r.json()
    tid = task['id']
    print(f"   Created Task ID {tid}")

    # 2. Check DB
    count = check_db_count(tid)
    print(f"   DB Count for ID {tid}: {count} (Expected: 1)")
    if count != 1:
        print("❌ Setup failed: Task not found in DB.")
        return

    # 3. Delete via API
    print("2. Deleting task via API...")
    r = requests.post(f"{BASE_URL}/tasks/{tid}/delete")
    r.raise_for_status()
    print("   Delete request success.")

    # 4. Check DB Again
    count_after = check_db_count(tid)
    print(f"   DB Count for ID {tid} after delete: {count_after} (Expected: 0)")

    if count_after == 0:
        print("✅ SUCCESS: Task completely removed from DB.")
    else:
        print("❌ FAILURE: Task still exists in DB.")

if __name__ == "__main__":
    run()
