import pandas as pd


def load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.drop_duplicates()
    frame["customer_id"] = frame["customer_id"].str.strip().str.title()
    frame["amount"] = pd.to_numeric(frame["amount"].str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce")
    missing = frame[["customer_id", "amount"]].isna().any(axis=1)
    print(f"dropping {int(missing.sum())} rows with missing keys")
    return frame[~missing]


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.assign(month=frame["order_date"].dt.to_period("M"))
                 .groupby("month")["amount"].agg(["count", "sum", "mean"]).reset_index())


if __name__ == "__main__":
    print(monthly_summary(clean(load("data/orders.csv"))).tail(12))
