# Anime4K v4 Filter Implementation Report

## Executive Summary

The project already has a partial `Anime4KFilter` stub (lines 24-86 in `anime4k.py`). This report details all the existing filter architecture, protocols, and supporting systems needed to ensure a complete, production-ready Anime4K v4 implementation.

---

## 1. FILTER PROTOCOL ARCHITECTURE

**File**: `hipixel_core/filters/base.py` (lines 26-138)

### Protocol Definition
```python
@runtime_checkable
class Filter(Protocol):
```

The `Filter` is a **formal Protocol** (not a base class) using Python's `typing.Protocol` with `@runtime_checkable`. This enables duck-typing while maintaining explicit interface contracts.

### Filter Protocol Methods

#### Identity
- **`name`** (property): Unique string identifier (e.g., `"anime4k"`)
- **`required_models`** (property): List[str] of model registry keys needed

#### Lifecycle
- **`setup(backend: InferenceBackend, params: FilterParams) -> None`**
  - Called once before first `process_frame()`
  - Should load model(s) into backend using `backend.load_model(path, key)`
  - Use `ModelManager.get_model_path(model_name)` to resolve registry names

- **`teardown(backend: InferenceBackend) -> None`**
  - Called after processing completes
  - Must unload models via `backend.unload_model(key)`
  - Must be idempotent

#### Frame Processing
- **`process_frame(frame: VideoFrame, backend: InferenceBackend, params: FilterParams) -> VideoFrame`**
  - **CRITICAL**: Must return a NEW VideoFrame, never mutate input
  - Should handle tiling for large frames (see RealESRGAN pattern)
  - Must be thread-safe for pipeline worker threads

#### Resource Estimation
- **`estimated_vram_mb(input_resolution: tuple[int, int]) -> int`**
  - Returns peak VRAM in MB for given (width, height)
  - Used by Pipeline for tile-size scheduling

### Filter Implementations

1. **RealESRGANFilter** — 2x/4x super-resolution with tile-based inference
2. **Anime4KFilter** — Already partially stubbed ✓
3. **NAFNetFilter** — ONNX denoising with strength blending
4. **CASFilter** — CPU-only adaptive sharpening (no models)
5. **RIFEFilter** — Phase 1 stub (raises NotImplementedError)

---

## 2. VIDEOFRAME TYPE SYSTEM

**File**: `hipixel_core/types.py` (lines 36-96)

### VideoFrame Dataclass
```python
@dataclass
class VideoFrame:
    data: np.ndarray                    # (H, W, 3), uint8 or float32
    pts: float                          # Presentation timestamp (seconds)
    width: int
    height: int
    colorspace: ColorSpace = ColorSpace.BT709
    is_hdr: bool = False
    hdr_metadata: dict[str, Any] | None = None
```

### Key Properties
- **`data` shape**: Always `(H, W, 3)` — RGB channels last
- **`data` dtype**: Either `uint8` [0-255] or `float32` [0.0-1.0]
- **`resolution`** property: Returns `(width, height)` tuple

### Helper Methods
- **`to_float32() -> VideoFrame`**: Converts to float32 normalized [0,1]
- **`to_uint8() -> VideoFrame`**: Converts to uint8 [0,255]

### Other Important Types
- **`FilterParams`** (line 228): Type alias `dict[str, Any]` for filter options
- **`ColorSpace`** enum: BT601, BT709, BT2020, SRGB, LINEAR
- **`DeviceInfo`**: Describes backend hardware (vram_mb, backend_name, etc.)

---

## 3. INFERENCEBACKEND PROTOCOL

**File**: `hipixel_core/backends/base.py` (lines 22-138)

### Backend Protocol
```python
@runtime_checkable
class InferenceBackend(Protocol):
```

### Key Methods

#### Identity
- **`name`** property: "cpu", "cuda", "coreml", etc.
- **`device_info`** property: Returns DeviceInfo

#### Lifecycle
- **`initialize() -> None`**: One-time setup (driver, CUDA context)
- **`shutdown() -> None`**: Release all resources (idempotent)

#### Model Management
- **`load_model(model_path: str, model_key: str) -> None`**
  - Loads ONNX (or platform-native) model into GPU/CPU memory
  - `model_key`: Logical name for later `run()` calls

- **`unload_model(model_key: str) -> None`**
  - Removes model from memory (no-op if not loaded)

- **`is_model_loaded(model_key: str) -> bool`**

#### Inference
- **`run(inputs: dict[str, np.ndarray], model_key: str) -> dict[str, np.ndarray]`**
  - Executes single forward pass
  - **Returns**: `{output_name: np.ndarray}` dict
  - Input tensor names are auto-remapped if needed (see CpuBackend._remap_inputs)

#### VRAM Management
- **`available_vram_mb() -> int`**: Returns free VRAM (0 for CPU)
- **`warmup(model_key: str, input_shape: tuple[int, ...]) -> None`**: JIT primer pass

### CpuBackend Implementation

**File**: `hipixel_core/backends/cpu.py` (lines 41-164)

Uses **ONNX Runtime** with CPU Execution Provider.

#### Key Features
- **Input name remapping** (_remap_inputs, lines 21-38):
  - Community ONNX models may use arbitrary input names ("x", "lq", "input.1", etc.)
  - If caller provides `{"input": tensor}` but model expects `"lq"`:
    - Tensors are re-bound by **position** (first tensor → first input, etc.)
  - This allows filters to always use `{"input": img}` regardless of actual model names

- **Session management**: Stores `dict[str, ort.InferenceSession]`

---

## 4. TILE-BASED INFERENCE PATTERN

### RealESRGANFilter Tile Implementation

**File**: `hipixel_core/filters/real_esrgan.py` (lines 156-198)

This is the reference pattern for handling large frames.

```python
def _tile_infer(self, img: np.ndarray, backend: InferenceBackend) -> np.ndarray:
    """
    1. Split img into overlapping tiles
    2. Run inference on each tile
    3. Stitch results with weighted averaging (no seams)
    """
    h, w = img.shape[:2]
    tile = self._tile_size        # e.g. 512
    pad = self._tile_padding      # e.g. 32 (overlap region)
    scale = self._scale           # 2 or 4

    out_h, out_w = h * scale, w * scale
    output = np.zeros((out_h, out_w, 3), dtype=np.float32)
    weight = np.zeros((out_h, out_w, 1), dtype=np.float32)

    for y in range(0, h, tile):
        for x in range(0, w, tile):
            # Padded bounds (clamped to image)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + tile + pad)
            y2 = min(h, y + tile + pad)

            # Extract tile with padding
            patch = img[y1:y2, x1:x2]           # (ph, pw, 3) HWC
            patch_t = np.transpose(patch, (2, 0, 1))[np.newaxis]  # NCHW: (1, 3, ph, pw)

            # Inference
            result = backend.run({"input": patch_t}, self._model_key)
            out_patch = result.get("output", next(iter(result.values())))
            out_patch = np.transpose(out_patch[0], (1, 2, 0))  # HWC: (ph*scale, pw*scale, 3)

            # Accumulate to output with weights
            ox1, oy1 = x1 * scale, y1 * scale
            ox2, oy2 = x2 * scale, y2 * scale
            output[oy1:oy2, ox1:ox2] += out_patch
            weight[oy1:oy2, ox1:ox2] += 1.0

    # Normalize overlapping regions
    output = output / np.maximum(weight, 1.0)
    return np.clip(output, 0.0, 1.0).astype(np.float32)
```

#### Key Points
- **NCHW format**: backend.run() expects (1, 3, H, W) tensors
- **Transpose pattern**: `HWC → NCHW` on input, `NCHW → HWC` on output
- **Weighted averaging**: Overlapping regions are averaged to eliminate tile seams
- **Output scaling**: For 2x scale, output dimensions = input × 2
- **Clipping**: Final output clipped to [0, 1] range

#### Auto Tile Sizing

RealESRGANFilter._auto_tile_size (lines 116-150):
- Uses 50% of available VRAM as budget
- Accounts for: input tile + scaled output + 4× activation overhead
- Result clamped to [64, 1024] and rounded to 64-pixel boundary
- CPU backend (vram=0) returns safe default of 256

---

## 5. MODEL REGISTRY SYSTEM

### Registry File

**Path**: `hipixel_core/models/registry.json` (76 lines)

```json
{
  "version": "1",
  "models": {
    "Anime4K_v4_Upscale_Denoise_x2": {
      "filename": "Anime4K_v4_Upscale_Denoise_x2.onnx",
      "url": "https://github.com/bloc97/Anime4K/releases/download/v4.0.1/...",
      "mirrors": [],
      "sha256": "",
      "size_bytes": 0,
      "scale": 2,
      "type": "anime_superresolution",
      "description": "Anime4K v4 — 2× upscale + denoising for cel-shaded content",
      "version": "4.0.1"
    },
    ...
  }
}
```

#### Anime4K Registry Entries

**Primary**: `Anime4K_v4_Upscale_Denoise_x2`
- Scale: 2
- Type: `anime_superresolution`
- URL: GitHub releases v4.0.1 zip
- Size unknown (0 bytes) — no hash check

**Note**: Only 2x variant in registry. 4x variants may need to be added.

### ModelManager API

**File**: `hipixel_core/models/manager.py` (lines 46-228)

```python
class ModelManager:
    @classmethod
    def get_model_path(cls, model_name: str, auto_download: bool = True) -> str:
        """
        Returns path to model file, downloading if needed.
        Cache location: ~/.cache/hipixel-core/models/
        """
    
    @classmethod
    def download(cls, model_name: str, force: bool = False) -> Path:
        """Explicitly download a model."""
    
    @classmethod
    def list_registry(cls) -> list[dict[str, Any]]:
        """Get all model entries from registry.json."""
    
    @classmethod
    def list_cached(cls) -> list[str]:
        """Get names of models currently cached on disk."""
```

#### Usage Pattern (from NAFNetFilter.setup)

```python
from hipixel_core.models.manager import ModelManager

model_path = ModelManager.get_model_path("Anime4K_v4_Upscale_Denoise_x2")
backend.load_model(model_path, "anime4k_model")
```

---

## 6. EXISTING FILTER IMPLEMENTATIONS

### NAFNetFilter (Reference for ONNX Pattern)

**File**: `hipixel_core/filters/nafnet.py` (lines 23-92)

```python
class NAFNetFilter:
    name: str = "nafnet"
    
    def __init__(self) -> None:
        self._model_key: str = ""
        self._strength: float = 0.8
        self._tile_size: int = 256

    @property
    def required_models(self) -> list[str]:
        return [self._model_key] if self._model_key else ["NAFNet-REDS-width64"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        self._strength = float(params.get("strength", 0.8))
        model_name: str = str(params.get("model", "NAFNet-REDS-width64"))
        self._tile_size = int(params.get("tile_size", 256))
        self._model_key = f"nafnet_{model_name}"
        
        model_path = ModelManager.get_model_path(model_name)
        backend.load_model(model_path, self._model_key)

    def teardown(self, backend: InferenceBackend) -> None:
        if self._model_key:
            backend.unload_model(self._model_key)

    def process_frame(self, frame: VideoFrame, backend: InferenceBackend, params: FilterParams) -> VideoFrame:
        f32 = frame.to_float32()
        img = np.transpose(f32.data, (2, 0, 1))[np.newaxis]  # HWC → NCHW
        result = backend.run({"input": img}, self._model_key)
        denoised = next(iter(result.values()))  # Get first output
        denoised = np.clip(np.transpose(denoised[0], (1, 2, 0)), 0.0, 1.0).astype(np.float32)
        
        # Blend with original
        strength = float(params.get("strength", self._strength))
        blended = (1.0 - strength) * f32.data + strength * denoised
        
        return VideoFrame(
            data=np.clip(blended, 0.0, 1.0).astype(np.float32),
            pts=frame.pts,
            width=frame.width,
            height=frame.height,
            colorspace=frame.colorspace,
            is_hdr=frame.is_hdr,
            hdr_metadata=frame.hdr_metadata,
        )

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        w, h = input_resolution
        mp = w * h / 1_000_000
        return int(mp * 192)  # 192 MB per megapixel
```

**Key Pattern**:
- Simple ONNX pass-through (no tiling)
- Strength blending for user control
- VRAM estimate based on megapixels

### Anime4KFilter (Current Stub)

**File**: `hipixel_core/filters/anime4k.py` (lines 24-86)

```python
class Anime4KFilter:
    name: str = "anime4k"

    def __init__(self) -> None:
        self._model_key: str = ""
        self._scale: int = 2
        self._tile_size: int = 512

    @property
    def required_models(self) -> list[str]:
        return [self._model_key] if self._model_key else ["Anime4K_v4_Upscale_Denoise_x2"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        self._scale = int(params.get("scale", 2))
        model_name: str = str(params.get("model", "Anime4K_v4_Upscale_Denoise_x2"))
        self._tile_size = int(params.get("tile_size", 512))
        self._model_key = f"anime4k_{model_name}"
        
        from hipixel_core.models.manager import ModelManager
        model_path = ModelManager.get_model_path(model_name)
        backend.load_model(model_path, self._model_key)

    def teardown(self, backend: InferenceBackend) -> None:
        if self._model_key:
            backend.unload_model(self._model_key)

    def process_frame(self, frame: VideoFrame, backend: InferenceBackend, params: FilterParams) -> VideoFrame:
        f32 = frame.to_float32()
        img = np.transpose(f32.data, (2, 0, 1))[np.newaxis]  # HWC → NCHW
        result = backend.run({"input": img}, self._model_key)
        out = next(iter(result.values()))  # (1, 3, H*s, W*s)
        out = np.clip(np.transpose(out[0], (1, 2, 0)), 0.0, 1.0).astype(np.float32)
        return VideoFrame(
            data=out,
            pts=frame.pts,
            width=out.shape[1],
            height=out.shape[0],
            colorspace=frame.colorspace,
            is_hdr=frame.is_hdr,
            hdr_metadata=frame.hdr_metadata,
        )

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        w, h = input_resolution
        mp = w * h / 1_000_000
        return int(mp * 256)  # Lighter than Real-ESRGAN

    def __repr__(self) -> str:
        return f"Anime4KFilter(scale={self._scale}, model_key={self._model_key!r})"
```

**Status**: ✓ COMPLETE — Already implements full protocol correctly!

**Issue**: Does NOT implement tile-based inference. For large frames, this will cause OOM errors. Should adopt RealESRGANFilter's `_tile_infer` pattern.

### CASFilter (CPU-Only Reference)

**File**: `hipixel_core/filters/cas.py` (lines 24-97)

- CPU-only sharpening (no models)
- `required_models` returns empty list `[]`
- VRAM estimate: 0 MB
- Unsharp mask + adaptive gain algorithm

---

## 7. TEST PATTERNS

**Files**: 
- `tests/test_inference_e2e.py` (795 lines)
- `tests/test_filters.py` (113 lines)

### Synthetic ONNX Model Builder

**Function**: `_make_identity_onnx()` (lines 59-107)

Creates a minimal Identity ONNX model from raw protobuf bytes without requiring the `onnx` package:
```python
def _make_identity_onnx(
    input_name: str = "input",
    output_name: str = "output",
) -> bytes:
    """Return raw bytes of a minimal ONNX Identity model."""
```

This allows testing without downloading real models.

### Test Frame Helpers

```python
def _synth_frame(w: int = 64, h: int = 48) -> VideoFrame:
    """Reproducible random uint8 frame (seed=42)."""

def _uniform_frame(w: int = 64, h: int = 48, value: float = 0.5) -> VideoFrame:
    """Uniform float32 frame (useful for tile-seam checks)."""

def _create_test_video(path: Path, w: int = 64, h: int = 48, frames: int = 5, fps: int = 25) -> None:
    """Create synthetic video with FFmpeg lavfi testsrc."""
```

### Filter Test Classes

1. **TestNAFNetSingleFrame** (lines 303-390)
   - `_setup()`: Initialize NAFNetFilter with mocked ModelManager
   - Tests: dimensions, strength blending, dtype, range, PTS preservation

2. **TestRealESRGANSingleFrame** (lines 397-495)
   - Tests: scale=1 identity model, tile stitching (no seams)
   - Tests: tile-seam validation with uniform frames

3. **TestDynamicTileSize** (lines 708-794)
   - Tests `_auto_tile_size()` logic
   - VRAM-dependent tile sizing

4. **TestPipelineCASEndToEnd** / **TestPipelineNAFNetEndToEnd** (lines 502-701)
   - Full decode → filter → encode pipeline
   - Uses `@pytest.mark.slow` and skips if FFmpeg unavailable

### Mocking Pattern

```python
with mock.patch(
    "hipixel_core.models.manager.ModelManager.get_model_path",
    return_value=str(p),  # Return path to synthetic model
):
    f.setup(be, params)
```

---

## 8. FILTER REGISTRY

**File**: `hipixel_core/filters/__init__.py` (lines 1-49)

```python
FILTER_REGISTRY: dict[str, type[object]] = {
    "real_esrgan": RealESRGANFilter,
    "anime4k": Anime4KFilter,
    "nafnet": NAFNetFilter,
    "cas": CASFilter,
    "rife": RIFEFilter,
}

def get_filter(name: str) -> object:
    """Instantiate a filter by its registry name."""
```

Anime4K is already registered ✓

---

## 9. MAIN EXPORTS

**File**: `hipixel_core/__init__.py` (33 lines)

Exports:
- `ColorSpace`, `DeviceInfo`, `OutputSpec`, `PipelineResult`, `ProgressEvent`, `VideoFrame`, `VideoMeta`

Does NOT export filters directly (filters accessed via `hipixel_core.filters` package).

---

## SUMMARY TABLE

| Component | Status | File | Notes |
|-----------|--------|------|-------|
| Filter Protocol | ✓ Complete | base.py | Formal Protocol with @runtime_checkable |
| Anime4KFilter impl | ✓ Complete | anime4k.py | Full protocol, no tiling (potential OOM) |
| NAFNetFilter | ✓ Complete | nafnet.py | Reference for ONNX pattern, no tiling |
| RealESRGANFilter | ✓ Complete | real_esrgan.py | Reference for tile-based inference |
| CASFilter | ✓ Complete | cas.py | CPU-only reference |
| Backend Protocol | ✓ Complete | backends/base.py | InferenceBackend protocol |
| CpuBackend | ✓ Complete | backends/cpu.py | ONNX Runtime + input remapping |
| VideoFrame types | ✓ Complete | types.py | HWC, uint8/float32 support |
| ModelManager | ✓ Complete | models/manager.py | Download/cache with registry lookup |
| Model Registry | ⚠ Partial | registry.json | Anime4K 2x present, no 4x variants |
| Tests | ✓ Complete | test_inference_e2e.py | Synthetic ONNX + tile-seam validation |
| Filter Registry | ✓ Complete | filters/__init__.py | Anime4K registered |

---

## RECOMMENDATIONS FOR PRODUCTION ANIME4K

1. **ADD TILE-BASED INFERENCE** to Anime4KFilter (adopt RealESRGANFilter._tile_infer pattern)
   - Current naive implementation will OOM on large frames
   - Tile size: 512 pixels (good default for anime)
   - Padding: 32 pixels (overlap region)

2. **ADD ANIME4K 4X VARIANT** to registry.json
   - Check bloc97/Anime4K releases for v4 4x model
   - Follow same registration pattern

3. **ADD TEST CASE** for Anime4K tile inference
   - Reuse `_make_identity_onnx()` pattern
   - Validate no seams with uniform frames (like RealESRGAN tests)

4. **OPTIONAL**: Add strength parameter like NAFNetFilter for blending

5. **VERIFY MODEL I/O NAMES**
   - Anime4K may use different input/output names
   - Backend auto-remapping should handle it, but verify in tests

