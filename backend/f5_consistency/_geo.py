"""Minimal spherical geometry + time helpers. No GIS dependency for the F5 MVP.

All coordinates are (lat, lon) in degrees, EPSG:4326 (Blueprint Part 30).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

_EARTH_RADIUS_KM = 6371.0088
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def parse_iso(ts: str) -> datetime:
    """Parse a UTC ISO-8601 'Z' timestamp. Rejects naive datetimes (Part 30)."""
    if ts is None or str(ts).strip() == "":
        raise ValueError("empty timestamp")
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"naive datetime not permitted: {ts!r}")
    return dt.astimezone(timezone.utc)


def hours_between(a: str, b: str) -> float:
    """Absolute hours between two ISO timestamps."""
    return abs((parse_iso(a) - parse_iso(b)).total_seconds()) / 3600.0


def signed_hours(later: str, earlier: str) -> float:
    return (parse_iso(later) - parse_iso(earlier)).total_seconds() / 3600.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))
