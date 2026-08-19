from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"


def build_dim_recipients(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS dim_recipients")
    con.execute(
        """
        CREATE TABLE dim_recipients AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY recipient_name) AS recipient_id,
            recipient_name
        FROM (
            SELECT DISTINCT recipient_name
            FROM stg_awards
            WHERE recipient_name IS NOT NULL
        )
        """
    )
    count = con.execute("SELECT COUNT(*) FROM dim_recipients").fetchone()[0]
    print(f"dim_recipients: {count} unique recipients")


def build_dim_agencies(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS dim_agencies")
    con.execute(
        """
        CREATE TABLE dim_agencies AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY awarding_agency, awarding_sub_agency) AS agency_id,
            awarding_agency,
            awarding_sub_agency
        FROM (
            SELECT DISTINCT awarding_agency, awarding_sub_agency
            FROM stg_awards
            WHERE awarding_agency IS NOT NULL
        )
        """
    )
    count = con.execute("SELECT COUNT(*) FROM dim_agencies").fetchone()[0]
    print(f"dim_agencies: {count} unique agency/sub-agency pairs")


def build_fact_awards(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS fact_awards")
    con.execute(
        """
        CREATE TABLE fact_awards AS
        SELECT
            s.award_uid,
            s.award_id,
            r.recipient_id,
            a.agency_id,
            s.award_amount,
            s.start_date,
            s.end_date,
            s.data_quality_flag
        FROM stg_awards s
        LEFT JOIN dim_recipients r ON s.recipient_name = r.recipient_name
        LEFT JOIN dim_agencies a
            ON s.awarding_agency = a.awarding_agency
            AND s.awarding_sub_agency = a.awarding_sub_agency
        """
    )
    count = con.execute("SELECT COUNT(*) FROM fact_awards").fetchone()[0]
    print(f"fact_awards: {count} rows")

    # Sanity check: did every row successfully resolve to a dimension key?
    # If not, something's wrong with the join — silent nulls here would
    # quietly break any downstream aggregation by recipient or agency.
    unmatched = con.execute(
        """
        SELECT COUNT(*) FROM fact_awards
        WHERE recipient_id IS NULL OR agency_id IS NULL
        """
    ).fetchone()[0]
    if unmatched:
        print(f"  WARNING: {unmatched} row(s) failed to join to a dimension key")
    else:
        print("  All rows resolved to valid recipient_id and agency_id")


if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))

    build_dim_recipients(con)
    build_dim_agencies(con)
    build_fact_awards(con)

    con.close()