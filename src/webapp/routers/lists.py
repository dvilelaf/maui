from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from src.webapp.state import coordinator
from src.webapp.routers.tasks import TaskResponse

router = APIRouter(prefix="/api/lists", tags=["lists"])

# Models
class ListResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    task_count: int
    tasks: List[TaskResponse] = []

class ListCreate(BaseModel):
    name: str

class ShareRequest(BaseModel):
    username: str

# Endpoints
@router.get("/{user_id}", response_model=List[ListResponse])
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
        result.append(ListResponse(
            id=lst.id,
            name=lst.title,
            owner_id=lst.owner_id,
            task_count=len(tasks_in_list),
            tasks=task_responses
        ))
    return result

@router.post("/{user_id}/add", response_model=ListResponse)
async def create_list(user_id: int, lst: ListCreate):
    new_list = coordinator.task_manager.create_list(user_id, lst.name)
    return ListResponse(id=new_list.id, name=new_list.title, owner_id=user_id, task_count=0, tasks=[])

@router.post("/{list_id}/delete")
async def delete_list(list_id: int, user_id: int = Body(..., embed=True)):
    success = coordinator.task_manager.delete_list(user_id, list_id)
    if not success:
         raise HTTPException(status_code=403, detail="Failed to delete list")
    return {"status": "success"}

@router.post("/{list_id}/leave")
async def leave_list(list_id: int, user_id: int = Body(..., embed=True)):
    success, msg = await coordinator.task_manager.leave_list(user_id, list_id)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

@router.post("/{list_id}/share")
async def share_list(list_id: int, body: ShareRequest, user_id: int = Body(..., embed=True)):
    success, msg = await coordinator.task_manager.share_list(user_id, list_id, body.username)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}
