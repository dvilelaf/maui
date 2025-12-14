from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from src.webapp.state import coordinator
from src.webapp.routers.tasks import TaskResponse
from src.webapp.auth import get_current_user

router = APIRouter(prefix="/api/lists", tags=["lists"])


# Models
class ListResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    task_count: int
    color: str = "#f2f2f2"
    tasks: List[TaskResponse] = []


class ListCreate(BaseModel):
    name: str


class ShareRequest(BaseModel):
    username: str
    # user_id: int - from auth now


# Endpoints
@router.get("", response_model=List[ListResponse])
async def get_lists(user_id: int = Depends(get_current_user)):
    """Get all lists for authenticated user."""
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
                deadline=str(t.deadline) if t.deadline else None,
            )
            for t in tasks_in_list
        ]
        result.append(
            ListResponse(
                id=lst.id,
                name=lst.title,
                owner_id=lst.owner_id,
                task_count=len(tasks_in_list),
                color=lst.color or "#f2f2f2",
                tasks=task_responses,
            )
        )
    return result


@router.post("/add", response_model=ListResponse)
async def create_list(lst: ListCreate, user_id: int = Depends(get_current_user)):
    new_list = coordinator.task_manager.create_list(user_id, lst.name)
    return ListResponse(
        id=new_list.id, name=new_list.title, owner_id=user_id, task_count=0, tasks=[]
    )


@router.post("/{list_id}/delete")
async def delete_list(list_id: int, user_id: int = Depends(get_current_user)):
    success = coordinator.task_manager.delete_list(user_id, list_id)
    if not success:
        raise HTTPException(status_code=403, detail="Failed to delete list")
    return {"status": "success"}


@router.post("/{list_id}/leave")
async def leave_list(list_id: int, user_id: int = Depends(get_current_user)):
    success, msg = await coordinator.task_manager.leave_list(user_id, list_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}


class ListUpdate(BaseModel):
    name: str


class ListColorUpdate(BaseModel):
    color: str


# Endpoints
@router.post("/{list_id}/color")
async def update_list_color(
    list_id: int, update: ListColorUpdate, user_id: int = Depends(get_current_user)
):
    success = coordinator.task_manager.edit_list_color(user_id, list_id, update.color)
    if not success:
        raise HTTPException(
            status_code=403, detail="Failed to change list color or permission denied"
        )
    return {"status": "success"}


# Endpoints
@router.post("/{list_id}/update")
async def update_list(
    list_id: int, update: ListUpdate, user_id: int = Depends(get_current_user)
):
    success = coordinator.task_manager.edit_list(user_id, list_id, update.name)
    if not success:
        raise HTTPException(
            status_code=430, detail="Failed to rename list or permission denied"
        )
    return {"status": "success"}


@router.post("/{list_id}/share")
async def share_list(
    list_id: int, body: ShareRequest, user_id: int = Depends(get_current_user)
):
    success, msg = await coordinator.task_manager.share_list(
        user_id, list_id, body.username
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}


class ReorderRequest(BaseModel):
    list_ids: List[int]


@router.post("/reorder")
async def reorder_lists_endpoint(
    req: ReorderRequest, user_id: int = Depends(get_current_user)
):
    success = coordinator.task_manager.reorder_lists(user_id, req.list_ids)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reorder lists")
    return {"status": "success"}
