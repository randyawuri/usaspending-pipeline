"""
Checks the TRUE total award count for our filters via
spending_by_award_count — a lightweight endpoint that returns counts
grouped by award type category, without paginating full records.

spending_by_award (what fetch_usaspending.py uses)
caps out at 10,000 results per query. This script tells us whether our
current pull (5,745 records) is the real, complete total, or a
truncated slice of something larger — before we build any workaround
for a problem we might not actually still have.
"""

import requests

URL = "https://api.usaspending.gov/api/v2/search/spending_by_award_count/"

AGENCY_NAME = "National Aeronautics and Space Administration"
ACTIVITY_FISCAL_YEAR = 2023


def build_payload() -> dict:
    return {
        "filters": {
            "agencies": [
                {
                    "type": "awarding",
                    "tier": "toptier",
                    "name": AGENCY_NAME,
                }
            ],
            "time_period": [
                {
                    "date_type": "action_date",  # match fetch_usaspending.py exactly
                    "start_date": f"{ACTIVITY_FISCAL_YEAR - 1}-10-01",
                    "end_date": f"{ACTIVITY_FISCAL_YEAR}-09-30",
                }
            ],
            "award_type_codes": ["A", "B", "C", "D"],
        }
    }


if __name__ == "__main__":
    payload = build_payload()
    response = requests.post(URL, json=payload)
    response.raise_for_status()
    data = response.json()

    print(f"True award counts for {AGENCY_NAME}, FY{ACTIVITY_FISCAL_YEAR} activity:\n")
    for category, count in data.get("results", {}).items():
        print(f"  {category:20s} {count}")

    contracts_total = data.get("results", {}).get("contracts")
    print(f"\nContracts total (our award_type_codes A-D scope): {contracts_total}")
    print("Records currently in data/raw pull: 5745")

    if contracts_total is not None:
        if contracts_total == 5745:
            print("\n✅ MATCH — the current pull is complete, not truncated.")
        else:
            print(
                f"\n⚠️  MISMATCH — true total is {contracts_total}, "
                f"pull has 5745. Missing {contracts_total - 5745} records."
            )