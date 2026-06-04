# Performance Tuning — hipixel-core

This document covers how to measure, interpret, and improve filter throughput
in hipixel-core.  It is updated as real hardware data becomes available.

---

## Table of Contents

1. [Benchmarking workflow](#1-benchmarking-workflow)
2. [Expected throughput targets](#2-expected-throughput-targets)
3. [Tile inference rationale](#3-tile-inference-rationale)
4. [Backend selection](#4-backend-selection)
5. [Per-filter tuning knobs](#5-per-filter-tuning-knobs)
6. [Pipeline threading model](#6-pipeline-threading-model)
7. [Real hardware comparison table](#7-real-hardware-comparison-table)
8. [Common bottlenecks and remedies](#8-common-bottlenecks-and-remedies)

---

## 1. Benchmarking workflow

### Quick CPU smoke test (CI-safe, no GPU or models required)

```bash
# Default: CAS at 1280×720, 30 frames
hipixel-core bench

# All CPU-capable filters
hipixel-core bench --all-filters

# Higher resolution, more frames for stable numbers
hipixel-core bench --all-filters --resolution 1080p --frames 120

# Save results for later comparison
hipixel-core bench --all-filters --output results/cpu-$(date +%Y%m%d).json
hipixel-core bench --all-filters --output results/cpu-$(date +%Y%m%d).md
```

### Python API

```python
from hipixel_core.backends.selector import select_backend
from hipixel_core.bench import BenchmarkRunner

backend = select_backend()
backend.initialize()

runner = BenchmarkRunner(backend)

# Single filter
result = runner.run_filter("cas", resolution="1280x720", frames=120)
print(f"{result.filter_name}  avg {result.avg_fps:.1f} fps  p95 {result.p95_ms:.2f} ms")

# All CPU-safe filters
report = runner.run_cpu_filters(resolution="1280x720", frames=60)
print(report.to_markdown())
report.save("results/bench.json")

backend.shutdown()
```

### Interpreting the numbers

| Column | Meaning |
|--------|---------|
| **FPS avg** | Mean frames-per-second across the timed run (higher = better) |
| **FPS min** | Worst single frame (useful for jitter analysis) |
| **FPS max** | Best single frame |
| **p50 ms** | Median frame latency in milliseconds |
| **p95 ms** | 95th-percentile latency — 5 % of frames were slower than this |

> **Note:** The benchmark measures only `process_frame` wall-clock time.
> Decode, encode, and I/O are excluded.  Real-world throughput in the
> full pipeline (`Pipeline.run`) will be lower due to those stages.

---

## 2. Expected throughput targets

These are *design targets* for Phase 0.  Columns marked ⏳ will be filled
with real measurements when the corresponding hardware run completes.

### CPU (pure NumPy, no ONNX)

| Filter | 720p target | 1080p target | Notes |
|--------|------------|-------------|-------|
| `cas` | ≥ 300 fps | ≥ 130 fps | Purely vectorised NumPy |
| `aces` | ≥ 250 fps | ≥ 110 fps | Piecewise NumPy, no model |

### Apple Silicon — CoreML (M1 / M2 / M2 Max)

| Filter | 720p target | 1080p target | 4K target |
|--------|------------|-------------|----------|
| `real_esrgan` (2×) | ≥ 15 fps | ≥ 6 fps | ⏳ |
| `real_esrgan` (4×) | ≥ 6 fps | ≥ 2 fps | ⏳ |
| `anime4k` | ≥ 20 fps | ≥ 8 fps | ⏳ |
| `nafnet` | ≥ 25 fps | ≥ 10 fps | ⏳ |
| `cas` | ≥ 600 fps | ≥ 280 fps | Runs on CPU even with CoreML backend |
| `aces` | ≥ 500 fps | ≥ 230 fps | CPU-only |

### NVIDIA CUDA (RTX 3080 / 4090 class)

| Filter | 720p target | 1080p target | 4K target |
|--------|------------|-------------|----------|
| `real_esrgan` (2×) | ≥ 30 fps | ≥ 12 fps | ⏳ |
| `real_esrgan` (4×) | ≥ 12 fps | ≥ 5 fps | ⏳ |
| `anime4k` | ≥ 45 fps | ≥ 20 fps | ⏳ |
| `nafnet` | ≥ 60 fps | ≥ 25 fps | ⏳ |

> Real measurements will be added to the [hardware comparison table](#7-real-hardware-comparison-table)
> once Phase 0.8 hardware runs are complete.

---

## ⚠️ Phase 0 已知性能限制

> 本节记录 v0.1.0-alpha 经过实测后暴露的性能现状，**不阻塞发布**，
> 将在 Phase 2.5 Rust 内核迁移时系统性解决。

### 测试环境

| 项目 | 值 |
|------|-----|
| 硬件 | Apple M4 Pro (48GB 统一内存) |
| OS | macOS 26.5 |
| Python | 3.12.13 |
| 后端 | CoreML EP + ANE/GPU |
| 测试素材 | 1920×1080 @ 23.98fps H.265 动漫 |

### CPU 滤镜实测（无模型）

| 滤镜 | 720p | 1080p | 4K | p50(1080p) |
|------|------|-------|-----|-----------|
| `cas` | 29.6 fps | **13.2 fps** | 3.1 fps | 75.75ms |
| `aces` | 76.4 fps | **33.0 fps** | 8.1 fps | 30.34ms |

> `cas` / `aces` 均为纯 NumPy，无 ONNX 模型，1080p 可用于非实时后处理。
> 4K 帧处理慢主要受制于 scipy `uniform_filter` 的 CPU 内存带宽；Phase 2.5
> 迁移 Metal 着色器后预计提升 10–20×。

### 神经网络滤镜实测（ANE via .mlpackage）

| 滤镜 | 模型 | 每 tile 耗时 | 1080p tile 数 | 实测 fps | 目标 fps | 差距 |
|------|------|------------|-------------|---------|---------|-----|
| `nafnet` | NAFNet-REDS-width64 (263MB) | ~27,000ms | 40 (256px) | **0.003** | ≥5 | ×1600 |
| `real_esrgan` | RealESRGAN_x4plus .mlpackage | ~1,690ms | 12 (512px) | **0.047** | ≥2 | ×43 |

### 根本原因分析

1. **NAFNet-REDS-width64** 是为离线图片修复设计的超大 U-Net（263MB），每个
   256px tile 需要 ~27 秒；整张 1080p 帧需 40 个 tile，远超视频处理需求。
   后续方案：引入 NAFNet-width16（~16MB，理论快 16×）。

2. **RealESRGAN .mlpackage** tile 推理已达 ~1.7s，是 CPU 路径（37s）的 22 倍，
   ANE 加速有效。但 1080p 需 12 个 tile，瓶颈转移到 tile 数量而非单 tile 速度。
   根因：Python ONNX 路径无法使用 CoreML EP（output shape rank 不匹配 bug），
   必须走 `.mlpackage` + coremltools；而整帧推理（1 tile）会 OOM。
   后续方案：Phase 2.5 改用 Metal MPSGraph 直接处理全帧，无需 tiling。

3. **CAS 是唯一实用的实时滤镜**（1080p 13.2fps），但无超分能力。

### 对 v0.1.0-alpha 发布的影响

- `sharpen-only`（CAS）和 `hdr-compatible`（ACES+CAS）预设可用于生产
- 其余预设（含 NAFNet / Real-ESRGAN）仅适合**离线批处理**，不适合实时观看
- CLI 功能完整，流水线架构经过验证，为 Phase 2.5 Rust 迁移提供清晰基线

---

## 3. Tile inference rationale

High-resolution frames (1080p, 4K) often exceed GPU VRAM limits when processed
as a single tensor.  hipixel-core splits frames into overlapping tiles before
passing them to ONNX models.

### How tiling works

```
┌─────────────────────────────────┐
│          1920×1080 frame        │
│  ┌────────┐  ┌────────┐        │
│  │ tile 0 │  │ tile 1 │  …     │  tile_size = 512, overlap = 16
│  └────────┘  └────────┘        │
│  ┌────────┐  ┌────────┐        │
│  │ tile 2 │  │ tile 3 │  …     │
│  └────────┘  └────────┘        │
└─────────────────────────────────┘
        ↓  run model per tile
        ↓  blend overlap regions (average)
┌─────────────────────────────────┐
│        reconstructed output     │
└─────────────────────────────────┘
```

### VRAM consumption per tile

For a 2× super-resolution model (e.g. Real-ESRGAN):

| Tile size | Input tensor | Output tensor | Approx VRAM |
|-----------|-------------|--------------|------------|
| 256×256 | 0.8 MB | 3.1 MB | ~200 MB |
| 512×512 | 3.1 MB | 12.6 MB | ~700 MB |
| 768×768 | 7.1 MB | 28.3 MB | ~1.5 GB |

The `tile_size` parameter trades VRAM for parallelism:

- **Smaller tiles** → lower peak VRAM, more tiles (more overhead per frame)
- **Larger tiles** → higher VRAM, fewer tiles (less overhead, better throughput)

### Dynamic tile sizing

`RealESRGANFilter` adjusts `tile_size` dynamically based on available VRAM:

```python
# Approximate heuristic (see filters/real_esrgan.py)
if available_vram_mb >= 8000:
    tile_size = 768
elif available_vram_mb >= 4000:
    tile_size = 512
else:
    tile_size = 256
```

Override via filter params:

```python
result = pipeline.run(
    source=meta, output_spec=spec, backend=backend,
    filter_params={"real_esrgan": {"tile_size": 512, "overlap": 16}},
)
```

---

## 4. Backend selection

```
Priority order (auto-selected):
  1. CoreML  — macOS 13+, Apple Silicon
  2. CUDA    — Linux/Windows, NVIDIA GPU, CUDA 11.8+
  3. CPU     — always available (fallback)
```

Force a specific backend:

```bash
hipixel-core bench --backend cpu
hipixel-core bench --backend coreml
hipixel-core bench --backend cuda
```

```python
from hipixel_core.backends.selector import select_backend
be = select_backend(force="cpu")
```

### Backend capabilities

| Backend | ONNX acceleration | CPU filters | Notes |
|---------|------------------|-------------|-------|
| `cpu` | ONNX CPU provider | ✅ | Always available; slowest for neural models |
| `coreml` | CoreML EP | ✅ | Requires `pip install hipixel-core[coreml]`; macOS only |
| `cuda` | CUDA EP + TensorRT | ✅ | Requires `pip install hipixel-core[cuda]`; Linux/Windows |

---

## 5. Per-filter tuning knobs

### CAS (`cas`)

| Param | Default | Range | Effect |
|-------|---------|-------|--------|
| `sharpness` | `0.5` | `0.0–1.0` | Higher = stronger sharpening; 0 = pass-through |

Throughput is essentially constant regardless of `sharpness` (same code path).

### ACES Tone-Mapping (`aces`)

| Param | Default | Options | Effect |
|-------|---------|---------|--------|
| `exposure` | `1.0` | `> 0.0` | Linear brightness multiplier before tone-mapping |
| `method` | `"aces_fitted"` | `"aces_fitted"`, `"reinhard"` | Tone-mapping curve |
| `gamma` | `"srgb"` | `"srgb"`, `"linear"` | Apply sRGB OETF to output |

`"aces_fitted"` (Narkowicz 2016) is slightly heavier than `"reinhard"` but
gives better highlight rolloff — prefer it for HDR→SDR delivery.

### Real-ESRGAN (`real_esrgan`)

| Param | Default | Notes |
|-------|---------|-------|
| `scale` | `2` | `2` or `4` — also selects the model variant |
| `tile_size` | auto | Override dynamic VRAM-based selection |
| `overlap` | `16` | Blend margin in pixels; reduce to 8 for speed |
| `denoise_strength` | `0.5` | 0 = no denoise; 1 = full Real-ESRGAN-denoise model |

### Anime4K (`anime4k`)

| Param | Default | Notes |
|-------|---------|-------|
| `scale` | `2` | `2` or `4` |
| `mode` | `"A"` | `"A"` (HQ)  `"B"` (fast)  `"C"` (ultra) |
| `denoise` | `True` | Enables coupled denoising pass |

### NAFNet Denoising (`nafnet`)

| Param | Default | Notes |
|-------|---------|-------|
| `strength` | `0.5` | Blend weight: 0 = original, 1 = fully denoised |
| `tile_size` | auto | VRAM-based; smaller for low-VRAM devices |

---

## 6. Pipeline threading model

```
Thread 1 (decode)   Thread 2 (infer)    Thread 3 (encode)
──────────────────  ──────────────────  ──────────────────
FFmpeg decode →     filter chain →      FFmpeg encode
frame_queue         output_queue
(maxsize=4)         (maxsize=4)
```

- **`frame_queue`** buffers decoded raw frames.  Increase if decode is faster
  than inference (rare).
- **`output_queue`** buffers processed frames waiting for the encoder.  The
  default depth of 4 is conservative — tuning beyond 8 rarely helps.

The pipeline stalls on the slowest stage.  Profile which thread is the
bottleneck before tuning queue sizes.

---

## 7. Real hardware comparison table

### CAS + ACES (CPU-only, pure NumPy — no model required)

**Apple M4 Pro · macOS 26.5 · Python 3.12.13 · 2026-06-04**

| Filter | Resolution | FPS avg | FPS min | FPS max | p50 ms | p95 ms |
|--------|------------|--------:|--------:|--------:|-------:|-------:|
| `cas`  | 1280×720   |   29.6  |   28.9  |   30.2  |  33.57 |  34.42 |
| `cas`  | 1920×1080  |   13.2  |   12.9  |   13.5  |  75.75 |  76.24 |
| `cas`  | 3840×2160  |    3.1  |    3.0  |    3.2  | 324.88 | 328.41 |
| `aces` | 1280×720   |   76.4  |   74.1  |   78.5  |  13.09 |  13.42 |
| `aces` | 1920×1080  |   33.0  |   32.1  |   33.7  |  30.34 |  30.85 |
| `aces` | 3840×2160  |    8.1  |    7.9  |    8.3  | 123.12 | 124.34 |

> `cas` 和 `aces` 为纯 NumPy 实现，无论何种后端均在 CPU 运行。

### Neural filters (Apple M4 Pro · CoreML ANE · .mlpackage — v0.1.0-alpha)

> ⚠️ 以下数据来自对真实动漫视频（1920×1080 H.265）的管道实测，
> 包含 tile 分割 + 推理 + 拼接的全部开销，非 `bench` 合成帧数据。

| Filter | Model | tile_size | Tiles/frame | FPS avg | Target | Status |
|--------|-------|----------:|------------:|--------:|-------:|--------|
| `nafnet` | NAFNet-REDS-width64 | 512px | 12 | **0.003** | ≥5 | ❌ 差 1600× |
| `real_esrgan` (4×) | RealESRGAN_x4plus .mlpackage | 512px | 12 | **0.047** | ≥2 | ❌ 差 43× |

详细根因见 [已知性能限制](#️-phase-0-已知性能限制)。

### Other platforms

> ⏳ Linux/CUDA 和 Windows/DirectML 数据待 Phase 0.8 硬件补测后填入。
>
> 贡献方法：
> ```bash
> hipixel-core bench --all-filters --resolution 1080p --frames 120 \
>     --output bench-$(hostname)-$(date +%Y%m%d).json
> ```
> 将 JSON 文件附到对应 GitHub Issue 或 PR。

---

## 8. Common bottlenecks and remedies

### "p95 latency is 3–5× p50" — high jitter

**Cause**: OS scheduler preemption or Python GIL contention during a long
NumPy operation.

**Remedy**:
- Increase `frames` in the benchmark run to 120+ to reduce noise.
- For model-based filters: check that ONNX is actually using the GPU EP,
  not falling back to CPU (`hipixel-core info`).

### "avg_fps drops 50% at 4K vs 1080p" (worse than expected quadratic)

**Cause**: Tiling overhead or model not using hardware batching.

**Remedy**:
- Increase `tile_size` if VRAM allows.
- Check model batch size (`batch_size=1` is the current default; batching is
  not yet implemented in Phase 0).

### "ACES/CAS FPS is low on a fast machine"

**Cause**: NumPy may fall back to a non-BLAS path if not compiled with OpenBLAS
or Accelerate.

**Remedy**:
```bash
python -c "import numpy as np; np.show_config()"
```
Look for `blas_opt_info` / `lapack_opt_info` entries.  Install `numpy` from
a wheel that bundles OpenBLAS:
```bash
pip install --upgrade numpy
```

### "CoreML backend slower than CPU for CAS"

This is expected.  `cas` and `aces` are pure-NumPy and run on the CPU
regardless of which backend is active.  The backend only accelerates ONNX
model inference.

---

*Last updated: 2026-06-04 — Phase 0 基准数据已写入（Apple M4 Pro），已知神经网络滤镜性能限制已记录，待 Phase 2.5 Rust 迁移解决。*
