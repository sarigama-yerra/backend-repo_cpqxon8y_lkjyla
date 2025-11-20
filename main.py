import os
from datetime import datetime, time, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import smtplib
from email.mime.text import MIMEText

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

# --- Email helper ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@websitekoning.com")


def send_email(subject: str, body: str, to_addrs: List[str]):
    if not (SMTP_HOST and SMTP_FROM):
        # No SMTP configured; skip silently but log to console
        print("[email] SMTP not configured. Would send:", subject, to_addrs)
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(to_addrs)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_addrs, msg.as_string())
    except Exception as e:
        print("[email] Error sending email:", e)


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

# --- Appointment helpers ---
BUSINESS_START = time(10, 0)
BUSINESS_END = time(17, 0)
SLOT_DURATION = timedelta(minutes=30)
BUFFER = timedelta(minutes=15)
MAX_CONCURRENT = 2  # allow one overlap -> capacity 2


def within_business_hours(start_dt: datetime, end_dt: datetime) -> bool:
    # same-day enforcement
    if start_dt.date() != end_dt.date():
        return False
    if start_dt.weekday() > 4:  # 0=Mon
        return False
    start_t = start_dt.time()
    end_t = end_dt.time()
    # Start at or after 10:00, end at or before 17:00
    return (start_t >= BUSINESS_START) and (end_t <= BUSINESS_END)


@app.post("/api/appointments")
async def create_appointment(appt: Appointment, background: BackgroundTasks):
    """Create an appointment with business rules:
    - Only weekdays Mon–Fri, 10:00–17:00
    - Fixed 30-minute duration
    - 15-minute buffer around appointments
    - Max 2 concurrent appointments in the same buffered window
    """
    # Basic time validation
    if appt.end <= appt.start:
        raise HTTPException(status_code=400, detail="Eindtijd moet na starttijd liggen")

    # Fixed 30-minute duration
    if (appt.end - appt.start) != SLOT_DURATION:
        raise HTTPException(status_code=400, detail="Alleen afspraken van 30 minuten zijn mogelijk")

    # Business hours and weekdays
    if not within_business_hours(appt.start, appt.end):
        raise HTTPException(status_code=400, detail="Afspraken kunnen alleen ma–vr tussen 10:00 en 17:00")

    if db is None:
        return {"status": "accepted", "stored": False}

    # Overlap check with buffer and capacity
    try:
        buffered_start = appt.start - BUFFER
        buffered_end = appt.end + BUFFER
        overlapping_count = db["appointment"].count_documents({
            "$and": [
                {"start": {"$lt": buffered_end}},
                {"end": {"$gt": buffered_start}},
            ]
        })
        if overlapping_count >= MAX_CONCURRENT:
            raise HTTPException(status_code=409, detail="Tijdslot is vol. Kies een ander moment.")

        _id = create_document("appointment", appt)

        # Send notifications (best effort)
        start_str = appt.start.strftime("%Y-%m-%d %H:%M")
        end_str = appt.end.strftime("%H:%M")
        subject = f"Nieuwe afspraak: {appt.name} – {start_str}"
        body_admin = (
            f"Nieuwe afspraak geboekt:\n\n"
            f"Naam: {appt.name}\n"
            f"E-mail: {appt.email}\n"
            f"Telefoon: {appt.phone}\n"
            f"Tijd: {start_str} - {end_str}\n"
            f"Bron: {appt.source or 'website'}\n"
            f"Notitie: {appt.note or '-'}\n"
            f"ID: {_id}\n"
        )
        admin_recipients = ["nick@websitekoning.com", "amine@websitekoning.com"]
        background.add_task(send_email, subject, body_admin, admin_recipients)

        subject_client = "Bevestiging afspraak – Website Koning"
        body_client = (
            f"Hi {appt.name},\n\n"
            f"Je afspraak is bevestigd op {start_str} (30 minuten).\n"
            f"We bellen of videobellen op het afgesproken tijdstip.\n\n"
            f"Tot dan!\nWebsite Koning"
        )
        background.add_task(send_email, subject_client, body_client, [appt.email])

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
        docs = get_documents("appointment", limit=200)
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
