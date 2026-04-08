from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ProjectCreate(BaseModel):
    title: str
    description: str
    category: str
    required_skills: List[str]
    budget_min: float
    budget_max: float
    budget_type: str
    timeline: str
    deadline: Optional[datetime] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None