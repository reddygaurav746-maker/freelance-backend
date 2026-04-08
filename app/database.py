from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

# Async MongoDB client
client = AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.DATABASE_NAME]
