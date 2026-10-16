#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Settings of each customer: the zones its users may log in from, and who gets its login alerts.
# The zones go to a KVDB that the login zone decoder reads, because a rule never sees the GeoIP fields.

import json
import os

from wazuh_api import api

CUSTOMERS_FILE = os.environ.get("CUSTOMERS_FILE", "customers.json")
CM = "_plugins/_content_manager"
KVDB_TITLE = "ns8-login-zones"
# The continent_code values of GeoIP. A zone "@EU" is a continent: NA or AS alone are countries
CONTINENTS = {"AF": "Africa", "AN": "Antarctica", "AS": "Asia", "EU": "Europe", "NA": "North America",
              "OC": "Oceania", "SA": "South America"}
# English short names of ISO 3166-1, for the emails: a code alone like PM tells nothing
COUNTRIES = {
    "AD": "Andorra", "AE": "United Arab Emirates", "AF": "Afghanistan", "AG": "Antigua and Barbuda",
    "AI": "Anguilla", "AL": "Albania", "AM": "Armenia", "AO": "Angola", "AQ": "Antarctica",
    "AR": "Argentina", "AS": "American Samoa", "AT": "Austria", "AU": "Australia", "AW": "Aruba",
    "AX": "Åland Islands", "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BB": "Barbados",
    "BD": "Bangladesh", "BE": "Belgium", "BF": "Burkina Faso", "BG": "Bulgaria", "BH": "Bahrain",
    "BI": "Burundi", "BJ": "Benin", "BL": "Saint Barthélemy", "BM": "Bermuda", "BN": "Brunei",
    "BO": "Bolivia", "BQ": "Bonaire, Sint Eustatius and Saba", "BR": "Brazil", "BS": "Bahamas",
    "BT": "Bhutan", "BV": "Bouvet Island", "BW": "Botswana", "BY": "Belarus", "BZ": "Belize", "CA": "Canada",
    "CC": "Cocos (Keeling) Islands", "CD": "DR Congo", "CF": "Central African Republic", "CG": "Congo",
    "CH": "Switzerland", "CI": "Côte d'Ivoire", "CK": "Cook Islands", "CL": "Chile", "CM": "Cameroon",
    "CN": "China", "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba", "CV": "Cape Verde", "CW": "Curaçao",
    "CX": "Christmas Island", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DJ": "Djibouti",
    "DK": "Denmark", "DM": "Dominica", "DO": "Dominican Republic", "DZ": "Algeria", "EC": "Ecuador",
    "EE": "Estonia", "EG": "Egypt", "EH": "Western Sahara", "ER": "Eritrea", "ES": "Spain", "ET": "Ethiopia",
    "FI": "Finland", "FJ": "Fiji", "FK": "Falkland Islands", "FM": "Micronesia", "FO": "Faroe Islands",
    "FR": "France", "GA": "Gabon", "GB": "United Kingdom", "GD": "Grenada", "GE": "Georgia",
    "GF": "French Guiana", "GG": "Guernsey", "GH": "Ghana", "GI": "Gibraltar", "GL": "Greenland",
    "GM": "Gambia", "GN": "Guinea", "GP": "Guadeloupe", "GQ": "Equatorial Guinea", "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands", "GT": "Guatemala", "GU": "Guam",
    "GW": "Guinea-Bissau", "GY": "Guyana", "HK": "Hong Kong", "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras", "HR": "Croatia", "HT": "Haiti", "HU": "Hungary", "ID": "Indonesia", "IE": "Ireland",
    "IL": "Israel", "IM": "Isle of Man", "IN": "India", "IO": "British Indian Ocean Territory", "IQ": "Iraq",
    "IR": "Iran", "IS": "Iceland", "IT": "Italy", "JE": "Jersey", "JM": "Jamaica", "JO": "Jordan",
    "JP": "Japan", "KE": "Kenya", "KG": "Kyrgyzstan", "KH": "Cambodia", "KI": "Kiribati", "KM": "Comoros",
    "KN": "Saint Kitts and Nevis", "KP": "North Korea", "KR": "South Korea", "KW": "Kuwait",
    "KY": "Cayman Islands", "KZ": "Kazakhstan", "LA": "Laos", "LB": "Lebanon", "LC": "Saint Lucia",
    "LI": "Liechtenstein", "LK": "Sri Lanka", "LR": "Liberia", "LS": "Lesotho", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "LY": "Libya", "MA": "Morocco", "MC": "Monaco", "MD": "Moldova",
    "ME": "Montenegro", "MF": "Saint Martin (French part)", "MG": "Madagascar", "MH": "Marshall Islands",
    "MK": "North Macedonia", "ML": "Mali", "MM": "Myanmar", "MN": "Mongolia", "MO": "Macao",
    "MP": "Northern Mariana Islands", "MQ": "Martinique", "MR": "Mauritania", "MS": "Montserrat",
    "MT": "Malta", "MU": "Mauritius", "MV": "Maldives", "MW": "Malawi", "MX": "Mexico", "MY": "Malaysia",
    "MZ": "Mozambique", "NA": "Namibia", "NC": "New Caledonia", "NE": "Niger", "NF": "Norfolk Island",
    "NG": "Nigeria", "NI": "Nicaragua", "NL": "Netherlands", "NO": "Norway", "NP": "Nepal", "NR": "Nauru",
    "NU": "Niue", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama", "PE": "Peru", "PF": "French Polynesia",
    "PG": "Papua New Guinea", "PH": "Philippines", "PK": "Pakistan", "PL": "Poland",
    "PM": "Saint Pierre and Miquelon", "PN": "Pitcairn Islands", "PR": "Puerto Rico", "PS": "Palestine",
    "PT": "Portugal", "PW": "Palau", "PY": "Paraguay", "QA": "Qatar", "RE": "Reunion", "RO": "Romania",
    "RS": "Serbia", "RU": "Russia", "RW": "Rwanda", "SA": "Saudi Arabia", "SB": "Solomon Islands",
    "SC": "Seychelles", "SD": "Sudan", "SE": "Sweden", "SG": "Singapore", "SH": "Saint Helena",
    "SI": "Slovenia", "SJ": "Svalbard and Jan Mayen", "SK": "Slovakia", "SL": "Sierra Leone",
    "SM": "San Marino", "SN": "Senegal", "SO": "Somalia", "SR": "Suriname", "SS": "South Sudan",
    "ST": "Sao Tome and Principe", "SV": "El Salvador", "SX": "Sint Maarten (Dutch part)", "SY": "Syria",
    "SZ": "Eswatini", "TC": "Turks and Caicos Islands", "TD": "Chad", "TF": "French Southern Territories",
    "TG": "Togo", "TH": "Thailand", "TJ": "Tajikistan", "TK": "Tokelau", "TL": "Timor-Leste",
    "TM": "Turkmenistan", "TN": "Tunisia", "TO": "Tonga", "TR": "Türkiye", "TT": "Trinidad and Tobago",
    "TV": "Tuvalu", "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraine", "UG": "Uganda",
    "UM": "United States Minor Outlying Islands", "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
    "VA": "Vatican City", "VC": "Saint Vincent and the Grenadines", "VE": "Venezuela",
    "VG": "British Virgin Islands", "VI": "U.S. Virgin Islands", "VN": "Vietnam", "VU": "Vanuatu",
    "WF": "Wallis and Futuna", "WS": "Samoa", "XK": "Kosovo", "YE": "Yemen", "YT": "Mayotte",
    "ZA": "South Africa", "ZM": "Zambia", "ZW": "Zimbabwe"
}


def load():
    try:
        with open(CUSTOMERS_FILE) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    data.setdefault("customers", {})
    return data


def save(data):
    tmp = CUSTOMERS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CUSTOMERS_FILE)


def kvdb_content(data):
    """customer:list marks a customer with zones, customer:FR and customer:@EU are its zones."""
    content = {}
    for name, customer in data["customers"].items():
        zones = customer.get("zones", [])
        if zones:
            content[f"{name}:list"] = True
            content.update({f"{name}:{zone}": True for zone in zones})
    # The Content Manager refuses an empty KVDB
    return content or {"none:list": False}


def _draft_id(index, title):
    answer = api("POST", f"{index}/_search", {"size": 50, "query": {"bool": {"filter": [
        {"match_phrase": {"space.name": "draft"}}, {"match_phrase": {"document.metadata.title": title}}]}}})
    for hit in answer.get("hits", {}).get("hits", []):
        if hit["_source"]["document"]["metadata"]["title"] == title:
            return hit["_id"]
    return None


def integration_id(title="ns8"):
    return _draft_id("wazuh-threatintel-integrations", title)


def write_kvdb(integration):
    """Create or update the KVDB of the zones in the draft space; the caller promotes it."""
    resource = {
        "metadata": {"title": KVDB_TITLE, "description": "Zones the users of each customer may log in from",
                     "author": "NethServer", "references": ["https://github.com/stephdl/ns8-wazuh"]},
        "enabled": True,
        "content": kvdb_content(load()),
    }
    existing = _draft_id("wazuh-threatintel-kvdbs", KVDB_TITLE)
    if existing:
        answer = api("PUT", f"{CM}/kvdbs/{existing}", {"resource": resource})
    else:
        answer = api("POST", f"{CM}/kvdbs", {"integration": integration, "resource": resource})
    if answer.get("status") not in (200, 201):
        raise RuntimeError(f"{KVDB_TITLE}: {answer.get('message', answer)}")


def promote():
    # A change needs both steps to reach the space the engine runs
    for space in ("draft", "test"):
        changes = api("GET", f"{CM}/promote?space={space}").get("changes", {})
        if any(changes.get(kind) for kind in changes):
            answer = api("POST", f"{CM}/promote", {"space": space, "changes": changes})
            if answer.get("status") != 200:
                raise RuntimeError(f"promotion from {space}: {answer.get('message', answer)}")


def zone_name(zone):
    """FR gives France (FR), @EU gives Europe (continent)."""
    if zone.startswith("@"):
        return f"{CONTINENTS.get(zone[1:], zone[1:])} (continent)"
    return f"{COUNTRIES.get(zone, zone)} ({zone})"
