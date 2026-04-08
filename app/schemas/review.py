from pydantic import BaseModel
from typing import Optional

class ReviewCreate(BaseModel):
    contract_id: str
    rating: int
    comment: str

class ReviewUpdate(BaseModel):
    rating: Optional[int]
    comment: Optional[str]

class DisputeCreate(BaseModel):
    contract_id: str
    reason: str
    description: str