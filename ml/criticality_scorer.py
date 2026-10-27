import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier, XGBRegressor
import shap
from sklearn.preprocessing import LabelEncoder
from railopt.models import MaintenanceTask, ALWAYS_EMERGENCY, DefectSeverity, SAFETY_CRITICAL_DEFECTS

class CriticalityScorer:
    """Predicts severity class and 0-100 criticality score for a task."""
    def __init__(self):
        self.classifier = XGBClassifier(eval_metric='mlogloss', random_state=42)
        self.regressor = XGBRegressor(random_state=42)
        self.categorical_cols = ["department", "asset_type", "defect_category", "traffic_density_class", "season"]
        self.encoders = {col: LabelEncoder() for col in self.categorical_cols}
        self.target_encoder = LabelEncoder()
        
    def _preprocess(self, X: pd.DataFrame, training: bool = False) -> pd.DataFrame:
        X_proc = X.copy()
        if "task_id" in X_proc.columns:
            X_proc = X_proc.drop(columns=["task_id"])
            
        for col in self.categorical_cols:
            if col in X_proc.columns:
                if training:
                    X_proc[col] = self.encoders[col].fit_transform(X_proc[col].astype(str))
                else:
                    # Handle unseen labels gracefully
                    classes = self.encoders[col].classes_
                    X_proc[col] = X_proc[col].map(lambda x: x if x in classes else classes[0])
                    X_proc[col] = self.encoders[col].transform(X_proc[col].astype(str))
        return X_proc

    def fit(self, X: pd.DataFrame, y_class: pd.Series, y_score: pd.Series):
        """Fit models on extracted features."""
        X_proc = self._preprocess(X, training=True)
        y_class_encoded = self.target_encoder.fit_transform(y_class)
        
        self.classifier.fit(X_proc, y_class_encoded)
        self.regressor.fit(X_proc, y_score)
        
    def predict(self, X: pd.DataFrame, tasks: list[MaintenanceTask] = None) -> tuple[np.ndarray, np.ndarray]:
        """Predict severity class and score."""
        X_proc = self._preprocess(X, training=False)
        
        class_preds_encoded = self.classifier.predict(X_proc)
        class_preds = self.target_encoder.inverse_transform(class_preds_encoded)
        score_preds = self.regressor.predict(X_proc)
        score_preds = np.clip(score_preds, 0, 100)
        
        if tasks is not None:
            # Safety override
            for i, task in enumerate(tasks):
                if task.defect_category in ALWAYS_EMERGENCY:
                    class_preds[i] = DefectSeverity.EMERGENCY.value
                    score_preds[i] = max(95.0, score_preds[i])
                elif task.defect_category in SAFETY_CRITICAL_DEFECTS:
                    score_preds[i] = max(70.0, score_preds[i])
                    if class_preds[i] not in (DefectSeverity.EMERGENCY.value, DefectSeverity.HIGH.value):
                        class_preds[i] = DefectSeverity.HIGH.value
                    
        return class_preds, score_preds
        
    def explain(self, X: pd.DataFrame) -> list[dict[str, float]]:
        """Return SHAP values for predictions."""
        X_proc = self._preprocess(X, training=False)
        explainer = shap.TreeExplainer(self.regressor)
        shap_values = explainer.shap_values(X_proc)
        
        results = []
        for i in range(len(X_proc)):
            row_shap = {col: float(shap_values[i][j]) for j, col in enumerate(X_proc.columns)}
            results.append(row_shap)
        return results

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            "classifier": self.classifier,
            "regressor": self.regressor,
            "encoders": self.encoders,
            "target_encoder": self.target_encoder
        }, path)
        
    def load(self, path: str):
        data = joblib.load(path)
        self.classifier = data["classifier"]
        self.regressor = data["regressor"]
        self.encoders = data["encoders"]
        self.target_encoder = data["target_encoder"]
