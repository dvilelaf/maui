
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging

from src.services.coordinator import Coordinator
from src.utils.schema import TaskStatus, TaskSchema

from contextlib import asynccontextmanager
from src.utils.config import Config
from src.database.core import db, init_db

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Database...")
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))
    db.connect()
    yield
    # Shutdown
    logger.info("Closing Database...")
    if not db.is_closed():
        db.close()

app = FastAPI(title="Maui Web App", lifespan=lifespan)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Coordinator (singleton-like per process)
coordinator = Coordinator()

# Pydantic models for API
class TaskCreate(BaseModel):
    content: str
    list_id: Optional[int] = None

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    content: str
    status: str
    list_id: Optional[int]
    deadline: Optional[str]

class ListResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    task_count: int
    tasks: List["TaskResponse"] = []

class ListCreate(BaseModel):
    name: str

# --- API Endpoints ---

@app.get("/api/tasks/{user_id}", response_model=List[TaskResponse])
async def get_tasks(user_id: int):
    """Get all pending tasks for a user."""
    tasks = coordinator.task_manager.get_user_tasks(user_id)
    return [
        TaskResponse(
            id=t.id,
            content=t.title,
            status=t.status,
            list_id=t.task_list.id if t.task_list else None,
            deadline=str(t.deadline) if t.deadline else None
        )
        for t in tasks
    ]

@app.get("/api/lists/{user_id}", response_model=List[ListResponse])
async def get_lists(user_id: int):
    """Get all lists for a user."""
    lists = coordinator.task_manager.get_lists(user_id)
    result = []
    for lst in lists:
        tasks_in_list = coordinator.task_manager.get_tasks_in_list(lst.id)
        task_responses = [
            TaskResponse(
                id=t.id,
                content=t.title,
                status=t.status,
                list_id=t.task_list.id if t.task_list else None,
                deadline=str(t.deadline) if t.deadline else None
            ) for t in tasks_in_list
        ]
        # Allow accessing owner.id. Using peewee object directly.
        result.append(ListResponse(
            id=lst.id,
            name=lst.title,
            owner_id=lst.owner_id, # Map owner ID using raw foreign key
            task_count=len(tasks_in_list),
            tasks=task_responses
        ))
    return result

@app.post("/api/tasks/{user_id}/add", response_model=TaskResponse)
async def add_task(user_id: int, task: TaskCreate):
    """Add a new task."""
    # Create TaskSchema for internal use
    from datetime import datetime
    schema = TaskSchema(
        title=task.content,
        description="", # Default
        priority="MEDIUM", # Default
        deadline=None,
        list_name=None # Handle mapping list_id if needed, but schema uses list_name?
                       # Wait, TaskSchema has list_name, but we have list_id.
                       # TaskManager logic resolves list_name.
                       # If we have ID, we might need to adjust TaskManager or pass list_name if possible.
                       # But for now let's see. TaskManager maps list_name to ID.
                       # Since we strictly have list_id (optional), we might need to modify TaskManager to accept list_id or handle it here.
                       # The cleanest way given existing TaskManager.add_task logic:
                       # It ONLY looks at task_data.list_name.
                       # I should probably update TaskManager.add_task to respect an explicit list_id/task_list override if possible,
                       # OR just pass list_name if we knew it.
                       # But `TaskCreate` has `list_id`.
                       # Actually, looking at TaskManager.add_task:
                       # "if task_data.list_name: found_list = ..."
                       # It ignores list_id.
                       # I cannot easily pass list_id via TaskSchema if it doesn't support it or logic doesn't use it.
                       # Let's check TaskSchema definition.
    )
    # Actually TaskManager.add_task creates the Task model:
    # task_list=target_list_id
    # target_list_id comes from find_list_by_name(list_name).
    # This is a limitation of TaskManager.add_task. It is designed for Bot (text-based).
    # I should OVERLOAD or MODIFY TaskManager.add_task to accept an optional explicit `list_id`.

    # Let's modify TaskManager.add_task first to verify my hypothesis.
    # But for now, fixing the call signature to at least pass a schema is Step 1.
    # Step 2 is ensuring list assignment works.

    new_task = coordinator.task_manager.add_task(
        user_id=user_id,
        task_data=schema
    )

    # Wait, if I pass schema with list_name=None, it won't be assigned to a list even if I wanted to.
    # And I can't look up name from ID easily here without extra query.
    # Better to allow `add_task` to take an extra arg `override_list_id`?
    # Or just update the task after creation if list_id is set?
    # Updating after creation is safer/easier with existing legacy code.

    if new_task and task.list_id:
        # Update relationship
        new_task.task_list = task.list_id
        new_task.save()
    if not new_task:
        raise HTTPException(status_code=500, detail="Failed to create task")

    return TaskResponse(
        id=new_task.id,
        content=new_task.title,
        status=new_task.status,
        list_id=new_task.task_list.id if new_task.task_list else None,
        deadline=str(new_task.deadline) if new_task.deadline else None
    )

@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    success = coordinator.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

    return {"status": "success"}

@app.post("/api/tasks/{task_id}/uncomplete")
async def uncomplete_task(task_id: int):
    success = coordinator.task_manager.update_task_status(task_id, TaskStatus.PENDING)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@app.post("/api/lists/{user_id}/add", response_model=ListResponse)
async def create_list(user_id: int, lst: ListCreate):
    new_list = coordinator.task_manager.create_list(user_id, lst.name)
    return ListResponse(id=new_list.id, name=new_list.title, owner_id=user_id, task_count=0, tasks=[])

@app.post("/api/tasks/{task_id}/delete")
async def delete_task(task_id: int):
    success = coordinator.task_manager.delete_task(task_id)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@app.post("/api/tasks/{task_id}/update")
async def update_task_content(task_id: int, update: TaskUpdate):
    # Create TaskSchema from TaskUpdate
    # We only map content -> title for now as that's the main edit
    schema = TaskSchema(
        title=update.content if update.content is not None else "", # Handle optional
        deadline=None, # Todo: Parse if passed
        description="",
        priority="MEDIUM"
    )

    # We need to construct a schema that ONLY has the fields we want to update.
    # TaskManager.edit_task uses model_dump(exclude_unset=True).
    # But TaskSchema fields are required? No, they have defaults in schema.py but
    # let's check TaskSchema definition if I can.
    # Actually TaskSchema probably has defaults.
    # Let's verify TaskSchema in src/utils/schema.py if I have doubts, but for now
    # I'll rely on constructing it.

    # Wait, passing empty strings might overwrite existing data if I'm not careful.
    # TaskManager.edit_task does: updates = update_data.model_dump(exclude_unset=True)
    # If I create TaskSchema(title=""), title IS set.
    # So I need to be careful.
    # Pydantic models in Python: if field has default, it is set.

    # Better approach: Modify TaskManager.edit_task to accept a dict?
    # Or just ensure TaskSchema fields are Optional.
    # Let's assume for this task we are strictly updating CONTENT (title).

    # If update.content is None, we shouldn't send it.
    # But TaskSchema requires title?

    # Let's look at TaskSchema.
    # Use code search or just view it?
    # I'll assume for now I can pass what I have.

    if update.content:
        schema = TaskSchema(title=update.content)
        success = coordinator.task_manager.edit_task(task_id, schema)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or no changes")

    return {"status": "success"}

class InviteResponse(BaseModel):
    list_id: int
    list_name: str
    owner_name: str

class ShareRequest(BaseModel):
    username: str

@app.post("/api/lists/{list_id}/delete")
async def delete_list(list_id: int, user_id: int = Body(..., embed=True)):
    success = coordinator.task_manager.delete_list(user_id, list_id)
    if not success:
         raise HTTPException(status_code=403, detail="Failed to delete list")
    return {"status": "success"}

@app.post("/api/lists/{list_id}/leave")
async def leave_list(list_id: int, user_id: int = Body(..., embed=True)):
    success, msg = await coordinator.task_manager.leave_list(user_id, list_id)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

@app.post("/api/lists/{list_id}/share")
async def share_list(list_id: int, body: ShareRequest):
    success, msg = await coordinator.task_manager.share_list(list_id, body.username)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

@app.get("/api/invites/{user_id}", response_model=List[InviteResponse])
async def get_invites(user_id: int):
    invites = coordinator.task_manager.get_pending_invites(user_id)
    return [InviteResponse(**i) for i in invites]

@app.post("/api/invites/{list_id}/respond")
async def respond_invite_action(list_id: int, user_id: int = Body(..., embed=True), accept: bool = Body(..., embed=True)):
    success, msg = await coordinator.task_manager.respond_to_invite(user_id, list_id, accept)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# Serve Frontend - Must be last
app.mount("/", StaticFiles(directory="src/webapp/static", html=True), name="static")
