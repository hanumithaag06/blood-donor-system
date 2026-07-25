"""
Pydantic schemas — the API boundary contract. These define what shape of
data is acceptable coming in (request) and going out (response), separate
from ORM models (data storage) and business rules (services).
"""
from datetime import date, datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator

BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


# ---------- Donor Schemas ----------

class DonorCreateSchema(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    blood_group: BloodGroup
    gender: Optional[Literal["Male", "Female", "Other"]] = None
    phone: str = Field(..., min_length=7, max_length=15)
    area: str = Field(..., min_length=1, max_length=100)
    is_available: bool = True

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("phone")
    @classmethod
    def phone_digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("phone must contain digits only")
        return v


class DonorUpdateSchema(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    blood_group: Optional[BloodGroup] = None
    gender: Optional[Literal["Male", "Female", "Other"]] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=15)
    area: Optional[str] = Field(None, min_length=1, max_length=100)
    is_available: Optional[bool] = None


class DonorResponseSchema(BaseModel):
    id: int
    full_name: str
    date_of_birth: date
    blood_group: str
    gender: Optional[str] = None
    phone: str
    area: str
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Donation Schemas ----------

class DonationCreateSchema(BaseModel):
    donor_id: int
    donation_date: date
    volume_ml: Optional[int] = Field(None, gt=0)
    location: Optional[str] = None

    @field_validator("donation_date")
    @classmethod
    def donation_date_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("donation_date cannot be in the future")
        return v


class DonationResponseSchema(BaseModel):
    id: int
    donor_id: int
    donation_date: date
    volume_ml: Optional[int]
    location: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Eligibility Schema ----------

class EligibilityResponseSchema(BaseModel):
    donor_id: int
    is_eligible: bool
    reason: str
    last_donation_date: Optional[date] = None
    next_eligible_date: Optional[date] = None
    days_remaining: Optional[int] = None


# ---------- Search Schema ----------

class SearchQuerySchema(BaseModel):
    blood_group: Optional[BloodGroup] = None
    area: Optional[str] = None
    eligible_only: Optional[bool] = None
    available_only: Optional[bool] = None


# ---------- Prediction Schema ----------

class PredictionResponseSchema(BaseModel):
    donor_id: int
    response_likelihood: float = Field(..., ge=0.0, le=1.0)
    confidence_label: str


# ---------- Assistant Schema ----------

class AssistantQuerySchema(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)


class AssistantResponseSchema(BaseModel):
    intent: str
    answer: str
    data: Optional[list] = None


# ---------- Dashboard Schemas ----------

class DashboardStatsSchema(BaseModel):
    total_donors: int
    eligible_today: int
    available_donors: int
    rare_blood_donors: int


# ---------- Donor Details Schema ----------

class DonorDetailsResponseSchema(BaseModel):
    donor: DonorResponseSchema
    total_donations: int
    last_donation_date: Optional[date] = None
    eligibility: EligibilityResponseSchema