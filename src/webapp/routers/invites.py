from fastapi import APIRouter, HTTPException, Body
from typing import List
from pydantic import BaseModel
from src.webapp.state import coordinator

router = APIRouter(prefix="/api/invites", tags=["invites"])

# Models
class InviteResponse(BaseModel):
    list_id: int
    list_name: str
    owner_name: str

# Endpoints
@router.get("/{user_id}", response_model=List[InviteResponse])
async def get_invites(user_id: int):
    invites = coordinator.task_manager.get_pending_invites(user_id)
    return [InviteResponse(**i) for i in invites]

@router.post("/{list_id}/respond")
async def respond_invite_action(list_id: int, user_id: int = Body(..., embed=True), accept: bool = Body(..., embed=True)):
    success, msg = await coordinator.task_manager.respond_to_invite(user_id, list_id, accept)
    if not success:
         raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}
