#!/usr/bin/env python3
"""Create a verified test user directly in MongoDB for testing."""
import os
import sys
sys.path.insert(0, '/app/backend')

# Load environment variables
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from auth import security as sec

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "vibeverse"

async def create_test_user():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    email = "freeuser@test.com"
    password = "TestPass123!"
    name = "Free Test User"
    
    # Check if user already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        print(f"User {email} already exists with ID: {existing['_id']}")
        print(f"Org ID: {existing.get('default_org_id')}")
        return str(existing["_id"]), existing.get("default_org_id")
    
    # Create verified user
    user_doc = {
        "email": email,
        "name": name,
        "password_hash": sec.hash_password(password),
        "global_role": "user",
        "auth_provider": "local",
        "email_verified": True,  # Skip verification
        "created_at": datetime.now(timezone.utc)
    }
    
    user_res = await db.users.insert_one(user_doc)
    user_id = str(user_res.inserted_id)
    print(f"Created user: {email} with ID: {user_id}")
    
    # Create personal org with 50 credits (free plan)
    org_doc = {
        "name": f"{name}'s Org",
        "owner_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "plan": "free",
        "credits": 50
    }
    org_res = await db.organizations.insert_one(org_doc)
    org_id = str(org_res.inserted_id)
    print(f"Created org: {org_id} with 50 credits on free plan")
    
    # Create membership
    await db.memberships.insert_one({
        "org_id": org_id,
        "user_id": user_id,
        "role": "owner",
        "created_at": datetime.now(timezone.utc)
    })
    
    # Update user with default_org_id
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"default_org_id": org_id}}
    )
    
    print(f"✅ Test user created successfully!")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"User ID: {user_id}")
    print(f"Org ID: {org_id}")
    
    client.close()
    return user_id, org_id

if __name__ == "__main__":
    asyncio.run(create_test_user())
