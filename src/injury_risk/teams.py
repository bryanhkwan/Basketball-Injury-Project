"""The 30 teams: tricode, full name, home-arena location, standard UTC offset and altitude.

Locations are the arena's city (a few miles of error does not matter for travel). Golden State moved from
Oakland to San Francisco in 2019 and the Clippers to Inglewood in 2024: both under 15 miles, ignored.
Games away from either team's arena (Orlando bubble, Tampa, Mexico City, Paris, Las Vegas...) use
NEUTRAL_CITIES, keyed by the venue city in ESPN's schedule.
"""
from __future__ import annotations

import math

# tricode: (full name, latitude, longitude, standard UTC offset in hours, altitude in feet)
TEAMS = {
    "ATL": ("Atlanta Hawks", 33.757, -84.396, -5, 1050),
    "BOS": ("Boston Celtics", 42.366, -71.062, -5, 20),
    "BKN": ("Brooklyn Nets", 40.683, -73.975, -5, 30),
    "CHA": ("Charlotte Hornets", 35.225, -80.839, -5, 750),
    "CHI": ("Chicago Bulls", 41.881, -87.674, -6, 600),
    "CLE": ("Cleveland Cavaliers", 41.496, -81.688, -5, 650),
    "DAL": ("Dallas Mavericks", 32.790, -96.810, -6, 430),
    "DEN": ("Denver Nuggets", 39.749, -105.008, -7, 5280),
    "DET": ("Detroit Pistons", 42.341, -83.055, -5, 600),
    "GSW": ("Golden State Warriors", 37.768, -122.388, -8, 10),
    "HOU": ("Houston Rockets", 29.751, -95.362, -6, 50),
    "IND": ("Indiana Pacers", 39.764, -86.155, -5, 715),
    "LAC": ("LA Clippers", 34.043, -118.267, -8, 300),
    "LAL": ("Los Angeles Lakers", 34.043, -118.267, -8, 300),
    "MEM": ("Memphis Grizzlies", 35.138, -90.051, -6, 300),
    "MIA": ("Miami Heat", 25.781, -80.188, -5, 10),
    "MIL": ("Milwaukee Bucks", 43.045, -87.917, -6, 620),
    "MIN": ("Minnesota Timberwolves", 44.979, -93.276, -6, 830),
    "NOP": ("New Orleans Pelicans", 29.949, -90.082, -6, 10),
    "NYK": ("New York Knicks", 40.750, -73.993, -5, 30),
    "OKC": ("Oklahoma City Thunder", 35.463, -97.515, -6, 1200),
    "ORL": ("Orlando Magic", 28.539, -81.384, -5, 100),
    "PHI": ("Philadelphia 76ers", 39.901, -75.172, -5, 40),
    "PHX": ("Phoenix Suns", 33.446, -112.071, -7, 1090),
    "POR": ("Portland Trail Blazers", 45.532, -122.667, -8, 50),
    "SAC": ("Sacramento Kings", 38.580, -121.500, -8, 30),
    "SAS": ("San Antonio Spurs", 29.427, -98.437, -6, 650),
    "TOR": ("Toronto Raptors", 43.643, -79.379, -5, 250),
    "UTA": ("Utah Jazz", 40.768, -111.901, -7, 4226),
    "WAS": ("Washington Wizards", 38.898, -77.021, -5, 30),
}

NAME_ALIASES = {"Los Angeles Clippers": "LAC", "LA Lakers": "LAL"}

# venue city (as ESPN writes it) -> (latitude, longitude, standard UTC offset, altitude in feet)
NEUTRAL_CITIES = {
    "Lake Buena Vista": (28.370, -81.560, -5, 100),   # 2020 restart and playoffs (bubble)
    "Bay Lake": (28.370, -81.560, -5, 100),
    "Orlando": (28.539, -81.384, -5, 100),
    "Tampa": (27.943, -82.452, -5, 50),               # Raptors' 2020-21 home games
    "Mexico City": (19.403, -99.096, -6, 7350),
    "Paris": (48.839, 2.379, 1, 120),
    "London": (51.503, 0.003, 0, 50),
    "Berlin": (52.506, 13.443, 1, 110),
    "Las Vegas": (36.103, -115.178, -8, 2000),        # NBA Cup knockout rounds
    "Abu Dhabi": (24.466, 54.366, 4, 10),
    "Saitama": (35.895, 139.630, 9, 30),
    "Montreal": (45.496, -73.569, -5, 100),
    "Vancouver": (49.278, -123.109, -8, 50),
    "Seattle": (47.622, -122.354, -8, 150),
}


def full_name(tricode: str) -> str:
    return TEAMS[tricode][0]


def location(tricode: str) -> tuple[float, float, int, int]:
    _, lat, lon, utc, alt = TEAMS[tricode]
    return lat, lon, utc, alt


def resolve_name(text: str, candidates=None) -> str | None:
    """Tricode for a (possibly partial, wrapped) team name such as 'Timberwolves', among ``candidates``."""
    words = {w.lower() for w in text.split()}
    if not words:
        return None
    pool = candidates or TEAMS.keys()
    names = {code: TEAMS[code][0] for code in pool if code in TEAMS}
    for alias, code in NAME_ALIASES.items():
        if code in names:
            names[code + "|" + alias] = alias
    best, best_hits = None, 0
    for key, name in names.items():
        hits = len(words & {w.lower() for w in name.split()})
        if hits > best_hits:
            best, best_hits = key.split("|")[0], hits
    return best


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))
