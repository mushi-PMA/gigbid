import pandas as pd


def load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.drop_duplicates()
    frame["plan"] = frame["plan"].str.strip().str.title()
    frame["tenure_days"] = pd.to_numeric(frame["tenure_days"].str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    frame["region"] = pd.to_datetime(frame["region"], errors="coerce")
    missing = frame[["plan", "tenure_days"]].isna().any(axis=1)
    print(f"dropping {int(missing.sum())} rows with missing keys")
    return frame[~missing]


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.assign(month=frame["region"].dt.to_period("M"))
                 .groupby("month")["tenure_days"].agg(["count", "sum", "mean"]).reset_index())


if __name__ == "__main__":
    print(monthly_summary(clean(load("data/subscribers.csv"))).tail(12))
