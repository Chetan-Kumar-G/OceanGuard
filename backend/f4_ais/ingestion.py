"""Deterministic AIS Ingestion Service for Feature F4.

Reads historical AIS transmissions, invokes validation and UTC normalization,
preserves raw provenance (source, is_observed, nav_status, vessel static dimensions),
and guarantees zero event_id invention or ground-truth leakage.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple, Union

from shared.config.settings import get_settings
from backend.f4_ais.schemas import (
    AISValidationReport,
    RawAISRecord,
    ValidatedAISFix,
)
from backend.f4_ais.validation import AISValidationService, validate_ais_stream


class AISIngestionService:
    """Service responsible for reading, parsing, and validating raw AIS datasets."""

    def __init__(self, validation_service: Optional[AISValidationService] = None) -> None:
        self.validator = validation_service or AISValidationService()

    @staticmethod
    def stream_raw_csv(
        csv_path: Path, max_records: Optional[int] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Streams raw AIS dictionary records line-by-line from a CSV file.

        Prevents loading entire multi-gigabyte archives into memory at once.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Raw AIS CSV file not found at {csv_path}")

        count = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row
                count += 1
                if max_records is not None and count >= max_records:
                    break

    def ingest_csv(
        self,
        csv_path: Optional[Path] = None,
        max_records: Optional[int] = None,
    ) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
        """Ingests and validates raw AIS transmissions from a CSV file.

        Args:
            csv_path: Optional path to the CSV file. Defaults to D4_AIS_RAW_CSV_PATH.
            max_records: Optional cap on the number of records to ingest.

        Returns:
            Tuple of (list of ValidatedAISFix, complete AISValidationReport)
        """
        path = csv_path or get_settings().D4_AIS_RAW_CSV_PATH
        stream = self.stream_raw_csv(path, max_records=max_records)
        return self.validator.validate_stream(stream)

    def ingest_records(
        self, records: Iterable[Union[Dict[str, Any], RawAISRecord]]
    ) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
        """Ingests and validates in-memory raw AIS records.

        Guarantees:
        - Timestamps normalized to UTC ISO-8601.
        - Geographic coordinates validated in EPSG:4326.
        - Missing navigation values preserved as None (distinct from 0.0).
        - Provenance fields (source, is_observed, nav_status, static dimensions) preserved.
        - Event IDs are NEVER assigned or invented at this ingestion layer.
        """
        return self.validator.validate_stream(records)
