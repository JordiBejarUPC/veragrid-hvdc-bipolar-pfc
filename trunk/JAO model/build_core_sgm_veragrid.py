"""Build a topology-only VeraGrid model from the 2026 Core SGM release.

The source workbook contains the electrical equipment and ratings.  The HTML
publication contains the map coordinates.  This importer deliberately does not
create injections or operating points; it creates the physical topology only.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import statistics
import sys
import unicodedata
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import openpyxl
from scipy.spatial import cKDTree


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import VeraGridEngine.api as gce  # noqa: E402


DEFAULT_SOURCE_DIR = Path(
    r"C:\Users\nuagb\Downloads\202603_Core Static Grid Model_9th release"
    r"\202603_Core Static Grid Model_9th release"
)
DEFAULT_XLSX = DEFAULT_SOURCE_DIR / "202603_Core Static Grid Model_External.xlsx"
DEFAULT_HTML = DEFAULT_SOURCE_DIR / "2026-03-16_Core_SGM_publication.html"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "Core_SGM_2026_topology.veragrid"

SBASE_MVA = 100.0
SQRT3 = math.sqrt(3.0)
NS = uuid.UUID("4f642fba-4f00-45ae-89e8-bebfd9c1745e")

ENTSOE_MILIN_SOURCE = (
    "https://eepublicdownloads.entsoe.eu/tyndp-documents/IoSN2020/"
    "200810_RegIP2020_CCE_beforeconsultation.pdf"
)
ERU_MILIN_SOURCE = "https://eru.gov.cz/sites/default/files/obsah/prilohy/navrh-dprps-2023-2032.pdf"
ERU_OLD_LINE_SOURCE = (
    "https://eru.gov.cz/sites/default/files/import_files/"
    "P%C5%99%C3%ADloha%202%20-%20PPPS%20%C4%8C%C3%A1st%20VII_%20-%20"
    "Za%C5%99%C3%ADzen%C3%AD%20PS%20-%20revize.pdf"
)
TRANSELECTRICA_SOURCE = (
    "https://www.transelectrica.ro/documents/10179/17407876/"
    "2_1_Note%2Bon%2Bthe%2Bapproval%2Bby%2BThe%2BGeneral%2BMeeting%2Bof%2B"
    "Shareholders%2Bof%2BETG%2BDevelopment%2BPlan%2B2024-2033.pdf/"
    "f3e1c19f-34c9-4e05-b182-2e650799a5d9"
)

MANUAL_COORDINATES = {
    # The publication map omits these three external tie-line geometries.
    norm_name: (latitude, longitude, source)
    for norm_name, latitude, longitude, source in [
        ("camporosso", 43.8277778, 7.6297222, "Wikimedia/OSM Camporosso substation coordinate"),
        ("menton trinite victor", 43.7416667, 7.3147222, "La Trinite municipality coordinate; substation-level approximation"),
        ("arkale", 43.30507, -1.84244, "OpenStreetMap Arkale substation coordinate"),
        ("argia", 43.42319, -1.42899, "OpenStreetMap Argia site coordinate"),
        ("hernani", 43.27095, -1.96375, "OpenStreetMap Hernani substation coordinate"),
    ]
}
MANUAL_COORDINATE_REFERENCES = {
    "Camporosso": "https://commons.wikimedia.org/wiki/Category:Camporosso_substation",
    "Menton/Trinite Victor": "https://fr.wikipedia.org/wiki/La_Trinit%C3%A9_(Alpes-Maritimes)",
    "Arkale": "https://mapcarta.com/W31110032",
    "Argia": "https://mapcarta.com/W78770178",
    "Hernani": "https://mapcarta.com/W1316397504",
}


COUNTRY_NAMES = {
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "ES": "Spain",
    "FR": "France",
    "HR": "Croatia",
    "HU": "Hungary",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "UA": "Ukraine",
}

TSO_COUNTRY = {
    "50HERTZ": "DE",
    "AMPRION GMBH": "DE",
    "APG": "AT",
    "CEPS": "CZ",
    "CREOS": "LU",
    "ELES": "SI",
    "ELIA": "BE",
    "HOPS": "HR",
    "MAVIR": "HU",
    "PSE": "PL",
    "RTE": "FR",
    "SEPS": "SK",
    "TEL": "RO",
    "TENNET NL": "NL",
    "TENNETGMBH": "DE",
    "TRANSNETBW": "DE",
}

DEFAULT_TSO_BY_COUNTRY = {
    "AT": "APG",
    "BA": "NOSBiH",
    "BE": "ELIA",
    "BG": "ESO Bulgaria",
    "CH": "Swissgrid",
    "CZ": "CEPS",
    "DK": "Energinet",
    "ES": "Red Electrica de Espana",
    "FR": "RTE",
    "HR": "HOPS",
    "HU": "MAVIR",
    "IT": "Terna",
    "LT": "Litgrid",
    "LU": "Creos",
    "NL": "TenneT NL",
    "NO": "Statnett",
    "PL": "PSE",
    "RO": "TEL",
    "RS": "EMS Serbia",
    "SE": "Svenska kraftnaet",
    "SI": "ELES",
    "SK": "SEPS",
    "UA": "Ukrenergo",
}


def stable_id(kind: str, key: str) -> str:
    return uuid.uuid5(NS, f"{kind}|{key}").hex


def norm(value: Any) -> str:
    if value is None:
        return ""
    text = html_lib.unescape(str(value)).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss").replace("ø", "o").replace("ł", "l")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    text = str(value).replace("\xa0", " ").strip().replace(",", ".")
    if not text:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    return val if math.isfinite(val) else None


def normalize_voltage(value: Any) -> float | None:
    value = number(value)
    if value is None or value <= 0:
        return None
    if value >= 550:
        return 750.0
    if value >= 275:
        return 380.0
    if value >= 180:
        return 220.0
    if value >= 135:
        return 150.0
    return 110.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def choose_current(values: tuple[Any, ...]) -> tuple[float | None, str]:
    periods = [number(v) for v in values[6:12]]
    periods = [v for v in periods if v is not None and v > 0]
    fixed = number(values[12])
    dlr_max = number(values[14])
    if dlr_max is not None and dlr_max > 0:
        return dlr_max, "DLR maximum"
    if fixed is not None and fixed > 0:
        return fixed, "fixed"
    if periods:
        return max(periods), "maximum seasonal period"
    return None, "missing"


def transformer_current(values: tuple[Any, ...]) -> tuple[float | None, str]:
    lo = number(values[3])
    hi = number(values[4])
    fixed = number(values[5])
    candidates = [v for v in (lo, hi) if v is not None and v > 0]
    if candidates:
        return max(candidates), "maximum min/max rating"
    if fixed is not None and fixed > 0:
        return fixed, "fixed"
    return None, "missing"


def extract_lat_lng(value: Any) -> tuple[list[float], list[float]] | None:
    if isinstance(value, dict):
        if "lat" in value and "lng" in value:
            return list(value["lat"]), list(value["lng"])
        for child in value.values():
            found = extract_lat_lng(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = extract_lat_lng(child)
            if found is not None:
                return found
    return None


def parse_label(label: str) -> tuple[str, str]:
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", label or ""))
    clean = re.sub(r"\s+", " ", clean).strip()
    name_match = re.search(r"NE name:\s*(.*?)\s+EIC Code:", clean, re.IGNORECASE)
    eic_match = re.search(r"EIC Code:\s*(\S+)", clean, re.IGNORECASE)
    return (name_match.group(1).strip() if name_match else "", eic_match.group(1).strip() if eic_match else "")


def parse_html_map(path: Path) -> tuple[list[tuple[float, float]], list[tuple[float, float]], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json"[^>]*>(.*?)</script>', text, re.DOTALL)
    if not match:
        raise ValueError(f"No leaflet JSON payload found in {path}")
    payload = json.loads(match.group(1))
    calls = payload["x"]["calls"]

    circle_calls = [c for c in calls if c["method"] == "addCircleMarkers"]
    transformer_call = next(c for c in circle_calls if c["args"][4] == "Transformers")
    substation_call = next(c for c in circle_calls if c["args"][4] == "Substations")
    transformer_coords = list(zip(map(float, transformer_call["args"][0]), map(float, transformer_call["args"][1])))
    substation_coords = list(zip(map(float, substation_call["args"][0]), map(float, substation_call["args"][1])))

    polyline_call = next(c for c in calls if c["method"] == "addPolylines" and c["args"][2] == "Lines")
    geometries: list[dict[str, Any]] = []
    for geometry, label in zip(polyline_call["args"][0], polyline_call["args"][6]):
        lat_lng = extract_lat_lng(geometry)
        if lat_lng is None:
            continue
        lats, lngs = lat_lng
        if not lats or not lngs:
            continue
        name, eic = parse_label(label)
        geometries.append(
            {
                "name": name,
                "eic": eic,
                "key": (norm(name), norm(eic)),
                "start": (float(lats[0]), float(lngs[0])),
                "end": (float(lats[-1]), float(lngs[-1])),
            }
        )
    return transformer_coords, substation_coords, geometries


@dataclass
class LineRecord:
    sheet: str
    row: int
    name: str
    eic: str
    tso: str
    station_a: str
    station_b: str
    raw_voltage: float | None
    values: tuple[Any, ...]
    current_a: float | None
    rating_basis: str
    r_ohm: float | None
    x_ohm: float | None
    b_us: float | None
    length_km: float | None
    source_comment: str
    geometry: dict[str, Any] | None = None
    direct_rate_mva: float | None = None
    inference_notes: list[str] = field(default_factory=list)

    @property
    def station_keys(self) -> tuple[str, str]:
        return norm(self.station_a), norm(self.station_b)


@dataclass
class TransformerRecord:
    row: int
    name: str
    eic: str
    tso: str
    current_a: float | None
    rating_basis: str
    primary_kv: float | None
    secondary_kv: float | None
    r_ohm: float | None
    x_ohm: float | None
    b_us: float | None
    g_us: float | None
    source_comment: str
    coord: tuple[float, float]
    station_key: str = ""
    direct_rate_mva: float | None = None
    inference_notes: list[str] = field(default_factory=list)


def load_workbook_records(path: Path) -> tuple[list[LineRecord], list[TransformerRecord], list[dict[str, Any]]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    decommissioned: dict[tuple[str, str, str], dict[str, Any]] = {}
    decommission_log: list[dict[str, Any]] = []
    for row in wb["Change Log"].iter_rows(min_row=3, values_only=True):
        version = number(row[1])
        description = str(row[6] or "")
        if version == 9 and "decommission" in description.lower():
            sheet = str(row[3] or "").strip()
            eic = norm(row[5])
            key = (sheet, eic, norm(row[4]))
            decommissioned[key] = {"sheet": sheet, "name": row[4], "eic": row[5], "reason": description}

    line_records: list[LineRecord] = []
    for sheet in ("Lines", "Tielines"):
        for row_idx, values in enumerate(wb[sheet].iter_rows(min_row=3, values_only=True), start=3):
            if not values[0]:
                continue
            eic = str(values[1] or "").strip()
            decommission_key = (sheet, norm(eic), norm(values[0]))
            if decommission_key in decommissioned:
                decommission_log.append(decommissioned[decommission_key])
                continue
            current, basis = choose_current(values)
            line_records.append(
                LineRecord(
                    sheet=sheet,
                    row=row_idx,
                    name=str(values[0]).strip(),
                    eic=eic,
                    tso=str(values[2] or "Unknown TSO").strip(),
                    station_a=str(values[3] or f"Unknown A row {row_idx}").strip(),
                    station_b=str(values[4] or f"Unknown B row {row_idx}").strip(),
                    raw_voltage=number(values[5]),
                    values=tuple(values),
                    current_a=current,
                    rating_basis=basis,
                    r_ohm=number(values[15]),
                    x_ohm=number(values[16]),
                    b_us=number(values[17]),
                    length_km=number(values[18]),
                    source_comment=str(values[19] or "").strip(),
                )
            )

    transformers: list[TransformerRecord] = []
    rows = [r for r in wb["Transformers"].iter_rows(min_row=3, values_only=True) if r[0]]
    for row_idx, values in enumerate(rows, start=3):
        current, basis = transformer_current(values)
        transformers.append(
            TransformerRecord(
                row=row_idx,
                name=str(values[0]).strip(),
                eic=str(values[1] or "").strip(),
                tso=str(values[2] or "Unknown TSO").strip(),
                current_a=current,
                rating_basis=basis,
                primary_kv=number(values[6]),
                secondary_kv=number(values[7]),
                r_ohm=number(values[8]),
                x_ohm=number(values[9]),
                b_us=number(values[10]),
                g_us=number(values[11]),
                source_comment=str(values[17] or "").strip(),
                coord=(0.0, 0.0),
            )
        )
    return line_records, transformers, decommission_log


def match_geometries(records: list[LineRecord], geometries: list[dict[str, Any]]) -> int:
    queues: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for item in geometries:
        queues[item["key"]].append(item)
    matched = 0
    for rec in records:
        key = (norm(rec.name), norm(rec.eic))
        if queues[key]:
            rec.geometry = queues[key].popleft()
            matched += 1
    return matched


def marker_tree(coords: list[tuple[float, float]]) -> tuple[cKDTree, np.ndarray]:
    scaled = np.asarray([[lat, lon * 0.65] for lat, lon in coords], dtype=float)
    return cKDTree(scaled), scaled


def nearest_marker(tree: cKDTree, point: tuple[float, float]) -> tuple[int, float]:
    distance, idx = tree.query([point[0], point[1] * 0.65], k=1)
    return int(idx), float(distance) * 111.0


def station_coordinates(
    records: list[LineRecord],
    marker_coords: list[tuple[float, float]],
) -> tuple[dict[str, int], dict[str, tuple[float, float]], dict[str, str], dict[str, str]]:
    tree, _ = marker_tree(marker_coords)
    observations: dict[str, list[tuple[float, float]]] = defaultdict(list)
    labels: dict[str, str] = {}
    neighbors: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        a, b = rec.station_keys
        labels.setdefault(a, rec.station_a)
        labels.setdefault(b, rec.station_b)
        neighbors[a].add(b)
        neighbors[b].add(a)
        if rec.geometry is not None:
            observations[a].append(rec.geometry["start"])
            observations[b].append(rec.geometry["end"])

    markers: dict[str, int] = {}
    coords: dict[str, tuple[float, float]] = {}
    sources: dict[str, str] = {}
    for station, points in observations.items():
        votes = Counter(nearest_marker(tree, p)[0] for p in points)
        marker = votes.most_common(1)[0][0]
        markers[station] = marker
        coords[station] = marker_coords[marker]
        sources[station] = "HTML line endpoint snapped to HTML substation marker"

    unresolved = set(labels).difference(coords)
    for _ in range(8):
        progressed = False
        for station in list(unresolved):
            known = [coords[n] for n in neighbors[station] if n in coords]
            if not known:
                continue
            point = (statistics.median(p[0] for p in known), statistics.median(p[1] for p in known))
            marker, _ = nearest_marker(tree, point)
            markers[station] = marker
            coords[station] = marker_coords[marker]
            sources[station] = "inferred from connected substations and snapped to HTML marker"
            unresolved.remove(station)
            progressed = True
        if not progressed:
            break

    manual_index = -1
    for station in list(unresolved):
        manual = MANUAL_COORDINATES.get(station)
        if manual is None:
            continue
        latitude, longitude, source = manual
        markers[station] = manual_index
        manual_index -= 1
        coords[station] = (latitude, longitude)
        sources[station] = source
        unresolved.remove(station)

    if unresolved:
        all_lat = statistics.median(p[0] for p in marker_coords)
        all_lon = statistics.median(p[1] for p in marker_coords)
        for station in unresolved:
            marker, _ = nearest_marker(tree, (all_lat, all_lon))
            markers[station] = marker
            coords[station] = marker_coords[marker]
            sources[station] = "fallback to central HTML substation marker"
    return markers, coords, labels, sources


def transformer_station_name(name: str) -> str:
    text = re.sub(r"^(?:TR|PST)\s*", "", name, flags=re.IGNORECASE).strip()
    slash_format = re.search(r"/\s*\d{3}\s*-\s*\d{3}\s*kV\s*/\s*([^/]+?)(?:\s*/|$)", name, re.IGNORECASE)
    if slash_format:
        return slash_format.group(1).strip()
    text = re.split(r"\s+\d{2,3}(?:[.,]\d+)?\s*/\s*\d{2,3}", text, maxsplit=1)[0].strip()
    text = re.split(r"\s+\d{3}\s*kV\s+TR\s*\d", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    text = re.split(r"\s+(?:TR|PST)\s*[A-Z]*\d", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    text = re.sub(r"\s+(?:T|AT)\d+[A-Z]*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+\d+$", "", text).strip()
    return text or name


def add_transformer_stations(
    transformers: list[TransformerRecord],
    transformer_coords: list[tuple[float, float]],
    marker_coords: list[tuple[float, float]],
    station_markers: dict[str, int],
    station_coords_map: dict[str, tuple[float, float]],
    station_labels: dict[str, str],
    coordinate_sources: dict[str, str],
) -> None:
    if len(transformers) != len(transformer_coords):
        raise ValueError(f"Transformer count mismatch: workbook={len(transformers)} map={len(transformer_coords)}")
    tree, _ = marker_tree(marker_coords)
    marker_to_stations: dict[int, list[str]] = defaultdict(list)
    for station, marker in station_markers.items():
        marker_to_stations[marker].append(station)

    for rec, coord in zip(transformers, transformer_coords):
        rec.coord = coord
        marker, _ = nearest_marker(tree, coord)
        candidate_label = transformer_station_name(rec.name)
        candidate = norm(candidate_label)
        options = marker_to_stations.get(marker, [])
        chosen = ""
        if candidate in station_labels:
            chosen = candidate
        elif options:
            def score(station: str) -> float:
                target = norm(station_labels[station])
                if candidate in target or target in candidate:
                    return 1.0
                return SequenceMatcher(None, candidate, target).ratio()

            best = max(options, key=score)
            if len(options) == 1 or score(best) >= 0.45:
                chosen = best
        if not chosen:
            chosen = candidate
            if chosen in station_labels and station_markers.get(chosen) != marker:
                chosen = f"{candidate} {norm(rec.tso)} {marker}"
            station_labels[chosen] = candidate_label
            station_markers[chosen] = marker
            station_coords_map[chosen] = marker_coords[marker]
            coordinate_sources[chosen] = "HTML transformer coordinate snapped to HTML substation marker"
            marker_to_stations[marker].append(chosen)
        rec.station_key = chosen


def infer_missing_source_values(
    lines: list[LineRecord],
    transformers: list[TransformerRecord],
    station_coords_map: dict[str, tuple[float, float]],
) -> list[dict[str, Any]]:
    fills: list[dict[str, Any]] = []
    voltage_evidence: dict[str, Counter[float]] = defaultdict(Counter)
    for rec in lines:
        if rec.raw_voltage:
            voltage_evidence[rec.station_keys[0]][rec.raw_voltage] += 1
            voltage_evidence[rec.station_keys[1]][rec.raw_voltage] += 1
    for rec in lines:
        if rec.raw_voltage is None:
            a, b = rec.station_keys
            common = set(voltage_evidence[a]).intersection(voltage_evidence[b])
            if common:
                rec.raw_voltage = max(common, key=lambda v: voltage_evidence[a][v] + voltage_evidence[b][v])
            else:
                combined = voltage_evidence[a] + voltage_evidence[b]
                rec.raw_voltage = combined.most_common(1)[0][0] if combined else 380.0
            rec.inference_notes.append(f"Missing voltage inferred as {rec.raw_voltage:g} kV from connected equipment")
            fills.append({"element": rec.name, "field": "voltage", "value": rec.raw_voltage, "method": "connected equipment"})

    ceps_specific = []
    for rec in lines:
        if (
            rec.sheet == "Lines"
            and norm(rec.tso) == "ceps"
            and normalize_voltage(rec.raw_voltage) == 380.0
            and rec.length_km and rec.length_km > 0
            and rec.r_ohm is not None and rec.x_ohm is not None and rec.b_us is not None
        ):
            ceps_specific.append((rec.r_ohm / rec.length_km, rec.x_ohm / rec.length_km, rec.b_us / rec.length_km))
    if not ceps_specific:
        raise ValueError("No CEPS 380 kV reference lines available for missing-parameter inference")
    r_per_km = statistics.median(v[0] for v in ceps_specific)
    x_per_km = statistics.median(v[1] for v in ceps_specific)
    b_per_km = statistics.median(v[2] for v in ceps_specific)

    czech = {rec.eic: rec for rec in lines if rec.eic in {"27T-TLI-V477MR-D", "27T-TLI-V475KM-9"}}
    if len(czech) == 2:
        distances: dict[str, float] = {}
        for eic, rec in czech.items():
            a, b = rec.station_keys
            distances[eic] = max(0.1, haversine_km(station_coords_map[a], station_coords_map[b]))
        route_total = 137.7 + 0.7
        scale = route_total / sum(distances.values())
        for eic, rec in czech.items():
            rec.length_km = distances[eic] * scale
            rec.r_ohm = r_per_km * rec.length_km
            rec.x_ohm = x_per_km * rec.length_km
            rec.b_us = b_per_km * rec.length_km
            rec.direct_rate_mva = 1730.0
            rec.rating_basis = "ENTSO-E target capacity"
            rec.inference_notes.extend(
                [
                    "1730 MVA rating from ENTSO-E Regional Investment Plan 2020 (2x1730 MVA loop)",
                    "Length allocated by mapped endpoint distance from the 137.7 km former V475 route plus 0.7 km Milin loop",
                    "R/X/B inferred from median CEPS 380 kV per-km parameters in this release",
                ]
            )
            fills.extend(
                [
                    {"element": rec.name, "field": "rate", "value": 1730.0, "unit": "MVA", "method": ENTSOE_MILIN_SOURCE},
                    {"element": rec.name, "field": "length", "value": rec.length_km, "unit": "km", "method": "official route lengths allocated by mapped distance"},
                    {"element": rec.name, "field": "R/X/B", "value": [rec.r_ohm, rec.x_ohm, rec.b_us], "method": "median CEPS 380 kV specific parameters"},
                ]
            )

    current_by_class: dict[tuple[str, float], list[float]] = defaultdict(list)
    for rec in lines:
        voltage = normalize_voltage(rec.raw_voltage)
        if voltage and rec.current_a is not None and rec.current_a > 0:
            current_by_class[(norm(rec.tso), voltage)].append(rec.current_a)
    for rec in lines:
        if rec.current_a is not None or rec.direct_rate_mva is not None:
            continue
        voltage = normalize_voltage(rec.raw_voltage)
        references = current_by_class.get((norm(rec.tso), voltage or 0.0), [])
        if not references:
            raise ValueError(f"Cannot infer missing rating for {rec.name}")
        rec.current_a = statistics.median(references)
        rec.rating_basis = "median TSO and voltage-class current"
        rec.inference_notes.append(
            f"Missing current rating inferred as {rec.current_a:g} A from the median for this TSO and voltage class"
        )
        fills.append(
            {
                "element": rec.name,
                "field": "current rating",
                "value": rec.current_a,
                "unit": "A",
                "method": "median TSO and voltage-class current in this release",
            }
        )

    for rec in lines:
        if rec.length_km is None:
            a, b = rec.station_keys
            rec.length_km = max(0.1, haversine_km(station_coords_map[a], station_coords_map[b]) * 1.08)
            rec.inference_notes.append("Missing length inferred as 1.08 times mapped straight-line distance")
            fills.append({"element": rec.name, "field": "length", "value": rec.length_km, "unit": "km", "method": "mapped distance x 1.08"})

    specific_by_class: dict[tuple[str, float], list[tuple[float, float, float]]] = defaultdict(list)
    for rec in lines:
        voltage = normalize_voltage(rec.raw_voltage)
        if (
            voltage
            and rec.length_km and rec.length_km > 0
            and rec.r_ohm is not None and rec.x_ohm is not None and rec.b_us is not None
        ):
            specific_by_class[(norm(rec.tso), voltage)].append(
                (rec.r_ohm / rec.length_km, rec.x_ohm / rec.length_km, rec.b_us / rec.length_km)
            )
    for rec in lines:
        if rec.r_ohm is not None and rec.x_ohm is not None and rec.b_us is not None:
            continue
        voltage = normalize_voltage(rec.raw_voltage)
        references = specific_by_class.get((norm(rec.tso), voltage or 0.0), [])
        if rec.b_us is None and rec.r_ohm is not None and rec.x_ohm is not None and "-" in str(rec.values[17]):
            rec.b_us = 0.0
            method = "source dash interpreted as zero shunt susceptance"
        elif references and rec.length_km:
            rpk = statistics.median(v[0] for v in references)
            xpk = statistics.median(v[1] for v in references)
            bpk = statistics.median(v[2] for v in references)
            rec.r_ohm = rec.r_ohm if rec.r_ohm is not None else rpk * rec.length_km
            rec.x_ohm = rec.x_ohm if rec.x_ohm is not None else xpk * rec.length_km
            rec.b_us = rec.b_us if rec.b_us is not None else bpk * rec.length_km
            method = "median TSO and voltage-class specific parameters"
        else:
            raise ValueError(f"Cannot infer missing R/X/B for {rec.name}")
        rec.inference_notes.append(method)
        fills.append(
            {
                "element": rec.name,
                "field": "R/X/B",
                "value": [rec.r_ohm, rec.x_ohm, rec.b_us],
                "method": method,
            }
        )

    by_eic = {rec.eic: rec for rec in transformers}
    existing = by_eic.get("30T-BUCU400TR3-6")
    new = by_eic.get("30T-BUCU400TR4-3")
    if existing:
        existing.direct_rate_mva = 250.0
        existing.rating_basis = "Transelectrica nominal rating"
        existing.inference_notes.append("250 MVA nominal rating confirmed by Transelectrica 400/110 kV transformer specification family")
    if new and existing:
        new.primary_kv = existing.primary_kv
        new.secondary_kv = existing.secondary_kv
        new.r_ohm = existing.r_ohm
        new.x_ohm = existing.x_ohm
        new.b_us = existing.b_us
        new.g_us = existing.g_us
        new.current_a = existing.current_a
        new.direct_rate_mva = 250.0
        new.rating_basis = "Transelectrica nominal rating"
        new.inference_notes.extend(
            [
                "250 MVA nominal rating from Transelectrica development plan",
                "Voltage and electrical parameters copied from co-located Bucuresti Sud transformer 3 of the same 400/121 kV, 250 MVA family",
            ]
        )
        fills.extend(
            [
                {"element": new.name, "field": "rate", "value": 250.0, "unit": "MVA", "method": TRANSELECTRICA_SOURCE},
                {"element": new.name, "field": "voltage and R/X/B/G", "value": [new.primary_kv, new.secondary_kv, new.r_ohm, new.x_ohm, new.b_us, new.g_us], "method": "co-located transformer 3 proxy"},
            ]
        )
    zero_shunt_transformers = 0
    for rec in transformers:
        if rec.r_ohm is None or rec.x_ohm is None:
            continue
        changed = False
        if rec.b_us is None:
            rec.b_us = 0.0
            changed = True
        if rec.g_us is None:
            rec.g_us = 0.0
            changed = True
        if changed:
            zero_shunt_transformers += 1
            rec.inference_notes.append("Missing transformer shunt B/G interpreted as zero")
    if zero_shunt_transformers:
        fills.append(
            {
                "elements": zero_shunt_transformers,
                "field": "transformer B/G",
                "value": 0.0,
                "method": "blank shunt entries interpreted as zero",
            }
        )
    return fills


def eic_country_pair(eic: str) -> tuple[str, str] | None:
    match = re.search(r"10T-([A-Z]{2})-([A-Z]{2})-", eic.upper())
    if not match:
        return None
    aliases = {"SR": "RS"}
    return aliases.get(match.group(1), match.group(1)), aliases.get(match.group(2), match.group(2))


def station_country_and_owner_evidence(
    lines: list[LineRecord],
    transformers: list[TransformerRecord],
    station_coords_map: dict[str, tuple[float, float]],
) -> tuple[dict[str, str], dict[str, Counter[str]]]:
    countries: dict[str, Counter[str]] = defaultdict(Counter)
    owners: dict[str, Counter[str]] = defaultdict(Counter)
    for rec in lines:
        tso_key = rec.tso.upper()
        cc = TSO_COUNTRY.get(tso_key)
        if rec.sheet == "Lines" and cc:
            for station in rec.station_keys:
                countries[station][cc] += 10
                owners[station][rec.tso] += 10
    for rec in transformers:
        cc = TSO_COUNTRY.get(rec.tso.upper())
        if cc:
            countries[rec.station_key][cc] += 10
            owners[rec.station_key][rec.tso] += 10

    def top_cc(station: str) -> str | None:
        return countries[station].most_common(1)[0][0] if countries[station] else None

    def nearest_country_distance(station: str, cc: str) -> float:
        point = station_coords_map[station]
        candidates = [station_coords_map[s] for s in countries if top_cc(s) == cc and s in station_coords_map]
        return min((haversine_km(point, p) for p in candidates), default=1e9)

    ties = [rec for rec in lines if rec.sheet == "Tielines"]
    for _ in range(3):
        for rec in ties:
            pair = eic_country_pair(rec.eic)
            if not pair:
                continue
            a, b = rec.station_keys
            ca, cb = top_cc(a), top_cc(b)
            c1, c2 = pair
            if ca in pair and cb not in pair:
                countries[b][c2 if ca == c1 else c1] += 5
            elif cb in pair and ca not in pair:
                countries[a][c2 if cb == c1 else c1] += 5
            elif ca not in pair and cb not in pair:
                direct = nearest_country_distance(a, c1) + nearest_country_distance(b, c2)
                reverse = nearest_country_distance(a, c2) + nearest_country_distance(b, c1)
                if direct <= reverse:
                    countries[a][c1] += 5
                    countries[b][c2] += 5
                else:
                    countries[a][c2] += 5
                    countries[b][c1] += 5

    resolved = {station: top_cc(station) for station in station_coords_map if top_cc(station)}
    known = list(resolved)
    for station in station_coords_map:
        if station in resolved:
            continue
        if known:
            nearest = min(known, key=lambda other: haversine_km(station_coords_map[station], station_coords_map[other]))
            resolved[station] = resolved[nearest]
        else:
            resolved[station] = "DE"

    for rec in ties:
        for station in rec.station_keys:
            cc = resolved[station]
            if TSO_COUNTRY.get(rec.tso.upper()) == cc:
                owners[station][rec.tso] += 4
    for station, cc in resolved.items():
        if not owners[station]:
            owners[station][DEFAULT_TSO_BY_COUNTRY.get(cc, f"External TSO {cc}")] += 1
    return resolved, owners


def line_pu(r_ohm: float, x_ohm: float, b_us: float, v_kv: float) -> tuple[float, float, float]:
    zbase = v_kv * v_kv / SBASE_MVA
    return r_ohm / zbase, x_ohm / zbase, b_us * 1e-6 * zbase


def owner_names_for_tie(records: Iterable[LineRecord], station_owner_evidence: dict[str, Counter[str]]) -> list[str]:
    result = {rec.tso for rec in records}
    for rec in records:
        for station in rec.station_keys:
            if station_owner_evidence[station]:
                result.add(station_owner_evidence[station].most_common(1)[0][0])
    return sorted(result)


def combine_tielines(
    records: list[LineRecord],
    station_markers: dict[str, int],
    station_owner_evidence: dict[str, Counter[str]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, tuple[str, str], float], list[LineRecord]] = defaultdict(list)
    for rec in records:
        a, b = rec.station_keys
        marker_a = str(station_markers.get(a, a))
        marker_b = str(station_markers.get(b, b))
        pair = tuple(sorted((marker_a, marker_b)))
        groups[(norm(rec.eic) or f"row {rec.row}", pair, normalize_voltage(rec.raw_voltage) or 0.0)].append(rec)

    result: list[dict[str, Any]] = []
    for group in groups.values():
        distinct_tsos = {norm(rec.tso) for rec in group}
        if len(group) > 1 and len(distinct_tsos) > 1:
            first = group[0]
            currents = [rec.current_a for rec in group if rec.current_a and rec.current_a > 0]
            result.append(
                {
                    "records": group,
                    "name": first.name,
                    "eic": first.eic,
                    "station_a": first.station_keys[0],
                    "station_b": first.station_keys[1],
                    "voltage": normalize_voltage(first.raw_voltage),
                    "current": min(currents) if currents else None,
                    "direct_rate": None,
                    "r_ohm": sum(rec.r_ohm or 0.0 for rec in group),
                    "x_ohm": sum(rec.x_ohm or 0.0 for rec in group),
                    "b_us": sum(rec.b_us or 0.0 for rec in group),
                    "length": sum(rec.length_km or 0.0 for rec in group),
                    "owners": owner_names_for_tie(group, station_owner_evidence),
                    "consolidated": True,
                }
            )
        else:
            for rec in group:
                result.append(
                    {
                        "records": [rec],
                        "name": rec.name,
                        "eic": rec.eic,
                        "station_a": rec.station_keys[0],
                        "station_b": rec.station_keys[1],
                        "voltage": normalize_voltage(rec.raw_voltage),
                        "current": rec.current_a,
                        "direct_rate": rec.direct_rate_mva,
                        "r_ohm": rec.r_ohm,
                        "x_ohm": rec.x_ohm,
                        "b_us": rec.b_us,
                        "length": rec.length_km,
                        "owners": owner_names_for_tie([rec], station_owner_evidence),
                        "consolidated": False,
                    }
                )
    return result


def build_grid(xlsx: Path, html: Path, output: Path) -> dict[str, Any]:
    transformer_coords, marker_coords, geometries = parse_html_map(html)
    lines, transformers, decommission_log = load_workbook_records(xlsx)
    matched_geometries = match_geometries(lines, geometries)
    station_markers, coords, labels, coordinate_sources = station_coordinates(lines, marker_coords)
    add_transformer_stations(
        transformers,
        transformer_coords,
        marker_coords,
        station_markers,
        coords,
        labels,
        coordinate_sources,
    )
    fills = infer_missing_source_values(lines, transformers, coords)
    station_countries, station_owner_evidence = station_country_and_owner_evidence(lines, transformers, coords)

    owner_name_set = {rec.tso for rec in lines} | {rec.tso for rec in transformers}
    owner_name_set |= {name for evidence in station_owner_evidence.values() for name in evidence}
    owners = {
        name: gce.Owner(name=name, code=name, idtag=stable_id("owner", norm(name)))
        for name in sorted(owner_name_set)
    }
    used_country_codes = sorted(set(station_countries.values()))
    countries = {
        cc: gce.Country(name=COUNTRY_NAMES.get(cc, cc), code=cc, idtag=stable_id("country", cc))
        for cc in used_country_codes
    }

    grid = gce.MultiCircuit(
        name="Core SGM 2026-03 topology",
        Sbase=SBASE_MVA,
        fbase=50.0,
        idtag=stable_id("grid", "Core SGM 2026-03 topology"),
    )
    grid.comments = (
        "Topology-only model built from the Core Static Grid Model 9th release workbook and publication map. "
        "One bus is used per substation and normalized voltage level. DLR lines use DLRmax; otherwise fixed or "
        "the highest seasonal period is used. Tielines are represented as Line devices. Coordinates are inferred "
        "from publication geometries and snapped to publication substation markers. See the adjacent build report "
        "for assumptions and source-gap fills."
    )
    for country in countries.values():
        grid.add_country(country)
    for owner in owners.values():
        grid.add_owner(owner)

    substations: dict[str, Any] = {}
    voltage_levels: dict[tuple[str, float], Any] = {}
    buses: dict[tuple[str, float], Any] = {}

    station_voltages: dict[str, set[float]] = defaultdict(set)
    for rec in lines:
        v = normalize_voltage(rec.raw_voltage)
        if v:
            for station in rec.station_keys:
                station_voltages[station].add(v)
    for rec in transformers:
        for v in (normalize_voltage(rec.primary_kv), normalize_voltage(rec.secondary_kv)):
            if v:
                station_voltages[rec.station_key].add(v)

    for station in sorted(station_voltages, key=lambda s: labels.get(s, s).lower()):
        lat, lon = coords[station]
        cc = station_countries[station]
        label = labels.get(station, station)
        sub = gce.Substation(
            name=label,
            code=f"SGM-SUB-{station}",
            idtag=stable_id("substation", station),
            latitude=lat,
            longitude=lon,
            country=countries[cc],
        )
        sub.comment = f"Coordinate source: {coordinate_sources.get(station, 'inferred from publication map')}"
        owner_counts = station_owner_evidence[station]
        total = sum(owner_counts.values()) or 1
        for owner_name, weight in owner_counts.items():
            sub.associate_owner(owners[owner_name], weight / total)
        grid.add_substation(sub)
        substations[station] = sub
        for voltage in sorted(station_voltages[station]):
            vl = gce.VoltageLevel(
                name=f"{label} {voltage:g} kV",
                code=f"SGM-VL-{station}-{voltage:g}",
                idtag=stable_id("voltage-level", f"{station}|{voltage:g}"),
                Vnom=voltage,
                substation=sub,
            )
            bus = gce.Bus(
                name=f"{label} {voltage:g} kV",
                code=f"SGM-BUS-{station}-{voltage:g}",
                idtag=stable_id("bus", f"{station}|{voltage:g}"),
                Vnom=voltage,
                substation=sub,
                voltage_level=vl,
                country=countries[cc],
                latitude=lat,
                longitude=lon,
            )
            for owner_name, weight in owner_counts.items():
                vl.associate_owner(owners[owner_name], weight / total)
                bus.associate_owner(owners[owner_name], weight / total)
            grid.add_voltage_level(vl)
            grid.add_bus(bus)
            voltage_levels[(station, voltage)] = vl
            buses[(station, voltage)] = bus

    rating_basis_counts: Counter[str] = Counter()
    created_line_sources = 0
    line_devices = 0
    internal = [rec for rec in lines if rec.sheet == "Lines"]
    tie_records = [rec for rec in lines if rec.sheet == "Tielines"]
    line_payloads: list[dict[str, Any]] = []
    for rec in internal:
        line_payloads.append(
            {
                "records": [rec],
                "name": rec.name,
                "eic": rec.eic,
                "station_a": rec.station_keys[0],
                "station_b": rec.station_keys[1],
                "voltage": normalize_voltage(rec.raw_voltage),
                "current": rec.current_a,
                "direct_rate": rec.direct_rate_mva,
                "r_ohm": rec.r_ohm,
                "x_ohm": rec.x_ohm,
                "b_us": rec.b_us,
                "length": rec.length_km,
                "owners": [rec.tso],
                "consolidated": False,
            }
        )
    line_payloads.extend(combine_tielines(tie_records, station_markers, station_owner_evidence))

    for idx, payload in enumerate(line_payloads):
        records = payload["records"]
        voltage = payload["voltage"]
        if not voltage:
            raise ValueError(f"No normalized voltage for {payload['name']}")
        r_ohm = payload["r_ohm"]
        x_ohm = payload["x_ohm"]
        b_us = payload["b_us"]
        if r_ohm is None or x_ohm is None or b_us is None:
            raise ValueError(f"Missing R/X/B after inference for {payload['name']}")
        rate = payload["direct_rate"]
        if rate is None and payload["current"]:
            rate = SQRT3 * voltage * payload["current"] / 1000.0
        if rate is None or rate <= 0:
            raise ValueError(f"Missing rating after inference for {payload['name']}")
        r_pu, x_pu, b_pu = line_pu(r_ohm, x_ohm, b_us, voltage)
        source_rows = ", ".join(f"{rec.sheet}!{rec.row}" for rec in records)
        notes = [note for rec in records for note in rec.inference_notes]
        source_comments = [rec.source_comment for rec in records if rec.source_comment]
        comment_parts = [
            f"Source rows: {source_rows}",
            f"Rating: {rate:.3f} MVA; basis: {records[0].rating_basis}",
            f"Source electrical values: R={r_ohm:g} ohm, X={x_ohm:g} ohm, B={b_us:g} microS, length={payload['length']:.4g} km",
        ]
        if payload["consolidated"]:
            comment_parts.append("Opposite TSO shares consolidated: R/X/B/length summed and the minimum segment rating used")
        comment_parts.extend(source_comments)
        comment_parts.extend(notes)
        code = payload["eic"] or f"SGM-LINE-{records[0].sheet}-{records[0].row}"
        line = gce.Line(
            bus_from=buses[(payload["station_a"], voltage)],
            bus_to=buses[(payload["station_b"], voltage)],
            name=payload["name"],
            code=code,
            idtag=stable_id("line", f"{code}|{source_rows}|{idx}"),
            r=r_pu,
            x=x_pu,
            b=b_pu,
            g=0.0,
            rate=rate,
            design_rate=rate,
            length=max(0.001, float(payload["length"])),
        )
        line.comment = " | ".join(comment_parts)
        branch_owners = [owners[name] for name in payload["owners"] if name in owners]
        for owner in branch_owners:
            line.associate_owner(owner, 1.0 / len(branch_owners))
        grid.add_line(line)
        line_devices += 1
        created_line_sources += len(records)
        for rec in records:
            rating_basis_counts[rec.rating_basis] += 1

    for rec in transformers:
        primary = normalize_voltage(rec.primary_kv)
        secondary = normalize_voltage(rec.secondary_kv)
        if not primary or not secondary:
            raise ValueError(f"Missing transformer voltage after inference for {rec.name}")
        if None in (rec.r_ohm, rec.x_ohm, rec.b_us, rec.g_us):
            raise ValueError(f"Missing transformer R/X/B/G after inference for {rec.name}")
        rate = rec.direct_rate_mva
        if rate is None and rec.current_a:
            rate = SQRT3 * float(rec.primary_kv) * rec.current_a / 1000.0
        if rate is None or rate <= 0:
            raise ValueError(f"Missing transformer rating after inference for {rec.name}")
        zbase = primary * primary / SBASE_MVA
        tr = gce.Transformer2W(
            bus_from=buses[(rec.station_key, primary)],
            bus_to=buses[(rec.station_key, secondary)],
            name=rec.name,
            code=rec.eic or f"SGM-TR-{rec.row}",
            idtag=stable_id("transformer", f"{rec.eic}|{rec.row}|{rec.name}"),
            HV=max(primary, secondary),
            LV=min(primary, secondary),
            nominal_power=rate,
            design_rate=rate,
            rate=rate,
            r=float(rec.r_ohm) / zbase,
            x=float(rec.x_ohm) / zbase,
            b=float(rec.b_us) * 1e-6 * zbase,
            g=float(rec.g_us) * 1e-6 * zbase,
        )
        comments = [
            f"Source row: Transformers!{rec.row}",
            f"Rating: {rate:.3f} MVA; basis: {rec.rating_basis}",
            f"Source electrical values: R={rec.r_ohm:g} ohm, X={rec.x_ohm:g} ohm, B={rec.b_us:g} microS, G={rec.g_us:g} microS",
        ]
        if rec.source_comment:
            comments.append(rec.source_comment)
        comments.extend(rec.inference_notes)
        tr.comment = " | ".join(comments)
        tr.associate_owner(owners[rec.tso], 1.0)
        grid.add_transformer2w(tr)
        rating_basis_counts[rec.rating_basis] += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    gce.save_file(grid=grid, filename=str(output))
    reopened = gce.open_file(filename=str(output))
    nc = gce.compile_numerical_circuit_at(reopened)

    validation = {
        "roundtrip_open": reopened is not None,
        "valid_for_simulation": bool(reopened.valid_for_simulation()),
        "compiled_numerical_circuit": nc is not None,
        "positive_line_ratings": all(line.rate > 0 for line in reopened.lines),
        "positive_transformer_ratings": all(tr.rate > 0 for tr in reopened.transformers2w),
        "all_substations_have_coordinates": all(
            math.isfinite(sub.latitude) and math.isfinite(sub.longitude) and not (sub.latitude == 0 and sub.longitude == 0)
            for sub in reopened.substations
        ),
        "all_substations_have_country": all(sub.country is not None for sub in reopened.substations),
        "all_buses_have_country": all(bus.country is not None for bus in reopened.buses),
        "all_physical_devices_have_owner": all(
            len(obj.owners_list) > 0
            for collection in (reopened.substations, reopened.voltage_levels, reopened.buses, reopened.lines, reopened.transformers2w)
            for obj in collection
        ),
        "count_roundtrip": {
            "buses": [len(grid.buses), len(reopened.buses)],
            "substations": [len(grid.substations), len(reopened.substations)],
            "voltage_levels": [len(grid.voltage_levels), len(reopened.voltage_levels)],
            "lines": [len(grid.lines), len(reopened.lines)],
            "transformers2w": [len(grid.transformers2w), len(reopened.transformers2w)],
        },
    }
    if not all(v for k, v in validation.items() if not isinstance(v, dict)):
        raise AssertionError(f"Validation failed: {validation}")
    if any(before != after for before, after in validation["count_roundtrip"].values()):
        raise AssertionError(f"Roundtrip count mismatch: {validation['count_roundtrip']}")

    report = {
        "model": grid.name,
        "sources": {"workbook": str(xlsx), "map": str(html)},
        "reference_sources_for_fills": {
            "milin_capacity": ENTSOE_MILIN_SOURCE,
            "milin_loop_length": ERU_MILIN_SOURCE,
            "former_v475_length": ERU_OLD_LINE_SOURCE,
            "bucuresti_sud_transformer": TRANSELECTRICA_SOURCE,
            "manual_coordinates": MANUAL_COORDINATE_REFERENCES,
        },
        "rules": {
            "scope": "topology only",
            "bus_model": "one bus per source substation name and normalized voltage level",
            "voltage_normalization_kv": {"110-130": 110, "135-179": 150, "180-274": 220, "275-549": 380, ">=550": 750},
            "line_rating_priority": ["DLR maximum", "fixed", "maximum seasonal period"],
            "tielines": "VeraGrid Line devices; opposite TSO border shares consolidated",
            "owner": "TSO",
        },
        "source_counts": {
            "active_line_and_tieline_rows": len(lines),
            "transformer_rows": len(transformers),
            "html_line_geometries": len(geometries),
            "matched_line_geometries": matched_geometries,
            "html_substation_markers": len(marker_coords),
            "html_transformer_markers": len(transformer_coords),
            "decommissioned_current_rows_excluded": len(decommission_log),
        },
        "output_counts": {
            "countries": len(grid.countries),
            "owners": len(grid.owners),
            "substations": len(grid.substations),
            "voltage_levels": len(grid.voltage_levels),
            "buses": len(grid.buses),
            "lines": line_devices,
            "transformers2w": len(grid.transformers2w),
            "source_line_rows_represented": created_line_sources,
            "tieline_rows_consolidated": len(tie_records) - (line_devices - len(internal)),
        },
        "rating_basis_counts": dict(sorted(rating_basis_counts.items())),
        "coordinate_source_counts": dict(sorted(Counter(coordinate_sources.values()).items())),
        "decommissioned_rows_excluded": decommission_log,
        "filled_source_gaps": fills,
        "validation": validation,
        "output": str(output),
    }
    report_path = output.with_name(output.stem + "_build_report.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["output_counts"], indent=2))
    print(json.dumps(validation, indent=2))
    print(f"Saved: {output}")
    print(f"Report: {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_grid(args.xlsx, args.html, args.output)


if __name__ == "__main__":
    main()
