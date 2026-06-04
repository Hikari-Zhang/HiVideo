# hipixel-core Logging System — Quick Reference

## Current State: ❌ **NO LOGGING**

| Aspect | Status | Details |
|--------|--------|---------|
| **Python logging module** | ❌ Not used | 0 imports of `logging` anywhere |
| **Console output** | ✓ Rich only | 32 calls to `console.print()` in `cli.py` only |
| **Progress tracking** | Partial | Rich Progress bars in CLI + model downloads only |
| **Error handling** | Ad-hoc | ~35 exception types, some caught silently |
| **Log files** | ❌ None | No persistent audit trail |
| **Verbosity flags** | ❌ Missing | No `--verbose` or `--quiet` options |
| **Structured output** | ❌ None | Human-readable only (no JSON logs) |

---

## Key Findings by Component

### 1. CLI Layer (`cli.py`) — Only place with output
- **32 `console.print()` calls** (all in `cli.py`)
- Uses **Rich** for formatting (colors, tables, progress bars)
- Two console objects: `console` (stdout) + `err_console` (stderr)
- **No verbosity control** — all output hard-coded
- **Progress callback** from pipeline passes FPS/frame count to Progress bar

### 2. Core Modules — Silent by Design
- **`pipeline.py`**: No output. Exceptions aggregated, first re-raised
- **`backends/*.py`**: No output during init/model load. Silent VRAM probes
- **`filters/*.py`**: No output. Model loading errors propagate as exceptions
- **`models/manager.py`**: Rich Progress bar ONLY for downloads, not caching
- **`video/*.py`**: Silent. FFmpeg stderr suppressed with `-loglevel error`

### 3. Biggest Gaps
1. **No visibility into filter execution** — can't see which filter fails or how long each takes
2. **Silent tile calculations** — Real-ESRGAN computes tile strategy without logging it
3. **Model loading opacity** — No logging of ONNX→CoreML conversions or cache hits
4. **Threading errors** — Only first thread error shown; others discarded silently
5. **No backend selection reasoning** — Auto-detection happens silently
6. **No VRAM tracking** — Probed but never logged

---

## Recommended Logging Architecture

### Level 1: Core Logging (Essential)
```python
# Add to each module:
import logging
logger = logging.getLogger(__name__)

# Key log points:
logger.info(f"Filter {name} setup: {model_name}")
logger.debug(f"Tile size: {tile_size} (VRAM: {available_mb} MB)")
logger.error(f"Filter failed: {exc}")
```

### Level 2: Verbosity Control (CLI)
```bash
hipixel-core enhance input.mp4 -o out.mp4 --verbose      # DEBUG level
hipixel-core enhance input.mp4 -o out.mp4                # INFO level (default)
hipixel-core enhance input.mp4 -o out.mp4 --quiet        # WARNING level
```

### Level 3: Structured Output (Monitoring)
```bash
hipixel-core enhance input.mp4 -o out.mp4 --log-format json
# Output: {"timestamp": "...", "level": "INFO", "component": "pipeline", "message": "..."}
```

---

## File Locations of Output

| File | Output Type | Count | Notes |
|------|-------------|-------|-------|
| `cli.py` | console.print() | 32 | Main output point |
| `cli.py` | Rich Progress | 5 | Progress bars in commands |
| `models/manager.py` | Rich Progress | 1 | Model download progress |
| All others | (silent) | 0 | No output at all |

---

## Exception Handling Overview

### Raised (to propagate up):
- `ModelNotFoundError`, `ModelIntegrityError` (models)
- `FileNotFoundError`, `ValueError` (video I/O)
- `RuntimeError`, `KeyError` (backends)
- `ImportError` (missing dependencies)

### Caught & Displayed (CLI only):
- Input file not found
- Backend initialization errors
- Batch file processing errors
- Model download errors

### Caught & Silently Ignored:
- Platform probe failures (backends/selector.py)
- VRAM queries on unsupported systems (backends/cuda.py, coreml.py)
- Benchmark filter execution errors (bench/runner.py)

---

## Design Constraints

1. **No output in core modules** — maintain library usability
2. **CLI controls verbosity** — not individual components
3. **Rich integration** — already a dependency, leverage it
4. **Backward compatible** — don't break existing error messages
5. **Low overhead** — logging shouldn't slow down per-frame processing

---

## Next Steps for Implementation

1. **Create `hipixel_core/logging.py`** — central logging configuration
2. **Add module loggers** to:
   - `backends/__init__.py` (one logger per backend)
   - `filters/__init__.py` (one logger per filter)
   - `pipeline.py` (pipeline execution)
   - `models/manager.py` (model lifecycle)
   - `video/decoder.py`, `video/encoder.py` (video I/O)
   - `bench/runner.py` (benchmarking)
3. **Update CLI** (`cli.py`):
   - Add `--verbose`, `--quiet` flags
   - Set log level based on flags
   - Redirect logs to file if `--log-file` provided
4. **Update exceptions** — add backtrace + context
5. **Tests** — verify logging doesn't break functionality

---

**Full audit report:** `LOGGING_AUDIT_REPORT.md` (14 sections, 500+ lines)
