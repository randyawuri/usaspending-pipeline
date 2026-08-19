import json
from collections import Counter
from datetime import datetime
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_latest_raw_file() -> list[dict]:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {RAW_DIR}")
    latest = files[-1]
    print(f"Validating: {latest.name}\n")
    with open(latest) as f:
        return json.load(f)


def check_primary_key_uniqueness(records: list[dict]) -> list[str]:
    """
    generated_internal_id is the real primary key (see README design
    notes — Award ID alone was found NOT to be unique: it can be
    scoped to a parent IDV contract rather than globally unique).
    """
    issues = []
    ids = [r.get("generated_internal_id") for r in records]
    dupes = [item for item, count in Counter(ids).items() if count > 1]
    if dupes:
        issues.append(
            f"{len(dupes)} duplicate generated_internal_id value(s) found: {dupes[:5]}"
        )
    return issues


def check_date_order(records: list[dict]) -> list[str]:
    """
    End Date should never be before Start Date. Found via manual
    inspection (Award ID 80KSC023F0006); now checked systematically
    across every record.
    """
    issues = []
    bad_records = []
    for r in records:
        start_str = r.get("Start Date")
        end_str = r.get("End Date")
        if not start_str or not end_str:
            continue
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d")
            end = datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            issues.append(
                f"Unparseable date on {r.get('generated_internal_id')}: "
                f"Start={start_str!r} End={end_str!r}"
            )
            continue
        if end < start:
            bad_records.append(
                (r.get("generated_internal_id"), start_str, end_str)
            )

    if bad_records:
        issues.append(f"{len(bad_records)} record(s) with End Date before Start Date:")
        for gid, start_str, end_str in bad_records:
            issues.append(f"    {gid}: Start={start_str} End={end_str}")

    return issues


def check_negative_amounts(records: list[dict]) -> list[str]:
    """
    Award Amount shouldn't be negative. Not yet found in any pull,
    but not yet ruled out either — worth checking every time rather
    than assuming past absence means future absence.
    """
    issues = []
    negative = [r for r in records if (r.get("Award Amount") or 0) < 0]
    if negative:
        issues.append(f"{len(negative)} record(s) with negative Award Amount:")
        for r in negative[:5]:
            issues.append(
                f"    {r.get('generated_internal_id')}: {r.get('Award Amount')}"
            )
    return issues


def run_all_checks(records: list[dict]) -> None:
    checks = [
        ("Primary key uniqueness (generated_internal_id)", check_primary_key_uniqueness),
        ("Date order (End Date >= Start Date)", check_date_order),
        ("Negative Award Amount", check_negative_amounts),
    ]

    total_issues = 0
    for name, check_fn in checks:
        issues = check_fn(records)
        status = "FAIL" if issues else "PASS"
        print(f"[{status}] {name}")
        for issue in issues:
            print(f"    {issue}")
        total_issues += len(issues)
        print()

    print(f"{'='*50}")
    if total_issues:
        print(f"{total_issues} issue(s) found. Review before modeling.")
    else:
        print("All checks passed.")


if __name__ == "__main__":
    records = load_latest_raw_file()
    print(f"Total records: {len(records)}\n")
    run_all_checks(records)