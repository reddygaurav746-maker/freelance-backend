from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.auth.jwt_handler import verify_token

router = APIRouter(prefix="/messages", tags=["Messages"])


class MessageCreate(BaseModel):
    recipient_id: str
    content: str


class MessageUpdate(BaseModel):
    read: Optional[bool] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, recipient_id: str):
        if recipient_id in self.active_connections:
            await self.active_connections[recipient_id].send_json(message)

    async def broadcast(self, message: dict, sender_id: str):
        for user_id, connection in self.active_connections.items():
            if user_id != sender_id:
                await connection.send_json(message)


manager = ConnectionManager()


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


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = {
                "type": "message",
                "content": data,
                "sender_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            # Broadcast to all connected users
            await manager.broadcast(message_data, user_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)


@router.post("/")
def send_message(message: MessageCreate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    recipient = db.users.find_one({"_id": ObjectId(message.recipient_id)})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    if str(user["_id"]) == message.recipient_id:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")
    
    message_data = {
        "sender_id": str(user["_id"]),
        "sender_name": user["name"],
        "recipient_id": message.recipient_id,
        "content": message.content,
        "read": False,
        "created_at": datetime.now().isoformat()
    }
    
    result = db.messages.insert_one(message_data)
    message_data["_id"] = str(result.inserted_id)
    
    # Try to send real-time notification
    recipient_id = message.recipient_id
    notification = {
        "type": "new_message",
        "message": message_data
    }
    import asyncio
    asyncio.create_task(manager.send_personal_message(notification, recipient_id))
    
    return {"message": "Message sent successfully", "message_data": message_data}


@router.get("/")
def get_conversations(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    user_id = str(user["_id"])
    
    # Get all unique conversations
    sent_messages = list(db.messages.find({"sender_id": user_id}).sort("created_at", -1))
    received_messages = list(db.messages.find({"recipient_id": user_id}).sort("created_at", -1))
    
    # Get unique user IDs
    user_ids = set()
    for msg in sent_messages:
        user_ids.add(msg["recipient_id"])
    for msg in received_messages:
        user_ids.add(msg["sender_id"])
    
    # Build conversations
    conversations = []
    for other_user_id in user_ids:
        other_user = db.users.find_one({"_id": ObjectId(other_user_id)})
        if other_user:
            # Get last message
            last_sent = db.messages.find_one({
                "sender_id": user_id,
                "recipient_id": other_user_id
            }, sort=[("created_at", -1)])
            
            last_received = db.messages.find_one({
                "sender_id": other_user_id,
                "recipient_id": user_id
            }, sort=[("created_at", -1)])
            
            last_message = None
            if last_sent and last_received:
                last_message = last_sent if last_sent["created_at"] > last_received["created_at"] else last_received
            elif last_sent:
                last_message = last_sent
            elif last_received:
                last_message = last_received
            
            # Count unread messages
            unread_count = db.messages.count_documents({
                "sender_id": other_user_id,
                "recipient_id": user_id,
                "read": False
            })
            
            conversations.append({
                "user_id": other_user_id,
                "user_name": other_user["name"],
                "last_message": last_message["content"] if last_message else None,
                "last_message_time": last_message["created_at"] if last_message else None,
                "unread_count": unread_count
            })
    
    # Sort by last message time
    conversations.sort(key=lambda x: x["last_message_time"] or "", reverse=True)
    
    return {"conversations": conversations}


@router.get("/conversation/{other_user_id}")
def get_conversation(other_user_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    user_id = str(user["_id"])
    
    # Get messages between the two users
    messages = list(db.messages.find({
        "$or": [
            {"sender_id": user_id, "recipient_id": other_user_id},
            {"sender_id": other_user_id, "recipient_id": user_id}
        ]
    }).sort("created_at", 1))
    
    for message in messages:
        message["_id"] = str(message["_id"])
    
    # Mark messages as read
    db.messages.update_many(
        {
            "sender_id": other_user_id,
            "recipient_id": user_id,
            "read": False
        },
        {"$set": {"read": True}}
    )
    
    return {"messages": messages}


@router.get("/unread-count")
def get_unread_count(authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    user_id = str(user["_id"])
    
    unread_count = db.messages.count_documents({
        "recipient_id": user_id,
        "read": False
    })
    
    return {"unread_count": unread_count}


@router.put("/{message_id}")
def update_message(message_id: str, message_update: MessageUpdate, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        message = db.messages.find_one({"_id": ObjectId(message_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only recipient can mark as read
    if message["recipient_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_data = {k: v for k, v in message_update.model_dump().items() if v is not None}
    
    db.messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": update_data}
    )
    
    updated_message = db.messages.find_one({"_id": ObjectId(message_id)})
    updated_message["_id"] = str(updated_message["_id"])
    
    return {"message": "Message updated successfully", "message_data": updated_message}


@router.delete("/{message_id}")
def delete_message(message_id: str, authorization: str = Header(None)):
    user = get_current_user(authorization)
    
    try:
        message = db.messages.find_one({"_id": ObjectId(message_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only sender can delete
    if message["sender_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.messages.delete_one({"_id": ObjectId(message_id)})
    
    return {"message": "Message deleted successfully"}
