"""
Eligibility Service — pure business logic, no I/O.
Given a donor's DOB and their last donation date (already fetched by the
caller), computes eligibility. Kept dependency-free so it can be unit
tested with plain Python values, no database or Flask context required.
"""
from datetime import date, timedelta
from typing import Optional

from app.settings import settings
from app.schemas import EligibilityResponseSchema


class EligibilityService:

    def __init__(
        self,
        interval_days: int = settings.ELIGIBILITY_INTERVAL_DAYS,
        min_age: int = settings.MIN_DONOR_AGE,
        max_age: int = settings.MAX_DONOR_AGE,
    ):
        self.interval_days = interval_days
        self.min_age = min_age
        self.max_age = max_age

    def _calculate_age(self, date_of_birth: date, as_of: date) -> int:
        age = as_of.year - date_of_birth.year
        if (as_of.month, as_of.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        return age

    def check_eligibility(
        self,
        donor_id: int,
        date_of_birth: date,
        last_donation_date: Optional[date],
        as_of: Optional[date] = None,
    ) -> EligibilityResponseSchema:
        """
        Returns a structured eligibility result, never a bare boolean,
        per Phase 8's requirement for explainable output.
        """
        as_of = as_of or date.today()

        age = self._calculate_age(date_of_birth, as_of)
        if age < self.min_age:
            return EligibilityResponseSchema(
                donor_id=donor_id,
                is_eligible=False,
                reason=f"Donor is under the minimum eligible age of {self.min_age}.",
                last_donation_date=last_donation_date,
                next_eligible_date=None,
            )
        if age > self.max_age:
            return EligibilityResponseSchema(
                donor_id=donor_id,
                is_eligible=False,
                reason=f"Donor exceeds the maximum eligible age of {self.max_age}.",
                last_donation_date=last_donation_date,
                next_eligible_date=None,
            )

        # First-time donor: no donation history means immediately eligible
        if last_donation_date is None:
            return EligibilityResponseSchema(
                donor_id=donor_id,
                is_eligible=True,
                reason="First-time donor with no prior donation history.",
                last_donation_date=None,
                next_eligible_date=None,
            )

        next_eligible_date = last_donation_date + timedelta(days=self.interval_days)

        if as_of >= next_eligible_date:
            return EligibilityResponseSchema(
                donor_id=donor_id,
                is_eligible=True,
                reason=f"Minimum interval of {self.interval_days} days since last donation has passed.",
                last_donation_date=last_donation_date,
                next_eligible_date=next_eligible_date,
            )

        days_remaining = (next_eligible_date - as_of).days
        return EligibilityResponseSchema(
            donor_id=donor_id,
            is_eligible=False,
            reason=f"Donor must wait {days_remaining} more day(s) since last donation.",
            last_donation_date=last_donation_date,
            next_eligible_date=next_eligible_date,
        )