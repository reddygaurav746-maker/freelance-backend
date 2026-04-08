from fastapi import APIRouter, Depends, HTTPException, Header
from beanie import PydanticObjectId
from datetime import datetime

from app.models.proposal import Proposal
from app.models.project import Project
from app.models.user import User
from app.auth.jwt_handler import verify_token
from app.schemas.proposal import ProposalCreate, ProposalUpdate
from app.services.get_current_user import get_current_user

router = APIRouter(prefix="/proposals", tags=["Proposals"])

@router.post("/")
async def create_proposal(
    data: ProposalCreate,
    user = Depends(get_current_user)   
):
    if user.role != "freelancer":
        raise HTTPException(403, "Only freelancers")
    project = await Project.get(PydanticObjectId(data.project_id))
    if not project:
        raise HTTPException(404, "Project not found")
    proposal = Proposal(
        **data.model_dump(),
        freelancer_id=str(user.id),
        freelancer_name=user.name,
        freelancer_email=user.email,
        status="pending"
    )
    await proposal.insert()
    return proposal

@router.get("/")
async def get_proposals():
    return await Proposal.find_all().to_list()


@router.put("/{proposal_id}")
async def update_proposal(proposal_id: str, data: ProposalUpdate, user = Depends(get_current_user)):
    proposal = await Proposal.get(PydanticObjectId(proposal_id))
    if not proposal:
        raise HTTPException(404, "Not found")

    if proposal.freelancer_id != str(user.id):
        raise HTTPException(403, "Not yours")

    for k, v in data.items():
        setattr(proposal, k, v)

    await proposal.save()
    return proposal


@router.delete("/{proposal_id}")
async def delete_proposal(proposal_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)

    proposal = await Proposal.get(PydanticObjectId(proposal_id))
    if not proposal:
        raise HTTPException(404, "Not found")

    if proposal.freelancer_id != str(user.id):
        raise HTTPException(403, "Not yours")

    await proposal.delete()
    return {"message": "Deleted"}