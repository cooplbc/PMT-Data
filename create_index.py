"""
Creates the pmt_live_reporting index in Elasticsearch with proper field mappings.
Run this once before ingesting data.
"""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

INDEX_NAME = "pmt_live_reporting"

MAPPING = {
    "mappings": {
        "properties": {
            # Identifiers
            "dsr_number":           {"type": "keyword"},
            "dsr_id":               {"type": "keyword"},

            # Geography / Territory
            "geo":                  {"type": "keyword"},
            "territory_level_1":    {"type": "keyword"},
            "territory_level_2":    {"type": "keyword"},
            "territory_level_3":    {"type": "keyword"},

            # Deal classification
            "solution":             {"type": "keyword"},
            "request_type":         {"type": "keyword"},
            "status":               {"type": "keyword"},
            "stage":                {"type": "keyword"},
            "record_type":          {"type": "keyword"},

            # People
            "opportunity_name":     {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "opportunity_owner":    {"type": "keyword"},
            "rvp":                  {"type": "keyword"},
            "area_leader":          {"type": "keyword"},
            "created_by":           {"type": "keyword"},

            # Revenue (all stored as doubles, nulls for missing)
            "acv_converted":        {"type": "double"},
            "opportunity_amount":   {"type": "double"},
            "acv":                  {"type": "double"},
            "nne":                  {"type": "double"},
            "nne_converted":        {"type": "double"},

            # Dates
            "created_date":         {"type": "date", "format": "M/d/yyyy||yyyy-MM-dd"},
            "close_date":           {"type": "date", "format": "M/d/yyyy||yyyy-MM-dd"},
            "closed_date":          {"type": "date", "format": "M/d/yyyy||yyyy-MM-dd"},

            # Quarters
            "quarter_completed":    {"type": "keyword"},
            "deal_close_quarter":   {"type": "keyword"},
        }
    }
}


def get_client():
    return Elasticsearch(
        os.environ["ELASTICSEARCH_URL"],
        api_key=os.environ["ELASTICSEARCH_API_KEY"],
    )


def create_index():
    es = get_client()

    if es.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists. Delete it first if you want to recreate it.")
        return

    es.indices.create(index=INDEX_NAME, body=MAPPING)
    print(f"Index '{INDEX_NAME}' created successfully.")


if __name__ == "__main__":
    create_index()
