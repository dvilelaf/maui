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

class TimeFilter(str, Enum):
    TODAY = "TODAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"
    ALL = "ALL"

TARGET_ALL = "ALL"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskSchema(BaseModel):
    title: Optional[str] = Field(None, description="The short summary or title of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task, if any")
    priority: Optional[str] = Field("MEDIUM", description="Task priority: LOW, MEDIUM, HIGH, URGENT")
    deadline: Optional[datetime] = Field(None, description="The deadline for the task, if explicitly mentioned or inferred.")

    @field_validator('priority')
    def validate_priority(cls, v):
        if v is None:
            return 'MEDIUM'
        if v.upper() not in ('LOW', 'MEDIUM', 'HIGH', 'URGENT'):
            return 'MEDIUM'
        return v.upper()

    @field_validator('title')
    def validate_title(cls, v):
        if v:
            return v[0].upper() + v[1:]
        return v

class TaskExtractionResponse(BaseModel):
    is_relevant: bool = Field(description="True if the user input describes a task interaction.")
    intent: UserIntent = Field(description="The intent of the user.")
    time_filter: Optional[TimeFilter] = Field(TimeFilter.ALL, description="For QUERY_TASKS. Defaults to ALL.")
    formatted_task: Optional[TaskSchema] = Field(None, description="The extracted task details (for ADD or EDIT).")
    target_search_term: Optional[str] = Field(None, description="Key phrase to find the existing task (for EDIT/CANCEL/COMPLETE).")
    reasoning: Optional[str] = Field(None, description="If UNKNOWN or ambiguous, explain why.")
