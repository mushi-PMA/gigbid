import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def rfm_table(orders: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    grouped = orders.groupby("customer_id").agg(
        recency=("order_date", lambda d: (today - d.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("amount", "sum"),
    )
    return grouped


def segment(rfm: pd.DataFrame, clusters: int = 5) -> pd.DataFrame:
    scaled = StandardScaler().fit_transform(rfm.assign(monetary=rfm["monetary"].clip(upper=rfm["monetary"].quantile(0.99))))
    rfm = rfm.copy()
    rfm["segment"] = KMeans(n_clusters=clusters, n_init=10, random_state=3).fit_predict(scaled)
    return rfm.groupby("segment").agg(["mean", "count"]).round(1)
