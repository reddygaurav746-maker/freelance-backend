from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    title: str
    description: str
    budget: float
    duration: str
    
    skills: List[str]
    category: str

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    duration: Optional[str] = None
    skills: Optional[List[str]] = None
    category: Optional[str] = None
    status: Optional[str] = None

async def get_current_user_id(authorization: str = None):
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
    
    return user

@router.post("/")
async def create_project(project: ProjectCreate, authorization: str = Header(None)):
    user = await get_current_user_id(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can post projects")
    
    project_data = {
        "title": project.title,
        "description": project.description,
        "budget": project.budget,
        "duration": project.duration,
        "skills": project.skills,
        "category": project.category,
        "client_id": str(user["_id"]),
        "client_name": user["name"],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "proposals_count": 0
    }
    
    result = await db.projects.insert_one(project_data)
    project_data["_id"] = str(result.inserted_id)
    
    return {"message": "Project created successfully", "project": project_data}

@router.get("/")
async def get_projects(
    authorization: str = Header(None),
    status: str = None,
    category: str = None,
    min_budget: float = None,
    max_budget: float = None
):
    query = {"status": "open"}
    
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if min_budget is not None:
        query["budget"] = {"$gte": min_budget}
    if max_budget is not None:
        if "budget" in query:
            query["budget"]["$lte"] = max_budget
        else:
            query["budget"] = {"$lte": max_budget}
    
    projects = await db.projects.find(query).sort("created_at", -1).to_list(length=None)
    
    for project in projects:
        project["_id"] = str(project["_id"])
    
    return {"projects": projects}

@router.get("/my-projects")
async def get_my_projects(authorization: str = Header(None)):
    user = await get_current_user_id(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can view their projects")
    
    projects = await db.projects.find({"client_id": str(user["_id"])}).sort("created_at", -1).to_list(length=None)
    
    for project in projects:
        project["_id"] = str(project["_id"])
    
    return {"projects": projects}

@router.get("/{project_id}")
async def get_project(project_id: str, authorization: str = Header(None)):
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project["_id"] = str(project["_id"])
    return {"project": project}

@router.put("/{project_id}")
async def update_project(project_id: str, project: ProjectUpdate, authorization: str = Header(None)):
    user = await get_current_user_id(authorization)
    
    try:
        existing_project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if existing_project["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only update your own projects")
    
    update_data = {k: v for k, v in project.model_dump().items() if v is not None}
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": update_data}
    )
    
    updated_project = await db.projects.find_one({"_id": ObjectId(project_id)})
    updated_project["_id"] = str(updated_project["_id"])
    
    return {"message": "Project updated successfully", "project": updated_project}

@router.delete("/{project_id}")
async def delete_project(project_id: str, authorization: str = Header(None)):
    user = await get_current_user_id(authorization)
    
    try:
        existing_project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if existing_project["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only delete your own projects")
    
    await db.projects.delete_one({"_id": ObjectId(project_id)})
    
    return {"message": "Project deleted successfully"}

@router.get("/categories/list")
def get_categories():
    categories = [
        "Web Development",
        "Mobile Development",
        "UI/UX Design",
        "Graphic Design",
        "Data Science",
        "DevOps",
        "Content Writing",
        "Digital Marketing",
        "Video Editing",
        "Other"
    ]
    return {"categories": categories}