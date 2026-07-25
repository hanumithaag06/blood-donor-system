"""
Search Service — optimized donor search combining multiple filters.
Eligibility filtering happens in Python after a single DB query (rather
than per-donor DB calls) to avoid N+1 query patterns — Phase 9 requirement.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Donor
from app.repository import DonorRepository
from app.services.eligibility_service import EligibilityService
from app.utils import get_logger

logger = get_logger(__name__)


class SearchService:

    def __init__(self, session: Session):
        self.session = session
        self.donor_repo = DonorRepository(session)
        self.eligibility_service = EligibilityService()

    def search(
        self,
        blood_group: Optional[str] = None,
        area: Optional[str] = None,
        eligible_only: Optional[bool] = None,
        available_only: Optional[bool] = None,
    ) -> list[dict]:
        """
        Runs a single filtered DB query for blood_group/area/availability,
        then applies eligibility filtering in-memory (since eligibility is
        a derived, not stored, value — see Phase 5 schema design).
        """
        is_available_filter = True if available_only else None

        donors: list[Donor] = self.donor_repo.search(
            blood_group=blood_group,
            area=area,
            is_available=is_available_filter,
        )

        logger.info(
            f"Search matched {len(donors)} donor(s) before eligibility filter "
            f"(blood_group={blood_group}, area={area})"
        )

        results = []
        for donor in donors:
            last_donation = self.donor_repo.get_last_donation_date(donor.id)
            eligibility = self.eligibility_service.check_eligibility(
                donor_id=donor.id,
                date_of_birth=donor.date_of_birth,
                last_donation_date=last_donation,
            )

            if eligible_only and not eligibility.is_eligible:
                continue

            results.append({
                "donor": donor,
                "eligibility": eligibility,
            })

        return results

    def count_by_blood_group(self, blood_group: str) -> int:
        return self.donor_repo.count_by_blood_group(blood_group)