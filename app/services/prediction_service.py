"""
Prediction Service — bridges the ML inference module (app/ml/model.py)
to the rest of the application. Services never import scikit-learn
directly; they go through this thin wrapper.
"""
from sqlalchemy.orm import Session

from app.models import Donor
from app.repository import DonorRepository
from app.services.eligibility_service import EligibilityService
from app.ml.model import PredictionModel
from app.schemas import PredictionResponseSchema
from app.utils import get_logger, NotFoundError

logger = get_logger(__name__)


class PredictionService:

    def __init__(self, session: Session):
        self.session = session
        self.donor_repo = DonorRepository(session)
        self.eligibility_service = EligibilityService()
        self.model = PredictionModel()

    def predict_response_likelihood(self, donor_id: int) -> PredictionResponseSchema:
        donor: Donor = self.donor_repo.get_by_id(donor_id)
        if not donor:
            raise NotFoundError(f"Donor with id={donor_id} not found.")

        last_donation = self.donor_repo.get_last_donation_date(donor_id)
        eligibility = self.eligibility_service.check_eligibility(
            donor_id=donor.id,
            date_of_birth=donor.date_of_birth,
            last_donation_date=last_donation,
        )

        features = self._build_feature_vector(donor, last_donation, eligibility.is_eligible)
        probability = self.model.predict_proba(features)

        confidence_label = self._confidence_label(probability)

        logger.info(f"Predicted response_likelihood={probability:.2f} for donor_id={donor_id}")

        return PredictionResponseSchema(
            donor_id=donor_id,
            response_likelihood=round(probability, 4),
            confidence_label=confidence_label,
        )

    def _build_feature_vector(self, donor: Donor, last_donation_date, is_eligible: bool) -> dict:
        """
        Builds the exact feature dict the trained model expects.
        Kept in sync with app/ml/train.py's feature engineering —
        any change here requires retraining.
        """
        from datetime import date
        days_since_last_donation = (
            (date.today() - last_donation_date).days if last_donation_date else -1
        )
        age = date.today().year - donor.date_of_birth.year

        return {
            "age": age,
            "days_since_last_donation": days_since_last_donation,
            "is_eligible": int(is_eligible),
            "is_available": int(donor.is_available),
        }

    def _confidence_label(self, probability: float) -> str:
        if probability >= 0.7:
            return "High"
        elif probability >= 0.4:
            return "Medium"
        return "Low"