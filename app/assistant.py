"""
Assistant module — dynamically selects response fields based on detected
intent, instead of always returning the full donor profile.
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
    return re.sub(r"\s+", " ", text)


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

        # ---- Full profile intent: "show donor details of X" ----
        if donor_name and ("details" in text or "profile" in text or "show donor" in text):
            return self._handle_donor_profile(donor_name)

        # ---- Count intents: return a single number, nothing else ----
        if "how many" in text or text.startswith("count"):
            if "available" in text:
                return self._handle_count_with_details(available_only=True, label="Available Donors")
            if "eligible" in text:
                return self._handle_count_with_details(eligible_only=True, label="Eligible Donors",
                                                       fields=["name", "blood_group", "phone", "area"])
            if blood_group:
                return self._handle_count_with_details(blood_group=blood_group, label=f"{blood_group} Donors",
                                                       fields=["name", "phone", "area", "available"])
            # bare "how many donors" — count only, no detail dump, since no filter narrows it
            results = self.search_service.search()
            return AssistantResponseSchema(intent="count_donors", answer=f"Total Donors : {len(results)}", data=[len(results)])

        # ---- List intents: area / blood group / eligible / available ----
        if "available" in text and blood_group:
            return self._handle_search(
                blood_group=blood_group, available_only=True,
                header=f"Available {blood_group} Donors", fields=["name", "phone", "area"]
            )
        if "available" in text:
            return self._handle_search(
                area=area, available_only=True,
                header="Available Donors", fields=["name", "phone", "area"]
            )
        if "eligible" in text:
            return self._handle_search(
                blood_group=blood_group, area=area, eligible_only=True,
                header="Eligible Donors", fields=["name", "blood_group", "phone", "area"]
            )
        if area:
            return self._handle_search(
                area=area, header=f"{area} Donors",
                fields=["name", "blood_group", "phone", "area"]
            )
        if blood_group:
            return self._handle_search(
                blood_group=blood_group, header=f"{blood_group} Donors",
                fields=["name", "blood_group", "phone", "area"]
            )
        if "list donors" in text or "all donors" in text or "show donors" in text:
            return self._handle_search(
                header="All Donors", fields=["name", "blood_group", "phone", "area"]
            )

        logger.info(f"Unmatched assistant query: {raw_query!r}")
        return AssistantResponseSchema(intent="unknown", answer=FALLBACK_MESSAGE, data=None)

    # ---------- Extraction helpers ----------

    def _extract_blood_group(self, text: str) -> Optional[str]:
        variants = text.replace("positive", "+").replace("negative", "-")
        for group in settings.VALID_BLOOD_GROUPS:
            if group.lower() in variants:
                return group
        return None

    def _extract_area(self, text: str) -> Optional[str]:
        for area in settings.CHENNAI_AREAS:
            if area.lower() in text:
                return area
        return None

    def _extract_full_donor_name(self, text: str) -> Optional[str]:
        """Matches 'details of X', 'profile of X', 'show donor X'."""
        match = re.search(r"(?:details of|profile of|donor details of|show donor)\s+([a-z\s]+)$", text)
        return match.group(1).strip().title() if match else None

    # ---------- Field-selective formatting ----------

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

    def _format_donor_list(self, results: list[dict], header: str, fields: list[str]) -> str:
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

    # ---------- Handlers ----------

    def _handle_search(
        self, blood_group=None, area=None, eligible_only=None, available_only=None,
        header="Donors", fields=None,
    ) -> AssistantResponseSchema:
        fields = fields or ["name", "blood_group", "phone", "area"]
        results = self.search_service.search(
            blood_group=blood_group, area=area,
            eligible_only=eligible_only, available_only=available_only,
        )
        answer = self._format_donor_list(results, header, fields)
        donor_names = [r["donor"].full_name for r in results]
        return AssistantResponseSchema(intent="search_donors", answer=answer, data=donor_names)

    def _handle_count_with_details(
        self, blood_group=None, eligible_only=None, available_only=None,
        area=None, label="Donors", fields=None,
    ) -> AssistantResponseSchema:
        """Requirement #6: return count AND donor detail cards together."""
        fields = fields or ["name", "phone", "area", "available"]
        results = self.search_service.search(
            blood_group=blood_group, area=area,
            eligible_only=eligible_only, available_only=available_only,
        )
        header = f"{label} Found : {len(results)}"
        answer = self._format_donor_list(results, header, fields)
        return AssistantResponseSchema(intent="count_with_details", answer=answer, data=[len(results)])

    def _handle_count_only(
        self, blood_group=None, eligible_only=None, available_only=None, label="Donors"
    ) -> AssistantResponseSchema:
        results = self.search_service.search(
            blood_group=blood_group, eligible_only=eligible_only, available_only=available_only,
        )
        count = len(results)
        answer = f"{label} : {count}"
        return AssistantResponseSchema(intent="count_donors", answer=answer, data=[count])

    def _handle_donor_profile(self, name: str) -> AssistantResponseSchema:
        results = self.search_service.search()
        match = next((r for r in results if name.lower() in r["donor"].full_name.lower()), None)

        if not match:
            return AssistantResponseSchema(
                intent="donor_profile", answer=f"No donor found matching '{name}'.", data=None
            )

        donor, eligibility = match["donor"], match["eligibility"]
        total_donations = self.donor_service.get_total_donations(donor.id)
        last_donation = eligibility.last_donation_date or "No prior donation"

        answer = (
            f"Name: {donor.full_name}\n"
            f"Blood Group: {donor.blood_group}\n"
            f"Phone: {donor.phone_number}\n"
            f"Gender: {donor.gender or 'Not specified'}\n"
            f"Area: {donor.area}\n"
            f"DOB: {donor.date_of_birth}\n"
            f"Last Donation: {last_donation}\n"
            f"Eligibility: {'Eligible' if eligibility.is_eligible else 'Not Eligible'}\n"
            f"Available Today: {'Yes' if donor.is_available else 'No'}\n"
            f"Total Donations: {total_donations}"
        )
        return AssistantResponseSchema(intent="donor_profile", answer=answer, data=[donor.full_name])