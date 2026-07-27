"""
Assistant module — intent-aware, field-selective, Tanglish-normalized.
"""
import re
import string
import difflib
from typing import Optional

from sqlalchemy.orm import Session

from app.services.search_service import SearchService
from app.services.donor_service import DonorService
from app.repository import DonationRepository
from app.schemas import AssistantResponseSchema
from app.settings import settings
from app.utils import get_logger

logger = get_logger(__name__)

FALLBACK_MESSAGE = (
    "I'm not sure because this question is outside the scope of the Blood "
    "Donor Registry system. I can assist with donor search, donor "
    "availability, donor registration, eligibility, donation history, and "
    "blood group information. For other queries, please contact the "
    "hospital office or system administrator."
)

TANGLISH_FUZZY_THRESHOLD = 0.82
DOMAIN_ANCHOR_WORDS = ("donor", "donors", "blood", "eligib", "registr")
PROFILE_INTENT_WORDS = ("details", "profile", "show donor", "phone", "number", "contact", "blood group")


def normalize(text: str) -> str:
    text = text.lower().strip()
    punctuation_to_strip = string.punctuation.replace("+", "").replace("-", "")
    text = text.translate(str.maketrans("", "", punctuation_to_strip))
    text = re.sub(r"\s+", " ", text)
    return _apply_tanglish_map(text)


def _apply_tanglish_map(text: str) -> str:
    known_words = list(settings.TANGLISH_WORD_MAP.keys())
    words = text.split()
    translated = []
    for word in words:
        if word in settings.TANGLISH_WORD_MAP:
            translated.append(settings.TANGLISH_WORD_MAP[word])
            continue
        close = difflib.get_close_matches(word, known_words, n=1, cutoff=TANGLISH_FUZZY_THRESHOLD)
        if close:
            translated.append(settings.TANGLISH_WORD_MAP[close[0]])
        else:
            translated.append(word)
    return " ".join(translated)


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
        donor_name = self._extract_full_donor_name(text)

        # HARD GATE — first check, unconditionally. A query is in-scope
        # only if it names a domain anchor word, a blood group, an area,
        # or a donor name. "available"/"eligible" alone (which can appear
        # via unreliable Tanglish translation on unrelated sentences) are
        # NOT sufficient on their own.
        if not self._is_domain_relevant(text, blood_group, area, donor_name):
            logger.info(f"Out-of-scope query: {raw_query!r} (normalized: {text!r})")
            return AssistantResponseSchema(intent="unknown", answer=FALLBACK_MESSAGE, data=None)

        if donor_name and any(w in text for w in PROFILE_INTENT_WORDS):
            return self._handle_donor_profile(donor_name)

        available_only = "available" in text
        eligible_only = "eligible" in text

        if "how many" in text or "count" in text:
            return self._handle_count_with_details(
                blood_group=blood_group, area=area,
                eligible_only=eligible_only or None, available_only=available_only or None,
            )

        return self._handle_search(
            blood_group=blood_group, area=area,
            eligible_only=eligible_only or None, available_only=available_only or None,
        )

    def _is_domain_relevant(self, text, blood_group, area, donor_name) -> bool:
        if any(anchor in text for anchor in DOMAIN_ANCHOR_WORDS):
            return True
        if blood_group or donor_name:
            return True
        return False

    def _extract_blood_group(self, text: str) -> Optional[str]:
        variants = text.replace("positive", "+").replace("negative", "-")
        for group in sorted(settings.VALID_BLOOD_GROUPS, key=len, reverse=True):
            if group.lower() in variants:
                return group
        return None

    def _extract_area(self, text: str) -> Optional[str]:
        for area in settings.CHENNAI_AREAS:
            if area.lower() in text:
                return area
        text_no_spaces = text.replace(" ", "")
        for area in settings.CHENNAI_AREAS:
            if area.lower().replace(" ", "") in text_no_spaces:
                return area
        words = text.split()
        area_names_lower = [a.lower() for a in settings.CHENNAI_AREAS]
        for word in words:
            close = difflib.get_close_matches(word, area_names_lower, n=1, cutoff=0.85)
            if close:
                return settings.CHENNAI_AREAS[area_names_lower.index(close[0])]
        return None

    def _extract_full_donor_name(self, text: str) -> Optional[str]:
        match = re.search(r"(?:details of|profile of|donor details of|show donor)\s+([a-z\s]+)$", text)
        if match:
            return match.group(1).strip().title()
        match = re.search(r"^([a-z]+)\s+(?:[a-z]+\s+)?oda\b", text)
        if match:
            return match.group(1).strip().title()
        return None

    def _build_header(self, available_only, eligible_only, blood_group, area) -> str:
        parts = []
        if available_only:
            parts.append("Available")
        if eligible_only:
            parts.append("Eligible")
        if blood_group:
            parts.append(blood_group)
        parts.append("Donors")
        header = " ".join(parts)
        if area:
            header += f" in {area}"
        return header

    def _handle_search(self, blood_group=None, area=None, eligible_only=None, available_only=None) -> AssistantResponseSchema:
        results = self.search_service.search(
            blood_group=blood_group, area=area,
            eligible_only=eligible_only, available_only=available_only,
        )
        header = self._build_header(available_only, eligible_only, blood_group, area)
        fields = ["name", "phone", "area"] if (available_only and not blood_group and not eligible_only) else ["name", "blood_group", "phone", "area"]
        answer = self._format_donor_list(results, header, fields)
        return AssistantResponseSchema(intent="search_donors", answer=answer, data=[r["donor"].full_name for r in results])

    def _handle_count_with_details(self, blood_group=None, area=None, eligible_only=None, available_only=None) -> AssistantResponseSchema:
        results = self.search_service.search(
            blood_group=blood_group, area=area,
            eligible_only=eligible_only, available_only=available_only,
        )
        header = self._build_header(available_only, eligible_only, blood_group, area)
        header = f"{header} Found : {len(results)}"
        fields = ["name", "phone", "area", "available"] if not (blood_group or eligible_only) else ["name", "blood_group", "phone", "area", "available"]
        answer = self._format_donor_list(results, header, fields)
        return AssistantResponseSchema(intent="count_with_details", answer=answer, data=[len(results)])

    def _format_field(self, field: str, donor, eligibility) -> str:
        mapping = {
            "id": f"Donor ID : D{donor.id:06d}",
            "name": f"Name : {donor.full_name}",
            "blood_group": f"Blood Group : {donor.blood_group}",
            "phone": f"Phone : {donor.phone_number}",
            "area": f"Area : {donor.area}",
            "eligibility": f"Eligibility : {'Eligible' if eligibility.is_eligible else 'Not Eligible'}",
            "available": f"Availability : {'Available' if donor.is_available else 'Not Available'}",
        }
        return mapping.get(field, "")

    def _format_donor_list(self, results, header, fields) -> str:
        if not results:
            return f"{header}\n\nNo donors found."
        separator = "-" * 32
        lines = [header, "", separator]
        for i, r in enumerate(results, start=1):
            donor, eligibility = r["donor"], r["eligibility"]
            lines.append(str(i))
            lines.append("")
            for f in fields:
                lines.append(self._format_field(f, donor, eligibility))
            lines.append("")
            lines.append(separator)
        return "\n".join(lines)

    def _handle_donor_profile(self, name: str) -> AssistantResponseSchema:
        results = self.search_service.search()
        match = next((r for r in results if name.lower() in r["donor"].full_name.lower()), None)
        if not match:
            return AssistantResponseSchema(intent="donor_profile", answer=f"No donor found matching '{name}'.", data=None)
        donor, eligibility = match["donor"], match["eligibility"]
        total_donations = self.donor_service.get_total_donations(donor.id)
        last_donation = eligibility.last_donation_date or "No prior donation"
        answer = (
            f"Name: {donor.full_name}\nBlood Group: {donor.blood_group}\n"
            f"Phone: {donor.phone_number}\nGender: {donor.gender or 'Not specified'}\n"
            f"Area: {donor.area}\nDOB: {donor.date_of_birth}\nLast Donation: {last_donation}\n"
            f"Eligibility: {'Eligible' if eligibility.is_eligible else 'Not Eligible'}\n"
            f"Available Today: {'Yes' if donor.is_available else 'No'}\nTotal Donations: {total_donations}"
        )
        return AssistantResponseSchema(intent="donor_profile", answer=answer, data=[donor.full_name])