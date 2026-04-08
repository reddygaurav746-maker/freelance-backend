from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime
from beanie import PydanticObjectId

from app.models.project import Project
from app.models.user import User
from app.auth.jwt_handler import verify_token
from app.schemas.project import ProjectCreate
from app.services.get_current_user import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])



@router.post("/")
async def create_project(
    data: ProjectCreate,
    authorization: str = None
):
    user = await get_current_user(authorization)

    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients allowed")

    project = Project(
        **data.model_dump(),   
        client_id=str(user.id),
        client_name=user.name,
        status="open",
        proposals_count=0,
        created_at=datetime.utcnow()
    )

    await project.insert()
    return project

@router.get("/")
async def get_projects():
    return await Project.find_all().to_list()


@router.get("/{project_id}")
async def get_project(project_id: str):
    project = await Project.get(PydanticObjectId(project_id))
    if not project:
        raise HTTPException(404, "Not found")
    return project


@router.put("/{project_id}")
async def update_project(project_id: str, data: dict, authorization: str = Header(None)):
    user = await get_current_user(authorization)

    project = await Project.get(PydanticObjectId(project_id))
    if not project:
        raise HTTPException(404, "Not found")

    if project.client_id != str(user.id):
        raise HTTPException(403, "Not yours")

    for k, v in data.items():
        setattr(project, k, v)

    await project.save()
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)

    project = await Project.get(PydanticObjectId(project_id))
    if not project:
        raise HTTPException(404, "Not found")

    if project.client_id != str(user.id):
        raise HTTPException(403, "Not yours")

    await project.delete()
    return {"message": "Deleted"}