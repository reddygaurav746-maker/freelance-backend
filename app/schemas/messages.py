from pydantic import BaseModel
from typing import Optional

class MessageCreate(BaseModel):
    recipient_id: str
    content: str

class MessageUpdate(BaseModel):
    read: Optional[bool]