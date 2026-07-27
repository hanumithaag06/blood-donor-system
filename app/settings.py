"""
Centralized configuration loader.
All tunable business rules and environment values live here — nowhere else
in the codebase should read from os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Typed application configuration, loaded once at import time."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///blood_donor.db")

    ELIGIBILITY_INTERVAL_DAYS: int = int(os.getenv("ELIGIBILITY_INTERVAL_DAYS", "90"))
    MIN_DONOR_AGE: int = int(os.getenv("MIN_DONOR_AGE", "18"))
    MAX_DONOR_AGE: int = int(os.getenv("MAX_DONOR_AGE", "65"))

    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    VALID_BLOOD_GROUPS: tuple = (
        "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
    )

    CHENNAI_AREAS: tuple = (
        "Anna Nagar", "Adyar", "Ambattur", "Ashok Nagar", "Alandur", "Avadi",
        "Besant Nagar", "Chromepet", "Egmore", "Guindy", "Kodambakkam",
        "Kolathur", "Madhavaram", "Madipakkam", "Mogappair", "Mylapore",
        "Nanganallur", "OMR", "Pallavaram", "Perambur", "Porur",
        "Royapettah", "Saidapet", "Tambaram", "T Nagar", "Thiruvanmiyur",
        "Triplicane", "Vadapalani", "Velachery", "Villivakkam", "Virugambakkam",
    )

    TANGLISH_WORD_MAP: dict = {
        "la": "in",
        "kaatu": "show",
        "kattu": "show",
        "kamika": "show",
        "irukka": "available",
        "iruka": "available",
        "irukanga": "available",
        "thaguhi": "eligible",
        "thaguthi": "eligible",
        "evalavu": "count",
        "ethanai": "count",
        "ennikai": "count",
        "irukuranga": "available",
        "irukura": "available",
        "evlo": "how many",
        "evolo": "how many",
        "evallo": "how many",
        "yevlo": "how many",
    }


settings = Settings()