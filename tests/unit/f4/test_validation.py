"""Unit tests for raw AIS validation, timestamp normalization, and coordinate checks.

Covers:
- Test D: AIS timestamp normalization to UTC
- Test E: AIS coordinate and navigation validation boundary
"""
from datetime import datetime, timezone
import pytest

from backend.f4_ais.validation import parse_utc_timestamp, validate_ais_record, validate_ais_stream


def test_timestamp_normalization_utc():
    """Test D: Verifies AIS timestamps are correctly normalized to UTC ISO-8601."""
    # 1. Standard ISO with Z
    dt1 = parse_utc_timestamp("2026-01-16T00:07:03Z")
    assert dt1.tzinfo == timezone.utc
    assert dt1.hour == 0 and dt1.minute == 7 and dt1.second == 3

    # 2. ISO with +00:00 offset
    dt2 = parse_utc_timestamp("2026-01-16T02:30:00+00:00")
    assert dt2.tzinfo == timezone.utc
    assert dt2.hour == 2 and dt2.minute == 30

    # 3. ISO with non-zero offset converts to UTC correctly
    dt3 = parse_utc_timestamp("2026-01-16T03:00:00+02:00")
    assert dt3.tzinfo == timezone.utc
    assert dt3.hour == 1 and dt3.minute == 0  # 03:00 +02:00 -> 01:00 UTC

    # 4. Naive timestamp string
    dt4 = parse_utc_timestamp("2026-01-16T05:15:00")
    assert dt4.tzinfo == timezone.utc
    assert dt4.hour == 5

    # 5. Malformed string raises ValueError
    with pytest.raises(ValueError):
        parse_utc_timestamp("not-a-timestamp")

    with pytest.raises(ValueError):
        parse_utc_timestamp("")


def test_coordinate_and_nav_field_validation():
    """Test E: Verifies invalid coordinates, MMSIs, and navigation fields are flagged."""
    valid_raw = {
        "mmsi": "226110445",
        "timestamp": "2026-01-16T00:07:03Z",
        "latitude": 36.123456,
        "longitude": 21.654321,
        "sog_kn": 12.5,
        "cog_deg": 270.0,
        "heading_deg": 272.0,
        "source": "AIS-terrestrial",
        "is_observed": True,
    }

    # 1. Valid record succeeds
    fix, issues = validate_ais_record(valid_raw)
    assert fix is not None
    assert len(issues) == 0
    assert fix.mmsi == "226110445"
    assert fix.latitude == 36.123456
    assert fix.longitude == 21.654321

    # 2. Latitude out of bounds [-90, 90]
    bad_lat = dict(valid_raw, latitude=95.0)
    fix, issues = validate_ais_record(bad_lat)
    assert fix is None
    assert any(i.field_name == "latitude" for i in issues)

    # 3. Longitude out of bounds [-180, 180]
    bad_lon = dict(valid_raw, longitude=-185.0)
    fix, issues = validate_ais_record(bad_lon)
    assert fix is None
    assert any(i.field_name == "longitude" for i in issues)

    # 4. Invalid MMSI (not 9 digits)
    bad_mmsi = dict(valid_raw, mmsi="12345")
    fix, issues = validate_ais_record(bad_mmsi)
    assert fix is None
    assert any(i.field_name == "mmsi" for i in issues)

    # 5. Extreme SOG (> 102.2 knots) flagged as issue
    extreme_sog = dict(valid_raw, sog_kn=150.0)
    fix, issues = validate_ais_record(extreme_sog)
    assert any(i.field_name == "sog_kn" for i in issues)

    # 6. Stream validation report
    stream = [valid_raw, bad_lat, bad_lon, bad_mmsi]
    valid_fixes, report = validate_ais_stream(stream)
    assert report.total_records == 4
    assert report.valid_records == 1
    assert report.invalid_records == 3
    assert len(valid_fixes) == 1
