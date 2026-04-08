from pydantic import BaseModel
from typing import Optional, List

class ProjectCreate(BaseModel):
    title: str
    description: str
    budget: float
    duration: str
    skills: List[str]
    category: str

class ProjectUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    budget: Optional[float]
    duration: Optional[str]
    skills: Optional[List[str]]
    category: Optional[str]
    status: Optional[str]