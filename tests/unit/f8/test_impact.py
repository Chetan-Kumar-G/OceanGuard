"""GIS impact overlay: coast / sensitive-zone distances and the beaching flag,
checked against hand values from the synthetic ``config.used.yaml`` geography."""
from __future__ import annotations

from shared.config.settings import get_settings
from backend.f8_forecast.impact import (
    beaching_risk,
    coast_distance_km,
    impact_area_candidates,
    zone_distance_km,
)

_CFG = get_settings().load_config_yaml()  # coast_edge=south, AOI 400x400,
#                                           MPA_North_Bank @ (120,45) r=25, MPA_East_Shoal @ (300,90) r=30


def test_coast_distance_for_south_edge_is_the_y_coordinate():
    assert coast_distance_km(_CFG, cx_km=150.0, cy_km=37.0) == 37.0
    assert coast_distance_km(_CFG, cx_km=10.0, cy_km=3.0) == 3.0


def test_zone_distance_is_boundary_distance_and_names_the_nearest():
    d, name = zone_distance_km(_CFG, cx_km=120.0, cy_km=45.0)  # centre of MPA_North_Bank
    assert name == "MPA_North_Bank"
    assert d == 0.0  # inside the disc -> clamped to 0

    d2, name2 = zone_distance_km(_CFG, cx_km=120.0, cy_km=120.0)  # 75 km north of centre, r=25
    assert name2 == "MPA_North_Bank"
    assert abs(d2 - 50.0) < 1e-6


def test_beaching_risk_triggers_when_coast_within_two_spreads():
    assert beaching_risk(coast_d_km=5.0, spread_km=3.0) is True     # 5 < 6
    assert beaching_risk(coast_d_km=20.0, spread_km=3.0) is False   # 20 > 6


def test_impact_candidates_lists_coast_edge_when_beaching():
    names = impact_area_candidates(_CFG, frame=None, envelope_poly_km=None, coast_d_km=2.0, spread_km=3.0)
    assert "coastline:south" in names
