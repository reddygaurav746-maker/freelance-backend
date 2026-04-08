"""
Script to add 100 sample jobs to the database
"""
import asyncio
from datetime import datetime, timedelta
import random
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["freelanc"]
collections = db["prects"]
# Sample data for generating realistic jobs
CATEGORIES = [
    "Web Development", "Mobile App Development", "UI/UX Design", 
    "Graphic Design", "Content Writing", "Digital Marketing",
    "Data Science", "Machine Learning", "DevOps", "Blockchain",
    "Video Editing", "Logo Design", "SEO", "Virtual Assistant",
    "Customer Service"
]

SKILLS = {
    "Web Development": ["React", "Node.js", "Python", "Django", "Flask", "Vue.js", "Angular", "PHP", "Laravel", "WordPress"],
    "Mobile App Development": ["React Native", "Flutter", "Swift", "Kotlin", "iOS", "Android", "Xamarin"],
    "UI/UX Design": ["Figma", "Adobe XD", "Sketch", "UI Design", "UX Research", "Prototyping", "Wireframing"],
    "Graphic Design": ["Photoshop", "Illustrator", "Canva", "Logo Design", "Branding", "Print Design"],
    "Content Writing": ["Copywriting", "SEO Writing", "Technical Writing", "Blog Writing", "Creative Writing"],
    "Digital Marketing": ["Social Media", "Google Ads", "Facebook Ads", "Email Marketing", "Analytics"],
    "Data Science": ["Python", "R", "SQL", "Tableau", "Pandas", "NumPy", "Data Analysis"],
    "Machine Learning": ["Python", "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Deep Learning"],
    "DevOps": ["Docker", "Kubernetes", "AWS", "GCP", "Jenkins", "CI/CD", "Terraform"],
    "Blockchain": ["Solidity", "Web3", "Ethereum", "Smart Contracts", "NFT", "DeFi"],
    "Video Editing": ["Adobe Premiere", "Final Cut Pro", "DaVinci Resolve", "After Effects"],
    "Logo Design": ["Adobe Illustrator", "Branding", "Logo Design", "Typography"],
    "SEO": ["On-page SEO", "Off-page SEO", "Keyword Research", "Link Building", "Technical SEO"],
    "Virtual Assistant": ["Administrative", "Data Entry", "Calendar Management", "Email Management"],
    "Customer Service": ["Chat Support", "Email Support", "Phone Support", "Zendesk"]
}

JOB_TITLES = {
    "Web Development": [
        "Full Stack Developer Needed", "React Developer for E-commerce Site",
        "WordPress Developer for Blog", "Need Node.js Backend Developer",
        "Django Web Application Developer", "Frontend React Developer",
        "PHP/Laravel Developer Required", "Vue.js Developer for Dashboard",
        "Angular Developer for Enterprise App", "MERN Stack Developer"
    ],
    "Mobile App Development": [
        "React Native Developer for MVP", "Flutter App Development",
        "iOS Developer for Shopping App", "Android Developer for FinTech App",
        "Mobile App UI/UX Implementation", "Cross-platform App Developer",
        "React Native for Social App", "Swift iOS Developer Needed",
        "Kotlin Android Developer", "Mobile App Security Expert"
    ],
    "UI/UX Design": [
        "UI Designer for Mobile App", "UX Research and Design",
        "Figma Design for Web App", "Redesign Landing Page",
        "Design System Creation", "Prototyping for Startup",
        "User Flow and Wireframe Design", "Dashboard UI Design",
        "Mobile App Interface Design", "Website UI/UX Overhaul"
    ],
    "Graphic Design": [
        "Logo Designer for Startup", "Brand Identity Designer",
        "Social Media Graphics", "Flyer and Poster Design",
        "Business Card Design", "Illustration for Children Book",
        "Icon Set Design", "Banner Design for Website",
        "Packaging Design", "T-shirt Graphic Design"
    ],
    "Content Writing": [
        "Blog Writer for Tech Site", "SEO Content Writer",
        "Technical Writer for Docs", "Copywriter for Landing Page",
        "Content Strategy Writer", "Product Description Writer",
        "Case Study Writer", "White Paper Writer",
        "Social Media Content Creator", "Script Writer for Videos"
    ],
    "Digital Marketing": [
        "Social Media Manager", "Google Ads Specialist",
        "Facebook Ads Manager", "Email Marketing Campaign",
        "Marketing Analytics Expert", "SEO Specialist",
        "Content Marketing Strategy", "Influencer Marketing",
        "PPC Campaign Manager", "Growth Marketing Expert"
    ],
    "Data Science": [
        "Data Analyst for Business Intelligence", "Python Data Analysis",
        "Pandas Expert for Data Cleaning", "SQL Database Expert",
        "Tableau Dashboard Creator", "Statistical Analysis",
        "Data Visualization Expert", "Business Analytics",
        "Predictive Modeling", "Data Pipeline Developer"
    ],
    "Machine Learning": [
        "ML Model Development", "Image Recognition with TensorFlow",
        "NLP Project Development", "Recommendation System",
        "Chatbot Development with AI", "Object Detection Model",
        "Time Series Forecasting", "MLOps Implementation",
        "AI for Healthcare Project", "Deep Learning Expert"
    ],
    "DevOps": [
        "Docker Container Setup", "Kubernetes Cluster Management",
        "AWS Infrastructure Setup", "CI/CD Pipeline Implementation",
        "Terraform Configuration", "Jenkins Pipeline Creation",
        "DevOps for Startup", "Cloud Architecture Design",
        "Server Migration", "Monitoring and Logging Setup"
    ],
    "Blockchain": [
        "Smart Contract Developer", "Solidity Developer for DeFi",
        "NFT Marketplace Development", "Web3 Integration",
        "Ethereum DApp Development", "Crypto Trading Bot",
        "Blockchain Security Audit", "Token Development",
        "DAO Development", "Metaverse Project Development"
    ],
    "Video Editing": [
        "YouTube Video Editor", "Promo Video Editing",
        "Wedding Video Editor", "Motion Graphics Designer",
        "Short Form Video Editor", "Documentary Editor",
        "Commercial Video Editor", "Vlog Editor Needed",
        "Music Video Editor", "Explainer Video Editor"
    ],
    "Logo Design": [
        "Minimalist Logo Design", "Tech Company Logo",
        "Restaurant Logo Design", "Fashion Brand Logo",
        "Startup Logo Creation", "Modern Logo Redesign",
        "Wordmark Logo Design", "Mascot Logo Design",
        "Eco-friendly Brand Logo", "Luxury Brand Logo"
    ],
    "SEO": [
        "Technical SEO Audit", "On-page SEO Optimization",
        "Backlink Building", "Keyword Research Expert",
        "SEO Content Writer", "Local SEO Specialist",
        "eCommerce SEO", "SEO for WordPress",
        "Google Ranking Expert", "SEO Consultant Needed"
    ],
    "Virtual Assistant": [
        "Administrative Assistant", "Data Entry Specialist",
        "Calendar Management", "Email Management",
        "Research Assistant", "Customer Support VA",
        "HR Assistant", "Project Coordinator",
        "Bookkeeping Assistant", "Travel Planning VA"
    ],
    "Customer Service": [
        "Live Chat Support", "Email Support Agent",
        "Phone Support Representative", "Customer Success Manager",
        "Helpdesk Support", "Zendesk Specialist",
        "Technical Support Agent", "Order Processing",
        "Customer Retention Specialist", "Retention Agent"
    ]
}

DESCRIPTIONS = [
    "Looking for an experienced professional to help with this project. Must have proven track record.",
    "Need someone reliable who can deliver quality work on time. Open to negotiation for the right candidate.",
    "Urgent requirement - need to start immediately. Please share your portfolio and relevant experience.",
    "Long-term opportunity for the right developer. Looking for someone who can commit to ongoing work.",
    "Creative project requiring innovative solutions. Open to new approaches and ideas.",
    "Technical project needing specific expertise. Please detail your experience in proposal.",
    "Startup looking for talented individual to join our team. Equity options available.",
    "Enterprise project requiring professional approach. Must be available for weekly meetings.",
    "Remote position - must be self-motivated and detail-oriented. Great opportunity for growth.",
    "Looking for specialist with deep knowledge in this area. Competitive rates for the right person."
]

CLIENTS = [
    {"name": "TechStart Inc.", "industry": "Technology"},
    {"name": "Digital Agency Co.", "industry": "Marketing"},
    {"name": "Creative Studios", "industry": "Design"},
    {"name": "DataDriven Corp", "industry": "Analytics"},
    {"name": "InnovateTech", "industry": "Software"},
    {"name": "BrandBuilders", "industry": "Advertising"},
    {"name": "CloudFirst", "industry": "Cloud Services"},
    {"name": "SmartSolutions", "industry": "Consulting"},
    {"name": "NextGen Apps", "industry": "Mobile"},
    {"name": "ContentPro", "industry": "Media"}
]

def generate_project(category):
    """Generate a sample project"""
    title = random.choice(JOB_TITLES.get(category, ["Project Developer"]))
    
    # Select 2-5 random skills for this category
    category_skills = SKILLS.get(category, ["Python"])
    num_skills = random.randint(2, min(5, len(category_skills)))
    skills = random.sample(category_skills, num_skills)
    
    # Budget range based on category
    budget_ranges = {
        "Web Development": (500, 10000),
        "Mobile App Development": (1000, 15000),
        "UI/UX Design": (300, 5000),
        "Graphic Design": (100, 2000),
        "Content Writing": (50, 1500),
        "Digital Marketing": (200, 5000),
        "Data Science": (500, 8000),
        "Machine Learning": (1000, 15000),
        "DevOps": (500, 8000),
        "Blockchain": (1000, 12000),
        "Video Editing": (200, 3000),
        "Logo Design": (100, 1500),
        "SEO": (200, 3000),
        "Virtual Assistant": (100, 1500),
        "Customer Service": (100, 2000)
    }
    
    min_budget, max_budget = budget_ranges.get(category, (500, 5000))
    budget_min = random.randint(min_budget, max_budget)
    budget_max = random.randint(budget_min, min(max_budget, budget_min + 2000))
    
    # Timeline options
    timelines = ["Less than 1 month", "1-3 months", "3-6 months", "More than 6 months"]
    
    client = random.choice(CLIENTS)
    
    return {
        "title": title,
        "description": random.choice(DESCRIPTIONS),
        "category": category,
        "required_skills": skills,
        "budget_min": float(budget_min),
        "budget_max": float(budget_max),
        "budget_type": random.choice(["fixed", "hourly"]),
        "timeline": random.choice(timelines),
        "deadline": datetime.now() + timedelta(days=random.randint(30, 180)),
        "status": "open",
        "client_id": f"client_{random.randint(1, 10)}",
        "client_name": client["name"],
        "created_at": datetime.now() - timedelta(days=random.randint(0, 30)),
        "proposals_count": random.randint(0, 10)
    }

def add_sample_jobs():
    """Add 100 sample jobs to the database"""
    print("Adding 100 sample jobs to database...")
    
    # Clear existing projects (optional - comment out to keep existing)
    # db.projects.delete_many({"client_id": {"$regex": "sample_"}})
    
    # Generate and insert 100 sample projects
    projects = []
    for i in range(100):
        category = random.choice(CATEGORIES)
        project = generate_project(category)
        project["client_id"] = f"sample_client_{i}"
        projects.append(project)
    
    # Insert into database
    result = db.projects.insert_many(projects)
    
    print(f"Successfully added {len(result.inserted_ids)} sample jobs!")
    
    # Print some stats
    print("\nCategory distribution:")
    for category in CATEGORIES:
        count = db.projects.count_documents({"category": category, "client_id": {"$regex": "sample_"}})
        if count > 0:
            print(f"  {category}: {count}")

if __name__ == "__main__":
    add_sample_jobs()
    client.close()