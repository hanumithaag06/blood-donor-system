"""
Assistant module — intent-based query handling.
Pipeline: normalize(text) -> match_intent(text) -> respond(intent, params)
Deliberately rule-based (not spaCy/LLM) since the supported query set is
small and fixed — see Phase 3 reasoning. Kept behind this single interface
so the matching strategy can be swapped later without touching services.
"""
import re
import string
from typing import Optional

from sqlalchemy.orm import Session

from app.services.search_service import SearchService
from app.services.donor_service import DonorService
from app.repository import DonationRepository
from app.schemas import AssistantResponseSchema
from app.settings import settings
from app.utils import get_logger

logger = get_logger(__name__)

FALLBACK_MESSAGE = "I don't know how to answer that."


def normalize(text: str) -> str:
    """Lowercase, trim, and strip punctuation for reliable keyword matching.
    Preserves '+' and '-' since they're meaningful in blood group codes
    (e.g. O+, A-) rather than noise to strip."""
    text = text.lower().strip()
    punctuation_to_strip = string.punctuation.replace("+", "").replace("-", "")
    text = text.translate(str.maketrans("", "", punctuation_to_strip))
    text = re.sub(r"\s+", " ", text)
    return text


class Assistant:

    def __init__(self, session: Session):
        self.session = session
        self.search_service = SearchService(session)
        self.donor_service = DonorService(session)
        self.donation_repo = DonationRepository(session)

    def handle_query(self, raw_query: str) -> AssistantResponseSchema:
        text = normalize(raw_query)

        blood_group = self._extract_blood_group(text)
        area = self._extract_area(text)

        if "how many" in text and blood_group:
            return self._handle_count(blood_group)

        if "recent" in text or "recently" in text:
            return self._handle_recent_donors()

        if "available" in text and "today" in text:
            return self._handle_available_today()

        if blood_group or area:
            return self._handle_search(blood_group, area)

        logger.info(f"Unmatched assistant query: {raw_query!r}")
        return AssistantResponseSchema(intent="unknown", answer=FALLBACK_MESSAGE, data=None)

    def _extract_blood_group(self, text: str) -> Optional[str]:
        # Normalize spaced-out patterns like "o positive" / "a negative" too
        text_variants = text.replace("positive", "+").replace("negative", "-")
        for group in settings.VALID_BLOOD_GROUPS:
            normalized_group = group.lower().replace("+", " +").replace("-", " -")
            if group.lower() in text_variants or normalized_group in text_variants:
                return group
        return None

    def _extract_area(self, text: str) -> Optional[str]:
        match = re.search(r"\bin ([a-z\s]+?)(?:\s(?:who|with|that)\b|$)", text)
        if match:
            return match.group(1).strip().title()
        return None

    def _handle_search(self, blood_group: Optional[str], area: Optional[str]) -> AssistantResponseSchema:
        results = self.search_service.search(blood_group=blood_group, area=area)
        donor_names = [r["donor"].full_name for r in results]

        filters_desc = " and ".join(
            f for f in [blood_group, f"in {area}" if area else None] if f
        )
        answer = (
            f"Found {len(donor_names)} donor(s) {filters_desc}."
            if donor_names else f"No donors found {filters_desc}."
        )
        return AssistantResponseSchema(intent="search_donors", answer=answer, data=donor_names)

    def _handle_count(self, blood_group: str) -> AssistantResponseSchema:
        count = self.search_service.count_by_blood_group(blood_group)
        return AssistantResponseSchema(
            intent="count_donors",
            answer=f"There are {count} donor(s) with blood group {blood_group}.",
            data=[count],
        )

    def _handle_recent_donors(self) -> AssistantResponseSchema:
        recent = self.donation_repo.list_recent(days=30)
        names = [d.donor.full_name for d in recent] if recent else []
        answer = (
            f"{len(names)} donor(s) donated in the last 30 days."
            if names else "No donors have donated in the last 30 days."
        )
        return AssistantResponseSchema(intent="recent_donations", answer=answer, data=names)

    def _handle_available_today(self) -> AssistantResponseSchema:
        results = self.search_service.search(available_only=True)
        names = [r["donor"].full_name for r in results]
        answer = (
            f"{len(names)} donor(s) are currently marked available."
            if names else "No donors are currently marked available."
        )
        return AssistantResponseSchema(intent="available_donors", answer=answer, data=names)