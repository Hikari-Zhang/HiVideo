# hipixel-core Logging System Design Guide

**Status:** Audit Complete | Ready for Implementation  
**Date:** 2026-05-30  
**Deliverables:** 3 comprehensive documents + this guide

---

## 📋 What You Have

Three detailed analysis documents have been created:

### 1. **LOGGING_AUDIT_REPORT.md** (677 lines, 23 KB)
The authoritative deep-dive into the current system.

**Includes:**
- Executive summary of findings
- Section 1-11: Detailed analysis of each component
- Section 12: Comprehensive gap analysis (10 ranked items)
- Section 13: Summary table showing status across modules
- Section 14: Recommendations for design

**Read when:** Designing the logging architecture, making component-level decisions

**Key sections:**
- Section 1: All 32 console.print() calls documented with line numbers
- Section 3: Error handling patterns and silent failures cataloged
- Section 6-8: Backend, filter, and model diagnostics gaps
- Section 12: Critical gaps ranked by impact

---

### 2. **LOGGING_QUICK_REFERENCE.md** (133 lines, 4.8 KB)
One-page executive summary with lookup tables.

**Includes:**
- Current state status matrix
- Key findings by component
- Biggest gaps (ranked)
- Recommended architecture (3-level)
- File locations of all output
- Exception handling overview
- Design constraints
- Next steps for implementation

**Read when:** Quick lookup, making implementation decisions, stakeholder briefings

**Key tables:**
- Component status table
- Exception handling overview
- File locations of output (1 table)
- Implementation roadmap

---

### 3. **DIAGNOSTIC_SUMMARY.txt** (266 lines, 11 KB)
Ranked analysis of issues and design implications.

**Includes:**
- Critical findings (5 major categories)
- Component-by-component breakdown
- Ranked gap analysis (10 items)
- Design implications (5 key insights)
- Implementation roadmap (4 phases)
- File reference summary

**Read when:** Understanding design constraints, planning implementation phases, addressing stakeholders

---

## 🎯 Quick Facts

| Metric | Value |
|--------|-------|
| **Logging system exists?** | ❌ No |
| **Import of `logging` module** | 0 (zero) |
| **console.print() calls** | 32 (all in cli.py) |
| **Core modules with output** | 0 (intentionally silent) |
| **Custom exception types** | 3 |
| **Silent failures** | 4+ locations |
| **Error types** | 10+ standard + 3 custom |
| **Progress bars** | 2 locations (CLI, models) |
| **Verbosity flags** | ❌ 0 (missing) |
| **Log files** | ❌ 0 (missing) |

---

## 🔴 Critical Gaps (Do These First)

1. **No logging in filter execution** — Can't identify which filter fails
2. **Silent VRAM tracking** — Can't diagnose OOM or tile size issues
3. **Silent tile calculations** — No visibility into Real-ESRGAN strategy
4. **No verbosity control** — Can't suppress or redirect output
5. **Only first thread error shown** — Silent failures in decode/encode threads

---

## 📐 Design Recommendations

### Architecture (3-Level)

```python
# Level 1: Core Logging (Essential)
import logging
logger = logging.getLogger(__name__)
logger.info(f"Filter {name} setup: {model_name}")
logger.debug(f"Tile size: {tile_size} (VRAM: {available_mb})")

# Level 2: Verbosity Control (CLI)
# hipixel-core enhance input.mp4 -o out.mp4 --verbose    # DEBUG
# hipixel-core enhance input.mp4 -o out.mp4              # INFO (default)
# hipixel-core enhance input.mp4 -o out.mp4 --quiet      # WARNING

# Level 3: Structured Output (Monitoring)
# hipixel-core enhance input.mp4 --log-format json
```

### Key Principles

1. **Keep core modules silent** — Maintain library reusability
2. **CLI controls all output** — --verbose, --quiet, --log-file
3. **Leverage Rich** — Already a dependency, use for formatting
4. **Add context to errors** — Include backtrace, model path, dimensions
5. **Log critical events:**
   - Backend selection & initialization
   - Model loading start/end
   - Filter setup/teardown
   - Thread lifecycle events
   - Exception details with context

---

## 🛠️ Implementation Roadmap

### Phase 1: Core Logging (Week 1)
- Create `hipixel_core/logging.py`
- Add module loggers to backends, filters, pipeline, models, video I/O
- Implement key logging points

### Phase 2: CLI Integration (Week 1-2)
- Add `--verbose`, `--quiet`, `--log-file`, `--log-format` flags
- Configure logging from CLI
- Integrate with Rich console

### Phase 3: Extended Diagnostics (Week 2-3)
- Per-filter timing logs
- VRAM usage tracking
- Tile strategy logging
- All thread errors (not just first)

### Phase 4: Structured Output (Week 3-4)
- JSON format support
- Machine-readable logs
- CI/monitoring integration
- Log rotation/archival

---

## 📝 Files Referenced in Documents

### Audit Report Covers All These:

**Core:**
- `hipixel_core/cli.py` (32 print calls)
- `hipixel_core/pipeline.py` (threading, error aggregation)
- `hipixel_core/types.py` (data models)

**Backends (0 output each):**
- `hipixel_core/backends/base.py` (protocol)
- `hipixel_core/backends/selector.py` (auto-detection)
- `hipixel_core/backends/cpu.py`
- `hipixel_core/backends/cuda.py` (VRAM probes)
- `hipixel_core/backends/coreml.py` (ONNX→MLPackage conversion)

**Filters (0 output each):**
- `hipixel_core/filters/base.py` (protocol)
- `hipixel_core/filters/cas.py`
- `hipixel_core/filters/nafnet.py`
- `hipixel_core/filters/real_esrgan.py` (tile calculation)
- `hipixel_core/filters/aces.py`

**Infrastructure:**
- `hipixel_core/models/manager.py` (1 progress bar)
- `hipixel_core/video/decoder.py` (silent probe)
- `hipixel_core/video/encoder.py` (FFmpeg suppressed)
- `hipixel_core/bench/runner.py` (silent execution)

**Configuration:**
- `pyproject.toml` (dependencies, entry points)

---

## 🎓 Understanding the Findings

### Why is the codebase silent?

The design intentionally separates:
- **Library layer** (pipeline, backends, filters): Silent, exception-based
- **CLI layer** (cli.py): User-facing output, progress tracking

This is **good for reuse** (library users control their own output) but **bad for debugging** (no visibility into core operations).

### What gets logged today?

**Only in CLI (`cli.py`):**
- User input validation errors
- Backend selection results
- Pre/post-processing information
- Progress bars (using Rich)
- Batch processing results
- Benchmark output

**Everything else is silent:**
- Core pipeline execution
- Model loading
- Filter execution
- Frame processing
- VRAM allocation
- Thread coordination

### What's the biggest problem?

**Can't debug filter execution failures.**

When a filter fails during processing:
1. Exception bubbles up through pipeline
2. First thread error is shown, others are lost
3. No logging of which filter failed, where, why
4. No context about VRAM, frame size, tile size, etc.

### Why isn't CoreML conversion logged?

The conversion from ONNX to CoreML (lines 159-167 of `coreml.py`) is completely silent:
- Could take seconds on first use
- User has no way to know what's happening
- No progress indicator
- Errors would be cryptic

This is the **biggest hidden delay** in the codebase.

---

## 🚀 Next Steps

1. **Read the audit reports** (5-10 minutes each)
2. **Identify logging requirements** (which modules need which logs?)
3. **Design exception enhancement** (what context to include?)
4. **Implement Phase 1** (core logging module)
5. **Add module loggers** (backends, filters, pipeline)
6. **Update CLI** (add verbosity flags)
7. **Test end-to-end** (verify logging doesn't break performance)

---

## 📞 Questions This Audit Answers

- **Where does output come from?** → 32 calls in cli.py only
- **Why are core modules silent?** → Design choice for library reuse
- **Where are the biggest gaps?** → Filter execution, VRAM tracking, tile strategy
- **How many exceptions are there?** → 10+ standard types + 3 custom
- **Why are thread errors lost?** → Only first exception propagated
- **What about model loading?** → Silent. Only download progress shown.
- **How is VRAM tracked?** → Computed but never logged
- **Why no CoreML conversion logs?** → Completely silent
- **Can I suppress output?** → No (all output hard-coded)
- **Why verbosity flags missing?** → Never implemented

---

## 📚 Document Cross-References

When you need to know...

| Question | Read... |
|----------|---------|
| Where are all the console.print() calls? | Audit Report § 1.1 |
| What are all the exception types? | Audit Report § 3 |
| How does the pipeline work? | Audit Report § 5 |
| What's wrong with backends? | Audit Report § 6 |
| Why are filters silent? | Audit Report § 7 |
| How does model loading work? | Audit Report § 8 |
| What's the tile calculation doing? | Audit Report § 7.2 |
| What are the biggest gaps? | Audit Report § 12 |
| How should I implement logging? | Quick Reference § Recommended Architecture |
| What's the priority? | Diagnostic Summary § Biggest Gaps |
| How long will implementation take? | Diagnostic Summary § Recommended Next Steps |

---

## ✅ Validation Checklist

Before designing the logging system, verify you have:

- [ ] Read LOGGING_AUDIT_REPORT.md sections 1, 3, 12
- [ ] Read LOGGING_QUICK_REFERENCE.md fully
- [ ] Read DIAGNOSTIC_SUMMARY.txt fully
- [ ] Identified 5+ logging points in each component
- [ ] Understood the library vs CLI duality
- [ ] Understood threading error aggregation issue
- [ ] Understood CoreML conversion opacity
- [ ] Understood tile calculation gap
- [ ] Decided on verbosity level strategy
- [ ] Decided on log file location strategy

---

**Audit prepared by:** Comprehensive codebase analysis  
**Analysis date:** 2026-05-30  
**Audit files:** 3 documents (677 + 133 + 266 lines)  
**Ready for:** Implementation design phase

