"""
Offline ML training pipeline. Run manually: python -m app.ml.train
NOT imported by the live Flask app — see app/ml/model.py for the
lightweight inference wrapper the app actually uses.

Prediction target: "Will this donor respond/show up if contacted for an
emergency donation?" — chosen because it represents genuine uncertainty
(unlike blood_group or age, which are deterministic facts already known).
This is exactly the kind of signal that helps hospital staff prioritize
who to call first during an emergency, without pretending to predict
something that isn't actually uncertain.
"""
import pickle
from datetime import date, timedelta
import random

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix
)

from app.utils import get_logger

logger = get_logger(__name__)

RANDOM_SEED = 42
MODEL_OUTPUT_PATH = "app/ml/artifacts/response_model.pkl"


def generate_training_dataset(n_samples: int = 500) -> pd.DataFrame:
    """
    Generates a synthetic but structurally realistic dataset for
    demonstration purposes, since no real historical "did they respond"
    data exists yet in this project's scope.

    IMPORTANT: In production, this function would be replaced with a real
    query against a `contact_log` table (donor contacted -> did they
    respond, yes/no) — that table doesn't exist yet in our Phase 5 schema
    since it wasn't part of the current requirements. This is flagged
    here explicitly rather than silently faked as real data.
    """
    random.seed(RANDOM_SEED)
    rows = []
    for _ in range(n_samples):
        age = random.randint(18, 65)
        days_since_last_donation = random.choice([-1] + list(range(10, 400)))
        is_eligible = 1 if (days_since_last_donation == -1 or days_since_last_donation >= 90) else 0
        is_available = random.choice([0, 1])

        # Synthetic but logically-grounded target: eligible + available +
        # recently active donors are more likely to respond.
        base_prob = 0.2
        if is_eligible:
            base_prob += 0.3
        if is_available:
            base_prob += 0.3
        if days_since_last_donation != -1 and days_since_last_donation < 180:
            base_prob += 0.1

        responded = 1 if random.random() < base_prob else 0

        rows.append({
            "age": age,
            "days_since_last_donation": days_since_last_donation,
            "is_eligible": is_eligible,
            "is_available": is_available,
            "responded": responded,
        })

    return pd.DataFrame(rows)


def prepare_data(df: pd.DataFrame):
    """
    Feature selection and cleaning. Ensures no leakage: 'responded' (the
    target) is excluded from features, and no feature is derived FROM the
    target itself.
    """
    df = df.dropna()  # data cleaning: drop incomplete rows

    feature_cols = ["age", "days_since_last_donation", "is_eligible", "is_available"]
    X = df[feature_cols]
    y = df["responded"]

    return X, y


def train_model(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100, max_depth=5, random_state=RANDOM_SEED
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }

    feature_importance = dict(zip(X.columns, model.feature_importances_))

    return model, metrics, feature_importance


def save_model(model, path: str = MODEL_OUTPUT_PATH) -> None:
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"Model saved to {path}")


def run_training_pipeline() -> None:
    logger.info("Generating training dataset...")
    df = generate_training_dataset()

    logger.info("Preparing features...")
    X, y = prepare_data(df)

    logger.info("Training model...")
    model, metrics, feature_importance = train_model(X, y)

    logger.info(f"Evaluation metrics: {metrics}")
    logger.info(f"Feature importance: {feature_importance}")

    save_model(model)


if __name__ == "__main__":
    run_training_pipeline()