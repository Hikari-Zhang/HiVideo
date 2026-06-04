# Quick Reference: Anime4K Implementation Guide

## Filter Protocol Checklist

Every Filter must implement:

- ✅ `name` property → `"anime4k"`
- ✅ `required_models` property → `["Anime4K_v4_Upscale_Denoise_x2"]`
- ✅ `setup(backend, params)` → Load model via `ModelManager.get_model_path()`
- ✅ `teardown(backend)` → Unload model via `backend.unload_model(key)`
- ✅ `process_frame(frame, backend, params)` → Return NEW VideoFrame
- ✅ `estimated_vram_mb(resolution)` → int (MB estimate)

## Frame Format

```
Input: VideoFrame
├─ data: np.ndarray (H, W, 3)
│  ├─ dtype: uint8 [0-255] OR float32 [0.0-1.0]
│  └─ Shape: Always 3D, channels last (HWC)
├─ pts: float (presentation timestamp)
├─ width, height: int
└─ colorspace, is_hdr, hdr_metadata

Output: NEW VideoFrame with:
├─ data: ALWAYS float32 [0.0-1.0]
├─ width, height: Updated for scale (e.g., 2x: 1920→3840)
└─ All metadata preserved
```

## Backend.run() Protocol

```python
# Input: dict with one or more named tensors
inputs = {"input": np.ndarray (N, C, H, W)}  # Note: NCHW format!

# Backend auto-remaps if model uses different names
# (e.g., if model expects "lq" instead of "input")

# Output: dict with named outputs
result = backend.run(inputs, model_key)
# result = {"output": np.ndarray (N, C, H, W)}

# To get first/any output:
out = result.get("output", next(iter(result.values())))
```

## Tensor Transpose Pattern

```python
# INPUT: VideoFrame with HWC data
frame.data  # shape: (H, W, 3), float32 [0,1]

# PREPARE FOR BACKEND (NCHW):
img = np.transpose(frame.data, (2, 0, 1))[np.newaxis]
# Result: (1, 3, H, W)

# AFTER BACKEND.RUN():
out = result["output"]  # (1, 3, H*scale, W*scale)
out = np.transpose(out[0], (1, 2, 0))  # Back to HWC
# Result: (H*scale, W*scale, 3)

# SAFETY:
out = np.clip(out, 0.0, 1.0).astype(np.float32)
```

## Tile-Based Inference (Pseudo-code)

```python
def _tile_infer(self, img, backend):
    """Handle large frames without OOM"""
    h, w = img.shape[:2]
    tile, pad = self._tile_size, self._tile_padding
    scale = self._scale
    
    output = np.zeros((h*scale, w*scale, 3), dtype=np.float32)
    weight = np.zeros((h*scale, w*scale, 1), dtype=np.float32)
    
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            # Get padded region (clamped to bounds)
            x1, x2 = max(0, x-pad), min(w, x+tile+pad)
            y1, y2 = max(0, y-pad), min(h, y+tile+pad)
            
            # Run inference on tile
            patch = img[y1:y2, x1:x2]
            patch_nchw = np.transpose(patch, (2,0,1))[np.newaxis]
            out_patch = backend.run({"input": patch_nchw}, key)["output"]
            out_patch = np.transpose(out_patch[0], (1,2,0))
            
            # Accumulate with weights
            ox1, ox2 = x1*scale, x2*scale
            oy1, oy2 = y1*scale, y2*scale
            output[oy1:oy2, ox1:ox2] += out_patch
            weight[oy1:oy2, ox1:ox2] += 1.0
    
    # Normalize overlaps (NO SEAMS!)
    return output / np.maximum(weight, 1.0)
```

## Model Registry Entry

```json
{
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
  }
}
```

## Test Pattern

```python
from tests.test_inference_e2e import _make_identity_onnx, _synth_frame, _uniform_frame
from unittest import mock

# Create synthetic ONNX model (no download needed)
p = tmp_path / "anime4k_stub.onnx"
p.write_bytes(_make_identity_onnx("input", "output"))

# Create backend
be = CpuBackend()
be.initialize()

# Create filter
f = Anime4KFilter()

# Mock model path
with mock.patch("hipixel_core.models.manager.ModelManager.get_model_path", return_value=str(p)):
    f.setup(be, {"scale": 2, "model": "Anime4K_v4_Upscale_Denoise_x2"})

# Test single frame
frame = _synth_frame(64, 48)
result = f.process_frame(frame, be, {})

# Validate tile stitching (uniform frame should stay uniform)
uniform = _uniform_frame(64, 48, value=0.5)
result_uniform = f.process_frame(uniform, be, {})
assert np.abs(result_uniform.to_float32().data - 0.5).max() < 1e-5

# Cleanup
f.teardown(be)
be.shutdown()
```

## Key Files

| Purpose | File | Lines |
|---------|------|-------|
| Filter Protocol | `hipixel_core/filters/base.py` | 26-138 |
| Anime4K impl | `hipixel_core/filters/anime4k.py` | 24-86 |
| Reference tile impl | `hipixel_core/filters/real_esrgan.py` | 156-198 |
| Backend protocol | `hipixel_core/backends/base.py` | 22-138 |
| CPU backend | `hipixel_core/backends/cpu.py` | 41-164 |
| Frame types | `hipixel_core/types.py` | 36-96 |
| Model manager | `hipixel_core/models/manager.py` | 46-228 |
| Model registry | `hipixel_core/models/registry.json` | all |
| Tests | `tests/test_inference_e2e.py` | 1-795 |

## Common Pitfalls

1. **Forgetting NCHW format** → Backend expects (batch, channels, height, width)
2. **Mutating input frame** → Must return NEW VideoFrame, never modify input
3. **Not clipping output** → Always `np.clip(out, 0.0, 1.0)`
4. **Large frame OOM** → Use tile-based inference (512px tiles)
5. **Input name mismatches** → Backend auto-remaps, but test with different names
6. **Forgetting cleanup** → Always call `teardown()` to free GPU memory
7. **Wrong dtype** → Output must be float32, input can be uint8 or float32

## Running Tests

```bash
# Single frame filter tests
pytest tests/test_filters.py::TestAnime4K -v

# End-to-end tile tests
pytest tests/test_inference_e2e.py::TestAnime4KSingleFrame -v

# Full pipeline test
pytest tests/test_inference_e2e.py::TestPipelineAnime4KEndToEnd -v --tb=short

# All tests
pytest tests/ -v
```

