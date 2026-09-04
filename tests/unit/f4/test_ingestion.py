"""Unit tests for F4.1 AIS Ingestion and Validation.

Covers tests A through X from F4.1 Specification Section 8:
- Test A: Valid AIS record accepted
- Test B: Malformed MMSI rejected
- Test C: Short MMSI rejected
- Test D: Leading-zero MMSI rejected
- Test E: Malformed timestamp rejected
- Test F: Timezone offset normalized to UTC
- Test G: Invalid latitude rejected
- Test H: Invalid longitude rejected
- Test I: Negative SOG rejected
- Test J: Invalid COG rejected
- Test K: Invalid heading rejected
- Test L: Heading 511 accepted
- Test M: Missing SOG remains None
- Test N: Missing COG remains None
- Test O: Missing heading remains None
- Test P: None is distinct from 0.0
- Test Q: is_observed=True preserved (observed record)
- Test R: is_observed=False preserved (non-observed record)
- Test S: Source preserved verbatim
- Test T: nav_status preserved
- Test U: Vessel static attributes preserved
- Test V: No event_id exists on ValidatedAISFix
- Test W: Valid position with missing navigation values is retained
- Test X: Complete synthetic AIS ingestion
"""
from datetime import datetime, timezone
import pytest

from shared.config.settings import get_settings
from backend.f4_ais.agents import AISIngestionAgent
from backend.f4_ais.ingestion import AISIngestionService
from backend.f4_ais.schemas import ValidatedAISFix
from backend.f4_ais.validation import AISValidationService, validate_ais_record


@pytest.fixture
def sample_valid_record():
    return {
        "mmsi": "226110445",
        "timestamp": "2026-01-16T00:07:03Z",
        "latitude": 35.0,
        "longitude": 22.116984,
        "sog_kn": 7.41,
        "cog_deg": 270.0,
        "heading_deg": 272.1,
        "nav_status": "UnderWayUsingEngine",
        "vessel_type": "Tanker",
        "vessel_length": 287.7,
        "vessel_width": 44.5,
        "draught": 12.7,
        "source": "AIS-terrestrial",
        "is_observed": True,
        "sim_hours": 264.1178,
    }


def test_a_valid_ais_record_accepted(sample_valid_record):
    """Test A: Valid AIS record accepted."""
    service = AISValidationService()
    fix, issues = service.validate_record(sample_valid_record)
    assert fix is not None
    assert len(issues) == 0
    assert fix.mmsi == "226110445"
    assert fix.latitude == 35.0
    assert fix.longitude == 22.116984
    assert fix.sog_kn == 7.41
    assert fix.cog_deg == 270.0
    assert fix.heading_deg == 272.1


def test_b_malformed_mmsi_rejected(sample_valid_record):
    """Test B: Malformed MMSI rejected (non-numeric characters)."""
    rec = dict(sample_valid_record, mmsi="22611ABCD")
    fix, issues = validate_ais_record(rec)
    assert fix is None
    assert any(i.field_name == "mmsi" for i in issues)


def test_c_short_mmsi_rejected(sample_valid_record):
    """Test C: Short MMSI rejected (fewer than 9 digits)."""
    rec = dict(sample_valid_record, mmsi="12345678")
    fix, issues = validate_ais_record(rec)
    assert fix is None
    assert any(i.field_name == "mmsi" for i in issues)


def test_d_leading_zero_mmsi_rejected(sample_valid_record):
    """Test D: Leading-zero MMSI rejected (valid MID starts with digits 2-7)."""
    rec = dict(sample_valid_record, mmsi="012345678")
    fix, issues = validate_ais_record(rec)
    assert fix is None
    assert any(i.field_name == "mmsi" for i in issues)


def test_e_malformed_timestamp_rejected(sample_valid_record):
    """Test E: Malformed timestamp rejected."""
    rec = dict(sample_valid_record, timestamp="invalid-time-format")
    fix, issues = validate_ais_record(rec)
    assert fix is None
    assert any(i.field_name == "timestamp" for i in issues)


def test_f_timezone_offset_normalized_to_utc(sample_valid_record):
    """Test F: Timezone offset normalized to UTC."""
    rec = dict(sample_valid_record, timestamp="2026-01-16T03:07:03+03:00")
    fix, issues = validate_ais_record(rec)
    assert fix is not None
    assert fix.timestamp_utc.tzinfo == timezone.utc
    assert fix.timestamp_utc.hour == 0  # 03:07 +03:00 -> 00:07 UTC
    assert fix.timestamp_iso == "2026-01-16T00:07:03Z"


def test_g_invalid_latitude_rejected(sample_valid_record):
    """Test G: Invalid latitude rejected (outside [-90, 90])."""
    rec_high = dict(sample_valid_record, latitude=90.001)
    fix_high, issues_high = validate_ais_record(rec_high)
    assert fix_high is None
    assert any(i.field_name == "latitude" for i in issues_high)

    rec_low = dict(sample_valid_record, latitude=-90.001)
    fix_low, issues_low = validate_ais_record(rec_low)
    assert fix_low is None
    assert any(i.field_name == "latitude" for i in issues_low)


def test_h_invalid_longitude_rejected(sample_valid_record):
    """Test H: Invalid longitude rejected (outside [-180, 180])."""
    rec_high = dict(sample_valid_record, longitude=180.1)
    fix_high, issues_high = validate_ais_record(rec_high)
    assert fix_high is None
    assert any(i.field_name == "longitude" for i in issues_high)

    rec_low = dict(sample_valid_record, longitude=-180.1)
    fix_low, issues_low = validate_ais_record(rec_low)
    assert fix_low is None
    assert any(i.field_name == "longitude" for i in issues_low)


def test_i_negative_sog_rejected(sample_valid_record):
    """Test I: Negative SOG rejected."""
    rec = dict(sample_valid_record, sog_kn=-1.5)
    fix, issues = validate_ais_record(rec)
    assert fix is None
    assert any(i.field_name == "sog_kn" for i in issues)


def test_j_invalid_cog_rejected(sample_valid_record):
    """Test J: Invalid COG rejected (e.g. < 0 or > 360)."""
    rec_neg = dict(sample_valid_record, cog_deg=-5.0)
    fix_neg, issues_neg = validate_ais_record(rec_neg)
    assert fix_neg is None
    assert any(i.field_name == "cog_deg" for i in issues_neg)

    rec_high = dict(sample_valid_record, cog_deg=365.0)
    fix_high, issues_high = validate_ais_record(rec_high)
    assert fix_high is None
    assert any(i.field_name == "cog_deg" for i in issues_high)


def test_k_invalid_heading_rejected(sample_valid_record):
    """Test K: Invalid heading rejected (outside [0, 360] and not 511)."""
    rec_bad = dict(sample_valid_record, heading_deg=400.0)
    fix_bad, issues_bad = validate_ais_record(rec_bad)
    assert fix_bad is None
    assert any(i.field_name == "heading_deg" for i in issues_bad)

    rec_neg = dict(sample_valid_record, heading_deg=-1.0)
    fix_neg, issues_neg = validate_ais_record(rec_neg)
    assert fix_neg is None
    assert any(i.field_name == "heading_deg" for i in issues_neg)


def test_l_heading_511_accepted(sample_valid_record):
    """Test L: Heading 511 accepted as standard AIS unavailable indicator."""
    rec_511 = dict(sample_valid_record, heading_deg=511.0)
    fix_511, issues_511 = validate_ais_record(rec_511)
    assert fix_511 is not None
    assert fix_511.heading_deg == 511.0
    assert len(issues_511) == 0


def test_m_missing_sog_remains_none(sample_valid_record):
    """Test M: Missing SOG remains None."""
    rec = dict(sample_valid_record, sog_kn=None)
    fix, issues = validate_ais_record(rec)
    assert fix is not None
    assert fix.sog_kn is None


def test_n_missing_cog_remains_none(sample_valid_record):
    """Test N: Missing COG remains None."""
    rec = dict(sample_valid_record, cog_deg="")
    fix, issues = validate_ais_record(rec)
    assert fix is not None
    assert fix.cog_deg is None


def test_o_missing_heading_remains_none(sample_valid_record):
    """Test O: Missing heading remains None."""
    rec = dict(sample_valid_record, heading_deg=None)
    fix, issues = validate_ais_record(rec)
    assert fix is not None
    assert fix.heading_deg is None


def test_p_none_is_distinct_from_zero(sample_valid_record):
    """Test P: None is distinct from 0.0 for SOG and COG."""
    # SOG
    rec_missing_sog = dict(sample_valid_record, sog_kn=None)
    rec_zero_sog = dict(sample_valid_record, sog_kn=0.0)
    fix_missing_sog, _ = validate_ais_record(rec_missing_sog)
    fix_zero_sog, _ = validate_ais_record(rec_zero_sog)
    assert fix_missing_sog.sog_kn is None
    assert fix_zero_sog.sog_kn == 0.0
    assert fix_missing_sog.sog_kn != fix_zero_sog.sog_kn

    # COG
    rec_missing_cog = dict(sample_valid_record, cog_deg=None)
    rec_zero_cog = dict(sample_valid_record, cog_deg=0.0)
    fix_missing_cog, _ = validate_ais_record(rec_missing_cog)
    fix_zero_cog, _ = validate_ais_record(rec_zero_cog)
    assert fix_missing_cog.cog_deg is None
    assert fix_zero_cog.cog_deg == 0.0
    assert fix_missing_cog.cog_deg != fix_zero_cog.cog_deg


def test_q_is_observed_true_preserved(sample_valid_record):
    """Test Q: is_observed=True preserved for observed AIS records."""
    rec = dict(sample_valid_record, is_observed=True)
    fix, _ = validate_ais_record(rec)
    assert fix is not None
    assert fix.is_observed is True


def test_r_is_observed_false_preserved(sample_valid_record):
    """Test R: is_observed=False preserved for non-observed AIS records."""
    rec = dict(sample_valid_record, is_observed=False)
    fix, _ = validate_ais_record(rec)
    assert fix is not None
    assert fix.is_observed is False


def test_s_source_preserved_verbatim(sample_valid_record):
    """Test S: Source preserved verbatim."""
    rec1 = dict(sample_valid_record, source="AIS-terrestrial")
    fix1, _ = validate_ais_record(rec1)
    assert fix1.source == "AIS-terrestrial"

    rec2 = dict(sample_valid_record, source="AIS-satellite")
    fix2, _ = validate_ais_record(rec2)
    assert fix2.source == "AIS-satellite"


def test_t_nav_status_preserved(sample_valid_record):
    """Test T: nav_status preserved verbatim."""
    rec = dict(sample_valid_record, nav_status="RestrictedManoeuvrability")
    fix, _ = validate_ais_record(rec)
    assert fix.nav_status == "RestrictedManoeuvrability"


def test_u_vessel_static_attributes_preserved(sample_valid_record):
    """Test U: Vessel static attributes preserved."""
    fix, _ = validate_ais_record(sample_valid_record)
    assert fix.vessel_type == "Tanker"
    assert fix.vessel_length == 287.7
    assert fix.vessel_width == 44.5
    assert fix.draught == 12.7


def test_v_no_event_id_exists_on_validated_ais_fix(sample_valid_record):
    """Test V: No event_id exists on ValidatedAISFix."""
    service = AISIngestionService()
    fixes, _ = service.ingest_records([sample_valid_record])
    assert len(fixes) == 1
    fix = fixes[0]
    assert not hasattr(fix, "event_id")
    assert "event_id" not in fix.model_dump()


def test_w_valid_position_with_missing_navigation_values_is_retained():
    """Test W: Valid position with missing navigation values is retained."""
    record = {
        "mmsi": "226110445",
        "timestamp": "2026-01-16T00:07:03Z",
        "latitude": 35.0,
        "longitude": 22.116984,
        "sog_kn": None,
        "cog_deg": None,
        "heading_deg": None,
        "source": "AIS-terrestrial",
        "is_observed": True,
    }
    fix, issues = validate_ais_record(record)
    assert fix is not None, f"Fix was unexpectedly rejected: {issues}"
    assert len(issues) == 0
    assert fix.latitude == 35.0
    assert fix.longitude == 22.116984
    assert fix.sog_kn is None
    assert fix.cog_deg is None
    assert fix.heading_deg is None


def test_x_complete_synthetic_ais_ingestion():
    """Test X: Complete synthetic AIS ingestion of D4_ais_raw.csv."""
    agent = AISIngestionAgent()
    settings = get_settings()
    csv_path = settings.D4_AIS_RAW_CSV_PATH

    fixes, report = agent.ingest_from_csv(csv_path)

    # Ingestion metrics verification
    assert report.total_records == 29407
    assert report.valid_records == 29407
    assert report.invalid_records == 0
    assert len(report.issues) == 0
    assert len(fixes) == 29407

    # Unique MMSIs verification
    unique_mmsis = set(f.mmsi for f in fixes)
    assert len(unique_mmsis) == 44

    # Observed vs non-observed verification
    observed_count = sum(1 for f in fixes if f.is_observed)
    non_observed_count = sum(1 for f in fixes if not f.is_observed)
    assert observed_count == 14822
    assert non_observed_count == 14585
