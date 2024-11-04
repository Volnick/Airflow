import os
import pandas as pd
from datetime import datetime
from airflow.models import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable


def process_output(**kwargs):
    ti = kwargs['ti']
    date_output = ti.xcom_pull(task_ids='get_datetime')
    # Hier können Sie die Ausgabe weiterverarbeiten oder verwenden
    print("Ausgabe des Datums: ", date_output)

with DAG(
    dag_id='first_airflow_dag',
    schedule_interval='* * * * *',
    start_date=datetime(year=2024, month=3, day=22),
    catchup=False
) as dag:
    task_get_datetime = BashOperator(
        task_id='get_datetime',
        bash_command='date',
    )

    task_process_output = PythonOperator(
        task_id='process_output',
        python_callable=process_output,
        provide_context=True
    )

    task_get_datetime >> task_process_output