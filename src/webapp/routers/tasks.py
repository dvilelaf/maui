from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from src.webapp.state import coordinator
from src.utils.schema import TaskStatus, TaskSchema

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Models
class TaskCreate(BaseModel):
    content: str
    list_id: Optional[int] = None

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    user_id: int

class TaskResponse(BaseModel):
    id: int
    content: str
    status: str
    list_id: Optional[int]
    deadline: Optional[str]

# Endpoints
@router.get("/{user_id}", response_model=List[TaskResponse])
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

@router.post("/{user_id}/add", response_model=TaskResponse)
async def add_task(user_id: int, task: TaskCreate):
    """Add a new task."""
    schema = TaskSchema(
        title=task.content,
        description="",
        priority="MEDIUM",
        deadline=None,
        list_name=None
    )

    new_task = coordinator.task_manager.add_task(
        user_id=user_id,
        task_data=schema
    )

    if new_task and task.list_id:
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

@router.post("/{task_id}/complete")
async def complete_task(task_id: int, user_id: int = Body(..., embed=True)):
    # This works fine as a single body param
    success = coordinator.task_manager.update_task_status(user_id, task_id, TaskStatus.COMPLETED)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found or permission denied")
    return {"status": "success"}

@router.post("/{task_id}/uncomplete")
async def uncomplete_task(task_id: int, user_id: int = Body(..., embed=True)):
    success = coordinator.task_manager.update_task_status(user_id, task_id, TaskStatus.PENDING)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found or permission denied")
    return {"status": "success"}

@router.post("/{task_id}/delete")
async def delete_task(task_id: int, user_id: int = Body(..., embed=True)):
    success = coordinator.task_manager.delete_task(user_id, task_id)
    if not success:
         raise HTTPException(status_code=404, detail="Task not found or permission denied")
    return {"status": "success"}

@router.post("/{task_id}/update")
async def update_task_content(task_id: int, update: TaskUpdate):
    # update includes user_id now
    if update.content:
        schema = TaskSchema(title=update.content)
        success = coordinator.task_manager.edit_task(update.user_id, task_id, schema)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found, permission denied, or no changes")

    return {"status": "success"}
