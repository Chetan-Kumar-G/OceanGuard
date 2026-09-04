"""Deterministic raw AIS validation service for F4.

Validates MMSI, coordinates, timestamps, SOG, COG, and maintains an auditable
validation report without silently discarding records.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from backend.f4_ais.schemas import (
    AISValidationIssue,
    AISValidationReport,
    RawAISRecord,
    ValidatedAISFix,
)

_MMSI_REGEX = re.compile(r"^[1-9]\d{8}$")


def parse_utc_timestamp(ts_val: Any) -> datetime:
    """Parses and normalizes a timestamp value into UTC datetime.

    Accepts:
    - ISO-8601 string (e.g. '2026-01-16T00:07:03Z', '2026-01-16T00:07:03+00:00')
    - datetime object

    Raises:
        ValueError if string is unparseable or cannot be mapped to UTC.
    """
    if isinstance(ts_val, datetime):
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=timezone.utc)
        return ts_val.astimezone(timezone.utc)

    if not isinstance(ts_val, str):
        raise ValueError(f"Expected timestamp string or datetime, got {type(ts_val).__name__}: {ts_val}")

    s = ts_val.strip()
    if not s:
        raise ValueError("Timestamp string is empty")

    # Handle trailing Z for standard ISO parsing
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # Default naive timestamps to UTC with explicit normalization
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def validate_ais_record(
    record: Union[Dict[str, Any], RawAISRecord],
    row_idx: int = 0
) -> Tuple[Optional[ValidatedAISFix], List[AISValidationIssue]]:
    """Validates an individual raw AIS record against maritime navigation rules.

    Returns:
        Tuple of (ValidatedAISFix if valid else None, list of validation issues)
    """
    issues: List[AISValidationIssue] = []
    d = record.model_dump() if isinstance(record, RawAISRecord) else dict(record)

    raw_mmsi = str(d.get("mmsi", "")).strip()
    if not _MMSI_REGEX.match(raw_mmsi):
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="mmsi",
                raw_value=raw_mmsi,
                reason="MMSI must be a 9-digit numeric string with a valid MID"
            )
        )

    # Validate timestamp
    raw_ts = d.get("timestamp")
    parsed_dt: Optional[datetime] = None
    iso_str: str = ""
    try:
        parsed_dt = parse_utc_timestamp(raw_ts)
        iso_str = parsed_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="timestamp",
                raw_value=raw_ts,
                reason=f"Invalid UTC ISO-8601 timestamp: {str(e)}"
            )
        )

    # Validate latitude
    lat_val: Optional[float] = None
    try:
        lat_val = float(d.get("latitude"))
        if math.isnan(lat_val) or not (-90.0 <= lat_val <= 90.0):
            issues.append(
                AISValidationIssue(
                    row_index=row_idx,
                    mmsi=raw_mmsi,
                    field_name="latitude",
                    raw_value=d.get("latitude"),
                    reason="Latitude must be a valid float between -90.0 and 90.0 degrees"
                )
            )
            lat_val = None
    except (TypeError, ValueError):
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="latitude",
                raw_value=d.get("latitude"),
                reason="Latitude is non-numeric or missing"
            )
        )

    # Validate longitude
    lon_val: Optional[float] = None
    try:
        lon_val = float(d.get("longitude"))
        if math.isnan(lon_val) or not (-180.0 <= lon_val <= 180.0):
            issues.append(
                AISValidationIssue(
                    row_index=row_idx,
                    mmsi=raw_mmsi,
                    field_name="longitude",
                    raw_value=d.get("longitude"),
                    reason="Longitude must be a valid float between -180.0 and 180.0 degrees"
                )
            )
            lon_val = None
    except (TypeError, ValueError):
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="longitude",
                raw_value=d.get("longitude"),
                reason="Longitude is non-numeric or missing"
            )
        )

    # Validate SOG (distinguish missing/None from 0.0)
    sog_val: Optional[float] = None
    raw_sog = d.get("sog_kn")
    if raw_sog is not None and str(raw_sog).strip() != "":
        try:
            val = float(raw_sog)
            if math.isnan(val) or val < 0.0 or val > 102.2:
                issues.append(
                    AISValidationIssue(
                        row_index=row_idx,
                        mmsi=raw_mmsi,
                        field_name="sog_kn",
                        raw_value=raw_sog,
                        reason="SOG must be within standard AIS range [0.0, 102.2] knots"
                    )
                )
            else:
                sog_val = val
        except (TypeError, ValueError):
            issues.append(
                AISValidationIssue(
                    row_index=row_idx,
                    mmsi=raw_mmsi,
                    field_name="sog_kn",
                    raw_value=raw_sog,
                    reason="SOG is non-numeric"
                )
            )

    # Validate COG (distinguish missing/None from 0.0)
    cog_val: Optional[float] = None
    raw_cog = d.get("cog_deg")
    if raw_cog is not None and str(raw_cog).strip() != "":
        try:
            val = float(raw_cog)
            if math.isnan(val) or val < 0.0 or val > 360.0:
                issues.append(
                    AISValidationIssue(
                        row_index=row_idx,
                        mmsi=raw_mmsi,
                        field_name="cog_deg",
                        raw_value=raw_cog,
                        reason="COG must be within [0.0, 360.0] degrees"
                    )
                )
            else:
                cog_val = val
        except (TypeError, ValueError):
            issues.append(
                AISValidationIssue(
                    row_index=row_idx,
                    mmsi=raw_mmsi,
                    field_name="cog_deg",
                    raw_value=raw_cog,
                    reason="COG is non-numeric"
                )
            )

    # Validate Heading (distinguish missing/None from 0.0; allow 511 for not available)
    heading_val: Optional[float] = None
    raw_heading = d.get("heading_deg")
    if raw_heading is not None and str(raw_heading).strip() != "":
        try:
            val = float(raw_heading)
            if math.isnan(val) or val < 0.0 or (val > 360.0 and val != 511.0):
                issues.append(
                    AISValidationIssue(
                        row_index=row_idx,
                        mmsi=raw_mmsi,
                        field_name="heading_deg",
                        raw_value=raw_heading,
                        reason="Heading must be within [0.0, 360.0] degrees or 511 (not available)"
                    )
                )
            else:
                heading_val = val
        except (TypeError, ValueError):
            issues.append(
                AISValidationIssue(
                    row_index=row_idx,
                    mmsi=raw_mmsi,
                    field_name="heading_deg",
                    raw_value=raw_heading,
                    reason="Heading is non-numeric"
                )
            )

    # Parse optional numeric dimension fields and check physical non-negativity
    def _opt_float(val: Any) -> Optional[float]:
        if val is None or str(val).strip() == "":
            return None
        try:
            f = float(val)
            return f if not math.isnan(f) else None
        except (TypeError, ValueError):
            return None

    length_val = _opt_float(d.get("vessel_length"))
    if length_val is not None and length_val < 0.0:
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="vessel_length",
                raw_value=d.get("vessel_length"),
                reason="Vessel length must be non-negative"
            )
        )

    width_val = _opt_float(d.get("vessel_width"))
    if width_val is not None and width_val < 0.0:
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="vessel_width",
                raw_value=d.get("vessel_width"),
                reason="Vessel width must be non-negative"
            )
        )

    draught_val = _opt_float(d.get("draught"))
    if draught_val is not None and draught_val < 0.0:
        issues.append(
            AISValidationIssue(
                row_index=row_idx,
                mmsi=raw_mmsi,
                field_name="draught",
                raw_value=d.get("draught"),
                reason="Vessel draught must be non-negative"
            )
        )

    # If validation errors exist, return None with the issues list
    if issues:
        return None, issues

    # Parse boolean is_observed
    raw_obs = d.get("is_observed", True)
    if isinstance(raw_obs, str):
        is_observed = raw_obs.strip().lower() in ("true", "1", "yes")
    else:
        is_observed = bool(raw_obs)

    fix = ValidatedAISFix(
        mmsi=raw_mmsi,
        timestamp_utc=parsed_dt,  # type: ignore[arg-type]
        timestamp_iso=iso_str,
        latitude=lat_val,  # type: ignore[arg-type]
        longitude=lon_val,  # type: ignore[arg-type]
        sog_kn=sog_val,
        cog_deg=cog_val,
        heading_deg=heading_val,
        nav_status=str(d.get("nav_status", "UnderWayUsingEngine")),
        vessel_type=str(d.get("vessel_type")) if d.get("vessel_type") else None,
        vessel_length=length_val,
        vessel_width=width_val,
        draught=draught_val,
        source=str(d.get("source", "AIS-terrestrial")),
        is_observed=is_observed,
        sim_hours=_opt_float(d.get("sim_hours")),
    )

    return fix, issues


def validate_ais_stream(
    records: Iterable[Union[Dict[str, Any], RawAISRecord]]
) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
    """Validates an iterable stream of raw AIS records.

    Returns:
        Tuple of (list of ValidatedAISFix, complete AISValidationReport)
    """
    valid_fixes: List[ValidatedAISFix] = []
    all_issues: List[AISValidationIssue] = []
    total = 0

    for idx, rec in enumerate(records):
        total += 1
        fix, issues = validate_ais_record(rec, row_idx=idx)
        if issues:
            all_issues.extend(issues)
        if fix is not None:
            valid_fixes.append(fix)

    report = AISValidationReport(
        total_records=total,
        valid_records=len(valid_fixes),
        invalid_records=total - len(valid_fixes),
        issues=all_issues,
    )
    return valid_fixes, report


class AISValidationService:
    """Deterministic validation service for maritime AIS data."""

    def validate_record(
        self, record: Union[Dict[str, Any], RawAISRecord], row_idx: int = 0
    ) -> Tuple[Optional[ValidatedAISFix], List[AISValidationIssue]]:
        """Validates a single AIS record."""
        return validate_ais_record(record, row_idx=row_idx)

    def validate_stream(
        self, records: Iterable[Union[Dict[str, Any], RawAISRecord]]
    ) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
        """Validates a stream or batch of AIS records."""
        return validate_ais_stream(records)

