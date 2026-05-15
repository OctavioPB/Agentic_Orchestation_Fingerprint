"""Airflow DAG: orchid_etl — extract → transform → load pipeline."""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG(
    dag_id="orchid_etl",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    extract_task = PythonOperator(
        task_id="extract",
        python_callable=lambda: print("extracting"),
    )
    transform_task = PythonOperator(
        task_id="transform",
        python_callable=lambda: print("transforming"),
    )
    load_task = PythonOperator(
        task_id="load",
        python_callable=lambda: print("loading"),
    )

    extract_task >> transform_task >> load_task
    load_task >> extract_task  # BUG: creates cycle extract→transform→load→extract
