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
MANAGED = "Replaced at each update: clone it before changing it."


def count(label=None):
    return {"id": "1", "enabled": True, "type": "count", "schema": "metric",
            "params": {"customLabel": label} if label else {}}


def terms(id, field, schema, size=10, label=None, missing=False, missing_label="-"):
    return {"id": id, "enabled": True, "type": "terms", "schema": schema,
            "params": {"field": field, "size": size, "order": "desc", "orderBy": "1",
                       "otherBucket": False, "otherBucketLabel": "Other",
                       "missingBucket": missing, "missingBucketLabel": missing_label,
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


# The world countries layer of the OpenSearch maps service, as the region map editor saves it
WORLD_COUNTRIES = {"name": "World Countries", "origin": "elastic_maps_service", "id": "world_countries",
                   "layerId": "elastic_maps_service.World Countries", "isEMS": True,
                   "attribution": "Made with NaturalEarth", "format": {"type": "geojson"},
                   "fields": [{"type": "id", "name": "iso2", "description": "ISO 3166-1 alpha-2 Code"},
                              {"type": "id", "name": "iso3", "description": "ISO 3166-1 alpha-3 Code"},
                              {"type": "name", "name": "name", "description": "Name"}]}


def geo_map():
    """Countries colored by count: the tooltip gives the country name, a circle map only its coordinates."""
    params = {"addTooltip": True, "colorSchema": "Yellow to Red", "isDisplayWarning": False, "legendPosition": "bottomright",
              "mapZoom": 2, "mapCenter": [20, 0], "outlineWeight": 1, "showAllShapes": True, "emsHotLink": "",
              "layerChosenByUser": "default", "selectedLayer": WORLD_COUNTRIES,
              "selectedJoinField": WORLD_COUNTRIES["fields"][0],
              "wms": {"enabled": False, "options": {"format": "image/png", "transparent": True}}}
    aggs = [count(), terms("2", "source.geo.country_iso_code", "segment", size=200)]
    return "region_map", params, aggs


def status_ranges(id="3"):
    return {"id": id, "enabled": True, "type": "range", "schema": "group",
            "params": {"field": "http.response.status_code", "ranges": [
                {"from": 100, "to": 300, "label": "OK"}, {"from": 300, "to": 400, "label": "Redirect or cache"},
                {"from": 400, "to": 500, "label": "Client error"}, {"from": 500, "to": 600, "label": "Server error"}]}}


def search_source(query):
    return json.dumps({"query": {"language": "kuery", "query": query}, "filter": [],
                       "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"})


def index_ref(pattern):
    return [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": pattern}]


def vis(id, title, pattern, query, spec):
    kind, params, aggs = spec
    params = dict(params, type=params.get("type", kind)) if kind not in ("table", "region_map") else params
    return {"id": id, "type": "visualization",
            "attributes": {"title": title, "description": "", "version": 1, "uiStateJSON": "{}",
                           "visState": json.dumps({"title": title, "type": kind, "params": params, "aggs": aggs}),
                           "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}},
            "references": index_ref(pattern)}


def markdown(id, title, text):
    params = {"markdown": text, "fontSize": 12, "openLinksInNewTab": False}
    return {"id": id, "type": "visualization",
            "attributes": {"title": title, "description": "", "version": 1, "uiStateJSON": "{}",
                           "visState": json.dumps({"title": title, "type": "markdown", "params": params, "aggs": []}),
                           "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}},
            "references": []}


def search(id, title, pattern, query, columns):
    return {"id": id, "type": "search",
            "attributes": {"title": title, "description": "", "version": 1, "hits": 0,
                           "columns": columns, "sort": [["@timestamp", "desc"]],
                           "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}},
            "references": index_ref(pattern)}


def controls(id, pattern, apps=False, program=False, site=False):
    """Customer then agent pickers: the customer is the Wazuh group the agent enrolled in."""
    fields = [("1", "wazuh.agent.groups", "Customer", ""), ("2", "wazuh.agent.name", "Agent", "1")]
    # The picker lists every application of the agent, whatever the dashboard shows: only where several can match
    if apps:
        fields.append(("4", "orchestrator.namespace", "Application", "2"))
    if program:
        fields.append(("3", "process.name", "Program", "4"))
    if site:
        fields.append(("5", "service.target.name", "Site", "2"))
    params = {"controls": [{"id": cid, "fieldName": field, "label": label, "type": "list", "parent": parent,
                            "indexPatternRefName": f"control_{i}_index_pattern",
                            # Dynamic options ask the indexer for 10 values only and ignore size
                            "options": {"type": "terms", "multiselect": True, "dynamicOptions": False,
                                        "size": 500, "order": "desc"}}
                           for i, (cid, field, label, parent) in enumerate(fields)],
              "updateFiltersOnChange": True, "useTimeFilter": True, "pinFilters": False}
    return {"id": id, "type": "visualization",
            "attributes": {"title": "Customer and agent", "description": "", "version": 1, "uiStateJSON": "{}",
                           "visState": json.dumps({"title": "Customer and agent", "type": "input_control_vis",
                                                   "params": params, "aggs": []}),
                           "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}},
            "references": [{"name": f"control_{i}_index_pattern", "type": "index-pattern", "id": pattern}
                           for i in range(len(fields))]}


def dashboard(id, title, description, panels, pattern=EVENTS, apps=False, program=False, site=False):
    """panels: list of (object, w, h). Laid out left to right on a 48 columns grid, under the customer picker."""
    panels = [(controls(f"{id}-controls", pattern, apps, program, site), 48, 5)] + panels
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


# The audit marks cron jobs and the systemd user sessions as failed logins, but nobody logs in
AUTH = ("event.category:authentication"
        " and not process.executable:(\"/usr/bin/crond\" or \"/usr/sbin/cron\" or \"/usr/lib/systemd/systemd\")")
FAIL = f"{AUTH} and event.outcome:failure"
write("10-logins.ndjson", dashboard("ns8-logins", "NS8 - Logins",
    "Successful and failed logins on every service and server", [
    (vis("ns8-logins-outcome", "Logins by outcome", EVENTS, AUTH,
         metric(group=terms("2", "event.outcome", "group", size=3))), 16, 8),
    (vis("ns8-logins-timeline", "Logins over time", EVENTS, AUTH,
         over_time(terms("3", "event.outcome", "group", size=3), kind="histogram")), 32, 8),
    (vis("ns8-logins-services", "Logins by service", EVENTS, AUTH,
         # The logins of the standard Wazuh integrations have no service type: mostly ssh to the server
         bars(terms("2", "service.type", "segment", size=10, missing=True, missing_label="ssh / host"),
              series=terms("3", "event.outcome", "group", size=3))), 16, 12),
    (vis("ns8-logins-failed-users", "Failed logins by user", EVENTS, FAIL,
         table(terms("2", "user.name", "bucket", size=50, label="User"))), 16, 12),
    (vis("ns8-logins-failed-sources", "Failed logins by source", EVENTS, FAIL,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.geo.city_name", "bucket", size=1, label="City", missing=True))), 16, 12),
    (vis("ns8-logins-countries", "Logins by country", EVENTS, AUTH,
         pie(terms("2", "source.geo.country_name", "segment", size=10))), 16, 14),
    (vis("ns8-logins-map", "Failed logins map", EVENTS, FAIL, geo_map()), 32, 14),
    (search("ns8-logins-failures", "NS8 - Failed logins", EVENTS, FAIL,
            ["wazuh.agent.name", "process.name", "user.name", "source.ip", "source.geo.country_name"]), 48, 14),
], apps=True))

# The apache and nginx of the lamp and webserver sites log the same requests again, without the route
WEB = "event.category:web and process.name:traefik"
PROBE_PATHS = "url.path:(*wp-login* or *xmlrpc* or *.env* or *phpmyadmin* or *.git* or *wp-admin* or *.php*)"
# A request to no route hit the bare address or an unknown name: nobody browses there
SCANS = f"{WEB} and (not service.target.name:* or (http.response.status_code:404 and {PROBE_PATHS}))"
SITES = f"{WEB} and service.target.name:* and not (http.response.status_code:404 and {PROBE_PATHS})"
# 499: the client closed the connection, often a sync client
# Traefik drops the User-Agent header: only the nginx and apache lines of the sites behind it carry one
AGENTS = "event.category:web and user_agent.original:*"
SITE_ERRORS = f"{SITES} and http.response.status_code >= 400 and not http.response.status_code:499"


write("20-web.ndjson", dashboard("ns8-web", "NS8 - Web",
    "Web traffic: the sites, their errors, and the scanners", [
    (markdown("ns8-web-help", "How to read it",
              "**Sites**: real traffic. **Errors to fix**: broken pages of the sites. "
              "**Scans**: bots probing for flaws."), 48, 3),
    (markdown("ns8-web-sites-title", "Sites", "### Sites"), 48, 2),
    (vis("ns8-web-timeline", "Site requests over time", APPS, SITES,
         over_time(status_ranges(), kind="histogram")), 32, 10),
    (vis("ns8-web-status", "Site status codes", APPS, SITES,
         pie(terms("2", "http.response.status_code", "segment", size=10))), 16, 10),
    (vis("ns8-hosting-sites", "Requests by site", APPS, SITES,
         bars(terms("2", "service.target.name", "segment", size=30), series=status_ranges("3"))), 24, 14),
    (vis("ns8-web-map", "Visitors map", APPS, SITES, geo_map()), 24, 14),
    (vis("ns8-web-sources", "Top visitors", APPS, SITES,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.as.organization.name", "bucket", size=1, label="Network", missing=True))), 24, 14),
    (vis("ns8-web-agents", "Top user agents", APPS, AGENTS,
         table(terms("2", "user_agent.original", "bucket", size=30, label="User agent"))), 24, 14),
    (markdown("ns8-web-errors-title", "Errors to fix", "### Errors to fix"), 48, 2),
    (vis("ns8-web-errors", "Site errors over time", APPS, SITE_ERRORS,
         over_time(terms("3", "http.response.status_code", "group", size=10), kind="line")), 24, 14),
    (vis("ns8-hosting-errors", "Server errors by site", APPS, f"{SITES} and http.response.status_code >= 500",
         table(terms("2", "service.target.name", "bucket", size=20, label="Site"),
               terms("3", "url.path", "bucket", size=5, label="Path"))), 24, 14),
    (vis("ns8-web-paths", "Missing pages by site", APPS, f"{SITES} and http.response.status_code:404",
         table(terms("2", "service.target.name", "bucket", size=20, label="Site"),
               terms("3", "url.path", "bucket", size=10, label="Path"))), 48, 14),
    (markdown("ns8-web-scans-title", "Scans", "### Scans"), 48, 2),
    (vis("ns8-web-scans-timeline", "Scans over time", APPS, SCANS,
         over_time(terms("3", "service.target.name", "group", size=10, missing=True, missing_label="no site"),
                   kind="histogram")), 24, 14),
    (vis("ns8-web-scans-map", "Scanners map", APPS, SCANS, geo_map()), 24, 14),
    (vis("ns8-hosting-probes", "Probed paths", APPS, SCANS,
         table(terms("2", "url.path", "bucket", size=50, label="Path"),
               terms("3", "service.target.name", "bucket", size=3, label="Site", missing=True,
                     missing_label="no site"))), 24, 14),
    (vis("ns8-hosting-probers", "Scanning sources", APPS, SCANS,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.as.organization.name", "bucket", size=1, label="Network", missing=True))), 24, 14),
], site=True))

CROWDSEC = "event.action:crowdsec-alert"
write("30-crowdsec.ndjson", dashboard("ns8-crowdsec", "NS8 - CrowdSec",
    "Attacks blocked by CrowdSec, and where they come from", [
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
               terms("5", "source.geo.city_name", "bucket", size=1, label="City", missing=True),
               terms("4", "event.reason", "bucket", size=3, label="Scenario"))), 32, 14),
    (vis("ns8-crowdsec-map", "Alerts map", APPS, CROWDSEC, geo_map()), 48, 14),
]))

NOT_INFO = "not wazuh.rule.level:informational"
write("40-fleet.ndjson", dashboard("ns8-fleet", "NS8 - Fleet",
    "Alerts of every server, and when each one last reported", [
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
    "Accounts, services and firewall rules changed on the servers", [
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

MAIL = "service.type:(postfix or rspamd)"
DELIVERY = "service.type:postfix and event.action:(sent or bounced or deferred or expired)"
REJECTED = "event.action:mail-rejected"
SPAM = "service.type:rspamd"
SASL = "service.type:postfix and event.action:logon-failed"
write("60-mail.ndjson", dashboard("ns8-mail", "NS8 - Mail",
    "Sent and rejected mail, spam, viruses and failed mail logins", [
    (vis("ns8-mail-delivery-count", "Deliveries by status", APPS, DELIVERY,
         metric(group=terms("2", "event.action", "group", size=5))), 24, 8),
    (vis("ns8-mail-rejected-count", "Rejected messages", APPS, REJECTED,
         metric(extra_metrics=[{"id": "2", "enabled": True, "type": "cardinality", "schema": "metric",
                                "params": {"field": "source.ip", "customLabel": "Distinct sources"}}])), 24, 8),
    (vis("ns8-mail-timeline", "Mail flow over time", APPS, f"{DELIVERY} or {REJECTED}",
         over_time(terms("3", "event.action", "group", size=6), kind="histogram")), 48, 10),
    (vis("ns8-mail-spam-actions", "Spam filter decisions", APPS, SPAM,
         pie(terms("2", "event.action", "segment", size=6))), 16, 14),
    (vis("ns8-mail-reject-reasons", "Rejection reasons", APPS, REJECTED,
         table(terms("2", "event.reason", "bucket", size=30, label="Reason"),
               terms("3", "event.code", "bucket", size=3, label="Code"))), 32, 14),
    (vis("ns8-mail-senders", "Top senders", APPS, SPAM,
         table(terms("2", "email.from.address", "bucket", size=30, label="Sender"))), 16, 14),
    (vis("ns8-mail-recipients", "Top recipients", APPS, "service.type:postfix and event.action:sent",
         table(terms("2", "email.to.address", "bucket", size=30, label="Recipient"))), 16, 14),
    (vis("ns8-mail-bounces", "Bounced and deferred", APPS, "service.type:postfix and event.action:(bounced or deferred)",
         table(terms("2", "email.to.address", "bucket", size=30, label="Recipient"),
               terms("3", "event.action", "bucket", size=2, label="Status"))), 16, 14),
    (vis("ns8-mail-sasl-sources", "SMTP login failures", APPS, SASL,
         table(terms("2", "source.ip", "bucket", size=30, label="Source IP"),
               terms("3", "user.name", "bucket", size=3, label="User", missing=True),
               terms("4", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.geo.city_name", "bucket", size=1, label="City", missing=True))), 24, 14),
    (vis("ns8-mail-sasl-map", "SMTP login failures map", APPS, SASL, geo_map()), 24, 14),
    (search("ns8-mail-viruses", "NS8 - Mail viruses", APPS, f'{REJECTED} and event.reason:*virus*',
            ["source.ip", "email.from.address", "email.to.address", "event.reason"]), 48, 12),
]))

SAMBA_AUTH = "service.type:samba and event.category:authentication"
SAMBA_FAIL = f"{SAMBA_AUTH} and event.outcome:failure"
SAMBA_IAM = "service.type:samba and event.category:iam and not event.action:primary-group-set"
write("70-directory.ndjson", dashboard("ns8-directory", "NS8 - Directory",
    "Domain logins and account changes on Samba. Needs the Samba audit, see the README", [
    (vis("ns8-directory-outcome", "Domain logins by outcome", APPS, SAMBA_AUTH,
         metric(group=terms("2", "event.outcome", "group", size=3))), 16, 8),
    (vis("ns8-directory-timeline", "Domain logins over time", APPS, SAMBA_AUTH,
         over_time(terms("3", "event.outcome", "group", size=3), kind="histogram")), 32, 8),
    (vis("ns8-directory-failures-reason", "Failure reasons", APPS, SAMBA_FAIL,
         pie(terms("2", "event.reason", "segment", size=10))), 16, 14),
    (vis("ns8-directory-failed-users", "Failed logins by account", APPS, SAMBA_FAIL,
         table(terms("2", "user.name", "bucket", size=50, label="Account"),
               terms("3", "event.reason", "bucket", size=2, label="Reason"))), 16, 14),
    (vis("ns8-directory-failed-sources", "Failed logins by source", APPS, SAMBA_FAIL,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.domain", "bucket", size=3, label="Workstation", missing=True),
               terms("4", "service.name", "bucket", size=3, label="Service"))), 16, 14),
    (vis("ns8-directory-services", "Logins by service", APPS, SAMBA_AUTH,
         bars(terms("2", "service.name", "segment", size=10),
              series=terms("3", "event.outcome", "group", size=3))), 24, 12),
    (vis("ns8-directory-changes", "Account changes by type", APPS, SAMBA_IAM,
         bars(terms("2", "event.action", "segment", size=10))), 24, 12),
    (search("ns8-directory-changes-list", "NS8 - Directory changes", APPS, SAMBA_IAM,
            ["wazuh.agent.name", "event.action", "user.target.name", "group.name", "event.reason"]), 48, 16),
]))

PHONE = "service.type:(kamailio or nethvoice) and event.outcome:failure"
SIP = "service.type:kamailio and event.outcome:failure"
write("95-telephony.ndjson", dashboard("ns8-telephony", "NS8 - Telephony",
    "Failed phone and NethVoice logins, and where they come from", [
    (vis("ns8-telephony-count", "Failures by service", APPS, PHONE,
         metric(group=terms("2", "service.name", "group", size=5))), 16, 8),
    (vis("ns8-telephony-timeline", "Failures over time", APPS, PHONE,
         over_time(terms("3", "service.name", "group", size=5), kind="histogram")), 32, 8),
    (vis("ns8-telephony-sip-sources", "SIP failures by source", APPS, SIP,
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.geo.city_name", "bucket", size=1, label="City", missing=True))), 24, 14),
    (vis("ns8-telephony-sip-users", "SIP failures by extension", APPS, SIP,
         table(terms("2", "user.name", "bucket", size=50, label="Extension"),
               terms("3", "event.code", "bucket", size=2, label="SIP status"))), 24, 14),
    (vis("ns8-telephony-map", "Failures map", APPS, PHONE, geo_map()), 48, 14),
], apps=True))

PVE = "service.type:proxmox"
PVE_AUTH = f"{PVE} and event.category:authentication"
PVE_TASK = f"{PVE} and event.action:task-started"
write("97-proxmox.ndjson", dashboard("ns8-proxmox", "NS8 - Proxmox",
    "Logins, virtual machine tasks and failed backups on Proxmox", [
    (vis("ns8-proxmox-logins", "Logins by outcome", APPS, PVE_AUTH,
         metric(group=terms("2", "event.outcome", "group", size=3))), 16, 8),
    (vis("ns8-proxmox-tasks-timeline", "Tasks over time", APPS, PVE_TASK,
         over_time(terms("3", "event.code", "group", size=10), kind="histogram")), 32, 8),
    (vis("ns8-proxmox-failed-sources", "Failed logins by source", APPS, f"{PVE_AUTH} and event.outcome:failure",
         table(terms("2", "source.ip", "bucket", size=50, label="Source IP"),
               terms("3", "user.name", "bucket", size=3, label="User"),
               terms("4", "source.geo.country_name", "bucket", size=1, label="Country", missing=True),
               terms("5", "source.geo.city_name", "bucket", size=1, label="City", missing=True))), 24, 14),
    (vis("ns8-proxmox-tasks-by-user", "Tasks by type and user", APPS, PVE_TASK,
         table(terms("2", "event.code", "bucket", size=30, label="Task"),
               terms("3", "user.name", "bucket", size=5, label="User"))), 24, 14),
    (search("ns8-proxmox-failed-tasks", "NS8 - Proxmox failed tasks", APPS,
            f"{PVE} and event.action:task-ended and event.outcome:failure",
            ["wazuh.agent.name", "event.code", "service.name", "user.name", "event.reason"]), 48, 12),
    (search("ns8-proxmox-destroyed", "NS8 - Proxmox deleted guests", APPS,
            f"{PVE_TASK} and event.code:(qmdestroy or vzdestroy)",
            ["wazuh.agent.name", "event.code", "service.name", "user.name"]), 48, 10),
    (vis("ns8-proxmox-map", "Failed logins map", APPS, f"{PVE_AUTH} and event.outcome:failure", geo_map()), 48, 14),
]))

# One list of raw lines, like journalctl: pick the customer and the server, then read
write("05-journal.ndjson", dashboard("ns8-journal", "NS8 - Journal",
    "Every log line, like journalctl. Pick a server, an application and a program, or search a word", [
    (search("ns8-journal-lines", "NS8 - Journal lines", EVENTS, "",
            ["wazuh.agent.name", "orchestrator.namespace", "process.name", "message"]), 48, 80),
], apps=True, program=True))
