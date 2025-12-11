from peewee import Model, CharField, IntegerField, DateTimeField, ForeignKeyField, TimeField, BooleanField
from datetime import datetime
from src.database.core import db
from src.utils.schema import TaskStatus, UserStatus

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    telegram_id = IntegerField(primary_key=True)
    username = CharField(null=True)
    notification_time = TimeField(default="09:00:00") # Default 9 AM
    reminder_lead_time_minutes = IntegerField(default=60) # Default 1 hour before
    status = CharField(default=UserStatus.PENDING)

class Task(BaseModel):
    id = IntegerField(primary_key=True) # Peewee AutoField is default for 'id', but we might want explicit control or just let it auto-increment.
    # Actually, standard AuditField is best. Let's rely on default 'id' PK for Task if standard int pk is enough.
    # But wait, user requirement: "Cada tarea tiene un id" (inferred by LLM except id).
    # Usually DB assigns ID. Let's stick to standard auto-incrementing ID for database storage, distinct from any semantic ID if needed.
    # Simplest is standard SQLite AutoIncrement.

    user = ForeignKeyField(User, backref='tasks')
    title = CharField()
    description = CharField(null=True)
    priority = CharField(default="MEDIUM") # LOW, MEDIUM, HIGH, URGENT
    created_at = DateTimeField(default=datetime.now)
    deadline = DateTimeField(null=True)
    status = CharField(default=TaskStatus.PENDING) # PENDING, COMPLETED, CANCELLED
    reminder_sent = BooleanField(default=False)

def create_tables():
    with db:
        db.create_tables([User, Task])
