from beanie import Document
from datetime import datetime
from typing import List

class Project(Document):
    title: str
    description: str
    budget: float
    duration: str
    skills: List[str]
    category: str
    client_id: str
    client_name: str
    status: str = "open"
    proposals_count: int = 0
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "projects"