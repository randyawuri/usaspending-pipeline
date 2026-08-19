import json
import time
from pathlib import Path

import requests

# --- Config: change these to scope your pull -------------------------------

AGENCY_NAME = "National Aeronautics and Space Administration"


ACTIVITY_FISCAL_YEAR = 2023

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PAGE_LIMIT = 100  # max records per page the API will return


AWARD_TYPE_CODES = ["A", "B", "C", "D"]

# --- API details -------------------------------------------------------------

URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def build_payload(page: int) -> dict:
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
                    "date_type": "action_date",  
                    "start_date": f"{ACTIVITY_FISCAL_YEAR - 1}-10-01",
                    "end_date": f"{ACTIVITY_FISCAL_YEAR}-09-30",
                }
            ],
            "award_type_codes": AWARD_TYPE_CODES,
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Awarding Sub Agency",
            "Start Date",
            "End Date",
        ],
        "page": page,
        "limit": PAGE_LIMIT,
        "sort": "Award Amount",
        "order": "desc",
    }


def fetch_all_pages() -> list[dict]:
    """
    Pull every page of results for the given filters.
    """
    all_results = []
    page = 1

    while True:
        payload = build_payload(page)
        response = requests.post(URL, json=payload)
        response.raise_for_status()  

        data = response.json()
        results = data.get("results", [])

        for r in results:
            r["_requested_award_type_codes"] = AWARD_TYPE_CODES

        all_results.extend(results)

        has_next = data.get("page_metadata", {}).get("hasNext", False)
        print(f"Page {page}: pulled {len(results)} records (has_next={has_next})")

        if not has_next:
            break

        page += 1
        time.sleep(0.5)  

    return all_results


def save_raw(results: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"usaspending_{AGENCY_NAME.replace(' ', '_')}_{ACTIVITY_FISCAL_YEAR}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    return out_path


if __name__ == "__main__":
    print(f"Pulling awards for {AGENCY_NAME}, FY{ACTIVITY_FISCAL_YEAR}...")
    results = fetch_all_pages()
    print(f"Total records pulled: {len(results)}")

    out_path = save_raw(results)
    print(f"Saved raw data to {out_path}")