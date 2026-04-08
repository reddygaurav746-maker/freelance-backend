from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.services.get_current_user import get_current_user

router = APIRouter(prefix="/clients", tags=["Clients"])


class ClientProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    verification_status: Optional[str] = None

@router.get("/")
def get_clients(authorization: str = Header(None)):
    # Only accessible by admins (not implemented yet)
    clients = list(db.users.find({"role": "client"}))
    
    for client in clients:
        client["_id"] = str(client["_id"])
        # Get client profile
        profile = db.clients.find_one({"user_id": str(client["_id"])})
        if profile:
            client["profile"] = {
                "company_name": profile.get("company_name"),
                "company_website": profile.get("company_website"),
                "industry": profile.get("industry"),
                "verification_status": profile.get("verification_status")
            }
    
    return {"clients": clients}


@router.get("/me")
def get_my_profile(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can view this profile")
    
    user["_id"] = str(user["_id"])
    
    # Get client profile
    profile = db.clients.find_one({"user_id": str(user["_id"])})
    if profile:
        profile["_id"] = str(profile["_id"])
        user["profile"] = profile
    
    return {"user": user}


@router.get("/{client_id}")
def get_client(client_id: str, authorization: str = Header(None)):
    try:
        client = db.users.find_one({"_id": ObjectId(client_id), "role": "client"})
    except:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client["_id"] = str(client["_id"])
    
    # Get client profile
    profile = db.clients.find_one({"user_id": client_id})
    if profile:
        profile["_id"] = str(profile["_id"])
        client["profile"] = profile
    
    return {"client": client}


@router.put("/me")
def update_my_profile(profile_update: ClientProfileUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can update profiles")
    
    # Check if profile exists
    existing_profile = db.clients.find_one({"user_id": str(user["_id"])})
    
    profile_data = {k: v for k, v in profile_update.model_dump().items() if v is not None}
    profile_data["user_id"] = str(user["_id"])
    profile_data["updated_at"] = datetime.now().isoformat()
    
    if existing_profile:
        db.clients.update_one(
            {"user_id": str(user["_id"])},
            {"$set": profile_data}
        )
    else:
        profile_data["created_at"] = datetime.now().isoformat()
        db.clients.insert_one(profile_data)
    
    updated_profile = db.clients.find_one({"user_id": str(user["_id"])})
    updated_profile["_id"] = str(updated_profile["_id"])
    
    return {"message": "Profile updated successfully", "profile": updated_profile}


@router.get("/me/stats")
def get_my_stats(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can view stats")
    
    user_id = str(user["_id"])
    total_projects = db.projects.count_documents({"client_id": user_id})
    
    # Count open projects
    open_projects = db.projects.count_documents({
        "client_id": user_id,
        "status": "open"
    })
    
    # Count in-progress projects
    in_progress_projects = db.projects.count_documents({
        "client_id": user_id,
        "status": "in_progress"
    })
    
    # Count completed projects
    completed_projects = db.projects.count_documents({
        "client_id": user_id,
        "status": "completed"
    })
    
    # Count active contracts
    active_contracts = db.contracts.count_documents({
        "client_id": user_id,
        "status": "active"
    })
    
    # Calculate total spent
    contracts = list(db.contracts.find({"client_id": user_id, "status": "completed"}))
    total_spent = sum(c.get("budget", 0) for c in contracts)
    
    # Get reviews received
    reviews = list(db.reviews.find({"client_id": user_id}))
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews)
    
    return {
        "stats": {
            "total_projects": total_projects,
            "open_projects": open_projects,
            "in_progress_projects": in_progress_projects,
            "completed_projects": completed_projects,
            "active_contracts": active_contracts,
            "total_spent": total_spent,
            "average_rating": avg_rating,
            "total_reviews": len(reviews)
        }
    }
