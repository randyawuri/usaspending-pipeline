from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
TABLE = "stg_awards"


def run(con: duckdb.DuckDBPyConnection, label: str, sql: str) -> None:
    print(f"--- {label} ---")
    result = con.execute(sql).fetchdf()
    print(result.to_string(index=False))
    print()


if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))

    run(con, "Row count", f"SELECT COUNT(*) AS total_rows FROM {TABLE}")

    run(
        con,
        "Schema (types actually stuck)",
        f"DESCRIBE {TABLE}",
    )

    run(
        con,
        "Award amount summary",
        f"""
        SELECT
            MIN(award_amount) AS min_amount,
            MAX(award_amount) AS max_amount,
            ROUND(AVG(award_amount), 2) AS avg_amount,
            ROUND(SUM(award_amount), 2) AS total_amount
        FROM {TABLE}
        """,
    )

    run(
        con,
        "Date range covered",
        f"""
        SELECT
            MIN(start_date) AS earliest_start,
            MAX(start_date) AS latest_start,
            MIN(end_date) AS earliest_end,
            MAX(end_date) AS latest_end
        FROM {TABLE}
        """,
    )

    run(
        con,
        "Top 10 recipients by total award amount",
        f"""
        SELECT
            recipient_name,
            COUNT(*) AS num_awards,
            ROUND(SUM(award_amount), 2) AS total_amount
        FROM {TABLE}
        GROUP BY recipient_name
        ORDER BY total_amount DESC
        LIMIT 10
        """,
    )

    run(
        con,
        "Flagged (data quality) records",
        f"""
        SELECT award_uid, recipient_name, start_date, end_date, data_quality_flag
        FROM {TABLE}
        WHERE data_quality_flag IS NOT NULL
        """,
    )

    con.close()