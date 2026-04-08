from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/freelancers", tags=["Freelancers"])


class FreelancerProfileUpdate(BaseModel):
    skills: Optional[List[str]] = None
    hourly_rate: Optional[float] = None
    bio: Optional[str] = None
    portfolio: Optional[List[str]] = None
    availability: Optional[str] = None
    certifications: Optional[List[str]] = None
    title: Optional[str] = None


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


@router.get("/")
def get_freelancers(
    authorization: str = Header(None),
    skills: str = None,
    min_rate: float = None,
    max_rate: float = None
):
    query = {"role": "freelancer"}
    
    if skills:
        query["skills"] = {"$in": skills.split(",")}
    
    freelancers = list(db.users.find(query))
    
    # Filter by hourly rate if specified
    if min_rate is not None or max_rate is not None:
        filtered = []
        for f in freelancers:
            profile = db.freelancers.find_one({"user_id": str(f["_id"])})
            if profile:
                rate = profile.get("hourly_rate", 0)
                if min_rate is not None and rate < min_rate:
                    continue
                if max_rate is not None and rate > max_rate:
                    continue
                f["profile"] = profile
            filtered.append(f)
        freelancers = filtered
    
    for freelancer in freelancers:
        freelancer["_id"] = str(freelancer["_id"])
        # Get freelancer profile
        profile = db.freelancers.find_one({"user_id": str(freelancer["_id"])})
        if profile:
            freelancer["profile"] = {
                "skills": profile.get("skills", []),
                "hourly_rate": profile.get("hourly_rate"),
                "bio": profile.get("bio"),
                "availability": profile.get("availability"),
                "title": profile.get("title")
            }
    
    return {"freelancers": freelancers}


@router.get("/search")
def search_freelancers(
    authorization: str = Header(None),
    q: str = None,
    skills: str = None,
    min_rate: float = None,
    max_rate: float = None,
    availability: str = None
):
    query = {"role": "freelancer"}
    
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}}
        ]
    
    freelancers = list(db.users.find(query))
    
    # Filter based on skills, rate, availability
    filtered = []
    for f in freelancers:
        profile = db.freelancers.find_one({"user_id": str(f["_id"])})
        if profile:
            if skills:
                freelancer_skills = profile.get("skills", [])
                if not any(s in freelancer_skills for s in skills.split(",")):
                    continue
            
            rate = profile.get("hourly_rate")
            if min_rate is not None and (rate is None or rate < min_rate):
                continue
            if max_rate is not None and (rate is None or rate > max_rate):
                continue
            
            if availability and profile.get("availability") != availability:
                continue
            
            f["profile"] = profile
        filtered.append(f)
    
    for freelancer in filtered:
        freelancer["_id"] = str(freelancer["_id"])
    
    return {"freelancers": filtered}


@router.get("/me")
def get_my_profile(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can view this profile")
    
    user["_id"] = str(user["_id"])
    
    # Get freelancer profile
    profile = db.freelancers.find_one({"user_id": str(user["_id"])})
    if profile:
        profile["_id"] = str(profile["_id"])
        user["profile"] = profile
    
    return {"user": user}


@router.get("/{freelancer_id}")
def get_freelancer(freelancer_id: str, authorization: str = Header(None)):
    try:
        freelancer = db.users.find_one({"_id": ObjectId(freelancer_id), "role": "freelancer"})
    except:
        raise HTTPException(status_code=400, detail="Invalid freelancer ID")
    
    if not freelancer:
        raise HTTPException(status_code=404, detail="Freelancer not found")
    
    freelancer["_id"] = str(freelancer["_id"])
    
    # Get freelancer profile
    profile = db.freelancers.find_one({"user_id": freelancer_id})
    if profile:
        profile["_id"] = str(profile["_id"])
        freelancer["profile"] = profile
    
    # Get freelancer reviews
    reviews = list(db.reviews.find({"freelancer_id": freelancer_id}))
    for review in reviews:
        review["_id"] = str(review["_id"])
    freelancer["reviews"] = reviews
    
    # Calculate average rating
    if reviews:
        total_rating = sum(r.get("rating", 0) for r in reviews)
        freelancer["average_rating"] = total_rating / len(reviews)
    
    return {"freelancer": freelancer}


@router.put("/me")
def update_my_profile(profile_update: FreelancerProfileUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can update profiles")
    
    # Check if profile exists
    existing_profile = db.freelancers.find_one({"user_id": str(user["_id"])})
    
    profile_data = {k: v for k, v in profile_update.model_dump().items() if v is not None}
    profile_data["user_id"] = str(user["_id"])
    profile_data["updated_at"] = datetime.now().isoformat()
    
    if existing_profile:
        db.freelancers.update_one(
            {"user_id": str(user["_id"])},
            {"$set": profile_data}
        )
    else:
        profile_data["created_at"] = datetime.now().isoformat()
        db.freelancers.insert_one(profile_data)
    
    updated_profile = db.freelancers.find_one({"user_id": str(user["_id"])})
    updated_profile["_id"] = str(updated_profile["_id"])
    
    return {"message": "Profile updated successfully", "profile": updated_profile}


@router.get("/me/stats")
def get_my_stats(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can view stats")
    
    user_id = str(user["_id"])
    
    # Count proposals
    total_proposals = db.proposals.count_documents({"freelancer_id": user_id})
    
    # Count accepted proposals
    accepted_proposals = db.proposals.count_documents({
        "freelancer_id": user_id,
        "status": "accepted"
    })
    
    # Count active contracts
    active_contracts = db.contracts.count_documents({
        "freelancer_id": user_id,
        "status": "active"
    })
    
    # Count completed contracts
    completed_contracts = db.contracts.count_documents({
        "freelancer_id": user_id,
        "status": "completed"
    })
    
    # Calculate total earnings
    contracts = list(db.contracts.find({"freelancer_id": user_id, "status": "completed"}))
    total_earnings = sum(c.get("budget", 0) for c in contracts)
    
    # Get reviews
    reviews = list(db.reviews.find({"freelancer_id": user_id}))
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews)
    
    return {
        "stats": {
            "total_proposals": total_proposals,
            "accepted_proposals": accepted_proposals,
            "active_contracts": active_contracts,
            "completed_contracts": completed_contracts,
            "total_earnings": total_earnings,
            "average_rating": avg_rating,
            "total_reviews": len(reviews)
        }
    }
