"""
Model manager — download, verify, and cache AI model weights.

All models are stored under ``~/.cache/hipixel-core/models/``.
Each model entry in ``registry.json`` includes:
    - Download URL (primary + mirror)
    - SHA-256 hash for integrity verification
    - Expected file size in bytes
    - Version string

The manager enforces version locking: if a different version is already
cached, it is kept unless explicitly updated with ``force=True``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TransferSpeedColumn,
)

from hipixel_core._log import get_logger

_log = get_logger("models.manager")

#: Default cache directory for downloaded models
_CACHE_DIR = Path.home() / ".cache" / "hipixel-core" / "models"

#: Path to the model registry bundled with the package
_REGISTRY_PATH = Path(__file__).parent / "registry.json"


class ModelNotFoundError(Exception):
    """Raised when a model key is not in the registry."""


class ModelIntegrityError(Exception):
    """Raised when a downloaded model fails SHA-256 verification."""


class ModelManager:
    """Manages AI model lifecycle: discovery, download, and verification.

    All methods are class methods; no instantiation required.
    """

    _registry: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def get_model_path(cls, model_name: str, auto_download: bool = True) -> str:
        """Return the local path to a model file, downloading if needed.

        Priority order:
        1. Native CoreML ``.mlpackage`` (best for Apple Silicon)
        2. ONNX ``.onnx`` file (fallback for other platforms)

        Args:
            model_name:     Registry key, e.g. ``"RealESRGAN_x2plus"``.
            auto_download:  If True, download the model when not cached.

        Returns:
            Absolute path to the model file (preferring ``.mlpackage``).

        Raises:
            ``ModelNotFoundError`` if the model is not in the registry.
            ``ModelIntegrityError`` if downloaded file fails hash check.
        """
        entry = cls._get_entry(model_name)
        base_name = Path(entry["filename"]).stem  # e.g., "RealESRGAN_x4plus"

        # 1. Search for matching .mlpackage files (best for Apple Silicon).
        #    Only use them when coremltools is actually importable; otherwise
        #    fall through silently to the ONNX path so inference still works.
        #    Priority: _dynamic > _static_* > others
        if _CACHE_DIR.exists():
            mlpackages = [
                f for f in _CACHE_DIR.iterdir()
                if f.suffix == ".mlpackage" and f.stem.startswith(base_name)
            ]
            if mlpackages:
                try:
                    import coremltools  # noqa: F401 — availability check only
                    _coremltools_available = True
                except ImportError:
                    _coremltools_available = False
                    _log.debug(
                        "ModelManager: coremltools not installed — "
                        "skipping .mlpackage for %s, falling back to ONNX",
                        base_name,
                    )

                if _coremltools_available:
                    # Prefer _dynamic (supports arbitrary input sizes)
                    dynamic = [f for f in mlpackages if "_dynamic" in f.stem]
                    if dynamic:
                        _log.debug("ModelManager: using dynamic CoreML model: %s", dynamic[0])
                        return str(dynamic[0])
                    # Fall back to first match (static)
                    _log.debug("ModelManager: using static CoreML model: %s", mlpackages[0])
                    return str(mlpackages[0])

        # 2. ONNX .onnx file (fallback)
        onnx_path: Path = _CACHE_DIR / str(entry["filename"])

        if onnx_path.exists():
            # Verify integrity.  When size_bytes is unknown (0) we trust the
            # cached file; otherwise a size mismatch forces a fresh download.
            expected_size: int = entry.get("size_bytes", 0)
            if expected_size == 0 or onnx_path.stat().st_size == expected_size:
                _log.debug("ModelManager: using ONNX model: %s", onnx_path)
                return str(onnx_path)
            # Size mismatch — re-download
            onnx_path.unlink()

        # No model cached — download ONNX version
        if not auto_download:
            raise FileNotFoundError(
                f"Model '{model_name}' not cached. "
                "Run `hipixel-core models download {model_name}` to fetch it."
            )

        cls._download(model_name, entry, onnx_path)
        return str(onnx_path)

    @classmethod
    def download(cls, model_name: str, force: bool = False) -> Path:
        """Explicitly download a model by name.

        Args:
            model_name:  Registry key.
            force:       If True, re-download even if already cached.

        Returns:
            Local path to the downloaded model.
        """
        entry = cls._get_entry(model_name)
        local_path: Path = _CACHE_DIR / str(entry["filename"])

        if local_path.exists() and not force:
            return local_path

        cls._download(model_name, entry, local_path)
        return local_path

    @classmethod
    def list_registry(cls) -> list[dict[str, Any]]:
        """Return all entries from the model registry."""
        return list(cls._load_registry().get("models", {}).values())

    @classmethod
    def list_cached(cls) -> list[str]:
        """Return names of models currently cached on disk."""
        registry = cls._load_registry()
        cached = []
        for name, entry in registry.get("models", {}).items():
            path = _CACHE_DIR / entry["filename"]
            if path.exists():
                cached.append(name)
        return cached

    @classmethod
    def remove(cls, model_name: str) -> bool:
        """Delete a cached model file.

        Returns:
            True if the file was deleted, False if it wasn't cached.
        """
        entry = cls._get_entry(model_name)
        path = _CACHE_DIR / entry["filename"]
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @classmethod
    def _get_entry(cls, model_name: str) -> dict[str, Any]:
        registry = cls._load_registry()
        entry: dict[str, Any] | None = registry.get("models", {}).get(model_name)
        if entry is None:
            available = ", ".join(registry.get("models", {}).keys())
            raise ModelNotFoundError(
                f"Model '{model_name}' not found in registry. Available: {available}"
            )
        return entry

    @classmethod
    def _load_registry(cls) -> dict[str, Any]:
        if cls._registry is None:
            cls._registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        return cls._registry

    @classmethod
    def _download(
        cls,
        model_name: str,
        entry: dict[str, Any],
        dest: Path,
    ) -> None:
        """Download a model with progress display and integrity check."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        urls: list[str] = [entry["url"], *entry.get("mirrors", [])]
        last_error: Exception | None = None

        for url in urls:
            try:
                cls._download_url(model_name, url, dest, entry)
                return
            except Exception as exc:
                last_error = exc
                if dest.exists():
                    dest.unlink()

        raise RuntimeError(
            f"Failed to download model '{model_name}' from all sources."
        ) from last_error

    @staticmethod
    def _download_url(
        model_name: str,
        url: str,
        dest: Path,
        entry: dict[str, Any],
    ) -> None:
        """Stream download with Rich progress bar."""
        tmp = dest.with_suffix(".tmp")
        sha = hashlib.sha256()

        with Progress(
            "[bold blue]{task.description}",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            total = entry.get("size_bytes", 0) or None
            task = progress.add_task(f"Downloading {model_name}", total=total)

            with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        sha.update(chunk)
                        progress.update(task, advance=len(chunk))

        digest = sha.hexdigest()
        expected = entry.get("sha256", "")
        if expected and digest != expected:
            tmp.unlink(missing_ok=True)
            raise ModelIntegrityError(
                f"SHA-256 mismatch for '{model_name}': "
                f"expected {expected[:16]}…, got {digest[:16]}…"
            )

        shutil.move(str(tmp), str(dest))

    # ------------------------------------------------------------------
    # pth → onnx auto-conversion pipeline
    # ------------------------------------------------------------------

    @classmethod
    def _ensure_convert_deps(cls) -> None:
        """Lazy-check that torch + basicsr are importable.

    Raises
    ------
    ImportError
        With a **helpful message** pointing to ``pip install hipixel-core[convert]``.

    Notes
    -----
    BasicSR is NOT required — we use local architecture definitions
    in ``hipixel_core.models.converters.archs``.
    """
        try:
            import torch  # noqa: F401 – imported for side effects
            import onnx  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Converting pth→onnx requires PyTorch and ONNX.\n"
                "Install them with:\n"
                "    pip install 'hipixel-core[convert]'"
            ) from exc

    @classmethod
    def _convert_pth_to_onnx(
        cls,
        model_name: str,
        entry: dict[str, Any],
        dest: Path,
    ) -> None:
        """Download ``.pth`` weights (if needed) and export ``.onnx`` to *dest*.

        Parameters
        ----------
        model_name:
            Registry key, e.g. ``"RealESRGAN_x4plus"``.
        entry:
            The corresponding registry entry (must contain ``source_pth_url``
            and ``arch_config``).
        dest:
            Destination ``.onnx`` path (the file that ``get_model_path()``
            expects to find).
        """
        cls._ensure_convert_deps()

        from hipixel_core.models.converters import convert as _convert

        cache_dir: Path = _CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)

        pth_name: str = entry.get("pth_name", f"{model_name}.pth")
        pth_path: Path = cache_dir / pth_name

        # --------------------------------------------------------------
        # 1. Fetch .pth if not already cached
        # --------------------------------------------------------------
        if not pth_path.exists():
            pth_url: str = entry["source_pth_url"]
            print(f"  Downloading .pth weights: {pth_url} …")
            tmp = pth_path.with_suffix(".tmp")
            with httpx.stream("GET", pth_url, follow_redirects=True, timeout=120.0) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            tmp.rename(pth_path)
            print(f"  Saved .pth → {pth_path}")
        else:
            print(f"  Using cached .pth: {pth_path}")

        # --------------------------------------------------------------
        # 2. Convert → .onnx
        # --------------------------------------------------------------
        arch_config: dict[str, Any] = entry["arch_config"]
        print(f"  Converting {model_name} → {dest.name} …")
        _convert(pth_path, dest, arch_config=arch_config)
        print(f"  ✓ Converted → {dest}")

    @classmethod
    def _download(
        cls,
        model_name: str,
        entry: dict[str, Any],
        dest: Path,
    ) -> None:
        """Download a model with progress display and integrity check."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------------------
        # Fast path: try URL / mirrors first
        # --------------------------------------------------------------
        urls: list[str] = []
        primary = entry.get("url", "")
        if primary:
            urls.append(primary)
        urls.extend(entry.get("mirrors", []))

        last_error: Exception | None = None

        for url in urls:
            if not url:
                continue
            try:
                cls._download_url(model_name, url, dest, entry)
                return
            except Exception as exc:
                last_error = exc
                if dest.exists():
                    dest.unlink()
                print(f"  Download failed ({exc}); trying next source …")

        # --------------------------------------------------------------
        # Fallback: pth → onnx auto-conversion
        # --------------------------------------------------------------
        if "source_pth_url" in entry and "arch_config" in entry:
            print(f"  All downloads failed — attempting pth→onnx conversion …")
            try:
                cls._convert_pth_to_onnx(model_name, entry, dest)
                return
            except Exception as exc:
                last_error = exc
                print(f"  Conversion also failed: {exc}")

        raise RuntimeError(
            f"Failed to obtain model '{model_name}' (all sources and conversion failed)."
        ) from last_error
