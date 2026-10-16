/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// The codes come from list-customers, so the page and the emails share one list.
// The browser names the countries in the language of the page.

function countryName(code, locale) {
  try {
    const name = new Intl.DisplayNames([locale || "en"], {
      type: "region",
    }).of(code);
    return name && name !== code ? name : code;
  } catch (e) {
    return code;
  }
}

// Label of a zone as stored by the backend: "FR" or "@EU", a continent
export function zoneLabel(zone, locale, continents, continentWord) {
  if (zone.startsWith("@")) {
    const code = zone.slice(1);
    return `${continents[code] || code} (${continentWord})`;
  }
  return `${countryName(zone, locale)} (${zone})`;
}

// Options of NsMultiSelect: the continents first, then the countries by name
export function zoneOptions(countries, continents, locale, continentWord) {
  const continentOptions = Object.keys(continents)
    .sort()
    .map((code) => {
      const value = "@" + code;
      return {
        value,
        label: zoneLabel(value, locale, continents, continentWord),
        name: value,
      };
    });
  const countryOptions = countries
    .map((code) => ({
      value: code,
      label: zoneLabel(code, locale, continents, continentWord),
      name: code,
    }))
    .sort((a, b) => a.label.localeCompare(b.label, locale));
  return continentOptions.concat(countryOptions);
}
