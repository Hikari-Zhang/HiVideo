# hipixel-core

AI video enhancement engine for [HiVideo](https://github.com/hikari-dev/HiVideo) and HiPixel.

**Phase 0 · Python-first implementation**
> Phase 2.5 will add a Rust kernel with PyO3 + UniFFI bindings for Swift/HiVideo integration.

---

## Features

| Feature | Status |
|---|---|
| Super-resolution (Real-ESRGAN 2×/4×) | ✅ Phase 0 |
| Anime upscaling (Anime4K v4) | ✅ Phase 0 |
| Video denoising (NAFNet) | ✅ Phase 0 |
| Contrast sharpening (CAS) | ✅ Phase 0 |
| ACES tone-mapping (HDR→SDR) | ✅ Phase 0 |
| Frame interpolation (RIFE) | 🔜 Phase 1 |
| Colorization (DeOldify) | 🔜 Phase 1 |
| CoreML / Apple Silicon backend | ✅ Phase 0 |
| CUDA / NVIDIA backend | ✅ Phase 0 |
| CPU fallback | ✅ Phase 0 |
| Preset system (10 built-in) | ✅ Phase 0 |
| 3-thread decode→infer→encode pipeline | ✅ Phase 0 |
| CI: macOS · Linux · Windows matrix | ✅ Phase 0 |
| Rust kernel (PyO3 + UniFFI) | 🔜 Phase 2.5 |

---

## Quick Start

```bash
# Install with uv
uv pip install hipixel-core

# Enhance a video using the "old-film-revival" preset
hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4

# List available presets
hipixel-core presets list

# Show system info (detected GPU backend, VRAM)
hipixel-core info

# Download a specific model manually
hipixel-core models download RealESRGAN_x2plus
```

---

## Installation

```bash
# Base (CPU only)
pip install hipixel-core

# With Apple Silicon / CoreML acceleration
pip install "hipixel-core[coreml]"

# With NVIDIA CUDA acceleration
pip install "hipixel-core[cuda]"
```

**Requirements:**
- Python 3.11+
- FFmpeg (must be on `$PATH`)
- macOS 13+ with Apple Silicon *or* Linux/Windows with CUDA 11.8+

---

## Built-in Presets

| ID | Description | Min VRAM |
|---|---|---|
| `old-film-revival` | Denoise → 2× super-res → sharpen | 4 GB |
| `anime-enhance-2x` | Anime4K 2× upscale + denoise | 3 GB |
| `live-action-4k` | 4× upscale for HD→4K | 8 GB |
| `denoise-only` | NAFNet denoising, preserve resolution | 2 GB |
| `sharpen-only` | CAS sharpening only | CPU |
| `quick-enhance` | Fast 2× upscale for previews | 2 GB |
| `anime-4x-ultra` | Two-pass 4× anime upscale | 8 GB |
| `bw-restoration` | Restore B&W film: denoise → 2× super-res → sharpen | 4 GB |
| `hdr-compatible` | ACES HDR→SDR tone-mapping + sharpen | CPU |
| `smooth-60fps` | Frame interpolation to 60fps via RIFE *(Phase 1)* | 4 GB |

---

## Custom Preset

Create a `.json` file:

```json
{
  "$schema": "https://hipixel.dev/schemas/preset/v1.json",
  "id": "my-preset",
  "filters": [
    {"filter": "nafnet", "params": {"strength": 0.5}},
    {"filter": "real_esrgan", "params": {"scale": 2}},
    {"filter": "cas", "params": {"sharpness": 0.4}}
  ],
  "output": {"resolution": "2x", "codec": "h265", "crf": 18}
}
```

```bash
hipixel-core enhance input.mp4 --preset ./my-preset.json -o output.mp4
```

---

## Python API

```python
from hipixel_core.backends.selector import select_backend
from hipixel_core.filters.cas import CASFilter
from hipixel_core.pipeline import Pipeline
from hipixel_core.presets.manager import PresetManager
from hipixel_core.types import OutputSpec
from hipixel_core.video.decoder import probe

# Load preset
preset = PresetManager.load("old-film-revival")
pipeline = Pipeline.from_preset(PresetManager.as_pipeline_dict(preset))

# Probe source
meta = probe("input.mp4")
spec = OutputSpec(path="output.mp4", codec="h265", crf=18)

# Select and initialize backend
backend = select_backend()
backend.initialize()

# Run with progress callback
result = pipeline.run(
    source=meta,
    output_spec=spec,
    backend=backend,
    progress_cb=lambda e: print(f"{e.progress_pct:.1f}% — {e.fps_avg:.1f} fps"),
)
print(f"Done in {result.elapsed_s:.1f}s, avg {result.avg_fps:.1f} fps")
backend.shutdown()
```

---

## Development

```bash
# Clone the monorepo
git clone https://github.com/hikari-dev/HiVideo
cd HiVideo/hipixel-core

# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest -v -m "not slow and not gpu"

# Lint
uv run ruff check .
uv run mypy hipixel_core/

# Run the CLI in dev mode
uv run hipixel-core info
```

---

## Architecture

```
CLI (Typer + Rich)
    ↓
Pipeline (3-thread: decode → infer → encode)
    ↓
Filter Chain (RealESRGAN / Anime4K / NAFNet / CAS / ACES / RIFE)
    ↓
InferenceBackend (CoreML / CUDA / CPU)
    ↓
Model Manager (download / cache / verify)
```

See [`docs/architecture/hipixel-core-design.md`](../docs/architecture/hipixel-core-design.md) for the full system design.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
