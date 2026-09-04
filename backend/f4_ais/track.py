"""Feature F4.3 — Vessel Track Reconstruction Service.

Constructs vessel-specific chronological AIS tracks from CorridorAISMatch records
(or ValidatedAISFix records with hypothesis association).
Enforces:
- Grouping by MMSI and hypothesis context
- Strictly chronological, deterministic sorting
- Reporting gap detection and metric calculation
- Strict preservation of is_observed (observed vs non-observed/interpolated)
- Frozen track ID convention: TRK_<event_id>_<mmsi>
- Zero fabricated observed records and zero ML attribution
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from backend.f4_ais.schemas import CorridorAISMatch, ValidatedAISFix, VesselTrack


# [UNRESOLVED] Default reporting gap threshold.
# In the synthetic generator, gap_thr was based on vessel.report_interval_min * 3.0 (0.1h to 0.5h).
# In operational AIS without per-vessel metadata, 1.0 hour is the standard dropout threshold.
DEFAULT_GAP_THRESHOLD_HOURS: float = 1.0


class TrackReconstructionService:
    """Deterministic domain service for reconstructing vessel tracks from AIS fixes."""

    def __init__(self, default_gap_threshold_hours: float = DEFAULT_GAP_THRESHOLD_HOURS) -> None:
        self.default_gap_threshold_hours = default_gap_threshold_hours

    @staticmethod
    def format_track_id(event_id: Optional[str], mmsi: str) -> str:
        """Enforces the frozen Track ID convention: TRK_<event_id>_<mmsi>."""
        prefix = event_id if event_id else "UNKNOWN"
        return f"TRK_{prefix}_{mmsi}"

    def build_tracks_from_corridor_matches(
        self,
        matches: Sequence[CorridorAISMatch],
        gap_threshold_hours: Optional[float] = None,
    ) -> Dict[str, VesselTrack]:
        """Groups CorridorAISMatch records into tracks by (event_id, source_hypothesis_id, mmsi).

        Returns:
            Dictionary mapping track key f"{hyp_id}_{mmsi}" to VesselTrack.
        """
        threshold = gap_threshold_hours if gap_threshold_hours is not None else self.default_gap_threshold_hours
        grouped: Dict[Tuple[str, str, str], List[CorridorAISMatch]] = {}

        for m in matches:
            key = (m.event_id, m.source_hypothesis_id, m.mmsi)
            grouped.setdefault(key, []).append(m)

        tracks: Dict[str, VesselTrack] = {}
        for (event_id, hyp_id, mmsi), fix_list in grouped.items():
            track = self._build_single_track(
                mmsi=mmsi,
                fixes=fix_list,
                event_id=event_id,
                hypothesis_id=hyp_id,
                gap_threshold_hours=threshold,
            )
            track_key = f"{hyp_id}_{mmsi}"
            tracks[track_key] = track

        return tracks

    def build_tracks(
        self,
        fixes: Sequence[Union[CorridorAISMatch, ValidatedAISFix]],
        event_id: Optional[str] = None,
        hypothesis_id: Optional[str] = None,
        gap_threshold_hours: Optional[float] = None,
    ) -> Dict[str, VesselTrack]:
        """Groups AIS fixes by MMSI and reconstructs chronological tracks.

        Supports both CorridorAISMatch and ValidatedAISFix records.
        """
        threshold = gap_threshold_hours if gap_threshold_hours is not None else self.default_gap_threshold_hours
        by_mmsi: Dict[str, List[Union[CorridorAISMatch, ValidatedAISFix]]] = {}

        for f in fixes:
            by_mmsi.setdefault(f.mmsi, []).append(f)

        tracks: Dict[str, VesselTrack] = {}
        # Deterministic MMSI ordering
        for mmsi in sorted(by_mmsi.keys()):
            fix_list = by_mmsi[mmsi]
            # Infer event_id and hypothesis_id from fixes if available
            ev_id = event_id
            h_id = hypothesis_id
            if fix_list and isinstance(fix_list[0], CorridorAISMatch):
                ev_id = ev_id or fix_list[0].event_id
                h_id = h_id or fix_list[0].source_hypothesis_id

            track = self._build_single_track(
                mmsi=mmsi,
                fixes=fix_list,
                event_id=ev_id,
                hypothesis_id=h_id,
                gap_threshold_hours=threshold,
            )
            tracks[mmsi] = track

        return tracks

    def _build_single_track(
        self,
        mmsi: str,
        fixes: Sequence[Union[CorridorAISMatch, ValidatedAISFix]],
        event_id: Optional[str],
        hypothesis_id: Optional[str],
        gap_threshold_hours: float,
    ) -> VesselTrack:
        """Constructs and validates a single chronological VesselTrack."""
        if not fixes:
            return VesselTrack(
                mmsi=mmsi,
                track_id=self.format_track_id(event_id, mmsi),
                event_id=event_id,
                source_hypothesis_id=hypothesis_id,
                fixes=[],
                duration_hours=0.0,
                observation_count=0,
                non_observation_count=0,
                gap_count=0,
                max_gap_hours=0.0,
                track_completeness=0.0,
            )

        # Strictly chronological, stable sorting: (timestamp_utc, latitude, longitude)
        sorted_fixes = sorted(
            fixes,
            key=lambda x: (
                x.timestamp_utc.astimezone(timezone.utc)
                if x.timestamp_utc.tzinfo is not None
                else x.timestamp_utc.replace(tzinfo=timezone.utc),
                x.latitude,
                x.longitude,
            ),
        )

        first_fix = sorted_fixes[0]
        last_fix = sorted_fixes[-1]

        t0 = first_fix.timestamp_utc
        t1 = last_fix.timestamp_utc
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        if t1.tzinfo is None:
            t1 = t1.replace(tzinfo=timezone.utc)

        duration_hours = max(0.0, (t1.timestamp() - t0.timestamp()) / 3600.0)

        # Observations vs non-observations
        obs_count = sum(1 for f in sorted_fixes if f.is_observed)
        non_obs_count = len(sorted_fixes) - obs_count

        # Gap detection
        gap_count = 0
        max_gap_hours = 0.0
        total_gap_hours = 0.0

        for i in range(len(sorted_fixes) - 1):
            fa = sorted_fixes[i]
            fb = sorted_fixes[i + 1]
            ta = fa.timestamp_utc if fa.timestamp_utc.tzinfo else fa.timestamp_utc.replace(tzinfo=timezone.utc)
            tb = fb.timestamp_utc if fb.timestamp_utc.tzinfo else fb.timestamp_utc.replace(tzinfo=timezone.utc)
            dt_h = max(0.0, (tb.timestamp() - ta.timestamp()) / 3600.0)

            if dt_h > gap_threshold_hours:
                gap_count += 1
                max_gap_hours = max(max_gap_hours, dt_h)
                total_gap_hours += dt_h

        # [UNRESOLVED — TRACK COMPLETENESS FORMULATION]
        # MVP ASSUMPTION: Evaluates a gap-based track completeness proxy:
        # 1.0 - (total_gap_hours / track_duration_h)
        # Note: This is NOT the percentage of expected transmissions, as broadcast cadence is unknown.
        if duration_hours <= 0.0:
            track_completeness = 1.0 if obs_count > 0 else 0.0
        else:
            completeness = 1.0 - min(1.0, total_gap_hours / max(duration_hours, 1.0))
            track_completeness = round(completeness, 4)

        # Extract vessel metadata from first non-null record
        v_type = next((f.vessel_type for f in sorted_fixes if f.vessel_type), None)
        v_length = next((f.vessel_length for f in sorted_fixes if f.vessel_length is not None), None)
        v_width = next((f.vessel_width for f in sorted_fixes if f.vessel_width is not None), None)
        v_draught = next((f.draught for f in sorted_fixes if f.draught is not None), None)

        return VesselTrack(
            mmsi=mmsi,
            track_id=self.format_track_id(event_id, mmsi),
            event_id=event_id,
            source_hypothesis_id=hypothesis_id,
            fixes=sorted_fixes,
            vessel_type=v_type,
            vessel_length=v_length,
            vessel_width=v_width,
            draught=v_draught,
            first_timestamp=first_fix.timestamp_iso,
            last_timestamp=last_fix.timestamp_iso,
            duration_hours=round(duration_hours, 4),
            observation_count=obs_count,
            non_observation_count=non_obs_count,
            gap_count=gap_count,
            max_gap_hours=round(max_gap_hours, 4),
            track_completeness=track_completeness,
        )
