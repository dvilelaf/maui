from src.database.core import init_db
from src.database.models import User
from src.utils.config import Config

def update_saris():
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))

    # Ensure columns exist first by running migration implicitly if needed? No, separate task.

    # Logic: Update "user who has no username" to first_name = "Saris"
    # Find users with NULL username
    users = User.select().where(User.username.is_null(True))

    count = 0
    for user in users:
        print(f"Found user without username: {user.telegram_id}")
        user.first_name = "Saris"
        user.save()
        count += 1

    print(f"Updated {count} users.")

if __name__ == "__main__":
    update_saris()
