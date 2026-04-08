from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/payments", tags=["Payments"])


class EscrowCreate(BaseModel):
    contract_id: str
    amount: float


class WithdrawalCreate(BaseModel):
    amount: float


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


@router.post("/escrow")
def create_escrow(escrow: EscrowCreate, authorization: str = Header(None)):
    """Client funds escrow for a contract"""
    user = get_current_user(authorization)
    
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can fund escrow")
    
    # Get the contract
    try:
        contract = db.contracts.find_one({"_id": ObjectId(escrow.contract_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contract ID")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract["client_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="You can only fund escrow for your own contracts")
    
    # Create escrow transaction
    transaction_data = {
        "contract_id": escrow.contract_id,
        "client_id": str(user["_id"]),
        "freelancer_id": contract["freelancer_id"],
        "amount": escrow.amount,
        "type": "escrow_fund",
        "status": "held",  # held, released, refunded
        "created_at": datetime.now().isoformat()
    }
    
    result = db.transactions.insert_one(transaction_data)
    transaction_data["_id"] = str(result.inserted_id)
    
    return {"message": "Escrow funded successfully", "transaction": transaction_data}


@router.get("/escrow/{contract_id}")
def get_contract_escrow(contract_id: str, authorization: str = Header(None)):
    """Get escrow balance for a contract"""
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
    
    # Get escrow transactions
    escrow_transactions = list(db.transactions.find({
        "contract_id": contract_id,
        "type": {"$in": ["escrow_fund", "milestone_payment"]},
        "status": {"$in": ["held", "released"]}
    }))
    
    total_held = sum(t.get("amount", 0) for t in escrow_transactions if t.get("status") == "held")
    total_released = sum(t.get("amount", 0) for t in escrow_transactions if t.get("status") == "released")
    
    return {
        "escrow": {
            "contract_id": contract_id,
            "total_held": total_held,
            "total_released": total_released,
            "transactions": escrow_transactions
        }
    }


@router.get("/")
def get_transactions(authorization: str = Header(None), transaction_type: str = None):
    """Get user's transactions"""
    user = get_current_user(authorization)
    
    user_id = str(user["_id"])
    
    if user["role"] == "client":
        query = {"client_id": user_id}
    else:
        query = {"freelancer_id": user_id}
    
    if transaction_type:
        query["type"] = transaction_type
    
    transactions = list(db.transactions.find(query).sort("created_at", -1))
    
    for transaction in transactions:
        transaction["_id"] = str(transaction["_id"])
    
    return {"transactions": transactions}


@router.get("/escrow-balance")
def get_escrow_balance(authorization: str = Header(None)):
    """Get freelancer's total escrow balance"""
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can view escrow balance")
    
    user_id = str(user["_id"])
    
    # Get all held transactions for this freelancer
    held_transactions = list(db.transactions.find({
        "freelancer_id": user_id,
        "status": "held"
    }))
    
    total_held = sum(t.get("amount", 0) for t in held_transactions)
    
    # Get all released transactions
    released_transactions = list(db.transactions.find({
        "freelancer_id": user_id,
        "status": "released"
    }))
    
    total_released = sum(t.get("amount", 0) for t in released_transactions)
    
    # Get withdrawals
    withdrawals = list(db.transactions.find({
        "freelancer_id": user_id,
        "type": "withdrawal"
    }))
    
    total_withdrawn = sum(t.get("amount", 0) for t in withdrawals)
    
    return {
        "balance": {
            "available": total_released - total_withdrawn,
            "in_escrow": total_held,
            "total_earned": total_released,
            "total_withdrawn": total_withdrawn
        }
    }


@router.post("/withdraw")
def create_withdrawal(withdrawal: WithdrawalCreate, authorization: str = Header(None)):
    """Freelancer requests withdrawal"""
    user = get_current_user(authorization)
    
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Only freelancers can request withdrawals")
    
    user_id = str(user["_id"])
    
    # Get freelancer's available balance
    released_transactions = list(db.transactions.find({
        "freelancer_id": user_id,
        "status": "released"
    }))
    
    total_released = sum(t.get("amount", 0) for t in released_transactions)
    
    withdrawals = list(db.transactions.find({
        "freelancer_id": user_id,
        "type": "withdrawal"
    }))
    
    total_withdrawn = sum(t.get("amount", 0) for t in withdrawals)
    
    available = total_released - total_withdrawn
    
    if withdrawal.amount > available:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    if withdrawal.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    
    # Create withdrawal transaction
    transaction_data = {
        "freelancer_id": user_id,
        "amount": withdrawal.amount,
        "type": "withdrawal",
        "status": "pending",  # pending, completed, failed
        "created_at": datetime.now().isoformat()
    }
    
    result = db.transactions.insert_one(transaction_data)
    transaction_data["_id"] = str(result.inserted_id)
    
    return {"message": "Withdrawal requested successfully", "transaction": transaction_data}


@router.get("/withdrawals")
def get_withdrawals(authorization: str = Header(None)):
    """Get user's withdrawal history"""
    user = get_current_user(authorization)
    
    user_id = str(user["_id"])
    
    withdrawals = list(db.transactions.find({
        "freelancer_id": user_id,
        "type": "withdrawal"
    }).sort("created_at", -1))
    
    for withdrawal in withdrawals:
        withdrawal["_id"] = str(withdrawal["_id"])
    
    return {"withdrawals": withdrawals}


@router.get("/{transaction_id}")
def get_transaction(transaction_id: str, authorization: str = Header(None)):
    """Get transaction details"""
    user = get_current_user(authorization)
    
    try:
        transaction = db.transactions.find_one({"_id": ObjectId(transaction_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid transaction ID")
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    user_id = str(user["_id"])
    
    # Check access
    if user["role"] == "client":
        if transaction.get("client_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if transaction.get("freelancer_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    transaction["_id"] = str(transaction["_id"])
    
    return {"transaction": transaction}
