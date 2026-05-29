# 🚀 HiVideo · Quick Start Guide

## What Is This Project?

**HiVideo** = macOS AI-native video player with real-time enhancement  
**HiPixel** = Web-based batch video enhancement and export tool  
**hipixel-core** = Shared Rust + Python AI processing engine

## Current Status

```
📊 Design: 100% ✅
📝 Code:   0% ⏳
🎨 UI:     30% ✅ (partial mockups done)
```

## Where to Start?

### For Managers/Stakeholders (30 min)
1. Read: `EXPLORATION-COMPLETE.md` (this directory)
2. Read: `README.md`
3. Check: `docs/dev-plan/PHASE-0-TASKS.md` for timeline

### For Engineers (2-3 hours)
1. Read: `README.md` (10 min)
2. Skim: `docs/DIRECTORY-STRUCTURE.md` (15 min)
3. Read: `docs/dev-plan/PHASE-0-TASKS.md` (30 min) — your tasks are here!
4. Deep: `docs/PRD.md` sections 4.1-4.9 (1 hour)

### For Designers (1-2 hours)
1. Read: `README.md` (10 min)
2. Read: `docs/dev-plan/PHASE-0-TASKS.md` Task #10 (15 min)
3. Deep: `docs/PRD.md` sections 3 & 5 (45 min)

### For DevOps (1.5 hours)
1. Read: `README.md` (10 min)
2. Read: `docs/dev-plan/PHASE-0-TASKS.md` (30 min)
3. Deep: `docs/DEV-PLAN.md` CI/CD matrix section (30 min)

## What Needs to Happen Now?

### Phase 0: Build hipixel-core CLI (Next 4 weeks)

**10 Tasks** tracked in Claude task system:

| Task | Work Item | Duration | Start |
|------|-----------|----------|-------|
| #1 | Monorepo setup | 2-3 days | NOW ⏰ |
| #2 | GPU backend | 4-5 days | After #1 |
| #3 | Video codecs | 4-5 days | After #1 |
| #4 | Real-ESRGAN | 3-4 days | After #2+#3 |
| #5 | Pipeline | 2-3 days | After #4 |
| #6 | Presets | 2-3 days | After #5 |
| #7 | CLI | 3-4 days | After #6 |
| #8 | Benchmarks | 2-3 days | After #7 |
| #9 | Release | 2-3 days | After #8 |
| #10 | UI Design | 3 weeks | NOW (parallel) |

**Success Milestone M1** (end of Phase 0):
```bash
hipixel-core enhance movie.mp4 --preset old-film-revival -o output.mp4
```

## Key Documents

| File | Purpose | Read Time |
|------|---------|-----------|
| `README.md` | Project overview | 10 min |
| `EXPLORATION-COMPLETE.md` | Status snapshot | 15 min |
| `docs/PRD.md` | Complete spec | 1-2 hours |
| `docs/DIRECTORY-STRUCTURE.md` | Repo analysis | 20 min |
| `docs/dev-plan/PHASE-0-TASKS.md` | This sprint | 30 min |
| `docs/dev-plan/DEV-PLAN.md` | Full roadmap | 45 min |

## Critical Path

```
Phase 0 (hipixel-core) ← Must complete first
    ↓
Phase 1 (HiVideo MVP)
    ↓
Phases 2-10 (Full features)
```

**No blockers to starting Phase 0 right now!** ✅

## Performance Targets

By end of Phase 0:
- Real-ESRGAN: ≥0.5fps (1080p→4K on M-series Mac)
- NAFNet denoise: ≥5fps (1080p)
- Full preset: ≥0.3fps

## Tech Stack Summary

**Frontend**: SwiftUI + Metal (macOS), React + Vite (Web)  
**AI Core**: ONNX Runtime + CoreML (macOS), CUDA (Windows), DirectML (AMD)  
**Backend**: FastAPI (Python), Redis Streams  
**Storage**: SQLite (local), PostgreSQL (server), S3/MinIO (objects)  
**Codecs**: FFmpeg + VideoToolbox (macOS) + hardware acceleration  

## Questions?

### "Can we start coding now?"
✅ **YES.** Phase 0.1 is ready. No design dependencies.

### "How long to v1.0?"
~26 weeks if following plan. Can be optimized with larger team.

### "What's the biggest risk?"
Execution risk depends on team size/experience. Technical risk is LOW.

### "Should I follow the exact timeline?"
Use as guide. Adjust based on team velocity. Weekly checkpoints recommended.

### "When can we start Phase 1?"
After M1 (hipixel-core CLI working) = ~4 weeks.

## Next Action

**Pick one:**

1. **If you're starting Phase 0.1**: 
   - Open `docs/dev-plan/PHASE-0-TASKS.md`
   - Look at Task #1 deliverables
   - Create Cargo workspace

2. **If you're doing Phase 0.5 design**:
   - Open `docs/dev-plan/PHASE-0-TASKS.md` Task #10
   - Set up Figma workspace
   - Create design token library

3. **If you're managing the project**:
   - Open `docs/dev-plan/PHASE-0-TASKS.md`
   - Assign tasks #1-10 to team members
   - Set weekly checkpoint reviews

---

**Status**: ✅ Ready to start  
**Timeline**: 4 weeks to M1, 26 weeks to v1.0  
**Next Milestone**: M1 hipixel-core CLI working  

*For detailed information, see the full documents linked above.*
