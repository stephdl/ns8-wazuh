/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// The continent_code values of GeoIP. "@" keeps them apart from countries: NA is also Namibia
export const CONTINENTS = ["AF", "AN", "AS", "EU", "NA", "OC", "SA"];

const CONTINENT_NAMES = {
  AF: "Africa",
  AN: "Antarctica",
  AS: "Asia",
  EU: "Europe",
  NA: "North America",
  OC: "Oceania",
  SA: "South America",
};

// ISO 3166-1 alpha-2 codes; the browser gives their names in the language of the page
export const COUNTRIES = (
  "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ " +
  "BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM " +
  "DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS " +
  "GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN " +
  "KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ " +
  "MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM " +
  "PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV " +
  "SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI " +
  "VN VU WF WS XK YE YT ZA ZM ZW"
).split(" ");

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

// Label of a zone as stored by the backend: "FR" or "@EU"
export function zoneLabel(zone, locale, continentWord) {
  if (zone.startsWith("@")) {
    const code = zone.slice(1);
    return `${CONTINENT_NAMES[code] || code} (${continentWord})`;
  }
  return `${countryName(zone, locale)} (${zone})`;
}

// Options of NsMultiSelect: the continents first, then the countries by name
export function zoneOptions(locale, continentWord) {
  const continents = CONTINENTS.map((code) => {
    const value = "@" + code;
    return { value, label: zoneLabel(value, locale, continentWord), name: value };
  });
  const countries = COUNTRIES.map((code) => ({
    value: code,
    label: zoneLabel(code, locale, continentWord),
    name: code,
  })).sort((a, b) => a.label.localeCompare(b.label, locale));
  return continents.concat(countries);
}
