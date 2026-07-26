
import csv
from datetime import datetime
from pathlib import Path

from app.db import get_session, init_db
from app.models import Donor, Donation
from app.utils import get_logger

logger = get_logger(__name__)

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "donor_history.csv"


def _parse_date(value: str):
    return datetime.strptime(value.strip(), "%Y-%m-%d").date() if value.strip() else None


def _parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _parse_int(value: str):
    return int(value.strip()) if value.strip() else None


def run_seed() -> None:
    init_db()

    if not CSV_PATH.exists():
        logger.error(f"Seed CSV not found at {CSV_PATH}")
        return

    with get_session() as session:
        if session.query(Donor).first():
            print("Database already contains data — skipping seed to avoid duplicates.")
            return

        donor_cache: dict[str, Donor] = {}  # phone_number -> Donor, avoids inserting duplicates
        donation_count = 0

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                phone = row["phone_number"].strip()

                # Insert the donor only once, even though the CSV repeats
                # their row for every donation they've made.
                if phone not in donor_cache:
                    donor = Donor(
                        full_name=row["full_name"].strip(),
                        date_of_birth=_parse_date(row["date_of_birth"]),
                        gender=row.get("gender", "").strip() or None,
                        blood_group=row["blood_group"].strip(),
                        phone_number=phone,
                        area=row["area"].strip(),
                        is_available=_parse_bool(row["is_available"]),
                    )
                    session.add(donor)
                    session.flush()  # populate donor.id for the donation FK below
                    donor_cache[phone] = donor

                donor = donor_cache[phone]
                donation_date = _parse_date(row["donation_date"])

                # Some donors are first-time (no donation row) — CSV
                # represents this as blank donation_date/location/volume_ml.
                if donation_date:
                    donation = Donation(
                        donor_id=donor.id,
                        donation_date=donation_date,
                        location=row.get("location", "").strip() or None,
                        volume_ml=_parse_int(row.get("volume_ml", "")),
                    )
                    session.add(donation)
                    donation_count += 1

        print(f"Seeded {len(donor_cache)} donors and {donation_count} donations from {CSV_PATH.name}.")


if __name__ == "__main__":
    run_seed()