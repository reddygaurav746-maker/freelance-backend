from pydantic import BaseModel
from typing import Optional

class MilestoneCreate(BaseModel):
    contract_id: str
    title: str
    description: str
    amount: float
    due_date: str

class MilestoneUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    amount: Optional[float]
    due_date: Optional[str]
    status: Optional[str]