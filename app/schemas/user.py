from pydantic import BaseModel
from typing import Literal

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Literal["freelancer", "client"]

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    name: str
    email: str
    role: str