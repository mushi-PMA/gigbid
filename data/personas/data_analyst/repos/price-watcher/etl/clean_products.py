import pandas as pd


def load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.drop_duplicates()
    frame["name"] = frame["name"].str.strip().str.title()
    frame["price"] = pd.to_numeric(frame["price"].str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    frame["competitor"] = pd.to_datetime(frame["competitor"], errors="coerce")
    missing = frame[["name", "price"]].isna().any(axis=1)
    print(f"dropping {int(missing.sum())} rows with missing keys")
    return frame[~missing]


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.assign(month=frame["competitor"].dt.to_period("M"))
                 .groupby("month")["price"].agg(["count", "sum", "mean"]).reset_index())


if __name__ == "__main__":
    print(monthly_summary(clean(load("data/products.csv"))).tail(12))
