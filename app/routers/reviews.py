from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token
from app.services.get_current_user import get_current_user

router = APIRouter(prefix="/reviews", tags=["Reviews"])

class ReviewCreate(BaseModel):
    contract_id: str
    rating: int
    comment: str

class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    comment: Optional[str] = None

class DisputeCreate(BaseModel):
    contract_id: str
    reason: str
    description: str

@router.post("/")
def create_review(review: ReviewCreate, authorization: str = Header(None)):
    """Create a review after contract completion"""
    user = get_current_user(authorization)
    try:
        contract = db.contracts.find_one({"_id": ObjectId(review.contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only review completed contracts")

    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")

        existing_review = db.reviews.find_one({
            "contract_id": review.contract_id,
            "client_id": str(user["_id"])
        })
        
        if existing_review:
            raise HTTPException(status_code=400, detail="You have already reviewed this contract")
        review_data = {
            "contract_id": review.contract_id,
            "project_id": contract["project_id"],
            "client_id": str(user["_id"]),
            "client_name": user["name"],
            "freelancer_id": contract["freelancer_id"],
            "freelancer_name": contract["freelancer_name"],
            "rating": review.rating,
            "comment": review.comment,
            "reviewer_type": "client",
            "created_at": datetime.now().isoformat()
        }
    
    elif user["role"] == "freelancer":
        if contract["freelancer_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")

        existing_review = db.reviews.find_one({
            "contract_id": review.contract_id,
            "freelancer_id": str(user["_id"])
        })
        
        if existing_review:
            raise HTTPException(status_code=400, detail="You have already reviewed this contract")
        
        review_data = {
            "contract_id": review.contract_id,
            "project_id": contract["project_id"],
            "client_id": contract["client_id"],
            "client_name": contract["client_name"],
            "freelancer_id": str(user["_id"]),
            "freelancer_name": user["name"],
            "rating": review.rating,
            "comment": review.comment,
            "reviewer_type": "freelancer",
            "created_at": datetime.now().isoformat()
        }
    
    else:
        raise HTTPException(status_code=403, detail="Invalid user role")
    
    if review.rating < 1 or review.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    result = db.reviews.insert_one(review_data)
    review_data["_id"] = str(result.inserted_id)
    
    return {"message": "Review submitted successfully", "review": review_data}

@router.get("/")
def get_reviews(authorization: str = Header(None), contract_id: str = None):
    """Get reviews"""
    user = get_current_user(authorization)
    query = {}
    if contract_id:
        query["contract_id"] = contract_id
    reviews = list(db.reviews.find(query).sort("created_at", -1))
    for review in reviews:
        review["_id"] = str(review["_id"])
    return {"reviews": reviews}

@router.get("/my-reviews")
def get_my_reviews(authorization: str = Header(None)):
    """Get current user's reviews"""
    user = get_current_user(authorization) 
    user_id = str(user["_id"])
    if user["role"] == "client":
        reviews = list(db.reviews.find({"client_id": user_id}).sort("created_at", -1))
    else:
        reviews = list(db.reviews.find({"freelancer_id": user_id}).sort("created_at", -1))
    for review in reviews:
        review["_id"] = str(review["_id"])
    return {"reviews": reviews}

@router.get("/freelancer/{freelancer_id}")
def get_freelancer_reviews(freelancer_id: str, authorization: str = Header(None)):
    reviews = list(db.reviews.find({"freelancer_id": freelancer_id}).sort("created_at", -1))
    for review in reviews:
        review["_id"] = str(review["_id"])
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews)
    return {
        "reviews": reviews,
        "average_rating": avg_rating,
        "total_reviews": len(reviews)
    }


@router.get("/client/{client_id}")
def get_client_reviews(client_id: str, authorization: str = Header(None)):
    """Get reviews for a client"""
    reviews = list(db.reviews.find({"client_id": client_id}).sort("created_at", -1))
    
    for review in reviews:
        review["_id"] = str(review["_id"])
    
    # Calculate average rating
    avg_rating = 0
    if reviews:
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews)
    
    return {
        "reviews": reviews,
        "average_rating": avg_rating,
        "total_reviews": len(reviews)
    }


@router.get("/{review_id}")
def get_review(review_id: str, authorization: str = Header(None)):
    """Get single review"""
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review["_id"] = str(review["_id"])
    
    return {"review": review}


@router.put("/{review_id}")
def update_review(review_id: str, review_update: ReviewUpdate, authorization: str = Header(None)):
    """Update a review (only within 30 days)"""
    user = get_current_user(authorization)
    
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Check ownership
    if user["role"] == "client":
        if review.get("client_id") != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if review.get("freelancer_id") != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if within 30 days
    created_at = datetime.fromisoformat(review["created_at"])
    days_since = (datetime.now() - created_at).days
    
    if days_since > 30:
        raise HTTPException(status_code=400, detail="Can only update reviews within 30 days")
    
    update_data = {k: v for k, v in review_update.model_dump().items() if v is not None}
    
    if "rating" in update_data:
        if update_data["rating"] < 1 or update_data["rating"] > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    if update_data:
        db.reviews.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": update_data}
        )
    
    updated_review = db.reviews.find_one({"_id": ObjectId(review_id)})
    updated_review["_id"] = str(updated_review["_id"])
    
    return {"message": "Review updated successfully", "review": updated_review}


@router.delete("/{review_id}")
def delete_review(review_id: str, authorization: str = Header(None)):
    """Delete a review"""
    user = get_current_user(authorization)
    
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Only admin can delete reviews (not implemented)
    raise HTTPException(status_code=403, detail="Cannot delete reviews")


# Dispute Resolution
@router.post("/dispute")
def raise_dispute(dispute: DisputeCreate, authorization: str = Header(None)):
    """Raise a dispute for a contract"""
    user = get_current_user(authorization)
    
    # Get the contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(dispute.contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check access
    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    elif user["role"] == "freelancer":
        if contract["freelancer_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if dispute already exists
    existing_dispute = db.disputes.find_one({
        "contract_id": dispute.contract_id,
        "status": {"$ne": "resolved"}
    })
    
    if existing_dispute:
        raise HTTPException(status_code=400, detail="Dispute already exists for this contract")
    
    dispute_data = {
        "contract_id": dispute.contract_id,
        "project_id": contract["project_id"],
        "raised_by": str(user["_id"]),
        "raised_by_name": user["name"],
        "raised_by_role": user["role"],
        "reason": dispute.reason,
        "description": dispute.description,
        "status": "open",  # open, under_review, resolved
        "resolution": None,
        "created_at": datetime.now().isoformat()
    }
    
    result = db.disputes.insert_one(dispute_data)
    dispute_data["_id"] = str(result.inserted_id)
    
    return {"message": "Dispute raised successfully", "dispute": dispute_data}


@router.get("/dispute/{dispute_id}")
def get_dispute(dispute_id: str, authorization: str = Header(None)):
    """Get dispute details"""
    user = get_current_user(authorization)
    
    try:
        dispute = db.disputes.find_one({"_id": ObjectId(dispute_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid dispute ID")
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    # Check access
    try:
        contract = db.contracts.find_one({"_id": ObjectId(dispute["contract_id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    elif user["role"] == "freelancer":
        if contract["freelancer_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    dispute["_id"] = str(dispute["_id"])
    
    return {"dispute": dispute}


@router.get("/dispute/contract/{contract_id}")
def get_contract_dispute(contract_id: str, authorization: str = Header(None)):
    """Get dispute for a contract"""
    user = get_current_user(authorization)
    
    try:
        contract = db.contracts.find_one({"_id": ObjectId(contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check access
    if user["role"] == "client":
        if contract["client_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    elif user["role"] == "freelancer":
        if contract["freelancer_id"] != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    dispute = db.disputes.find_one({
        "contract_id": contract_id,
        "status": {"$ne": "resolved"}
    })
    
    if not dispute:
        return {"dispute": None}
    
    dispute["_id"] = str(dispute["_id"])
    
    return {"dispute": dispute}


@router.put("/dispute/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, authorization: str = Header(None)):
    """Resolve a dispute (admin only - simplified)"""
    user = get_current_user(authorization)
    try:
        dispute = db.disputes.find_one({"_id": ObjectId(dispute_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid dispute ID")
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    if dispute["status"] == "resolved":
        raise HTTPException(status_code=400, detail="Dispute already resolved")
    
    # Update dispute status
    db.disputes.update_one(
        {"_id": ObjectId(dispute_id)},
        {"$set": {"status": "resolved", "resolved_at": datetime.now().isoformat()}}
    )
    
    updated_dispute = db.disputes.find_one({"_id": ObjectId(dispute_id)})
    updated_dispute["_id"] = str(updated_dispute["_id"])
    
    return {"message": "Dispute resolved successfully", "dispute": updated_dispute}
