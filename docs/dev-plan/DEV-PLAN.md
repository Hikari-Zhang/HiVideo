# HiVideo + HiPixel · 开发计划与进度追踪

> 单一真相来源（Single Source of Truth）。完成一项就把 `[ ]` 改成 `[x]`。
> 优先级：🔴 P0 阻塞 / 🟡 P1 重要 / 🟢 P2 可选

---

## 📊 总览看板

| 阶段 | 状态 | 计划周 | 完成度 |
|---|---|---|---|
| Phase 0 · hipixel-core 内核抽离 + CLI（**Python 优先**） | ✅ 完成 | 3 周 | ~90% |
| **Phase 0.5 · UI/UX 设计与原型** | 🔄 进行中 | **3 周** | ~65% |
| Phase 1 · HiVideo MVP 播放器 | ⏸ 未开始 | 6 周 | 0% |
| Phase 2 · HiPixel MVP Web 服务 | ⏸ 未开始 | 5 周 | 0% |
| **Phase 2.5 · hipixel-core Rust 内核迁移** | ⏸ 未开始 | **3 周** | 0% |
| Phase 3 · HiVideo AI 入场 | ⏸ 未开始 | 6 周 | 0% |
| Phase 4 · HiPixel 分布式 + Windows | ⏸ 未开始 | 4 周 | 0% |
| Phase 5 · 智能管家（角色 / 摘要 / 跳过） | ⏸ 未开始 | 4 周 | 0% |
| Phase 6 · 字幕子系统 | ⏸ 未开始 | 3 周 | 0% |
| Phase 7 · 网盘 + 副本管理 | ⏸ 未开始 | 4 周 | 0% |
| Phase 8 · 远程节点联动 | ⏸ 未开始 | 3 周 | 0% |
| Phase 9 · 扩展插件 + 系统集成 | ⏸ 未开始 | 4 周 | 0% |
| Phase 10 · 打磨 + 上线 | ⏸ 未开始 | 4 周 | 0% |
| **合计** | — | **52 周** | **0%** |

> 状态图例：⏸ 未开始 / 🔄 进行中 / ✅ 完成 / ⚠ 阻塞 / ❌ 取消
> 设计与编码并行：Phase 0.5 和 Phase 0 可大部分并行（设计师 / 工程师不同人）。每个后续 Phase 都包含「设计先行 → 评审 → 编码」的子流程，避免代码做完才发现 UI 要返工。
> **语言策略**：Phase 0 Python 优先快速验证 AI 效果；Phase 2.5 将视频 I/O 和帧处理层迁移到 Rust，完成后 Phase 3 HiVideo 才能通过 Swift FFI 调用 hipixel-core。

---

## Phase 0 · hipixel-core 内核抽离 + CLI（3 周）🔴

> 目标：跑通 `hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4`
> **语言策略（已决策）**：Python 优先——整个 Phase 0 用纯 Python 实现，快速验证 AI 效果与流水线可行性。Rust 内核迁移在 Phase 2.5 进行。

### 0.1 项目骨架（Day 1-2）

- [x] 🔴 在 HiVideo monorepo 下创建 `hipixel-core/` 子目录
- [x] 🔴 ~~选择主语言~~（**已决策：Phase 0 Python 优先，Phase 2.5 迁移 Rust**）
- [x] 🔴 配置 Python `pyproject.toml`（uv / Poetry 管理依赖）
- [x] 🔴 配置 GitHub Actions CI 矩阵：`macos-14` + `ubuntu-22.04` + `windows-2022`（5 jobs：lint / test-macos / test-linux / test-windows / build，Python 3.11 + 3.12 矩阵，build 门控于三平台测试全通过）
- [x] 🔴 引入 FFmpeg 依赖（系统检测 / 静态链接二选一）
- [x] 🔴 引入 ONNX Runtime 跨平台依赖
- [x] 🟡 配置 `cargo fmt` + `clippy` + `ruff` + `mypy` 一致性检查
- [x] 🟡 写 README + LICENSE（推荐 Apache 2.0）（README 已更新：10 个内置预设、ACES 滤镜、3 平台 CI 徽章；LICENSE Apache 2.0 已存在）

### 0.2 GPU 后端抽象层（Day 3-5）

- [x] 🔴 定义 `InferenceBackend` trait/protocol（init / load_model / run / cleanup）
- [x] 🔴 实现 CoreML 后端（macOS / Apple Silicon）
- [x] 🔴 实现 CUDA 后端（Linux / Windows + NVIDIA）
- [ ] 🟡 实现 DirectML 后端（Windows + AMD / Intel）
- [ ] 🟡 实现 OpenVINO 后端（Intel CPU / Arc）
- [x] 🟢 实现 CPU 兜底后端（任何平台）
- [x] 🔴 写 GPU 检测模块（自动选最优后端）
- [ ] 🟡 显存检测 + 不足时自动降级处理

### 0.3 视频解码 / 编码（Day 6-7）

- [x] 🔴 FFmpeg 解复用器封装（MP4 / MKV / MOV / AVI）
- [x] 🔴 视频解码（H.264 / H.265 软解先跑通）
- [ ] 🟡 接 VideoToolbox 硬解（macOS）
- [ ] 🟡 接 NVDEC 硬解（NVIDIA）
- [x] 🔴 视频编码（H.264 / H.265 软编先跑通）
- [ ] 🟡 NVENC 硬编（NVIDIA）
- [ ] 🟡 VideoToolbox 编码（macOS）
- [x] 🔴 帧格式转换（YUV ↔ RGB ↔ tensor）
- [x] 🟡 颜色空间处理（BT.709 / BT.2020）

### 0.4 第一个滤镜 · Real-ESRGAN 超分（Day 8-10）

- [x] 🔴 下载 Real-ESRGAN-General-x2 ONNX 模型（registry.json 已更新真实 ONNX URL + size_bytes）
- [x] 🔴 ONNX 模型加载到 InferenceBackend（含输入张量名自动重映射）
- [x] 🔴 单帧推理跑通：input frame → output frame（31 个 e2e 测试覆盖，含合成 ONNX Identity 模型验证全栈：ORT 加载 → 张量重映射 → tile 拼接 → NAFNet 混合 → 3 线程 Pipeline）
- [x] 🔴 视频流处理：连续帧 → tile 切分 → 推理 → 拼接（`RealESRGANFilter._tile_infer()` 已实现）
- [x] 🟡 显存优化：动态调整 tile 大小（`_auto_tile_size()` 根据 VRAM 自动计算，CPU 兜底 256px，上限 1024px，步长 64px）
- [x] 🟡 进度回调 + 帧速率统计（`FpsTracker` 滚动窗口 deque，修复 fps_current 计算 bug，`ProgressEvent` 含 fps_current / fps_avg / progress_pct）
- [x] 🟡 写单帧测试（PSNR / SSIM 验证）（`test_metrics.py` 17 个测试 + `test_pipeline_progress.py` 12 个测试，130 个测试全部通过）

### 0.5 滤镜流水线（Day 11-12）

- [x] 🔴 定义 `Filter` trait 和 `Pipeline` 概念
- [x] 🔴 实现 Anime4K v4 滤镜（动漫超分）（`anime4k.py` 已实现，8 个测试覆盖）
- [x] 🔴 实现 NAFNet 降噪滤镜（`nafnet.py` 已实现，NAFNet-REDS-width64.onnx URL 已更新）
- [x] 🟡 实现 CAS 锐化滤镜（GPU shader）
- [x] 🟡 实现 ACES tone-mapping（HDR→SDR）（`aces.py`，Narkowicz ACES fitted + Reinhard，无模型 CPU 实现，11 个测试覆盖）
- [ ] 🟡 实现 RIFE 插帧滤镜
- [ ] 🟢 实现 DeOldify 上色滤镜
- [x] 🔴 滤镜串联机制（Pipeline.chain([f1, f2, f3])）
- [ ] 🟡 共享纹理优化（避免多次 GPU↔CPU 拷贝）

### 0.6 预设系统（Day 13）

- [x] 🔴 定义 `Preset` JSON Schema
- [x] 🔴 实现 7 个内置预设：
  - [x] 🔴 老片救星
  - [x] 🔴 番剧增强
  - [x] 🟡 黑白复刻（`bw-restoration.json`：重度 NAFNet 降噪 + RealESRGAN 2× + CAS）
  - [x] 🟡 HDR 兼容（`hdr-compatible.json`：ACES tone-mapping + CAS，纯 CPU 无显存需求）
  - [x] 🟡 丝滑插帧 60fps（`smooth-60fps.json`：NAFNet + RIFE v4.6，Phase 1 实现前 stub 占位）
  - [x] 🟡 极致修复
  - [x] 🟢 最快速度
- [x] 🔴 预设加载与执行
- [ ] 🟡 用户自定义预设支持

### 0.7 CLI 命令实现（Day 14-15）

- [x] 🔴 `hipixel-core enhance` 主命令
- [x] 🔴 `hipixel-core batch` 批量命令
- [x] 🟡 `hipixel-core presets ls` 列预设
- [x] 🟡 `hipixel-core models ls` 列模型
- [x] 🟡 `hipixel-core models download <name>` 下载模型
- [x] 🟡 `hipixel-core bench` 性能基准
- [ ] 🟡 `hipixel-core demo` 演示模式
- [x] 🟡 进度条（indicatif / rich）
- [x] 🟡 详细 / 安静日志级别

### 0.8 验证与基准（Day 16-18）

- [ ] 🔴 准备测试素材：480p DVDrip / 720p 番剧 / 1080p 实拍 / 4K HDR
- [ ] 🔴 在 M1 / M2 / M2 Max 上跑基准
- [ ] 🟡 在 RTX 3060 / 4090 上跑基准（如有硬件）
- [ ] 🟡 在 AMD / Intel Arc 上跑基准（如有硬件）
- [ ] 🔴 输出性能对比表（⚠ 阻塞于真实硬件 — 表格已在 `performance-tuning.md` 中占位）
- [ ] 🟡 录制 demo 视频（before/after）
- [x] 🟡 撰写性能调优文档（`docs/architecture/performance-tuning.md`：tile 推理原理、期望 FPS 目标、调优旋钮、8 节完整文档）
- [x] 🟡 基准框架实现（`hipixel_core/bench/`：`synthetic.py` 合成帧生成 + `runner.py` `BenchmarkRunner`/`BenchmarkResult`/`BenchmarkReport` + 64 个测试全部通过）
- [x] 🟡 扩展 `bench` CLI（`--all-filters`、`--filter NAME`、`--output PATH`、`--format json|md|table`）

### 0.9 打包与发布（Day 19-21）

- [ ] 🟡 macOS：universal binary + 公证（暂跳过签名）
- [ ] 🟡 Linux：static binary（Docker 友好）
- [ ] 🟡 Windows：PyInstaller 打包 exe
- [ ] 🟡 模型按需下载机制（首次运行 / 显式 download 命令）
- [ ] 🟡 发布到 GitHub Releases
- [ ] 🟢 发布到 Homebrew tap（macOS）
- [ ] 🟢 发布到 crates.io（如选 Rust）

---

## Phase 0.5 · UI/UX 设计与原型（3 周）🔴

> 目标：在动手写 HiVideo / HiPixel 代码之前，把所有核心界面的高保真设计稿做出来。
> **设计先行原则**：每个界面有 Figma 设计稿 + 交互标注 + 设计 token + 评审通过后，再让工程师对着实现。
> 与 Phase 0 大部分可并行（不同人执行）。

### 0.5.1 设计基础设施（Week 1, Day 1-3）

- [x] 🔴 选定设计工具：**Figma**（推荐 / 协作好）+ 工程端 SwiftUI
- [x] 🔴 创建文件结构（`docs/design/` 目录已建立，含 5 个规范文档）
- [ ] 🔴 建立 Figma 工作区与项目文件：HiVideo / HiPixel / Shared 三个 Page
- [ ] 🔴 引入 Apple 官方 macOS UI Kit（Figma Community）
- [x] 🔴 引入 SF Symbols 图标库（映射表见 `docs/design/00-tokens.md §7`）
- [ ] 🟡 配置 Figma Tokens 插件（Token JSON 已在 `04-handoff.md` 中导出）
- [x] 🟡 建立设计版本管理规范（通过 git 追踪 `docs/design/`）

### 0.5.2 设计 Token 与组件库（Week 1, Day 3-7）

- [x] 🔴 **配色 Token**：浅色 / 深色双套（`docs/design/00-tokens.md §1` + `Colors.swift`）
- [x] 🔴 字体 Token：SF Pro / SF Pro Rounded（数字）/ SF Mono（`00-tokens §2` + `Typography.swift`）
- [x] 🔴 圆角 Token：6 / 8 / 12 / 18px（`00-tokens §4` + `Spacing.swift`）
- [x] 🔴 间距 Token：4 / 8 / 12 / 16 / 20 / 24 / 32 / 48（`00-tokens §3` + `Spacing.swift`）
- [x] 🔴 阴影 / 模糊 Token：NSVisualEffectView 各材质映射（`00-tokens §5` + `Spacing.swift`）
- [x] 🔴 动效 Token：spring 时长 / damping（`00-tokens §6` + `Spacing.swift`）
- [ ] 🔴 基础组件 Figma 稿：按钮 / 输入框 / 滑条 / 开关 / 选择器 / Tab / Toast / Modal
- [x] 🟡 业务组件 SwiftUI：海报卡（`PosterCard.swift`）/ 角色卡（`CharacterCard.swift`）
- [ ] 🟡 状态变体 Figma 稿：默认 / hover / active / disabled / loading
- [ ] 🟡 导出 Style Guide PDF（团队共识 + 后续接手参考）

### 0.5.3 HiVideo 核心界面设计（Week 2）

#### A. 入口与基础（Day 8-9）

- [x] 🔴 启动屏规范（`01-hivideo-core §1`）· Figma 高保真稿待补
- [x] 🔴 主窗口框架规范（`01 §2`，三栏布局常量在 `Spacing.swift`）· Figma 待补
- [ ] 🔴 偏好设置 / 设置中心信息架构

#### B. 媒体库（Day 9-11）

- [x] 🔴 媒体库 · 网格视图规范（`01 §3` + `PosterCard.swift`）· Figma 待补
- [x] 🔴 媒体库 · 列表视图规范（`01 §4`）· Figma 待补
- [x] 🔴 媒体库 · 时间线视图规范（`01 §5`）· Figma 待补
- [x] 🔴 视频详情面板规范（`01 §6`，4 个 Tab 完整定义）· Figma 待补
- [x] 🔴 智能分组（侧边栏分组结构见 `01 §2`）
- [ ] 🟡 空状态 / 加载状态 / 错误状态

#### C. 播放器（Day 11-12）

- [x] 🔴 沉浸式播放窗规范（`01 §7` + `PlayerControls.swift`）· Figma 待补
- [x] 🔴 控制条详细布局（`01 §7`，含浮窗位置、72pt 高）
- [x] 🔴 字幕 / 音轨菜单（控制条右侧按钮组定义完整）
- [x] 🔴 时间轴预览缩略图（进度条悬停规范见 `01 §7`）
- [ ] 🟡 全屏 vs 窗口尺寸适配

#### D. 命令面板与快捷键（Day 12-13）

- [x] 🔴 ⌘K 命令面板（`01 §8` + `CommandPalette.swift`，含搜索结果分类）· Figma 待补
- [x] 🔴 ⌘/ 快捷键速查面板（`01 §9`）· Figma 待补
- [ ] 🟡 自定义快捷键设置页

#### E. 角色识别（Day 13-14）✅ 已有部分原型

- [x] 🔴 角色侧边栏 + 角色网格主区（`01 §10` + `CharacterCard.swift`）
- [x] 🔴 角色详情页（`01 §11` + `CharacterCard.swift` DetailHeader，含 Tony Stark 原型）
- [x] 🟡 未知角色命名弹窗（`02-hivideo-interactions §8`）
- [x] 🟡 误聚类拆分流程（`02 §9`）
- [ ] 🟡 对手戏 / 高光集锦页

### 0.5.4 HiVideo 高频交互设计（Week 3, Day 15-17）

- [x] 🔴 **副本选择弹窗**（`02-hivideo-interactions §1`，完整 5 区布局 + 操作策略表）
- [x] 🔴 **删除安全网 toast**（`02 §2`，5s 撤销 + 30 分钟历史栈 + 流程图）
- [x] 🔴 **画质增强浮窗**（`02 §3`，滤镜开关 + 强度 + 性能仪表）
- [x] 🔴 **音频增强浮窗**（`02 §4`，电平 + LUFS + 设备预设 + 深夜三档）
- [x] 🔴 **算力节点设置页**（`02 §5`，节点卡 + 自动发现 + 手动输入流程）
- [x] 🔴 **添加 SMB 网盘向导**（`02 §6`，4 步弹窗 + 测试连接）
- [x] 🟡 **字幕编辑器**（`02 §7`，三栏布局：列表 / 预览 / 波形）
- [ ] 🟡 **在线字幕搜索结果列表**
- [ ] 🟡 网盘诊断面板
- [ ] 🟡 配置备份恢复弹窗

### 0.5.5 HiPixel Web 界面设计（Week 3, Day 18-19）

- [x] 🔴 **上传屏**（`03-hipixel-web §1`，大留白 + 拖拽区 + 7 张预设大卡）
- [x] 🔴 **队列屏**（`03 §2`，任务列表 + 进度条 + 4 状态 Tab）
- [x] 🔴 **对比屏**（`03 §3`，before/after 拖动分割线 + 关键帧报告侧栏）
- [x] 🟡 关键帧报告侧栏（`03 §3` 已含详细规范）
- [ ] 🟡 任务详情页
- [ ] 🟡 设置 / 配额 / 用户管理
- [ ] 🟡 暗色模式适配
- [ ] 🟡 移动端响应式（次要，但要预留）

### 0.5.6 Windows HiPixel 界面设计（Week 3, Day 19-20）

- [x] 🔴 安装向导四步（`03 §4`，欢迎 / GPU 检测 / 模型下载 / 完成）
- [x] 🔴 系统托盘菜单（`03 §5`，暂停 / 队列 / 设置 / 退出 + 三色图标状态）
- [ ] 🟡 配对码确认弹窗（Windows 端）
- [x] 🟡 GPU 利用率 / 温度监视小窗（`03 §5` 已含 GPU 监视浮窗规范）
- [ ] 🟢 任务完成通知样式

### 0.5.7 设计评审与交付（Week 3, Day 20-21）

- [ ] 🔴 内部评审：流程顺畅度 / 视觉一致性 / 可用性
- [ ] 🔴 用户测试（5 人左右，让他们试操作）
- [ ] 🔴 修订 + 第二轮评审
- [ ] 🔴 设计稿冻结（freeze）→ 工程师对着实现
- [ ] 🟡 导出标注稿（Figma → Zeplin / Figma 自带 Inspect）
- [x] 🟡 设计 token 导出 JSON 给工程师（`docs/design/04-handoff.md` 已含 Token JSON）
- [ ] 🟡 录制交互动效参考视频
- [x] 🟡 撰写「设计 → 实现」对照清单（`docs/design/04-handoff.md`）

### 0.5.8 持续迭代机制

- [ ] 🟡 后续 Phase 中新增功能 → 先回到 Figma 加稿 → 评审 → 实现
- [ ] 🟡 每个 Phase 末做 UI 走查（实际效果 vs 设计稿差异 → 修正）
- [ ] 🟡 维护 Figma Library 版本号，工程实现引用对应版本

---

## Phase 1 · HiVideo MVP 播放器（6 周）🔴

> 目标：能播 1080p H.264 全屏沉浸，有续播，有简洁 UI
> **前置 UI 已就绪（Phase 0.5）**：启动屏 / 主窗口 / 媒体库 / 播放器 / 命令面板

### 1.0 设计走查（Day 1）

- [ ] 🔴 与设计稿对照，确认本 Phase 涉及的所有界面已完成
- [ ] 🔴 找出不足的设计稿，回 Phase 0.5 补齐
- [ ] 🟡 设计 token 导入到 Xcode 资产目录

### 1.1 Xcode 项目骨架（Week 1）

- [ ] 🔴 创建 Xcode 项目：HiVideo / SwiftUI / macOS 14+
- [ ] 🔴 配置 Bundle ID + 团队签名
- [ ] 🔴 模块拆分：PlaybackKit / MediaKit / AIKit / PluginKit / App
- [ ] 🔴 引入 SwiftPM 依赖：FFmpegKit / hipixel-core（Swift binding）
- [ ] 🟡 配置 SwiftLint + SwiftFormat
- [ ] 🟡 配置 GitHub Actions：build + test
- [ ] 🟡 设置最低部署目标 + Apple Silicon Only

### 1.2 PlaybackKit 框架（Week 2-3）

- [ ] 🔴 定义 `Player` 协议（play / pause / seek / rate）
- [ ] 🔴 实现基于 AVPlayer 的简单后端（先跑通）
- [ ] 🔴 实现基于 FFmpeg + VideoToolbox 的高级后端
- [ ] 🔴 Metal 渲染层（CAMetalLayer + 自定义 shader）
- [ ] 🔴 音视频同步（PTS 对齐）
- [ ] 🟡 倍速不变调（AVAudioUnitTimePitch）
- [ ] 🟡 帧步进（前 / 后）
- [ ] 🟡 字幕轨道选择
- [ ] 🟡 多音轨切换
- [ ] 🟡 HDR 元数据透传

### 1.3 极简 UI（Week 4）

- [ ] 🔴 启动屏（拖入提示 + 最近播放）
- [ ] 🔴 沉浸式播放窗（无边框 + 浮现控制条）
- [ ] 🔴 控制条：播放 / 进度 / 音量 / 全屏
- [ ] 🟡 时间轴预览（缩略图）
- [ ] 🟡 字幕菜单
- [ ] 🟡 音轨菜单
- [ ] 🟢 截图功能（⌘⇧S）

### 1.4 媒体库 v1（Week 5）

- [ ] 🔴 SQLite 数据库 schema 设计
- [ ] 🔴 添加监视文件夹
- [ ] 🔴 后台扫描器（增量）
- [ ] 🔴 提取元数据（分辨率 / 时长 / 编码）
- [ ] 🟡 生成时间轴缩略图
- [ ] 🔴 网格视图 UI
- [ ] 🟡 列表视图 UI
- [ ] 🔴 续播位置记录
- [ ] 🟡 详情面板（侧边滑入）

### 1.5 基础快捷键（Week 6）

- [ ] 🔴 Space 播放暂停
- [ ] 🔴 ←→ ±5s / ⇧←→ ±30s
- [ ] 🔴 ↑↓ 音量 / M 静音
- [ ] 🔴 F 全屏 / ⌘W 关闭
- [ ] 🔴 ⌘O 打开文件 / ⌘⇧O 打开文件夹
- [ ] 🟡 [ ] 变速
- [ ] 🟡 0-9 百分比跳转
- [ ] 🟢 ⌘K 命令面板（先放占位）

### 1.6 MVP 验收

- [ ] 🔴 能播 1080p H.264 / H.265 流畅
- [ ] 🔴 4K HDR CPU < 8%（M1）
- [ ] 🔴 启动时间 < 1.5s
- [ ] 🔴 内存 < 400MB
- [ ] 🟡 媒体库扫描 1000 文件 / 分钟
- [ ] 🟡 录制 demo 视频

---

## Phase 2 · HiPixel MVP Web 服务（5 周）🔴

> **前置 UI 已就绪**：上传屏 / 队列屏 / 对比屏（Phase 0.5）

### 2.0 设计走查（Day 1）
- [ ] 🔴 三屏设计稿对齐 + 切图 + 设计 token 导入前端
- [ ] 🟡 设计稿与 React 组件命名映射表

### 2.1 Server 骨架（Week 1）

- [ ] 🔴 创建仓库 `hipixel-server/`
- [ ] 🔴 FastAPI + uvicorn 项目结构
- [ ] 🔴 Redis Stream 任务队列
- [ ] 🔴 PostgreSQL schema（user / task / quota）
- [ ] 🔴 MinIO 对象存储集成
- [ ] 🟡 SQLAlchemy + Alembic 迁移
- [ ] 🟡 Pydantic 请求/响应模型

### 2.2 任务编排（Week 2）

- [ ] 🔴 任务提交端点 `POST /v1/tasks`
- [ ] 🔴 任务查询端点 `GET /v1/tasks/:id`
- [ ] 🔴 任务列表端点 `GET /v1/tasks`
- [ ] 🔴 取消任务端点 `DELETE /v1/tasks/:id`
- [ ] 🟡 SSE 进度推送 `GET /v1/tasks/:id/progress`
- [ ] 🟡 Webhook 回调
- [ ] 🟡 重试 / 故障转移逻辑

### 2.3 上传与存储（Week 3）

- [ ] 🔴 直接上传端点（multipart）
- [ ] 🔴 TUS 协议断点续传
- [ ] 🟡 URL 拉取（HTTP / S3 / WebDAV）
- [ ] 🟡 远程拉取（节点直拉 NAS）
- [ ] 🔴 输出文件预签名下载 URL
- [ ] 🟡 短链分享 + 7 天过期

### 2.4 Worker 集群（Week 3-4）

- [ ] 🔴 Worker 启动脚本（消费 Redis Stream）
- [ ] 🔴 调用 hipixel-core CLI 处理任务
- [ ] 🔴 进度上报到 Redis（前端 SSE 拉取）
- [ ] 🟡 GPU 检测 + 任务亲和
- [ ] 🟡 失败重试 + 死信队列
- [ ] 🟡 任务超时机制

### 2.5 Web 前端（Week 4-5）

- [ ] 🔴 React + Vite + shadcn/ui 项目
- [ ] 🔴 上传屏：拖拽 + 预设大卡
- [ ] 🔴 队列屏：任务列表 + 进度环
- [ ] 🟡 对比屏：before/after 拖动分割线
- [ ] 🟡 关键帧报告
- [ ] 🟡 浏览器通知
- [ ] 🟡 暗色模式

### 2.6 MVP 验收

- [ ] 🔴 上传 500MB → 提交任务 → 完成 → 下载流程跑通
- [ ] 🔴 Docker Compose 一键起
- [ ] 🟡 文档 + 示例
- [ ] 🟡 上线 demo 站点

---

## Phase 2.5 · hipixel-core Rust 内核迁移（3 周）🔴

> 目标：将 Phase 0 的 Python 实现中性能关键路径迁移到 Rust，对外暴露 Python（PyO3）和 Swift（UniFFI）两套绑定。
> **前置**：Phase 0 Python CLI 功能完整、基准数据可用。
> **后置**：Phase 3 HiVideo AI 入场依赖 Swift binding 才能实时调用。

### 2.5.1 Rust 工作区搭建（Day 1-2）

- [ ] 🔴 在 `hipixel-core/` 下初始化 Cargo workspace（与 pyproject.toml 共存）
- [ ] 🔴 配置 CI 矩阵新增 `windows-2022` / `ubuntu-22.04` Rust 测试 job
- [ ] 🔴 引入 PyO3（Python 绑定）+ UniFFI（Swift / Kotlin 绑定）
- [ ] 🔴 配置 `cargo fmt` + `clippy` + `cargo test` 门控
- [ ] 🟡 配置 `cargo deny`（依赖许可证检查）

### 2.5.2 视频 I/O Rust 化（Day 3-7）

- [ ] 🔴 FFmpeg 系统库检测 / 静态链接（`ffmpeg-sys-next` crate）
- [ ] 🔴 视频解码器 Rust 实现（H.264 / H.265 软解）
- [ ] 🔴 视频编码器 Rust 实现（H.264 / H.265 软编）
- [ ] 🔴 帧格式转换（YUV ↔ RGB ↔ tensor，Rust 侧）
- [ ] 🟡 VideoToolbox 硬解硬编 Rust 封装（macOS）
- [ ] 🟡 NVDEC / NVENC Rust 封装（NVIDIA）

### 2.5.3 GPU 后端抽象层 Rust 化（Day 8-12）

- [ ] 🔴 定义 `InferenceBackend` trait（load_model / run / cleanup）
- [ ] 🔴 ONNX Runtime Rust 绑定（`ort` crate）
- [ ] 🟡 CoreML 后端 Rust 封装（macOS，通过 `objc2`）
- [ ] 🟡 CUDA 后端 Rust 封装（`cudarc` crate）
- [ ] 🔴 GPU 自动检测模块（Rust 侧，替换 Python 版本）

### 2.5.4 Python / Swift 绑定（Day 13-16）

- [ ] 🔴 PyO3 暴露 `enhance()` / `Pipeline` / `Preset` 接口
- [ ] 🔴 Python 层切换为调用 Rust 内核（CLI / Worker 无感知）
- [ ] 🔴 UniFFI 生成 Swift binding（`.swift` + `.h`）
- [ ] 🔴 Swift Package 封装（供 HiVideo 使用）
- [ ] 🟡 Python wheels 构建（maturin / manylinux）

### 2.5.5 一致性验证（Day 17-21）

- [ ] 🔴 同一段视频，Python 纯版 vs Rust 内核版 PSNR/SSIM 差值 ≤ 0.5dB
- [ ] 🔴 性能对比：Rust 视频 I/O 比 Python ffmpeg-python 快 ≥ 2×
- [ ] 🟡 内存占用对比
- [ ] 🟡 更新性能基准文档

---

## Phase 3 · HiVideo AI 入场（6 周）🔴

> **前置 UI 已就绪**：画质增强浮窗 / 音频增强浮窗 / 字幕菜单（Phase 0.5）
> **前置代码**：Phase 2.5 Swift binding 完成

### 3.0 设计走查（Day 1）
- [ ] 🔴 画质 / 音频浮窗设计稿评审通过
- [ ] 🔴 自然语言搜索结果 UI 设计稿确认
- [ ] 🟡 实时性能仪表样式 token 化

### 3.1 AIKit 框架（Week 1）

- [ ] 🔴 定义 AI 任务模型 / 队列 / 优先级
- [ ] 🔴 后台任务调度器（充电 + 锁屏优先）
- [ ] 🔴 模型管理器（按需下载 / 卸载）
- [ ] 🟡 进度通知系统

### 3.2 智能字幕 Whisper（Week 2-3）

- [ ] 🔴 集成 whisper.cpp（Metal 加速）
- [ ] 🔴 模型下载（small / medium / large 按需）
- [ ] 🔴 音轨提取 → Whisper → SRT
- [ ] 🟡 词级时间戳
- [ ] 🟡 自动语种检测
- [ ] 🟡 翻译到目标语种
- [ ] 🟡 ⌘J 一键生成快捷键

### 3.3 实时画质增强（Week 3-4）

- [ ] 🔴 通过 hipixel-core Swift binding 接入
- [ ] 🔴 播放器右下角 ✨ 入口
- [ ] 🔴 滤镜浮窗 UI
- [ ] 🟡 智能预设自动决策
- [ ] 🟡 实时性能仪表
- [ ] 🟡 温控感知降级
- [ ] 🟡 续航模式

### 3.4 智能音量（Week 5）

- [ ] 🔴 EBU R128 离线扫描
- [ ] 🔴 实时增益归一化
- [ ] 🔴 Demucs Lite 对话增强
- [ ] 🔴 深夜模式动态压限器
- [ ] 🟡 ⌘⇧M 深夜模式快捷键
- [ ] 🟡 设备 EQ 预设
- [ ] 🟢 AirPods 空间音频

### 3.5 自动分类（Week 6）

- [ ] 🔴 集成 CLIP Core ML
- [ ] 🔴 关键帧抽取 + 嵌入
- [ ] 🔴 HDBSCAN 聚类
- [ ] 🟡 类别名 LLM 生成
- [ ] 🟡 媒体库智能分组 UI

### 3.6 自然语言搜索（Week 6）

- [ ] 🔴 sqlite-vec 向量检索集成
- [ ] 🔴 文本嵌入 → 相似度查询
- [ ] 🔴 ⌘F 搜索框扩展
- [ ] 🟡 结果展示：缩略图 + 高亮片段

---

## Phase 4 · HiPixel 分布式 + Windows（4 周）🟡

> **前置 UI 已就绪**：Windows 安装向导 / 系统托盘 / 配对码弹窗（Phase 0.5）

### 4.0 设计走查（Day 1）
- [ ] 🟡 Windows 安装向导四步设计稿评审
- [ ] 🟡 系统托盘菜单交互稿确认

### 4.1 多用户与配额（Week 1）

- [ ] 🟡 用户体系（邮箱 / OAuth）
- [ ] 🟡 配额限制（GPU 分钟 / 文件大小 / 并发）
- [ ] 🟡 团队 / 项目分组
- [ ] 🟡 自部署关闭注册模式

### 4.2 Worker 集群化（Week 2）

- [ ] 🟡 多 Worker 横向扩展
- [ ] 🟡 任务亲和（HDR→NVIDIA / 番剧→Apple）
- [ ] 🟡 优先级队列（付费 > 免费）
- [ ] 🟡 K8s Helm chart

### 4.3 Windows 一键安装包（Week 3）

- [ ] 🔴 PyInstaller 打包入口程序
- [ ] 🔴 内置 Redis embedded + SQLite
- [ ] 🔴 GPU 检测 + 后端按需拉取
- [ ] 🔴 系统托盘 UI（暂停 / 队列 / 退出）
- [ ] 🟡 mDNS 局域网广播
- [ ] 🟡 EV Code Signing
- [ ] 🟡 自动更新（Sparkle for Windows 风格）

### 4.4 GPU 后端完善（Week 3-4）

- [ ] 🔴 TensorRT FP16 集成（RTX 30/40/50）
- [ ] 🟡 DirectML 集成（AMD / Intel）
- [ ] 🟡 NVENC / AMF / Quick Sync 硬编码
- [ ] 🟡 一致性测试（PSNR/SSIM 差 ≤ 0.5dB）

### 4.5 公网访问（Week 4）

- [ ] 🟡 WireGuard / Tailscale 集成指南
- [ ] 🟡 HTTPS + JWT 严格鉴权
- [ ] 🟡 私密模式（处理完即删）

---

## Phase 5 · 智能管家（4 周）🟡

> **前置 UI 已就绪**：角色侧边栏 / 角色详情页（Phase 0.5，已有原型）

### 5.0 设计走查（Day 1）
- [ ] 🟡 未知角色命名弹窗设计稿
- [ ] 🟡 误聚类拆分流程设计稿
- [ ] 🟡 视频摘要展示样式
- [ ] 🟡 智能跳过提示 toast 样式

### 5.1 角色识别（Week 1-2）

- [ ] 🟡 RetinaFace + ArcFace 真人脸识别
- [ ] 🟡 AnimeFace 动漫角色识别
- [ ] 🟡 OSNet 全身 ReID
- [ ] 🟡 pyannote 声纹识别
- [ ] 🟡 字幕实体识别
- [ ] 🟡 多模态加权融合
- [ ] 🟡 增量聚类 + 跨视频合并
- [ ] 🟡 命名三层来源（TMDB / 字幕 / 用户）

### 5.2 角色 UI（Week 2）

- [ ] 🟡 媒体库左侧"角色"分组
- [ ] 🟡 角色头像墙
- [ ] 🟡 角色详情页（Hero + 出场视频 + 时间轴）
- [ ] 🟡 关联角色 / 同框频率
- [ ] 🟢 角色高光集锦

### 5.3 视频摘要（Week 3）

- [ ] 🟡 关键帧抽取 + LLM 摘要
- [ ] 🟡 章节列表（含时间戳）
- [ ] 🟡 30 秒高光片段
- [ ] 🟡 ⌘U 快捷键

### 5.4 智能跳过（Week 4）

- [ ] 🟡 片头/片尾候选检测
- [ ] 🟡 学习用户跳过行为
- [ ] 🟡 提示式跳过 + 取消按钮

---

## Phase 6 · 字幕子系统（3 周）🟡

> **前置 UI 已就绪**：字幕编辑器三栏 / 在线搜索结果列表（Phase 0.5）

### 6.0 设计走查（Day 1）
- [ ] 🟡 字幕编辑器三栏布局设计稿
- [ ] 🟡 字幕样式设置浮窗
- [ ] 🟡 双语模式 + 词典悬停交互

### 6.1 在线下载（Week 1）

- [ ] 🟡 OpenSubtitles API 集成
- [ ] 🟡 射手 / Assrt API 集成
- [ ] 🟡 文件哈希匹配
- [ ] 🟡 IMDB / TMDB ID 匹配
- [ ] 🟡 候选列表 UI

### 6.2 AI 对齐管线（Week 1-2）

- [ ] 🟡 长度 / 帧率快速检查
- [ ] 🟡 Whisper 锚点 + DTW 对齐
- [ ] 🟡 静默检测对齐
- [ ] 🟡 互相关偏移
- [ ] 🟡 LLM 段落级映射（翻译版）
- [ ] 🟡 融合评分 + 一致性校验

### 6.3 字幕编辑器（Week 2-3）

- [ ] 🟡 三栏布局：列表 / 预览 / 波形
- [ ] 🟡 整体偏移（⌘[ ⌘]）
- [ ] 🟡 帧率拉伸
- [ ] 🟡 单条编辑 / 拆分 / 合并
- [ ] 🟡 AI 修订（LLM 错别字 / 翻译润色）

### 6.4 多轨与样式（Week 3）

- [ ] 🟡 多字幕轨道管理
- [ ] 🟡 双语模式
- [ ] 🟢 词典悬停（插件）
- [ ] 🟡 ASS 高级样式
- [ ] 🟢 5 种风格预设

---

## Phase 7 · 网盘 + 副本管理（4 周）🟡

> **前置 UI 已就绪**：添加网盘向导 / 副本选择弹窗 / 网盘诊断面板（Phase 0.5）

### 7.0 设计走查（Day 1）
- [ ] 🟡 添加 SMB 网盘 4 步向导设计稿
- [ ] 🟡 副本选择弹窗正稿（PRD 阶段已有原型）
- [ ] 🟡 网盘诊断面板布局
- [ ] 🟡 重复管理面板（自动 / 候选 / 申诉 三 Tab）

### 7.1 P0 网盘协议（Week 1-2）

- [ ] 🟡 SMB v2/v3 集成
- [ ] 🟡 WebDAV / WebDAV+HTTPS
- [ ] 🟡 NFS v3/v4
- [ ] 🟢 AFP
- [ ] 🟡 DLNA / UPnP 发现
- [ ] 🟡 Jellyfin API
- [ ] 🟢 Plex API（只读）
- [ ] 🟢 Emby API

### 7.2 流播策略（Week 2）

- [ ] 🟡 直接流式 + Range 请求
- [ ] 🟡 智能预取 60s
- [ ] 🟡 离线缓存 LRU
- [ ] 🟢 服务端转码协商（Jellyfin/Plex）

### 7.3 网盘 UI（Week 3）

- [ ] 🟡 添加网盘向导
- [ ] 🟡 凭据 Keychain 存储
- [ ] 🟡 侧边栏挂载点
- [ ] 🟡 网盘诊断面板

### 7.4 多副本合并（Week 3-4）

- [ ] 🟡 Variant 数据模型重构
- [ ] 🟡 内容指纹（头中尾 SHA256）
- [ ] 🟡 帧 pHash
- [ ] 🟡 音频指纹（Chromaprint）
- [ ] 🟡 加权融合判定
- [ ] 🟡 重复管理面板（自动 / 候选 / 申诉）

### 7.5 副本选择弹窗（Week 4）

- [ ] 🟡 多副本操作弹窗组件
- [ ] 🟡 网盘能力矩阵
- [ ] 🟡 网盘禁移五道防线
- [ ] 🟡 失败兜底 + 待重试队列

---

## Phase 8 · 远程节点联动（3 周）🟡

> **前置 UI 已就绪**：算力节点设置页 / 配对码弹窗（Phase 0.5）

### 8.0 设计走查（Day 1）
- [ ] 🟡 算力节点列表 + 状态详情设计稿
- [ ] 🟡 节点配对流程（4 步）UI
- [ ] 🟡 任务路由选择器（AI 按钮旁的 ⚙）
- [ ] 🟡 多节点池 dashboard（如做 P1）

### 8.1 节点发现（Week 1）

- [ ] 🟡 mDNS 服务广播 `_hipixel._tcp.local`
- [ ] 🟡 Bonjour 客户端集成
- [ ] 🟡 节点候选列表 UI

### 8.2 配对与信任（Week 1-2）

- [ ] 🟡 一次性配对码生成
- [ ] 🟡 DH 密钥交换
- [ ] 🟡 mTLS 证书签发
- [ ] 🟡 Keychain 凭据存储
- [ ] 🟡 信任吊销 + 审计日志

### 8.3 任务路由（Week 2）

- [ ] 🟡 路由决策器（任务大小 × 网络 × 偏好）
- [ ] 🟡 文件传输三策略（上传 / 共享网盘 / 节点直拉）
- [ ] 🟡 进度回报合并
- [ ] 🟡 故障自动降级

### 8.4 多节点池（Week 3）

- [ ] 🟢 节点池统一管理
- [ ] 🟢 「快/省/近」标签调度
- [ ] 🟢 手动钉选
- [ ] 🟢 故障转移

### 8.5 与 Variant 整合（Week 3）

- [ ] 🟡 远程任务输出作为新 Variant
- [ ] 🟡 ✨ AI 修复徽章
- [ ] 🟡 来源节点名称显示

---

## Phase 9 · 扩展插件 + 系统集成（4 周）🟢

### 9.0 设计走查（Day 1）
- [ ] 🟢 插件市场 / 已安装插件管理页
- [ ] 🟢 插件权限授权弹窗
- [ ] 🟢 设置中心信息架构最终化

### 9.1 插件 SDK（Week 1-2）

- [ ] 🟢 JavaScriptCore 沙箱
- [ ] 🟢 Swift 沙箱二进制
- [ ] 🟢 生命周期 Hook
- [ ] 🟢 注入点 API
- [ ] 🟢 权限模型

### 9.2 首发插件（Week 2-3）

- [ ] 🟢 TMDB 元数据
- [ ] 🟢 Bangumi
- [ ] 🟢 弹幕（B 站 / NicoNico）
- [ ] 🟢 AirPlay 增强
- [ ] 🟢 Trakt 同步
- [ ] 🟢 Subtitles.org

### 9.3 系统集成（Week 3-4）

- [ ] 🟢 Spotlight 索引
- [ ] 🟢 服务菜单
- [ ] 🟢 触控板手势
- [ ] 🟢 通知中心
- [ ] 🟢 快捷指令
- [ ] 🟢 iCloud Drive 同步

### 9.4 资源管理高级（Week 4）

- [ ] 🟢 重复文件检测
- [ ] 🟢 磁盘空间面板
- [ ] 🟢 文件完整性校验
- [ ] 🟢 配置备份恢复

---

## Phase 10 · 打磨 + 上线（4 周）🟡

### 10.0 全局 UI 走查（Week 1）
- [ ] 🟡 设计稿 vs 实际实现差异清单
- [ ] 🟡 高频路径打磨（启动 / 播放 / 增强 / 设置）
- [ ] 🟡 暗色模式逐页核查
- [ ] 🟡 国际化文案（中 / 英）
- [ ] 🟡 高分辨率适配（4K / 5K 屏）
- [ ] 🟡 辅助功能审计（VoiceOver / 键盘聚焦 / 字号缩放）

### 10.1 性能优化（Week 1-2）

- [ ] 🟡 内存占用收敛
- [ ] 🟡 启动时间优化
- [ ] 🟡 大库性能测试（5000+ 视频）
- [ ] 🟡 长时间播放稳定性
- [ ] 🟡 GPU 温控压力测试

### 10.2 文档与官网（Week 2-3）

- [ ] 🟡 用户文档
- [ ] 🟡 API 参考
- [ ] 🟡 插件开发指南
- [ ] 🟡 官网着陆页
- [ ] 🟡 介绍视频

### 10.3 上架准备（Week 3-4）

- [ ] 🟡 App Store 沙盒适配（如选 MAS 路径）
- [ ] 🟡 公证 + 签名
- [ ] 🟡 截图 + 描述 + 关键词
- [ ] 🟡 隐私政策 / 用户协议
- [ ] 🟡 Beta 招募

### 10.4 发布（Week 4）

- [ ] 🟡 v1.0 发布
- [ ] 🟡 公关稿件
- [ ] 🟡 社区运营启动
- [ ] 🟡 用户反馈收集渠道

---

## 🎯 关键里程碑

- [ ] 🚩 **M1**：hipixel-core CLI 跑通 demo（Phase 0 末，第 3 周）
- [ ] 🚩 **M0.5**：UI 设计稿冻结（Phase 0.5 末，第 6 周）
- [ ] 🚩 **M2**：HiVideo MVP 能播视频（Phase 1 末，第 12 周）
- [ ] 🚩 **M3**：HiPixel Web 跑通端到端（Phase 2 末，第 17 周）
- [ ] 🚩 **M3.5**：hipixel-core Rust 内核 + Swift binding 完成（Phase 2.5 末，第 20 周）
- [ ] 🚩 **M4**：HiVideo AI 字幕 + 画质增强可用（Phase 3 末，第 26 周）
- [ ] 🚩 **M5**：HiPixel Windows 安装包发布（Phase 4 末，第 30 周）
- [ ] 🚩 **M6**：HiVideo 角色识别可用（Phase 5 末，第 34 周）
- [ ] 🚩 **M7**：HiVideo Beta 公开（Phase 7 末，第 44 周）
- [ ] 🚩 **M8**：HiVideo + HiPixel 联动可用（Phase 8 末，第 47 周）
- [ ] 🚩 **M9**：v1.0 正式发布（Phase 10 末，第 52 周）

> 注：Phase 0 与 Phase 0.5 大部分并行，里程碑周数按串行最大值计算。Phase 2.5 Rust 迁移为 Phase 3 的强前置依赖。

---

## 📌 待决策（不要忘）

- [ ] ❓ HiVideo 是否上 Mac App Store？影响插件审核 + Whisper 模型大小
- [ ] ❓ 付费模式：买断 / 订阅 / 免费 + AI 增强订阅 / 完全开源
- [ ] ❓ 是否做 iOS / iPadOS 配套？Catalyst 还是原生 iOS
- [ ] ❓ HiPixel 商业化：纯开源 / 开源核心 + SaaS / 商业闭源
- [ ] ❓ 插件市场审核：早期人工 vs 社区开放
- [ ] ❓ 品牌系列化：是否扩展 HiAudio / HiSub 等

---

## 📝 使用方法

1. 完成一项 → 把 `[ ]` 改成 `[x]`
2. 阶段完成 → 把"⏸ 未开始"改成"✅ 完成"，更新完成度
3. 遇到阻塞 → 标记 ⚠ 并在备注里写原因
4. 决策后 → 在"待决策"区域勾选并写下结论
5. 每完成一个 Phase → 在工作日志记录回顾
