"""
Data Access Layer — the only module allowed to write direct SQLAlchemy
queries. Services call these methods; they never touch a Session directly.
This boundary is what makes services unit-testable with mocks and makes
the eventual SQLite -> PostgreSQL migration a config change, not a rewrite.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Donor, Donation


class DonorRepository:
    """Handles all direct DB access for the Donor entity."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, donor: Donor) -> Donor:
        self.session.add(donor)
        self.session.flush()
        return donor

    def get_by_id(self, donor_id: int) -> Optional[Donor]:
        return self.session.get(Donor, donor_id)

    def get_by_phone(self, phone_number: str) -> Optional[Donor]:
        return self.session.query(Donor).filter(Donor.phone_number == phone_number).first()

    def update(self, donor: Donor) -> Donor:
        self.session.flush()
        return donor

    def list_all(self) -> list[Donor]:
        return self.session.query(Donor).all()

    def search(
        self,
        blood_group: Optional[str] = None,
        area: Optional[str] = None,
        is_available: Optional[bool] = None,
        name: Optional[str] = None,
    ) -> list[Donor]:
        query = self.session.query(Donor)

        if blood_group:
            query = query.filter(Donor.blood_group == blood_group.strip().upper())
        if area:
            # Case-insensitive, whitespace-trimmed comparison — both sides
            # normalized identically so "Anna Nagar" == "anna nagar " == " ANNA NAGAR"
            query = query.filter(func.lower(func.trim(Donor.area)) == area.strip().lower())
        if is_available is not None:
            query = query.filter(Donor.is_available == is_available)
        if name:
            query = query.filter(Donor.full_name.ilike(f"%{name.strip()}%"))

        return query.all()

    def get_last_donation_date(self, donor_id: int) -> Optional[date]:
        """
        Derives the most recent donation date for a donor directly via SQL
        MAX(), rather than loading all donation rows into Python. Relies on
        idx_donation_donor_id_date for performance.
        """
        result = (
            self.session.query(func.max(Donation.donation_date))
            .filter(Donation.donor_id == donor_id)
            .scalar()
        )
        return result

    def count_by_blood_group(self, blood_group: str) -> int:
        return (
            self.session.query(func.count(Donor.id))
            .filter(Donor.blood_group == blood_group)
            .scalar()
        )

    def count_donations(self, donor_id: int) -> int:
        """Computed count — never stored, per Phase 5 normalization decision."""
        return (
            self.session.query(func.count(Donation.id))
            .filter(Donation.donor_id == donor_id)
            .scalar()
        )

    def count_donations_today(self) -> int:
        from datetime import date as date_cls
        return (
            self.session.query(func.count(Donation.id))
            .filter(Donation.donation_date == date_cls.today())
            .scalar()
        )


class DonationRepository:
    """Handles all direct DB access for the Donation entity."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, donation: Donation) -> Donation:
        self.session.add(donation)
        self.session.flush()
        return donation

    def get_by_id(self, donation_id: int) -> Optional[Donation]:
        return self.session.get(Donation, donation_id)

    def list_by_donor(self, donor_id: int) -> list[Donation]:
        return (
            self.session.query(Donation)
            .filter(Donation.donor_id == donor_id)
            .order_by(Donation.donation_date.desc())
            .all()
        )

    def exists_on_date(self, donor_id: int, donation_date: date) -> bool:
        """Used by validation layer to warn on same-day duplicate entries."""
        return (
            self.session.query(Donation)
            .filter(
                Donation.donor_id == donor_id,
                Donation.donation_date == donation_date,
            )
            .first()
            is not None
        )

    def list_recent(self, days: int = 30) -> list[Donation]:
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=days)
        return (
            self.session.query(Donation)
            .filter(Donation.donation_date >= cutoff)
            .order_by(Donation.donation_date.desc())
            .all()
        )

    def count_donations_today(self) -> int:
        from datetime import date as date_cls
        return (
            self.session.query(func.count(Donation.id))
            .filter(Donation.donation_date == date_cls.today())
            .scalar()
        )