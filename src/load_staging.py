import json
from pathlib import Path

import duckdb
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

STAGING_TABLE = "stg_awards"


def load_latest_raw_file() -> list[dict]:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {RAW_DIR}")
    latest = files[-1]
    print(f"Loading: {latest.name}")
    with open(latest) as f:
        return json.load(f)


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)

    # --- Type conversion ---------------------------------------------
    # Raw JSON gives us strings/floats with no guaranteed types.
    # Doing this once here means every downstream consumer of the
    # staging table can trust the types instead of re-parsing.
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    df["Award Amount"] = pd.to_numeric(df["Award Amount"], errors="coerce")

    # --- Data quality flag ---------------------------------------------
    df["data_quality_flag"] = None
    bad_dates = df["End Date"] < df["Start Date"]
    df.loc[bad_dates, "data_quality_flag"] = "end_date_before_start_date"

    # --- Column naming ---------------------------------------------
    df = df.rename(
        columns={
            "Award ID": "award_id",
            "Recipient Name": "recipient_name",
            "Award Amount": "award_amount",
            "Awarding Agency": "awarding_agency",
            "Awarding Sub Agency": "awarding_sub_agency",
            "Start Date": "start_date",
            "End Date": "end_date",
            "generated_internal_id": "award_uid",  # the real primary key
        }
    )

    # --- Drop pull-level metadata that isn't real per-row data --------
    df = df.drop(columns=["_requested_award_type_codes"], errors="ignore")

    return df


def load_to_duckdb(df: pd.DataFrame) -> None:
    con = duckdb.connect(str(DB_PATH))


    dupe_count = df["award_uid"].duplicated().sum()
    if dupe_count:
        raise ValueError(
            f"{dupe_count} duplicate award_uid values found — "
            f"run validate_raw.py and resolve before staging."
        )

    con.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE}")
    con.execute(f"CREATE TABLE {STAGING_TABLE} AS SELECT * FROM df")

    count = con.execute(f"SELECT COUNT(*) FROM {STAGING_TABLE}").fetchone()[0]
    flagged = con.execute(
        f"SELECT COUNT(*) FROM {STAGING_TABLE} WHERE data_quality_flag IS NOT NULL"
    ).fetchone()[0]

    print(f"Loaded {count} records into {STAGING_TABLE} ({DB_PATH})")
    print(f"  {flagged} record(s) carry a data_quality_flag")

    con.close()


if __name__ == "__main__":
    records = load_latest_raw_file()
    df = to_dataframe(records)
    load_to_duckdb(df)