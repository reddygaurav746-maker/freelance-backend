from fastapi import APIRouter, Depends, HTTPException, Header
from beanie import PydanticObjectId
from datetime import datetime

from app.models.contract import Contract
from app.models.proposal import Proposal
from app.models.project import Project
from app.models.user import User
from app.schemas.contract import ContractCreate
from app.services.get_current_user import get_current_user

router = APIRouter(prefix="/contracts", tags=["Contracts"])

@router.post("/")
async def create_contract(data:ContractCreate ,user = Depends(get_current_user)):
    if user.role != "client":
        raise HTTPException(403, "Only clients")

    proposal = await Proposal.get(PydanticObjectId(data.proposal_id))
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    project = await Project.get(PydanticObjectId(proposal.project_id))

    contract = Contract(
        proposal_id=str(proposal.id),
        project_id=str(project.id),
        client_id=str(user.id),
        freelancer_id=proposal.freelancer_id,
        terms=data["terms"],
        budget=proposal.proposed_budget,
        timeline=proposal.timeline,
        status="active",
        created_at=datetime.utcnow()
    )

    await contract.insert()
    return contract


@router.get("/")
async def get_contracts():
    return await Contract.find_all().to_list()


@router.get("/{contract_id}")
async def get_contract(contract_id: str):
    contract = await Contract.get(PydanticObjectId(contract_id))
    if not contract:
        raise HTTPException(404, "Not found")
    return contract


@router.put("/{contract_id}")
async def update_contract(contract_id: str, data: dict):
    contract = await Contract.get(PydanticObjectId(contract_id))
    if not contract:
        raise HTTPException(404, "Not found")

    for k, v in data.items():
        setattr(contract, k, v)

    await contract.save()
    return contract