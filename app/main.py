from fastapi import FastAPI
from app.database import db, client
from app.routers import auth, projects, proposals, contracts, freelancers, clients, messages, milestones, payments, reviews
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

app = FastAPI(title="Freelancer Marketplace API", version="1.0.0")

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(proposals.router)
app.include_router(contracts.router)
app.include_router(freelancers.router)
app.include_router(clients.router)
app.include_router(messages.router)
app.include_router(milestones.router)
app.include_router(payments.router)
app.include_router(reviews.router)

@app.get("/")
def home():
    return {"message": "Freelancer Marketplace API is running", "status": "success"}

@app.get("/test-db")
async def test_db():
    await client.admin.command("ping")
    return {"message": "MongoDB connected successfully"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Create indexes for better performance
@app.on_event("startup")
async def startup_event():
    # Create indexes on users collection
    db.users.create_index("email", unique=True)
    
    # Create indexes on projects collection
    db.projects.create_index("client_id")
    db.projects.create_index("status")
    db.projects.create_index("category")
    db.projects.create_index("created_at")
    
    # Create indexes on proposals collection
    db.proposals.create_index("project_id")
    db.proposals.create_index("freelancer_id")
    db.proposals.create_index("status")
    
    # Create indexes on contracts collection
    db.contracts.create_index("client_id")
    db.contracts.create_index("freelancer_id")
    db.contracts.create_index("status")
    
    # Create indexes on milestones collection
    db.milestones.create_index("contract_id")
    db.milestones.create_index("status")
    
    # Create indexes on transactions collection
    db.transactions.create_index("contract_id")
    db.transactions.create_index("client_id")
    db.transactions.create_index("freelancer_id")
    db.transactions.create_index("type")
    
    # Create indexes on messages collection
    db.messages.create_index("sender_id")
    db.messages.create_index("recipient_id")
    
    # Create indexes on reviews collection
    db.reviews.create_index("contract_id")
    db.reviews.create_index("freelancer_id")
    db.reviews.create_index("client_id")
    
    print("Database indexes created successfully")

