"""Project configuration loader.

Single source of truth for AWS profile, region, model IDs, and feature toggles.
All other modules MUST import settings from here — never hardcode.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass(frozen=True)
class ModelConfig:
    id: str
    provider: str
    context_window: int
    use_for: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    aws_profile: str
    aws_region: str
    primary_model: ModelConfig
    secondary_model: ModelConfig
    bedrock_beta_headers: tuple[str, ...]
    max_tokens_default: int
    temperature_default: float
    embedding_id: str
    embedding_dimensions: int
    opensearch_collection: str
    opensearch_index: str
    tile_size: int
    tile_overlap: int
    dpi: int
    max_self_correction_iterations: int
    artifacts_dir: Path
    logs_dir: Path


def _build_model(raw: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        id=raw["id"],
        provider=raw["provider"],
        context_window=int(raw["context_window"]),
        use_for=tuple(raw["use_for"]),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    with SETTINGS_PATH.open() as f:
        raw = yaml.safe_load(f)
    return Settings(
        aws_profile=raw["aws"]["profile"],
        aws_region=raw["aws"]["region"],
        primary_model=_build_model(raw["models"]["primary"]),
        secondary_model=_build_model(raw["models"]["secondary"]),
        bedrock_beta_headers=tuple(raw["bedrock"]["beta_headers"]),
        max_tokens_default=int(raw["bedrock"]["max_tokens_default"]),
        temperature_default=float(raw["bedrock"]["temperature_default"]),
        embedding_id=raw["embedding"]["id"],
        embedding_dimensions=int(raw["embedding"]["dimensions"]),
        opensearch_collection=raw["opensearch"]["collection_name"],
        opensearch_index=raw["opensearch"]["index_name"],
        tile_size=int(raw["extraction"]["tile_size"]),
        tile_overlap=int(raw["extraction"]["tile_overlap"]),
        dpi=int(raw["extraction"]["dpi"]),
        max_self_correction_iterations=int(raw["extraction"]["max_self_correction_iterations"]),
        artifacts_dir=PROJECT_ROOT / raw["storage"]["artifacts_dir"],
        logs_dir=PROJECT_ROOT / raw["storage"]["logs_dir"],
    )
