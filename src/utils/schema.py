from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, time, timedelta

class TaskSchema(BaseModel):
    title: str = Field(description="The short summary or title of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task, if any")
    priority: str = Field("MEDIUM", description="Task priority: LOW, MEDIUM, HIGH, URGENT")
    deadline: Optional[datetime] = Field(None, description="The deadline for the task, if explicitly mentioned or inferred.")

    @field_validator('priority')
    def validate_priority(cls, v):
        if v.upper() not in ('LOW', 'MEDIUM', 'HIGH', 'URGENT'):
            return 'MEDIUM'
        return v.upper()

class TaskExtractionResponse(BaseModel):
    is_relevant: bool = Field(description="True if the user input describes a task, False otherwise.")
    formatted_task: Optional[TaskSchema] = Field(None, description="The extracted task details if relevant.")
    reasoning: Optional[str] = Field(None, description="If not relevant, explain why.")
