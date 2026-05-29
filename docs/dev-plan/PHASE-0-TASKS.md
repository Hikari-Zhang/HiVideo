# 📋 HiVideo Project · Phase 0 Task Breakdown

## Overview
This document details all tasks for **Phase 0: hipixel-core Kernel Extraction** (~3 weeks) and **Phase 0.5: UI/UX Design** (~3 weeks, run in parallel).

Goal: Ship a working `hipixel-core enhance video.mp4 --preset old-film-revival -o output.mp4` CLI with solid performance baselines.

---

## Phase 0 · hipixel-core Kernel (Tasks 1-9)

### 0.1: Monorepo Setup ⚙️
**Owner**: Engineer (Infrastructure)  
**Duration**: 2-3 days  
**Deliverables**:
- [ ] Cargo workspace structure (core lib + CLI binary + tests)
- [ ] Python project setup (pyproject.toml with poetry)
- [ ] GitHub Actions CI matrix (macOS, Linux, Windows)
- [ ] README with development setup guide
- [ ] Makefile / build scripts (build.sh, test.sh, bench.sh)
- [ ] Logging infrastructure (tracing + log crates)

---

### 0.2: GPU Backend Abstraction 🎮
**Owner**: Engineer (GPU/Systems)  
**Duration**: 4-5 days  
**Blockers**: After 0.1 completes  
**Deliverables**:
- [ ] GPU backend trait definition
- [ ] CoreML backend implementation (primary on Apple Silicon)
- [ ] CUDA backend stub (interface only for Week 1)
- [ ] DirectML backend stub (interface only for Week 1)
- [ ] Device discovery and capability querying
- [ ] Unified tensor representation
- [ ] 10+ unit tests per backend

**Performance Targets**:
- CoreML inference: < 100ms for typical model

---

### 0.3: Video Codec Wrapping 🎬
**Owner**: Engineer (Multimedia)  
**Duration**: 4-5 days  
**Blockers**: After 0.1 completes  
**Deliverables**:
- [ ] FFmpeg wrapper (ffmpeg-next or similar crate)
- [ ] H.264, H.265, VP9, AV1 decode support
- [ ] H.264, H.265 encode support (ProRes optional)
- [ ] Hardware accelerated decode (VideoToolbox on macOS)
- [ ] Color space conversion utilities
- [ ] Metadata extraction (codec, resolution, FPS, duration)
- [ ] 15+ integration tests with real video files

**Performance Targets**:
- 1080p H.264 decode: > 200fps
- 1080p H.265 decode: > 150fps

---

### 0.4: Real-ESRGAN Filter 🖼️
**Owner**: Engineer (AI/ML)  
**Duration**: 3-4 days  
**Blockers**: After 0.2 and 0.3 complete  
**Deliverables**:
- [ ] Download & validate Real-ESRGAN ONNX model
- [ ] ONNX Runtime integration
- [ ] Frame-by-frame inference loop
- [ ] Input preprocessing (normalization, tiling)
- [ ] Output postprocessing
- [ ] Integration with decode/encode pipeline
- [ ] 10+ test cases (visual validation)

**Performance Targets**:
- 1080p → 4K: > 0.5fps on Apple Silicon

---

### 0.5: Filter Pipeline Architecture 🔀
**Owner**: Engineer (Architecture)  
**Duration**: 2-3 days  
**Blockers**: After 0.4 completes  
**Deliverables**:
- [ ] Filter trait and registry
- [ ] Sequential chaining support
- [ ] GPU memory optimization (buffer reuse)
- [ ] Real-time vs batch mode flags
- [ ] Filter graph validation
- [ ] 8+ integration tests (multi-filter combos)

**Example Test**: Real-ESRGAN + NAFNet (denoise) on 1080p video

---

### 0.6: Preset System 📦
**Owner**: Engineer (Data/Config)  
**Duration**: 2-3 days  
**Blockers**: After 0.5 completes  
**Deliverables**:
- [ ] Preset schema (JSON/TOML format)
- [ ] Filesystem + database storage
- [ ] 6 builtin presets:
  - old-film-revival (denoise + upscale + color correct)
  - anime-enhancement (Anime4K style)
  - black-white-restoration (DeOldify colorize)
  - hdr-compatible (tone map + compress)
  - smooth-60fps (RIFE interpolation)
  - ultimate-restoration (all filters combined)
- [ ] Preset validation and versioning
- [ ] JSON export for UI consumption
- [ ] 12+ test cases

---

### 0.7: CLI Implementation 🖥️
**Owner**: Engineer (CLI/UX)  
**Duration**: 3-4 days  
**Blockers**: After 0.6 completes  
**Deliverables**:
- [ ] clap-based argument parser
- [ ] Main commands: enhance, info, list-presets, list-filters, benchmark
- [ ] Flags: --preset, --filter, --output, --gpu, --verbose, --dry-run
- [ ] Config file support (~/.hipixel/config.toml)
- [ ] Progress bar and logging
- [ ] Error messages with suggestions
- [ ] Python bindings (ctypes/PyO3)
- [ ] 20+ test cases

**Example Usage**:
```bash
hipixel-core enhance movie.mp4 --preset old-film-revival -o output.mp4 --verbose
```

---

### 0.8: Benchmarking & Validation 📊
**Owner**: Engineer (QA/Performance)  
**Duration**: 2-3 days  
**Blockers**: After 0.7 completes  
**Deliverables**:
- [ ] Collect benchmark video set (720p, 1080p, 4K, various codecs)
- [ ] Per-filter performance report
- [ ] Per-preset performance report
- [ ] GPU memory profiling
- [ ] Thermal profile data
- [ ] Stress test results (2+ hour videos)
- [ ] Visual quality validation framework
- [ ] Benchmark report template
- [ ] GitHub Actions continuous benchmarking

**Performance Baselines**:
- Real-ESRGAN 1080p→4K: ≥0.5fps
- NAFNet denoise 1080p: ≥5fps
- Full preset (all filters): ≥0.3fps

---

### 0.9: Packaging & Release 📦
**Owner**: Engineer (DevOps/Release)  
**Duration**: 2-3 days  
**Blockers**: After 0.8 passes  
**Deliverables**:
- [ ] crates.io publication (Rust)
- [ ] PyPI publication (Python)
- [ ] GitHub release with binaries
- [ ] macOS homebrew formula
- [ ] Windows Scoop formula
- [ ] Linux apt/yum packages
- [ ] Installation verification tests
- [ ] Changelog and release notes
- [ ] Getting started guide (Rust + Python)

**Release**: v0.1.0

---

## Phase 0.5 · UI/UX Design (Task 10 · PARALLEL)

**Owner**: Designer  
**Duration**: 3 weeks (overlaps with Phase 0)  
**Deliverables**:
- [ ] Figma workspace setup with design tokens
  - Typography scale (8px base)
  - Color system (brand + functional + semantic)
  - Spacing system
  - Component library (buttons, inputs, cards, modals, etc.)
- [ ] HiVideo core screens (high-fidelity):
  - Splash/launch screen
  - Media library grid
  - Playback screen with hotkey hints
  - Command palette
  - Character sidebar & detail
  - Preferences modal
- [ ] HiPixel web design:
  - Upload interface
  - Queue management
  - Account settings
- [ ] Responsive specifications (macOS primary, mention iPad/web)
- [ ] Accessibility checklist (WCAG 2.1 AA)
- [ ] Design-to-dev handoff document
- [ ] Component storybook (Figma or Storybook.js)

---

## 📈 Timeline & Milestones

### Week 1 (Days 1-7)
- ✅ 0.1 Monorepo setup
- 🔄 0.2 GPU backend (in progress)
- 🔄 0.3 Video codec (in progress)
- 🔄 0.5 Design kickoff

### Week 2 (Days 8-14)
- ✅ 0.2 GPU backend complete
- ✅ 0.3 Video codec complete
- 🔄 0.4 Real-ESRGAN (in progress)
- 🔄 0.5 Design screens (in progress)

### Week 3 (Days 15-21)
- ✅ 0.4 Real-ESRGAN complete
- ✅ 0.5 Pipeline architecture complete
- ✅ 0.6 Preset system complete
- ✅ 0.7 CLI complete
- 🔄 0.8 Benchmarking (in progress)
- ✅ 0.5 Design deliverables complete

### Week 4 (Days 22-28, rollover)
- ✅ 0.8 Benchmarking complete
- ✅ 0.9 Release packaging complete
- 📦 v0.1.0 ship

---

## 🎯 Milestone M1: hipixel-core CLI Working

**Definition of Done**:
- [ ] `hipixel-core enhance test.mp4 --preset old-film-revival -o output.mp4` works end-to-end
- [ ] Output video quality is visually acceptable
- [ ] Performance baseline documented (≥0.5fps for realistic presets)
- [ ] Tests pass on macOS, Linux, Windows (CI green)
- [ ] Packaged and published to crates.io + PyPI
- [ ] Documentation complete and searchable

---

## 🚀 Next Phase: Phase 1 (HiVideo MVP Playback)

Once M1 is shipped:
1. Create Xcode project skeleton
2. Implement basic playback (decode with VideoToolbox + Metal rendering)
3. Call hipixel-core CLI for real-time enhancement
4. Validate 1080p H.264 playback at 60fps with enhancement
5. Build basic UI (media library, playback controls)

---

## 📚 References

- [DEV-PLAN.md](../../docs/dev-plan/DEV-PLAN.md) - Full 11-phase roadmap
- [PRD.md](../../docs/PRD.md) - Complete feature specification
- [README.md](../../README.md) - Project overview

---

**Last Updated**: 2026-05-30  
**Status**: Ready to start Phase 0.1  
**Next Action**: Create Cargo workspace and GitHub Actions CI
