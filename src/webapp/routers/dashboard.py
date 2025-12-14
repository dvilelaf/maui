from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from src.webapp.state import coordinator
from src.webapp.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardItem(BaseModel):
    type: str  # 'task' or 'list'
    data: Any
    created_at: datetime
    position: int


class DatedItem(BaseModel):
    id: int
    title: str
    deadline: datetime
    priority: str
    status: str
    list_id: Optional[int]
    list_name: Optional[str]
    list_color: Optional[str]


@router.get("/dated", response_model=List[DatedItem])
async def get_dated_items(user_id: int = Depends(get_current_user)):
    # Legacy path param removed. Frontend must use /dated
    tasks = coordinator.task_manager.get_dated_items(user_id)
    result = []
    for t in tasks:
        item = {
            "id": t.id,
            "title": t.title,
            "deadline": t.deadline,
            "priority": t.priority,
            "status": t.status,
            "list_id": None,
            "list_name": None,
            "list_color": None,
        }
        if t.task_list:
            item["list_id"] = t.task_list.id
            item["list_name"] = t.task_list.title
            item["list_color"] = t.task_list.color

        result.append(item)
    return result


@router.get("/all")
async def get_all_items(user_id: int = Depends(get_current_user)):
    # Returns mixed list of Tasks and Lists
    # We return raw dicts because Pydantic Polymorphism with "data" Any field is tricky without Unions,
    # and we want to keep it simple JSON.
    items = coordinator.task_manager.get_dashboard_items(user_id)

    # Serialize for frontend
    serialized = []
    for item in items:
        data = item["data"]
        obj = {
            "type": item["type"],
            "id": data.id,
            "title": data.title,
            "position": item["position"],
            "created_at": item["created_at"].isoformat()
            if item["created_at"]
            else None,
        }

        if item["type"] == "task":
            obj["status"] = data.status
            obj["priority"] = data.priority
            obj["deadline"] = data.deadline.isoformat() if data.deadline else None

        elif item["type"] == "list":
            obj["color"] = data.color
            # Owner? Task count?
            # kept simple for dashboard view
            obj["task_count"] = data.tasks.count()

        serialized.append(obj)

    return serialized


class ReorderItem(BaseModel):
    type: str
    id: int


class ReorderMixedRequest(BaseModel):
    user_id: int
    items: List[ReorderItem]


@router.post("/reorder")
async def reorder_mixed(req: ReorderMixedRequest, user_id: int = Depends(get_current_user)):
    # Ignore req.user_id, use authorized user_id

    # Simple logic: Iterate and update each entity with its new global index.
    from src.database.models import Task, TaskList, SharedAccess, db

    try:
        with db.atomic():
            for index, item in enumerate(req.items):
                if item.type == "task":
                    Task.update(position=index).where(
                        (Task.id == item.id) & (Task.user == user_id)
                    ).execute()
                elif item.type == "list":
                    # Update Owned
                    res = (
                        TaskList.update(position=index)
                        .where(
                            (TaskList.id == item.id) & (TaskList.owner == user_id)
                        )
                        .execute()
                    )
                    if res == 0:
                        # Update Shared
                        SharedAccess.update(position=index).where(
                            (SharedAccess.task_list == item.id)
                            & (SharedAccess.user == user_id)
                        ).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

