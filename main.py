import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from database import db, create_document, get_documents
from schemas import Lead, BlogPost, Testimonial, Appointment

app = FastAPI(title="Website Koning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Seed routes to ensure pages work even without DB set
@app.on_event("startup")
async def seed_content():
    # If DB not configured, skip seeding
    if db is None:
        return
    try:
        if db["blogpost"].count_documents({}) == 0:
            posts = [
                {"title": "Conversiegerichte websites: wat werkt?", "excerpt": "Praktische tips voor meer leads.", "content": "...", "tags": ["conversie", "mkb"]},
                {"title": "Snelheid = omzet", "excerpt": "Waarom laadtijd je ROI bepaalt.", "content": "...", "tags": ["performance"]},
            ]
            for p in posts:
                create_document("blogpost", p)
        if db["testimonial"].count_documents({}) == 0:
            testimonials = [
                {"author": "Bakkerij De Graaf", "role": "Lokale bakker", "quote": "Binnen 2 weken live en direct meer aanvragen.", "rating": 5},
                {"author": "FixIt Service", "role": "Loodgieter", "quote": "Heldere prijzen en snelle service. Aanrader!", "rating": 5},
            ]
            for t in testimonials:
                create_document("testimonial", t)
    except Exception:
        # Non-fatal: we want API to stay up even if DB not available
        pass

# Leads endpoints
@app.post("/api/leads")
async def create_lead(lead: Lead):
    if db is None:
        # Accept but do not store if DB missing
        return {"status": "accepted", "stored": False}
    try:
        _id = create_document("lead", lead)
        return {"id": _id, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads")
async def list_leads():
    if db is None:
        return []
    try:
        docs = get_documents("lead", limit=50)
        # Convert ObjectId to string if present
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Content endpoints
@app.get("/api/posts")
async def list_posts():
    if db is None:
        # Fallback static content
        return [
            {"id": "1", "title": "Conversiegerichte websites: wat werkt?", "excerpt": "Praktische tips voor meer leads."},
            {"id": "2", "title": "Snelheid = omzet", "excerpt": "Waarom laadtijd je ROI bepaalt."},
        ]
    try:
        docs = get_documents("blogpost", limit=20)
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/testimonials")
async def list_testimonials():
    if db is None:
        return [
            {"author": "Bakkerij De Graaf", "role": "Lokale bakker", "quote": "Binnen 2 weken live en direct meer aanvragen.", "rating": 5},
            {"author": "FixIt Service", "role": "Loodgieter", "quote": "Heldere prijzen en snelle service. Aanrader!" , "rating": 5},
        ]
    try:
        docs = get_documents("testimonial", limit=20)
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Appointment endpoints
@app.post("/api/appointments")
async def create_appointment(appt: Appointment):
    """Create an appointment, preventing overlaps for the same time window.
    Two appointments are considered conflicting if their time ranges overlap.
    """
    # Validate time range
    if appt.end <= appt.start:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    if db is None:
        # Accept but do not store if DB missing
        return {"status": "accepted", "stored": False}

    # Check for overlap: (existing.start < new.end) AND (existing.end > new.start)
    try:
        conflict = db["appointment"].find_one({
            "$and": [
                {"start": {"$lt": appt.end}},
                {"end": {"$gt": appt.start}},
            ]
        })
        if conflict:
            raise HTTPException(status_code=409, detail="Tijdslot is al bezet. Kies een andere tijd.")

        _id = create_document("appointment", appt)
        return {"id": _id, "status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/appointments")
async def list_appointments():
    if db is None:
        return []
    try:
        docs = get_documents("appointment", limit=100)
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
