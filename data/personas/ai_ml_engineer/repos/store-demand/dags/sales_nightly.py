from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from sales.jobs import extract_source, rebuild_features, publish_table

default_args = {"owner": "data", "retries": 2, "retry_delay": timedelta(minutes=10)}

with DAG(
    dag_id="sales_nightly",
    start_date=datetime(2025, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    default_args=default_args,
) as dag:
    extract = PythonOperator(task_id="extract_source", python_callable=extract_source)
    features = PythonOperator(task_id="rebuild_features", python_callable=rebuild_features)
    publish = PythonOperator(task_id="publish_table", python_callable=publish_table)
    extract >> features >> publish
