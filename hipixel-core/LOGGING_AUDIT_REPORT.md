# hipixel-core Logging & Output System Audit

**Date:** 2026-05-30  
**Scope:** Complete codebase analysis at `/Users/hikari/Documents/Git/HiVideo/hipixel-core/`  
**Status:** Ready for logging system design

---

## Executive Summary

The hipixel-core codebase currently **has NO logging system** — all output is:
- **Console-based** via Rich (`console.print()`, `err_console.print()`) in `cli.py` only
- **Error handling** via exceptions with silent failures in core modules
- **Diagnostic info** either missing or scattered across backends/models/filters

### Quick Stats
- **Total Python files:** 30 (hipixel_core + tests)
- **Console output calls:** 32 (all in `cli.py`)
- **Logging imports:** 0 (no `import logging` anywhere)
- **Error handling:** 35+ `raise` statements, mostly generic exceptions
- **Progress tracking:** Only in `cli.py` via Rich Progress bars

---

## 1. CONSOLE OUTPUT & PRINT STATEMENTS

### 1.1 CLI Layer (`hipixel_core/cli.py`) — 32 console.print() calls

**Lines with console output:**

| Line | Type | Content | Context |
|------|------|---------|---------|
| 49 | Init | `console = Console()` | Main Rich console object |
| 50 | Init | `err_console = Console(stderr=True, style="bold red")` | Error console (stderr) |
| 118 | Error | Input file not found | `enhance` command |
| 123 | Error | --preset and --filter mutually exclusive | Validation |
| 127 | Error | Specify --preset or at least one --filter | Validation |
| 130 | Header | `console.rule("[bold cyan]hipixel-core[/bold cyan]")` | CLI banner |
| 132 | Status | `with console.status("[bold]Probing input file…")` | Context manager |
| 135-140 | Info | Input metadata (resolution, fps, frames) | Post-probe |
| 145 | Info | Preset name | After loading |
| 152 | Info | Filter names | After composing |
| 162 | Info | Dry run complete message | Dry-run exit |
| 166 | Status | Selecting inference backend | Context manager |
| 170-173 | Info | Backend info (name, device) | Post-init |
| 186 | Progress | Rich Progress bar during enhance | Main processing loop |
| 209-215 | Success | Result summary (frames, time, fps) | Post-processing |
| 217 | Error | Processing failed message | Exception handler |
| 240 | Error | Input directory not found | `batch` command |
| 247 | Warning | No files matching glob | Empty input check |
| 250-252 | Info | Batch processing start info | Header |
| 257 | Progress | Per-file progress (i/total) | Loop |
| 276 | Success | Per-file success | Loop result |
| 279 | Error | Per-file error | Exception |
| 282 | Error | Per-file exception | Catch-all |
| 284-286 | Summary | Batch completion stats | Final summary |
| 311 | Info | Preset list table | `presets list` |
| 324 | Info | Preset details JSON | `presets show` |
| 351 | Info | Model registry table | `models list` |
| 366 | Success | Model cached message | `models download` |
| 378 | Success | Model removed message | `models remove` |
| 380 | Warning | Model not cached | `models remove` (not found) |
| 421 | Info | System info table | `info` |
| 476 | Error | Invalid resolution | `bench` command |
| 485-490 | Info | Benchmark configuration | Header |
| 512-517 | Progress + Info | Per-filter result | Loop |
| 530, 532, 553 | Output | Formatted results (JSON/Markdown/table) | `bench` output |
| 560 | Info | Report saved message | File export |

**Rich usage:**
- `Console()` for standard output (stdout)
- `Console(stderr=True, style="bold red")` for errors
- Rich markup: `[bold]`, `[cyan]`, `[green]`, `[red]`, `[yellow]`, `[dim]`, `[magenta]`, `[white]`
- **Progress bars:** `Progress`, `BarColumn`, `TaskProgressColumn`, `TimeElapsedColumn`, `TimeRemainingColumn`
- **Tables:** `Table` for structured output
- **Context managers:** `console.status()` for temporary status messages

### 1.2 Other modules — NO direct console output

**Checked:**
- ❌ `pipeline.py` — no print(), no console output (only exceptions)
- ❌ `backends/*.py` (cpu, cuda, coreml, selector, base) — no output
- ❌ `filters/*.py` (cas, nafnet, real_esrgan, aces, anime4k, rife, base) — no output
- ❌ `models/manager.py` — Rich Progress bar ONLY during download (lines 202-217), no direct prints
- ❌ `video/decoder.py` — no output (probe silently fails or succeeds)
- ❌ `video/encoder.py` — FFmpeg stderr suppressed (`-loglevel error`)
- ❌ `bench/runner.py` — no direct output (only data structures)
- ❌ `types.py`, `metrics.py`, `_fps_tracker.py` — no output

**Model download progress (in `models/manager.py:202-217`):**
```python
with Progress(
    "[bold blue]{task.description}",
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
) as progress:
    total = entry.get("size_bytes", 0) or None
    task = progress.add_task(f"Downloading {model_name}", total=total)
    # ... stream download with progress.update()
```

---

## 2. LOGGING MODULE USAGE

**Status:** ❌ **ZERO usage of Python's `logging` module**

No imports of:
- `import logging`
- `from logging import ...`
- `logging.getLogger()`
- `logging.basicConfig()`

**Result:** No persistent logs, no log levels (DEBUG, INFO, WARNING, ERROR), no log files, no structured logging.

---

## 3. ERROR HANDLING & EXCEPTION SURFACING

### 3.1 Exception Types Defined

**In `models/manager.py`:**
- `ModelNotFoundError` (line 38)
- `ModelIntegrityError` (line 42)

**Custom exceptions used but not defined in the codebase:**
- Generic `FileNotFoundError`, `ValueError`, `RuntimeError`, `KeyError`, `ImportError`

### 3.2 Error Handling Patterns

| Module | Error Type | Location | Handling |
|--------|-----------|----------|----------|
| **cli.py** | Input validation | Lines 118, 123, 127 | `err_console.print()` + `raise typer.Exit(1)` |
| **cli.py** | Backend init failure | Line 418-419 | Caught, displayed in table as "[red]error: {exc}[/red]" |
| **cli.py** | Batch file processing | Line 280-282 | Caught, printed as "[red]✗[/red]" + exception |
| **cli.py** | Benchmark resolution | Line 475-477 | Caught, `console.print()` + `raise typer.Exit(code=1)` |
| **pipeline.py** | Threading errors | Lines 181-182, 196-197, 197-198 | Exceptions accumulated in `errors` list, re-raised at line 242 |
| **backends/cpu.py** | Model not loaded | Lines 94-95, 134, 151 | Silent `RuntimeError`/`KeyError` (no console output) |
| **backends/cuda.py** | CUDA unavailable | Lines 58-68 | `ImportError` with helpful message |
| **backends/coreml.py** | CoreML unavailable | Lines 64-70 | `ImportError` with helpful message |
| **models/manager.py** | Model not found | Line 154-156 | `ModelNotFoundError` with list of available models |
| **models/manager.py** | Download failure | Line 187-189 | `RuntimeError` after trying all mirrors |
| **models/manager.py** | SHA256 mismatch | Lines 221-226 | `ModelIntegrityError` with hex digest preview |
| **video/decoder.py** | File not found | Line 39-40 | `FileNotFoundError` |
| **video/decoder.py** | No video stream | Line 64-65 | `ValueError` |
| **filters/*.py** | Model not loaded | e.g. nafnet.py | Silent `KeyError` from backend |

### 3.3 Silent Failures

**Exceptions raised but not caught at top level:**
1. Model loading errors in filters (`setup()` method)
2. Frame processing errors in filters (`process_frame()` method)
3. Backend initialization errors propagate to CLI only

**Exceptions caught silently:**
1. `backends/selector.py` lines 56-57: `except ImportError: return False` (probing)
2. `backends/cuda.py` line 134: `except Exception: return 0` (VRAM probing)
3. `backends/coreml.py` line 192: `except Exception: return 0` (sysctl probing)
4. `bench/runner.py` line X: `except Exception` during filter benchmarking

---

## 4. CLI STRUCTURE (`cli.py`)

### 4.1 Console Objects (lines 49-50)

```python
console = Console()                                    # stdout, normal style
err_console = Console(stderr=True, style="bold red")  # stderr, red styling
```

### 4.2 Typer App (lines 42-48)

```python
app = typer.Typer(
    name="hipixel-core",
    help="AI video enhancement engine — HiVideo / HiPixel",
    add_completion=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,  # Rich exception rendering
)
```

### 4.3 Verbosity/Quiet Flags

**Status:** ❌ **NO --verbose or --quiet flags implemented**

All commands use hard-coded output. No way to suppress or increase verbosity.

### 4.4 Progress Callbacks

**`enhance` command** (lines 177-195):
```python
with Progress(...) as progress:
    task = progress.add_task("[cyan]Enhancing…", total=meta.frame_count)
    
    def cb(event: ProgressEvent) -> None:
        progress.update(
            task,
            completed=event.frame_index,
            description=f"[cyan]{event.fps_avg:.1f} fps[/cyan] [dim]stage: {event.stage}[/dim]",
        )
    
    result = pipeline.run(..., progress_cb=cb)
```

**Progress event from `types.py`:**
```python
@dataclass
class ProgressEvent:
    frame_index: int
    total_frames: int
    elapsed_s: float
    fps_current: float
    fps_avg: float
    stage: str = "enhance"  # Dynamic stage name
```

---

## 5. PIPELINE STRUCTURE (`pipeline.py`)

### 5.1 What Gets Logged During a Run

**Logged (via progress callback to CLI only):**
- Current frame index (lines 221-228)
- Elapsed time
- Current/average FPS
- Stage name

**NOT logged:**
- Filter setup start/end
- Model loading progress
- VRAM usage
- Tile-based processing details
- Per-thread errors until final exception

### 5.2 3-Thread Architecture (lines 161-242)

Three daemon threads:
1. **decode_worker** (lines 177-184)
   - Decodes frames → `q_in`
   - Exceptions captured in `errors` list (line 182)
   
2. **process_worker** (lines 186-199)
   - Reads `q_in` → applies filters → writes `q_out`
   - Exceptions captured in `errors` list (line 197)
   
3. **encode_worker** (lines 201-229)
   - Reads `q_out` → encodes → writes to disk
   - **Progress callback triggered here** (lines 220-228)
   - Exceptions captured in `errors` list (line 197, not shown in this section)

**Sentinel:** `_EOS` object marks end-of-stream

**Queue depth:** `_QUEUE_DEPTH = 4` (default buffer between stages)

### 5.3 Error Aggregation

All thread exceptions collected in `errors` list, first one re-raised at line 242:
```python
if errors:
    raise errors[0]
```

**Problem:** Other thread errors are silently discarded (only first is raised).

---

## 6. BACKENDS DIAGNOSTIC OUTPUT (`backends/*.py`)

### 6.1 Backend Selector (`backends/selector.py`)

**Lines 30-70:** Platform probes (all silent, return boolean)
- `_is_apple_silicon()` — checks `sys.platform`, `platform.machine()`
- `_has_cuda_gpu()` — checks ONNX available providers
- `_is_windows_dml()` — checks `sys.platform`
- `_has_intel_gpu()` — tries to import openvino

**Lines 113-117:** Automatic backend selection (silent)
- No output during detection
- No output if no backend available (raises RuntimeError at line 119)

### 6.2 CPU Backend (`backends/cpu.py`)

**Diagnostic info:**
- `__repr__()` at line 161-163 shows `initialized` flag and loaded model keys
- No console output during:
  - `initialize()` (line 72-76)
  - `load_model()` (line 87-102)
  - `run()` (line 114-138)
  - `warmup()` (line 148-155)

**Error messages:**
- "Backend not initialized. Call initialize() first." (line 95)
- "Model '{model_key}' is not loaded." (line 134)

### 6.3 CUDA Backend (`backends/cuda.py`)

**Diagnostic methods:**
- `_probe_gpu_name()` (lines 149-157) — silent, returns string
- `_probe_total_vram_mb()` (lines 159-168) — silent, returns int
- `_probe_compute_capability()` (lines 170-179) — silent, returns string

**Error messages:**
- "onnxruntime-gpu is required for the CUDA backend..." (line 59-62)
- "CUDAExecutionProvider is not available..." (line 65-68)
- "Backend not initialized. Call initialize() first." (line 84-85)
- "Model '{model_key}' is not loaded." (line 116)

**VRAM probing** (lines 126-135):
- Silent exception handling: `except Exception: return 0`
- No fallback message if pynvml is missing

### 6.4 CoreML Backend (`backends/coreml.py`)

**Conversion & caching:**
- `_get_or_convert()` (lines 159-167) — silent ONNX→MLPackage conversion
- No progress bar or status for conversion (unlike model downloads)
- Cache file: `~/.cache/hipixel-core/coreml/{stem}_{hash}.mlpackage`

**Error messages:**
- "coremltools is required for the CoreML backend..." (line 66-70)

**VRAM probing** (lines 178-193):
- Silent `except Exception: return 0` (line 192)
- Uses `sysctl hw.memsize` on macOS

### 6.5 Device Info Output (from CLI only)

See `cli.py` line 418-419 for backend error display:
```python
table.add_row("Active backend", f"[red]error: {exc}[/red]")
```

---

## 7. FILTERS DIAGNOSTIC OUTPUT (`filters/*.py`)

### 7.1 Filter Base Protocol (`filters/base.py`)

**Lines 62-123:** Protocol defines these lifecycle methods but NO logging:
- `setup(backend, params)` — loads models
- `teardown(backend)` — unloads models
- `process_frame(frame, backend, params)` — processes frame
- `estimated_vram_mb(input_resolution)` — returns int

### 7.2 Per-Filter Implementation

#### CAS Filter (`filters/cas.py`)
- **Lines 44-48:** `setup()` — stores sharpness param (silent)
- **Lines 50-68:** `process_frame()` — applies sharpening (silent)
- **Line 97:** `__repr__()` — debug representation only
- **No diagnostic output**

#### NAFNet Filter (`filters/nafnet.py`)
- **Lines 44-53:** `setup()` — loads model from ModelManager (silent model loading)
- **Lines 59-83:** `process_frame()` — blends denoised output (silent)
- **Line 52:** `ModelManager.get_model_path()` returns path or downloads (rich progress bar)
- **No per-filter diagnostic output**

#### Real-ESRGAN Filter (`filters/real_esrgan.py`)
- **Lines 70-86:** `setup()` — calculates tile size from VRAM (silent)
- **Lines 92-109:** `process_frame()` — tile-based inference (silent)
- **Lines 116-130:** `_auto_tile_size()` — returns int silently
- **No diagnostic output of tile sizes, VRAM usage, or tiling strategy**

#### ACES Tone-Mapping Filter (`filters/aces.py`)
- **Lines 65-69:** `setup()` — stores parameters (silent)
- **Lines 74-100+:** `process_frame()` — applies tone mapping (silent)
- **No diagnostic output**

#### Anime4K Filter (`filters/anime4k.py`)
- Not reviewed in detail (not fully implemented)

#### RIFE Filter (`filters/rife.py`)
- **Lines ~20:** Raises `NotImplementedError("RIFE is not yet implemented (Phase 1).")`
- No diagnostic implementation

### 7.3 Filter Setup Errors

**Problem:** Model loading errors in `setup()` propagate directly to pipeline, but no context about:
- Which filter is being set up
- Which model is being loaded
- VRAM available vs. required
- Tile size calculations

---

## 8. MODEL MANAGER DIAGNOSTICS (`models/manager.py`)

### 8.1 Download Progress (lines 202-217)

**Only place in core code with Rich progress bar outside CLI:**
```python
with Progress(
    "[bold blue]{task.description}",
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
) as progress:
    total = entry.get("size_bytes", 0) or None
    task = progress.add_task(f"Downloading {model_name}", total=total)
    # ... download with progress.update(task, advance=len(chunk))
```

**Progress shown:**
- Download % complete
- Transfer speed
- ETA (from Rich)

### 8.2 Diagnostic Information Missing

**No logging of:**
- Cache hits (when model already exists)
- Cache directory used
- Model versions / update checks
- Size of cached models
- Mirror fallback attempts (exception silently caught at line 182)
- SHA256 verification details (only shown if mismatch at lines 221-226)

### 8.3 Error Messages

**ModelNotFoundError** (lines 154-156):
```python
raise ModelNotFoundError(
    f"Model '{model_name}' not found in registry. Available: {available}"
)
```
Lists all available models inline.

**ModelIntegrityError** (lines 221-226):
```python
raise ModelIntegrityError(
    f"SHA-256 mismatch for '{model_name}': "
    f"expected {expected[:16]}…, got {digest[:16]}…"
)
```

**RuntimeError on download failure** (lines 187-189):
```python
raise RuntimeError(
    f"Failed to download model '{model_name}' from all sources."
) from last_error
```
Chained from last exception, but mirror attempts not logged.

---

## 9. VIDEO I/O DIAGNOSTICS

### 9.1 Decoder (`video/decoder.py`)

**Probe function** (lines 26-99):
- Silent metadata extraction via `ffprobe`
- FFmpeg verbosity: `-v quiet` (line 45)
- No output on success
- Raises exceptions on failure

**Diagnostic info extracted but not logged:**
- Frame count estimation (lines 75-81)
- FPS parsing from `r_frame_rate` (line 73)
- Colorspace detection (line 94)
- HDR detection (line 95)
- Audio stream count (line 57, 62)

**Error messages:**
- "Video file not found: {path}" (line 40)
- "No video stream found in: {path}" (line 65)

### 9.2 Encoder (`video/encoder.py`)

**FFmpeg subprocess** (lines 56-100):
- Verbosity: `-loglevel error` (line 65)
- Only FFmpeg errors are shown to stderr
- No progress display (unlike decoder/encoder framework in Rust version)

**Error messages:** (not found in review)
- Likely from FFmpeg subprocess stderr

---

## 10. BENCHMARK DIAGNOSTICS (`bench/runner.py`)

### 10.1 Benchmark Result Collection

**BenchmarkResult** (lines 45-90):
- Collects: filter_name, resolution, frame_count, fps stats, backend/device info, timestamp
- Stores raw per-frame timings in `_frame_times_ms` (line 71)

### 10.2 Benchmark Output

**to_json()** (line 114-116):
```python
def to_json(self, indent: int = 2) -> str:
    return json.dumps(self.to_dict(), indent=indent)
```

**to_markdown()** (lines 118-150):
```python
# Renders as markdown table, optionally adds device/backend metadata
```

### 10.3 No Per-Run Diagnostics

**Missing logging during benchmark:**
- Frame processing latency details
- Any filtering/warmup steps
- Backend state before/after
- Outlier detection (e.g., GC pauses, context switches)

---

## 11. DEPENDENCIES & ENTRY POINTS (`pyproject.toml`)

### 11.1 Logging-Related Dependencies

**Status:** ❌ None

```toml
dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.7.0",           # Console output only
    "numpy>=1.26.0",
    "Pillow>=10.3.0",
    "scipy>=1.13.0",
    "ffmpeg-python>=0.2.0",
    "pydantic>=2.7.0",
    "httpx>=0.27.0",
    "onnxruntime>=1.18.0",
]
```

**Rich capabilities used:**
- Rich Console
- Rich Progress bars
- Rich Tables
- Rich markup

**NOT used from Rich:**
- Rich logging handler
- Rich file rotation
- Structured logging

### 11.2 Entry Point

```toml
[project.scripts]
hipixel-core = "hipixel_core.cli:app"
```

Only CLI app is exposed; core modules are not directly importable with logging.

---

## 12. GAPS & MISSING DIAGNOSTICS

### Critical Gaps

| Category | Gap | Impact |
|----------|-----|--------|
| **Logging** | No logging module at all | Can't debug runtime issues, no audit trail |
| **Per-filter diagnostics** | No logging in `setup()`, `process_frame()`, `teardown()` | Can't identify which filter fails |
| **Model loading** | No visibility into model download, conversion, or loading | User doesn't know why setup is slow |
| **VRAM tracking** | Backend reports available VRAM but it's never logged | Can't diagnose OOM or tile size decisions |
| **Tile-based processing** | Real-ESRGAN tiles are computed silently | No visibility into tile count, overlap, performance |
| **Threading errors** | Only first thread error is raised; others discarded | Silent failures in decode/encode threads |
| **Backend initialization** | No step-by-step logging of driver setup, compilation | Opaque CoreML ONNX→MLPackage conversion timing |
| **Progress granularity** | Progress only from encoder thread, not from decoders/processing | Pipeline bottleneck not visible |
| **Verbosity control** | No `--verbose` or `--quiet` flags | All output is hard-coded |
| **Structured output** | No machine-readable diagnostics (only human-readable console) | Hard to parse for monitoring/CI |

### Nice-to-Have Diagnostics

| Feature | Example |
|---------|---------|
| **Cache statistics** | "Model cache: 512 MB used, 3 models cached" |
| **Backend selection reasoning** | "Selected CUDA (NVIDIA RTX 4090) over CPU" |
| **Filter performance** | "nafnet: 23ms/frame @ 1280x720 (strength=0.8)" |
| **Memory usage timeline** | "Peak VRAM: 2048 MB (tile 1/8)" |
| **FFmpeg integration logs** | "ffmpeg: decoded 1200/1200 frames" |
| **Preset expansion** | "Preset 'old-film-revival' → [nafnet, cas, aces]" |

---

## 13. SUMMARY TABLE

| Component | Print() Calls | Logging Module | Error Handling | Progress Tracking |
|-----------|---------------|-----------------|-----------------|-------------------|
| **cli.py** | 32 (Rich console) | None | Manual + typer.Exit | Rich Progress bar |
| **pipeline.py** | 0 | None | Exception aggregation | Via callback to CLI |
| **backends/** | 0 | None | Silent probes + exceptions | None |
| **filters/** | 0 | None | Exceptions in setup/process | None |
| **models/manager.py** | 0 | None | 3 custom exceptions | Rich Progress (download only) |
| **video/i o** | 0 | None | Exceptions | None |
| **bench/** | 0 | None | Silently caught | None |

---

## 14. RECOMMENDATIONS FOR LOGGING SYSTEM DESIGN

1. **Adopt Python's `logging` module:**
   - Create module-level loggers for each component
   - Support DEBUG, INFO, WARNING, ERROR, CRITICAL levels
   - Enable --verbose/-v (DEBUG), --quiet/-q (WARNING) flags in CLI

2. **Structured logging:**
   - Consider `structlog` or Rich's built-in logging handler for JSON output
   - Include context: filter name, model name, resolution, VRAM, FPS

3. **Per-layer logging:**
   - **Backend:** Model loading, device init, VRAM probes, warmup
   - **Filters:** Setup start/end, per-frame processing times, tile strategy
   - **Pipeline:** Thread lifecycle, queue depth, FPS checkpoints
   - **Models:** Cache hits, downloads, conversions, integrity checks
   - **Video I/O:** Probe results, encode parameters, frame count

4. **Progress events:** Extend `ProgressEvent` to include:
   - Current filter name
   - VRAM used
   - Frame decode/process/encode times
   - Exception context if error occurs

5. **Log file output:** Default to `~/.cache/hipixel-core/logs/` with rotation

6. **Error context:** Include backtrace, model path, frame dimensions, backend state in exceptions

---

## Files Analyzed

```
hipixel_core/
  __init__.py
  cli.py                    ← 32 console.print() calls
  pipeline.py               ← 0 output, exception aggregation
  types.py                  ← Data models
  metrics.py                ← Metrics computation
  _fps_tracker.py           ← FPS tracking utility
  backends/
    __init__.py
    base.py                 ← Protocol definition
    selector.py             ← 0 output, silent probes
    cpu.py                  ← 0 output
    cuda.py                 ← 0 output, silent VRAM probes
    coreml.py               ← 0 output, silent conversion
  filters/
    __init__.py
    base.py                 ← Protocol definition
    cas.py                  ← 0 output
    nafnet.py               ← 0 output, silent model load
    real_esrgan.py          ← 0 output, silent tile calculation
    aces.py                 ← 0 output
    anime4k.py              ← Not reviewed
    rife.py                 ← NotImplementedError
  models/
    __init__.py
    manager.py              ← Rich Progress for downloads only
    registry.json           ← Model metadata
  video/
    __init__.py
    decoder.py              ← 0 output, silent probe
    encoder.py              ← FFmpeg stderr suppressed
  bench/
    __init__.py
    runner.py               ← 0 output, data collection only
    synthetic.py            ← Test frame generation
  presets/
    __init__.py
    manager.py              ← Preset loading
```

---

**Report compiled:** 2026-05-30  
**Next step:** Design and implement logging architecture
