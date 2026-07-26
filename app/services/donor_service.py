"""
Donor Service — orchestrates donor CRUD, donation history, and the
donation-completion workflow. All business logic lives here; repository
stays pure data-access, per requirement #9.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Donor, Donation
from app.repository import DonorRepository, DonationRepository
from app.schemas import DonorCreateSchema, DonorUpdateSchema, DonationCreateSchema, DonationCompleteSchema
from app.services.eligibility_service import EligibilityService
from app.utils import get_logger, NotFoundError, DuplicateError, ValidationError, normalize_area

logger = get_logger(__name__)


class DonorService:

    def __init__(self, session: Session):
        self.session = session
        self.donor_repo = DonorRepository(session)
        self.donation_repo = DonationRepository(session)
        self.eligibility_service = EligibilityService()

    # ---------- Mode 1: Add New Donor ----------

    def create_donor(self, data: DonorCreateSchema) -> Donor:
        existing = self.donor_repo.get_by_phone(data.phone_number)
        if existing:
            raise DuplicateError(f"A donor with phone_number {data.phone_number} already exists.")

        donor_data = data.model_dump()
        donor_data["area"] = normalize_area(donor_data["area"])  # NEW
        donor = Donor(**donor_data)
        self.donor_repo.create(donor)
        logger.info(f"Created donor id={donor.id}")
        return donor

    # ---------- Mode 2: Update Existing Donor ----------

    def find_donor_for_update(
        self, phone_number: Optional[str] = None, donor_id: Optional[int] = None
    ) -> Donor:
        """Looks up a donor by phone_number OR donor_id — used by Mode 2 to
        prevent duplicate donor creation."""
        if donor_id is not None:
            donor = self.donor_repo.get_by_id(donor_id)
        elif phone_number is not None:
            donor = self.donor_repo.get_by_phone(phone_number)
        else:
            raise ValidationError("Provide either phone_number or donor_id to look up a donor.")

        if not donor:
            raise NotFoundError("No matching donor found.")
        return donor

    def update_donor(self, donor_id: int, data: DonorUpdateSchema) -> Donor:
        donor = self.get_donor(donor_id)
        updates = data.model_dump(exclude_unset=True)

        if "area" in updates:
            updates["area"] = normalize_area(updates["area"])  # NEW

        if "phone_number" in updates and updates["phone_number"] != donor.phone_number:
            existing = self.donor_repo.get_by_phone(updates["phone_number"])
            if existing:
                raise DuplicateError(f"A donor with phone_number {updates['phone_number']} already exists.")

        for field, value in updates.items():
            setattr(donor, field, value)

        self.donor_repo.update(donor)
        logger.info(f"Updated donor id={donor_id}")
        return donor

    # ---------- Donation Completion Workflow (requirement #5) ----------

    def complete_donation(self, donor_id: int, data: DonationCompleteSchema) -> dict:
        """
        Records a donation and updates donor status in one workflow:
        - inserts donation history (never overwrites prior records)
        - sets is_available = False (donor unavailable until re-enabled/eligible)
        - eligibility/next-eligible-date is recomputed on next read, not stored
        """
        donor = self.get_donor(donor_id)

        donation = Donation(
            donor_id=donor_id,
            donation_date=data.donation_date,
            location=data.location,
            volume_ml=data.volume_ml,
        )
        self.donation_repo.create(donation)

        donor.is_available = False
        self.donor_repo.update(donor)

        logger.info(f"Completed donation workflow for donor_id={donor_id}")

        last_donation = self.donor_repo.get_last_donation_date(donor_id)
        eligibility = self.eligibility_service.check_eligibility(
            donor_id=donor_id,
            date_of_birth=donor.date_of_birth,
            last_donation_date=last_donation,
        )

        return {
            "donor_id": donor_id,
            "is_available": donor.is_available,
            "total_donations": self.donor_repo.count_donations(donor_id),
            "eligibility": eligibility,
        }

    def set_availability(self, donor_id: int, is_available: bool) -> Donor:
        """Manual availability override (requirement #6 — admin re-enable)."""
        donor = self.get_donor(donor_id)
        donor.is_available = is_available
        self.donor_repo.update(donor)
        logger.info(f"Set is_available={is_available} for donor_id={donor_id}")
        return donor

    # ---------- Existing methods (unchanged) ----------

    def get_donor(self, donor_id: int) -> Donor:
        donor = self.donor_repo.get_by_id(donor_id)
        if not donor:
            raise NotFoundError(f"Donor with id={donor_id} not found.")
        return donor

    def list_donors(self) -> list[Donor]:
        return self.donor_repo.list_all()

    def get_last_donation_date(self, donor_id: int) -> Optional[date]:
        return self.donor_repo.get_last_donation_date(donor_id)

    def get_total_donations(self, donor_id: int) -> int:
        return self.donor_repo.count_donations(donor_id)

    def get_donation_history(self, donor_id: int) -> list[Donation]:
        self.get_donor(donor_id)
        return self.donation_repo.list_by_donor(donor_id)

    def add_donation(self, data: DonationCreateSchema) -> Donation:
        self.get_donor(data.donor_id)
        if self.donation_repo.exists_on_date(data.donor_id, data.donation_date):
            logger.warning(f"Duplicate-date donation for donor_id={data.donor_id} on {data.donation_date}.")
        donation = Donation(**data.model_dump())
        self.donation_repo.create(donation)
        logger.info(f"Recorded donation id={donation.id} for donor_id={data.donor_id}")
        return donation