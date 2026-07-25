"""
Database engine and session lifecycle management.
This is the ONLY module that should create a SQLAlchemy engine or session.
All other layers (repositories) receive a session, they never construct one.
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.settings import settings

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables. Call once at application startup."""
    from app import models  # noqa: F401 ensures models are registered on Base
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """
    Provide a transactional scope around a series of operations.
    Usage:
        with get_session() as session:
            session.add(obj)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_dev_data() -> None:
    """
    Populate the database with sample donors/donations for local development
    and manual demoing. Not used by automated tests (see tests/conftest.py
    for test-specific fixtures).
    """
    from datetime import date, timedelta
    from app.models import Donor, Donation

    with get_session() as session:
        if session.query(Donor).first():
            print("Seed data already present, skipping.")
            return

        donors = [
            Donor(full_name="Arun Kumar", date_of_birth=date(1995, 4, 12),
                  blood_group="O+", phone="9000000001", area="Tambaram", is_available=True),
            Donor(full_name="Divya Shree", date_of_birth=date(1998, 9, 3),
                  blood_group="A-", phone="9000000002", area="Velachery", is_available=True),
            Donor(full_name="Karthik Raja", date_of_birth=date(1990, 1, 20),
                  blood_group="B+", phone="9000000003", area="Tambaram", is_available=False),
        ]
        session.add_all(donors)
        session.flush()  # populate donor.id before creating donations

        donations = [
            Donation(donor_id=donors[0].id, donation_date=date.today() - timedelta(days=120)),
            Donation(donor_id=donors[1].id, donation_date=date.today() - timedelta(days=10)),
        ]
        session.add_all(donations)

        print("Seed data inserted.")