from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, field_validator
from src.webapp.state import coordinator
from src.utils.schema import TaskStatus, TaskSchema
from src.webapp.auth import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# Models
class TaskCreate(BaseModel):
    content: str
    list_id: Optional[int] = None
    deadline: Optional[str] = None
    recurrence: Optional[str] = None

    @field_validator("deadline")
    @classmethod
    def empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v == "":
            return None
        return v


class TaskResponse(BaseModel):
    id: int
    content: str
    status: str
    list_id: Optional[int]
    deadline: Optional[str]


# Endpoints
@router.get("", response_model=List[TaskResponse])
async def get_tasks(user_id: int = Depends(get_current_user)):
    """Get all pending tasks for authenticated user."""
    tasks = coordinator.task_manager.get_user_tasks(user_id)
    return [
        TaskResponse(
            id=t.id,
            content=t.title,
            status=t.status,
            list_id=t.task_list.id if t.task_list else None,
            deadline=str(t.deadline) if t.deadline else None,
        )
        for t in tasks
    ]


@router.post("/add", response_model=TaskResponse)
async def add_task(task: TaskCreate, user_id: int = Depends(get_current_user)):
    """Add a new task."""
    schema = TaskSchema(
        title=task.content,
        description="",
        priority="MEDIUM",
        deadline=task.deadline,
        list_name=None,
        recurrence=task.recurrence,
    )

    new_task = coordinator.task_manager.add_task(user_id=user_id, task_data=schema)

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
        deadline=str(new_task.deadline) if new_task.deadline else None,
    )


@router.post("/{task_id}/complete")
async def complete_task(task_id: int, user_id: int = Depends(get_current_user)):
    # Note: we ignore body user_id now, trusting the auth header
    success = coordinator.task_manager.update_task_status(
        user_id, task_id, TaskStatus.COMPLETED
    )
    if not success:
        raise HTTPException(
            status_code=404, detail="Task not found or permission denied"
        )
    return {"status": "success"}


@router.post("/{task_id}/uncomplete")
async def uncomplete_task(task_id: int, user_id: int = Depends(get_current_user)):
    success = coordinator.task_manager.update_task_status(
        user_id, task_id, TaskStatus.PENDING
    )
    if not success:
        raise HTTPException(
            status_code=404, detail="Task not found or permission denied"
        )
    return {"status": "success"}


class TaskUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    recurrence: Optional[str] = None
    # user_id mixed in for backward compat if needed, but we prefer auth
    # user_id: int  <-- Removing this from strict requirement or ignoring it

    @field_validator("deadline")
    @classmethod
    def empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v == "":
            return None
        return v

    @field_validator("recurrence")
    @classmethod
    def empty_recurrence_to_none(cls, v: Optional[str]) -> Optional[str]:
        # Frontend sends "" for "No recurrence", we map to None
        if v == "":
            return None
        return v


@router.post("/{task_id}/delete")
async def delete_task(task_id: int, user_id: int = Depends(get_current_user)):
    success = coordinator.task_manager.delete_task(user_id, task_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Task not found or permission denied"
        )
    return {"status": "success"}


@router.post("/{task_id}/update")
async def update_task_content(
    task_id: int, update: TaskUpdate, user_id: int = Depends(get_current_user)
):
    # Check if there's anything to update
    # We now also check for recurrence
    if update.content is not None or update.deadline is not None or update.recurrence is not None:

        # We assume content (title) is the primary update, but others are optional.
        schema_kwargs = {}
        if update.content is not None:
            schema_kwargs["title"] = update.content

        # Handle deadline and recurrence.
        # Note: If deadline/recurrence is explicitly None (because frontend sent null?), it might be ignored if we use exclude_unset?
        # But we are constructing TaskSchema manually.
        # TaskSchema instantiation doesn't care about unset, it's just arguments.

        # We rely on the fact that we ONLY call this if at least one field is not None (conceptually, though unset fields might be problematic if we don't distinguish).
        # Actually, if frontend sends `deadline: null` or `deadline: ""`, Pydantic validator makes it None.
        # If it sends nothing, it is None by default in TaskUpdate.
        # How do we distinguish "Field Not Sent" vs "Field Sent as Null"?
        # Pydantic's `update.model_dump(exclude_unset=True)` is the robust way.

        update_dict = update.model_dump(exclude_unset=True)

        # We need to map 'content' to 'title' for TaskSchema
        if "content" in update_dict:
            update_dict["title"] = update_dict.pop("content")

        # TaskSchema expects keys matching its fields.
        # We can pass **update_dict directly.

        schema = TaskSchema(**update_dict)

        # Use user_id from Depends, ignore any body user_id
        success = coordinator.task_manager.edit_task(user_id, task_id, schema)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Task not found, permission denied, or no changes",
            )

    return {"status": "success"}
