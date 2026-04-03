"""
Generates the PMT Live Reporting overview dashboard and imports it into Kibana 9.3.1.

Panels:
  - Total RFPs Submitted         (ES|QL metric, textBased)
  - Total RFIs                   (ES|QL metric, textBased)
  - Total Vendor Questionnaires  (ES|QL metric, textBased)
  - Total Projects               (ES|QL metric, textBased)
  - Total Revenue Won            (ES|QL metric, textBased)
  - ACV Revenue by Territory     (bar chart, formBased, stage = 8 - Closed Won)

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
DATAVIEW_ID  = "04a0b59e-4cec-4308-bf57-d8e6183bc4a9"  # existing Kibana data view

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
# Bar chart panel builder — formBased datasource (Kibana 9.3.1 native format)
# ---------------------------------------------------------------------------

def make_bar_panel(x, y, w, h, title, x_field, x_label, y_field, y_label, filters=None):
    """Build a Kibana 9.3.1 bar chart panel using formBased datasource."""
    panel_id = str(uuid.uuid4())
    layer_id = str(uuid.uuid4())
    x_col_id = str(uuid.uuid4())
    y_col_id = str(uuid.uuid4())

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
            "query": {"query": "", "language": "kuery"},
            "attributes": {
                "title": title,
                "visualizationType": "lnsXY",
                "type": "lens",
                "references": [
                    {"type": "index-pattern", "id": DATAVIEW_ID,
                     "name": f"indexpattern-datasource-layer-{layer_id}"}
                ],
                "state": {
                    "visualization": {
                        "legend": {"isVisible": True, "position": "right"},
                        "valueLabels": "hide",
                        "preferredSeriesType": "bar",
                        "layers": [{
                            "layerId": layer_id,
                            "accessors": [y_col_id],
                            "position": "top",
                            "seriesType": "bar",
                            "showGridlines": False,
                            "layerType": "data",
                            "xAccessor": x_col_id
                        }]
                    },
                    "query": {"query": "", "language": "kuery"},
                    "filters": filters or [],
                    "datasourceStates": {
                        "formBased": {
                            "layers": {
                                layer_id: {
                                    "columns": {
                                        x_col_id: {
                                            "label": x_label,
                                            "dataType": "string",
                                            "operationType": "terms",
                                            "sourceField": x_field,
                                            "isBucketed": True,
                                            "params": {
                                                "size": 20,
                                                "orderBy": {"type": "column", "columnId": y_col_id},
                                                "orderDirection": "desc",
                                                "otherBucket": False,
                                                "missingBucket": False,
                                                "parentFormat": {"id": "terms"},
                                                "include": [], "exclude": [],
                                                "includeIsRegex": False,
                                                "excludeIsRegex": False
                                            },
                                            "customLabel": True
                                        },
                                        y_col_id: {
                                            "label": y_label,
                                            "dataType": "number",
                                            "operationType": "sum",
                                            "sourceField": y_field,
                                            "isBucketed": False,
                                            "params": {"emptyAsNull": True},
                                            "customLabel": True
                                        }
                                    },
                                    "columnOrder": [x_col_id, y_col_id],
                                    "sampling": 1,
                                    "ignoreGlobalFilters": False,
                                    "incompleteColumns": {},
                                    "indexPatternId": DATAVIEW_ID
                                }
                            },
                            "currentIndexPatternId": DATAVIEW_ID
                        },
                        "textBased": {
                            "layers": {},
                            "indexPatternRefs": [{"id": DATAVIEW_ID, "title": INDEX, "timeField": ""}]
                        }
                    },
                    "internalReferences": [],
                    "adHocDataViews": {}
                },
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

CLOSED_WON_FILTER = [{
    "meta": {"alias": None, "disabled": False, "negate": False,
             "key": "stage", "type": "phrase", "params": {"query": "8 - Closed Won"}},
    "query": {"match_phrase": {"stage": "8 - Closed Won"}}
}]


def build_dashboard():
    panels = [make_panel(*args) for args in PANEL_DEFS]
    panels.append(make_bar_panel(
        0, 16, 48, 15,
        "ACV Revenue by Territory (Closed Won)",
        x_field="territory_level_1", x_label="Territory",
        y_field="acv_converted",     y_label="ACV Revenue",
        filters=CLOSED_WON_FILTER
    ))
    return {
        "type": "dashboard",
        "id": DASHBOARD_ID,
        "attributes": {
            "title": "PMT Live Reporting Overview",
            "description": "YTD metrics: RFPs, RFIs, Vendor Questionnaires, Total Projects, Revenue Won",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": True}),
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
