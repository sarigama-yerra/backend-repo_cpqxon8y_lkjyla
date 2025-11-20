"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Class name lowercased is the collection name:
- Lead -> "lead"
- BlogPost -> "blogpost"
- Testimonial -> "testimonial"
- Appointment -> "appointment"
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class Lead(BaseModel):
    name: str = Field(..., description="Full name of the lead")
    email: EmailStr = Field(..., description="Email address of the lead")
    phone: Optional[str] = Field(None, description="Phone number")
    message: Optional[str] = Field(None, description="Message or context")
    consent: bool = Field(True, description="GDPR consent to be contacted")
    source: Optional[str] = Field("website", description="Source of the lead (e.g., website, campaign)")

class BlogPost(BaseModel):
    title: str
    excerpt: str
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = Field("Website Koning")

class Testimonial(BaseModel):
    author: str
    role: Optional[str] = None
    quote: str
    rating: Optional[int] = Field(5, ge=1, le=5)

class Appointment(BaseModel):
    name: str
    email: EmailStr
    phone: str = Field(..., description="Phone number is required")
    start: datetime = Field(..., description="Start time in ISO 8601 (UTC or naive server local)")
    end: datetime = Field(..., description="End time in ISO 8601 (UTC or naive server local)")
    note: Optional[str] = None
    source: Optional[str] = Field("website", description="Booking source")
    assigned_to: Optional[str] = Field(None, description="Assigned staff member handling this appointment")

# Example additional schemas (kept for reference)
class User(BaseModel):
    name: str
    email: EmailStr
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    in_stock: bool = True
