from pydantic import BaseModel
from typing import Optional

class ProposalCreate(BaseModel):
    project_id: str
    cover_letter: str
    proposed_budget: float
    timeline: str

class ProposalUpdate(BaseModel):
    cover_letter: Optional[str]
    proposed_budget: Optional[float]
    timeline: Optional[str]
    status: Optional[str]