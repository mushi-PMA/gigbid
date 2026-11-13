import pandas as pd
import xgboost as xgb


def add_lags(frame: pd.DataFrame, target: str, lags=(1, 7, 14, 28)) -> pd.DataFrame:
    frame = frame.sort_values(["store_id", "date"]).copy()
    for lag in lags:
        frame[f"{target}_lag_{lag}"] = frame.groupby("store_id")[target].shift(lag)
    frame[f"{target}_roll_7"] = frame.groupby("store_id")[target].transform(lambda s: s.shift(1).rolling(7).mean())
    frame["dow"] = frame["date"].dt.dayofweek
    frame["month"] = frame["date"].dt.month
    return frame.dropna()


def fit_forecaster(frame: pd.DataFrame, target: str, cutoff: str):
    features = [c for c in frame.columns if c.startswith(target + "_") or c in ("dow", "month")]
    train, valid = frame[frame["date"] < cutoff], frame[frame["date"] >= cutoff]
    model = xgb.XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=6, subsample=0.8)
    model.fit(train[features], train[target], eval_set=[(valid[features], valid[target])], verbose=False)
    error = (model.predict(valid[features]) - valid[target]).abs().mean()
    print(f"validation MAE: {error:.2f}")
    return model
