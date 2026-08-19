"""
Orchestrates the full pipeline as a single Airflow DAG:

    fetch -> check_true_count -> validate -> load_raw -> dbt_build

Each task shells out to the PROJECT venv's Python (or dbt binary) —
Airflow itself runs in its own separate venv (see requirements-airflow.txt
and README "Orchestration"). This mirrors a common real-world pattern:
the orchestrator's environment and the environment that does the actual
work are deliberately kept separate.

Set USASPENDING_PROJECT_ROOT before starting Airflow so these tasks can
find the right venv and scripts, e.g.:

    export USASPENDING_PROJECT_ROOT=/Users/you/path/to/usaspending-pipeline

Known limitation (documented, not accidental): validate_raw.py always
exits 0 — it's a reporting step, not a hard gate. In a more mature
pipeline you'd likely split it into a hard-fail check (e.g. primary key
uniqueness, negative amounts — genuine blockers) and a soft-warn check
(the known end_date/start_date issue, which is already handled
downstream via the data_quality_flag column, not something that should
halt the pipeline). Worth revisiting if this pipeline grows.
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = os.environ.get(
    "USASPENDING_PROJECT_ROOT",
    "/CHANGE_ME/usaspending-pipeline",  # overridden via env var — see docstring
)
VENV_PYTHON = f"{PROJECT_ROOT}/venv/bin/python3"
VENV_DBT = f"{PROJECT_ROOT}/venv/bin/dbt"

default_args = {
    "owner": "randy",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="usaspending_pipeline",
    description="Fetch, validate, and model NASA award spending data end-to-end",
    default_args=default_args,
    schedule=None,  # manually triggered — this pulls a fixed historical
                     # fiscal year, not a rolling window, so there's no
                     # natural "run every day" cadence. A live/rolling
                     # pull would instead use e.g. schedule="@daily".
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["usaspending", "portfolio"],
) as dag:

    fetch = BashOperator(
        task_id="fetch_usaspending",
        bash_command=f"{VENV_PYTHON} {PROJECT_ROOT}/src/fetch_usaspending.py",
    )

    check_true_count = BashOperator(
        task_id="check_true_count",
        bash_command=f"{VENV_PYTHON} {PROJECT_ROOT}/src/check_true_count.py",
    )

    validate_raw = BashOperator(
        task_id="validate_raw",
        bash_command=f"{VENV_PYTHON} {PROJECT_ROOT}/src/validate_raw.py",
    )

    load_raw = BashOperator(
        task_id="load_raw_to_duckdb",
        bash_command=f"{VENV_PYTHON} {PROJECT_ROOT}/src/load_raw_to_duckdb.py",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {PROJECT_ROOT}/dbt && {VENV_DBT} build --profiles-dir .",
    )

    fetch >> check_true_count >> validate_raw >> load_raw >> dbt_build