import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DUPLICATE_IDS_TO_CHECK = ["80NSSC23FA621", "80NSSC23FA536"]


def load_latest_raw_file() -> list[dict]:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {RAW_DIR}")
    latest = files[-1]
    print(f"Inspecting: {latest.name}\n")
    with open(latest) as f:
        return json.load(f)


def show_zero_dollar_awards(records: list[dict]) -> None:
    zero_awards = [r for r in records if r.get("Award Amount") == 0]
    print(f"=== Zero-dollar awards: {len(zero_awards)} found ===\n")
    for r in zero_awards:
        print(json.dumps(r, indent=2))
        print()


def show_duplicate_records(records: list[dict], award_ids: list[str]) -> None:
    print("=== Duplicate Award ID records ===\n")
    for target_id in award_ids:
        matches = [r for r in records if r.get("Award ID") == target_id]
        print(f"Award ID {target_id}: {len(matches)} matching record(s)\n")
        for i, r in enumerate(matches):
            print(f"--- Record {i + 1} ---")
            print(json.dumps(r, indent=2))
            print()

        # Quick diff hint: are the records byte-for-byte identical,
        # or do they differ in some field?
        if len(matches) > 1:
            unique_serialized = {json.dumps(r, sort_keys=True) for r in matches}
            if len(unique_serialized) == 1:
                print(f"  → All {len(matches)} records for {target_id} are IDENTICAL.\n")
            else:
                print(f"  → Records for {target_id} DIFFER — not a simple duplicate.\n")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    records = load_latest_raw_file()
    show_zero_dollar_awards(records)
    show_duplicate_records(records, DUPLICATE_IDS_TO_CHECK)