from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/milestones", tags=["Milestones"])


class MilestoneCreate(BaseModel):
    contract_id: str
    title: str
    description: str
    amount: float
    due_date: str


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


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
def create_milestone(milestone: MilestoneCreate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can create milestones")
    
    # Get the contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone.contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only create milestones for your own contracts")
    
    if contract["status"] != "active":
        raise HTTPException(status_code=400, detail="Can only add milestones to active contracts")
    
    milestone_data = {
        "contract_id": milestone.contract_id,
        "title": milestone.title,
        "description": milestone.description,
        "amount": milestone.amount,
        "due_date": milestone.due_date,
        "status": "pending",  # pending, in_progress, submitted, approved, paid
        "created_at": datetime.now().isoformat()
    }
    
    result = db.milestones.insert_one(milestone_data)
    milestone_data["_id"] = str(result.inserted_id)
    
    return {"message": "Milestone created successfully", "milestone": milestone_data}


@router.get("/")
def get_milestones(authorization: str = Header(None), contract_id: str = None):
    user = get_current_user(authorization)
    
    query = {}
    
    if contract_id:
        query["contract_id"] = contract_id
    else:
        # Get milestones for user's contracts
        if user["role"] == "client":
            contracts = list(db.contracts.find({"client_id": str(user["_id"])}))
            contract_ids = [str(c["_id"]) for c in contracts]
            query["contract_id"] = {"$in": contract_ids}
        elif user["role"] == "freelancer":
            contracts = list(db.contracts.find({"freelancer_id": str(user["_id"])}))
            contract_ids = [str(c["_id"]) for c in contracts]
            query["contract_id"] = {"$in": contract_ids}
    
    milestones = list(db.milestones.find(query).sort("created_at", -1))
    
    for milestone in milestones:
        milestone["_id"] = str(milestone["_id"])
    
    return {"milestones": milestones}


@router.get("/{milestone_id}")
def get_milestone(milestone_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract to check access
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if user["role"] == "client" and contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if user["role"] == "freelancer" and contract["freelancer_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    milestone["_id"] = str(milestone["_id"])
    milestone["contract"] = {
        "title": contract.get("project_title"),
        "budget": contract.get("budget")
    }
    
    return {"milestone": milestone}


@router.put("/{milestone_id}")
def update_milestone(milestone_id: str, milestone_update: MilestoneUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    update_data = {k: v for k, v in milestone_update.model_dump().items() if v is not None}
    
    # Only client can update milestone details (not status)
    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Remove status from update_data if client is updating (status changes are separate endpoints)
        if "status" in update_data:
            del update_data["status"]
    else:
        raise HTTPException(status_code=403, detail="Only clients can update milestones")
    
    if update_data:
        db.milestones.update_one(
            {"_id": ObjectId(milestone_id)},
            {"$set": update_data}
        )
    
    updated_milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    updated_milestone["_id"] = str(updated_milestone["_id"])
    
    return {"message": "Milestone updated successfully", "milestone": updated_milestone}


@router.put("/{milestone_id}/submit")
def submit_milestone(milestone_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can submit milestones")
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if contract["freelancer_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if milestone["status"] != "pending" and milestone["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Can only submit pending or in_progress milestones")
    
    # Update milestone status
    db.milestones.update_one(
        {"_id": ObjectId(milestone_id)},
        {"$set": {"status": "submitted", "submitted_at": datetime.now().isoformat()}}
    )
    
    updated_milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    updated_milestone["_id"] = str(updated_milestone["_id"])
    
    return {"message": "Milestone submitted for approval", "milestone": updated_milestone}


@router.put("/{milestone_id}/approve")
def approve_milestone(milestone_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can approve milestones")
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if milestone["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Can only approve submitted milestones")
    
    # Update milestone status to approved
    db.milestones.update_one(
        {"_id": ObjectId(milestone_id)},
        {"$set": {"status": "approved", "approved_at": datetime.now().isoformat()}}
    )
    
    updated_milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    updated_milestone["_id"] = str(updated_milestone["_id"])
    
    return {"message": "Milestone approved", "milestone": updated_milestone}


@router.put("/{milestone_id}/release-payment")
def release_payment(milestone_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can release payment")
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if milestone["status"] != "approved":
        raise HTTPException(status_code=400, detail="Can only release payment for approved milestones")
    
    # Create transaction for the payment
    transaction_data = {
        "contract_id": milestone["contract_id"],
        "milestone_id": milestone_id,
        "client_id": contract["client_id"],
        "freelancer_id": contract["freelancer_id"],
        "amount": milestone["amount"],
        "type": "milestone_payment",
        "status": "completed",
        "created_at": datetime.now().isoformat()
    }
    
    db.transactions.insert_one(transaction_data)
    
    # Update milestone status to paid
    db.milestones.update_one(
        {"_id": ObjectId(milestone_id)},
        {"$set": {"status": "paid", "paid_at": datetime.now().isoformat()}}
    )
    
    updated_milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    updated_milestone["_id"] = str(updated_milestone["_id"])
    
    return {"message": "Payment released successfully", "milestone": updated_milestone}


@router.delete("/{milestone_id}")
def delete_milestone(milestone_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can delete milestones")
    
    try:
        milestone = db.milestones.find_one({"_id": ObjectId(milestone_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid milestone ID")
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Get contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(milestone["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if milestone["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only delete pending milestones")
    
    db.milestones.delete_one({"_id": ObjectId(milestone_id)})
    
    return {"message": "Milestone deleted successfully"}
