"""
Inference-only wrapper for the trained model.
Deliberately does NOT import anything from train.py — the live Flask app
should never pull in the training pipeline's dependencies (train_test_split,
dataset generation, etc.) just to serve a prediction request.
"""
import pickle
import os

from app.utils import get_logger

logger = get_logger(__name__)

MODEL_PATH = "app/ml/artifacts/response_model.pkl"


class PredictionModel:
    """Loads a pre-trained model once and serves predictions."""

    _model = None  # class-level cache so the model loads only once per process

    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        if PredictionModel._model is None:
            PredictionModel._model = self._load_model()

    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.warning(
                f"No trained model found at {self.model_path}. "
                "Run `python -m app.ml.train` first. Falling back to a "
                "naive default predictor."
            )
            return None

        with open(self.model_path, "rb") as f:
            model = pickle.load(f)
        logger.info(f"Loaded trained model from {self.model_path}")
        return model

    def predict_proba(self, features: dict) -> float:
        """
        Returns the probability (0.0-1.0) that the donor responds.
        Falls back to a simple heuristic if no trained model is present,
        so the API doesn't break in a fresh environment before training
        has been run.
        """
        if PredictionModel._model is None:
            return self._fallback_heuristic(features)

        import pandas as pd
        feature_order = ["age", "days_since_last_donation", "is_eligible", "is_available"]
        X = pd.DataFrame([[features[col] for col in feature_order]], columns=feature_order)

        probability = PredictionModel._model.predict_proba(X)[0][1]
        return float(probability)

    def _fallback_heuristic(self, features: dict) -> float:
        score = 0.2
        if features.get("is_eligible"):
            score += 0.3
        if features.get("is_available"):
            score += 0.3
        return min(score, 1.0)