import os
import joblib
import pandas as pd
import numpy as np
from lightgbm import LGBMRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import LabelEncoder

class TrafficImpactPredictor:
    """Predicts disruption (score, trains affected, delay) of a block."""
    def __init__(self):
        self.model = MultiOutputRegressor(LGBMRegressor(random_state=42))
        self.categorical_cols = ["section_traffic_density"]
        self.encoders = {col: LabelEncoder() for col in self.categorical_cols}
        
    def _preprocess(self, X: pd.DataFrame, training: bool = False) -> pd.DataFrame:
        X_proc = X.copy()
        if "window_id" in X_proc.columns:
            X_proc = X_proc.drop(columns=["window_id"])
            
        for col in self.categorical_cols:
            if col in X_proc.columns:
                if training:
                    X_proc[col] = self.encoders[col].fit_transform(X_proc[col].astype(str))
                else:
                    classes = self.encoders[col].classes_
                    X_proc[col] = X_proc[col].map(lambda x: x if x in classes else classes[0])
                    X_proc[col] = self.encoders[col].transform(X_proc[col].astype(str))
        return X_proc

    def fit(self, X: pd.DataFrame, y: pd.DataFrame):
        """Fit model on impact targets (traffic_impact_score, trains_affected, cumulative_delay_minutes)."""
        X_proc = self._preprocess(X, training=True)
        self.model.fit(X_proc, y)
        
    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict impacts."""
        X_proc = self._preprocess(X, training=False)
        preds = self.model.predict(X_proc)
        
        # Ensure non-negative
        preds = np.maximum(0, preds)
        
        return pd.DataFrame(preds, columns=["traffic_impact_score", "trains_affected", "cumulative_delay_minutes"])
        
    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            "model": self.model,
            "encoders": self.encoders
        }, path)
        
    def load(self, path: str):
        data = joblib.load(path)
        self.model = data["model"]
        self.encoders = data["encoders"]
