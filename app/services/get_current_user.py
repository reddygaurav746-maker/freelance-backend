from fastapi import Header, HTTPException
from app.models.user import User
from app.auth.jwt_handler import verify_token

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid token")

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)

    user = await User.find_one(User.email == payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")

    return user