from beanie import Document
from datetime import datetime

class Contract(Document):
    proposal_id: str
    project_id: str

    client_id: str
    freelancer_id: str

    terms: str
    budget: float
    timeline: str

    status: str = "active"
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "contracts"