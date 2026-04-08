from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os


from app.models.user import User
from app.models.project import Project
from app.models.proposal import Proposal
from app.models.contract import Contract

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "freelance_db")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]


async def init_db():
    await init_beanie(
        database=db,
        document_models=[
            User,
            Project,
            Proposal,
            Contract,
        ]
    )