"""
Reads PMT_Live_Reporting-YTD_Projects.csv, cleans the data, and bulk ingests
into the pmt_live_reporting Elasticsearch index.

Run create_index.py first to set up the index mapping.
"""

import os
import re
import pandas as pd
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

load_dotenv()

INDEX_NAME = "pmt_live_reporting"
CSV_FILE = "PMT_Live_Reporting-YTD_Projects.csv"
BATCH_SIZE = 500

# Map CSV column names to clean snake_case field names
COLUMN_MAP = {
    "Deal Support Request Number":              "dsr_number",
    "Deal Support Request ID":                  "dsr_id",
    "Opportunity Geo":                          "geo",
    "Opportunity Name":                         "opportunity_name",
    "Opportunity Owner":                        "opportunity_owner",
    "Opportunity Solution":                     "solution",
    "Opportunity: ACV (converted)":             "acv_converted",
    "Opportunity Amount":                       "opportunity_amount",
    "Opportunity Close Date":                   "close_date",
    "Request Type":                             "request_type",
    "Opportunity Stage":                        "stage",
    "Closed Date":                              "closed_date",
    "Opportunity: Opportunity N&E":             "nne",
    "Opportunity: ACV":                         "acv",
    "Opportunity: Opportunity N&E (converted)": "nne_converted",
    "Opportunity: RVP":                         "rvp",
    "Opportunity: Area Leader":                 "area_leader",
    "Status":                                   "status",
    "Created By: Full Name":                    "created_by",
    "Created Date":                             "created_date",
    "Record Type":                              "record_type",
    "Opportunity: Territory Level 1":           "territory_level_1",
    "Opportunity: Territory Level 2":           "territory_level_2",
    "Opportunity: Territory Level 3":           "territory_level_3",
    "Quarter Completed":                        "quarter_completed",
    "Deal Close Quarter":                       "deal_close_quarter",
}

REVENUE_FIELDS = ["acv_converted", "opportunity_amount", "acv", "nne", "nne_converted"]
DATE_FIELDS = ["created_date", "close_date", "closed_date"]


def clean_currency(value):
    """Strip $, commas, and whitespace; return float or None."""
    if pd.isna(value) or str(value).strip() in ("", "$0.00", "$0"):
        return None
    cleaned = re.sub(r"[\$,\s]", "", str(value))
    try:
        result = float(cleaned)
        return result if result != 0.0 else None
    except ValueError:
        return None


def clean_date(value):
    """Return date string as-is if non-empty, else None. ES handles M/d/yyyy format."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    return str(value).strip()


def clean_keyword(value):
    """Return stripped string or None if empty/placeholder."""
    if pd.isna(value):
        return None
    val = str(value).strip()
    # Drop obvious placeholder values
    if val == "" or "Placeholder" in val or val == "GLOBAL_UNALLOCATED":
        return None
    return val


def transform_row(row):
    """Transform a raw CSV row into a clean Elasticsearch document."""
    doc = {}

    for field, value in row.items():
        if field in REVENUE_FIELDS:
            doc[field] = clean_currency(value)
        elif field in DATE_FIELDS:
            doc[field] = clean_date(value)
        else:
            doc[field] = clean_keyword(value)

    return doc


def generate_actions(df):
    """Yield bulk action dicts for each row."""
    for _, row in df.iterrows():
        doc = transform_row(row)
        dsr_number = doc.get("dsr_number")

        yield {
            "_index": INDEX_NAME,
            "_id": dsr_number,  # idempotent: re-running won't create duplicates
            "_source": doc,
        }


def get_client():
    return Elasticsearch(
        os.environ["ELASTICSEARCH_URL"],
        api_key=os.environ["ELASTICSEARCH_API_KEY"],
    )


def ingest():
    print(f"Reading {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    print(f"  {len(df)} rows found.")

    # Rename columns
    df = df.rename(columns=COLUMN_MAP)

    # Drop any columns not in our mapping
    known_fields = list(COLUMN_MAP.values())
    df = df[[col for col in known_fields if col in df.columns]]

    es = get_client()

    # Verify index exists
    if not es.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' does not exist. Run create_index.py first.")
        return

    print(f"Ingesting into '{INDEX_NAME}' in batches of {BATCH_SIZE}...")
    success, errors = bulk(es, generate_actions(df), chunk_size=BATCH_SIZE, raise_on_error=False)

    print(f"  Ingested: {success} documents")
    if errors:
        print(f"  Errors:   {len(errors)}")
        for err in errors[:5]:
            print(f"    {err}")

    print("Done.")


if __name__ == "__main__":
    ingest()
