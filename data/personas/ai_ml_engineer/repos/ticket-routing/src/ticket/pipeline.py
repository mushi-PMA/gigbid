import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TEXT_OR_CATEGORY = ["subject", "channel"]
NUMBERS = ["body_length"]


def build_pipeline() -> Pipeline:
    prepare = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore"), TEXT_OR_CATEGORY),
        ("numbers", StandardScaler(), NUMBERS),
    ])
    return Pipeline([("prepare", prepare), ("model", GradientBoostingClassifier(random_state=7))])


def run(path: str, target: str = "label") -> Pipeline:
    data = pd.read_csv(path).dropna(subset=[target])
    x_train, x_test, y_train, y_test = train_test_split(
        data.drop(columns=[target]), data[target], test_size=0.2, stratify=data[target], random_state=7)
    pipeline = build_pipeline().fit(x_train, y_train)
    print(classification_report(y_test, pipeline.predict(x_test)))
    return pipeline
