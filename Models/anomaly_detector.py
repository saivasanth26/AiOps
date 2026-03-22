# Models/anomaly_detector.py

import os
import logging
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from Configs.settings import (
    BASELINE_SAMPLES,
    COLLECTION_INTERVAL,
    CONTAMINATION,
    N_ESTIMATORS,
    RANDOM_STATE,
    BASELINE_DATA_PATH,
    MODEL_PATH,
    SCALER_PATH,
)

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Isolation Forest based anomaly detector.
    Handles baseline collection, model training, persistence and prediction.
    """

    def __init__(self):
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None
        self.is_trained: bool = False

    # ──────────────────────────────────────────
    # Training
    # ──────────────────────────────────────────

    def train(self, baseline_data: list[list[float]]) -> None:
        """
        Train Isolation Forest on baseline feature vectors.
        Saves model and scaler to disk after training.
        """
        X = np.array(baseline_data)
        logger.info("Training on %d baseline samples", len(X))

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
        )
        self.model.fit(X_scaled)
        self.is_trained = True

        self._save(baseline_data)
        logger.info("Model trained and saved successfully")

    # ──────────────────────────────────────────
    # Prediction
    # ──────────────────────────────────────────

    def predict(self, feature_vector: list[float]) -> dict:
        """
        Predict whether a feature vector is anomalous.
        Returns dict with is_anomaly, score, and scaled vector.
        """
        if not self.is_trained:
            raise RuntimeError("Model is not trained. Call train() first.")

        X = np.array(feature_vector).reshape(1, -1)
        X_scaled = self.scaler.transform(X)

        prediction = self.model.predict(X_scaled)[0]
        score = self.model.decision_function(X_scaled)[0]
        is_anomaly = prediction == -1

        result = {
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": round(float(score), 6),
            "prediction": int(prediction),
        }

        if is_anomaly:
            logger.warning(
                "ANOMALY DETECTED — score: %.6f, vector: %s",
                score, feature_vector
            )
        else:
            logger.info(
                "Normal — score: %.6f, vector: %s",
                score, feature_vector
            )

        return result

    # ──────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────

    def _save(self, baseline_data: list[list[float]]) -> None:
        """Save model, scaler and baseline data to disk."""
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)
        np.save(BASELINE_DATA_PATH, np.array(baseline_data))

        logger.info(
            "Saved model → %s, scaler → %s, baseline → %s",
            MODEL_PATH, SCALER_PATH, BASELINE_DATA_PATH
        )

    def load(self) -> bool:
        """
        Load model and scaler from disk if they exist.
        Returns True if loaded successfully, False otherwise.
        """
        if (
            os.path.exists(MODEL_PATH)
            and os.path.exists(SCALER_PATH)
        ):
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.is_trained = True
            logger.info("Model loaded from disk")
            return True

        logger.info("No saved model found — training required")
        return False