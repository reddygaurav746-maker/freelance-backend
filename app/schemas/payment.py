from pydantic import BaseModel

class EscrowCreate(BaseModel):
    contract_id: str
    amount: float

class WithdrawalCreate(BaseModel):
    amount: float