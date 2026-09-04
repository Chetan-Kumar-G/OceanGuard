"""Shared configuration infrastructure for OceanGuard."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application and dataset settings."""
    # Base directories
    PROJECT_ROOT: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data"

    @property
    def SYNTHETIC_ROOT(self) -> Path:
        """Parent of the generated dataset (holds ``outputs/`` and ``oiltrace_synth/``)."""
        return self.DATA_DIR / "raw" / "synthetic"

    @property
    def RAW_SYNTHETIC_DIR(self) -> Path:
        """Canonical location of the generated D1..D8 CSVs and image/mask folders."""
        outputs = self.SYNTHETIC_ROOT / "outputs"
        if outputs.exists():
            return outputs
        return self.SYNTHETIC_ROOT

    @property
    def SIH_SATELLITE_DIR(self) -> Path:
        return self.DATA_DIR / "raw" / "sih_satellite"

    @property
    def MODELS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "models"

    @property
    def EVALUATION_DIR(self) -> Path:
        return self.DATA_DIR / "evaluation" / "synthetic"

    @property
    def CONFIG_YAML_PATH(self) -> Path:
        """Discovers the synthetic configuration file without mutating filenames.
        Checks config.yaml first, then seamlessly falls back to config.used.yaml.
        """
        primary = self.RAW_SYNTHETIC_DIR / "config.yaml"
        if primary.exists():
            return primary
        fallback = self.RAW_SYNTHETIC_DIR / "config.used.yaml"
        if fallback.exists():
            return fallback
        return primary

    @property
    def D1_SCENES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D1_satellite_scenes.csv"

    @property
    def D2_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D2_temporal_states.csv"

    @property
    def D3_SOURCE_HYPOTHESES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D3_source_hypotheses.csv"

    @property
    def D3_PARTICLES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D3_hindcast_particles.csv"

    @property
    def D4_AIS_RAW_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D4_ais_raw.csv"

    @property
    def D4_VESSEL_TRACKS_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D4_vessel_tracks.csv"

    @property
    def D5_EVIDENCE_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D5_evidence_consistency.csv"

    @property
    def D6_RANKING_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D6_evidence_ranking.csv"

    @property
    def D7_NODES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D7_graph_nodes.csv"

    @property
    def D7_EDGES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D7_graph_edges.csv"

    @property
    def D8_FORECAST_RUNS_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D8_forecast_runs.csv"

    @property
    def D8_FORECAST_PARTICLES_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "D8_forecast_particles.csv"

    @property
    def D8_EVALUATION_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "evaluation_only" / "D8_evaluation.csv"

    @property
    def GROUND_TRUTH_CSV_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "ground_truth_events.csv"

    @property
    def MANIFEST_JSON_PATH(self) -> Path:
        return self.RAW_SYNTHETIC_DIR / "manifest.json"

    # API settings
    API_V1_PREFIX: str = "/api/v1"
    APP_NAME: str = "OceanGuard OilTrace AI"
    DEBUG: bool = False

    def load_config_yaml(self) -> Dict[str, Any]:
        """Loads the discovered YAML configuration dictionary."""
        path = self.CONFIG_YAML_PATH
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found at {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
