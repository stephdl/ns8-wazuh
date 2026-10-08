#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Build the indexer security documents that map an NS8 user domain to Wazuh."""

import copy

# The rootless pod reaches the host loopback, where the LDAP proxy listens, at this address
LDAP_HOST_FROM_POD = "10.0.2.2"

# Service accounts must keep using the internal database only
INTERNAL_USERS = ["admin", "kibanaserver", "wazuh-manager", "wazuh-wui"]

# kibana_read_only hides the dashboard buttons that would save objects
READONLY_INDEXER_ROLES = ["readall", "kibana_user", "kibana_read_only"]

# Names of the Wazuh API rules owned by the module, so they can be found and replaced
API_RULE_ADMIN = "ns8_ldap_admin"
API_RULE_READONLY = "ns8_ldap_readonly"


def _ldap_backend_config(domain, users_filter_clause=""):
    config = {
        "enable_ssl": False,
        "enable_start_tls": False,
        "enable_ssl_client_auth": False,
        "verify_hostnames": False,
        "hosts": [f"{LDAP_HOST_FROM_POD}:{domain['port']}"],
        "bind_dn": domain["bind_dn"],
        "password": domain["bind_password"],
        "userbase": domain["base_dn"],
        "resolve_nested_roles": False,
    }
    if domain["schema"] == "ad":
        config["usersearch"] = f"(&(sAMAccountName={{0}}){users_filter_clause})"
        config["username_attribute"] = "sAMAccountName"
        config["resolve_nested_roles"] = True
    else:
        config["usersearch"] = f"(&(uid={{0}}){users_filter_clause})"
        config["username_attribute"] = "uid"
    return config


def _ldap_authz_config(domain, users_filter_clause=""):
    config = _ldap_backend_config(domain, users_filter_clause)
    config["rolebase"] = domain["base_dn"]
    config["rolename"] = "cn"
    config["userrolename"] = "disabled"
    if domain["schema"] == "ad":
        config["rolesearch"] = "(member={0})"
    else:
        # {1} is the user name, rfc2307 groups list their members by uid
        config["rolesearch"] = "(memberUid={1})"
    return config


def build_security_config(default_config, domain=None, users_filter_clause=""):
    """Return the security config document, with the LDAP domain when given.

    The result is always derived from the image default, so applying it twice
    gives the same document and removing the domain removes its entries."""
    document = copy.deepcopy(default_config)
    dynamic = document["config"]["dynamic"]
    dynamic.get("authc", {}).pop("ns8_ldap", None)
    dynamic.setdefault("authz", {}).pop("ns8_ldap_roles", None)
    if domain is None:
        return document
    dynamic["authc"]["ns8_ldap"] = {
        "description": "NS8 user domain",
        "http_enabled": True,
        "transport_enabled": False,
        "order": 5,
        "http_authenticator": {"type": "basic", "challenge": False},
        "authentication_backend": {
            "type": "ldap",
            "config": _ldap_backend_config(domain, users_filter_clause),
        },
    }
    dynamic["authz"]["ns8_ldap_roles"] = {
        "description": "Groups of the NS8 user domain",
        "http_enabled": True,
        "transport_enabled": False,
        "authorization_backend": {
            "type": "ldap",
            "config": _ldap_authz_config(domain, users_filter_clause),
        },
    }
    return document


def _map_group(document, role, group):
    entry = document.setdefault(role, {"reserved": False})
    backend_roles = entry.setdefault("backend_roles", [])
    if group not in backend_roles:
        backend_roles.append(group)


def build_roles_mapping(default_mapping, admin_group=None, readonly_group=None):
    """Return the roles mapping document, with the admin group mapped to all_access
    and the read-only group mapped to the roles that open the dashboard without writing."""
    document = copy.deepcopy(default_mapping)
    if admin_group:
        _map_group(document, "all_access", admin_group)
    if readonly_group:
        for role in READONLY_INDEXER_ROLES:
            _map_group(document, role, readonly_group)
    return document


def build_api_rules(admin_group=None, readonly_group=None):
    """Return the Wazuh API rules that give the same groups the matching API role.

    The dashboard calls the API on behalf of the user, and the API only knows
    the groups as backend_roles, so each group needs its own rule."""
    rules = {}
    if admin_group:
        rules[API_RULE_ADMIN] = ("administrator", {"MATCH": {"backend_roles": [admin_group]}})
    if readonly_group:
        rules[API_RULE_READONLY] = ("readonly", {"MATCH": {"backend_roles": [readonly_group]}})
    return rules
