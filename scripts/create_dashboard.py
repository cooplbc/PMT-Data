"""
Generates the PMT Live Reporting overview dashboard and imports it into Kibana 9.3.1.

Creates a single dashboard with 5 Lens metric panels using ES|QL.
Panel format reverse-engineered from manually-created Kibana 9.3.1 panels.

Panels:
  - Total RFPs Submitted
  - Total RFIs
  - Total Vendor Questionnaires
  - Total Projects
  - Total Revenue Won  (sum of acv_converted where status = Closed)

Usage:
    python scripts/create_dashboard.py
"""

import hashlib
import json
import os
import subprocess
import uuid
from dotenv import load_dotenv

load_dotenv()

API_KEY      = os.environ["ELASTICSEARCH_API_KEY"]
KIBANA_URL   = os.environ["KIBANA_URL"].rstrip("/")
DASHBOARD_ID = "pmt-live-reporting-overview"
NDJSON_PATH  = "dashboards/pmt_overview_dashboard.ndjson"
INDEX        = "pmt_live_reporting"

# Kibana generates a SHA-256-based ID for ad-hoc ES|QL data views
ADHOC_DV_ID = hashlib.sha256(INDEX.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Panel builder — exact format from Kibana 9.3.1 manual panel creation
# ---------------------------------------------------------------------------

def make_panel(x, y, w, h, title, esql):
    panel_id = str(uuid.uuid4())
    layer_id  = str(uuid.uuid4())

    return {
        "type": "lens",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "embeddableConfig": {
            "enhancements": {"dynamicActions": {"events": []}},
            "syncColors": False,
            "syncCursor": True,
            "syncTooltips": False,
            "filters": [],
            "query": {"esql": esql},
            "attributes": {
                "title": title,
                "references": [],
                "state": {
                    "datasourceStates": {
                        "textBased": {
                            "layers": {
                                layer_id: {
                                    "index": ADHOC_DV_ID,
                                    "query": {"esql": esql},
                                    "columns": [
                                        {
                                            "columnId": "result",
                                            "fieldName": "result",
                                            "label": title,
                                            "customLabel": True,
                                            "meta": {"type": "number", "esType": "long"},
                                            "inMetricDimension": True
                                        }
                                    ]
                                }
                            },
                            "indexPatternRefs": [
                                {"id": ADHOC_DV_ID, "title": INDEX}
                            ]
                        }
                    },
                    "filters": [],
                    "query": {"esql": esql},
                    "visualization": {
                        "layerId": layer_id,
                        "layerType": "data",
                        "metricAccessor": "result"
                    },
                    "adHocDataViews": {
                        ADHOC_DV_ID: {
                            "id": ADHOC_DV_ID,
                            "title": INDEX,
                            "sourceFilters": [],
                            "type": "esql",
                            "fieldFormats": {},
                            "runtimeFieldMap": {},
                            "allowNoIndex": False,
                            "name": INDEX,
                            "allowHidden": False,
                            "managed": False
                        }
                    },
                    "needsRefresh": False
                },
                "visualizationType": "lnsMetric",
                "version": 1
            }
        }
    }


# ---------------------------------------------------------------------------
# Panel definitions
# ---------------------------------------------------------------------------

PANEL_DEFS = [
    (0,  0,  6, 8, "Total RFPs Submitted",
     f'FROM {INDEX} | WHERE request_type == "RFP" | STATS result = COUNT(*)'),

    (6,  0,  6, 8, "Total RFIs",
     f'FROM {INDEX} | WHERE request_type == "RFI" | STATS result = COUNT(*)'),

    (12, 0,  6, 8, "Total Vendor Questionnaires",
     f'FROM {INDEX} | WHERE request_type == "Vendor Questionaire" | STATS result = COUNT(*)'),

    (18, 0,  6, 8, "Total Projects",
     f'FROM {INDEX} | STATS result = COUNT(*)'),

    (0,  8, 24, 8, "Total Revenue Won",
     f'FROM {INDEX} | WHERE status == "Closed" | STATS result = SUM(acv_converted)'),
]


# ---------------------------------------------------------------------------
# Build + save + import
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
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
            "version": 1,
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        },
        "references": [],
        "managed": False
    }


def save_ndjson(dashboard):
    with open(NDJSON_PATH, "w") as f:
        f.write(json.dumps(dashboard) + "\n")
    print(f"Saved to {NDJSON_PATH}")


def import_to_kibana():
    result = subprocess.run([
        "curl", "-s", "-w", "\nHTTP %{http_code}", "-X", "POST",
        f"{KIBANA_URL}/api/saved_objects/_import?overwrite=true",
        "-H", f"Authorization: ApiKey {API_KEY}",
        "-H", "kbn-xsrf: true",
        "-F", f"file=@{NDJSON_PATH};type=application/ndjson"
    ], capture_output=True, text=True)

    lines = result.stdout.strip().split("\n")
    body, status = "\n".join(lines[:-1]), lines[-1]

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
