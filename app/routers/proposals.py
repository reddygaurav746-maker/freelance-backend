from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/proposals", tags=["Proposals"])

class ProposalCreate(BaseModel):
    project_id: str
    cover_letter: str
    proposed_budget: float
    timeline: str

class ProposalUpdate(BaseModel):
    cover_letter: Optional[str] = None
    proposed_budget: Optional[float] = None
    timeline: Optional[str] = None
    status: Optional[str] = None

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
    
    return user

@router.post("/")
def create_proposal(proposal: ProposalCreate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can submit proposals")
    
    # Check if project exists
    try:
        project = db.projects.find_one({"_id": ObjectId(proposal.project_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.get("status") != "open":
        raise HTTPException(status_code=400, detail="Project is not open for proposals")
    
    # Check if already submitted proposal
    existing_proposal = db.proposals.find_one({
        "project_id": proposal.project_id,
        "freelancer_id": str(user["_id"])
    })
    
    if existing_proposal:
        raise HTTPException(status_code=400, detail="You have already submitted a proposal for this project")
    
    proposal_data = {
        "project_id": proposal.project_id,
        "freelancer_id": str(user["_id"]),
        "freelancer_name": user["name"],
        "freelancer_email": user["email"],
        "cover_letter": proposal.cover_letter,
        "proposed_budget": proposal.proposed_budget,
        "timeline": proposal.timeline,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    result = db.proposals.insert_one(proposal_data)
    proposal_data["_id"] = str(result.inserted_id)
    
    # Update project proposals count
    db.projects.update_one(
        {"_id": ObjectId(proposal.project_id)},
        {"$inc": {"proposals_count": 1}}
    )
    
    return {"message": "Proposal submitted successfully", "proposal": proposal_data}

@router.get("/")
def get_proposals(
    authorization: str = Header(None),
    project_id: str = None,
    status: str = None
):
    user = get_current_user(authorization)
    
    query = {}
    
    if user["role"] == "client":
        # Get proposals for client's projects
        projects = list(db.projects.find({"client_id": str(user["_id"])}))
        project_ids = [str(p["_id"]) for p in projects]
        query["project_id"] = {"$in": project_ids}
    elif user["role"] == "freelancer":
        query["freelancer_id"] = str(user["_id"])
    
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    
    proposals = list(db.proposals.find(query).sort("created_at", -1))
    
    for proposal in proposals:
        proposal["_id"] = str(proposal["_id"])
        # Get project details
        try:
            project = db.projects.find_one({"_id": ObjectId(proposal["project_id"])})
            if project:
                proposal["project"] = {
                    "title": project.get("title"),
                    "budget": project.get("budget"),
                    "client_name": project.get("client_name")
                }
        except:
            pass
    
    return {"proposals": proposals}

@router.get("/my-proposals")
def get_my_proposals(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can view their proposals")
    
    proposals = list(db.proposals.find({"freelancer_id": str(user["_id"])}).sort("created_at", -1))
    
    for proposal in proposals:
        proposal["_id"] = str(proposal["_id"])
        # Get project details
        try:
            project = db.projects.find_one({"_id": ObjectId(proposal["project_id"])})
            if project:
                proposal["project"] = {
                    "title": project.get("title"),
                    "budget": project.get("budget"),
                    "status": project.get("status")
                }
        except:
            pass
    
    return {"proposals": proposals}

@router.get("/{proposal_id}")
def get_proposal(proposal_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        proposal = db.proposals.find_one({"_id": ObjectId(proposal_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid proposal ID")
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Check if user has access
    if user["role"] == "freelancer" and proposal["freelancer_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if user["role"] == "client":
        project = db.projects.find_one({"_id": ObjectId(proposal["project_id"])})
        if not project or project["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    proposal["_id"] = str(proposal["_id"])
    return {"proposal": proposal}

@router.put("/{proposal_id}")
def update_proposal(proposal_id: str, proposal_update: ProposalUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        existing_proposal = db.proposals.find_one({"_id": ObjectId(proposal_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid proposal ID")
    
    if not existing_proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Freelancer can update their own proposal if still pending
    if user["role"] == "freelancer":
        if existing_proposal["freelancer_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="You can only update your own proposals")
        if existing_proposal["status"] != "pending":
            raise HTTPException(status_code=400, detail="Can only update pending proposals")
    
    # Client can accept/reject proposals
    if user["role"] == "client":
        project = db.projects.find_one({"_id": ObjectId(existing_proposal["project_id"])})
        if not project or project["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if proposal_update.status in ["accepted", "rejected"]:
            # Update proposal status
            db.proposals.update_one(
                {"_id": ObjectId(proposal_id)},
                {"$set": {"status": proposal_update.status}}
            )
            
            # If accepted, reject all other proposals for this project
            if proposal_update.status == "accepted":
                db.proposals.update_many(
                    {
                        "project_id": existing_proposal["project_id"],
                        "_id": {"$ne": ObjectId(proposal_id)}
                    },
                    {"$set": {"status": "rejected"}}
                )
                # Update project status
                db.projects.update_one(
                    {"_id": ObjectId(existing_proposal["project_id"])},
                    {"$set": {"status": "in_progress"}}
                )
            
            updated_proposal = db.proposals.find_one({"_id": ObjectId(proposal_id)})
            updated_proposal["_id"] = str(updated_proposal["_id"])
            return {"message": f"Proposal {proposal_update.status}", "proposal": updated_proposal}
    
    # Regular update for freelancers
    update_data = {k: v for k, v in proposal_update.model_dump().items() if v is not None}
    
    db.proposals.update_one(
        {"_id": ObjectId(proposal_id)},
        {"$set": update_data}
    )
    
    updated_proposal = db.proposals.find_one({"_id": ObjectId(proposal_id)})
    updated_proposal["_id"] = str(updated_proposal["_id"])
    
    return {"message": "Proposal updated successfully", "proposal": updated_proposal}

@router.delete("/{proposal_id}")
def delete_proposal(proposal_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        existing_proposal = db.proposals.find_one({"_id": ObjectId(proposal_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid proposal ID")
    
    if not existing_proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if existing_proposal["freelancer_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only delete your own proposals")
    
    if existing_proposal["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only delete pending proposals")
    
    db.proposals.delete_one({"_id": ObjectId(proposal_id)})
    
    # Update project proposals count
    db.projects.update_one(
        {"_id": ObjectId(existing_proposal["project_id"])},
        {"$inc": {"proposals_count": -1}}
    )
    
    return {"message": "Proposal deleted successfully"}