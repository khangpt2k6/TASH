"""Typed configuration loader for the scGPT API.

The application is fully driven by ``config.yaml``. Settings are validated
through Pydantic so that a malformed or missing field fails fast at startup
rather than during a request.

The path to the config file may be overridden with the ``SCGPT_CONFIG``
environment variable; this is the recommended way to point a container at a
mounted configuration in production.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Sub-sections


class AppConfig(BaseModel):
    name: str
    version: str
    host: str
    port: int = Field(gt=0, lt=65536)
    workers: int = Field(ge=1)
    request_timeout_seconds: int = Field(ge=1)


class ModelPreprocess(BaseModel):
    normalize_total: float = 10_000.0
    log1p: bool = True
    n_bins: int = Field(default=51, ge=2)


class ModelConfig(BaseModel):
    path: str
    pad_token: str = "<pad>"
    pad_value: int = -2
    special_tokens: List[str] = ["<pad>", "<cls>", "<eoc>"]
    load_partial_state_dict: bool = True


class InferenceConfig(BaseModel):
    batch_size: int = Field(ge=1)
    max_seq_len: int = Field(ge=8)
    use_fast_transformer: bool = False
    preprocess: ModelPreprocess = ModelPreprocess()


class PathsConfig(BaseModel):
    cache_dir: str
    output_dir: str
    log_dir: str


class GPUConfig(BaseModel):
    required: bool = True
    device_id: int = Field(ge=0)
    memory_fraction: float = Field(default=0.0, ge=0.0, le=1.0)


class DownloadConfig(BaseModel):
    timeout_seconds: int = Field(ge=1)
    max_size_gb: float = Field(gt=0)
    cache_enabled: bool = True


class LoggingConfig(BaseModel):
    # ``json`` would shadow ``BaseModel.json`` in Pydantic 2; we expose it as
    # ``json_format`` internally while preserving the YAML key name.
    model_config = ConfigDict(populate_by_name=True)

    level: str = "INFO"
    json_format: bool = Field(default=True, alias="json")
    file: str = "logs/scgpt-api.log"
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    backup_count: int = Field(default=5, ge=0)

    @field_validator("level")
    @classmethod
    def valid_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"logging.level must be one of {sorted(allowed)}")
        return upper


class UMAPConfig(BaseModel):
    n_neighbors: int = Field(ge=2)
    min_dist: float = Field(ge=0.0)
    metric: str = "cosine"
    color_by: List[str] = []
    dpi: int = Field(default=150, ge=50)
    figsize: Tuple[float, float] = (10.0, 8.0)


class JobsConfig(BaseModel):
    max_history: int = Field(default=500, ge=1)


# Root settings


class Settings(BaseModel):
    """Root settings object, mirrors the layout of ``config.yaml``."""

    app: AppConfig
    model: ModelConfig
    inference: InferenceConfig
    paths: PathsConfig
    gpu: GPUConfig
    download: DownloadConfig
    logging: LoggingConfig
    umap: UMAPConfig
    jobs: JobsConfig = JobsConfig()

    # Absolute path of the config file used, for diagnostics.
    config_path: str = ""

    def ensure_directories(self) -> None:
        """Create any directories the application needs to write to."""
        for p in (
            self.paths.cache_dir,
            self.paths.output_dir,
            self.paths.log_dir,
        ):
            Path(p).mkdir(parents=True, exist_ok=True)


# Loader


_DEFAULT_CONFIG_FILENAME = "config.yaml"


def resolve_config_path() -> Path:
    """Find the config file, honouring the ``SCGPT_CONFIG`` env var."""
    override = os.environ.get("SCGPT_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parent / _DEFAULT_CONFIG_FILENAME).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache the application settings.

    The result is cached for the lifetime of the process – settings are not
    expected to change at runtime.
    """
    cfg_path = resolve_config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {cfg_path}. Set SCGPT_CONFIG to "
            "point at a valid YAML file."
        )

    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    settings = Settings(**raw, config_path=str(cfg_path))
    settings.ensure_directories()
    return settings
