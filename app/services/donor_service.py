"""
Donor Service — orchestrates donor CRUD and donation-history operations.
Wraps repository calls, applies application-level checks (e.g. duplicate
phone), and translates ORM objects into response schemas.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Donor, Donation
from app.repository import DonorRepository, DonationRepository
from app.schemas import DonorCreateSchema, DonorUpdateSchema, DonationCreateSchema
from app.utils import get_logger, NotFoundError, DuplicateError

logger = get_logger(__name__)


class DonorService:

    def __init__(self, session: Session):
        self.session = session
        self.donor_repo = DonorRepository(session)
        self.donation_repo = DonationRepository(session)

    def create_donor(self, data: DonorCreateSchema) -> Donor:
        existing = self.donor_repo.get_by_phone(data.phone)
        if existing:
            raise DuplicateError(f"A donor with phone {data.phone} already exists.")

        donor = Donor(**data.model_dump())
        self.donor_repo.create(donor)
        logger.info(f"Created donor id={donor.id}")
        return donor

    def get_donor(self, donor_id: int) -> Donor:
        donor = self.donor_repo.get_by_id(donor_id)
        if not donor:
            raise NotFoundError(f"Donor with id={donor_id} not found.")
        return donor

    def update_donor(self, donor_id: int, data: DonorUpdateSchema) -> Donor:
        donor = self.get_donor(donor_id)
        updates = data.model_dump(exclude_unset=True)

        if "phone" in updates and updates["phone"] != donor.phone:
            existing = self.donor_repo.get_by_phone(updates["phone"])
            if existing:
                raise DuplicateError(f"A donor with phone {updates['phone']} already exists.")

        for field, value in updates.items():
            setattr(donor, field, value)

        self.donor_repo.update(donor)
        logger.info(f"Updated donor id={donor_id}")
        return donor

    def list_donors(self) -> list[Donor]:
        return self.donor_repo.list_all()

    def get_last_donation_date(self, donor_id: int) -> Optional[date]:
        return self.donor_repo.get_last_donation_date(donor_id)

    def get_donation_history(self, donor_id: int) -> list[Donation]:
        self.get_donor(donor_id)  # raises NotFoundError if donor doesn't exist
        return self.donation_repo.list_by_donor(donor_id)

    def add_donation(self, data: DonationCreateSchema) -> Donation:
        self.get_donor(data.donor_id)  # ensures donor exists before FK insert

        if self.donation_repo.exists_on_date(data.donor_id, data.donation_date):
            logger.warning(
                f"Duplicate-date donation entry for donor_id={data.donor_id} "
                f"on {data.donation_date} — allowed but flagged."
            )

        donation = Donation(**data.model_dump())
        self.donation_repo.create(donation)
        logger.info(f"Recorded donation id={donation.id} for donor_id={data.donor_id}")
        return donation