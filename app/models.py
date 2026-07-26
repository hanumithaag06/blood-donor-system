"""
SQLAlchemy ORM models: Donor and Donation.
These classes define data structure only — no business logic (e.g. no
eligibility calculation methods here). See app/services/ for logic.
"""
from datetime import date, datetime

from sqlalchemy import (
    Column, Integer, String, Date, Boolean, DateTime,
    ForeignKey, CheckConstraint, Index
)
from sqlalchemy.orm import relationship

from app.db import Base
from app.settings import settings


class Donor(Base):
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    blood_group = Column(String, nullable=False)
    gender = Column(String, nullable=True)  # 'Male' / 'Female' / 'Other' — optional, additive field
    phone_number = Column(String, nullable=False, unique=True, index=True)
    area = Column(String, nullable=False)
    is_available = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    donations = relationship(
        "Donation", back_populates="donor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"blood_group IN {settings.VALID_BLOOD_GROUPS}",
            name="ck_donor_blood_group_valid"
        ),
        CheckConstraint(
            "date_of_birth <= CURRENT_DATE",
            name="ck_donor_dob_not_future"
        ),
        Index("idx_donor_blood_group", "blood_group"),
        Index("idx_donor_area", "area"),
        Index("idx_donor_blood_group_area", "blood_group", "area"),
    )

    def __repr__(self) -> str:
        return f"<Donor id={self.id} name={self.full_name!r} blood_group={self.blood_group}>"


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    donor_id = Column(Integer, ForeignKey("donors.id"), nullable=False)
    donation_date = Column(Date, nullable=False)
    volume_ml = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    donor = relationship("Donor", back_populates="donations")

    __table_args__ = (
        CheckConstraint(
            "donation_date <= CURRENT_DATE",
            name="ck_donation_date_not_future"
        ),
        CheckConstraint(
            "volume_ml IS NULL OR volume_ml > 0",
            name="ck_donation_volume_positive"
        ),
        Index("idx_donation_donor_id_date", "donor_id", "donation_date"),
    )

    def __repr__(self) -> str:
        return f"<Donation id={self.id} donor_id={self.donor_id} date={self.donation_date}>"