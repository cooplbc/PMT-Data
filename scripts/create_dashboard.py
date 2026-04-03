"""
Generates the PMT Live Reporting overview dashboard and imports it into Kibana 9.x.

Creates a single dashboard with 5 Lens metric panels (by-value / panelConfig format):
  - Total RFPs Submitted
  - Total RFIs
  - Total Vendor Questionnaires
  - Total Projects
  - Total Revenue Won  (sum of acv_converted where status = Closed)

Also saves the NDJSON export to dashboards/pmt_overview_dashboard.ndjson
so it can be re-imported manually via Kibana > Stack Management > Saved Objects.

Usage:
    python scripts/create_dashboard.py
"""

import json
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.environ["ELASTICSEARCH_API_KEY"]
KIBANA_URL = os.environ["KIBANA_URL"].rstrip("/")

# Use the pre-existing pmt_live_reporting data view
DATAVIEW_ID  = "48c80059-b48d-41a6-948e-3d1aa8284356"
DASHBOARD_ID = "pmt-live-reporting-overview"
NDJSON_PATH  = "dashboards/pmt_overview_dashboard.ndjson"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_filter(field, value):
    return {
        "meta": {
            "alias": None, "disabled": False, "negate": False,
            "key": field, "type": "phrase", "params": {"query": value}
        },
        "query": {"match_phrase": {field: value}}
    }


def make_count_col(label):
    return {
        "label": label, "dataType": "number", "operationType": "count",
        "isBucketed": False, "scale": "ratio", "sourceField": "___records___", "params": {}
    }


def make_sum_col(label, field):
    return {
        "label": label, "dataType": "number", "operationType": "sum",
        "isBucketed": False, "scale": "ratio", "sourceField": field,
        "params": {"format": {"id": "currency", "params": {"decimals": 0}}}
    }


def make_panel(panel_index, x, y, w, h, title, col, filters):
    """Build a Kibana 9.x by-value Lens panel using panelConfig format."""
    ref_name = f"{panel_index}:indexpattern-datasource-layer-layer1"
    panel = {
        "version": "9.0.0",
        "type": "lens",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_index},
        "panelIndex": panel_index,
        "panelConfig": {
            "title": title,
            "description": "",
            "visualizationType": "lnsMetric",
            "state": {
                "datasourceStates": {
                    "formBased": {
                        "layers": {
                            "layer1": {
                                "columns": {"col1": col},
                                "columnOrder": ["col1"],
                                "incompleteColumns": {}
                            }
                        }
                    }
                },
                "filters": filters,
                "query": {"query": "", "language": "kuery"},
                "visualization": {
                    "layerId": "layer1",
                    "layerType": "data",
                    "metricAccessor": "col1"
                },
                "internalReferences": [],
                "adHocDataViews": {}
            },
            "references": [
                {"type": "index-pattern", "id": DATAVIEW_ID, "name": ref_name}
            ]
        }
    }
    return panel, ref_name


# ---------------------------------------------------------------------------
# Build dashboard
# ---------------------------------------------------------------------------

PANEL_DEFS = [
    # (panel_index, x,  y,  w,  h,  title,                        column,                                        filters)
    ("p1",  0,  0,  6, 8, "Total RFPs Submitted",        make_count_col("Total RFPs"),              [make_filter("request_type", "RFP")]),
    ("p2",  6,  0,  6, 8, "Total RFIs",                  make_count_col("Total RFIs"),              [make_filter("request_type", "RFI")]),
    ("p3", 12,  0,  6, 8, "Total Vendor Questionnaires", make_count_col("Total Vendor Q"),          [make_filter("request_type", "Vendor Questionaire")]),
    ("p4", 18,  0,  6, 8, "Total Projects",              make_count_col("Total Projects"),          []),
    ("p5",  0,  8, 24, 8, "Total Revenue Won",           make_sum_col("Total Revenue Won", "acv_converted"), [make_filter("status", "Closed")]),
]


def build_dashboard():
    panels = []
    references = []

    for args in PANEL_DEFS:
        panel, ref_name = make_panel(*args)
        panels.append(panel)
        references.append({"type": "index-pattern", "id": DATAVIEW_ID, "name": ref_name})

    return {
        "type": "dashboard",
        "id": DASHBOARD_ID,
        "attributes": {
            "title": "PMT Live Reporting Overview",
            "description": "YTD metrics: RFPs, RFIs, Vendor Questionnaires, Total Projects, Revenue Won",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({
                "useMargins": True, "syncColors": False, "hidePanelTitles": False
            }),
            "version": 1,
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": references,
        "managed": False
    }


# ---------------------------------------------------------------------------
# Save + import
# ---------------------------------------------------------------------------

def save_ndjson(dashboard):
    with open(NDJSON_PATH, "w") as f:
        f.write(json.dumps(dashboard) + "\n")
    print(f"Saved to {NDJSON_PATH}")


def import_to_kibana():
    result = subprocess.run([
        "curl", "-s", "-w", "\nHTTP %{http_code}",
        "-X", "POST",
        f"{KIBANA_URL}/api/saved_objects/_import?overwrite=true",
        "-H", f"Authorization: ApiKey {API_KEY}",
        "-H", "kbn-xsrf: true",
        "-F", f"file=@{NDJSON_PATH};type=application/ndjson"
    ], capture_output=True, text=True)

    lines = result.stdout.strip().split("\n")
    body = "\n".join(lines[:-1])
    status = lines[-1]

    try:
        data = json.loads(body)
        if data.get("success"):
            print(f"Import successful: {data.get('successCount', 0)} object(s) created/updated")
        else:
            print(f"Import failed ({status}):")
            print(json.dumps(data, indent=2))
    except Exception:
        print(f"Response ({status}): {body[:500]}")


if __name__ == "__main__":
    dashboard = build_dashboard()
    save_ndjson(dashboard)
    print(f"Importing to Kibana at {KIBANA_URL} ...")
    import_to_kibana()
