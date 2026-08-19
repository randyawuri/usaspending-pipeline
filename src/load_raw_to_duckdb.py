import json
from pathlib import Path

import duckdb
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

RAW_TABLE = "raw_awards"


def load_latest_raw_file() -> list[dict]:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {RAW_DIR}")
    latest = files[-1]
    print(f"Loading: {latest.name}")
    with open(latest) as f:
        return json.load(f)


def load_raw_to_duckdb(records: list[dict]) -> None:
    df = pd.DataFrame(records)  # deliberately untransformed — raw in, raw stored

    con = duckdb.connect(str(DB_PATH))
    con.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")
    con.execute(f"CREATE TABLE {RAW_TABLE} AS SELECT * FROM df")

    count = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
    print(f"Loaded {count} raw records into {RAW_TABLE} ({DB_PATH})")

    con.close()


if __name__ == "__main__":
    records = load_latest_raw_file()
    load_raw_to_duckdb(records)