"""
Generates the PMT Live Reporting overview dashboard and imports it into Kibana serverless.

Creates a single dashboard with 5 Lens metric panels using ES|QL (textBased datasource),
which is the supported approach for Kibana serverless:
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

API_KEY      = os.environ["ELASTICSEARCH_API_KEY"]
KIBANA_URL   = os.environ["KIBANA_URL"].rstrip("/")
DASHBOARD_ID = "pmt-live-reporting-overview"
NDJSON_PATH  = "dashboards/pmt_overview_dashboard.ndjson"
INDEX        = "pmt_live_reporting"


# ---------------------------------------------------------------------------
# Panel builder — ES|QL / textBased datasource
# ---------------------------------------------------------------------------

def make_panel(panel_index, x, y, w, h, title, esql):
    """Build a Kibana serverless Lens metric panel using an ES|QL query."""
    return {
        "version": "9.0.0",
        "type": "lens",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_index},
        "panelIndex": panel_index,
        "title": title,
        "embeddableConfig": {
            "enhancements": {},
            "description": "",
            "visualizationType": "lnsMetric",
            "state": {
                "datasourceStates": {
                    "textBased": {
                        "layers": {
                            "layer1": {
                                "query": {"esql": esql},
                                "columns": [
                                    {
                                        "columnId": "result",
                                        "fieldName": "result",
                                        "meta": {"type": "number"}
                                    }
                                ],
                                "index": {
                                    "id": INDEX,
                                    "title": INDEX,
                                    "timeFieldName": "created_date"
                                }
                            }
                        }
                    }
                },
                "filters": [],
                "query": {"query": "", "language": "kuery"},
                "visualization": {
                    "layerId": "layer1",
                    "layerType": "data",
                    "metricAccessor": "result"
                },
                "internalReferences": [],
                "adHocDataViews": {}
            },
            "references": []
        }
    }


# ---------------------------------------------------------------------------
# Panel definitions
# ---------------------------------------------------------------------------

PANEL_DEFS = [
    # (panel_index, x,  y,   w,  h,  title,                        esql)
    ("p1",  0,  0,  6, 8, "Total RFPs Submitted",
     f'FROM {INDEX} | WHERE request_type == "RFP" | STATS result = COUNT(*)'),

    ("p2",  6,  0,  6, 8, "Total RFIs",
     f'FROM {INDEX} | WHERE request_type == "RFI" | STATS result = COUNT(*)'),

    ("p3", 12,  0,  6, 8, "Total Vendor Questionnaires",
     f'FROM {INDEX} | WHERE request_type == "Vendor Questionaire" | STATS result = COUNT(*)'),

    ("p4", 18,  0,  6, 8, "Total Projects",
     f'FROM {INDEX} | STATS result = COUNT(*)'),

    ("p5",  0,  8, 24, 8, "Total Revenue Won",
     f'FROM {INDEX} | WHERE status == "Closed" | STATS result = SUM(acv_converted)'),
]


# ---------------------------------------------------------------------------
# Build dashboard
# ---------------------------------------------------------------------------

def build_dashboard():
    panels = [make_panel(*args) for args in PANEL_DEFS]

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
        "references": [],
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
