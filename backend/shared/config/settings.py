from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base Paths
    workspace_root: Path = Path(__file__).resolve().parents[3]
    data_dir: Path = workspace_root / "data"
    synthetic_data_dir: Path = data_dir / "raw" / "synthetic"
    sih_satellite_dir: Path = data_dir / "raw" / "sih_satellite"
    models_dir: Path = workspace_root / "models"
    
    # F1 Model configuration
    f1_model_name: str = "unet_baseline"
    f1_model_version: str = "v1"
    f1_model_path: Optional[Path] = None
    
    # Inference parameters
    f1_confidence_threshold: float = 0.50
    f1_min_area_px: int = 20
    f1_lookalike_threshold: float = 0.35
    
    # API Settings
    api_title: str = "OceanGuard AI Detection API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    def get_model_weights_path(self) -> Path:
        if self.f1_model_path and self.f1_model_path.exists():
            return self.f1_model_path
        return self.models_dir / "f1_detection" / self.f1_model_name / self.f1_model_version / "model.pt"


settings = Settings()
