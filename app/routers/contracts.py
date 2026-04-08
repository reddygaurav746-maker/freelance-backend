from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/contracts", tags=["Contracts"])


class ContractCreate(BaseModel):
    proposal_id: str
    terms: str
    start_date: str
    end_date: str


class ContractUpdate(BaseModel):
    status: Optional[str] = None
    terms: Optional[str] = None


def get_current_user(authorization: str = None):
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
    
    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.post("/")
def create_contract(contract: ContractCreate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can create contracts")
    
    # Get the proposal
    try:
        proposal = db.proposals.find_one({"_id": ObjectId(contract.proposal_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid proposal ID")
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal["status"] != "accepted":
        raise HTTPException(status_code=400, detail="Can only create contract from accepted proposal")
    
    # Get the project
    try:
        project = db.projects.find_one({"_id": ObjectId(proposal["project_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only create contracts for your own projects")
    
    # Check if contract already exists for this proposal
    existing_contract = db.contracts.find_one({"proposal_id": contract.proposal_id})
    if existing_contract:
        raise HTTPException(status_code=400, detail="Contract already exists for this proposal")
    
    contract_data = {
        "proposal_id": contract.proposal_id,
        "project_id": proposal["project_id"],
        "client_id": str(user["_id"]),
        "client_name": user["name"],
        "freelancer_id": proposal["freelancer_id"],
        "freelancer_name": proposal["freelancer_name"],
        "freelancer_email": proposal["freelancer_email"],
        "project_title": project["title"],
        "terms": contract.terms,
        "budget": proposal["proposed_budget"],
        "timeline": proposal["timeline"],
        "start_date": contract.start_date,
        "end_date": contract.end_date,
        "status": "active",
        "created_at": datetime.now().isoformat()
    }
    
    result = db.contracts.insert_one(contract_data)
    contract_data["_id"] = str(result.inserted_id)
    
    # Update project status
    db.projects.update_one(
        {"_id": ObjectId(proposal["project_id"])},
        {"$set": {"status": "in_progress"}}
    )
    
    return {"message": "Contract created successfully", "contract": contract_data}


@router.get("/")
def get_contracts(authorization: str = Header(None), status: str = None):
    user = get_current_user(authorization)
    
    query = {}
    
    if user["role"] == "client":
        query["client_id"] = str(user["_id"])
    elif user["role"] == "freelancer":
        query["freelancer_id"] = str(user["_id"])
    
    if status:
        query["status"] = status
    
    contracts = list(db.contracts.find(query).sort("created_at", -1))
    
    for contract in contracts:
        contract["_id"] = str(contract["_id"])
    
    return {"contracts": contracts}


@router.get("/my-contracts")
def get_my_contracts(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] == "client":
        contracts = list(db.contracts.find({"client_id": str(user["_id"])}).sort("created_at", -1))
    else:
        contracts = list(db.contracts.find({"freelancer_id": str(user["_id"])}).sort("created_at", -1))
    
    for contract in contracts:
        contract["_id"] = str(contract["_id"])
    
    return {"contracts": contracts}


@router.get("/{contract_id}")
def get_contract(contract_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check access
    if user["role"] == "client" and contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if user["role"] == "freelancer" and contract["freelancer_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    contract["_id"] = str(contract["_id"])
    
    # Get milestones for this contract
    milestones = list(db.milestones.find({"contract_id": contract_id}))
    for milestone in milestones:
        milestone["_id"] = str(milestone["_id"])
    contract["milestones"] = milestones
    
    return {"contract": contract}


@router.put("/{contract_id}")
def update_contract(contract_id: str, contract_update: ContractUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        existing_contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not existing_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Only client can update contract terms
    if user["role"] == "client":
        if existing_contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="You can only update your own contracts")
    else:
        raise HTTPException(status_code=403, detail="Only clients can update contracts")
    
    update_data = {k: v for k, v in contract_update.model_dump().items() if v is not None}
    
    db.contracts.update_one(
        {"_id": ObjectId(contract_id)},
        {"$set": update_data}
    )
    
    updated_contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    updated_contract["_id"] = str(updated_contract["_id"])
    
    return {"message": "Contract updated successfully", "contract": updated_contract}


@router.put("/{contract_id}/complete")
def complete_contract(contract_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Client marks as completed
        db.contracts.update_one(
            {"_id": ObjectId(contract_id)},
            {"$set": {"status": "completed", "completed_at": datetime.now().isoformat()}}
        )
        
        # Update project status
        db.projects.update_one(
            {"_id": ObjectId(contract["project_id"])},
            {"$set": {"status": "completed"}}
        )
    else:
        raise HTTPException(status_code=403, detail="Only clients can mark contracts as completed")
    
    updated_contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    updated_contract["_id"] = str(updated_contract["_id"])
    
    return {"message": "Contract marked as completed", "contract": updated_contract}


@router.delete("/{contract_id}")
def delete_contract(contract_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        existing_contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not existing_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if existing_contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only delete your own contracts")
    
    if existing_contract["status"] != "active":
        raise HTTPException(status_code=400, detail="Can only delete active contracts")
    
    db.contracts.delete_one({"_id": ObjectId(contract_id)})
    
    return {"message": "Contract deleted successfully"}
