import json
from collections import Counter
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_latest_raw_file() -> list[dict]:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {RAW_DIR}")
    latest = files[-1]
    print(f"Inspecting: {latest.name}\n")
    with open(latest) as f:
        return json.load(f)


def inspect(records: list[dict]) -> None:
    print(f"Total records: {len(records)}\n")

    if not records:
        print("No records to inspect.")
        return

    # 1. What fields actually exist, and how consistently?
    all_keys = Counter()
    for r in records:
        all_keys.update(r.keys())
    print("Field presence (out of total records):")
    for key, count in all_keys.most_common():
        pct = 100 * count / len(records)
        print(f"  {key:30s} {count:6d}  ({pct:.1f}%)")
    print()

    # 2. Null / empty check per field
    print("Null or empty values per field:")
    sample_fields = list(records[0].keys())
    for field in sample_fields:
        null_count = sum(
            1 for r in records if r.get(field) in (None, "", "None")
        )
        if null_count:
            pct = 100 * null_count / len(records)
            print(f"  {field:30s} {null_count:6d} null/empty  ({pct:.1f}%)")
    print()

    # 3. Duplicate check on the natural key
    award_ids = [r.get("Award ID") for r in records]
    dupes = [item for item, count in Counter(award_ids).items() if count > 1]
    print(f"Duplicate Award IDs: {len(dupes)}")
    if dupes[:3]:
        print(f"  Example duplicates: {dupes[:3]}")
    print()

    # 4. Recipient name consistency (common source of messiness)
    recipient_names = [r.get("Recipient Name") for r in records if r.get("Recipient Name")]
    unique_recipients = set(recipient_names)
    print(f"Unique recipient names: {len(unique_recipients)} (out of {len(recipient_names)} non-null)")
    # crude check: same recipient, different casing/whitespace
    normalized = Counter(n.strip().upper() for n in recipient_names)
    raw_variants = Counter(recipient_names)
    if len(normalized) < len(raw_variants):
        print(f"  → {len(raw_variants) - len(normalized)} likely casing/whitespace duplicates")
    print()

    # 5. Award Amount sanity check
    amounts = []
    bad_amounts = []
    for r in records:
        val = r.get("Award Amount")
        try:
            amounts.append(float(val))
        except (TypeError, ValueError):
            bad_amounts.append(val)
    if amounts:
        print(f"Award Amount — min: {min(amounts):,.2f}  max: {max(amounts):,.2f}")
    if bad_amounts:
        print(f"Non-numeric Award Amount values: {len(bad_amounts)}  e.g. {bad_amounts[:3]}")
    print()

    # 6. Date field spot-check
    for date_field in ["Start Date", "End Date"]:
        sample_dates = [r.get(date_field) for r in records[:5]]
        print(f"{date_field} sample values: {sample_dates}")


if __name__ == "__main__":
    records = load_latest_raw_file()
    inspect(records)