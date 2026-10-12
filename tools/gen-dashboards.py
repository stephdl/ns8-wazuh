#!/usr/bin/env python3
"""Generate the NS8 dashboards as saved objects ndjson files.

Usage: tools/gen-dashboards.py imageroot/content/dashboards
"""

import json
import os
import sys

OUT = sys.argv[1]

EVENTS = "wazuh-events-v5*"
APPS = "wazuh-events-v5-applications*"
SYSTEM = "wazuh-events-v5-system-activity*"
FINDINGS = "wazuh-findings-v5*"
MANAGED = "Managed by the NS8 module and replaced at each update: clone it before changing it."


def count(label=None):
    return {"id": "1", "enabled": True, "type": "count", "schema": "metric",
            "params": {"customLabel": label} if label else {}}


def terms(id, field, schema, size=10, label=None, missing=False):
    return {"id": id, "enabled": True, "type": "terms", "schema": schema,
            "params": {"field": field, "size": size, "order": "desc", "orderBy": "1",
                       "otherBucket": False, "otherBucketLabel": "Other",
                       "missingBucket": missing, "missingBucketLabel": "-",
                       **({"customLabel": label} if label else {})}}


def histogram(id="2"):
    return {"id": id, "enabled": True, "type": "date_histogram", "schema": "segment",
            "params": {"field": "@timestamp", "useNormalizedOpenSearchInterval": True,
                       "scaleMetricValues": False, "interval": "auto", "drop_partials": False,
                       "min_doc_count": 1, "extended_bounds": {}}}


def axes(kind, horizontal=False):
    return {
        "type": kind if kind != "horizontal_bar" else "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "left" if horizontal else "bottom",
                          "show": True, "style": {}, "scale": {"type": "linear"},
                          "labels": {"show": True, "filter": not horizontal, "truncate": 100}, "title": {}}],
        "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
                       "position": "bottom" if horizontal else "left", "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"},
                       "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Count"}}],
        "seriesParams": [{"show": True, "type": "line" if kind == "line" else "histogram",
                          "mode": "normal" if kind == "line" else "stacked",
                          "data": {"label": "Count", "id": "1"}, "valueAxis": "ValueAxis-1",
                          "drawLinesBetweenPoints": True, "lineWidth": 2, "interpolate": "linear",
                          "showCircles": True}],
        "addTooltip": True, "addLegend": True, "legendPosition": "right", "times": [],
        "addTimeMarker": False, "labels": {},
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
    }


def over_time(split_agg, kind="line"):
    """A line or stacked bar chart over time, split in series by split_agg."""
    split_agg = dict(split_agg, schema="group")
    return kind, axes(kind), [count(), histogram("2"), split_agg]


def bars(split_agg, series=None):
    aggs = [count(), dict(split_agg, schema="segment")]
    if series:
        aggs.append(dict(series, schema="group"))
    return "horizontal_bar", axes("horizontal_bar", horizontal=True), aggs


def table(*buckets, extra_metrics=()):
    params = {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False,
              "sort": {"columnIndex": None, "direction": None}, "showTotal": False,
              "totalFunc": "sum", "percentageCol": "", "showToolbar": True}
    return "table", params, [count("Count"), *extra_metrics, *[dict(b, schema="bucket") for b in buckets]]


def pie(split_agg):
    params = {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right",
              "isDonut": True, "labels": {"show": False, "values": True, "last_level": True, "truncate": 100}}
    return "pie", params, [count(), dict(split_agg, schema="segment")]


def metric(group=None, extra_metrics=()):
    params = {"addTooltip": True, "addLegend": False, "type": "metric",
              "metric": {"percentageMode": False, "useRanges": False, "colorSchema": "Green to Red",
                         "metricColorMode": "None", "colorsRange": [{"from": 0, "to": 10000}],
                         "labels": {"show": True}, "invertColors": False,
                         "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "",
                                   "fontSize": 36}}}
    aggs = [count("Count"), *extra_metrics]
    if group:
        aggs.append(dict(group, schema="group"))
    return "metric", params, aggs


def geo_map(field="source.geo.location"):
    params = {"colorSchema": "Yellow to Red", "mapType": "Scaled Circle Markers", "isDesaturated": True,
              "addTooltip": True, "heatClusterSize": 1.5, "legendPosition": "bottomright",
              "mapZoom": 2, "mapCenter": [20, 0],
              "wms": {"enabled": False, "options": {"format": "image/png", "transparent": True}}}
    aggs = [count(), {"id": "2", "enabled": True, "type": "geohash_grid", "schema": "segment",
                      "params": {"field": field, "autoPrecision": True, "precision": 2,
                                 "useGeocentroid": True, "isFilteredByCollar": True}}]
    return "tile_map", params, aggs


def status_ranges(id="3"):
    return {"id": id, "enabled": True, "type": "range", "schema": "group",
            "params": {"field": "http.response.status_code", "ranges": [
                {"from": 100, "to": 300, "key": "1xx-2xx"}, {"from": 300, "to": 400, "key": "3xx"},
                {"from": 400, "to": 500, "key": "4xx"}, {"from": 500, "to": 600, "key": "5xx"}]}}


def search_source(query):
    return json.dumps({"query": {"language": "kuery", "query": query}, "filter": [],
                       "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"})


def index_ref(pattern):
    return [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": pattern}]


def vis(id, title, pattern, query, spec):
    kind, params, aggs = spec
    params = dict(params, type=params.get("type", kind)) if kind not in ("table", "tile_map") else params
    return {"id": id, "type": "visualization",
            "attributes": {"title": title, "description": "", "version": 1, "uiStateJSON": "{}",
                           "visState": json.dumps({"title": title, "type": kind, "params": params, "aggs": aggs}),
                           "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}},
            "references": index_ref(pattern)}


def search(id, title, pattern, query, columns):
    return {"id": id, "type": "search",
            "attributes": {"title": title, "description": "", "version": 1, "hits": 0,
                           "columns": columns, "sort": [["@timestamp", "desc"]],
                           "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}},
            "references": index_ref(pattern)}


def dashboard(id, title, description, panels):
    """panels: list of (object, w, h). Laid out left to right on a 48 columns grid."""
    x = y = row_h = 0
    panels_json, references = [], []
    for i, (obj, w, h) in enumerate(panels):
        if x + w > 48:
            x, y, row_h = 0, y + row_h, 0
        panels_json.append({"version": "3.6.0", "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i + 1)},
                            "panelIndex": str(i + 1), "embeddableConfig": {}, "panelRefName": f"panel_{i}"})
        references.append({"name": f"panel_{i}", "type": obj["type"], "id": obj["id"]})
        x += w
        row_h = max(row_h, h)
    dash = {"id": id, "type": "dashboard",
            "attributes": {"title": title, "description": f"{description}. {MANAGED}", "hits": 0, "version": 1,
                           "panelsJSON": json.dumps(panels_json),
                           "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
                           "timeRestore": True, "timeFrom": "now-24h", "timeTo": "now",
                           "refreshInterval": {"pause": True, "value": 0},
                           "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(
                               {"query": {"language": "kuery", "query": ""}, "filter": []})}},
            "references": references}
    return [o for o, _, _ in panels] + [dash]


def write(name, objects):
    with open(os.path.join(OUT, name), "w") as f:
        for o in objects:
            f.write(json.dumps(o, separators=(",", ":")) + "\n")


AUTH = "event.category:authentication"
FAIL = f"{AUTH} and event.outcome:failure"
write("10-logins.ndjson", dashboard("ns8-logins", "NS8 - Logins",
    "Logins to NS8 services and to the hosts, by outcome, user, source and country", [
    (vis("ns8-logins-outcome", "Logins by outcome", EVENTS, AUTH,
         metric(group=terms("2", "event.outcome", "group", size=3))), 16, 8),
    (vis("ns8-logins-timeline", "Logins over time", EVENTS, AUTH,
         over_time(terms("3", "event.outcome", "group", size=3), kind="histogram")), 32, 8),
    (vis("ns8-logins-services", "Logins by service", EVENTS, AUTH,
         bars(terms("2", "process.name", "segment", size=10, missing=True),
              series=terms("3", "event.outcome", "group", size=3))), 16, 12),
    (vis("ns8-logins-failed-users", "Failed logins by user", EVENTS, FAIL,
         table(terms("2", "user.name", "bucket", size=50, label="User"))), 16, 12),
    (vis("ns8-logins-failed-sources", "Failed logins by source", EVENTS, FAIL,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True))), 16, 12),
    (vis("ns8-logins-countries", "Logins by country", EVENTS, AUTH,
         pie(terms("2", "source.geo.country_name", "segment", size=10))), 16, 14),
    (vis("ns8-logins-map", "Failed logins map", EVENTS, FAIL, geo_map()), 32, 14),
    (search("ns8-logins-failures", "NS8 - Failed logins", EVENTS, FAIL,
            ["wazuh.agent.name", "process.name", "user.name", "source.ip", "source.geo.country_name"]), 48, 14),
]))

WEB = "event.category:web"
write("20-web.ndjson", dashboard("ns8-web", "NS8 - Web",
    "HTTP requests received by the NS8 reverse proxy", [
    (vis("ns8-web-timeline", "Requests over time", APPS, WEB, over_time(status_ranges(), kind="histogram")), 32, 10),
    (vis("ns8-web-status", "Status codes", APPS, WEB,
         pie(terms("2", "http.response.status_code", "segment", size=10))), 16, 10),
    (vis("ns8-web-errors", "Client and server errors", APPS, f"{WEB} and http.response.status_code >= 400",
         over_time(terms("3", "http.response.status_code", "group", size=10), kind="line")), 48, 10),
    (vis("ns8-web-paths", "Top paths in error", APPS, f"{WEB} and http.response.status_code >= 400",
         table(terms("2", "url.path", "bucket", size=50, label="Path"),
               terms("3", "http.response.status_code", "bucket", size=3, label="Status"))), 24, 14),
    (vis("ns8-web-sources", "Top sources", APPS, WEB,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True))), 24, 14),
    (vis("ns8-web-countries", "Requests by country", APPS, WEB,
         pie(terms("2", "source.geo.country_name", "segment", size=10))), 16, 14),
    (vis("ns8-web-map", "Requests map", APPS, WEB, geo_map()), 32, 14),
]))

CROWDSEC = "event.action:crowdsec-alert"
write("30-crowdsec.ndjson", dashboard("ns8-crowdsec", "NS8 - CrowdSec",
    "Scenarios triggered by CrowdSec and the IP addresses behind them", [
    (vis("ns8-crowdsec-total", "Alerts", APPS, CROWDSEC,
         metric(extra_metrics=[{"id": "2", "enabled": True, "type": "cardinality", "schema": "metric",
                                "params": {"field": "source.ip", "customLabel": "Distinct IPs"}}])), 16, 8),
    (vis("ns8-crowdsec-timeline", "Alerts over time", APPS, CROWDSEC,
         over_time(terms("3", "event.reason", "group", size=10), kind="histogram")), 32, 8),
    (vis("ns8-crowdsec-scenarios", "Scenarios", APPS, CROWDSEC,
         pie(terms("2", "event.reason", "segment", size=15))), 16, 14),
    (vis("ns8-crowdsec-sources", "Top IPs", APPS, CROWDSEC,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("4", "event.reason", "bucket", size=3, label="Scenario"))), 32, 14),
    (vis("ns8-crowdsec-map", "Alerts map", APPS, CROWDSEC, geo_map()), 48, 14),
]))

NOT_INFO = "not wazuh.rule.level:informational"
write("40-fleet.ndjson", dashboard("ns8-fleet", "NS8 - Fleet",
    "Findings of every agent, and when each agent sent its last event", [
    (vis("ns8-fleet-levels", "Findings over time", FINDINGS, "",
         over_time(terms("3", "wazuh.rule.level", "group", size=5), kind="histogram")), 32, 10),
    (vis("ns8-fleet-level-count", "Findings by level", FINDINGS, "",
         metric(group=terms("2", "wazuh.rule.level", "group", size=5))), 16, 10),
    (vis("ns8-fleet-agents", "Findings by agent", FINDINGS, NOT_INFO,
         bars(terms("2", "wazuh.agent.name", "segment", size=20),
              series=terms("3", "wazuh.rule.level", "group", size=5))), 24, 14),
    (vis("ns8-fleet-tactics", "MITRE tactics", FINDINGS, NOT_INFO,
         pie(terms("2", "wazuh.rule.mitre.tactic.name", "segment", size=10))), 24, 14),
    (vis("ns8-fleet-rules", "Top rules, informational excluded", FINDINGS, NOT_INFO,
         table(terms("2", "wazuh.rule.title", "bucket", size=50, label="Rule"),
               terms("3", "wazuh.rule.level", "bucket", size=1, label="Level"))), 24, 14),
    (vis("ns8-fleet-last-event", "Last event per agent", EVENTS, "",
         table(terms("2", "wazuh.agent.name", "bucket", size=100, label="Agent"),
               extra_metrics=[{"id": "3", "enabled": True, "type": "max", "schema": "metric",
                               "params": {"field": "@timestamp", "customLabel": "Last event"}}])), 24, 14),
]))

CHANGES = ("event.action:(user-created or user-deleted or user-modified or group-created or group-deleted"
           " or group-modified or service-stopped or service-deleted or firewall-rule-modified or config-modified)"
           " and not service.name:user@* and not service.name:fix-xdg-state@*"
           # The CrowdSec bouncer rewrites its nftables set at every ban
           " and not process.name:crowdsec-firew*")
write("50-system-changes.ndjson", dashboard("ns8-system-changes", "NS8 - System changes",
    "Accounts, services and firewall changed on the hosts", [
    (vis("ns8-system-changes-count", "Changes by type", SYSTEM, CHANGES,
         metric(group=terms("2", "event.action", "group", size=10))), 48, 8),
    (vis("ns8-system-changes-timeline", "Changes over time", SYSTEM, CHANGES,
         over_time(terms("3", "event.action", "group", size=10), kind="histogram")), 32, 10),
    (vis("ns8-system-changes-agents", "Changes by agent", SYSTEM, CHANGES,
         bars(terms("2", "wazuh.agent.name", "segment", size=20))), 16, 10),
    (search("ns8-system-changes-list", "NS8 - System changes", SYSTEM, CHANGES,
            ["wazuh.agent.name", "event.action", "user.target.name", "group.name", "service.name",
             "process.name", "user.name"]), 48, 16),
]))
