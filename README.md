# USAspending Pipeline

An end-to-end data pipeline that pulls federal contract spending data
from the [USAspending.gov API](https://api.usaspending.gov), validates
it, models it into a proper dimensional structure with dbt, and
orchestrates the whole thing with Airflow.

Built as a self-taught learning project — but more importantly, as a
record of a real investigation. The API's raw data looked clean at
first glance and wasn't: a silently null field, a date filter that
matched on the wrong thing, an ID that turned out not to be unique, and
a hard record cap that was easy to miss. Every one of those got found,
diagnosed, and fixed — and the reasoning behind each decision is
documented inline as it happened, not written up after the fact. See
**Design notes** below for the full story.

## Status

✅ Complete — raw ingestion, validation, dimensional modeling (dbt),
and orchestration (Airflow) all working end-to-end.

## Architecture

```
USAspending API
      │  (fetch_usaspending.py)
      ▼
raw JSON (data/raw/)
      │  (check_true_count.py, validate_raw.py — verify completeness & quality)
      │  (load_raw_to_duckdb.py — raw load, untransformed)
      ▼
raw_awards (DuckDB)
      │  (dbt: stg_awards — typing, renaming, quality flag)
      ▼
stg_awards
      │  (dbt: dimensional split)
      ▼
dim_recipients ─┐
dim_agencies ───┼──▶ fact_awards
      │
      ▼
dbt tests (uniqueness, not-null, referential integrity) — all passing

Orchestrated end-to-end by Airflow (dags/usaspending_pipeline_dag.py):
fetch → count-check → validate → load → dbt build
```

## What this project demonstrates

- **Investigating data instead of trusting it.** Several issues here
  (a null field, mismatched date semantics, a non-unique "unique" ID,
  a silent 10,000-record API cap) were invisible at a glance and only
  surfaced through systematic inspection — see Design notes for how
  each was found and resolved.
- **Deliberate, documented tradeoffs**, not just working code — e.g.
  flagging bad records instead of silently dropping them, and writing
  down *why* at the time the decision was made.
- **A real ingestion → validation → modeling → orchestration
  pipeline**, using the standard tools for each layer (Python for
  ingestion, dbt for transformation/testing, Airflow for
  orchestration) rather than one script doing everything.
- **Environment and tooling problems solved along the way** — a
  Python-version-related native extension crash, dbt path/schema
  resolution issues, and an Airflow dependency build failure — each
  diagnosed methodically rather than worked around blindly.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # fill in any values if/when needed
```

**Note on Python version**: use a stable release (3.11 or 3.12), not the
newest available. This project hit a segfault under Python 3.14 — likely
DuckDB/NumPy native-extension wheels not yet stable-built for a Python
version that new. Data pipeline dependencies generally lag behind the
latest Python release; pinning to one version behind latest is a
reasonable default, not just a workaround for this specific crash.

## Usage

Pull raw award data for a given agency and fiscal year:

```bash
python src/fetch_usaspending.py
```

Output lands in `data/raw/` as JSON (gitignored — not committed).

## Design notes / decisions

<!--
Use this section as you go to record *why* you made choices, not just what
they are. This is the part that actually demonstrates engineering judgment
to anyone reviewing the project later (including future you).

Example format:
### Why raw JSON before any database?
Keeping an unmodified raw layer means I can always re-derive the cleaned
data without re-hitting the API. Standard pattern in real pipelines
(raw → staged → modeled).
-->

### Why "Award Type" is excluded from the fields request

Confirmed by inspecting the raw output: `spending_by_award` returns `null`
for `Award Type` on every record, regardless of what's requested in the
`fields` array. This is a documented limitation of this specific endpoint,
not a bug in the request — some fields (Award Type, NAICS, obligation
amount, date signed, extent competed) simply aren't populated here and
require either per-award detail lookups or the `spending_by_transaction`
endpoint instead.

Rather than carry a dead null column, the field was dropped from the
request, and each record is tagged on ingestion with the
`award_type_codes` actually used in the filter
(`_requested_award_type_codes`) — a controlled substitute that reflects
what we asked for, since the API won't tell us what it returned.

### Why the pull uses `date_type: "action_date"` explicitly, and what that means

Initial inspection showed award `Start Date` values decades outside the
requested fiscal year (e.g. 1993 start dates in a "FY2023" pull). Root
cause: USAspending's `time_period` filter defaults to `action_date`,
which matches on an award's *latest transaction/modification* date —
not its original start date. A long-running award that simply received
a funding modification during FY2023 will match the filter even though
it began decades earlier.

This is set **explicitly** in the request (rather than relying on the
API's default) so the behavior is documented in code, not implied. The
fiscal year config variable is named `ACTIVITY_FISCAL_YEAR` rather than
a bare `FISCAL_YEAR` for the same reason — to keep it visible that this
pipeline captures **award activity during a fiscal year**, not **awards
that began in a fiscal year**. These are genuinely different datasets,
and conflating them would produce a model that looks correct but answers
the wrong question.

Worth noting for later: a documented USAspending API issue reports that
`action_date` filtering compares against a "latest action date" value
that can shift over time, which may make exact record counts for a
fixed historical date range slightly unstable if the pull is re-run
later. Not a concern for this project's current scope, but relevant if
the pipeline ever needs to reproduce an exact historical count.

### Why `generated_internal_id`, not `Award ID`, is the primary key

`inspect_raw.py` flagged 2 duplicate `Award ID` values. Pulling the full
records (via `investigate_flagged_records.py`) showed these are **not**
duplicates at all — they're distinct awards (different recipients,
amounts, and dates) that happen to share an `Award ID` string while
sitting under different parent IDV (indefinite delivery vehicle)
contracts. The difference only shows up in `generated_internal_id`,
which encodes the award ID *plus* its parent contract vehicle
(e.g. `CONT_AWD_80NSSC23FA621_8000_NNG15SD60B_8000` vs.
`..._NNG15SD42B_8000`).

Conclusion: `Award ID` alone is not a reliable unique key in this
dataset — it can be scoped to a parent contract vehicle rather than
globally unique. **`generated_internal_id` is the correct natural key**
going forward for any modeling, joins, or deduplication logic.

### Zero-dollar awards: expected pattern, one exception found

45 records in the FY2023 activity pull have `Award Amount == 0.0`.
Inspecting them directly, the large majority share a consistent shape:
a populated third segment in `generated_internal_id` (e.g. `NNG15SD60B`),
indicating these are individual delivery/task orders issued under a
larger IDV contract — a $0 value here is plausible as a legitimate
no-cost or not-yet-obligated order record, not a data error. Decision:
**keep these** rather than filtering them out, since they appear to be
real (if unusual) records.

One record in this set surfaced a separate, genuine data quality issue
unrelated to the zero-dollar pattern: Award ID `80KSC023F0006` has
`End Date` (2022-11-17) **before** `Start Date` (2022-11-21) — not
explainable by the IDV structure above. See `validate_raw.py`, added
to systematically check for this and similar issues across the full
dataset rather than relying on spot-checks.

### Date-order validation result, and the flag-don't-drop decision

Running `validate_raw.py` against the full FY2023 pull (5,745 records)
found **3** records with `End Date` before `Start Date` — 3x more than
the single record caught by manual spot-checking, which is the reason
this check exists as an automated, permanent rule rather than a one-off
fix. All 3 have small gaps (days, not years) between the two dates,
suggesting a source data entry issue rather than a systemic bug in this
pipeline's date handling.

Decision: **flag, don't drop.** `load_staging.py` adds a
`data_quality_flag` column to the staging table rather than excluding
these records outright. Reasoning: the rest of each record (recipient,
amount, agency) may still be legitimate and useful, and silently
dropping data hides information from anyone building on top of this
model later. Downstream consumers (dashboards, further modeling) can
filter on `data_quality_flag IS NULL` themselves if they want only
clean records — the choice is preserved, not made for them.

## Data validation

`src/validate_raw.py` runs automated checks against the raw pull and
reports issues found (does not modify data). Current checks:

- `generated_internal_id` uniqueness (the real primary key — see
  design notes above)
- `End Date` before `Start Date` (found via manual inspection; now
  checked systematically)
- `Award Amount` negative values (not yet found, but not yet ruled out
  either — worth checking every pull)

Run after every fetch, before treating a pull as ready for modeling:

```bash
python src/fetch_usaspending.py
python src/validate_raw.py
```

## Pipeline stages

1. **`fetch_usaspending.py`** — raw ingestion from the USAspending API,
   saved unmodified to `data/raw/*.json`.
2. **`validate_raw.py`** — reports data quality issues against the raw
   pull. Read-only; doesn't fix anything.
3. **`load_raw_to_duckdb.py`** — loads raw JSON into DuckDB
   **untransformed** (table `raw_awards`). Python's job stops here —
   fetch, validate, get raw data into the warehouse.
4. **dbt** (`dbt/` directory) — everything from `raw_awards` onward:
   typing, renaming, the data-quality flag, and the dimensional model
   (`stg_awards` → `dim_recipients` / `dim_agencies` / `fact_awards`).

Run the full chain:
```bash
python src/fetch_usaspending.py
python src/check_true_count.py                                # confirm the pull is complete, not capped
python src/validate_raw.py                                    # review before proceeding
python src/load_raw_to_duckdb.py
cd dbt && dbt build --profiles-dir . && cd ..
```

`dbt build` runs every model **and** every test in dependency order —
stg_awards, then the dimension tables, then fact_awards, failing loudly
if any test fails rather than silently producing bad output.

### Why the transformation logic moved from Python to dbt

`load_staging.py` and `build_dimensional_model.py` (still in `src/`
for reference) originally hand-wrote in pandas/SQL exactly what dbt
is built to manage: typing, renaming, the quality flag, and the
fact/dimension split. Writing it by hand first was deliberate — it
made the reasoning behind each transformation concrete (see the design
notes throughout this README) before handing the mechanics to a tool
built for it.

What dbt adds that the hand-written version didn't have for free:
- **Tests as configuration, not one-off scripts.** The manual checks
  in `validate_raw.py` (uniqueness, the join-integrity check in
  `build_dimensional_model.py`) are now `unique`, `not_null`, and
  `relationships` tests in `dbt/models/marts/schema.yml`, plus a
  singular test for negative amounts. `dbt build` runs all of them
  automatically, every time — nothing relies on remembering to run a
  separate script.
- **Lineage and documentation.** `dbt docs generate` produces a
  browsable dependency graph showing exactly how `fact_awards` derives
  from `stg_awards` derives from `raw_awards` — useful both for this
  project and as a directly transferable skill to real dbt projects.
- **Materialization control.** Staging models are views (cheap, always
  reflect the latest raw load); marts are tables (materialized once,
  fast to query) — a standard dbt convention, configured in
  `dbt_project.yml` rather than decided ad hoc per script.

### Why dimensional modeling, at this scale

`stg_awards` alone already "works" for 5,745 rows — a flat table in
DuckDB handles that fine. Splitting into `dim_recipients` /
`dim_agencies` / `fact_awards` isn't solving a performance problem this
dataset has yet; it's practicing the structure real analytics warehouses
use, and it does buy real things even here:

- Recipient- or agency-level attributes (e.g. a future "recipient
  industry" or "agency budget" lookup) attach to the dimension table
  once, instead of being duplicated across every award row.
- `fact_awards` stays lean — just keys and measures — which is the
  standard shape for a fact table and makes aggregation queries
  (totals by recipient, by agency, etc.) cheap and obvious.
- The join-integrity risk (a fact row failing to resolve to a
  dimension key) is now covered by dbt's `relationships` test instead
  of a one-off Python check — same safeguard, enforced automatically
  on every build.

## Orchestration (Airflow)

The full chain (fetch → count-check → validate → load → dbt build) is
orchestrated as a single Airflow DAG (`dags/usaspending_pipeline_dag.py`)
instead of being run as a manual sequence of commands.

### Why Airflow gets its own venv

Airflow has a large, tightly-pinned dependency tree that regularly
conflicts with other Python packages. Rather than install it into the
main project venv (risking dependency conflicts with dbt-core, duckdb,
pandas), it lives in a **separate** venv. Each Airflow task then shells
out to the *project's* venv (its Python interpreter, its dbt binary) as
a subprocess — Airflow orchestrates, but doesn't do the actual work in
its own environment. This is a standard real-world pattern, not just a
workaround for this project.

### Setup

```bash
# 1. Separate venv for Airflow only
python3.12 -m venv airflow_venv
source airflow_venv/bin/activate
pip install "apache-airflow==3.3.1" --constraint \
  "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.1/constraints-3.12.txt"

# 2. Point Airflow at this project's dags/ folder and a local AIRFLOW_HOME
#    (keeps everything self-contained inside the project, same reasoning
#    as dbt's local profiles.yml)
export AIRFLOW_HOME=$(pwd)/airflow_home
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/dags

# 3. Tell the DAG where the *project* venv lives (used to invoke
#    the actual pipeline scripts and dbt — see dags/usaspending_pipeline_dag.py)
export USASPENDING_PROJECT_ROOT=$(pwd)

# 4. Start Airflow (webserver + scheduler in one process — fine for
#    local/learning use; not how you'd run it in production)
airflow standalone
```

`airflow standalone` prints an admin username/password on first run —
log into the UI (usually `http://localhost:8080`), find `usaspending_pipeline`
in the DAG list, and trigger it manually (the DAG has `schedule=None` —
see design notes in the DAG file for why).

### Design notes

- **`schedule=None`**: this pipeline pulls a fixed historical fiscal
  year, not a rolling/live window — there's no natural "run every day"
  cadence for FY2023 data that won't change. A pipeline pulling a
  rolling window (e.g. "last 30 days of activity") would use a real
  schedule (`@daily`, etc.) instead; noted in the DAG file so the
  choice reads as deliberate, not an oversight.
- **`validate_raw` doesn't hard-fail the DAG.** The script always exits
  0 — it's a reporting step. The known `end_date < start_date` issue is
  already handled downstream via the `data_quality_flag` column (see
  design notes above), so it shouldn't halt the pipeline. A more
  mature version of this DAG would likely split validation into a
  hard-fail branch (primary key uniqueness, negative amounts — genuine
  blockers) and a soft-warn branch (known, already-handled issues) —
  noted as a real next improvement rather than an oversight.
- **`retries=1` / `retry_delay=2min`** on every task — a basic,
  deliberate resilience choice given this hits an external API and
  a local database; not tuned further since this project doesn't yet
  have failure patterns to tune against.

## Known limitations

- **`spending_by_award` does not populate several expected fields**
  (Award Type, NAICS, obligation amount, date signed, extent competed)
  regardless of the `fields` requested. If the model eventually needs
  these, the pipeline will need to add per-award detail lookups or
  switch to `spending_by_transaction` for the relevant fields.
- **Inconsistent field naming in the API response.** Search endpoints
  mix capitalized/spaced keys (`"Award ID"`) with lowercase snake_case
  keys (`internal_id`, `generated_internal_id`) in the *same* response
  object. Worth normalizing during the cleaning/staging step rather
  than carrying both conventions downstream.
- **Result set may be capped.** A pull returned exactly 10,000
  records, a suspiciously round number. Confirmed: the paginated
  search endpoints cap out at 10,000 records per query as a practical
  limit. For agency/date-range combinations that may exceed this,
  the pipeline will need to use the bulk download endpoint
  (`POST /api/v2/download/awards/`) instead — not yet implemented.
  **Update:** re-checked after the `date_type` fix (see design notes)
  using `spending_by_award_count`, a lightweight endpoint that returns
  the true total independent of pagination. For the current scope
  (NASA, FY2023 activity, contracts A–D), the true total is exactly
  5,745 — matching the pull exactly. The cap was real, but this
  specific pull is not truncated; the earlier `date_type` fix appears
  to have resolved it as a side effect, confirmed rather than assumed.
  **This will not hold for every future pull** — a larger agency,
  wider date range, or broader award-type scope could still exceed
  10,000. Before trusting any new pull as complete, run
  `check_true_count.py` first (or add it as a standard pre-fetch step)
  rather than assuming this result generalizes.

## Project structure

```
├── src/                # ingestion + validation (Python)
├── dbt/                # transformation + modeling (dbt)
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/    # stg_awards, sources.yml
│   │   └── marts/      # dim_recipients, dim_agencies, fact_awards, schema.yml
│   └── tests/          # singular tests (e.g. no_negative_award_amounts.sql)
├── dags/                # Airflow DAG orchestrating the full chain
│   └── usaspending_pipeline_dag.py
├── data/raw/            # raw pulled data (gitignored)
├── notebooks/           # scratch exploration, not production code
├── tests/               # tests for Python pipeline logic
├── requirements.txt          # main project deps (fetch/validate/load + dbt)
├── requirements-airflow.txt  # Airflow deps — separate venv, see "Orchestration"
└── .env.example
```