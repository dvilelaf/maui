import requests
import sys

USER_ID = 599142
BASE_URL = "http://localhost:8000/api"

def run_checks():
    print(f"Checking API at {BASE_URL}...")

    # 1. Get Tasks - Check for completed ones
    try:
        r = requests.get(f"{BASE_URL}/tasks/{USER_ID}")
        r.raise_for_status()
        tasks = r.json()
        print(f"✅ GET /tasks returned {len(tasks)} tasks.")

        has_completed = any(t['status'] == 'COMPLETED' for t in tasks)
        if has_completed:
            print("   ✅ Found COMPLETED tasks in list.")
        else:
            print("   ⚠️ No COMPLETED tasks found (might be expected if DB is clean).")

    except Exception as e:
        print(f"❌ GET /tasks FAILED: {e}")
        return

    # 2. Add Task
    new_id = None
    try:
        r = requests.post(f"{BASE_URL}/tasks/{USER_ID}/add", json={"content": "Test Verification Task"})
        r.raise_for_status()
        t = r.json()
        new_id = t['id']
        print(f"✅ POST /add created task ID {new_id}: {t['content']}")
    except Exception as e:
        print(f"❌ POST /add FAILED: {e}")
        return

    # 3. Verify Added Task appears in list
    try:
        r = requests.get(f"{BASE_URL}/tasks/{USER_ID}")
        tasks = r.json()
        found = any(t['id'] == new_id for t in tasks)
        if found:
             print(f"✅ New task {new_id} appears in GET /tasks.")
        else:
             print(f"❌ New task {new_id} NOT found in GET /tasks.")
    except Exception as e:
        print(f"❌ Verification GET FAILED: {e}")

    # 4. Delete Task
    if new_id:
        try:
            r = requests.post(f"{BASE_URL}/tasks/{new_id}/delete")
            r.raise_for_status()
            print(f"✅ POST /delete task {new_id} success.")

            # Verify it's gone from list
            r = requests.get(f"{BASE_URL}/tasks/{USER_ID}")
            tasks = r.json()
            found = any(t['id'] == new_id for t in tasks)
            if not found:
                print(f"✅ Deleted task {new_id} is correctly HIDDEN from GET /tasks.")
            else:
                print(f"❌ Deleted task {new_id} is STILL VISIBLE in GET /tasks.")

        except Exception as e:
            print(f"❌ POST /delete FAILED: {e}")

    # 5. Create List
    try:
        r = requests.post(f"{BASE_URL}/lists/{USER_ID}/add", json={"name": "New Test List"})
        r.raise_for_status()
        l = r.json()
        print(f"✅ POST /lists/add created list ID {l['id']}: {l['name']}")
    except Exception as e:
        print(f"❌ POST /lists/add FAILED: {e}")

    # 6. Uncomplete Task (if any)
    # Find a completed task first
    try:
         r = requests.get(f"{BASE_URL}/tasks/{USER_ID}")
         tasks = r.json()
         completed = next((t for t in tasks if t['status'] == 'COMPLETED'), None)
         if completed:
             cid = completed['id']
             r = requests.post(f"{BASE_URL}/tasks/{cid}/uncomplete")
             r.raise_for_status()
             print(f"✅ POST /uncomplete task {cid} success.")

             # Verify it's pending
             r = requests.get(f"{BASE_URL}/tasks/{USER_ID}")
             t_fresh = next((t for t in r.json() if t['id'] == cid), None)
             if t_fresh and t_fresh['status'] == 'PENDING':
                 print(f"✅ Task {cid} is now PENDING.")
             else:
                 print(f"❌ Task {cid} failed to revert to PENDING.")
         else:
             print("ℹ️ No completed task found to test uncomplete.")
    except Exception as e:
        print(f"❌ Uncomplete flow FAILED: {e}")

    # 7. List Management & Sharing
    try:
        # Create user B to share with
        SHARED_USER_ID = 999999
        r = requests.post(f"{BASE_URL}/tasks/{SHARED_USER_ID}/add", json={"content": "User B Task"}) # Init user implicitly if needed or just use ID

        # Share List 2 with User B
        # First ensure User B exists in DB (TaskManager.add_task does it implicitly? No, User access does.
        # But share_list looks up by username. User 999999 has no username unless we set it?
        # Let's inspect access.py resolve logic. It needs exact username match usually.
        # "User.get_or_none(User.username == query_str)"
        # I cannot easily create a username-d user via API add_task.
        # I might need to skip full Share flow verification in this script unless I insert a user into DB directly.
        # Let's verify Delete List instead.

        print("   Testing Delete List...")
        # Get pending lists
        r = requests.get(f"{BASE_URL}/lists/{USER_ID}")
        lists = r.json()
        if lists:
            lid = lists[0]['id']
            r = requests.post(f"{BASE_URL}/lists/{lid}/delete", json={"user_id": USER_ID})
            r.raise_for_status()
            print(f"✅ POST /lists/{lid}/delete success.")

            # Verify gone
            r = requests.get(f"{BASE_URL}/lists/{USER_ID}")
            remaining = [l['id'] for l in r.json()]
            if lid not in remaining:
                 print(f"✅ List {lid} is gone.")
            else:
                 print(f"❌ List {lid} STILL EXISTS.")
        else:
            print("ℹ️ No lists to delete.")

    except Exception as e:
        print(f"❌ List Management FAILED: {e}")

    # 8. Check Lists (original #7, renumbered)
    try:
        r = requests.get(f"{BASE_URL}/lists/{USER_ID}")
        r.raise_for_status()
        lists = r.json()
        print(f"✅ GET /lists returned {len(lists)} lists.")
        if len(lists) > 0:
            if 'tasks' in lists[0]:
                 print(f"   ✅ List 0 contains 'tasks' field (len={len(lists[0]['tasks'])}).")
            else:
                 print(f"   ❌ List response MISSING 'tasks' field.")
    except Exception as e:
         print(f"❌ GET /lists FAILED: {e}")

    # 9. Check Invites (New)
    try:
        r = requests.get(f"{BASE_URL}/invites/{USER_ID}")
        r.raise_for_status()
        invites = r.json()
        print(f"✅ GET /invites success (Count: {len(invites)}).")
    except Exception as e:
        print(f"❌ GET /invites FAILED: {e}")

if __name__ == "__main__":
    run_checks()
