from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from app.database import db
from app.auth.jwt_handler import create_access_token, verify_token
from app.auth.password import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Literal["freelancer", "client"]

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(user: UserCreate):
    existing_user = await db.users.find_one({"email": user.email})

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password before storing
    hashed_pwd = hash_password(user.password)
    
    user_data = {
        "name": user.name,
        "email": user.email,
        "password": hashed_pwd,
        "role": user.role
    }

    await db.users.insert_one(user_data)

    # Create JWT token
    token = create_access_token({"sub": user.email, "role": user.role})

    return {
        "token": token,
        "user": {
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }

@router.post("/login")
async def login(user: UserLogin):
    existing_user = await db.users.find_one({"email": user.email})

    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify the password using hashed comparison
    if not verify_password(user.password, existing_user["password"]):
        raise HTTPException(status_code=400, detail="Invalid password")

    # Create JWT token
    token = create_access_token({
        "sub": existing_user["email"],
        "role": existing_user["role"]
    })

    return {
        "token": token,
        "user": {
            "name": existing_user["name"],
            "email": existing_user["email"],
            "role": existing_user["role"]
        }
    }
    
@router.get("/me")
async def get_current_user(authorization: str = None):
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }
