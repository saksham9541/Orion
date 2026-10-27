import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

class DurationEstimator:
    """Predicts maintenance task duration and confidence intervals."""
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.categorical_cols = ["department", "asset_type", "defect_category"]
        self.encoders = {col: LabelEncoder() for col in self.categorical_cols}
        
    def _preprocess(self, X: pd.DataFrame, training: bool = False) -> pd.DataFrame:
        X_proc = X.copy()
        
        # Select only relevant features if available
        features_to_use = self.categorical_cols + ["crew_size", "is_night_work", "weather_class"]
        
        # Some features might not be in basic X (like crew_size instead of crew_size_required)
        if "crew_size_required" in X_proc.columns and "crew_size" not in X_proc.columns:
            X_proc["crew_size"] = X_proc["crew_size_required"]
            
        if "is_night_work" not in X_proc.columns:
            X_proc["is_night_work"] = 0
            
        if "weather_class" not in X_proc.columns:
            X_proc["weather_class"] = 0
            
        # Keep only what's needed
        cols_present = [c for c in features_to_use if c in X_proc.columns]
        X_proc = X_proc[cols_present]
        
        for col in self.categorical_cols:
            if col in X_proc.columns:
                if training:
                    X_proc[col] = self.encoders[col].fit_transform(X_proc[col].astype(str))
                else:
                    classes = self.encoders[col].classes_
                    X_proc[col] = X_proc[col].map(lambda x: x if x in classes else classes[0])
                    X_proc[col] = self.encoders[col].transform(X_proc[col].astype(str))
        return X_proc

    def fit(self, X: pd.DataFrame, y: pd.Series):
        X_proc = self._preprocess(X, training=True)
        self.model.fit(X_proc, y)
        
    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predicts duration_hours, p25, p75."""
        X_proc = self._preprocess(X, training=False)
        
        # Predictions from all trees for quantiles
        preds_all_trees = np.array([tree.predict(X_proc.values) for tree in self.model.estimators_])
        
        duration_hours = np.mean(preds_all_trees, axis=0)
        p25 = np.percentile(preds_all_trees, 25, axis=0)
        p75 = np.percentile(preds_all_trees, 75, axis=0)
        
        return pd.DataFrame({
            "duration_hours": np.maximum(0, duration_hours),
            "p25": np.maximum(0, p25),
            "p75": np.maximum(0, p75)
        })
        
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
