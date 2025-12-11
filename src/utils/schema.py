from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, time, timedelta

from enum import Enum

class UserIntent(str, Enum):
    ADD_TASK = "ADD_TASK"
    QUERY_TASKS = "QUERY_TASKS"
    CANCEL_TASK = "CANCEL_TASK"
    COMPLETE_TASK = "COMPLETE_TASK"
    EDIT_TASK = "EDIT_TASK"
    UNKNOWN = "UNKNOWN"

class TaskSchema(BaseModel):
    title: Optional[str] = Field(None, description="The short summary or title of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task, if any")
    priority: str = Field("MEDIUM", description="Task priority: LOW, MEDIUM, HIGH, URGENT")
    deadline: Optional[datetime] = Field(None, description="The deadline for the task, if explicitly mentioned or inferred.")

    @field_validator('priority')
    def validate_priority(cls, v):
        if v.upper() not in ('LOW', 'MEDIUM', 'HIGH', 'URGENT'):
            return 'MEDIUM'
        return v.upper()

class TaskExtractionResponse(BaseModel):
    is_relevant: bool = Field(description="True if the user input describes a task interaction.")
    intent: UserIntent = Field(description="The intent of the user.")
    time_filter: Optional[str] = Field(None, description="For QUERY_TASKS: 'TODAY', 'WEEK', 'MONTH', or 'ALL'. Defaults to 'ALL' if unspecified.")
    formatted_task: Optional[TaskSchema] = Field(None, description="The extracted task details (for ADD or EDIT).")
    target_search_term: Optional[str] = Field(None, description="Key phrase to find the existing task (for EDIT/CANCEL/COMPLETE).")
    reasoning: Optional[str] = Field(None, description="If UNKNOWN or ambiguous, explain why.")
