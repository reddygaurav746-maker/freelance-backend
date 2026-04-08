from beanie import Document
from datetime import datetime

class Proposal(Document):
    project_id: str
    freelancer_id: str

    freelancer_name: str
    freelancer_email: str

    cover_letter: str
    proposed_budget: float
    timeline: str

    status: str = "pending"
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "proposals"