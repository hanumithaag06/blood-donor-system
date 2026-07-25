"""
Standalone seeding script for realistic demo data.
Run with: python -m app.seed

Distinct from app/db.py's seed_dev_data() (which inserts a tiny 3-donor
smoke-test set for automated dev startup via `main.py --seed`). This
script populates a larger, more realistic dataset for manual testing,
demos, and assessment — useful for exercising search/filter/assistant
functionality with more than a handful of rows.
"""
from datetime import date, timedelta
import random

from app.db import get_session, init_db
from app.models import Donor, Donation
from app.settings import settings

RANDOM_SEED = 7

FIRST_NAMES = [
    "Arun", "Divya", "Karthik", "Meena", "Suresh", "Priya", "Vijay", "Anitha",
    "Ramesh", "Kavya", "Naveen", "Deepa", "Sanjay", "Lakshmi", "Arjun", "Swathi",
]
LAST_NAMES = [
    "Kumar", "Shree", "Raja", "Iyer", "Nair", "Menon", "Pillai", "Reddy",
]
AREAS = ["Tambaram", "Velachery", "Adyar", "Anna Nagar", "T Nagar", "Guindy"]


def _random_phone(existing: set) -> str:
    while True:
        phone = "9" + "".join(random.choices("0123456789", k=9))
        if phone not in existing:
            existing.add(phone)
            return phone


def _random_dob() -> date:
    # Keeps most donors within the eligible age band, with a few outliers
    # to exercise the age-boundary eligibility rules during manual testing.
    age = random.choice(
        [random.randint(settings.MIN_DONOR_AGE, settings.MAX_DONOR_AGE)] * 8
        + [random.randint(10, settings.MIN_DONOR_AGE - 1)]
        + [random.randint(settings.MAX_DONOR_AGE + 1, 80)]
    )
    today = date.today()
    return date(today.year - age, random.randint(1, 12), random.randint(1, 28))


def run_seed(num_donors: int = 25) -> None:
    random.seed(RANDOM_SEED)
    init_db()

    with get_session() as session:
        if session.query(Donor).first():
            print("Database already contains data — skipping seed to avoid duplicates.")
            return

        used_phones: set = set()
        donors = []

        for _ in range(num_donors):
            donor = Donor(
                full_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                date_of_birth=_random_dob(),
                blood_group=random.choice(settings.VALID_BLOOD_GROUPS),
                phone=_random_phone(used_phones),
                area=random.choice(AREAS),
                is_available=random.choice([True, True, False]),  # skew toward available
            )
            donors.append(donor)

        session.add_all(donors)
        session.flush()  # populate donor.id before creating donations

        donations = []
        for donor in donors:
            # Roughly 70% of donors have donation history; the rest are
            # first-time donors, exercising the "no history" eligibility path.
            if random.random() < 0.7:
                num_donations = random.randint(1, 3)
                last_date = date.today() - timedelta(days=random.randint(5, 500))
                for _ in range(num_donations):
                    donations.append(
                        Donation(donor_id=donor.id, donation_date=last_date)
                    )
                    last_date -= timedelta(days=random.randint(90, 200))

        session.add_all(donations)

        print(f"Seeded {len(donors)} donors and {len(donations)} donations.")


if __name__ == "__main__":
    run_seed()