"""
Preset manager — load, validate, and resolve enhancement presets.

Presets are JSON files that describe a complete filter pipeline:
    - Which filters to run and in what order
    - Filter parameters (strength, scale, tile size, etc.)
    - Output encoding specification
    - Hardware requirements (min VRAM)

Built-in presets are bundled in ``hipixel_core/presets/builtin/``.
Users can also supply external ``.json`` preset files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Preset schema (Pydantic v2)
# ---------------------------------------------------------------------------

_BUILTIN_DIR = Path(__file__).parent / "builtin"


class FilterStep(BaseModel):
    """Single filter step within a preset pipeline."""

    filter: str
    params: dict[str, Any] = Field(default_factory=dict)


class OutputConfig(BaseModel):
    """Output encoding configuration embedded in a preset."""

    resolution: str = "2x"
    fps: str = "preserve"  # "preserve" or a number string
    codec: str = "h265"
    crf: int = 18
    container: str = "mp4"

    @field_validator("crf")
    @classmethod
    def validate_crf(cls, v: int) -> int:
        if not 0 <= v <= 51:
            raise ValueError(f"CRF must be in [0, 51], got {v}")
        return v


class Requirements(BaseModel):
    """Hardware requirements declared by a preset."""

    min_vram_mb: int = 0
    recommended_vram_mb: int = 0


class PresetSchema(BaseModel):
    """Full preset document schema (matches preset/v1.json)."""

    schema_url: str | None = Field(None, alias="$schema")
    id: str
    name: str | None = None
    description: str | None = None
    filters: list[FilterStep]
    output: OutputConfig = Field(default_factory=OutputConfig)
    requirements: Requirements = Field(default_factory=Requirements)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class PresetManager:
    """Loads and caches enhancement presets from disk.

    Preset resolution order (first match wins):
        1. Absolute/relative path ending in ``.json``
        2. Built-in preset by ID (``hipixel_core/presets/builtin/<id>.json``)
    """

    _cache: ClassVar[dict[str, PresetSchema]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, preset_id_or_path: str) -> PresetSchema:
        """Load and return a validated preset.

        Args:
            preset_id_or_path:  Either a built-in preset ID (e.g.
                ``"old-film-revival"``) or a path to a custom ``.json`` file.

        Returns:
            Validated :class:`PresetSchema` instance.

        Raises:
            ``FileNotFoundError`` if no matching preset is found.
            ``ValueError`` if the preset fails schema validation.
        """
        if preset_id_or_path in cls._cache:
            return cls._cache[preset_id_or_path]

        path = cls._resolve_path(preset_id_or_path)
        preset = cls._load_file(path)
        cls._cache[preset_id_or_path] = preset
        return preset

    @classmethod
    def list_builtin(cls) -> list[str]:
        """Return IDs of all built-in presets."""
        return sorted(p.stem for p in _BUILTIN_DIR.glob("*.json"))

    @classmethod
    def as_pipeline_dict(cls, preset: PresetSchema) -> dict[str, Any]:
        """Convert a PresetSchema to the dict format expected by Pipeline."""
        return {
            "filters": [{"filter": step.filter, "params": step.params} for step in preset.filters],
            "output": preset.output.model_dump(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_path(cls, id_or_path: str) -> Path:
        p = Path(id_or_path)
        # Explicit path
        if p.suffix == ".json" and p.exists():
            return p
        # Built-in lookup
        builtin = _BUILTIN_DIR / f"{id_or_path}.json"
        if builtin.exists():
            return builtin
        raise FileNotFoundError(
            f"Preset not found: '{id_or_path}'. Built-in presets: {', '.join(cls.list_builtin())}"
        )

    @classmethod
    def _load_file(cls, path: Path) -> PresetSchema:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return PresetSchema.model_validate(raw)
