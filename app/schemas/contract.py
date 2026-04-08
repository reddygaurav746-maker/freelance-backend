from pydantic import BaseModel
from typing import Optional

class ContractCreate(BaseModel):
    proposal_id: str
    terms: str
    start_date: str
    end_date: str

class ContractUpdate(BaseModel):
    status: Optional[str]
    terms: Optional[str]