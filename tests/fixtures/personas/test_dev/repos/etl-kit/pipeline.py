from airflow import DAG


def load_sales(store_ids):
    """Load daily sales for each store into the warehouse with an upsert."""
    for store in store_ids:
        upsert("sales", fetch(store))
